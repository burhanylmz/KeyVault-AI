"""
FAZ 3: Çift Katmanlı Kriptografi ve Oturum Güvenliği (security.py)
- Bcrypt (passlib/bcrypt) ile kullanıcı parolalarının tek yönlü hash'lenmesi ve doğrulanması.
- AES-256 (cryptography AESGCM - 256-bit / 32-byte key) ile anahtar bitting ve derinlik verilerinin çift yönlü şifrelenmesi.
- PyJWT ile oturum yönetimi (JWT oluşturma ve doğrulama).
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext

from app.config import (
    AES_256_KEY,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Kullanıcı şifresini Bcrypt ile tek yönlü olarak hash'ler."""
    if not plain_password:
        raise ValueError("Parola boş olamaz.")
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Düz metin şifreyi Bcrypt hash'i ile doğrular."""
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def encrypt_data(plain_text: str) -> str:
    """
    Metin verisini (bitting kodu veya JSON milimetrik derinlik dizisi)
    32-byte (256-bit) anahtarlı AES-256-GCM ile çift yönlü şifreler.
    Çıktı formatı: Base64(12_byte_nonce + ciphertext_with_tag).
    """
    if plain_text is None:
        raise ValueError("Şifrelenecek veri None olamaz.")
    if len(AES_256_KEY) != 32:
        raise RuntimeError("AES-256 anahtarı tam 32 byte (256 bit) olmalıdır.")

    aesgcm = AESGCM(AES_256_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
    combined = nonce + ciphertext
    return base64.urlsafe_b64encode(combined).decode("ascii")


def decrypt_data(cipher_text: str) -> str:
    """
    encrypt_data ile AES-256-GCM kullanılarak şifrelenmiş Base64 veriyi
    orijinal düz metnine (plain-text) geri çözer.
    """
    if not cipher_text:
        raise ValueError("Çözülecek şifreli veri boş olamaz.")
    if len(AES_256_KEY) != 32:
        raise RuntimeError("AES-256 anahtarı tam 32 byte (256 bit) olmalıdır.")

    raw = base64.urlsafe_b64decode(cipher_text.encode("ascii"))
    if len(raw) < 28:
        raise ValueError("Geçersiz veya bozuk AES-256 şifreli veri bloğu.")

    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(AES_256_KEY)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Kullanıcı oturumu için imzalı JWT erişim belirteci (Access Token) üretir."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    """JWT erişim belirtecini doğrular ve payload sözlüğünü döndürür."""
    if not token:
        raise ValueError("JWT token boş olamaz.")
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    return dict(payload)
