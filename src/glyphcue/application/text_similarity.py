from __future__ import annotations


def _levenshtein_distance(a: str, b: str) -> int:
    """Plain Levenshtein edit distance, character by character.

    No tokenization of any kind (whitespace or otherwise) -- this is
    the same reason M1's `_character_overlap_length` and M3's CER
    benchmark both operate per-character: it is the one comparison
    method that works identically for English, Chinese, and Japanese,
    since CJK text has no spaces to split on.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current_row.append(
                min(
                    previous_row[j] + 1,  # deletion
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j - 1] + cost,  # substitution
                )
            )
        previous_row = current_row
    return previous_row[-1]


def character_similarity(a: str, b: str) -> float:
    """1.0 = identical, 0.0 = maximally different, character-level.

    `1 - (Levenshtein distance / max(len(a), len(b)))`: a *symmetric*
    similarity (a and b are interchangeable), normalized by the longer
    of the two strings. This is deliberately a different formula from
    M3's CER (`benchmarks/ocr_runtime_selection/cer.py`), which is
    *asymmetric* -- it normalizes by the reference string's length only
    (`distance / len(reference)`), because CER specifically measures
    error relative to a known-correct ground truth, not similarity
    between two peer readings. Do not conflate the two: this function
    has no "reference" argument because it doesn't need one -- it is
    used for grouping/voting among peer OCR readings, not for scoring
    against ground truth (see `benchmarks/multi_frame_consensus/` for
    the CER-based evaluation, which uses the real CER formula).
    Deliberately not based on whitespace tokenization, so it behaves
    identically for English, Chinese, and Japanese text.
    """
    if a == b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1 - (_levenshtein_distance(a, b) / longest)
