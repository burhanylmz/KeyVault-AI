"""
FAZ 3: İlişkisel (1-to-Many) SQLAlchemy ORM Modelleri (models.py)
- User ve KeyVault tabloları (Ham SQL kullanmadan ORM mimarisi).
- Anahtar verileri (bitting ve milimetrik derinlikler) yalnızca AES-256 şifreli sütunlarda saklanır.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True, default="KeyVault Kullanicisi")
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # 1-to-Many İlişki: Bir kullanıcının birden fazla anahtarı olabilir
    keys = relationship(
        "KeyVault",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class KeyVault(Base):
    __tablename__ = "key_vaults"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_name = Column(String(255), nullable=False)
    profile_type = Column(String(100), nullable=False, default="YALE-5")
    mode = Column(String(50), nullable=False, default="STANDARD")

    # AES-256 ile şifrelenmiş hassas anahtar verileri (Plain-text ASLA tutulmaz)
    encrypted_bitting = Column(Text, nullable=False)
    encrypted_depths = Column(Text, nullable=False)
    encrypted_positions = Column(Text, nullable=True)

    macs_valid = Column(Boolean, nullable=False, default=True)
    macs_state = Column(String(50), nullable=False, default="q_accept")
    scale_factor_k = Column(Float, nullable=False, default=0.1)

    # Gerçek fotoğraf yerine kasada gösterilen güvenli 2D vektör çizimi (Base64 PNG)
    vector_drawing_b64 = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    owner = relationship("User", back_populates="keys")
