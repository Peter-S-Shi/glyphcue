"""Character Error Rate: Levenshtein edit distance / len(reference)."""

from __future__ import annotations


def character_error_rate(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0

    previous_row = list(range(len(hypothesis) + 1))
    for i, ref_char in enumerate(reference, start=1):
        current_row = [i]
        for j, hyp_char in enumerate(hypothesis, start=1):
            cost = 0 if ref_char == hyp_char else 1
            current_row.append(
                min(
                    previous_row[j] + 1,  # deletion
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j - 1] + cost,  # substitution
                )
            )
        previous_row = current_row

    edit_distance = previous_row[-1]
    return edit_distance / len(reference)
