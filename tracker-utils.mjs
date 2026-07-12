/**
 * tracker-utils.mjs — shared helpers for reading/writing applications.md table rows
 */

/**
 * Rebuild a Markdown table row from a `line.split('|').map(s => s.trim())` parts
 * array (which carries empty leading/trailing entries from the outer pipes),
 * matching the `| a | b | c |` spacing convention used across the tracker scripts.
 */
export function rebuildRow(parts) {
  const cells = parts.slice(1, -1);
  return `| ${cells.join(' | ')} |`;
}
