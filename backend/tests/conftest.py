import os
import uuid
from pathlib import Path

import pg8000.native
import pytest

from loan_engine.migrate import migrate

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
TEST_DATABASE = "loan_engine_test"


def _admin_connection(database: str) -> pg8000.native.Connection:
    return pg8000.native.Connection(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "55432")),
        user=os.environ.get("DB_USER", "loan_engine"),
        password=os.environ["DB_PASSWORD"],
        database=database,
    )


@pytest.fixture(scope="session")
def database() -> str:
    admin = _admin_connection(os.environ.get("DB_NAME", "loan_engine"))
    admin.run(f"drop database if exists {TEST_DATABASE} with (force)")
    admin.run(f"create database {TEST_DATABASE}")
    admin.close()
    conn = _admin_connection(TEST_DATABASE)
    migrate(conn, MIGRATIONS)
    conn.close()
    return TEST_DATABASE


@pytest.fixture
def conn(database: str) -> pg8000.native.Connection:
    connection = _admin_connection(database)
    yield connection
    connection.run("truncate upload_batches, users, matches, notifications, match_runs cascade")
    connection.close()


@pytest.fixture
def batch_id(conn: pg8000.native.Connection) -> str:
    new_id = str(uuid.uuid4())
    conn.run("insert into upload_batches (batch_id, s3_key) values (cast(:id as uuid), 'test')", id=new_id)
    return new_id
