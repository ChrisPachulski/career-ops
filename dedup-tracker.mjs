#!/usr/bin/env node
/**
 * dedup-tracker.mjs — Remove duplicate applications from the DuckDB tracker.
 *
 * The unique index (lower(company), lower(role)) prevents exact duplicates at
 * insert time. This script detects FUZZY duplicates — same company + roles
 * with strong word overlap — and merges them.
 *
 * For each cluster: keeps the row with highest score. If a loser has a more
 * advanced status (Applied > Evaluated, Interview > Applied, etc.), promotes
 * the winner's status. Merges notes. Deletes losers.
 *
 * Run: node dedup-tracker.mjs [--dry-run]
 */

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { withLock } from './scripts/lockfile.mjs';

const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');
const DRY_RUN = process.argv.includes('--dry-run');

// Higher rank = more advanced in pipeline. Applied > Rejected because active > terminal.
const STATUS_RANK = {
  'SKIP': 0, 'Discarded': 0,
  'Rejected': 1, 'Evaluated': 2,
  'Applied': 3, 'Responded': 4,
  'Interview': 5, 'Offer': 6,
};

function normalizeRole(role) {
  return role.toLowerCase()
    .replace(/[()]/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/[^a-z0-9 /]/g, '')
    .trim();
}

function rolesMatch(a, b) {
  const wordsA = normalizeRole(a).split(/\s+/).filter(w => w.length > 3);
  const wordsB = normalizeRole(b).split(/\s+/).filter(w => w.length > 3);
  const overlap = wordsA.filter(w => wordsB.some(wb => wb.includes(w) || w.includes(wb)));
  return overlap.length >= 2;
}

async function main() {
  const db = await Database.create(DB_PATH);

  // Group by company
  const byCompany = await db.all(`
    SELECT lower(company) AS ck, list(id) AS ids
    FROM applications
    GROUP BY ck
    HAVING count(*) > 1
  `);

  if (byCompany.length === 0) {
    console.log('No companies with multiple applications.');
    await db.close();
    return;
  }

  const clusters = [];
  for (const { ids } of byCompany) {
    const idList = ids.map(Number);
    const rows = await db.all(
      `SELECT id, company, role, score, CAST(status AS VARCHAR) AS status, notes
       FROM applications WHERE id IN (${idList.map(() => '?').join(',')})`,
      ...idList
    );
    const clustered = new Set();
    for (let i = 0; i < rows.length; i++) {
      if (clustered.has(rows[i].id)) continue;
      const group = [rows[i]];
      for (let j = i + 1; j < rows.length; j++) {
        if (clustered.has(rows[j].id)) continue;
        if (rolesMatch(rows[i].role, rows[j].role)) group.push(rows[j]);
      }
      if (group.length > 1) {
        for (const g of group) clustered.add(g.id);
        clusters.push(group);
      }
    }
  }

  if (clusters.length === 0) {
    console.log('No fuzzy duplicates.');
    await db.close();
    return;
  }

  console.log(`Found ${clusters.length} duplicate clusters:`);
  for (const c of clusters) {
    console.log(`  Company: ${c[0].company}`);
    for (const row of c) console.log(`    #${row.id} ${row.role} (${row.status}, score=${row.score})`);
  }

  if (DRY_RUN) {
    console.log('\n(dry run — no changes)');
    await db.close();
    return;
  }

  await withLock(async () => {
    for (const cluster of clusters) {
      const sorted = [...cluster].sort((a, b) => {
        const sa = Number(a.score ?? -1);
        const sb = Number(b.score ?? -1);
        return sb - sa;
      });
      const winner = sorted[0];
      const losers = sorted.slice(1);
      let bestStatus = winner.status;
      let bestRank = STATUS_RANK[bestStatus] ?? 0;
      const mergedNotes = [winner.notes, ...losers.map(l => `[merged from #${l.id}] ${l.notes ?? ''}`.trim())]
        .filter(Boolean)
        .join('; ');
      for (const loser of losers) {
        const rank = STATUS_RANK[loser.status] ?? 0;
        if (rank > bestRank) { bestStatus = loser.status; bestRank = rank; }
      }
      await db.run('BEGIN TRANSACTION');
      try {
        await db.run(
          `UPDATE applications SET status = ?::application_status, notes = ?, updated_at = now() WHERE id = ?`,
          bestStatus, mergedNotes, winner.id
        );
        const loserIds = losers.map(l => l.id);
        await db.run(
          `DELETE FROM applications WHERE id IN (${loserIds.map(() => '?').join(',')})`,
          ...loserIds
        );
        // Also drop any reports associated with losers (they're orphaned)
        await db.run(
          `DELETE FROM reports WHERE application_id IN (${loserIds.map(() => '?').join(',')})`,
          ...loserIds
        );
        await db.run('COMMIT');
        console.log(`  merged: kept #${winner.id} (status=${bestStatus}), deleted ${loserIds.map(i => '#'+i).join(', ')}`);
      } catch (e) {
        await db.run('ROLLBACK');
        console.error(`  ERROR merging cluster: ${e.message}`);
      }
    }
  }, { reason: 'dedup-tracker' });

  await db.close();
  console.log(`\nDone. ${clusters.length} clusters processed.`);
}

main().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
