"""Weekday effect and period aggregates."""
from collections import defaultdict
from datetime import datetime
import numpy as np


def day_of_week_offsets(dates: list[datetime], values, trend) -> dict[int, float]:
    """Mean deviation from trend per weekday (0=Monday)."""
    buckets = defaultdict(list)
    for d, v, tr in zip(dates, values, trend):
        buckets[d.weekday()].append(v - tr)
    return {k: float(np.mean(x)) for k, x in sorted(buckets.items()) if len(x) >= 2}


def aggregate(dates: list[datetime], values, period: str = "week") -> list[dict]:
    buckets = defaultdict(list)
    for d, v in zip(dates, values):
        key = d.strftime("%G-W%V") if period == "week" else d.strftime("%Y-%m")
        buckets[key].append(v)
    return [{"period": k, "mean": float(np.mean(x)), "min": float(min(x)), "max": float(max(x)), "n": len(x)}
            for k, x in sorted(buckets.items())]
