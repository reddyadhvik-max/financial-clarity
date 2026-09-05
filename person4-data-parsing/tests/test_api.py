"""API-level session behavior: a session id is issued on first contact,
reused on request, isolates offers between sessions, and DELETE /session
makes stored offers genuinely unreachable afterward.
"""
from fastapi.testclient import TestClient

from parser.api import app

SAMPLE_TEXT = "Your Total Compensation (CTC) for the year will be Rs. 10,00,000."


def _client():
    return TestClient(app)


def test_first_request_without_session_header_gets_one_issued():
    client = _client()
    response = client.post("/parse/text", json={"text": SAMPLE_TEXT})
    assert response.status_code == 200
    assert "X-Session-Id" in response.headers
    assert response.json()["session_id"] == response.headers["X-Session-Id"]


def test_reusing_session_header_sees_previously_parsed_offers():
    client = _client()
    first = client.post("/parse/text", json={"text": SAMPLE_TEXT})
    session_id = first.headers["X-Session-Id"]

    listing = client.get("/offers", headers={"X-Session-Id": session_id})
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_different_sessions_cannot_see_each_others_offers():
    client = _client()
    first = client.post("/parse/text", json={"text": SAMPLE_TEXT})
    session_a = first.headers["X-Session-Id"]

    second_session_start = client.post("/session")
    session_b = second_session_start.json()["session_id"]

    listing_b = client.get("/offers", headers={"X-Session-Id": session_b})
    assert listing_b.status_code == 200
    assert listing_b.json() == []  # session B never parsed anything, and can't see session A's offer

    listing_a = client.get("/offers", headers={"X-Session-Id": session_a})
    assert len(listing_a.json()) == 1


def test_delete_session_makes_its_offers_unreachable():
    client = _client()
    parsed = client.post("/parse/text", json={"text": SAMPLE_TEXT})
    session_id = parsed.headers["X-Session-Id"]
    offer_id = parsed.json()["offer_id"]

    close_response = client.delete("/session", headers={"X-Session-Id": session_id})
    assert close_response.status_code == 200
    assert close_response.json()["closed"] is True

    # Same session id, but it's gone now -> the API transparently starts a
    # NEW session rather than erroring, and that new session has never
    # heard of the old offer_id.
    after_close = client.get(f"/offers/{offer_id}", headers={"X-Session-Id": session_id})
    assert after_close.status_code == 404


def test_deleting_an_unknown_session_returns_404():
    client = _client()
    response = client.delete("/session", headers={"X-Session-Id": "never-existed"})
    assert response.status_code == 404
