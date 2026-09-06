from __future__ import annotations

import json
from pathlib import Path

RELEASE_URL = "https://github.com/Peter-S-Shi/glyphcue/releases/tag/v1.0.0"
RELEASE_COMMIT = "d394ec777803364f27a7a9f0cf287f393f977db3"
INSTALLER_BUILD_COMMIT = "34489a9d9862849e19f50b79e55d5530bd163494"
INSTALLER_SHA = "F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446"
SOURCE_SHA = "FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC"
PROVENANCE_SHA = "53CAAEF2849AF108EA7D99042693735AA51174C95AB5506832B03078FAD36EB4"


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 occurrence, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


# DESIGN.md + architecture top lifecycle: only the current-state clause, never historical records.
old_top_clause = (
    "Feature Freeze ACTIVE; **Release Ready remains NO**; **Portfolio Packaging Ready remains NO** "
    "(pending post-merge publication: merge PR #31 → create v1.0.0 tag → generate final provenance.json & SHA256SUMS.txt → "
    "publish GitHub Release with all four assets → independent download verification). **Next target: post-merge v1.0.0 release publication & verification, "
    "followed by Milestone 14 (Portfolio Packaging & Stop-Building Closure)**."
)
new_top_clause = (
    "Feature Freeze ACTIVE; **GlyphCue v1.0.0 is PUBLICLY RELEASED & VERIFIED**; **Release Ready = YES**; "
    "**Portfolio Packaging Ready = YES**. The public GitHub Release `v1.0.0` is live with all four required assets, "
    "and independent clean-download SHA-256 verification passed. **Next target: Milestone 14 (Portfolio Packaging & Stop-Building Closure)**."
)
for path in ("DESIGN.md", "GLYPHCUE_PRODUCT_ARCHITECTURE.md"):
    replace_once(path, old_top_clause, new_top_clause)

# Architecture closeout summary.
replace_once(
    "GLYPHCUE_PRODUCT_ARCHITECTURE.md",
    "✓ CLOSED & ACCEPTED (2026-09-06) — Gate A (5 OCR models under Apache-2.0, MIT license, LGPL FFmpeg) PASS; Gate B (rebuilt payload, candidate installer frozen as GlyphCue-Setup-1.0.0.exe SHA-256 F88C2FE2...) PASS. Release Ready remains NO and Portfolio Packaging Ready remains NO pending post-merge release sequence (merge PR #31 → create v1.0.0 tag → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: GlyphCue-Setup-1.0.0.exe, GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip, SHA256SUMS.txt, provenance.json → independent download verification). Next target: post-merge v1.0.0 publication & verification, then Milestone 14 (Portfolio Packaging & Stop-Building Closure).",
    "✓ COMPLETE / PUBLICLY RELEASED & VERIFIED (2026-09-06) — Gate A (5 OCR models under Apache-2.0, MIT license, LGPL FFmpeg) PASS; Gate B (rebuilt payload, candidate installer frozen as GlyphCue-Setup-1.0.0.exe SHA-256 F88C2FE2...) PASS; PR #31 merged; annotated tag `v1.0.0` points to release commit `d394ec777803364f27a7a9f0cf287f393f977db3`; the public GitHub Release is live with all four required assets; independent clean-download SHA-256 verification passed. Release Ready = YES; Portfolio Packaging Ready = YES. Next target: Milestone 14 (Portfolio Packaging & Stop-Building Closure).",
)

# ROADMAP current-state reconciliation. Historical milestone statements are intentionally untouched.
replace_once(
    "ROADMAP.md",
    "Feature Freeze remains ACTIVE; **Release Ready remains NO**; **Portfolio Packaging Ready remains NO** (pending formal v1.0.0 GitHub Release publication, release tag, and independent download verification). **Next development target: formal v1.0.0 release publication & verification, followed by Milestone 14 (Portfolio Packaging & Stop-Building Closure)**.",
    "Feature Freeze remains ACTIVE; **GlyphCue v1.0.0 is PUBLICLY RELEASED & VERIFIED**; **Release Ready = YES**; **Portfolio Packaging Ready = YES**. The formal GitHub Release is live with all four required assets and independent clean-download SHA-256 verification passed. **Next development target: Milestone 14 (Portfolio Packaging & Stop-Building Closure)**.",
)
replace_once(
    "ROADMAP.md",
    "> Packaging and installer-lifecycle validation (Phases A–F) is COMPLETE and PASS; the post-M13 Public Distribution Gate (Issue #30, PR #31) is CLOSED & ACCEPTED (5 OCR models resolved under Apache-2.0, GlyphCue under MIT, PyAV FFmpeg replaced with pinned LGPL build, candidate installer frozen as `GlyphCue-Setup-1.0.0.exe`, SHA-256 `F88C2FE2...`). This does not itself make GlyphCue publicly shipped or Release Ready until formal v1.0.0 GitHub Release publication, release tag, and independent download verification occur. `Release Ready = NO`; `Portfolio Packaging Ready = NO`.",
    "> Packaging and installer-lifecycle validation (Phases A–F) is COMPLETE and PASS; the post-M13 Public Distribution Gate (Issue #30, PR #31) is COMPLETE / PUBLICLY RELEASED & VERIFIED. The annotated `v1.0.0` tag points to release commit `d394ec777803364f27a7a9f0cf287f393f977db3`; the public GitHub Release is live with all four required assets; the installer and FFmpeg corresponding-source archive were independently re-downloaded and their SHA-256 values matched the frozen identities. `Release Ready = YES`; `Portfolio Packaging Ready = YES`.",
)
replace_once(
    "ROADMAP.md",
    "`Release Ready = NO` and `Portfolio Packaging Ready = NO` remain current until the post-merge release sequence (merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: `GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, `provenance.json` → independently verify downloads) completes.",
    "The post-merge publication sequence is COMPLETE: PR #31 merged; annotated tag `v1.0.0` points to release commit `d394ec777803364f27a7a9f0cf287f393f977db3`; final `provenance.json` and `SHA256SUMS.txt` were generated; the public GitHub Release is live with all four required assets; independent clean-download SHA-256 verification passed. `Release Ready = YES`; `Portfolio Packaging Ready = YES`.",
)
replace_once(
    "ROADMAP.md",
    "Convert the completed technical work into a concise, credible professional artifact and formally stop V1 feature development. (Portfolio Packaging may begin now that Milestone 13's engineering closure is complete; it does not itself make GlyphCue publicly shipped or Release Ready — see §20.)",
    "Convert the completed technical work into a concise, credible professional artifact and formally stop V1 feature development. Portfolio Packaging may begin now: GlyphCue v1.0.0 is publicly released and independently verified, and `Portfolio Packaging Ready = YES` — see §20.",
)
replace_once(
    "ROADMAP.md",
    "Release Ready                           NO (pending formal v1.0.0 GitHub Release publication, release tag, and independent download verification)\nPortfolio Packaging Ready               NO (pending formal v1.0.0 release publication & verification)",
    "Release Ready                           YES (v1.0.0 public GitHub Release live; independent download verification PASS)\nPortfolio Packaging Ready               YES (Public Distribution Gate complete; M14 may begin)",
)
replace_once(
    "ROADMAP.md",
    "> **Formal v1.0.0 Release Publication & Verification → Milestone 14 (Portfolio Packaging & Stop-Building Closure)** (ROADMAP §21)",
    "> **Milestone 14 — Portfolio Packaging & Stop-Building Closure** (ROADMAP §21)",
)
replace_once(
    "ROADMAP.md",
    "8. **Release Ready remains NO; Portfolio Packaging Ready remains NO**: until the post-merge release sequence (merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets → independently verify downloads) completes.\n9. **Next Target**: Merge PR #31 → create v1.0.0 tag on main → generate final provenance.json and SHA256SUMS.txt → publish GitHub Release with all four assets (`GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, `provenance.json`) → independently verify downloads → Portfolio Packaging Ready = YES / Milestone 14 (Portfolio Packaging & Stop-Building Closure, §21).",
    "8. **Release Ready = YES; Portfolio Packaging Ready = YES**: `v1.0.0` is publicly released with all four required assets and independent clean-download SHA-256 verification PASS.\n9. **Next Target**: Milestone 14 (Portfolio Packaging & Stop-Building Closure, §21).",
)
replace_once(
    "ROADMAP.md",
    "M10–M13 convert engineering work into a finished, evaluated, hardened, and professionally legible product. (M13 is COMPLETE and post-M13 Public Distribution Gate is CLOSED & ACCEPTED; Release Ready and Portfolio Packaging Ready remain NO until formal v1.0.0 GitHub Release publication, release tag, and independent download verification.)",
    "M10–M13 convert engineering work into a finished, evaluated, hardened, and professionally legible product. M13 and the post-M13 Public Distribution Gate are COMPLETE; GlyphCue v1.0.0 is publicly released and independently verified; Release Ready = YES and Portfolio Packaging Ready = YES. M14 is the active next target.",
)

# PROJECT_STATUS current truth. Historical M13 evidence remains unchanged.
replace_once(
    "PROJECT_STATUS.md",
    "**Milestone 13 — Release Candidate & Signed Release / Minimum Runtime-Fidelity Packaging Experiment (Issue #27): COMPLETE / PASS (Phases A–F all passed; merged to `main` via PR #29); Post-M13 Public Distribution Gate (Issue #30, PR #31): CLOSED & ACCEPTED; Release Ready = NO; Portfolio Packaging Ready = NO.**",
    "**Milestone 13 — Release Candidate & Signed Release / Minimum Runtime-Fidelity Packaging Experiment (Issue #27): COMPLETE / PASS (Phases A–F all passed; merged to `main` via PR #29); Post-M13 Public Distribution Gate (Issue #30, PR #31): COMPLETE / PUBLICLY RELEASED & VERIFIED; GlyphCue v1.0.0 LIVE; Release Ready = YES; Portfolio Packaging Ready = YES; next target = Milestone 14.**",
)
replace_once(
    "PROJECT_STATUS.md",
    "- **Release Status**: **Release Ready = NO**; **Portfolio Packaging Ready = NO** (v1.0.0 release candidate is accepted and packaging/redistribution compliance gates are closed; both remain NO until the post-merge release sequence — PR merge → create v1.0.0 tag → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets → independent download verification — is completed).",
    "- **Release Status**: **Release Ready = YES**; **Portfolio Packaging Ready = YES**. Annotated tag `v1.0.0` points to release commit `d394ec777803364f27a7a9f0cf287f393f977db3`; the public GitHub Release is live with all four required assets; independent clean-download verification reproduced installer SHA-256 `F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446` and FFmpeg corresponding-source SHA-256 `FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC`.",
)
replace_once(
    "PROJECT_STATUS.md",
    "- Active working branch: `release/1.0.0-public-distribution` (PR [#31](https://github.com/Peter-S-Shi/glyphcue/pull/31) — Close GlyphCue v1.0.0 Public Distribution Gate; governing Issue [#30](https://github.com/Peter-S-Shi/glyphcue/issues/30)).\n- Public Distribution Gate vehicle: PR [#31](https://github.com/Peter-S-Shi/glyphcue/pull/31) — Gate A (Licensing & Redistribution Compliance) and Gate B (Minimum Real Public Distribution Payload & Candidate Freeze) are CLOSED & ACCEPTED.",
    "- Active working branch: none for V1 release engineering; `v1.0.0` is publicly released and verified.\n- Public Distribution Gate vehicle: PR [#31](https://github.com/Peter-S-Shi/glyphcue/pull/31) — merged; Gate A/B, release publication, and independent download verification are COMPLETE. Governing Issue [#30](https://github.com/Peter-S-Shi/glyphcue/issues/30) is ready to close as completed with this reconciliation.\n- Public release: [GlyphCue v1.0.0](https://github.com/Peter-S-Shi/glyphcue/releases/tag/v1.0.0), release commit `d394ec777803364f27a7a9f0cf287f393f977db3`.",
)
replace_once(
    "PROJECT_STATUS.md",
    "- `Release Ready = NO`; `Portfolio Packaging Ready = NO`. The candidate installer and redistribution compliance gates are fully resolved and accepted, but formal release tag, GitHub Release asset publication, and independent download verification have not yet occurred.\n- SmartScreen / not-publicly-trusted disclosure text is accepted policy and to be included in user-facing release notes and documentation upon publication.",
    "- No open Public Distribution Gate blocker remains. `Release Ready = YES`; `Portfolio Packaging Ready = YES`.\n- SmartScreen / not-publicly-trusted disclosure is published in the v1.0.0 GitHub Release notes; formal production/public-trust signing remains optional future hardening, not a V1 release blocker.",
)
replace_once(
    "PROJECT_STATUS.md",
    "1. Merge PR [#31](https://github.com/Peter-S-Shi/glyphcue/pull/31) into `main`.\n2. Create `v1.0.0` tag on the accepted `main` merge commit.\n3. Generate final `provenance.json` (binding the final `main` merge commit/tag and frozen installer hash) and `SHA256SUMS.txt`.\n4. Formally publish the GlyphCue `v1.0.0` GitHub Release attaching all four release assets: `GlyphCue-Setup-1.0.0.exe` (SHA-256 `F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446`), `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip` (SHA-256 `FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC`), `SHA256SUMS.txt`, and `provenance.json`, with release notes including SmartScreen disclosure.\n5. Independently verify downloads and clean installation from public assets.\n6. Portfolio Packaging Ready = YES; advance to Milestone 14 (Portfolio Packaging & Stop-Building Closure).",
    "1. Close Issue [#30](https://github.com/Peter-S-Shi/glyphcue/issues/30) as completed after this post-release governance reconciliation merges.\n2. Advance to Milestone 14 — Portfolio Packaging & Stop-Building Closure. No further V1 release-engineering work is required unless new regression evidence appears.",
)

# Phase D relay: preserve Phase D history, reconcile only current downstream state.
replace_once(
    "docs/m13_phase_d/PHASE_D_RELAY.md",
    "**Status:** Phase D COMPLETE / PASS. Phase E COMPLETE / PASS. Phase F COMPLETE / PASS. Milestone 13 COMPLETE (merged via PR #29). Post-M13 Public Distribution Gate (Issue #30, PR #31) CLOSED & ACCEPTED. Release Ready = NO; Portfolio Packaging Ready = NO (pending post-merge release sequence: merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: GlyphCue-Setup-1.0.0.exe, GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip, SHA256SUMS.txt, provenance.json → independent download verification).",
    "**Status:** Phase D COMPLETE / PASS. Phase E COMPLETE / PASS. Phase F COMPLETE / PASS. Milestone 13 COMPLETE (merged via PR #29). Post-M13 Public Distribution Gate (Issue #30, PR #31) COMPLETE / PUBLICLY RELEASED & VERIFIED. GlyphCue v1.0.0 is live; Release Ready = YES; Portfolio Packaging Ready = YES; next target = Milestone 14.",
)
replace_once(
    "docs/m13_phase_d/PHASE_D_RELAY.md",
    "- **Current Status:** Phase D D4 reconciliation, Phase E owner-led validation, and Phase F owner-led lifecycle validation are all **COMPLETE / PASS**. Milestone 13 is **COMPLETE**. Post-M13 Public Distribution Gate (Issue #30, PR #31) is **CLOSED & ACCEPTED**. `Release Ready = NO` and `Portfolio Packaging Ready = NO` remain current until the post-merge release sequence (merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: `GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, `provenance.json` → independently verify downloads) completes.",
    "- **Current Status:** Phase D D4 reconciliation, Phase E owner-led validation, and Phase F owner-led lifecycle validation are all **COMPLETE / PASS**. Milestone 13 is **COMPLETE**. Post-M13 Public Distribution Gate (Issue #30, PR #31) is **COMPLETE / PUBLICLY RELEASED & VERIFIED**. `Release Ready = YES`; `Portfolio Packaging Ready = YES`; next target is Milestone 14.",
)
replace_once(
    "docs/m13_phase_d/PHASE_D_RELAY.md",
    "- [x] Progression permitted to Phase E at D4 closure. Phase E and Phase F have since completed; Milestone 13 is complete; Post-M13 Public Distribution Gate is closed; Release Ready remains NO and Portfolio Packaging Ready remains NO pending post-merge release sequence (merge PR #31 → create v1.0.0 tag → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets → independent download verification).",
    "- [x] Progression permitted to Phase E at D4 closure. Phase E and Phase F have since completed; Milestone 13 is complete; the Post-M13 Public Distribution Gate subsequently completed with public v1.0.0 publication and independent download verification. Release Ready = YES; Portfolio Packaging Ready = YES.",
)
replace_once(
    "docs/m13_phase_d/PHASE_D_RELAY.md",
    "> **Post-Merge Release Sequence:**\n> `merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json and SHA256SUMS.txt → publish GitHub Release with all four assets → independently verify downloads → Portfolio Packaging Ready = YES / Milestone 14`\n> \n> **Current Release Status:** `Release Ready = NO`; `Portfolio Packaging Ready = NO` (until the above post-merge sequence completes).",
    "> **Post-Merge Release Sequence:** **COMPLETE / VERIFIED**. PR #31 merged; annotated `v1.0.0` tag points to release commit `d394ec777803364f27a7a9f0cf287f393f977db3`; final provenance/checksums were generated; the GitHub Release is public with all four required assets; independent clean-download SHA-256 verification passed.\n> \n> **Current Release Status:** `Release Ready = YES`; `Portfolio Packaging Ready = YES`. Next lifecycle target: Milestone 14.",
)
replace_once(
    "docs/m13_phase_d/PHASE_D_RELAY.md",
    "Distribution Gate (Issue #30, PR #31) is **CLOSED & ACCEPTED**. `Release Ready`\nremains **NO** and `Portfolio Packaging Ready` remains **NO** pending the post-merge\nrelease sequence with all four assets and independent download verification (Section 10).",
    "Distribution Gate (Issue #30, PR #31) is **COMPLETE / PUBLICLY RELEASED & VERIFIED**. `Release Ready`\nis **YES** and `Portfolio Packaging Ready` is **YES** after public v1.0.0 publication\nwith all four required assets and independent clean-download verification (Section 10).",
)

# Phase D state JSON: keep historical selected-installer evidence; update only downstream/current gates.
state_path = Path("docs/m13_phase_d/phase_d_state.json")
state = json.loads(state_path.read_text(encoding="utf-8"))
state["gates"]["release_ready"] = True
state["gates"]["portfolio_packaging_ready"] = True
state["gates"]["public_distribution_gate"] = "COMPLETE_VERIFIED"
state["public_distribution_gate_status"] = "COMPLETE_VERIFIED"
state["public_release"] = {
    "status": "LIVE_VERIFIED",
    "release_url": RELEASE_URL,
    "tag": "v1.0.0",
    "release_commit_sha": RELEASE_COMMIT,
    "installer_build_source_commit_sha": INSTALLER_BUILD_COMMIT,
    "installer_sha256": INSTALLER_SHA.lower(),
    "ffmpeg_corresponding_source_sha256": SOURCE_SHA.lower(),
    "provenance_asset_sha256": PROVENANCE_SHA.lower(),
    "independent_download_verification": "PASS",
    "verified_at": "2026-09-06",
}
state["next_gate"] = "Milestone 14 — Portfolio Packaging & Stop-Building Closure. Public Distribution Gate is complete; Release Ready = YES; Portfolio Packaging Ready = YES."
state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# Compliance audit: reconcile current publication status while preserving intermediate audit history as historical.
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "**Status:** Gate A **PASS**. Gate B (minimum real public-distribution payload) implemented and verified against a freshly rebuilt real `app_root`/installer — see §6. Both Owner governance questions RESOLVED (§5). Not yet tagged, not yet published as a GitHub Release, PR #31 not yet merged.",
    "**Status:** Gate A **PASS**. Gate B (minimum real public-distribution payload) implemented and verified against a freshly rebuilt real `app_root`/installer — see §6. Both Owner governance questions RESOLVED (§5). PR #31 merged; `v1.0.0` tagged and publicly released with all four required assets; independent clean-download SHA-256 verification PASS. Public Distribution Gate COMPLETE.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "**Packaging guard added this session (not yet wired into the real build):**",
    "**Historical intermediate state (superseded by Gate B closure below): packaging guard added before real-build wiring:**",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "**Not yet done (explicitly out of this session's scope, per instruction not to freeze/rebuild the public installer):** wiring this guard and the DLL-swap into `execute_phase_b.py`/`execute_phase_c.py`'s actual packaging pipeline, and re-running it against a real rebuilt `app_root`. That remains a minimum action for Gate A closure (§6), not yet executed.",
    "**Historical intermediate state (superseded by §6):** at this audit point, wiring this guard and the DLL swap into `execute_phase_b.py`/`execute_phase_c.py` and rebuilding the real `app_root` had not yet been executed. Section 6 records the subsequent implementation, rebuild, verification, and Gate A/B closure.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "The explicit SmartScreen/not-publicly-trusted disclosure text for the README/release notes and installer still needs drafting as a follow-up (see `docs/v1_public_release_dependency_provenance.json`'s `owner_governance_decisions.signing_policy_decision.not_yet_done`) — recording the decision here does not by itself produce that user-facing copy.",
    "The explicit SmartScreen/not-publicly-trusted disclosure was subsequently published in the v1.0.0 GitHub Release notes. The final v1.0.0 distribution contract required this user-facing release disclosure; formal public-trust signing remains optional future hardening.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "### Remaining before tagging/publishing v1.0.0 (not performed this session, per instruction)",
    "### Post-release closure (completed 2026-09-06)",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "1. Draft the explicit SmartScreen/not-publicly-trusted disclosure text for the README/release notes and installer (the signing *policy* is resolved; the user-facing disclosure *copy* is not yet written).",
    "1. **COMPLETE:** SmartScreen/not-publicly-trusted disclosure published in the v1.0.0 GitHub Release notes.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "4. Attach all four assets (`GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, and post-merge generated `provenance.json` bound to the final `main` merge commit and `v1.0.0` tag) to the formal GitHub v1.0.0 Release.",
    "4. **COMPLETE:** all four required assets (`GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, `provenance.json`) attached to the public GitHub v1.0.0 Release.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "5. Execute the post-merge release sequence: merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json and SHA256SUMS.txt → publish GitHub Release with all four assets → independently verify downloads → Portfolio Packaging Ready = YES / Milestone 14.",
    "5. **COMPLETE:** PR #31 merged → annotated `v1.0.0` tag created on release commit `d394ec777803364f27a7a9f0cf287f393f977db3` → final provenance/checksums generated → GitHub Release published with all four assets → independent downloads verified. `Portfolio Packaging Ready = YES`; next target = Milestone 14.",
)
replace_once(
    "docs/v1_public_distribution_gate_a_compliance_audit.md",
    "None of the above requires touching OCR/runtime architecture, retesting Phase D/E/F, F1-F4, or a B/C dual reseal — no targeted check this session exposed a contradiction requiring one.",
    "The remaining recommended items above are non-blocking future hardening. No OCR/runtime architecture change, Phase D/E/F rerun, F1-F4 rerun, or B/C dual reseal is required for the completed v1.0.0 release.",
)

# Public-release dependency/governance provenance: add final publication record; do not overwrite historical M13 inventory.
prov_path = Path("docs/v1_public_release_dependency_provenance.json")
prov = json.loads(prov_path.read_text(encoding="utf-8"))
prov["lgpl_ffmpeg_replacement"]["corresponding_source_package"]["purpose"] = (
    "Published as a same-release GitHub v1.0.0 asset (not merely linked to a mutable upstream page) per FFmpeg distribution-compliance guidance. "
    f"Public release: {RELEASE_URL}."
)
signing = prov["owner_governance_decisions"]["signing_policy_decision"]
signing.pop("not_yet_done", None)
signing["release_disclosure_status"] = "PUBLISHED in the v1.0.0 GitHub Release notes; SmartScreen/not-publicly-trusted behavior is explicitly disclosed to end users."
prov["public_release"] = {
    "status": "LIVE_VERIFIED",
    "release_url": RELEASE_URL,
    "tag": "v1.0.0",
    "release_commit_sha": RELEASE_COMMIT,
    "installer_build_source_commit_sha": INSTALLER_BUILD_COMMIT,
    "installer": {
        "filename": "GlyphCue-Setup-1.0.0.exe",
        "sha256": INSTALLER_SHA.lower(),
        "size_bytes": 610633568,
        "authenticode_status": "Valid",
        "signer_thumbprint": "DEDF7D0881E3A172CC018B63CCCF69FC51333AFC",
    },
    "ffmpeg_corresponding_source": {
        "filename": "GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip",
        "sha256": SOURCE_SHA.lower(),
        "size_bytes": 16859628,
    },
    "provenance_asset_sha256": PROVENANCE_SHA.lower(),
    "independent_download_verification": "PASS",
    "verified_at": "2026-09-06",
}
prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

print("Post-release governance reconciliation applied successfully.")
