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
    x_dispatch_provider = type("XDispatchProvider", (object,), {})
    x_dispatch = type("XDispatch", (object,), {})
    x_service_info = type("XServiceInfo", (object,), {})
    x_initialization = type("XInitialization", (object,), {})

    uno = sys.modules.get("uno", types.ModuleType("uno"))
    uno.Any = lambda *_args: _args[-1] if _args else None
    uno.getConstantByName = lambda _name: None
    uno.systemPathToFileUrl = lambda value: value
    uno.fileUrlToSystemPath = lambda value: value
    uno.createUnoStruct = lambda _name: types.SimpleNamespace()
    sys.modules["uno"] = uno

    unohelper = sys.modules.get("unohelper", types.ModuleType("unohelper"))
    unohelper.Base = uno_base
    unohelper.fileUrlToSystemPath = lambda value: value
    unohelper.ImplementationHelper = lambda: types.SimpleNamespace(addImplementation=lambda *_args, **_kwargs: None)
    sys.modules["unohelper"] = unohelper

    sys.modules.setdefault("com", types.ModuleType("com"))
    sys.modules.setdefault("com.sun", types.ModuleType("com.sun"))
    sys.modules.setdefault("com.sun.star", types.ModuleType("com.sun.star"))

    frame = sys.modules.get("com.sun.star.frame", types.ModuleType("com.sun.star.frame"))
    frame.XDispatchProvider = x_dispatch_provider
    frame.XDispatch = x_dispatch
    sys.modules["com.sun.star.frame"] = frame

    lang = sys.modules.get("com.sun.star.lang", types.ModuleType("com.sun.star.lang"))
    lang.XServiceInfo = x_service_info
    lang.XInitialization = x_initialization
    sys.modules["com.sun.star.lang"] = lang

    beans = sys.modules.get("com.sun.star.beans", types.ModuleType("com.sun.star.beans"))
    beans.PropertyValue = type("PropertyValue", (object,), {})
    sys.modules["com.sun.star.beans"] = beans


_install_uno_stubs()

from tejocr import tejocr_service


class TestTejocrServiceFormatting(unittest.TestCase):
    def test_filtertube_dispatch_url_is_supported(self):
        service = tejocr_service.TejOCRService(object())
        url = types.SimpleNamespace(Complete=tejocr_service.DISPATCH_URL_FILTERTUBE)

        self.assertIs(service.queryDispatch(url, "_self", 0), service)

    def test_service_configures_saved_ui_language_on_init(self):
        ctx = object()
        with patch.object(tejocr_service.uno_utils, "get_setting", return_value="es") as get_setting, \
             patch.object(tejocr_service.locale_setup, "configure", wraps=tejocr_service.locale_setup.configure) as configure:
            tejocr_service.TejOCRService(ctx)

        get_setting.assert_any_call(
            tejocr_service.constants.CFG_KEY_UI_LANGUAGE,
            tejocr_service.constants.DEFAULT_UI_LANGUAGE,
            ctx,
        )
        configure.assert_any_call("es", ctx=ctx)

    def test_merge_pdf_runtime_hint_keeps_available_renderer_clean(self):
        merged = tejocr_service._merge_pdf_runtime_hint(
            {"available": True, "engine": "pdftoppm", "hints": []},
            "/path/python3 -m pip install pdf2image",
        )

        self.assertEqual(merged["hints"], [])

    def test_merge_pdf_runtime_hint_adds_runtime_command_only_when_unavailable(self):
        merged = tejocr_service._merge_pdf_runtime_hint(
            {"available": False, "engine": None, "hints": ["brew install poppler"]},
            "/path/python3 -m pip install pdf2image",
        )

        self.assertIn("brew install poppler", merged["hints"])
        self.assertIn("Install PDF conversion runtime in this Python:", "\n".join(merged["hints"]))

    def test_failed_reason_for_dialog_compacts_install_hints(self):
        formatted = tejocr_service._format_failed_reason_for_dialog(
            "PDF rendering failed. Install one of:\n - brew install poppler\n"
            " - Install PDF conversion runtime in this Python: /Applications/.../python3 -m pip install pdf2image"
        )

        self.assertIn("PDF rendering failed.", formatted)
        self.assertIn("Open Setup & Diagnostics for install commands.", formatted)
        self.assertNotIn("brew install poppler", formatted)

    def test_processing_details_use_stacked_blocks(self):
        block = tejocr_service._build_processing_details_for_dialog(
            {
                "improve_image": False,
                "grayscale": False,
                "binarize": False,
                "invert": False,
                "scale": 1.0,
                "psm": "5",
                "oem": "3",
                "show_preview": False,
            }
        )

        self.assertIn("Processing:\n• Improve image: off\n• Grayscale: off\n• Binarize: off\n• Invert: off", block)
        self.assertIn("\nRecognition:\n• Scale: 1.0x\n• PSM: 5\n• OEM: 3\n• Preview: off", block)

    def test_ocr_complete_block_can_skip_line_cap_for_scrollable_sources(self):
        block = tejocr_service._format_ocr_complete_block(
            "Sources (9 total):\n• one\n• two\n• three\n• four\n• five\n• six\n• seven\n• eight\n• nine\n\nFailed sources:\n• ten",
            "No source details available.",
            max_lines=None,
        )

        self.assertIn("Failed sources:", block)
        self.assertIn("• ten", block)
        self.assertNotIn("\n...", block)

    def test_runtime_diagnostics_use_summary_and_multiline_requested_effective(self):
        block = tejocr_service._build_runtime_diagnostics_for_dialog(
            "Executor: modern | Requested: PSM 5, OEM 3, preset custom | "
            "Effective: PSM 5, OEM 3, preset custom, lang eng+enm+hin | Attempts: 1 | PDF DPI: 200"
        )

        self.assertIn("• Executor: modern", block)
        self.assertIn("• Attempts: 1", block)
        self.assertIn("• PDF DPI: 200", block)
        self.assertIn("\n\nRequested:\n• PSM: 5\n• OEM: 3\n• Preset: custom", block)
        self.assertIn(
            "\n\nEffective:\n• PSM: 5\n• OEM: 3\n• Preset: custom\n• Language:\n  [eng]  +  [enm]  +  [hin]",
            block,
        )


if __name__ == "__main__":
    unittest.main()
