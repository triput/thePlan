"""Fernet helpers for OAuth token columns (`*_token_enc`)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.api.errors import ApiError
from app.config import Settings


def _fernet(settings: Settings) -> Fernet:
    key = (settings.token_encryption_key or "").strip()
    if not key:
        raise ApiError(
            503,
            "TOKEN_ENCRYPTION_KEY is not configured",
            "CALENDAR_CRYPTO_NOT_CONFIGURED",
        )
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001 — invalid key format
        raise ApiError(
            503,
            "TOKEN_ENCRYPTION_KEY is invalid (expect Fernet url-safe base64 key)",
            "CALENDAR_CRYPTO_INVALID_KEY",
        ) from exc


def encrypt_token(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(settings: Settings, ciphertext: str) -> str:
    try:
        return _fernet(settings).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ApiError(500, "Stored calendar token could not be decrypted", "CALENDAR_TOKEN_DECRYPT") from exc
