import os
import uuid

import boto3

from loan_engine import batches
from loan_engine.db import shared_connection
from loan_engine.handlers.http import json_response

s3 = boto3.client("s3")

FUNNEL_QUERY = "select * from match_runs where batch_id = cast(:batch_id as uuid)"

NOTIFICATIONS_QUERY = """
select status, count(*) from notifications
where batch_id = cast(:batch_id as uuid)
group by status
"""


def handler(event: dict, context: object) -> dict:
    batch_id = event["pathParameters"]["batch_id"]
    try:
        uuid.UUID(batch_id)
    except ValueError:
        return json_response(404, {"error": "Upload not found."})
    conn = shared_connection()
    batch = batches.get(conn, batch_id)
    if batch is None:
        return json_response(404, {"error": "Upload not found."})

    funnel_rows = conn.run(FUNNEL_QUERY, batch_id=batch_id)
    funnel = dict(zip((c["name"] for c in conn.columns), funnel_rows[0], strict=True)) if funnel_rows else None
    notifications = {status: count for status, count in conn.run(NOTIFICATIONS_QUERY, batch_id=batch_id)}

    errors_url = None
    if batch["errors_key"]:
        errors_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["UPLOAD_BUCKET"], "Key": batch["errors_key"]},
            ExpiresIn=600,
        )

    return json_response(
        200,
        {"batch": batch, "funnel": funnel, "notifications": notifications, "errors_url": errors_url},
    )
