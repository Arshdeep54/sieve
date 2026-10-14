import io

import pytest

from loan_engine.ingest import InvalidFileError, ingest_users

HEADER = "user_id,name,email,monthly_income,credit_score,employment_status,age"
ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"


def _ingest(conn, batch_id, *rows):
    errors = io.StringIO()
    result = ingest_users(conn, batch_id, [HEADER, *rows], errors)
    return result, errors.getvalue().splitlines()[1:]


def test_upserts_valid_rows_and_reports_rejects(conn, batch_id):
    result, errors = _ingest(
        conn,
        batch_id,
        f"{ALICE},Alice,a@example.com,50000,720,Salaried,30",
        f"{BOB},Bob,b@example.com,40000,999,Business,40",
    )
    assert (result.total_rows, result.valid_rows, result.rejected_rows) == (2, 1, 1)
    assert errors[0].startswith("3,credit_score")
    assert conn.run("select user_id::text, employment_status from users") == [[ALICE, "salaried"]]


def test_last_duplicate_in_file_wins(conn, batch_id):
    _ingest(
        conn,
        batch_id,
        f"{ALICE},Alice,a@example.com,50000,720,Salaried,30",
        f"{ALICE},Alice,a@example.com,90000,780,Salaried,31",
    )
    assert conn.run("select monthly_income, credit_score from users") == [[90000, 780]]


def test_reupload_updates_user_and_moves_it_to_the_new_batch(conn, batch_id):
    _ingest(conn, batch_id, f"{ALICE},Alice,a@example.com,50000,720,Salaried,30")
    second = "33333333-3333-4333-8333-333333333333"
    conn.run("insert into upload_batches (batch_id, s3_key) values (cast(:id as uuid), 'test')", id=second)
    _ingest(conn, second, f"{ALICE},Alice,a@example.com,60000,730,Salaried,30")
    assert conn.run("select batch_id::text, monthly_income from users") == [[second, 60000]]


def test_rejects_file_missing_required_columns(conn, batch_id):
    with pytest.raises(InvalidFileError, match="credit_score"):
        ingest_users(conn, batch_id, ["user_id,email,monthly_income,employment_status,age"], io.StringIO())
