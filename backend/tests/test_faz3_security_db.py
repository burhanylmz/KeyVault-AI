"""
FAZ 3 Birim Testleri (tests/test_faz3_security_db.py)
- Test veritabanında (SQLite In-Memory ORM) bir kullanıcı oluşturma, parolasının düz metin olmadığını ve Bcrypt ile doğrulandığını test etme.
- 3-1-4-2-5 bitting kodunu ve milimetrik derinlikleri AES-256 ile şifreleyip DB'ye kaydetme, DB'deki ham sütunun '3-1-4-2-5' içermediğini, ancak decrypt_data çağrıldığında birebir '3-1-4-2-5' olarak geri çözüldüğünü doğrulama.
- JWT üretme ve doğrulama fonksiyonlarını test etme.
"""

import json
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base
from app.models import KeyVault, User
from app.security import (
    create_access_token,
    decrypt_data,
    encrypt_data,
    hash_password,
    verify_access_token,
    verify_password,
)


@pytest.fixture()
def db_session():
    """Her test için izole SQLite In-Memory ORM oturumu."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_faz3_user_bcrypt_and_aes256_vault_orm(db_session):
    """
    1. Kullanıcı oluştur ve Bcrypt parola hash/doğrulama kontrolü yap.
    2. 3-1-4-2-5 bitting kodunu AES-256 ile şifreleyip KeyVault tablosuna kaydet.
    3. Ham sütunun '3-1-4-2-5' içermediğini, decrypt_data ile birebir '3-1-4-2-5' çözüldüğünü doğrula.
    """
    plain_pass = "GucluSifre!2026"
    hashed_pass = hash_password(plain_pass)

    # Parola düz metin olmamalı ve Bcrypt formatında ($2b$) olmalı
    assert hashed_pass != plain_pass
    assert hashed_pass.startswith("$2b$") or hashed_pass.startswith("$2a$")
    assert verify_password(plain_pass, hashed_pass) is True
    assert verify_password("YanlisSifre", hashed_pass) is False

    # ORM ile kullanıcı kaydı
    user = User(email="muhendis@keyvault.ai", full_name="Test Muhendisi", password_hash=hashed_pass)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.id is not None

    # 3-1-4-2-5 bitting ve derinliklerin AES-256 ile şifrelenmesi
    original_bitting = "3-1-4-2-5"
    original_depths = [1.50, 0.50, 2.00, 1.00, 2.50]

    cipher_bitting = encrypt_data(original_bitting)
    cipher_depths = encrypt_data(json.dumps(original_depths))

    assert cipher_bitting != original_bitting
    assert "3-1-4-2-5" not in cipher_bitting

    vault_item = KeyVault(
        user_id=user.id,
        key_name="Merkez Ofis Kapi",
        profile_type="YALE-5",
        mode="STANDARD",
        encrypted_bitting=cipher_bitting,
        encrypted_depths=cipher_depths,
        macs_valid=True,
        macs_state="q_5",
        scale_factor_k=0.10,
    )
    db_session.add(vault_item)
    db_session.commit()
    db_session.refresh(vault_item)

    # 1-to-Many ORM ilişkisi ve DB ham sütun kontrolü
    assert len(user.keys) == 1
    stored_key = db_session.query(KeyVault).filter_by(id=vault_item.id).first()
    assert stored_key is not None
    assert "3-1-4-2-5" not in stored_key.encrypted_bitting
    assert "1.5" not in stored_key.encrypted_depths

    # decrypt_data ile birebir geri çözme kontrolü
    decrypted_bitting = decrypt_data(stored_key.encrypted_bitting)
    decrypted_depths = json.loads(decrypt_data(stored_key.encrypted_depths))

    assert decrypted_bitting == "3-1-4-2-5"
    assert decrypted_depths == original_depths


def test_faz3_jwt_token_lifecycle():
    """JWT oluşturma ve doğrulama testi."""
    token = create_access_token({"sub": "muhendis@keyvault.ai", "user_id": 42})
    payload = verify_access_token(token)
    assert payload["sub"] == "muhendis@keyvault.ai"
    assert payload["user_id"] == 42
