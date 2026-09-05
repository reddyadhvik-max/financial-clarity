import pytest

from app import rules


def test_get_rule_returns_versioned_record():
    rule = rules.get_rule("CAP_80C")
    assert rule["rule_id"] == "CAP_80C"
    assert rule["fy"] == "2025-26"
    assert rule["value"] == 150_000


def test_get_rule_unknown_id_raises():
    with pytest.raises(rules.RuleNotFoundError):
        rules.get_rule("NOT_A_REAL_RULE")


def test_get_rule_unknown_fy_raises():
    with pytest.raises(rules.RuleNotFoundError):
        rules.get_rule("CAP_80C", fy="1999-00")


def test_current_fy():
    assert rules.current_fy() == "2025-26"
