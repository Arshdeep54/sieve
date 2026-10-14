"""Apply SQL migrations in filename order, once each, recording them in schema_migrations."""

from pathlib import Path

import pg8000.native

from loan_engine.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

CREATE_MIGRATIONS_TABLE = """
create table if not exists schema_migrations (
    version text primary key,
    applied_at timestamptz not null default now()
)
"""


def migrate(conn: pg8000.native.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations, each in its own transaction, and return the names applied."""
    conn.run(CREATE_MIGRATIONS_TABLE)
    applied = {row[0] for row in conn.run("select version from schema_migrations")}
    newly_applied = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in applied:
            continue
        conn.run("begin")
        try:
            conn.execute_simple(path.read_text())
            conn.run("insert into schema_migrations (version) values (:version)", version=path.name)
            conn.run("commit")
        except Exception:
            conn.run("rollback")
            raise
        newly_applied.append(path.name)
    return newly_applied


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else MIGRATIONS_DIR
    print(migrate(connect(), target) or "up to date")
