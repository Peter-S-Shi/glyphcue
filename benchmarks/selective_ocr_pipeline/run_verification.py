"""Milestone 4 selective-vs-dense OCR pipeline verification, on the real
PaddleOcrEngine (V1 default runtime, see docs/adr/0001-ocr-runtime-selection.md).

Run manually (not part of CI/pytest -- requires the optional `[ocr]`
extra): `python benchmarks/selective_ocr_pipeline/run_verification.py`

Proves, on a real generated fixture and a real OCR engine (not
FakeOcrEngine): selective OCR performs materially fewer OCR calls than
naive dense OCR while still capturing the fixture's real text changes as
Observations. All metrics come from PipelineMetrics, filled in by the
real `build_ocr_evidence_job` execution path -- nothing here is
estimated.

Writes results to verification_results.json next to this script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixture import SEGMENTS, generate_fixture  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine  # noqa: E402
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job  # noqa: E402
from glyphcue.application.ocr_invocation_policy import NaiveDenseOcrPolicy  # noqa: E402
from glyphcue.application.pipeline_metrics import PipelineMetrics  # noqa: E402
from glyphcue.application.processing_range import ProcessingRange  # noqa: E402
from glyphcue.domain.roi import ROI  # noqa: E402
from glyphcue.persistence.database import connect  # noqa: E402
from glyphcue.persistence.observation_repository import ObservationRepository  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "generated_fixture"
RESULTS_PATH = Path(__file__).parent / "verification_results.json"
FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def _run_job(video_path: Path, db_path: Path, *, dense: bool) -> tuple[PipelineMetrics, list]:
    engine = PaddleOcrEngine(language="en")
    conn = connect(db_path)
    repository = ObservationRepository(conn)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        FULL_FRAME_ROI,
        engine,
        repository,
        metrics,
        policy=NaiveDenseOcrPolicy() if dense else None,
    )

    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(120_000)
    job.start()
    loop.exec()
    job.wait(timeout=1.0)

    observations = repository.list_all()
    return metrics, observations


def main() -> None:
    app = QApplication.instance() or QApplication([])
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    video_path = FIXTURE_DIR / "subtitle_swap.mp4"
    ground_truth = generate_fixture(video_path)
    print(f"Generated fixture: {len(ground_truth)} frames -> {video_path}")

    print("Running selective (ChangeTriggeredOcrPolicy) pipeline with real PaddleOcrEngine...")
    selective_metrics, selective_observations = _run_job(
        video_path, FIXTURE_DIR / "selective.sqlite3", dense=False
    )

    print("Running dense (NaiveDenseOcrPolicy) baseline pipeline with real PaddleOcrEngine...")
    dense_metrics, dense_observations = _run_job(
        video_path, FIXTURE_DIR / "dense.sqlite3", dense=True
    )

    results = {
        "fixture_frame_count": len(ground_truth),
        "fixture_ground_truth_segments": [
            {"start_ms": s, "end_ms": e, "text": t} for s, e, t in SEGMENTS
        ],
        "selective": {
            "frames_analyzed": selective_metrics.frames_analyzed,
            "ocr_calls": selective_metrics.ocr_calls,
            "observations_created": selective_metrics.observations_created,
            "elapsed_seconds": round(selective_metrics.elapsed_seconds, 4),
            "ocr_calls_per_minute": round(selective_metrics.ocr_calls_per_minute, 2),
            "effective_processing_speed": round(selective_metrics.effective_processing_speed, 4),
            "observed_texts": [obs.text for obs in selective_observations],
        },
        "dense": {
            "frames_analyzed": dense_metrics.frames_analyzed,
            "ocr_calls": dense_metrics.ocr_calls,
            "observations_created": dense_metrics.observations_created,
            "elapsed_seconds": round(dense_metrics.elapsed_seconds, 4),
            "ocr_calls_per_minute": round(dense_metrics.ocr_calls_per_minute, 2),
            "effective_processing_speed": round(dense_metrics.effective_processing_speed, 4),
        },
        "ocr_call_reduction_percent": round(
            100.0 * (1 - selective_metrics.ocr_calls / dense_metrics.ocr_calls), 1
        ),
    }

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
