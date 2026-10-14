from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1] / "ui"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def handler(event: dict, context: object) -> dict:
    name, content_type = FILES[event["rawPath"]]
    return {
        "statusCode": 200,
        "headers": {"Content-Type": content_type, "Cache-Control": "no-cache"},
        "body": (UI_DIR / name).read_text(),
    }
