"""Trend smoothers: Hacker's Diet exponential moving average and LOWESS."""
import numpy as np


def ewma_trend(t_days, values, alpha: float = 0.1) -> np.ndarray:
    """Exponentially weighted trend; alpha is per day so gaps are handled correctly."""
    t = np.asarray(t_days, dtype=float)
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return v
    out = np.empty_like(v)
    out[0] = v[0]
    for i in range(1, len(v)):
        dt = max(t[i] - t[i - 1], 1e-6)
        a = 1.0 - (1.0 - alpha) ** dt
        out[i] = out[i - 1] + a * (v[i] - out[i - 1])
    return out


def lowess_trend(t_days, values, frac: float = 0.3) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    if len(v) < 5:
        return v.copy()
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
    except ImportError:  # statsmodels is optional
        return ewma_trend(t_days, v)
    return lowess(v, np.asarray(t_days, dtype=float), frac=frac, return_sorted=False)
