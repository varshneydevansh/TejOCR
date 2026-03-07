# TejOCR Security and Risk Review

**Reviewed**: 2026-03-07  
**Release target**: 0.1.9

## Scope

This review covers the current TejOCR runtime and packaging state after the OCR hardening work:

- OCR engine execution path
- PDF helper/runtime detection
- setup and diagnostics command generation
- user-configurable executable paths
- logging and local data exposure
- package metadata consistency

## Executive Summary

TejOCR remains a local, offline LibreOffice extension with no network transport, no remote code download, and no document-macro execution path added by the OCR runtime. That keeps the external attack surface relatively small.

There is no obvious remote-code-execution issue in the hardened OCR pipeline as currently implemented. The main remaining risks are:

1. **Trusted executable path risk**: a user- or environment-provided Tesseract path is still treated as trusted and may point to any local executable.
2. **Local privacy exposure risk**: OCR output and source metadata may be shown in dialogs, copied to clipboard, or exposed to a local user via the log file and UI workflow.
3. **Packaging consistency risk**: release metadata and manifest references must stay aligned with packaged files to avoid stale or broken install-time metadata behavior.

## What Was Hardened

### 1. LibreOffice Python launcher safety

The runtime previously risked launching unsafe LibreOffice helper wrappers on macOS while building install guidance. The hardened runtime now:

- rejects `Contents/Resources/python`
- rejects `LibreOfficePython`
- rejects helper scripts like `python3-config` / `python3.11-config`
- avoids executing candidate Python interpreters just to print pip commands

This materially reduced a local stability and trust issue in setup/diagnostics and PDF-helper guidance paths.

### 2. OCR execution predictability

Preset behavior is now bounded and explicit:

- `Fast`: 1 exact attempt
- `Balanced`: 1 exact attempt + at most 1 recovery
- `Accuracy`: 1 exact attempt + at most 1 enhanced recovery
- `Custom`: strict user-selected values

This reduces the old "unexpected fallback chain" behavior that made OCR output harder to reason about.

### 3. PDF rendering behavior

PDF OCR now:

- streams pages instead of rasterizing the full document up front
- uses preset-driven base DPI
- rerenders weak pages when necessary

This reduces resource spikes and makes PDF behavior more predictable for both single-page and multi-page documents.

## Remaining Risks

### Risk 1: Trusted executable path boundary

**Status**: still present by design  
**Severity**: Medium  
**Applies to**: local machine trust boundary only

TejOCR allows users or environment variables to provide a custom Tesseract executable path. If a malicious or incorrect executable is configured, TejOCR will treat it as the OCR engine and execute it.

Why this is not currently a remote vulnerability:

- the path must already be controlled locally,
- TejOCR does not fetch executables over the network,
- this is equivalent to trusting a local OCR binary configured by the user or administrator.

Recommended follow-up:

- warn explicitly in UI that custom Tesseract path must point to a trusted local binary,
- optionally verify basename/metadata more strictly before save/run,
- add a "reset to auto-detect" fast path in settings.

### Risk 2: Local privacy exposure through UI and clipboard

**Status**: still present  
**Severity**: Medium  
**Applies to**: local privacy, not code execution

OCR output may contain sensitive personal or document data. That data can currently be:

- shown in review dialogs,
- shown in completion dialogs,
- copied to the system clipboard,
- visible in document insertion targets,
- partially reflected in source labels and summaries.

Current mitigating factors:

- runtime diagnostics do not intentionally log full OCR text,
- preview fallback truncates oversized dialog content,
- logging is configured to favor `ERROR` level in production.

Recommended follow-up:

- keep full OCR text out of logs,
- reduce how much OCR content is shown in completion dialogs by default,
- favor compact summaries plus explicit technical-details sections,
- document clipboard/privacy implications in user help.

### Risk 3: Packaging and metadata consistency

**Status**: partially mitigated in 0.1.9  
**Severity**: Medium  
**Applies to**: installation integrity and release correctness

`description.xml` and `META-INF/manifest.xml` reference release-note and description files. If the build script omits those files, LibreOffice metadata behavior can become stale or inconsistent.

Recommended follow-up:

- keep `build_tejocr.py`, `description.xml`, and `META-INF/manifest.xml` in sync,
- validate packaged files against manifest entries as part of release build checks,
- keep release notes and description text files included in the final `.oxt`.

## Findings Not Considered Vulnerabilities

- Hidden executor rollback (`HiddenOcrExecutor`) is a maintainer rollback switch, not a user-facing security control.
- OCR preview and completion density are usability issues first; they do not currently amount to a security defect by themselves.
- The extension remains offline and local-only; no cloud OCR or remote API path is involved.

## Recommended 0.1.9 Follow-up Work

1. Add a warning label near custom Tesseract path that this field must point to a trusted local executable.
2. Add a release-build check that compares `META-INF/manifest.xml` entries with actual packaged files.
3. Redesign review/completion/setup dialogs so sensitive content is shown more deliberately and technical details are not dumped by default.
4. Keep runtime helper detection purely non-executing for any future install-guidance features.

## Validation Checklist

- `python3 -m unittest discover -s tests`
- package build includes release-note and descriptor text files referenced by metadata
- settings/setup no longer spawn unsafe LibreOffice Python helper launchers
- OCR logs do not contain full extracted document text during normal success paths
