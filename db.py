"""Supabase client wiring.

Credentials come from environment variables, never hardcoded config, and a
missing value fails loudly rather than silently producing a client that will
error on first use.
"""

import os

from supabase import Client, create_client


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)


def get_trip_slug() -> str:
    return os.getenv("TRIP_SLUG", "london-october")
