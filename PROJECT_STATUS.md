# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-05

## Current milestone

**Milestone 13 — Release Candidate & Signed Release / Minimum Runtime-Fidelity Packaging Experiment (Issue #27): Phase C FINAL ACCEPTED.**

Milestone 13 Minimum Runtime-Fidelity Packaging Experiment is executing on dedicated branch `milestone/13-release-candidate` governed by Wayfinder charter packages #17–#26 and execution issue #27:
- **Phase A — Frozen Inputs & Experiment Scaffold: ACCEPTED (2026-09-05)**:
  - Authoritative build-base identity frozen in `docs/m13_build_base_identity.json` and `.md` across 85 wheels/sdists, CPython 3.12.10 embeddable archive, and 3 authoritative ONNX models.
  - Fail-closed scaffold test suite in `tools/packaging/validate_scaffold.py` with 13 passing tests.
- **Phase B — Primary Runtime Assembly & First Installer Build: ACCEPTED (2026-09-05)**:
  - First-party launcher `GlyphCue.exe` compiled and inner-signed with test certificate `A3E4E5320779C9F63E513D870E209C26B819C61E`.
  - Authoritative models (`PP-OCRv6_det_medium.onnx`, `PP-OCRv6_rec_small.onnx`, `ch_ppocr_mobile_v2.0_cls_mobile.onnx`) and migrations assembled.
  - CycloneDX 1.6 JSON SBOM and Payload Manifest generated; Inno Setup offline installer built.
- **Phase C — Clean Reconstruction & Drift Verification: FINAL ACCEPTED (2026-09-05)**:
  - Two independent clean reconstructions (Clean Reconstruction A and Clean Reconstruction B) produced from trusted source commit `5905df09d012cb63a34b98c484b43958477e52e8`. The earlier same-session AG baseline was contaminated by local checkout bytecode and is superseded.
  - Strict payload drift verification across 21,712 total files: 21,711 unsigned payload files compared with 0 mismatches (100% byte-for-byte SHA-256 equality); 0 missing/additional files.
  - First-party launcher `GlyphCue.exe`: pre-sign SHA-256 identical (`0a1612e3f5897f4147a758c045723aafacaeba206218327d5296f72202569102`), post-sign SHA-256 identical (`187ee188700d0ec599cbbe0854931967e35bab90fd5e09409fb7d18320516e17`), Authenticode signature valid under approved test certificate `A3E4E5320779C9F63E513D870E209C26B819C61E`.
  - Inno Setup installer envelope comparison: size delta 496 bytes within allowed Inno Setup header/timestamp and PKCS#7 envelope delta; signatures valid on both. Envelope verdict: **PASS**.
  - Manifest-to-disk reconciliation: 100% path and file count match (21,711 files) on both reconstructions with 0 unindexed and 0 missing files.
  - Gate verdicts: Integrity Gate: PASS, Untracked File Gate: PASS, Provenance Gate: PASS, Release Redistribution Compliance Gate: OPEN (recorded). Overall Phase C verdict: **FINAL PASS / ACCEPTED**.
- **Phase D — Target-Machine Offline Runtime & DirectML Validation**: **NOT STARTED (eligible next)**.
- **Release Status**: **Release Ready = NO** (Phase D and Release Redistribution Compliance Gate pending).
- **Release Redistribution Compliance Gate**: **OPEN**.

### Validation
- Clean Reconstruction A vs B Verification: **PASS** (21,711/21,711 unsigned files identical, signed PE identical, installer envelope PASS).
- Packaging Experiment Scaffold & Drift Test Suite (`tools/packaging/validate_scaffold.py`): **13 passed** (including manifest-to-disk reconciliation and strict offline staging regressions).
- Phase C Isolated Clean Reconstruction & Drift Pipeline (`tools/packaging/execute_phase_c.py`): **PASS** (zero unsigned file drift, zero signed PE drift, envelope drift PASS).
- Private Runtime Local Import Sanity Checks: **PASS** (imports and migrations verified on disposable scratch copies; DirectML hardware acceptance reserved for Phase D).
- Product Hardening II Targeted Suite (`tests/ui/test_product_hardening_ii_seams.py`): **5 passed** in 1.03s.
- Product Hardening II Affected Suites: **53 passed** in 3.95s.
- Local Whole-Repository Regression: **962 passed, 1 skipped, 1 xfailed** in 172.06s (0 failures).
- DirectML Hardware Preflight: **PASS** (`DmlExecutionProvider` confirmed active on detector and recognizer).
- GitHub Actions Clean-Environment CI: **SUCCESS** (Run `33966863334`, CI #152).
- Final Human Acceptance: **PASS** (repository owner real-product smoke check).
- Stage ① UI Suite: **310 passed, 1 xfailed** (100% UI pass rate).
- Stage ② Targeted Test Suites:
  - Cue Cleaning domain/adapter tests (`tests/application/test_cue_cleaning.py`): **25 passed**.
  - Clean Cues UI integration tests (`tests/ui/test_clean_cues_integration.py`): **14 passed**.
- Whole-Repository Regression (M12 Stage ② baseline): **957 passed, 1 skipped, 1 xfailed**.

### Milestone 11 Retrospective Summary (CLOSED)

Every acceptance-gate item in ROADMAP.md §18 executed with real,
CI-verified evidence (see the full stage-by-stage record below,
unchanged from how it happened). After hands-on re-testing of the
packaged product, the repository owner rejected Release Acceptance for
three release-blocking reasons not caught by the automated gates below:

1. The release-blocking Cue-quality finding comes from the repository
   owner's hands-on product-level retest of the approved ≤5× DirectML
   production path, where the final reconstructed Cue output contained
   too many low-value / duplicate / fragmented Cues to be accepted for
   release. The fail-closed DirectML DevQA verifier (see "DevQA DirectML
   verification asset", below) separately proved that the intended
   DirectML backend and `DmlExecutionProvider` were genuinely reachable
   and active. Its periodic raw Observation confirmations are expected
   diagnostic behavior and are not, by themselves, evidence of defective
   final Cue output. The first causal seam responsible for the
   unacceptable final Cue quality remains unresolved and is explicitly
   deferred to Milestone 12 Stage ②.
2. QA review UX was not acceptable: `Discard` did not remove a discarded
   Cue from the visible workspace, Pending/Needs-Review/Approved state
   interleaving broke linear/chronological review, and junk-Cue volume
   reaching the review surface was too high (addressed in Stage ①).
3. Windows packaging remains exploratory — Nuitka was already retired
   mid-milestone, and PyInstaller's own collection-gap fixes (Stage
   ⑦-C, below) are themselves evidence of an immature packaging path.

**Disposition:** `Release Ready = NO`. Release/Packaging work is
**SUSPENDED**. Feature Freeze is lifted only for the corrective rework
scoped in **Milestone 12 — Product Rework & Cue Quality Recovery**
(ROADMAP.md §19) — it is not a general reopening of V1 feature scope.
The originally-next Release Candidate milestone is renumbered to
Milestone 13 (ROADMAP.md §20) and does not begin until Milestone 12 is
complete and accepted, followed by a second Product Hardening & Full
Regression pass. See "Git / PR status" and "Next action" below.

### DevQA DirectML verification asset (added 2026-09-04, retained after closure)

A DevQA-only, fail-closed verification entrypoint was added to make the
DirectML production path's real behavior observable going forward,
independent of the UI's downstream grouping/reconstruction layer:

- [`tools/devqa_directml_verify.py`](tools/devqa_directml_verify.py) —
  constructs `DirectMlOcrEngine`/`DirectMlTextDetector` for real, drills
  to the raw ONNX Runtime sessions, asserts `DmlExecutionProvider` is
  active on both, exits non-zero with a clear reason on any failure.
  Never silently falls back.
- [`Launch-GlyphCue-DirectML-DevQA.bat`](Launch-GlyphCue-DirectML-DevQA.bat) —
  runs that preflight and refuses to launch on failure; otherwise starts
  the same `python -m glyphcue` product UI (same `PRODUCTION_TRIGGER`
  pipeline, same Architecture B — no new pipeline, no new UI toggle, no
  user-facing backend selection).
- Uses a dedicated, disposable venv (`.venv-directml-devqa/`, gitignored)
  with the `[directml]` extra installed, kept separate from the trusted
  `.venv`. Not part of the shipped product; diagnostic-only.
- This tool proves backend reachability/provider activation and
  preserves a deterministic way to reproduce the intended DirectML
  production runtime. Its periodic raw Observation confirmations are
  diagnostic evidence only; they must not be cited as proof of defective
  final Cue quality.
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Stage ⑤ **Representative Evaluation is
CLOSED by Human Adjudication (2026-09-03)** — the M10 transferred
acceptance gate 9 (ROADMAP §18) is fully satisfied across all five frozen
windows (`sample_g`, `sample_e`, `sample_h`, `sample_f`, `sample_c`, 180 s
each) plus clean baseline reserve `sample_a` (177 s), all achieving 100%
window coverage with zero crashes.

Following the earlier split-profile stress run (§15) and single-language
completion supplement (§16, which triggered the closed Caption Identity
Corrective Gate), the **bilingual completion supplement (§17)** ran
`sample_h` (900–1080s), `sample_f` (560–740s), and `sample_c` (480–660s)
to 100% completion under the formal Architecture B + DirectML product path:
- **Coverage & Realtime:** All three windows completed 180/180 s (100.0%).
  Realtime ratios measured **2.71×** (`sample_h`), **3.66×** (`sample_f`),
  and **4.16×** (`sample_c`) — all strictly ≤5.0× realtime, closing the
  M11 performance target and resolving the CPU baseline bottleneck.
- **Correctness & Multilingual Separation:** Point recall was **100.0%
  (31/31 verified instants)** across all three bilingual samples (`h`: 10/10,
  `f`: 11/11, `c`: 10/10). `multilingual_missing_layer_count` was **0** and
  `multilingual_wrong_assignment_count` was **0** across all 31 instants.
  Zero layer swaps in conversational speech.
- **Residual Documented Limitations:**
  - `sample_c`: An isolated non-text reading (`"zh": "3\n8"`) on Cue 1
    (480.0–481.1s, 1.1s) safely fail-closed with `ambiguous_languages: ["zh"]`;
    it did not contaminate Cue 2 (481.1s, CER 0.0) or downstream cues (7/10
    verified instants achieved CER 0.0000).
  - `sample_f`: Screen-recording b-roll editor toolbar glyphs (`B I U S ミ H1 H2`)
    recognized into `zh` with fail-closed ambiguity flags.
Stage ⑤ is CLOSED. Stage ⑥ **Full Regression is CLOSED by Human
Adjudication (2026-09-03)**, on baseline `906f9e7`. Evidence split
explicitly:

- **GitHub Actions is authoritative** for the automated, whole-repository
  regression required by ROADMAP §18 ("Automated regression" — Path A,
  Path B, persistence, jobs, export, cancellation, migrations, settings,
  offscreen UI): clean `ubuntu-latest`/Python 3.12, unfiltered `pytest`,
  green on the Stage ⑥ evidence baseline `906f9e7` (run `33823586648`).
  Not duplicated locally.
- **Stage ⑥ additionally audited platform-specific branches** —
  `sys.platform == "win32"` appears in 7 source files; 6 were already
  exercised by CI-run mocks. The one meaningful Linux-CI coverage gap
  (`src/glyphcue/application/source_identity.py`'s Windows-only
  case-folding/forward-slash branch, never taken on a Linux runner and
  never asserted by any existing caller) was closed with three
  deterministic regression tests
  (`tests/application/test_source_identity.py`, `sys.platform` mocked so
  they run identically on any CI runner) — commit `906f9e7`, CI green.
- **Real Windows verification** (this milestone's already-established
  current-product evidence, not re-run for Stage ⑥ specifically): both
  directions of DirectML selection/fallback confirmed on real Windows
  hardware — `create_ocr_engine`/`create_text_detector` correctly fall
  back to Paddle CPU without the `[directml]` extra installed, and
  correctly resolve to `DirectMlOcrEngine`/`DirectMlTextDetector` (with
  `DmlExecutionProvider` confirmed present) and complete real end-to-end
  multilingual evidence jobs when it is.
- **Deliberately NOT Stage ⑥ evidence, deferred to Stage ⑦:** actual
  packaging, clean-machine package execution, and Formal Human QA. No
  pytest re-run and no private-corpus re-evaluation were performed for
  this closure — documentation/lifecycle reconciliation only.

### Stage ⑦-A/⑦-B Packaging Hardening & Technical Smoke (2026-09-04)

**Nuitka/pyside6-deploy retired as the packaging path.** Five controlled
build attempts (2026-09-03/04, diagnosed under strict single-variable-
change discipline) hit repeated build-system/resource blockers on this
machine — a MinGW64 cache-extraction race, RAM exhaustion during the
Scons/gcc compile phase, an indeterminate codegen-phase stall, an
unclassified near-instant silent exit, and RAM exhaustion again during
Nuitka's own Python-analysis phase even under `--jobs=2`. Human
adjudication (2026-09-04) retired Nuitka as the V1 packaging path rather
than continuing to chase compiler-toolchain issues, and activated
**PyInstaller — already documented in ROADMAP.md's Packaging section as
the existing fallback**, not a newly invented path. A concise diagnostic
summary of the abandoned Nuitka attempts is preserved locally
(`prompt-drafts/M11-Stage7A-Nuitka-Abandoned-Summary-2026-09-04.md`,
git-excluded); the large disposable Nuitka cache, build output, watchdog
scripts/logs, and probe venv have been deleted.

**PyInstaller onedir build: real, successful, on the formal baseline**
(commit `81ace857`, dedicated disposable venv
`.glyphcue-pyinstaller-venv`, Python 3.12, `pip install -e ".[ocr,directml]"`
+ `pyinstaller`/`pyinstaller-hooks-contrib`, entry `src/glyphcue/__main__.py`,
`--collect-data glyphcue.persistence.migrations_sql --collect-submodules glyphcue --windowed`).
Build completed in ~161s (pure analysis/packaging, no C compilation —
no RAM pressure observed), producing a 779 MB onedir directory. Verified
present in the bundle: `migrations_sql/*.sql` (all 5 migrations),
`onnxruntime/capi/DirectML.dll`, PyAV's own bundled FFmpeg DLLs
(`av.libs/avcodec-62-*.dll` etc.), and Qt Multimedia's FFmpeg/Windows
Media Foundation backend plugins (`PySide6/plugins/multimedia/*.dll`) —
all auto-discovered by PyInstaller's standard hooks with no product-code
changes.

**Technical smoke, all real (no mocks):**
- Launch/exit: packaged `GlyphCue.exe` launched cleanly under an
  isolated `USERPROFILE` (never touching real user data), showed the
  correct window title, stayed alive, and closed cleanly via `WM_CLOSE`
  (exercises `closeEvent`/`commit_pending_edits`) with zero orphan
  processes.
- Default-mode/UI rendering: a foreground-verified native screenshot
  (method per persisted session convention) confirmed the packaged app
  renders identically to source — defaults to Path A: Video Extraction
  with ROI fields, Play/Pause, and "Run OCR Evidence" all visible and
  styled correctly, proving Qt plugins/stylesheet/fonts loaded correctly
  from the frozen bundle. (One earlier capture showed Path B active;
  root-caused to a concurrent manual click during that capture window,
  not a packaging defect — reproduced clean twice after.)
- Persistence initialization: packaged app created
  `<profile>\.glyphcue\glyphcue.sqlite3` and applied all 5 migrations
  (`schema_migrations` = `[1,2,3,4,5]`; `cues`, `language_layers`,
  `track_groups`, `observations` tables all present) — confirmed by
  direct SQLite inspection.
- OCR/DirectML provider selection: `create_ocr_engine`/
  `create_text_detector` invoked directly against the exact dependency
  versions bundled into the package (same `.glyphcue-pyinstaller-venv`)
  — `prefer_directml=False` resolves to `PaddleOcrEngine`/
  `PaddleOcrTextDetector`; `prefer_directml=True` resolves to
  `DirectMlOcrEngine`/`DirectMlTextDetector` with RapidOCR's own log
  confirming `"try to use DirectML as primary provider"`. **Correction
  (see below): this smoke only exercised *construction*, not
  `.initialize()`. The Paddle CPU path's `initialize()` had a real,
  frozen-only failure that this construction-only check did not catch —
  found the same day via real manual Stage ⑦-C testing and fixed; see
  "Stage ⑦-C manual testing" below.** The DirectML `initialize()` path
  was separately real-hardware-verified earlier in M11 (P3/P4B gates)
  and is unaffected by this fix.
- Not automated (no native UI-automation tool available in this
  session): a full click-driven Path B / caption-import / OCR-run pass
  through the actual packaged GUI. Application logic itself is unchanged
  by packaging and already covered by the pytest suite; this gap is
  listed under Stage ⑦-C below.

No GlyphCue product code was changed for any of this — the whole
packaging-contract audit resolved through PyInstaller's standard hook
discovery plus explicit `--collect-data`/`--collect-submodules` flags.

### Stage ⑦-C manual testing — Run OCR Evidence failure, found and fixed (2026-09-04)

Real human click-through on the packaged `.exe` (Path A: open video → set
range → **Run OCR Evidence**) failed immediately: `Failed: OCR evidence
job failed after 0.02s (0 frames analyzed, 0 OCR calls, 0 observations
kept)`. Diagnosed under the `diagnosing-bugs` discipline:

- `Job._run` (`src/glyphcue/jobs/job.py:79`) does `except Exception:
  self._set_state(JobState.FAILED)` with **no logging of the exception**
  — a pre-existing product-code gap (not packaging-specific, not touched:
  out of this gate's scope) that made the real error invisible in the UI.
- Built a throwaway PyInstaller repro (`create_ocr_engine("en",
  prefer_directml=False).initialize()` only, `--console` build) to
  recover the real traceback outside the swallowing `Job` wrapper. The
  same call succeeds unfrozen (same venv, same dependency versions) —
  proving the defect is packaging-specific, not a dependency/version
  problem.
- **Root cause, three stacked layers, all pure PyInstaller collection
  gaps, zero product code involved:**
  1. `paddlex/configs/pipelines/OCR.yaml` (and the rest of
     `paddlex/configs/`, ~1.3 MB) was never collected — no
     `pyinstaller-hooks-contrib` hook exists for `paddlex` — so
     `paddlex.inference.pipelines.load_pipeline_config` raised
     `Exception: The pipeline (OCR) does not exist!`. Fix:
     `--collect-data paddlex`.
  2. `paddlex.utils.deps.require_extra` gates OCR pipeline creation on
     `importlib.metadata` seeing installed-distribution metadata for its
     "ocr-core" extra's six dependencies (`imagesize`,
     `opencv-contrib-python`, `pyclipper`, `pypdfium2`, `python-bidi`,
     `shapely`) — PyInstaller does not copy `.dist-info` by default, so
     every one of these looked "not installed" even though the actual
     package files were present and functional. Fix: `--copy-metadata
     paddlex` plus `--copy-metadata` for each of the six.
  3. Paddle's inference runtime loads several of its own bundled DLLs
     (`paddle/libs/mklml.dll` and others) dynamically at runtime rather
     than via static PE imports, so PyInstaller's automatic binary-
     dependency scan missed them (only `mkldnn.dll` was auto-detected) —
     `RuntimeError: (PreconditionNotMet) ... mklml.dll ... error code is
     126`. Fix: `--collect-binaries paddle`.
- Verified the fix at each layer individually (three intermediate
  throwaway repro builds, one per layer) before combining, then verified
  the full combination reaches `initialize() OK`, then rebuilt the real
  `GlyphCue.exe` with the complete flag set and confirmed
  `paddle/libs/mklml.dll` and `paddlex/configs/pipelines/OCR.yaml` are
  now both present in the bundle (880 MB, up from 779 MB).
- All throwaway repro builds/scripts deleted after verification
  (`diagnosing-bugs` Phase 6 cleanup); nothing left in the repo or on
  disk beyond the fixed real build.

**Historical last-verified M11 PyInstaller onedir reproduction/build
command (preserved as engineering evidence only; not an active release
path and not a forward packaging decision — supersedes the ⑦-A command
above only in the sense that it reflects the latest state this
investigation reached, preserved only so the M11 packaging investigation
remains reproducible if future research needs it):**

```
pyinstaller --noconfirm --clean \
  --name GlyphCue \
  --collect-data glyphcue.persistence.migrations_sql \
  --collect-submodules glyphcue \
  --collect-data paddlex \
  --copy-metadata paddlex \
  --copy-metadata imagesize \
  --copy-metadata opencv-contrib-python \
  --copy-metadata pyclipper \
  --copy-metadata pypdfium2 \
  --copy-metadata python-bidi \
  --copy-metadata shapely \
  --collect-binaries paddle \
  --collect-all rapidocr \
  --windowed \
  src/glyphcue/__main__.py
```

(`--collect-all rapidocr` added 2026-09-04 by the Stage ⑦ Runtime Default
Corrective Gate below — the version above without it produces a package
that cannot use DirectML at all. 911 MB onedir output, up from 880 MB.)

**Not yet re-verified after this fix:** the actual click-driven "Run OCR
Evidence" pass on the rebuilt `GlyphCue.exe` (this session verified the
fix at the `create_ocr_engine(...).initialize()` reproduction level,
identical to the exact failure point observed in the UI, but has no
native UI-automation tool to click the button itself). **This is now the
first item of Stage ⑦-C**: re-run the same manual click-through
(open video → Run OCR Evidence → confirm real observations are produced,
not just "no crash") on the rebuilt `.exe` at
`.glyphcue-pyinstaller-build\dist\GlyphCue\GlyphCue.exe`.

### Stage ⑦-C manual testing — packaged-performance isolation (2026-09-04)

Real human testing on the (Paddle-fixed) packaged `.exe` measured
`sample_g` (10.05–20.05s, monolingual) at **~20× slower than realtime**,
far outside the ≤5× target the user recalled from earlier M11 performance
hardening. Diagnosed under `diagnosing-bugs`: is this a packaging
regression, or expected behavior of whichever code path actually ran?

**Isolation benchmark** (`build_ocr_evidence_job` invoked directly,
identical video/ROI/range/code path, no competing CPU-heavy process —
verified via CPU-delta sampling before each run):

| Environment | Engine | OCR call latency (mean/median/P95) | Realtime cost |
|---|---|---|---|
| dev `.venv`, unfrozen, CPU Paddle (default) | `PaddleOcrEngine` | 41724 / 42219 / 62219 ms | **108.4×** |
| Packaged `.exe`, CPU Paddle (default, no env var) | `PaddleOcrEngine` | (user's original report) 5896 / 3625 / 11351 ms | 19.7× |
| pyinstaller-venv, unfrozen, DirectML (`prefer_directml=True`) | `DirectMlOcrEngine` | 270.6 / 188.0 / 359.0 ms | **4.02×** |
| Packaged `.exe` (throwaway repro, DirectML forced) | `DirectMlOcrEngine` | 308.7 / 203.0 / 375.0 ms | **4.19×** |

(Realtime cost = wall-clock seconds per media second processed, same
convention as `sample_h`/`sample_f`/`sample_c`'s 2.71×/3.66×/4.16×
elsewhere in this file — lower is faster; ≤5.0× is the M11 performance
target.)

**Finding: not a packaging regression.** The unfrozen dev `.venv` running
the exact same default CPU path was, if anything, *slower* than the
user's packaged run (108× vs 20× — noise/thermal/content-dependent, not
a meaningful "packaging made it faster" claim either). `PaddleOcrEngine`
explicitly sets `enable_mkldnn=False` (`paddleocr_engine.py:41`, a
deliberate workaround for a real paddleocr==3.7.0/paddlepaddle==3.3.1
crash — see the code comment and ADR-0001), which disables Intel's CPU
inference acceleration; this repo's own history already documents plain
CPU-path runs at 7×–159× depending on content (see the Chinese-CER
integration smoke and the Hybrid/Production profile comparison earlier
in this file). The **≤5× realtime target was only ever met via the
opt-in DirectML acceleration** (`GLYPHCUE_PREFER_DIRECTML_OCR=1` /
`GLYPHCUE_PREFER_DIRECTML_DETECTOR=1`, the P3/P4B performance-hardening
gates) — not the shipped default. The packaged DirectML run (4.19×)
closely reproduces the unfrozen DirectML run (4.02×): packaging is
performance-neutral once the same code path is actually exercised.

**Real DirectML provider confirmation on the packaged repro** (not just
the "try to use DirectML" log line): `text_det.session.session.get_providers()`
and `text_rec.session.session.get_providers()` both returned
`['DmlExecutionProvider', 'CPUExecutionProvider']` — DirectML genuinely
active, not silently falling back to CPU.

**Model provenance confirmed clean:** the packaged repro's RapidOCR
models resolved to `_internal\rapidocr\models\*.onnx`
(`PP-OCRv6_det_small.onnx` 9,929,594 bytes, `PP-OCRv6_rec_small.onnx`
21,234,383 bytes, `ch_ppocr_mobile_v2.0_cls_mobile.onnx` 585,532 bytes) —
RapidOCR's own "File exists and is valid" check passed against the
already-installed venv copies (via `--collect-all rapidocr`), so nothing
was silently downloaded or hand-copied to make the number look good.

**New, separate packaging-completeness finding (not a performance issue):**
the `rapidocr` package is **entirely absent** from the current real
`GlyphCue.exe` build (`_internal\rapidocr\` does not exist) — the
canonical build command above only fixed the CPU Paddle path
(`--collect-binaries paddle` etc.); it never added `--collect-all
rapidocr` for the DirectML path. This means **the packaged product today
cannot use DirectML at all**, even with the opt-in env vars set — it
would fail with `ModuleNotFoundError`, not silently fall back (the
`create_ocr_engine`/`create_text_detector` preflight only catches
*platform/init* failures, not a missing module in a frozen bundle it
never expected). This needs its own fix (`--collect-all rapidocr` added
to the canonical build command) before Stage ⑦-C can close — tracked as
a new checklist item below, separate from the release-policy question.

### Stage ⑦ Runtime Default Corrective Gate (2026-09-04) — CLOSED by Human Adjudication

Human adjudication approved closing both remaining items above together
as one small corrective gate: (1) the `rapidocr` packaging-completeness
blocker, (2) changing Windows production's DirectML policy from hidden
opt-in to default-preferred-with-verified-fallback. Executed under
`/tdd`.

**1. Packaging-completeness fix.** `--collect-all rapidocr` added to the
canonical PyInstaller onedir build command (now the fourth and final
addition, alongside the Paddle/paddlex fixes). Real `GlyphCue.exe`
rebuilt (911 MB, up from 880 MB) and verified: `_internal\rapidocr\models\`
contains all three real `.onnx` files bundled from the already-installed
venv copies (`--collect-all` pulls the actual installed package data, not
a fresh download) — same files, same byte sizes, as the earlier
isolation benchmark's provenance check above.

**2. Runtime default policy change** (`src/glyphcue/ui/app.py`): the two
env vars were renamed and their polarity flipped —
`GLYPHCUE_PREFER_DIRECTML_OCR`/`GLYPHCUE_PREFER_DIRECTML_DETECTOR`
(opt-in; had to be set to `"1"` to get the accelerated backend) are now
`GLYPHCUE_DISABLE_DIRECTML_OCR`/`GLYPHCUE_DISABLE_DIRECTML_DETECTOR`
(opt-out; a normal launch with no env var set now attempts DirectML
first). `create_ocr_engine`/`create_text_detector` themselves are
unchanged — same real platform/package preflight, same real
initialization probe, same automatic fallback to
`PaddleOcrEngine`/`PaddleOcrTextDetector` on any unsupported platform,
missing install, or provider-init failure; Paddle remains the resilience
fallback inside the single `PRODUCTION_TRIGGER` pipeline, not a second
pipeline, and no retired Hybrid selector was touched. The env vars were
kept, not deleted — repurposed as a DevQA/support override to force
deterministic Paddle-only testing, which the task explicitly asked to
preserve if still justified.

**TDD (`tests/ui/test_app_path_a_entrypoint.py`):** red-then-green at the
real seam (`app_module._ocr_engine_factory`/`_hybrid_detector_factory`,
the exact callables `PathAMediaPane`/the shared detector wiring call).
Old opt-in tests replaced with: default-prefers-DirectML-when-supported,
falls-back-to-Paddle-when-unsupported, falls-back-to-Paddle-when-the-real-
probe-fails, and forced-to-Paddle-when-explicitly-disabled — one test per
env var, mirrored for both the OCR engine and text detector factories (8
new/changed tests total). The one existing test that exercises a real Job
run (`test_create_path_a_app_constructs_the_live_single_language_runtime`)
was pinned to `directml_platform_supported() -> False` so it stays
deterministic now that the default actually attempts DirectML, rather
than depending on what happens to be installed in whichever machine runs
it. Targeted run: 12 passed. Full `tests/ui` + `tests/adapters` +
`tests/application`: **793 passed, 1 skipped, 1 xfailed** (177s,
unrelated pre-existing skip/xfail) — no regressions from the default
flip.

**Real packaged smoke** (frozen repro built with the exact same
now-complete flag set as the real `GlyphCue.exe`, invoking the real
`app_module._ocr_engine_factory` — not a hand-rolled substitute):

- Default (no env var): `DirectMlOcrEngine` selected; `get_providers()`
  confirmed `['DmlExecutionProvider', 'CPUExecutionProvider']` on both
  the detector and recognizer sessions — real acceleration, not a log
  message taken on faith.
- Real OCR-evidence run on `sample_g` (10.05–20.05s), same conditions as
  the isolation benchmark above (no competing CPU load): 25 OCR calls,
  65 observations, **Realtime cost = 5.48×** on that single run — a real
  first-look number, but numerically above the ≤5.0× target on its own,
  so not accepted as evidence of meeting the target without repeating it.
- `GLYPHCUE_DISABLE_DIRECTML_OCR=1`: `PaddleOcrEngine` selected as
  required, and a real `.initialize()` call succeeded — the DevQA
  override and the Paddle resilience fallback both proven working in the
  actual packaged product, not just in source.

**Evidence-inconsistency follow-up (2026-09-04, same day):** a single
5.48× run is not enough to adjudicate against a ≤5.0× target — re-ran the
identical packaged `sample_g` (10.05–20.05s) DirectML smoke **three
times in one process**, confirmed idle machine each time (no competing
build/test/OCR load), same real `app_module._ocr_engine_factory` default
path, freshly re-selecting/re-initializing the engine each run:

| Run | Engine | Providers (det/rec) | Realtime cost |
|---|---|---|---|
| 1 | `DirectMlOcrEngine` | `DmlExecutionProvider` (both) | 4.806× |
| 2 | `DirectMlOcrEngine` | `DmlExecutionProvider` (both) | 5.192× |
| 3 | `DirectMlOcrEngine` | `DmlExecutionProvider` (both) | 4.489× |

**Median = 4.806× ≤ 5.0×.** All three runs independently confirmed
`DirectMlOcrEngine` selected and `DmlExecutionProvider` genuinely active.
Per the pre-committed adjudication rule (median decides, ≤5.0× closes the
seam, >5.0× would have required stopping and reporting rather than
redefining the target), **this closes the evidence gap**: the packaged
DirectML path meets the M11 ≤5.0× performance target, with normal
run-to-run variance (4.49×–5.19×, a ~15% spread) rather than a
regression — the original 5.48× stands as an upper-bound single
observation, not the representative figure.

**Cleanup:** all throwaway repro builds/scripts for this gate deleted
after verification, matching every prior packaging repro this session.

**CI confirmation:** GitHub Actions run `33894871162` for commit
`3380478` (this gate's code/test commit) completed **success** — full
automated regression is green on the actual pushed changes, not just the
793-test local subset run before pushing.

**Stage ⑥ evidence baseline refreshed to `4afb8d4`** (human-adjudicated;
not a reopening of Stage ⑥ itself). Between `906f9e7` and `4afb8d4`, the
**M11 Legacy Pipeline Retirement Corrective Gate** removed
`EXPERIMENTAL_HYBRID` as a product/DevQA-reachable pipeline: no UI
control, launch-time switch, or env var anywhere in `src/` can select it
anymore (`path_a_media_pane.py`'s `dev_ocr_profile_combo` /
`enable_dev_ocr_profile_selector`, and `app.py`'s
`GLYPHCUE_DEV_OCR_PROFILE_SELECTOR`, are gone entirely). The
implementation (`hybrid_evidence_job.py`, `hybrid_cascade_dry_run.py`,
`caption_identity_verification.py`, `occupancy_normalized_distance.py`,
`sparse_observation_semantics.py`, `text_anchored_region_mask.py`, and
the `EXPERIMENTAL_HYBRID` enum member) is deliberately KEPT, not
deleted: fresh import analysis found it load-bearing for 8 tracked
benchmark scripts, including `benchmarks/private_video_corpus/run_evaluation.py`
(the script that produced this document's own Stage ⑤ evidence numbers
above) — deleting or relocating it risked either breaking that tracked
tooling or a scope-expanding refactor across 8 files, both explicitly
ruled out. `paddleocr_text_detector.py`'s docstring, previously stale
(claimed to exist "ONLY" for the dev profile), is corrected: it is
shared, load-bearing production infrastructure for the shipped
multilingual `PRODUCTION_TRIGGER` path. DirectML→Paddle fallback is
untouched. Targeted tests green (`tests/application` 416,
`tests/adapters` 82+1 skipped, `tests/ui` 292+1 xfailed), GitHub Actions
whole-suite CI green (run `33828500457`), and a real Windows smoke via
the actual `create_app`/`main()` launch entrypoint confirmed
`dev_ocr_profile_combo` no longer exists as an attribute and
`hybrid_detector_factory` remains correctly wired for multilingual
production runs. Full Regression itself was not repeated for this
change — targeted tests plus CI's own whole-suite run were treated as
sufficient, consistent with Stage ⑥'s own evidence discipline above.
**Residual finding surfaced during this smoke — since diagnosed and
fixed (`face04b`, separate small Corrective Gate, 2026-09-04):** in this
worktree's `.venv` (plain `onnxruntime` + `cv2` + `pyclipper` installed
but not the pinned `[directml]` extra), `create_text_detector(prefer_directml=True)`
was returning a `DirectMlTextDetector` instance even though
`DmlExecutionProvider` was not actually available —
`onnxruntime.InferenceSession` silently substitutes `CPUExecutionProvider`
instead of raising, so the detector's own initialization probe reported
success on a session that was really running on CPU the whole time.
Fixed in `_ExactPaddleDirectMlDetectorBackend.initialize()`
(`directml_text_detector.py`): the session's own `get_providers()` is
now checked after construction, and initialization raises explicitly if
`DmlExecutionProvider` isn't actually active, routing through the
existing probe-catches-exception fallback to `PaddleOcrTextDetector`
exactly like any other real DirectML init failure. Regression tests at
the defect's own seam (`test_initialize_raises_when_dml_provider_is_not_actually_active`,
confirmed red before the fix; `test_initialize_succeeds_when_dml_provider_is_genuinely_active`)
in `tests/adapters/test_directml_text_detector_contract.py`. Verified on
real Windows hardware both directions: this worktree's `.venv` (no real
DirectML) now correctly selects `PaddleOcrTextDetector`; the dedicated
`[directml]` venv provisioned earlier this milestone (real
`DmlExecutionProvider` present) still correctly selects
`DirectMlTextDetector`. `create_ocr_engine`'s equivalent preflight was
never affected (`rapidocr` package presence is a genuine, non-silent
signal there). Detector model, thresholds, Architecture B semantics, and
performance tuning untouched. Targeted tests green (`tests/adapters` 84
passed, 1 skipped), GitHub Actions whole-suite CI green (run
`33829120305`).

All Stage ⑤ residual non-blocking findings (below) are preserved
unchanged. M11 was **not** complete at this point in the record (later
sections below cover Stage ⑥/⑦ and this document's closure). **Update:**
M11 subsequently closed on 2026-09-04 with Release Acceptance rejected by
Human Adjudication — see "Current milestone" at the top of this document.

**Workbench UI rendering & cardification pass completed (2026-09-04):** scoped cardification applied to Center Pane (`#heroMediaCard`, `#previewLoopBox`, `#ocrActionBox` with `#ocrStatusBox`) and Right Pane (`#qaHeaderCard`, `#timingCard` integrating split/merge, `#languageLayerCard` with `#layerTag` pills, `#evidenceCard`, `#observationEvidenceCard`, `#exportCard`), aligning the production workbench visual hierarchy with `UI Design/glyphcue_workbench_prototype.html` without altering any domain/pipeline logic or window layout seam budgets (full suite green: 900 passed, 1 skipped, 1 xfailed). Next execution step at this point in the record was **Stage ⑦ Formal Human QA & Packaging Hardening** — see later sections below and "Current milestone" at the top of this document for how Stage ⑦ and M11 ultimately closed.

**Multilingual Architecture B integrated** (shared detection + universal
recognition, corrective 12-case gate — see
[`docs/multilingual/track_group_reconstruction.md`](docs/multilingual/track_group_reconstruction.md)'s
Milestone 11 Architecture B section). Full 180 s verification on all three
bilingual windows confirmed ≤5× realtime and zero conversational layer swaps.
A real 10s-window post-integration smoke on all three surfaced a genuine,
unresolved **speed/correctness trade-off, not a closed result**: on CPU
Paddle (the shipped default), correctness/layer/timing/review semantics
held (correct script separation, sensible multiline joins, missing/
ambiguous diagnostics firing as documented) but wall time measured
7.4×–14.0× realtime (`sample_h` 13.99×, `sample_f` 7.45×, `sample_c`
9.25×) — a real ~7–15× improvement over the pre-Architecture-B baseline's
~99–159×, but still over the ≤5× target. With the opt-in DirectML
engine+detector (P2/P3/P4B), all three measured well under the ≤5×
target (`sample_h` 2.11×, `sample_f` 2.93×, `sample_c` 3.12×), but that
same run showed real correctness degradation not seen on CPU: multiple
Cues with language content visibly swapped into the wrong layer (e.g.
`sample_h`'s first Cue put an English sentence under `"zh"`), at least
one garbled non-text reading (`sample_c`'s first Cue read `"zh": "3\n8"`
where CPU Paddle read real Chinese text), and roughly 1.5–3× more Cues
produced for the identical window (`sample_h`: 12 CPU vs 21 DirectML)
from noisier per-frame recognition fragmenting otherwise-stable states.
**Update — root cause diagnosed and fixed, gate CLOSED (commit `075ac4b`,
on top of the visual-line script-incompatibility veto in `615b56b`).**
The DirectML-path layer-content errors above were re-diagnosed against
real raw `sample_f` (566–568.4s) observations, not guessed: DirectML's
own detector (P4B, `box_thresh=0.45`, unchanged) correctly produced
separate polygons for the English line and the Chinese line beneath it
— there was no detector under-segmentation. The actual bug was in
`_cluster_by_visual_line` (`language_layer_assignment.py`): a
legitimately mixed Han+Latin OCR reading of the Chinese line (e.g.
`"srs有效的原因是"`, the ASCII substring `"srs"` bleeding into an
otherwise-Chinese transcription) makes `_dominant_script` return `None`
— the same value it returns for genuinely no-signal text like bare
digits. The prior script-incompatibility veto (added in `615b56b`)
treated both as "no evidence, never block a merge", so a few pixels of
real Y-overlap let the mixed-script reading merge into the adjacent
decisive-English cluster and get silently classified `en`. `075ac4b`
adds `_has_mixed_script_evidence` and extends the veto: an observation
carrying real mixed Han+Latin evidence is never absorbed into an
adjacent DECISIVE single-language cluster by geometry alone — it starts
its own cluster, staying fail-closed/ambiguous through the existing
unresolved-cluster fallback exactly like any other no-single-decisive-
script cluster. No new numeric threshold; genuinely no-signal text
(digits/punctuation) is unaffected
(`test_non_decisive_neighbor_never_triggers_a_false_veto` still passes).

TDD red→green: the new regression
(`test_mixed_script_observation_adjacent_to_decisive_neighbor_is_not_absorbed`)
reproduced the exact bug against the pre-fix code, then passed after the
fix. Full targeted Architecture B + visual-line regression (29 tests)
and the whole suite (902 passed, 1 skipped, 1 xfailed) are green; GitHub
Actions CI is green on PR #13 (run `33815414759`).

Re-verified against the real DirectML product path
(`create_ocr_engine(prefer_directml=True)` +
`create_text_detector(prefer_directml=True)`, real
`build_multilingual_ocr_evidence_job` →
`reconstruct_multilingual_cues_for_track_group`) on all three frozen
10s windows (`sample_h` 900–910s, `sample_f` 560–570s, `sample_c`
480–490s), run from a freshly provisioned, disposable `[directml]` venv
(this worktree's own `.venv` only carries the `[ocr]` extra; `[directml]`
is deliberately its own environment per `pyproject.toml`) with the
pinned `rapidocr==3.9.2`/`onnxruntime-directml==1.24.4` confirmed via
`onnxruntime.get_available_providers()` (`DmlExecutionProvider` present)
and both `create_ocr_engine`/`create_text_detector` confirmed to
actually resolve to their DirectML classes before any timing was taken
(the detector needed `PP-OCRv6_det_medium.onnx`, ~59MB, fetched fresh
from the same pinned `v3.9.2` RapidOCR/modelscope registry `pyproject.toml`
already trusts — this environment's model cache was otherwise empty):
- **No layer swap in any window.** `sample_f`'s previously-swapped
  content is now correct: `"srs有效的原因是"` stays in the `zh` layer
  across all four affected Cues (566.3–568.4s) and each is correctly
  flagged `ambiguous_languages = {"zh"}` — fail-closed, not silently
  confident, exactly as designed.
- **Realtime:** `sample_h` 3.47×, `sample_f` 4.51×, `sample_c` 4.80× —
  all ≤5×, though visibly higher than the previously-measured
  2.11×/2.93×/3.12×; this run's model/session cache was cold (first
  inference in a brand-new venv), which plausibly explains the gap. Not
  independently isolated from a warm-cache re-run in this session.
- **`sample_c`'s pre-existing `"zh": "3\n8"` garbled first-Cue reading
  persists unchanged** — correctly flagged ambiguous, not a layer swap,
  and not diagnosed by this fix (out of scope: no detector/threshold
  changes were made). Still a separately open, un-diagnosed item.
- Cue counts this round: `sample_h` 18, `sample_f` 23, `sample_c` 7
  (10s windows). `sample_h`'s 18 sits between the CPU baseline's 12 and
  the pre-veto DirectML bug's 21; this run did not re-baseline against a
  fresh CPU-Paddle control, so fragmentation parity is reported as
  observed, not independently re-confirmed against CPU in this pass.

Per human authorization given with these results in hand, **the
Multilingual Performance Corrective Gate is CLOSED.** This closes the
Corrective Gate specifically — it does not by itself close Stage ⑤
Representative Evaluation (below) or advance PR #13 out of Draft.

Feature Freeze was ACTIVE at this point in the record (Milestones 0–10
complete and merged, PRs #1–#12). **Update:** as of Milestone 12's 2026-09-05
closure, Feature Freeze is REINSTATED — see "Current milestone" at the top of this
document.


## Work completed in this stage

Stage ⑤ Representative Evaluation. Full detail:
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md).

**⑤-A Corpus selection — CLOSED.** Corpus frozen at five 3-minute
windows: `sample_g` 90–270 s, `sample_e` 150–330 s, `sample_h`
900–1080 s, `sample_f` 560–740 s, `sample_c` 480–660 s. `sample_a` held
as a clean-baseline reserve; `sample_b` and `sample_d` ruled out as
redundant.

**⑤-B Evaluation preparation — CLOSED.** All five ROI proposals approved
unchanged at the human gate, and all 44 ground-truth candidates confirmed
with no corrections. Confirmed ground truth: 72 point-sample cues across
52 verified instants (`g` 11, `e` 10, `h` 20, `f` 21, `c` 20 inherited),
plus 2 verified negative points that deliberately emit no cue. One
`sample_f` instant carries only its English layer — its Chinese layer is
illegible in the frame and was left untranscribed rather than guessed.

**⑤-C Representative evaluation — CLOSED by Human Adjudication (2026-09-03):**

- Manifest path inconsistency resolved: the canonical
  `private_samples/m10_video_corpus/manifest.json` now exists with
  exactly the five frozen entries; the M10 export copy is untouched and
  read by nothing.
- `_ROI_BY_ENTRY_ID` extended with the four new entry ids at exactly the
  approved ROI values; preflight fails if ids and manifest ever disagree.
- `_PROFILE_BY_ENTRY_ID` replaces the earlier single frozen profile:
  `EXPERIMENTAL_HYBRID` for `sample_g`/`sample_e`, `PRODUCTION_TRIGGER`
  for `sample_h`/`sample_f`/`sample_c`, per the ⑤-C human gate's approval
  of Option A. Preflight requires every manifest entry to have an
  assigned profile and refuses a multilingual entry assigned Hybrid.
  Results record the actual profile per entry, and a
  `_summarize_by_profile` step aggregates strictly within each profile —
  nothing merges a Hybrid and a Production result into one number.
- New `--preflight` and `--crash-check` entry points; `run()` refuses to
  start unless preflight passes. Both re-confirmed **5/5 windows
  runnable** under the split profile, and the crash-check re-verified
  the M10 incident does not reproduce (clean cancellation, no orphaned
  thread) on all five real windows.
- **The real evaluation ran to completion (exit code 0, no exceptions)
  against real video and real OCR/detector models.** Every one of the
  five windows came back `partial_timeout`: each hit the 600 s per-entry
  cap before finishing its 180 s window (coverage 2.2%–60.9%). This
  reproduces, on real footage, the exact performance cost
  `docs/m10_performance_diagnosis.md` already diagnosed — reported
  honestly, not retried with a longer timeout to get a better number.
- **By profile (never merged):** Hybrid (`sample_g`, `sample_e`) — mean
  point recall 52.7%, mean realtime ratio 6.2×. Production
  (`sample_h`, `sample_f`, `sample_c`) — mean point recall 9.7%, mean
  realtime ratio 128.8×. The gap is real and consistent within each
  group, but the two groups are also different content (single- vs.
  multi-language), so it is reported as a signal for a future controlled
  comparison, not a conclusion about promoting either profile.
- Full per-window table and the Human Adjudication list are in
  `docs/m11_representative_evaluation.md` §15.

**Completion supplement (human-gate approved, strictly scoped) — RUN
COMPLETE:**

- New `run_completion_supplement()` / `--completion-supplement`: Hybrid
  only, 1800 s per-entry timeout, exactly three entries —
  `sample_g`/`sample_e` at their unchanged ⑤-A/⑤-B window and ROI, plus
  the pre-existing M10 `sample_a` clean-baseline reserve reused verbatim
  (window, ROI, ground truth all from the M10 export manifest,
  unchanged). A dedicated preflight-equivalent check refuses to run any
  entry not single-language or missing a manifest/ROI. Writes to a
  **separate** results file
  (`evaluation_results_completion_supplement.json`) — the five-window
  stress run's own results file is never opened or touched by this path.
- **All three completed** (`succeeded`, not a timeout cancellation):
  point recall 90–100% across 31 verified instants. Total wall clock
  74.5 min; no exceptions.
- **New finding, reported as initially measured:** mean CER on the two
  Chinese-language entries exceeded 1.0 (`sample_e` 1.166, `sample_a`
  1.679) — the recovered text at matched instants diverges from the
  short verified reference by more edits than the reference contains.
  `sample_g`'s English CER (0.163) was normal. While not diagnosed
  during that evaluation run itself, this finding served as the historical
  trigger for the subsequent **Caption Identity Corrective Gate**, which
  formally diagnosed and resolved the root cause in product code.

**Bilingual completion supplement (Architecture B + DirectML, human-gate approved) — RUN COMPLETE:**

- Ran `sample_h` (900–1080s), `sample_f` (560–740s), and `sample_c` (480–660s)
  through the formal Architecture B + DirectML product path (`DirectMlOcrEngine` +
  `DirectMlTextDetector`) in an isolated `[directml]` environment.
- **All three completed 180/180 s (100.0% coverage)** to `succeeded` state:
  - `sample_h`: 488.1 s wall clock, **2.71×** realtime, 10/10 point recall (100%), CER zh 0.2523 / en 0.0183, 0 missing, 0 wrong assignment.
  - `sample_f`: 659.2 s wall clock, **3.66×** realtime, 11/11 point recall (100%), CER zh 0.0611 / en 0.4641, 0 missing, 0 wrong assignment.
  - `sample_c`: 748.2 s wall clock, **4.16×** realtime, 10/10 point recall (100%), CER zh 0.1316 / en 0.4316, 0 missing, 0 wrong assignment.
- Point recall across the three bilingual windows is **31/31 (100.0%)**; multilingual missing and wrong assignment are **0/0**. Zero layer swaps in conversational dialogue.
- Residual limitations preserved: `sample_c` isolated `"3\n8"` boundary non-text reading fail-closed with `ambiguous_languages: ["zh"]`, non-contaminating; `sample_f` screen-recording editor button glyphs flagged ambiguous.
- Stage ⑤ Representative Evaluation is formally **CLOSED by Human Adjudication (2026-09-03)**. Detailed results recorded in `docs/m11_representative_evaluation.md` §17 and `EVALUATION_REPORT.md`.

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

### Product Corrective & Performance Enhancements Integrated in M11

1. **Caption Identity Corrective Gate (CLOSED):**
   - Investigated and resolved the root cause of the Chinese-language CER finding (hybrid state transition and multi-frame consensus disambiguation in `hybrid_evidence_job` / `caption_identity_verification`).
   - Integrated formal fixes into `src/glyphcue/application/`; full regression verified with 843 tests passing at gate closure (current repository baseline is 902 passed, 1 skipped, 1 xfailed).

2. **P2 Recognition-Only Performance Patch (INTEGRATED):**
   - Eliminated duplicate detection when external polygons are already available for representative frames.
   - Introduced `RegionOcrEngine.recognize_regions()` on `PaddleOcrEngine` with safe fallback; achieved ~3.26× E2E speedup on real Hybrid pipelines.

3. **P3 Windows DirectML OCR Recognizer (INTEGRATED):**
   - Added Windows-only, opt-in GPU acceleration for text recognition (`PP-OCRv6_rec_small.onnx`) via `GLYPHCUE_PREFER_DIRECTML_OCR=1`.
   - Included non-importing platform preflight, execution probe, and safe fallback to Paddle CPU.

4. **P4B Same-Detector DirectML Text Detector Acceleration (INTEGRATED):**
   - Pure execution-backend substitution using official `PP-OCRv6_det_medium.onnx` with exact-matching Paddle DBNet pre/post-processing (`limit_side_len=640`, `thresh=0.2`, `box_thresh=0.45`, `unclip_ratio=1.4`, ImageNet normalization).
   - Windows-only, opt-in via `GLYPHCUE_PREFER_DIRECTML_DETECTOR=1`, with safe CPU fallback.
   - No meaningful downstream geometry/evidence drift / sufficient geometry parity (100% subtitle recall, 0.835 mean IoU across 12 diverse frames): 100% subtitle text and timing parity on `sample_g` and `sample_e`, delivering ~1.67–1.79× E2E speedup.

### Architecture Direction Decisions

- **Parallel Chunking Feasibility Gate (REJECTED):**
  Formally evaluated across thread and multiprocess architectures; rejected based on empirical evidence (Direct3D 12 device access violations across threads, multiprocess lock serialization). Parallel chunking is closed and not a pending work item.

## Validation


| Suite | Result |
|---|---|
| `pytest` (targeted P4B selection, contract & UI seams) | **40 passed** in 1.19s |
| `pytest` (whole repository, full suite) | **902 passed, 1 skipped, 1 xfailed** in 118s |
| `tests/ui` (one process) | 295 passed, 1 xfailed |
| GitHub Actions CI (Stage ⑥ evidence baseline `906f9e7`) | GREEN — run `33823586648` |
| `pytest` (`tests/application/test_source_identity.py`, Stage ⑥ Windows-branch gap closure) | **3 passed** |
| `pytest` (Legacy Pipeline Retirement targeted: `tests/application`, `tests/adapters`, `tests/ui`) | **790 passed, 1 skipped, 1 xfailed** |
| GitHub Actions CI (Stage ⑥ evidence baseline refreshed to `4afb8d4`) | GREEN — run `33828500457` |
| `pytest` (`tests/adapters`, DirectML provider-preflight fix `face04b`) | **84 passed, 1 skipped** |
| GitHub Actions CI (`face04b`) | GREEN — run `33829120305` |

Privacy check: no secrets, credentials, real user data, personal
identifiers, or absolute local paths in the committed changes; local
media, `private_samples/` and `prompt-drafts/` remain untracked. The new
corpus, preparation and preflight documents describe the private samples
by structural property, counts and metrics only, and name no speaker,
channel, publication or brand appearing in them. Every artifact carrying
real content — the corpus manifest with its confirmed caption text, the
ground-truth worksheets, the frame-evidence sheets and the videos — is
written under `private_samples/` and stays untracked. No caption text
appears anywhere in the repository.

## Git / PR status

- Authoritative state: `main` contains Milestone 12 Stage ② (PR [#15](https://github.com/Peter-S-Shi/glyphcue/pull/15)) and Product Hardening II & Full Regression (PR [#16](https://github.com/Peter-S-Shi/glyphcue/pull/16)); Product Hardening II is CLOSED / ACCEPTED.
- Active working branch: none / no active hardening or implementation branch.
- Product Hardening II vehicle: PR [#16](https://github.com/Peter-S-Shi/glyphcue/pull/16) — Product Hardening II & Full Regression Pass; completed integration vehicle.
- Milestone 12 Stage ② vehicle: PR [#15](https://github.com/Peter-S-Shi/glyphcue/pull/15) — Milestone 12 Stage ②: Cue Production Quality Recovery (Cue Cleaner V0.6.1 Integration); completed integration vehicle for Stage ②.

## Unresolved

- Release Ready = NO (remains NO until the Milestone 13 release gate itself succeeds).
- Packaging suspension lifted; packaging work may resume strictly within scoped Milestone 13 release/packaging activities.
- Residual non-blocking evaluation findings preserved (informational, not release blockers on their own):
  - `sample_c`: Isolated window-boundary non-text reading (`"zh": "3\n8"`) on Cue 1 (1.1s), safely fail-closed with `ambiguous_languages: ["zh"]`; non-contaminating.
  - `sample_f`: One illegible Chinese layer at 661.1s left untranscribed in GT rather than guessed; rapid b-roll editor button glyphs flagged ambiguous.
- Cue Cleaner V0.6.1 accepted conservative limitation: Clean Cues reduces cleanup burden but is not required to eliminate every residual duplicate/fragment; remaining cases stay visible in the queue for manual resolution via existing manual Merge workflow (`M` shortcut / Merge button). Residual duplicates are explicitly not release blockers.

## Next action

1. Advance into Milestone 13 (Release Candidate & Signed Release, ROADMAP §20).
2. Packaging work may resume strictly within scoped Milestone 13 release/packaging deliverables.
