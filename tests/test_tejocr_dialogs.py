# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import types
import unittest
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)


def _install_uno_stubs():
    uno_base = type("UnoBase", (object,), {})
    x_action_listener = type("XActionListener", (object,), {})
    x_item_listener = type("XItemListener", (object,), {})
    x_job_executor = type("XJobExecutor", (object,), {})

    uno = sys.modules.get("uno", types.ModuleType("uno"))
    uno.Any = lambda *_args: _args[-1] if _args else None
    uno.getConstantByName = lambda _name: None
    uno.systemPathToFileUrl = lambda value: value
    uno.fileUrlToSystemPath = lambda value: value
    uno.createUnoStruct = lambda _name: types.SimpleNamespace()
    uno.XActionListener = x_action_listener
    uno.XItemListener = x_item_listener
    sys.modules["uno"] = uno

    unohelper = sys.modules.get("unohelper", types.ModuleType("unohelper"))
    unohelper.Base = uno_base
    sys.modules["unohelper"] = unohelper

    sys.modules.setdefault("com", types.ModuleType("com"))
    sys.modules.setdefault("com.sun", types.ModuleType("com.sun"))
    sys.modules.setdefault("com.sun.star", types.ModuleType("com.sun.star"))

    task = sys.modules.get("com.sun.star.task", types.ModuleType("com.sun.star.task"))
    task.XJobExecutor = x_job_executor
    sys.modules["com.sun.star.task"] = task

    awt = sys.modules.get("com.sun.star.awt", types.ModuleType("com.sun.star.awt"))
    awt.XActionListener = x_action_listener
    awt.XItemListener = x_item_listener
    sys.modules["com.sun.star.awt"] = awt


_install_uno_stubs()

from tejocr import tejocr_dialogs, tejocr_pdf


class TestTejocrDialogs(unittest.TestCase):
    def test_resolve_tesseract_path_uses_single_argument_probe(self):
        with patch.object(tejocr_dialogs.uno_utils, "get_setting", return_value="/custom/tesseract"), \
             patch.object(tejocr_dialogs.uno_utils, "find_tesseract_executable", return_value="/resolved/tesseract") as finder:
            resolved = tejocr_dialogs._resolve_tesseract_path(ctx=object())

        self.assertEqual(resolved, "/resolved/tesseract")
        finder.assert_called_once_with("/custom/tesseract")

    def test_settings_handler_initializes_language_state_defaults(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)

        self.assertEqual(handler._selected_codes, {tejocr_dialogs.constants.DEFAULT_OCR_LANGUAGE})
        self.assertEqual(handler._all_lang_keys, [])
        self.assertEqual(handler._all_lang_map, {})
        self.assertEqual(handler._visible_lang_keys, [])

    def test_package_status_uses_metadata_without_importing_package(self):
        with patch.object(tejocr_dialogs.importlib_util, "find_spec", return_value=object()) as find_spec, \
             patch.object(tejocr_dialogs.importlib_metadata, "version", return_value="1.2.3") as version:
            available, detected_version = tejocr_dialogs._package_status("PIL", "Pillow")

        self.assertTrue(available)
        self.assertEqual(detected_version, "1.2.3")
        find_spec.assert_called_once_with("PIL")
        version.assert_called_once_with("Pillow")

    def test_refresh_dependency_state_does_not_unload_existing_modules(self):
        fake_pil = types.ModuleType("PIL")
        sys.modules["PIL"] = fake_pil
        self.addCleanup(lambda: sys.modules.pop("PIL", None))

        with patch.object(tejocr_dialogs.site, "getsitepackages", return_value=[]), \
             patch.object(tejocr_dialogs.site, "getusersitepackages", return_value=""):
            tejocr_dialogs._refresh_dependency_import_state()

        self.assertIs(sys.modules.get("PIL"), fake_pil)

    def test_runtime_psm_map_parses_cli_help_without_engine_import(self):
        help_output = "0|osd_only Orientation and script detection (OSD) only.\n3|auto Fully automatic page segmentation, but no OSD.\n"
        completed = types.SimpleNamespace(stdout=help_output, stderr="")

        with patch.object(tejocr_dialogs, "_resolve_tesseract_path", return_value="/usr/bin/tesseract"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=completed):
            runtime_map = tejocr_dialogs._get_runtime_psm_map()

        self.assertIn("Diagnostic mode", runtime_map["0"])
        self.assertIn("Fully automatic", runtime_map["3"])
        self.assertNotIn("osd_only", runtime_map["0"])
        self.assertNotIn("auto Fully", runtime_map["3"])

    def test_runtime_oem_map_strips_internal_mode_aliases(self):
        help_output = (
            "0|tesseract_only Legacy engine only.\n"
            "1|lstm_only Neural nets LSTM engine only.\n"
            "3|default Default, based on what is available.\n"
        )
        completed = types.SimpleNamespace(stdout=help_output, stderr="")

        with patch.object(tejocr_dialogs, "_resolve_tesseract_path", return_value="/usr/bin/tesseract"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=completed):
            runtime_map = tejocr_dialogs._get_runtime_oem_map()

        self.assertEqual(runtime_map["0"], "0: Legacy engine only.")
        self.assertEqual(runtime_map["1"], "1: Neural nets LSTM engine only.")
        self.assertEqual(runtime_map["3"], "3: Default, based on what is available.")

    def test_get_lo_python_path_delegates_to_safe_runtime_resolver(self):
        with patch.object(tejocr_pdf, "_resolve_python_executable", return_value="/safe/libreoffice/python3"):
            resolved = tejocr_dialogs._get_lo_python_path()

        self.assertEqual(resolved, "/safe/libreoffice/python3")

    def test_tesseract_language_map_uses_cli_output(self):
        list_langs = "List of available languages in \"/opt/homebrew/share/tessdata/\" (3):\neng\nhin\nscript/Latin\n"
        completed = types.SimpleNamespace(stdout=list_langs, stderr="")

        with patch.object(tejocr_dialogs, "_resolve_tesseract_path", return_value="/usr/bin/tesseract"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=completed):
            languages = tejocr_dialogs._get_tesseract_language_map()

        self.assertEqual(languages["eng"], "English")
        self.assertEqual(languages["hin"], "Hindi")
        self.assertEqual(languages["script/Latin"], "script/Latin")


if __name__ == "__main__":
    unittest.main()
