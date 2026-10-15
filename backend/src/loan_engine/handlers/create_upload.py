"""POST /uploads: register a batch and hand the browser a presigned S3 POST."""

import json
import os
import uuid

import boto3
from botocore.config import Config

from loan_engine import batches
from loan_engine.db import shared_connection
from loan_engine.handlers.http import json_response

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
UPLOAD_URL_TTL_SECONDS = 600

s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))


def handler(event: dict, context: object) -> dict:
    """Create the batch and return a presigned POST capped at MAX_UPLOAD_BYTES."""
    batch_id = str(uuid.uuid4())
    key = f"uploads/{batch_id}.csv"
    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    batches.create(shared_connection(), batch_id, key, _file_name(event), claims["email"])
    upload = s3.generate_presigned_post(
        Bucket=os.environ["UPLOAD_BUCKET"],
        Key=key,
        Conditions=[["content-length-range", 1, MAX_UPLOAD_BYTES]],
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )
    return json_response(201, {"batch_id": batch_id, "upload": upload, "max_bytes": MAX_UPLOAD_BYTES})


def _file_name(event: dict) -> str | None:
    try:
        name = json.loads(event.get("body") or "{}").get("file_name")
    except (ValueError, AttributeError):
        return None
    if not isinstance(name, str):
        return None
    return name.strip()[:200] or None
