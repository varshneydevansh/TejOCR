# Plan: TejOCR UI Alignment

**Generated**: 2026-03-07  
**Updated**: 2026-03-07  
**Estimated Complexity**: High

## Overview

TejOCR's OCR runtime is now substantially more mature than its LibreOffice UI. The engine already has bounded preset semantics, adaptive PDF handling, requested-vs-effective diagnostics, stricter `Custom` behavior, better language validation, and faster PDF/batch execution. The UI still presents much of that through crowded XDL layouts, fallback infoboxes, and dense completion dialogs.

This revised plan narrows the scope to the actual remaining gap:

1. make Settings explain the runtime truthfully,
2. make Setup & Diagnostics actionable and trustworthy,
3. make result/review dialogs readable instead of dump-like,
4. treat macOS production LibreOffice install guidance as a first-class blocker, not a side note.

The plan also incorporates three product decisions already made:

- PDF DPI stays derived for `Fast`, `Balanced`, and `Accuracy`.
- Manual PDF DPI is exposed only in `Custom`.
- The UI must still show the derived PDF policy for the standard presets so users understand what each preset really does.

For `OCR Complete`, the current UI already shows full diagnostics immediately as a dense message box. This plan treats that as the current behavior and moves the product toward a compact summary first, with technical details available beneath it or on demand.

`FilterTube.in` remains in Settings, but it should read as a distinct secondary surface rather than competing visually with OCR configuration.

## Prerequisites

- Current runtime behavior remains the source of truth:
  - [ocr_runtime.py](/Users/devanshvarshney/TejOCR/python/tejocr/ocr_runtime.py)
  - [tejocr_engine.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_engine.py)
  - [tejocr_pdf.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_pdf.py)
- Current full settings and setup surfaces:
  - [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl)
  - [tejocr_setup_dialog.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_setup_dialog.xdl)
  - [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- Current fallback/compatibility dialog path:
  - [tejocr_interactive_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_interactive_dialogs.py)
- Current install and security notes:
  - [installation.md](/Users/devanshvarshney/TejOCR/docs/troubleshooting/installation.md)
  - [security-review.md](/Users/devanshvarshney/TejOCR/docs/dev/security-review.md)

## Status Against OCR Hardening

### Already achieved in code/runtime

- `Sprint 1` from the original hardening plan is largely complete.
  - Pure runtime planning exists.
  - Run stats and attempt stats exist.
  - Benchmark harness and fixture corpus exist.
  - Tests run outside LibreOffice.
- `Sprint 2` is largely complete in semantics.
  - Runtime-derived PSM/OEM labels exist.
  - OEM support coercion exists.
  - Language validation and requested-vs-effective diagnostics exist.
- `Sprint 3` is largely complete in execution behavior.
  - Run-scoped session exists.
  - Direct `tesseract` subprocess path exists.
  - Retry caps exist.
  - PDF page streaming and adaptive DPI exist.
  - Batch parallelism exists.
- `Sprint 4` is only partly complete.
  - Benchmarks, comparison, and rollout docs exist.
  - Manual UI/QA polish is still incomplete.

### Still not aligned in product/UI terms

- Settings does not explain derived PDF behavior clearly enough.
- `Custom` is semantically strict in runtime, but under-exposed in the full settings UI.
- Setup still falls back to an infobox path in cases where a dedicated diagnostics experience should be used.
- The production macOS install command for LibreOffice Python packages is still not trustworthy enough to present as a polished guided action.
- `OCR Complete` and review flows still behave like debug output instead of product dialogs.
- Auto-detected Tesseract state is validated, but not clearly surfaced back to the user.

### Practical completion estimate

- OCR hardening overall: about `80-85%` complete.
- UI alignment to that hardening: about `35-40%` complete.
- Setup/install UX on production macOS LibreOffice: below `50%` complete because the current pip guidance path is still unreliable.

## Current Findings To Carry Forward

### Current `OCR Complete` behavior

Today the completion UI shows full diagnostics immediately in a message box:

- source breakdown,
- selected languages,
- preset,
- preprocessing flags,
- runtime executor,
- requested/effective config,
- attempts,
- PDF DPI,
- renderer.

That is why the current completion dialog feels cluttered. The plan assumes compact-by-default is the target, not the current state.

### Current `Custom` behavior

Runtime meaning is already strong:

- no preset override,
- no silent fallback override,
- exact manual PSM/OEM/scale/preprocessing values.

UI meaning is still weak:

- the full settings dialog does not expose the entire manual control story clearly,
- manual PDF DPI is not yet visibly attached to `Custom`,
- users can select `Custom` without understanding what new control authority it grants them.

### Current setup/install blocker

The user has reproduced:

```bash
/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract pillow
```

ending with a killed process on macOS production LibreOffice.

That means setup/install guidance is still unresolved for at least one important deployment class. Earlier success with `LibreOfficeDev.app` does not make production `LibreOffice.app` safe by default. The likely difference is bundle/runtime/signing behavior between the two app builds, not just the directory roots used for candidate discovery.

The UI cannot be considered complete until it stops presenting a command path that may be dead on arrival for the user's actual LibreOffice install.

## Design Direction

Use a restrained **editorial control room** approach rather than a generic utility form:

- strong section bands,
- high-contrast readiness states,
- quiet primary surface,
- blue reserved for OCR actions,
- green/amber/red only for readiness and warnings,
- a deliberately distinct secondary visual language for `FilterTube.in`,
- summary first, technical detail second.

This should not try to mimic a web app inside LibreOffice. It should make the XDL surface feel deliberate, scannable, and less cluttered, while staying within LibreOffice dialog constraints.

## UX Rules

### Rule 1: Presets must explain consequences

- `Fast`: show that PDFs use `200 DPI`, one exact attempt, no enhanced retry.
- `Balanced`: show `200 DPI` base with rerender to `300 DPI` if needed, and at most two attempts.
- `Accuracy`: show `300 DPI` base and enhanced recovery.
- `Custom`: show that user-selected engine and preprocessing values are honored exactly, including manual PDF DPI.

### Rule 2: Derived values must stay visible

- Derived PDF DPI must be visible even when not editable.
- Requested and effective runtime info belongs to diagnostics and review surfaces, not the primary settings area.
- Auto-detected path must be visible even when the editable field is blank.

### Rule 3: Advanced does not mean hidden by accident

- `Custom` must reveal an actual manual area.
- Non-custom presets can still show advanced controls, but the UI must indicate when a preset is deriving or overriding behavior.

### Rule 4: Setup must guide action, not dump text

- The setup dialog should answer:
  - what is missing,
  - what is already available,
  - what exact action is recommended next,
  - which copyable command is safe for this OS and LibreOffice bundle.

### Rule 5: Result dialogs should separate summary from internals

- Summary belongs up front.
- Detailed runtime diagnostics belong behind a smaller secondary block or expander-style area.
- Long source lists must be clipped or grouped rather than dumped inline.

## Sprint 1: Truth Model and Install-Path Audit

**Goal**: lock the exact runtime-to-UI mapping and resolve what install guidance the UI is allowed to present on each platform.

**Demo/Validation**:
- One truth table for primary, advanced, derived, and diagnostic fields.
- One install-guidance matrix for `LibreOffice.app`, `LibreOfficeDev.app`, and platform variants.

### Task 1.1: Classify every surfaced field
- **Location**: [ocr_runtime.py](/Users/devanshvarshney/TejOCR/python/tejocr/ocr_runtime.py), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py), [tejocr_service.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_service.py)
- **Description**: classify controls and text outputs into `primary`, `advanced`, `derived`, or `diagnostic`.
- **Complexity**: 4
- **Dependencies**: none
- **Acceptance Criteria**:
  - Preset, language, output mode, preview, and merge are primary.
  - PSM/OEM and preprocessing are advanced.
  - PDF DPI is derived for standard presets and editable only in `Custom`.
  - Attempts, renderer, requested/effective config, and fallback reasons are diagnostic.
- **Validation**:
  - Review classification against actual runtime plan objects.

### Task 1.2: Define preset-to-UI messaging
- **Location**: [constants.py](/Users/devanshvarshney/TejOCR/python/tejocr/constants.py), [ocr_runtime.py](/Users/devanshvarshney/TejOCR/python/tejocr/ocr_runtime.py)
- **Description**: specify exactly what the UI must say for each preset, including PDF behavior text and whether advanced controls are explanatory or editable.
- **Complexity**: 4
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Each preset has a stable helper description.
  - `Balanced` explicitly mentions `200 DPI` base with rerender to `300 DPI` if needed.
  - `Custom` explicitly mentions manual PDF DPI.
- **Validation**:
  - Text review against current screenshots and runtime policy.

### Task 1.3: Audit install-command trust model by platform and bundle
- **Location**: [tejocr_pdf.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_pdf.py), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py), [installation.md](/Users/devanshvarshney/TejOCR/docs/troubleshooting/installation.md)
- **Description**: document which command strategies are safe to recommend on macOS production LibreOffice, LibreOfficeDev, and other supported platform paths.
- **Complexity**: 8
- **Dependencies**: none
- **Acceptance Criteria**:
  - The UI no longer recommends a command path that is known to be killed on this machine class.
  - The docs clearly distinguish `LibreOffice.app` from `LibreOfficeDev.app` behavior where necessary.
  - The plan explicitly allows the setup UI to say "restart LibreOffice and re-validate" or "use external package guidance" when LO-python pip cannot be trusted.
- **Validation**:
  - Reproduction notes plus manual matrix for the relevant app bundles.

## Sprint 2: Settings Dialog Recomposition

**Goal**: turn Settings into a trustworthy control center instead of a control dump.

**Demo/Validation**:
- Users can tell what preset they are using, what it means for PDF behavior, whether TejOCR is ready, and what Tesseract path is in effect without reading a wall of text.

### Task 2.1: Recompose the layout into explicit zones
- **Location**: [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl), [tejocr_settings_dialog.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog.xdl)
- **Description**: restructure the layout into:
  - readiness header,
  - OCR defaults,
  - PDF behavior block,
  - advanced engine block,
  - footer summary/actions,
  - distinct `FilterTube.in` tile.
- **Complexity**: 6
- **Dependencies**: Sprint 1
- **Acceptance Criteria**:
  - Primary controls sit above advanced controls.
  - The dialog breathes better and is less cramped.
  - `FilterTube.in` no longer looks like another OCR action button.
- **Validation**:
  - Manual visual review on current LibreOffice targets.

### Task 2.2: Add a dedicated PDF behavior block
- **Location**: [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: show the effective preset-driven PDF policy in plain language.
- **Complexity**: 5
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - `Fast`, `Balanced`, and `Accuracy` show derived PDF behavior.
  - `Custom` exposes manual DPI value and editable control.
  - The block updates immediately when preset changes.
- **Validation**:
  - Manual preset switching and screenshot comparison.

### Task 2.3: Surface auto-detected Tesseract path
- **Location**: [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: if the path field is blank, display `Auto-detected:` with the resolved path or `not detected`.
- **Complexity**: 4
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - `Test` updates the helper text.
  - The user can distinguish blank-by-choice from unresolved auto-detection.
- **Validation**:
  - Manual test with blank field and custom path.

### Task 2.4: Make `Custom` reveal a real manual section
- **Location**: [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: separate beginner-safe configuration from true manual control and bind `Custom` to a visible advanced/manual zone.
- **Complexity**: 7
- **Dependencies**: Task 2.2
- **Acceptance Criteria**:
  - `Custom` clearly exposes PSM, OEM, scale, preprocessing, and manual PDF DPI.
  - Standard presets visibly show that some values are derived rather than fully manual.
  - The settings help text describes `Custom` in the same terms as runtime.
- **Validation**:
  - Manual walkthrough of `Balanced` and `Custom`.

### Task 2.5: Improve readiness and status labeling
- **Location**: [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: replace vague status strings with short, scannable readiness text.
- **Complexity**: 4
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Header status and footer summary are not redundant.
  - Messages like `Ready for image + PDF OCR`, `OCR ready, PDF renderer missing`, and `Tesseract missing` are used consistently.
  - Status colors match actual readiness.
- **Validation**:
  - Mocked dependency-state tests plus manual checks.

### Task 2.6: Restyle `FilterTube.in` as a secondary surface
- **Location**: [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: keep the button, but make it read as a distinct tile or sponsor card rather than a peer OCR control.
- **Complexity**: 3
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - The button stays present.
  - The color and placement are clearly distinct from OCR actions.
  - It does not visually interrupt the OCR configuration flow.
- **Validation**:
  - Manual screenshot review.

### Task 2.7: Keep fallback settings flow semantically aligned
- **Location**: [tejocr_interactive_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_interactive_dialogs.py), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: align the compatibility/fallback settings flow with the redesigned full settings dialog so preset meaning, `Custom`, PDF behavior, and path guidance do not diverge by dialog implementation.
- **Complexity**: 6
- **Dependencies**: Tasks 2.2 to 2.5
- **Acceptance Criteria**:
  - Full and fallback settings flows describe presets the same way.
  - `Custom` semantics and manual control expectations match.
  - Auto-detected path and setup-entry guidance are consistent across both surfaces.
- **Validation**:
  - Manual comparison of XDL and interactive settings flows.

## Sprint 3: Setup & Diagnostics Redesign

**Goal**: make Setup & Diagnostics actionable, structured, and honest about platform-specific install limitations.

**Demo/Validation**:
- The dialog answers:
  - what is missing,
  - what is installed,
  - what the next best action is,
  - what exact command can safely be copied.

### Task 3.1: Make the dedicated setup dialog the normal path
- **Location**: [tejocr_setup_dialog.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_setup_dialog.xdl), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: remove the conditions that still send users into the infobox fallback during normal operation.
- **Complexity**: 6
- **Dependencies**: Sprint 1
- **Acceptance Criteria**:
  - Dedicated setup dialog is used whenever the dialog model is available.
  - Infobox fallback is last resort only.
  - The fallback text explicitly says it is degraded mode.
- **Validation**:
  - Manual open on normal and forced-fallback cases.

### Task 3.2: Rebuild diagnostics into action blocks
- **Location**: [tejocr_setup_dialog.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_setup_dialog.xdl), [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: structure the dialog into:
  - overall status,
  - dependency checklist,
  - install action,
  - copyable command,
  - validation action,
  - notes/restart guidance.
- **Complexity**: 6
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - No long unstructured paragraph dump.
  - Missing dependencies use explicit status rows.
  - Copy command and validate actions are obvious.
- **Validation**:
  - Manual review with missing Python packages and with everything installed.

### Task 3.3: Replace unsafe install guidance on macOS production LibreOffice
- **Location**: [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py), [installation.md](/Users/devanshvarshney/TejOCR/docs/troubleshooting/installation.md), [WIKI_Installation_Guide.md](/Users/devanshvarshney/TejOCR/docs/WIKI_Installation_Guide.md)
- **Description**: stop presenting install commands that may still be killed on production `LibreOffice.app`, and define a safe fallback guidance model.
- **Complexity**: 8
- **Dependencies**: Task 1.3
- **Acceptance Criteria**:
  - If a command path is not trustworthy for the current bundle, the UI says so.
  - The user still gets platform-specific next steps.
  - `Validate` and restart guidance remain first-class actions.
- **Validation**:
  - Manual testing on production LibreOffice and LibreOfficeDev where available.

### Task 3.4: Show dynamic post-install state transitions clearly
- **Location**: [tejocr_dialogs.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_dialogs.py)
- **Description**: after `Validate`, refresh package and renderer state in-place and show concise before/after readiness updates.
- **Complexity**: 5
- **Dependencies**: Task 3.2
- **Acceptance Criteria**:
  - `Py: 0/3 | PDF: ok` can move to `Py: 3/3 | PDF: ok` without reopening the entire settings surface.
  - If restart is still required, the dialog states that directly.
- **Validation**:
  - Manual validate flow after package install or simulated package availability change.

## Sprint 4: Review and Completion UX

**Goal**: replace wall-of-text review/completion windows with structured result dialogs.

**Demo/Validation**:
- Users can confirm insertion and understand outcomes quickly, while still having access to technical details when needed.

### Task 4.1: Redesign the review dialog around summary first
- **Location**: [tejocr_service.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_service.py), [uno_utils.py](/Users/devanshvarshney/TejOCR/python/tejocr/uno_utils.py)
- **Description**: make review focus on:
  - source count,
  - output size,
  - clipped preview,
  - insertion confirmation,
  - optional details.
- **Complexity**: 7
- **Dependencies**: Sprint 2
- **Acceptance Criteria**:
  - Single-source and multi-source review share the same structure.
  - Long previews are clipped cleanly.
  - Technical metadata is separated from the primary preview.
- **Validation**:
  - Manual selected image, single PDF, and mixed batch review flows.

### Task 4.2: Redesign `OCR Complete`
- **Location**: [tejocr_service.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_service.py), [uno_utils.py](/Users/devanshvarshney/TejOCR/python/tejocr/uno_utils.py)
- **Description**: convert the completion dialog from a debug-style dump into a compact summary with an optional technical details section.
- **Complexity**: 7
- **Dependencies**: Sprint 2
- **Acceptance Criteria**:
  - Primary surface shows success/failure, destination, total sources, and short source summary.
  - Technical details include preset, language, attempts, PDF DPI, renderer, requested/effective config.
  - Multi-file output does not produce unreadable walls of text.
- **Validation**:
  - Manual image-only, PDF-only, and mixed-batch completion flows.

### Task 4.3: Standardize detail formatting
- **Location**: [tejocr_service.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_service.py), [ocr_runtime.py](/Users/devanshvarshney/TejOCR/python/tejocr/ocr_runtime.py)
- **Description**: create one formatting standard for runtime detail rows instead of ad hoc inline pipes and oversized blocks.
- **Complexity**: 4
- **Dependencies**: Task 4.2
- **Acceptance Criteria**:
  - Runtime summaries are short and consistent.
  - Detail order is predictable.
  - Formatting works for one source and many sources.
- **Validation**:
  - Snapshot-style tests on summary/detail builders.

### Task 4.4: Define graceful fallback behavior for limited LibreOffice sessions
- **Location**: [uno_utils.py](/Users/devanshvarshney/TejOCR/python/tejocr/uno_utils.py), [tejocr_service.py](/Users/devanshvarshney/TejOCR/python/tejocr/tejocr_service.py)
- **Description**: ensure that when a richer review or completion window is not supported, the fallback infobox/message-box path still uses the compact summary model rather than regressing to a full dump.
- **Complexity**: 5
- **Dependencies**: Tasks 4.1 to 4.3
- **Acceptance Criteria**:
  - Unsupported multiline/review sessions still show summary-first messaging.
  - Technical details remain available in a smaller secondary block or follow-up action, not as the default wall of text.
  - Single-source and multi-source cases remain readable in fallback mode.
- **Validation**:
  - Manual testing in a session that forces the non-rich dialog path.

## Sprint 5: Docs, QA, and Rollout

**Goal**: align docs and manual QA with the redesigned UI so the release is not ahead of its instructions.

**Demo/Validation**:
- Docs match actual screenshots/flows.
- Manual QA checklist covers the redesigned settings, setup, review, and completion surfaces.

### Task 5.1: Update screenshots and docs for `0.1.9` UI reality
- **Location**: [README.md](/Users/devanshvarshney/TejOCR/README.md), [installation.md](/Users/devanshvarshney/TejOCR/docs/troubleshooting/installation.md), [WIKI_Installation_Guide.md](/Users/devanshvarshney/TejOCR/docs/WIKI_Installation_Guide.md)
- **Description**: update user-facing docs to match the redesigned settings/setup/result flows and the platform-specific install reality.
- **Complexity**: 4
- **Dependencies**: Sprints 2 to 4
- **Acceptance Criteria**:
  - Docs no longer imply setup/install behavior that the UI does not actually guarantee.
  - `Custom` and PDF behavior are explained in the same terms as the UI.
- **Validation**:
  - Docs review against final dialog copy.

### Task 5.2: Expand manual QA checklist for UI truthfulness
- **Location**: [ocr-hardening-checklist.md](/Users/devanshvarshney/TejOCR/docs/dev/ocr-hardening-checklist.md)
- **Description**: add explicit UI-verification items for settings, setup, review, and completion.
- **Complexity**: 3
- **Dependencies**: Sprints 2 to 4
- **Acceptance Criteria**:
  - Checklist covers preset switching, `Custom`, derived PDF behavior, detected path display, setup copy command, validate refresh, and mixed batch completion readability.
- **Validation**:
  - Manual checklist run.

### Task 5.3: Release guardrails for install guidance changes
- **Location**: [security-review.md](/Users/devanshvarshney/TejOCR/docs/dev/security-review.md), [installation.md](/Users/devanshvarshney/TejOCR/docs/troubleshooting/installation.md)
- **Description**: document the remaining trust boundary around custom executable paths and any still-limited install flows.
- **Complexity**: 3
- **Dependencies**: Sprint 3
- **Acceptance Criteria**:
  - Docs explicitly call out trusted custom path risk.
  - Docs are honest about platform cases where automatic package guidance is limited or restart-bound.
- **Validation**:
  - Security/doc review.

### Task 5.4: Review localization and label-length fit after the redesign
- **Location**: [l10n](/Users/devanshvarshney/TejOCR/l10n), [tejocr_settings_dialog_full.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_settings_dialog_full.xdl), [tejocr_setup_dialog.xdl](/Users/devanshvarshney/TejOCR/dialogs/tejocr_setup_dialog.xdl)
- **Description**: verify that the redesigned copy still fits the XDL surfaces and translation pipeline, especially for longer helper text and status labels.
- **Complexity**: 3
- **Dependencies**: Sprints 2 to 4
- **Acceptance Criteria**:
  - Updated copy remains localizable.
  - No critical truncation occurs in the redesigned surfaces.
  - English source strings are stable enough for translation follow-up.
- **Validation**:
  - Manual label-fit review plus translation string audit.

## Testing Strategy

- Unit:
  - preset-to-helper-text mapping,
  - derived vs editable field rules,
  - status label builders,
  - runtime detail summary formatters.
- Dialog integration:
  - settings state refresh,
  - setup dialog rendering with mocked dependency states,
  - `Custom` reveal behavior,
  - auto-detected path helper text,
  - PDF behavior helper updates on preset change.
  - fallback settings path parity,
  - compact fallback review/completion formatting.
- Manual LibreOffice QA:
  - settings open/save,
  - setup dialog on missing dependencies,
  - validate after install,
  - blank Tesseract path plus auto-detect,
  - `Balanced` vs `Custom`,
  - single image,
  - single PDF,
  - multi-page PDF,
  - mixed image + PDF batch,
  - preview on/off,
  - merge on/off.
- Negative cases:
  - Tesseract missing,
  - PDF renderer missing,
  - unsupported OEM,
  - missing traineddata,
  - killed or non-viable LibreOffice Python pip path on macOS production bundle.

## Potential Risks & Gotchas

- LibreOffice XDL has limited layout flexibility, so some design ambitions must be expressed through hierarchy and wording more than rich styling.
- The compatibility fallback dialog already exposes more engine controls than the full settings dialog. The redesign must reduce inconsistency, not create a second divergent UX.
- A blank path field plus auto-detect summary must not accidentally overwrite user intent or saved settings.
- `Custom` can become overwhelming if too many controls become visible without grouping and explanation.
- Setup guidance must not over-promise on macOS production LibreOffice until the install-path trust model is actually validated.
- The `FilterTube.in` surface can still feel intrusive if placement and contrast are not intentionally controlled.
- Dense OCR result metadata is still useful; the risk is not that it exists, but that it dominates the primary completion experience.

## Rollback Plan

- Keep the current runtime behavior unchanged while iterating on UI composition.
- Ship UI restructuring behind the existing package version flow without changing OCR executor semantics.
- If a redesigned dialog fails on a LibreOffice variant, retain the compatibility/fallback path temporarily, but label it clearly as degraded mode.
- If install-command changes prove unreliable on a platform, fall back to validation-only guidance plus docs rather than showing unsafe copy commands.
