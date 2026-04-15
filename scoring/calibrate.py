# scoring/calibrate.py
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


def parse_global_score(text: str) -> float | None:
    match = re.search(r"\*\*Score:\*\*\s*([\d.]+)/5", text)
    if match:
        return float(match.group(1))
    return None


def parse_score_table(text: str) -> dict[str, float] | None:
    """Extract dimension scores from the weighted score table.

    Handles three column orderings found in production reports:
      1. Dimension | Weight | Score | Weighted   (059-063, 071)
      2. Dimension | Score  | Weight | Weighted   (070, 072-074)
      3. Dimension | Weight | Score  | Rationale  (060-061 -- text last col)

    In all cases the score is a bare float (e.g. 3.0) and the weight is a
    percentage string (e.g. 25%).  The heuristic: whichever of col2/col3 ends
    with "%" is the weight; the other is the score.
    """
    # Match dimension rows: name | col2 | col3 | col4
    # col4 may be a float, a markdown bold float, or free-form text.
    pattern = re.compile(
        r"^\|\s*(CV Match|Archetype Fit|Comp Alignment|Level Fit|Org Risk|Blockers)\s*"
        r"\|\s*([\d.]+%?)\s*\|\s*([\d.]+%?)\s*\|",
        re.MULTILINE,
    )

    scores: dict[str, float] = {}
    for match in pattern.finditer(text):
        name = match.group(1)
        col2 = match.group(2).strip()
        col3 = match.group(3).strip()

        # Identify score vs weight by presence of '%'
        if "%" in col2:
            # col2 = weight, col3 = score
            score = float(col3)
        else:
            # col2 = score, col3 = weight
            score = float(col2)

        scores[name] = score

    if len(scores) == 6:
        return scores
    return None


def parse_report(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {
        "file": path.name,
        "global_score": parse_global_score(text),
        "dimensions": parse_score_table(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calibrate scoring engine against existing reports"
    )
    parser.add_argument("--reports-dir", type=str, default="reports/")
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        print(f"Reports directory not found: {reports_dir}", file=sys.stderr)
        return 1

    reports = []
    for path in sorted(reports_dir.glob("*.md")):
        parsed = parse_report(path)
        if parsed["global_score"] is not None:
            reports.append(parsed)

    if not reports:
        print("No reports with scores found.", file=sys.stderr)
        return 1

    global_scores = [r["global_score"] for r in reports]
    with_tables = [r for r in reports if r["dimensions"] is not None]

    print(f"\nReports parsed: {len(reports)}")
    print(f"Reports with score tables: {len(with_tables)}")
    print(f"Global score range: {min(global_scores):.1f} - {max(global_scores):.1f}")
    print(f"Global score mean: {sum(global_scores) / len(global_scores):.2f}")

    sorted_scores = sorted(global_scores)
    n = len(sorted_scores)
    median = (
        sorted_scores[n // 2]
        if n % 2 == 1
        else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
    )
    print(f"Global score median: {median:.2f}")

    if with_tables:
        print("\n--- Dimension Score Distribution (from score tables) ---\n")

        dim_data = []
        for r in with_tables:
            for dim_name, dim_score in r["dimensions"].items():
                dim_data.append(
                    {
                        "file": r["file"],
                        "dimension": dim_name,
                        "score": dim_score,
                        "global": r["global_score"],
                    }
                )

        df = pd.DataFrame(dim_data)
        summary = df.groupby("dimension")["score"].agg(
            ["mean", "std", "min", "max", "count"]
        )
        print(summary.to_string())

        print("\n--- Per-Report Score Table Comparison ---\n")
        for r in with_tables:
            print(f"\n{r['file']} (global: {r['global_score']})")
            for dim, score in r["dimensions"].items():
                print(f"  {dim}: {score}")

    csv_path = reports_dir.parent / "data" / "calibration-results.tsv"
    rows = []
    for r in reports:
        row: dict = {"file": r["file"], "global_score": r["global_score"]}
        if r["dimensions"]:
            row.update(r["dimensions"])
        rows.append(row)

    df_out = pd.DataFrame(rows)
    df_out.to_csv(csv_path, sep="\t", index=False)
    print(f"\nCalibration results written to: {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
