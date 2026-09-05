"""SessionStore: creation, isolation, explicit close, and idle eviction.
Proves data really is gone once a session ends, not just unreachable via
the normal API surface.
"""
from parser.sessions import SessionStore
from parser.storage import save_offer, list_offers
from parser.parser_engine import OfferLetterParser

SAMPLE_TEXT = "Your Total Compensation (CTC) for the year will be Rs. 10,00,000."


def test_create_returns_a_usable_connection():
    store = SessionStore()
    session_id = store.create()
    conn = store.get_conn(session_id)
    assert conn is not None
    assert list_offers(conn) == []


def test_unknown_session_id_returns_none():
    store = SessionStore()
    assert store.get_conn("never-created") is None


def test_sessions_are_isolated_from_each_other():
    store = SessionStore()
    session_a = store.create()
    session_b = store.create()

    save_offer(store.get_conn(session_a), OfferLetterParser().parse_text(SAMPLE_TEXT))

    assert len(list_offers(store.get_conn(session_a))) == 1
    assert len(list_offers(store.get_conn(session_b))) == 0


def test_close_destroys_the_session_and_its_data():
    store = SessionStore()
    session_id = store.create()
    save_offer(store.get_conn(session_id), OfferLetterParser().parse_text(SAMPLE_TEXT))

    closed = store.close(session_id)
    assert closed is True
    assert store.get_conn(session_id) is None  # session, and everything in it, is gone


def test_closing_an_unknown_session_returns_false():
    store = SessionStore()
    assert store.close("never-created") is False


def test_idle_eviction_drops_sessions_past_the_timeout(monkeypatch):
    store = SessionStore()
    session_id = store.create()
    assert store.get_conn(session_id) is not None

    # simulate 30+ minutes of inactivity without actually sleeping in the test
    import parser.sessions as sessions_module
    monkeypatch.setattr(sessions_module, "SESSION_IDLE_TIMEOUT_SECONDS", -1)

    assert store.get_conn(session_id) is None
    assert store.active_session_count() == 0
