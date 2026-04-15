# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework & Structure

**Testing approach:** Custom test suite in a single file, no external test framework (no Jest, Vitest, Mocha, etc.)

**Test file location:**
- `test-all.mjs` in project root
- Runs all categories of tests in sequence
- Not integrated with npm scripts (no `npm test` configured)

**Run command:**
```bash
node test-all.mjs           # Run all tests
node test-all.mjs --quick   # Skip dashboard build (faster)
```

**Exit codes:**
- `0` = All tests passed (or warnings only, safe to push)
- `1` = Tests failed (do NOT push/merge)

## Test Organization

**10 test categories** in a single file, executed sequentially:

### 1. Syntax Checks
Validates all `.mjs` files parse without syntax errors:
```javascript
const mjsFiles = readdirSync(ROOT).filter(f => f.endsWith('.mjs'));
for (const f of mjsFiles) {
  const result = run(`node --check ${f}`);
  if (result !== null) {
    pass(`${f} syntax OK`);
  } else {
    fail(`${f} has syntax errors`);
  }
}
```
- Uses `node --check` (no execution, parse-only)
- Fails on any syntax error

### 2. Script Execution
Runs critical scripts with empty/boilerplate data to ensure graceful degradation:
```javascript
const scripts = [
  { name: 'cv-sync-check.mjs', expectExit: 1, allowFail: true },
  { name: 'verify-pipeline.mjs', expectExit: 0 },
  { name: 'merge-tracker.mjs', expectExit: 0 },
  { name: 'update-system.mjs check', expectExit: 0 },
];

for (const { name, allowFail } of scripts) {
  const result = run(`node ${name} 2>&1`);
  if (result !== null) {
    pass(`${name} runs OK`);
  } else if (allowFail) {
    warn(`${name} exited with error (expected without user data)`);
  } else {
    fail(`${name} crashed`);
  }
}
```
- Captured in `try-catch`, exit code not strictly checked (graceful-first philosophy)
- `allowFail=true` scripts warn but don't fail if they exit 1 (expected for missing CV)
- Timeout: 30 seconds per script

### 3. Liveness Classification Logic
Unit tests for job posting liveness detection (`liveness-core.mjs`):
```javascript
const { classifyLiveness } = await import(pathToFileURL(join(ROOT, 'liveness-core.mjs')).href);

const expiredChromeApply = classifyLiveness({
  finalUrl: 'https://example.com/jobs/closed-role',
  bodyText: 'Company Careers\nApply\nThe job you are looking for is no longer open.',
  applyControls: [],
});
if (expiredChromeApply.result === 'expired') {
  pass('Expired pages are not revived by nav/footer "Apply" text');
} else {
  fail(`Expired page misclassified as ${expiredChromeApply.result}`);
}

const activeWorkdayPage = classifyLiveness({
  finalUrl: 'https://example.workday.com/job/123',
  bodyText: ['663 JOBS FOUND', 'Senior AI Engineer', '...'].join('\n'),
  applyControls: ['Apply for this Job'],
});
if (activeWorkdayPage.result === 'active') {
  pass('Visible apply controls still keep real job pages active');
} else {
  fail(`Active job page misclassified as ${activeWorkdayPage.result}`);
}
```
- Direct imports from module: `pathToFileURL()` + dynamic import
- Synthetic test data (no API calls)
- Tests: expired page detection, active page detection, edge cases

### 4. Dashboard Build
Validates Go dashboard compiles:
```javascript
if (!QUICK) {
  console.log('\n4. Dashboard build');
  const goBuild = run('cd dashboard && go build -o /tmp/career-dashboard-test . 2>&1');
  if (goBuild !== null) {
    pass('Dashboard compiles');
  } else {
    fail('Dashboard build failed');
  }
} else {
  console.log('\n4. Dashboard build (skipped --quick)');
}
```
- Skipped with `--quick` flag for CI speed
- Output to `/tmp/career-dashboard-test` (ephemeral)

### 5. Data Contract Validation
Checks system files exist and user files are gitignored:
```javascript
const systemFiles = [
  'CLAUDE.md', 'VERSION', 'DATA_CONTRACT.md',
  'modes/_shared.md', 'modes/_profile.template.md',
  'modes/evaluate.md', 'modes/pdf.md', 'modes/scan.md',
  'templates/states.yml', 'templates/cv-template.html',
  '.claude/skills/career-ops/SKILL.md',
];

for (const f of systemFiles) {
  if (fileExists(f)) {
    pass(`System file exists: ${f}`);
  } else {
    fail(`Missing system file: ${f}`);
  }
}

const userFiles = ['config/profile.yml', 'modes/_profile.md', 'portals.yml'];
for (const f of userFiles) {
  const tracked = run(`git ls-files ${f}`);
  if (tracked === '') {
    pass(`User file gitignored: ${f}`);
  } else {
    fail(`User file IS tracked (should be gitignored): ${f}`);
  }
}
```
- Verifies no system files are missing
- Verifies user files are NOT tracked in git (gitignore enforcement)
- Uses `git ls-files` to check tracking status

### 6. Personal Data Leak Check
Scans codebase for author/test data that shouldn't be committed:
```javascript
const leakPatterns = [
  'Santiago', 'santifer.io', 'Santifer iRepair', 'Zinkee', 'ALMAS',
  'hi@santifer.io', '688921377', '/Users/santifer/',
];

const scanExtensions = ['md', 'yml', 'html', 'mjs', 'sh', 'go', 'json'];
const excludeDirs = ['node_modules', '.git', 'dashboard/go.sum'];
const allowedFiles = ['README.md', 'LICENSE', 'CITATION.cff', 'CONTRIBUTING.md',
  'package.json', '.github/FUNDING.yml', 'CLAUDE.md', 'go.mod', 'test-all.mjs'];

let leakFound = false;
for (const pattern of leakPatterns) {
  const result = run(
    `grep -rn "${pattern}" --include="*.{${scanExtensions.join(',')}}" . 2>/dev/null | grep -v node_modules | grep -v ".git/"`
  );
  if (result) {
    for (const line of result.split('\n')) {
      const file = line.split(':')[0].replace('./', '');
      if (allowedFiles.some(a => file.includes(a))) continue;
      warn(`Possible personal data in ${file}: "${pattern}"`);
      leakFound = true;
    }
  }
}
if (!leakFound) {
  pass('No personal data leaks outside allowed files');
}
```
- Patterns: author's name, email, company names, ID numbers, home paths
- Excluded dirs: node_modules, .git
- Allowed files: README, LICENSE, contributing guides, go.mod (allowed to have author)
- Returns warnings, not failures (for human review)

### 7. Absolute Path Check
Ensures no hardcoded `/Users/` paths in code:
```javascript
const absPathResult = run(
  `grep -rn "/Users/" --include="*.mjs" --include="*.sh" --include="*.md" --include="*.go" --include="*.yml" . 2>/dev/null | grep -v node_modules | grep -v ".git/"`
);
if (!absPathResult) {
  pass('No absolute paths in code files');
} else {
  for (const line of absPathResult.split('\n').filter(Boolean)) {
    fail(`Absolute path: ${line.slice(0, 100)}`);
  }
}
```
- Scans `.mjs`, `.sh`, `.md`, `.go`, `.yml` files
- Fails immediately if any hardcoded `/Users/` found
- Trims output to first 100 chars per line (long paths)

### 8. Mode File Integrity
Validates all mode files exist and cross-reference correctly:
```javascript
const expectedModes = [
  '_shared.md', '_profile.template.md', 'evaluate.md', 'pdf.md', 'scan.md',
  'batch.md', 'apply.md', 'auto-pipeline.md', 'contact.md', 'deep.md',
  'compare.md', 'pipeline.md', 'project.md', 'tracker.md', 'training.md',
];

for (const mode of expectedModes) {
  if (fileExists(`modes/${mode}`)) {
    pass(`Mode exists: ${mode}`);
  } else {
    fail(`Missing mode: ${mode}`);
  }
}

const shared = readFile('modes/_shared.md');
if (shared.includes('_profile.md')) {
  pass('_shared.md references _profile.md');
} else {
  fail('_shared.md does NOT reference _profile.md');
}
```
- Checks all 15 mode files are present
- Validates `_shared.md` (updatable system defaults) references `_profile.md` (user overrides)

### 9. CLAUDE.md Integrity
Ensures project instruction file has all required sections:
```javascript
const claude = readFile('CLAUDE.md');
const requiredSections = [
  'Data Contract', 'Update Check', 'Ethical Use',
  'Offer Verification', 'Canonical States', 'TSV Format',
  'First Run', 'Onboarding',
];

for (const section of requiredSections) {
  if (claude.includes(section)) {
    pass(`CLAUDE.md has section: ${section}`);
  } else {
    fail(`CLAUDE.md missing section: ${section}`);
  }
}
```
- Checks for required sections by string match (no regex)
- Failure = missing critical documentation

### 10. Version File
Validates semantic versioning:
```javascript
if (fileExists('VERSION')) {
  const version = readFile('VERSION').trim();
  if (/^\d+\.\d+\.\d+$/.test(version)) {
    pass(`VERSION is valid semver: ${version}`);
  } else {
    fail(`VERSION is not valid semver: "${version}"`);
  }
} else {
  fail('VERSION file missing');
}
```
- Regex: `X.Y.Z` format (three numbers separated by dots)
- No `v` prefix, no pre-release tags

## Liveness Classification Tests (Detailed)

Located in `liveness-core.mjs`, exported as `classifyLiveness()`:

**Test cases in test-all.mjs:**

1. **Expired page with generic "Apply" in footer:**
   - Input: HTTP 200, body contains "The job you are looking for is no longer open", no apply controls outside footer
   - Expected: `{ result: 'expired', reason: 'pattern matched: ...' }`
   - Purpose: Ensures generic "Apply" button in nav doesn't revive expired postings

2. **Active job page from Workday:**
   - Input: HTTP 200, Workday URL, body has "663 JOBS FOUND" (listing page marker) AND "Apply for this Job" button visible
   - Expected: `{ result: 'active', reason: 'visible apply control detected' }`
   - Purpose: Validates apply control detection overrides listing page marker (real job detail page with navigation)

**Core patterns tested in liveness-core.mjs:**

Hard expired patterns:
- "job (is )?no longer available"
- "position has been filled"
- "job posting has expired"
- "no longer accepting applications"
- "this (position|role|job) (is )?no longer"
- "job (listing )?is closed"
- "job (listing )?not found"
- "the page you are looking for doesn.t exist"
- German: "diese stelle (ist )?(nicht mehr|bereits) besetzt"
- French: "offre (expirée|n'est plus disponible)"

Listing page patterns (false positives):
- "\d+\s+jobs?\s+found"
- "search for jobs page is loaded"

Apply control patterns (must be visible):
- "apply", "solicitar" (ES), "bewerben" (DE), "postuler" (FR)
- "submit application", "easy apply", "start application"

Minimum content threshold: 300 characters (nav/footer only = expired)

## Test Execution Flow

```javascript
function pass(msg) { console.log(`  ✅ ${msg}`); passed++; }
function fail(msg) { console.log(`  ❌ ${msg}`); failed++; }
function warn(msg) { console.log(`  ⚠️  ${msg}`); warnings++; }

function run(cmd, opts = {}) {
  try {
    return execSync(cmd, { cwd: ROOT, encoding: 'utf-8', timeout: 30000, ...opts }).trim();
  } catch (e) {
    return null;
  }
}
```

**Execution order:**
1. Print test suite header
2. Run 10 test categories in sequence
3. Count passed/failed/warnings
4. Print summary:
   - `📊 Results: {passed} passed, {failed} failed, {warnings} warnings`
5. Exit with code:
   - `0` if `failed === 0` (safe to push)
   - `1` if `failed > 0` (do NOT push)

**Sample output:**
```
🧪 career-ops test suite

1. Syntax checks
  ✅ merge-tracker.mjs syntax OK
  ✅ generate-pdf.mjs syntax OK
  ...

2. Script execution (graceful on empty data)
  ✅ verify-pipeline.mjs runs OK
  ⚠️  cv-sync-check.mjs exited with error (expected without user data)
  ...

10. Version file
  ✅ VERSION is valid semver: 1.0.0

==================================================
📊 Results: 47 passed, 0 failed, 2 warnings
🟢 All tests passed — safe to push/merge
```

## Coverage & Testing Philosophy

**What is tested:**
- Syntax: all `.mjs` files
- Execution: critical scripts (merge, verify, generate-pdf, update-system)
- Logic: liveness classification (job posting active/expired detection)
- Configuration: mode files, CLAUDE.md structure, VERSION format
- Data integrity: gitignore rules, personal data leaks, absolute paths
- Integration: system file presence, cross-file references

**What is NOT tested:**
- Unit tests per function (no test framework)
- Integration tests with real Playwright browsers (separate from test-all.mjs)
- Coverage measurement (no coverage tool)
- Specific scoring logic (Blocks A-F in modes/ are not validated by tests)
- Report generation output (verified manually)

**Why custom test suite:**
- Simple, no dependencies beyond Node.js
- Fast (all tests < 5 seconds)
- Checks data contract enforcement (gitignore, file structure)
- Detects personal data leaks automatically
- Can be run pre-commit (git hook friendly)

## Playwright Usage (Not Test Framework)

**Playwright is NOT used for testing** — it's a runtime dependency for:
- `generate-pdf.mjs`: HTML to PDF rendering
- `check-liveness.mjs`: Job posting URL validation
- `scan.mjs`: Portal scraping and job detection

**Playwright test framework (from node_modules) is ignored** — career-ops uses its own custom test suite instead.

---

*Testing analysis: 2026-04-14*
