#!/bin/bash
# Reapply local modifications after career-ops system update.
# These patches add: 6-dimension weighted scoring, blocker gate criteria,
# calibration benchmarks, apply.md guardrail, language mode scoring refs,
# DATA_CONTRACT story-bank exception.
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
    git commit -m "chore: reapply local scoring and guardrail patches"
    echo "Patches applied successfully."
else
    echo "Patches do not apply cleanly (upstream likely changed the same lines)."
    echo "Manual resolution needed. Your patches are preserved in config/local-patches.diff"
    echo "Your pre-update commits are also preserved in git history."
    exit 1
fi
