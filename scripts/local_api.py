"""Serve the UI and upload API locally, standing in for API Gateway, S3 and the Lambdas."""

import threading
import uuid
from email import message_from_bytes
from email.policy import HTTP
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ingest_local import ingest_file
from loan_engine import batches, report
from loan_engine.db import connect
from loan_engine.handlers.create_upload import MAX_UPLOAD_BYTES
from loan_engine.handlers.http import json_response

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data" / "uploads"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def _batch_id(path: str, prefix: str) -> str | None:
    try:
        return str(uuid.UUID(path.removeprefix(prefix)))
    except ValueError:
        return None


def _uploaded_file(content_type: str, body: bytes) -> bytes | None:
    form = message_from_bytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body, policy=HTTP
    )
    for part in form.iter_parts():
        if part.get_param("name", header="content-disposition") == "file":
            return part.get_payload(decode=True)
    return None


def _ingest_in_background(batch_id: str, csv_path: Path) -> None:
    conn = connect()
    try:
        ingest_file(conn, batch_id, csv_path)
    finally:
        conn.close()


class LocalApi(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/uploads/"):
            self._status(_batch_id(self.path, "/uploads/"))
        elif self.path.startswith("/errors/"):
            self._errors_file(_batch_id(self.path, "/errors/"))
        elif self.path in STATIC:
            name, content_type = STATIC[self.path]
            self._send(HTTPStatus.OK, (ROOT / "ui" / name).read_bytes(), content_type)
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if self.path == "/uploads":
            self._create_upload()
        elif self.path.startswith("/local-upload/"):
            self._receive_upload(_batch_id(self.path, "/local-upload/"))
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def _create_upload(self) -> None:
        batch_id = str(uuid.uuid4())
        conn = connect()
        batches.create(conn, batch_id, f"uploads/{batch_id}.csv")
        conn.close()
        upload = {"url": f"/local-upload/{batch_id}", "fields": {}}
        self._json(
            HTTPStatus.CREATED,
            {"batch_id": batch_id, "upload": upload, "max_bytes": MAX_UPLOAD_BYTES},
        )

    def _receive_upload(self, batch_id: str | None) -> None:
        length = int(self.headers.get("Content-Length", 0))
        if batch_id is None or not 0 < length <= MAX_UPLOAD_BYTES + 64 * 1024:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid upload."})
            return
        data = _uploaded_file(
            self.headers.get("Content-Type", ""), self.rfile.read(length)
        )
        if not data:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "The form has no file field."})
            return
        UPLOADS.mkdir(parents=True, exist_ok=True)
        csv_path = UPLOADS / f"{batch_id}.csv"
        csv_path.write_bytes(data)
        threading.Thread(
            target=_ingest_in_background, args=(batch_id, csv_path), daemon=True
        ).start()
        self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")

    def _status(self, batch_id: str | None) -> None:
        conn = connect()
        body = report.describe(conn, batch_id) if batch_id else None
        conn.close()
        if body is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Upload not found."})
            return
        body["errors_url"] = (
            f"/errors/{batch_id}" if body["batch"]["errors_key"] else None
        )
        self._json(HTTPStatus.OK, body)

    def _errors_file(self, batch_id: str | None) -> None:
        conn = connect()
        batch = batches.get(conn, batch_id) if batch_id else None
        conn.close()
        if batch is None or not batch["errors_key"]:
            self._json(
                HTTPStatus.NOT_FOUND, {"error": "No rejected rows for this upload."}
            )
            return
        self._send(
            HTTPStatus.OK,
            Path(batch["errors_key"]).read_bytes(),
            "text/csv; charset=utf-8",
        )

    def _json(self, status: HTTPStatus, body: dict) -> None:
        response = json_response(status, body)
        self._send(
            status, response["body"].encode(), response["headers"]["Content-Type"]
        )

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8040), LocalApi)
    print("UI and API on http://localhost:8040")
    server.serve_forever()
