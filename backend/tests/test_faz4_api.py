"""
FAZ 4 Uçtan Uca (E2E) API Testleri (tests/test_faz4_api.py)
- FastAPI TestClient ile:
  1. Kullanıcı kaydı (/api/auth/register)
  2. Login olup JWT alma (/api/auth/login)
  3. Sentetik anahtar fotoğrafını /api/keys/scan-and-save uç noktasına gönderme
  4. /api/keys/my-vault ile kasadan çekme
  5. /api/keys/{key_id}/export-gcode ve /api/keys/{key_id}/export-pdf dosyalarını indirme (HTTP 200 kontrolü).
"""

import io
import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, get_db
from app.main import app
from app.vision_pipeline import create_synthetic_key_image_bytes


@pytest.fixture()
def api_client():
    """TestClient için izole In-Memory SQLite veritabanı kurulumu."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_faz4_end_to_end_api_workflow(api_client: TestClient):
    """
    Uçtan uca senaryo:
    Register -> Login (JWT) -> Scan & Save (YALE-5 3-1-4-2-5) -> My Vault -> Export G-Code & PDF (HTTP 200).
    """
    # 1. Kullanıcı Kaydı (/api/auth/register)
    reg_resp = api_client.post(
        "/api/auth/register",
        json={
            "email": "cilingir_test@keyvault.ai",
            "password": "SuperSecurePassword!2026",
            "full_name": "Usta Cilingir",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data

    # 2. Login olup JWT alma (/api/auth/login)
    login_resp = api_client.post(
        "/api/auth/login",
        json={
            "email": "cilingir_test@keyvault.ai",
            "password": "SuperSecurePassword!2026",
        },
    )
    assert login_resp.status_code == 200
    jwt_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {jwt_token}"}

    # 3. Sentetik anahtar fotoğrafını /api/keys/scan-and-save uç noktasına gönderme
    synthetic_png_bytes = create_synthetic_key_image_bytes(
        depths_mm=[1.50, 0.50, 2.00, 1.00, 2.50],
        card_pixel_width=856,
    )
    scan_resp = api_client.post(
        "/api/keys/scan-and-save",
        headers=auth_headers,
        data={"key_name": "Ev Ana Kapisi", "profile_type": "YALE-5"},
        files={"file": ("synthetic_key.png", io.BytesIO(synthetic_png_bytes), "image/png")},
    )
    assert scan_resp.status_code == 201, scan_resp.text
    scanned_key = scan_resp.json()
    key_id = scanned_key["id"]
    assert scanned_key["bitting_code"] == "3-1-4-2-5"
    assert scanned_key["mode"] == "STANDARD"
    assert scanned_key["macs_valid"] is True
    assert scanned_key["vector_drawing_b64"] is not None

    # 4. /api/keys/my-vault ile kasadan çekme
    vault_resp = api_client.get("/api/keys/my-vault", headers=auth_headers)
    assert vault_resp.status_code == 200
    vault_list = vault_resp.json()
    assert len(vault_list) == 1
    assert vault_list[0]["id"] == key_id
    assert vault_list[0]["bitting_code"] == "3-1-4-2-5"

    # 5. /api/keys/{key_id}/export-gcode indirme (HTTP 200 kontrolü)
    gcode_resp = api_client.get(f"/api/keys/{key_id}/export-gcode", headers=auth_headers)
    assert gcode_resp.status_code == 200
    assert "G21" in gcode_resp.text
    assert "G01" in gcode_resp.text
    assert "M30" in gcode_resp.text

    # 6. /api/keys/{key_id}/export-pdf indirme (HTTP 200 ve %PDF kontrolü)
    pdf_resp = api_client.get(f"/api/keys/{key_id}/export-pdf", headers=auth_headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

    # 7. RAW_MODE (Kapalı kaynak profil - KALE) tarama ve G-Code indirme kontrolü
    raw_mode_bytes = create_synthetic_key_image_bytes(
        depths_mm=[1.20, 2.30, 0.90, 2.10, 1.60],
        card_pixel_width=856,
    )
    raw_resp = api_client.post(
        "/api/keys/scan-and-save",
        headers=auth_headers,
        data={"key_name": "Depo Kilit", "profile_type": "KALE-KILIT"},
        files={"file": ("kale_key.png", io.BytesIO(raw_mode_bytes), "image/png")},
    )
    assert raw_resp.status_code == 201
    raw_item = raw_resp.json()
    assert raw_item["mode"] == "RAW_MODE"
    assert raw_item["bitting_code"] is None

    # 8. Bilyalı Anahtar (Dimple Key) donanım kısıtlaması HTTP 422 kontrolü
    dimple_bytes = create_synthetic_key_image_bytes(dimple_mode=True)
    dimple_resp = api_client.post(
        "/api/keys/scan-and-save",
        headers=auth_headers,
        data={"key_name": "Bilyali Anahtar", "profile_type": "YALE-5"},
        files={"file": ("dimple_key.png", io.BytesIO(dimple_bytes), "image/png")},
    )
    assert dimple_resp.status_code == 422

