import json
import os
import urllib.request

from loan_engine.signing import sign


def trigger_matching(batch_id: str) -> None:
    body = json.dumps({"batch_id": batch_id}).encode()
    request = urllib.request.Request(
        os.environ["N8N_WEBHOOK_URL"],
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Signature": sign(body, os.environ["WEBHOOK_SECRET"]),
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()
