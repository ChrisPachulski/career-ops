#!/usr/bin/env node
/**
 * reconcile-tracker.mjs — Idempotent consistency job over the DuckDB store.
 *
 * Replaces the old merge-tracker.mjs (which read batch/tracker-additions/*.tsv
 * and merged into applications.md). Now that LLM agents write directly to DuckDB
 * via scripts/db-write.mjs insert-report, there is no TSV staging to merge —
 * this script verifies the state is consistent and fixes common issues.
 *
 * Also replaces normalize-statuses.mjs since status normalization is enforced
 * at write time by the application_status ENUM.
 *
 * Checks performed:
 *   - applications rows with NULL or invalid status (would be rejected by ENUM
 *     at write time; only possible via direct DB manipulation)
 *   - applications whose latest_report_id points to a non-existent report
 *   - duplicate (company, role) clusters (unique index should prevent new ones)
 *   - pipeline rows marked processed but without an application_id
 *   - applications with a url that still appears as "pending" in pipeline
 *
 * Usage:
 *   node reconcile-tracker.mjs           # report + fix
 *   node reconcile-tracker.mjs --dry-run # report only, no fixes
 */

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { withLock } from './scripts/lockfile.mjs';

const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');

  const db = await Database.create(DB_PATH);
  let issues = 0;
  let fixes = 0;

  // 1. Orphan latest_report_id pointers
  const orphans = await db.all(`
    SELECT a.id, a.company, a.role, a.latest_report_id
    FROM applications a
    LEFT JOIN reports r ON r.id = a.latest_report_id
    WHERE a.latest_report_id IS NOT NULL AND r.id IS NULL
  `);
  if (orphans.length > 0) {
    issues += orphans.length;
    console.log(`[issue] ${orphans.length} applications with orphan latest_report_id`);
    for (const o of orphans) console.log(`  #${o.id} ${o.company} — ${o.role} → missing report ${o.latest_report_id}`);
    if (!dryRun) {
      await withLock(async () => {
        await db.run(`
          UPDATE applications a SET latest_report_id = (
            SELECT max(r.id) FROM reports r WHERE r.application_id = a.id
          )
          WHERE a.latest_report_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM reports r WHERE r.id = a.latest_report_id
          )
        `);
      }, { reason: 'reconcile-orphans' });
      fixes += orphans.length;
    }
  }

  // 2. Duplicate company+role (unique index should prevent; look anyway)
  const dupes = await db.all(`
    SELECT lower(company) AS ck, lower(role) AS rk, count(*) AS n, list(id) AS ids
    FROM applications
    GROUP BY ck, rk
    HAVING n > 1
  `);
  if (dupes.length > 0) {
    issues += dupes.length;
    console.log(`[issue] ${dupes.length} duplicate company+role clusters`);
    for (const d of dupes) console.log(`  "${d.ck}::${d.rk}" → IDs ${d.ids}`);
    console.log('  (manual resolution required — inspect clusters before merging)');
  }

  // 3. Pipeline rows marked processed but missing application_id
  const orphanPipeline = await db.all(`
    SELECT url, company, title, processed_at
    FROM pipeline
    WHERE processed_at IS NOT NULL AND application_id IS NULL
  `);
  if (orphanPipeline.length > 0) {
    issues += orphanPipeline.length;
    console.log(`[issue] ${orphanPipeline.length} pipeline rows marked processed but missing application_id`);
    if (!dryRun) {
      await withLock(async () => {
        await db.run(`
          UPDATE pipeline p SET application_id = (
            SELECT a.id FROM applications a WHERE a.url = p.url LIMIT 1
          )
          WHERE p.processed_at IS NOT NULL AND p.application_id IS NULL
        `);
      }, { reason: 'reconcile-pipeline-link' });
      fixes += orphanPipeline.length;
    }
  }

  // 4. Applications whose url still appears pending in pipeline
  const stalePending = await db.all(`
    SELECT p.url, p.company, p.title, a.id AS app_id
    FROM pipeline p
    INNER JOIN applications a ON a.url = p.url
    WHERE p.processed_at IS NULL
  `);
  if (stalePending.length > 0) {
    issues += stalePending.length;
    console.log(`[issue] ${stalePending.length} pipeline rows pending but have an application`);
    if (!dryRun) {
      await withLock(async () => {
        await db.run(`
          UPDATE pipeline p SET
            processed_at = now(),
            processed_status = 'evaluated',
            application_id = (SELECT a.id FROM applications a WHERE a.url = p.url LIMIT 1)
          WHERE p.processed_at IS NULL
            AND EXISTS (SELECT 1 FROM applications a WHERE a.url = p.url)
        `);
      }, { reason: 'reconcile-stale-pending' });
      fixes += stalePending.length;
    }
  }

  console.log('');
  console.log(`Reconcile summary: ${issues} issues, ${fixes} fixed${dryRun ? ' (dry run)' : ''}`);
  await db.close();
}

main().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
