"""Time-grid layout and formatting logic.

This is a straight port of the interaction logic from the Claude Design
mockup ("London Trip.dc.html" — see support.js/`Component.blocksFor`,
`.gaps`, `fmt`, `dur`) from its client-side JS onto real `timestamptz` data,
computed server-side. The mockup used a fixed "-7 hours" hack to fake the
Denver/London toggle since it had no real timezone data; here the same
visual result falls out of real `zoneinfo` conversions, because both zones
sit on a constant 7-hour offset for the whole trip (BST and MDT don't change
during these ten days).
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

H0 = 8  # first hour shown on the rail
H1 = 23  # last hour shown on the rail
PX_MOBILE = 62  # pixels per hour, phone rail
PX_DESKTOP = 44  # pixels per hour, desktop rail

INK = {
    "travel": {"label": "Flight & airport", "ink": "#8fa2bd"},
    "transit": {"label": "Travel to event", "ink": "#6d7a8c"},
    "theatre": {"label": "Theatre", "ink": "#c9973f"},
    "meal": {"label": "Meal", "ink": "#c07555"},
    "walk": {"label": "Walking", "ink": "#7f9c6e"},
    "museum": {"label": "Museum", "ink": "#9182b8"},
    "library": {"label": "Library", "ink": "#5d97a1"},
    "tourist": {"label": "Tourist attraction", "ink": "#b0687f"},
    "rest": {"label": "Hotel & rest", "ink": "#6a6572"},
}

TIMEZONES = {
    "london": {"zone": ZoneInfo("Europe/London"), "chip": "GMT+1 London"},
    "denver": {"zone": ZoneInfo("America/Denver"), "chip": "MDT Denver"},
}


def fmt(h: float) -> str:
    t = h % 24
    hh = int(t)
    mm = round((t - hh) * 60)
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}"


def dur(hours: float) -> str:
    hh = int(hours)
    mm = round((hours - hh) * 60)
    if not hh and not mm:
        return "0m"
    parts = []
    if hh:
        parts.append(f"{hh}h")
    if mm:
        parts.append(f"{mm}m")
    return " ".join(parts)


def hours_of_day(dt: datetime, day_date: date, tz: ZoneInfo) -> float:
    """Hours elapsed since local midnight of `day_date` in `tz`."""
    midnight = datetime.combine(day_date, time.min, tzinfo=tz)
    return (dt.astimezone(tz) - midnight).total_seconds() / 3600


@dataclass
class LaidOutBlock:
    block: dict
    top: int
    height: int
    left_pct: float
    width_pct: float
    show_start: bool
    lines: int
    pad: str
    show_range: bool
    show_sub: bool
    range_label: str
    start_only: str


def _assign_lanes(items: list[dict]) -> tuple[dict[int, int], dict[int, int]]:
    """Greedy interval-graph coloring, ported from the mockup's lane assignment."""
    lane_end: list[float] = []
    lane_of: dict[int, int] = {}
    for i, b in enumerate(items):
        lane_index = next((li for li, end in enumerate(lane_end) if end <= b["s"] + 0.001), None)
        if lane_index is None:
            lane_index = len(lane_end)
            lane_end.append(b["e"])
        else:
            lane_end[lane_index] = b["e"]
        lane_of[i] = lane_index

    group_cols: dict[int, int] = {}
    for i, b in enumerate(items):
        n = 1
        for j, o in enumerate(items):
            if j != i and o["s"] < b["e"] - 0.001 and b["s"] < o["e"] - 0.001:
                n = max(n, lane_of[j] + 1)
        group_cols[i] = max(n, lane_of[i] + 1)
    return lane_of, group_cols


def layout_blocks(blocks: list[dict], day_date: date, tz: ZoneInfo, px: int) -> list[dict]:
    """Position blocks on the hour rail, matching `Component.blocksFor`."""
    items = []
    for b in blocks:
        s_raw = hours_of_day(b["starts_at"], day_date, tz)
        e_raw = hours_of_day(b["ends_at"], day_date, tz)
        if e_raw <= H0:
            continue
        items.append({**b, "s": s_raw, "e": e_raw})
    items.sort(key=lambda b: (b["s"], b["e"]))

    lane_of, group_cols = _assign_lanes(items)
    desk = px == PX_DESKTOP

    laid_out = []
    for i, b in enumerate(items):
        s, e = max(b["s"], H0), min(b["e"], H1)
        lane, cols = lane_of[i], group_cols[i]
        height = max(40 if desk else 26, round((e - s) * px) - 4)
        show_start = desk and cols < 2 and height >= 58
        lines = max(1, (height - 10 - (11 if show_start else 0)) // 13)
        laid_out.append(
            {
                "id": b["id"],
                "type": b["type"],
                "title": b["title"],
                "sub": b.get("subtitle") or INK[b["type"]]["label"],
                "who": b["who"],
                "ink": INK[b["type"]]["ink"],
                "top": round((s - H0) * px),
                "h": height,
                "tall": height >= 46,
                "wide": cols < 2,
                "narrow": cols > 1,
                "lines": int(lines),
                "show_start": show_start,
                "pad": "8px 10px" if height >= 46 else "4px 9px",
                "show_range": height >= 44,
                "show_sub": height >= 62,
                "left": f"{(lane * 100 / cols):.3f}%",
                "width": f"calc({(100 / cols):.3f}% - 3px)",
                "range": f"{fmt(b['s'])}–{fmt(b['e'])}",
            }
        )
    return laid_out


def compute_gaps(blocks: list[dict], day_date: date, tz: ZoneInfo, window: tuple[float, float] = (9, 21)) -> list[dict]:
    """Free-window suggestions, ported from `Component.gaps`."""
    day_start, day_end = window
    spans = sorted(
        (
            (hours_of_day(b["starts_at"], day_date, tz), hours_of_day(b["ends_at"], day_date, tz))
            for b in blocks
        ),
        key=lambda x: x[0],
    )
    out = []
    cur = day_start
    for s, e in spans:
        if s - cur >= 1:
            out.append((cur, s))
        cur = max(cur, e)
    if day_end - cur >= 1:
        out.append((cur, day_end))

    results = []
    for s, e in out:
        length = e - s
        if length >= 2.5:
            hint = "Long enough for a museum with a proper sit-down — V&A or the Wallace Collection."
        elif length >= 1.75:
            hint = "Library or bookshop window. British Library is 12 min on the Piccadilly line."
        elif length >= 1.25:
            hint = "Good walking block. Nothing ticketed, no rushing."
        else:
            hint = "Coffee, a browse, or padding before the next thing."
        results.append(
            {
                "range": f"{fmt(s)}–{fmt(e)}",
                "len": dur(length),
                "hours": length,
                "hint": hint,
                "start_hour": s,
            }
        )
    return results


def vacation_length(starts_at: datetime, ends_at: datetime) -> str:
    total_hours = (ends_at - starts_at).total_seconds() / 3600
    days = int(total_hours // 24)
    hours = round(total_hours % 24)
    if hours == 0:
        return f"{days} days"
    return f"{days} days {hours} hrs"
