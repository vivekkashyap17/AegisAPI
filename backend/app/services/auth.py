from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from app.core.config import settings, get_private_key, get_public_key


def hash_password(password: str) -> str:
    # bcrypt caps at 72 bytes — slice AFTER encoding so multi-byte chars don't overflow
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, get_private_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, get_private_key(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, get_public_key(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    # Reject tokens whose type doesn't match (e.g. a refresh token used as an access token)
    if expected_type is not None and payload.get("type") != expected_type:
        return None
    return payload