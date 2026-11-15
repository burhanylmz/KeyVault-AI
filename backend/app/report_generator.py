"""
FAZ 2: 2D Vektör Çizim ve PDF Kesim Kartı Üretici (report_generator.py)
- Matplotlib ile gerçek anahtarın birebir milimetrik silüetini, yatay (X, ΔX, Namlu Boyu, Toplam Boy)
  ve dikey (Kesim Derinliği, Kalan Et Kalınlığı, Namlu Yüksekliği) kumpas ölçüleriyle çizen
  güvenli 2D vektör çizimini (Base64 PNG) üretir.
- ReportLab ile içinde 2D çizim, tam kumpas/geometri tablosu, MACS DFA durumu ve G-Code satırları bulunan
  indirilebilir PDF Kesim Kartı üretir.
"""

from __future__ import annotations

import base64
import io
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
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
    profile_outline_mm: Optional[Dict[str, List[float]]] = None,
    blade_width_mm: Optional[float] = None,
    blade_length_mm: Optional[float] = None,
    total_length_mm: Optional[float] = None,
    bow_height_mm: Optional[float] = None,
) -> str:
    """
    Gerçek anahtar fotoğrafı yerine kasada (KeyVault) saklanacak ve gösterilecek,
    anahtarın gerçek 2D silüetini ve tüm yatay/dikey milimetrik kumpas ölçülerini
    içeren teknik vektör çizimini oluşturur (Base64 PNG).
    """
    if not raw_depths_mm:
        raw_depths_mm = [1.5, 0.5, 2.0, 1.0, 2.5]

    n_cuts = len(raw_depths_mm)
    if valley_positions_mm and len(valley_positions_mm) == n_cuts:
        x_cuts = [float(x) for x in valley_positions_mm]
    else:
        x_cuts = [4.0 + i * 4.5 for i in range(n_cuts)]

    eff_blade_w = float(blade_width_mm) if blade_width_mm and blade_width_mm > 2.5 else 6.2
    if max(raw_depths_mm) + 1.5 > eff_blade_w:
        eff_blade_w = round(max(raw_depths_mm) + 3.2, 2)

    eff_blade_len = (
        float(blade_length_mm)
        if blade_length_mm and blade_length_mm > x_cuts[-1]
        else round(max(x_cuts[-1] + 3.5, 21.0), 2)
    )
    eff_bow_h = float(bow_height_mm) if bow_height_mm and bow_height_mm > eff_blade_w else round(eff_blade_w * 2.7, 2)

    fig, ax = plt.subplots(figsize=(8.6, 4.0), dpi=130)

    if (
        profile_outline_mm
        and "x_mm" in profile_outline_mm
        and len(profile_outline_mm["x_mm"]) >= 10
    ):
        # Taranan gerçek anahtarın birebir milimetrik silüeti
        x_curve = np.array(profile_outline_mm["x_mm"], dtype=float)
        y_up = np.array(profile_outline_mm["y_upper_mm"], dtype=float)
        y_lo = np.array(profile_outline_mm["y_lower_mm"], dtype=float)

        poly_x = np.concatenate([x_curve, x_curve[::-1]])
        poly_y = np.concatenate([y_up, y_lo[::-1]])
        ax.fill(poly_x, poly_y, color="#334155", alpha=0.90, edgecolor="#0F172A", linewidth=2.0)

        bow_min_x = float(np.min(x_curve))
        hole_cx = bow_min_x * 0.62
        hole_cy = float(np.median(y_up[x_curve < 0] + y_lo[x_curve < 0]) / 2.0) if np.any(x_curve < 0) else eff_blade_w * 0.5
        hole_r = min(2.4, abs(bow_min_x) * 0.18)
        hole = mpatches.Circle((hole_cx, hole_cy), hole_r, facecolor="#FFFFFF", edgecolor="#0F172A", linewidth=1.5)
        ax.add_patch(hole)
        eff_total_len = float(total_length_mm) if total_length_mm else round(eff_blade_len - bow_min_x, 2)
    else:
        # Gerçekçi yuvarlak başlı ve omuz çıkıntılı anahtar silüeti
        bow_len = 18.0
        bow_r = eff_bow_h / 2.0
        bow_cy = eff_blade_w / 2.0
        bow_cx = -bow_len + bow_r

        angles = np.linspace(np.pi * 0.22, np.pi * 1.78, 50)
        bow_xs = bow_cx + bow_r * np.cos(angles)
        bow_ys = bow_cy + bow_r * np.sin(angles)

        # Omuz çıkıntısı (collar) ve X=0 omuz inişi
        collar_xs = [-3.2, -0.4, 0.0]
        collar_top_ys = [eff_blade_w + 1.4, eff_blade_w + 1.4, eff_blade_w]

        # Sürekli (continuous) gerçekçi diş profili
        blade_xs: List[float] = [0.0]
        blade_ys: List[float] = [eff_blade_w]
        half_top = 1.25
        half_bot = 0.42
        for idx, (x_c, d_mm) in enumerate(zip(x_cuts, raw_depths_mm)):
            prev_x = blade_xs[-1]
            next_x = x_cuts[idx + 1] if idx + 1 < len(x_cuts) else eff_blade_len - 1.5
            x_lt = max(prev_x + 0.05, x_c - half_top)
            x_lb = max(x_lt + 0.15, x_c - half_bot)
            x_rb = min(next_x - 0.20, x_c + half_bot)
            x_rt = min(next_x - 0.05, x_c + half_top)
            cut_y = max(1.0, eff_blade_w - float(d_mm))
            if idx == 0:
                blade_xs.append(x_lt)
                blade_ys.append(eff_blade_w)
            blade_xs.extend([x_lb, x_rb])
            blade_ys.extend([cut_y, cut_y])
            if idx == len(x_cuts) - 1:
                blade_xs.append(x_rt)
                blade_ys.append(eff_blade_w)

        # Anahtar ucu pahı ve düz sırt (Y=0)
        tip_xs = [eff_blade_len - 1.4, eff_blade_len, eff_blade_len - 1.0, 0.0, -0.4, -3.2]
        tip_ys = [eff_blade_w * 0.72, eff_blade_w * 0.25, 0.0, 0.0, -1.2, -1.2]

        full_xs = np.concatenate([collar_xs, blade_xs, tip_xs, bow_xs[::-1]])
        full_ys = np.concatenate([collar_top_ys, blade_ys, tip_ys, bow_ys[::-1]])
        ax.fill(full_xs, full_ys, color="#334155", alpha=0.90, edgecolor="#0F172A", linewidth=2.0)

        hole = mpatches.Circle((bow_cx - 1.5, bow_cy), 2.3, facecolor="#FFFFFF", edgecolor="#0F172A", linewidth=1.5)
        ax.add_patch(hole)
        bow_min_x = -bow_len
        eff_total_len = float(total_length_mm) if total_length_mm else round(eff_blade_len + bow_len, 2)

    # Kesilmemiş namlu üst hizası (Uncut Baseline) ve Omuz (X=0) referans çizgisi
    ax.hlines(
        eff_blade_w,
        0.0,
        eff_blade_len,
        colors="#10B981",
        linestyles=":",
        linewidth=1.3,
        label=f"Kesilmemiş Namlu Eni ({eff_blade_w:.2f}mm)",
    )
    ax.axvline(0.0, color="#EF4444", linestyle="--", linewidth=1.4, label="Omuz Referansı (X=0)")

    # Diş noktaları: Yatay konum (X), Kesim Derinliği (-d) ve Sırttan Kalan Kalınlık (K)
    for idx, (x_c, d_mm) in enumerate(zip(x_cuts, raw_depths_mm), start=1):
        rem_h = max(0.5, round(eff_blade_w - float(d_mm), 2))
        y_val = eff_blade_w - float(d_mm)
        ax.plot([x_c, x_c], [0.0, y_val], color="#38BDF8", linestyle="-", linewidth=1.4)
        ax.plot([x_c, x_c], [y_val, eff_blade_w], color="#F59E0B", linestyle="--", linewidth=1.2)
        ax.plot(x_c, y_val, "o", color="#38BDF8", markersize=6)

        stagger_y = eff_blade_w + 1.3 + ((idx - 1) % 2) * 2.1
        ax.annotate(
            f"D{idx} (X:{x_c:.1f})\n-{d_mm:.2f} | K:{rem_h:.2f}mm",
            xy=(x_c, y_val),
            xytext=(x_c, stagger_y),
            ha="center",
            fontsize=6.8,
            color="#0F172A",
            weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#E0F2FE", ec="#0284C7", lw=0.8),
            arrowprops=dict(arrowstyle="->", color="#0284C7", lw=0.8),
        )

    # Alt kısımda Omuzdan Uca Namlu Boyu ve Toplam Boy ölçülendirme okları
    ax.annotate(
        "",
        xy=(eff_blade_len, -2.5),
        xytext=(0.0, -2.5),
        arrowprops=dict(arrowstyle="<->", color="#0284C7", lw=1.4),
    )
    ax.text(
        eff_blade_len / 2.0,
        -3.5,
        f"Namlu Boyu (X=0 -> Uç): {eff_blade_len:.2f} mm   |   Toplam Anahtar Boyu: {eff_total_len:.2f} mm",
        ha="center",
        va="top",
        fontsize=8.0,
        weight="bold",
        color="#0F172A",
    )

    title_code = (
        f"Fabrika Kodu: {bitting_code}"
        if bitting_code
        else "Üretici Kodu Yok — Doğrudan Milimetrik Ölçüm (RAW_MODE)"
    )
    ax.set_title(
        f"KeyVault-AI 2D Teknik Ölçüm Planı | Marka/Profil: {profile_type} | {title_code}",
        fontsize=9.5,
        weight="bold",
    )
    ax.set_xlabel("X Ekseni - Omuzdan (X=0) Yatay Mesafe (mm)", fontsize=8.5)
    ax.set_ylabel("Y Ekseni - Sırttan Yükseklik (mm)", fontsize=8.5)
    ax.set_xlim(bow_min_x - 3.0, eff_blade_len + 4.0)
    ax.set_ylim(-6.5, max(eff_bow_h * 0.75, eff_blade_w + 5.5))
    ax.grid(True, linestyle=":", alpha=0.45)
    ax.legend(loc="upper left", fontsize=7.5)
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
    blade_width_mm: Optional[float] = None,
    blade_length_mm: Optional[float] = None,
    total_length_mm: Optional[float] = None,
) -> bytes:
    """
    İçinde 2D vektör çizim, tam kumpas/milimetrik geometri tablosu (X konumu, diş aralığı ΔX,
    kesim derinliği, sırttan kalan kalınlık), MACS DFA durumu ve G-Code satırları bulunan
    indirilebilir PDF Kesim Kartı (bytes) üretir.
    """
    if not vector_png_base64:
        vector_png_base64 = generate_2d_key_vector_base64(
            raw_depths_mm=raw_depths_mm,
            bitting_code=bitting_code,
            profile_type=profile_type,
            valley_positions_mm=valley_positions_mm,
            blade_width_mm=blade_width_mm,
            blade_length_mm=blade_length_mm,
            total_length_mm=total_length_mm,
        )

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    page_w, page_h = A4

    # Başlık Çubuğu
    c.setFillColor(colors.HexColor("#0F172A"))
    c.rect(0, page_h - 65, page_w, 65, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(35, page_h - 36, "KeyVault-AI - Endustriyel CNC & Anahtarci Kesim Karti")
    c.setFont("Helvetica", 9)
    c.drawString(
        35,
        page_h - 52,
        "ISO/IEC 7810 Referans Kart Kalibrasyonlu Tam Kumpas Geometrisi & CNC G-Code Raporu",
    )

    # Meta Bilgiler ve MACS DFA Durumu
    y_cursor = page_h - 88
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(35, y_cursor, f"Anahtar Adi: {key_name}")
    c.drawString(300, y_cursor, f"Marka / Profil: {profile_type}")

    y_cursor -= 16
    mode_str = (
        f"{bitting_code} (Standart Fabrika Tablosu)"
        if bitting_code
        else "Uretici Tablosu Yok - Dogrudan Milimetrik CNC (RAW_MODE)"
    )
    c.setFont("Helvetica", 9.5)
    c.drawString(35, y_cursor, f"Kesim Modu: {mode_str}")

    macs_label = f"URETIME UYGUN ({macs_state})" if macs_valid else f"KESIM UYARISI ({macs_state})"
    c.setFillColor(colors.HexColor("#15803D") if macs_valid else colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(360, y_cursor, f"MACS DFA: {macs_label}")

    # 2D Vektör Çizimi Gömme
    y_cursor -= 175
    try:
        img_bytes = base64.b64decode(vector_png_base64)
        img_reader = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(img_reader, 35, y_cursor, width=520, height=165, preserveAspectRatio=True)
    except Exception:
        c.setFillColor(colors.black)
        c.drawString(35, y_cursor + 80, "[2D Vektor Cizimi]")

    x_positions = (
        valley_positions_mm
        if valley_positions_mm and len(valley_positions_mm) == len(raw_depths_mm)
        else [round(4.0 + i * 4.5, 2) for i in range(len(raw_depths_mm))]
    )
    eff_blade_w = float(blade_width_mm) if blade_width_mm and blade_width_mm > 2.5 else 6.2
    if max(raw_depths_mm) + 1.5 > eff_blade_w:
        eff_blade_w = round(max(raw_depths_mm) + 3.2, 2)
    eff_blade_len = (
        float(blade_length_mm)
        if blade_length_mm
        else round(max(x_positions[-1] + 3.5, 21.0), 2)
    )
    eff_total_len = float(total_length_mm) if total_length_mm else round(eff_blade_len + 18.0, 2)

    # Genel Anahtar Kumpas Ölçüleri
    y_cursor -= 20
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(
        35,
        y_cursor,
        f"Genel Kumpas Olculeri: Toplam Boy: {eff_total_len:.2f} mm  |  Namlu Boyu (X=0->Uc): {eff_blade_len:.2f} mm  |  Kesilmemis Namlu Eni: {eff_blade_w:.2f} mm",
    )

    # Diş Çukuru, Yatay Konum, Aralık ve Kalan Kalınlık Tablosu
    y_cursor -= 22
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(35, y_cursor, "1. Tam Milimetrik Dis ve Kumpas Tablosu (Omuz X=0 ve Sirt Referansli)")

    y_cursor -= 16
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(38, y_cursor, "Dis No")
    c.drawString(95, y_cursor, "Yatay Konum (X)")
    c.drawString(190, y_cursor, "Dis Araligi (dX)")
    c.drawString(285, y_cursor, "Kesim Derinligi")
    c.drawString(385, y_cursor, "Kalan Kalinlik (Kumpas)")
    c.drawString(500, y_cursor, "Fabrika Kodu")
    c.line(35, y_cursor - 4, 555, y_cursor - 4)

    bitting_parts = bitting_code.split("-") if bitting_code else ["-"] * len(raw_depths_mm)

    c.setFont("Helvetica", 8.5)
    for idx, (x_mm, d_mm) in enumerate(zip(x_positions, raw_depths_mm), start=1):
        y_cursor -= 14
        b_val = bitting_parts[idx - 1] if idx - 1 < len(bitting_parts) else "-"
        dx_mm = x_mm if idx == 1 else (x_mm - x_positions[idx - 2])
        rem_mm = max(0.5, round(eff_blade_w - float(d_mm), 2))
        c.drawString(38, y_cursor, f"Dis #{idx} (D{idx})")
        c.drawString(95, y_cursor, f"{x_mm:.2f} mm")
        c.drawString(190, y_cursor, f"{dx_mm:.2f} mm")
        c.drawString(285, y_cursor, f"-{d_mm:.2f} mm")
        c.drawString(385, y_cursor, f"{rem_mm:.2f} mm")
        c.drawString(500, y_cursor, str(b_val))

    # CNC G-Code Komut Satırları
    y_cursor -= 24
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(35, y_cursor, "2. Derlenen ISO CNC G-Code Komutlari (.gcode)")

    y_cursor -= 10
    c.setFillColor(colors.HexColor("#F1F5F9"))
    box_height = max(110, min(200, y_cursor - 35))
    c.rect(35, y_cursor - box_height, 520, box_height, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Courier", 8)
    text_y = y_cursor - 13
    for line in gcode_text.strip().splitlines():
        if text_y < 40:
            break
        c.drawString(45, text_y, line)
        text_y -= 10.0

    c.showPage()
    c.save()
    pdf_buf.seek(0)
    return pdf_buf.read()
