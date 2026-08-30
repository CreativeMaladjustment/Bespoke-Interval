"""Bespoke Interval — FastAPI app.

All route and business logic lives here (see the repo's Python +
Supabase + Vercel skill for why `api/index.py` is kept to a one-line
re-export). Every page read goes through the Supabase service-role key —
there is no client-side Supabase usage and no separate API layer, since the
whole app is server-rendered HTML.
"""

import os
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import logic
import templates
from auth import COOKIE_NAME, Session, read_session, sign_session, verify_password
from db import get_supabase_client, get_trip_slug

app = FastAPI()

COOKIE_KWARGS = dict(httponly=True, samesite="lax", secure=os.getenv("VERCEL_ENV") is not None, max_age=60 * 60 * 24 * 30)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "bespoke-interval"}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _date_label(d: date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


class Bundle:
    """Everything the app needs about the (single) trip, fetched fresh per request."""

    def __init__(self, client, slug: str):
        trip_row = client.table("trips").select("*").eq("slug", slug).single().execute().data
        if not trip_row:
            raise RuntimeError(f"No trip found for slug={slug!r}. Did you run the seed migration?")
        self.trip = {
            **trip_row,
            "starts_at": _parse_dt(trip_row["starts_at"]),
            "ends_at": _parse_dt(trip_row["ends_at"]),
        }

        self.travelers = (
            client.table("travelers").select("*").eq("trip_id", self.trip["id"]).order("sort_order").execute().data
        )

        day_rows = (
            client.table("trip_days").select("*").eq("trip_id", self.trip["id"]).order("day_index").execute().data
        )
        self.days = [
            {
                **d,
                "calendar_date": date.fromisoformat(d["calendar_date"]),
                "dow": date.fromisoformat(d["calendar_date"]).strftime("%a"),
                "dom": str(date.fromisoformat(d["calendar_date"]).day),
                "date_label": _date_label(date.fromisoformat(d["calendar_date"])),
            }
            for d in day_rows
        ]
        self.days_by_index = {d["day_index"]: d for d in self.days}
        self.days_by_id = {d["id"]: d for d in self.days}
        self.days_by_date = {d["calendar_date"]: d for d in self.days}

        block_rows = client.table("blocks").select("*").eq("trip_id", self.trip["id"]).order("starts_at").execute().data
        self.blocks_by_day: dict[int, list[dict]] = {d["day_index"]: [] for d in self.days}
        self.block_by_id: dict[str, dict] = {}
        self.block_by_ticket_id: dict[str, dict] = {}
        self.block_by_flight_id: dict[str, dict] = {}
        for b in block_rows:
            b = {**b, "starts_at": _parse_dt(b["starts_at"]), "ends_at": _parse_dt(b["ends_at"])}
            day = self.days_by_id.get(b["trip_day_id"])
            if day:
                self.blocks_by_day[day["day_index"]].append(b)
            self.block_by_id[b["id"]] = b
            if b.get("ticket_id"):
                self.block_by_ticket_id[b["ticket_id"]] = b
            if b.get("flight_id"):
                self.block_by_flight_id[b["flight_id"]] = b

        ticket_rows = (
            client.table("tickets").select("*").eq("trip_id", self.trip["id"]).order("sort_order").execute().data
        )
        self.tickets = []
        for t in ticket_rows:
            when = t["occurs_at"]
            when_label = _date_label(_parse_dt(when).astimezone(_zone(self.trip["destination_timezone"])).date()) if when else ""
            occurs = _parse_dt(when).astimezone(_zone(self.trip["destination_timezone"])) if when else None
            time_label = occurs.strftime("%H:%M") if occurs else ""
            self.tickets.append(
                {
                    **t,
                    "ink": logic.INK[t["category"]]["ink"],
                    "when": f"{when_label} · {time_label}" if when else "",
                }
            )
        self.ticket_by_id = {t["id"]: t for t in self.tickets}

        flight_rows = (
            client.table("flights").select("*").eq("trip_id", self.trip["id"]).order("sort_order").execute().data
        )
        self.flights = [
            {
                **f,
                "departs_at": _parse_dt(f["departs_at"]) if f.get("departs_at") else None,
                "arrives_at": _parse_dt(f["arrives_at"]) if f.get("arrives_at") else None,
            }
            for f in flight_rows
        ]
        self.flight_by_id = {f["id"]: f for f in self.flights}


def _zone(name: str):
    from zoneinfo import ZoneInfo

    return ZoneInfo(name)


def _get_bundle() -> Bundle:
    client = get_supabase_client()
    return Bundle(client, get_trip_slug())


def _authenticate(request: Request) -> tuple[Session, Bundle] | None:
    """Reads the session cookie and validates it against the *current* trip.

    A signed cookie only proves it was issued by this app at some point — it
    doesn't prove the trip/traveler it names still exist or still match
    (e.g. TRIP_SLUG was repointed at a different trip, or the traveler list
    changed). Treat a mismatch the same as no session at all.
    """
    session = read_session(request)
    if not session:
        return None
    bundle = _get_bundle()
    if session.trip_id != bundle.trip["id"]:
        return None
    if not any(t["id"] == session.traveler_id for t in bundle.travelers):
        return None
    return session, bundle


def _login_redirect() -> RedirectResponse:
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


def _block_sheet(b: dict, day_label: str) -> str:
    from zoneinfo import ZoneInfo

    london = ZoneInfo("Europe/London")
    denver = ZoneInfo("America/Denver")
    start_l, end_l = b["starts_at"].astimezone(london), b["ends_at"].astimezone(london)
    start_d, end_d = b["starts_at"].astimezone(denver), b["ends_at"].astimezone(denver)
    facts = [
        {"k": "London time", "v": f"{start_l.strftime('%H:%M')} – {end_l.strftime('%H:%M')}"},
        {"k": "Denver time", "v": f"{start_d.strftime('%H:%M')} – {end_d.strftime('%H:%M')}"},
        {"k": "Length", "v": logic.dur((b["ends_at"] - b["starts_at"]).total_seconds() / 3600)},
        {"k": "Day", "v": day_label},
    ]
    if b.get("ticket_id"):
        edit_href, edit_label = f"/tickets/{b['ticket_id']}/edit", "Edit ticket"
    elif b.get("flight_id"):
        edit_href, edit_label = f"/flights/{b['flight_id']}/edit", "Edit leg"
    else:
        edit_href, edit_label = f"/blocks/{b['id']}/edit", "Edit block"
    return templates._sheet(
        f"sheet-{b['id']}",
        logic.INK[b["type"]]["ink"],
        logic.INK[b["type"]]["label"],
        b["title"],
        b.get("subtitle") or "No notes yet.",
        b["who"],
        facts,
        edit_href=edit_href,
        edit_label=edit_label,
    )


def _week_indices(day_index: int, total: int) -> list[int]:
    idx0 = day_index - 1
    if idx0 <= 2:
        start0 = 1 if total > 5 else 0
    else:
        start0 = min(idx0 - 1, max(total - 5, 0))
    return [i + 1 for i in range(start0, min(start0 + 5, total))]


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not _authenticate(request):
        return _login_redirect()
    return RedirectResponse("/day/2", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if _authenticate(request):
        return RedirectResponse("/day/2", status_code=303)
    bundle = _get_bundle()
    return HTMLResponse(templates.login_page(bundle.travelers, bundle.trip["name"]))


@app.post("/login", response_class=HTMLResponse)
def login_submit(traveler_id: str = Form(...), password: str = Form(...)):
    bundle = _get_bundle()
    traveler = next((t for t in bundle.travelers if t["id"] == traveler_id), None)
    if not traveler or not verify_password(password):
        return HTMLResponse(
            templates.login_page(bundle.travelers, bundle.trip["name"], error="That password didn't match. Try again."),
            status_code=401,
        )
    token = sign_session(bundle.trip["id"], traveler["id"], traveler["name"])
    resp = RedirectResponse("/day/2", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, **COOKIE_KWARGS)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


def _tz_from_request(request: Request) -> str:
    tz = request.query_params.get("tz", "london")
    return tz if tz in logic.TIMEZONES else "london"


@app.get("/day/{day_index}", response_class=HTMLResponse)
def day_view(request: Request, day_index: int):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    day = bundle.days_by_index.get(day_index)
    if not day:
        return RedirectResponse("/day/2", status_code=303)

    tz_key = _tz_from_request(request)
    tz = logic.TIMEZONES[tz_key]["zone"]
    toggle_tz = "denver" if tz_key == "london" else "london"

    day_blocks = bundle.blocks_by_day[day_index]
    mobile_blocks = logic.layout_blocks(day_blocks, day["calendar_date"], tz, logic.PX_MOBILE)
    gaps = logic.compute_gaps(day_blocks, day["calendar_date"], tz)

    week_day_indices = _week_indices(day_index, len(bundle.days))
    week_days = []
    for wi in week_day_indices:
        wd = bundle.days_by_index.get(wi)
        if not wd:
            continue
        blocks = logic.layout_blocks(bundle.blocks_by_day[wi], wd["calendar_date"], tz, logic.PX_DESKTOP)
        week_days.append({**wd, "blocks": blocks, "tag": wd["tag"] or ""})

    planned_hours = sum((b["ends_at"] - b["starts_at"]).total_seconds() / 3600 for b in day_blocks)
    walk_hours = sum(
        (b["ends_at"] - b["starts_at"]).total_seconds() / 3600 for b in day_blocks if b["type"] == "walk"
    )
    free_total = sum(g["hours"] for g in gaps)
    stats = [
        {"label": "Planned", "value": logic.dur(planned_hours), "ink": "var(--ink)"},
        {
            "label": "Free windows",
            "value": f"{len(gaps)} · {logic.dur(free_total)}" if gaps else "none",
            "ink": "var(--gold)",
        },
        {"label": "On foot", "value": logic.dur(walk_hours) if walk_hours else "—", "ink": "#7f9c6e"},
    ]

    tickets_sidebar = [t for t in bundle.tickets][:4]

    first_date, last_date = bundle.days[0]["calendar_date"], bundle.days[-1]["calendar_date"]
    week_title = f"{first_date.day} – {last_date.day} {last_date.strftime('%B %Y')}"

    sheets = "".join(_block_sheet(b, day["date_label"]) for b in day_blocks)
    for wd in week_days:
        for b in bundle.blocks_by_day[wd["day_index"]]:
            if wd["day_index"] != day_index:
                sheets += _block_sheet(b, wd["date_label"])
    sheets += "".join(templates.sheet_for_ticket(t) for t in tickets_sidebar)

    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "day": day,
        "days": bundle.days,
        "mobile_blocks": mobile_blocks,
        "px_mobile": logic.PX_MOBILE,
        "px_desktop": logic.PX_DESKTOP,
        "gaps": gaps,
        "stats": stats,
        "tz_chip": logic.TIMEZONES[tz_key]["chip"],
        "toggle_href": f"/day/{day_index}?tz={toggle_tz}",
        "week_days": week_days,
        "week_title": week_title,
        "tickets": tickets_sidebar,
        "sheets": sheets,
    }
    return HTMLResponse(templates.day_page(ctx))


@app.get("/tickets", response_class=HTMLResponse)
def tickets_view(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    sheets = "".join(templates.sheet_for_ticket(t) for t in bundle.tickets)
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "tickets": bundle.tickets,
        "sheets": sheets,
    }
    return HTMLResponse(templates.tickets_page(ctx))


def _parse_facts(text: str) -> list[dict]:
    facts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        facts.append({"k": k.strip(), "v": v.strip()})
    return facts


def _facts_to_text(facts: list[dict]) -> str:
    return "\n".join(f"{f['k']}: {f['v']}" for f in facts)


def _empty_ticket_form() -> dict:
    return {
        "category": "theatre",
        "kind": "",
        "title": "",
        "venue": "",
        "occurs_at": "",
        "who": "Both",
        "facts_text": "",
        "sort_order": 0,
        "duration_minutes": 90,
    }


def _sync_ticket_block(
    client,
    bundle: "Bundle",
    ticket_id: str,
    *,
    occurs_at: datetime | None,
    category: str,
    title: str,
    venue: str,
    who: str,
    duration_minutes: int,
) -> None:
    """Keep the calendar block generated from a ticket in sync with it.

    A ticket only appears on the Week/Day calendar through this linked
    block, since that view renders exclusively from `blocks`."""
    existing = bundle.block_by_ticket_id.get(ticket_id)

    if not occurs_at:
        if existing:
            client.table("blocks").delete().eq("id", existing["id"]).execute()
        return

    dest_tz = _zone(bundle.trip["destination_timezone"])
    day = bundle.days_by_date.get(occurs_at.astimezone(dest_tz).date())
    if not day:
        if existing:
            client.table("blocks").delete().eq("id", existing["id"]).execute()
        return

    payload = {
        "trip_id": bundle.trip["id"],
        "trip_day_id": day["id"],
        "type": category,
        "title": title,
        "subtitle": venue or None,
        "starts_at": occurs_at.isoformat(),
        "ends_at": (occurs_at + timedelta(minutes=duration_minutes)).isoformat(),
        "who": who,
        "ticket_id": ticket_id,
    }
    if existing:
        client.table("blocks").update(payload).eq("id", existing["id"]).execute()
    else:
        client.table("blocks").insert(payload).execute()


FLIGHT_BLOCK_DEFAULT_MINUTES = 90


def _sync_flight_block(
    client,
    bundle: "Bundle",
    flight_id: str,
    *,
    departs_at: datetime | None,
    arrives_at: datetime | None,
    leg: str,
    code: str,
    note: str,
) -> None:
    """Keep the calendar block generated from a flight leg in sync with it.

    Mirrors _sync_ticket_block: a flight leg only appears on the Week/Day
    calendar through this linked block. When both departs_at and arrives_at
    are set the block spans exactly that; with only one set (e.g. a
    wheels-down/wheels-up leg that only marks a single instant) it falls
    back to a default duration, same idea as a ticket's duration_minutes."""
    existing = bundle.block_by_flight_id.get(flight_id)

    if not departs_at and not arrives_at:
        if existing:
            client.table("blocks").delete().eq("id", existing["id"]).execute()
        return

    if departs_at and arrives_at:
        starts_at, ends_at = departs_at, arrives_at
    elif departs_at:
        starts_at, ends_at = departs_at, departs_at + timedelta(minutes=FLIGHT_BLOCK_DEFAULT_MINUTES)
    else:
        starts_at, ends_at = arrives_at, arrives_at + timedelta(minutes=FLIGHT_BLOCK_DEFAULT_MINUTES)

    dest_tz = _zone(bundle.trip["destination_timezone"])
    day = bundle.days_by_date.get(starts_at.astimezone(dest_tz).date())
    if not day:
        if existing:
            client.table("blocks").delete().eq("id", existing["id"]).execute()
        return

    payload = {
        "trip_id": bundle.trip["id"],
        "trip_day_id": day["id"],
        "type": "travel",
        "title": leg,
        "subtitle": " · ".join(s for s in (code, note) if s) or None,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "who": "Both",
        "flight_id": flight_id,
    }
    if existing:
        client.table("blocks").update(payload).eq("id", existing["id"]).execute()
    else:
        client.table("blocks").insert(payload).execute()


@app.get("/tickets/add", response_class=HTMLResponse)
def ticket_add_form(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "ticket_id": None,
        "form": _empty_ticket_form(),
        "form_action": "/tickets/add",
    }
    return HTMLResponse(templates.ticket_form_page(ctx))


@app.post("/tickets/add", response_class=HTMLResponse)
def ticket_add_submit(
    request: Request,
    category: str = Form(...),
    kind: str = Form(...),
    title: str = Form(...),
    venue: str = Form(""),
    occurs_at: str = Form(""),
    who: str = Form("Both"),
    facts_text: str = Form(""),
    sort_order: int = Form(0),
    duration_minutes: int = Form(90),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    if category not in logic.INK:
        return RedirectResponse("/tickets/add", status_code=303)
    client = get_supabase_client()
    title = title.strip()
    venue = venue.strip()
    occurs_dt = _dest_local_dt(bundle.trip, occurs_at)
    result = client.table("tickets").insert(
        {
            "trip_id": bundle.trip["id"],
            "category": category,
            "kind": kind.strip(),
            "title": title,
            "venue": venue or None,
            "occurs_at": _iso(occurs_dt),
            "who": who,
            "facts": _parse_facts(facts_text),
            "sort_order": sort_order,
        }
    ).execute()
    ticket_id = result.data[0]["id"]
    _sync_ticket_block(
        client, bundle, ticket_id,
        occurs_at=occurs_dt, category=category, title=title, venue=venue, who=who,
        duration_minutes=duration_minutes,
    )
    return RedirectResponse("/tickets", status_code=303)


@app.get("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def ticket_edit_form(request: Request, ticket_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    ticket = bundle.ticket_by_id.get(ticket_id)
    if not ticket:
        return RedirectResponse("/tickets", status_code=303)
    occurs_at = _parse_dt(ticket["occurs_at"]) if ticket.get("occurs_at") else None
    linked_block = bundle.block_by_ticket_id.get(ticket_id)
    duration_minutes = (
        round((linked_block["ends_at"] - linked_block["starts_at"]).total_seconds() / 60) if linked_block else 90
    )
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "ticket_id": ticket_id,
        "form": {
            "category": ticket["category"],
            "kind": ticket["kind"],
            "title": ticket["title"],
            "venue": ticket.get("venue") or "",
            "occurs_at": _dest_local_str(bundle.trip, occurs_at),
            "who": ticket["who"],
            "facts_text": _facts_to_text(ticket["facts"]),
            "sort_order": ticket.get("sort_order") or 0,
            "duration_minutes": duration_minutes,
        },
        "form_action": f"/tickets/{ticket_id}/edit",
    }
    return HTMLResponse(templates.ticket_form_page(ctx))


@app.post("/tickets/{ticket_id}/edit", response_class=HTMLResponse)
def ticket_edit_submit(
    request: Request,
    ticket_id: str,
    category: str = Form(...),
    kind: str = Form(...),
    title: str = Form(...),
    venue: str = Form(""),
    occurs_at: str = Form(""),
    who: str = Form("Both"),
    facts_text: str = Form(""),
    sort_order: int = Form(0),
    duration_minutes: int = Form(90),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    if category not in logic.INK:
        return RedirectResponse(f"/tickets/{ticket_id}/edit", status_code=303)
    client = get_supabase_client()
    title = title.strip()
    venue = venue.strip()
    occurs_dt = _dest_local_dt(bundle.trip, occurs_at)
    client.table("tickets").update(
        {
            "category": category,
            "kind": kind.strip(),
            "title": title,
            "venue": venue or None,
            "occurs_at": _iso(occurs_dt),
            "who": who,
            "facts": _parse_facts(facts_text),
            "sort_order": sort_order,
        }
    ).eq("id", ticket_id).execute()
    _sync_ticket_block(
        client, bundle, ticket_id,
        occurs_at=occurs_dt, category=category, title=title, venue=venue, who=who,
        duration_minutes=duration_minutes,
    )
    return RedirectResponse("/tickets", status_code=303)


@app.post("/tickets/{ticket_id}/delete")
def ticket_delete(request: Request, ticket_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    client = get_supabase_client()
    client.table("tickets").delete().eq("id", ticket_id).execute()
    return RedirectResponse("/tickets", status_code=303)


def _clock_bounds(bundle: "Bundle") -> tuple[datetime, datetime]:
    """The vacation clock's start/end instants: the flagged flight legs'
    arrival/departure when set, falling back to the trip's own boundary
    columns for trips that haven't flagged a leg yet."""
    start_leg = next((f for f in bundle.flights if f.get("is_trip_start") and f.get("arrives_at")), None)
    end_leg = next((f for f in bundle.flights if f.get("is_trip_end") and f.get("departs_at")), None)
    starts_at = start_leg["arrives_at"] if start_leg else bundle.trip["starts_at"]
    ends_at = end_leg["departs_at"] if end_leg else bundle.trip["ends_at"]
    return starts_at, ends_at


@app.get("/flights", response_class=HTMLResponse)
def flights_view(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    dest_tz = _zone(bundle.trip["destination_timezone"])
    starts_at, ends_at = _clock_bounds(bundle)
    starts_local = starts_at.astimezone(dest_tz)
    ends_local = ends_at.astimezone(dest_tz)
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(starts_at, ends_at),
        "flights": bundle.flights,
        "starts_label": f"{_date_label(starts_local.date())} · {starts_local.strftime('%H:%M')} · {bundle.trip.get('starts_terminal') or ''}".strip(" ·"),
        "ends_label": f"{_date_label(ends_local.date())} · {ends_local.strftime('%H:%M')} · {bundle.trip.get('ends_terminal') or ''}".strip(" ·"),
    }
    return HTMLResponse(templates.flights_page(ctx))


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dest_local_dt(trip: dict, value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=_zone(trip["destination_timezone"]))


def _dest_local_str(trip: dict, dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone(_zone(trip["destination_timezone"])).strftime("%Y-%m-%dT%H:%M")


def _empty_flight_form() -> dict:
    return {
        "leg": "",
        "code": "",
        "endpoint_from": "",
        "endpoint_from_sub": "",
        "endpoint_to": "",
        "endpoint_to_sub": "",
        "note": "",
        "sort_order": 0,
        "arrives_at": "",
        "departs_at": "",
        "is_trip_start": False,
        "is_trip_end": False,
    }


@app.get("/flights/add", response_class=HTMLResponse)
def flight_add_form(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "flight_id": None,
        "form": _empty_flight_form(),
        "form_action": "/flights/add",
    }
    return HTMLResponse(templates.flight_form_page(ctx))


@app.post("/flights/add", response_class=HTMLResponse)
def flight_add_submit(
    request: Request,
    leg: str = Form(...),
    code: str = Form(""),
    endpoint_from: str = Form(""),
    endpoint_from_sub: str = Form(""),
    endpoint_to: str = Form(""),
    endpoint_to_sub: str = Form(""),
    note: str = Form(""),
    sort_order: int = Form(0),
    arrives_at: str = Form(""),
    departs_at: str = Form(""),
    is_trip_start: str | None = Form(None),
    is_trip_end: str | None = Form(None),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    client = get_supabase_client()
    if is_trip_start:
        client.table("flights").update({"is_trip_start": False}).eq("trip_id", bundle.trip["id"]).eq("is_trip_start", True).execute()
    if is_trip_end:
        client.table("flights").update({"is_trip_end": False}).eq("trip_id", bundle.trip["id"]).eq("is_trip_end", True).execute()
    leg = leg.strip()
    code = code.strip()
    note = note.strip()
    departs_dt = _dest_local_dt(bundle.trip, departs_at)
    arrives_dt = _dest_local_dt(bundle.trip, arrives_at)
    result = client.table("flights").insert(
        {
            "trip_id": bundle.trip["id"],
            "leg": leg,
            "code": code or None,
            "endpoint_from": endpoint_from.strip() or None,
            "endpoint_from_sub": endpoint_from_sub.strip() or None,
            "endpoint_to": endpoint_to.strip() or None,
            "endpoint_to_sub": endpoint_to_sub.strip() or None,
            "note": note or None,
            "sort_order": sort_order,
            "arrives_at": _iso(arrives_dt),
            "departs_at": _iso(departs_dt),
            "is_trip_start": bool(is_trip_start),
            "is_trip_end": bool(is_trip_end),
        }
    ).execute()
    flight_id = result.data[0]["id"]
    _sync_flight_block(client, bundle, flight_id, departs_at=departs_dt, arrives_at=arrives_dt, leg=leg, code=code, note=note)
    return RedirectResponse("/flights", status_code=303)


@app.get("/flights/{flight_id}/edit", response_class=HTMLResponse)
def flight_edit_form(request: Request, flight_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    flight = bundle.flight_by_id.get(flight_id)
    if not flight:
        return RedirectResponse("/flights", status_code=303)
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "flight_id": flight_id,
        "form": {
            "leg": flight["leg"],
            "code": flight.get("code") or "",
            "endpoint_from": flight.get("endpoint_from") or "",
            "endpoint_from_sub": flight.get("endpoint_from_sub") or "",
            "endpoint_to": flight.get("endpoint_to") or "",
            "endpoint_to_sub": flight.get("endpoint_to_sub") or "",
            "note": flight.get("note") or "",
            "sort_order": flight.get("sort_order") or 0,
            "arrives_at": _dest_local_str(bundle.trip, flight.get("arrives_at")),
            "departs_at": _dest_local_str(bundle.trip, flight.get("departs_at")),
            "is_trip_start": bool(flight.get("is_trip_start")),
            "is_trip_end": bool(flight.get("is_trip_end")),
        },
        "form_action": f"/flights/{flight_id}/edit",
    }
    return HTMLResponse(templates.flight_form_page(ctx))


@app.post("/flights/{flight_id}/edit", response_class=HTMLResponse)
def flight_edit_submit(
    request: Request,
    flight_id: str,
    leg: str = Form(...),
    code: str = Form(""),
    endpoint_from: str = Form(""),
    endpoint_from_sub: str = Form(""),
    endpoint_to: str = Form(""),
    endpoint_to_sub: str = Form(""),
    note: str = Form(""),
    sort_order: int = Form(0),
    arrives_at: str = Form(""),
    departs_at: str = Form(""),
    is_trip_start: str | None = Form(None),
    is_trip_end: str | None = Form(None),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    client = get_supabase_client()
    if is_trip_start:
        client.table("flights").update({"is_trip_start": False}).eq("trip_id", bundle.trip["id"]).eq("is_trip_start", True).execute()
    if is_trip_end:
        client.table("flights").update({"is_trip_end": False}).eq("trip_id", bundle.trip["id"]).eq("is_trip_end", True).execute()
    leg = leg.strip()
    code = code.strip()
    note = note.strip()
    departs_dt = _dest_local_dt(bundle.trip, departs_at)
    arrives_dt = _dest_local_dt(bundle.trip, arrives_at)
    client.table("flights").update(
        {
            "leg": leg,
            "code": code or None,
            "endpoint_from": endpoint_from.strip() or None,
            "endpoint_from_sub": endpoint_from_sub.strip() or None,
            "endpoint_to": endpoint_to.strip() or None,
            "endpoint_to_sub": endpoint_to_sub.strip() or None,
            "note": note or None,
            "sort_order": sort_order,
            "arrives_at": _iso(arrives_dt),
            "departs_at": _iso(departs_dt),
            "is_trip_start": bool(is_trip_start),
            "is_trip_end": bool(is_trip_end),
        }
    ).eq("id", flight_id).execute()
    _sync_flight_block(client, bundle, flight_id, departs_at=departs_dt, arrives_at=arrives_dt, leg=leg, code=code, note=note)
    return RedirectResponse("/flights", status_code=303)


@app.post("/flights/{flight_id}/delete")
def flight_delete(request: Request, flight_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    client = get_supabase_client()
    client.table("flights").delete().eq("id", flight_id).execute()
    return RedirectResponse("/flights", status_code=303)


def _empty_form(day_index: int, prefill_type: str = "museum", start_hour: float | None = None) -> dict:
    start = logic.fmt(start_hour) if start_hour is not None else "14:00"
    return {
        "day_index": day_index,
        "type": prefill_type,
        "title": "",
        "subtitle": "",
        "start": start,
        "length_minutes": 120,
        "travel_pad": False,
        "who": "Both",
    }


@app.get("/add", response_class=HTMLResponse)
def add_form(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth

    try:
        day_index = int(request.query_params.get("day", 2))
    except ValueError:
        day_index = 2
    if day_index not in bundle.days_by_index:
        day_index = next(iter(bundle.days_by_index), 2)

    prefill_type = request.query_params.get("type", "museum")
    if prefill_type not in logic.INK:
        prefill_type = "museum"

    start_hour = None
    start_param = request.query_params.get("start")
    if start_param is not None:
        try:
            start_hour = float(start_param)
        except ValueError:
            start_hour = None

    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "days": bundle.days,
        "form": _empty_form(day_index, prefill_type, start_hour),
        "form_action": "/add",
    }
    return HTMLResponse(templates.add_page(ctx))


def _local_dt(day: dict, tz_name: str, hh: int, mm: int) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime(day["calendar_date"].year, day["calendar_date"].month, day["calendar_date"].day, hh, mm, tzinfo=ZoneInfo(tz_name))


@app.post("/add", response_class=HTMLResponse)
def add_submit(
    request: Request,
    day_index: int = Form(...),
    type: str = Form(...),
    title: str = Form(...),
    subtitle: str = Form(""),
    start: str = Form(...),
    length_minutes: int = Form(...),
    who: str = Form("Both"),
    travel_pad: str | None = Form(None),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    day = bundle.days_by_index.get(day_index)
    if not day or type not in logic.INK:
        return RedirectResponse("/add", status_code=303)

    hh, mm = (int(p) for p in start.split(":"))
    starts_at = _local_dt(day, day["reference_timezone"], hh, mm)
    ends_at = starts_at + timedelta(minutes=length_minutes)

    client = get_supabase_client()
    rows = [
        {
            "trip_id": bundle.trip["id"],
            "trip_day_id": day["id"],
            "type": type,
            "title": title.strip(),
            "subtitle": subtitle.strip() or None,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "who": who,
        }
    ]
    if travel_pad:
        pad_start = starts_at - timedelta(minutes=45)
        rows.insert(
            0,
            {
                "trip_id": bundle.trip["id"],
                "trip_day_id": day["id"],
                "type": "transit",
                "title": f"Travel to {title.strip()}",
                "subtitle": f"Auto-blocked for the {starts_at.strftime('%H:%M')} start",
                "starts_at": pad_start.isoformat(),
                "ends_at": starts_at.isoformat(),
                "who": who,
            },
        )
    client.table("blocks").insert(rows).execute()
    return RedirectResponse(f"/day/{day_index}", status_code=303)


@app.get("/blocks/{block_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, block_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    block = bundle.block_by_id.get(block_id)
    if not block:
        return RedirectResponse("/day/2", status_code=303)
    day = bundle.days_by_id[block["trip_day_id"]]
    from zoneinfo import ZoneInfo

    local_start = block["starts_at"].astimezone(ZoneInfo(day["reference_timezone"]))
    length_minutes = round((block["ends_at"] - block["starts_at"]).total_seconds() / 60)
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(*_clock_bounds(bundle)),
        "days": bundle.days,
        "block_id": block_id,
        "form": {
            "day_index": day["day_index"],
            "type": block["type"],
            "title": block["title"],
            "subtitle": block.get("subtitle"),
            "start": local_start.strftime("%H:%M"),
            "length_minutes": length_minutes,
            "travel_pad": False,
            "who": block["who"],
        },
        "form_action": f"/blocks/{block_id}/edit",
    }
    return HTMLResponse(templates.add_page(ctx))


@app.post("/blocks/{block_id}/edit", response_class=HTMLResponse)
def edit_submit(
    request: Request,
    block_id: str,
    day_index: int = Form(...),
    type: str = Form(...),
    title: str = Form(...),
    subtitle: str = Form(""),
    start: str = Form(...),
    length_minutes: int = Form(...),
    who: str = Form("Both"),
):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    day = bundle.days_by_index.get(day_index)
    if not day or type not in logic.INK:
        return RedirectResponse(f"/blocks/{block_id}/edit", status_code=303)

    hh, mm = (int(p) for p in start.split(":"))
    starts_at = _local_dt(day, day["reference_timezone"], hh, mm)
    ends_at = starts_at + timedelta(minutes=length_minutes)

    client = get_supabase_client()
    client.table("blocks").update(
        {
            "trip_day_id": day["id"],
            "type": type,
            "title": title.strip(),
            "subtitle": subtitle.strip() or None,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "who": who,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", block_id).execute()
    return RedirectResponse(f"/day/{day_index}", status_code=303)


@app.post("/blocks/{block_id}/delete")
def delete_block(request: Request, block_id: str):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    block = bundle.block_by_id.get(block_id)
    day_index = bundle.days_by_id[block["trip_day_id"]]["day_index"] if block else 2
    client = get_supabase_client()
    if block and block.get("ticket_id"):
        # Deleting a ticket cascades (via FK) to delete this block too.
        client.table("tickets").delete().eq("id", block["ticket_id"]).execute()
    elif block and block.get("flight_id"):
        client.table("flights").delete().eq("id", block["flight_id"]).execute()
    else:
        client.table("blocks").delete().eq("id", block_id).execute()
    return RedirectResponse(f"/day/{day_index}", status_code=303)
