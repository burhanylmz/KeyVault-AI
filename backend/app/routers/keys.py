"""
FAZ 4: Anahtar Analizi, Dijital Kasa ve CNC G-Code / PDF Dışa Aktarım Uç Noktaları (routers/keys.py)
- POST /api/keys/scan-and-save (In-Memory analiz, RAM sıfırlama, AES-256 kayıt, 2D vektör çizim döndürme)
- GET  /api/keys/my-vault (JWT korumalı kasa listesi)
- GET  /api/keys/{key_id}/export-gcode (CNC .gcode indirme)
- GET  /api/keys/{key_id}/export-pdf (ReportLab PDF Kesim Kartı indirme)
"""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.compiler_dfa import GCodeCompiler, MACS_DFA
from app.database import get_db
from app.models import KeyVault, User
from app.report_generator import generate_2d_key_vector_base64, generate_cutting_card_pdf
from app.routers.auth import get_current_user
from app.schemas import KeyVaultItemResponse
from app.security import decrypt_data, encrypt_data
from app.vision_pipeline import DimpleKeyHardwareError, analyze_key_image

router = APIRouter(prefix="/api/keys", tags=["KeyVault"])


def _deserialize_vault_item(item: KeyVault) -> KeyVaultItemResponse:
    """Veritabanındaki AES-256 şifreli KeyVault kaydını çözerek yanıt şemasına dönüştürür."""
    decrypted_bitting_raw = decrypt_data(item.encrypted_bitting)
    bitting_code: Optional[str] = (
        None if decrypted_bitting_raw == "RAW_MODE" else decrypted_bitting_raw
    )
    raw_depths_mm: List[float] = json.loads(decrypt_data(item.encrypted_depths))
    valley_positions_mm: List[float] = (
        json.loads(decrypt_data(item.encrypted_positions))
        if item.encrypted_positions
        else [round(4.0 + i * 4.5, 2) for i in range(len(raw_depths_mm))]
    )
    return KeyVaultItemResponse(
        id=item.id,
        key_name=item.key_name,
        profile_type=item.profile_type,
        mode=item.mode,
        bitting_code=bitting_code,
        raw_depths_mm=raw_depths_mm,
        valley_positions_mm=valley_positions_mm,
        macs_valid=item.macs_valid,
        macs_state=item.macs_state,
        scale_factor_k=item.scale_factor_k,
        vector_drawing_b64=item.vector_drawing_b64,
        created_at=item.created_at,
    )


@router.post("/scan-and-save", response_model=KeyVaultItemResponse, status_code=status.HTTP_201_CREATED)
async def scan_and_save_key(
    file: UploadFile = File(...),
    key_name: str = Form("Ana Giris Anahtari"),
    profile_type: str = Form("YALE-5"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KeyVaultItemResponse:
    """
    Yüklenen anahtar fotoğrafını diske kaydetmeden RAM'de analiz eder,
    finally bloğunda pikselleri sıfırlar, bitting ve derinlikleri AES-256 ile
    şifreleyerek veritabanına kaydeder ve 2D güvenli vektör çizimini döndürür.
    """
    raw_bytes = await file.read()
    try:
        analysis = analyze_key_image(raw_bytes=raw_bytes, profile_type=profile_type)
    except DimpleKeyHardwareError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        del raw_bytes

    mode: str = analysis["mode"]
    bitting_code: Optional[str] = analysis["bitting_code"]
    raw_depths_mm: List[float] = analysis["raw_depths_mm"]
    valley_positions_mm: List[float] = analysis["valley_positions_mm"]
    scale_k: float = analysis["scale_factor_k"]

    dfa = MACS_DFA()
    if bitting_code:
        macs_valid = dfa.validate(bitting_code)
        macs_state = dfa.current_state
        if not macs_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"MACS DFA Üretim Reddi ({macs_state}): {dfa.violation_detail}",
            )
    else:
        macs_valid = dfa.validate_raw_depths(raw_depths_mm)
        macs_state = dfa.current_state

    vector_b64 = generate_2d_key_vector_base64(
        raw_depths_mm=raw_depths_mm,
        bitting_code=bitting_code,
        profile_type=profile_type,
        valley_positions_mm=valley_positions_mm,
    )

    encrypted_bitting = encrypt_data(bitting_code if bitting_code else "RAW_MODE")
    encrypted_depths = encrypt_data(json.dumps(raw_depths_mm))
    encrypted_positions = encrypt_data(json.dumps(valley_positions_mm))

    vault_record = KeyVault(
        user_id=current_user.id,
        key_name=key_name,
        profile_type=profile_type,
        mode=mode,
        encrypted_bitting=encrypted_bitting,
        encrypted_depths=encrypted_depths,
        encrypted_positions=encrypted_positions,
        macs_valid=macs_valid,
        macs_state=macs_state,
        scale_factor_k=scale_k,
        vector_drawing_b64=vector_b64,
    )
    db.add(vault_record)
    db.commit()
    db.refresh(vault_record)

    return _deserialize_vault_item(vault_record)


@router.get("/my-vault", response_model=List[KeyVaultItemResponse])
def list_my_vault(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[KeyVaultItemResponse]:
    """Aktif kullanıcının kasasındaki tüm anahtarları AES-256'dan çözerek listeler."""
    records = (
        db.query(KeyVault)
        .filter(KeyVault.user_id == current_user.id)
        .order_by(KeyVault.id.desc())
        .all()
    )
    return [_deserialize_vault_item(rec) for rec in records]


@router.get("/{key_id}/export-gcode")
def export_key_gcode(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Kasadan seçilen anahtarın CNC .gcode dosyasını derler ve indirilebilir olarak döndürür."""
    record = (
        db.query(KeyVault)
        .filter(KeyVault.id == key_id, KeyVault.user_id == current_user.id)
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anahtar kaydı bulunamadı.",
        )

    item = _deserialize_vault_item(record)
    compiler = GCodeCompiler()
    gcode_content = compiler.compile(
        bitting_code=item.bitting_code,
        raw_depths_mm=item.raw_depths_mm,
        profile_type=item.profile_type,
        valley_positions_mm=item.valley_positions_mm,
    )
    return Response(
        content=gcode_content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="keyvault_{item.id}.gcode"'
        },
    )


@router.get("/{key_id}/export-pdf")
def export_key_pdf(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Kasadan seçilen anahtarın ReportLab PDF Kesim Kartını üretir ve döndürür."""
    record = (
        db.query(KeyVault)
        .filter(KeyVault.id == key_id, KeyVault.user_id == current_user.id)
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anahtar kaydı bulunamadı.",
        )

    item = _deserialize_vault_item(record)
    compiler = GCodeCompiler()
    gcode_content = compiler.compile(
        bitting_code=item.bitting_code,
        raw_depths_mm=item.raw_depths_mm,
        profile_type=item.profile_type,
        valley_positions_mm=item.valley_positions_mm,
    )
    pdf_bytes = generate_cutting_card_pdf(
        key_name=item.key_name,
        profile_type=item.profile_type,
        bitting_code=item.bitting_code,
        raw_depths_mm=item.raw_depths_mm,
        macs_valid=item.macs_valid,
        macs_state=item.macs_state,
        gcode_text=gcode_content,
        vector_png_base64=item.vector_drawing_b64,
        valley_positions_mm=item.valley_positions_mm,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="keyvault_{item.id}_kesim_karti.pdf"'
        },
    )
