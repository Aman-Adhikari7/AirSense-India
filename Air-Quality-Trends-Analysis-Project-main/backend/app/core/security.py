"""Password hashing, JWT handling and the auth dependencies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, Request, Response
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Used to burn the same CPU time when a login email does not exist (avoids user enumeration by timing).
_DUMMY_HASH = pwd_context.hash("not-a-real-password")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    """Constant-ish time check. Pass hashed=None for unknown users."""
    return pwd_context.verify(plain, hashed or _DUMMY_HASH) and hashed is not None


def create_access_token(payload: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    to_encode = payload.copy()
    minutes = expires_minutes if expires_minutes is not None else settings.JWT_EXPIRES_MIN
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except InvalidTokenError:
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        max_age=settings.JWT_EXPIRES_MIN * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def get_auth_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return {'id', 'email'} from a Bearer token or the auth cookie, else None."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    return {"id": payload.get("sub"), "email": payload.get("email")}


def require_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: 401 unless the request carries a valid token."""
    user = get_auth_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
