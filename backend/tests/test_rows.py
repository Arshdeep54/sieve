import pytest

from loan_engine.rows import RowError, missing_columns, parse_row

VALID = {
    "user_id": "b35de23e-755f-4c6a-81d8-f7dd99ce53ef",
    "name": "Dhruv Iyengar",
    "email": "Dhruv.Iyengar@Example.com",
    "monthly_income": "131000",
    "credit_score": "725",
    "employment_status": "Self-Employed",
    "age": "37",
}


def test_parses_and_normalises_a_valid_row():
    row = parse_row(VALID)
    assert row.email == "dhruv.iyengar@example.com"
    assert row.employment_status == "self_employed"
    assert (row.monthly_income, row.credit_score, row.age) == (131000, 725, 37)


def test_accepts_thousands_separators_and_header_whitespace():
    row = parse_row({f" {key.upper()} ": value for key, value in {**VALID, "monthly_income": "1,31,000"}.items()})
    assert row.monthly_income == 131000


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("user_id", "123", "user_id"),
        ("email", "no-at-sign", "email"),
        ("monthly_income", "", "monthly_income"),
        ("monthly_income", "-5", "monthly_income"),
        ("credit_score", "950", "credit_score"),
        ("employment_status", "Student", "employment_status"),
        ("age", "16", "age"),
    ],
)
def test_rejects_invalid_values_with_a_reason(field, value, message):
    with pytest.raises(RowError, match=message):
        parse_row({**VALID, field: value})


def test_reports_missing_required_columns():
    assert missing_columns(["user_id", "Email", "age"]) == ["monthly_income", "credit_score", "employment_status"]
