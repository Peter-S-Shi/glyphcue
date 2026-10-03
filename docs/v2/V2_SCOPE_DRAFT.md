# GlyphCue V2 Product Scope Draft

**Status:** candidate canonical scope for human review\
**Research basis:** V2 Discovery Round 1, Round 2, and Round 3\
**Authority:** product decisions in this document are authoritative only after user review. Round 3 engineering evidence supports feasibility and risk; it does not silently close product gates. The current HTML sample and `DESIGN_NOTES.md` are design proposals, not acceptance evidence.

## 1. Product definition

GlyphCue V2 is a local-first desktop workflow for turning video or audio without usable subtitles into an editable timed transcript, bilingual subtitles, single-narrator dubbing, and subtitle/media exports. The editable Source Transcript revision and provenance are the semantic source of truth; Subtitle Cues are derived display units that can be edited for presentation and export. OCR of burned-in subtitles is no longer the primary workflow.

English, Chinese, and French are the initial validation anchor set. All six source/target directions may be evaluated, but the V2.0 release matrix remains an explicit Product decision after quality, runtime, and distribution evidence. Language support is stage-specific and capability-driven, so the product must not encode a permanent three-language enum.

## 2. V2.0 Core Foundation

The shared foundation for the V2.0 product workflows must include:

1. local media import and probe: duration, streams, frame rate, audio tracks, seekability, and warnings;
2. local speech recognition that produces timestamped source spans and auditable run metadata;
3. an editable Source Transcript with stable span IDs, source-language metadata, split/merge, text correction, and time edits;
4. cue layout and subtitle editing with line, duration, gap, reading-speed, and overlap validation;
5. project revisions, undoable edits, provenance, derived-result invalidation, stale-result handling, and locked-span handling;
6. subtitle and text export for SRT, VTT, ASS, and plain text, with deterministic export snapshots;
7. burned-in subtitle and subtitle-plus-audio/video export through an explicit FFmpeg pipeline;
8. a local resource manager for models, backends, voices, fonts, licenses, hashes, install state, and rollback;
9. offline operation for the local path, with clear diagnostics when a required resource or backend is unavailable;
10. recovery-safe project storage and backup/restore of metadata plus referenced artifacts.

## 3. Required V2.0 Product Workflows

V2.0 scope includes both workflows below. A workflow can be re-scoped only through an explicit Product Gate if licensing or feasibility evidence prevents a responsible release:

1. bilingual subtitle translation from the editable Source Transcript, with a reviewable target text and subtitle export;
2. single-narrator dubbing with explicit voice and language selection, inspectable timing/alignment, and audio replacement or mix export.

The intended default execution path is local. The exact supported language pairs, voices, and runtime profiles are release decisions gated by measured evidence.

### Optional V2.0 provider path

An explicitly configured BYOK provider adapter for translation or TTS may ship when its terms and privacy gate pass. BYOK is never an implicit fallback and must show provider, endpoint, region, model/voice, payload class, and privacy effect before execution.

## 4. Deferred capabilities

Voice cloning, automatic multi-speaker casting, lip-sync, source separation, live captions, cloud ASR, collaboration, plugin marketplaces, automatic V1 project migration, browser/mobile clients, and broad speculative media features are outside V2.0. They require a new product gate rather than being added opportunistically.

## 5. Language and capability policy

Every stage reports one of `listed`, `product-verified`, `experimental`, or `unavailable` for a BCP-47 language tag. The UI must show the actual source language and source-to-target pair for the current operation. ASR, translation, TTS, alignment, and subtitle rendering each have independent capability records.

The six EN/ZH/FR directions form the initial evaluation matrix. Evaluation does not commit all six to V2.0 release. The release matrix requires a later explicit Product decision based on quality, timestamps, privacy, runtime, and licensing evidence for the selected resource set; unavailable directions must be surfaced before work begins.

## 6. Domain and data invariants

- A project has stable IDs for project, media, transcript span, cue, translation, take, artifact, resource, task, and revision.
- Source Transcript revision and provenance determine the semantic content; Subtitle Cues derive display timing and layout from that source, with presentation edits traceable to it.
- Edits create revisions; worker results identify the input revision and cannot silently overwrite newer edits.
- Provenance records source, operation, model/resource revision, parameters, and parent artifact IDs.
- Split and merge operations preserve traceable ancestry. Locked spans reject destructive automatic replacement.
- Late, failed, cancelled, and stale results are visible states, not hidden retries.
- Subtitle timing is represented in media time and exported through a deterministic snapshot. Variable frame rate, long GOP, multi-track media, Unicode paths, and non-seekable inputs are explicit test cases.
- Source media is referenced by path/identity and is not silently copied into the project.

## 7. Architecture baseline

The baseline is one controller/project writer, isolated capability workers, and a persistent project model. Workers communicate through versioned jobs and structured events; workers do not write the project database directly. ASR and an aligner may share a process only when the protocol reports both phases and their resource costs.

Qt Quick/QML with a Python controller and Tauri 2 with a TypeScript UI/Rust controller remain candidate shells. The framework is not closed until the framework slice contract passes with the same fixture. No claim of Qt or Tauri superiority is made here.

The persistence candidate is SQLite metadata plus a project asset directory. The released runtime must identify its actual SQLite version/source ID and satisfy the applicable WAL safety gate; the recent SQLite WAL-reset fix makes package provenance a release requirement, not a documentation detail. [SQLite 3.51.3 release notes](https://www.sqlite.org/releaselog/3_51_3.html)

## 8. Local AI and external-service policy

The default ASR, translation, alignment, and TTS path is local. Candidate implementations are selected by measured quality, timestamp behavior, hardware support, install size, offline behavior, and license chain. Current candidates remain a shortlist, not a lock: Whisper-family runtimes, Qwen ASR/alignment, Qwen or similar local translation, and Kokoro/Qwen-style local TTS require the experiments and distribution checks in Round 3.

Any external provider is an explicit BYOK action. Secrets belong in the OS credential store, never project JSON, logs, screenshots, or exported artifacts. The UI must show the exact request boundary and must not silently fall back from local execution to a cloud service.

## 9. Workspace and UI contract

The proposed shell has logical workspaces for media/project setup, source transcript, bilingual translation, dubbing/takes, and export/review. A four-track editing view, layout presets, a controllable splitter, stage-local language labels, and explicit synthetic/loading/error states are appropriate design direction.

The Human UI Gate is still open. Acceptance requires a real visual and keyboard review of the current HTML sample plus a framework slice using real IME composition, accents, emoji, RTL text, focus traversal, splitter behavior, 10k-span virtualization, stale/late states, and export failure states. The sample is not evidence of implemented performance or accessibility.

## 10. Persistence, resources, and recovery

Project writes are serialized by the controller. File outputs use staging, validation, flush/replace, publish, and metadata commit steps with orphan reconciliation. Backups must preserve database consistency and referenced artifacts.

Resources are immutable revisions identified by exact source, version, hash, license, backend, hardware requirements, and install location. Downloads use staging and verification; mutable “latest” resources, unsigned catalogs, arbitrary install scripts, incomplete license chains, or unclear redistribution rights fail the distribution gate.

## 11. Export and support contract

Every export records its input revision, cue snapshot, media probe, renderer/FFmpeg build profile, fonts, audio take, and warnings. FFmpeg is a production dependency whose build, codec profile, and license notices must be identified; successful command construction alone is insufficient.

Support documentation must state the tested OS/runtime, exact model/backend/resource revision, hardware profile, quality/timestamp limits, installation and offline behavior, privacy boundary, and restore behavior. “Runs on Windows” is not a sufficient support claim.

## 12. Product gates

- **PG-01 Workflow:** representative videos without usable subtitles can complete media import, local ASR, Source Transcript correction, bilingual subtitle review, single-narrator dubbing, and subtitle/media export with recoverable edits, inspectable timing, and no silent data or privacy boundary changes. Agree fixture-level completion and usability criteria before acceptance.
- **PG-02 Language:** evaluate the EN/ZH/FR anchor set and candidate directions, then explicitly approve the V2.0 release matrix from measured stage and pair capabilities; unsupported directions are surfaced before work begins.
- **PG-03 Quality/timing:** ASR, translation, alignment, and dubbing meet agreed fixture-level quality and timing criteria.
- **PG-04 Hardware/runtime:** selected local paths pass the declared CPU/GPU matrix without silent fallback.
- **PG-05 UI:** Human UI Gate passes visual, keyboard, IME, RTL, accessibility, and large-document checks.
- **PG-06 Persistence:** revision, stale-result, crash-recovery, backup/restore, and orphan-reconciliation checks pass.
- **PG-07 Distribution:** every bundled or downloaded asset has a verified license and provenance chain; FFmpeg, fonts, G2P/phonemizer, model weights, native libraries, and WebView/runtime terms are included.
- **PG-08 Privacy/BYOK:** local mode is demonstrably offline; external calls are explicit, inspectable, and credential-safe.
- **PG-09 Export:** SRT/VTT/ASS/text, burned-in media, and dubbing audio replacement or mix exports are deterministic and tested on representative media.
- **PG-10 Workflow re-scope:** if licensing or feasibility prevents either required V2.0 Product Workflow, obtain an explicit Product decision on revised release scope; a failed gate does not silently turn that workflow into an optional feature.

## 13. Smallest implementation sequence after approval

1. Freeze the domain, worker protocol, resource manifest, and 10k-span fixture.
2. Run the framework slice with stub workers and close the Human UI Gate.
3. Implement persistence/recovery and media probe before real model integration.
4. Add one measured local ASR path, then evaluate the six EN/ZH/FR translation directions and decide the V2.0 release matrix.
5. Add one licensed single-narrator TTS path and dubbing/timing evidence.
6. Complete FFmpeg export, resource delivery, notices, offline verification, and support documentation.

No phase may claim release readiness while a product gate is pending or while a dependency's source-code license has been confused with its model-weight, native-library, font, or provider terms.

## 14. Definition of done for the scope milestone

This scope milestone is complete when the user accepts this document as the V2 design input, the decision register records every open gate, the framework slice contract is executable by the design/engineering agent, and the research reports provide inspectable evidence for every non-trivial architecture and licensing constraint. Production implementation, model benchmarking, packaging, and UI acceptance remain later milestones.
