import os
import uuid

import boto3
from botocore.config import Config

from loan_engine import batches
from loan_engine.db import shared_connection
from loan_engine.handlers.http import json_response

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_URL_TTL_SECONDS = 600

s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))


def handler(event: dict, context: object) -> dict:
    batch_id = str(uuid.uuid4())
    key = f"uploads/{batch_id}.csv"
    batches.create(shared_connection(), batch_id, key)
    upload = s3.generate_presigned_post(
        Bucket=os.environ["UPLOAD_BUCKET"],
        Key=key,
        Conditions=[["content-length-range", 1, MAX_UPLOAD_BYTES]],
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )
    return json_response(201, {"batch_id": batch_id, "upload": upload, "max_bytes": MAX_UPLOAD_BYTES})
