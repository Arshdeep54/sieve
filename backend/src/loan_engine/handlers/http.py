"""API Gateway response helpers."""

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID


def json_response(status: int, body: dict) -> dict:
    """Build an HTTP API response, serialising datetimes, UUIDs and decimals."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_encode),
    }


def _encode(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialise {type(value).__name__}")
