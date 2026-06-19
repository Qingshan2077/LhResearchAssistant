"""Encryption helpers for locally persisted secrets."""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from app.config import settings

_FERNET_PREFIX = "gAAAAA"


def _key_path() -> Path:
    return Path(settings.data_dir) / ".key"


def _create_key(path: Path) -> bytes:
    """Create the key with restrictive permissions and handle first-run races."""
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes().strip()
    with os.fdopen(descriptor, "wb") as key_file:
        key_file.write(key)
    try:
        path.chmod(0o600)
    except OSError:
        logger.warning("Could not restrict encryption-key permissions: {}", path)
    return key


def _get_cipher() -> Fernet:
    path = _key_path()
    key = path.read_bytes().strip() if path.exists() else _create_key(path)
    return Fernet(key)


def is_encrypted(value: str) -> bool:
    return bool(value and value.startswith(_FERNET_PREFIX))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext while avoiding accidental double encryption."""
    if not plaintext or is_encrypted(plaintext):
        return plaintext or ""
    return _get_cipher().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt Fernet data and transparently accept legacy plaintext values."""
    if not ciphertext or not is_encrypted(ciphertext):
        return ciphertext or ""
    try:
        return _get_cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, OSError) as exc:
        logger.error("Could not decrypt a locally stored secret: {}", exc)
        return ""


def encrypt_api_key(plaintext: str) -> str:
    return encrypt_secret(plaintext)


def decrypt_api_key(ciphertext: str) -> str:
    return decrypt_secret(ciphertext)
