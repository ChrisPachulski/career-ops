// Lockfile helpers for serializing DuckDB writes across scan/merge/ingest scripts.
// DuckDB allows single writer per file; these helpers ensure scripts cooperate.

import { writeFileSync, readFileSync, unlinkSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const CAREER_OPS = dirname(dirname(fileURLToPath(import.meta.url)));
const LOCK_PATH = join(CAREER_OPS, 'data', '.career-ops.lock');
const STALE_THRESHOLD_MS = 60_000;
const DEFAULT_TIMEOUT_MS = 30_000;
const POLL_INTERVAL_MS = 100;

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function readLock() {
  if (!existsSync(LOCK_PATH)) return null;
  try {
    const raw = readFileSync(LOCK_PATH, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function isStale(lock) {
  if (!lock) return true;
  const age = Date.now() - lock.acquired_at;
  return age > STALE_THRESHOLD_MS;
}

export async function acquireLock({ timeoutMs = DEFAULT_TIMEOUT_MS, reason = '' } = {}) {
  const deadline = Date.now() + timeoutMs;
  const myLock = { pid: process.pid, acquired_at: Date.now(), reason };

  while (Date.now() < deadline) {
    const existing = readLock();
    if (!existing || isStale(existing)) {
      try {
        writeFileSync(LOCK_PATH, JSON.stringify(myLock, null, 2), { flag: 'w' });
        const readBack = readLock();
        if (readBack && readBack.pid === process.pid && readBack.acquired_at === myLock.acquired_at) {
          return myLock;
        }
      } catch (e) {
        // Race: another process wrote between our read and write.
      }
    }
    await sleep(POLL_INTERVAL_MS);
  }
  const blocker = readLock();
  throw new Error(`Lock acquire timeout after ${timeoutMs}ms. Blocker: ${JSON.stringify(blocker)}`);
}

export function releaseLock(myLock) {
  const existing = readLock();
  if (!existing) return;
  if (existing.pid !== myLock.pid || existing.acquired_at !== myLock.acquired_at) {
    return;
  }
  try {
    unlinkSync(LOCK_PATH);
  } catch {
    // already gone
  }
}

export async function withLock(fn, opts = {}) {
  const lock = await acquireLock(opts);
  try {
    return await fn();
  } finally {
    releaseLock(lock);
  }
}
