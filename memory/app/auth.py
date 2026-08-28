"""Password hashing and JWT helpers for the auth endpoints.

Tokens are HS256 JWTs signed with the shared ``JWT_SECRET`` so the
orchestrator can verify them without calling back into this service.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional
import os

import bcrypt
import jwt
from fastapi import HTTPException

DEFAULT_JWT_SECRET = "shopping-ai-dev-secret"
TOKEN_TTL_SECONDS = 7 * 24 * 3600


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=TOKEN_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def user_id_from_token(token: str) -> int:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")


def user_id_from_authorization(authorization: Optional[str]) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return user_id_from_token(authorization.split(" ", 1)[1].strip())
