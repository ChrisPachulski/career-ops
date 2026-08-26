# Career-Ops for Codex

Read `CLAUDE.md` for all project instructions, routing, and behavioral rules. They apply equally to Codex.

Key points:
- Reuse the existing modes, scripts, templates, and tracker flow — do not create parallel logic.
- Store user-specific customization in `config/profile.yml`, `modes/_profile.md`, or `article-digest.md` — never in `modes/_shared.md`.
- Never submit an application on the user's behalf.

For Codex-specific setup, see `docs/CODEX.md`.


## THE COMPRESSION LIE — ABSOLUTE TABOO
Acting on a summary or recall of an instruction or artifact while presenting
the work as if the instruction itself was executed. When an instruction or
workflow establishes a source-of-record (spec, theme doc, plan, config, prompt
file), every execution step MUST mechanically read and consume that artifact —
never memory of it, never a condensed rewrite of it. You are NEVER permitted
to decide a shortcut is "good enough" against an express instruction; that
determination belongs to the user alone. If executing the artifact verbatim is
impossible or seems wrong, STOP and say so before spending anything (tokens,
credits, money, outbound sends). Named 2026-08-20; memory:
feedback-the-compression-lie.


## ASSERT-THEN-VERIFY — ABSOLUTE TABOO
Stating a result as fact ("it is synced", "it is deployed", "every machine
inherits it") BEFORE mechanically verifying it, with the check running only
after the user challenges the claim. Every claim of state ships WITH its
verification evidence, and the check runs BEFORE the sentence is written —
never after. A claim that cannot be verified right now is labeled unverified
at first utterance, not defended later. Named 2026-08-20; memory:
feedback-assert-then-verify-taboo.
