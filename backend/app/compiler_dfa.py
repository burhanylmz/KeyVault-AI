"""
FAZ 2: Biçimsel Diller, MACS DFA Otomatı ve CNC G-Code Derleyicisi (compiler_dfa.py)
- Python `re` ile bitting format doğrulaması: ^[1-9](-[1-9]){4,5}$
- MACS_DFA Sınıfı: Komşu iki diş farkı 4'ü aşarsa (|d_i - d_{i+1}| > 4) q_reject durumuna geçerek üretimi reddeder.
- GCodeCompiler Sınıfı: Standart Bitting kodunu veya RAW_MODE milimetrik derinliklerini CNC .gcode komutlarına (G21, G90, G00 X0.0 Y0.0, G01 X... Y-... F120, M30) derler.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.vision_pipeline import YALE_DEPTH_TABLE_MM

BITTING_REGEX = re.compile(r"^[1-9](-[1-9]){4,5}$")


def validate_bitting_regex(bitting_code: str) -> bool:
    """Bitting şifresinin biçimsel dil kurallarına (^[1-9](-[1-9]){4,5}$) uygunluğunu doğrular."""
    if not isinstance(bitting_code, str):
        return False
    return bool(BITTING_REGEX.match(bitting_code.strip()))


class MACS_DFA:
    """
    Maximum Adjacent Cut Specification (MACS) Deterministik Sonlu Otomatı (DFA).
    Tanım: M = (Q, Sigma, delta, q_start, F)
    - Q = {q_start, q_1, ..., q_9, q_reject}
    - Sigma = {1, 2, 3, 4, 5, 6, 7, 8, 9}
    - Komşu iki diş derinlik kodu farkı |d_i - d_{i+1}| > macs_limit (4) ise
      durum q_reject (yutucu red durumu) olur.
    """

    def __init__(self, macs_limit: int = 4) -> None:
        self.macs_limit: int = macs_limit
        self.current_state: str = "q_start"
        self.trace: List[Dict[str, Any]] = []
        self.violation_detail: Optional[str] = None

    def reset(self) -> None:
        self.current_state = "q_start"
        self.trace = []
        self.violation_detail = None

    def transition(self, prev_digit: Optional[int], next_digit: int, step_idx: int) -> str:
        """DFA durum geçiş fonksiyonu delta(q, sigma)."""
        if self.current_state == "q_reject":
            return "q_reject"

        if next_digit < 1 or next_digit > 9:
            self.current_state = "q_reject"
            self.violation_detail = f"Adım {step_idx}: Geçersiz alfabe sembolü ({next_digit})."
            return self.current_state

        if prev_digit is None:
            self.current_state = f"q_{next_digit}"
            self.trace.append(
                {
                    "step": step_idx,
                    "input": next_digit,
                    "diff": 0,
                    "from_state": "q_start",
                    "to_state": self.current_state,
                }
            )
            return self.current_state

        diff = abs(prev_digit - next_digit)
        from_state = self.current_state
        if diff > self.macs_limit:
            self.current_state = "q_reject"
            self.violation_detail = (
                f"MACS İhlali (Adım {step_idx}): |{prev_digit} - {next_digit}| = {diff} > {self.macs_limit}"
            )
        else:
            self.current_state = f"q_{next_digit}"

        self.trace.append(
            {
                "step": step_idx,
                "input": next_digit,
                "diff": diff,
                "from_state": from_state,
                "to_state": self.current_state,
            }
        )
        return self.current_state

    def validate(self, bitting_code: str) -> bool:
        """
        Verilen bitting kodunu önce Regex, ardından MACS DFA durum geçişleriyle doğrular.
        Geçerliyse True (q_accept), geçersizse False (q_reject) döndürür.
        """
        self.reset()
        if not validate_bitting_regex(bitting_code):
            self.current_state = "q_reject"
            self.violation_detail = f"Regex format hatası: '{bitting_code}' (Beklenen: ^[1-9](-[1-9]){{4,5}}$)"
            return False

        digits = [int(part) for part in bitting_code.strip().split("-")]
        prev_digit: Optional[int] = None
        for idx, digit in enumerate(digits, start=1):
            state = self.transition(prev_digit, digit, idx)
            prev_digit = digit
            if state == "q_reject":
                return False

        return self.current_state != "q_reject"

    def validate_with_details(self, bitting_code: str) -> Dict[str, Any]:
        is_valid = self.validate(bitting_code)
        return {
            "is_valid": is_valid,
            "final_state": self.current_state,
            "status_label": "GEÇERLİ (q_accept)" if is_valid else "GEÇERSİZ (q_reject)",
            "macs_limit": self.macs_limit,
            "violation": self.violation_detail,
            "trace": self.trace,
        }

    def validate_raw_depths(self, raw_depths_mm: List[float], max_diff_mm: float = 2.0) -> bool:
        """RAW_MODE milimetrik derinlikler için komşu çukur farkı kontrolü (4 adım * 0.5mm = 2.0mm)."""
        self.reset()
        if not raw_depths_mm or len(raw_depths_mm) < 4:
            self.current_state = "q_reject"
            self.violation_detail = "Yetersiz çukur sayısı."
            return False

        for i in range(len(raw_depths_mm) - 1):
            diff = abs(raw_depths_mm[i] - raw_depths_mm[i + 1])
            if diff > max_diff_mm + 1e-6:
                self.current_state = "q_reject"
                self.violation_detail = (
                    f"RAW MACS İhlali: |{raw_depths_mm[i]:.2f} - {raw_depths_mm[i+1]:.2f}| = {diff:.2f}mm > {max_diff_mm:.2f}mm"
                )
                return False

        self.current_state = "q_accept_raw"
        return True


class GCodeCompiler:
    """
    Hem standart Bitting kodunu (örn. '3-1-4-2-5') hem de RAW_MODE milimetrik
    derinlik dizisini ISO CNC G-Code (.gcode) komutlarına derler.
    """

    def __init__(
        self,
        first_pin_offset_mm: float = 4.0,
        pin_pitch_mm: float = 4.5,
        feed_rate: int = 120,
    ) -> None:
        self.first_pin_offset_mm = first_pin_offset_mm
        self.pin_pitch_mm = pin_pitch_mm
        self.feed_rate = feed_rate

    def bitting_to_depths_mm(self, bitting_code: str) -> List[float]:
        if not validate_bitting_regex(bitting_code):
            raise ValueError(f"Geçersiz bitting formatı: {bitting_code}")
        digits = [int(x) for x in bitting_code.strip().split("-")]
        return [round(YALE_DEPTH_TABLE_MM[d], 2) for d in digits]

    def compile(
        self,
        bitting_code: Optional[str] = None,
        raw_depths_mm: Optional[List[float]] = None,
        profile_type: str = "YALE-5",
        valley_positions_mm: Optional[List[float]] = None,
    ) -> str:
        """
        Standart bitting veya RAW_MODE derinliklerini CNC G-Code metnine dönüştürür.
        MACS DFA kuralını ihlal eden anahtarların üretimini reddeder.
        """
        dfa = MACS_DFA()
        mode = "RAW_MODE"

        if bitting_code:
            if not dfa.validate(bitting_code):
                raise ValueError(
                    f"MACS DFA Üretim Reddi ({dfa.current_state}): {dfa.violation_detail}"
                )
            depths = self.bitting_to_depths_mm(bitting_code)
            mode = "STANDARD"
        elif raw_depths_mm and len(raw_depths_mm) >= 4:
            depths = [round(float(d), 2) for d in raw_depths_mm]
            mode = "RAW_MODE"
        else:
            raise ValueError("G-Code derlemesi için geçerli bitting_code veya raw_depths_mm gereklidir.")

        if valley_positions_mm and len(valley_positions_mm) == len(depths):
            x_positions = [round(float(x), 2) for x in valley_positions_mm]
        else:
            x_positions = [
                round(self.first_pin_offset_mm + idx * self.pin_pitch_mm, 2)
                for idx in range(len(depths))
            ]

        lines: List[str] = [
            "; === KeyVault-AI Otomatik CNC Anahtar Kesim Programı ===",
            f"; Profil: {profile_type} | Mod: {mode}",
            f"; Bitting: {bitting_code if bitting_code else 'RAW_MODE'}",
            f"; Derinlikler (mm): {', '.join(f'{d:.2f}' for d in depths)}",
            "G21 ; Milimetrik birim sistemi",
            "G90 ; Mutlak koordinat modu",
            "G00 X0.0 Y0.0 ; Omuz (X=0) referans noktasına konumlan",
        ]

        half_flat = 0.60
        for idx, (x_mm, depth_mm) in enumerate(zip(x_positions, depths), start=1):
            x_entry = max(0.0, round(x_mm - half_flat, 2))
            x_exit = round(x_mm + half_flat, 2)
            lines.append(f"; --- Diş {idx}: X={x_mm:.2f}mm, Derinlik={depth_mm:.2f}mm ---")
            lines.append(f"G01 X{x_entry:.2f} Y0.00 F{self.feed_rate}")
            lines.append(f"G01 X{x_mm:.2f} Y-{depth_mm:.2f} F{self.feed_rate}")
            lines.append(f"G01 X{x_exit:.2f} Y0.00 F{self.feed_rate}")

        lines.append("G00 X0.0 Y0.0 ; Güvenli başlangıç noktasına dön")
        lines.append("M30 ; Program sonu")
        return "\n".join(lines) + "\n"
