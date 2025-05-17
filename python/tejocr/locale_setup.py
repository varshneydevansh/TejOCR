# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Basic internationalization setup."""

import gettext
import os
from tejocr import constants

# Dummy translator class that just returns the original string
class NullTranslator:
    def gettext(self, message):
        return message
    
    def ngettext(self, singular, plural, n):
        if n == 1:
            return singular
        else:
            return plural

_translator_instance = None

def get_translator(locale_dir=None, language_code=None):
    """
    Initializes and returns a translator instance.
    For now, it returns a NullTranslator that doesn't actually translate,
    allowing the _() calls to work without .mo files.
    """
    global _translator_instance
    if _translator_instance is None:
        # In a full i18n setup, this would try to find .mo files
        # based on language_code and locale_dir.
        # For now, we always use the NullTranslator.
        # print(f"Locale setup: Using NullTranslator. Real translations not yet implemented.")
        _translator_instance = NullTranslator()
        
        # Example of how it might look with actual gettext:
        # try:
        #     if locale_dir is None:
        #         # Assuming l10n is in the parent directory of the 'python' package directory
        #         base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        #         locale_dir = os.path.join(base_path, 'l10n')

        #     if language_code is None:
        #         # Attempt to get language from LibreOffice settings or system locale
        #         # This is complex and needs UNO access, which might not be available at this point.
        #         # For simplicity, could fall back to a configured default or 'en'.
        #         language_code = 'en' # Or get from constants.DEFAULT_UI_LANG if defined

        #     if os.path.isdir(locale_dir):
        #         lang = gettext.translation(
        #             constants.EXTENSION_ID,  # Domain (usually extension ID or name)
        #             localedir=locale_dir,
        #             languages=[language_code],
        #             fallback=True  # Fallback to parent language (e.g., 'en' if 'en_US' not found)
        #         )
        #         lang.install() # Makes _ available globally if not assigning to a variable
        #         _translator_instance = lang
        #         # print(f"Locale setup: Loaded translations for '{language_code}' from '{locale_dir}'")
        #     else:
        #         # print(f"Locale setup: Locale directory '{locale_dir}' not found. Using NullTranslator.")
        #         _translator_instance = NullTranslator()
        # except FileNotFoundError:
        #     # print(f"Locale setup: No translations found for domain '{constants.EXTENSION_ID}' and language '{language_code}'. Using NullTranslator.")
        #     _translator_instance = NullTranslator()
        # except Exception as e:
        #     # print(f"Locale setup: Error initializing gettext: {e}. Using NullTranslator.")
        #     _translator_instance = NullTranslator()
            
    return _translator_instance

# Make a default _ function available for direct import if desired,
# though it's generally better for modules to call get_translator().gettext explicitly.
_ = get_translator().gettext

if __name__ == "__main__":
    # Test the dummy translator
    t = get_translator()
    print(t.gettext("Hello"))
    print(_("Test"))
    print(t.ngettext("One item", "Multiple items", 1))
    print(t.ngettext("One item", "Multiple items", 5)) 