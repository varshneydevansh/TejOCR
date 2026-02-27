# TejOCR Test Suite

This directory contains maintained automated tests for TejOCR runtime-agnostic logic.

## Current tests

- `test_tejocr_engine.py`: unit tests for OCR engine option handling, preprocessing, and dependency checks.

## How to run

Run from repository root:

```bash
python3 -m unittest discover -s tests
```

If you need an isolated interpreter environment, run:

```bash
python3 -m unittest tests.test_tejocr_engine
```

## Notes

- Legacy manual scripts (`test_*.py` at repository root) have been removed to keep this directory as the maintained test source.
- Tests that require UNO-specific integration are mocked where possible.
- Some runtime behavior still requires manual verification in LibreOffice (UI workflows, extension dialogs).
