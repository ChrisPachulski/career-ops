/**
 * tracker-parse.mjs — shared header-aware column mapping and row parsing for
 * applications.md readers (dedup-tracker.mjs, merge-tracker.mjs,
 * verify-pipeline.mjs).
 *
 * The applications.md table supports two layouts:
 *   - 9-column:  | # | Date | Company | Role | Score | Status | PDF | Report | Notes |
 *   - 10-column: | # | Date | Company | Role | Location | Score | Status | PDF | Report | Notes |
 *
 * Column position therefore isn't reliable across trackers — an inserted
 * Location column would shift every index after Role. Detecting columns by
 * header NAME instead keeps every reader in lockstep regardless of layout.
 */

// Fixed-position fallback for trackers with no recognizable header row
// (matches the original 9-column layout: | # | Date | Company | Role | Score | Status | PDF | Report | Notes |).
export const LEGACY_COLMAP = { num: 1, date: 2, company: 3, role: 4, score: 5, status: 6, pdf: 7, report: 8, notes: 9 };

const HEADER_ALIASES = {
  '#': 'num', 'num': 'num', 'date': 'date', 'company': 'company', 'empresa': 'company',
  'role': 'role', 'puesto': 'role', 'location': 'location', 'score': 'score',
  'status': 'status', 'pdf': 'pdf', 'report': 'report', 'notes': 'notes',
};

/**
 * Scan tracker lines for a header row and map column names to their index.
 *
 * A line qualifies as the header row when it starts with `|` and contains
 * both a "company" and a "role" cell (case-insensitive). Only recognized
 * aliases (HEADER_ALIASES) are mapped; unknown header cells are ignored so an
 * extra/custom column doesn't break detection of the rest.
 *
 * @param {string[]} allLines - Full applications.md content split into lines.
 * @returns {object|null} Column-name-to-index map, or null when no header row
 *   with the minimum required columns (num, company, role, score, status) is found.
 */
export function detectColumns(allLines) {
  for (const line of allLines) {
    if (!line.startsWith('|')) continue;
    const cells = line.split('|').map(s => s.trim().toLowerCase());
    if (!cells.includes('company') || !cells.includes('role')) continue;
    const map = {};
    cells.forEach((c, i) => { if (HEADER_ALIASES[c] != null) map[HEADER_ALIASES[c]] = i; });
    if (['num', 'company', 'role', 'score', 'status'].every(k => map[k] != null)) return map;
  }
  return null;
}

/**
 * Resolve the column map for a tracker file, always returning a usable map.
 *
 * Wraps detectColumns() with the LEGACY_COLMAP fallback so callers never have
 * to null-check the result themselves.
 *
 * @param {string[]} allLines - Full applications.md content split into lines.
 * @returns {object} Column-name-to-index map (detected header map, or LEGACY_COLMAP).
 */
export function resolveColumns(allLines) {
  return detectColumns(allLines) || LEGACY_COLMAP;
}

/**
 * Parse one Markdown applications.md table row into a tracker row object.
 *
 * Header/separator rows and rows without a valid positive tracker number
 * return null. `location` and `notes` default to '' when the layout doesn't
 * include those optional columns.
 *
 * @param {string} line - One line from applications.md.
 * @param {object} colmap - Column-name-to-index map (from resolveColumns/detectColumns).
 * @returns {object|null} Parsed tracker row `{num, date, company, role, location,
 *   score, status, pdf, report, notes}`, or null for non-data rows.
 */
export function parseTrackerRow(line, colmap) {
  if (!line.startsWith('|')) return null;
  const parts = line.split('|').map(s => s.trim());
  const maxIdx = Math.max(...Object.values(colmap));
  if (parts.length <= maxIdx) return null;
  const num = parseInt(parts[colmap.num]);
  if (isNaN(num) || num <= 0) return null;
  return {
    num,
    date: parts[colmap.date],
    company: parts[colmap.company],
    role: parts[colmap.role],
    location: colmap.location != null ? parts[colmap.location] : '',
    score: parts[colmap.score],
    status: parts[colmap.status],
    pdf: parts[colmap.pdf],
    report: parts[colmap.report],
    notes: colmap.notes != null ? (parts[colmap.notes] || '') : '',
  };
}
