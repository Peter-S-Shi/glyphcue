"""Subtle completion chime for genuine OCR job completion, per M12 UX requirements."""
from __future__ import annotations

import io
import math
import struct
import sys
import wave

_CHIME_WAV_BYTES: bytes | None = None


def _synthesize_hotel_bell_wav() -> bytes:
    """Synthesizes a short, gentle hotel desk bell 'ding' sound (approx. 250ms).

    Uses pure standard library (wave, math, struct) to generate a high fundamental
    frequency (~1568 Hz, G6) with harmonic shimmer and exponential decay.
    """
    buf = io.BytesIO()
    sample_rate = 44100
    duration = 0.25  # 250ms
    freq = 1568.0  # G6 pleasant bell chime
    n_samples = int(sample_rate * duration)
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            decay = math.exp(-12.0 * t)
            # Fundamental + overtone bell strike
            val = 0.75 * math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(
                2 * math.pi * freq * 2.756 * t
            )
            sample = int(32767.0 * 0.22 * decay * val)
            frames.extend(struct.pack("<h", sample))
        wav.writeframes(frames)
    return buf.getvalue()


def play_ocr_completion_chime() -> None:
    """Plays a short, low-disturbance single chime on genuine OCR job success.

    Fail-soft: wrapped in try-except so it never interrupts the UI or raises exceptions.
    """
    global _CHIME_WAV_BYTES
    try:
        if sys.platform == "win32":
            import winsound

            if _CHIME_WAV_BYTES is None:
                _CHIME_WAV_BYTES = _synthesize_hotel_bell_wav()
            winsound.PlaySound(_CHIME_WAV_BYTES, winsound.SND_MEMORY | winsound.SND_ASYNC)
        else:
            from PySide6.QtWidgets import QApplication

            QApplication.beep()
    except Exception:
        pass
