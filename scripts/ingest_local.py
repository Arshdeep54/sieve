"""Run the ingest pipeline against the local stack, standing in for S3 + the ingest Lambda."""

import sys
import uuid
from pathlib import Path

from loan_engine import batches, n8n
from loan_engine.db import connect
from loan_engine.ingest import ingest_users


def main(csv_path: Path) -> None:
    conn = connect()
    batch_id = str(uuid.uuid4())
    batches.create(conn, batch_id, f"local/{csv_path.name}")
    batches.mark_ingesting(conn, batch_id, None)
    errors_path = csv_path.with_name(f"{csv_path.stem}.{batch_id}.errors.csv")
    with (
        csv_path.open(encoding="utf-8-sig", newline="") as lines,
        errors_path.open("w", newline="") as errors,
    ):
        result = ingest_users(conn, batch_id, lines, errors)
    batches.mark_ingested(
        conn, batch_id, result.total_rows, result.valid_rows, str(errors_path)
    )
    print(
        f"batch {batch_id}: {result.valid_rows}/{result.total_rows} valid, errors -> {errors_path}"
    )
    n8n.trigger_matching(batch_id)
    print("matching triggered")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
