from loan_engine.db import connect
from loan_engine.migrate import migrate


def handler(event: dict, context: object) -> dict:
    return {"applied": migrate(connect())}
