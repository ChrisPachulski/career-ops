# career-ops (Pachulski fork)

A fork of [**santifer/career-ops**](https://github.com/santifer/career-ops) with a personalized brain layer.

santifer built a multi-agent job-search pipeline: paste a URL, get a scored evaluation, generate a tailored CV, track everything in a single source of truth. The system works well, and I'm grateful for it. This fork adds one thing on top — a compiled *brain* file that persists candidate context, scoring rules, and current company intelligence across evaluations so the system never has to reconstruct them from scratch.

**Everything that makes career-ops work is santifer's. My contribution is the brain layer. If you're new to career-ops, start at the upstream repo and its [case study](https://santifer.io/career-ops-system); come back here only if you want to add a similar context-compression layer to your own fork.**

---

## Why I forked it

The base system treats every evaluation as a clean slate: CV markdown in, job description in, scored report out. For the first ten offers that's fine. By the fortieth, I was re-supplying the same context to every session — who I am, which archetypes I target, what my comp floor is, what counts as a hard blocker, which proof points map to which roles, what the current hiring landscape looks like at the companies I care about.

The evaluation quality was high. The per-session context cost was rising. The gap I wanted to close was keeping the first without paying the second.

## What the brain adds

`career-ops-brain.md` is a single compiled file that replaces loading `cv.md + modes/_shared.md + modes/_profile.md + config/profile.yml + modes/evaluate.md` separately. It is regenerated periodically from evaluation output; the current revision was compiled after ninety evaluations.

Six sections, each with a specific job:

1. **Candidate identity** — name, location, comp floor, walk-away number, exit narrative.
2. **Proof points** — a metrics-only table mapping every portfolio project to the archetypes it's evidence for.
3. **Archetypes and framing** — the target role archetypes, what each buys, and which proof points to cite.
4. **Scoring rules** — the weighted dimensions and thresholds, plus blocker-gate rules that cap scores when hard gaps are present.
5. **Evaluation format** — the exact block structure the output must follow, with file-naming conventions and TSV columns for the tracker.
6. **Current intelligence** — live status per target company (Active / Mixed / Frozen / Stale / Dead), dates, comp ranges, and key signals.

The compiled brain compresses roughly 40 KB of scattered context into an 8 KB reference that fits cleanly inside a Claude Code conversation without burning headroom on restating the basics every time.

## How the brain is used

Inside Claude Code, the evaluator reads `career-ops-brain.md` as the first step of any evaluation. The existing santifer modes still drive the pipeline; the brain just short-circuits the context-loading phase. When the brain gets stale — say a company's status changes from Active to Frozen, or new proof points land — the brain is regenerated from the evaluation corpus and checked in.

## What I did NOT add

- The pipeline engine (scan, evaluate, batch, dashboard, tracker reconciliation) — santifer's.
- The six-block evaluation structure and the ATS-optimized PDF generator — santifer's.
- The Playwright portal scanner, the portals.yml schema, the Greenhouse/Ashby/Lever adapters — santifer's.
- The negotiation scripts, the STAR+R story accumulator, the interview-prep framework — santifer's.

My contribution is the brain. Full stop. The rest of the system is upstream work.

## Credit and license

- Original project: [github.com/santifer/career-ops](https://github.com/santifer/career-ops)
- Case study and design rationale: [santifer.io/career-ops-system](https://santifer.io/career-ops-system)
- License: MIT, matching upstream.

If santifer's system evolves — which it does, actively — check the upstream. This fork only maintains the brain-layer addition; the pipeline I'm using underneath is santifer's current release.

## If you want to adopt the brain layer

The brain is a single markdown file with six sections (above). There is no separate tool to install, no dependency graph, no infrastructure. Adapt the structure to your own context, save it as `career-ops-brain.md` in your fork's root, and tell Claude to read it first when evaluating.

The pattern generalizes beyond job search. I've used the same shape in a separate credit-card evaluation project (`card-ops`), and the brain-first evaluator works there for the same reason it works here: persistent context is cheaper than reconstructed context, and the system reasons better when it doesn't have to rediscover you every session.
