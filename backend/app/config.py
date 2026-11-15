"""
KeyVault-AI Uygulama Yapılandırması (config.py)
- AES-256 (32-byte / 256-bit anahtar) ve JWT ayarları.
- SQLite veritabanı bağlantı adresi.
"""

from __future__ import annotations

import hashlib
import os

DATABASE_URL: str = os.getenv("KEYVAULT_DATABASE_URL", "sqlite:///./keyvault.db")

# AES-256 için tam 32-byte (256-bit) Master Key
_RAW_AES_SECRET: str = os.getenv(
    "KEYVAULT_AES256_SECRET",
    "KeyVaultAI-2026-UltraSecure-AES256-MasterKey-32Bytes!",
)
AES_256_KEY: bytes = hashlib.sha256(_RAW_AES_SECRET.encode("utf-8")).digest()  # Tam 32 byte (256-bit)

# JWT Ayarları
JWT_SECRET_KEY: str = os.getenv(
    "KEYVAULT_JWT_SECRET",
    "KeyVaultAI-JWT-HS256-Signing-Secret-Key-2026-Autonomous",
)
JWT_ALGORITHM: str = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
