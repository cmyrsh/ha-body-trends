"""Export a user's data and analysis as json, csv or a markdown brief for Claude."""
import csv
import io
import json
from datetime import datetime

from .pipeline import _parse, analyze
from .store import FIELDS

PROMPT = """You are a careful analyst of body-composition data. Using only the data below:
1. Describe the weight and body-fat trends and how confident the data allows us to be.
2. Note plateaus, unusual readings, and weekday patterns.
3. Say whether lean mass is being preserved if weight is changing.
4. Suggest practical next steps, and what additional measurements would help.
Impedance-based body fat is noisy: favour trends over single values. This is not medical advice."""


def _anon_dates(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    t0 = _parse(rows[0]["ts"]).date()
    return [{**r, "ts": f"day {(_parse(r['ts']).date() - t0).days}"} for r in rows]


def _fmt(x):
    return "" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def build(user: str, rows: list[dict], profile: dict | None, fmt: str, anonymize: bool = True, opts: dict | None = None):
    """Returns (content_type, body)."""
    result = analyze(rows, profile, opts)
    label = "person" if anonymize else user
    cols = [f for f in FIELDS if not (anonymize and f == "impedance")]
    out_rows = [{"ts": r["ts"], **{c: r.get(c) for c in cols}} for r in rows]
    if anonymize:
        out_rows = _anon_dates(out_rows)

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ts", *cols])
        for r in out_rows:
            w.writerow([r["ts"], *[_fmt(r[c]) for c in cols]])
        return "text/csv", buf.getvalue()

    summary = dict(result.get("summary", {}))
    if anonymize:
        for k in ("first", "last", "goal_eta"):
            summary.pop(k, None)
    prof = {k: v for k, v in (profile or {}).items() if k != "slug" and v is not None}
    if anonymize:
        prof.pop("birth_year", None)

    if fmt == "json":
        payload = {"user": label, "profile": prof, "summary": summary, "trends": result.get("trends"),
                   "weekday_offsets": result.get("weekday_offsets"), "weekly": result.get("weekly"),
                   "outliers": result.get("outliers") if not anonymize else len(result.get("outliers", [])),
                   "measurements": out_rows}
        return "application/json", json.dumps(payload, indent=2)

    lines = [f"# Body measurement export: {label}", "", "## Task", PROMPT, "", "## Profile",
             *[f"- {k}: {v}" for k, v in prof.items()], "", "## Summary",
             *[f"- {k}: {_fmt(v)}" for k, v in summary.items()], "", "## Trends (per week, Theil-Sen on smoothed series)"]
    for metric, wins in (result.get("trends") or {}).items():
        for win, s in wins.items():
            if s:
                lines.append(f"- {metric} {win}: {s['per_week']:+.2f}/wk (95% {s['low']:+.2f}..{s['high']:+.2f})"
                             f"{', plateau' if s['plateau'] else ''}")
    lines += ["", "## Weekday offsets from trend (0=Mon, kg)",
              *[f"- {d}: {v:+.2f}" for d, v in (result.get("weekday_offsets") or {}).items()],
              "", "## Weekly mean weight", "| week | mean | min | max | n |", "|---|---|---|---|---|",
              *[f"| {a['period']} | {a['mean']:.2f} | {a['min']:.2f} | {a['max']:.2f} | {a['n']} |"
                for a in (result.get("weekly") or [])[-26:]],
              "", f"## Readings ({len(out_rows)})", "| " + " | ".join(["ts", *cols]) + " |",
              "|" + "---|" * (len(cols) + 1),
              *["| " + " | ".join([str(r["ts"]), *[_fmt(r[c]) for c in cols]]) + " |" for r in out_rows[-200:]]]
    return "text/markdown", "\n".join(lines) + "\n"
