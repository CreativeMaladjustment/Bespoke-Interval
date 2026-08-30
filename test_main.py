"""Tests mock the Supabase client — no live database, runs fully offline."""

import os
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("SESSION_SECRET", "test-secret")

import bcrypt
from starlette.testclient import TestClient

import main
from auth import sign_session

client = TestClient(main.app, follow_redirects=False)


def setup_function(_):
    client.cookies.clear()

TRIP_ID = "11111111-1111-1111-1111-111111111111"
DAY_ID = "22222222-2222-2222-2222-222222222222"
JD_ID = "33333333-3333-3333-3333-333333333333"
EMY_ID = "44444444-4444-4444-4444-444444444444"
BLOCK_ID = "55555555-5555-5555-5555-555555555555"

PIN_HASH = bcrypt.hashpw(b"4610", bcrypt.gensalt()).decode()


def _trip_row():
    return {
        "id": TRIP_ID,
        "slug": "thanksgiving-london-2026",
        "name": "Thanksgiving, London",
        "home_timezone": "America/Denver",
        "destination_timezone": "Europe/London",
        "pin_hash": PIN_HASH,
        "starts_at": "2026-11-22T09:15:00+00:00",
        "starts_terminal": "LHR T2",
        "ends_at": "2026-11-30T16:10:00+00:00",
        "ends_terminal": "LHR T5",
    }


def _travelers():
    return [
        {"id": JD_ID, "trip_id": TRIP_ID, "name": "jd", "initial": "j", "role": "Trip owner", "sort_order": 0},
        {"id": EMY_ID, "trip_id": TRIP_ID, "name": "emy", "initial": "e", "role": "Traveller", "sort_order": 1},
    ]


def _days():
    return [
        {
            "id": DAY_ID,
            "trip_id": TRIP_ID,
            "day_index": 2,
            "calendar_date": "2026-11-22",
            "reference_timezone": "Europe/London",
            "kicker": "Vacation clock starts 09:15",
            "tag": "Land LHR",
        }
    ]


def _blocks():
    return [
        {
            "id": BLOCK_ID,
            "trip_id": TRIP_ID,
            "trip_day_id": DAY_ID,
            "type": "walk",
            "title": "Walk: Bloomsbury squares",
            "subtitle": "Slow loop to shake off the flight",
            "starts_at": "2026-11-22T13:00:00+00:00",
            "ends_at": "2026-11-22T15:00:00+00:00",
            "who": "Both",
        }
    ]


def _tickets():
    return []


def _flights():
    return []


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def single(self):
        return self

    def insert(self, rows):
        return FakeExec(rows)

    def update(self, values):
        return self

    def delete(self):
        return self

    def execute(self):
        return FakeExec(self._data)


class FakeExec:
    def __init__(self, data):
        self.data = data


class FakeClient:
    TABLES = {
        "trips": lambda: _trip_row(),
        "travelers": lambda: _travelers(),
        "trip_days": lambda: _days(),
        "blocks": lambda: _blocks(),
        "tickets": lambda: _tickets(),
        "flights": lambda: _flights(),
    }

    def table(self, name):
        return FakeQuery(self.TABLES[name]())


@patch("main.get_supabase_client", return_value=FakeClient())
def test_root_redirects_to_login_when_signed_out(mock_client):
    resp = client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


@patch("main.get_supabase_client", return_value=FakeClient())
def test_login_page_renders_travelers(mock_client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "jd" in resp.text
    assert "emy" in resp.text


@patch("main.get_supabase_client", return_value=FakeClient())
def test_login_wrong_pin_rejected(mock_client):
    resp = client.post("/login", data={"traveler_id": JD_ID, "pin": "0000"})
    assert resp.status_code == 401
    assert "match" in resp.text


@patch("main.get_supabase_client", return_value=FakeClient())
def test_login_correct_pin_sets_cookie_and_redirects(mock_client):
    resp = client.post("/login", data={"traveler_id": JD_ID, "pin": "4610"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/day/2"
    assert "bespoke_session" in resp.cookies


@patch("main.get_supabase_client", return_value=FakeClient())
def test_day_view_requires_session(mock_client):
    resp = client.get("/day/2")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


@patch("main.get_supabase_client", return_value=FakeClient())
def test_day_view_renders_blocks_when_authenticated(mock_client):
    token = sign_session(TRIP_ID, JD_ID, "jd")
    client.cookies.set("bespoke_session", token)
    resp = client.get("/day/2")
    client.cookies.clear()
    assert resp.status_code == 200
    assert "Walk: Bloomsbury squares" in resp.text
    assert "Sun 22 Nov" in resp.text


@patch("main.get_supabase_client", return_value=FakeClient())
def test_stale_session_for_wrong_trip_is_rejected(mock_client):
    # A cookie signed for a trip/traveler that no longer matches the
    # currently configured trip (e.g. TRIP_SLUG was repointed) must not
    # grant access, and the stale cookie should be cleared.
    token = sign_session("00000000-0000-0000-0000-000000000000", JD_ID, "jd")
    client.cookies.set("bespoke_session", token)
    resp = client.get("/day/2")
    client.cookies.clear()
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert resp.cookies.get("bespoke_session") in (None, '""')


@patch("main.get_supabase_client", return_value=FakeClient())
def test_stale_session_for_unknown_traveler_is_rejected(mock_client):
    token = sign_session(TRIP_ID, "00000000-0000-0000-0000-000000000000", "Ghost")
    client.cookies.set("bespoke_session", token)
    resp = client.get("/day/2")
    client.cookies.clear()
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


@patch("main.get_supabase_client", return_value=FakeClient())
def test_add_form_survives_bad_query_params(mock_client):
    token = sign_session(TRIP_ID, JD_ID, "jd")
    client.cookies.set("bespoke_session", token)
    resp = client.get("/add?day=not-a-number&type=nonsense-type&start=also-not-a-number")
    client.cookies.clear()
    assert resp.status_code == 200


def test_week_indices_cap_at_trip_bounds():
    assert main._week_indices(1, 10) == [2, 3, 4, 5, 6]
    assert main._week_indices(10, 10) == [6, 7, 8, 9, 10]
    assert main._week_indices(4, 10) == [3, 4, 5, 6, 7]


def test_logic_fmt_and_dur():
    from logic import dur, fmt

    assert fmt(19.5) == "19:30"
    assert dur(1.25) == "1h 15m"
    assert dur(0.25) == "15m"
