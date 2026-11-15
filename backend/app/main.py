"""
FAZ 4: FastAPI Giriş Noktası ve CORS Yapılandırması (main.py)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, keys

# Veritabanı tablolarını başlat
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="KeyVault-AI — Otonom Optik Anahtar Profilometri ve Dijital Kasa API",
    description=(
        "ISO/IEC 7810 Referans Kart Kalibrasyonu, 3x3 Homografi, SciPy Çukur Ölçümü, "
        "MACS DFA Otomatı, CNC G-Code Derleyicisi ve Çift Katmanlı (Bcrypt + AES-256) Kriptografik Kasa."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(keys.router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "KeyVault-AI Backend"}
