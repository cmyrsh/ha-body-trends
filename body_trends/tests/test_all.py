import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import export, main, mqtt_ingest
from app.analysis import forecast, outliers, smoothing, trend
from app.pipeline import analyze
from app.store import Store


def series(days=60, start=90.0, slope_per_day=-0.05, noise=0.2, seed=1):
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 1, 1, 7, tzinfo=timezone.utc)
    return [
        {"ts": (t0 + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "weight": start + slope_per_day * i + rng.normal(0, noise), "bodyFatPercent": 25.0 - 0.02 * i}
        for i in range(days)
    ]


def test_hampel_flags_spike():
    v = [80.0 + 0.1 * (i % 3) for i in range(20)]
    v[10] = 95
    assert outliers.hampel_mask(v).nonzero()[0].tolist() == [10]


def test_ewma_handles_gaps():
    t = [0, 1, 20]
    out = smoothing.ewma_trend(t, [80, 80, 90], alpha=0.1)
    assert 80 < out[2] < 90 and out[2] > 80 + 10 * 0.1  # longer gap moves the trend further


def test_theil_sen_recovers_slope():
    t = np.arange(60)
    s = trend.slope_per_week(t, 90 - 0.05 * t, 30)
    assert s["per_week"] == pytest.approx(-0.35, abs=0.01) and not s["plateau"]


def test_plateau_detected():
    t = np.arange(40)
    rng = np.random.default_rng(1)
    assert trend.slope_per_week(t, 80 + rng.normal(0, 0.3, 40), 30)["plateau"]


def test_goal_eta_downward():
    fc = forecast.holt_damped(np.arange(40), 90 - 0.1 * np.arange(40), horizon=120)
    assert forecast.goal_eta(fc, 86.0, 85.0) is not None


def test_analyze_with_outlier_and_profile():
    rows = series()
    rows[30]["weight"] = 130
    res = analyze(rows, {"height_cm": 180, "sex": "male", "goal_weight": 85})
    assert rows[30]["ts"] in res["outliers"]
    assert res["trends"]["weight"]["30d"]["per_week"] == pytest.approx(-0.35, abs=0.1)
    assert res["summary"]["bmi_band"] and "ffmi" in res["summary"]


def test_analyze_empty():
    assert analyze([], None)["n"] == 0


def test_ingest_dedupe_and_users(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    p = json.dumps({"timestamp": "2026-01-01T07:00:00Z", "weight": 80.5, "bodyFatPercent": 20}).encode()
    assert mqtt_ingest.handle_message(st, "scale/body-composition", "scale/body-composition/alice", p)
    assert not mqtt_ingest.handle_message(st, "scale/body-composition", "scale/body-composition/alice", p)
    assert mqtt_ingest.handle_message(st, "scale/body-composition", "scale/body-composition/bob", p)
    assert [u["slug"] for u in st.users()] == ["alice", "bob"]


@pytest.mark.parametrize("payload", [b"nope", b"{}", b'{"timestamp":"x","weight":-1}', b'{"timestamp":"2026-01-01T00:00:00Z"}'])
def test_ingest_rejects_bad(tmp_path, payload):
    st = Store(str(tmp_path / "t.db"))
    assert not mqtt_ingest.handle_message(st, "b", "b/alice", payload)


def test_export_anonymized(tmp_path):
    rows = series(20)
    for r in rows:
        r["impedance"] = 500.0
    ctype, body = export.build("alice", rows, {"slug": "alice", "birth_year": 1980, "height_cm": 180}, "md")
    assert "alice" not in body and "impedance" not in body and "1980" not in body and "2026-01" not in body
    assert "day 0" in body
    _, csv_body = export.build("alice", rows, None, "csv", anonymize=False)
    assert "impedance" in csv_body and "2026-01-01" in csv_body


def test_api_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(str(tmp_path / "api.db")))
    for r in series(30):
        main.store.upsert_measurement("alice", r["ts"], {"weight": r["weight"]})
    c = TestClient(main.app)
    assert c.get("/api/users").json()[0]["slug"] == "alice"
    c.put("/api/users/alice", json={"height_cm": 175, "goal_weight": 85})
    a = c.get("/api/users/alice/analysis").json()
    assert a["n"] == 30 and a["summary"]["goal_weight"] == 85
    assert c.get("/api/export?user=alice&format=md").status_code == 200
    assert c.get("/api/export?user=nobody").status_code == 404
    csv_file = "timestamp,weight\n2025-12-01T07:00:00Z,91.0\n"
    r = c.post("/api/import/alice", files={"file": ("h.csv", csv_file)})
    assert r.json() == {"added": 1, "skipped": 0}


class FakeClient:
    def __init__(self):
        self.published, self.subscribed = {}, []

    def publish(self, topic, payload, retain=False):
        self.published[topic] = payload

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)


def test_publish_user_and_export_file(tmp_path, monkeypatch):
    from app import mqtt_publish
    monkeypatch.setenv("BT_EXPORT_DIR", str(tmp_path / "exports"))
    st = Store(str(tmp_path / "p.db"))
    for r in series(30):
        st.upsert_measurement("alice", r["ts"], {"weight": r["weight"], "bodyFatPercent": r["bodyFatPercent"]})
    c = FakeClient()
    mqtt_publish.publish_user(c, st, "alice", {})
    state = json.loads(c.published["body_trends/alice/state"])
    assert state["trend_weight"] and state["weight_rate_30d"] < 0
    assert "homeassistant/button/body_trends_alice/export/config" in c.published
    path = mqtt_publish.write_export(st, "alice", {})
    assert path.exists() and "alice" not in path.read_text()
