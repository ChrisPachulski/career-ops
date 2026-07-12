/**
 * tracker-links.mjs — shared report-link normalization for applications.md
 *
 * TSV additions (batch/tracker-additions/*.tsv) always carry a root-relative
 * report link, e.g. `[5](reports/5-company-role-2026-01-01.md)`, because that's
 * the simplest form for an evaluation worker to generate. applications.md itself
 * can live at two different depths — `data/applications.md` or the repo root —
 * so the same root-relative link needs different prefixes to stay clickable:
 * `../reports/...` from `data/applications.md`, `reports/...` from the root
 * layout (see #760 and the "Report link normalization" section of CLAUDE.md/AGENTS.md).
 *
 * normalizeReportLink() re-derives the correct relative path from the report's
 * filename alone, so it's idempotent regardless of what prefix the incoming
 * link already has (root-relative, already-relativized, or absolute).
 */

import { relative, join, basename } from 'path';

// Matches a Markdown report link cell/fragment: [123](anything/123-slug-date.md)
const REPORT_LINK_RE = /\[(\d+)\]\(([^)]+)\)/;

/**
 * Rewrite a Markdown report link so its path resolves relative to the tracker
 * file's own directory.
 *
 * Accepts either a bare report-link fragment (e.g. from a TSV addition's
 * `report` field) or a full pipe-delimited tracker row that happens to contain
 * one (used by the `--migrate` one-time rewrite). Any text outside the link
 * itself, and any input with no link at all, passes through unchanged.
 *
 * @param {string} input - Report cell, or a full tracker row line, that may
 *   contain a `[num](path)` Markdown link.
 * @param {string} trackerDir - Absolute directory containing applications.md.
 * @param {string} reportsRoot - Absolute directory that contains the `reports/` folder.
 * @returns {string} Input with the report link's path rewritten relative to
 *   trackerDir; unchanged if no report link is present.
 */
export function normalizeReportLink(input, trackerDir, reportsRoot) {
  if (typeof input !== 'string') return input;
  const match = input.match(REPORT_LINK_RE);
  if (!match) return input;

  const [fullMatch, num, rawPath] = match;
  const filename = basename(rawPath);
  const absoluteTarget = join(reportsRoot, 'reports', filename);
  let relativePath = relative(trackerDir, absoluteTarget);
  // Always use forward slashes in Markdown links, even on Windows.
  relativePath = relativePath.split('\\').join('/');

  const newLink = `[${num}](${relativePath})`;
  return input.slice(0, match.index) + newLink + input.slice(match.index + fullMatch.length);
}
