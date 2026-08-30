# Bespoke-Interval

A private itinerary planner built for two travelers. Schedules every block in the destination timezone, reserves travel time around ticketed events, tracks theatre and timed-entry bookings, and matches free windows to museums, libraries, and walks. The trip runs wheels-down to wheels-up.

The design (`design/London Trip.dc.html`, a Claude Design export) is the visual spec for the app: a private "Thanksgiving, London" trip for two travelers, jd and emy, with a shared password, a day/week schedule, a tickets list, and a flights/vacation-clock view.

## Stack

Server-rendered Python (FastAPI) + Supabase (Postgres) + Vercel, with no client-side framework and no build step — see `.claude/SKILL.md` for the full pattern this repo follows. There is no user-account system: the app is unlocked with one shared password for the trip, plus picking which traveler you are.

```
main.py                       # all routes and business logic
templates.py                  # server-rendered HTML (shared CSS shell + page renderers)
logic.py                      # time-grid layout, gap-finding, formatting (ported from the design's JS)
auth.py                       # signed session cookie + password verification
db.py                         # Supabase client
api/index.py                  # Vercel entry-point shim (re-exports `app` from main.py)
supabase/migrations/          # schema + seed data, applied via the Supabase CLI
test_main.py                  # pytest, mocks the Supabase client
```

## First-time setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Install the Supabase CLI and run `supabase login`.
3. From the repo root: `supabase link --project-ref <your-project-ref>` (the ref is in the project's dashboard URL).
4. Apply the schema and seed data: `supabase db push`. This creates the `trips`, `travelers`, `trip_days`, `blocks`, `tickets`, and `flights` tables (all with RLS enabled and no public policies — every read/write goes through the backend's service-role key) and seeds one trip: **Thanksgiving, London**, Nov 22–30, 2026, for jd and emy.
5. From the dashboard (Project Settings → API), copy the **Project URL** and the **service-role key**. These become `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` below. The service-role key must never be exposed to the browser — it's only read server-side.

### 2. Vercel

1. From the [Vercel dashboard](https://vercel.com): Add New → Project → import this GitHub repo. This is what wires up auto-deploy on push to the default branch and preview deployments on PRs.
2. Under Settings → Environment Variables, add:

   | Variable | Value | Environments |
   |---|---|---|
   | `SUPABASE_URL` | from Supabase step 5 | Production, Preview, Development |
   | `SUPABASE_SERVICE_ROLE_KEY` | from Supabase step 5 | Production, Preview, Development — never expose to the client |
   | `SESSION_SECRET` | a long random string (`python3 -c "import secrets; print(secrets.token_hex(32))"`) | Production, Preview, Development |
   | `PASSWORD` | the shared password for jd and emy | Production, Preview, Development |
   | `TRIP_SLUG` | `thanksgiving-london-2026` (optional — this is the default) | all |

3. Deploy. `vercel.json` at the repo root tells Vercel to build `main.py` with `@vercel/python` and route all traffic to it.

### 3. Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SESSION_SECRET
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload
```

Then open `http://localhost:8000`, pick jd or emy, and enter the shared password (set in your `.env` file).

Run the tests (these mock the Supabase client — no live database needed):

```bash
pytest
```

## Notes on how the schema maps to the design

- `trips` holds the trip's true wheels-down/wheels-up instants — these drive the "vacation clock" and the London/Denver timezone toggle. The shared password is stored in the PASSWORD environment variable.
- `trip_days` gives each of the ten days on the itinerary a calendar date and its own natural timezone (Day 1, before landing, is America/Denver; every day after is Europe/London) — this replaces the design mockup's fixed "-7 hours" placeholder with a real, DST-correct conversion.
- `blocks` are the color-coded schedule items (`travel`, `transit`, `theatre`, `meal`, `walk`, `museum`, `library`, `tourist`, `rest`); free-window suggestions on the day/week view are computed from the gaps between them, not stored.
- `tickets` and `flights` are the "Bought & booked" and "Flights" screens' data — presentational, not scheduling inputs.

Adding a block from the app can also insert an auto-blocked "Travel to…" transit block 45 minutes before it, matching the design's "a 19:30 curtain blocks 18:45 too" behavior.
