"""Google OAuth ID-token verification for FastAPI."""

from __future__ import annotations

import os
import logging
from typing import Any

from fastapi import Depends, HTTPException, Request
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from investigation_logger.logger import get_user, upsert_user

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

_google_transport = google_requests.Request()


def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency — verify Google ID token and return user info including role."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ", 1)[1]
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

    try:
        idinfo = id_token.verify_oauth2_token(token, _google_transport, GOOGLE_CLIENT_ID)
    except ValueError as exc:
        logger.warning("Invalid Google ID token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    # Check if user already exists to preserve their role
    existing = get_user(user_id)
    role = existing.get("role", "candidate") if existing else None

    upsert_user(user_id, email, name, picture, role=role)

    # Re-fetch to get the definitive role from DB
    if not existing:
        existing = get_user(user_id)
    final_role = existing.get("role", "candidate") if existing else "candidate"

    return {"user_id": user_id, "email": email, "name": name, "picture": picture, "role": final_role}


def require_role(role: str):
    """FastAPI dependency factory — restrict endpoint to users with a specific role."""
    def dependency(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user.get("role") != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
