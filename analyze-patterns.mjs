#!/usr/bin/env node
/**
 * analyze-patterns.mjs — Rejection-pattern detector over the DuckDB store.
 *
 * Aggregates applications + reports into outcome patterns. Everything that
 * used to require opening 150+ .md files is now a single SQL query because
 * the report header fields (archetype, remote, comp, tldr) are denormalized
 * onto the applications table.
 *
 * Run: node analyze-patterns.mjs           (JSON to stdout)
 *      node analyze-patterns.mjs --summary (human-readable)
 *      node analyze-patterns.mjs --min-threshold 3
 */

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

const args = process.argv.slice(2);
const summaryMode = args.includes('--summary');
const minIdx = args.indexOf('--min-threshold');
const MIN_THRESHOLD = minIdx !== -1 && args[minIdx + 1] !== undefined
  ? (Number.isNaN(parseInt(args[minIdx + 1])) ? 5 : parseInt(args[minIdx + 1]))
  : 5;

function jsonSafe(val) {
  if (typeof val === 'bigint') return Number(val);
  if (val instanceof Date) return val.toISOString();
  return val;
}

async function main() {
  if (!existsSync(DB_PATH)) {
    console.error(`No database at ${DB_PATH}`);
    process.exit(1);
  }
  const db = await Database.create(DB_PATH);

  const funnel = await db.all(`
    SELECT CAST(status AS VARCHAR) AS status, count(*) AS n
    FROM applications
    GROUP BY status
    ORDER BY n DESC
  `);

  const byOutcome = await db.all(`
    SELECT
      CASE
        WHEN status IN ('Interview','Offer','Responded','Applied') THEN 'positive'
        WHEN status IN ('Rejected','Discarded') THEN 'negative'
        WHEN status = 'SKIP' THEN 'self_filtered'
        ELSE 'pending'
      END AS outcome,
      count(*) AS n,
      avg(score) AS avg_score,
      min(score) AS min_score,
      max(score) AS max_score
    FROM applications
    WHERE score IS NOT NULL
    GROUP BY outcome
    ORDER BY n DESC
  `);

  const byArchetype = await db.all(`
    SELECT archetype, count(*) AS total,
           sum(CASE WHEN status IN ('Interview','Offer','Responded','Applied') THEN 1 ELSE 0 END) AS positive,
           sum(CASE WHEN status IN ('Rejected','Discarded') THEN 1 ELSE 0 END) AS negative,
           sum(CASE WHEN status = 'SKIP' THEN 1 ELSE 0 END) AS self_filtered,
           avg(score) AS avg_score
    FROM applications
    WHERE archetype IS NOT NULL
    GROUP BY archetype
    HAVING total >= ?
    ORDER BY total DESC
  `, MIN_THRESHOLD);

  const byLegitimacy = await db.all(`
    SELECT CAST(legitimacy AS VARCHAR) AS legitimacy, count(*) AS n, avg(score) AS avg_score
    FROM applications
    WHERE legitimacy IS NOT NULL
    GROUP BY legitimacy
    ORDER BY n DESC
  `);

  const byRemote = await db.all(`
    SELECT remote, count(*) AS n, avg(score) AS avg_score
    FROM applications
    WHERE remote IS NOT NULL
    GROUP BY remote
    HAVING n >= ?
    ORDER BY n DESC
  `, MIN_THRESHOLD);

  const scoreHistogram = await db.all(`
    SELECT
      CASE
        WHEN score >= 4.5 THEN '4.5+'
        WHEN score >= 4.0 THEN '4.0-4.4'
        WHEN score >= 3.5 THEN '3.5-3.9'
        WHEN score >= 3.0 THEN '3.0-3.4'
        WHEN score < 3.0 THEN '<3.0'
      END AS bucket,
      count(*) AS n
    FROM applications
    WHERE score IS NOT NULL
    GROUP BY bucket
    ORDER BY bucket DESC
  `);

  const result = {
    funnel: funnel.map(r => ({ status: r.status, n: Number(r.n) })),
    by_outcome: byOutcome.map(r => ({
      outcome: r.outcome, n: Number(r.n),
      avg_score: r.avg_score != null ? Number(r.avg_score) : null,
      min_score: r.min_score != null ? Number(r.min_score) : null,
      max_score: r.max_score != null ? Number(r.max_score) : null,
    })),
    by_archetype: byArchetype.map(r => ({
      archetype: r.archetype, total: Number(r.total),
      positive: Number(r.positive), negative: Number(r.negative),
      self_filtered: Number(r.self_filtered),
      avg_score: r.avg_score != null ? Number(r.avg_score) : null,
    })),
    by_legitimacy: byLegitimacy.map(r => ({ legitimacy: r.legitimacy, n: Number(r.n), avg_score: Number(r.avg_score) })),
    by_remote: byRemote.map(r => ({ remote: r.remote, n: Number(r.n), avg_score: Number(r.avg_score) })),
    score_histogram: scoreHistogram.map(r => ({ bucket: r.bucket, n: Number(r.n) })),
    meta: { min_threshold: MIN_THRESHOLD },
  };

  await db.close();

  if (summaryMode) {
    console.log('\nApplication funnel:');
    for (const r of result.funnel) console.log(`  ${r.status.padEnd(12)} ${r.n}`);
    console.log('\nBy outcome (scored only):');
    for (const r of result.by_outcome) console.log(`  ${r.outcome.padEnd(14)} n=${r.n} avg_score=${(r.avg_score ?? 0).toFixed(2)}`);
    console.log(`\nBy archetype (min ${MIN_THRESHOLD}):`);
    for (const r of result.by_archetype) console.log(`  ${(r.archetype || '').padEnd(40)} total=${r.total} +=${r.positive} -=${r.negative} sf=${r.self_filtered} avg=${(r.avg_score ?? 0).toFixed(2)}`);
    console.log(`\nScore histogram:`);
    for (const r of result.score_histogram) console.log(`  ${r.bucket.padEnd(10)} ${r.n}`);
  } else {
    console.log(JSON.stringify(result, jsonSafe, 2));
  }
}

main().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
