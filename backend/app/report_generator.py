"""
FAZ 2: 2D Vektör Çizim ve PDF Kesim Kartı Üretici (report_generator.py)
- Matplotlib ile gerçek fotoğraf yerine kasada gösterilecek güvenli 2D vektör çizimini (Base64 PNG) üretir.
- ReportLab ile içinde 2D çizim, bitting/ham derinlik tablosu, MACS DFA durumu ve G-Code satırları bulunan
  indirilebilir PDF Kesim Kartı üretir.
"""

from __future__ import annotations

import base64
import io
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def generate_2d_key_vector_base64(
    raw_depths_mm: List[float],
    bitting_code: Optional[str] = None,
    profile_type: str = "YALE-5",
    valley_positions_mm: Optional[List[float]] = None,
) -> str:
    """
    Gerçek anahtar fotoğrafı yerine kasada (KeyVault) saklanacak ve gösterilecek
    güvenli 2D teknik vektör çizimini oluşturur ve Base64 PNG olarak döndürür.
    """
    if not raw_depths_mm:
        raw_depths_mm = [1.5, 0.5, 2.0, 1.0, 2.5]

    n_cuts = len(raw_depths_mm)
    if valley_positions_mm and len(valley_positions_mm) == n_cuts:
        x_cuts = [float(x) for x in valley_positions_mm]
    else:
        x_cuts = [4.0 + i * 4.5 for i in range(n_cuts)]

    blade_len = max(x_cuts[-1] + 5.0, 28.0)
    blade_height = 8.5

    # Anahtar üst profil noktaları (X=0 omuz referansından uca)
    xs = [-12.0, -12.0, 0.0, 0.0]
    ys = [-3.0, blade_height + 3.0, blade_height + 3.0, blade_height]

    notch_half_w = 1.4
    for x_c, d_mm in zip(x_cuts, raw_depths_mm):
        xs.extend([x_c - notch_half_w, x_c, x_c + notch_half_w])
        ys.extend([blade_height, blade_height - float(d_mm), blade_height])

    # Anahtar ucu ve alt kenar
    xs.extend([blade_len - 1.5, blade_len, blade_len - 1.0, 0.0, 0.0, -12.0])
    ys.extend([blade_height, 2.0, 0.0, 0.0, -3.0, -3.0])

    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=120)
    ax.fill(xs, ys, color="#1E293B", alpha=0.88, edgecolor="#0F172A", linewidth=2.0)

    # Omuz (X=0) referans çizgisi
    ax.axvline(0.0, color="#EF4444", linestyle="--", linewidth=1.2, label="Omuz Referansı (X=0)")

    # Çukur derinlik noktalarını işaretle
    for idx, (x_c, d_mm) in enumerate(zip(x_cuts, raw_depths_mm), start=1):
        y_val = blade_height - float(d_mm)
        ax.plot(x_c, y_val, "o", color="#38BDF8", markersize=6)
        ax.annotate(
            f"D{idx}\n-{d_mm:.2f}mm",
            xy=(x_c, y_val),
            xytext=(x_c, y_val - 2.3),
            ha="center",
            fontsize=7.5,
            color="#F8FAFC",
            weight="bold",
        )

    title_code = bitting_code if bitting_code else "RAW_MODE (Milimetrik)"
    ax.set_title(
        f"KeyVault-AI 2D Vektör Profili | {profile_type} | {title_code}",
        fontsize=10,
        weight="bold",
    )
    ax.set_xlabel("X Ekseni - Omuzdan Mesafe (mm)", fontsize=8.5)
    ax.set_ylabel("Y Ekseni - Namlu Yüksekliği (mm)", fontsize=8.5)
    ax.set_xlim(-14.0, blade_len + 3.0)
    ax.set_ylim(-4.5, blade_height + 4.5)
    ax.grid(True, linestyle=":", alpha=0.45)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_cutting_card_pdf(
    key_name: str,
    profile_type: str,
    bitting_code: Optional[str],
    raw_depths_mm: List[float],
    macs_valid: bool,
    macs_state: str,
    gcode_text: str,
    vector_png_base64: Optional[str] = None,
    valley_positions_mm: Optional[List[float]] = None,
) -> bytes:
    """
    İçinde 2D vektör çizim, bitting/ham derinlik tablosu, MACS DFA durumu ve
    G-Code satırları bulunan indirilebilir PDF Kesim Kartı (bytes) üretir.
    """
    if not vector_png_base64:
        vector_png_base64 = generate_2d_key_vector_base64(
            raw_depths_mm=raw_depths_mm,
            bitting_code=bitting_code,
            profile_type=profile_type,
            valley_positions_mm=valley_positions_mm,
        )

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    page_w, page_h = A4

    # Başlık Çubuğu
    c.setFillColor(colors.HexColor("#0F172A"))
    c.rect(0, page_h - 65, page_w, 65, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(35, page_h - 38, "KeyVault-AI - Endustriyel CNC Anahtar Kesim Karti")
    c.setFont("Helvetica", 9)
    c.drawString(35, page_h - 54, "ISO/IEC 7810 Kalibrasyonlu Optik Profilometri & MACS DFA Derleyici Raporu")

    # Meta Bilgiler ve MACS DFA Durumu
    y_cursor = page_h - 90
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35, y_cursor, f"Anahtar Adi: {key_name}")
    c.drawString(300, y_cursor, f"Profil Tipi: {profile_type}")

    y_cursor -= 18
    mode_str = bitting_code if bitting_code else "RAW_MODE (Kapali Kaynak / Ham Olcum)"
    c.setFont("Helvetica", 10)
    c.drawString(35, y_cursor, f"Bitting / Mod: {mode_str}")

    macs_label = f"GEÇERLİ ({macs_state})" if macs_valid else f"REDDEDİLDİ ({macs_state})"
    c.setFillColor(colors.HexColor("#15803D") if macs_valid else colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(300, y_cursor, f"MACS DFA Durumu: {macs_label}")

    # 2D Vektör Çizimi Gömme
    y_cursor -= 175
    try:
        img_bytes = base64.b64decode(vector_png_base64)
        img_reader = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(img_reader, 35, y_cursor, width=520, height=160, preserveAspectRatio=True)
    except Exception:
        c.setFillColor(colors.black)
        c.drawString(35, y_cursor + 80, "[2D Vektor Cizimi]")

    # Bitting / Ham Derinlik Tablosu
    y_cursor -= 25
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35, y_cursor, "1. Dis Cukuru ve Milimetrik Derinlik Tablosu (Omuz X=0 Referansli)")

    y_cursor -= 18
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y_cursor, "Dis No")
    c.drawString(120, y_cursor, "X Konumu (mm)")
    c.drawString(240, y_cursor, "Bitting Kodu")
    c.drawString(360, y_cursor, "Kesim Derinligi (mm)")
    c.line(35, y_cursor - 4, 550, y_cursor - 4)

    bitting_parts = bitting_code.split("-") if bitting_code else ["RAW"] * len(raw_depths_mm)
    x_positions = (
        valley_positions_mm
        if valley_positions_mm and len(valley_positions_mm) == len(raw_depths_mm)
        else [round(4.0 + i * 4.5, 2) for i in range(len(raw_depths_mm))]
    )

    c.setFont("Helvetica", 9)
    for idx, (x_mm, d_mm) in enumerate(zip(x_positions, raw_depths_mm), start=1):
        y_cursor -= 15
        b_val = bitting_parts[idx - 1] if idx - 1 < len(bitting_parts) else "RAW"
        c.drawString(40, y_cursor, f"Pin #{idx}")
        c.drawString(120, y_cursor, f"{x_mm:.2f} mm")
        c.drawString(240, y_cursor, str(b_val))
        c.drawString(360, y_cursor, f"-{d_mm:.2f} mm")

    # CNC G-Code Komut Satırları
    y_cursor -= 28
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35, y_cursor, "2. Derlenen ISO CNC G-Code Komutlari (.gcode)")

    y_cursor -= 12
    c.setFillColor(colors.HexColor("#F1F5F9"))
    box_height = max(120, min(220, y_cursor - 40))
    c.rect(35, y_cursor - box_height, 520, box_height, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Courier", 8)
    text_y = y_cursor - 14
    for line in gcode_text.strip().splitlines():
        if text_y < 45:
            break
        c.drawString(45, text_y, line)
        text_y -= 10.5

    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf.read()
