"""Local SQLite persistence: save, fetch, and filter parsed offers.
Uses a temp DB path per test (pytest's tmp_path) so tests never touch the
real data/offers.db used by the running API.
"""
from parser.parser_engine import OfferLetterParser
from parser.storage import get_offer, list_offers, save_offer

SAMPLE_TEXT = """
Company Name: Gamma Labs
Dear Kabir Singh,
We are thrilled to extend an offer of employment to you at Gamma Labs for the position of Backend Engineer.
Your Total Compensation (CTC) for the year will be Rs. 20,00,000.
Basic Pay: Rs. 10,00,000 per annum
Employer PF: Rs. 1,20,000 per annum
"""


def test_save_and_get_offer_roundtrip(tmp_path):
    db_path = tmp_path / "offers.db"
    result = OfferLetterParser().parse_text(SAMPLE_TEXT)

    offer_id = save_offer(result, source_filename="gamma_offer.txt", db_path=db_path)
    fetched = get_offer(offer_id, db_path=db_path)

    assert fetched is not None
    assert fetched["offer_id"] == offer_id
    assert fetched["metadata"]["company_name"] == "Gamma Labs"
    assert fetched["fields"]["top_line"]["total_ctc"]["value"] == 2000000.0


def test_get_offer_returns_none_for_unknown_id(tmp_path):
    db_path = tmp_path / "offers.db"
    save_offer(OfferLetterParser().parse_text(SAMPLE_TEXT), db_path=db_path)
    assert get_offer("does-not-exist", db_path=db_path) is None


def test_list_offers_filters_by_company_name(tmp_path):
    db_path = tmp_path / "offers.db"
    save_offer(OfferLetterParser().parse_text(SAMPLE_TEXT), db_path=db_path)

    matches = list_offers(db_path=db_path, company_name="gamma")
    assert len(matches) == 1
    assert matches[0]["company_name"] == "Gamma Labs"

    no_matches = list_offers(db_path=db_path, company_name="nonexistent")
    assert no_matches == []


def test_list_offers_filters_by_ctc_range(tmp_path):
    db_path = tmp_path / "offers.db"
    save_offer(OfferLetterParser().parse_text(SAMPLE_TEXT), db_path=db_path)

    assert len(list_offers(db_path=db_path, min_ctc=1_900_000)) == 1
    assert len(list_offers(db_path=db_path, min_ctc=3_000_000)) == 0


def test_list_offers_filters_by_missing_field(tmp_path):
    db_path = tmp_path / "offers.db"
    save_offer(OfferLetterParser().parse_text(SAMPLE_TEXT), db_path=db_path)

    # gratuity was never mentioned in SAMPLE_TEXT -> should show up as missing
    missing_gratuity = list_offers(db_path=db_path, missing_field="gratuity", category="retirals")
    assert len(missing_gratuity) == 1

    missing_basic = list_offers(db_path=db_path, missing_field="basic_pay", category="fixed")
    assert missing_basic == []  # basic_pay was found, not missing
