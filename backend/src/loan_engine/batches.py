"""Upload batch lifecycle: one row per upload, moved through pending, ingesting, ingested and onward."""

import pg8000.native


def create(
    conn: pg8000.native.Connection,
    batch_id: str,
    s3_key: str,
    file_name: str | None = None,
    uploaded_by: str | None = None,
) -> None:
    """Register a batch before the browser uploads, so the S3 event can find it."""
    conn.run(
        """
        insert into upload_batches (batch_id, s3_key, file_name, uploaded_by)
        values (cast(:batch_id as uuid), :s3_key, :file_name, :uploaded_by)
        """,
        batch_id=batch_id,
        s3_key=s3_key,
        file_name=file_name,
        uploaded_by=uploaded_by,
    )


def recent(conn: pg8000.native.Connection, limit: int = 20) -> list[dict]:
    """Return the latest batches, newest first, for the uploads list."""
    rows = conn.run(
        """
        select batch_id, file_name, uploaded_by, status, valid_rows, created_at
        from upload_batches
        order by created_at desc
        limit :limit
        """,
        limit=limit,
    )
    return [dict(zip((column["name"] for column in conn.columns), row, strict=True)) for row in rows]


def get(conn: pg8000.native.Connection, batch_id: str) -> dict | None:
    """Return the batch row as a dict, or None if it does not exist."""
    rows = conn.run(
        "select * from upload_batches where batch_id = cast(:batch_id as uuid)",
        batch_id=batch_id,
    )
    if not rows:
        return None
    return dict(zip((column["name"] for column in conn.columns), rows[0], strict=True))


def find_live_duplicate(conn: pg8000.native.Connection, batch_id: str, etag: str) -> str | None:
    """Return an earlier batch with the same file ETag, ignoring failed, pending and duplicate ones."""
    rows = conn.run(
        """
        select batch_id from upload_batches
        where etag = :etag
          and batch_id <> cast(:batch_id as uuid)
          and status not in ('duplicate', 'failed', 'pending')
        limit 1
        """,
        etag=etag,
        batch_id=batch_id,
    )
    return str(rows[0][0]) if rows else None


def mark_duplicate(conn: pg8000.native.Connection, batch_id: str, original_id: str) -> None:
    """Close a batch whose file was already ingested, pointing at the original."""
    conn.run(
        """
        update upload_batches
        set status = 'duplicate', duplicate_of = cast(:original_id as uuid), updated_at = now()
        where batch_id = cast(:batch_id as uuid)
        """,
        batch_id=batch_id,
        original_id=original_id,
    )


def mark_ingesting(conn: pg8000.native.Connection, batch_id: str, etag: str | None) -> None:
    """Record the file ETag and clear any previous error before ingestion starts."""
    conn.run(
        """
        update upload_batches
        set status = 'ingesting', etag = :etag, error = null, updated_at = now()
        where batch_id = cast(:batch_id as uuid)
        """,
        batch_id=batch_id,
        etag=etag,
    )


def mark_ingested(
    conn: pg8000.native.Connection,
    batch_id: str,
    total_rows: int,
    valid_rows: int,
    errors_key: str | None,
) -> None:
    """Store row counts and the rejected-rows file key once ingestion succeeds."""
    conn.run(
        """
        update upload_batches
        set status = 'ingested',
            total_rows = :total_rows,
            valid_rows = :valid_rows,
            rejected_rows = :rejected_rows,
            errors_key = :errors_key,
            updated_at = now()
        where batch_id = cast(:batch_id as uuid)
        """,
        batch_id=batch_id,
        total_rows=total_rows,
        valid_rows=valid_rows,
        rejected_rows=total_rows - valid_rows,
        errors_key=errors_key,
    )


def mark_failed(conn: pg8000.native.Connection, batch_id: str, error: str) -> None:
    """Mark the batch failed with a message the UI can show."""
    conn.run(
        """
        update upload_batches
        set status = 'failed', error = :error, updated_at = now()
        where batch_id = cast(:batch_id as uuid)
        """,
        batch_id=batch_id,
        error=error,
    )
