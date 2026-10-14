"""Run the ingest pipeline against the local stack, standing in for S3 + the ingest Lambda."""

import hashlib
import sys
import uuid
from pathlib import Path

import pg8000.native
from loan_engine import batches, n8n
from loan_engine.db import connect
from loan_engine.ingest import InvalidFileError, ingest_users


def ingest_file(conn: pg8000.native.Connection, batch_id: str, csv_path: Path) -> None:
    """Ingest a local CSV the way the ingest Lambda does, including duplicate detection."""
    with csv_path.open("rb") as raw:
        etag = hashlib.file_digest(raw, "md5").hexdigest()
    original_id = batches.find_live_duplicate(conn, batch_id, etag)
    if original_id:
        batches.mark_duplicate(conn, batch_id, original_id)
        print(f"batch {batch_id}: same file as batch {original_id}")
        return

    batches.mark_ingesting(conn, batch_id, etag)
    errors_path = csv_path.with_name(f"{csv_path.stem}.{batch_id}.errors.csv")
    try:
        with (
            csv_path.open(encoding="utf-8-sig", newline="") as lines,
            errors_path.open("w", newline="") as errors,
        ):
            result = ingest_users(conn, batch_id, lines, errors)
    except InvalidFileError as error:
        batches.mark_failed(conn, batch_id, str(error))
        errors_path.unlink(missing_ok=True)
        print(f"batch {batch_id}: {error}")
        return

    errors_key = str(errors_path) if result.rejected_rows else None
    if errors_key is None:
        errors_path.unlink()
    batches.mark_ingested(
        conn, batch_id, result.total_rows, result.valid_rows, errors_key
    )
    print(f"batch {batch_id}: {result.valid_rows}/{result.total_rows} valid")
    n8n.trigger_matching(batch_id)


def main(csv_path: Path) -> None:
    """Register a batch for the file and ingest it."""
    conn = connect()
    batch_id = str(uuid.uuid4())
    batches.create(conn, batch_id, f"local/{csv_path.name}")
    ingest_file(conn, batch_id, csv_path)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
