"""One-time migration of plaintext provider API keys to Fernet ciphertext."""

import sys
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.database.sqlite import LLMProvider
from app.services.crypto import encrypt_api_key, is_encrypted


def migrate_existing_keys() -> int:
    db = SessionLocal()
    try:
        records = db.query(LLMProvider).all()
        count = 0
        for record in records:
            if record.api_key and not is_encrypted(record.api_key):
                record.api_key = encrypt_api_key(record.api_key)
                count += 1
        db.commit()
        logger.info("Migrated {} API keys", count)
        return count
    except Exception:
        db.rollback()
        logger.exception("API key migration failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_existing_keys()
