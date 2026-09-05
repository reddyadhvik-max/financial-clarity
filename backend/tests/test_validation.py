from app.validation import validate_ctc_breakup


def test_valid_breakup_passes():
    result = validate_ctc_breakup({"basic": 600_000, "hra": 300_000})
    assert result.valid
    assert result.missing_fields == []


def test_missing_hra_is_reported():
    result = validate_ctc_breakup({"basic": 600_000})
    assert not result.valid
    assert result.missing_fields == ["hra"]


def test_missing_both_required_fields():
    result = validate_ctc_breakup({})
    assert not result.valid
    assert set(result.missing_fields) == {"basic", "hra"}


def test_malformed_negative_field():
    result = validate_ctc_breakup({"basic": 600_000, "hra": -100})
    assert not result.valid
    assert "hra" in result.malformed_fields


def test_malformed_non_numeric_field():
    result = validate_ctc_breakup({"basic": "lots", "hra": 300_000})
    assert not result.valid
    assert "basic" in result.malformed_fields


def test_to_dict_shape_for_agent_clarification():
    result = validate_ctc_breakup({"basic": 600_000})
    d = result.to_dict()
    assert d == {"valid": False, "missing_fields": ["hra"]}
