"""Validation and normalisation of a single users CSV row."""

import re
import uuid
from dataclasses import dataclass

REQUIRED_COLUMNS = ("user_id", "email", "monthly_income", "credit_score", "employment_status", "age")

EMPLOYMENT_ALIASES = {
    "salaried": "salaried",
    "self-employed": "self_employed",
    "self employed": "self_employed",
    "self_employed": "self_employed",
    "business": "business",
}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class UserRow:
    """A validated user, normalised for storage."""

    user_id: str
    name: str
    email: str
    monthly_income: int
    credit_score: int
    employment_status: str
    age: int


class RowError(ValueError):
    """The row is invalid; the message is written to the rejected-rows file."""

    pass


def missing_columns(header: list[str]) -> list[str]:
    """Return the required columns absent from the header, matched case-insensitively."""
    present = {column.strip().lower() for column in header}
    return [column for column in REQUIRED_COLUMNS if column not in present]


def parse_row(raw: dict[str, str]) -> UserRow:
    """Validate one CSV record and return it normalised, or raise RowError."""
    values = {key.strip().lower(): (value or "").strip() for key, value in raw.items() if key}
    return UserRow(
        user_id=_uuid(values["user_id"]),
        name=values.get("name", ""),
        email=_email(values["email"]),
        monthly_income=_int_in_range("monthly_income", values["monthly_income"], 1, 100_000_000),
        credit_score=_int_in_range("credit_score", values["credit_score"], 300, 900),
        employment_status=_employment(values["employment_status"]),
        age=_int_in_range("age", values["age"], 18, 100),
    )


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise RowError(f"user_id is not a valid UUID: {value!r}") from error


def _email(value: str) -> str:
    if not EMAIL_PATTERN.match(value):
        raise RowError(f"email is invalid: {value!r}")
    return value.lower()


def _int_in_range(field: str, value: str, low: int, high: int) -> int:
    try:
        number = int(float(value.replace(",", "")))
    except ValueError as error:
        raise RowError(f"{field} is not a number: {value!r}") from error
    if not low <= number <= high:
        raise RowError(f"{field} must be between {low} and {high}: {number}")
    return number


def _employment(value: str) -> str:
    normalised = EMPLOYMENT_ALIASES.get(value.lower())
    if normalised is None:
        raise RowError(f"employment_status is not one of Salaried, Self-Employed, Business: {value!r}")
    return normalised
