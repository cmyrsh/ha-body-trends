"""Turn raw measurements for one user into series, trends and a summary."""
from datetime import datetime, timedelta, timezone
import numpy as np

from .analysis import composition, forecast, outliers, smoothing, trend, weekly

TREND_METRICS = {"weight": "kg", "bodyFatPercent": "%", "muscleMass": "kg", "waterPercent": "%"}
WINDOWS = (7, 30, 90)


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def analyze(rows: list[dict], profile: dict | None, opts: dict | None = None) -> dict:
    opts = opts or {}
    alpha = opts.get("smoothing_alpha", 0.1)
    window = opts.get("hampel_window", 7)
    sigmas = opts.get("hampel_sigmas", 3.5)
    profile = profile or {}
    weights = [r for r in rows if r.get("weight") is not None]
    if not weights:
        return {"n": 0, "series": {}, "trends": {}, "summary": {}}

    dates = [_parse(r["ts"]) for r in weights]
    t0 = dates[0]
    t_all = np.array([(d - t0).total_seconds() / 86400 for d in dates])
    flagged = outliers.hampel_mask([r["weight"] for r in weights], window, sigmas)
    keep = ~flagged

    series, trends = {}, {}
    for metric, unit in TREND_METRICS.items():
        idx = [i for i, r in enumerate(weights) if r.get(metric) is not None and keep[i]]
        if not idx:
            continue
        t = t_all[idx]
        v = np.array([weights[i][metric] for i in idx], dtype=float)
        sm = smoothing.ewma_trend(t, v, alpha)
        series[metric] = {
            "unit": unit,
            "ts": [weights[i]["ts"] for i in idx],
            "value": v.tolist(),
            "trend": sm.tolist(),
        }
        trends[metric] = {f"{w}d": trend.slope_per_week(t, sm, w) for w in WINDOWS}

    w = series["weight"]
    t_w = t_all[keep]
    fc = forecast.holt_damped(t_w, w["trend"], horizon=60)
    summary = {
        "n_readings": len(weights),
        "n_outliers": int(flagged.sum()),
        "first": weights[0]["ts"],
        "last": weights[-1]["ts"],
        "latest_weight": w["value"][-1],
        "trend_weight": w["trend"][-1],
    }
    latest = [r for r in weights if r["weight"] is not None][-1]
    if latest.get("bodyFatPercent") is not None:
        fl = composition.fat_lean(w["trend"][-1], latest["bodyFatPercent"])
        summary.update(fl)
        summary["body_fat_band"] = composition.body_fat_band(latest["bodyFatPercent"], profile.get("sex"))
        if profile.get("height_cm"):
            summary["ffmi"] = composition.ffmi(fl["lean_mass"], profile["height_cm"])
    if profile.get("height_cm"):
        bmi = w["trend"][-1] / (profile["height_cm"] / 100) ** 2
        summary["bmi_trend"] = bmi
        summary["bmi_band"] = composition.bmi_band(bmi)
    if profile.get("goal_weight") is not None and fc:
        eta = forecast.goal_eta(fc, w["trend"][-1], profile["goal_weight"])
        summary["goal_weight"] = profile["goal_weight"]
        summary["goal_eta"] = (t0 + timedelta(days=eta)).strftime("%Y-%m-%d") if eta is not None else None

    kept_dates = [d for d, k in zip(dates, keep) if k]
    return {
        "n": len(weights),
        "series": series,
        "trends": trends,
        "forecast": fc,
        "t0": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outliers": [weights[i]["ts"] for i in np.flatnonzero(flagged)],
        "weekday_offsets": weekly.day_of_week_offsets(kept_dates, w["value"], w["trend"]),
        "weekly": weekly.aggregate(kept_dates, w["value"], "week"),
        "monthly": weekly.aggregate(kept_dates, w["value"], "month"),
        "summary": summary,
    }
