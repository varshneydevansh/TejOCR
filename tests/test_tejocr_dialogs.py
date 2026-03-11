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


class _FakeModel:
    def __init__(self):
        self.StringItemList = ()
        self.SelectedItems = ()


class _FakeControl:
    def __init__(self, text="", state=0, selected_positions=None):
        self._text = text
        self._state = state
        self._selected_positions = tuple(selected_positions or ())
        self._model = _FakeModel()

    def getText(self):
        return self._text

    def setText(self, value):
        self._text = value

    def getState(self):
        return self._state

    def setState(self, value):
        self._state = value

    def getModel(self):
        return self._model

    def getSelectedItemsPos(self):
        return self._selected_positions

    def getSelectedItemPos(self):
        if len(self._selected_positions) == 1:
            return self._selected_positions[0]
        return self._selected_positions

    def selectItemPos(self, pos, _select):
        self._selected_positions = (pos,)


class _FakeDialog:
    def __init__(self, controls):
        self._controls = controls

    def getControl(self, name):
        return self._controls.get(name)


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

    def test_selected_languages_label_uses_visual_language_tags(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)
        label = _FakeControl()
        handler.get_control = lambda name: label if name == "SelectedLangsLabel" else None
        handler._selected_codes = {"eng", "enm", "hin"}

        handler._update_selected_langs_label()

        self.assertEqual(label.getText(), "Selected: [eng]  +  [enm]  +  [hin]")

    def test_ocr_complete_dialog_splits_profile_blocks(self):
        main, processing, recognition = tejocr_dialogs.TejOCRCompleteDialogHandler._split_profile_blocks(
            "Output: Create a new text box\nLanguage:\n[eng]  +  [enm]  +  [hin]\nPreset: Custom\n\n"
            "Processing:\n• Improve image: off\n• Grayscale: off\n• Binarize: off\n• Invert: off\n"
            "Recognition:\n• Scale: 1.0x\n• PSM: 3\n• OEM: 3\n• Preview: off"
        )

        self.assertIn("Output: Create a new text box", main)
        self.assertEqual(
            processing,
            "Processing:\n• Improve image: off\n• Grayscale: off\n• Binarize: off\n• Invert: off",
        )
        self.assertEqual(
            recognition,
            "Recognition:\n• Scale: 1.0x\n• PSM: 3\n• OEM: 3\n• Preview: off",
        )

    def test_ocr_complete_dialog_splits_source_blocks(self):
        summary, details = tejocr_dialogs.TejOCRCompleteDialogHandler._split_source_blocks(
            "Sources (6 total):\n• aadhaar.jpg (1826 chars)\n• Corvin...pdf (2117 chars)"
        )

        self.assertEqual(summary, "Sources (6 total):")
        self.assertEqual(details, "• aadhaar.jpg (1826 chars)\n• Corvin...pdf (2117 chars)")

    def test_ocr_complete_dialog_normalizes_source_items_for_listbox(self):
        items = tejocr_dialogs.TejOCRCompleteDialogHandler._normalize_list_items(
            "• aadhaar.jpg (1826 chars)\n\n• {long_name}".format(long_name="x" * 140)
        )

        self.assertEqual(items[0], "• aadhaar.jpg (1826 chars)")
        self.assertEqual(len(items), 2)
        self.assertTrue(items[1].endswith("..."))

    def test_ocr_complete_dialog_splits_runtime_blocks(self):
        summary, requested, effective = tejocr_dialogs.TejOCRCompleteDialogHandler._split_runtime_blocks(
            "• Executor: modern\n• Attempts: 1\n• PDF DPI: 200\n\n"
            "Requested:\n• PSM: 3\n• OEM: 3\n• Preset: custom\n\n"
            "Effective:\n• PSM: 3\n• OEM: 3\n• Preset: custom\n• Language:\n  [eng]  +  [enm]  +  [hin]"
        )

        self.assertEqual(summary, "• Executor: modern\n• Attempts: 1\n• PDF DPI: 200")
        self.assertEqual(requested, "Requested:\n• PSM: 3\n• OEM: 3\n• Preset: custom")
        self.assertEqual(
            effective,
            "Effective:\n• PSM: 3\n• OEM: 3\n• Preset: custom\n• Language:\n  [eng]  +  [enm]  +  [hin]",
        )

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

    def test_runtime_psm_map_keeps_mode_2_readable_without_duplicate_not_implemented(self):
        help_output = "2|auto_only Automatic page segmentation, but no OSD, or OCR. (not implemented)\n"
        completed = types.SimpleNamespace(stdout=help_output, stderr="")

        with patch.object(tejocr_dialogs, "_resolve_tesseract_path", return_value="/usr/bin/tesseract"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=completed):
            runtime_map = tejocr_dialogs._get_runtime_psm_map()

        self.assertIn("Diagnostic mode", runtime_map["2"])
        self.assertEqual(runtime_map["2"].lower().count("not implemented"), 1)
        self.assertNotIn("auto_only", runtime_map["2"])

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

    def test_build_pip_command_uses_powershell_safe_windows_invocation(self):
        with patch.object(tejocr_dialogs.os, "name", "nt"):
            command = tejocr_dialogs._build_pip_command(r"C:\Program Files\LibreOffice\program\python.exe")

        self.assertEqual(
            command,
            '& "C:\\Program Files\\LibreOffice\\program\\python.exe" -m pip install',
        )

    def test_windows_pip_bootstrap_commands_use_libreoffice_python_dir(self):
        with patch("platform.system", return_value="Windows"):
            commands = tejocr_dialogs._pip_bootstrap_commands_for_platform(
                r"C:\Program Files\LibreOffice\program\python.exe"
            )

        self.assertEqual(commands[0], 'cd "C:\\Program Files\\LibreOffice\\program"')
        self.assertIn("get-pip.py", commands[1])
        self.assertIn(".\\python.exe -", commands[1])

    def test_build_setup_script_payload_uses_powershell_format_on_windows(self):
        with patch("platform.system", return_value="Windows"):
            payload, filename = tejocr_dialogs._build_setup_script_payload(
                ['choco install tesseract', '& "C:\\LibreOffice\\program\\python.exe" -m pip install pillow']
            )

        self.assertEqual(filename, "tejocr-setup.ps1")
        self.assertIn("$ErrorActionPreference = 'Stop'", payload)
        self.assertIn('choco install tesseract', payload)

    def test_copy_text_to_clipboard_preserves_multiline_snapshot_payload(self):
        handler = tejocr_dialogs.TejOCRSetupDialogHandler(ctx=None)

        with patch.object(handler, "_copy_lines_to_clipboard", return_value=True) as copier:
            copied = handler._copy_text_to_clipboard("Line 1\nLine 2")

        self.assertTrue(copied)
        copier.assert_called_once_with(["Line 1\nLine 2"], "Nothing available to copy.", normalize_commands=False)

    def test_build_support_snapshot_includes_runtime_details_and_commands(self):
        handler = tejocr_dialogs.TejOCRSetupDialogHandler(ctx=None)

        snapshot = handler._build_support_snapshot({
            "summary": "Image OCR ready; PDF OCR still needs runtime support.",
            "lo_python_path_display": r"C:\Program Files\LibreOffice\program\python.exe",
            "pip_ok": True,
            "pip_version": "25.0",
            "tesseract_ok": True,
            "tesseract_version": "v5.5.2",
            "pillow_ok": False,
            "pdf2image_ok": False,
            "pdf_renderer_status": "PDF Renderer: Not found",
            "optional_compat_label": "⚠ Compatibility extras (optional): missing numpy",
            "setup_commands": ['choco install tesseract', '& "C:\\Program Files\\LibreOffice\\program\\python.exe" -m pip install pillow'],
            "next_steps": "Open Setup & Diagnostics for install commands.",
        })

        self.assertIn("TejOCR Setup Snapshot", snapshot)
        self.assertIn(r"LibreOffice Python: C:\Program Files\LibreOffice\program\python.exe", snapshot)
        self.assertIn("Tesseract: available (v5.5.2)", snapshot)
        self.assertIn("Pillow: missing", snapshot)
        self.assertIn("Recommended commands:", snapshot)
        self.assertIn("Guidance:", snapshot)

    def test_copy_lines_to_clipboard_uses_absolute_pbcopy_fallback_on_macos(self):
        handler = tejocr_dialogs.TejOCRSetupDialogHandler(ctx=None)

        with patch.object(tejocr_dialogs.uno_utils, "create_instance", return_value=None), \
             patch("shutil.which", return_value=None), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=types.SimpleNamespace(returncode=0, stderr=b"")), \
             patch.object(sys, "platform", "darwin"):
            copied = handler._copy_lines_to_clipboard(["echo hello"], "missing", normalize_commands=False)

        self.assertTrue(copied)

    def test_check_dependencies_treats_numpy_and_pytesseract_as_optional(self):
        def _package_side_effect(module_name, distribution_name=None):
            mapping = {
                ("PIL", "Pillow"): (False, ""),
                ("pdf2image", "pdf2image"): (False, ""),
                ("pytesseract", "pytesseract"): (False, ""),
                ("numpy", "numpy"): (False, ""),
                ("pip", "pip"): (True, "25.0"),
            }
            return mapping.get((module_name, distribution_name), (False, ""))

        with patch.object(tejocr_dialogs, "_get_lo_python_path", return_value=r"C:\Program Files\LibreOffice\program\python.exe"), \
             patch.object(tejocr_dialogs, "_package_status", side_effect=_package_side_effect), \
             patch.object(tejocr_dialogs, "_refresh_dependency_import_state"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=types.SimpleNamespace(returncode=0, stdout="tesseract 5.5.2\n", stderr="")), \
             patch.object(tejocr_pdf, "get_pdf_renderer_status", return_value={"available": False, "engine": None, "hints": ["choco install poppler"], "error": ""}), \
             patch("platform.system", return_value="Windows"):
            status = tejocr_dialogs._check_dependencies()

        self.assertTrue(status["tesseract_ok"])
        self.assertTrue(status["pip_ok"])
        self.assertEqual(status["summary"], "Image OCR ready; PDF OCR still needs runtime support.")
        self.assertEqual(status["python_missing_packages"], ["pillow"])
        self.assertIn("numpy", status["optional_missing_packages"])
        self.assertIn("pytesseract", status["optional_missing_packages"])
        self.assertIn("pdf2image", status["optional_missing_packages"])
        self.assertIn('& "C:\\Program Files\\LibreOffice\\program\\python.exe" -m pip install pillow', status["installation_guide"])
        self.assertIn("Compatibility extras only if needed", status["installation_guide"])

    def test_tesseract_language_map_uses_cli_output(self):
        list_langs = "List of available languages in \"/opt/homebrew/share/tessdata/\" (3):\neng\nhin\nscript/Latin\n"
        completed = types.SimpleNamespace(stdout=list_langs, stderr="")

        with patch.object(tejocr_dialogs, "_resolve_tesseract_path", return_value="/usr/bin/tesseract"), \
             patch.object(tejocr_dialogs.subprocess, "run", return_value=completed):
            languages = tejocr_dialogs._get_tesseract_language_map()

        self.assertEqual(languages["eng"], "English")
        self.assertEqual(languages["hin"], "Hindi")
        self.assertEqual(languages["script/Latin"], "script/Latin")

    def test_settings_handler_save_uses_defined_preview_control_and_persists_changed_fields(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)
        handler.current_psm = "6"
        handler.current_oem = "1"
        handler._selected_codes = {"eng", "hin"}
        handler.initial_settings = {
            tejocr_dialogs.constants.CFG_KEY_TESSERACT_PATH: "",
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_LANG: "eng",
            tejocr_dialogs.constants.CFG_KEY_LAST_SELECTED_LANG: "eng",
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_OUTPUT_MODE: tejocr_dialogs.constants.OUTPUT_MODE_CURSOR,
            tejocr_dialogs.constants.CFG_KEY_LAST_OUTPUT_MODE: tejocr_dialogs.constants.OUTPUT_MODE_CURSOR,
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_GRAYSCALE: False,
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_BINARIZE: False,
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_PRESET: tejocr_dialogs.constants.OCR_PRESET_BALANCED,
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_PSM: "3",
            tejocr_dialogs.constants.CFG_KEY_DEFAULT_OEM: "3",
            tejocr_dialogs.constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT: 0,
            tejocr_dialogs.constants.CFG_KEY_MERGE_BATCH_RESULTS: 0,
        }

        controls = {
            "TesseractPathTextField": _FakeControl(text=""),
            "DefaultGrayscaleCheckbox": _FakeControl(state=1),
            "DefaultBinarizeCheckbox": _FakeControl(state=0),
            "DefaultPresetDropdown": _FakeControl(selected_positions=(2,)),
            "DefaultPreviewCheckbox": _FakeControl(state=1),
            "DefaultMergeBatchCheckbox": _FakeControl(state=1),
            "SettingsStatusLabel": _FakeControl(text="Ready"),
        }
        handler.get_control = controls.get
        handler._get_selected_output_mode = lambda: tejocr_dialogs.constants.OUTPUT_MODE_TEXTBOX

        saved = {}

        def _capture_setting(key, value, _ctx):
            saved[key] = value
            return True

        with patch.object(tejocr_dialogs.uno_utils, "set_setting", side_effect=_capture_setting):
            result = handler._handle_ok_action()

        self.assertTrue(result)
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_LANG], "eng+hin")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_LAST_SELECTED_LANG], "eng+hin")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_OUTPUT_MODE], tejocr_dialogs.constants.OUTPUT_MODE_TEXTBOX)
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_PRESET], tejocr_dialogs.constants.OCR_PRESET_ACCURATE)
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_GRAYSCALE], "true")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_PSM], "6")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_DEFAULT_OEM], "1")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT], "true")
        self.assertEqual(saved[tejocr_dialogs.constants.CFG_KEY_MERGE_BATCH_RESULTS], "true")
        self.assertEqual(controls["SettingsStatusLabel"].getText(), "Settings saved successfully")

    def test_advanced_params_dropdown_uses_clean_runtime_labels(self):
        handler = tejocr_dialogs.TejOCRAdvancedParamsDialogHandler(ctx=None, current_psm="3", current_oem="3")
        psm_control = _FakeControl()
        handler.dialog = _FakeDialog({"PSMDropdown": psm_control})

        handler._populate_dropdown(
            "PSMDropdown",
            {"3": "3: Fully automatic page segmentation, but no OSD. (Default)"},
            "3",
        )

        self.assertEqual(
            psm_control.getModel().StringItemList,
            ("3: Fully automatic page segmentation, but no OSD. (Default)",),
        )

    def test_settings_modern_styling_applies_resting_colors_to_setup_and_help(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)
        controls = {
            "FilterTubeTagline2": _FakeControl(),
            "FilterTubeButton": _FakeControl(),
            "SaveButton": _FakeControl(),
            "SetupButton": _FakeControl(),
            "HelpButtonSettings": _FakeControl(),
            "AdvancedParamsButton": _FakeControl(),
            "MessageButtonSettings": _FakeControl(),
        }
        handler.dialog = _FakeDialog(controls)
        handler.get_control = controls.get

        handler._apply_modern_styling()

        self.assertEqual(controls["SetupButton"].getModel().BackgroundColor, handler.COLOR_BTN_PRIMARY)
        self.assertEqual(controls["SetupButton"].getModel().TextColor, handler.COLOR_TEXT_ON_DARK)
        self.assertEqual(controls["HelpButtonSettings"].getModel().BackgroundColor, handler.COLOR_BTN_WARNING)
        self.assertEqual(controls["HelpButtonSettings"].getModel().TextColor, 0xFFFFFF)

    def test_settings_dependency_summary_labels_optional_python_extras_clearly(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)
        controls = {
            "TesseractStatusLabel": _FakeControl(),
            "PdfStatusLabel": _FakeControl(),
            "PythonPackagesStatusLabel": _FakeControl(),
            "SettingsStatusLabel": _FakeControl(),
        }
        handler.get_control = controls.get

        dependency_status = {
            "tesseract_ok": True,
            "numpy_ok": False,
            "pytesseract_ok": False,
            "pillow_ok": False,
            "pdf_renderer_available": True,
            "summary": "Image + PDF OCR ready.",
        }

        with patch.object(tejocr_dialogs, "_check_dependencies", return_value=dependency_status):
            handler._check_and_display_dependencies()

        self.assertEqual(controls["TesseractStatusLabel"].getText(), "Tesseract: Available")
        self.assertEqual(controls["PdfStatusLabel"].getText(), "PDF: ok")
        self.assertEqual(controls["PythonPackagesStatusLabel"].getText(), "Extras: 0/3 (optional)")
        self.assertEqual(
            controls["PdfStatusLabel"].getModel().TextColor,
            handler.COLOR_GREEN,
        )
        self.assertEqual(
            controls["PythonPackagesStatusLabel"].getModel().TextColor,
            handler.COLOR_AMBER,
        )
        self.assertEqual(controls["SettingsStatusLabel"].getText(), "Image + PDF OCR ready.")

    def test_show_setup_reuses_setup_dependency_status_for_settings_labels(self):
        handler = tejocr_dialogs.SettingsDialogHandler(ctx=None)
        controls = {
            "TesseractStatusLabel": _FakeControl(),
            "PdfStatusLabel": _FakeControl(),
            "PythonPackagesStatusLabel": _FakeControl(),
            "SettingsStatusLabel": _FakeControl(),
        }
        handler.get_control = controls.get

        fake_status = {
            "tesseract_ok": True,
            "numpy_ok": False,
            "pytesseract_ok": False,
            "pillow_ok": False,
            "pdf_renderer_available": True,
            "summary": "Image + PDF OCR ready.",
        }

        class _FakeSetupHandler:
            def __init__(self, *_args, **_kwargs):
                self.dependency_status = fake_status

            def show(self):
                return None

        with patch.object(tejocr_dialogs, "TejOCRSetupDialogHandler", _FakeSetupHandler):
            handler._show_setup()

        self.assertEqual(controls["TesseractStatusLabel"].getText(), "Tesseract: Available")
        self.assertEqual(controls["PdfStatusLabel"].getText(), "PDF: ok")
        self.assertEqual(controls["PythonPackagesStatusLabel"].getText(), "Extras: 0/3 (optional)")
        self.assertEqual(controls["SettingsStatusLabel"].getText(), "Image + PDF OCR ready.")


if __name__ == "__main__":
    unittest.main()
