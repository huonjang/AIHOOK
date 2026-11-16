"""Small owner-only account sessions for the AIHOOK MVP.

Cookie sessions are opaque random tokens; only their SHA-256 hashes are stored.
Never use a client-supplied business_id as an authorization boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession

COOKIE = "aihook_session"
SESSION_SECONDS = 7 * 24 * 60 * 60


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        method, n, r, p, salt_hex, digest_hex = encoded.split('$')
        if method != 'scrypt' or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_login_session(db: Session, response: Response, user: User) -> None:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=_token_hash(token), user_id=user.id, expires_at=_now() + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=SESSION_SECONDS, path='/api', httponly=True,
        secure=os.getenv('AIHOOK_COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'},
        samesite='lax',
    )


def clear_login_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        session = db.get(UserSession, _token_hash(token))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE, path='/api', samesite='lax')


def _allowed_origin(request: Request) -> None:
    """Reject browser cross-origin state-changing calls not explicitly approved.

    Vite proxies /api from :5173 and therefore sends an Origin of :5173.
    The default list is local development only; set AIHOOK_ALLOWED_ORIGINS in deployment.
    """
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return
    origin = request.headers.get('origin')
    if origin is None:
        return  # CLI / server-to-server calls without browser Origin
    allowed = {
        'http://localhost:5173', 'http://127.0.0.1:5173',
        'http://localhost:8000', 'http://127.0.0.1:8000',
    }
    allowed.update(x.strip() for x in os.getenv('AIHOOK_ALLOWED_ORIGINS', '').split(',') if x.strip())
    if origin not in allowed:
        raise HTTPException(status_code=403, detail='Nguồn yêu cầu không được cho phép.')


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    _allowed_origin(request)
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 200:
        raise HTTPException(status_code=401, detail='Vui lòng đăng nhập.')
    item = db.get(UserSession, _token_hash(token))
    if not item or item.expires_at <= _now():
        raise HTTPException(status_code=401, detail='Phiên đăng nhập đã hết hạn.')
    user = db.get(User, item.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail='Tài khoản không tồn tại.')
    return user


def current_business_id(user: User = Depends(current_user)) -> int:
    return user.business_id
