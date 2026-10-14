"""HMAC signatures for webhooks sent to n8n."""

import hashlib
import hmac
import time


def sign(body: bytes, secret: str, timestamp: int | None = None) -> str:
    """Sign the timestamp and body so n8n can reject forged or replayed requests."""
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"
