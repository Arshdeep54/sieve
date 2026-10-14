"""Lambda that applies database migrations from inside the VPC."""

from loan_engine.db import connect
from loan_engine.migrate import migrate


def handler(event: dict, context: object) -> dict:
    """Apply pending migrations and return their names."""
    return {"applied": migrate(connect())}
