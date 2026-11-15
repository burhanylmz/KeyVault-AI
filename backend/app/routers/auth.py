"""
FAZ 4: Kimlik Doğrulama ve JWT Oturum Uç Noktaları (routers/auth.py)
- POST /api/auth/register
- POST /api/auth/login
- get_current_user JWT Dependency
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security import (
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Bearer JWT token doğrulaması yaparak aktif kullanıcıyı döndürür."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum belirteci (Bearer Token) bulunamadı.",
        )
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        email = payload.get("sub")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Geçersiz veya süresi dolmuş JWT token: {exc}",
        ) from exc

    user = None
    if user_id is not None:
        user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None and email:
        user = db.query(User).filter(User.email == str(email)).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )
    return user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user( payload: UserRegisterRequest, db: Session = Depends(get_db) ) -> TokenResponse:
    """Yeni kullanıcı kaydı oluşturur (Bcrypt parola hash'leme) ve JWT döndürür."""
    normalized_email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi ile kayıtlı bir kullanıcı zaten mevcut.",
        )

    new_user = User(
        email=normalized_email,
        full_name=payload.full_name or "KeyVault Kullanicisi",
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": new_user.email, "user_id": new_user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Kullanıcı girişini Bcrypt ile doğrular ve JWT Access Token üretir."""
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya parola hatalı.",
        )

    token = create_access_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
