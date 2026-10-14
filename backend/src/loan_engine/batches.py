import pg8000.native


def create(conn: pg8000.native.Connection, batch_id: str, s3_key: str) -> None:
    conn.run(
        "insert into upload_batches (batch_id, s3_key) values (cast(:batch_id as uuid), :s3_key)",
        batch_id=batch_id,
        s3_key=s3_key,
    )


def get(conn: pg8000.native.Connection, batch_id: str) -> dict | None:
    rows = conn.run(
        "select * from upload_batches where batch_id = cast(:batch_id as uuid)",
        batch_id=batch_id,
    )
    if not rows:
        return None
    return dict(zip((column["name"] for column in conn.columns), rows[0], strict=True))


def find_live_duplicate(conn: pg8000.native.Connection, batch_id: str, etag: str) -> str | None:
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
    conn.run(
        """
        update upload_batches
        set status = 'failed', error = :error, updated_at = now()
        where batch_id = cast(:batch_id as uuid)
        """,
        batch_id=batch_id,
        error=error,
    )
