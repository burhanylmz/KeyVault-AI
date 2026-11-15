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


class KeyPreviewResponse(BaseModel):
    key_name: str
    profile_type: str
    detected_brand: Optional[str] = None
    mode: str
    bitting_code: Optional[str] = None
    raw_depths_mm: List[float]
    valley_positions_mm: List[float]
    remaining_heights_mm: List[float] = Field(default_factory=list)
    pitch_values_mm: List[float] = Field(default_factory=list)
    total_length_mm: float = 0.0
    bow_height_mm: float = 0.0
    blade_length_mm: float = 0.0
    blade_width_mm: float = 0.0
    macs_valid: bool
    macs_state: str
    scale_factor_k: float
    card_pixel_width: float
    vector_drawing_b64: Optional[str] = None
    annotated_photo_b64: Optional[str] = None


class KeyConfirmSaveRequest(BaseModel):
    key_name: str = Field(..., min_length=1, max_length=255)
    profile_type: str = Field(default="STANDART-5P", max_length=100)
    mode: str = Field(default="STANDARD", max_length=50)
    bitting_code: Optional[str] = None
    raw_depths_mm: List[float]
    valley_positions_mm: List[float]
    macs_valid: bool = True
    macs_state: str = "q_accept"
    scale_factor_k: float = 0.1
    vector_drawing_b64: Optional[str] = None
