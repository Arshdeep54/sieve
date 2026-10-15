"""Runs workflow A's product validation code exactly as shipped, on extraction outputs that once went wrong."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / "n8n" / "workflows" / "A_loan_product_discovery.json"
HARNESS = """
const code = process.argv[1];
const products = JSON.parse(process.argv[2]);
const page = () => ({ item: { json: { source_id: 1, url: 'https://example.com', content_hash: 'h' } } });
const response = { choices: [{ message: { content: JSON.stringify({ products }) } }] };
console.log(JSON.stringify(new Function('$', '$json', 'require', code)(page, response, require).json.products));
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _validate(products):
    nodes = json.loads(WORKFLOW.read_text())["nodes"]
    code = next(node["parameters"]["jsCode"] for node in nodes if node["name"] == "Validate products")
    result = subprocess.run(
        ["node", "-e", HARNESS, code, json.dumps(products)], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _product(name, employment, lender="Kotak Mahindra Bank", **criteria):
    return {"lender": lender, "product_name": name, "employment_types": employment, "min_credit_score": 750, **criteria}


def test_drops_products_for_lender_staff_and_existing_customers():
    products = _validate(
        [
            _product("Kotak Personal Loan (Salaried)", ["salaried"]),
            _product("Kotak Personal Loan (Salaried, Kotak Salary Account Holder)", ["salaried"]),
            _product("Kotak Personal Loan (Salaried, Kotak Mahindra Bank Employee)", ["salaried"]),
        ]
    )

    assert [product["product_name"] for product in products] == ["Kotak Personal Loan (Salaried)"]


def test_unsplit_self_employed_covers_business_owners():
    products = _validate(
        [
            _product("Bajaj Personal Loan (Salaried)", ["salaried"], lender="Bajaj Finance"),
            _product("Bajaj Personal Loan (Self-employed)", ["self_employed"], lender="Bajaj Finance"),
        ]
    )

    assert products[1]["employment_types"] == ["self_employed", "business"]


def test_split_self_employed_segments_stay_split():
    products = _validate(
        [
            _product("Personal Loan (Professionals)", ["self_employed"]),
            _product("Personal Loan (Business owners)", ["business"]),
        ]
    )

    assert [product["employment_types"] for product in products] == [["self_employed"], ["business"]]


def test_aggregator_pages_supply_rates_only():
    products = _validate(
        [
            _product("SBI Personal Loan", [], lender="State Bank of India", interest_rate_min=10.0, min_age=21),
            _product("HDFC Personal Loan", ["salaried"], lender="HDFC Bank", interest_rate_min=9.99),
        ]
    )

    assert [(p["interest_rate_min"], p["min_credit_score"], p["min_age"], p["employment_types"]) for p in products] == [
        (10.0, None, None, None),
        (9.99, None, None, None),
    ]
