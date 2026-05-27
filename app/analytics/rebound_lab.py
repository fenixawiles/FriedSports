"""
Rebound Leverage Lab

Question: Controlling for FG% parity, how much does total rebounding differential
predict winning?

This module provides a pure query function that returns binned results — no side effects.
"""

from app.models import db
from app.analytics.models import DerivedGameMetrics, LabGame, LabSeason


# Default TRB bins: (low_inclusive, high_inclusive, label)
DEFAULT_BINS = [
    (None, -10, "≤ -10"),
    (-9, -5,  "-9 to -5"),
    (-4, -1,  "-4 to -1"),
    (0,   0,  "0"),
    (1,   4,  "+1 to +4"),
    (5,   9,  "+5 to +9"),
    (10, None, "≥ +10"),
]


def _make_bins(bin_size: int) -> list:
    """Generate symmetric bins of given size around 0."""
    if bin_size <= 0:
        bin_size = 5
    bins = []
    # Negative tail
    bins.append((None, -(bin_size * 2 + 1), f"≤ -{bin_size * 2 + 1}"))
    step = bin_size
    lo = -(bin_size * 2)
    while lo < 0:
        hi = min(lo + step - 1, -1)
        bins.append((lo, hi, f"{lo} to {hi}"))
        lo += step
    # Zero
    bins.append((0, 0, "0"))
    # Positive
    hi = step
    while hi <= bin_size * 2:
        lo = hi - step + 1
        bins.append((lo, hi, f"+{lo} to +{hi}"))
        hi += step
    bins.append((bin_size * 2 + 1, None, f"≥ +{bin_size * 2 + 1}"))
    return bins


def run_rebound_leverage_query(
    league_id: int,
    season_id: int = None,
    fg_pct_parity_threshold: float = 0.02,
    bin_size: int = 5,
    playoffs_only: bool = False,
) -> dict:
    """
    Among games where |fg_pct_diff| <= threshold (FG% parity),
    bin by trb_diff range and compute win%, avg point margin.

    Returns:
        {
            "bins": [
                {
                    "label": "≤ -10",
                    "sample": 12,
                    "win_pct": 0.083,
                    "avg_margin": -8.5,
                }
            ],
            "total_qualifying": 247,
            "total_filtered": 180,
            "threshold_used": 0.02,
        }
    """
    # Base query: DerivedGameMetrics joined to LabGame for league/season filter
    query = (
        db.session.query(DerivedGameMetrics)
        .join(LabGame, DerivedGameMetrics.game_id == LabGame.id)
        .filter(LabGame.league_id == league_id)
        .filter(LabGame.status == "final")
    )

    if season_id:
        query = query.filter(LabGame.season_id == season_id)

    if playoffs_only:
        query = (
            query.join(LabSeason, LabGame.season_id == LabSeason.id)
            .filter(LabSeason.season_type == "playoffs")
        )

    all_rows = query.all()
    total_qualifying = len(all_rows)

    # Filter by FG% parity
    parity_rows = [
        r for r in all_rows
        if r.fg_pct_diff is not None
        and abs(r.fg_pct_diff) <= fg_pct_parity_threshold
    ]
    total_filtered = len(parity_rows)

    # Build bins
    bins_def = _make_bins(bin_size)
    results = []

    for (lo, hi, label) in bins_def:
        def in_bin(r):
            if r.trb_diff is None:
                return False
            if lo is not None and r.trb_diff < lo:
                return False
            if hi is not None and r.trb_diff > hi:
                return False
            return True

        bucket = [r for r in parity_rows if in_bin(r)]
        n = len(bucket)
        if n == 0:
            results.append({
                "label": label,
                "sample": 0,
                "win_pct": None,
                "avg_margin": None,
            })
            continue

        wins = sum(1 for r in bucket if r.win)
        avg_margin = round(sum(r.point_margin for r in bucket) / n, 1)
        win_pct = round(wins / n, 3)

        results.append({
            "label": label,
            "sample": n,
            "win_pct": win_pct,
            "avg_margin": avg_margin,
        })

    # Drop empty bins from edges
    non_empty = [r for r in results if r["sample"] > 0]

    return {
        "bins": non_empty if non_empty else results,
        "total_qualifying": total_qualifying,
        "total_filtered": total_filtered,
        "threshold_used": fg_pct_parity_threshold,
    }
