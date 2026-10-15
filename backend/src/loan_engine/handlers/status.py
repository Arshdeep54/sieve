"""GET /uploads and GET /uploads/{batch_id}: the uploads list and the progress report polled by the UI."""

import os
import uuid

import boto3
from botocore.config import Config

from loan_engine import batches, report
from loan_engine.db import shared_connection
from loan_engine.handlers.http import json_response

s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))


def handler(event: dict, context: object) -> dict:
    """Return recent uploads, or one batch report with a short-lived link to its rejected-rows file."""
    if event["routeKey"] == "GET /uploads":
        return json_response(200, {"uploads": batches.recent(shared_connection())})
    batch_id = event["pathParameters"]["batch_id"]
    try:
        uuid.UUID(batch_id)
    except ValueError:
        return json_response(404, {"error": "Upload not found."})
    body = report.describe(shared_connection(), batch_id)
    if body is None:
        return json_response(404, {"error": "Upload not found."})

    errors_key = body["batch"]["errors_key"]
    body["errors_url"] = (
        s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["UPLOAD_BUCKET"], "Key": errors_key},
            ExpiresIn=600,
        )
        if errors_key
        else None
    )
    return json_response(200, body)
