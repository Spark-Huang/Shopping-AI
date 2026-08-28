"""JWT verification for orchestrator endpoints.

Tokens are minted by the memory service's /auth endpoints using the shared
``JWT_SECRET``; this module verifies them locally (no memory round trip).
"""

from typing import Optional
import os

import jwt
from fastapi import HTTPException

DEFAULT_JWT_SECRET = "shopping-ai-dev-secret"


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)


def user_id_from_authorization(authorization: Optional[str]) -> int:
    """Extract the user id from a ``Bearer <jwt>`` Authorization header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")


def require_user(user_id: int, authorization: Optional[str]) -> None:
    """401 without a valid token; 403 when the token belongs to another user."""
    token_user_id = user_id_from_authorization(authorization)
    if token_user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Token does not grant access to this user",
        )
