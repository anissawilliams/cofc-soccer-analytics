"""Minimal server-side staff access tokens with no database dependency."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import Header, HTTPException


TOKEN_VERSION = "v1"
DEFAULT_TTL_SECONDS = 12 * 60 * 60


class StaffAuthNotConfigured(RuntimeError):
    pass


def _passcode() -> str:
    value = os.getenv("COFC_STAFF_PASSCODE", "")
    if not value:
        raise StaffAuthNotConfigured("COFC_STAFF_PASSCODE is not configured")
    return value


def token_ttl_seconds() -> int:
    return int(os.getenv("COFC_STAFF_TOKEN_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))


def authenticate_staff(passcode: str, *, now: Optional[int] = None) -> Optional[str]:
    expected = _passcode()
    if not hmac.compare_digest(passcode.encode("utf-8"), expected.encode("utf-8")):
        return None
    issued_at = int(time.time() if now is None else now)
    payload = f"{TOKEN_VERSION}.{issued_at}"
    signature = hmac.new(expected.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_staff_token(token: str, *, now: Optional[int] = None) -> bool:
    try:
        version, issued_text, supplied_signature = token.split(".", 2)
        issued_at = int(issued_text)
        current_time = int(time.time() if now is None else now)
        if version != TOKEN_VERSION or issued_at > current_time + 60:
            return False
        if current_time - issued_at > token_ttl_seconds():
            return False
        payload = f"{version}.{issued_at}"
        expected_signature = hmac.new(
            _passcode().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(supplied_signature, expected_signature)
    except (AttributeError, StaffAuthNotConfigured, TypeError, ValueError):
        return False


def require_staff(authorization: Optional[str] = Header(default=None)) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not verify_staff_token(token):
        raise HTTPException(status_code=401, detail="Valid staff access required")
