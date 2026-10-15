"""Serves the static upload UI bundled into the Lambda package."""

import json
import os
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1] / "ui"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def handler(event: dict, context: object) -> dict:
    """Return the requested UI file, or the sign-in settings the page needs at /config.json."""
    if event["rawPath"] == "/config.json":
        auth = {"domain": os.environ["AUTH_DOMAIN"], "client_id": os.environ["AUTH_CLIENT_ID"]}
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Cache-Control": "no-cache"},
            "body": json.dumps({"auth": auth}),
        }
    name, content_type = FILES[event["rawPath"]]
    return {
        "statusCode": 200,
        "headers": {"Content-Type": content_type, "Cache-Control": "no-cache"},
        "body": (UI_DIR / name).read_text(),
    }
