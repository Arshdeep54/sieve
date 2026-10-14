"""Streaming CSV ingestion: validate rows, COPY them into a staging table, then upsert users."""

import csv
import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TextIO

import pg8000.native

from loan_engine.rows import RowError, UserRow, missing_columns, parse_row

COPY_CHUNK_ROWS = 2000

CREATE_STAGING = """
create temp table users_staging (
    line_no integer,
    user_id uuid,
    name text,
    email text,
    monthly_income integer,
    credit_score smallint,
    employment_status text,
    age smallint
) on commit drop
"""

COPY_STAGING = "copy users_staging from stdin with (format csv)"

UPSERT_USERS = """
insert into users (user_id, name, email, monthly_income, credit_score, employment_status, age, batch_id)
select distinct on (user_id)
       user_id, name, email, monthly_income, credit_score, employment_status, age, cast(:batch_id as uuid)
from users_staging
order by user_id, line_no desc
on conflict (user_id) do update set
    name = excluded.name,
    email = excluded.email,
    monthly_income = excluded.monthly_income,
    credit_score = excluded.credit_score,
    employment_status = excluded.employment_status,
    age = excluded.age,
    batch_id = excluded.batch_id,
    updated_at = now()
"""


class InvalidFileError(ValueError):
    """The file as a whole is unusable, e.g. empty or missing required columns."""

    pass


@dataclass
class IngestResult:
    """Row counts reported back to the batch record."""

    total_rows: int = 0
    valid_rows: int = 0
    users_upserted: int = 0

    @property
    def rejected_rows(self) -> int:
        return self.total_rows - self.valid_rows


def ingest_users(
    conn: pg8000.native.Connection,
    batch_id: str,
    lines: Iterable[str],
    errors: TextIO,
) -> IngestResult:
    """Validate a users CSV and upsert it in one transaction, streaming rows through COPY."""
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        raise InvalidFileError("The file is empty.")
    missing = missing_columns(reader.fieldnames)
    if missing:
        raise InvalidFileError(f"Missing required columns: {', '.join(missing)}.")

    result = IngestResult()
    error_writer = csv.writer(errors)
    error_writer.writerow(["line", "reason", "row"])

    def valid_rows() -> Iterator[tuple[int, UserRow]]:
        for raw in reader:
            result.total_rows += 1
            try:
                row = parse_row(raw)
            except RowError as error:
                raw_line = ",".join(str(value) for value in raw.values() if value is not None)
                error_writer.writerow([reader.line_num, str(error), raw_line])
                continue
            result.valid_rows += 1
            yield reader.line_num, row

    conn.run("begin")
    try:
        conn.run(CREATE_STAGING)
        conn.run(COPY_STAGING, stream=_csv_chunks(valid_rows()))
        conn.run(UPSERT_USERS, batch_id=batch_id)
        result.users_upserted = conn.row_count
        conn.run("commit")
    except Exception:
        conn.run("rollback")
        raise
    return result


def _csv_chunks(rows: Iterable[tuple[int, UserRow]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    pending = 0
    for line_no, row in rows:
        writer.writerow(
            [
                line_no,
                row.user_id,
                row.name,
                row.email,
                row.monthly_income,
                row.credit_score,
                row.employment_status,
                row.age,
            ]
        )
        pending += 1
        if pending == COPY_CHUNK_ROWS:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
            pending = 0
    if pending:
        yield buffer.getvalue()
