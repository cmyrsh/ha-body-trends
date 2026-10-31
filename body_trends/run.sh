#!/usr/bin/with-contenv bashio
export BT_DB=/data/body.db
export BT_OPTIONS=/data/options.json
export BT_EXPORT_DIR=/share/body_trends/exports
export BT_SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
cd /app
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8099
