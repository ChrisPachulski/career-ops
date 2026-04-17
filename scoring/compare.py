from __future__ import annotations

from scoring.models import ScoreResult


def compare_results(
    labeled_results: list[tuple[str, ScoreResult]],
) -> list[dict[str, object]]:
    """Merge multiple ScoreResults into a ranked comparison table.

    Each entry in *labeled_results* is (label, ScoreResult) where *label* is
    a human-readable identifier like "Anthropic -- Staff DSE".

    Returns a list of dicts sorted by global_score descending, each containing:
      - label, global_score, rank
      - per-dimension scores (keyed by dimension name)
      - delta_* columns (distance from best per dimension)
      - index_* columns (ratio to batch mean per dimension)
    """
    if not labeled_results:
        return []

    dim_names = [d.name for d in labeled_results[0][1].dimensions]

    rows: list[dict[str, object]] = []
    for label, result in labeled_results:
        row: dict[str, object] = {
            "label": label,
            "global_score": result.global_score,
        }
        for dim in result.dimensions:
            row[dim.name] = dim.score
        rows.append(row)

    rows.sort(key=lambda r: float(r["global_score"]), reverse=True)

    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    best = rows[0]
    for row in rows:
        for dim in dim_names:
            row[f"delta_{dim}"] = round(
                float(row.get(dim, 0)) - float(best.get(dim, 0)), 1
            )

    for dim in dim_names:
        values = [float(r.get(dim, 0)) for r in rows]
        mean = sum(values) / len(values) if values else 0.0
        for row in rows:
            row[f"index_{dim}"] = (
                round(float(row.get(dim, 0)) / mean, 2) if mean > 0 else 1.0
            )

    return rows


def format_comparison_table(
    rows: list[dict[str, object]],
    dim_names: list[str],
) -> str:
    """Render comparison rows as a markdown table."""
    if not rows:
        return ""

    header = "| Rank | Offer | Score |"
    sep = "|------|-------|-------|"
    for dim in dim_names:
        header += f" {dim} |"
        sep += f" {'---':->5s} |"

    lines = [header, sep]
    for row in rows:
        parts = [
            f"| {row['rank']}",
            f"| {row['label']}",
            f"| {float(row['global_score']):.1f}",
        ]
        for dim in dim_names:
            score = float(row.get(dim, 0))
            delta = float(row.get(f"delta_{dim}", 0))
            delta_str = f" ({delta:+.1f})" if delta != 0.0 else ""
            parts.append(f"| {score:.1f}{delta_str}")
        lines.append(" ".join(parts) + " |")

    return "\n".join(lines)
