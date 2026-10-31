"""Robust rate-of-change estimates."""
import numpy as np
from scipy.stats import theilslopes


def slope_per_week(t_days, values, window_days: float) -> dict | None:
    """Theil-Sen slope over the trailing window, in units per week.

    `plateau` is True when the 95% interval of the slope includes zero.
    """
    t = np.asarray(t_days, dtype=float)
    v = np.asarray(values, dtype=float)
    if len(t) == 0:
        return None
    sel = t >= t[-1] - window_days
    if sel.sum() < 3 or np.ptp(t[sel]) < 1:
        return None
    slope, _, lo, hi = theilslopes(v[sel], t[sel], 0.95)
    return {
        "per_week": float(slope * 7),
        "low": float(lo * 7),
        "high": float(hi * 7),
        "plateau": bool(lo <= 0 <= hi),
        "n": int(sel.sum()),
    }
