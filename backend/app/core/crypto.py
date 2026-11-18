from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SENSITIVE_KEY_TOKENS = (
    "secret",
    "password",
    "api_key",
    "token",
    "totp",
    "private_key",
    "authorization",
)


class SecretVault:
    """Encrypts and decrypts secrets at rest using AES-256-GCM."""

    _PREFIX = "v1:"
    _NONCE_LEN = 12

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256-GCM key must be exactly 32 bytes")
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt UTF-8 plaintext and return versioned base64 token."""
        nonce = os.urandom(self._NONCE_LEN)
        ciphertext = self._aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{self._PREFIX}{encoded}"

    def decrypt(self, token: str) -> str:
        """Decrypt and authenticate a versioned AES-256-GCM token."""
        if not isinstance(token, str) or not token.startswith(self._PREFIX):
            raise ValueError("Invalid or tampered ciphertext")
        try:
            payload = base64.urlsafe_b64decode(token[len(self._PREFIX):].encode("ascii"))
            if len(payload) <= self._NONCE_LEN:
                raise ValueError("Invalid or tampered ciphertext")
            nonce = payload[: self._NONCE_LEN]
            ciphertext = payload[self._NONCE_LEN :]
            plaintext = self._aes.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception as exc:
            raise ValueError("Invalid or tampered ciphertext") from exc


def mask_secret(value: str) -> str:
    """Mask a secret so only a brief prefix/suffix is shown when sufficiently long."""
    if not value:
        return ""
    if len(value) >= 10:
        return f"{value[:4]}...{value[-4:]}"
    return "••••••••"


def redact_secrets(payload: Any) -> Any:
    """Recursively copy structures and replace sensitive field values with '[REDACTED]'."""
    if isinstance(payload, dict):
        redacted: dict[Any, Any] = {}
        for key, val in payload.items():
            key_lower = str(key).lower()
            if any(tok in key_lower for tok in _SENSITIVE_KEY_TOKENS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(val)
        return redacted
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_secrets(item) for item in payload)
    return payload
