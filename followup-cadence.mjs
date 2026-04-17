#!/usr/bin/env node
/**
 * followup-cadence.mjs — Follow-up cadence tracker over the DuckDB store.
 *
 * Joins applications × follow_ups and classifies each actionable application
 * (Applied / Responded / Interview) by urgency. Replaces the old
 * markdown+follow-ups.md parser with a CTE + CASE over date arithmetic.
 *
 * Cadence rules:
 *   Applied,   no follow-up,      days_since >= APPLIED_FIRST           -> overdue
 *   Applied,   >=1 follow-ups,    days_since_last_fu >= 7               -> overdue
 *   Applied,   >= APPLIED_MAX_FU  follow-ups total                      -> cold
 *   Responded, days_since_app == 0                                      -> urgent
 *   Responded, days_since_app >= 3                                      -> overdue
 *   Interview, days_since_app >= 1                                      -> overdue (thank-you)
 *   otherwise                                                           -> waiting
 *
 * Run: node followup-cadence.mjs              (JSON)
 *      node followup-cadence.mjs --summary    (human-readable)
 *      node followup-cadence.mjs --overdue-only
 *      node followup-cadence.mjs --applied-days 10
 */

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

const args = process.argv.slice(2);
const summaryMode = args.includes('--summary');
const overdueOnly = args.includes('--overdue-only');
const appliedDaysIdx = args.indexOf('--applied-days');
const APPLIED_FIRST = appliedDaysIdx !== -1 ? parseInt(args[appliedDaysIdx + 1]) || 7 : 7;
const APPLIED_MAX_FU = 2;

async function main() {
  if (!existsSync(DB_PATH)) {
    console.error(`No database at ${DB_PATH}`);
    process.exit(1);
  }
  const db = await Database.create(DB_PATH);

  const rows = await db.all(`
    WITH fu AS (
      SELECT application_id,
             count(*) AS fu_count,
             max(follow_up_date) AS last_fu_date
      FROM follow_ups
      GROUP BY application_id
    ),
    joined AS (
      SELECT a.id, a.company, a.role,
             strftime(a.applied_date, '%Y-%m-%d') AS applied_date,
             CAST(a.status AS VARCHAR) AS status,
             a.notes,
             coalesce(fu.fu_count, 0) AS followup_count,
             CASE WHEN fu.last_fu_date IS NOT NULL
                  THEN strftime(fu.last_fu_date, '%Y-%m-%d')
                  ELSE NULL END AS last_followup_date,
             date_diff('day', a.applied_date, current_date) AS days_since_app,
             date_diff('day', fu.last_fu_date, current_date) AS days_since_last_fu
      FROM applications a
      LEFT JOIN fu ON fu.application_id = a.id
      WHERE a.status IN ('Applied','Responded','Interview')
    )
    SELECT *,
      CASE
        WHEN status = 'Applied'   AND followup_count >= ? THEN 'cold'
        WHEN status = 'Applied'   AND followup_count = 0 AND days_since_app >= ? THEN 'overdue'
        WHEN status = 'Applied'   AND followup_count > 0 AND days_since_last_fu >= 7 THEN 'overdue'
        WHEN status = 'Responded' AND days_since_app <= 0 THEN 'urgent'
        WHEN status = 'Responded' AND days_since_app >= 3 THEN 'overdue'
        WHEN status = 'Interview' AND days_since_app >= 1 THEN 'overdue'
        ELSE 'waiting'
      END AS urgency
    FROM joined
    ORDER BY applied_date
  `, APPLIED_MAX_FU, APPLIED_FIRST);

  const result = rows.map(r => ({
    id: Number(r.id),
    company: r.company,
    role: r.role,
    applied_date: r.applied_date,
    status: r.status,
    followup_count: Number(r.followup_count),
    last_followup_date: r.last_followup_date,
    days_since_app: Number(r.days_since_app),
    days_since_last_fu: r.days_since_last_fu != null ? Number(r.days_since_last_fu) : null,
    urgency: r.urgency,
    notes: r.notes,
  }));

  const filtered = overdueOnly
    ? result.filter(r => r.urgency === 'overdue' || r.urgency === 'urgent')
    : result;

  await db.close();

  if (summaryMode) {
    const urgencyOrder = ['urgent', 'overdue', 'waiting', 'cold'];
    const byUrg = {};
    for (const r of filtered) (byUrg[r.urgency] ||= []).push(r);
    console.log('\nFollow-up cadence:');
    for (const urg of urgencyOrder) {
      const list = byUrg[urg] || [];
      if (list.length === 0) continue;
      console.log(`\n  ${urg.toUpperCase()} (${list.length})`);
      for (const r of list) {
        console.log(`    #${r.id} ${r.company} — ${r.role} (${r.status}, applied ${r.applied_date}, ${r.days_since_app}d ago, ${r.followup_count} fu)`);
      }
    }
    const totals = Object.entries(byUrg).map(([k, v]) => `${k}=${v.length}`).join(', ');
    console.log(`\n  Totals: ${totals || 'none'}`);
  } else {
    console.log(JSON.stringify(filtered, null, 2));
  }
}

main().catch(err => {
  console.error('Fatal:', err?.message || err);
  process.exit(1);
});
