"""SQLite persistence for users, profiles and measurements."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

FIELDS = [
    "weight", "impedance", "bmi", "bodyFatPercent", "waterPercent", "boneMass",
    "muscleMass", "visceralFat", "physiqueRating", "bmr", "metabolicAge",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    slug TEXT PRIMARY KEY,
    height_cm REAL, birth_year INTEGER, sex TEXT, goal_weight REAL
);
CREATE TABLE IF NOT EXISTS measurements (
    user TEXT NOT NULL,
    ts TEXT NOT NULL,
    weight REAL, impedance REAL, bmi REAL, bodyFatPercent REAL, waterPercent REAL,
    boneMass REAL, muscleMass REAL, visceralFat REAL, physiqueRating REAL,
    bmr REAL, metabolicAge REAL, extra TEXT,
    PRIMARY KEY (user, ts)
);
"""


def normalize_ts(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(_SCHEMA)

    def upsert_measurement(self, user: str, ts: str, values: dict, extra: dict | None = None) -> bool:
        """Insert a reading; returns False if (user, ts) already exists."""
        ts = normalize_ts(ts)
        cols = [f for f in FIELDS if values.get(f) is not None]
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO users(slug) VALUES (?)", (user,))
            cur = self._db.execute(
                f"INSERT OR IGNORE INTO measurements(user, ts, extra{''.join(',' + c for c in cols)}) "
                f"VALUES (?,?,?{',?' * len(cols)})",
                [user, ts, json.dumps(extra) if extra else None, *[values[c] for c in cols]],
            )
            self._db.commit()
            return cur.rowcount == 1

    def users(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM users ORDER BY slug").fetchall()
        return [dict(r) for r in rows]

    def get_user(self, slug: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM users WHERE slug=?", (slug,)).fetchone()
        return dict(row) if row else None

    def set_profile(self, slug: str, **profile) -> None:
        allowed = {"height_cm", "birth_year", "sex", "goal_weight"}
        data = {k: v for k, v in profile.items() if k in allowed}
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO users(slug) VALUES (?)", (slug,))
            for k, v in data.items():
                self._db.execute(f"UPDATE users SET {k}=? WHERE slug=?", (v, slug))
            self._db.commit()

    def measurements(self, user: str, start: str | None = None, end: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM measurements WHERE user=?", [user]
        if start:
            q += " AND ts>=?"; args.append(normalize_ts(start))
        if end:
            q += " AND ts<=?"; args.append(normalize_ts(end))
        with self._lock:
            rows = self._db.execute(q + " ORDER BY ts", args).fetchall()
        return [dict(r) for r in rows]
