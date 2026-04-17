#!/usr/bin/env node
/**
 * verify-pipeline.mjs — Health check for the DuckDB-backed career-ops pipeline.
 *
 * DuckDB constraints enforce most invariants at write time:
 *   - status column is an ENUM (invalid values rejected)
 *   - score is DECIMAL(3,1) with CHECK 0 <= score <= 5
 *   - (lower(company), lower(role)) is UNIQUE
 *   - primary/foreign keys prevent most structural corruption
 *
 * This script checks the invariants DuckDB cannot enforce:
 *   1. Fuzzy duplicates (company+role match after more aggressive normalization)
 *   2. latest_report_id points to an extant report
 *   3. Pipeline rows marked processed have a valid application_id
 *   4. Report seq_nums are contiguous-ish (no huge gaps suggesting lost data)
 *
 * Run: node verify-pipeline.mjs
 */

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

let errors = 0;
let warnings = 0;

function error(msg) { console.log(`[ERR] ${msg}`); errors++; }
function warn(msg) { console.log(`[WARN] ${msg}`); warnings++; }
function ok(msg) { console.log(`[OK] ${msg}`); }

async function main() {
  if (!existsSync(DB_PATH)) {
    console.log(`No database found at ${DB_PATH}. Run: node scripts/init-db.mjs`);
    process.exit(0);
  }
  const db = await Database.create(DB_PATH);

  const [{ appCount }] = await db.all('SELECT count(*) AS appCount FROM applications');
  const [{ reportCount }] = await db.all('SELECT count(*) AS reportCount FROM reports');
  const [{ pipelineCount }] = await db.all('SELECT count(*) AS pipelineCount FROM pipeline');
  const [{ scanCount }] = await db.all('SELECT count(*) AS scanCount FROM scan_history');

  console.log('');
  console.log(`Database: ${Number(appCount)} applications, ${Number(reportCount)} reports, ${Number(pipelineCount)} pipeline, ${Number(scanCount)} scan-history`);
  console.log('');

  // 1. Fuzzy duplicate company+role clusters (unique index handles exact; this catches near-dupes)
  const dupes = await db.all(`
    SELECT
      lower(regexp_replace(company, '[^a-zA-Z0-9]', '', 'g')) AS ck,
      lower(regexp_replace(role, '[^a-zA-Z0-9 ]', '', 'g')) AS rk,
      count(*) AS n,
      list(id) AS ids
    FROM applications
    GROUP BY ck, rk
    HAVING n > 1
  `);
  if (dupes.length === 0) {
    ok('No fuzzy duplicates');
  } else {
    for (const d of dupes) warn(`Possible duplicate cluster: "${d.ck}::${d.rk}" IDs=${d.ids}`);
  }

  // 2. Orphan latest_report_id
  const orphans = await db.all(`
    SELECT a.id, a.company, a.role, a.latest_report_id
    FROM applications a
    LEFT JOIN reports r ON r.id = a.latest_report_id
    WHERE a.latest_report_id IS NOT NULL AND r.id IS NULL
  `);
  if (orphans.length === 0) {
    ok('All latest_report_id pointers valid');
  } else {
    for (const o of orphans) error(`#${o.id} ${o.company}: latest_report_id=${o.latest_report_id} missing`);
  }

  // 3. Pipeline inconsistencies
  const pipeOrphans = await db.all(`
    SELECT count(*) AS n
    FROM pipeline
    WHERE processed_at IS NOT NULL AND application_id IS NULL
  `);
  if (Number(pipeOrphans[0].n) === 0) {
    ok('All processed pipeline rows linked to applications');
  } else {
    warn(`${pipeOrphans[0].n} pipeline rows marked processed but missing application_id (run reconcile-tracker)`);
  }

  // 4. Report sequence gaps
  const gaps = await db.all(`
    WITH ordered AS (
      SELECT seq_num, lag(seq_num) OVER (ORDER BY seq_num) AS prev_seq
      FROM reports
    )
    SELECT seq_num, prev_seq, (seq_num - prev_seq) AS gap
    FROM ordered
    WHERE prev_seq IS NOT NULL AND (seq_num - prev_seq) > 10
  `);
  if (gaps.length === 0) {
    ok('No large gaps in report sequence');
  } else {
    for (const g of gaps) warn(`Report seq_num jump: ${g.prev_seq} -> ${g.seq_num} (gap=${g.gap})`);
  }

  // 5. Applications missing a URL but with score (odd data)
  const scoreNoUrl = await db.all(`
    SELECT count(*) AS n FROM applications WHERE score IS NOT NULL AND url IS NULL
  `);
  if (Number(scoreNoUrl[0].n) === 0) {
    ok('All scored applications have a URL');
  } else {
    warn(`${scoreNoUrl[0].n} scored applications missing URL`);
  }

  console.log('');
  console.log('='.repeat(50));
  console.log(`Pipeline health: ${errors} errors, ${warnings} warnings`);
  if (errors === 0 && warnings === 0) {
    console.log('Pipeline is clean');
  } else if (errors === 0) {
    console.log('Pipeline OK with warnings');
  } else {
    console.log('Pipeline has errors — fix before proceeding');
  }

  await db.close();
  process.exit(errors > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
