# GlyphCue — ROADMAP.md

**Document type:** Authoritative V1 milestone roadmap  
**Project:** GlyphCue  
**Repository:** `Peter-S-Shi/glyphcue`  
**Lifecycle phase:** Production Development in progress → Milestone 5 complete, Milestone 6 next  
**Status:** Current V1 execution roadmap  
**Last updated:** 2026-08-31

---

# 1. Purpose

This roadmap converts the accepted GlyphCue product architecture, career-evidence strategy, technology stack, and three-round prototype result into an execution sequence.

It is intentionally milestone-driven.

The roadmap does **not** reopen product discovery.

It implements the already accepted product thesis:

> **GlyphCue is a local-first difficult-subtitle reconstruction workbench that integrates mature media/OCR infrastructure, owns the product-specific orchestration, builds the hard reconstruction seams deeply, evaluates them against ground truth, routes uncertain results to human QA, and ships as a hardened Windows desktop product.**

The governing documents are:

- `GLYPHCUE_PRODUCT_ARCHITECTURE.md`
- `DESIGN.md`
- the two Grill review documents as historical decision evidence

When implementation questions arise:

- product scope comes from `GLYPHCUE_PRODUCT_ARCHITECTURE.md`;
- UI / UX comes from `DESIGN.md`;
- development order and milestone gates come from this file.

---

# 2. Roadmap Philosophy

The roadmap follows the Career-Portfolio Delta Grill sequencing:

```text
Thin Path B spine
→ early pivot to Path A
→ hard Applied AI reconstruction work
→ Path B deepening
→ evaluation/evidence closure
→ feature freeze
→ hardening
→ RC / signed release
→ portfolio packaging
```

This sequence is deliberate.

It avoids two bad extremes:

### Bad extreme A — Build Path B completely first

That would maximize architecture de-risking but delay GlyphCue's highest-value CV/OCR/multimedia evidence.

### Bad extreme B — Start with the hardest Path A algorithms immediately

That would place expensive CV/OCR work on top of an unproven canonical `Observation → Cue → QA → Export` spine.

The selected sequence validates the spine cheaply, then moves the majority of custom-engineering budget to Path A.

---

# 3. V1 Technology Baseline

The V1 technology choices are frozen at roadmap start.

## Language

**Python 3.12**

## Desktop UI

**PySide6 + Qt Widgets**

## Product-shell implementation

Expected primitives include:

- `QMainWindow`
- `QSplitter`
- Qt model/view
- purpose-built widgets
- custom delegates / painting where useful
- centralized semantic design tokens

QSS is a rendering mechanism, not the product architecture.

## Human media playback

**Qt Multimedia / QMediaPlayer**

## Algorithmic frame / timestamp access

**PyAV**

## Heavy media transforms

**Bundled, license-audited FFmpeg CLI via `QProcess`**

## Subtitle file IO

**pysubs2 behind a GlyphCue-owned format adapter**

## OCR

**GlyphCue-owned `OcrEngine` adapter**

V1 default runtime: **PaddleOCR**, chosen via benchmark evidence (Milestone 3). See `docs/adr/0001-ocr-runtime-selection.md` and `docs/benchmarks/ocr_runtime_selection.md`.

Evaluated candidates:

- RapidOCR / ONNX Runtime — rejected as V1 default (failed Japanese recognition outright), remains a legitimate future option for a lighter-weight configuration.
- PaddleOCR — chosen (perfect CER across the benchmark corpus, including Japanese).

## CPU / GPU

- CPU-only core path is mandatory.
- GPU support is optional acceleration.
- V1 acceptance must not depend on a specific GPU.

## Persistence

- SQLite
- typed Python domain objects
- repository layer
- explicit migrations
- media files remain filesystem assets

## Testing

- pytest
- deterministic fixtures
- integration tests
- evaluation corpus
- regression tests

## Packaging

Primary:

> `pyside6-deploy / Nuitka`

Hardening / RC packaging form:

> standalone directory first

Final installer:

> Inno Setup 7

PyInstaller remains a fallback if the primary deployment path produces unresolved blocking defects.

---

# 4. V1 Domain Simplification — Multilingual Timing Closed

Representative target samples have resolved the multilingual timing question for V1.

## Accepted V1 material profile

Within one Track Group:

- language layers appear together;
- language layers disappear together;
- meaningful timing skew was not observed in representative target material;
- rare missing/asymmetric layers are treated as degraded / low-quality source conditions.

## V1 model

```text
Cue
├─ start_time
├─ end_time
└─ language_layers[1..N]
```

Timing belongs to the Cue.

Language Layers inherit the Cue timing.

V1 does **not** implement:

- per-language independent timing;
- language-cue alignment graph;
- layer timing override;
- one-to-many multilingual timing relations.

This is an intentional V1 domain simplification based on the supported material profile.

It is **not** a universal claim about all burned-in multilingual subtitles.

---

# 5. Roadmap Stages

The V1 roadmap contains four execution stages.

```text
STAGE A — Canonical Spine Validation
M0–M1

STAGE B — Path A Applied AI Core
M2–M7

STAGE C — Path B Deepening + Product Completion
M8–M9

STAGE D — Evidence Closure + Shipping
M10–M13
```

The project should resist milestone inflation.

New milestones should be created only if a real dependency or acceptance gate cannot be represented cleanly inside the current structure.

---

# 6. Milestone Summary

| Milestone | Name | Primary Outcome |
|---|---|---|
| M0 | Production Foundation | Runnable production skeleton + contracts + CI |
| M1 | Thin Path B Vertical Slice | `SRT/VTT → Observation → Cue → minimal QA → non-destructive export` |
| M2 | Path A Media & Job Orchestration | Local video → PTS-correct frames + playback + ROI/range + cancelable job |
| M3 | OCR Adapter & Runtime Selection | OCR abstraction + evidence-based CPU runtime choice |
| M4 | Selective OCR Evidence Pipeline | Cheap visual gating → OCR observations with correct timestamps |
| M5 | Multi-Frame Consensus & Cue Reconstruction | CJK-aware consensus + stable cue reconstruction |
| M6 | Multilingual Track Group Reconstruction | 1…N language layers sharing Cue timing |
| M7 | Reconstruction QA & Review Priority | Production QA workspace + curated evidence + validated review routing |
| M8 | Path B CJK / Rolling Normalization Deepening | Robust multilingual/noisy caption normalization |
| M9 | V1 Product Completion & Feature Freeze | Accepted exports/workflows complete; no open feature blockers |
| M10 | Evaluation & Career Evidence Closure | Benchmark, metrics, failure report, performance evidence, ADR closure |
| M11 | Product Hardening & Full Regression | Product-quality convergence on frozen scope |
| M12 | Release Candidate & Signed Release | Clean-install accepted V1 release |
| M13 | Portfolio Packaging & Stop-Building Closure | Public technical story complete; V1 development formally stops |

---

# 7. Milestone 0 — Production Foundation

## Goal

Create the smallest production-quality skeleton capable of supporting all later milestones without prematurely building product features.

## Scope

### Repository / package structure

Establish clear separation between:

```text
ui/
application/
domain/
infrastructure/
adapters/
jobs/
persistence/
evaluation/
tests/
```

Exact folder naming may differ if the agent proposes a simpler equivalent.

Do not create abstraction layers without a concrete responsibility.

### Core domain types

Introduce the minimum types required for M1:

```text
Observation
Cue
LanguageLayer
ReviewState
Provenance
```

For V1:

```text
Cue.start_time
Cue.end_time
Cue.language_layers[]
```

Timing is Cue-level.

### Adapter boundaries

Define narrow contracts for future dependencies:

- subtitle format IO;
- OCR engine;
- media frame source;
- media transform service.

Do not implement all adapters deeply yet.

### Persistence foundation

Create:

- SQLite initialization;
- explicit migration mechanism;
- repository boundary;
- test database support.

Do not design a huge schema for future speculative features.

### Desktop shell skeleton

Implement only enough PySide6 structure to prove:

- app starts;
- three-pane shell can exist;
- theme tokens load;
- shared services can be injected;
- no production redesign of the validated shell occurs.

### Quality baseline

Set up:

- pytest;
- lint / formatting if desired;
- type checking where practical;
- CI;
- deterministic fixture folder;
- test command documented.

## Explicit non-goals

Do not implement:

- real OCR;
- real Path A frame processing;
- full Path B normalizer;
- full QA UI;
- export suite;
- fancy onboarding;
- home dashboard.

## Acceptance gate

M0 passes only when:

1. clean environment can install dependencies;
2. app launches;
3. test suite runs from one documented command;
4. canonical domain types exist;
5. adapter seams exist without leaking third-party types into domain code;
6. SQLite initializes and migrates deterministically;
7. `DESIGN.md` shell can be represented without architectural contradiction;
8. no prototype-only controls or fake metrics have entered production.

---

# 8. Milestone 1 — Thin Path B Vertical Slice

## Goal

Validate the complete canonical spine using structured timed-text input before expensive CV/OCR work begins.

Target flow:

```text
SRT/VTT
→ parse
→ Observation
→ minimal reconstruction
→ Cue
→ minimal QA
→ non-destructive export
```

This milestone must be thin.

It is **not** the full Path B implementation.

## Scope

### Format ingestion

Support at least:

- SRT
- VTT

through the format adapter.

### Observation creation

Imported raw caption cues become GlyphCue evidence objects.

Third-party `pysubs2` objects must not become canonical domain objects.

### Minimum reconstruction cases

Port / recreate the strongest seed-cleaner behaviors as tests:

- normal subtitle → unchanged;
- growing-window rolling caption;
- sliding-overlap caption;
- overlapping timing case.

Include at least one CJK fixture so the canonical spine is never Latin-only.

Do not yet solve every CJK normalization problem.

### Non-destructive contract

Production behavior must preserve:

- original input file;
- separate output;
- safe write;
- atomic finalization where appropriate.

### Minimal production QA

Implement only enough of the frozen workbench to review a reconstructed Cue:

- queue selection;
- active Cue;
- source observations;
- editable text;
- approve;
- export.

The design should already follow `DESIGN.md`.

Do not implement the entire final QA workspace.

### Minimal export

Support normalized:

- SRT
- VTT

## Acceptance gate

M1 passes only when:

1. clean SRT/VTT can be imported;
2. normal input can remain unchanged;
3. rolling fixture can reconstruct into a cleaner Cue sequence;
4. at least one CJK fixture passes without whitespace-token assumptions becoming a domain invariant;
5. original source remains untouched;
6. QA can display source evidence and reconstructed Cue;
7. approved result exports to a new file;
8. end-to-end tests cover the vertical slice;
9. no Path A dependency is required.

## Career evidence created

- canonical domain ownership;
- safe transformation contract;
- build-vs-integrate boundary;
- test-driven reconstruction behavior;
- thin vertical-slice sequencing rationale.

---

# 9. Milestone 2 — Path A Media & Job Orchestration

## Goal

Build the media systems foundation that makes Path A a real local desktop workflow.

Target flow:

```text
local video
→ playback
→ PTS-correct frame access
→ ROI / range
→ cancelable processing job
```

No production OCR accuracy claim is required yet.

## Scope

### Local media import

Support local video selection and metadata inspection.

### Human playback

Use Qt Multimedia for:

- Play / Pause;
- seek;
- cue-span replay infrastructure;
- normal audio/video playback.

### Algorithm frame access

Use PyAV for:

- stream inspection;
- decoded frames;
- timestamp / PTS access;
- frame → NumPy conversion;
- selected-range decoding.

### PTS correctness

Create explicit tests proving the code does not assume:

```text
timestamp = frame_number / fps
```

as a universal rule.

Include at least one VFR or non-trivial timestamp fixture if practical.

### ROI

Implement production ROI selection / persistence compatible with:

```text
Track Group
→ ROI
→ Language Layers 1..N
```

### Processing range

Support:

- whole media;
- selected start/end range.

Preserve source timeline by default.

### Background job boundary

Introduce production job state:

```text
Queued
Running
CancelRequested
Succeeded
Failed
Cancelled
```

Processing must not block the Qt UI thread.

### Progress

Implement truthful phase / processed-time progress for the media job.

## Acceptance gate

M2 passes only when:

1. video plays in the frozen workbench;
2. PyAV can decode the same source independently for analysis;
3. media playback and analysis timestamps can be mapped correctly;
4. ROI can be defined and restored;
5. partial range processing works;
6. a long fake/analysis job can be canceled cleanly;
7. UI remains responsive;
8. no OCR engine has leaked into the application/domain layer.

## Career evidence created

- multimedia integration;
- PTS-aware engineering;
- Qt/PyAV separation of responsibility;
- long-running job architecture;
- cancellation-safe desktop processing.

---

# 10. Milestone 3 — OCR Adapter & Runtime Selection

## Goal

Select an OCR runtime through evidence rather than preference, while freezing GlyphCue's own OCR contract.

## Scope

### `OcrEngine` contract

Create a GlyphCue-owned interface that isolates:

- initialization;
- recognition;
- supported languages/scripts;
- runtime information;
- shutdown;
- normalized errors.

Output should become GlyphCue observations, not vendor-specific objects.

### Candidates

Initial benchmark:

- RapidOCR / ONNX Runtime
- PaddleOCR

Do not expand to many candidates unless both fail a concrete requirement.

### Benchmark corpus

Use a small diagnostic set containing:

- English;
- Chinese;
- Japanese;
- bilingual crop;
- low-quality crop;
- representative subtitle styles.

### Compare

At minimum:

- text quality / CER where ground truth exists;
- CPU latency;
- startup time;
- memory;
- model/package size;
- packaging friction;
- API/error behavior;
- multilingual support.

### Decision record

Produce an ADR:

```text
Chosen runtime
Why
What was rejected
What remains swappable
What evidence supported the choice
```

## Acceptance gate

M3 passes only when:

1. at least two credible candidates were evaluated;
2. benchmark data exists;
3. CPU path is viable;
4. one runtime is selected as V1 default;
5. adapter tests prove vendor types do not leak upward;
6. engine can be replaced in tests;
7. packaging implications are documented.

## Career evidence created

- pretrained-model integration;
- evidence-based dependency selection;
- CPU-constrained AI deployment judgment;
- honest build-vs-integrate reasoning.

---

# 11. Milestone 4 — Selective OCR Evidence Pipeline

## Goal

Turn Path A media into timestamped OCR evidence efficiently.

Target flow:

```text
ROI frame stream
→ cheap change analysis
→ candidate states
→ selective OCR
→ Observation
```

## Scope

### Cheap visual analysis

Choose a simple, explainable baseline such as:

- frame difference;
- SSIM;
- perceptual similarity;
- equivalent lightweight method.

Do not over-engineer this layer.

### OCR invocation policy

OCR should run when evidence suggests subtitle state may have changed or needs confirmation.

Do not OCR every decoded frame by default.

### Observation generation

Each OCR result should preserve useful provenance:

- PTS;
- ROI;
- raw text;
- engine score;
- geometry where available;
- engine/runtime metadata;
- source frame reference or reproducible locator.

### Job integration

The pipeline must support:

- cancellation;
- progress;
- failure;
- partial working state where appropriate.

### Performance instrumentation

Collect:

- frames analyzed;
- OCR calls;
- elapsed time;
- OCR calls/minute;
- effective processing speed.

## Acceptance gate

M4 passes only when:

1. local video + ROI can produce OCR observations;
2. observation timestamps are source-correct;
3. selective OCR performs materially fewer OCR calls than naive dense OCR on representative fixture(s);
4. the pipeline remains explainable;
5. cancellation works;
6. observations are inspectable in the QA workbench;
7. performance metrics are captured honestly;
8. no novelty claim is made about commodity change detection.

## Career evidence created

- AI inference orchestration;
- performance-aware pipeline design;
- evidence capture;
- systems-level media/OCR integration.

---

# 12. Milestone 5 — Multi-Frame Consensus & Cue Reconstruction

## Goal

Build GlyphCue's highest-priority custom technical seam:

> stable Cue reconstruction from noisy neighboring OCR observations.

This milestone receives deep engineering attention.

## Scope

### Consensus baseline

Start with a simple explainable baseline.

Do not jump directly to opaque complexity.

### CJK-aware behavior

The algorithm must not depend fundamentally on whitespace tokenization.

Evaluate behavior on:

- Japanese;
- Chinese;
- Latin text.

### Reconstruction

Group temporally related observations into stable Cue candidates.

Produce:

- stable text;
- Cue start;
- Cue end;
- provenance links to supporting observations;
- reconstruction diagnostics.

### Boundary refinement

Use visual/OCR evidence to improve:

- in-point;
- out-point;
- transition rejection.

### Explainability

The owner must be able to explain:

- the consensus method;
- why it was selected;
- alternatives;
- failure modes;
- benchmark evidence.

### Evaluation

Begin measuring immediately.

Do not wait until M10.

At minimum compare:

```text
single-frame OCR baseline
vs
multi-frame reconstruction
```

on representative ground truth.

## Acceptance gate

M5 passes only when:

1. a documented consensus baseline exists;
2. multi-frame reconstruction is deterministic under tests;
3. CJK fixtures are first-class;
4. consensus performance is measured against single-frame baseline;
5. failure cases are recorded;
6. Cue provenance remains inspectable;
7. the algorithm is independently explainable;
8. additional complexity is rejected unless measured evidence justifies it.

## Career evidence created

- custom Applied AI algorithmic engineering;
- comparative evaluation;
- CJK-aware system design;
- failure analysis;
- explainability.

---

# 13. Milestone 6 — Multilingual Track Group Reconstruction

## Goal

Make multilingual burned-in subtitle reconstruction a production capability.

## Scope

### Track Group

Production model:

```text
Track Group
├─ ROI
└─ Language Layers 1..N
```

### Shared Cue timing

For V1 supported material:

```text
Cue.start
Cue.end
LanguageLayers inherit timing
```

Do not implement per-layer timing.

### Layer separation

Build an explainable method for separating / assigning multilingual text within a shared visual subtitle block.

Possible signals may include:

- vertical layout;
- script detection;
- language hints;
- line geometry;
- OCR grouping.

The implementation should use the simplest method that benchmark evidence supports.

### Missing/asymmetric layers

Rare inconsistent source material should produce:

- diagnostic;
- review flag;
- degraded/unsupported condition if necessary.

Do not expand the schema solely to support low-quality edge material.

### UI

Implement production 1…N layer presentation according to `DESIGN.md`.

## Acceptance gate

M6 passes only when:

1. two-language target material reconstructs into separate language layers;
2. three-language fixture does not break the model/UI;
3. timing is Cue-level;
4. layer ordering is stable;
5. missing/asymmetric layer behavior is explicit;
6. multilingual separation quality is evaluated;
7. no bilingual-only hard-coding remains in domain/service code.

## Career evidence created

- multilingual visual-text reasoning;
- domain simplification backed by real samples;
- difficult-subtitle reconstruction evidence;
- product-algorithm alignment.

---

# 14. Milestone 7 — Reconstruction QA & Review Priority

## Goal

Mature the frozen QA workbench into a production human-in-the-loop review system.

## Scope

### Shared QA grammar

Both paths preserve:

```text
Evidence
→ Observation
→ Cue
→ Human Review
→ Export
```

### Production UI

Implement the validated three-pane shell:

```text
Left
Structure + Queue

Center
Primary Evidence

Right
Reconstruction QA + Supporting Evidence
```

### Curated evidence

Default:

> Compact Curated Evidence

with full evidence expandable.

### Review Priority

Create a transparent ranking signal using available evidence such as:

- OCR engine score;
- cross-frame disagreement;
- timing instability;
- language-layer ambiguity;
- reconstruction inconsistency.

Do not present it as probability.

### QA interactions

Implement:

- edit text;
- timing nudge;
- Approve;
- Split;
- Merge;
- Discard;
- Previous / Next;
- Replay;
- evidence selection.

Keyboard behavior must preserve:

```text
Space = Play/Pause
Ctrl+Enter = Approve
```

### Review routing evaluation

Begin measuring whether Review Priority actually finds errors.

## Acceptance gate

M7 passes only when:

1. Path A and Path B both fit the frozen shell;
2. evidence remains visible during QA;
3. curated evidence is useful and full evidence remains accessible;
4. Review Priority is explainable;
5. no fake confidence percentage appears;
6. top-ranked cues capture more real errors than random review on benchmark data, or a documented negative result explains failure;
7. keyboard review flow is usable;
8. no full subtitle-editor scope has leaked in.

## Career evidence created

- human-in-the-loop AI;
- uncertainty-aware review;
- ranking evaluation;
- production UI/AI system integration.

---

# 15. Milestone 8 — Path B Deepening: CJK / Rolling Normalization

## Goal

Return to Path B after the main Path A evidence has matured and complete its difficult-caption value.

## Scope

### Robust parsing

Handle realistic malformed input defensively:

- ordering problems;
- overlaps;
- irregular timing;
- partial corruption where recoverable.

Do not destroy source data.

### Rolling normalization

Deepen handling of:

- growing captions;
- sliding overlap;
- repeated text;
- segmentation;
- timing normalization.

### CJK

Replace the seed cleaner's Latin-centric assumptions.

Do not freeze a specific tokenization strategy until measured.

### Conservative behavior

Normal input remains unchanged.

### Diagnostics

Explain:

- repeated growth;
- sliding overlap;
- timing collision;
- source-order warning;
- segmentation ambiguity.

## Acceptance gate

M8 passes only when:

1. representative English rolling cases pass;
2. representative CJK rolling cases pass;
3. malformed/out-of-order input has explicit safe behavior;
4. original input remains preserved;
5. clean captions remain unchanged;
6. reconstructed output is inspectable through the shared QA shell;
7. normalization quality is evaluated against ground truth fixtures.

## Career evidence created

- multilingual text-algorithm engineering;
- defensive parsing;
- conservative transformation;
- cross-path canonical-model reuse.

---

# 16. Milestone 9 — V1 Product Completion & Feature Freeze

## Goal

Complete the accepted V1 product surface and then stop adding features.

This milestone is about closure.

## Scope

### User-facing outputs

Required:

- SRT;
- VTT;
- readable transcript;
- AI-ready transcript preset.

### Thin media output

Only if the already accepted architecture and implementation cost justify it:

- soft-subtitle muxing;
- subtitle burn-in/rendering.

These remain integration features, not technical-depth targets.

### Product workflows

Complete:

- Path A import/setup/process/review/export;
- Path B import/normalize/review/export;
- processing range;
- source-protection behavior;
- job progress/cancel;
- settings required by actual implementation.

### First-launch / empty state

Implement only the minimal entry surface needed to:

- open video;
- open SRT/VTT.

Do not add a dashboard.

### Scope audit

Explicitly confirm V1 does **not** add:

- ASR;
- YouTube acquisition;
- subtitle removal/inpainting;
- long-term learning system;
- full subtitle editor;
- full video editor;
- built-in AI summary;
- batch approve without evidence;
- Path B linked video without explicit need;
- user-facing diagnostic JSON without explicit approval.

## Feature Freeze gate

M9 closes only when:

1. all accepted V1 workflows are complete;
2. no known feature blocker remains;
3. UI conforms to `DESIGN.md`;
4. automated regression suite is green;
5. known issues are classified;
6. feature freeze is formally declared;
7. any new feature now requires Stop-Building Rule justification.

## Career evidence created

- product-scope discipline;
- coherent end-to-end delivery;
- architectural restraint;
- feature-freeze governance.

---

# 17. Milestone 10 — Evaluation & Career Evidence Closure

## Goal

Turn GlyphCue from a working AI product into a credible evaluated Applied AI system.

Evaluation has been happening earlier.

M10 consolidates and closes the evidence package.

## Evaluation corpus

Target initial envelope:

> 3–5 representative videos × 2–5 minute segments

plus:

- Path B fixtures;
- public demo-safe material.

Private realistic samples may remain private.

## Required metrics

Where appropriate:

### Text
- CER;
- WER where meaningful.

### Cue recovery
- precision;
- recall.

### Timing
- start error;
- end error.

### Multilingual
- layer separation errors;
- missing / wrong layer assignment.

### Path B
- duplicate-removal correctness;
- segmentation correctness;
- timing normalization.

### Performance
- processing speed;
- frames analyzed/sec;
- OCR calls/minute;
- CPU use;
- memory where useful;
- package/runtime cost.

### Review Priority
- error-capture curve;
- top-N / top-percentile recall;
- random-review baseline;
- missed failure classes.

## Required documents

Produce:

### `EVALUATION_REPORT.md`

Must explain:

- corpus;
- ground truth;
- metrics;
- results;
- baselines;
- negative results;
- limitations.

### `FAILURE_MODE_REPORT.md`

Must include observed failures, not only theoretical ones.

### Build-vs-Integrate table

Document:

- mature dependency;
- GlyphCue orchestration;
- GlyphCue custom contribution;
- evidence / rationale.

### ADR closure

Key decisions should be captured:

- OCR runtime;
- media architecture;
- consensus approach;
- multilingual timing simplification;
- selective OCR strategy;
- packaging path.

## Acceptance gate

M10 passes only when:

1. evaluation corpus exists;
2. metrics are reproducible;
3. at least one comparative baseline exists for major custom seams;
4. negative/weak results are reported honestly;
5. failure taxonomy is grounded in observed evidence;
6. Review Priority ranking is evaluated;
7. performance evidence exists;
8. Explainability Ceiling is satisfied;
9. Must-Have Portfolio Evidence items 2–5 are substantially complete.

---

# 18. Milestone 11 — Product Hardening & Full Regression

## Goal

Converge the frozen V1 product toward release quality.

No feature expansion.

## Scope

### Automated regression

Run full suite across:

- Path A;
- Path B;
- persistence;
- jobs;
- export;
- cancellation;
- migrations;
- settings;
- packaging seams.

### Manual QA

Exercise:

- fresh install-like environment;
- representative real workflows;
- long-running jobs;
- cancel/failure;
- multilingual content;
- CJK;
- malformed subtitle import;
- export/reopen;
- keyboard flow;
- window resize/scaling.

### Performance hardening

Address:

- leaks;
- runaway memory;
- thread/process cleanup;
- repeated OCR initialization;
- slow UI update paths.

### Failure hardening

Ensure failures preserve:

- source files;
- DB integrity;
- recoverable app state;
- user-readable diagnostics.

### Packaging hardening

Primary target:

> Nuitka / pyside6-deploy standalone directory

Resolve:

- Qt plugins;
- FFmpeg path;
- OCR model assets;
- runtime DLLs;
- local resource paths.

## Acceptance gate

M11 passes only when:

1. feature freeze remains intact;
2. regression is green;
3. manual QA critical paths pass;
4. known release blockers are zero;
5. package runs on clean test environment;
6. source/data integrity is verified under failure/cancel;
7. performance is acceptable against documented baseline;
8. unresolved non-blocking issues are documented.

---

# 19. Milestone 12 — Release Candidate & Signed Release

## Goal

Produce, verify, and accept the real GlyphCue V1 release artifact.

## Scope

### RC build

Create release candidate from frozen accepted source.

### Installer

Package standalone application with:

> Inno Setup 7

### Signing

Apply the project's established Windows signing path where available.

### Clean install

Test:

- install;
- first launch;
- local media import;
- OCR runtime/model availability;
- Path A workflow;
- Path B workflow;
- export;
- uninstall / upgrade behavior where required.

### Human acceptance

The release is not accepted solely because CI is green.

Human acceptance must confirm:

- product looks like the validated GlyphCue design;
- primary workflows are understandable;
- QA is usable;
- no critical regression exists.

### Release documentation

Required:

- README user-facing update;
- install instructions;
- system requirements;
- known limitations;
- privacy/local-first statement;
- third-party dependency/license attribution;
- release notes.

## Acceptance gate

M12 closes only when:

```text
RC built
→ clean install passed
→ manual acceptance passed
→ release blockers = 0
→ signed/formal installer accepted
→ GitHub release ready
```

At this point V1 is a shipped product.

---

# 20. Milestone 13 — Portfolio Packaging & Stop-Building Closure

## Goal

Convert the shipped technical work into a concise, credible professional artifact and formally stop V1 feature development.

## Required public evidence

### Technical README

Must explain:

- real user problem;
- two ingestion paths;
- canonical `Observation → Cue` model;
- three-pane QA workbench;
- Build vs Integrate;
- custom technical seams;
- evaluation results;
- known limitations.

### Architecture visual

Provide one clean diagram showing:

```text
Path A / Path B
→ Evidence
→ Observation
→ Reconstruction
→ Cue
→ QA
→ Export
```

### Demo

Create a short public-safe demo video/GIF showing:

- local input;
- ROI or caption ingestion;
- processing;
- flagged Cue;
- evidence inspection;
- correction/approval;
- export.

### Evaluation summary

Expose public-safe metrics and methodology without publishing restricted source material.

### Failure honesty

Highlight at least a few real limitations.

### Decision evidence

Surface major ADRs / Build-vs-Integrate decisions.

### Interview dossier

Privately prepare:

- whiteboard explanations;
- system trade-offs;
- benchmark story;
- failure modes;
- why each major dependency was chosen;
- what was custom vs integrated.

## Stop-Building closure

V1 feature development formally stops when:

1. Must-Have Portfolio Evidence exists;
2. product quality is accepted;
3. signed release exists;
4. implementation is explainable;
5. remaining ideas do not add a missing career-evidence category or fix a real product-quality deficiency.

After this gate:

> New feature requests default to `Deferred / Next Version`.

## Acceptance gate

M13 passes only when the project can be shown to a technical recruiter / interviewer without requiring oral explanation to hide missing evidence.

---

# 21. Evaluation Is Continuous, Not a Late Milestone

M10 is evidence closure.

It is **not** the first time evaluation occurs.

Required early evidence:

| Milestone | Evaluation obligation |
|---|---|
| M1 | Path B fixture correctness |
| M2 | timestamp / job correctness |
| M3 | OCR runtime benchmark |
| M4 | OCR-call/performance instrumentation |
| M5 | single-frame vs multi-frame comparison |
| M6 | multilingual separation measurement |
| M7 | Review Priority error-capture analysis begins |
| M8 | CJK/rolling normalization evaluation |
| M9 | full workflow regression |
| M10 | corpus-wide consolidation |

An implementation milestone that adds an AI/reconstruction seam without adding tests/evidence for that seam is incomplete.

---

# 22. Documentation Discipline

Each milestone should update macro records when the product truth changes.

At minimum maintain:

- `ROADMAP.md`
- `GLYPHCUE_PRODUCT_ARCHITECTURE.md`
- `DESIGN.md`
- future `PROJECT_STATUS.md`
- ADR / decision log
- evaluation/failure documents when created

Documentation should not trail the product lifecycle indefinitely.

For any final prompt that will make a PR merge-ready:

> **Macro record documents must be edited into the correct post-merge state before the PR is declared ready to merge.**

Do not leave macro docs describing the pre-merge world and plan to repair them afterward.

This rule exists to prevent repeated lifecycle-record drift.

---

# 23. Milestone PR Discipline

Default implementation pattern:

```text
Milestone branch
↓
Implementation + tests + evidence
↓
Agent self-review
↓
Remote push
↓
ChatGPT / human review
↓
Corrective pass if required
↓
Macro docs updated to post-merge truth
↓
PR merge-ready
↓
Merge
↓
Verify remote main
```

A Milestone is not complete merely because an agent says “done.”

---

# 24. Agent Prompt Discipline

Future production implementation prompts should remain milestone-oriented and concise.

Default style:

> one strong natural-language startup prompt describing the milestone goal, boundaries, acceptance evidence, and autonomy level.

Do not write enormous construction manuals unless a milestone genuinely requires a detailed corrective contract.

Every agent prompt should include:

> **Manual Skills Selection recommendation**

based on the actual work.

Do not automatically keep `/prototype` selected during production implementation.

The Prototype Decision Loop is closed.

---

# 25. Architecture / Design Change Control

If implementation reveals a contradiction:

### Local implementation issue
Solve inside the milestone.

### Product-shell contradiction
Escalate to `DESIGN.md`.

### Domain-model contradiction
Escalate to `GLYPHCUE_PRODUCT_ARCHITECTURE.md`.

### Product-scope contradiction
Do not silently add a feature.

Run a scope decision first.

Prototype HTML must not be treated as authority over current macro documents.

---

# 26. V1 Non-Goals

The roadmap explicitly excludes:

- arbitrary YouTube/platform downloading;
- platform caption scraping;
- ASR generation;
- untimed script alignment;
- full subtitle-authoring suite;
- full video editor;
- long-term learning-management system;
- built-in general AI chat/summary;
- generative subtitle removal/inpainting;
- default advanced CV tuning;
- per-language timing model;
- market-novelty claims without evidence;
- opaque AI complexity that violates Explainability Ceiling.

---

# 27. Stop-Building Rule

The V1 project does not continue until every imaginable useful feature exists.

Once required career evidence is:

- complete;
- verified;
- explainable;
- hardened;
- shipped;

new features are rejected by default.

A new feature may enter V1 only if it:

1. fixes a real product-quality deficiency; or
2. adds a previously missing, high-value career-evidence category.

Reasons that do **not** justify V1 expansion:

- “competitors have it”;
- “it looks more complete”;
- “it is cool”;
- “it adds more AI”;
- “it might be useful someday.”

---

# 28. V1 Completion Definition

GlyphCue V1 is complete only when all are true:

## Product

- Path A works end-to-end.
- Path B works end-to-end.
- frozen QA workbench is implemented.
- accepted exports work.
- feature freeze completed.

## Applied AI

- OCR integration is evidence-selected.
- selective OCR is operational.
- multi-frame consensus is measured.
- multilingual reconstruction is measured.
- CJK is explicitly evaluated.
- Review Priority is evaluated.

## Engineering

- local-first processing is reliable.
- long jobs are cancelable.
- persistence is safe.
- source transformations are non-destructive.
- regression is strong.
- packaging works cleanly.

## Evidence

- Evaluation Report exists.
- Failure-Mode Report exists.
- ADR / Build-vs-Integrate evidence exists.
- performance evidence exists.

## Delivery

- hardening completed.
- RC accepted.
- clean installer accepted.
- formal release exists.

## Portfolio

- README tells the technical story.
- demo-safe showcase exists.
- public-safe evaluation summary exists.
- interview dossier exists.

Only then should the roadmap be considered complete.

---

# 29. Current Lifecycle State

```text
Repository created                     ✓
Product discovery                      ✓
First architecture Grill               ✓
Career-Portfolio Delta Grill           ✓
Product architecture consolidated      ✓
Prototype Round 1                      ✓
Prototype Round 2                      ✓
Prototype Round 3                      ✓
Product Shell Validation               ✓
DESIGN.md                              ✓
Multilingual timing decision           ✓
Technology Stack Freeze                ✓

Production Roadmap                     ✓  ← this document

Milestone 0 — Production Foundation    ✓ complete
Milestone 1 — Thin Path B Vertical Slice ✓ complete
Milestone 2 — Path A Media & Job Orchestration ✓ complete
Milestone 3 — OCR Adapter & Runtime Selection ✓ complete
Milestone 4 — Selective OCR Evidence Pipeline ✓ complete
Milestone 5 — Multi-Frame Consensus & Cue Reconstruction ✓ complete

Production Development                 IN PROGRESS
```

---

# 30. Immediate Next Action

The next engineering action is:

> **Milestone 6 — Multilingual Track Group Reconstruction**

Do not ask AG2.0 to implement the whole roadmap.

Advance one milestone at a time.

After M6 is pushed:

1. inspect the remote repository;
2. verify the milestone against its acceptance gate;
3. correct deficiencies;
4. merge only when the milestone is genuinely accepted;
5. then issue the M7 prompt.

---

# 31. Roadmap Summary

```text
M0
Production Foundation
        ↓
M1
Thin Path B Vertical Slice
        ↓
M2
Path A Media & Job Orchestration
        ↓
M3
OCR Adapter & Runtime Selection
        ↓
M4
Selective OCR Evidence Pipeline
        ↓
M5
Multi-Frame Consensus & Cue Reconstruction
        ↓
M6
Multilingual Track Group Reconstruction
        ↓
M7
Reconstruction QA & Review Priority
        ↓
M8
Path B CJK / Rolling Deepening
        ↓
M9
V1 Product Completion + Feature Freeze
        ↓
M10
Evaluation & Career Evidence Closure
        ↓
M11
Product Hardening + Full Regression
        ↓
M12
Release Candidate + Signed Release
        ↓
M13
Portfolio Packaging + Stop-Building Closure
```

The center of gravity is intentionally M2–M7.

That is where GlyphCue earns most of its unique Applied AI / multimedia engineering evidence.

M1 de-risks the canonical spine.

M8 completes the second ingestion path.

M9–M13 convert engineering work into a finished, evaluated, hardened, shipped, and professionally legible product.

---

# 32. Final Roadmap Principle

GlyphCue should not optimize for the number of features completed.

It should optimize for:

```text
real user value
×
clear engineering ownership
×
measured Applied AI quality
×
explainability
×
product reliability
×
delivery credibility
```

The roadmap is finished when those things are convincingly present — not when there is nothing else anyone could possibly add.
