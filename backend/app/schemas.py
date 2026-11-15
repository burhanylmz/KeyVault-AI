"""
Pydantic Veri Doğrulama Şemaları (schemas.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = Field(default="KeyVault Kullanicisi", max_length=255)


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class KeyVaultItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key_name: str
    profile_type: str
    mode: str
    bitting_code: Optional[str] = None
    raw_depths_mm: List[float]
    valley_positions_mm: List[float]
    macs_valid: bool
    macs_state: str
    scale_factor_k: float
    vector_drawing_b64: Optional[str] = None
    created_at: datetime
