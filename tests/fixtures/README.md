# Benchmark Fixtures

This directory is for small OCR benchmark fixtures and a local manifest.

## Generate the local corpus

Regenerate the benchmark fixtures and manifest with:

```bash
python3 tests/fixtures/generate_benchmark_fixtures.py
```

This writes:

- image fixtures for English, mixed `eng+hin`, sparse text, single-line text, and small text
- `single_page_document.pdf`
- `multi_page_document.pdf`
- `benchmark_manifest.json`
- an optional benchmark report can then be written to `benchmark_report.local.json`

## Expected manifest

Create `benchmark_manifest.json` here with a top-level `cases` array. Example shape:

```json
{
  "cases": [
    {
      "label": "english-image",
      "path": "english-image.png",
      "type": "image",
      "preset": "balanced",
      "lang": "eng",
      "expected_text": "Hello OCR"
    },
    {
      "label": "single-page-pdf",
      "path": "single-page.pdf",
      "type": "pdf",
      "preset": "balanced",
      "lang": "eng",
      "expected_text": "Expected transcript"
    }
  ]
}
```

Paths may be relative to this manifest file or absolute.

## Running the benchmark

From the repository root:

```bash
python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json
```

Optional JSON report output:

```bash
python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json --output /tmp/tejocr-benchmark.json
```

The current local workflow in this repo also writes:

```bash
python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json --output tests/fixtures/benchmark_report.local.json
```

Modern vs legacy comparison on the same machine:

```bash
python3 tests/benchmark_ocr.py \
  --manifest tests/fixtures/benchmark_manifest.json \
  --executor modern \
  --baseline-executor legacy \
  --baseline-output tests/fixtures/benchmark_baseline.legacy.local.json \
  --output tests/fixtures/benchmark_report.modern.local.json \
  --enforce-targets
```

## Suggested local corpus

- image with a single text line
- sparse text image
- single-page PDF
- multi-page PDF
- mixed-language sample such as `eng+hin`

Keep large or sensitive benchmark inputs out of git. Store only sanitized fixtures here when they are safe to commit.
