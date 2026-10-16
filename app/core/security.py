import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "workergrid-production-secret-key-32-bytes-long!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Symmetric Encryption Key for sensitive tokens (Fernet requiring 32 url-safe base64 bytes)
_raw_encryption_key = os.getenv("ENCRYPTION_KEY")
if not _raw_encryption_key:
    # Deterministic fallback key for dev environment based on SECRET_KEY
    import base64
    import hashlib
    key_bytes = hashlib.sha256(SECRET_KEY.encode()).digest()
    _raw_encryption_key = base64.urlsafe_b64encode(key_bytes).decode()

fernet = Fernet(_raw_encryption_key.encode())

import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")



def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta if expires_delta else timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def encrypt_token(plain_token: str) -> str:
    if not plain_token:
        return ""
    return fernet.encrypt(plain_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    try:
        return fernet.decrypt(encrypted_token.encode()).decode()
    except Exception:
        raise ValueError("Failed to decrypt token")


def create_oauth_state(user_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=10)
    data = {
        "exp": expire,
        "iat": now,
        "type": "oauth_state",
        "user_id": user_id,
        "nonce": os.urandom(8).hex(),
    }
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def verify_oauth_state(state_token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(state_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "oauth_state":
            raise ValueError("Invalid OAuth state type")
        return payload
    except Exception as err:
        raise ValueError(f"Invalid OAuth state parameter: {err}")
