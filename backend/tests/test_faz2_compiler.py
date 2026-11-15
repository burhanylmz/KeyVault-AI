"""
FAZ 2 Birim Testleri (tests/test_faz2_compiler.py)
- 3-1-4-2-5 girdisinin MACS DFA'dan True, 1-8-2-9-1 girdisinin False döndüğünü doğrulama.
- Regex (^[1-9](-[1-9]){4,5}$) doğrulaması.
- Üretilen .gcode metninde G21, G90, G00, G01 ve M30 koordinatlarının bulunduğunu doğrulama (hem Bitting hem RAW_MODE).
- Matplotlib 2D vektör çiziminin geçerli Base64 PNG ürettiğini ve ReportLab çıktısının %PDF başlığıyla geçerli bir PDF byte dizisi ürettiğini doğrulama.
"""

import base64
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.compiler_dfa import GCodeCompiler, MACS_DFA, validate_bitting_regex
from app.report_generator import generate_2d_key_vector_base64, generate_cutting_card_pdf


def test_faz2_macs_dfa_validation():
    """3-1-4-2-5 girdisinin DFA'dan True, 1-8-2-9-1 girdisinin False döndüğünü doğrula."""
    dfa = MACS_DFA(macs_limit=4)

    # Geçerli bitting: |3-1|=2<=4, |1-4|=3<=4, |4-2|=2<=4, |2-5|=3<=4
    assert validate_bitting_regex("3-1-4-2-5") is True
    assert dfa.validate("3-1-4-2-5") is True
    assert dfa.current_state == "q_5"

    # Geçersiz MACS: |1-8|=7 > 4 -> q_reject
    assert validate_bitting_regex("1-8-2-9-1") is True
    assert dfa.validate("1-8-2-9-1") is False
    assert dfa.current_state == "q_reject"

    # Ek örnek kontrol: |1-7|=6 > 4 -> q_reject
    assert dfa.validate("3-1-7-2-5") is False
    assert dfa.current_state == "q_reject"

    # Regex format hatası kontrolü
    assert dfa.validate("3-1-4") is False
    assert dfa.validate("0-1-2-3-4") is False


def test_faz2_gcode_compiler_standard_and_raw():
    """Üretilen .gcode metninde G21 ve G01 koordinatlarının bulunduğunu doğrula."""
    compiler = GCodeCompiler()

    # 1. Standart Bitting derlemesi
    gcode_std = compiler.compile(bitting_code="3-1-4-2-5", profile_type="YALE-5")
    assert "G21" in gcode_std
    assert "G90" in gcode_std
    assert "G00 X0.0 Y0.0" in gcode_std
    assert "G01 X4.00 Y-1.50 F120" in gcode_std
    assert "M30" in gcode_std

    # 2. RAW_MODE milimetrik derinlik derlemesi
    gcode_raw = compiler.compile(
        bitting_code=None,
        raw_depths_mm=[1.25, 2.10, 0.85, 1.90, 2.40],
        profile_type="KALE-RAW",
    )
    assert "G21" in gcode_raw
    assert "G01 X4.00 Y-1.25 F120" in gcode_raw
    assert "M30" in gcode_raw

    # 3. MACS ihlali olan kodun derlenmesinin reddedilmesi
    with pytest.raises(ValueError):
        compiler.compile(bitting_code="1-8-2-9-1", profile_type="YALE-5")


def test_faz2_vector_plot_and_reportlab_pdf():
    """2D Vektör Base64 PNG ve ReportLab %PDF byte dizisi üretimini doğrula."""
    depths = [1.50, 0.50, 2.00, 1.00, 2.50]
    b64_png = generate_2d_key_vector_base64(
        raw_depths_mm=depths, bitting_code="3-1-4-2-5", profile_type="YALE-5"
    )
    raw_png = base64.b64decode(b64_png)
    assert raw_png.startswith(b"\x89PNG")

    compiler = GCodeCompiler()
    gcode_text = compiler.compile(bitting_code="3-1-4-2-5", profile_type="YALE-5")

    pdf_bytes = generate_cutting_card_pdf(
        key_name="Ana Giris Kapisi",
        profile_type="YALE-5",
        bitting_code="3-1-4-2-5",
        raw_depths_mm=depths,
        macs_valid=True,
        macs_state="q_5",
        gcode_text=gcode_text,
        vector_png_base64=b64_png,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
