# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from tejocr import constants
from tejocr import ocr_runtime


DEFAULTS = {
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


class TestOcrRuntime(unittest.TestCase):
    def test_fast_plan_is_single_exact_attempt_with_200_dpi(self):
        plan = ocr_runtime.resolve_execution_plan(
            {"preset": constants.OCR_PRESET_FAST, "lang": "eng"},
            available_languages=["eng"],
            default_options=DEFAULTS,
        )

        self.assertEqual(plan.pdf_dpi, 200)
        self.assertEqual(len(plan.attempts), 1)
        self.assertEqual(plan.attempts[0].label, "exact")
        self.assertFalse(plan.attempts[0].enhanced)
        self.assertEqual(plan.effective_options["psm"], constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_FAST]["psm"])

    def test_balanced_plan_adds_single_recovery_attempt(self):
        plan = ocr_runtime.resolve_execution_plan(
            {"preset": constants.OCR_PRESET_BALANCED, "lang": "eng", "psm": "3"},
            available_languages=["eng"],
            default_options=DEFAULTS,
        )

        self.assertEqual(plan.pdf_dpi, 200)
        self.assertEqual([attempt.label for attempt in plan.attempts], ["exact", "recovery"])
        self.assertEqual(plan.attempts[1].psm, "11")
        self.assertFalse(plan.attempts[1].enhanced)

    def test_accuracy_plan_adds_enhanced_attempt(self):
        plan = ocr_runtime.resolve_execution_plan(
            {"preset": constants.OCR_PRESET_ACCURATE, "lang": "eng"},
            available_languages=["eng"],
            default_options=DEFAULTS,
        )

        self.assertEqual(plan.pdf_dpi, 300)
        self.assertEqual([attempt.label for attempt in plan.attempts], ["exact", "enhanced"])
        self.assertTrue(plan.attempts[1].enhanced)
        self.assertTrue(plan.attempts[1].improve_image)
        self.assertTrue(plan.attempts[1].grayscale)
        self.assertTrue(plan.attempts[1].binarize)

    def test_custom_plan_keeps_exact_user_configuration(self):
        plan = ocr_runtime.resolve_execution_plan(
            {
                "preset": constants.OCR_PRESET_CUSTOM,
                "lang": "eng",
                "psm": "7",
                "oem": "1",
                "scale": 1.3,
                "grayscale": True,
                "binarize": True,
                "invert": True,
                "improve_image": True,
            },
            available_languages=["eng"],
            default_options=DEFAULTS,
        )

        self.assertEqual(len(plan.attempts), 1)
        attempt = plan.attempts[0]
        self.assertEqual(attempt.psm, "7")
        self.assertEqual(attempt.oem, "1")
        self.assertEqual(attempt.scale, 1.3)
        self.assertTrue(attempt.grayscale)
        self.assertTrue(attempt.binarize)
        self.assertTrue(attempt.invert)
        self.assertTrue(attempt.improve_image)

    def test_language_validation_preserves_order_and_skips_missing_codes(self):
        result = ocr_runtime.validate_language_codes(
            "eng+hin+zzz",
            ["eng", "hin", "script/Latin"],
            default_language="eng",
            platform_name="Darwin",
        )

        self.assertEqual(result.normalized, "eng+hin")
        self.assertEqual(result.invalid_codes, ["zzz"])
        self.assertTrue(result.validated)
        self.assertIn("skipped", result.warning)
        self.assertIn("brew install tesseract-lang", result.install_hint)

    def test_language_validation_falls_back_to_first_available_language(self):
        result = ocr_runtime.validate_language_codes(
            "zzz",
            ["hin", "eng"],
            default_language="fra",
            platform_name="Linux",
        )

        self.assertEqual(result.normalized, "hin")
        self.assertEqual(result.invalid_codes, ["zzz"])
        self.assertTrue(result.validated)

    def test_language_preview_groups_script_packs(self):
        preview = ocr_runtime.build_language_preview(
            ["eng", "hin", "script/Latin", "script/Devanagari"],
            limit=10,
        )

        self.assertIn("Installed languages: eng, hin", preview)
        self.assertIn("Script packs: script/Latin, script/Devanagari", preview)

    def test_coerce_supported_oem_keeps_supported_selection(self):
        oem_value, warning = ocr_runtime.coerce_supported_oem(
            "3",
            {"0": False, "1": True, "2": False, "3": True},
            fallback=constants.DEFAULT_OEM_MODE,
        )

        self.assertEqual(oem_value, "3")
        self.assertEqual(warning, "")

    def test_coerce_supported_oem_replaces_unsupported_legacy_mode(self):
        oem_value, warning = ocr_runtime.coerce_supported_oem(
            "0",
            {"0": False, "1": True, "2": False, "3": True},
            fallback=constants.DEFAULT_OEM_MODE,
        )

        self.assertEqual(oem_value, "3")
        self.assertIn("Selected OEM 0 is unsupported", warning)

    def test_run_diagnostics_reports_requested_and_effective_values(self):
        stats = ocr_runtime.OcrRunStats(
            source_type="file",
            source_label="sample.png",
            requested_options={"psm": "7", "oem": "1", "preset": "custom"},
            effective_options={"psm": "7", "oem": "1", "preset": "custom", "lang": "eng"},
            pdf_dpi=200,
            renderer="pdftoppm",
            used_language="eng",
            attempts=[
                ocr_runtime.OcrAttemptStats(
                    label="exact",
                    lang="eng",
                    psm="7",
                    oem="1",
                    scale=1.0,
                    improve_image=False,
                    grayscale=False,
                    binarize=False,
                    invert=False,
                    seconds=0.12,
                    output_length=42,
                    success=True,
                    low_signal=False,
                )
            ],
        )

        diagnostics = ocr_runtime.build_run_diagnostics_text(stats)
        self.assertIn("Executor: modern", diagnostics)
        self.assertIn("Requested: PSM 7, OEM 1, preset custom", diagnostics)
        self.assertIn("Effective: PSM 7, OEM 1, preset custom, lang eng", diagnostics)
        self.assertIn("Attempts: 1", diagnostics)
        self.assertIn("PDF DPI: 200", diagnostics)
        self.assertIn("Renderer: pdftoppm", diagnostics)


if __name__ == "__main__":
    unittest.main()
