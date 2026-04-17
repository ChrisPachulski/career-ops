#!/bin/bash
# Reapply local modifications after career-ops system update.
#
# The patches file represents the full fork divergence from santifer/career-ops
# upstream/main. It covers:
#   - 6-dimension weighted scoring engine (scoring/, tests/)
#   - DuckDB migration: data/career-ops.duckdb as the source of truth
#     (scripts/init-db.mjs, scripts/db-write.mjs, scripts/lockfile.mjs,
#      reconcile-tracker.mjs, rewrites of scan/verify/dedup/analyze/followup,
#      deletion of merge-tracker.mjs + normalize-statuses.mjs)
#   - Dashboard JSON-snapshot read path (dashboard/internal/data/career.go)
#   - Batch two-phase commit via batch/ingest-queue/
#   - Mode docs + batch prompt updated to the CLI ingest path
#   - DATA_CONTRACT story-bank exception, apply.md guardrail, language refs
#
# After upstream pulls new changes, this file may need to be regenerated:
#   git diff upstream/main -- [code paths] > config/local-patches.diff
#   # then append `git diff --no-index /dev/null <new-files>` for untracked code
#
# Usage: Run after `node update-system.mjs apply`
#   bash config/reapply-local-patches.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "Reapplying local patches..."
if git apply --check config/local-patches.diff 2>/dev/null; then
    git apply config/local-patches.diff
    git add -A
    git commit -m "chore: reapply local scoring, DuckDB migration, and guardrail patches"
    echo "Patches applied successfully."
else
    echo "Patches do not apply cleanly (upstream likely changed the same lines)."
    echo "Manual resolution needed. Your patches are preserved in config/local-patches.diff"
    echo "Your pre-update commits are also preserved in git history."
    exit 1
fi
