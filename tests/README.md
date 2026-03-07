# TejOCR Test Suite

This directory contains maintained automated tests for TejOCR runtime-agnostic logic.

## Current tests

- `test_ocr_runtime.py`: pure planning/runtime tests for presets, bounded retries, language validation, and diagnostics.
- `test_tejocr_engine.py`: engine tests for the direct CLI OCR path, recovery behavior, and OEM gating. UNO is stubbed so these tests run in plain `python3`.
- `test_benchmark_ocr.py`: regression tests for benchmark comparison thresholds and report evaluation.
- `test_tejocr_pdf.py`: PDF helper tests for renderer fast-path detection.
- `benchmark_ocr.py`: optional local benchmark harness for image/PDF latency and transcript accuracy scoring.

## How to run

Run from repository root:

```bash
python3 -m unittest discover -s tests
```

If you need an isolated interpreter environment, run:

```bash
python3 -m unittest tests.test_ocr_runtime tests.test_tejocr_engine
```

Optional benchmark run:

```bash
python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json
```

Modern vs legacy comparison with threshold enforcement:

```bash
python3 tests/benchmark_ocr.py \
  --manifest tests/fixtures/benchmark_manifest.json \
  --executor modern \
  --baseline-executor legacy \
  --baseline-output tests/fixtures/benchmark_baseline.legacy.local.json \
  --output tests/fixtures/benchmark_report.modern.local.json \
  --enforce-targets
```

## Notes

- Legacy manual scripts (`test_*.py` at repository root) have been removed to keep this directory as the maintained test source.
- Tests that require UNO-specific integration are stubbed or mocked where possible.
- Some runtime behavior still requires manual verification in LibreOffice (UI workflows, extension dialogs).
