# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import types
import unittest


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
TESTS_ROOT = CURRENT_DIR
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
for path in (TESTS_ROOT, PYTHON_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


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


from tejocr import constants
import benchmark_ocr


class TestBenchmarkOcr(unittest.TestCase):
    def test_compare_reports_passes_when_targets_are_met(self):
        baseline = {
            "cases": [
                {"label": "english-image-fast", "preset": constants.OCR_PRESET_FAST, "accuracy": 1.0, "seconds": 0.5, "page_count": 1},
                {"label": "english-image", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 0.5, "page_count": 1},
                {"label": "small-text-image", "preset": constants.OCR_PRESET_ACCURATE, "accuracy": 0.9, "seconds": 0.5, "page_count": 1},
                {"label": "single-page-pdf", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 1.0, "page_count": 1},
            ],
            "summary": {"throughput_pages_per_second": 1.0},
        }
        current = {
            "cases": [
                {"label": "english-image-fast", "preset": constants.OCR_PRESET_FAST, "accuracy": 0.995, "seconds": 0.1, "page_count": 1},
                {"label": "english-image", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 0.995, "seconds": 0.1, "page_count": 1},
                {"label": "small-text-image", "preset": constants.OCR_PRESET_ACCURATE, "accuracy": 0.91, "seconds": 0.1, "page_count": 1},
                {"label": "single-page-pdf", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 0.5, "page_count": 1},
            ],
            "summary": {"throughput_pages_per_second": 2.5},
        }

        comparison = benchmark_ocr.compare_reports(current, baseline)
        self.assertTrue(comparison["passed"])
        self.assertEqual(comparison["violations"], [])

    def test_compare_reports_reports_regressions(self):
        baseline = {
            "cases": [
                {"label": "english-image-fast", "preset": constants.OCR_PRESET_FAST, "accuracy": 1.0, "seconds": 0.5, "page_count": 1},
                {"label": "english-image", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 0.5, "page_count": 1},
                {"label": "small-text-image", "preset": constants.OCR_PRESET_ACCURATE, "accuracy": 0.95, "seconds": 0.5, "page_count": 1},
                {"label": "single-page-pdf", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 1.0, "page_count": 1},
            ],
            "summary": {"throughput_pages_per_second": 2.0},
        }
        current = {
            "cases": [
                {"label": "english-image-fast", "preset": constants.OCR_PRESET_FAST, "accuracy": 0.95, "seconds": 0.4, "page_count": 1},
                {"label": "english-image", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 0.95, "seconds": 0.4, "page_count": 1},
                {"label": "small-text-image", "preset": constants.OCR_PRESET_ACCURATE, "accuracy": 0.9, "seconds": 0.4, "page_count": 1},
                {"label": "single-page-pdf", "preset": constants.OCR_PRESET_BALANCED, "accuracy": 1.0, "seconds": 0.8, "page_count": 1},
            ],
            "summary": {"throughput_pages_per_second": 1.0},
        }

        comparison = benchmark_ocr.compare_reports(current, baseline)
        self.assertFalse(comparison["passed"])
        self.assertGreaterEqual(len(comparison["violations"]), 3)
