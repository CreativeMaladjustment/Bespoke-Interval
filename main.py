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
from auth import COOKIE_NAME, Session, read_session, sign_session, verify_pin
from db import get_supabase_client, get_trip_slug

app = FastAPI()

COOKIE_KWARGS = dict(httponly=True, samesite="lax", secure=os.getenv("VERCEL_ENV") is not None, max_age=60 * 60 * 24 * 30)


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

        block_rows = client.table("blocks").select("*").eq("trip_id", self.trip["id"]).order("starts_at").execute().data
        self.blocks_by_day: dict[int, list[dict]] = {d["day_index"]: [] for d in self.days}
        self.block_by_id: dict[str, dict] = {}
        for b in block_rows:
            b = {**b, "starts_at": _parse_dt(b["starts_at"]), "ends_at": _parse_dt(b["ends_at"])}
            day = self.days_by_id.get(b["trip_day_id"])
            if day:
                self.blocks_by_day[day["day_index"]].append(b)
            self.block_by_id[b["id"]] = b

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

        self.flights = (
            client.table("flights").select("*").eq("trip_id", self.trip["id"]).order("sort_order").execute().data
        )


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
    return templates._sheet(
        f"sheet-{b['id']}",
        logic.INK[b["type"]]["ink"],
        logic.INK[b["type"]]["label"],
        b["title"],
        b.get("subtitle") or "No notes yet.",
        b["who"],
        facts,
        edit_href=f"/blocks/{b['id']}/edit",
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
def login_submit(traveler_id: str = Form(...), pin: str = Form(...)):
    bundle = _get_bundle()
    traveler = next((t for t in bundle.travelers if t["id"] == traveler_id), None)
    if not traveler or not verify_pin(pin, bundle.trip["pin_hash"]):
        return HTMLResponse(
            templates.login_page(bundle.travelers, bundle.trip["name"], error="That code didn't match. Try again."),
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
        "vacation": logic.vacation_length(bundle.trip["starts_at"], bundle.trip["ends_at"]),
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
        "vacation": logic.vacation_length(bundle.trip["starts_at"], bundle.trip["ends_at"]),
        "tickets": bundle.tickets,
        "sheets": sheets,
    }
    return HTMLResponse(templates.tickets_page(ctx))


@app.get("/flights", response_class=HTMLResponse)
def flights_view(request: Request):
    auth = _authenticate(request)
    if not auth:
        return _login_redirect()
    session, bundle = auth
    dest_tz = _zone(bundle.trip["destination_timezone"])
    starts_local = bundle.trip["starts_at"].astimezone(dest_tz)
    ends_local = bundle.trip["ends_at"].astimezone(dest_tz)
    ctx = {
        "trip": bundle.trip,
        "travelers": bundle.travelers,
        "session": session,
        "vacation": logic.vacation_length(bundle.trip["starts_at"], bundle.trip["ends_at"]),
        "flights": bundle.flights,
        "starts_label": f"{_date_label(starts_local.date())} · {starts_local.strftime('%H:%M')} · {bundle.trip.get('starts_terminal') or ''}".strip(" ·"),
        "ends_label": f"{_date_label(ends_local.date())} · {ends_local.strftime('%H:%M')} · {bundle.trip.get('ends_terminal') or ''}".strip(" ·"),
    }
    return HTMLResponse(templates.flights_page(ctx))


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
        "vacation": logic.vacation_length(bundle.trip["starts_at"], bundle.trip["ends_at"]),
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
        "vacation": logic.vacation_length(bundle.trip["starts_at"], bundle.trip["ends_at"]),
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
    client.table("blocks").delete().eq("id", block_id).execute()
    return RedirectResponse(f"/day/{day_index}", status_code=303)
