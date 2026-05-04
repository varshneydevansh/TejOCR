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

from tejocr import locale_setup


LOCALE_DIR = os.path.join(PROJECT_ROOT, "l10n")


class TestLocaleSetup(unittest.TestCase):
    def tearDown(self):
        locale_setup.configure("en", locale_dir=LOCALE_DIR)

    def test_available_ui_languages_exposes_completed_catalogs(self):
        languages = locale_setup.get_available_ui_languages(LOCALE_DIR)

        self.assertEqual(languages["en"], "English")
        self.assertEqual(languages["es"], "Español")
        for code in (
            "ar", "bn", "de", "fa", "fr", "hi", "id", "it", "ja", "ko",
            "mr", "nl", "pa", "pl", "pt_BR", "ru", "sw", "ta", "te",
            "tr", "uk", "ur", "vi", "zh_CN",
        ):
            self.assertIn(code, languages)

    def test_spanish_catalog_loads_from_merged_translation(self):
        translator = locale_setup.configure("es", locale_dir=LOCALE_DIR)

        self.assertEqual(translator.gettext("Copied to Clipboard"), "Se copió en el portapapeles")
        self.assertEqual(locale_setup.get_effective_language(), "es")

    def test_auto_locale_resolves_supported_parent_language(self):
        with unittest.mock.patch.object(locale_setup, "_detect_libreoffice_language", return_value="es-MX"):
            effective = locale_setup.resolve_language("auto", ctx=object(), locale_dir=LOCALE_DIR)

        self.assertEqual(effective, "es")

    def test_translation_function_is_dynamic_after_language_change(self):
        translate = locale_setup.get_translation_function()

        locale_setup.configure("es", locale_dir=LOCALE_DIR)
        self.assertEqual(translate("Copied to Clipboard"), "Se copió en el portapapeles")

        locale_setup.configure("en", locale_dir=LOCALE_DIR)
        self.assertEqual(translate("Copied to Clipboard"), "Copied to Clipboard")


if __name__ == "__main__":
    unittest.main()
