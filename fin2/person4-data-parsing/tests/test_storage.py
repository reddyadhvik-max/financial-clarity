"""Storage layer tests: save, fetch, and filter parsed offers against an
in-memory SQLite connection (never a file) — a fresh connection per test,
mirroring one upload session's lifetime.
"""
import sqlite3

import pytest

from parser.parser_engine import OfferLetterParser
from parser.storage import get_offer, init_schema, list_offers, save_offer

SAMPLE_TEXT = """
Company Name: Gamma Labs
Dear Kabir Singh,
We are thrilled to extend an offer of employment to you at Gamma Labs for the position of Backend Engineer.
Your Total Compensation (CTC) for the year will be Rs. 20,00,000.
Basic Pay: Rs. 10,00,000 per annum
Employer PF: Rs. 1,20,000 per annum
"""


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    init_schema(connection)
    yield connection
    connection.close()


def test_save_and_get_offer_roundtrip(conn):
    result = OfferLetterParser().parse_text(SAMPLE_TEXT)

    offer_id = save_offer(conn, result, source_filename="gamma_offer.txt")
    fetched = get_offer(conn, offer_id)

    assert fetched is not None
    assert fetched["offer_id"] == offer_id
    assert fetched["metadata"]["company_name"] == "Gamma Labs"
    assert fetched["fields"]["top_line"]["total_ctc"]["value"] == 2000000.0


def test_get_offer_returns_none_for_unknown_id(conn):
    save_offer(conn, OfferLetterParser().parse_text(SAMPLE_TEXT))
    assert get_offer(conn, "does-not-exist") is None


def test_list_offers_filters_by_company_name(conn):
    save_offer(conn, OfferLetterParser().parse_text(SAMPLE_TEXT))

    matches = list_offers(conn, company_name="gamma")
    assert len(matches) == 1
    assert matches[0]["company_name"] == "Gamma Labs"

    assert list_offers(conn, company_name="nonexistent") == []


def test_list_offers_filters_by_ctc_range(conn):
    save_offer(conn, OfferLetterParser().parse_text(SAMPLE_TEXT))

    assert len(list_offers(conn, min_ctc=1_900_000)) == 1
    assert len(list_offers(conn, min_ctc=3_000_000)) == 0


def test_list_offers_filters_by_missing_field(conn):
    save_offer(conn, OfferLetterParser().parse_text(SAMPLE_TEXT))

    # gratuity was never mentioned in SAMPLE_TEXT -> should show up as missing
    assert len(list_offers(conn, missing_field="gratuity", category="retirals")) == 1
    # basic_pay was found, not missing
    assert list_offers(conn, missing_field="basic_pay", category="fixed") == []


def test_two_connections_are_fully_isolated():
    """Each session's connection is its own in-memory database — nothing
    saved in one is visible from another, which is the whole point."""
    conn_a = sqlite3.connect(":memory:")
    conn_b = sqlite3.connect(":memory:")
    init_schema(conn_a)
    init_schema(conn_b)

    save_offer(conn_a, OfferLetterParser().parse_text(SAMPLE_TEXT))

    assert len(list_offers(conn_a)) == 1
    assert len(list_offers(conn_b)) == 0

    conn_a.close()
    conn_b.close()
