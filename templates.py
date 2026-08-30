"""Server-rendered HTML templates.

Plain Python f-strings returning `HTMLResponse` bodies — no Jinja, no
client-side framework, no build step, per this repo's stack convention.
One shared CSS shell carries the design tokens pulled from the Claude
Design export (`London Trip.dc.html`): the dark palette, the
Playfair Display / IBM Plex Sans / IBM Plex Mono type system, the gold
accent, and the card/rail component shapes. Small inline `<script>` blocks
are used only for trivial input affordances (building up a PIN, a stepper
button) — never a reason to add a framework.
"""

from html import escape as esc

SHARED_STYLE = """
:root{
  --bg:#0e0d11; --panel:#16151a; --panel-2:#1c1a20; --panel-3:#1e1c22; --panel-4:#221f27;
  --ink:#f2ece1; --ink-70:rgba(242,236,225,.7); --ink-55:rgba(242,236,225,.55);
  --ink-40:rgba(242,236,225,.4); --ink-25:rgba(242,236,225,.25); --ink-10:rgba(242,236,225,.1);
  --gold:#c9973f; --gold-hi:#e2b25e; --gold-dim:rgba(201,151,63,.35);
  --border:rgba(242,236,225,.09); --border-gold:rgba(201,151,63,.35);
}
*{box-sizing:border-box}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:rgba(242,236,225,.14);border-radius:8px}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
  font-family:'IBM Plex Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--gold);text-decoration:none}
a:hover{color:var(--gold-hi)}
input,select,button{font-family:inherit}
.serif{font-family:'Playfair Display',Georgia,serif}
.mono{font-family:'IBM Plex Mono',monospace}
.kicker{font:400 11px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}
.label{font:400 10px/1 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-40)}
.h1{font:400 32px/1.1 'Playfair Display',Georgia,serif;color:var(--ink);margin:8px 0 0}
.h2{font:400 26px/1.12 'Playfair Display',Georgia,serif;color:var(--ink);margin:6px 0 0}
.italic{font-style:italic;color:var(--gold)}
.pill{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:9px;
  border:1px solid var(--border-gold);color:var(--gold);font:500 10.5px/1 'IBM Plex Mono',monospace}
.btn{cursor:pointer;border:none;border-radius:9px;padding:9px 14px;font:500 11.5px/1 'IBM Plex Sans',sans-serif}
.btn-gold{background:var(--gold);color:#16151a}
.btn-ghost{background:transparent;border:1px solid var(--ink-10);color:var(--ink-70)}
.dash{height:1px;background:var(--border-gold);margin:20px 0}

.app{display:flex;min-height:100vh}
.sidebar{display:none}
.main{flex:1;min-width:0;padding-bottom:110px}
.mobile-topbar{padding:20px 20px 0;background:var(--panel-2);border-bottom:1px solid var(--border-gold)}
.mobile-tabbar{position:fixed;bottom:0;left:0;right:0;z-index:30;display:flex;gap:6px;
  padding:10px 12px 18px;background:linear-gradient(rgba(22,21,26,.0),var(--panel) 45%);
  backdrop-filter:blur(8px);border-top:1px solid var(--border)}
.tab{flex:1;text-align:center;padding:9px 0;border-radius:11px;font:500 11.5px/1 'IBM Plex Sans',sans-serif;
  color:var(--ink-55)}
.tab.active{background:rgba(201,151,63,.18);color:var(--gold)}
.desktop-only{display:none}

@media(min-width:900px){
  .app{max-width:1360px;margin:0 auto}
  .sidebar{display:flex;flex-direction:column;width:230px;flex:none;padding:26px 20px;
    border-right:1px solid var(--border);background:var(--panel-2);min-height:100vh}
  .main{padding:0 28px 60px}
  .mobile-topbar,.mobile-tabbar,.mobile-only{display:none!important}
  .desktop-only{display:block}
  .desktop-header{display:flex;align-items:flex-end;gap:18px;padding:28px 0 16px;border-bottom:1px solid var(--border)}
}

.people-row{display:flex;flex-direction:column;gap:9px;margin-top:14px}
.person-chip{display:flex;align-items:center;gap:9px}
.avatar{width:26px;height:26px;border-radius:50%;flex:none;color:#16151a;font:500 11px/26px 'IBM Plex Sans',sans-serif;text-align:center}
.side-nav{display:flex;flex-direction:column;gap:3px;margin-top:22px}
.side-nav a{display:block;padding:9px 11px;border-radius:9px;font:500 12.5px/1 'IBM Plex Sans',sans-serif;color:var(--ink-70)}
.side-nav a.active{background:rgba(201,151,63,.16);color:var(--gold)}
.ground-card{margin-top:24px;padding:13px;border-radius:11px;border:1px solid var(--gold-dim);background:rgba(201,151,63,.07)}

.day-chips{display:flex;gap:6px;margin-top:16px;overflow-x:auto;padding-bottom:4px}
.day-chip{flex:none;width:46px;padding:8px 0 9px;border-radius:11px;text-align:center;border:1px solid var(--border)}
.day-chip.active{background:rgba(201,151,63,.18);border-color:var(--border-gold)}
.day-chip .dow{font:400 9.5px/1 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-40)}
.day-chip.active .dow{color:var(--gold)}
.day-chip .dom{font:500 15px/1 'IBM Plex Sans',sans-serif;color:var(--ink-70);margin-top:6px}
.day-chip.active .dom{color:var(--gold)}

.stat-row{display:flex;gap:20px;padding:12px 20px;background:var(--panel);border-bottom:1px solid var(--border)}
.stat .label{margin-bottom:5px}
.stat .value{font:500 13px/1 'IBM Plex Sans',sans-serif}

.rail-wrap{padding:14px 20px 30px;overflow-x:auto}
.rail{position:relative}
.rail-line{position:absolute;left:0;right:0;height:1px;background:var(--ink-10)}
.rail-label{position:absolute;left:0;font:400 10px/1 'IBM Plex Mono',monospace;color:var(--ink-25)}
.rail-blocks{position:absolute;left:46px;right:0;top:0;bottom:0}
.block{position:absolute;cursor:pointer;border-radius:10px;overflow:hidden;background:rgba(242,236,225,.05);
  border:1px solid var(--ink-10);border-left-width:3px;border-left-style:solid;display:flex;flex-direction:column;gap:2px}
.block .title{font:500 13px/16px 'IBM Plex Sans',sans-serif;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.block .range{font:400 10px/16px 'IBM Plex Mono',monospace;flex:none}
.block .sub{font:400 11px/15px 'IBM Plex Sans',sans-serif;color:var(--ink-55);overflow:hidden}
.block-row{display:flex;align-items:baseline;justify-content:space-between;gap:8px}

.legend{display:flex;flex-direction:column;gap:9px;margin-top:13px}
.legend-item{display:flex;align-items:center;gap:10px;font:400 12.5px/1 'IBM Plex Sans',sans-serif;color:var(--ink-70)}
.swatch{width:10px;height:10px;border-radius:2px;flex:none}

.card{border-radius:14px;background:var(--panel-3);border:1px solid var(--ink-10);overflow:hidden}
.card-pad{padding:14px 15px}
.tick-head{display:flex;align-items:center;gap:8px}
.tick-facts{display:flex;flex-wrap:wrap;border-top:1px dashed rgba(242,236,225,.18)}
.tick-fact{flex:1;min-width:110px;padding:11px 12px;border-right:1px solid var(--border)}
.tick-fact .k{font:400 9px/1 'IBM Plex Mono',monospace;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-40)}
.tick-fact .v{font:500 12px/1.3 'IBM Plex Sans',sans-serif;color:rgba(242,236,225,.85);margin-top:5px}
.list-gap{display:flex;flex-direction:column;gap:11px;margin-top:20px}

.gap-card{padding:12px;border-radius:11px;border:1px dashed rgba(242,236,225,.22);background:rgba(242,236,225,.03)}

.clock-card{margin-top:18px;border-radius:16px;padding:18px;background:linear-gradient(150deg,#2a2530,#1b1a1f);
  border:1px solid var(--border-gold)}
.clock-split{display:flex;gap:12px;margin-top:16px}
.clock-half{flex:1;padding-top:11px;border-top:1px solid var(--gold-dim)}

.type-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.type-chip{cursor:pointer;display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:20px;
  background:rgba(242,236,225,.04);border:1px solid var(--ink-10);color:var(--ink-70);font:500 12px/1 'IBM Plex Sans',sans-serif}
.type-chip input{display:none}
.type-chip:has(input:checked){background:rgba(201,151,63,.14);border-color:var(--border-gold);color:var(--ink)}
.field-label{font:400 9.5px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-40);margin-top:22px}
.field-input{margin-top:10px;width:100%;padding:14px;border-radius:12px;background:var(--panel-3);
  border:1px solid var(--ink-10);color:var(--ink);font:400 14px/1 'IBM Plex Sans',sans-serif;outline:none}
.field-row{display:flex;gap:10px;margin-top:12px}
.field-col{flex:1}
.who-row{display:flex;gap:8px;margin-top:12px}
.who-chip{flex:1;cursor:pointer;text-align:center;padding:11px 0;border-radius:10px;background:rgba(242,236,225,.04);
  border:1px solid var(--ink-10);color:var(--ink-70);font:500 12.5px/1 'IBM Plex Sans',sans-serif}
.who-chip input{display:none}
.who-chip:has(input:checked){background:rgba(201,151,63,.16);border-color:var(--border-gold);color:var(--gold)}
.pad-toggle{cursor:pointer;margin-top:22px;padding:15px;border-radius:13px;background:rgba(242,236,225,.04);
  border:1px solid var(--ink-10);display:flex;align-items:center;gap:13px}
.pad-toggle input{display:none}
.pad-toggle:has(input:checked){background:rgba(201,151,63,.1);border-color:var(--gold-dim)}

.login-wrap{max-width:420px;margin:0 auto;padding:70px 22px 40px}
.people-picker{display:flex;gap:10px;margin-top:26px}
.person-card{flex:1;cursor:pointer;padding:15px 14px 14px;border-radius:16px;border:1px solid var(--ink-10);
  background:rgba(242,236,225,.04);display:flex;flex-direction:column;gap:11px}
.person-card input{display:none}
.person-card:has(input:checked){border-color:var(--border-gold);background:rgba(201,151,63,.12)}
.pin-dots{display:flex;gap:8px}
.pin-dot{width:9px;height:9px;border-radius:50%;border:1px solid var(--gold-dim)}
.pin-dot.on{background:var(--gold)}
.pin-pad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:16px}
.pin-key{height:54px;border-radius:13px;background:rgba(242,236,225,.05);border:1px solid var(--ink-10);
  display:flex;align-items:center;justify-content:center;cursor:pointer;font:400 20px/1 'IBM Plex Sans',sans-serif;color:var(--ink)}
.pin-key:disabled{visibility:hidden}
.error-note{margin-top:14px;color:#d98a8a;font:400 12.5px/1.5 'IBM Plex Sans',sans-serif}

.sheet-overlay{display:none;position:fixed;inset:0;z-index:50;background:rgba(10,9,12,.68);
  align-items:flex-end;justify-content:center}
.sheet-overlay:target{display:flex}
.sheet{width:100%;max-width:480px;background:var(--panel-3);border-top:1px solid var(--border-gold);
  border-radius:24px 24px 0 0;padding:22px 22px 34px}
.sheet-grip{width:38px;height:4px;border-radius:2px;background:var(--ink-10);margin:0 auto 18px}
.sheet-facts{display:flex;flex-wrap:wrap;margin-top:18px;border-top:1px dashed rgba(242,236,225,.18);padding-top:4px}
.sheet-fact{width:50%;padding:12px 0}
.sheet-actions{display:flex;gap:9px;margin-top:14px}
.sheet-actions a{flex:1;text-align:center;padding:14px;border-radius:12px;font:500 13px/1 'IBM Plex Sans',sans-serif}

.week-grid{display:flex;min-height:0}
.week-days{display:flex;padding:11px 0 9px 52px;border-bottom:1px solid var(--border)}
.week-day{flex:1;padding-left:6px}
.week-day .dow{font:400 9.5px/1 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-40)}
.week-day.active .dow{color:var(--gold)}
.week-day .tag{font:500 12px/1 'IBM Plex Sans',sans-serif;color:var(--ink-70);margin-top:6px}
.week-day.active .tag{color:var(--gold)}
.week-rail{position:relative;margin-top:6px;margin-left:52px}
.week-cols{display:flex}
.week-col{flex:1;position:relative;border-left:1px solid var(--border);padding:0 4px;min-height:1px}
.week-block{position:absolute;cursor:pointer;border-radius:7px;overflow:hidden;background:rgba(242,236,225,.05);
  border:1px solid var(--ink-10);border-left-width:3px;border-left-style:solid;padding:4px 6px;
  display:flex;flex-direction:column;gap:2px;margin-left:3px}
.week-block .title{font:500 10.5px/13px 'IBM Plex Sans',sans-serif;color:var(--ink);overflow:hidden}
.week-block .start{font:400 8.5px/11px 'IBM Plex Mono',monospace;opacity:.8}
.free-panel{width:264px;flex:none;padding:0 0 20px 20px}
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400'
    '&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">'
)


def _sheet(anchor: str, ink: str, kind: str, title: str, sub: str, who: str, facts: list[dict], edit_href: str | None = None) -> str:
    facts_html = "".join(
        f'<div class="sheet-fact"><div class="label">{esc(f["k"])}</div>'
        f'<div style="font:500 13px/1.35 \'IBM Plex Sans\',sans-serif;color:var(--ink);margin-top:6px">{esc(f["v"])}</div></div>'
        for f in facts
    )
    edit_link = (
        f'<a href="{esc(edit_href)}" class="btn-gold" style="border:1px solid var(--border-gold);'
        f'background:rgba(201,151,63,.16);color:var(--gold-hi)">Edit block</a>'
        if edit_href
        else ""
    )
    return f"""
<div class="sheet-overlay" id="{anchor}">
  <div class="sheet">
    <div class="sheet-grip"></div>
    <div style="display:flex;align-items:center;gap:8px">
      <span class="swatch" style="background:{ink}"></span>
      <span class="mono" style="font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:{ink}">{esc(kind)}</span>
      <span class="mono" style="margin-left:auto;font-size:10px;color:var(--ink-40)">{esc(who)}</span>
    </div>
    <div class="serif" style="font-size:27px;line-height:1.12;margin-top:12px">{esc(title)}</div>
    <div style="font:400 12.5px/1.55 'IBM Plex Sans',sans-serif;color:var(--ink-55);margin-top:8px">{esc(sub)}</div>
    <div class="sheet-facts">{facts_html}</div>
    <div class="sheet-actions">
      {edit_link}
      <a href="#" class="btn-ghost" style="border:1px solid var(--ink-10);color:var(--ink-55)">Close</a>
    </div>
  </div>
</div>
"""


def sheet_for_block(block: dict, day_label: str) -> str:
    from logic import INK, dur, fmt

    facts = [
        {"k": "London time", "v": f"{fmt(block['s'])} – {fmt(block['e'])}"},
        {"k": "Denver time", "v": f"{fmt(block['s'] - 7)} – {fmt(block['e'] - 7)}"},
        {"k": "Length", "v": dur(block["e"] - block["s"])},
        {"k": "Day", "v": day_label},
    ]
    return _sheet(
        f"sheet-{block['id']}",
        INK[block["type"]]["ink"],
        INK[block["type"]]["label"],
        block["title"],
        block.get("subtitle") or "No notes yet.",
        block["who"],
        facts,
        edit_href=f"/blocks/{block['id']}/edit",
    )


def sheet_for_ticket(ticket: dict) -> str:
    from logic import INK

    facts = list(ticket["facts"]) + [{"k": "When", "v": ticket["when"]}]
    return _sheet(
        f"sheet-t-{ticket['id']}",
        INK[ticket["category"]]["ink"],
        ticket["kind"],
        ticket["title"],
        ticket["venue"] or "",
        ticket["who"],
        facts,
    )


def legend_html() -> str:
    from logic import INK

    items = "".join(
        f'<div class="legend-item"><span class="swatch" style="background:{v["ink"]}"></span>{esc(v["label"])}</div>'
        for v in INK.values()
    )
    return (
        f'<div class="legend">{items}'
        '<div class="legend-item"><span class="swatch" style="border:1px dashed rgba(242,236,225,.45)"></span>'
        "Free — suggestion slot</div></div>"
    )


def shell(*, title: str, active: str, session, trip: dict, travelers: list[dict], vacation: str, body: str, sheets: str = "") -> str:
    people_html = "".join(
        f'<div class="person-chip"><span class="avatar" style="background:{"#c9973f" if t["id"] == session.traveler_id else "rgba(242,236,225,.75)"}">{esc(t["initial"])}</span>'
        f'<span style="font:400 12px/1 \'IBM Plex Sans\',sans-serif;color:var(--ink-70)">{esc(t["name"])}</span></div>'
        for t in travelers
    )
    nav_items = [("day", "/day/1", "Week / Day"), ("tickets", "/tickets", "Tickets"), ("flights", "/flights", "Flights"), ("add", "/add", "New block")]
    side_nav = "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}">{esc(label)}</a>' for key, href, label in nav_items
    )
    tabs = [("day", "/day/1", "Day"), ("tickets", "/tickets", "Tickets"), ("flights", "/flights", "Flights"), ("add", "/add", "+ Add")]
    tab_html = "".join(
        f'<a href="{href}" class="tab {"active" if key == active else ""}">{esc(label)}</a>' for key, href, label in tabs
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{FONT_LINK}
<style>{SHARED_STYLE}</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="serif" style="font-size:21px;line-height:1.15">{esc(trip["name"].split(",")[0])}<br>
      <span class="italic">{esc(trip["name"].split(",")[1].strip()) if "," in trip["name"] else ""}</span></div>
    <nav class="side-nav">{side_nav}</nav>
    <div class="dash" style="margin:22px 0;background:var(--border)"></div>
    <div class="label">Signed in</div>
    <div class="people-row">{people_html}</div>
    <div class="ground-card">
      <div class="kicker">On the ground</div>
      <div class="serif" style="font-size:22px;margin-top:8px">{esc(vacation)}</div>
    </div>
    <form method="post" action="/logout" style="margin-top:22px">
      <button class="btn btn-ghost" type="submit" style="width:100%">Sign out</button>
    </form>
  </aside>
  <div class="main">{body}</div>
</div>
<nav class="mobile-tabbar">{tab_html}</nav>
{sheets}
</body>
</html>"""


def login_page(travelers: list[dict], trip_name: str, error: str | None = None) -> str:
    people_html = "".join(
        f"""<label class="person-card">
          <input type="radio" name="traveler_id" value="{t['id']}" {"checked" if i == 0 else ""}>
          <span class="avatar" style="background:{"#c9973f" if i == 0 else "rgba(242,236,225,.75)"}">{esc(t['initial'])}</span>
          <span style="font:500 14.5px/1 'IBM Plex Sans',sans-serif">{esc(t['name'])}</span>
          <span class="mono" style="font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-40)">{esc(t['role'])}</span>
        </label>"""
        for i, t in enumerate(travelers)
    )
    error_html = f'<div class="error-note">{esc(error)}</div>' if error else ""
    name, _, sub = trip_name.partition(",")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — {esc(trip_name)}</title>
{FONT_LINK}
<style>{SHARED_STYLE}</style>
</head>
<body>
<div class="login-wrap">
  <div class="kicker">Private · two travellers</div>
  <div class="serif" style="font-size:44px;line-height:1;margin-top:14px">{esc(name)},<br>
    <span class="italic">{esc(sub.strip())}</span></div>
  <div style="font:400 13px/1.6 'IBM Plex Sans',sans-serif;color:var(--ink-55);margin-top:12px;max-width:320px">
    Nothing in here is public. Pick who you are, then enter the shared code.</div>

  <form method="post" action="/login">
    <div class="people-picker">{people_html}</div>

    <div style="margin-top:30px">
      <div class="label" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
        <span>Shared code</span>
        <span class="pin-dots" id="pin-dots">
          <span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span>
        </span>
      </div>
      <input type="hidden" name="pin" id="pin-input" maxlength="4" pattern="[0-9]{{4}}" required>
      <div class="pin-pad" id="pin-pad">
        <button type="button" class="pin-key" data-k="1">1</button>
        <button type="button" class="pin-key" data-k="2">2</button>
        <button type="button" class="pin-key" data-k="3">3</button>
        <button type="button" class="pin-key" data-k="4">4</button>
        <button type="button" class="pin-key" data-k="5">5</button>
        <button type="button" class="pin-key" data-k="6">6</button>
        <button type="button" class="pin-key" data-k="7">7</button>
        <button type="button" class="pin-key" data-k="8">8</button>
        <button type="button" class="pin-key" data-k="9">9</button>
        <button type="button" class="pin-key" disabled></button>
        <button type="button" class="pin-key" data-k="0">0</button>
        <button type="button" class="pin-key" data-k="back">&larr;</button>
      </div>
    </div>
    {error_html}
  </form>
</div>
<script>
(function(){{
  var input = document.getElementById('pin-input');
  var dots = document.querySelectorAll('#pin-dots .pin-dot');
  var form = input.closest('form');
  function render(){{
    dots.forEach(function(d, i){{ d.classList.toggle('on', i < input.value.length); }});
  }}
  document.getElementById('pin-pad').addEventListener('click', function(e){{
    var btn = e.target.closest('.pin-key');
    if (!btn || btn.disabled) return;
    var k = btn.getAttribute('data-k');
    if (k === 'back') input.value = input.value.slice(0, -1);
    else if (input.value.length < 4) input.value += k;
    render();
    if (input.value.length === 4) setTimeout(function(){{ form.submit(); }}, 180);
  }});
}})();
</script>
</body>
</html>"""


def render_block(el: dict) -> str:
    if el["wide"]:
        head = (
            f'<div class="block-row"><span class="title">{esc(el["title"])}</span>'
            f'<span class="range mono" style="color:{el["ink"]}">{el["range"]}</span></div>'
        )
    else:
        head = f'<div class="title" style="font-size:12.5px;line-height:15px">{esc(el["title"])}</div>'
        if el["show_range"]:
            head += f'<div class="range mono" style="font-size:9.5px;line-height:12px;color:{el["ink"]}">{el["range"]}</div>'
    sub = f'<div class="sub">{esc(el["sub"])}</div>' if el["show_sub"] else ""
    return (
        f'<a class="block" href="#sheet-{el["id"]}" '
        f'style="left:{el["left"]};width:{el["width"]};top:{el["top"]}px;height:{el["h"]}px;'
        f'border-left-color:{el["ink"]};padding:{el["pad"]}">{head}{sub}</a>'
    )


def render_week_block(el: dict) -> str:
    start_html = ""
    if el["show_start"]:
        start_html = f'<div class="start mono" style="color:{el["ink"]}">{el["range"].split("–")[0]}</div>'
    return (
        f'<a class="week-block" href="#sheet-{el["id"]}" '
        f'style="left:{el["left"]};width:{el["width"]};top:{el["top"]}px;height:{el["h"]}px;border-left-color:{el["ink"]}">'
        f'<div class="title" style="-webkit-box-orient:vertical;display:-webkit-box;overflow:hidden;'
        f'-webkit-line-clamp:{el["lines"]}">{esc(el["title"])}</div>{start_html}</a>'
    )


def render_hour_rail(px: int) -> tuple[str, int]:
    from logic import H0, H1, fmt

    parts = []
    for h in range(H0, H1 + 1):
        top = round((h - H0) * px)
        parts.append(f'<div class="rail-line" style="top:{top}px"></div>')
        parts.append(f'<div class="rail-label" style="top:{top - 5}px">{fmt(h)}</div>')
    height = (H1 - H0) * px + 20
    return "".join(parts), height


def day_chip(d: dict, active: bool) -> str:
    return (
        f'<a href="/day/{d["day_index"]}" class="day-chip {"active" if active else ""}">'
        f'<div class="dow">{esc(d["dow"])}</div><div class="dom">{esc(d["dom"])}</div></a>'
    )


def gap_card(g: dict, day_index: int) -> str:
    return f"""<div class="gap-card">
  <div style="display:flex;align-items:baseline;justify-content:space-between">
    <span class="mono" style="font-size:12px;color:var(--ink)">{esc(g["range"])}</span>
    <span class="mono" style="font-size:10px;color:var(--ink-40)">{esc(g["len"])}</span>
  </div>
  <div style="font:400 11.5px/1.45 'IBM Plex Sans',sans-serif;color:var(--ink-55);margin-top:7px">{esc(g["hint"])}</div>
  <a href="/add?day={day_index}&amp;start={g["start_hour"]}" class="mono"
     style="display:inline-block;margin-top:9px;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase">Fill this slot &rarr;</a>
</div>"""


def ticket_side_card(t: dict) -> str:
    return f"""<a href="#sheet-t-{t['id']}" class="card" style="display:block;padding:11px 12px;margin-bottom:8px;background:var(--panel-4)">
  <div style="display:flex;align-items:center;gap:7px">
    <span class="swatch" style="background:{t['ink']}"></span>
    <span class="mono" style="font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:{t['ink']}">{esc(t['kind'])}</span>
  </div>
  <div class="serif" style="font-size:15px;line-height:1.2;margin-top:7px">{esc(t['title'])}</div>
  <div class="mono" style="font-size:10.5px;line-height:1.4;color:var(--ink-40);margin-top:5px">{esc(t['when'])}</div>
</a>"""


def day_page(ctx: dict) -> str:
    day, days = ctx["day"], ctx["days"]
    mobile_lines, mobile_height = render_hour_rail(ctx["px_mobile"])
    mobile_blocks = "".join(render_block(b) for b in ctx["mobile_blocks"])
    day_chips = "".join(day_chip(d, d["day_index"] == day["day_index"]) for d in days)

    week_lines, week_height = render_hour_rail(ctx["px_desktop"])
    week_cols = []
    for wd in ctx["week_days"]:
        blocks_html = "".join(render_week_block(b) for b in wd["blocks"])
        week_cols.append(f'<div class="week-col">{blocks_html}</div>')
    week_day_headers = "".join(
        f'<a href="/day/{wd["day_index"]}" class="week-day {"active" if wd["day_index"] == day["day_index"] else ""}">'
        f'<div class="dow">{esc(wd["dow"])} {esc(wd["dom"])}</div><div class="tag">{esc(wd["tag"])}</div></a>'
        for wd in ctx["week_days"]
    )

    gaps_html = "".join(gap_card(g, day["day_index"]) for g in ctx["gaps"]) or (
        '<div style="font:400 12px/1.5 \'IBM Plex Sans\',sans-serif;color:var(--ink-40)">No free windows today.</div>'
    )
    tickets_html = "".join(ticket_side_card(t) for t in ctx["tickets"])

    stats_html = "".join(
        f'<div class="stat"><div class="label">{esc(s["label"])}</div>'
        f'<div class="value" style="color:{s["ink"]}">{esc(s["value"])}</div></div>'
        for s in ctx["stats"]
    )

    body = f"""
<div class="mobile-only mobile-topbar">
  <div class="kicker">{esc(day["kicker"])}</div>
  <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:10px">
    <div class="serif" style="font-size:28px;line-height:1.1;margin-top:6px">{esc(day["date_label"])}</div>
    <a href="{ctx["toggle_href"]}" class="pill">{esc(ctx["tz_chip"])}</a>
  </div>
  <div class="day-chips">{day_chips}</div>
</div>
<div class="mobile-only stat-row">{stats_html}</div>
<div class="mobile-only rail-wrap">
  <div class="rail" style="height:{mobile_height}px">
    {mobile_lines}
    <div class="rail-blocks">{mobile_blocks}</div>
  </div>
</div>
<div class="mobile-only" style="padding:20px">
  <div class="kicker">Free windows</div>
  <div class="list-gap">{gaps_html}</div>
</div>

<div class="desktop-only">
  <div class="desktop-header">
    <div>
      <div class="kicker">Week view · London time</div>
      <div class="h2">{esc(ctx["week_title"])}</div>
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
      <a href="{ctx["toggle_href"]}" class="pill">{esc(ctx["tz_chip"])}</a>
      <a href="/add" class="btn btn-gold">+ New block</a>
    </div>
  </div>
  <div class="week-grid">
    <div style="flex:1;min-width:0">
      <div class="week-days">{week_day_headers}</div>
      <div class="week-rail" style="height:{week_height}px">
        {week_lines}
        <div class="week-cols" style="position:absolute;left:0;right:0;top:0;bottom:0">{''.join(week_cols)}</div>
      </div>
    </div>
    <div class="free-panel">
      <div class="kicker">Free windows · {esc(day["date_label"])}</div>
      <div class="list-gap" style="margin-top:12px">{gaps_html}</div>
      <div class="dash"></div>
      <div class="kicker">Timed &amp; ticketed</div>
      <div style="margin-top:12px">{tickets_html}</div>
    </div>
  </div>
</div>
"""
    return shell(
        title=f"{day['date_label']} — {ctx['trip']['name']}",
        active="day",
        session=ctx["session"],
        trip=ctx["trip"],
        travelers=ctx["travelers"],
        vacation=ctx["vacation"],
        body=body,
        sheets=ctx["sheets"],
    )


def tickets_page(ctx: dict) -> str:
    cards = "".join(
        f"""<a href="#sheet-t-{t['id']}" class="card" style="display:block;margin-bottom:11px">
  <div class="card-pad">
    <div class="tick-head">
      <span class="swatch" style="background:{t['ink']}"></span>
      <span class="mono" style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:{t['ink']}">{esc(t['kind'])}</span>
      <span class="mono" style="margin-left:auto;font-size:10px;color:var(--ink-40)">{esc(t['who'])}</span>
    </div>
    <div class="serif" style="font-size:21px;line-height:1.15;margin-top:8px">{esc(t['title'])}</div>
    <div style="font:400 12px/1.5 'IBM Plex Sans',sans-serif;color:var(--ink-55)">{esc(t['venue'] or '')}</div>
  </div>
  <div class="tick-facts">{''.join(f'<div class="tick-fact"><div class="k">{esc(f["k"])}</div><div class="v">{esc(f["v"])}</div></div>' for f in t['facts'])}</div>
</a>"""
        for t in ctx["tickets"]
    )
    body = f"""
<div style="padding:56px 20px 30px">
  <div class="kicker">Bought &amp; booked</div>
  <div class="h1">Tickets</div>
  <div style="margin-top:20px">{cards}</div>
</div>
"""
    return shell(
        title=f"Tickets — {ctx['trip']['name']}",
        active="tickets",
        session=ctx["session"],
        trip=ctx["trip"],
        travelers=ctx["travelers"],
        vacation=ctx["vacation"],
        body=body,
        sheets=ctx["sheets"],
    )


def flights_page(ctx: dict) -> str:
    trip = ctx["trip"]
    rows = "".join(
        f"""<div class="card" style="margin-bottom:10px">
  <div class="card-pad">
    <div style="display:flex;align-items:center;gap:9px">
      <span class="mono" style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8fa2bd">{esc(f['leg'])}</span>
      <span class="mono" style="margin-left:auto;font-size:11px;color:var(--ink-55)">{esc(f['code'] or '')}</span>
    </div>
    <div style="display:flex;align-items:flex-end;gap:12px;margin-top:12px">
      <div><div class="serif" style="font-size:24px">{esc(f['endpoint_from'] or '')}</div>
        <div class="mono" style="font-size:11px;color:var(--ink-40);margin-top:6px">{esc(f['endpoint_from_sub'] or '')}</div></div>
      <div style="flex:1;height:1px;background:var(--gold-dim);margin-bottom:14px"></div>
      <div style="text-align:right"><div class="serif" style="font-size:24px">{esc(f['endpoint_to'] or '')}</div>
        <div class="mono" style="font-size:11px;color:var(--ink-40);margin-top:6px">{esc(f['endpoint_to_sub'] or '')}</div></div>
    </div>
    <div style="font:400 11.5px/1.5 'IBM Plex Sans',sans-serif;color:var(--ink-55);margin-top:12px;padding-top:11px;border-top:1px solid var(--border)">{esc(f['note'] or '')}</div>
  </div>
</div>"""
        for f in ctx["flights"]
    )
    body = f"""
<div style="padding:56px 20px 40px;max-width:640px">
  <div class="kicker">Trip boundaries</div>
  <div class="h1">Flights</div>
  <div class="clock-card">
    <div class="kicker">Vacation clock</div>
    <div class="h2" style="font-size:29px">{esc(ctx["vacation"])} <span class="italic" style="font-style:italic;font-size:18px;color:var(--ink-55)">on the ground</span></div>
    <div class="clock-split">
      <div class="clock-half"><div class="label">Starts · wheels down</div>
        <div style="font:500 13px/1.4 'IBM Plex Sans',sans-serif;margin-top:6px">{esc(ctx["starts_label"])}</div></div>
      <div class="clock-half"><div class="label">Ends · wheels up</div>
        <div style="font:500 13px/1.4 'IBM Plex Sans',sans-serif;margin-top:6px">{esc(ctx["ends_label"])}</div></div>
    </div>
  </div>
  <div style="margin-top:14px">{rows}</div>
  <a href="/add?type=travel" style="display:block;margin-top:16px;text-align:center;padding:14px;border-radius:13px;
     border:1px dashed var(--gold-dim);font:500 12.5px/1 'IBM Plex Sans',sans-serif">+ Add a flight or train leg</a>
</div>
"""
    return shell(
        title=f"Flights — {trip['name']}",
        active="flights",
        session=ctx["session"],
        trip=trip,
        travelers=ctx["travelers"],
        vacation=ctx["vacation"],
        body=body,
    )


def add_page(ctx: dict) -> str:
    from logic import INK

    type_chips = "".join(
        f"""<label class="type-chip">
  <input type="radio" name="type" value="{key}" {"checked" if key == ctx["form"]["type"] else ""}>
  <span class="swatch" style="background:{v['ink']}"></span>{esc(v['label'])}
</label>"""
        for key, v in INK.items()
    )
    who_chips = "".join(
        f"""<label class="who-chip"><input type="radio" name="who" value="{esc(w)}" {"checked" if w == ctx["form"]["who"] else ""}>{esc(w)}</label>"""
        for w in ("Dana", "Chris", "Both")
    )
    day_options = "".join(
        f'<option value="{d["day_index"]}" {"selected" if d["day_index"] == ctx["form"]["day_index"] else ""}>{esc(d["date_label"])}</option>'
        for d in ctx["days"]
    )
    error_html = f'<div class="error-note">{esc(ctx["error"])}</div>' if ctx.get("error") else ""
    body = f"""
<div style="padding:56px 20px 60px;max-width:520px">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <a href="/day/{ctx['form']['day_index']}" class="mono" style="font-size:12px;color:var(--ink-55)">Cancel</a>
    <span class="label">New block</span>
    <span></span>
  </div>
  <div class="h1">New block</div>
  <form method="post" action="{ctx["form_action"]}">
    <div class="field-label">Day</div>
    <select name="day_index" class="field-input">{day_options}</select>

    <div class="field-label">Type</div>
    <div class="type-chips">{type_chips}</div>

    <div class="field-label">What</div>
    <input class="field-input" name="title" placeholder="Name this block" value="{esc(ctx['form']['title'])}" required>

    <div class="field-label">Notes (optional)</div>
    <input class="field-input" name="subtitle" placeholder="Booking ref, address, notes" value="{esc(ctx['form'].get('subtitle') or '')}">

    <div class="field-row">
      <div class="field-col">
        <div class="field-label" style="margin-top:0">Start · London</div>
        <input class="field-input" type="time" name="start" value="{esc(ctx['form']['start'])}" step="900" required>
      </div>
      <div class="field-col">
        <div class="field-label" style="margin-top:0">Length (minutes)</div>
        <input class="field-input" type="number" name="length_minutes" min="15" step="15" value="{ctx['form']['length_minutes']}" required>
      </div>
    </div>

    <label class="pad-toggle">
      <input type="checkbox" name="travel_pad" value="1" {"checked" if ctx["form"].get("travel_pad") else ""}>
      <div>
        <div style="font:500 13px/1.3 'IBM Plex Sans',sans-serif">Block travel to this event</div>
        <div style="font:400 11.5px/1.4 'IBM Plex Sans',sans-serif;color:var(--ink-55);margin-top:4px">
          Adds a separate 45-minute "Travel to&hellip;" block right before this one.</div>
      </div>
    </label>

    <div style="margin-top:14px;padding:15px;border-radius:13px;background:var(--panel-3);border:1px solid var(--ink-10)">
      <div class="field-label" style="margin-top:0">Who's going</div>
      <div class="who-row">{who_chips}</div>
    </div>

    {error_html}
    <button type="submit" class="btn btn-gold" style="width:100%;margin-top:22px;padding:14px">Save block</button>
  </form>
  {f'''<form method="post" action="/blocks/{ctx["block_id"]}/delete" style="margin-top:10px" onsubmit="return confirm('Delete this block?')">
    <button type="submit" class="btn btn-ghost" style="width:100%;padding:14px;color:#d98a8a;border-color:rgba(217,138,138,.35)">Delete block</button>
  </form>''' if ctx.get("block_id") else ""}
</div>
"""
    return shell(
        title=f"New block — {ctx['trip']['name']}",
        active="add",
        session=ctx["session"],
        trip=ctx["trip"],
        travelers=ctx["travelers"],
        vacation=ctx["vacation"],
        body=body,
    )
