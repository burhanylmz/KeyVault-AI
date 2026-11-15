"""
FAZ 1 Birim Testleri (tests/test_faz1_vision.py)
- OpenCV ile RAM üzerinde sentetik görüntü (85.60mm oranlı referans kart + 5 dişli anahtar silüeti) oluşturma.
- vision_pipeline fonksiyonuna byte dizisi olarak gönderme.
- Ölçek katsayısı k'nın doğru hesaplandığını doğrulama.
- 5 çukurun SciPy (find_peaks) ile bulunduğunu doğrulama.
- YALE-5 (3-1-4-2-5) ve RAW_MODE (Kale/İto vb. kapalı kaynak profil) modlarının çalıştığını doğrulama.
- Bilyalı anahtar (Dimple Key) için DimpleKeyHardwareError fırlatıldığını doğrulama.
- İşlem sonunda RAM'deki görüntü matrisinin sıfırlandığını (img[:] == 0) doğrulama.
"""

import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.vision_pipeline import (
    DimpleKeyHardwareError,
    ISO_CARD_WIDTH_MM,
    analyze_key_image,
    create_synthetic_key_image_bytes,
)


def test_faz1_yale5_calibration_scipy_and_memory_zeroing():
    """
    856 piksel genişlikli referans kart (k = 85.60 / 856 = 0.10 mm/px) ve
    [1.5, 0.5, 2.0, 1.0, 2.5] mm derinlikli 5 diş çukuru -> '3-1-4-2-5' YALE-5 testi.
    Ayrıca finally bloğunda img[:] == 0 ile RAM sıfırlamasını doğrular.
    """
    expected_depths = [1.50, 0.50, 2.00, 1.00, 2.50]
    raw_bytes = create_synthetic_key_image_bytes(
        depths_mm=expected_depths, card_pixel_width=856
    )

    img_refs = []
    result = analyze_key_image(
        raw_bytes=raw_bytes,
        profile_type="YALE-5",
        img_ref_holder=img_refs,
    )

    # 1. Ölçek katsayısı k kontrolü (85.60 / 856 = 0.10 mm/piksel)
    expected_k = ISO_CARD_WIDTH_MM / 856.0
    assert abs(result["scale_factor_k"] - expected_k) < 0.002

    # 2. SciPy ile 5 çukurun bulunduğu ve derinliklerin doğruluğu
    assert len(result["raw_depths_mm"]) == 5
    for measured, target in zip(result["raw_depths_mm"], expected_depths):
        assert abs(measured - target) <= 0.15

    # 3. YALE-5 standart bitting eşleşmesi (3-1-4-2-5)
    assert result["mode"] == "STANDARD"
    assert result["bitting_code"] == "3-1-4-2-5"

    # 4. Homografi 3x3 matris boyutu kontrolü
    h_mat = np.array(result["homography_matrix"])
    assert h_mat.shape == (3, 3)

    # 5. RAM sıfırlama (Data Remanence önlemi: img[:] == 0) kontrolü
    assert result["memory_scrubbed"] is True
    assert len(img_refs) == 1
    assert np.all(img_refs[0][:] == 0), "Görüntü matrisi finally bloğunda sıfırlanmadı!"


def test_faz1_graceful_degradation_raw_mode():
    """
    Kapalı kaynak profil (KALE / ITO) veya tabloya uymayan derinlik verildiğinde
    çökmeden otomatik olarak RAW_MODE durumuna geçtiğini doğrular.
    """
    custom_depths = [1.20, 2.80, 0.90, 3.10, 1.70]
    raw_bytes = create_synthetic_key_image_bytes(
        depths_mm=custom_depths, card_pixel_width=856
    )

    result = analyze_key_image(raw_bytes=raw_bytes, profile_type="KALE-KILIT")
    assert result["mode"] == "RAW_MODE"
    assert result["bitting_code"] is None
    assert len(result["raw_depths_mm"]) == 5
    for measured, target in zip(result["raw_depths_mm"], custom_depths):
        assert abs(measured - target) <= 0.15


def test_faz1_dimple_key_hardware_error():
    """
    Z ekseninde çukurları olan bilyalı anahtar (Dimple Key) veya yetersiz 2D profilde
    DimpleKeyHardwareError fırlatıldığını doğrular.
    """
    dimple_bytes = create_synthetic_key_image_bytes(dimple_mode=True)
    img_refs = []
    with pytest.raises(DimpleKeyHardwareError):
        analyze_key_image(
            raw_bytes=dimple_bytes,
            profile_type="YALE-5",
            img_ref_holder=img_refs,
        )
    # Hata fırlatılsa bile finally bloğu çalışıp RAM'i sıfırlamalıdır!
    assert len(img_refs) == 1
    assert np.all(img_refs[0][:] == 0)
