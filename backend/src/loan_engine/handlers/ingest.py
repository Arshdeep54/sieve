import codecs
import logging
import tempfile
from urllib.parse import unquote_plus

import boto3

from loan_engine import batches, n8n
from loan_engine.db import shared_connection
from loan_engine.ingest import InvalidFileError, ingest_users

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

ALREADY_INGESTED = ("ingested", "matching", "matched", "notifying", "done")


def handler(event: dict, context: object) -> None:
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        process_upload(bucket, key)


def process_upload(bucket: str, key: str) -> None:
    conn = shared_connection()
    batch_id = key.removeprefix("uploads/").removesuffix(".csv")
    batch = batches.get(conn, batch_id)
    if batch is None:
        logger.warning("Ignoring upload without a registered batch: %s", key)
        return
    if batch["status"] in ALREADY_INGESTED:
        n8n.trigger_matching(batch_id)
        return
    if batch["status"] == "duplicate":
        return

    obj = s3.get_object(Bucket=bucket, Key=key)
    etag = obj["ETag"].strip('"')
    original_id = batches.find_live_duplicate(conn, batch_id, etag)
    if original_id:
        batches.mark_duplicate(conn, batch_id, original_id)
        logger.info("Batch %s duplicates %s", batch_id, original_id)
        return

    batches.mark_ingesting(conn, batch_id, etag)
    lines = codecs.iterdecode(obj["Body"].iter_lines(), "utf-8-sig")
    with tempfile.TemporaryFile("w+", newline="") as errors:
        try:
            result = ingest_users(conn, batch_id, lines, errors)
        except InvalidFileError as error:
            batches.mark_failed(conn, batch_id, str(error))
            return
        except Exception as error:
            batches.mark_failed(conn, batch_id, f"Ingestion failed: {error}")
            raise
        errors_key = None
        if result.rejected_rows:
            errors_key = f"errors/{batch_id}.csv"
            errors.seek(0)
            s3.put_object(Bucket=bucket, Key=errors_key, Body=errors.read().encode(), ContentType="text/csv")

    batches.mark_ingested(conn, batch_id, result.total_rows, result.valid_rows, errors_key)
    logger.info("Batch %s ingested %s/%s rows", batch_id, result.valid_rows, result.total_rows)
    n8n.trigger_matching(batch_id)
