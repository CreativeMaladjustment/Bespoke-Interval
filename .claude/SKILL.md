---
name: python-supabase-vercel-cicd
description: Sets up or replicates a Python (FastAPI) + Supabase + Vercel deployment pipeline — the pattern where Vercel's Git integration auto-deploys the backend on every push/PR, Supabase Postgres schema is tracked as versioned SQL migrations applied via the Supabase CLI, transactional email goes through Brevo, and CI secrets are scoped to a protected GitHub Environment rather than left readable by any workflow run. Use this whenever a user wants to deploy a Python backend to Vercel with a Supabase database, wants to "replicate" or "copy" a CI/CD setup from one repo into a new one, asks how to wire up Supabase migrations, Vercel cron jobs, environment variables, sending email (Brevo/transactional email), turning a Claude Design export into the app's frontend, or locking down GitHub Actions secrets so only approved reviewers/branches can access them. Also use it when debugging Vercel Python deploy failures (e.g. "app object not found", 500s that only happen in production) or Supabase RLS/migration issues in this stack.
---

# Python + Supabase + Vercel CI/CD

## What this pipeline actually is

There is no custom build server and (in the reference implementation this
skill is drawn from) no GitHub Actions workflow. "CI/CD" for this stack is
two independent, already-hosted pieces wired together by convention:

- **CD (the app)** — Vercel's native Git integration. Connect a GitHub repo
  to a Vercel project once, and every push to the default branch redeploys
  automatically; every PR gets its own preview deployment. There is nothing
  to write for this part — it's configuration, not code.
- **CD (the database)** — Supabase schema lives as an ordered list of SQL
  files under `supabase/migrations/`. The Supabase CLI applies them to a
  linked project with `supabase db push`. This step is **not** triggered by
  a git push — you (or an optional CI job, see below) must run it
  explicitly whenever a migration is added, and it must land *before* you
  deploy code that depends on the new schema.

Keep those two facts straight: pushing code ships the app; it does **not**
touch the database. A feature that adds a column and reads it will 500 in
production if you deploy the code before pushing the migration.

If the user wants actual gate-before-merge CI (tests/lint/security scan
blocking a bad deploy), that's an addition on top of this baseline — see
"Optional: a real CI gate" below. Don't assume it exists unless you're
adding it yourself.

## Repo layout

```
├── main.py                  # FastAPI app — ALL route/business logic lives here
├── api/
│   └── index.py              # Vercel entry-point shim, re-exports `app` from main.py
├── requirements.txt          # pinned dependencies
├── vercel.json                # build target, routing, cron schedule
├── supabase/
│   └── migrations/
│       └── <YYYYMMDDHHMMSS>_<description>.sql
└── test_<app>.py              # pytest, mocks the Supabase client — no live DB in tests
```

Why the split between `main.py` and `api/index.py`: Vercel's Python builder
(`@vercel/python`) discovers the ASGI `app` object via the `api/` directory
convention, but the app's logic should live at the repo root as an ordinary
importable module. `api/index.py` should contain nothing but:

```python
from main import app  # noqa: F401 — re-exported for Vercel
```

Do not duplicate any logic into `api/index.py`. Path-relative code (reading
a static file, computing a project root from `__file__`, etc.) that lives
in `api/` resolves relative to the Lambda bundle's `api/` subdirectory, not
the repo root — a classic source of "works locally, 404s/500s in
production" bugs in this stack. One source of truth (`main.py`) sidesteps
it entirely.

## Design input: Claude Design exports

Claude Design (the canvas-based design tool) exports as a **zip file** —
free, instant, no separate login — containing all the artboard files
(HTML/CSS and any assets) for the design. If the user hands you this zip,
treat it as the authoritative visual spec for the frontend — the same way
you'd treat a Figma handoff — not as inspiration to loosely follow:

- Unzip it and read every file inside before writing or restyling any
  template; don't work from a description of the design when the actual
  export is sitting right there.
- Pull the design tokens the export defines — color palette (including
  light/dark pairs if present), font families/weights, corner radii,
  spacing scale — into one shared place, matching this stack's existing
  pattern of one shared CSS block/shell rather than per-page styles.
- Map the export's component structure (cards, nav, buttons, list rows)
  onto the server-rendered templates you're already returning as
  `HTMLResponse` strings. The export is static HTML/CSS, but that's not a
  reason to bolt on a client-side framework or a build step — keep the app
  server-rendered, consistent with everything else in this pipeline. Any
  image/font assets bundled in the zip need a home in this app's static
  assets (e.g. alongside `public/`), not left referencing local zip paths.
- If the zip has multiple artboards for different breakpoints (mobile vs.
  desktop) or different screens, fold breakpoints into the existing
  responsive approach (e.g. one `@media` block) and map each screen to its
  corresponding route, rather than duplicating markup per device.
- If no export has been provided yet but the user references a design,
  ask for the zip before guessing at layout — a described design in words
  is not the same as the actual export, and getting this wrong means
  redoing styling work later.

## First-time setup

### 1. Supabase (database)

1. Create a project at supabase.com (or `supabase projects create` via CLI).
2. Install the Supabase CLI and authenticate: `supabase login`.
3. In the repo: `supabase init` (creates `supabase/config.toml` and the
   `supabase/migrations/` folder if they don't already exist).
4. Link the repo to the hosted project: `supabase link --project-ref <ref>`
   (the ref is in the project's dashboard URL/settings).
5. Write schema as migration files (see "Writing a migration" below) and
   apply them: `supabase db push`.
6. Grab from the dashboard (Project Settings → API): the project URL and
   the **service-role** key. These become `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` — see the env var checklist below for how
   they're used and why the service-role key never reaches the client.

### 2. Vercel (app hosting)

1. Create a project and either import the GitHub repo from the Vercel
   dashboard (Add New → Project → pick the repo) or link an existing
   local checkout with the CLI: `vercel link`.
2. Importing from GitHub is what wires up the CD behavior described above
   — auto-deploy on push to the default branch, preview deployments on
   PRs. If you only ran `vercel link`/`vercel deploy` from the CLI, deploys
   are manual until you also connect the repo in the dashboard's Git
   Integration settings.
3. Set environment variables in the project dashboard (Settings →
   Environment Variables) — see the checklist below for what's needed and
   which Vercel environments (Production / Preview / Development) should
   get each one.
4. For local development against the same env vars: `vercel env pull` to
   write them into a local `.env` file (never commit it — add `.env` to
   `.gitignore` if it isn't already).
5. `vercel.json` at the repo root tells Vercel how to build and route the
   Python app:

```json
{
  "builds": [
    { "src": "main.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "main.py" }
  ]
}
```

Add a `crons` block only if the app needs a scheduled job (see "Cron
endpoints" below) — omit it entirely otherwise, since an empty/unused
cron config is one more thing to keep in sync with reality.

### 3. requirements.txt

Pin exact versions (`==`, not `>=`) for everything the deploy needs —
Vercel builds fresh from `requirements.txt` on every deploy, so an
unpinned dependency can silently change behavior between deploys with no
corresponding code change to point at. At minimum:

```
fastapi==<version>
httpx==<version>
supabase==<version>
pytest==<version>
pytest-asyncio==<version>
anyio==<version>
```

Add whatever else the app needs (a push library, an HTTP client for a
third-party API, etc.) the same pinned way.

## Writing a migration

Name migration files so they sort in application order:
`<YYYYMMDDHHMMSS>_<short_description>.sql`, e.g.
`20260627111000_create_widgets.sql`. The timestamp prefix is the whole
point — Supabase (and any human reading the folder) applies/reads them in
that order, so never renumber or reorder an existing file, only add new
ones after it.

Every table that's reachable through the app's Supabase client needs Row
Level Security enabled, even if the app only ever queries it with the
service-role key (which bypasses RLS) — RLS is what stops the table from
being wide open to anyone who obtains the anon/public key or queries it
directly. A minimal table migration looks like:

```sql
create table if not exists public.widgets (
  id bigint generated always as identity primary key,
  name text not null,
  created_at timestamptz not null default now()
);

alter table public.widgets enable row level security;

-- Adjust the policy to match who should actually be able to read this table.
create policy "widgets are publicly readable"
  on public.widgets for select
  using (true);
```

Forgetting the `enable row level security` line is the single most common
mistake in this stack — a table created without it is readable/writable by
anyone with the anon key, RLS or not. If `supabase db lint` is available,
run it before pushing; it flags tables missing RLS.

Apply with `supabase db push` against the linked project. Do this **before**
merging/deploying application code that depends on the new schema — the
migration and the code that needs it are two separate deploys to two
separate systems, and only you control their order.

## Talking to Supabase from the app

Read credentials from environment variables, not hardcoded config, and
fail loudly (not with a silent `None`) if they're missing:

```python
import os
from supabase import Client, create_client

def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)
```

Call this inside each request handler (not once at import time) and turn
the `RuntimeError` into a 503 response — that way a misconfigured
deployment fails with a clear message instead of an unhandled crash the
first time a route touches the database.

The service-role key bypasses RLS entirely, so it must only ever be read
server-side (a Vercel env var the serverless function reads) — never send
it to the browser, never prefix it with anything client bundlers treat as
public (e.g. `NEXT_PUBLIC_`, `VITE_`), never put it in a migration or log
line.

## Cron endpoints

Vercel Cron just performs an HTTP GET to a route on schedule — the route
itself is ordinary app code, so it needs its own auth check or anyone who
finds the URL can trigger it. The standard pattern: set a `CRON_SECRET`
env var, and Vercel automatically sends it as a bearer token when it
invokes the cron; check it yourself:

```python
from fastapi import Header, HTTPException
import os

@app.get("/api/cron")
async def scheduled_job(authorization: str | None = Header(default=None)) -> dict:
    required_secret = os.getenv("CRON_SECRET")
    if required_secret and authorization != f"Bearer {required_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    ...
```

Register the schedule in `vercel.json`:

```json
{
  "crons": [
    { "path": "/api/cron", "schedule": "0 0 * * *" }
  ]
}
```

`CRON_SECRET` is optional (the route works without it) but strongly
recommended for anything that sends notifications, writes data, or costs
money to run — treat "optional" as "do it unless you have a specific
reason not to."

## Email (Brevo)

If the app needs to send email (welcome messages, digests, alerts — the
same role Vercel Cron plays for push notifications elsewhere in this
stack), use Brevo's transactional email HTTP API rather than SMTP. It's a
plain REST call, so it needs no new dependency beyond `httpx`, which is
already pinned in `requirements.txt`.

### Setup

1. Create a Brevo account at brevo.com.
2. **Verify a sender before writing any code.** Settings → Senders,
   Domains & Dedicated IPs → add the sending domain or address and follow
   the SPF/DKIM (ideally DMARC too) DNS records it gives you to add at
   your domain registrar. Brevo will accept API calls against an
   unverified sender, but delivery silently breaks — mail gets dropped or
   heavily spam-filtered — until verification finishes, so do this first
   rather than debugging "the API call succeeded but nothing arrived"
   later.
3. Generate an API key: Settings → SMTP & API → API Keys → Generate a new
   API key. Treat it exactly like the Supabase service-role key —
   server-side only, never shipped to the client, never logged.
4. Set env vars in Vercel: `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`,
   `BREVO_SENDER_NAME`. Only add it to Preview if Preview deployments
   should actually send real mail — otherwise leave it unset there so the
   app fails closed instead of emailing real users from a test deploy.

### App code

Follow the same fail-loudly-if-unset pattern as `get_supabase_client()`:

```python
import os
import httpx

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def send_email(*, to_email: str, subject: str, html_content: str, to_name: str | None = None) -> None:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    if not api_key or not sender_email:
        raise RuntimeError("BREVO_API_KEY and BREVO_SENDER_EMAIL are required")

    recipient = {"email": to_email, **({"name": to_name} if to_name else {})}
    payload = {
        "sender": {"email": sender_email, "name": os.getenv("BREVO_SENDER_NAME", "")},
        "to": [recipient],
        "subject": subject,
        "htmlContent": html_content,
    }
    response = httpx.post(
        BREVO_API_URL,
        json=payload,
        headers={"api-key": api_key, "content-type": "application/json"},
        timeout=10.0,
    )
    response.raise_for_status()
```

If a cron/batch job sends to many recipients at once, catch and
count/log failures per recipient rather than letting one bad address
raise and abort the whole batch — the same shape as the push-notification
loop this pattern is modeled on.

### Tests

Mock `httpx.post` (or mock `send_email` itself) the same way the Supabase
client is mocked — don't call the real Brevo API from tests. The free
tier is also rate-limited, so a suite that hits it for real will
eventually fail for reasons that have nothing to do with the code change
under test.

## Environment variables — where each one lives

| Variable | Set in | Used by |
|---|---|---|
| `SUPABASE_URL` | Vercel (all environments) | app, to reach the Supabase REST API |
| `SUPABASE_SERVICE_ROLE_KEY` | Vercel (all environments) — **never** the client | app, to query/write with RLS bypassed |
| `CRON_SECRET` | Vercel (Production; Preview if cron is tested there) | app, to authenticate Vercel's cron invocations |
| `BREVO_API_KEY` | Vercel (Production; Preview only if it should send real mail) | app, to send transactional email |
| `BREVO_SENDER_EMAIL` / `BREVO_SENDER_NAME` | Vercel | app, as the `sender` on outgoing email |
| any other provider secret the app needs (payment keys, third-party APIs) | Vercel | app |
| Supabase project ref / access token | GitHub Environment secret (see "Restrict who/what can read the CI secrets" below) — never the app itself | Supabase CLI in CI (`supabase link`, `supabase db push`) |

Don't commit a `.env` file — configure values directly in the Vercel
dashboard, and use `vercel env pull` to sync them locally for development.
Preview deployments can use a separate (e.g. staging) Supabase project by
scoping env vars to the Preview environment in Vercel's dashboard, if the
user wants isolated data for PR previews.

## Testing

Use `pytest` with `starlette.testclient.TestClient` (or `httpx.AsyncClient`
for async tests) against the FastAPI `app`. Mock the Supabase client
(`unittest.mock.patch`/`MagicMock`) rather than hitting a live database —
tests should run offline and not depend on migration state:

```python
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient
from main import app

client = TestClient(app)

@patch("main.get_supabase_client")
def test_something(mock_get_client):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = [...]
    mock_get_client.return_value = mock_client
    response = client.get("/some-route")
    assert response.status_code == 200
```

If the project follows TDD, write/update the test for a behavior change
before touching `main.py` — it's a good discipline in this stack
specifically because Vercel's serverless environment makes a class of bugs
(path resolution, missing env vars, cold-start import errors) easy to miss
locally and only surface once deployed; a test that mocks the client still
catches logic errors before they get anywhere near a deploy.

## Optional: a real CI gate

Everything above ships changes the moment they're pushed — nothing blocks
a broken push from reaching Preview, and nothing blocks a broken migration
from being applied by hand. If the user wants an actual gate (tests must
pass, a security scan must be clean, RLS lint must pass, before the change
is considered mergeable), add a GitHub Actions workflow. This is an
enhancement on top of the baseline pipeline, not something to assume
already exists:

```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest
      - run: pip install bandit
      - run: bandit -r . -x ./tests,./test_*.py
```

A migration-lint/apply job needs a Supabase access token and project ref
as repository secrets (`SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`) —
only add this job if the user actually wants migrations applied by CI
rather than by hand, since it changes who/what has write access to the
production database:

```yaml
  migrations:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
      - run: supabase link --project-ref ${{ secrets.SUPABASE_PROJECT_REF }}
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
      - run: supabase db lint
      - run: supabase db push
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
```

Note this workflow gates PRs and can run migrations on merge to main, but
it does not replace Vercel's Git integration for deploying the app itself
— that keeps working exactly as described above, unless the user
specifically wants to move to Vercel CLI deploys triggered from Actions
instead (a bigger change worth confirming before making).

### Restrict who/what can read the CI secrets

A secret stored as a plain repository secret (Settings → Secrets and
variables → Actions → *Repository secrets*) is readable by **any**
workflow job in the repo, the moment a matching workflow runs, with no
approval step — anyone who can push a branch or open a PR with write
access can add a step like `run: echo ${{ secrets.SUPABASE_ACCESS_TOKEN }}`
and exfiltrate it. For a secret that can push schema to a production
database or send email as your domain (`SUPABASE_ACCESS_TOKEN`,
`SUPABASE_PROJECT_REF`, `BREVO_API_KEY`), that's wider access than it
should have. GitHub **Environments** narrow it to specific people and
specific branches:

1. Repo Settings → Environments → New environment (e.g. `production`).
2. Under **Deployment protection rules**, add **Required reviewers** and
   name the specific people or team who must approve — the job pauses and
   waits for one of them to click Approve before it can run, so a
   compromised or malicious branch can't reach the secret unattended.
3. Under **Deployment branches and tags**, restrict it to `main` (or
   whichever branch is protected) — this also keeps fork PRs and
   PR-triggered runs from ever being eligible, since they never target
   that branch.
4. Add the sensitive values as **environment secrets** on `production`
   (Environments → production → Add secret), not as repository secrets —
   and delete the repository-level copies once they're moved. A value
   that exists in both places is only as protected as its weakest copy.
5. In the workflow, add `environment: production` to the job that needs
   them:

```yaml
  migrations:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: test
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
      - run: supabase link --project-ref ${{ secrets.SUPABASE_PROJECT_REF }}
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
      - run: supabase db lint
      - run: supabase db push
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
```

Only a job that declares `environment: production` can read
`production`'s secrets — the `test` job earlier in the same workflow
file, which runs on every PR including from contributors without deploy
access, still can't see them, even though it's defined right next to it.

This is a second, independent gate on top of ordinary branch protection
(required PR review, no direct pushes to `main`) — branch protection
stops a bad change from merging; the environment's required reviewers
stop that change, even if merged, from silently running with production
credentials without a named person separately signing off on the deploy
step itself.

## Common pitfalls

- **Logic duplicated into `api/index.py`.** Keep it a one-line re-export;
  anything else risks path-resolution bugs that only appear in production.
- **Deploying code before its migration.** The app redeploys on push;
  the database does not. Run `supabase db push` first for any change the
  new code depends on.
- **A table created without RLS.** Every `create table` migration needs an
  `alter table ... enable row level security` and at least one policy
  right next to it, not as a follow-up fix later.
- **Service-role key exposed to the client.** It must only be read from a
  server-side env var, never bundled into frontend code or logged.
- **Unpinned `requirements.txt`.** Vercel installs fresh on every deploy;
  an unpinned version can change behavior with no matching code diff to
  explain it.
- **Assuming there's a CI gate.** Unless one was explicitly added (see
  above), nothing stops a broken push from reaching Preview or a bad
  migration from being applied by hand — say so rather than assuming
  quality gates exist just because the project has tests in the repo.
- **Brevo sender not verified.** The API call succeeds either way, so a
  missing/incomplete SPF-DKIM verification looks like a silent failure —
  mail just never arrives. Verify the sender before wiring up `send_email`
  and troubleshooting anything else.
- **CI secrets left at repository scope.** If `SUPABASE_ACCESS_TOKEN`,
  `SUPABASE_PROJECT_REF`, or `BREVO_API_KEY` live under repository (or
  org-wide) secrets instead of an Environment with required reviewers,
  any workflow run — including one added by a compromised or malicious
  PR from anyone with write access — can read them with no approval step.
- **Styling from memory instead of the actual Claude Design export.**
  Guessing at colors/spacing instead of unzipping and reading the export
  means redoing the work once the real files are checked.
