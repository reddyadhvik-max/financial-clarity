"""Layer 1 (spatial/tabular) extraction, using a synthetic table shaped
exactly like pdfplumber's `page.extract_tables()` output — a list of rows,
each a list of cell strings — so this is testable without a real PDF file.
"""
from parser.tabular import extract_from_tables


def test_extracts_from_annual_column():
    table = [
        ["Component", "Monthly (Rs.)", "Annual (Rs.)"],
        ["Basic Pay", "60,000", "7,20,000"],
        ["House Rent Allowance", "30,000", "3,60,000"],
        ["Employer PF", "7,200", "86,400"],
    ]
    results = extract_from_tables([table])

    assert results["basic_pay"]["value"] == 720000.0
    assert results["basic_pay"]["confidence_tier"] == "found"
    assert results["hra"]["value"] == 360000.0
    assert results["employer_pf"]["value"] == 86400.0


def test_falls_back_to_monthly_times_12_when_annual_column_missing():
    table = [
        ["Component", "Monthly"],
        ["Basic Pay", "50,000"],
    ]
    results = extract_from_tables([table])
    assert results["basic_pay"]["value"] == 600000.0
    assert "monthly*12" in results["basic_pay"]["evidence"]


def test_ignores_tables_with_no_recognizable_columns():
    table = [
        ["Document", "Required"],
        ["PAN Card", "Yes"],
    ]
    results = extract_from_tables([table])
    assert results == {}


def test_ignores_unrecognized_row_labels():
    table = [
        ["Component", "Annual"],
        ["Some Unrelated Line Item", "12,345"],
    ]
    results = extract_from_tables([table])
    assert results == {}


def test_later_table_overwrites_earlier_value_for_same_field():
    tables = [
        [["Component", "Annual"], ["Basic Pay", "1,00,000"]],
        [["Component", "Annual"], ["Basic Pay", "2,00,000"]],
    ]
    results = extract_from_tables(tables)
    assert results["basic_pay"]["value"] == 200000.0
