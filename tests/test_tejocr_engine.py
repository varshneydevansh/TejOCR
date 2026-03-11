# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)


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

from tejocr import constants
from tejocr import tejocr_engine


class TestTejocrEngine(unittest.TestCase):
    def _session(self, **overrides):
        data = {
            "ready": True,
            "path_message": "Tesseract ready",
            "available_languages": ["eng", "hin"],
            "oem_support": {"0": True, "1": True, "2": True, "3": True},
            "tesseract_path": "/usr/bin/tesseract",
            "version": "tesseract 5.5.1",
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def _temp_image(self):
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))
        return handle.name

    def test_run_tesseract_subprocess_forces_utf8_decoding(self):
        with patch.object(tejocr_engine.subprocess, "run", return_value=types.SimpleNamespace()) as run_mock:
            tejocr_engine._run_tesseract_subprocess(["tesseract", "--version"])

        kwargs = run_mock.call_args.kwargs
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_perform_ocr_uses_cli_runtime_without_pytesseract(self):
        image_path = self._temp_image()
        session = self._session()

        with patch.object(tejocr_engine, "PYTESSERACT_AVAILABLE", False), \
             patch.object(tejocr_engine, "_prepare_image_for_attempt", return_value=(image_path, 0.01)), \
             patch.object(
                 tejocr_engine,
                 "_run_cli_ocr_attempt",
                 return_value={
                     "text": "Hello world from OCR",
                     "error": "",
                     "returncode": 0,
                     "used_language": "eng",
                     "seconds": 0.02,
                 },
             ):
            result = tejocr_engine.perform_ocr(
                None,
                None,
                "file",
                image_path,
                {"preset": constants.OCR_PRESET_BALANCED, "lang": "eng"},
                session=session,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Hello world from OCR")
        self.assertIn("Requested:", result["diagnostics"])
        self.assertEqual(len(result["stats"]["attempts"]), 1)

    def test_balanced_mode_runs_one_recovery_attempt_for_low_signal_output(self):
        image_path = self._temp_image()
        session = self._session()
        attempt_results = [
            {
                "text": "tiny",
                "error": "",
                "returncode": 0,
                "used_language": "eng",
                "seconds": 0.02,
            },
            {
                "text": "Recovered text with enough signal",
                "error": "",
                "returncode": 0,
                "used_language": "eng",
                "seconds": 0.03,
            },
        ]

        with patch.object(tejocr_engine, "_prepare_image_for_attempt", return_value=(image_path, 0.0)), \
             patch.object(tejocr_engine, "_run_cli_ocr_attempt", side_effect=attempt_results) as run_attempt:
            result = tejocr_engine.perform_ocr(
                None,
                None,
                "file",
                image_path,
                {"preset": constants.OCR_PRESET_BALANCED, "lang": "eng", "psm": "3"},
                session=session,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Recovered text with enough signal")
        self.assertEqual(run_attempt.call_count, 2)
        self.assertEqual(
            [attempt["label"] for attempt in result["stats"]["attempts"]],
            ["exact", "recovery"],
        )

    def test_legacy_executor_reports_legacy_attempts(self):
        image_path = self._temp_image()
        session = self._session()
        attempt_results = [
            {
                "text": "tiny",
                "error": "",
                "returncode": 0,
                "used_language": "eng",
                "seconds": 0.02,
            },
            {
                "text": "Legacy fallback recovered enough text",
                "error": "",
                "returncode": 0,
                "used_language": "eng",
                "seconds": 0.03,
            },
        ]
        legacy_attempts = [
            tejocr_engine.ocr_runtime.OcrAttemptPlan(
                label="legacy-1",
                lang="eng",
                psm="3",
                oem="3",
                scale=1.0,
                improve_image=False,
                grayscale=False,
                binarize=False,
                invert=False,
            ),
            tejocr_engine.ocr_runtime.OcrAttemptPlan(
                label="legacy-2",
                lang="eng",
                psm="11",
                oem="3",
                scale=1.0,
                improve_image=False,
                grayscale=False,
                binarize=False,
                invert=False,
            ),
        ]

        with patch.object(tejocr_engine, "_prepare_image_for_attempt", return_value=(image_path, 0.0)), \
             patch.object(tejocr_engine, "_run_cli_ocr_attempt", side_effect=attempt_results), \
             patch.object(tejocr_engine, "_build_legacy_attempt_plans", return_value=legacy_attempts):
            result = tejocr_engine.perform_ocr(
                None,
                None,
                "file",
                image_path,
                {
                    "preset": constants.OCR_PRESET_BALANCED,
                    "lang": "eng",
                    "executor_mode": constants.OCR_EXECUTOR_LEGACY,
                },
                session=session,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Legacy fallback recovered enough text")
        self.assertEqual(len(result["stats"]["attempts"]), 2)
        self.assertTrue(result["stats"]["attempts"][0]["label"].startswith("legacy-"))
        self.assertIn("Executor: legacy", result["diagnostics"])

    def test_unsupported_oem_fails_before_ocr_runs(self):
        session = self._session(oem_support={"0": False, "1": True, "2": False, "3": True})

        result = tejocr_engine.perform_ocr(
            None,
            None,
            "file",
            "ignored.png",
            {
                "preset": constants.OCR_PRESET_CUSTOM,
                "lang": "eng",
                "oem": "0",
            },
            session=session,
        )

        self.assertFalse(result["success"])
        self.assertIn("Selected OEM 0 is not supported", result["message"])

    def test_is_tesseract_ready_accepts_cli_runtime_without_pytesseract(self):
        session = self._session()

        with patch.object(tejocr_engine, "create_ocr_session", return_value=session), \
             patch.object(tejocr_engine, "_has_module", return_value=False):
            is_ready, message = tejocr_engine.is_tesseract_ready(show_gui_errors=False)

        self.assertTrue(is_ready)
        self.assertIn("direct CLI OCR active", message)

    def test_oem_probe_image_avoids_font_rendering(self):
        fake_image = types.SimpleNamespace(save=lambda *_args, **_kwargs: None)
        fake_draw = types.SimpleNamespace(
            rectangle=lambda *_args, **_kwargs: None,
            line=lambda *_args, **_kwargs: None,
            text=Mock(),
        )

        with patch.object(tejocr_engine, "PILLOW_AVAILABLE", True), \
             patch.object(tejocr_engine, "_get_temp_image_path", return_value="/tmp/oem_probe.png"), \
             patch.object(tejocr_engine.Image, "new", return_value=fake_image), \
             patch.object(tejocr_engine.ImageDraw, "Draw", return_value=fake_draw):
            probe_path = tejocr_engine._build_oem_probe_image()

        self.assertEqual(probe_path, "/tmp/oem_probe.png")
        fake_draw.text.assert_not_called()

    def test_runtime_oem_modes_annotate_unsupported_legacy_modes(self):
        session = self._session()

        with patch.object(
            tejocr_engine,
            "_extract_mode_descriptions",
            return_value={
                "0": "tesseract_only Legacy engine only.",
                "1": "lstm_only Neural nets LSTM engine only.",
                "2": "tesseract_lstm_combined Legacy + LSTM engines.",
                "3": "default Default, based on what is available.",
            },
        ), patch.object(
            tejocr_engine,
            "get_supported_oem_modes",
            return_value={"0": False, "1": True, "2": False, "3": True},
        ):
            modes = tejocr_engine.get_runtime_oem_modes(session=session)

        self.assertIn("unsupported by current traineddata/runtime", modes["0"])
        self.assertIn("unsupported by current traineddata/runtime", modes["2"])
        self.assertNotIn("tesseract_only", modes["0"])
        self.assertNotIn("lstm_only", modes["1"])
        self.assertNotIn("tesseract_lstm_combined", modes["2"])
        self.assertNotIn("default Default", modes["3"])


if __name__ == "__main__":
    unittest.main()
