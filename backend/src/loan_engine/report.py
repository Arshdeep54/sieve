"""Batch progress report served to the upload UI."""

import pg8000.native

from loan_engine import batches

FUNNEL_QUERY = "select * from match_runs where batch_id = cast(:batch_id as uuid)"

NOTIFICATIONS_QUERY = """
select status, count(*) from notifications
where batch_id = cast(:batch_id as uuid)
group by status
"""

PRODUCTS_QUERY = """
select p.lender, p.product_name, count(*) as matches, round(avg(m.score), 3) as avg_score
from matches m
join loan_products p on p.product_id = m.product_id
where m.batch_id = cast(:batch_id as uuid)
group by p.lender, p.product_name
order by matches desc, p.lender
"""

STAGES_QUERY = """
select stage, count(*) from matches
where batch_id = cast(:batch_id as uuid)
group by stage
"""


def describe(conn: pg8000.native.Connection, batch_id: str) -> dict | None:
    """Return the batch with its matching funnel, matches per product and email counts, or None."""
    batch = batches.get(conn, batch_id)
    if batch is None:
        return None
    funnel_rows = conn.run(FUNNEL_QUERY, batch_id=batch_id)
    funnel = dict(zip((c["name"] for c in conn.columns), funnel_rows[0], strict=True)) if funnel_rows else None
    return {
        "batch": batch,
        "funnel": funnel,
        "stages": dict(conn.run(STAGES_QUERY, batch_id=batch_id)),
        "products": [
            {"lender": lender, "product_name": name, "matches": matches, "avg_score": avg_score}
            for lender, name, matches, avg_score in conn.run(PRODUCTS_QUERY, batch_id=batch_id)
        ],
        "notifications": dict(conn.run(NOTIFICATIONS_QUERY, batch_id=batch_id)),
    }
