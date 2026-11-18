from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def generate_totp_secret() -> str:
    """Generate a random 160-bit Base32 secret for RFC 6238 TOTP."""
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def build_totp_uri(
    secret: str,
    account_name: str,
    issuer: str = "APEX AI Trading Lab",
) -> str:
    """Build an otpauth:// URI compatible with authenticator apps."""
    label = f"{quote(issuer)}:{quote(account_name)}"
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


def _decode_b32(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padded = normalized + "=" * (-len(normalized) % 8)
    return base64.b32decode(padded.encode("ascii"), casefold=True)


def generate_totp_code(
    secret: str,
    for_time: int | None = None,
    period: int = 30,
    digits: int = 6,
) -> str:
    """Compute an RFC 6238 TOTP code for the given Unix timestamp."""
    ts = int(time.time()) if for_time is None else int(for_time)
    counter = ts // period
    key = _decode_b32(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    otp = binary % (10**digits)
    return str(otp).zfill(digits)


def verify_totp_code(
    secret: str,
    code: str,
    for_time: int | None = None,
    window: int = 1,
    period: int = 30,
    digits: int = 6,
) -> bool:
    """Verify a TOTP code within +-window time steps using constant-time comparison."""
    cleaned = (code or "").strip()
    if len(cleaned) != digits or not cleaned.isdigit():
        return False

    ts = int(time.time()) if for_time is None else int(for_time)
    for step_offset in range(-window, window + 1):
        candidate = generate_totp_code(
            secret,
            for_time=ts + (step_offset * period),
            period=period,
            digits=digits,
        )
        if hmac.compare_digest(candidate, cleaned):
            return True
    return False


def hash_session_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a session token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_session_token() -> tuple[str, str]:
    """Generate a cryptographically secure session token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_session_token(raw_token)
