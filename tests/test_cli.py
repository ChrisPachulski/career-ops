import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run_cli(input_json: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scoring.cli"],
        input=input_json,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def _valid_input() -> dict:
    return {
        "salary_low": 250000,
        "salary_high": 300000,
        "salary_midpoint": None,
        "comp_target": 250000,
        "jd_seniority": "staff",
        "candidate_seniority": "staff",
        "detected_archetype": "AI Platform/LLMOps",
        "target_archetypes": ["AI Platform/LLMOps"],
        "archetype_adjacency": 1.0,
        "requirements": [
            {"text": "Python", "priority": "must", "match_strength": 0.9, "evidence": "yes"},
        ],
        "org_signals": {
            "glassdoor_rating": 4.0,
            "recent_layoffs": False,
            "org_stability": 4.5,
            "remote_policy": "remote",
            "location_fit": 5.0,
        },
        "blockers": [],
    }


class TestCli:
    def test_valid_input_exits_0(self):
        result = _run_cli(json.dumps(_valid_input()))
        assert result.returncode == 0

    def test_valid_input_returns_json(self):
        result = _run_cli(json.dumps(_valid_input()))
        output = json.loads(result.stdout)
        assert "global_score" in output
        assert "dimensions" in output
        assert "score_table" in output

    def test_invalid_json_exits_1(self):
        result = _run_cli("not json at all")
        assert result.returncode == 1

    def test_missing_required_field_exits_1(self):
        bad = _valid_input()
        del bad["comp_target"]
        result = _run_cli(json.dumps(bad))
        assert result.returncode == 1

    def test_file_input(self, tmp_path):
        f = tmp_path / "features.json"
        f.write_text(json.dumps(_valid_input()))
        result = subprocess.run(
            [sys.executable, "-m", "scoring.cli", "--input", str(f)],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "global_score" in output
