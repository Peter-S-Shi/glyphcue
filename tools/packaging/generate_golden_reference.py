"""Generates the golden reference OCR output for the synthetic video fixture.

Executes in the trusted DirectML development environment against the deterministic
synthetic test fixture and outputs docs/m13_synthetic_fixture_golden.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2

from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine
from tools.packaging.generate_synthetic_fixture import (
    FIXTURE_FPS,
    FIXTURE_TOTAL_FRAMES,
    generate_fixture,
)

GOLDEN_OUTPUT_PATH = Path("docs/m13_synthetic_fixture_golden.json")


def generate_golden_reference(output_file: Path | str = GOLDEN_OUTPUT_PATH) -> dict:
    """Generate golden reference OCR evaluation from the synthetic fixture."""
    dest = Path(output_file)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp_fixture = Path("temp_golden_fixture.mp4")
    size, sha256 = generate_fixture(tmp_fixture)

    try:
        engine = DirectMlOcrEngine()
        engine.initialize()

        cap = cv2.VideoCapture(str(tmp_fixture))
        frame_idx = 0
        raw_detections = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            timestamp_ms = int((frame_idx / FIXTURE_FPS) * 1000)
            regions = engine.recognize(frame)
            if regions:
                for r in regions:
                    raw_detections.append(
                        {
                            "frame_idx": frame_idx,
                            "timestamp_ms": timestamp_ms,
                            "text": r.text,
                            "confidence": round(float(r.confidence), 4),
                        }
                    )
            frame_idx += 1
        cap.release()

        # Aggregate raw detections into reconstructed contiguous cue intervals
        cues = []
        if raw_detections:
            current_text = raw_detections[0]["text"]
            current_start_ms = raw_detections[0]["timestamp_ms"]
            current_confidences = [raw_detections[0]["confidence"]]

            for d in raw_detections[1:]:
                if d["text"] == current_text:
                    current_confidences.append(d["confidence"])
                else:
                    # End previous cue
                    cues.append(
                        {
                            "cue_index": len(cues) + 1,
                            "start_ms": current_start_ms,
                            "end_ms": d["timestamp_ms"],
                            "text": current_text,
                            "avg_confidence": round(sum(current_confidences) / len(current_confidences), 4),
                        }
                    )
                    current_text = d["text"]
                    current_start_ms = d["timestamp_ms"]
                    current_confidences = [d["confidence"]]

            # Append final cue
            final_end_ms = int((FIXTURE_TOTAL_FRAMES / FIXTURE_FPS) * 1000)
            cues.append(
                {
                    "cue_index": len(cues) + 1,
                    "start_ms": current_start_ms,
                    "end_ms": final_end_ms,
                    "text": current_text,
                    "avg_confidence": round(sum(current_confidences) / len(current_confidences), 4),
                }
            )

        golden_record = {
            "schema_version": "1.0.0",
            "fixture_file": "glyphcue_synthetic_fixture_v1.mp4",
            "fixture_sha256": sha256,
            "fixture_size_bytes": size,
            "total_frames_evaluated": frame_idx,
            "reconstructed_cues_count": len(cues),
            "reconstructed_cues": cues,
            "sample_frame_detections": [
                d for d in raw_detections if d["frame_idx"] in (10, 30, 50)
            ],
        }

        dest.write_text(json.dumps(golden_record, indent=2), encoding="utf-8")
        return golden_record
    finally:
        if tmp_fixture.exists():
            tmp_fixture.unlink()


if __name__ == "__main__":
    out_target = Path(sys.argv[1]) if len(sys.argv) > 1 else GOLDEN_OUTPUT_PATH
    record = generate_golden_reference(out_target)
    print(f"Golden reference generated at: {out_target}")
    print(f"Reconstructed cues count: {record['reconstructed_cues_count']}")
    for cue in record["reconstructed_cues"]:
        print(f"  Cue {cue['cue_index']}: [{cue['start_ms']}ms - {cue['end_ms']}ms] {cue['text']} (conf: {cue['avg_confidence']})")
