# GlyphCue — DESIGN.md

**Document type:** Production-facing UI / UX design authority  
**Project:** GlyphCue  
**Repository:** `Peter-S-Shi/glyphcue`  
**Lifecycle phase:** Production Development in progress → Milestone 10 complete (evidence/evaluation closure accepted; representative-video gate transferred to Milestone 11, not waived — see `ROADMAP.md` §17's gate audit disposition), Feature Freeze ACTIVE, Milestone 11 (Product Hardening & Full Regression) next  
**Status:** Authoritative V1 design specification  
**Last updated:** 2026-08-31

---

# 1. Purpose

This document freezes the stable visual and interaction decisions established through three rounds of GlyphCue HTML prototyping.

It is the production-facing design authority for future implementation work.

It does **not** redefine product architecture. Product scope, domain semantics, evidence model, technical-depth priorities, and lifecycle rules remain governed by `GLYPHCUE_PRODUCT_ARCHITECTURE.md`.

This file defines:

- what GlyphCue should look and feel like;
- which regions exist in the product shell;
- what each region is responsible for;
- how Path A and Path B share one product grammar;
- visual tokens and component hierarchy;
- evidence presentation;
- QA interaction;
- keyboard behavior;
- accessibility requirements;
- which prototype ideas are explicitly **not** production requirements;
- which questions remain OPEN or DEFERRED.

When a future implementation or agent proposal conflicts with this file, this file wins unless the conflict is explicitly escalated as a design decision.

---

# 2. Source Basis

This design baseline consolidates accepted results from:

- `GLYPHCUE_PRODUCT_ARCHITECTURE.md`;
- `UI Design Candidates.md`;
- Prototype Round 1 — Path A Product Shell / Visual DNA;
- Prototype Round 2 — Multilingual / Timing / Evidence Density stress validation;
- Prototype Round 3 — Path B Product-Shell Compatibility validation;
- the accepted post-prototype product decisions made after each round.

The Round 3 HTML prototype is the strongest visual reference, but it is still a **prototype**, not production code.

Production implementation should reproduce the validated design semantics, not blindly copy every fake label, metric, algorithm name, or prototype-only control.

---

# 3. Design Status Vocabulary

Use these labels throughout this document.

## `FROZEN`

Validated strongly enough that V1 implementation should preserve it.

Changing it requires explicit design review.

## `GUIDELINE`

Preferred production direction.

Small implementation adjustments are allowed if they preserve the underlying interaction meaning.

## `OPEN`

Not yet decidable from UI prototyping alone.

Do not let UI implementation silently freeze it.

## `DEFERRED`

Not required for V1.

Do not add it merely because the prototype makes it easy.

## `PROTOTYPE-ONLY`

Existed only to test a design hypothesis.

It must not automatically appear in production.

---

# 4. Core Design Thesis

## `FROZEN`

GlyphCue is a:

> **Hybrid Dark Precision Evidence Workbench**

The product should feel like a modern local AI / media reconstruction tool:

- dark;
- precise;
- evidence-centered;
- technical without becoming a developer console;
- information-dense without becoming cramped;
- calm enough for long QA sessions;
- visually distinctive without decorative spectacle.

Internal metaphor:

> **Subtitle Reconstruction Evidence Workbench**

The product is not visually framed as:

- a generic SaaS dashboard;
- a subtitle document editor;
- a video editor clone;
- a hacker terminal;
- an “AI magic” interface;
- a marketing landing page.

The product should communicate its purpose through **structure**, not decoration.

> **Workbench is structure, not decoration.**

---

# 5. Reference Style Synthesis

The accepted visual direction combines three reference families.

## 5.1 Framer supplies visual confidence

Borrow:

- deep dark canvas;
- media / product evidence as visual hero;
- restrained electric-blue accent;
- cold, precise visual character;
- subtle blue focus/ring treatment;
- strong contrast between product evidence and surrounding chrome.

Do not borrow:

- giant marketing typography;
- extreme negative display tracking;
- excessive pill buttons;
- decorative glassmorphism;
- showpiece animation;
- website-first composition.

---

## 5.2 Airtable supplies information discipline

Borrow:

- sophisticated simplicity;
- strong information hierarchy;
- disciplined panel boundaries;
- clear state separation;
- restrained depth;
- consistent spacing;
- structured data legibility;
- calm secondary information.

Do not copy Airtable’s white visual skin.

The relevant lesson is its **organizational discipline**, not its literal palette.

---

## 5.3 Accessible & Ethical supplies non-negotiable interaction rules

Preserve:

- visible keyboard focus;
- high contrast;
- status represented with text/symbols, not color alone;
- keyboard operability;
- restrained motion;
- reduced-motion compatibility;
- practical hit targets;
- semantic state labels.

Accessibility is not a separate visual theme that can be removed later.

---

# 6. Product Shell Architecture

## `FROZEN`

The V1 workbench uses a shared three-pane shell:

```text
┌──────────────────────────────────────────────────────────────┐
│ Global App Chrome / Path Context                             │
├────────────────┬──────────────────────────┬──────────────────┤
│                │                          │                  │
│ Structure      │ Primary Evidence         │ Reconstruction   │
│ + Queue        │ Workspace                │ QA + Evidence    │
│                │                          │                  │
├────────────────┴──────────────────────────┴──────────────────┤
│ Job / Processing / Local Status                              │
└──────────────────────────────────────────────────────────────┘
```

This shell survived:

- multilingual stress;
- 1…N language-layer stress;
- timing-skew stress;
- dense evidence stress;
- Path A / Path B compatibility stress.

The shell is therefore considered stable for V1.

---

# 7. Region Responsibilities

## 7.1 Left Pane — Structure + Queue

## `FROZEN`

The left pane answers:

> **What am I processing, and what should I review next?**

It contains:

1. current source / structural context;
2. relevant reconstruction configuration summary;
3. search;
4. review filters;
5. reconstruction queue.

It is not:

- a generic file explorer;
- a settings panel;
- a complete project navigator;
- a place for all metadata.

The queue should prioritize items that require user attention.

---

## 7.2 Center Pane — Primary Evidence Workspace

## `FROZEN`

The center pane is the visual hero of the application.

It answers:

> **What evidence caused GlyphCue to reconstruct this Cue?**

The content differs legitimately by path:

### Path A
**Visual Evidence Workspace**

### Path B
**Timed Text Evidence Workspace**

The center pane must never degrade into a passive empty region or generic editor.

---

## 7.3 Right Pane — Reconstruction QA + Supporting Evidence

## `FROZEN`

The right pane answers:

> **What did GlyphCue reconstruct, why is it worth checking, and what should the user decide?**

It contains:

- active Cue identity;
- Review Priority / issue state;
- reconstruction diagnostics;
- editable reconstructed text / language layers;
- timing controls where appropriate;
- Approve / Split / Merge / Discard actions;
- supporting observations / source evidence.

The right pane is a focused reconstruction-review surface.

It is not a full Subtitle Edit replacement.

---

## 7.4 Footer / Job Status

## `FROZEN`

Long-running processing state belongs in a stable bottom/status region or dedicated job surface.

The footer may communicate:

- job state;
- phase;
- progress;
- current processing summary;
- local-first state.

Detailed telemetry should not permanently occupy top-level chrome unless real product use proves it necessary.

---

# 8. Global App Chrome

## `GUIDELINE`

The top chrome should remain compact.

Primary contents:

- GlyphCue identity;
- Path A / Path B switch;
- current source context;
- high-level job / reconstruction state;
- Export;
- Help / shortcuts.

Do not turn the header into a telemetry dashboard.

The current prototypes were slightly crowded. Production design should prefer:

> current task context first, diagnostics second.

Detailed metrics belong in:

- footer;
- job panel;
- diagnostics;
- evaluation surfaces.

---

# 9. Path Switching

## `FROZEN`

Path A and Path B are peer product modes.

Suggested labels:

- **Path A: Video Extraction**
- **Path B: Caption Normalizer**

Alternative future wording may be refined for public clarity, but the UI must preserve the product distinction:

```text
Path A
visual / OCR evidence

Path B
timed caption evidence
```

Switching paths should feel like changing evidence source inside one product, not launching a second tool.

Shared grammar must remain visible:

```text
Evidence
→ Observation
→ Cue
→ QA
→ Export
```

---

# 10. Path A — Visual Evidence Workspace

## `FROZEN`

Path A center hero is the video / frame evidence view.

It should support:

- stable media viewport;
- active ROI visualization;
- OCR line / region overlay when useful;
- reconstructed subtitle overlay when useful;
- PTS-aware time context;
- frame / time navigation;
- timeline;
- current Cue relationship.

The viewport should remain visually stable during review.

---

## 10.1 ROI visualization

ROI must be clearly distinguishable from:

- OCR line boxes;
- reconstructed subtitle overlay;
- selection;
- warning state.

Avoid assigning the same visual treatment to every overlay.

Recommended hierarchy:

```text
ROI
→ blue structural boundary

OCR lines
→ lighter / secondary analytical marks

Reconstructed text
→ readable content overlay

Current selection
→ strongest temporary focus treatment
```

---

## 10.2 Media controls

## `FROZEN`

`Space = Play / Pause`.

This convention must not be reused for approval.

Recommended QA/media keyboard grammar:

- `Space` — Play / Pause;
- `R` — Replay active Cue;
- `[` / `]` — Previous / Next Cue;
- Arrow keys — local stepping / time movement as appropriate;
- `Ctrl + Enter` — Approve and advance;
- `E` — Export;
- `?` — Shortcut help.

Exact frame-step semantics may depend on production media implementation.

The meaning of Space must remain stable.

---

# 11. Path A — Track Group Configuration

## `FROZEN`

A visual region is represented as a **Track Group**.

Conceptual UI:

```text
Track Group / Visual Region
├─ ROI
└─ Language Layers 1…N
```

The UI must not force users to redraw the same ROI for every language.

Language layers are repeatable units.

Do not hard-code:

```text
Language A
Language B
```

as the product model.

---

# 12. Language Layer Presentation

## `FROZEN`

Language layers should render as repeatable cards / rows.

Each layer may show:

- language name;
- script / language metadata where useful;
- reconstructed text;
- local issue marker;
- layer-local issue / asymmetry diagnostic.

V1 does not provide per-layer timing controls or a timing override in this presentation — timing belongs to the Cue (see §13).

The QA inspector may show all layers.

The left queue should not display unlimited full text for every layer.

## `GUIDELINE`

For high-N language cases:

- queue shows primary + secondary layer;
- additional layers collapse to `+N layers`;
- full layer content stays in the QA inspector.

This prevents the navigation list from becoming vertically unstable.

---

# 13. Multilingual Timing UI

## `V1 FROZEN`

The production domain model for multilingual timing is frozen for V1, per `ROADMAP.md` §4 (V1 Domain Simplification — Multilingual Timing Closed):

> shared Cue-level timing. Language Layers inherit the Cue's `start_time` / `end_time`.

Representative target samples showed:

- language layers appear together within a Track Group;
- language layers disappear together within a Track Group;
- meaningful timing skew was not observed in representative target material.

V1 UI must encode Cue-level timing as the shared timing span for all language layers in a Track Group. V1 does not implement per-language independent timing, a language-cue alignment graph, or layer timing override.

This is an intentional V1 domain simplification based on the supported material profile, not a universal claim about all burned-in multilingual subtitles. A future version may revisit it if evidence requires it.

## `GUIDELINE`

Accepted V1 UI shape:

```text
Cue Timing
34.600 → 39.200

Japanese
...

English
...
```

Rare missing/asymmetric layers are a degraded/low-quality source condition (diagnostic + review flag), not a case the V1 timing model needs to represent structurally.

---

# 14. Path B — Timed Text Evidence Workspace

## `FROZEN`

Path B must not become a generic text editor.

Its center hero is:

> **Timed Text Evidence Workspace**

It should make reconstruction evidence visible.

The accepted structure includes three conceptual elements.

---

## 14.1 Raw Timed Caption Stream

Show:

- source cue ID;
- raw timing;
- raw source text;
- overlap / rolling relationship;
- current source selection.

Repeated / superseded content may be visually dimmed.

New retained content may be highlighted.

Do not rely on color alone.

---

## 14.2 Consolidation / Reconstruction Explanation

The center should explain:

> Which source observations became this reconstructed Cue?

Example concept:

```text
Source Cues #101 + #102 + #103
→ Reconstructed Cue #01
```

The explanation must be descriptive, not falsely authoritative.

Avoid implying an algorithm has been frozen when only the behavior is known.

---

## 14.3 Timing / Collision Track

Path B should visualize:

- source timing overlap;
- collision;
- reconstructed Cue span;
- review-flagged boundaries.

The goal is to make temporal normalization inspectable.

---

# 15. Path B — Left Pane

## `FROZEN`

The upper structural context changes legitimately from Path A.

Path B left pane should show a compact ingestion / normalization profile, including:

- source filename;
- source format;
- source cue count;
- output / reconstructed cue count;
- language information if relevant;
- non-destructive source status.

The review queue remains structurally consistent with Path A.

Filters may include:

- All;
- Review Needed;
- Preserved / Clean;
- selected issue classes if they prove useful.

Do not create a filter taxonomy larger than the actual review workflow requires.

---

# 16. Non-Destructive Contract

## `FROZEN`

Path B must visibly communicate:

> **The source caption file is preserved.**

Recommended copy:

- `Source protected`;
- `Original file preserved`;
- `Writes normalized output to a new file`.

This product trust contract comes from the accepted seed-cleaner behavior.

The interface must also support the possibility that no transformation is needed.

---

# 17. Preserved / No-Change State

## `FROZEN`

Not every input should be “improved.”

For structurally normal captions, GlyphCue should be able to show:

- `Structure preserved`;
- `No reconstruction required`;
- `Preserved 1:1`.

This state should appear neutral / positive, not as an error.

Conservative behavior is part of the product identity.

---

# 18. Observation → Cue Visual Grammar

## `FROZEN`

Both paths must preserve the same user-facing logic:

```text
Observation(s)
→ reconstructed Cue
→ QA decision
```

Path-specific evidence labels are allowed.

### Path A
`Multi-Frame Observations`

### Path B
`Source Caption Observations`

Do not invent a second conceptual reconstruction model merely because the source format differs.

---

# 19. Evidence Density

## `FROZEN`

Default supporting evidence presentation is:

> **Compact Curated Evidence + Expand Full Evidence**

The user should see diagnostically useful observations first.

Path A examples:

- In-point;
- disagreement / ambiguity;
- representative consensus;
- Out-point.

Path B examples:

- first rolling fragment;
- overlap / disagreement fragment;
- final / representative source;
- boundary / collision source.

The product must preserve access to full evidence.

It should not bury the user under long lists of redundant stable observations by default.

---

# 20. Curated Evidence Principles

## `GUIDELINE`

Curated evidence should be selected because it helps answer:

> “Why did GlyphCue produce this reconstruction?”

It should not simply show the first four observations.

Selection semantics may eventually include:

- boundary evidence;
- disagreement evidence;
- representative consensus;
- anomalous input;
- source-order problem.

The actual selection algorithm is an implementation concern.

The UI spec only requires:

> evidence relevance over evidence volume.

---

# 21. Review Priority / Suspicion Score

## `FROZEN`

Review Priority is a triage signal.

It is **not** a probability.

Do not show:

```text
92% correct
```

or other probability-style claims unless future calibration supports them.

Accepted UI language:

- `Review Priority: 0.72`;
- `Review Priority: High`;
- `Needs Review`;
- `No Review Flags`;
- `Source Structure Preserved`.

---

## 21.1 Semantic discipline

Never label a low suspicion score as if it were another metric.

Rejected example:

```text
High Consensus: 0.02
```

Better:

```text
No Review Flags
```

or:

```text
Review Priority: Low
```

A heuristic must not masquerade as calibrated confidence.

---

# 22. Reconstruction Diagnostics

## `FROZEN`

Diagnostics should explain the reason for review.

Examples:

- CJK OCR ambiguity;
- boundary jitter;
- multilingual layer asymmetry;
- rolling cumulative growth;
- timing collision;
- source-order warning;
- segmentation ambiguity.

Diagnostics must be:

- concise;
- actionable;
- tied to evidence;
- readable without implementation knowledge.

Avoid overloading the user with raw model internals.

---

# 23. QA Action Hierarchy

## `FROZEN`

One region, one visual hero.

In the QA pane, the dominant action is:

> **Approve Reconstructed Cue**

Secondary actions:

- Split;
- Merge;
- Discard.

Primary approval should be visually stronger than all secondary correction actions.

Danger actions should not share the same visual prominence as approval.

---

# 24. Approval Shortcut

## `FROZEN`

Recommended approval shortcut:

> `Ctrl + Enter`

Do not overload Space.

If plain Enter is supported, it must not trigger while editing a text field and should be evaluated carefully for accidental approval risk.

A stable approval shortcut across Path A and Path B is preferred.

---

# 25. Batch Approval

## `DEFERRED`

Do not add “Approve all high-confidence cues” in V1 merely because many items appear clean.

Batch approval creates unanswered questions around:

- safety thresholds;
- false negatives;
- undo;
- calibration;
- human-in-the-loop responsibility.

Only reconsider if real QA throughput measurements show individual approval is a major bottleneck.

---

# 26. Path B Linked Video

## `DEFERRED`

Path B may later support an optional matching local video.

If added, video should act as supporting evidence.

It must not redefine Path B back into Path A.

The Path B core workbench must remain useful without linked video.

---

# 27. CJK Reconstruction Visualization

## `GUIDELINE`

CJK must be first-class.

The UI must not assume:

- whitespace-delimited words;
- English punctuation;
- `>>` speaker conventions;
- fixed Western line-length logic.

However:

## `OPEN`

The exact visual diff granularity for long CJK rolling captions is not frozen.

Do not hard-code:

- character n-gram;
- word segmentation;
- phrase segmentation;

as a UI/domain truth.

Production visualization should follow the actual algorithmic evidence once implementation is benchmarked.

---

# 28. Export Surface

## `FROZEN`

Primary user-facing exports:

- SRT;
- VTT;
- readable transcript;
- AI-ready transcript preset.

Potential media mux / render actions should remain thin and context-appropriate.

---

# 29. Diagnostic JSON Export

## `DEFERRED / INTERNAL`

The prototype included:

> `Sidecar Diagnostics (.JSON)`

This is **not** currently a standard V1 user-facing export format.

Treat JSON evidence output as:

- internal diagnostics;
- evaluation artifact;
- debugging / portfolio reproducibility mechanism;

until a real user-facing need is established.

Do not place it beside SRT/VTT as a default production tab without explicit approval.

---

# 30. AI-Ready Transcript

## `FROZEN`

AI-ready transcript remains an **export preset**, not a separate product subsystem.

It may control:

- timestamp density;
- cue merging;
- selected language layers;
- output formatting.

Do not add built-in AI summary/chat merely because the transcript is intended for AI use.

---

# 31. Progress and Job UX

## `FROZEN`

Long-running work must not appear frozen.

Processing must surface:

- current phase;
- progress where meaningful;
- current processed time / unit;
- cancellation.

Progress should be tied to real job state.

Avoid fake indefinite progress if real phase information exists.

---

## 31.1 Product personality

## `GUIDELINE`

Friendly status copy is allowed in restrained form.

Tone:

> serious technical workbench with personality.

Do not use:

- constant jokes;
- rapid rotating messages;
- childish mascots dominating work;
- animations that distract from evidence.

If playful copy is used:

- change slowly;
- prefer phase boundaries;
- keep real job status primary;
- honor reduced motion / quiet preferences.

---

# 32. Scroll Ownership

## `FROZEN`

The entire application must not become one giant scroll container.

Independent ownership:

- left queue scrolls independently;
- center evidence stream scrolls when needed;
- right QA / supporting evidence scrolls independently;
- media evidence remains stable when possible.

The user should not lose the primary evidence simply because a supporting list is long.

---

# 33. Layout Density

## `FROZEN`

GlyphCue should be information-rich but not cramped.

Professional density comes from:

- clear hierarchy;
- compact repeated components;
- predictable spacing;
- legible metadata;
- stable alignment.

It does not come from:

- 10px body text everywhere;
- excessive borders;
- maximum data per pixel;
- permanent telemetry clutter.

The current prototype density is the **upper bound direction**, not a mandate to make production denser.

---

# 34. Base Layout Tokens

The Round 2/3 prototype established the following working geometry.

## `GUIDELINE`

```text
Header height        ~52 px
Footer height        ~38 px
Left pane width      ~320 px
Right pane width     ~450 px
Center pane          flexible / remaining width
```

These values are production starting points.

Native desktop implementation may convert them into logical pixels / framework units.

Do not treat them as immutable if:

- OS scaling;
- localization;
- accessibility;
- minimum-window constraints;

require adjustment.

The **relative hierarchy** is more important:

> center is dominant; right QA is wider than left structure pane.

---

# 35. Pane Resizing

## `GUIDELINE`

Where technically reasonable:

- left and right panes should be resizable;
- practical minimum widths should prevent content collapse;
- users may be allowed to collapse secondary structure when focusing on evidence.

Do not allow resizing to destroy critical controls.

Exact splitter behavior is implementation-dependent.

---

# 36. Minimum Window / Reflow

## `OPEN`

The prototype was validated primarily as a desktop workbench at a wide viewport.

Production implementation must define:

- minimum supported window width;
- minimum supported height;
- behavior below preferred width;
- OS display scaling behavior.

The design should not automatically reflow into a mobile-style stacked layout.

This is a desktop product.

If space becomes insufficient, prefer:

1. panel resizing;
2. controlled panel collapse;
3. internal scrolling;

before stacking the entire application vertically.

---

# 37. Color System

## `FROZEN`

Use the Round 2/3 dark token family as the production color baseline.

### Background / Surfaces

```text
Void / App Background      #08090c
Surface 0                  #0f1217
Surface 1                  #151921
Surface 2                  #1b212c
Surface 3                  #232b38
Surface Hover              #2a3444
```

### Borders

```text
Border Subtle              #1e2634
Border Medium              #2a3547
Border Strong              #3b4960
Focus / Accent Border      #0099ff
```

### Text

```text
Primary Text               #f8fafc
Secondary Text             #94a3b8
Muted Text                 #64748b
Disabled Text              #475569
```

### Accent

```text
Electric Blue              #0099ff
Blue Hover                 #26abff
Blue Subtle                rgba(0, 153, 255, 0.12)
Blue Glow                  rgba(0, 153, 255, 0.25)
```

### Semantic

```text
Success                    #10b981
Warning                    #f59e0b
Danger                     #ef4444
Info                       #0ea5e9
```

---

# 38. Accent Discipline

## `FROZEN`

Electric blue is the primary interaction accent.

Use it for:

- focus;
- active Path;
- active selection;
- ROI;
- playhead;
- important interactive borders;
- selected source evidence;
- links / contextual actions.

Do **not** turn every clickable element blue.

Secondary controls should remain dark neutral.

Success, warning, and danger colors must retain semantic meaning.

---

# 39. Language Colors

## `GUIDELINE`

Different language layers may use restrained secondary colors for quick differentiation.

Prototype examples:

```text
Layer 1 / cyan           #38bdf8
Layer 2 / violet         #a78bfa
Layer 3 / green          #34d399
```

Language identity must not rely on color alone.

Always include:

- layer number;
- language name;
- text label.

Colors should remain supportive, not branding-level accents.

---

# 40. Typography

## `FROZEN` — Font roles

Primary UI stack:

```text
-apple-system
BlinkMacSystemFont
"Segoe UI"
Roboto
"Helvetica Neue"
Arial
sans-serif
```

Technical / timing stack:

```text
"JetBrains Mono"
"Cascadia Code"
"SF Mono"
Consolas
Menlo
monospace
```

Do not bundle proprietary reference fonts merely to imitate Framer or Airtable.

---

## 40.1 Type hierarchy

## `GUIDELINE`

The prototype established a compact desktop UI hierarchy.

Suggested production ranges:

```text
Brand / primary identity       15–16 px / 700
Panel / primary body           13–14 px / 400–500
Primary control                12–13 px / 600
Section heading                11–12 px / 700 / uppercase where appropriate
Secondary metadata             11–12 px
Technical metadata / PTS       10.5–12 px mono
Micro badges                   10–11 px
```

Do not import Framer’s giant display typography into the desktop application.

Long reconstructed text fields may use a slightly larger size than dense metadata.

---

# 41. Typography Discipline

## `FROZEN`

Use monospace only where fixed-width reading improves comprehension:

- PTS;
- source Cue IDs;
- counts;
- short technical metadata;
- timing values;
- diagnostic tags where useful.

Do not make the entire UI monospace.

The workbench should feel technical, not terminal-like.

---

# 42. Spacing System

## `GUIDELINE`

Use an 8px-oriented spacing rhythm with smaller internal increments where dense technical controls require them.

Common values:

```text
4 px    micro gaps
6 px    compact repeated-control gap
8 px    standard internal gap
10 px   compact card padding
12 px   standard card / panel padding
16 px   major panel padding
24 px   rare larger separation
```

Avoid arbitrary per-component spacing unless the information hierarchy requires it.

---

# 43. Radius System

## `FROZEN`

Use restrained radius.

Prototype baseline:

```text
Small             4 px
Medium            8 px
Large             12 px
Pill              full / 9999 px
```

Do not make every panel a large soft SaaS card.

Primary workbench panes should feel structural.

Pill shapes are appropriate for:

- status;
- filters;
- compact badges;

not for every button.

---

# 44. Depth and Shadow

## `FROZEN`

Depth should remain restrained.

The dark workbench is separated mainly through:

- surface value;
- borders;
- focus rings;
- local shadow around true floating surfaces.

Use stronger shadow for:

- modal;
- floating overlay;
- selected media canvas where useful.

Do not use heavy ambient shadows on every card.

Do not add glass panels for style alone.

---

# 45. Buttons

## 45.1 Primary

Use for the single dominant action in a region.

Examples:

- Export;
- Approve Cue.

Visual:

- strong fill;
- highest local contrast;
- clear hover/focus.

## 45.2 Secondary

Use neutral dark surface + border.

Examples:

- Split;
- Merge;
- Adjust ROI;
- Telemetry.

## 45.3 Quiet / Icon

Use for low-priority utility.

Examples:

- Help;
- close;
- local view actions.

## 45.4 Danger

Danger semantics must be clear.

Example:

- Discard Cue.

Danger should not visually compete with the primary action until hovered / focused unless the state is destructive and urgent.

---

# 46. One Region, One Visual Hero

## `FROZEN`

Every major region should have one dominant action or object.

### Left
Current review target / queue selection.

### Center
Evidence.

### Right
Approve / correct reconstructed Cue.

### Header
Current product / source context.

This principle should be used during production review to reject “everything looks equally important” layouts.

---

# 47. Inputs and Text Editing

## `FROZEN`

Reconstructed text editing should happen in focused per-layer fields.

Do not turn the right pane into a Word-style rich text editor.

Text edits should remain visibly tied to:

- active Cue;
- language layer;
- evidence.

Timing fields should use monospace or fixed-width presentation.

---

# 48. Timing Controls

## `GUIDELINE`

Direct timing editing should support:

- readable current value;
- small nudge;
- larger nudge;
- keyboard-accessible operation.

Prototype increments such as `±10 ms` and `±100 ms` are interaction examples.

They are not frozen product constants.

Final increments should follow real timing-resolution needs.

---

# 49. Timeline

## `FROZEN`

A compact timeline is part of the shared workbench grammar.

Path A:

- evidence / change density;
- Cue spans;
- playhead;
- flagged boundaries.

Path B:

- source overlap / timing density;
- reconstructed Cue spans;
- collision;
- flagged boundaries.

The timeline should explain temporal structure, not mimic a full NLE/video-editing timeline.

Avoid adding tracks, keyframes, editing tools, and media-editor complexity that GlyphCue does not need.

---

# 50. Timeline Color Semantics

## `GUIDELINE`

Suggested roles:

```text
Blue        active / analysis / playhead
Green       clean / reconstructed / preserved success
Amber       review needed / suspicious
Gray        neutral / preserved / inactive
```

Use labels/symbols in addition to color.

---

# 51. Modals

## `GUIDELINE`

Use modals for bounded secondary tasks such as:

- Export;
- shortcuts;
- job details;
- confirmation where necessary.

Do not put primary reconstruction workflow into modal chains.

Modals should be:

- compact;
- dismissible;
- keyboard accessible;
- visually consistent with dark surfaces.

---

# 52. Toasts

## `GUIDELINE`

Use for short confirmation:

- Cue approved;
- export copied;
- mode changed;
- non-critical operation completed.

Do not use toasts for:

- critical errors;
- long explanations;
- information the user must reference later.

Motion should be subtle and reduced-motion compatible.

---

# 53. Filters and Queue States

## `FROZEN`

Review filters should remain small and task-oriented.

Path A baseline:

- All;
- Review Needed;
- Clean / Approved.

Path B baseline:

- All Reconstructed;
- Review Needed;
- Preserved.

Only add issue-specific filters after real usage proves they help.

---

# 54. Empty States

## `GUIDELINE`

Empty states should explain the next useful action.

Examples:

### No media / source loaded
- Import local video;
- Import SRT/VTT.

### No review items
- `No review flags`;
- show summary;
- offer Export.

### No observations for current Cue
- explain whether evidence is unavailable, preserved, or not required.

Avoid celebratory clutter.

---

# 55. Error States

## `FROZEN`

Errors should identify:

1. what failed;
2. what was preserved;
3. what the user can do next.

Particularly important for Path B:

> source input must remain safe.

For long-running Path A:

- failed job state;
- partial work state;
- restart / cancel outcome;

must not be hidden behind a generic red toast.

---

# 56. Local-First Signaling

## `GUIDELINE`

A restrained local-first status may appear in the footer or source context.

Example:

> `Local-First · Source Protected`

Do not over-market privacy inside every screen.

The signal exists to reinforce trust, not to become decoration.

---

# 57. Accessibility Requirements

## `FROZEN`

Production implementation must preserve:

- visible focus state;
- keyboard navigation;
- readable contrast;
- non-color state labels;
- reduced-motion respect;
- clear disabled states;
- practical target sizes;
- accessible labels for icon-only controls.

Color is always secondary evidence.

Warning example:

```text
⚠ Review Priority: High
```

not merely an amber border.

---

# 58. Motion

## `FROZEN`

Motion must be functional and restrained.

Allowed:

- subtle hover;
- focus;
- modal transition;
- progress animation;
- small toast transition.

Avoid:

- decorative parallax;
- animated gradients;
- pulsing AI effects;
- constant waveform motion;
- unnecessary glowing;
- rapid state transitions.

Reduced-motion users should still receive complete state information.

---

# 59. Product Personality

## `GUIDELINE`

GlyphCue may be slightly playful in waiting states and microcopy.

The product must still read as a serious technical tool.

Preferred personality:

- concise;
- calm;
- occasionally witty;
- never childish;
- never mystical about AI.

Avoid copy like:

> “AI magic is happening…”

Prefer:

> “Comparing neighboring frames…”

or:

> “Checking ambiguous subtitle boundaries…”

---

# 60. Prototype-Only Elements That Must Not Ship by Default

## `PROTOTYPE-ONLY`

The following existed to validate decisions.

They are not standard production UI.

### Round 2 / 3 stress-test bar

Examples:

- 2-Layer / 3-Layer toggle;
- Shared Cue / Independent Layer Timing toggle;
- Compact Curated / Full Stream toggle;
- Path B scenario selector.

These controls were **prototype instrumentation**.

Production UI should not expose them as global bars.

---

### Fake implementation metrics

Examples:

- `97.6% frames skipped`;
- exact fake FPS;
- fixed duplicate-reduction percentage;
- prototype-specific model names.

Only show real metrics once the production system actually generates and justifies them.

---

### Fake algorithm names

Do not freeze:

- Levenshtein voting;
- character n-gram consensus;
- a specific rolling-overlap algorithm;

because they appeared in prototype data.

Use approved neutral product vocabulary until implementation evidence chooses the actual method.

---

# 61. Production Terminology

## `FROZEN`

Preferred stable UI vocabulary:

- Path A: Video Extraction;
- Path B: Caption Normalizer;
- Track Group;
- Language Layer;
- Cue;
- Observation;
- Review Priority;
- Reconstruction Diagnostics;
- Reconstruction QA;
- Source Caption Observation;
- Multi-Frame Observation;
- Source Protected;
- Preserved / No Reconstruction Required;
- Export.

Avoid user-facing jargon that does not help action.

---

# 62. Technical Vocabulary Visibility

## `GUIDELINE`

Terms such as:

- PTS;
- ROI;
- OCR;
- Cue;
- Observation;

are acceptable in GlyphCue because the product is a technical workbench.

But where first-time users may not understand them:

- use tooltip;
- short description;
- contextual label.

Do not simplify so aggressively that important timing/evidence meaning becomes vague.

---

# 63. Advanced Settings

## `FROZEN`

Default workflow should not expose CV pipeline tuning.

Do not make users configure:

- change thresholds;
- OCR preprocessing;
- scan density;
- spatial weighting;
- color weighting;

unless real evidence proves a setting is necessary.

If such controls are eventually added:

> place them in Advanced Settings and keep the default path automatic.

---

# 64. Settings Surface

## `GUIDELINE`

Settings should have lower visual intensity than the reconstruction workbench.

Do not reproduce the entire evidence-workbench visual density in Settings.

Settings should be:

- calm;
- grouped;
- searchable if large enough;
- low-decoration;
- clear about defaults.

---

# 65. Export Surface Hierarchy

## `FROZEN`

User-facing export priority:

1. subtitle files;
2. transcript;
3. AI-ready transcript preset;
4. thin media output if available.

Internal diagnostics must remain secondary.

Export should not require navigating away from the QA context.

---

# 66. Path A / Path B Legitimate Differences

## `FROZEN`

The two paths are allowed to differ where evidence itself differs.

| Region | Path A | Path B |
|---|---|---|
| Left context | ROI / Track Group | Source / Normalization Profile |
| Center hero | Video / Frame Evidence | Timed Text Evidence |
| Supporting evidence | Frame / OCR observations | Source caption observations |
| Main diagnostics | OCR / timing / multilingual evidence | rolling / overlap / timing / segmentation |
| Source trust | local media | protected local caption file |

The shared shell does not require identical widgets.

---

# 67. Shared Product Grammar

## `FROZEN`

Across both paths, preserve:

- Path context;
- Structure + Queue;
- Primary Evidence Workspace;
- Cue-centric QA;
- Review Priority;
- evidence expansion;
- Approve / correction grammar;
- Export;
- local-first status;
- keyboard discipline.

This continuity is what makes GlyphCue one product.

---

# 68. Do Not Turn GlyphCue Into a Full Subtitle Editor

## `FROZEN`

Do not add full professional editor surface area by default:

- styling authoring;
- advanced ASS authoring;
- global retiming suite;
- translation management suite;
- full subtitle-format conversion studio;
- rich text formatting;
- complex timeline editing.

GlyphCue owns reconstruction QA.

Deep editing can be delegated to the established subtitle ecosystem.

---

# 69. Do Not Turn GlyphCue Into a Video Editor

## `FROZEN`

Path A uses media evidence.

It does not imply:

- clip editing;
- multi-track editing;
- effects;
- transitions;
- color grading;
- audio mixing.

The video viewport serves reconstruction evidence.

---

# 70. Do Not Turn GlyphCue Into an AI Dashboard

## `FROZEN`

Avoid:

- “AI score” cards everywhere;
- floating model stats as decoration;
- abstract AI icons;
- magic-wand interactions without evidence;
- confidence percentages without calibration.

The product identity comes from inspectable evidence and human QA.

---

# 71. Do Not Turn GlyphCue Into a Developer Console

## `FROZEN`

Technical metadata is appropriate.

Console aesthetics are not the goal.

Avoid:

- full monospace UI;
- terminal-green text;
- dense diagnostic logs in the primary workspace;
- code-first presentation;
- developer-only vocabulary without user benefit.

---

# 72. DESIGN.md vs Product Architecture

This document must not resolve architecture questions that remain open.

Examples:

- actual consensus algorithm;
- actual CJK segmentation strategy.

Multilingual timing schema, the desktop technology stack, and the OCR runtime are no longer open — all are frozen for V1 (see §13 above, `ROADMAP.md` §3/§4, and `docs/adr/0001-ocr-runtime-selection.md` for the OCR runtime decision). This document still must not encode implementation details of the consensus/segmentation choices that remain genuinely open.

If implementation needs an open decision resolved, escalate it to architecture / engineering review.

Do not hide architectural decisions inside UI code.

---

# 73. DESIGN.md vs Prototype

The HTML prototype is a visual evidence artifact.

It is not the final production component map.

Future agents should not:

- copy prototype JS state directly into production architecture;
- copy fake metrics;
- preserve stress-test instrumentation;
- infer domain types from mock data;
- preserve every exact pixel value without framework validation.

They should preserve:

- layout grammar;
- visual hierarchy;
- interaction meaning;
- evidence presentation;
- shared shell.

---

# 74. Responsive / Scaling Guidance

## `GUIDELINE`

GlyphCue is a desktop-first product.

Prioritize:

- 100% / 125% / 150% Windows scaling;
- common laptop widths;
- 1080p desktop use;
- large external monitor use.

Do not optimize for phone or tablet layouts in V1.

Text, timing fields, and controls must not become unusably small at common OS scaling.

---

# 75. Localization

## `GUIDELINE`

The workbench must tolerate:

- English;
- French;
- CJK UI labels if localization is added later.

Avoid fixed-width labels that only fit English.

Source subtitle text must support multilingual Unicode correctly.

Do not use flag emoji as the only language identity.

---

# 76. Iconography

## `GUIDELINE`

Use a restrained line-icon family.

Icons support:

- media;
- source file;
- timeline;
- export;
- help;
- warning;
- protected source;
- evidence;
- navigation.

Do not mix unrelated icon families.

Text labels remain important for primary actions.

---

# 77. Focus Order

## `GUIDELINE`

Keyboard focus should follow task flow:

```text
Global mode / source
→ Left queue
→ Center evidence
→ Right QA fields
→ Approve / correction actions
→ Supporting evidence
→ Export / utility
```

Modal focus must be trapped within the modal and restored on close.

---

# 78. Review Flow

## `FROZEN`

The ideal reconstruction-review loop is:

```text
Select flagged Cue
↓
Inspect primary evidence
↓
Read diagnostic reason
↓
Edit text / timing if needed
↓
Inspect curated supporting evidence
↓
Approve
↓
Advance to next relevant Cue
```

The UI should reduce mode switching during this loop.

---

# 79. High-Throughput Review

## `GUIDELINE`

Optimize for keyboard + visual scanning before adding bulk actions.

Helpful characteristics:

- stable pane positions;
- predictable cue movement;
- no modal per Cue;
- approval without mouse travel;
- evidence visible near decision surface;
- current Cue identity always clear.

Batch automation is deferred until real throughput data justifies it.

---

# 80. Data Integrity UX

## `FROZEN`

The UI should communicate when an operation affects:

- source;
- reconstructed working state;
- exported result.

For Path B especially:

> original source is preserved.

Do not use ambiguous Save behavior that makes users fear destructive overwrite.

---

# 81. Save / Persistence Language

## `OPEN`

Exact persistence model is not frozen by UI prototype.

The production application will need clear language for:

- autosave;
- project/session state;
- exported files;
- source files.

Do not invent “Save Project” behavior before storage architecture defines it.

---

# 82. Path A Processing Setup

## `GUIDELINE`

Before processing, the setup flow should remain minimal:

- select local video;
- define ROI;
- choose language layer(s);
- optionally select processing range;
- start reconstruction.

Do not require advanced CV configuration in the main setup flow.

---

# 83. Path B Processing Setup

## `GUIDELINE`

Before normalization:

- select local SRT/VTT;
- inspect detected format/language;
- confirm non-destructive output behavior;
- start normalization.

Optional advanced settings must not dominate.

---

# 84. Processing Range

## `FROZEN`

Partial-video processing is a first-class Path A concept.

The UI should make the selected range visible.

**V1 frozen truth (closed in Milestone 9, resolving the prior "output/processing choice" framing):** selected ranges preserve original source timestamps. Rebasing (renumbering a selected range's timestamps relative to the selection rather than the source) is **not** a V1 output mode and may only re-enter scope through the Stop-Building Rule. This matches ROADMAP.md Milestone 2's and `ProcessingRange`'s existing, consistent absolute-source-timeline behavior -- this section only corrects the doc to state that as frozen truth, no rebasing feature was added to reach this.

Exact control shape (`PathAMediaPane`'s range checkbox + start/end fields) is implemented as of Milestone 9.

---

# 85. Empty Product Shell

## `GUIDELINE`

On first launch / no source:

Do not show an empty three-pane shell full of disabled controls.

Prefer a calm entry state that offers:

- `Open Video`;
- `Open Caption File`.

Once a source is loaded, transition into the full workbench shell.

This entry state should retain the same visual DNA.

---

# 86. Home / Landing Surface

## `OPEN`

The prototypes began inside an active workbench.

A minimal launch / recent-source surface may be needed.

If created, it should remain thin.

Do not create a dashboard merely because desktop apps often have one.

The product’s center remains the reconstruction workbench.

---

# 87. Recent Files / Projects

## `DEFERRED / EVIDENCE-DRIVEN`

Do not add a complex recent-project manager unless persistence/workflow needs prove it useful.

A small recent-source list may be acceptable later.

---

# 88. Theme

## `FROZEN for V1`

Dark Precision is the V1 visual identity.

Do not spend V1 scope on a full light theme unless accessibility or OS integration creates a concrete requirement.

A future light theme may be revisited after product stabilization.

---

# 89. Contrast Validation

## `REQUIRED BEFORE RELEASE`

The prototype palette is the baseline, but production implementation must validate actual rendered contrast in the target framework.

Do not claim WCAG compliance merely because the reference candidate mentioned it.

At minimum verify:

- primary text;
- secondary text;
- disabled states;
- blue accent;
- warning;
- success;
- focus;
- selected surfaces.

---

# 90. Reduced Motion

## `REQUIRED`

All non-essential motion must respect reduced-motion settings where practical.

Progress may continue to update numerically even when visual animation is reduced.

---

# 91. Design Tokens — Canonical Names

Future implementation should centralize semantic tokens.

Recommended naming:

```text
bg_void
surface_0
surface_1
surface_2
surface_3
surface_hover

border_subtle
border_medium
border_strong
border_focus

text_primary
text_secondary
text_muted
text_disabled

accent_primary
accent_primary_hover
accent_primary_subtle

semantic_success
semantic_warning
semantic_danger
semantic_info
```

Avoid scattered hard-coded colors across widgets.

---

# 92. State Tokens

Use shared semantic roles for:

- default;
- hover;
- focus;
- active;
- selected;
- disabled;
- warning;
- success;
- danger;
- preserved;
- review-needed.

A component may render these differently, but the semantic meaning should remain consistent.

---

# 93. Production Agent Guardrails

Future UI implementation agents must obey:

1. Do not redesign the three-pane shell.
2. Do not replace dark precision with a generic light dashboard.
3. Do not merge Path A and Path B into one ambiguous workflow.
4. Do not make the center pane secondary to forms.
5. Do not move full evidence into hidden diagnostics-only pages.
6. Do not turn the right QA pane into a full subtitle editor.
7. Do not expose prototype stress controls.
8. Do not ship fake metrics.
9. Do not freeze unapproved algorithm names in UI.
10. Do not display heuristic Review Priority as calibrated probability.
11. Do not reuse Space for approval.
12. Do not add batch approval without evidence.
13. Do not add linked video to Path B unless explicitly approved.
14. Do not add user-facing JSON diagnostics export without scope approval.
15. Do not implement per-language-layer independent timing; V1 Language Layers inherit Cue timing (frozen, see §13).
16. Do not encode state by color alone.
17. Do not use decoration to simulate technical sophistication.
18. Do not make every action primary.
19. Do not use a single giant scroll container.
20. Do not silently expand product scope through UI.

---

# 94. Open Design / Architecture Dependencies

The following remain explicitly unresolved.

## O2 — Minimum window / responsive collapse

Requires production-framework validation.

## O3 — Final persistence / save interaction

Depends on storage architecture.

## O4 — Optional Path B linked video

Deferred unless evidence justifies.

## O5 — CJK overlap-diff granularity

Depends on actual reconstruction algorithm.

## O6 — Home / first-launch surface

✓ Closed in Milestone 9: `GlyphCueEntry` (`src/glyphcue/ui/app.py`) implements the minimal entry surface from section 85 — `Open Video` / `Open Caption File`, no dashboard — as the production entrypoint.

---

# 95. Deferred Features

Current V1 design does not require:

- Batch Approve;
- Path B linked video;
- diagnostic JSON as normal user export;
- full light theme;
- full subtitle-authoring workspace;
- full video editor;
- ASR;
- AI summary/chat;
- long-term learning mode;
- subtitle removal / inpainting;
- platform downloading;
- advanced CV tuning in default UI.

---

# 96. What Is Now Frozen After Three Prototype Rounds

The following have sufficient visual evidence to stop prototyping.

### Visual DNA
- Hybrid Dark Precision Evidence Workbench.

### Product shell
- Header;
- three-pane body;
- footer/job state.

### Shared pane roles
- Left = Structure + Queue;
- Center = Primary Evidence;
- Right = Reconstruction QA + Evidence.

### Path A identity
- video/frame evidence as center hero.

### Path B identity
- timed-text evidence as center hero.

### Multilingual configuration
- Track Group → 1…N Language Layers.

### Evidence density
- Compact Curated default;
- expandable Full Evidence.

### Interaction
- independent scroll ownership;
- Cue-centric QA;
- Review Priority triage;
- Space = media Play/Pause;
- stable Approve shortcut.

### Trust
- Path B source protected / non-destructive behavior visible.

### Product coherence
- Path A and Path B are one GlyphCue workbench.

---

# 97. What Does NOT Need Another Prototype Round

Do not open another generic product-shell prototype merely to polish:

- colors;
- card spacing;
- header wording;
- one more evidence layout;
- small icon choices;
- exact button radius.

These can be resolved in production implementation against this design spec.

A new prototype loop is justified only if a future unknown materially affects:

- product architecture;
- core workflow;
- domain interaction;
- high-cost implementation direction.

---

# 98. Production Visual Review Checklist

A production milestone that creates or substantially changes UI should be reviewed against:

### Product identity
- Does it still look like GlyphCue?
- Is evidence visually central?

### Hierarchy
- Is one region / one visual hero preserved?
- Is the primary action obvious?

### Shell
- Are the three pane roles still intact?
- Is scroll ownership correct?

### Evidence
- Can the user understand why a Cue exists?
- Is relevant evidence visible before redundant evidence?

### QA
- Can the user correct and approve without leaving context?
- Are diagnostics actionable?

### Accessibility
- Focus visible?
- Color-independent status?
- Contrast acceptable?
- Keyboard path usable?

### Scope
- Did the UI invent a new feature?
- Did prototype-only instrumentation leak into production?

---

# 99. Design Acceptance Standard

V1 visual implementation should be considered acceptable when:

1. Path A and Path B both fit naturally in the frozen shared shell;
2. evidence remains the visual center;
3. multilingual content does not break layout;
4. dense evidence does not overwhelm review;
5. QA can be completed primarily from the right workbench pane;
6. primary workflows are keyboard-friendly;
7. long-running work remains legible and cancelable;
8. source-protection behavior is clear;
9. no uncalibrated AI-confidence claims are shown;
10. the interface looks like a serious technical product, not a prototype dashboard.

---

# 100. Final Design Principle

GlyphCue should not visually promise intelligence through spectacle.

It should earn trust by showing:

> what the source evidence was,  
> what the system reconstructed,  
> why the result deserves attention,  
> what the human decided,  
> and what clean artifact comes out.

The defining visual grammar is:

```text
Evidence
→ Reconstruction
→ Human Judgment
→ Clean Output
```

That is the GlyphCue product identity.
