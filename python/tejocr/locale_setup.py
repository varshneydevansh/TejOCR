# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Internationalization setup for TejOCR."""

import gettext
import locale
import os

from tejocr import constants


class NullTranslator:
    def gettext(self, message):
        return message

    def ngettext(self, singular, plural, n):
        return singular if n == 1 else plural


class TranslationProxy:
    """Stable proxy so modules that cached `_` still see language changes."""

    def gettext(self, message):
        return _active_translator.gettext(message)

    def ngettext(self, singular, plural, n):
        return _active_translator.ngettext(singular, plural, n)


_proxy = TranslationProxy()
_active_translator = NullTranslator()
_configured_language = constants.DEFAULT_UI_LANGUAGE
_effective_language = "en"
_locale_dir = None

LANGUAGE_DISPLAY_NAMES = {
    "auto": "Auto (LibreOffice/system)",
    "ar": "العربية",
    "bn": "বাংলা",
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fa": "فارسی",
    "fr": "Français",
    "hi": "हिन्दी",
    "id": "Bahasa Indonesia",
    "it": "Italiano",
    # Use Latin fallback here because LibreOffice dialog fonts on some systems
    # render Japanese UI-language names as tofu boxes.
    "ja": "Japanese (ja)",
    "ko": "한국어",
    "mr": "मराठी",
    "nl": "Nederlands",
    "pa": "ਪੰਜਾਬੀ",
    "pl": "Polski",
    "pt_BR": "Português (Brasil)",
    "ru": "Русский",
    "sw": "Kiswahili",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "tr": "Türkçe",
    "uk": "Українська",
    "ur": "اردو",
    "vi": "Tiếng Việt",
    "zh_CN": "简体中文",
}


def _default_locale_dir():
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "l10n")
    )


def _normalise_language_code(language_code):
    code = str(language_code or "").strip()
    if not code:
        return ""
    code = code.replace("-", "_")
    parts = [part for part in code.split("_") if part]
    if not parts:
        return ""
    language = parts[0].lower()
    if len(parts) == 1:
        return language
    return language + "_" + parts[1].upper()


def _candidate_language_codes(language_code):
    normalised = _normalise_language_code(language_code)
    if not normalised:
        return []
    candidates = [normalised]
    if "_" in normalised:
        parent = normalised.split("_", 1)[0]
        if parent not in candidates:
            candidates.append(parent)
    return candidates


def _catalog_path(locale_dir, language_code):
    return os.path.join(locale_dir, language_code, "LC_MESSAGES", constants.TEXT_DOMAIN + ".mo")


def _po_path(locale_dir, language_code):
    return os.path.join(locale_dir, language_code, "LC_MESSAGES", constants.TEXT_DOMAIN + ".po")


def _po_header_fields(content):
    fields = {}
    in_header = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line == 'msgid ""':
            in_header = True
            continue
        if not in_header:
            continue
        if line == 'msgstr ""':
            continue
        if line.startswith('"'):
            text = line[1:-1]
            if ":" in text:
                key, value = text.split(":", 1)
                fields[key.strip()] = value.strip().rstrip("\\n")
            continue
        if line:
            break
    return fields


def _po_catalog_has_reviewed_translations(po_path):
    if not os.path.exists(po_path):
        return False
    try:
        with open(po_path, "r", encoding="utf-8", errors="replace") as po_file:
            content = po_file.read()
    except Exception:
        return False

    if "nplurals=INTEGER" in content or "plural=EXPRESSION" in content:
        return False
    if _po_header_fields(content).get("X-TejOCR-Status", "").lower() != "reviewed":
        return False

    in_header = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line == 'msgid ""':
            in_header = True
            continue
        if in_header and line.startswith('"'):
            continue
        if in_header and line:
            in_header = False
        if not in_header and (line.startswith('msgstr "') or line.startswith('msgstr[0] "')):
            value = line.split('"', 1)[1].rsplit('"', 1)[0]
            if value:
                return True
    return False


def get_available_ui_languages(locale_dir=None):
    """Return languages with usable, reviewed catalogs."""
    locale_dir = locale_dir or _default_locale_dir()
    available = {"en": LANGUAGE_DISPLAY_NAMES["en"]}
    if not os.path.isdir(locale_dir):
        return available

    for entry in sorted(os.listdir(locale_dir)):
        code = _normalise_language_code(entry)
        if not code or code == "en":
            continue
        mo_path = _catalog_path(locale_dir, entry)
        if not os.path.exists(mo_path):
            continue
        if not _po_catalog_has_reviewed_translations(_po_path(locale_dir, entry)):
            continue
        try:
            gettext.translation(constants.TEXT_DOMAIN, localedir=locale_dir, languages=[entry])
        except Exception:
            continue
        available[code] = LANGUAGE_DISPLAY_NAMES.get(code, code)
    return available


def _detect_libreoffice_language(ctx=None):
    if ctx is None:
        return ""

    try:
        import uno

        service_manager = getattr(ctx, "ServiceManager", None)
        if service_manager is None:
            return ""
        provider = service_manager.createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider",
            ctx,
        )
        node_prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        node_prop.Name = "nodepath"
        node_prop.Value = "/org.openoffice.Setup/L10N"
        access = provider.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess",
            (node_prop,),
        )
        for name in ("ooLocale", "Locale"):
            try:
                value = access.getByName(name)
            except Exception:
                value = getattr(access, name, "")
            if value:
                return str(value)
    except Exception:
        return ""
    return ""


def _detect_system_language():
    candidates = []
    for env_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(value.split(":", 1)[0])
    try:
        loc = locale.getlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    for candidate in candidates:
        normalised = _normalise_language_code(candidate.split(".", 1)[0])
        if normalised:
            return normalised
    return "en"


def resolve_language(language_code=None, ctx=None, locale_dir=None):
    locale_dir = locale_dir or _default_locale_dir()
    requested = _normalise_language_code(language_code or constants.DEFAULT_UI_LANGUAGE)
    if requested in ("", "auto"):
        detected = _detect_libreoffice_language(ctx) or _detect_system_language()
        candidates = _candidate_language_codes(detected)
    else:
        candidates = _candidate_language_codes(requested)

    available = get_available_ui_languages(locale_dir)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return "en"


def configure(language_code=None, ctx=None, locale_dir=None):
    """Configure the active translation catalog and return the proxy translator."""
    global _active_translator, _configured_language, _effective_language, _locale_dir

    _locale_dir = locale_dir or _default_locale_dir()
    configured = _normalise_language_code(language_code or constants.DEFAULT_UI_LANGUAGE) or constants.DEFAULT_UI_LANGUAGE
    effective = resolve_language(configured, ctx=ctx, locale_dir=_locale_dir)

    if effective == "en":
        translator = NullTranslator()
    else:
        try:
            translator = gettext.translation(
                constants.TEXT_DOMAIN,
                localedir=_locale_dir,
                languages=[effective],
                fallback=False,
            )
        except Exception:
            translator = NullTranslator()
            effective = "en"

    _configured_language = configured
    _effective_language = effective
    _active_translator = translator
    return _proxy


def get_translator(locale_dir=None, language_code=None, ctx=None):
    if locale_dir is not None or language_code is not None or ctx is not None:
        configure(language_code or _configured_language, ctx=ctx, locale_dir=locale_dir)
    return _proxy


def get_translation_function():
    return _proxy.gettext


def get_configured_language():
    return _configured_language


def get_effective_language():
    return _effective_language


_ = get_translator().gettext


if __name__ == "__main__":
    t = get_translator()
    print(t.gettext("Hello"))
