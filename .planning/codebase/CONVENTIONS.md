# Coding Conventions

**Analysis Date:** 2026-04-14

## Naming Patterns

**Files:**
- Node.js scripts: `snake-case.mjs` (e.g., `merge-tracker.mjs`, `generate-pdf.mjs`, `check-liveness.mjs`)
- Configuration: `snake-case.yml` (e.g., `profile.yml`, `portals.yml`, `states.yml`)
- Markdown modes: `snake-case.md` (e.g., `_shared.md`, `_profile.md`, `evaluate.md`, `pdf.md`)
- HTML templates: `kebab-case.html` (e.g., `cv-template.html`)
- Test file: `test-all.mjs` (single comprehensive test suite)

**Functions:**
- Snake case: `checkUrl()`, `parseTracker()`, `normalizeCompany()`, `parseAppLine()`
- Exports: Named exports via `export function` (e.g., `export function classifyLiveness({...})`)
- Private helpers: Arrow functions at module scope, no special prefix

**Variables:**
- Snake case for all variables: `maxNum`, `addedCount`, `reportNum`, `bodyText`
- Constants: `UPPER_SNAKE_CASE` (e.g., `CANONICAL_STATES`, `ALIASES`, `CADENCE`)
- Booleans: Prefix with `is` or suffix with `Only`: `isTTY`, `summaryMode`, `overdueOnly`, `DRY_RUN`
- Collections: Descriptive singular prefix: `mjsFiles`, `tsvFiles`, `entries`, `leakPatterns`

**Markdown sections:**
- H1 for file title: `# Mode: evaluate -- Full Evaluation A-G`
- Nested structure with H2/H3: `## Block A -- Role Summary`, `### Signals to analyze`
- Code blocks: Triple backticks with language tag (e.g., ` ```bash `, ` ```typescript `)

## Code Style

**Formatting:**
- No linter or formatter configured (Prettier/ESLint absent)
- Manual conventions observed in codebase:
  - 2-space indentation
  - Single quotes for strings in JavaScript
  - Semicolons required
  - Line breaks after function declarations
  - Blank lines separating logical blocks

**Comments:**
- JSDoc-style block comments for module-level functions:
  ```javascript
  /**
   * merge-tracker.mjs — Merge batch tracker additions into applications.md
   *
   * Handles multiple TSV formats: 9-col, 8-col, pipe-delimited
   * Run: node career-ops/merge-tracker.mjs [--dry-run] [--verify]
   */
  ```
- Inline comments rare; code should be self-documenting
- Section separators: `// ── Section name ────────────────────────────────`
- No commented-out code

**Module imports:**
- ESM syntax only: `import { ... } from 'module'`
- Top of file after shebang and docstring
- Grouped by: Node.js builtins first, then external packages, then local imports
- Example from `merge-tracker.mjs`:
  ```javascript
  import { readFileSync, writeFileSync, readdirSync, mkdirSync, renameSync, existsSync } from 'fs';
  import { join, basename, dirname } from 'path';
  import { fileURLToPath } from 'url';
  import { execFileSync } from 'child_process';
  ```

**CLI argument parsing:**
- Manual `process.argv` checking: `process.argv.includes('--dry-run')`
- No argument parsing library (no yargs, no commander)
- Index-based parsing for value args:
  ```javascript
  const minThresholdIdx = args.indexOf('--min-threshold');
  const MIN_THRESHOLD = minThresholdIdx !== -1 && args[minThresholdIdx + 1]
    ? parseInt(args[minThresholdIdx + 1])
    : 5;
  ```

## Error Handling

**Pattern 1: Try-catch with graceful degradation**
```javascript
// From generate-pdf.mjs
generatePDF().catch((err) => {
  console.error('❌ PDF generation failed:', err.message);
  process.exit(1);
});

// From check-liveness.mjs
main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
```

**Pattern 2: Try-catch returning null on failure**
```javascript
// From doctor.mjs (checkPlaywright)
try {
  const { chromium } = await import('playwright');
  const execPath = chromium.executablePath();
  if (existsSync(execPath)) {
    return { pass: true, label: 'Playwright chromium installed' };
  }
  return { pass: false, label: '...', fix: '...' };
} catch {
  return { pass: false, label: '...', fix: '...' };
}
```

**Pattern 3: Null checks on optional values**
```javascript
// From check-liveness.mjs
const status = response?.status() ?? 0;
const bodyText = await page.evaluate(() => document.body?.innerText ?? '');
```

**Exit codes:**
- `0` = success (all checks passed, no changes to rollback)
- `1` = failure (hard blocker, data integrity issue, required to stop)
- Scripts allow graceful degradation: scripts run successfully even if user data (cv.md, profile.yml) is missing

**Logging:**
- Console-based: `console.log()`, `console.error()`, `console.warn()`
- Emoji prefixes for status clarity:
  - `✅` = success
  - `❌` = error / failure
  - `⚠️` = warning / note
  - `📊` = statistics
  - `📄` / `📁` / `📏` = file operations
  - `🔄` = update / change
  - `➕` / `⏭️` = addition / skip
- No structured logging; messages intended for human CLI reading

## File Input/Output

**File reading:**
- Synchronous by default: `readFileSync(path, 'utf-8')`
- Exception: Playwright operations use async (`readFile`, `writeFile` from `fs/promises`)
- Always check existence: `existsSync(path)` before reading

**File writing:**
- Synchronous: `writeFileSync(path, content)`
- Atomic: write entire file at once, no partial updates
- Example from `merge-tracker.mjs`:
  ```javascript
  if (!DRY_RUN) {
    writeFileSync(APPS_FILE, appLines.join('\n'));
    // Move processed files to merged/
    if (!existsSync(MERGED_DIR)) mkdirSync(MERGED_DIR, { recursive: true });
    for (const file of tsvFiles) {
      renameSync(join(ADDITIONS_DIR, file), join(MERGED_DIR, file));
    }
  }
  ```

**Path handling:**
- Always use `path` module: `join()`, `dirname()`, `basename()`
- Get project root via `import.meta.url`:
  ```javascript
  import { fileURLToPath } from 'url';
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
  ```
- Support both `data/applications.md` and root-level `applications.md`:
  ```javascript
  const APPS_FILE = existsSync(join(CAREER_OPS, 'data/applications.md'))
    ? join(CAREER_OPS, 'data/applications.md')
    : join(CAREER_OPS, 'applications.md');
  ```

## Markdown Data Conventions

**Tracker file (`data/applications.md`):**
- Markdown table with 9 columns: `# | Date | Company | Role | Score | Status | PDF | Report | Notes |`
- Entry format: `| 001 | 2026-04-10 | Company Name | Job Title | 4.5/5 | Applied | PDF | [001](reports/001-slug-date.md) | One-line summary |`
- Score always formatted `X.X/5` (one decimal place)
- Status must be canonical (from `templates/states.yml`): Evaluated, Applied, Responded, Interview, Offer, Rejected, Discarded, SKIP
- Report links: `[number](reports/{number}-{company-slug}-{YYYY-MM-DD}.md)`
- No markdown bold in status column (no `**Applied**`)
- No dates in status column

**Batch tracker additions (`batch/tracker-additions/*.tsv`):**
- Single-line TSV files, one addition per file
- Filename: `{number}-{company-slug}.tsv` (e.g., `059-anthropic-data-infra.tsv`)
- Format (9 columns, tab-separated):
  ```
  number	date	company	role	status	score	pdf_emoji	[number](report_path)	notes
  059	2026-04-13	Anthropic	Data Infrastructure	Evaluated	3.6/5	-	[059](reports/059-anthropic-data-infra-2026-04-13.md)	Critical domain gaps
  ```
- Column order in TSV: `status` before `score` (merge script auto-converts to markdown table order)
- Can also accept pipe-delimited format (markdown table row)
- After merge, files move to `batch/tracker-additions/merged/`

**Modes (`modes/*.md`):**
- Structured prompts for Claude in markdown
- H1 for mode name: `# Mode: evaluate -- Full Evaluation A-G`
- Blocks labeled: `## Block A -- Role Summary`, `## Block B -- CV Match`, etc.
- Tables for structured data:
  ```markdown
  | Dimension | Score | Weight | Weighted |
  |-----------|-------|--------|----------|
  | CV Match  | X.X   | 25%    | X.XX     |
  ```
- Code blocks show expected output format
- HTML comments for internal instructions:
  ```html
  <!-- This text is for Claude, not rendered -->
  ```

**Profile customization (`modes/_profile.md`):**
- Overrides system defaults from `modes/_shared.md`
- Never auto-updated (user's file)
- Contains: target archetypes, narrative framing, proof points, negotiation scripts, location preferences

**YAML configuration:**
- Keys: snake_case (e.g., `title_filter`, `apply_patterns`)
- Values: strings, lists, or nested objects
- Example from `templates/states.yml`:
  ```yaml
  states:
    - id: evaluated
      label: Evaluated
      aliases: [evaluada]
      description: Offer evaluated...
      dashboard_group: evaluated
  ```

## Data Types & Structures

**Parsing results (returned as objects):**
```javascript
// Application entry (from parseAppLine)
{
  num: 1,
  date: '2026-04-10',
  company: 'Company Name',
  role: 'Job Title',
  score: '4.5/5',
  status: 'Applied',
  pdf: 'PDF',
  report: '[001](reports/001-...)',
  notes: 'One line summary',
  raw: '| 1 | 2026-04-10 | ...'  // Original markdown line
}

// TSV addition entry (from parseTsvContent)
{
  num: 59,
  date: '2026-04-13',
  company: 'Anthropic',
  role: 'Data Infrastructure',
  status: 'Evaluated',  // Validated against CANONICAL_STATES
  score: '3.6/5',
  pdf: '-',
  report: '[059](reports/059-...)',
  notes: ''
}

// Liveness classification (from classifyLiveness)
{
  result: 'active' | 'expired' | 'uncertain',
  reason: 'Human-readable explanation'
}

// Test result (from test-all.mjs)
{
  pass: true | false,
  label: 'Description of check',
  fix?: 'How to fix if failed'  // Optional
}
```

## Shebang & Execution

**All CLI scripts start with:**
```javascript
#!/usr/bin/env node
```

**Run via:**
```bash
node script.mjs [args]
# NOT
./script.mjs
# (The shebang + executable bit allows ./script.mjs but convention is node script.mjs)
```

**Package.json scripts:**
```json
{
  "scripts": {
    "merge": "node merge-tracker.mjs",
    "verify": "node verify-pipeline.mjs",
    "pdf": "node generate-pdf.mjs"
  }
}
```

## Special Patterns

**Project root detection:**
Always use `fileURLToPath(import.meta.url)` to get absolute path, never assume `process.cwd()`:
```javascript
const CAREER_OPS = dirname(fileURLToPath(import.meta.url));
```

**String normalization:**
- Company names: lowercase alphanumeric only: `normalizeCompany(name) → name.toLowerCase().replace(/[^a-z0-9]/g, '')`
- Status: strip bold, lowercase, remove trailing dates, then alias lookup
- Role titles: whitespace trimmed, no special case normalization

**Multi-format parsing:**
Scripts detect and handle multiple input formats:
- TSV (tab-separated)
- Pipe-delimited (markdown table rows)
- Auto-detect which format and parse accordingly
- Example from `merge-tracker.mjs`: column order detection via heuristic regex matching

**Date handling:**
- Format: `YYYY-MM-DD` (ISO 8601)
- Stored as strings in markdown/YAML
- Parsed to Date objects only when calculating differences
- Example: `new Date(dateStr)` then `Math.floor((d2 - d1) / (1000 * 60 * 60 * 24))`

---

*Convention analysis: 2026-04-14*
