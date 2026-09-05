from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_parse_fields_valid():
    resp = client.post("/parse-fields", json={"fields": {"basic": 600_000, "hra": 300_000}})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_parse_fields_missing_returns_structured_error():
    resp = client.post("/parse-fields", json={"fields": {"basic": 600_000}})
    assert resp.status_code == 422
    assert resp.json() == {"valid": False, "missing_fields": ["hra"]}


def test_breakdown_happy_path():
    payload = {
        "ctc_breakup": {
            "basic": 600_000, "hra": 300_000, "special_allowance": 200_000, "bonus": 100_000,
        },
        "regime": "new",
    }
    resp = client.post("/breakdown", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["breakdown"]["in_hand_annual"] == 1_128_000.0
    assert "red_flags" in body


def test_breakdown_missing_field_rejected_before_calculation():
    payload = {"ctc_breakup": {"basic": 600_000}}
    resp = client.post("/breakdown", json=payload)
    assert resp.status_code == 422
    assert resp.json()["missing_fields"] == ["hra"]


def test_regime_comparison_happy_path():
    payload = {
        "gross_salary": 1_200_000,
        "deductions_claimed": {"80C": 150_000, "80D": 25_000},
        "basic": 600_000,
        "hra_received": 300_000,
        "rent_paid": 240_000,
        "is_metro": True,
    }
    resp = client.post("/regime-comparison", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["old_regime_tax"]["total_tax"] == 74_360.0
    assert body["new_regime_tax"]["total_tax"] == 0.0
    assert body["recommended"] == "new"


def test_regime_comparison_rent_without_basic_is_rejected():
    resp = client.post("/regime-comparison", json={"gross_salary": 1_200_000, "rent_paid": 240_000})
    assert resp.status_code == 422


def test_get_rule_found():
    resp = client.get("/rule/CAP_80C")
    assert resp.status_code == 200
    body = resp.json()
    assert body["value"] == 150_000
    assert body["fy"] == "2025-26"


def test_get_rule_not_found():
    resp = client.get("/rule/NOT_A_RULE")
    assert resp.status_code == 404


def test_completeness_scope():
    resp = client.get("/completeness-scope")
    assert resp.status_code == 200
    body = resp.json()
    assert "covered" in body and "not_covered" in body
    assert len(body["not_covered"]) > 0
