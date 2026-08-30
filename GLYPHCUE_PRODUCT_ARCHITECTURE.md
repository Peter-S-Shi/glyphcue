# GlyphCue — Product Architecture

**Document type:** Authoritative post-Grill product architecture baseline  
**Project:** GlyphCue  
**Repository:** `Peter-S-Shi/glyphcue`  
**Lifecycle phase:** Production Development in progress → Milestone 1 complete, Milestone 2 next  
**Status:** Authoritative V1 product architecture for production development  
**Last updated:** 2026-08-30

---

# 1. Purpose of This Document

This file is the first repository-level macro architecture document for GlyphCue.

It consolidates the accepted conclusions from:

- the original product discovery discussions;
- the first adversarial Product Architecture Grill;
- the second Career-Portfolio Delta Grill;
- the owner-approved decisions made during both Grill interviews.

This document is **not** a roadmap, milestone plan, coding specification, UI design file, or implementation prompt.

Its purpose is to answer:

> What is GlyphCue now, what problems does it own, what architectural constraints are already accepted, where should custom engineering depth live, and what remains genuinely open during V1 production development?

When this file conflicts with earlier exploratory baselines or Grill recommendations, **this file is the current planning authority**.

The two Grill reviews should remain in the repository as design-history / decision-evidence artifacts, but they no longer define current truth by themselves.

---

# 2. Product Identity

## 2.1 Working product definition

GlyphCue is a **local-first Windows subtitle reconstruction workbench** for turning difficult subtitle evidence into clean, structured, reusable subtitle data.

Its core inputs are:

1. video containing burned-in / hardcoded subtitles;
2. user-supplied timed captions or transcripts that are noisy, rolling, duplicated, or badly segmented.

Its core output is a structured subtitle representation that can be:

- reviewed;
- corrected;
- exported as subtitle files;
- reconstructed into readable transcripts;
- rendered back onto video when useful.

## 2.2 Product center

The accepted product center is:

> **Difficult subtitle reconstruction**

GlyphCue is **not** positioned internally as merely another generic:

```text
video
→ OCR
→ SRT
```

tool.

The generic detection / OCR / timing pipeline is important product infrastructure, but the highest-value custom work is concentrated in difficult reconstruction problems such as:

- bilingual / multilingual subtitle separation;
- multi-frame OCR consensus;
- noisy temporal reconstruction;
- rolling-caption normalization;
- CJK-sensitive text reconstruction;
- evidence-routed human review.

## 2.3 Working tagline

> **From pixels back to cues.**

This remains a strong working tagline for the burned-in subtitle path.

A broader wording such as:

> From noisy evidence back to clean cues.

may be reconsidered later if product identity needs to represent both ingestion paths equally.

Final marketing wording is **not frozen** by this architecture document.

---

# 3. Success Function

GlyphCue has three ordered success criteria.

## 3.1 Real self-use first

The product must solve the owner's real subtitle-recovery and caption-cleaning workflows.

It is not a fictional market exercise.

## 3.2 Product-quality generalization second

GlyphCue should still be built as a coherent, installable, understandable desktop product rather than a private one-off script.

Other users with similar problems should be able to understand and use it.

## 3.3 Career evidence third — but explicit

GlyphCue is also intentionally designed to become a strong portfolio project for:

1. **Applied AI Engineer**
2. **AI Product / AI Application Engineer**

The project should demonstrate:

- mature model / media integration;
- multimedia and CV system orchestration;
- custom algorithmic reconstruction;
- evaluation methodology;
- failure analysis;
- uncertainty-aware review;
- build-vs-integrate judgment;
- explainable engineering ownership;
- production-quality delivery.

Market originality is a bonus.

It is **not** the acceptance criterion.

---

# 4. Career Thesis

Working career thesis:

> GlyphCue demonstrates end-to-end Applied AI product engineering: identify a real problem, integrate mature OCR and multimedia infrastructure honestly, build the genuinely hard custom reconstruction seams, evaluate them against ground truth, analyze failure modes, route human attention intelligently, and ship the result as a hardened local desktop product.

Internal one-line principle:

> **A real problem, mature parts integrated honestly, the hard 20% built and measured, shipped like a product.**

---

# 5. Explicit Product Boundaries

## 5.1 OUT — platform acquisition

GlyphCue does not provide:

- YouTube video downloading;
- arbitrary platform-media downloading;
- YouTube caption scraping / acquisition;
- unofficial platform-caption extraction;
- downloader-style online platform integration.

The application works with **user-supplied local media and user-supplied subtitle/transcript assets**.

## 5.2 OUT — ASR subtitle generation

GlyphCue does not currently implement:

```text
video with no subtitle evidence
→ ASR / STT
→ generated subtitles
```

Speech recognition is not required for the current product center.

## 5.3 OUT — untimed-script alignment

GlyphCue does not currently implement:

```text
untimed script + video
→ forced alignment
→ generated subtitle timing
```

## 5.4 OUT — full learning-management system

GlyphCue does not become:

- a spaced-repetition system;
- a mistake-book platform;
- a learning streak / daily-plan system;
- a long-term mastery tracker;
- a cross-video curriculum manager.

Only QA-native playback interactions remain in V1 scope.

## 5.5 OUT — built-in general AI summarizer

GlyphCue may export AI-friendly transcript text.

It does not need to become an AI chat / summary / knowledge-management platform.

External AI tools can consume GlyphCue output.

## 5.6 DEFERRED — subtitle removal / video inpainting

Advanced generative subtitle removal is outside the current core.

Basic masking / blur / black-bar tools are also deferred unless later product evidence makes them worthwhile.

---

# 6. Core Architecture

The accepted canonical spine is:

```text
Evidence
→ Observation
→ Cue
→ Reconstruction QA
→ Export / Render
```

GlyphCue has two first-class ingestion paths that feed this spine.

---

# 7. Path A — Burned-in Subtitle Reconstruction

## 7.1 Input

```text
Local video
+
processing range
+
subtitle-region / language configuration
```

## 7.2 High-level pipeline

```text
Video
↓
Demux / Decode / Metadata
↓
PTS / time-base aware timing
↓
Selected processing range
↓
ROI sampling
↓
Cheap visual change analysis
↓
OCR candidate selection
↓
Selective OCR
↓
Temporal stabilization
↓
Multi-frame consensus
↓
Language-layer separation
↓
Cue boundary reconstruction
↓
Observation → Cue
↓
QA Workspace
↓
Export
```

## 7.3 Architectural principle

> **Frame analysis is not frame-by-frame OCR.**

Cheap visual analysis should decide when expensive OCR work is justified.

The exact change-detection algorithm is not frozen.

Candidate techniques may include:

- frame differencing;
- SSIM;
- perceptual hashing;
- edge-based statistics;
- change-point logic.

These techniques are established engineering methods, not claimed product novelty.

## 7.4 Timing principle

Do not assume:

```text
timestamp = frame_number / FPS
```

as a universal timing model.

GlyphCue should use media timestamps correctly, including PTS / time-base semantics where appropriate, so VFR media does not silently create timing drift.

---

# 8. Path B — Timed Caption Normalization

## 8.1 Input

```text
User-supplied SRT / VTT
+
optional matching local video
```

## 8.2 Problem class

Path B handles captions containing problems such as:

- rolling / incremental text;
- repeated partial sentences;
- sliding overlap;
- overlapping cue timing;
- poor segmentation;
- noisy automatic-caption structure.

## 8.3 Target pipeline

```text
Caption Parser
↓
Structure Analyzer
↓
Rolling / Noise Detection
↓
Incremental Text Consolidation
↓
Cue Reconstruction
↓
Timing Normalization
↓
Observation → Cue
↓
QA Workspace
↓
Export
```

## 8.4 Seed-code policy

The older `subtitle_cleaner.py` is treated as an **algorithmic seed**, not production GlyphCue code.

Preserve its strongest contracts:

- source file is never overwritten;
- transformation is conservative;
- normal subtitle input may remain unchanged;
- output is non-destructive;
- temporary write → atomic replacement;
- rolling growth and sliding overlap are recognized;
- structural cleaning is separated from semantic rewriting.

Do **not** preserve its Latin-centric implementation assumptions as product truth.

Known seed limitations include:

- whitespace-token dependence;
- English-oriented terminal punctuation;
- fixed 84-character segmentation;
- fixed 42-character wrapping;
- `>>` speaker-marker assumptions;
- poor CJK suitability;
- brittle behavior on malformed / unordered cues.

The intended direction is:

> **inherit contracts and problem knowledge; redesign the implementation for multilingual robustness.**

---

# 9. Path Status and Sequencing Principle

Path A and Path B are **equal first-class product capabilities**.

Equal product status does not mean equal implementation timing.

The accepted development-sequencing principle is:

```text
Stage 1
Thin Path B vertical slice
↓
prove Observation → Cue
prove non-destructive transformation
prove minimal QA + export
include at least one CJK fixture

Stage 2
Pivot main custom-engineering budget to Path A
↓
media / OCR integration
selective OCR
multi-frame consensus
multilingual separation
review-priority scoring
evaluation

Stage 3
Deepen Path B
↓
CJK-capable rolling normalization
QA maturation
remaining evidence-driven gaps
```

This sequencing is the architectural rationale implemented by the current milestone roadmap in `ROADMAP.md`; `ROADMAP.md` is authoritative for milestone ordering and gates.

---

# 10. Input Configuration Philosophy

GlyphCue follows:

> **Human-assisted automation, not human-configured CV engineering.**

The default setup should remain small.

## 10.1 Default user-facing configuration

Primary inputs:

1. **ROI / subtitle region**
2. **Language(s)**
3. **Optional processing range**

That is the intended V1 default configuration surface.

## 10.2 Hidden / automatic behavior

The following should default to automatic behavior rather than mandatory user controls:

- scan density;
- color characterization;
- spatial weighting;
- change-detection thresholds;
- OCR preprocessing;
- inference thresholds.

Advanced settings may be added only when real benchmark evidence proves that user control materially improves difficult cases.

---

# 11. Track Group Model

The extraction configuration should represent **visual regions first**, not languages first.

Preferred conceptual model:

```text
Track Group / Visual Region
├─ ROI
├─ visual characteristics
└─ language layers 1…N
```

Reason:

> ROI describes where text exists in the frame; language describes what is inside that region.

A bilingual subtitle block should not require the user to draw the same ROI twice merely because it contains two languages.

---

# 12. Multilingual Timing Decision — V1 Frozen

The physical configuration model and the canonical timing model are distinct questions.

A visual region may contain several language layers. For V1, representative target sample observation has resolved the timing semantics:

```text
single Cue with shared timing + N language layers
```

is the frozen V1 model. Language Layers inherit the Cue's timing; independent per-language timing, alignment graphs, and one-to-many/many-to-one timing relations are explicitly out of scope for V1.

See `ROADMAP.md` §4 (V1 Domain Simplification — Multilingual Timing Closed) for the accepted material profile and rationale:

- language layers appear together within a Track Group;
- language layers disappear together within a Track Group;
- meaningful timing skew was not observed in representative target material;
- rare missing/asymmetric layers are treated as degraded / low-quality source conditions.

This is an intentional V1 domain simplification based on the supported material profile, not a universal claim about all burned-in multilingual subtitles. It may be revisited in a future version if evidence requires it.

---

# 13. Canonical Domain Model

## 13.1 Two-level model

The accepted V1 direction is:

```text
Observation
→ Cue
```

Do not introduce an independent `CandidateCue` domain class unless later implementation evidence demonstrates distinct invariants that require it.

## 13.2 Observation

An Observation represents machine / source evidence.

Possible fields include:

- source timestamp;
- source media reference;
- frame / ROI reference;
- raw OCR text;
- OCR-engine score;
- visual-change evidence;
- preprocessing metadata;
- language / script information;
- source provenance;
- support for later Cue reconstruction.

Observation should remain as immutable or evidence-like as practical.

## 13.3 Cue

Cue is the product-facing editable subtitle unit.

Possible responsibilities include:

- start / end timing;
- text or language-layer content;
- provenance;
- review state;
- reconstruction flags;
- references to supporting observations;
- manual edits;
- approved final text.

Multilingual timing structure is frozen for V1 as described in §12: Language Layers inherit Cue timing.

---

# 14. Provenance and Fidelity

GlyphCue must preserve the difference between:

```text
Source evidence
→ normalized evidence
→ reconstructed cue
→ optional suggestion
→ user-approved final text
```

A model or normalization layer must not silently rewrite source meaning.

Where future AI-assisted correction exists, it should remain a **suggestion layer**, not an invisible overwrite.

---

# 15. Reconstruction QA Workspace

GlyphCue does **not** attempt to replace a full professional subtitle editor.

Its editor responsibility is narrower:

> Correct the errors GlyphCue itself may create or surface.

The product should provide a focused Reconstruction QA Workspace.

Expected capabilities include:

- video / frame context for a cue;
- click cue → seek;
- previous / next cue;
- replay current cue;
- recovered language layers;
- review-priority ordering;
- quick text correction;
- timing nudge;
- split / merge where reconstruction requires it;
- language-layer show / hide;
- issue / disagreement indicators.

Deep subtitle authoring, advanced styling, comprehensive format repair, and professional retiming can remain in external subtitle tools.

The QA workspace must still be good enough to close GlyphCue's own correction loop.

---

# 16. Review Priority / Suspicion Score

GlyphCue may produce a **Review Priority** or **Suspicion Score** that ranks cues for human inspection.

It should not pretend to be a calibrated probability.

Do not display misleading UI such as:

```text
92% confidence
```

unless formal calibration later justifies that interpretation.

Potential score signals may include:

- OCR-engine score;
- disagreement across frames;
- unstable cue boundaries;
- language-layer ambiguity;
- reconstruction inconsistency.

The user-facing purpose is:

> show what is most worth checking first.

---

# 17. Suspicion-Score Evaluation

Although probability-style UI remains rejected, evaluation-side validation is required.

The benchmark should test whether Review Priority actually captures errors.

Useful analysis includes:

```text
Top 10% most suspicious cues
→ what fraction of real errors are captured?

Top 20%
→ what fraction?

How does this compare with random inspection?
```

The Evaluation Report should include:

- error-capture curve;
- top-N / top-percentile error recall;
- score-component comparison where useful;
- failure classes that the score catches;
- failure classes that it misses.

If the score performs poorly, report that honestly.

Formal probabilistic calibration remains deferred unless later evidence volume makes it meaningful.

---

# 18. AI-Ready Transcript

The long-video → text → external AI use case remains valid.

However, **AI-ready Transcript is an export preset, not a separate product subsystem**.

Possible transcript presets:

```text
Readable
Compact / AI-ready
Custom
```

An AI-ready preset may:

- merge unnecessary cue fragmentation;
- reduce timestamp density;
- omit cue numbering;
- select only desired language layers;
- preserve sparse timestamps for source navigation;
- output Markdown / TXT.

GlyphCue creates clean AI-consumable source material.

External AI tools perform summary, Q&A, study, or knowledge extraction.

---

# 19. Output and Interoperability

## Core subtitle export

- SRT
- VTT

ASS may be considered later if richer subtitle styling becomes justified.

## Transcript export

- TXT
- Markdown
- AI-ready preset

## Media output

Where useful and inexpensive:

- soft-subtitle muxing;
- subtitle burn-in / rendering.

These are mature integration capabilities and should remain thin.

---

# 20. QA-Native Playback Interaction

The separate learning layer from early planning is removed.

V1 retains only interactions naturally needed by the QA workspace:

- click cue → seek;
- previous / next cue;
- replay current cue;
- show / hide language layers.

Pure learning functions such as:

- dedicated A-B study loop;
- special repetition modes;
- learning-oriented speed workflows;
- persistent study state;

remain deferred.

---

# 21. Long-Running Job UX

GlyphCue processing may take substantial time.

The application should use:

- background workers;
- explicit job state;
- progress events;
- responsive UI;
- cancellation.

Cancel is a core early capability.

Pause / Resume is optional and may come later.

## Progress UX

Progress should be phase-aware rather than a fake spinner.

Possible phases:

```text
Inspect media
Scan subtitle region
Detect changes
OCR & reconstruct
Validate output
```

Where knowable, show:

- phase;
- processed media time;
- progress percentage;
- estimated remaining time.

## Product personality

Friendly status copy may exist in a restrained form.

The product tone should be:

> **serious technical workbench with personality**

not a cartoon utility.

Quiet / reduced-motion behavior should be available when appropriate.

---

# 22. Local-First Deployment

GlyphCue remains local-first.

Reasons include:

- large media files;
- privacy;
- copyright sensitivity;
- predictable data ownership;
- local CPU/GPU availability;
- avoidance of mandatory cloud accounts and upload costs.

CPU execution must remain viable for core functionality.

GPU acceleration may be supported where it produces meaningful gains.

The product must not become unusable merely because the user lacks a specific compatible GPU.

---

# 23. Build vs Integrate

GlyphCue should not reimplement mature commodity infrastructure merely for originality.

## Integrate / depend on mature components

Likely examples:

- FFmpeg / media demux and decode;
- media encoding / muxing;
- pretrained OCR runtime / model;
- subtitle parsing utilities where suitable;
- desktop media playback infrastructure.

## GlyphCue owns orchestration

Even when the underlying components are mature, GlyphCue should own the product-specific orchestration:

- PTS-correct media flow;
- ROI sampling;
- OCR runtime lifecycle;
- selective OCR decisions;
- batching;
- job cancellation;
- progress state;
- evidence capture;
- downstream reconstruction.

This is legitimate Applied AI systems engineering.

It should be narrated honestly as integration / orchestration rather than novel algorithm invention.

---

# 24. Custom Technical Depth Priorities

Custom-engineering budget should be concentrated in this order.

## Priority 1 — CJK-aware multi-frame OCR consensus

Expected depth:

- alignment;
- voting / consensus;
- clustering;
- disagreement handling;
- transparent failure analysis.

This is currently the highest-density custom Applied AI evidence.

## Priority 2 — Bilingual / multilingual layer separation

Expected depth:

- visual layout reasoning;
- script / language identification where useful;
- region / language-layer association;
- robust handling of difficult multilingual blocks.

## Priority 3 — Evaluation methodology

Evaluation is part of engineering, not post-project paperwork.

## Priority 4 — Review Priority / suspicion scoring

Small cost, high evidence value when validated honestly.

## Priority 5 — CJK-capable rolling-caption normalization

Preserve the seed cleaner's contracts while replacing Latin-centric assumptions.

## Priority 6 — Selective OCR orchestration

Build cleanly and benchmark it.

Do not over-engineer generic subtitle-change detection merely to appear innovative.

Everything below these priorities receives normal production-quality engineering rather than research-style depth investment.

---

# 25. Evaluation Strategy

The evaluation corpus is a **core project artifact**.

It is not a formal competitor gate.

Its purpose is to prove GlyphCue's own quality and technical decisions.

## 25.1 Initial scale

Target envelope:

> **3–5 representative videos × approximately 2–5 minute segments**

Expand only when a new sample adds meaningful evidence coverage.

Do not turn GlyphCue into a dataset-labeling project.

## 25.2 Two-layer benchmark strategy

### Private realistic benchmark

Real self-use material may remain private.

It can produce:

- aggregate metrics;
- failure taxonomy;
- methodology;
- architecture decisions;
- performance results.

Do not publish restricted source material by default.

### Public demo-safe benchmark

Use:

- self-made material;
- open-licensed material;
- otherwise clearly redistributable material.

This layer supports:

- README examples;
- demo video / GIF;
- reproducible public sample;
- before / after results.

---

# 26. Evaluation Dimensions

Expected metrics / evidence may include:

## Text quality

- CER;
- WER where meaningful.

## Cue recovery

- cue precision;
- cue recall.

## Timing

- start-time error;
- end-time error;
- other boundary metrics if useful.

## Multilingual reconstruction

- language-layer separation quality;
- missing / incorrect layer assignment;
- alignment errors.

## Rolling normalization

- duplicate-removal correctness;
- segmentation correctness;
- timing normalization quality.

## Performance

- frames analyzed per second;
- OCR calls per minute;
- end-to-end processing time;
- CPU utilization;
- memory usage where useful;
- hardware sensitivity.

## Human-review routing

- suspicion-score error-capture effectiveness.

---

# 27. Failure Analysis

GlyphCue must maintain an honest failure model.

Expected failure classes include:

- OCR character confusion;
- CJK recognition instability;
- subtitle/background false positives;
- non-subtitle text inside ROI;
- rapid subtitle transitions;
- missed changes from sparse sampling;
- excessive OCR invocation;
- multilingual layer mixing;
- missing one language layer;
- timing drift;
- unstable cue boundaries;
- transition frames becoming phantom cues;
- rolling-caption duplication;
- poor resegmentation;
- malformed / unordered imported captions;
- color/style changes;
- karaoke / word-highlight styles;
- subtitle movement / region changes;
- long-video performance degradation;
- cancellation leaving partial state.

The final portfolio should include a Failure-Mode Report based on observed failures, not hypothetical completeness theater.

---

# 28. Explainability Ceiling

GlyphCue is developed with substantial AI coding-agent assistance.

Therefore a standing portfolio constraint applies:

> **Do not add custom technical complexity that the owner cannot independently explain, defend, evaluate, and distinguish from dependency behavior.**

## For integrated dependencies

The owner should be able to explain:

- what the component solves;
- why it was chosen;
- input / output contract;
- relevant alternatives;
- major trade-offs;
- known failure modes;
- how it is evaluated;
- how GlyphCue embeds it safely;
- what belongs to the dependency vs. GlyphCue.

The owner is not required to rederive the internals of mature pretrained models.

## For GlyphCue custom logic

The standard is higher.

The owner should be able to explain at whiteboard level:

- algorithm idea;
- design choices;
- alternatives;
- failure modes;
- evaluation;
- observed results.

Transparent algorithmic engineering is preferred over opaque complexity added merely for higher “AI sophistication.”

---

# 29. Must-Have Portfolio Evidence

GlyphCue becomes portfolio-ready only when the following evidence exists.

## Hard requirements

1. **Working end-to-end product**
   - installable Windows release;
   - public demo-safe Path A sample;
   - clean structured subtitle output.

2. **Evaluation Report**
   - corpus methodology;
   - text / timing / separation metrics;
   - performance;
   - suspicion-score error-capture analysis;
   - honest negative results.

3. **Failure-Mode Report**
   - real observed failures;
   - why they occur;
   - how GlyphCue handles them;
   - known limitations.

4. **Technical README / Architecture Story**
   - problem;
   - data/control flow;
   - Observation → Cue model;
   - Build-vs-Integrate table;
   - custom contributions vs dependencies.

5. **Decision Log / ADR evidence**
   - key product / architecture decisions;
   - alternatives rejected;
   - reasoning.

## Near-mandatory

6. **Demo video / GIF**
   - ROI setup;
   - real progress;
   - flagged cue review;
   - export.

7. **Performance evidence**
   - CPU throughput;
   - OCR call rate;
   - hardware sensitivity.

## Private interview preparation

8. **Interview talking-points dossier**
   - whiteboard explanation of each custom seam;
   - trade-offs;
   - failure modes;
   - benchmark results.

---

# 30. Stop-Building Rule

GlyphCue does not stop when an arbitrary feature list becomes empty.

It stops when the required **career evidence and product-quality evidence are complete**.

> **Once the Must-Have Portfolio Evidence is complete, verified, explainable, and shipped through the established lifecycle, new features are rejected by default unless they materially add a previously missing category of career evidence or fix a real product-quality deficiency.**

Rejected-by-default reasons include:

- “makes the product more complete”;
- “competitors have it”;
- “it is cool”;
- “more AI flavor”;
- “might be useful later.”

These normally route to:

> Deferred / Next Version

The Explainability Ceiling always continues to apply.

---

# 31. Release Standard

GlyphCue remains a real product, not only an evaluated notebook or algorithm demo.

The current expected lifecycle is:

```text
Product Discovery / Architecture
↓
Prototype / Product Shell Validation
↓
Feature Development
↓
Feature Complete
↓
Feature Freeze
↓
Product Hardening
↓
Regression + Manual Acceptance
↓
Release Candidate
↓
Human Accepted
↓
Signed / Formal Release
↓
Maintenance / Next Version
```

Hardening and RC are not optional decorations.

A working core algorithm does **not** equal project completion.

The detailed Milestone roadmap exists as `ROADMAP.md`.

---

# 32. Current Lifecycle State

As of this update:

```text
Repository created
✓

Product discovery
✓

First Product Architecture Grill
✓

Career-Portfolio Delta Grill
✓

Post-Grill architecture consolidation
✓  ← this document

Formal competitor Evidence Gate
Retired as blocker

Prototype Round 1
✓

Prototype Round 2
✓

Prototype Round 3
✓

Product Shell Validation
✓

DESIGN.md
✓ exists

Multilingual timing decision (O1)
✓ closed — see §12

V1 technology stack
✓ frozen — see ROADMAP.md §3

ROADMAP.md
✓ exists

Evaluation corpus
Required as engineering / portfolio evidence (produced across M1–M10 per ROADMAP.md)

Milestone 0 — Production Foundation
✓ complete

Milestone 1 — Thin Path B Vertical Slice
✓ complete

Production Development
IN PROGRESS — Milestone 2 (Path A Media & Job Orchestration) next
```

---

# 33. Remaining Open Architecture Decisions During Production Development

Only unresolved issues that can materially affect production architecture should remain here.

O1 (multilingual timing semantics), O2 (final desktop technology stack), and O4 (final UI / interaction model) are closed — see §12, `ROADMAP.md` §3, and `DESIGN.md` respectively. O3 and O5 remain genuinely open below.

## O3 — OCR runtime selection

The product architecture assumes mature pretrained OCR integration.

The exact engine / runtime should be selected through practical engineering evidence, not preference alone.

## O5 — Final public-facing identity wording

The internal product center is accepted.

Marketing description / GitHub description / tagline wording may still be refined after prototype.

---

# 34. Prototype Contract

Status: fulfilled. Prototype Rounds 1–3 and Product Shell Validation are complete; the accepted result is frozen in `DESIGN.md`. The contract below is retained as the historical record of what the prototype phase was required to test and preserve.

Prototype is a decision artifact.

Its job is to test whether this architecture becomes a coherent product when visible and interactive.

It must **not** silently change:

- product scope;
- Path A / Path B status;
- Observation → Cue semantics;
- Build-vs-Integrate boundaries;
- QA Workspace responsibility;
- Stop-Building Rule.

If the prototype exposes a genuine architecture contradiction, that becomes an explicit architecture decision rather than a quiet UI workaround.

The prototype may be throwaway.

Production development should not begin merely because a visually attractive mockup exists.

---

# 35. Architecture Guardrails for Future Agents

Future Codex / Claude Code work must preserve these rules unless an explicit product / architecture decision changes them.

1. Do not expand GlyphCue into a platform downloader.
2. Do not add ASR merely because an OCR path is difficult.
3. Do not silently turn the QA workspace into a full subtitle editor.
4. Do not expose CV tuning knobs by default without evidence.
5. Do not hard-code bilingual-only assumptions.
6. Do not implement per-language independent timing for V1; shared Cue-level timing is frozen (§12).
7. Do not silently rewrite recovered text for style or fluency.
8. Do not claim third-party model capabilities as GlyphCue inventions.
9. Do not claim market novelty without evidence.
10. Do not add AI complexity merely for portfolio appearance.
11. Do not remove commodity infrastructure merely because competitors also use it.
12. Preserve non-destructive transformation behavior.
13. Keep custom technical depth concentrated in the approved priorities.
14. Evaluation and failure analysis are product-engineering requirements.
15. New V1 features must survive the Stop-Building Rule.

---

# 36. Relationship to Historical Design Documents

The following document types remain useful but serve different roles.

## Product Architecture Grill documents

Role:

> historical adversarial review / design evidence

They explain how decisions were challenged.

They do not override this file.

## Career-Portfolio Delta Grill documents

Role:

> historical career-success-function correction and evidence strategy

Their accepted deltas have been consolidated here.

## `DESIGN.md`

Role:

> approved visual and interaction design, frozen after Prototype Rounds 1–3 and Product Shell Validation

It should not redefine product architecture silently.

## `ROADMAP.md`

Role:

> milestone-driven engineering progression

It implements this architecture and does not recreate product discovery. It is the current authoritative source for V1 technology stack and multilingual timing facts (see §12 above).

## Future `PROJECT_STATUS.md`

Role:

> current lifecycle / milestone / verification authority

It should point back to this architecture when describing the current product scope.

---

# 37. Current Architecture Summary

GlyphCue can currently be compressed to this model:

```text
                  GLYPHCUE

        ┌─────────────────────────┐
        │ Difficult Subtitle      │
        │ Reconstruction          │
        └────────────┬────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
 Path A — Video            Path B — Timed Captions
 Burned-in subtitles       Rolling / noisy SRT/VTT
        │                         │
        ▼                         ▼
 Visual / OCR Evidence      Text / Timing Evidence
        │                         │
        └────────────┬────────────┘
                     ▼
                Observation
                     │
                     ▼
            Reconstruction Logic
     consensus / separation / normalization
                     │
                     ▼
                    Cue
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       QA Review   Subtitle   Transcript
                    Export      Export
                                 │
                                 ▼
                          AI-ready preset
```

Engineering principle:

```text
Mature components
→ integrate honestly

Product-specific orchestration
→ own cleanly

Hard reconstruction seams
→ design + implement + evaluate deeply

Uncertainty
→ route to human review

Result
→ measure, explain, harden, ship
```

---

# 38. Final Architecture Principle

GlyphCue should not try to prove that every part of the system is novel.

It should prove something more professionally useful:

> **The team knows what to integrate, what to build, what to measure, what to distrust, what to let a human review, and when the product is complete enough to stop.**
