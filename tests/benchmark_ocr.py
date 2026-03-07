# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Local OCR benchmark harness for images and PDFs.

The manifest is a JSON object with a top-level `cases` array. Each case may contain:

- `label`: human-friendly case name
- `path`: image or PDF path, relative to the manifest file or absolute
- `type`: `image` or `pdf`
- `lang`: optional OCR language override
- `preset`: optional preset override
- `expected_text`: optional transcript for normalized accuracy scoring
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types


def _install_uno_stubs():
    if "uno" not in sys.modules:
        uno = types.ModuleType("uno")
        uno.Any = lambda *_args: _args[-1] if _args else None
        uno.getConstantByName = lambda _name: None
        uno.systemPathToFileUrl = lambda value: value
        uno.fileUrlToSystemPath = lambda value: value
        uno.createUnoStruct = lambda _name: types.SimpleNamespace()
        sys.modules["uno"] = uno
    if "unohelper" not in sys.modules:
        unohelper = types.ModuleType("unohelper")
        unohelper.Base = object
        sys.modules["unohelper"] = unohelper


_install_uno_stubs()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from tejocr import constants
from tejocr import ocr_runtime
from tejocr import tejocr_engine
from tejocr import tejocr_pdf


DEFAULT_OPTIONS = {
    "lang": constants.DEFAULT_OCR_LANGUAGE,
    "psm": constants.DEFAULT_PSM_MODE,
    "oem": constants.DEFAULT_OEM_MODE,
    "scale": 1.0,
    "grayscale": False,
    "binarize": False,
    "invert": False,
    "improve_image": False,
    "preset": constants.DEFAULT_OCR_PRESET,
    "show_preview": False,
    "merge_batch_results": False,
}

FAST_BALANCED_ACCURACY_REGRESSION_LIMIT = 0.01
SINGLE_PAGE_PDF_LATENCY_IMPROVEMENT_TARGET = 0.40
BULK_THROUGHPUT_MULTIPLIER_TARGET = 2.0


def _normalize_text(text):
    return " ".join(str(text or "").split()).strip().lower()


def _levenshtein_distance(left, right):
    left = _normalize_text(left)
    right = _normalize_text(right)
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            substitution = previous[j - 1] + (0 if left_char == right_char else 1)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def _accuracy_score(expected_text, actual_text):
    expected = _normalize_text(expected_text)
    actual = _normalize_text(actual_text)
    if not expected and not actual:
        return 1.0
    denominator = max(len(expected), len(actual), 1)
    distance = _levenshtein_distance(expected, actual)
    return max(0.0, 1.0 - (float(distance) / float(denominator)))


def _load_manifest(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("Benchmark manifest must contain a top-level 'cases' array.")
    return cases


def _resolve_case_path(manifest_path, case_path):
    if os.path.isabs(case_path):
        return case_path
    return os.path.abspath(os.path.join(os.path.dirname(manifest_path), case_path))


def _build_case_options(case, executor_mode=None):
    options = dict(DEFAULT_OPTIONS)
    for key in ("lang", "psm", "oem", "scale", "grayscale", "binarize", "invert", "improve_image", "preset"):
        if key in case:
            options[key] = case[key]
    if executor_mode:
        options["executor_mode"] = executor_mode
    return options


def _run_image_case(session, source_path, options):
    started = time.perf_counter()
    result = tejocr_engine.perform_ocr(
        None,
        None,
        "file",
        source_path,
        options,
        session=session,
    )
    elapsed = time.perf_counter() - started
    stats = result.get("stats") or {}
    return {
        "success": bool(result.get("success")),
        "text": result.get("text") or "",
        "message": result.get("message") or "",
        "seconds": elapsed,
        "attempts": len((stats.get("attempts") or [])),
        "renderer": "",
        "pdf_dpi": (stats.get("pdf_dpi") or 0),
        "page_count": 1,
        "diagnostics": result.get("diagnostics") or "",
        "stats": stats,
    }


def _run_pdf_case(session, source_path, options):
    plan = ocr_runtime.resolve_execution_plan(
        options,
        available_languages=getattr(session, "available_languages", []),
        default_options=DEFAULT_OPTIONS,
    )
    renderer_status = tejocr_pdf.get_pdf_renderer_status()
    renderer_name = renderer_status.get("engine") or ""
    page_count = tejocr_pdf.get_pdf_page_count(source_path) or 0
    base_dpi = plan.pdf_dpi
    attempt_count = 0
    total_ocr_seconds = 0.0
    total_render_seconds = 0.0
    page_texts = []
    page_outputs = []
    temp_images = []
    started = time.perf_counter()

    try:
        page_iterator = tejocr_pdf.iter_rasterized_pdf_pages(source_path, dpi=base_dpi)
        for page_number, image_path in page_iterator:
            if not image_path:
                continue
            temp_images.append(image_path)
            effective_dpi = base_dpi
            ocr_started = time.perf_counter()
            result = tejocr_engine.perform_ocr(
                None,
                None,
                "file",
                image_path,
                options,
                session=session,
            )
            total_ocr_seconds += time.perf_counter() - ocr_started
            stats = result.get("stats") or {}
            attempt_count += len((stats.get("attempts") or []))
            page_text = (result.get("text") or "").strip() if result.get("success") else ""
            effective_dpi = base_dpi

            small_text_page = False
            if base_dpi < 300:
                try:
                    small_text_page = tejocr_pdf.is_probably_small_text_page(image_path)
                except Exception:
                    small_text_page = False

            if base_dpi < 300 and (
                (not page_text)
                or ocr_runtime.is_low_signal_text(page_text)
                or small_text_page
            ):
                rerender_started = time.perf_counter()
                hi_res_image = tejocr_pdf.rasterize_pdf_page(source_path, page_number, dpi=300)
                total_render_seconds += time.perf_counter() - rerender_started
                if hi_res_image:
                    temp_images.append(hi_res_image)
                    retry_started = time.perf_counter()
                    retry = tejocr_engine.perform_ocr(
                        None,
                        None,
                        "file",
                        hi_res_image,
                        options,
                        session=session,
                    )
                    total_ocr_seconds += time.perf_counter() - retry_started
                    retry_stats = retry.get("stats") or {}
                    attempt_count += len((retry_stats.get("attempts") or []))
                    retry_text = (retry.get("text") or "").strip() if retry.get("success") else ""
                    if len(retry_text) >= len(page_text):
                        result = retry
                        stats = retry_stats
                        page_text = retry_text
                        effective_dpi = 300

            page_texts.append(page_text)
            page_outputs.append(
                {
                    "page": page_number,
                    "text_length": len(page_text),
                    "attempts": len((stats.get("attempts") or [])),
                    "pdf_dpi": effective_dpi,
                }
            )
    finally:
        tejocr_pdf.cleanup_temp_images(temp_images)

    elapsed = time.perf_counter() - started
    return {
        "success": True,
        "text": "\n\n".join(page_texts),
        "message": "",
        "seconds": elapsed,
        "attempts": attempt_count,
        "renderer": renderer_name,
        "pdf_dpi": base_dpi,
        "page_count": page_count or len(page_outputs),
        "pdf_render_seconds": total_render_seconds,
        "ocr_seconds": total_ocr_seconds,
        "page_outputs": page_outputs,
        "diagnostics": "Executor: {executor} | Requested: PSM {psm}, OEM {oem}, preset {preset} | Effective: PSM {epsm}, OEM {eoem}, preset {epreset}, lang {lang} | Attempts: {attempts} | PDF DPI: {dpi} | Renderer: {renderer}".format(
            executor=ocr_runtime.coerce_executor_mode(
                options.get("executor_mode"),
                constants.DEFAULT_OCR_EXECUTOR,
            ),
            psm=plan.requested_options.get("psm"),
            oem=plan.requested_options.get("oem"),
            preset=plan.requested_options.get("preset"),
            epsm=plan.effective_options.get("psm"),
            eoem=plan.effective_options.get("oem"),
            epreset=plan.effective_options.get("preset"),
            lang=plan.effective_options.get("lang"),
            attempts=attempt_count,
            dpi=base_dpi,
            renderer=renderer_name or "unknown",
        ),
    }


def _mean(values):
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    return sum(cleaned) / float(len(cleaned))


def _case_map(report):
    return {entry.get("label"): entry for entry in report.get("cases", []) if entry.get("label")}


def compare_reports(current_report, baseline_report):
    current_cases = _case_map(current_report)
    baseline_cases = _case_map(baseline_report)
    comparison = {
        "accuracy": {},
        "latency": {},
        "throughput": {},
        "warnings": [],
        "violations": [],
    }

    for preset in (constants.OCR_PRESET_FAST, constants.OCR_PRESET_BALANCED, constants.OCR_PRESET_ACCURATE):
        current_scores = []
        baseline_scores = []
        for label, current_case in current_cases.items():
            baseline_case = baseline_cases.get(label)
            if not baseline_case:
                continue
            if current_case.get("preset") != preset or baseline_case.get("preset") != preset:
                continue
            if current_case.get("accuracy") is None or baseline_case.get("accuracy") is None:
                continue
            current_scores.append(current_case["accuracy"])
            baseline_scores.append(baseline_case["accuracy"])

        if not current_scores or not baseline_scores:
            comparison["warnings"].append(
                "No comparable accuracy cases found for preset '{preset}'.".format(preset=preset)
            )
            continue

        current_mean = _mean(current_scores)
        baseline_mean = _mean(baseline_scores)
        delta = current_mean - baseline_mean
        comparison["accuracy"][preset] = {
            "current_mean": round(current_mean, 4),
            "baseline_mean": round(baseline_mean, 4),
            "delta": round(delta, 4),
        }
        if preset in (constants.OCR_PRESET_FAST, constants.OCR_PRESET_BALANCED):
            if delta < -FAST_BALANCED_ACCURACY_REGRESSION_LIMIT:
                comparison["violations"].append(
                    "Accuracy regression for preset '{preset}' exceeds 1pp.".format(preset=preset)
                )
        elif delta < 0:
            comparison["violations"].append(
                "Accuracy preset should be non-worse than baseline for preset '{preset}'.".format(
                    preset=preset
                )
            )

    current_single_pdf = current_cases.get("single-page-pdf")
    baseline_single_pdf = baseline_cases.get("single-page-pdf")
    if current_single_pdf and baseline_single_pdf:
        baseline_seconds = float(baseline_single_pdf.get("seconds", 0.0) or 0.0)
        current_seconds = float(current_single_pdf.get("seconds", 0.0) or 0.0)
        if baseline_seconds > 0:
            improvement = (baseline_seconds - current_seconds) / baseline_seconds
            comparison["latency"]["single-page-pdf"] = {
                "current_seconds": round(current_seconds, 4),
                "baseline_seconds": round(baseline_seconds, 4),
                "improvement_ratio": round(improvement, 4),
            }
            if improvement < SINGLE_PAGE_PDF_LATENCY_IMPROVEMENT_TARGET:
                comparison["violations"].append(
                    "Single-page PDF latency improvement is below the 40% target."
                )
    else:
        comparison["warnings"].append("Missing single-page-pdf case in current or baseline report.")

    current_throughput = float(current_report.get("summary", {}).get("throughput_pages_per_second", 0.0) or 0.0)
    baseline_throughput = float(baseline_report.get("summary", {}).get("throughput_pages_per_second", 0.0) or 0.0)
    if current_throughput > 0 and baseline_throughput > 0:
        multiplier = current_throughput / baseline_throughput
        comparison["throughput"] = {
            "current_pages_per_second": round(current_throughput, 4),
            "baseline_pages_per_second": round(baseline_throughput, 4),
            "multiplier": round(multiplier, 4),
        }
        if multiplier < BULK_THROUGHPUT_MULTIPLIER_TARGET:
            comparison["violations"].append(
                "Bulk corpus throughput is below the 2x target."
            )
    else:
        comparison["warnings"].append("Missing throughput data in current or baseline report.")

    comparison["passed"] = not comparison["violations"]
    return comparison


def run_benchmark(manifest_path, executor_mode=None):
    cases = _load_manifest(manifest_path)
    if not cases:
        return {
            "cases": [],
            "summary": {
                "count": 0,
                "executor_mode": ocr_runtime.coerce_executor_mode(executor_mode, constants.DEFAULT_OCR_EXECUTOR),
                "total_seconds": 0.0,
                "average_seconds": 0.0,
                "successful_cases": 0,
                "total_pages": 0,
                "throughput_cases_per_second": 0.0,
                "throughput_pages_per_second": 0.0,
            },
        }

    resolved_executor = ocr_runtime.coerce_executor_mode(executor_mode, constants.DEFAULT_OCR_EXECUTOR)
    session = tejocr_engine.create_ocr_session(show_gui_errors=False, executor_mode=resolved_executor)
    if not session or not getattr(session, "ready", False):
        raise RuntimeError(getattr(session, "path_message", "") or "Tesseract is not ready.")

    results = []
    for case in cases:
        label = case.get("label") or os.path.basename(str(case.get("path") or ""))
        source_path = _resolve_case_path(manifest_path, case.get("path", ""))
        case_type = str(case.get("type") or "image").strip().lower()
        options = _build_case_options(case, executor_mode=resolved_executor)

        if case_type == "pdf":
            outcome = _run_pdf_case(session, source_path, options)
        else:
            outcome = _run_image_case(session, source_path, options)

        expected_text = case.get("expected_text") or ""
        accuracy = _accuracy_score(expected_text, outcome.get("text", "")) if expected_text else None
        results.append(
            {
                "label": label,
                "path": source_path,
                "type": case_type,
                "executor_mode": resolved_executor,
                "preset": options.get("preset"),
                "lang": options.get("lang"),
                "success": outcome.get("success"),
                "seconds": round(float(outcome.get("seconds", 0.0)), 4),
                "attempts": int(outcome.get("attempts", 0)),
                "page_count": int(outcome.get("page_count", 0)),
                "renderer": outcome.get("renderer", ""),
                "pdf_dpi": int(outcome.get("pdf_dpi", 0)),
                "accuracy": round(float(accuracy), 4) if accuracy is not None else None,
                "diagnostics": outcome.get("diagnostics", ""),
                "message": outcome.get("message", ""),
            }
        )

    total_seconds = sum(float(item["seconds"]) for item in results)
    total_pages = sum(int(item.get("page_count", 0) or 0) for item in results)
    return {
        "cases": results,
        "summary": {
            "count": len(results),
            "executor_mode": resolved_executor,
            "total_seconds": round(total_seconds, 4),
            "average_seconds": round(total_seconds / float(len(results)), 4) if results else 0.0,
            "successful_cases": sum(1 for item in results if item.get("success")),
            "total_pages": total_pages,
            "throughput_cases_per_second": round(float(len(results)) / total_seconds, 4) if total_seconds else 0.0,
            "throughput_pages_per_second": round(float(total_pages) / total_seconds, 4) if total_seconds else 0.0,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark TejOCR against a local manifest.")
    parser.add_argument(
        "--manifest",
        default=os.path.join(SCRIPT_DIR, "fixtures", "benchmark_manifest.json"),
        help="Path to the benchmark manifest JSON file.",
    )
    parser.add_argument(
        "--executor",
        default=constants.DEFAULT_OCR_EXECUTOR,
        choices=constants.OCR_EXECUTOR_CHOICES,
        help="OCR executor mode to benchmark.",
    )
    parser.add_argument(
        "--baseline-report",
        default="",
        help="Optional existing JSON report to compare against.",
    )
    parser.add_argument(
        "--baseline-executor",
        default="",
        choices=("",) + constants.OCR_EXECUTOR_CHOICES,
        help="Optional executor mode to benchmark as the baseline on this same machine.",
    )
    parser.add_argument(
        "--baseline-output",
        default="",
        help="Optional path to save an auto-generated baseline report.",
    )
    parser.add_argument(
        "--enforce-targets",
        action="store_true",
        help="Exit non-zero if comparison targets fail.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON report output path.",
    )
    args = parser.parse_args(argv)

    manifest_path = os.path.abspath(args.manifest)
    if not os.path.isfile(manifest_path):
        raise SystemExit(
            "Benchmark manifest not found: {path}\nSee tests/fixtures/README.md for the expected format.".format(
                path=manifest_path
            )
        )

    report = run_benchmark(manifest_path, executor_mode=args.executor)
    baseline_report = None
    if args.baseline_executor:
        baseline_report = run_benchmark(manifest_path, executor_mode=args.baseline_executor)
        if args.baseline_output:
            baseline_output_path = os.path.abspath(args.baseline_output)
            with open(baseline_output_path, "w", encoding="utf-8") as handle:
                json.dump(baseline_report, handle, indent=2, ensure_ascii=True)
    elif args.baseline_report:
        baseline_report_path = os.path.abspath(args.baseline_report)
        with open(baseline_report_path, "r", encoding="utf-8") as handle:
            baseline_report = json.load(handle)

    if baseline_report:
        report["comparison"] = compare_reports(report, baseline_report)

    if args.output:
        output_path = os.path.abspath(args.output)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=True)

    print("Executor: {mode}".format(mode=report["summary"]["executor_mode"]))
    print("Benchmark cases: {count}".format(count=report["summary"]["count"]))
    print("Successful: {count}".format(count=report["summary"]["successful_cases"]))
    print("Total seconds: {seconds}".format(seconds=report["summary"]["total_seconds"]))
    print("Average seconds: {seconds}".format(seconds=report["summary"]["average_seconds"]))
    print("Throughput (cases/s): {value}".format(value=report["summary"]["throughput_cases_per_second"]))
    print("Throughput (pages/s): {value}".format(value=report["summary"]["throughput_pages_per_second"]))
    for item in report["cases"]:
        accuracy = "n/a" if item["accuracy"] is None else "{score:.2%}".format(score=item["accuracy"])
        print(
            "- {label}: {seconds}s | attempts={attempts} | pages={pages} | dpi={dpi} | renderer={renderer} | accuracy={accuracy}".format(
                label=item["label"],
                seconds=item["seconds"],
                attempts=item["attempts"],
                pages=item["page_count"],
                dpi=item["pdf_dpi"],
                renderer=item["renderer"] or "n/a",
                accuracy=accuracy,
            )
        )

    if baseline_report:
        comparison = report.get("comparison") or {}
        print("Comparison passed: {passed}".format(passed=comparison.get("passed")))
        for warning in comparison.get("warnings", []):
            print("Warning: {warning}".format(warning=warning))
        for violation in comparison.get("violations", []):
            print("Violation: {violation}".format(violation=violation))
        if args.enforce_targets and comparison.get("violations"):
            raise SystemExit(2)


if __name__ == "__main__":
    main()
