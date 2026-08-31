"""Milestone 6 targeted real-PaddleOCR verification: does the layer-
separation algorithm (`assign_observations_to_languages`, via the real
`reconstruct_multilingual_cues_for_track_group` seam) correctly recover
each language's own line from a real multi-region OCR read of a
genuinely multilingual visual block?

Scope, stated precisely: this is NOT a repeat of
`benchmarks/multi_frame_consensus/`'s multi-frame noise/consensus
benchmark (M6 doesn't change M5's consensus voting, so that evidence
still stands unchanged) and it deliberately does not re-run that
expensive 5-variant-per-line degradation sweep. It exercises exactly
the ONE thing M6 adds that depends on the real OCR runtime: whether
running each language's own real `PaddleOcrEngine` instance against the
SAME real multi-line image and feeding the results through the real
production `assign_observations_to_languages` +
`reconstruct_multilingual_cues_for_track_group` functions actually
separates the languages correctly, using real geometry and real (if
occasionally noisy/wrong) per-engine language tags -- not synthetic
Observations constructed by hand, which is all the pure-function unit
tests use.

Run manually (requires the `[ocr]` extra installed):
    python -m benchmarks.multilingual_reconstruction.run_evaluation
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.multilingual_reconstruction.fixture import BLOCKS, render_block
from benchmarks.ocr_runtime_selection.cer import character_error_rate
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup

_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"


def _observations_for_block(languages: tuple[str, ...], image) -> list[Observation]:
    observations: list[Observation] = []
    for language in languages:
        engine = PaddleOcrEngine(language)
        engine.initialize()
        try:
            regions = engine.recognize(image)
        finally:
            engine.shutdown()
        runtime_info = engine.runtime_info()
        for index, region in enumerate(regions):
            if not region.text:
                continue
            observations.append(
                Observation(
                    id=f"{language}-{index}",
                    text=region.text,
                    start_time=1.0,
                    end_time=1.001,
                    provenance=Provenance(
                        kind=ProvenanceKind.OCR_ENGINE, source=runtime_info.engine_name
                    ),
                    language=region.language,
                    confidence=region.confidence,
                    roi=_ROI,
                    geometry=region.geometry,
                    frame_reference="fixture@1.000000s",
                )
            )
    return observations


def run() -> dict:
    results = {}
    for block in BLOCKS:
        languages = tuple(language for language, _text, _font in block.lines)
        ground_truth_by_language = {
            language: text for language, text, _font in block.lines
        }
        image = render_block(block)
        observations = _observations_for_block(languages, image)
        track_group = TrackGroup(id=f"tg-{block.id}", roi=_ROI, languages=languages)

        cues, diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)

        per_language = {}
        if cues:
            for layer in cues[0].language_layers:
                ground_truth = ground_truth_by_language.get(layer.language, "")
                cer = character_error_rate(ground_truth, layer.text) if ground_truth else None
                per_language[layer.language] = {
                    "ground_truth": ground_truth,
                    "recovered_text": layer.text,
                    "cer": cer,
                }

        results[block.id] = {
            "languages": list(languages),
            "raw_observation_count": len(observations),
            "cue_count": len(cues),
            "missing_languages": list(diagnostics[0].missing_languages) if diagnostics else languages,
            "per_language": per_language,
        }
    return results


if __name__ == "__main__":
    results = run()
    _RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
