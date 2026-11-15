"""
FAZ 1: Görüntü İşleme, Kalibrasyon, Marka Tanıma ve Sayısal Ölçüm (vision_pipeline.py)
- In-Memory (RAM) görüntü okuma (np.frombuffer + cv2.imdecode) ve finally bloğunda güvenli imha (img[:] = 0 + gc.collect).
- ISO/IEC 7810 Referans Kart (85.60 mm x 53.98 mm) serbest konum/açı tespiti (YOLOv8 / OpenCV minAreaRect fallback) ve 3x3 Homografi.
- Çift yönlü (dişler yukarı veya aşağı bakabilir) OpenCV + SciPy (find_peaks + basamak/plato analizi) ile diş çukuru ölçümü.
- Anahtar başından (bow) RapidOCR + bulanık eşleştirme ile otomatik marka tespiti (BAY-TEC, KALE, YALE, BKS, İTO vb.).
- Standart profiller, kapalı kaynak profiller (RAW_MODE) ve bilyalı anahtarlar için DimpleKeyHardwareError.
"""

from __future__ import annotations

import base64
import difflib
import gc
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.signal import find_peaks

# ISO/IEC 7810 ID-1 Standart Kart Boyutları (mm)
ISO_CARD_WIDTH_MM: float = 85.60
ISO_CARD_HEIGHT_MM: float = 53.98

# Standart Bitting Derinlik Tablosu (mm cinsinden çukur derinliği)
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

KNOWN_KEY_BRANDS: Dict[str, str] = {
    "BAYTEC": "BAY-TEC",
    "BAY-TEC": "BAY-TEC",
    "BMETES": "BAY-TEC",
    "KALE": "KALE-KILIT",
    "YALE": "YALE-5",
    "ITO": "ITO-KILIT",
    "BKS": "BKS",
    "DAF": "DAF",
    "HOK": "HOK",
    "ABUS": "ABUS",
    "CISA": "CISA",
    "ISEO": "ISEO",
    "ASSA": "ASSA",
    "MULTLOCK": "MUL-T-LOCK",
}

_OCR_ENGINE: Any = None


def _get_ocr_engine() -> Any:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

            _OCR_ENGINE = RapidOCR()
        except Exception:
            _OCR_ENGINE = False
    return _OCR_ENGINE if _OCR_ENGINE is not False else None


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
    """
    Arka plan rengini (açık masa / koyu zemin) iç çerçeveden algılayarak
    nesneleri beyaz (255) maskeye çevirir. Kenardaki yabancı cisimlerden etkilenmez.
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    h, w = blurred.shape[:2]
    margin_y = max(2, min(20, h // 20))
    margin_x = max(2, min(20, w // 20))
    border_pixels = np.concatenate([
        blurred[margin_y, margin_x : w - margin_x],
        blurred[h - 1 - margin_y, margin_x : w - margin_x],
        blurred[margin_y : h - margin_y, margin_x],
        blurred[margin_y : h - margin_y, w - 1 - margin_x],
    ])
    bg_median = float(np.median(border_pixels))
    if bg_median > 110.0:
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def detect_card_and_key(
    img: np.ndarray, yolo_weights_path: Optional[str] = None
) -> Tuple[np.ndarray, Tuple[int, int, int, int], str]:
    """
    Referans kartın 4 köşesini ve anahtar ROI(x, y, w, h) alanını tespit eder.
    Kart ve anahtar kadraj içinde serbestçe (hafif eğik veya yuvarlatılmış köşeli)
    bulunabilir; görüntü sınırına değen yabancı masaüstü cisimlerini otomatik filtreler.
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

    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = _binarize_foreground(gray)

    # Kart üzerindeki parlama/yazıların konturu bölmemesi için hafif morfolojik kapama
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_valid = [c for c in contours if cv2.contourArea(c) > 400]

    # Görüntünün en dış kenarına (3px) yapışık olan yabancı cisimleri (laptop kenarı, defter vb.) ayıkla
    interior_contours = []
    for c in raw_valid:
        x, y, cw, ch = cv2.boundingRect(c)
        touches_border = (
            x <= 3 or y <= 3 or (x + cw) >= (w_img - 3) or (y + ch) >= (h_img - 3)
        )
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        aspect = max(rw, rh) / max(1.0, float(min(rw, rh)))
        if not touches_border and aspect < 12.0:
            interior_contours.append(c)

    valid_contours = interior_contours if len(interior_contours) >= 2 else raw_valid
    if len(valid_contours) < 2:
        raise ValueError(
            "Görüntüde referans kart ve anahtar birlikte tespit edilemedi. "
            "Lütfen kartın ve anahtarın tamamının kadraj içinde olduğundan emin olun."
        )

    valid_contours.sort(key=cv2.contourArea, reverse=True)

    card_contour = None
    key_contour = None

    for c in valid_contours:
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        aspect = max(rw, rh) / max(1.0, float(min(rw, rh)))
        if card_contour is None and 1.20 <= aspect <= 2.05:
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
        # Yuvarlatılmış köşeli gerçek kredi/referans kartları için minAreaRect
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

    k = ISO_CARD_WIDTH_MM / card_pixel_width

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


def detect_key_brand_from_bow(roi_bgr: np.ndarray, shoulder_offset: int) -> Optional[str]:
    """
    Anahtarın baş (bow) kısmındaki kabartma/baskı yazıyı (örn. BAY-TEC, KALE, YALE, BKS)
    RapidOCR ve bulanık dizi eşleştirme (difflib) ile otomatik tanır.
    """
    ocr = _get_ocr_engine()
    if ocr is None:
        return None

    h_roi, w_roi = roi_bgr.shape[:2]
    bow_end = max(shoulder_offset, min(w_roi, int(w_roi * 0.52)))
    if bow_end < 15:
        return None

    bow_crop = roi_bgr[:, :bow_end]
    # Kabartma metal yazıyı belirginleştirmek için 4x büyütme
    bow_up = cv2.resize(bow_crop, (0, 0), fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)

    candidates = [
        bow_up,
        cv2.rotate(bow_up, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(bow_up, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]

    detected_tokens: List[str] = []
    for cand in candidates:
        try:
            res, _ = ocr(cand)
            if res:
                for line in res:
                    txt = str(line[1]).upper().strip()
                    cleaned = re.sub(r"[^A-Z0-9\-]", "", txt)
                    if len(cleaned) >= 3:
                        detected_tokens.append(cleaned)
        except Exception:
            continue

    for token in detected_tokens:
        if token in KNOWN_KEY_BRANDS:
            return KNOWN_KEY_BRANDS[token]
        for key_pat, canonical in KNOWN_KEY_BRANDS.items():
            if key_pat in token:
                return canonical

    # Bulanık eşleştirme (örn. kabartma metalde 'BMETES' -> 'BAYTEC' -> 'BAY-TEC')
    best_brand: Optional[str] = None
    best_score: float = 0.0
    for token in detected_tokens:
        for key_pat, canonical in KNOWN_KEY_BRANDS.items():
            score = difflib.SequenceMatcher(None, token, key_pat).ratio()
            if score > best_score:
                best_score = score
                best_brand = canonical

    if best_brand and best_score >= 0.60:
        return best_brand

    if detected_tokens:
        return detected_tokens[0]
    return None


def _check_for_dimple_key(
    blade_mask: np.ndarray,
    blade_height_variation_px: float,
    profile_type: str,
) -> None:
    """
    Z ekseninde çukurları olan bilyalı anahtarları (dimple key) tespit eder.
    Yalnızca namlu (blade) bölgesini inceler; anahtar başındaki (bow) marka kabartmalarını
    veya tırtıklı desenleri bilya çukuru olarak algılamaz.
    """
    if profile_type.strip().upper() in {"DIMPLE", "BILYALI", "DIMPLE-KEY"}:
        raise DimpleKeyHardwareError(
            "Donanım Kısıtlaması: Z ekseninde çukurları olan bilyalı anahtar (Dimple Key) "
            "2D optik profilometri ile kesilemez."
        )

    # Eğer namlu kenarında gerçek diş kesimleri varsa (variation >= 3.0 px), bu bir bilyalı anahtar değildir
    if blade_height_variation_px >= 3.0:
        return

    contours, hierarchy = cv2.findContours(
        blade_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchy is not None:
        internal_holes = 0
        for idx, h_info in enumerate(hierarchy[0]):
            parent_idx = h_info[3]
            if parent_idx != -1:
                area = cv2.contourArea(contours[idx])
                peri = cv2.arcLength(contours[idx], True)
                if area > 12 and peri > 0:
                    circularity = 4.0 * np.pi * area / (peri * peri)
                    if circularity > 0.60:
                        internal_holes += 1
        if internal_holes >= 3:
            raise DimpleKeyHardwareError(
                f"Donanım Kısıtlaması: Anahtar namlusunda {internal_holes} adet Z-eksenli bilya çukuru tespit edildi."
            )


def extract_key_profile_and_valleys(
    warped_img: np.ndarray,
    key_bbox: Tuple[int, int, int, int],
    k: float,
    profile_type: str = "YALE-5",
    ky: Optional[float] = None,
) -> Tuple[List[float], List[float], np.ndarray, Optional[str], Dict[str, Any]]:
    """
    Gri tonlama, GaussianBlur ve Canny ile kenar profilini çıkarır.
    - Yatay ölçek (kx = k) ve dikey ölçek (ky) ayrı ayrı kullanılarak kamera eğimi telafi edilir.
    - Anahtar sırtı (spine) referans alınarak eğimden bağımsız (rotation-invariant) namlu yüksekliği,
      kalan et kalınlığı (kumpas ölçüsü) ve kesim derinliği hesaplanır.
    - Hem keskin V-çukurlarını hem de gerçek anahtarlardaki basamak/plato dişlerini yakalar.
    - Anahtar başından (bow) marka bilgisini (örn. BAY-TEC) okur.
    """
    kx_scale = float(k)
    ky_scale = float(ky) if ky is not None and ky > 0 else kx_scale

    kx, ky_box, kw, kh = key_bbox
    pad = 12
    h_img, w_img = warped_img.shape[:2]
    x1 = max(0, kx - pad)
    y1 = max(0, ky_box - pad)
    x2 = min(w_img, kx + kw + pad)
    y2 = min(h_img, ky_box + kh + pad)

    roi_bgr = warped_img[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    raw_mask = _binarize_foreground(gray)

    # Ana dış anahtar konturunu bul ve iç yansımaları doldurarak temiz silüet oluştur
    cnts, _ = cv2.findContours(raw_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise DimpleKeyHardwareError("Anahtar silüeti ayrıştırılamadı.")

    main_key_cnt = max(cnts, key=cv2.contourArea)
    solid_mask = np.zeros_like(raw_mask)
    cv2.drawContours(solid_mask, [main_key_cnt], -1, 255, -1)

    col_has_fg = np.any(solid_mask > 0, axis=0)
    valid_cols = np.where(col_has_fg)[0]
    if len(valid_cols) < 20:
        raise DimpleKeyHardwareError("Yetersiz 2D anahtar profili: Anahtar silüeti çok kısa.")

    x_start = int(valid_cols[0])
    x_end = int(valid_cols[-1])

    y_top = np.zeros(x_end - x_start + 1, dtype=np.float64)
    y_bot = np.zeros(x_end - x_start + 1, dtype=np.float64)

    for idx, col in enumerate(range(x_start, x_end + 1)):
        fg_rows = np.where(solid_mask[:, col] > 0)[0]
        if len(fg_rows) > 0:
            y_top[idx] = float(fg_rows[0])
            y_bot[idx] = float(fg_rows[-1])
        elif idx > 0:
            y_top[idx] = y_top[idx - 1]
            y_bot[idx] = y_bot[idx - 1]

    heights = y_bot - y_top
    # Eğer anahtar ters (baş sağda, uç solda) konulmuşsa otomatik çevir
    left_half_med = float(np.median(heights[: len(heights) // 3]))
    right_half_med = float(np.median(heights[2 * len(heights) // 3 :]))
    if right_half_med > left_half_med * 1.35:
        y_top = y_top[::-1].copy()
        y_bot = y_bot[::-1].copy()
        heights = y_bot - y_top
        roi_bgr = cv2.flip(roi_bgr, 1)
        raw_mask = cv2.flip(raw_mask, 1)
        solid_mask = cv2.flip(solid_mask, 1)

    # Omuz çıkıntısı (X=0 referans noktası) tespiti:
    # Kesilmiş namlularda çukurlar medyanı düşürdüğü için, kesilmemiş namlu referansı olarak
    # sağ yarıdaki (uç pahı hariç) 92. yüzdelik dilimi kullanıyoruz.
    n_total = len(heights)
    blade_core_slice = heights[int(n_total * 0.48) : max(int(n_total * 0.55), int(n_total * 0.90))]
    blade_ref_height = float(np.percentile(blade_core_slice, 92))

    shoulder_offset = 0
    bow_threshold = max(blade_ref_height * 1.12, blade_ref_height + 2.5)
    search_limit = int(n_total * 0.58)
    for i in range(search_limit):
        if heights[i] > bow_threshold:
            shoulder_offset = i + 1

    blade_y_top = y_top[shoulder_offset:]
    blade_y_bot = y_bot[shoulder_offset:]
    blade_heights = heights[shoulder_offset:]

    if len(blade_heights) < 15:
        raise DimpleKeyHardwareError(
            "Omuz (X=0) referansından sonra yeterli namlu profili bulunamadı."
        )

    # Namlu üzerindeki iç delikleri kontrol etmek için sadece namlu bölgesinin ham maskesini al
    blade_raw_mask = raw_mask[:, x_start + shoulder_offset : x_end + 1]
    # Uçtaki son %10 pah kısmını hariç tutarak namlu kalınlık değişimini ölç
    active_len = max(12, int(len(blade_heights) * 0.89))
    blade_variation = float(
        np.percentile(blade_heights[:active_len], 95)
        - np.percentile(blade_heights[:active_len], 5)
    )

    _check_for_dimple_key(blade_raw_mask, blade_variation, profile_type)

    # Dişlerin üst kenarda mı (blade_y_top) yoksa alt kenarda mı (blade_y_bot) olduğunu algıla
    core_top = blade_y_top[:active_len]
    core_bot = blade_y_bot[:active_len]
    top_var = float(np.percentile(core_top, 95) - np.percentile(core_top, 5))
    bot_var = float(np.percentile(core_bot, 95) - np.percentile(core_bot, 5))
    teeth_on_top = top_var >= bot_var

    # Kesilmemiş namlu yüksekliği (Uncut Blade Width):
    # Omuzdan hemen sonraki boyun (ilk 8 piksel) ve aktif namlu üzerindeki en yüksek sırt-taban mesafesi
    neck_slice = blade_heights[: max(4, min(10, len(blade_heights) // 8))]
    uncut_blade_height_px = float(
        max(np.median(neck_slice), np.percentile(blade_heights[:active_len], 95))
    )

    # Eğimden bağımsız (rotation-invariant) kesim derinliği:
    # Her X noktasında sırttan diş dibine olan gerçek kalınlığı (blade_heights),
    # kesilmemiş namlu kalınlığından (uncut_blade_height_px) çıkarıyoruz.
    cut_depth_px = np.maximum(0.0, uncut_blade_height_px - blade_heights)

    if teeth_on_top:
        y_baseline_arr = blade_y_bot - uncut_blade_height_px
    else:
        y_baseline_arr = blade_y_top + uncut_blade_height_px

    n_pins = 6 if "6" in profile_type else 5
    min_distance = max(6, len(cut_depth_px) // 12)
    v_peaks, _ = find_peaks(cut_depth_px[:active_len], prominence=1.5, distance=min_distance)

    # Sentetik veya ayrık V-dişli anahtarlarda her iki diş arasında derinlik 0'a döner:
    is_isolated_v_notch = False
    if len(v_peaks) >= n_pins:
        zero_returns = 0
        for idx_p in range(len(v_peaks) - 1):
            seg = cut_depth_px[v_peaks[idx_p] : v_peaks[idx_p + 1] + 1]
            if len(seg) > 0 and float(np.min(seg)) <= 0.6:
                zero_returns += 1
        if zero_returns >= len(v_peaks) - 2:
            is_isolated_v_notch = True

    if is_isolated_v_notch:
        peaks = v_peaks[:n_pins]
    else:
        if blade_variation < 2.5 and len(v_peaks) < 4:
            raise DimpleKeyHardwareError(
                f"Donanım/Profil Kısıtlaması: Yetersiz 2D diş profili ({len(v_peaks)} çukur bulundu, en az 4 gerekli)."
            )
        # Gerçek sürekli profilli anahtarlarda (örn. BAY-TEC, KALE) dişler arasında profil 0'a dönmez;
        # derin çukurlar, düz basamaklar (plato) ve sığ tepeler eşit aralıklı pim istasyonlarında yer alır.
        cut_mask_indices = np.where(cut_depth_px[:active_len] > 1.2)[0]
        cut_start = int(cut_mask_indices[0]) if len(cut_mask_indices) > 0 else max(4, int(active_len * 0.12))
        first_station = min(cut_start + 4, int(active_len * 0.22))
        last_station = max(first_station + n_pins * 4, active_len - 4)
        station_centers = np.linspace(first_station, last_station, n_pins)
        grad = np.abs(np.gradient(cut_depth_px))
        win = max(3, int(round((last_station - first_station) / (n_pins * 3.0))))
        sampled_peaks: List[int] = []
        for sc in station_centers:
            c_idx = int(round(sc))
            lo = max(cut_start, c_idx - win)
            hi = min(active_len, c_idx + win + 1)
            if hi > lo:
                best_local = lo + int(np.argmin(grad[lo:hi]))
            else:
                best_local = c_idx
            sampled_peaks.append(best_local)
        peaks = np.array(sampled_peaks, dtype=int)

    raw_depths_mm = [round(max(0.10, float(cut_depth_px[p] * ky_scale)), 2) for p in peaks]
    remaining_heights_mm = [round(max(0.50, float(blade_heights[p] * ky_scale)), 2) for p in peaks]
    valley_positions_mm = [round(float(p * kx_scale), 2) for p in peaks]
    pitch_values_mm = [
        round(valley_positions_mm[i] - valley_positions_mm[i - 1], 2)
        for i in range(1, len(valley_positions_mm))
    ]

    total_length_mm = round(float((x_end - x_start + 1) * kx_scale), 2)
    bow_height_mm = round(float(np.max(heights[: max(1, shoulder_offset)]) * ky_scale), 2)
    blade_length_mm = round(float(len(blade_heights) * kx_scale), 2)
    blade_width_mm = round(float(uncut_blade_height_px * ky_scale), 2)

    detected_brand: Optional[str] = None
    if profile_type.strip().upper() in {"AUTO", "OTOMATIK", "OTOMATİK"}:
        detected_brand = detect_key_brand_from_bow(roi_bgr, x_start + shoulder_offset)

    # Görsel kanıt çizimi için piksel koordinatlarını kaydet
    valley_img_pts: List[Tuple[int, int, int, int]] = []
    for p in peaks:
        px_x = x1 + x_start + shoulder_offset + int(p)
        if teeth_on_top:
            px_y = y1 + int(round(blade_y_top[p]))
            base_y = y1 + int(round(y_baseline_arr[p]))
            spine_y = y1 + int(round(blade_y_bot[p]))
        else:
            px_y = y1 + int(round(blade_y_bot[p]))
            base_y = y1 + int(round(y_baseline_arr[p]))
            spine_y = y1 + int(round(blade_y_top[p]))
        valley_img_pts.append((px_x, px_y, base_y, spine_y))

    # 2D teknik çizimde gerçek anahtar silüetini birebir göstermek için milimetrik profil eğrileri
    # Omuz (X=0) referanslı, sırt Y=0 tabanlı milimetrik kontur:
    step_sz = max(1, len(heights) // 90)
    sampled_indices = list(range(0, len(heights), step_sz))
    if sampled_indices[-1] != len(heights) - 1:
        sampled_indices.append(len(heights) - 1)

    spine_ref_px = float(np.median(blade_y_bot[:active_len] if teeth_on_top else blade_y_top[:active_len]))
    x_mm_curve: List[float] = []
    y_upper_mm_curve: List[float] = []
    y_lower_mm_curve: List[float] = []
    for idx_c in sampled_indices:
        x_rel_mm = round(float((idx_c - shoulder_offset) * kx_scale), 2)
        if teeth_on_top:
            # Sırt altta (y_bot), dişler üstte (y_top): Y=0 sırt kabul edilir
            u_mm = round(float((spine_ref_px - y_top[idx_c]) * ky_scale), 2)
            l_mm = round(float((spine_ref_px - y_bot[idx_c]) * ky_scale), 2)
        else:
            # Sırt üstte (y_top), dişler altta (y_bot): Standart görünüm için sırt Y=0, dişler yukarı doğru pozitif kalınlık
            u_mm = round(float((y_bot[idx_c] - spine_ref_px) * ky_scale), 2)
            l_mm = round(float((y_top[idx_c] - spine_ref_px) * ky_scale), 2)
        x_mm_curve.append(x_rel_mm)
        y_upper_mm_curve.append(u_mm)
        y_lower_mm_curve.append(l_mm)

    vis_meta: Dict[str, Any] = {
        "roi_box": (x1, y1, x2, y2),
        "shoulder_x": x1 + x_start + shoulder_offset,
        "key_start_x": x1 + x_start,
        "key_end_x": x1 + x_end,
        "teeth_on_top": teeth_on_top,
        "valley_img_pts": valley_img_pts,
        "total_length_mm": total_length_mm,
        "bow_height_mm": bow_height_mm,
        "blade_length_mm": blade_length_mm,
        "blade_width_mm": blade_width_mm,
        "remaining_heights_mm": remaining_heights_mm,
        "pitch_values_mm": pitch_values_mm,
        "kx_scale": round(kx_scale, 6),
        "ky_scale": round(ky_scale, 6),
        "profile_outline_mm": {
            "x_mm": x_mm_curve,
            "y_upper_mm": y_upper_mm_curve,
            "y_lower_mm": y_lower_mm_curve,
        },
    }

    return raw_depths_mm, valley_positions_mm, edges, detected_brand, vis_meta


def _render_annotated_proof_base64(
    img: np.ndarray,
    card_pts: np.ndarray,
    k: float,
    card_px_width: float,
    effective_profile: str,
    bitting_code: Optional[str],
    raw_depths_mm: List[float],
    vis_meta: Dict[str, Any],
) -> str:
    """
    Kullanıcının çektiği fotoğrafın üzerine:
    1. Anahtarın gerçek görüntüsüne zoom yaparak,
    2. Omuz (X=0), toplam boy, namlu boyu, namlu yüksekliği,
    3. Her dişin omuzdan yatay mesafesi (X), kesim derinliği (d) ve kalan et kalınlığını (h)
    işleyerek görsel kanıt görüntüsü (Base64 JPEG) üretir.
    """
    canvas = img.copy()
    try:
        x1, y1, x2, y2 = vis_meta["roi_box"]
        shoulder_x = vis_meta["shoulder_x"]
        key_start_x = vis_meta.get("key_start_x", x1)
        key_end_x = vis_meta.get("key_end_x", x2)
        teeth_on_top: bool = vis_meta["teeth_on_top"]
        valley_pts = vis_meta["valley_img_pts"]
        rem_heights = vis_meta.get("remaining_heights_mm", [])
        valley_x_mm = [
            round((pt[0] - shoulder_x) * vis_meta.get("kx_scale", k), 2)
            for pt in valley_pts
        ]

        # Anahtarın yakın çekim bölgesini önce kırpıp 2.2x büyütelim ki yazılar ve çizgiler kristal netliğinde olsun
        h_img, w_img = canvas.shape[:2]
        roi_w = max(1, x2 - x1)
        roi_h = max(1, y2 - y1)
        pad_x = max(45, int(roi_w * 0.16))
        pad_y = max(65, int(roi_h * 0.85))

        crop_x1 = max(0, x1 - pad_x)
        crop_y1 = max(0, y1 - pad_y)
        crop_x2 = min(w_img, x2 + pad_x)
        crop_y2 = min(h_img, y2 + pad_y)

        crop = canvas[crop_y1:crop_y2, crop_x1:crop_x2].copy()
        zoom_scale = 2.4 if crop.shape[1] < 420 else 1.5
        zoomed = cv2.resize(
            crop,
            (0, 0),
            fx=zoom_scale,
            fy=zoom_scale,
            interpolation=cv2.INTER_CUBIC,
        )

        def tx(px: int) -> int:
            return int(round((px - crop_x1) * zoom_scale))

        def ty(py: int) -> int:
            return int(round((py - crop_y1) * zoom_scale))

        zh, zw = zoomed.shape[:2]
        sx = tx(shoulder_x)
        ks_x = tx(key_start_x)
        ke_x = tx(key_end_x)
        ky1 = ty(y1 + 12)
        ky2 = ty(y2 - 12)

        # Toplam anahtar boyu yatay ölçüm oku (üstte/altta)
        total_len_mm = vis_meta.get("total_length_mm", 0.0)
        blade_len_mm = vis_meta.get("blade_length_mm", 0.0)
        blade_w_mm = vis_meta.get("blade_width_mm", 0.0)

        dim_y = max(24, ky1 - 28) if not teeth_on_top else min(zh - 22, ky2 + 32)
        cv2.line(zoomed, (ks_x, dim_y), (ke_x, dim_y), (255, 200, 60), 2)
        cv2.line(zoomed, (ks_x, dim_y - 6), (ks_x, dim_y + 6), (255, 200, 60), 2)
        cv2.line(zoomed, (ke_x, dim_y - 6), (ke_x, dim_y + 6), (255, 200, 60), 2)
        cv2.putText(
            zoomed,
            f"Toplam: {total_len_mm:.2f}mm | Namlu: {blade_len_mm:.2f}mm | En: {blade_w_mm:.2f}mm",
            (max(8, ks_x), max(16, dim_y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 230, 110),
            1,
            cv2.LINE_AA,
        )

        # Omuz (X=0) referans çizgisi
        cv2.line(zoomed, (sx, max(10, ky1 - 18)), (sx, min(zh - 10, ky2 + 18)), (70, 70, 255), 2)
        cv2.putText(
            zoomed,
            "X=0 (Omuz)",
            (max(6, sx - 38), min(zh - 10, ky2 + 34) if not teeth_on_top else max(18, ky1 - 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (110, 110, 255),
            2,
            cv2.LINE_AA,
        )

        # Her diş noktasında hem Kesim Derinliği (Sarı) hem Kalan Kalınlık (Yeşil) gösterimi
        for idx, (pt, d_mm) in enumerate(zip(valley_pts, raw_depths_mm), start=1):
            vx, vy, by, spy = tx(pt[0]), ty(pt[1]), ty(pt[2]), ty(pt[3])
            rem_mm = rem_heights[idx - 1] if idx - 1 < len(rem_heights) else 0.0
            x_mm = valley_x_mm[idx - 1] if idx - 1 < len(valley_x_mm) else 0.0

            # Sırttan diş dibine kalan et kalınlığı (Yeşil çizgi)
            cv2.line(zoomed, (vx - 2, spy), (vx - 2, vy), (80, 240, 120), 2)
            # Kesilmemiş hizadan diş dibine kesim derinliği (Sarı/Turuncu çizgi)
            cv2.line(zoomed, (vx + 2, by), (vx + 2, vy), (0, 215, 255), 2)
            cv2.circle(zoomed, (vx, vy), 5, (0, 255, 255), -1)
            cv2.circle(zoomed, (vx, vy), 5, (15, 23, 42), 1)

            stagger = ((idx - 1) % 2) * 28
            lbl_y = (ky1 - 16 - stagger) if teeth_on_top else (ky2 + 22 + stagger)
            lbl_y = max(22, min(zh - 18, lbl_y))
            cv2.putText(
                zoomed,
                f"D{idx} X:{x_mm:.1f}mm",
                (max(4, vx - 34), lbl_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                zoomed,
                f"-{d_mm:.2f} / K:{rem_mm:.2f}",
                (max(4, vx - 38), min(zh - 5, lbl_y + 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

        code_txt = bitting_code if bitting_code else "Yok (Milimetrik CNC)"
        key_header = f"MARKA: {effective_profile} | BITTING: {code_txt}"

        banner_h = 56
        banner = np.full((banner_h, zw, 3), (15, 23, 42), dtype=np.uint8)
        cv2.putText(
            banner,
            f"Ref Kart: 85.60x53.98mm ({card_px_width:.0f}px) | 1px = {k:.4f}mm",
            (10, 21),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (80, 240, 120),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            banner,
            key_header,
            (10, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 220, 80),
            2,
            cv2.LINE_AA,
        )
        zoomed_with_banner = np.vstack([banner, zoomed])

        ok, enc = cv2.imencode(
            ".jpg", zoomed_with_banner, [int(cv2.IMWRITE_JPEG_QUALITY), 92]
        )
        if not ok:
            return ""
        return base64.b64encode(enc.tobytes()).decode("ascii")
    finally:
        canvas[:] = 0


def match_bitting_profile(
    raw_depths_mm: List[float], profile_type: str = "YALE-5"
) -> Tuple[str, Optional[str]]:
    """
    - Veritabanında resmi fabrika derinlik tablosu yalnızca YALE-5 ve YALE-6 için mevcuttur.
    - BAY-TEC, KALE, ITO, BKS veya AUTO gibi fabrika tablosu veritabanında bulunmayan
      markalarda uydurma bitting kodu ÜRETİLMEZ; ('RAW_MODE', None) döndürülerek
      doğrudan milimetrik CNC/kumpas ölçümleri kullanılır.
    """
    norm_profile = profile_type.strip().upper()

    if norm_profile in STANDARD_PROFILES:
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

    return "RAW_MODE", None


def analyze_key_image(
    raw_bytes: bytes,
    profile_type: str = "YALE-5",
    yolo_weights_path: Optional[str] = None,
    img_ref_holder: Optional[List[np.ndarray]] = None,
) -> Dict[str, Any]:
    """
    Ana In-Memory Görüntü Analiz Boru Hattı:
    1. raw_bytes -> np.frombuffer -> cv2.imdecode (Diske ASLA kaydedilmez).
    2. ISO/IEC 7810 Referans Kart kalibrasyonu (yatay kx ve dikey ky ölçekleme).
    3. OpenCV + SciPy ile eğimden bağımsız (sırt referanslı) diş, kalan et ve yatay mesafe ölçümü.
    4. Yalnızca veritabanında tablosu olan profiller için Bitting, diğerleri için RAW_MODE.
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

        # Dikey perspektif telafisi için kartın dikey piksel yüksekliğinden ky ölçeğini hesapla
        tl, tr, br, bl = card_pts
        w_px = float(np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
        h_px = float(np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0
        card_h_px = min(w_px, h_px)
        ky = (ISO_CARD_HEIGHT_MM / card_h_px) if card_h_px > 0 else k

        raw_depths_mm, valley_positions_mm, _, detected_brand, vis_meta = (
            extract_key_profile_and_valleys(
                img, key_bbox, k, profile_type=profile_type, ky=ky
            )
        )

        effective_profile = profile_type
        if profile_type.strip().upper() in {"AUTO", "OTOMATIK", "OTOMATİK"}:
            effective_profile = detected_brand if detected_brand else "STANDART-5P"

        mode, bitting_code = match_bitting_profile(
            raw_depths_mm, profile_type=effective_profile
        )

        annotated_photo_b64 = _render_annotated_proof_base64(
            img=img,
            card_pts=card_pts,
            k=k,
            card_px_width=card_px_width,
            effective_profile=effective_profile,
            bitting_code=bitting_code,
            raw_depths_mm=raw_depths_mm,
            vis_meta=vis_meta,
        )

        return {
            "profile_type": effective_profile,
            "detected_brand": detected_brand,
            "mode": mode,
            "bitting_code": bitting_code,
            "raw_depths_mm": raw_depths_mm,
            "valley_positions_mm": valley_positions_mm,
            "remaining_heights_mm": vis_meta["remaining_heights_mm"],
            "pitch_values_mm": vis_meta["pitch_values_mm"],
            "total_length_mm": vis_meta["total_length_mm"],
            "bow_height_mm": vis_meta["bow_height_mm"],
            "blade_length_mm": vis_meta["blade_length_mm"],
            "blade_width_mm": vis_meta["blade_width_mm"],
            "profile_outline_mm": vis_meta["profile_outline_mm"],
            "scale_factor_k": round(float(k), 6),
            "card_pixel_width": round(float(card_px_width), 2),
            "homography_matrix": homography_matrix.tolist(),
            "detector": detector_used,
            "annotated_photo_b64": annotated_photo_b64,
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
        depths_mm = [1.50, 0.50, 2.00, 1.00, 2.50]

    k = ISO_CARD_WIDTH_MM / float(card_pixel_width)
    card_pixel_height = int(round(ISO_CARD_HEIGHT_MM / k))

    canvas_h = max(900, card_pixel_height + 420)
    canvas_w = max(1100, card_pixel_width + 200)
    canvas = np.full((canvas_h, canvas_w, 3), 255, dtype=np.uint8)

    card_x1, card_y1 = 80, 50
    card_x2 = card_x1 + card_pixel_width
    card_y2 = card_y1 + card_pixel_height
    cv2.rectangle(canvas, (card_x1, card_y1), (card_x2, card_y2), (30, 30, 30), -1)

    blade_y_top = card_y2 + 110
    blade_height_px = int(round(8.5 / k))
    blade_y_bot = blade_y_top + blade_height_px

    bow_x1 = 80
    shoulder_x = 220
    bow_y1 = blade_y_top - int(round(4.0 / k))
    bow_y2 = blade_y_bot + int(round(4.0 / k))

    cv2.rectangle(canvas, (bow_x1, bow_y1), (shoulder_x, bow_y2), (20, 20, 20), -1)

    pitch_px = int(round(4.5 / k))
    first_offset_px = int(round(4.0 / k))
    blade_length_px = first_offset_px + len(depths_mm) * pitch_px + int(round(4.0 / k))
    blade_x2 = shoulder_x + blade_length_px
    cv2.rectangle(canvas, (shoulder_x, blade_y_top), (blade_x2, blade_y_bot), (20, 20, 20), -1)

    if dimple_mode:
        center_y = (blade_y_top + blade_y_bot) // 2
        for idx in range(4):
            cx = shoulder_x + first_offset_px + idx * pitch_px
            cv2.circle(canvas, (cx, center_y), max(6, int(round(1.0 / k))), (255, 255, 255), -1)
    else:
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
