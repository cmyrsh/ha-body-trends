"""Publish trend entities (MQTT discovery) and handle the per-user export button."""
import json
import logging
import os
from pathlib import Path

from . import export
from .pipeline import analyze
from .store import Store

log = logging.getLogger("body_trends.publish")
PREFIX = "body_trends"

SENSORS = {
    "trend_weight": ("Trend weight", "kg", "weight", lambda r: r["summary"].get("trend_weight")),
    "weight_rate_30d": ("Weight change (30d)", "kg/wk", None,
                        lambda r: (r["trends"].get("weight", {}).get("30d") or {}).get("per_week")),
    "trend_body_fat": ("Trend body fat", "%", None,
                       lambda r: (r["series"].get("bodyFatPercent") or {}).get("trend", [None])[-1]),
    "lean_mass": ("Lean mass", "kg", "weight", lambda r: r["summary"].get("lean_mass")),
}


def _round(v):
    return None if v is None else round(float(v), 2)


def publish_user(client, store: Store, user: str, opts: dict) -> None:
    node = f"{PREFIX}_{user}"
    device = {"identifiers": [node], "name": f"Body Trends {user}", "manufacturer": "Body Trends"}
    for key, (name, unit, dclass, _) in SENSORS.items():
        cfg = {"name": name, "unique_id": f"{node}_{key}", "device": device,
               "state_topic": f"{PREFIX}/{user}/state", "value_template": f"{{{{ value_json.{key} }}}}",
               "unit_of_measurement": unit, "state_class": "measurement"}
        if dclass:
            cfg["device_class"] = dclass
        client.publish(f"homeassistant/sensor/{node}/{key}/config", json.dumps(cfg), retain=True)
    client.publish(f"homeassistant/button/{node}/export/config", json.dumps({
        "name": "Export trends", "unique_id": f"{node}_export", "device": device,
        "command_topic": f"{PREFIX}/{user}/export"}), retain=True)
    client.subscribe(f"{PREFIX}/{user}/export")
    result = analyze(store.measurements(user), store.get_user(user), opts)
    if result["n"]:
        state = {k: _round(fn(result)) for k, (_, _, _, fn) in SENSORS.items()}
        client.publish(f"{PREFIX}/{user}/state", json.dumps(state), retain=True)


def write_export(store: Store, user: str, opts: dict) -> Path:
    out = Path(os.environ.get("BT_EXPORT_DIR", "/share/body_trends/exports"))
    out.mkdir(parents=True, exist_ok=True)
    _, body = export.build(user, store.measurements(user), store.get_user(user), "md", True, opts)
    path = out / f"{user}-trends.md"
    path.write_text(body)
    log.info("Wrote %s", path)
    return path
