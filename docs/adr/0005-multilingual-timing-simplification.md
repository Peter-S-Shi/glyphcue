# ADR 0005: Multilingual Timing Simplification — Shared Cue-Level Timing

**Status:** Accepted
**Date:** 2026-08-31 (Milestone 10 ADR closure; decision originates from ROADMAP.md section 4 at roadmap start, exercised starting Milestone 6)
**Milestone:** ROADMAP.md section 4 (domain simplification, stated before Milestone 0) / Milestone 6 — Multilingual Track Group Reconstruction (first exercise)

## Context

A multilingual Track Group can, in principle, have each language's on-screen text appear and disappear on its own independent schedule — one Track Group's Chinese line ending half a second before its English line, for instance. Modeling that generally requires either per-language independent timing on each Cue, or a language-cue alignment graph relating layers across time. Both are real engineering investments: more domain complexity, more edge cases in reconstruction, and a materially harder QA review UI (independent per-layer timelines instead of one shared one).

## Chosen simplification

**Timing belongs to the Cue, not to individual Language Layers.** A Cue has one `start_time`/`end_time`; every `LanguageLayer` inside it inherits that timing. V1 does not implement per-language independent timing, a language-cue alignment graph, layer timing override, or one-to-many multilingual timing relations.

```text
Cue
├─ start_time
├─ end_time
└─ language_layers[1..N]
```

## Why

ROADMAP.md section 4 states the material basis for this: within a Track Group, language layers were observed to appear together and disappear together in the representative target material this product is scoped against, with rare missing/asymmetric layers treated as degraded/low-quality source conditions rather than evidence of a genuinely independent per-language schedule.

Given that material profile, per-language independent timing would add real domain and UI complexity (an alignment graph, per-layer timeline review) to solve a problem the target material doesn't actually present — complexity the Explainability Ceiling and Stop-Building Rule (`GLYPHCUE_PRODUCT_ARCHITECTURE.md`) both weigh against building speculatively. The M6 layer-separation algorithm (ADR pending real name — `assign_observations_to_languages`, documented in `docs/multilingual/track_group_reconstruction.md`) reuses M5's `group_into_state_runs` UNCHANGED specifically because this simplification holds: one physical video frame is one OCR-triggering event regardless of how many languages are read from it, so every language layer sees identical state-boundary evidence for a given frame. Rejecting the simplification would have forced M6 to re-derive its own per-language boundary logic instead of reusing M5's.

## What was rejected, and why

- **Per-language independent timing** (each Language Layer carries its own `start_time`/`end_time`) — rejected: not supported by the observed material profile, and would require M6's grouping to diverge from M5's shared state-run logic per language, undoing the direct-reuse relationship described above.
- **A language-cue alignment graph** (explicit one-to-many timing relations between layers) — rejected as strictly more general than the target material needs; a generalization built for a problem that hasn't been observed is exactly the kind of complexity the Stop-Building Rule rejects by default.
- **Layer timing override** (an escape hatch letting one layer deviate from the Cue's timing in specific cases) — rejected for V1 as an unnecessary partial version of full per-language timing, adding a rarely-used code path and UI affordance for a case the current material profile doesn't present.

## Known cost of the choice (accepted, not ignored)

- **This is a scoped claim about the supported material profile, not a universal claim about all burned-in multilingual subtitles** (ROADMAP.md section 4 states this explicitly). Source material where language layers genuinely have independent schedules is out of V1's supported profile; MultilingualDiagnostics' `missing_languages`/`ambiguous_languages` surface a real timing/evidence mismatch as a diagnostic when it occurs, rather than silently misrepresenting it, but V1 does not attempt to *model* an independent schedule when one is genuinely present in the source.
- **No dedicated benchmark or evaluation artifact backs the "representative target samples" claim.** Unlike ADR 0001/0002/0003 (each backed by a specific benchmark script and results file), this decision's evidentiary basis is ROADMAP.md section 4's own stated observation about the target material profile — it is a product-scoping decision made before Milestone 0, not a benchmarked comparison of "with alignment graph" vs. "without." This is recorded here as an honest limitation of this ADR's evidence, not papered over: if a future representative sample surfaces a genuinely independent-schedule case, that would be new evidence against this simplification, not something already ruled out by existing data.

## What remains swappable

The `Cue`/`LanguageLayer` domain model does not structurally forbid adding per-language timing later — it would be a new domain capability (a schema/model change), not a reversal of an architectural boundary, so nothing about M5/M6's current reuse relationship needs to be undone to revisit this if real evidence later justified it.

## What evidence supported this choice

ROADMAP.md section 4's stated observation about the representative target material profile (no separate benchmark artifact — see "Known cost" above for this limitation). The downstream reuse consequence (M6 reusing M5's `group_into_state_runs` unchanged) is verified by `docs/multilingual/track_group_reconstruction.md` and `benchmarks/multilingual_reconstruction/`.
