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


def test_meta_exposes_fy_and_ruleset_version():
    resp = client.get("/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_fy"] == "2025-26"
    assert body["ruleset_version"]


def test_waterfall_happy_path():
    payload = {
        "ctc_breakup": {"basic": 600_000, "hra": 300_000, "special_allowance": 200_000, "bonus": 100_000},
        "regime": "new",
    }
    resp = client.post("/waterfall", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["steps"][0]["label"] == "CTC (Total Cost to Company)"
    assert body["in_hand_monthly"] == 94_000.0


def test_waterfall_missing_field_rejected():
    resp = client.post("/waterfall", json={"ctc_breakup": {"basic": 600_000}})
    assert resp.status_code == 422


def test_classify_happy_path():
    payload = {"ctc_breakup": {"basic": 600_000, "hra": 300_000, "special_allowance": 200_000, "bonus": 100_000}}
    resp = client.post("/classify", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    bucket_ids = {b["bucket"] for b in body["buckets"]}
    assert bucket_ids == {"fixed_compensation", "employer_contributions", "variable", "one_time"}


def test_quality_score_happy_path():
    payload = {
        "ctc_breakup": {"basic": 600_000, "hra": 300_000, "special_allowance": 200_000, "bonus": 100_000},
        "regime": "new",
    }
    resp = client.post("/quality-score", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["overall_score"] <= 100
    assert set(body["sub_scores"]) == {"fixed_ratio", "variable_dependence", "take_home_ratio", "benefits"}


def test_compare_offers_happy_path():
    payload = {
        "offer_a": {"label": "Offer A", "regime": "new",
                    "ctc_breakup": {"basic": 300_000, "hra": 150_000}},
        "offer_b": {"label": "Offer B", "regime": "new",
                    "ctc_breakup": {"basic": 900_000, "hra": 450_000}},
    }
    resp = client.post("/compare-offers", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["best_for_cashflow"] == "offer_b"


def test_compare_offers_rejects_incomplete_offer():
    payload = {
        "offer_a": {"label": "Offer A", "ctc_breakup": {"basic": 300_000}},
        "offer_b": {"label": "Offer B", "ctc_breakup": {"basic": 900_000, "hra": 450_000}},
    }
    resp = client.post("/compare-offers", json=payload)
    assert resp.status_code == 422


def test_breakdown_accepts_camelcase_team_schema_field_names():
    payload = {
        "ctcBreakup": {"basic": 600_000, "hra": 300_000, "specialAllowance": 200_000,
                       "variablePay": 100_000, "employerPF": 72_000},
        "regime": "new",
    }
    resp = client.post("/breakdown", json=payload)
    assert resp.status_code == 200
    assert resp.json()["breakdown"]["in_hand_annual"] == 1_128_000.0


def test_gratuity_epf_timeline_happy_path():
    resp = client.post("/gratuity-epf-timeline", json={"joiningDate": "2019-06-15", "asOfDate": "2024-06-15"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["gratuity"]["vested"] is True
    assert len(body["milestones"]) == 4


def test_gratuity_epf_timeline_rejects_bad_date():
    resp = client.post("/gratuity-epf-timeline", json={"joining_date": "not-a-date"})
    assert resp.status_code == 422


def test_sample_offers_are_each_valid_breakdown_input():
    resp = client.get("/sample-offers")
    assert resp.status_code == 200
    samples = resp.json()["samples"]
    assert len(samples) == 3
    for sample in samples:
        breakdown_resp = client.post("/breakdown", json={"ctc_breakup": sample["ctc_breakup"], "regime": "new"})
        assert breakdown_resp.status_code == 200, sample["id"]
