"""Runs the matching SQL exactly as shipped in the n8n workflow against a real Postgres."""

import json
import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / "n8n" / "workflows" / "B_user_loan_matching.json"
SALARIED = "11111111-1111-4111-8111-111111111111"
LOW_INCOME = "22222222-2222-4222-8222-222222222222"
BUSINESS = "33333333-3333-4333-8333-333333333333"
TOO_OLD = "44444444-4444-4444-8444-444444444444"


def _query(node_name: str) -> str:
    nodes = json.loads(WORKFLOW.read_text())["nodes"]
    query = next(node["parameters"]["query"] for node in nodes if node["name"] == node_name)
    return re.sub(r"\$(\d)", r":p\1", query)


def _product(conn, name, *, min_income=None, employment=None, criteria=None, rate=None, active=True):
    return conn.run(
        """
        insert into loan_products (source_id, lender, product_name, source_url, interest_rate_min,
                                   min_monthly_income, min_credit_score, min_age, max_age, employment_types,
                                   qualitative_criteria, criteria_hash, is_active)
        values (1, 'Test Bank', :name, 'https://example.com', :rate, :min_income, 700, 21, 58,
                cast(:employment as text[]), :criteria, 'hash', :active)
        returning product_id
        """,
        name=name,
        rate=rate,
        min_income=min_income,
        employment=employment,
        criteria=criteria,
        active=active,
    )[0][0]


def _user(conn, batch_id, user_id, income, employment, age):
    conn.run(
        """
        insert into users (user_id, email, monthly_income, credit_score, employment_status, age, batch_id)
        values (cast(:user_id as uuid), 'x@example.com', :income, 750, :employment, :age, cast(:batch_id as uuid))
        """,
        user_id=user_id,
        income=income,
        employment=employment,
        age=age,
        batch_id=batch_id,
    )


@pytest.fixture
def batch(conn, batch_id):
    conn.run("update upload_batches set status = 'ingested' where batch_id = cast(:id as uuid)", id=batch_id)
    _user(conn, batch_id, SALARIED, 60000, "salaried", 30)
    _user(conn, batch_id, LOW_INCOME, 20000, "salaried", 30)
    _user(conn, batch_id, BUSINESS, 90000, "business", 40)
    _user(conn, batch_id, TOO_OLD, 90000, "salaried", 60)
    yield batch_id
    conn.run("truncate match_candidates, llm_eval_cache, loan_products cascade")


def _start(conn, batch_id):
    return conn.run(_query("Start matching"), p1=batch_id, p2="exec-1")[0][1]


def test_hard_filter_matches_numeric_rules_and_defers_qualitative_products(conn, batch):
    plain = _product(conn, "Plain", min_income=25000, employment="{salaried}", rate=10.0)
    _product(conn, "Needs review", min_income=25000, criteria="2 years of work experience")
    _product(conn, "Retired", min_income=25000, active=False)
    _product(conn, "Unmatchable")
    conn.run("update loan_products set min_credit_score = null where product_name = 'Unmatchable'")
    _start(conn, batch)

    funnel = conn.run(_query("SQL hard filter"), p1=batch)[0]

    assert funnel == [4, 2, 8, 3, 1, 2]
    assert conn.run("select user_id::text, product_id, stage from matches") == [[SALARIED, plain, "sql"]]
    deferred = conn.run("select user_id::text, class_key from match_candidates order by user_id")
    assert deferred == [[SALARIED, "salaried|inc50|cs750|age30"], [BUSINESS, "business|inc75|cs750|age40"]]


def test_missing_rate_scores_neutral_instead_of_zero(conn, batch):
    _product(conn, "No rate", employment="{salaried}")
    _start(conn, batch)
    conn.run(_query("SQL hard filter"), p1=batch)

    score = conn.run("select score from matches where user_id = cast(:id as uuid)", id=SALARIED)[0][0]

    assert float(score) == pytest.approx(0.5 * 0.5 + 0.25 * 0.5 + 0.25 * (60000 / 75000), abs=0.001)


def test_fan_out_applies_cached_verdicts_and_records_funnel(conn, batch):
    product = _product(conn, "Needs review", min_income=25000, criteria="2 years of work experience")
    conn.run(
        """
        insert into llm_eval_cache (product_id, product_version, class_key, verdict, reason, created_at)
        values (:id, 1, 'salaried|inc50|cs750|age30', 'likely', 'Experience unknown.', now() - interval '1 day')
        """,
        id=product,
    )
    started_at = _start(conn, batch)
    funnel = conn.run(_query("SQL hard filter"), p1=batch)[0]
    conn.run(
        """
        insert into llm_eval_cache (product_id, product_version, class_key, verdict, reason)
        values (:id, 1, 'business|inc75|cs750|age40', 'ineligible', 'Business owners are excluded.')
        """,
        id=product,
    )
    stats = dict(
        zip(
            ["users_in_batch", "products_active", "pairs_total", "pairs_after_sql", "sql_matches", "pairs_deferred"],
            funnel,
            strict=True,
        )
    )
    stats |= {"classes_to_judge": 2, "cache_hits": 1, "llm_calls": 1}

    conn.run(_query("Fan out + record funnel"), p1=batch, p2=started_at, p3=json.dumps(stats))

    matches = conn.run("select user_id::text, stage, verdict, reason from matches")
    assert matches == [[SALARIED, "cache", "likely", matches[0][3]]]
    assert matches[0][3].endswith("· Experience unknown.")
    assert conn.run("select count(*) from match_candidates") == [[0]]
    assert conn.run("select total_matches, llm_matches, cache_hits from match_runs") == [[1, 1, 1]]
    assert conn.run("select status from upload_batches") == [["matched"]]


def test_start_matching_refuses_a_batch_that_is_already_running(conn, batch):
    _start(conn, batch)

    assert conn.run(_query("Start matching"), p1=batch, p2="exec-2") == []
