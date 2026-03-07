# OCR Hardening Checklist

Use this checklist before shipping OCR pipeline changes.

## Automated checks

- Run `python3 -m unittest discover -s tests`
- Run `python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json`
- Run the modern vs legacy comparison:
  `python3 tests/benchmark_ocr.py --manifest tests/fixtures/benchmark_manifest.json --executor modern --baseline-executor legacy --baseline-output tests/fixtures/benchmark_baseline.legacy.local.json --output tests/fixtures/benchmark_report.modern.local.json --enforce-targets`
- Compare the benchmark report against the prior baseline on the same machine
- Review requested vs effective diagnostics for at least one image case and one PDF case

## Manual OCR cases

- Selected image, `Fast`
- Selected image, `Balanced`
- Selected image, `Accuracy`
- File image, `Custom` with manual PSM/OEM values
- Single-page PDF
- Multi-page PDF
- Mixed image + PDF batch
- Batch with merge enabled
- Batch with merge disabled
- Preview enabled
- Preview disabled
- `eng+hin` or another mixed-language case
- Missing language code case to verify install guidance
- OEM `0` or `2` on a runtime without legacy support to verify warning/disable behavior

## Expected behavior

- `Fast` performs one exact OCR attempt
- `Balanced` performs one exact attempt and at most one recovery attempt
- `Accuracy` performs one exact attempt and at most one enhanced preprocessing recovery
- `Custom` keeps the user-selected PSM/OEM/scale/preprocessing values exactly
- PDFs are rendered page-by-page instead of rasterizing the whole document up front
- `Fast` and `Balanced` start PDF OCR at `200 DPI`
- `Accuracy` starts PDF OCR at `300 DPI`
- Weak PDF pages may be rerendered at `300 DPI`
- Requested vs effective diagnostics are visible in completion messages and logs
- Missing language packs are reported with install guidance

## Failure cases to verify

- invalid Tesseract path
- missing Tesseract executable
- missing PDF renderer
- missing traineddata for requested language
- empty OCR result from low-quality source

## Rollout notes

- Keep benchmark inputs local and sanitized
- Measure PDF performance on both single-page and multi-page documents
- Measure bulk throughput with multiple files, not just one PDF
- Hidden rollback key for maintainers: `HiddenOcrExecutor=legacy`
