# D3 Corrective Retest Record

## Current Status

D3 remains FAIL for the superseded original canonical installer:
`GlyphCue-Setup.exe` with SHA-256
`3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3`.

That failure is scoped to Environment B runtime fidelity, not to all of
Milestone 13. Offline install, first launch, SQLite/user-data initialization,
packaged ONNX model integrity, and packaged DLL integrity passed on the
owner-qualified clean VM. The failing behavior was OCR runtime initialization:
RapidOCR attempted external retrieval of `PP-OCRv6_det_small.onnx`, and the
production Paddle CPU fallback attempted external Paddle model-host retrieval.

## Corrected Installer Gate History

The corrected Phase B/C reseal loop completed successfully. A later narrow D3
recognizer fallback fix was rebuilt without reopening the full reseal loop. The
installer used for the final owner D3 retest was:

- Path: `build_artifacts/d3_recognizer_fallback_fix/installer/GlyphCue-Setup.exe`
- Size: `544,118,632` bytes
- SHA-256: `cf76cb5632befccccb3b63bcd884e5f1e6f515d68fba8fdf0490845100d9b870`
- Signer subject:
  `CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root`
- Signer thumbprint: `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC`
- Authenticode status: `Valid` in the authorized local CurrentUser test-trust
  context.

Do not reuse the failed canonical installer for any future corrective retest.

## Certificate Scope And Cleanup

The corrected reseal uses the local self-signed GlyphCue development test
certificate `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC` only for corrected
Phase B/C reseal and subsequent M13 local test signing/verification. It is not
a V1 production signing identity.

Current local stores:

- `CurrentUser\My`: private-key certificate for local signing.
- `CurrentUser\Root`: public certificate trusted for local verification.
- `CurrentUser\TrustedPublisher`: public certificate trusted for local
  verification.

Final cleanup recommendation after M13 local testing/signing no longer needs
this certificate: remove thumbprint
`DEDF7D0881E3A172CC018B63CCCF69FC51333AFC` from `CurrentUser\My`,
`CurrentUser\Root`, and `CurrentUser\TrustedPublisher`; do not export or
commit any private key, PFX, or sensitive certificate material.

## Environment B Retest Procedure Used

The owner retest used this Environment B procedure:

1. Restore the clean pre-install snapshot named
   `GlyphCue D3 - Environment B Qualified Pre-Install`.
2. Keep the VM offline before installer execution.
3. Copy in only the narrow recognizer fallback fix installer and the
   deterministic diagnostic commands supplied with the build evidence.
4. Verify the corrected installer SHA-256 matches the relay state.
5. Verify Authenticode status is `Valid` under the local development test
   certificate thumbprint `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC`.
6. Install the corrected installer while still offline.
7. Launch GlyphCue once and verify the UI renders.
8. Confirm the user-data root and SQLite database initialize.
9. Verify these packaged ONNX files exist and match the frozen hashes:
   - `PP-OCRv6_det_medium.onnx`
   - `PP-OCRv6_rec_small.onnx`
   - `ch_ppocr_mobile_v2.0_cls_mobile.onnx`
10. Verify these packaged Paddle CPU directories exist under `models/paddle/`:
    - `PP-OCRv6_medium_det`
    - `PP-OCRv6_medium_rec`
11. Run the CPU fallback initialization diagnostic offline. Expected result:
    production selection resolves to `PaddleOcrEngine` and
    `PaddleOcrTextDetector` when no usable DML device/session is active; both
    initialize from packaged `models/paddle/` artifacts without network access
    or external model retrieval.
12. Run the bounded CPU-path OCR smoke. Expected result: end-to-end execution
    completes without crash and emits non-empty, non-degenerate Cues.

## Environment A Regression Check Guidance

For any future regression run after a D3 correction, rerun the Environment A
DirectML diagnostic against the same corrected installer:

- Verify the ONNX hashes are unchanged.
- Verify DirectML runtime DLL integrity is unchanged.
- Verify detector and recognizer ONNX sessions report `DmlExecutionProvider`.
- Verify no RapidOCR request is made for `PP-OCRv6_det_small.onnx`.
- Run the bounded DirectML OCR smoke offline.

## Verdict Rule

This document preserves the corrective retest procedure. As of D4
reconciliation on 2026-09-06, owner evidence has completed this retest:
`PaddleOcrEngine`, `PaddleOcrTextDetector`, one polygon, and bounded CPU OCR
smoke text `GLYPHCUE TEST 123`. The final Phase D verdict now lives in
`docs/m13_phase_d/PHASE_D_RELAY.md` and `docs/m13_phase_d/phase_d_state.json`.
