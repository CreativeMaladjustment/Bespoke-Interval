"""Session cookies and PIN verification.

This app has no user accounts — it's a private, two-traveler trip planner.
"Auth" is a single shared PIN for the trip plus picking which traveler you
are; a successful check issues a signed, httponly cookie naming the trip and
traveler. The cookie is signed (not encrypted) with itsdangerous, so it can't
be forged without SESSION_SECRET, but its contents (trip id, traveler id)
aren't sensitive enough to need encryption.
"""

import os
from dataclasses import dataclass

import bcrypt
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "bespoke_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET is required")
    return URLSafeTimedSerializer(secret, salt="bespoke-interval-session")


@dataclass
class Session:
    trip_id: str
    traveler_id: str
    traveler_name: str


def sign_session(trip_id: str, traveler_id: str, traveler_name: str) -> str:
    return _serializer().dumps(
        {"trip_id": trip_id, "traveler_id": traveler_id, "traveler_name": traveler_name}
    )


def read_session(request: Request) -> Session | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return Session(
        trip_id=data["trip_id"],
        traveler_id=data["traveler_id"],
        traveler_name=data["traveler_name"],
    )


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
