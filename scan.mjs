#!/usr/bin/env node

/**
 * scan.mjs — Zero-token portal scanner (DuckDB-backed)
 *
 * Fetches Greenhouse, Ashby, and Lever APIs directly, applies title
 * and location filters from portals.yml, deduplicates against the
 * DuckDB store, and inserts new offers into the pipeline + scan_history
 * tables in a single transaction.
 *
 * Zero Claude API tokens — pure HTTP + JSON + SQL.
 *
 * Usage:
 *   node scan.mjs                  # scan all enabled companies
 *   node scan.mjs --dry-run        # preview without writing to DB
 *   node scan.mjs --company Cohere # scan a single company
 */

import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';
import { Database } from 'duckdb-async';
import { withLock } from './scripts/lockfile.mjs';

const parseYaml = yaml.load;
const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const PORTALS_PATH = join(CAREER_OPS, 'portals.yml');
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

const CONCURRENCY = 10;
const FETCH_TIMEOUT_MS = 10_000;

// ── API detection ───────────────────────────────────────────────────

function detectApi(company) {
  if (company.api && company.api.includes('greenhouse')) {
    return { type: 'greenhouse', url: company.api };
  }

  const url = company.careers_url || '';

  const ashbyMatch = url.match(/jobs\.ashbyhq\.com\/([^/?#]+)/);
  if (ashbyMatch) {
    return {
      type: 'ashby',
      url: `https://api.ashbyhq.com/posting-api/job-board/${ashbyMatch[1]}?includeCompensation=true`,
    };
  }

  const leverMatch = url.match(/jobs\.lever\.co\/([^/?#]+)/);
  if (leverMatch) {
    return {
      type: 'lever',
      url: `https://api.lever.co/v0/postings/${leverMatch[1]}`,
    };
  }

  const ghEuMatch = url.match(/job-boards(?:\.eu)?\.greenhouse\.io\/([^/?#]+)/);
  if (ghEuMatch && !company.api) {
    return {
      type: 'greenhouse',
      url: `https://boards-api.greenhouse.io/v1/boards/${ghEuMatch[1]}/jobs`,
    };
  }

  return null;
}

// ── API parsers ─────────────────────────────────────────────────────

function parseGreenhouse(json, companyName) {
  const jobs = json.jobs || [];
  return jobs.map(j => ({
    title: j.title || '',
    url: j.absolute_url || '',
    company: companyName,
    location: j.location?.name || '',
  }));
}

function parseAshby(json, companyName) {
  const jobs = json.jobs || [];
  return jobs.map(j => ({
    title: j.title || '',
    url: j.jobUrl || '',
    company: companyName,
    location: j.location || '',
  }));
}

function parseLever(json, companyName) {
  if (!Array.isArray(json)) return [];
  return json.map(j => ({
    title: j.text || '',
    url: j.hostedUrl || '',
    company: companyName,
    location: j.categories?.location || '',
  }));
}

const PARSERS = { greenhouse: parseGreenhouse, ashby: parseAshby, lever: parseLever };

// ── Fetch with timeout ──────────────────────────────────────────────

async function fetchJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

// ── Title + location filters ────────────────────────────────────────

function buildTitleFilter(titleFilter) {
  const positive = (titleFilter?.positive || []).map(k => k.toLowerCase());
  const negative = (titleFilter?.negative || []).map(k => k.toLowerCase());

  return (title) => {
    const lower = title.toLowerCase();
    const hasPositive = positive.length === 0 || positive.some(k => lower.includes(k));
    const hasNegative = negative.some(k => lower.includes(k));
    return hasPositive && !hasNegative;
  };
}

function buildLocationFilter(locationFilter) {
  if (!locationFilter) return () => ({ pass: true });
  const accept = (locationFilter.accept_keywords || []).map(k => k.toLowerCase());
  const reject = (locationFilter.reject_keywords || []).map(k => k.toLowerCase());

  return (location) => {
    if (!location) return { pass: true, reason: 'unknown_location' };
    const lower = location.toLowerCase();
    const matchedAccept = accept.some(k => lower.includes(k));
    if (matchedAccept) return { pass: true, reason: 'accept_match' };
    const matchedReject = reject.find(k => lower.includes(k));
    if (matchedReject) return { pass: false, reason: `reject:${matchedReject}` };
    return { pass: true, reason: 'no_match' };
  };
}

// ── Dedup: load existing URLs + company/role pairs from DB ──────────

async function loadSeenSets(db) {
  const urlRows = await db.all(`
    SELECT url FROM pipeline
    UNION
    SELECT url FROM scan_history
    UNION
    SELECT url FROM applications WHERE url IS NOT NULL
  `);
  const seenUrls = new Set(urlRows.map(r => r.url));

  const crRows = await db.all(`
    SELECT lower(company) AS c, lower(title) AS r FROM pipeline
    UNION
    SELECT lower(company) AS c, lower(role) AS r FROM applications
  `);
  const seenCompanyRoles = new Set(crRows.map(r => `${r.c}::${r.r}`));

  return { seenUrls, seenCompanyRoles };
}

// ── Parallel fetch with concurrency limit ───────────────────────────

async function parallelFetch(tasks, limit) {
  const results = [];
  let i = 0;

  async function next() {
    while (i < tasks.length) {
      const task = tasks[i++];
      results.push(await task());
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => next());
  await Promise.all(workers);
  return results;
}

// ── Main ────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const companyFlag = args.indexOf('--company');
  const filterCompany = companyFlag !== -1 ? args[companyFlag + 1]?.toLowerCase() : null;

  if (!existsSync(PORTALS_PATH)) {
    console.error('Error: portals.yml not found. Run onboarding first.');
    process.exit(1);
  }

  if (!existsSync(DB_PATH)) {
    console.error(`Error: ${DB_PATH} not found. Run: node scripts/init-db.mjs`);
    process.exit(1);
  }

  const config = parseYaml(readFileSync(PORTALS_PATH, 'utf-8'));
  const companies = config.tracked_companies || [];
  const titleFilter = buildTitleFilter(config.title_filter);
  const locationFilter = buildLocationFilter(config.location_filter);

  const targets = companies
    .filter(c => c.enabled !== false)
    .filter(c => !filterCompany || c.name.toLowerCase().includes(filterCompany))
    .map(c => ({ ...c, _api: detectApi(c) }))
    .filter(c => c._api !== null);

  const skippedCount = companies.filter(c => c.enabled !== false).length - targets.length;

  console.log(`Scanning ${targets.length} companies via API (${skippedCount} skipped — no API detected)`);
  if (dryRun) console.log('(dry run — no DB writes)\n');

  const db = await Database.create(DB_PATH);
  const { seenUrls, seenCompanyRoles } = await loadSeenSets(db);

  const date = new Date().toISOString().slice(0, 10);
  let totalFound = 0;
  let totalTitleFiltered = 0;
  let totalLocationFiltered = 0;
  let totalDupes = 0;
  const newOffers = [];
  const skippedLocation = [];
  const errors = [];

  const tasks = targets.map(company => async () => {
    const { type, url } = company._api;
    try {
      const json = await fetchJson(url);
      const jobs = PARSERS[type](json, company.name);
      totalFound += jobs.length;

      for (const job of jobs) {
        if (!titleFilter(job.title)) {
          totalTitleFiltered++;
          continue;
        }
        if (seenUrls.has(job.url)) {
          totalDupes++;
          continue;
        }
        const key = `${job.company.toLowerCase()}::${job.title.toLowerCase()}`;
        if (seenCompanyRoles.has(key)) {
          totalDupes++;
          continue;
        }
        const locResult = locationFilter(job.location);
        if (!locResult.pass) {
          totalLocationFiltered++;
          skippedLocation.push({ ...job, source: `${type}-api`, reason: locResult.reason });
          seenUrls.add(job.url);
          continue;
        }
        seenUrls.add(job.url);
        seenCompanyRoles.add(key);
        newOffers.push({ ...job, source: `${type}-api` });
      }
    } catch (err) {
      errors.push({ company: company.name, error: err.message });
    }
  });

  await parallelFetch(tasks, CONCURRENCY);

  if (!dryRun && (newOffers.length > 0 || skippedLocation.length > 0)) {
    await withLock(async () => {
      await db.run('BEGIN TRANSACTION');
      try {
        for (const o of newOffers) {
          await db.run(
            `INSERT INTO pipeline (url, company, title, source, added_at)
             VALUES (?, ?, ?, ?, now())
             ON CONFLICT (url) DO NOTHING`,
            o.url, o.company, o.title, o.source
          );
          await db.run(
            `INSERT INTO scan_history (url, scan_date, portal, title, company, location, status)
             VALUES (?, ?, ?, ?, ?, ?, 'added'::scan_status)
             ON CONFLICT (url) DO UPDATE SET last_seen_at = now()`,
            o.url, date, o.source, o.title, o.company, o.location || null
          );
        }
        for (const o of skippedLocation) {
          await db.run(
            `INSERT INTO scan_history (url, scan_date, portal, title, company, location, status)
             VALUES (?, ?, ?, ?, ?, ?, 'skipped'::scan_status)
             ON CONFLICT (url) DO UPDATE SET last_seen_at = now()`,
            o.url, date, o.source, o.title, o.company, o.location || null
          );
        }
        await db.run('COMMIT');
      } catch (e) {
        await db.run('ROLLBACK');
        throw e;
      }
    }, { reason: 'scan' });
  }

  await db.close();

  console.log(`\n${'━'.repeat(45)}`);
  console.log(`Portal Scan — ${date}`);
  console.log(`${'━'.repeat(45)}`);
  console.log(`Companies scanned:        ${targets.length}`);
  console.log(`Total jobs found:         ${totalFound}`);
  console.log(`Filtered by title:        ${totalTitleFiltered} removed`);
  console.log(`Filtered by location:     ${totalLocationFiltered} rejected`);
  console.log(`Duplicates:               ${totalDupes} skipped`);
  console.log(`New offers added:         ${newOffers.length}`);

  if (errors.length > 0) {
    console.log(`\nErrors (${errors.length}):`);
    for (const e of errors) {
      console.log(`  x ${e.company}: ${e.error}`);
    }
  }

  if (newOffers.length > 0) {
    console.log('\nNew offers:');
    for (const o of newOffers) {
      console.log(`  + ${o.company} | ${o.title} | ${o.location || 'N/A'}`);
    }
    if (dryRun) {
      console.log('\n(dry run — run without --dry-run to save results)');
    } else {
      console.log(`\nResults written to ${DB_PATH} (pipeline + scan_history tables)`);
    }
  }

  console.log(`\n-> Run /career-ops pipeline to evaluate new offers.`);
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
