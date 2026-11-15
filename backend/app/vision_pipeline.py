"""
FAZ 1: Görüntü İşleme, Kalibrasyon ve Sayısal Ölçüm (vision_pipeline.py)
- In-Memory (RAM) görüntü okuma (np.frombuffer + cv2.imdecode) ve finally bloğunda güvenli imha (img[:] = 0 + gc.collect).
- ISO/IEC 7810 Referans Kart (85.60 mm x 53.98 mm) tespiti (YOLOv8 / OpenCV fallback) ve 3x3 Homografi (getPerspectiveTransform + warpPerspective).
- OpenCV (Gri tonlama, GaussianBlur, Canny) ön işleme, Omuz (X=0) referansı ve SciPy (scipy.signal.find_peaks) ile diş çukuru ölçümü.
- YALE-5 standart bitting eşleştirme, kapalı kaynak profiller (Kale/İto vb.) için RAW_MODE Graceful Degradation ve bilyalı anahtarlar için DimpleKeyHardwareError.
"""

from __future__ import annotations

import gc
import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.signal import find_peaks

# ISO/IEC 7810 ID-1 Standart Kart Boyutları (mm)
ISO_CARD_WIDTH_MM: float = 85.60
ISO_CARD_HEIGHT_MM: float = 53.98

# Standart Bitting Derinlik Tablosu (mm cinsinden çukur derinliği)
# Kod 1..9 -> 0.50 mm .. 4.50 mm (0.50 mm adım)
YALE_DEPTH_TABLE_MM: Dict[int, float] = {
    1: 0.50,
    2: 1.00,
    3: 1.50,
    4: 2.00,
    5: 2.50,
    6: 3.00,
    7: 3.50,
    8: 4.00,
    9: 4.50,
}

STANDARD_PROFILES: Dict[str, Dict[str, Any]] = {
    "YALE-5": {"pin_count": 5, "depths_mm": YALE_DEPTH_TABLE_MM, "tolerance_mm": 0.24},
    "YALE-6": {"pin_count": 6, "depths_mm": YALE_DEPTH_TABLE_MM, "tolerance_mm": 0.24},
}


class DimpleKeyHardwareError(Exception):
    """Z ekseninde çukurları olan bilyalı anahtar veya yetersiz 2D diş profili hatası."""


def order_points(pts: np.ndarray) -> np.ndarray:
    """4 köşe noktasını [sol-üst, sağ-üst, sağ-alt, sol-alt] sırasına diz."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # Top-left
    rect[2] = pts[np.argmax(s)]  # Bottom-right

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # Top-right
    rect[3] = pts[np.argmax(diff)]  # Bottom-left
    return rect


def _binarize_foreground(gray: np.ndarray) -> np.ndarray:
    """Arka plan rengini (açık/koyu) otomatik algılayarak nesneleri beyaz (255) maskeye çevirir."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    border_pixels = np.concatenate([
        blurred[0, :],
        blurred[-1, :],
        blurred[:, 0],
        blurred[:, -1],
    ])
    bg_median = float(np.median(border_pixels))
    if bg_median > 127.0:
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def detect_card_and_key(
    img: np.ndarray, yolo_weights_path: Optional[str] = None
) -> Tuple[np.ndarray, Tuple[int, int, int, int], str]:
    """
    Referans kartın 4 köşesini ve anahtar ROI(x, y, w, h) alanını tespit eder.
    YOLOv8 ağırlık dosyası mevcutsa YOLOv8 kullanır; yoksa OpenCV kontur/köşe tespiti
    fallback mekanizmasını çalıştırır.
    """
    detector_used = "OPENCV_FALLBACK"

    if yolo_weights_path and os.path.isfile(yolo_weights_path):
        try:
            from ultralytics import YOLO  # type: ignore

            model = YOLO(yolo_weights_path)
            results = model(img, verbose=False)
            if results and len(results[0].boxes) >= 2:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
                sorted_idx = np.argsort(areas)[::-1]
                c_box = boxes[sorted_idx[0]]
                k_box = boxes[sorted_idx[1]]
                card_pts = np.array(
                    [
                        [c_box[0], c_box[1]],
                        [c_box[2], c_box[1]],
                        [c_box[2], c_box[3]],
                        [c_box[0], c_box[3]],
                    ],
                    dtype=np.float32,
                )
                key_bbox = (
                    int(k_box[0]),
                    int(k_box[1]),
                    int(k_box[2] - k_box[0]),
                    int(k_box[3] - k_box[1]),
                )
                return order_points(card_pts), key_bbox, "YOLOV8"
        except Exception:
            detector_used = "OPENCV_FALLBACK"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = _binarize_foreground(gray)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = [c for c in contours if cv2.contourArea(c) > 500]
    if len(valid_contours) < 2:
        raise ValueError("Görüntüde referans kart ve anahtar birlikte tespit edilemedi.")

    valid_contours.sort(key=cv2.contourArea, reverse=True)

    card_contour = None
    key_contour = None

    for c in valid_contours:
        x, y, w, h = cv2.boundingRect(c)
        aspect = max(w, h) / max(1.0, float(min(w, h)))
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if card_contour is None and len(approx) == 4 and 1.35 <= aspect <= 1.85:
            card_contour = c
        elif key_contour is None:
            key_contour = c

    if card_contour is None:
        card_contour = valid_contours[0]
        key_contour = valid_contours[1]
    elif key_contour is None:
        for c in valid_contours:
            if c is not card_contour:
                key_contour = c
                break

    peri = cv2.arcLength(card_contour, True)
    approx = cv2.approxPolyDP(card_contour, 0.02 * peri, True)
    if len(approx) == 4:
        card_pts = approx.reshape(4, 2).astype(np.float32)
    else:
        rect = cv2.minAreaRect(card_contour)
        card_pts = cv2.boxPoints(rect).astype(np.float32)

    ordered_card_pts = order_points(card_pts)
    kx, ky, kw, kh = cv2.boundingRect(key_contour)
    return ordered_card_pts, (kx, ky, kw, kh), detector_used


def calibrate_and_rectify(
    img: np.ndarray, card_pts: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """
    3x3 Homografi matrisi (cv2.getPerspectiveTransform) ve cv2.warpPerspective ile
    görüntüyü 90° dik düzleme oturtur ve ölçek katsayısı k = 85.60 / card_pixel_width hesaplar.
    """
    tl, tr, br, bl = card_pts

    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    card_pixel_width = (width_top + width_bottom) / 2.0

    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    card_pixel_height = (height_left + height_right) / 2.0

    if card_pixel_width < card_pixel_height:
        card_pixel_width, card_pixel_height = card_pixel_height, card_pixel_width

    if card_pixel_width <= 0:
        raise ValueError("Geçersiz referans kart piksel genişliği.")

    # Ölçek Katsayısı: k = 85.60 / card_pixel_width (mm/piksel)
    k = ISO_CARD_WIDTH_MM / card_pixel_width

    # Sahneyi 90° dik düzleme oturtacak hedef noktalar
    dst_pts = np.array(
        [
            [tl[0], tl[1]],
            [tl[0] + card_pixel_width, tl[1]],
            [tl[0] + card_pixel_width, tl[1] + card_pixel_height],
            [tl[0], tl[1] + card_pixel_height],
        ],
        dtype=np.float32,
    )

    homography_matrix = cv2.getPerspectiveTransform(card_pts, dst_pts)
    h_img, w_img = img.shape[:2]
    border_val = tuple(int(v) for v in img[0, 0])
    warped_img = cv2.warpPerspective(
        img,
        homography_matrix,
        (w_img, h_img),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_val,
    )

    return warped_img, homography_matrix, k, card_pixel_width


def _check_for_dimple_key(key_gray: np.ndarray, key_mask: np.ndarray, profile_type: str) -> None:
    """
    Z ekseninde çukurları olan bilyalı anahtarları (dimple key) tespit eder.
    Tespit edilirse DimpleKeyHardwareError fırlatır.
    """
    if profile_type.strip().upper() in {"DIMPLE", "BILYALI", "MUL-T-LOCK", "DIMPLE-KEY"}:
        raise DimpleKeyHardwareError(
            "Donanım Kısıtlaması: Z ekseninde çukurları olan bilyalı anahtar (Dimple Key) "
            "2D optik profilometri ile kesilemez."
        )

    # Gövde içinde dairesel bilya yuvaları (iç konturlar) var mı kontrol et
    contours, hierarchy = cv2.findContours(key_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is not None:
        internal_holes = 0
        for idx, h_info in enumerate(hierarchy[0]):
            parent_idx = h_info[3]
            if parent_idx != -1:
                area = cv2.contourArea(contours[idx])
                peri = cv2.arcLength(contours[idx], True)
                if area > 15 and peri > 0:
                    circularity = 4.0 * np.pi * area / (peri * peri)
                    if circularity > 0.65:
                        internal_holes += 1
        # Baş (bow) kısmındaki tek anahtarlık deliği dışında gövdede >= 3 dairesel çukur varsa bilyalı anahtardır
        if internal_holes >= 3:
            raise DimpleKeyHardwareError(
                f"Donanım Kısıtlaması: Anahtar yüzeyinde {internal_holes} adet Z-eksenli bilya çukuru tespit edildi."
            )


def extract_key_profile_and_valleys(
    warped_img: np.ndarray,
    key_bbox: Tuple[int, int, int, int],
    k: float,
    profile_type: str = "YALE-5",
) -> Tuple[List[float], List[float], np.ndarray]:
    """
    Gri tonlama, GaussianBlur ve Canny ile kenar profilini çıkarır.
    Anahtarın omuz çıkıntısını X=0 referans noktası alır.
    scipy.signal.find_peaks ile diş çukurlarını (yerel minimumları) bulur ve
    k ile çarparak milimetrik derinlik dizisini (raw_depths_mm) çıkarır.
    """
    kx, ky, kw, kh = key_bbox
    pad = 10
    h_img, w_img = warped_img.shape[:2]
    x1 = max(0, kx - pad)
    y1 = max(0, ky - pad)
    x2 = min(w_img, kx + kw + pad)
    y2 = min(h_img, ky + kh + pad)

    roi_bgr = warped_img[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    mask = _binarize_foreground(gray)
    _check_for_dimple_key(gray, mask, profile_type)

    # Sütun bazlı anahtar silüeti sınırlarını çıkar
    col_has_fg = np.any(mask > 0, axis=0)
    valid_cols = np.where(col_has_fg)[0]
    if len(valid_cols) < 20:
        raise DimpleKeyHardwareError("Yetersiz 2D anahtar profili: Anahtar silüeti çok kısa.")

    x_start = int(valid_cols[0])
    x_end = int(valid_cols[-1])

    y_top = np.zeros(x_end - x_start + 1, dtype=np.float64)
    y_bot = np.zeros(x_end - x_start + 1, dtype=np.float64)

    for idx, col in enumerate(range(x_start, x_end + 1)):
        fg_rows = np.where(mask[:, col] > 0)[0]
        if len(fg_rows) > 0:
            y_top[idx] = float(fg_rows[0])
            y_bot[idx] = float(fg_rows[-1])
        elif idx > 0:
            y_top[idx] = y_top[idx - 1]
            y_bot[idx] = y_bot[idx - 1]

    heights = y_bot - y_top
    median_blade_height = float(np.median(heights[len(heights) // 3 :]))

    # Omuz çıkıntısı (X=0 referans noktası) tespiti:
    # Sol tarafta daha geniş bir anahtar başı (bow) varsa, yüksekliğin namlu (blade)
    # seviyesine düştüğü nokta omuz (shoulder) referansıdır (X=0).
    shoulder_offset = 0
    bow_threshold = median_blade_height * 1.25
    search_limit = int(len(heights) * 0.45)
    for i in range(search_limit):
        if heights[i] > bow_threshold:
            shoulder_offset = i + 1

    blade_y_top = y_top[shoulder_offset:]
    if len(blade_y_top) < 15:
        raise DimpleKeyHardwareError("Omuz (X=0) referansından sonra yeterli namlu profili bulunamadı.")

    # Kesilmemiş üst namlu referans çizgisi (y_baseline)
    y_baseline = float(np.percentile(blade_y_top, 5))

    # Diş çukurları: Namlu üst kenarının aşağı doğru yaptığı yerel minimumlar,
    # yani y_top(x) - y_baseline kesim derinliği sinyalinin tepe noktalarıdır.
    cut_depth_px = blade_y_top - y_baseline

    min_distance = max(8, len(cut_depth_px) // 12)
    peaks, _ = find_peaks(cut_depth_px, prominence=2.0, distance=min_distance)

    if len(peaks) < 4:
        raise DimpleKeyHardwareError(
            f"Donanım/Profil Kısıtlaması: Yetersiz 2D diş profili ({len(peaks)} çukur bulundu, en az 4 gerekli)."
        )

    raw_depths_mm = [round(float(cut_depth_px[p] * k), 2) for p in peaks]
    valley_positions_mm = [round(float(p * k), 2) for p in peaks]

    return raw_depths_mm, valley_positions_mm, edges


def match_bitting_profile(
    raw_depths_mm: List[float], profile_type: str = "YALE-5"
) -> Tuple[str, Optional[str]]:
    """
    Standart YALE-5/YALE-6 profiliyse bitting tablosuyla eşleştirip şifre üretir (örn. '3-1-4-2-5').
    Tabloda yoksa (Kale, İto vb. kapalı kaynak profiller) veya ölçüm eşleşmezse ÇÖKMEZ;
    otomatik olarak RAW_MODE durumuna geçer.
    """
    norm_profile = profile_type.strip().upper()
    if norm_profile not in STANDARD_PROFILES:
        return "RAW_MODE", None

    spec = STANDARD_PROFILES[norm_profile]
    expected_pins = spec["pin_count"]
    depth_table: Dict[int, float] = spec["depths_mm"]
    tolerance: float = spec["tolerance_mm"]

    if len(raw_depths_mm) != expected_pins:
        return "RAW_MODE", None

    bitting_digits: List[str] = []
    for d_mm in raw_depths_mm:
        best_code = min(depth_table.keys(), key=lambda c: abs(depth_table[c] - d_mm))
        if abs(depth_table[best_code] - d_mm) <= tolerance:
            bitting_digits.append(str(best_code))
        else:
            return "RAW_MODE", None

    return "STANDARD", "-".join(bitting_digits)


def analyze_key_image(
    raw_bytes: bytes,
    profile_type: str = "YALE-5",
    yolo_weights_path: Optional[str] = None,
    img_ref_holder: Optional[List[np.ndarray]] = None,
) -> Dict[str, Any]:
    """
    Ana In-Memory Görüntü Analiz Boru Hattı:
    1. raw_bytes -> np.frombuffer -> cv2.imdecode (Diske ASLA kaydedilmez).
    2. ISO/IEC 7810 Referans Kart kalibrasyonu + 3x3 Homografi perspektif düzeltme.
    3. OpenCV + SciPy ile omuz (X=0) referanslı diş çukuru derinlik ölçümü.
    4. YALE-5 Bitting veya RAW_MODE (Graceful Degradation) çıktısı.
    5. finally bloğunda img[:] = 0 ve gc.collect() ile RAM'den güvenli imha.
    """
    if not raw_bytes:
        raise ValueError("Boş görüntü verisi (raw_bytes) gönderildi.")

    nparr: Optional[np.ndarray] = None
    img: Optional[np.ndarray] = None
    warped_img: Optional[np.ndarray] = None

    try:
        nparr = np.frombuffer(raw_bytes, dtype=np.uint8).copy()
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Görüntü byte dizisi çözümlenemedi (cv2.imdecode başarısız).")

        if img_ref_holder is not None:
            img_ref_holder.append(img)

        card_pts, key_bbox, detector_used = detect_card_and_key(img, yolo_weights_path)
        warped_img, homography_matrix, k, card_px_width = calibrate_and_rectify(img, card_pts)

        raw_depths_mm, valley_positions_mm, _ = extract_key_profile_and_valleys(
            warped_img, key_bbox, k, profile_type=profile_type
        )

        mode, bitting_code = match_bitting_profile(raw_depths_mm, profile_type=profile_type)

        return {
            "profile_type": profile_type,
            "mode": mode,
            "bitting_code": bitting_code,
            "raw_depths_mm": raw_depths_mm,
            "valley_positions_mm": valley_positions_mm,
            "scale_factor_k": round(float(k), 6),
            "card_pixel_width": round(float(card_px_width), 2),
            "homography_matrix": homography_matrix.tolist(),
            "detector": detector_used,
            "memory_scrubbed": True,
        }
    finally:
        if img is not None:
            img[:] = 0
        if warped_img is not None:
            warped_img[:] = 0
        if nparr is not None:
            nparr[:] = 0
        gc.collect()


def create_synthetic_key_image_bytes(
    depths_mm: Optional[List[float]] = None,
    card_pixel_width: int = 856,
    dimple_mode: bool = False,
) -> bytes:
    """
    Test ve doğrulama için RAM üzerinde sentetik bir görüntü (85.60mm oranlı referans kart +
    5 dişli anahtar silüeti) oluşturur ve PNG byte dizisi olarak döndürür. Diske kayıt yapmaz.
    """
    if depths_mm is None:
        # Varsayılan: 3-1-4-2-5 -> [1.5, 0.5, 2.0, 1.0, 2.5] mm
        depths_mm = [1.50, 0.50, 2.00, 1.00, 2.50]

    k = ISO_CARD_WIDTH_MM / float(card_pixel_width)
    card_pixel_height = int(round(ISO_CARD_HEIGHT_MM / k))

    canvas_h = max(900, card_pixel_height + 420)
    canvas_w = max(1100, card_pixel_width + 200)
    canvas = np.full((canvas_h, canvas_w, 3), 255, dtype=np.uint8)

    # 1. ISO/IEC 7810 Referans Kartı Çiz (Üst Bölge)
    card_x1, card_y1 = 80, 50
    card_x2 = card_x1 + card_pixel_width
    card_y2 = card_y1 + card_pixel_height
    cv2.rectangle(canvas, (card_x1, card_y1), (card_x2, card_y2), (30, 30, 30), -1)

    # 2. Anahtar Silüeti Çiz (Alt Bölge)
    blade_y_top = card_y2 + 110
    blade_height_px = int(round(8.5 / k))
    blade_y_bot = blade_y_top + blade_height_px

    bow_x1 = 80
    shoulder_x = 220  # X = 0 Omuz referans noktası
    bow_y1 = blade_y_top - int(round(4.0 / k))
    bow_y2 = blade_y_bot + int(round(4.0 / k))

    # Anahtar başı (Bow)
    cv2.rectangle(canvas, (bow_x1, bow_y1), (shoulder_x, bow_y2), (20, 20, 20), -1)

    # Anahtar namlusu (Blade)
    pitch_px = int(round(4.5 / k))
    first_offset_px = int(round(4.0 / k))
    blade_length_px = first_offset_px + len(depths_mm) * pitch_px + int(round(4.0 / k))
    blade_x2 = shoulder_x + blade_length_px
    cv2.rectangle(canvas, (shoulder_x, blade_y_top), (blade_x2, blade_y_bot), (20, 20, 20), -1)

    if dimple_mode:
        # Diş açmak yerine gövde ortasına Z-eksenli bilya çukurları (beyaz daireler) çiz
        center_y = (blade_y_top + blade_y_bot) // 2
        for idx in range(4):
            cx = shoulder_x + first_offset_px + idx * pitch_px
            cv2.circle(canvas, (cx, center_y), max(6, int(round(1.0 / k))), (255, 255, 255), -1)
    else:
        # 5 adet V-şekilli diş çukuru (beyaz üçgen/poligon oyuk)
        half_notch_w = max(8, pitch_px // 3)
        for idx, d_mm in enumerate(depths_mm):
            valley_cx = shoulder_x + first_offset_px + idx * pitch_px
            depth_px = int(round(d_mm / k))
            valley_y = blade_y_top + depth_px
            notch_pts = np.array(
                [
                    [valley_cx - half_notch_w, blade_y_top - 2],
                    [valley_cx + half_notch_w, blade_y_top - 2],
                    [valley_cx, valley_y],
                ],
                dtype=np.int32,
            )
            cv2.fillPoly(canvas, [notch_pts], (255, 255, 255))

    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise RuntimeError("Sentetik görüntü PNG olarak kodlanamadı.")
    return encoded.tobytes()
