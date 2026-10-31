"""Holt damped-trend forecast with a widening prediction band, and goal ETA."""
import numpy as np


def holt_damped(t_days, values, horizon: int = 60, alpha=0.3, beta=0.1, phi=0.95) -> dict | None:
    t = np.asarray(t_days, dtype=float)
    v = np.asarray(values, dtype=float)
    if len(v) < 5:
        return None
    days = np.arange(np.floor(t[0]), np.floor(t[-1]) + 1)
    y = np.interp(days, t, v)
    level, trend = y[0], (y[min(7, len(y) - 1)] - y[0]) / max(min(7, len(y) - 1), 1)
    resid = []
    for obs in y[1:]:
        pred = level + phi * trend
        resid.append(obs - pred)
        new_level = alpha * obs + (1 - alpha) * pred
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    sigma = float(np.std(resid)) if resid else 0.0
    steps = np.arange(1, horizon + 1)
    damp = np.cumsum(phi ** steps)
    mean = level + damp * trend
    width = 1.96 * sigma * np.sqrt(steps)
    return {
        "t": (days[-1] + steps).tolist(),
        "mean": mean.tolist(),
        "low": (mean - width).tolist(),
        "high": (mean + width).tolist(),
    }


def goal_eta(forecast: dict | None, current: float, goal: float) -> float | None:
    """Day (same axis as forecast['t']) when the mean forecast first reaches the goal."""
    if not forecast:
        return None
    for t, m in zip(forecast["t"], forecast["mean"]):
        if (current >= goal and m <= goal) or (current < goal and m >= goal):
            return float(t)
    return None
