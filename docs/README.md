# TejOCR Documentation Hub

This folder contains all deep documentation for the extension.

## Quick Start

- [README (project entry)](../README.md)
- [Architecture overview](architecture/overview.md)
- [Dispatch and runtime flow](architecture/dispatch-flow.md)
- [Method call map](reference/method-map.md)
- [UNO APIs used](reference/uno-apis.md)
- [Output modes](reference/output-modes.md)
- [OCR presets and engine tuning](reference/ocr-options-and-engine-tuning.md)
- [Build and release](dev/build-release.md)
- [Packaging and metadata validation](dev/metadata-and-packaging.md)
- [Troubleshooting installation/license issues](troubleshooting/installation.md)
- [UI fallback behavior](troubleshooting/dialog-fallbacks.md)

## ASCII Diagrams Index

- [Architecture flow](architecture/overview.md#ascii-flow)
- [Selected image OCR flow](flow/selected-image-ocr.md)
- [File OCR flow](flow/file-image-ocr.md)
- [Output routing matrix](reference/output-modes.md#ascii-output-routing)
- [OCR tuning flow](reference/ocr-options-and-engine-tuning.md#runtime-option-resolution)

## Mermaid Diagrams

- [Architecture and dispatch flow](architecture/overview.md)
- [Dispatch breakdown](architecture/dispatch-flow.md)
- [Selected/file OCR state](flow/)
- [Method map](reference/method-map.md)
- [UNO API maps](reference/uno-apis.md)
- [Output mode flowchart](reference/output-modes.md)
- [OCR options and tuning flow](reference/ocr-options-and-engine-tuning.md)
- [Build/packaging diagnostics](dev/build-release.md)
- [Troubleshooting flows](troubleshooting/installation.md)

## Documentation Principles

These docs are written to be:
- action-oriented (what each handler does),
- traceable (function-by-function),
- runtime-oriented (what happens in LibreOffice),
- and install/debug friendly (especially extension manager and `description.xml` issues).

## Legacy docs location

The root-level markdown files (`DEVELOPER_GUIDE.md`, `TECHNICAL.md`, `FUNCTIONALITY.md`, `CODEMAP.md`) now contain short pointers to this folder to keep the top-level docs clean.
