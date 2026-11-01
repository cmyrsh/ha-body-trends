"""Subscribe to BLE Scale Sync topics and store readings."""
import json
import logging
import os

import paho.mqtt.client as mqtt

from .store import FIELDS, Store

log = logging.getLogger("body_trends.mqtt")


def parse_payload(payload: bytes | str) -> tuple[str, dict, dict] | None:
    """Return (timestamp, known fields, extra fields) or None if unusable."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("timestamp"), str):
        return None
    values = {k: data[k] for k in FIELDS if isinstance(data.get(k), (int, float)) and not isinstance(data.get(k), bool)}
    if "weight" not in values or values["weight"] <= 0:
        return None
    extra = {k: v for k, v in data.items() if k not in FIELDS and k != "timestamp"}
    return data["timestamp"], values, extra


def handle_message(store: Store, base_topic: str, topic: str, payload: bytes) -> bool:
    prefix = base_topic.rstrip("/") + "/"
    if not topic.startswith(prefix):
        return False
    user = topic[len(prefix):]
    if not user or "/" in user:
        return False
    parsed = parse_payload(payload)
    if not parsed:
        log.warning("Ignoring unusable payload on %s", topic)
        return False
    ts, values, extra = parsed
    try:
        return store.upsert_measurement(user, ts, values, extra)
    except ValueError:
        log.warning("Bad timestamp on %s", topic)
        return False


def load_options() -> dict:
    path = os.environ.get("BT_OPTIONS", "/data/options.json")
    try:
        with open(path) as f:
            return json.load(f)
    except OSError:
        return {}


def start(store: Store, opts: dict, on_new=None, on_export=None) -> mqtt.Client | None:
    host = opts.get("mqtt_host") or os.environ.get("BT_MQTT_HOST")
    if not host:
        log.warning("No MQTT host configured; ingest disabled")
        return None
    base = opts.get("base_topic", "scale/body-composition")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if opts.get("mqtt_username"):
        client.username_pw_set(opts["mqtt_username"], opts.get("mqtt_password"))

    def on_connect(c, _u, _f, reason_code, *_):
        log.info("MQTT connected to %s (%s); subscribing to %s/+", host, reason_code, base)
        c.subscribe(f"{base}/+", qos=1)
        for u in store.users():
            if on_new:
                on_new(c, u["slug"])

    def on_message(c, _u, msg):
        log.debug("MQTT recv topic=%s payload=%r", msg.topic, msg.payload[:500])
        if msg.topic.startswith("body_trends/") and msg.topic.endswith("/export"):
            if on_export:
                on_export(msg.topic.split("/")[1])
        else:
            stored = handle_message(store, base, msg.topic, msg.payload)
            log.debug("MQTT topic=%s stored=%s", msg.topic, stored)
            if stored and on_new:
                on_new(c, msg.topic[len(base) + 1:])

    def on_disconnect(_c, _u, _f, reason_code, *_):
        log.warning("MQTT disconnected (%s)", reason_code)

    def on_subscribe(_c, _u, _mid, reason_codes, *_):
        log.debug("MQTT subscribe result: %s", reason_codes)

    client.on_connect, client.on_message = on_connect, on_message
    client.on_disconnect, client.on_subscribe = on_disconnect, on_subscribe
    client.connect_async(host, int(opts.get("mqtt_port") or 1883))
    client.loop_start()
    return client
