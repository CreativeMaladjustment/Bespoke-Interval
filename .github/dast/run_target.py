"""Launches the FastAPI app as a live HTTP target for the OWASP ZAP DAST scan.

The app normally talks to a hosted Supabase project (see db.py) — there's no
local Postgres connection to point it at in CI. Rather than scan an app that
500s on every page (which would only exercise the "no database" error path),
this reuses the exact in-memory fixture double already proven out by the unit
tests (test_main.FakeClient) so ZAP gets fully-rendered pages, forms, and the
authenticated area to actually crawl and attack.

Dummy secrets below are scan-local only, never used outside this throwaway
process.
"""

import os
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "https://dast-scan.invalid")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dast-scan-key")
os.environ.setdefault("SESSION_SECRET", "dast-scan-session-secret")
os.environ.setdefault("PASSWORD", "dast-scan-password")

import uvicorn  # noqa: E402  (must follow the env defaults above)

from test_main import FakeClient  # noqa: E402

with patch("main.get_supabase_client", return_value=FakeClient()):
    import main  # noqa: E402  (import after the patch is active)

    uvicorn.run(main.app, host="0.0.0.0", port=8000)
