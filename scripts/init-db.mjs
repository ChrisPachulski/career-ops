#!/usr/bin/env node
// Initializes data/career-ops.duckdb with full schema.
// Idempotent: safe to run against an existing DB (skips objects that already exist).

import { Database } from 'duckdb-async';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';

const CAREER_OPS = dirname(dirname(fileURLToPath(import.meta.url)));
const DB_PATH = join(CAREER_OPS, 'data', 'career-ops.duckdb');

if (!existsSync(join(CAREER_OPS, 'data'))) {
  mkdirSync(join(CAREER_OPS, 'data'), { recursive: true });
}

const ENUMS = [
  `CREATE TYPE application_status AS ENUM (
    'Evaluated','Applied','Responded','Interview','Offer','Rejected','Discarded','SKIP'
  )`,
  `CREATE TYPE scan_status AS ENUM ('new','seen','added','skipped','closed')`,
  `CREATE TYPE legitimacy_tier AS ENUM ('verified','likely','unverified','suspicious','ghost')`,
  `CREATE TYPE verification_mode AS ENUM ('playwright','webfetch','unconfirmed','manual')`,
];

const SEQUENCES = [
  'CREATE SEQUENCE applications_id_seq START 1',
  'CREATE SEQUENCE reports_id_seq START 1',
  'CREATE SEQUENCE star_stories_id_seq START 1',
  'CREATE SEQUENCE interview_prep_id_seq START 1',
  'CREATE SEQUENCE pdfs_id_seq START 1',
  'CREATE SEQUENCE follow_ups_id_seq START 1',
];

const TABLES = [
  `CREATE TABLE scan_history (
    url VARCHAR PRIMARY KEY,
    scan_date DATE NOT NULL,
    portal VARCHAR NOT NULL,
    title VARCHAR,
    company VARCHAR,
    location VARCHAR,
    status scan_status NOT NULL DEFAULT 'new',
    first_seen_at TIMESTAMP NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  `CREATE TABLE pipeline (
    url VARCHAR PRIMARY KEY,
    company VARCHAR,
    title VARCHAR,
    source VARCHAR,
    jd_local_path VARCHAR,
    added_at TIMESTAMP NOT NULL DEFAULT now(),
    processed_at TIMESTAMP,
    processed_status VARCHAR,
    application_id INTEGER
  )`,

  `CREATE TABLE applications (
    id INTEGER PRIMARY KEY DEFAULT nextval('applications_id_seq'),
    applied_date DATE NOT NULL,
    company VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    score DECIMAL(3,1) CHECK (score IS NULL OR (score >= 0 AND score <= 5)),
    status application_status NOT NULL DEFAULT 'Evaluated',
    url VARCHAR,
    pipeline_url VARCHAR,
    batch_id VARCHAR,
    archetype VARCHAR,
    tldr VARCHAR,
    remote VARCHAR,
    comp VARCHAR,
    legitimacy legitimacy_tier,
    has_pdf BOOLEAN NOT NULL DEFAULT FALSE,
    pdf_id INTEGER,
    latest_report_id INTEGER,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  `CREATE TABLE reports (
    id INTEGER PRIMARY KEY DEFAULT nextval('reports_id_seq'),
    seq_num INTEGER NOT NULL UNIQUE,
    application_id INTEGER,
    company_slug VARCHAR NOT NULL,
    report_date DATE NOT NULL,
    url VARCHAR,
    batch_id VARCHAR,
    archetype VARCHAR,
    tldr VARCHAR,
    remote VARCHAR,
    comp VARCHAR,
    legitimacy legitimacy_tier,
    verification verification_mode NOT NULL DEFAULT 'playwright',
    score DECIMAL(3,1) CHECK (score IS NULL OR (score >= 0 AND score <= 5)),
    body TEXT NOT NULL,
    is_latest BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  `CREATE TABLE star_stories (
    id INTEGER PRIMARY KEY DEFAULT nextval('star_stories_id_seq'),
    title VARCHAR NOT NULL,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    reflection TEXT,
    tags VARCHAR[],
    first_used_report_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  `CREATE TABLE interview_prep (
    id INTEGER PRIMARY KEY DEFAULT nextval('interview_prep_id_seq'),
    application_id INTEGER NOT NULL,
    company VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  // pdfs: metadata for PDFs that live on the filesystem at output/{filename}.
  // The blob column is nullable because duckdb-async on Windows crashes when
  // binding binary Buffers > ~100 bytes (STATUS_STACK_BUFFER_OVERRUN). v1
  // keeps PDFs on disk only and records filename/byte_size/sha256 here so
  // the Go dashboard can find them and detect drift.
  `CREATE TABLE pdfs (
    id INTEGER PRIMARY KEY DEFAULT nextval('pdfs_id_seq'),
    application_id INTEGER,
    filename VARCHAR NOT NULL UNIQUE,
    blob BLOB,
    byte_size INTEGER NOT NULL,
    sha256 VARCHAR,
    generated_at TIMESTAMP NOT NULL DEFAULT now()
  )`,

  `CREATE TABLE follow_ups (
    id INTEGER PRIMARY KEY DEFAULT nextval('follow_ups_id_seq'),
    application_id INTEGER NOT NULL,
    follow_up_date DATE NOT NULL,
    channel VARCHAR,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT now()
  )`,
];

const INDEXES = [
  'CREATE UNIQUE INDEX applications_company_role_uniq ON applications(lower(company), lower(role))',
  'CREATE INDEX idx_scan_history_date ON scan_history(scan_date)',
  'CREATE INDEX idx_scan_history_company ON scan_history(lower(company))',
  `CREATE INDEX idx_pipeline_pending ON pipeline(processed_at)`,
  'CREATE INDEX idx_pipeline_company ON pipeline(lower(company))',
  'CREATE INDEX idx_applications_status ON applications(status)',
  'CREATE INDEX idx_applications_date ON applications(applied_date)',
  'CREATE INDEX idx_applications_score ON applications(score)',
  'CREATE INDEX idx_reports_application ON reports(application_id)',
  'CREATE INDEX idx_reports_latest ON reports(application_id, is_latest)',
  'CREATE INDEX idx_reports_date ON reports(report_date)',
];

const POST_SETUP = [
  'INSTALL fts',
  'LOAD fts',
  `PRAGMA create_fts_index('reports', 'id', 'body', 'tldr', 'archetype', overwrite=1)`,
];

async function indexExists(db, name) {
  try {
    const rows = await db.all(
      `SELECT index_name FROM duckdb_indexes() WHERE lower(index_name) = lower(?)`,
      name
    );
    return rows.length > 0;
  } catch {
    return false;
  }
}

async function runSafe(db, statement, label) {
  // For index creation, pre-check existence to avoid DuckDB's corrupted error message
  const indexMatch = statement.match(/CREATE (?:UNIQUE )?INDEX (\w+)/i);
  if (indexMatch) {
    if (await indexExists(db, indexMatch[1])) {
      console.log(`  skip ${label} (already exists)`);
      return;
    }
  }

  try {
    await db.all(statement);
    console.log(`  ok  ${label}`);
  } catch (e) {
    const msg = String(e?.message ?? '');
    const isAlreadyExists =
      e?.errorType === 'Catalog' ||
      msg.includes('already exists') ||
      msg.includes('Duplicate name');
    if (isAlreadyExists) {
      console.log(`  skip ${label} (already exists)`);
    } else {
      console.error(`  FAIL ${label}: errorType=${e?.errorType} msg=${JSON.stringify(msg)}`);
      throw e;
    }
  }
}

async function main() {
  console.log(`Initializing ${DB_PATH}`);
  const db = await Database.create(DB_PATH);

  console.log('\n[1/5] ENUMs');
  for (const stmt of ENUMS) {
    const name = stmt.match(/CREATE TYPE (\w+)/i)[1];
    await runSafe(db, stmt, name);
  }

  console.log('\n[2/5] Sequences');
  for (const stmt of SEQUENCES) {
    const name = stmt.match(/CREATE SEQUENCE (\w+)/i)[1];
    await runSafe(db, stmt, name);
  }

  console.log('\n[3/5] Tables');
  for (const stmt of TABLES) {
    const m = stmt.match(/CREATE (?:TABLE|UNIQUE INDEX)\s+(?:IF NOT EXISTS\s+)?(\w+)/i);
    const name = m ? m[1] : '(unknown)';
    await runSafe(db, stmt, name);
  }

  console.log('\n[4/5] Indexes');
  for (const stmt of INDEXES) {
    const m = stmt.match(/CREATE INDEX (\w+)/i);
    const name = m ? m[1] : '(unknown)';
    await runSafe(db, stmt, name);
  }

  console.log('\n[5/5] FTS extension + index');
  for (const stmt of POST_SETUP) {
    await runSafe(db, stmt, stmt.slice(0, 40));
  }

  console.log('\nTables present:');
  const tables = await db.all(`SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name`);
  for (const t of tables) console.log(`  - ${t.table_name}`);

  await db.close();
  console.log(`\nInitialization complete: ${DB_PATH}`);
}

main().catch(err => {
  console.error('\nFatal:', err);
  process.exit(1);
});
