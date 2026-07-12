/**
 * role-matcher.mjs — shared fuzzy role-title matcher for tracker deduplication
 *
 * dedup-tracker.mjs and merge-tracker.mjs both need to decide whether two job
 * titles for the SAME company are the same opening reworded (e.g. "Backend
 * Engineer" vs "Backend Engineer II" vs "Backend Engineer (Remote)") vs two
 * genuinely distinct roles (e.g. "Software Engineer" vs "Product Manager").
 * No fuzzy-match library is installed and none should be added here, so this
 * is a small, deterministic, dependency-free heuristic:
 *
 *   1. Normalize both titles (lowercase, strip parenthetical suffixes like
 *      "(Remote)"/"(Hybrid)", strip punctuation, collapse whitespace).
 *   2. Tokenize into words.
 *   3. Compare token sets with Jaccard similarity (intersection / union).
 *   4. Match when similarity >= MATCH_THRESHOLD.
 *
 * This is intentionally conservative — callers (dedup-tracker.mjs's roleMatch,
 * merge-tracker.mjs's duplicate-detection fallback) only use a positive match
 * to justify treating two rows as duplicates, so false positives (merging two
 * actually-distinct roles) are the costlier failure mode to guard against.
 */

// Chosen so that titles differing by one qualifier word out of two or three
// (e.g. "Backend Engineer" [2 tokens] vs "Backend Engineer II" [3 tokens] →
// intersection 2 / union 3 = 0.67) still match, while titles that share only
// a common, generic word (e.g. "Software Engineer" vs "Software Architect" →
// intersection 1 / union 3 = 0.33) do not.
const MATCH_THRESHOLD = 0.5;

// Suffixes commonly appended to job titles that don't change the role identity.
const PARENTHETICAL_RE = /\([^)]*\)/g;

/**
 * Normalize a job title into a comparable, lowercase token string.
 *
 * Strips parenthetical qualifiers (remote/hybrid/location tags), punctuation,
 * and collapses whitespace, so presentation differences don't affect matching.
 *
 * @param {string} title - Raw job title from a tracker row.
 * @returns {string} Normalized, lowercase, whitespace-collapsed title.
 */
function normalizeTitle(title) {
  return String(title ?? '')
    .toLowerCase()
    .replace(PARENTHETICAL_RE, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Split a normalized title into a set of tokens for Jaccard comparison.
 *
 * @param {string} normalized - Output of normalizeTitle().
 * @returns {Set<string>} Set of non-empty word tokens.
 */
function tokenize(normalized) {
  return new Set(normalized.split(' ').filter(Boolean));
}

/**
 * Compute Jaccard similarity (intersection / union) between two token sets.
 *
 * @param {Set<string>} a - First token set.
 * @param {Set<string>} b - Second token set.
 * @returns {number} Similarity in [0, 1]. Two empty sets are treated as
 *   identical (similarity 1) since there's no wording to disagree on.
 */
function jaccardSimilarity(a, b) {
  if (a.size === 0 && b.size === 0) return 1;
  let intersectionSize = 0;
  for (const token of a) {
    if (b.has(token)) intersectionSize++;
  }
  const unionSize = a.size + b.size - intersectionSize;
  return unionSize === 0 ? 1 : intersectionSize / unionSize;
}

/**
 * Decide whether two job titles likely refer to the same role.
 *
 * Used as a duplicate-detection signal ONLY after the caller has already
 * confirmed both rows belong to the same company — this function does not
 * consider company at all.
 *
 * @param {string} roleA - First job title.
 * @param {string} roleB - Second job title.
 * @returns {boolean} True when titles are near-duplicates (Jaccard similarity
 *   of their normalized token sets meets or exceeds MATCH_THRESHOLD).
 */
export function roleFuzzyMatch(roleA, roleB) {
  const normA = normalizeTitle(roleA);
  const normB = normalizeTitle(roleB);
  if (normA === normB) return true;
  if (!normA || !normB) return false;

  const similarity = jaccardSimilarity(tokenize(normA), tokenize(normB));
  return similarity >= MATCH_THRESHOLD;
}
