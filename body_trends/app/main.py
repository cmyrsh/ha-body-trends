"""FastAPI app served through HA ingress."""
import csv
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import export, mqtt_ingest, mqtt_publish
from .pipeline import analyze
from .store import FIELDS, Store

STATIC = Path(__file__).parent / "static"
store: Store | None = None
opts: dict = {}


def get_store() -> Store:
    global store
    if store is None:
        store = Store(os.environ.get("BT_DB", "/data/body.db"))
    return store


@asynccontextmanager
async def lifespan(app: FastAPI):
    global opts
    opts = mqtt_ingest.load_options()
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("body_trends").setLevel(logging.DEBUG if opts.get("debug") else logging.INFO)
    client = mqtt_ingest.start(
        get_store(), opts,
        on_new=lambda c, user: mqtt_publish.publish_user(c, get_store(), user, opts),
        on_export=lambda user: mqtt_publish.write_export(get_store(), user, opts),
    )
    yield
    if client:
        client.loop_stop()


app = FastAPI(lifespan=lifespan)


class Profile(BaseModel):
    height_cm: float | None = None
    birth_year: int | None = None
    sex: str | None = None
    goal_weight: float | None = None


def _user(slug: str) -> dict:
    u = get_store().get_user(slug)
    if not u:
        raise HTTPException(404, "unknown user")
    return u


@app.get("/api/users")
def users():
    return get_store().users()


@app.put("/api/users/{slug}")
def put_profile(slug: str, p: Profile):
    get_store().set_profile(slug, **p.model_dump(exclude_unset=True))
    return get_store().get_user(slug)


@app.get("/api/users/{slug}/analysis")
def analysis(slug: str, start: str | None = None, end: str | None = None):
    u = _user(slug)
    return analyze(get_store().measurements(slug, start, end), u, opts)


@app.get("/api/export")
def export_(user: str, format: str = "md", start: str | None = None, end: str | None = None,
            anonymize: bool = True):
    if format not in ("md", "json", "csv"):
        raise HTTPException(400, "format must be md, json or csv")
    u = _user(user)
    ctype, body = export.build(user, get_store().measurements(user, start, end), u, format, anonymize, opts)
    ext = {"md": "md", "json": "json", "csv": "csv"}[format]
    return Response(body, media_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="body-trends.{ext}"'})


@app.post("/api/import/{slug}")
async def import_(slug: str, file: UploadFile):
    """Backfill from CSV (header row; `timestamp` + known field names) or a JSON list."""
    raw = (await file.read()).decode()
    try:
        records = json.loads(raw) if raw.lstrip().startswith("[") else list(csv.DictReader(io.StringIO(raw)))
    except ValueError:
        raise HTTPException(400, "unparseable file")
    added = skipped = 0
    for rec in records:
        parsed = mqtt_ingest.parse_payload(json.dumps({k: _num(v) for k, v in rec.items()}))
        if parsed and get_store().upsert_measurement(slug, *parsed[:2], parsed[2] or None):
            added += 1
        else:
            skipped += 1
    return {"added": added, "skipped": skipped}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
