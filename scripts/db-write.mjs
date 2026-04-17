#!/usr/bin/env node
// Central ingester CLI for the career-ops DuckDB database.
// All writes go through this script so they share lockfile + transaction semantics.
//
// Subcommands:
//   insert-pipeline    --url URL --company C --title T --source S [--jd-local-path P]
//   upsert-scan-history --url URL --portal P --title T --company C --location L --status S --date YYYY-MM-DD
//   scan-commit        --json /tmp/scan-batch.json     (batch insert of pipeline + scan_history rows)
//   insert-report      --file reports/NNN-slug-date.md (parses header, upserts application + report)
//   upsert-application --json /tmp/app.json
//   insert-story       --file interview-prep/story-bank.md (parses last story block)
//   upsert-interview-prep --file interview-prep/{company}-{role}.md
//   insert-pdf         --application-id N --file output/cv-foo.pdf
//   drain-queue        --dir batch/ingest-queue
//   refresh-dashboard-json
//   render-markdown    [applications|pipeline|all]
//   query              --sql "SELECT ..."              (read-only ad-hoc query, returns JSON)

import { Database } from 'duckdb-async';
import { readFileSync, writeFileSync, existsSync, statSync, readdirSync, unlinkSync, mkdirSync } from 'fs';
import { join, dirname, basename } from 'path';
import { fileURLToPath } from 'url';
import { createHash } from 'crypto';
import { withLock } from './lockfile.mjs';

const SCRIPTS_DIR = dirname(fileURLToPath(import.meta.url));
const CAREER_OPS = dirname(SCRIPTS_DIR);
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');
const DASHBOARD_JSON = join(CAREER_OPS, 'data', 'dashboard.json');
const APPLICATIONS_MD = join(CAREER_OPS, 'data', 'applications.md');
const PIPELINE_MD = join(CAREER_OPS, 'data', 'pipeline.md');

const CANONICAL_STATUSES = ['Evaluated', 'Applied', 'Responded', 'Interview', 'Offer', 'Rejected', 'Discarded', 'SKIP'];
const STATUS_ALIASES = {
  hold: 'Evaluated',
  sent: 'Applied',
  skip: 'SKIP',
  monitor: 'SKIP',
  'geo blocker': 'SKIP',
};

function normalizeStatus(raw) {
  if (!raw) return null;
  const trimmed = String(raw).replace(/\*\*/g, '').trim();
  for (const c of CANONICAL_STATUSES) {
    if (trimmed.toLowerCase() === c.toLowerCase()) return c;
  }
  const aliased = STATUS_ALIASES[trimmed.toLowerCase()];
  if (aliased) return aliased;
  return null;
}

// ── Argument parsing ────────────────────────────────────────────────────────

function parseArgs(argv) {
  const [command, ...rest] = argv;
  const flags = {};
  const positional = [];
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    if (arg.startsWith('--')) {
      const body = arg.slice(2);
      const eqIdx = body.indexOf('=');
      if (eqIdx >= 0) {
        // --key=value form
        flags[body.slice(0, eqIdx)] = body.slice(eqIdx + 1);
      } else {
        // --key [value] form
        const key = body;
        const next = rest[i + 1];
        if (next !== undefined && !next.startsWith('--')) {
          flags[key] = next;
          i++;
        } else {
          flags[key] = true;
        }
      }
    } else {
      positional.push(arg);
    }
  }
  return { command, flags, positional };
}

// ── Report parser ───────────────────────────────────────────────────────────

const HEADER_PATTERNS = {
  date: /^\*\*Date:\*\*\s*(\S+)/m,
  url: /^\*\*URL:\*\*\s*(https?:\/\/\S+)/m,
  archetype: /^\*\*Archetype:\*\*\s*(.+)$/m,
  score: /^\*\*Score:\*\*\s*([\d.]+)\s*\/\s*5/m,
  legitimacy: /^\*\*Legitimacy:\*\*\s*(.+)$/m,
  pdf: /^\*\*PDF:\*\*\s*(.+)$/m,
  batchId: /^\*\*Batch ID:\*\*\s*(\d+)/m,
  verification: /^\*\*Verification:\*\*\s*(.+)$/m,
  tldr: /^\*\*TL;DR:\*\*\s*(.+)$/m,
  remote: /^\*\*Remote:\*\*\s*(.+)$/m,
  comp: /^\*\*Comp:\*\*\s*(.+)$/m,
};

const BLOCK_A_PATTERNS = {
  tldr: /\|\s*TL;DR\s*\|\s*(.+?)\s*\|/,
  archetype: /\|\s*Archetype\s*\|\s*(.+?)\s*\|/,
  remote: /\|\s*Remote\s*\|\s*(.+?)\s*\|/,
  comp: /\|\s*Comp\s*\|\s*(.+?)\s*\|/i,
};

const LEGITIMACY_MAP = {
  'high confidence': 'verified',
  'verified': 'verified',
  'proceed with caution': 'likely',
  'likely': 'likely',
  'suspicious': 'suspicious',
  'unverified': 'unverified',
  'ghost': 'ghost',
};

function normalizeLegitimacy(raw) {
  if (!raw) return null;
  const lower = String(raw).toLowerCase().trim();
  for (const [key, val] of Object.entries(LEGITIMACY_MAP)) {
    if (lower.includes(key)) return val;
  }
  return 'unverified';
}

function parseTitleLine(firstLine) {
  // "# Evaluation: {Company} -- {Role}"  or  "# Evaluation: {Company} - {Role}"
  const m = firstLine.match(/^#\s*(?:Evaluation|Eval):\s*(.+?)\s*(?:--|—|-)\s*(.+?)$/);
  if (!m) return { company: null, role: null };
  return { company: m[1].trim(), role: m[2].trim() };
}

function parseFilename(filename) {
  // "NNN-slug-YYYY-MM-DD.md"
  const base = basename(filename, '.md');
  const m = base.match(/^(\d+)-(.+)-(\d{4}-\d{2}-\d{2})$/);
  if (!m) return { seqNum: null, companySlug: null, dateStr: null };
  return { seqNum: parseInt(m[1], 10), companySlug: m[2], dateStr: m[3] };
}

function parseReport(path) {
  const body = readFileSync(path, 'utf-8');
  const lines = body.split('\n');
  const firstLine = lines[0] || '';
  const { company, role } = parseTitleLine(firstLine);
  const { seqNum, companySlug, dateStr } = parseFilename(path);

  const extractHeader = (re) => {
    const m = body.match(re);
    return m ? m[1].trim() : null;
  };

  const date = extractHeader(HEADER_PATTERNS.date) || dateStr;
  const url = extractHeader(HEADER_PATTERNS.url);
  const scoreStr = extractHeader(HEADER_PATTERNS.score);
  const score = scoreStr ? parseFloat(scoreStr) : null;
  const legitimacyRaw = extractHeader(HEADER_PATTERNS.legitimacy);
  const legitimacy = normalizeLegitimacy(legitimacyRaw);
  const pdfRaw = extractHeader(HEADER_PATTERNS.pdf);
  const batchId = extractHeader(HEADER_PATTERNS.batchId);
  const verification = extractHeader(HEADER_PATTERNS.verification);

  const archetype =
    extractHeader(HEADER_PATTERNS.archetype) ||
    (body.match(BLOCK_A_PATTERNS.archetype)?.[1] ?? null);
  const tldr =
    extractHeader(HEADER_PATTERNS.tldr) ||
    (body.match(BLOCK_A_PATTERNS.tldr)?.[1] ?? null);
  const remote =
    extractHeader(HEADER_PATTERNS.remote) ||
    (body.match(BLOCK_A_PATTERNS.remote)?.[1] ?? null);
  const comp =
    extractHeader(HEADER_PATTERNS.comp) ||
    (body.match(BLOCK_A_PATTERNS.comp)?.[1] ?? null);

  return {
    seqNum, companySlug, date, company, role,
    url, score, archetype, tldr, remote, comp,
    legitimacy, batchId, verification, pdfRaw,
    body,
  };
}

// ── Subcommand handlers ─────────────────────────────────────────────────────

async function cmdInsertPipeline(db, flags) {
  const { url, company, title, source = 'manual', 'jd-local-path': jdLocalPath = null } = flags;
  if (!url) throw new Error('--url required');
  await db.run(
    `INSERT INTO pipeline (url, company, title, source, jd_local_path)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT (url) DO UPDATE SET
       company = excluded.company,
       title = excluded.title,
       source = excluded.source,
       jd_local_path = excluded.jd_local_path`,
    url, company ?? null, title ?? null, source, jdLocalPath
  );
  console.log(`pipeline: ${url}`);
}

async function cmdUpsertScanHistory(db, flags) {
  const { url, portal, title = null, company = null, location = null, status = 'new', date } = flags;
  if (!url || !portal || !date) throw new Error('--url --portal --date required');
  await db.run(
    `INSERT INTO scan_history (url, scan_date, portal, title, company, location, status)
     VALUES (?, ?, ?, ?, ?, ?, ?::scan_status)
     ON CONFLICT (url) DO UPDATE SET
       last_seen_at = now(),
       status = excluded.status,
       portal = excluded.portal,
       title = coalesce(excluded.title, scan_history.title),
       company = coalesce(excluded.company, scan_history.company),
       location = coalesce(excluded.location, scan_history.location)`,
    url, date, portal, title, company, location, status
  );
  console.log(`scan_history: ${url}`);
}

async function cmdScanCommit(db, flags) {
  const { json } = flags;
  if (!json) throw new Error('--json path required');
  const payload = JSON.parse(readFileSync(json, 'utf-8'));
  const { pipeline = [], scan_history = [] } = payload;
  await db.run('BEGIN TRANSACTION');
  try {
    for (const p of pipeline) {
      await db.run(
        `INSERT INTO pipeline (url, company, title, source, jd_local_path)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT (url) DO NOTHING`,
        p.url, p.company ?? null, p.title ?? null, p.source ?? 'scan', p.jd_local_path ?? null
      );
    }
    for (const s of scan_history) {
      await db.run(
        `INSERT INTO scan_history (url, scan_date, portal, title, company, location, status)
         VALUES (?, ?, ?, ?, ?, ?, ?::scan_status)
         ON CONFLICT (url) DO UPDATE SET
           last_seen_at = now(),
           status = excluded.status`,
        s.url, s.scan_date, s.portal, s.title ?? null, s.company ?? null, s.location ?? null, s.status ?? 'added'
      );
    }
    await db.run('COMMIT');
    console.log(`scan_commit: ${pipeline.length} pipeline + ${scan_history.length} history rows`);
  } catch (e) {
    await db.run('ROLLBACK');
    throw e;
  }
}

// insertReportCore performs the applications + reports + pipeline mutations
// for a parsed report. It does NOT manage transactions -- the caller decides
// whether to wrap it in BEGIN/COMMIT (single-file ingest: cmdInsertReport)
// or fold it into a larger transaction (batch drain: cmdDrainQueue).
async function insertReportCore(db, parsed) {
  // Upsert application (use company+role unique key)
  const existingApp = await db.all(
    `SELECT id FROM applications WHERE lower(company) = lower(?) AND lower(role) = lower(?)`,
    parsed.company, parsed.role
  );

  let applicationId;
  if (existingApp.length > 0) {
    applicationId = existingApp[0].id;
    await db.run(
      `UPDATE applications SET
         applied_date = ?,
         score = ?,
         url = coalesce(?, url),
         archetype = coalesce(?, archetype),
         tldr = coalesce(?, tldr),
         remote = coalesce(?, remote),
         comp = coalesce(?, comp),
         legitimacy = coalesce(?::legitimacy_tier, legitimacy),
         batch_id = coalesce(?, batch_id),
         updated_at = now()
       WHERE id = ?`,
      parsed.date, parsed.score, parsed.url, parsed.archetype,
      parsed.tldr, parsed.remote, parsed.comp, parsed.legitimacy,
      parsed.batchId, applicationId
    );
  } else {
    const row = await db.all(
      `INSERT INTO applications (
         applied_date, company, role, score, status, url, archetype, tldr, remote, comp,
         legitimacy, batch_id
       ) VALUES (?, ?, ?, ?, 'Evaluated', ?, ?, ?, ?, ?, ?::legitimacy_tier, ?)
       RETURNING id`,
      parsed.date, parsed.company, parsed.role, parsed.score, parsed.url,
      parsed.archetype, parsed.tldr, parsed.remote, parsed.comp, parsed.legitimacy,
      parsed.batchId
    );
    applicationId = row[0].id;
  }

  // Mark prior reports as not-latest
  await db.run(
    `UPDATE reports SET is_latest = FALSE WHERE application_id = ?`,
    applicationId
  );

  // Insert new report
  const reportRow = await db.all(
    `INSERT INTO reports (
       seq_num, application_id, company_slug, report_date, url, batch_id, archetype,
       tldr, remote, comp, legitimacy, verification, score, body, is_latest
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::legitimacy_tier, ?::verification_mode, ?, ?, TRUE)
     ON CONFLICT (seq_num) DO UPDATE SET
       application_id = excluded.application_id,
       body = excluded.body,
       score = excluded.score,
       tldr = excluded.tldr,
       archetype = excluded.archetype,
       remote = excluded.remote,
       comp = excluded.comp,
       legitimacy = excluded.legitimacy,
       is_latest = TRUE
     RETURNING id`,
    parsed.seqNum, applicationId, parsed.companySlug, parsed.date, parsed.url,
    parsed.batchId, parsed.archetype, parsed.tldr, parsed.remote, parsed.comp,
    parsed.legitimacy, (parsed.verification || 'playwright').toLowerCase(),
    parsed.score, parsed.body
  );
  const reportId = reportRow[0].id;

  await db.run(
    `UPDATE applications SET latest_report_id = ? WHERE id = ?`,
    reportId, applicationId
  );

  // Close out matching pipeline row if URL matches
  if (parsed.url) {
    await db.run(
      `UPDATE pipeline SET processed_at = now(), processed_status = 'evaluated', application_id = ?
       WHERE url = ?`,
      applicationId, parsed.url
    );
  }

  return { applicationId, reportId, seqNum: parsed.seqNum };
}

async function cmdInsertReport(db, flags) {
  const { file } = flags;
  if (!file) throw new Error('--file required');
  if (!existsSync(file)) throw new Error(`File not found: ${file}`);

  const parsed = parseReport(file);
  if (!parsed.company || !parsed.role) {
    throw new Error(`Could not parse company/role from first line of ${file}. Expected "# Evaluation: {Company} -- {Role}".`);
  }
  if (!parsed.seqNum) {
    throw new Error(`Could not parse sequence number from filename ${file}. Expected "NNN-slug-YYYY-MM-DD.md".`);
  }

  await db.run('BEGIN TRANSACTION');
  try {
    const { applicationId, reportId, seqNum } = await insertReportCore(db, parsed);
    await db.run('COMMIT');
    console.log(`insert-report: application=${applicationId} report=${reportId} seq_num=${seqNum}`);
  } catch (e) {
    await db.run('ROLLBACK');
    throw e;
  }
}

async function cmdUpdateStatus(db, flags) {
  const { id: idRaw, status } = flags;
  if (!idRaw || !status) throw new Error('--id and --status required');
  const appId = parseInt(idRaw, 10);
  const normalized = normalizeStatus(status);
  if (!normalized) throw new Error(`Unknown status: ${status}`);
  await db.run('BEGIN TRANSACTION');
  try {
    await db.run(
      `UPDATE applications SET status = ?::application_status, updated_at = now() WHERE id = ?`,
      normalized, appId
    );
    await db.run('COMMIT');
    console.log(`update-status: id=${appId} status=${normalized}`);
  } catch (e) {
    await db.run('ROLLBACK');
    throw e;
  }
}

async function cmdUpsertApplication(db, flags) {
  const { json } = flags;
  if (!json) throw new Error('--json required');
  const p = JSON.parse(readFileSync(json, 'utf-8'));
  const status = normalizeStatus(p.status) || 'Evaluated';
  const existing = await db.all(
    `SELECT id FROM applications WHERE lower(company) = lower(?) AND lower(role) = lower(?)`,
    p.company, p.role
  );
  if (existing.length > 0) {
    await db.run(
      `UPDATE applications SET
         status = ?::application_status,
         score = coalesce(?, score),
         notes = coalesce(?, notes),
         url = coalesce(?, url),
         updated_at = now()
       WHERE id = ?`,
      status, p.score ?? null, p.notes ?? null, p.url ?? null, existing[0].id
    );
    console.log(`updated application ${existing[0].id}`);
  } else {
    const row = await db.all(
      `INSERT INTO applications (applied_date, company, role, status, score, url, notes)
       VALUES (?, ?, ?, ?::application_status, ?, ?, ?)
       RETURNING id`,
      p.applied_date || new Date().toISOString().slice(0, 10),
      p.company, p.role, status, p.score ?? null, p.url ?? null, p.notes ?? null
    );
    console.log(`inserted application ${row[0].id}`);
  }
}

async function cmdInsertPdf(db, flags) {
  const { 'application-id': appIdRaw, file } = flags;
  if (!appIdRaw || !file) throw new Error('--application-id and --file required');
  const appId = parseInt(appIdRaw, 10);
  if (!existsSync(file)) throw new Error(`File not found: ${file}`);
  const buf = readFileSync(file);
  const sha256 = createHash('sha256').update(buf).digest('hex');
  const filename = basename(file);

  // PDFs are stored on the filesystem at output/{filename}. We record
  // metadata (filename, byte_size, sha256) in the pdfs table but NOT the
  // bytes themselves. Binding large binary Buffers via duckdb-async on
  // Windows crashes the Node process silently (STATUS_STACK_BUFFER_OVERRUN).
  // The Go dashboard reconstructs the PDF path as `${careerOpsPath}/output/${filename}`.
  const blobMarker = null;

  // Ensure the column allows NULL (idempotent; older DBs may have it NOT NULL).
  try {
    await db.run(`ALTER TABLE pdfs ALTER COLUMN blob DROP NOT NULL`);
  } catch (_) {
    // Already nullable, or column already in desired state.
  }

  await db.run('BEGIN TRANSACTION');
  try {
    const row = await db.all(
      `INSERT INTO pdfs (application_id, filename, blob, byte_size, sha256)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT (filename) DO UPDATE SET
         blob = excluded.blob,
         byte_size = excluded.byte_size,
         sha256 = excluded.sha256,
         generated_at = now()
       RETURNING id`,
      appId, filename, blobMarker, buf.length, sha256
    );
    await db.run(
      `UPDATE applications SET pdf_id = ?, has_pdf = TRUE, updated_at = now() WHERE id = ?`,
      row[0].id, appId
    );
    await db.run('COMMIT');
    console.log(`insert-pdf: pdf_id=${row[0].id} app=${appId} filename=${filename} bytes=${buf.length} (metadata only, bytes live at output/${filename})`);
  } catch (e) {
    await db.run('ROLLBACK');
    throw e;
  }
}

async function cmdInsertStory(db, flags) {
  const { json } = flags;
  if (!json) throw new Error('--json required');
  const p = JSON.parse(readFileSync(json, 'utf-8'));
  const row = await db.all(
    `INSERT INTO star_stories (title, situation, task, action, result, reflection, tags, first_used_report_id)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
     RETURNING id`,
    p.title, p.situation ?? null, p.task ?? null, p.action ?? null,
    p.result ?? null, p.reflection ?? null,
    p.tags ?? [], p.first_used_report_id ?? null
  );
  console.log(`insert-story: id=${row[0].id}`);
}

async function cmdUpsertInterviewPrep(db, flags) {
  const { file } = flags;
  if (!file) throw new Error('--file required');
  const body = readFileSync(file, 'utf-8');
  const base = basename(file, '.md');
  // Filename convention: {company-slug}-{role-slug}.md — we don't try to split
  // perfectly; we store the filename components and look up the application.
  const name = base;
  const match = await db.all(
    `SELECT id, company, role FROM applications
     WHERE lower(replace(company, ' ', '-')) || '-' || lower(replace(role, ' ', '-')) LIKE ?`,
    `${name.toLowerCase()}%`
  );
  if (match.length === 0) {
    throw new Error(`Could not match interview-prep file ${file} to an application. Looked for pattern like "${name}".`);
  }
  const app = match[0];
  await db.run(
    `INSERT INTO interview_prep (application_id, company, role, body)
     VALUES (?, ?, ?, ?)`,
    app.id, app.company, app.role, body
  );
  console.log(`interview-prep: app=${app.id} (${app.company} — ${app.role})`);
}

async function cmdDrainQueue(db, flags) {
  // NOTE: `--dir` must NOT be used as a flag name -- node-pre-gyp (pulled in
  // by the duckdb native binding) prefix-matches --dir to its own --directory
  // flag and crashes on module load before our code runs. Use --queue-dir.
  const { 'queue-dir': dir = join(CAREER_OPS, 'batch', 'ingest-queue') } = flags;
  if (!existsSync(dir)) {
    console.log(`drain-queue: no queue directory at ${dir}`);
    return;
  }
  const files = readdirSync(dir).filter(f => f.endsWith('.json'));
  if (files.length === 0) {
    console.log('drain-queue: empty');
    return;
  }
  await db.run('BEGIN TRANSACTION');
  try {
    let processed = 0;
    for (const f of files) {
      const full = join(dir, f);
      const payload = JSON.parse(readFileSync(full, 'utf-8'));
      if (payload.kind === 'report' && payload.reportPath) {
        if (!existsSync(payload.reportPath)) {
          console.log(`  skip ${f}: reportPath ${payload.reportPath} missing`);
          continue;
        }
        const parsed = parseReport(payload.reportPath);
        if (!parsed.company || !parsed.role || !parsed.seqNum) {
          console.log(`  skip ${f}: header parse failed for ${payload.reportPath}`);
          continue;
        }
        const { applicationId, reportId, seqNum } = await insertReportCore(db, parsed);
        console.log(`  ${f}: application=${applicationId} report=${reportId} seq_num=${seqNum}`);
        unlinkSync(full);
        processed++;
      } else if (payload.kind === 'application') {
        // Reserved for future use
        console.log(`  skip ${f}: kind=application not yet implemented`);
      } else {
        console.log(`  skip ${f}: unknown kind`);
      }
    }
    await db.run('COMMIT');
    console.log(`drain-queue: processed ${processed}/${files.length} files`);
  } catch (e) {
    await db.run('ROLLBACK');
    throw e;
  }
}

// ── Read-only subcommands (no lock) ─────────────────────────────────────────

async function cmdRefreshDashboardJson(db) {
  const rows = await db.all(`
    SELECT a.id,
           strftime(a.applied_date, '%Y-%m-%d') AS date,
           a.company, a.role,
           CAST(a.score AS DOUBLE) AS score,
           CAST(a.status AS VARCHAR) AS status,
           a.has_pdf, a.url, a.batch_id, a.archetype, a.tldr,
           a.remote, a.comp,
           CAST(a.legitimacy AS VARCHAR) AS legitimacy,
           a.notes,
           r.seq_num AS report_num,
           r.company_slug AS report_company_slug,
           strftime(r.report_date, '%Y-%m-%d') AS report_date
    FROM applications a
    LEFT JOIN reports r ON r.id = a.latest_report_id
    ORDER BY a.id
  `);
  writeFileSync(DASHBOARD_JSON, JSON.stringify(rows, null, 2), 'utf-8');
  console.log(`dashboard.json: ${rows.length} rows → ${DASHBOARD_JSON}`);
}

function formatDate(val) {
  if (val == null) return '';
  if (val instanceof Date) return val.toISOString().slice(0, 10);
  return String(val);
}

async function cmdRenderMarkdown(db, positional) {
  const target = positional[0] || 'all';
  if (target === 'applications' || target === 'all') {
    const rows = await db.all(`
      SELECT row_number() OVER (ORDER BY applied_date, id) AS num,
             strftime(applied_date, '%Y-%m-%d') AS date, company, role,
             CAST(score AS DOUBLE) AS score,
             CAST(status AS VARCHAR) AS status,
             has_pdf, latest_report_id, notes
      FROM applications
      ORDER BY applied_date, id
    `);
    const reportMap = new Map();
    if (rows.some(r => r.latest_report_id)) {
      const reports = await db.all(
        `SELECT id, seq_num, company_slug, strftime(report_date, '%Y-%m-%d') AS report_date FROM reports`
      );
      for (const r of reports) reportMap.set(r.id, r);
    }
    const header = [
      `<!-- Generated from data/career-ops.duckdb — edit via scripts, not directly -->`,
      `# Applications Tracker`,
      ``,
      `| # | Date | Company | Role | Score | Status | PDF | Report | Notes |`,
      `|---|------|---------|------|-------|--------|-----|--------|-------|`,
    ];
    const body = rows.map(r => {
      const pdf = r.has_pdf ? '✅' : '❌';
      const rep = r.latest_report_id && reportMap.has(r.latest_report_id)
        ? reportMap.get(r.latest_report_id)
        : null;
      const report = rep
        ? `[${rep.seq_num}](reports/${String(rep.seq_num).padStart(3, '0')}-${rep.company_slug}-${rep.report_date}.md)`
        : '';
      const scoreStr = r.score != null ? `${Number(r.score).toFixed(1)}/5` : '';
      return `| ${r.num} | ${r.date} | ${r.company} | ${r.role} | ${scoreStr} | ${r.status} | ${pdf} | ${report} | ${r.notes ?? ''} |`;
    }).join('\n');
    writeFileSync(APPLICATIONS_MD, header.join('\n') + '\n' + body + '\n', 'utf-8');
    console.log(`applications.md: ${rows.length} rows → ${APPLICATIONS_MD}`);
  }
  if (target === 'pipeline' || target === 'all') {
    const rows = await db.all(`
      SELECT url, company, title, source
      FROM pipeline
      WHERE processed_at IS NULL
      ORDER BY added_at
    `);
    const header = [
      `<!-- Generated from data/career-ops.duckdb — edit via scripts, not directly -->`,
      `# Pipeline`,
      ``,
      `## Pending`,
      ``,
    ];
    const body = rows.map(r => `- [ ] ${r.url} | ${r.company ?? ''} | ${r.title ?? ''}`).join('\n');
    writeFileSync(PIPELINE_MD, header.join('\n') + body + '\n', 'utf-8');
    console.log(`pipeline.md: ${rows.length} pending → ${PIPELINE_MD}`);
  }
}

function jsonReplacer(_key, value) {
  if (typeof value === 'bigint') return Number(value);
  if (value instanceof Date) return value.toISOString();
  if (value instanceof Uint8Array || value instanceof Buffer) {
    return `[bytes:${value.length}]`;
  }
  return value;
}

async function cmdQuery(db, flags) {
  const { sql } = flags;
  if (!sql) throw new Error('--sql required');
  const rows = await db.all(sql);
  console.log(JSON.stringify(rows, jsonReplacer, 2));
}

// ── Dispatcher ──────────────────────────────────────────────────────────────

const WRITE_COMMANDS = new Set([
  'insert-pipeline', 'upsert-scan-history', 'scan-commit',
  'insert-report', 'upsert-application', 'update-status',
  'insert-pdf', 'insert-story', 'upsert-interview-prep', 'drain-queue',
  'render-markdown', 'refresh-dashboard-json',
]);

// Commands that mutate the `reports` table. DuckDB FTS is snapshot-based, so
// the index must be rebuilt after any insert/update to keep match_bm25 queries
// accurate. Rebuild is O(N) over all report bodies -- acceptable for a small
// tracker (hundreds of reports), revisit if this grows.
const REPORT_MUTATING = new Set(['insert-report', 'drain-queue']);

async function refreshReportsFtsIndex(db) {
  await db.run(
    `PRAGMA create_fts_index('reports', 'id', 'body', 'tldr', 'archetype', overwrite=1)`
  );
}

async function run() {
  const { command, flags, positional } = parseArgs(process.argv.slice(2));
  if (!command) {
    console.error('Usage: db-write.mjs <command> [flags]');
    console.error('Commands: insert-pipeline upsert-scan-history scan-commit insert-report');
    console.error('          upsert-application insert-pdf insert-story upsert-interview-prep');
    console.error('          drain-queue refresh-dashboard-json render-markdown query');
    process.exit(1);
  }

  const handlers = {
    'insert-pipeline': (db) => cmdInsertPipeline(db, flags),
    'upsert-scan-history': (db) => cmdUpsertScanHistory(db, flags),
    'scan-commit': (db) => cmdScanCommit(db, flags),
    'insert-report': (db) => cmdInsertReport(db, flags),
    'upsert-application': (db) => cmdUpsertApplication(db, flags),
    'update-status': (db) => cmdUpdateStatus(db, flags),
    'insert-pdf': (db) => cmdInsertPdf(db, flags),
    'insert-story': (db) => cmdInsertStory(db, flags),
    'upsert-interview-prep': (db) => cmdUpsertInterviewPrep(db, flags),
    'drain-queue': (db) => cmdDrainQueue(db, flags),
    'refresh-dashboard-json': (db) => cmdRefreshDashboardJson(db),
    'render-markdown': (db) => cmdRenderMarkdown(db, positional),
    'query': (db) => cmdQuery(db, flags),
  };

  const handler = handlers[command];
  if (!handler) {
    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }

  const needsLock = WRITE_COMMANDS.has(command);
  const action = async () => {
    const db = await Database.create(DB_PATH);
    try {
      await handler(db);
      // Auto-refresh derived artifacts after any write
      if (REPORT_MUTATING.has(command)) {
        await refreshReportsFtsIndex(db);
      }
      if (WRITE_COMMANDS.has(command) && command !== 'refresh-dashboard-json' && command !== 'render-markdown') {
        await cmdRefreshDashboardJson(db);
      }
    } finally {
      await db.close();
    }
  };

  if (needsLock) {
    await withLock(action, { reason: command });
  } else {
    await action();
  }
}

run().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
