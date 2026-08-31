"""Logs into the locally-running DAST target and prints the session cookie.

Most of this app's attack surface (day view, agenda, ticket/flight CRUD
forms) sits behind the single shared-password login. A baseline ZAP scan
that only ever sees "/" and "/login" would miss nearly everything, so the
workflow captures a valid session cookie here and hands it to ZAP's request
replacer so the crawl/attack runs authenticated.

Uses httpx, which is already a project dependency (requirements.txt).
"""

import sys

import httpx

from test_main import JD_ID

resp = httpx.post(
    "http://localhost:8000/login",
    data={"traveler_id": JD_ID, "password": "dast-scan-password"},
    follow_redirects=False,
    timeout=10.0,  # fail fast instead of hanging the workflow if the target never responds
)

cookie = resp.cookies.get("bespoke_session")
if not cookie:
    print(f"Login failed (status={resp.status_code}); no session cookie set", file=sys.stderr)
    sys.exit(1)

print(cookie)
