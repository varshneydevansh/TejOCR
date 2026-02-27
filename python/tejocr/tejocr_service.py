# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Main service implementation for the TejOCR extension."""

import sys
import os
import datetime
import platform

# --- Python Path Modification for OXT Structure: python/tejocr ---
# This ensures that the 'python' directory (which contains the 'tejocr' package)
# is on the sys.path, allowing 'from tejocr import ...' to work.
try:
    # Get the directory of the current script (e.g., .../OXT_ROOT/python/tejocr/)
    current_script_dir = os.path.dirname(os.path.realpath(__file__))
    # Get the parent directory (e.g., .../OXT_ROOT/python/)
    python_dir_in_oxt = os.path.dirname(current_script_dir)

    if python_dir_in_oxt not in sys.path:
        sys.path.insert(0, python_dir_in_oxt)
except Exception as e_sys_path:
    # Keep bootstrap import-path handling silent to avoid startup noise in normal usage.
    pass
# --- End of Python Path Modification ---

try:
    import uno
    import unohelper
    import os
    from com.sun.star.frame import XDispatchProvider, XDispatch
    from com.sun.star.lang import XServiceInfo, XInitialization
    from com.sun.star.beans import PropertyValue

    # Now that 'python/' (containing 'tejocr/') should be on sys.path,
    # we can import 'tejocr' as if it's a top-level package.
    from tejocr import uno_utils
    from tejocr import constants
    from tejocr import locale_setup
    
    # Set up internationalization function
    try:
        _ = locale_setup.get_translation_function()
    except:
        # Fallback if locale setup fails
        def _(text):
            return text

except ImportError as e_imp:
    import traceback
    # Set up fallback _ function
    def _(text):
        return text
    raise
except Exception as e_gen:
    import traceback
    # Set up fallback _ function
    def _(text):
        return text
    raise

# Initialize logger for this module
try:
    logger = uno_utils.get_logger("TejOCR.Service") # This now uses the imported uno_utils
except Exception as e_log:
    logger = None 

# Constants for dispatch URLs (centralize for easier management)
DISPATCH_URL_OCR_SELECTED = "uno:org.libreoffice.TejOCR.OCRSelectedImage"
DISPATCH_URL_OCR_FROM_FILE = "uno:org.libreoffice.TejOCR.OCRImageFromFile"
DISPATCH_URL_SETTINGS = "uno:org.libreoffice.TejOCR.Settings"
DISPATCH_URL_TOOLBAR_ACTION = "uno:org.libreoffice.TejOCR.ToolbarAction"

IMPLEMENTATION_NAME = "org.libreoffice.TejOCR.PythonService.TejOCRService"
SERVICE_NAME = "com.sun.star.frame.ProtocolHandler"

# Constants for the Tesseract missing/configuration prompt
TESSERACT_INSTALL_GUIDE_URL = "https://tesseract-ocr.github.io/tessdoc/Installation.html"


def _get_tesseract_setup_guide():
    """Return platform-aware quick troubleshooting steps."""
    name = (platform.system() or "").lower()
    package_cmd = f'"{sys.executable}" -m pip install -U numpy pytesseract pillow'
    if name == "darwin":
        return "Install Tesseract:\n  brew install tesseract\nInstall Python dependencies in LibreOffice Python:\n%s" % package_cmd
    if name == "windows":
        return "Install Tesseract:\n  1) Download and install from UB-Mannheim:\n     https://github.com/UB-Mannheim/tesseract/wiki\nInstall Python dependencies in LibreOffice Python:\n%s" % package_cmd
    return "Install Tesseract:\n  sudo apt install tesseract-ocr tesseract-ocr-eng\nInstall Python dependencies in LibreOffice Python:\n%s" % package_cmd


def _build_dependency_diagnostics(ctx=None):
    """Build a compact dependency diagnostics string for user-facing dialogs."""
    configured_path = ""
    detected_path = ""

    try:
        if ctx:
            configured_path = (
                uno_utils.get_setting(
                    constants.CFG_KEY_TESSERACT_PATH,
                    "",
                    ctx,
                )
                or ""
            ).strip()
    except Exception:
        configured_path = ""

    try:
        detected_path = uno_utils.find_tesseract_executable(configured_path) or ""
    except Exception:
        detected_path = ""

    return (
        _("LibreOffice Python: {python}\n").format(python=sys.executable)
        + _("Configured Tesseract path: {path}\n").format(
            path=configured_path or _("(not set)")
        )
        + _("Detected Tesseract path: {path}\n").format(
            path=detected_path or _("(not auto-detected)")
        )
        + _("PATH: {path}\n").format(
            path=(os.environ.get("PATH") or _("(not available)"))[:140]
        )
        + _("Working dir: {cwd}\n").format(
            cwd=(os.getcwd() if hasattr(os, "getcwd") else _("(unknown)"))
        )
    )


def _message_box_positive_button_pressed(result):
    """Return True when a confirm/accept button is clicked in a UNO message box."""
    if result is None:
        return False

    try:
        ok_result = uno.getConstantByName("com.sun.star.awt.MessageBoxResults.OK")
        if ok_result is not None and result == ok_result:
            return True
    except Exception:
        pass

    try:
        yes_result = uno.getConstantByName("com.sun.star.awt.MessageBoxResults.YES")
        if yes_result is not None and result == yes_result:
            return True
    except Exception:
        pass

    return result in (1,)


def _format_dependency_short_status(message):
    if not message:
        return _("Dependency check did not return details.")
    return message.replace("\n", " ")


def _normalize_language_request(language_input):
    """Normalize comma/plus-separated language inputs and drop empty entries."""
    if not language_input:
        return constants.DEFAULT_OCR_LANGUAGE
    normalized = str(language_input).replace(",", "+").strip()
    normalized = "+".join([part.strip().lower() for part in normalized.split("+") if part.strip()])
    return normalized or constants.DEFAULT_OCR_LANGUAGE


def _normalize_language_codes(language_input):
    """Split normalized language text into canonical tokens."""
    normalized = _normalize_language_request(language_input)
    return [part.strip() for part in normalized.split("+") if part.strip()]


def _validate_language_codes(language_input, available_languages):
    """Validate language tokens against available Tesseract languages."""
    normalized_codes = _normalize_language_codes(language_input)
    if not normalized_codes:
        return constants.DEFAULT_OCR_LANGUAGE, [], False

    normalized = "+".join(normalized_codes)
    if not available_languages:
        return normalized, [], False

    available_set = {
        str(language).strip().lower() for language in available_languages if str(language).strip()
    }
    if not available_set:
        return normalized, [], False

    valid_codes = [code for code in normalized_codes if code in available_set]
    invalid_codes = [code for code in normalized_codes if code not in available_set]

    if not valid_codes:
        valid_codes = [constants.DEFAULT_OCR_LANGUAGE]

    return "+".join(valid_codes), invalid_codes, True


def _build_language_validation_message(language_input, invalid_codes, validated):
    """Build user-facing language warning text."""
    if validated and invalid_codes:
        invalid_text = ", ".join(invalid_codes)
        return (
            _("Some language codes are not installed and were skipped: {invalid_codes}. Using: {used_codes}.")
            .format(invalid_codes=invalid_text, used_codes=_normalize_language_request(language_input))
        )
    if not validated and language_input:
        return _("Language availability could not be verified. Using: {used_codes}.").format(
            used_codes=_normalize_language_request(language_input)
        )
    return ""


def _coerce_preset_request(preset_name, fallback):
    if not preset_name:
        return fallback or constants.DEFAULT_OCR_PRESET
    normalized = str(preset_name).strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0].strip()
    if normalized in constants.OCR_PRESET_CHOICES:
        return normalized
    return fallback or constants.DEFAULT_OCR_PRESET


def _coerce_preset_profile(preset_name):
    preset_key = _coerce_preset_request(preset_name, constants.DEFAULT_OCR_PRESET)
    return preset_key, constants.OCR_QUALITY_PRESETS.get(preset_key)


def _resolve_output_mode_preference(ctx):
    """Resolve output mode using explicit default mode preference first."""
    default_output_mode = _coerce_output_mode(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
            constants.DEFAULT_OUTPUT_MODE,
            ctx,
        ),
        constants.DEFAULT_OUTPUT_MODE,
    )
    last_output_mode = _coerce_output_mode(
        uno_utils.get_setting(
            constants.CFG_KEY_LAST_OUTPUT_MODE,
            default_output_mode,
            ctx,
        ),
        default_output_mode,
    )

    # If a non-default output mode is configured as the default, it must always
    # be treated as the effective mode for this session, even if legacy
    # LastOutputMode still stores a cursor value.
    if default_output_mode != constants.DEFAULT_OUTPUT_MODE:
        if last_output_mode != default_output_mode:
            try:
                uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, default_output_mode, ctx)
                logger.debug(
                    "Synced LastOutputMode '{stale}' to configured default '{current}'".format(
                        stale=last_output_mode, current=default_output_mode
                    )
                )
            except Exception:
                logger.debug("Could not sync LastOutputMode preference; continuing with configured default output mode.")
        return default_output_mode

    return last_output_mode


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return int(value) != 0
        except Exception:
            return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on", "enabled", "enable")
    return False


def _coerce_float(value, default=1.0):
    try:
        parsed = float(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _coerce_scale(value, default=1.0):
    try:
        if value is None:
            return default
        parsed = float(value)
        return max(1.0, round(parsed, 2))
    except Exception:
        try:
            return float(default)
        except Exception:
            return 1.0


def _coerce_output_mode(value, fallback):
    """Normalize output mode keys coming from settings or UI."""
    if value is None:
        return fallback
    normalized = str(value).strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0].strip()
    normalized = normalized.replace(" ", "_")
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace("__", "_")
    normalized = normalized.strip("_")

    alias_map = {
        "atcursor": constants.OUTPUT_MODE_CURSOR,
        "at_cursor": constants.OUTPUT_MODE_CURSOR,
        "cursor": constants.OUTPUT_MODE_CURSOR,
        "insert": constants.OUTPUT_MODE_CURSOR,
        "insert_at_cursor": constants.OUTPUT_MODE_CURSOR,
        "text_box": constants.OUTPUT_MODE_TEXTBOX,
        "textbox": constants.OUTPUT_MODE_TEXTBOX,
        "new_textbox": constants.OUTPUT_MODE_TEXTBOX,
        "new_text_box": constants.OUTPUT_MODE_TEXTBOX,
        "clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "to_clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "replace_image": constants.OUTPUT_MODE_REPLACE,
        "replace": constants.OUTPUT_MODE_REPLACE,
    }
    if normalized in alias_map:
        return alias_map[normalized]

    if normalized == "new_text_box":
        normalized = "new_textbox"
    if normalized in (
        constants.OUTPUT_MODE_CURSOR,
        constants.OUTPUT_MODE_TEXTBOX,
        constants.OUTPUT_MODE_CLIPBOARD,
        constants.OUTPUT_MODE_REPLACE,
    ):
        return normalized
    return fallback


def _format_output_mode_for_summary(output_mode):
    """Return a human-readable output mode label for post-run messages."""
    return {
        constants.OUTPUT_MODE_CURSOR: "Insert at cursor",
        constants.OUTPUT_MODE_TEXTBOX: "Create a new text box",
        constants.OUTPUT_MODE_CLIPBOARD: "Copy to clipboard",
        constants.OUTPUT_MODE_REPLACE: "Replace selected image",
    }.get(_coerce_output_mode(output_mode, constants.OUTPUT_MODE_CURSOR), "Insert at cursor")


def _format_preset_for_summary(preset):
    """Return a human-readable quality preset name for status messages."""
    if not preset:
        preset = constants.DEFAULT_OCR_PRESET
    normalized_preset = str(preset).strip().lower()
    preset_profile = constants.OCR_QUALITY_PRESETS.get(normalized_preset, {})
    return preset_profile.get("label", normalized_preset.title())


def _build_preprocessing_summary(ocr_options):
    """Build a short preprocessing summary from OCR option flags."""
    def _bool_text(value):
        return "on" if bool(value) else "off"

    return " | ".join(
        [
            f"improve_image={_bool_text(ocr_options.get('improve_image', False))}",
            f"grayscale={_bool_text(ocr_options.get('grayscale', False))}",
            f"binarize={_bool_text(ocr_options.get('binarize', False))}",
            f"invert={_bool_text(ocr_options.get('invert', False))}",
            f"scale={ocr_options.get('scale', constants.DEFAULT_SCALE_FACTOR)}x",
            f"psm={ocr_options.get('psm', constants.DEFAULT_PSM_MODE)}",
            f"oem={ocr_options.get('oem', constants.DEFAULT_OEM_MODE)}",
            f"preset={_format_preset_for_summary(ocr_options.get('preset', constants.DEFAULT_OCR_PRESET))}",
            f"preview={'on' if _coerce_bool(ocr_options.get('show_preview', constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT)) else 'off'}",
        ]
    )


def _is_pdf_path(path):
    """Return True when the path points to a PDF file."""
    if not path:
        return False
    return str(path).lower().endswith(".pdf")


def _safe_enable_file_picker_multi_select(file_picker, logger):
    """Enable multi-file selection on FilePicker across UNO variants.

    Returns:
        tuple(bool, bool): (is_multi_enabled, is_multi_verified)
        - is_multi_enabled: whether we were able to call any setter/API to request multi-select.
        - is_multi_verified: whether state probe confirms the picker is in multi-select mode.
    """
    if not file_picker:
        return False, False

    if hasattr(uno, "Any"):
        true_bool = uno.Any("boolean", True)
        multi_short = uno.Any("short", 2)
        multi_short_fallback = uno.Any("short", 2)
        multi_short_alt = uno.Any("short", 1)
    else:
        true_bool = True
        multi_short = 2
        multi_short_fallback = 2
        multi_short_alt = 1

    try:
        picker_members = sorted([name for name in dir(file_picker) if "multi" in str(name).lower()])
        logger.debug(
            "set_file_picker_multi_select: file_picker multi-related members: {members}".format(
                members=", ".join(picker_members) if picker_members else "(none)"
            )
        )
    except Exception:
        picker_members = []

    state_getters = (
        "isMultiSelection",
        "isMultiSelectionMode",
        "isMultiSelect",
        "isMultipleSelection",
        "isMultiSelectMode",
        "isAllowMultiSelection",
        "isAllowMultipleSelection",
        "isMultiSelectionEnabled",
        "isSelectionMode",
        "isSelectionType",
        "isSelection",
        "getMultiSelection",
        "getMultiSelectionMode",
        "getMultiSelect",
        "getMultipleSelection",
        "getMultiSelectMode",
        "getAllowMultiSelection",
        "getAllowMultipleSelection",
        "getSelectionMode",
        "getSelectionType",
        "getSelection",
    )

    property_names = (
        "MultiSelection",
        "MultiSelectionMode",
        "SelectionMode",
        "AllowMultiSelection",
        "AllowMultipleSelection",
        "MultiSelect",
        "MultiSelectMode",
        "MultipleSelection",
        "MultiSelectModeEnabled",
        "MultiSelectionEnabled",
        "SelectionType",
        "Selection",
    )

    def _coerce_boolish(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            try:
                normalized = int(value)
            except Exception:
                return None
            # Non-zero usually indicates enabled for integer/short-style flags.
            return normalized != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("1", "true", "yes", "on", "enabled", "enable", "multiple", "multi"):
                return True
            if normalized in ("0", "false", "no", "off", "disabled", "disable"):
                return False
            return None
        return None

    def _probe():
        for getter in state_getters:
            if not hasattr(file_picker, getter):
                continue
            try:
                value = getattr(file_picker, getter)()
            except Exception as exc:
                logger.debug(
                    "set_file_picker_multi_select: getter {name} failed: {error}".format(
                        name=getter, error=exc
                    )
                )
                continue
            state = _coerce_boolish(value)
            if state is True:
                logger.debug("set_file_picker_multi_select: getter {name} indicates enabled".format(name=getter))
                return True
        if hasattr(file_picker, "getPropertyValue"):
            for key in property_names:
                try:
                    value = file_picker.getPropertyValue(key)
                except Exception:
                    continue
                state = _coerce_boolish(value)
                if state is True:
                    logger.debug(
                        "set_file_picker_multi_select: property {key} indicates enabled".format(key=key)
                    )
                    return True
        return False

    def _resolve_selection_constant(candidates):
        if not hasattr(uno, "getConstantByName"):
            return None
        for candidate in candidates:
            try:
                return uno.getConstantByName(candidate)
            except Exception:
                continue
        return None

    def _safe_constant(candidates):
        if not hasattr(uno, "getConstantByName"):
            return None
        for candidate in candidates:
            try:
                return uno.getConstantByName(candidate)
            except Exception:
                continue
        return None

    def _set_payloads(payloads):
        if payloads is None:
            return []
        cleaned = []
        seen = set()
        for payload in payloads:
            if payload is None:
                continue
            marker = repr(payload)
            if marker in seen:
                continue
            seen.add(marker)
            cleaned.append(payload)
        return cleaned

    def _set_method(method_name, payloads):
        if not hasattr(file_picker, method_name):
            return False, False
        method = getattr(file_picker, method_name)
        method_accepted = False
        for payload in _set_payloads(payloads):
            try:
                method(payload)
            except Exception as exc:
                logger.debug(
                    "set_file_picker_multi_select: {name}({value}) failed: {error}".format(
                        name=method_name, value=payload, error=exc
                    )
                )
                continue
            logger.debug(
                "set_file_picker_multi_select: method {name}({value}) accepted".format(
                    name=method_name, value=payload
                )
            )
            method_accepted = True
            if _probe():
                return True, True
        if method_accepted:
            final_probe = _probe()
            logger.debug(
                "set_file_picker_multi_select: method {name} accepted with no immediate verification; final probe={probe}".format(
                    name=method_name, probe=final_probe
                )
            )
            return True, bool(final_probe)
        return False, False

    def _set_property(name, payloads):
        if not hasattr(file_picker, "setPropertyValue"):
            return False, False
        property_accepted = False
        for payload in _set_payloads(payloads):
            try:
                file_picker.setPropertyValue(name, payload)
            except Exception as exc:
                logger.debug(
                    "set_file_picker_multi_select: property {name}={value} failed: {error}".format(
                        name=name, value=payload, error=exc
                    )
                )
                continue
            logger.debug(
                "set_file_picker_multi_select: property {name}={value} accepted".format(
                    name=name, value=payload
                )
            )
            property_accepted = True
            if _probe():
                return True, True
        if property_accepted:
            final_probe = _probe()
            logger.debug(
                "set_file_picker_multi_select: property {name} accepted with no immediate verification; final probe={probe}".format(
                    name=name, probe=final_probe
                )
            )
            return True, bool(final_probe)

        return False, False

    resolved_multiselect = (
        _resolve_selection_constant([
            "com.sun.star.ui.dialogs.SelectionType.MULTI",
            "com.sun.star.ui.dialogs.SelectionType.MULTISELECTION",
            "com.sun.star.view.SelectionType.MULTI",
            "com.sun.star.text.ControlCharacter.MULTISELECTION",
            "com.sun.star.ui.dialogs.FilePickerAction.MULTI_SELECTION",
        ])
        or multi_short
    )

    if resolved_multiselect == 0:
        resolved_multiselect = multi_short

    multiselect_payloads = (
        resolved_multiselect,
        multi_short_fallback,
        multi_short,
        multi_short_alt,
        True,
        true_bool,
        "MULTI",
        "MULTI_SELECTION",
    )
    selection_mode_payloads = (
        true_bool,
        multi_short_fallback,
        multi_short,
        multi_short_alt,
        resolved_multiselect,
        True,
        True,
        true_bool,
        2,
        1,
        "MULTI",
        "MULTISELECTION",
    )

    resolved_selection_multiselect_mode = _safe_constant([
        "com.sun.star.ui.dialogs.SelectionType.MULTI",
        "com.sun.star.ui.dialogs.SelectionType.MULTISELECTION",
        "com.sun.star.ui.dialogs.FilePickerAction.MULTI",
        "com.sun.star.view.SelectionType.MULTI",
        "com.sun.star.text.ControlCharacter.MULTISELECTION",
    ]) or resolved_multiselect or (uno.Any("short", 2) if hasattr(uno, "Any") else 2)

    # Normalize common single/multi constants to a stable integer/short payload:
    # most UNO implementations use 0/1/2-style constants where non-zero indicates multi-select.
    try:
        resolved_selection_multiselect_mode = int(resolved_selection_multiselect_mode)
    except Exception:
        pass

    legacy_selection_payloads = (
        resolved_selection_multiselect_mode,
        multi_short_fallback,
        multi_short_alt,
        2,
        1,
        True,
        true_bool,
        "MULTI",
        "MULTISELECTION",
    )

    best_effort = False

    if picker_set := _set_method("setMultiSelection", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setMultiSelectionMode", multiselect_payloads):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setMultiSelectionMode", selection_mode_payloads):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setMultiSelect", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method(
        "setMultiSelectMode",
        (True, true_bool, multi_short, multi_short_alt, 2, 1),
    ):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method(
        "setSelectionType",
        (
            "MULTI",
            "MULTISELECTION",
            resolved_selection_multiselect_mode,
            multi_short,
            multi_short_alt,
            2,
            1,
            True,
            true_bool,
        ),
    ):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True
        logger.debug(
            "set_file_picker_multi_select: setSelectionType accepted with fallback payload; continuing."
        )

    # Some UNO implementations expose selection mode as integer enums.
    if picker_set := _set_method(
        "setSelectionMode",
        legacy_selection_payloads,
    ):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True
        logger.debug("set_file_picker_multi_select: setSelectionMode accepted with no immediate verification; continuing.")

    if picker_set := _set_method("setAllowMultiSelection", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setAllowMultipleSelection", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setMultiSelectionEnabled", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    if picker_set := _set_method("setMultiSelectEnabled", (True, true_bool)):
        method_accepted, method_verified = picker_set
        best_effort = best_effort or method_accepted
        if method_verified:
            return True, True

    for key in property_names:
        if property_set := _set_property(
            key,
            (
                uno.Any("short", 2) if hasattr(uno, "Any") else 2,
                multi_short,
                resolved_multiselect,
                True,
                true_bool,
                2,
                _safe_constant([
                    "com.sun.star.view.SelectionType.MULTI",
                    "com.sun.star.view.SelectionType.MULTISELECTION",
                    "com.sun.star.ui.dialogs.SelectionType.MULTI",
                    "com.sun.star.ui.dialogs.FilePickerAction.MULTI",
                ]),
            ),
        ):
            property_accepted, property_verified = property_set
            best_effort = best_effort or property_accepted
            if property_verified:
                return True, True

    if best_effort:
        best_probe = _probe()
        logger.debug(
            "set_file_picker_multi_select: setter/property call accepted; final probe state={state}".format(
                state=best_probe
            )
        )
        return True, bool(best_probe)

    if _probe():
        logger.debug(
            "set_file_picker_multi_select: multi-select state is enabled and readable."
        )
        return True, True

    logger.debug(
        "set_file_picker_multi_select: unable to verify multi-select state; continuing as best-effort."
    )
    return False, False


def _build_default_ocr_options(ctx):
    """Load OCR defaults from settings for dialog pre-fills and OCR fallback."""
    output_mode_preference = _resolve_output_mode_preference(ctx)
    merge_batch_results = _coerce_bool(
        uno_utils.get_setting(
            constants.CFG_KEY_MERGE_BATCH_RESULTS,
            constants.DEFAULT_MERGE_BATCH_RESULTS,
            ctx,
        )
    )
    default_scale = _coerce_scale(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_SCALE,
            constants.DEFAULT_SCALE_FACTOR,
            ctx,
        ),
        constants.DEFAULT_SCALE_FACTOR,
    )
    default_preset = _coerce_preset_request(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_PRESET,
            constants.DEFAULT_OCR_PRESET,
            ctx,
        ),
        constants.DEFAULT_OCR_PRESET,
    )

    return {
        "lang": _normalize_language_request(
            uno_utils.get_setting(
                constants.CFG_KEY_LAST_SELECTED_LANG,
                uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx),
                ctx,
            )
        ),
        "output_mode": _coerce_output_mode(
            output_mode_preference,
            constants.DEFAULT_OUTPUT_MODE,
        ),
        "psm": str(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_PSM,
                constants.DEFAULT_PSM_MODE,
                ctx,
            )
        ).strip()
        or constants.DEFAULT_PSM_MODE,
        "oem": str(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_OEM,
                constants.DEFAULT_OEM_MODE,
                ctx,
            )
        ).strip()
        or constants.DEFAULT_OEM_MODE,
        "grayscale": _coerce_bool(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_GRAYSCALE,
                str(constants.DEFAULT_PREPROC_GRAYSCALE),
                ctx,
            )
        ),
        "binarize": _coerce_bool(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_BINARIZE,
                str(constants.DEFAULT_PREPROC_BINARIZE),
                ctx,
            )
        ),
        "invert": _coerce_bool(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_INVERT,
                str(constants.DEFAULT_PREPROC_INVERT),
                ctx,
            )
        ),
        "scale": default_scale,
        "improve_image": _coerce_bool(
            uno_utils.get_setting(
                constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT,
                str(constants.DEFAULT_IMPROVE_IMAGE),
                ctx,
            )
        ),
        "preset": default_preset,
        "show_preview": _coerce_bool(
            uno_utils.get_setting(
                constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                ctx,
            )
        ),
        "merge_batch_results": merge_batch_results,
        "language_warning": "",
    }


def _normalize_dialog_result(dialog_result, defaults, available_languages):
    """Normalize OCR options dialog results with fallback defaults."""
    default_lang = defaults["lang"]
    default_lang = _normalize_language_request(default_lang)
    default_output_mode = _coerce_output_mode(defaults["output_mode"], constants.DEFAULT_OUTPUT_MODE)
    default_preset = _coerce_preset_request(defaults.get("preset"), constants.DEFAULT_OCR_PRESET)
    default_grayscale = _coerce_bool(defaults.get("grayscale", False))
    default_binarize = _coerce_bool(defaults.get("binarize", False))
    default_invert = _coerce_bool(defaults.get("invert", False))
    default_scale = _coerce_scale(defaults.get("scale"), 1.0)
    default_psm = str(defaults.get("psm", constants.DEFAULT_PSM_MODE)).strip() or constants.DEFAULT_PSM_MODE
    default_oem = str(defaults.get("oem", constants.DEFAULT_OEM_MODE)).strip() or constants.DEFAULT_OEM_MODE
    default_show_preview = _coerce_bool(defaults.get("show_preview", constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT))
    default_merge = _coerce_bool(defaults.get("merge_batch_results", constants.DEFAULT_MERGE_BATCH_RESULTS))

    if dialog_result is None:
        return {
            "lang": default_lang,
            "output_mode": default_output_mode,
            "improve_image": _coerce_bool(defaults.get("improve_image", False)),
            "grayscale": default_grayscale,
            "binarize": default_binarize,
            "invert": default_invert,
            "scale": default_scale,
            "psm": default_psm,
            "oem": default_oem,
            "preset": default_preset,
            "show_preview": default_show_preview,
            "merge_batch_results": default_merge,
            "language_warning": "",
        }

    if not isinstance(dialog_result, (tuple, list)) or len(dialog_result) < 3:
        return {
            "lang": default_lang,
            "output_mode": default_output_mode,
            "improve_image": _coerce_bool(defaults.get("improve_image", False)),
            "grayscale": default_grayscale,
            "binarize": default_binarize,
            "invert": default_invert,
            "scale": default_scale,
            "psm": default_psm,
            "oem": default_oem,
            "preset": default_preset,
            "show_preview": default_show_preview,
            "merge_batch_results": default_merge,
            "language_warning": "",
        }

    if len(dialog_result) >= 3 and dialog_result[0] is None and dialog_result[1] is None and dialog_result[2] in (False, 0, None):
        return None

    language_input = dialog_result[0] or default_lang
    normalized_language, invalid_codes, validated = _validate_language_codes(
        language_input,
        available_languages,
    )
    language = normalized_language or default_lang
    output_mode = _coerce_output_mode(dialog_result[1], default_output_mode)
    improve_image = _coerce_bool(dialog_result[2])
    extra_options = dialog_result[3] if len(dialog_result) > 3 and isinstance(dialog_result[3], dict) else {}
    language_warning = _build_language_validation_message(language, invalid_codes, validated)

    selected_preset = _coerce_preset_request(extra_options.get("preset", default_preset), default_preset)
    preset_profile = constants.OCR_QUALITY_PRESETS.get(selected_preset)

    requested_psm = str(extra_options.get("psm", default_psm)).strip() or default_psm
    requested_oem = str(extra_options.get("oem", default_oem)).strip() or default_oem
    requested_scale = _coerce_scale(extra_options.get("scale", default_scale), default_scale)
    requested_grayscale = _coerce_bool(extra_options.get("grayscale", default_grayscale))
    requested_binarize = _coerce_bool(extra_options.get("binarize", default_binarize))
    requested_invert = _coerce_bool(extra_options.get("invert", default_invert))
    requested_show_preview = _coerce_bool(extra_options.get("show_preview", default_show_preview))
    requested_merge = _coerce_bool(
        extra_options.get(
            "merge_batch_results",
            extra_options.get("merge_results", extra_options.get("merge", default_merge)),
        )
    )
    requested_improve = _coerce_bool(extra_options.get("improve_image", improve_image)) if dialog_result and len(dialog_result) > 2 else improve_image

    if preset_profile:
        requested_psm = str(preset_profile.get("psm", requested_psm)).strip() or requested_psm
        requested_oem = str(preset_profile.get("oem", requested_oem)).strip() or requested_oem
        requested_scale = _coerce_scale(preset_profile.get("scale", requested_scale), requested_scale)
        requested_grayscale = _coerce_bool(preset_profile.get("grayscale", requested_grayscale))
        requested_binarize = _coerce_bool(preset_profile.get("binarize", requested_binarize))
        requested_invert = _coerce_bool(preset_profile.get("invert", requested_invert))
        requested_improve = _coerce_bool(preset_profile.get("improve_image", requested_improve))

    return {
        "lang": language,
        "output_mode": output_mode,
        "improve_image": requested_improve,
        "grayscale": requested_grayscale,
        "binarize": requested_binarize,
        "invert": requested_invert,
        "scale": requested_scale,
        "psm": requested_psm,
        "oem": requested_oem,
        "show_preview": requested_show_preview,
        "merge_batch_results": requested_merge,
        "preset": selected_preset,
        "language_warning": language_warning,
    }


def _build_output_text_for_batch(results, tr=None):
    """Format batch OCR results as a single text block."""
    translator = tr if callable(tr) else (lambda text: text)
    if not results:
        return ""

    formatted_sections = []
    for index, (source_label, text) in enumerate(results, start=1):
        label = source_label or translator("Source")
        clean_text = (text or "").strip()
        if not clean_text:
            clean_text = translator("No readable text extracted from this source.")
        source_len = len((text or "").strip())
        formatted_sections.append(
            "===== {prefix}: {label} ({length} chars) =====".format(
                prefix=translator("Source {index}").format(index=index),
                length=source_len,
                label=label,
            )
        )
        formatted_sections.append(clean_text)
    return "\n\n".join(formatted_sections)


def _preview_snippet(text, max_chars=140):
    """Build a short inline preview snippet for status UI summaries."""
    if not text:
        return ""
    normalized = " ".join((text or "").replace("\n", " ").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _count_files_by_type(paths):
    """Return (file_count, pdf_count, image_count) for OCR run logs/labels."""
    file_count = len([path for path in (paths or []) if path])
    pdf_count = sum(1 for path in (paths or []) if _is_pdf_path(path))
    return file_count, pdf_count, max(0, file_count - pdf_count)


def _format_batch_title(total_files, pdf_count, image_count):
    """Format source count summary for preview/title UI."""
    image_count = max(0, image_count)
    parts = [str(total_files)]

    if total_files == 1:
        return "Review OCR result — {count} source".format(count=total_files)

    if pdf_count and image_count:
        return "Review OCR result — {count} files ({pdf} PDF, {images} image)".format(
            count=total_files,
            pdf=pdf_count,
            images=image_count,
        )

    if pdf_count:
        return "Review OCR result — {count} PDF file(s)".format(count=total_files)

    return "Review OCR result — {count} image file(s)".format(count=total_files)


def _persist_last_ocr_preferences(ctx, language, output_mode, merge_batch_results=None):
    """Persist run-time choices so next time dialogs open with user's last used values."""
    try:
        normalized_lang = _normalize_language_request(language)
        if normalized_lang:
            uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, normalized_lang, ctx)
        normalized_output = _coerce_output_mode(output_mode, constants.DEFAULT_OUTPUT_MODE)
        if normalized_output:
            uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, normalized_output, ctx)
        if merge_batch_results is not None:
            uno_utils.set_setting(
                constants.CFG_KEY_MERGE_BATCH_RESULTS,
                "true" if _coerce_bool(merge_batch_results) else "false",
                ctx,
            )
    except Exception:
        pass

# --- Global variables for lazily loaded modules ---
_tejocr_interactive_dialogs_module = None
_tejocr_output_module = None
_tejocr_engine_module = None # Added for consistency if engine is also complex

# --- Helper functions for lazy loading ---
def _ensure_modules_loaded(service_instance, engine=False, dialogs=False, output=False):
    """Ensures all critical modules (dialogs, output, engine) are loaded."""
    global _tejocr_interactive_dialogs_module, _tejocr_output_module, _tejocr_engine_module
    import importlib
    
    if dialogs:
        service_instance.logger.debug("Loading/reloading tejocr_interactive_dialogs module...")
        try:
            from tejocr import tejocr_interactive_dialogs as _interactive_dialogs_mod
            _tejocr_interactive_dialogs_module = (
                importlib.reload(_interactive_dialogs_mod)
                if _tejocr_interactive_dialogs_module is not None
                else _interactive_dialogs_mod
            )
            service_instance.logger.debug("tejocr_interactive_dialogs module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(
                f"CRITICAL ERROR: Failed to load or refresh tejocr_interactive_dialogs: {e}",
                exc_info=True,
            )
            uno_utils.show_message_box(
                _("Error"),
                _("Extension internal error: Interactive Dialogs module failed. Check logs."),
                "errorbox",
                parent_frame=service_instance.frame,
                ctx=service_instance.ctx,
            )
            return False

    if output:
        service_instance.logger.debug("Lazily importing tejocr_output module...")
        try:
            if _tejocr_output_module is None:
                from tejocr import tejocr_output as _output_mod
                _tejocr_output_module = _output_mod
            service_instance.logger.debug("tejocr_output module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_output: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("Extension internal error: Output module failed. Check logs."), "errorbox", parent_frame=service_instance.frame, ctx=service_instance.ctx)
            return False
            
    if engine:
        service_instance.logger.debug("Lazily importing tejocr_engine module...")
        try:
            if _tejocr_engine_module is None:
                from tejocr import tejocr_engine as _engine_mod
                _tejocr_engine_module = _engine_mod
            service_instance.logger.debug("tejocr_engine module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_engine: {e}", exc_info=True)
            # No message box here as this is often a dependency of dialogs/output
            return False
            
    return True

class TejOCRService(unohelper.Base, XServiceInfo, XDispatchProvider, XDispatch, XInitialization):
    def __init__(self, ctx, *args):
        self.ctx = ctx
        self.frame = None
        # self.logger is now an instance variable, initialized from the module-level logger
        # This ensures each instance has a logger, but they all point to the same configured logger.
        self.logger = logger 
        self.logger.info(f"TejOCRService __init__ called with ctx: {self.ctx is not None}")
        # No deferred imports block here anymore. Modules are loaded by _ensure_modules_loaded.
        self.logger.info("TejOCRService __init__ completed. Modules will be late-loaded.")
            
    def initialize(self, args):
        self.logger.info("TejOCRService initializing...")

        # --- DEBUGGING CONSTANTS UPDATE ---
        try:
            # Ensure we are getting the latest version of constants
            import importlib
            from tejocr import constants as fresh_constants_module
            importlib.reload(fresh_constants_module)
            self.logger.info(f"DEBUG_CONSTANTS_CHECK: DEBUG_CONSTANT_VERSION = {fresh_constants_module.DEBUG_CONSTANT_VERSION}")
            if hasattr(fresh_constants_module, 'CFG_KEY_IMPROVE_IMAGE_DEFAULT'):
                self.logger.info(f"DEBUG_CONSTANTS_CHECK: CFG_KEY_IMPROVE_IMAGE_DEFAULT = {fresh_constants_module.CFG_KEY_IMPROVE_IMAGE_DEFAULT}")
            else:
                self.logger.error("DEBUG_CONSTANTS_CHECK: CFG_KEY_IMPROVE_IMAGE_DEFAULT is NOT FOUND in fresh_constants_module!")

        except AttributeError as ae:
            self.logger.error(f"DEBUG_CONSTANTS_CHECK: AttributeError accessing a constant: {ae} - This likely means the constants module is stale.")
        except Exception as e:
            self.logger.error(f"DEBUG_CONSTANTS_CHECK: Error trying to access DEBUG_CONSTANT_VERSION: {e}")
        # --- END DEBUGGING ---

        if args:
            for arg in args:
                if hasattr(arg, 'Name') and arg.Name == "Frame":
                    self.frame = arg.Value
                    self.logger.debug(f"Frame set from args: {self.frame is not None}")
        
        if not self.frame:
            self.logger.debug("No frame from args, getting current frame...")
            self.frame = uno_utils.get_current_frame(self.ctx) 
            self.logger.debug(f"Got current frame: {self.frame is not None}")
            
        self.logger.info(f"TejOCRService initialized with frame: {self.frame is not None}")
        self._test_frame_access() # Keep for diagnostics

    def _test_frame_access(self):
        """Internal test method to verify frame access works correctly."""
        try:
            self.logger.debug("Testing frame access...")
            test_frame = uno_utils.get_current_frame(self.ctx)
            if test_frame:
                self.logger.debug("TEST: Successfully got a current frame")
                # Test selection checking - should work even without an actual selection
                selection_result = uno_utils.is_graphic_object_selected(test_frame, self.ctx)
                self.logger.debug(f"TEST: is_graphic_object_selected returned {selection_result}")
            else:
                self.logger.warning("TEST: Could not get a current frame for testing!")
                
            # Check self.frame again too
            if self.frame:
                self.logger.debug("TEST: self.frame is set")
                selection_result = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
                self.logger.debug(f"TEST: is_graphic_object_selected on self.frame returned {selection_result}")
            else:
                self.logger.warning("TEST: self.frame is not set!")
                
        except Exception as e:
            self.logger.error(f"TEST: Error in frame access test: {e}", exc_info=True)

    def _test_url_matching(self):
        """Internal test method to verify URL matching works correctly."""
        self.logger.debug("_test_url_matching: Testing URL matching...")
        try:
            # Create a mock URL for testing
            from com.sun.star.util import URL as UnoURL
            test_url = UnoURL()
            test_url.Complete = DISPATCH_URL_OCR_SELECTED
            test_url.Protocol = "uno:"
            test_url.Path = DISPATCH_URL_OCR_SELECTED[4:] # Without protocol
            test_url.Main = DISPATCH_URL_OCR_SELECTED[4:] # Without protocol

            # Now test our matching method
            for cmd in [DISPATCH_URL_OCR_SELECTED, DISPATCH_URL_OCR_FROM_FILE, DISPATCH_URL_SETTINGS, DISPATCH_URL_TOOLBAR_ACTION]:
                result = self._matches_command_url(test_url, cmd)
                self.logger.debug(f"_test_url_matching: matching '{test_url.Complete}' against '{cmd}': {result}")
                
            # Test our dispatch method
            result = self.queryDispatch(test_url, "_self", 0)
            self.logger.debug(f"_test_url_matching: queryDispatch test URL result: {result is not None}")
            
            # Also test with a different command
            test_url.Complete = DISPATCH_URL_OCR_FROM_FILE
            test_url.Path = DISPATCH_URL_OCR_FROM_FILE[4:]
            result = self.queryDispatch(test_url, "_self", 0)

        except Exception as e:
            self.logger.error(f"_test_url_matching error: {e}", exc_info=True)

    # XServiceInfo
    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, ServiceName):
        return ServiceName == SERVICE_NAME

    def getSupportedServiceNames(self):
        return (SERVICE_NAME,)

    def _matches_command_url(self, url_obj, command_url_constant):
        """Internal helper to robustly match a URL object against our command URL constants.
        Tries various matching approaches to handle different URL formats from LibreOffice."""
        if not url_obj or not hasattr(url_obj, 'Complete'): return False
        return url_obj.Complete == command_url_constant

    def queryDispatch(self, URL, TargetFrameName, SearchFlags):
        self.logger.debug(f"queryDispatch CALLED for URL: {URL.Complete if URL else 'None'}, Target: {TargetFrameName}")
        dispatch = None
        if self._matches_command_url(URL, DISPATCH_URL_OCR_SELECTED) or \
           self._matches_command_url(URL, DISPATCH_URL_OCR_FROM_FILE) or \
           self._matches_command_url(URL, DISPATCH_URL_SETTINGS) or \
           self._matches_command_url(URL, DISPATCH_URL_TOOLBAR_ACTION):
            # We handle these URLs, so return self as the XDispatch object
            dispatch = self 
            self.logger.debug(f"queryDispatch: MATCHED URL '{URL.Complete}', returning self.")
        else:
            self.logger.debug(f"queryDispatch: NOT MATCHED URL '{URL.Complete}', returning None.")
        return dispatch

    def queryDispatches(self, Requests):
        self.logger.debug(f"queryDispatches CALLED with {len(Requests) if Requests else 0} requests.")
        dispatches = []
        for req in Requests:
            dispatches.append(self.queryDispatch(req.FeatureURL, req.FrameName, req.SearchFlags))
        return tuple(dispatches)

    def dispatch(self, URL, Arguments):
        self.logger.info(f"Dispatching URL: {URL.Complete if URL else 'None'}")
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)
            if not self.frame:
                self.logger.error("Cannot perform action: No active document window for dispatch.")
                return

        # CRITICAL: Ensure all necessary modules are loaded before proceeding
        if not _ensure_modules_loaded(self):
            self.logger.error("Dispatch aborted: Critical modules could not be loaded.")
            return

        # Now use _tejocr_interactive_dialogs_module, _tejocr_output_module, _tejocr_engine_module
        action_map = {
            DISPATCH_URL_OCR_SELECTED: lambda: self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image),
            DISPATCH_URL_OCR_FROM_FILE: lambda: self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file),
            DISPATCH_URL_SETTINGS: self._handle_settings,
            DISPATCH_URL_TOOLBAR_ACTION: self._handle_toolbar_action # New handler for combined logic
        }

        if URL.Complete in action_map:
            action_map[URL.Complete]()
        else:
            self.logger.warning(f"No action mapped for dispatch URL: {URL.Complete}")
            
    def _ensure_tesseract_is_ready_and_run(self, actual_handler_method, *args, **kwargs):
        """Wrapper to check Tesseract setup before running OCR-dependent handlers."""
        self.logger.debug(f"_ensure_tesseract_is_ready_and_run called for: {actual_handler_method.__name__}")

        if constants.DEVELOPMENT_MODE_STRICT_PLACEHOLDERS:
            self.logger.info("DEVELOPMENT_MODE_STRICT_PLACEHOLDERS is True. Bypassing Tesseract checks.")
            if not _ensure_modules_loaded(self, dialogs=True):  # Still ensure dialogs module is loaded
                self.logger.critical("Dialogs module could not be loaded even in strict placeholder mode.")
                uno_utils.show_message_box(
                    title=_("Critical Error"),
                    message=_("The dialogs module could not be loaded. Please check logs."),
                    type="errorbox", parent_frame=self.frame, ctx=self.ctx
                )
                return
            actual_handler_method(*args, **kwargs)
            return

        # Ensure core modules and the engine module are loaded
        if not _ensure_modules_loaded(self, engine=True, dialogs=True, output=True):
            self.logger.error("Core modules (engine/dialogs/output) could not be loaded. Cannot proceed with OCR.")
            # Message box already shown by _ensure_modules_loaded typically
            return

        # Now that modules are loaded, attempt to use the engine's readiness check.
        # Keep GUI noise controlled: show a single, user-friendly action prompt with
        # a direct path to Settings when the dependency setup is incomplete.
        try:
            if _tejocr_engine_module and hasattr(_tejocr_engine_module, 'is_tesseract_ready'):
                is_ready, message = _tejocr_engine_module.is_tesseract_ready(
                    self.ctx,
                    show_gui_errors=False,
                    parent_frame=self.frame
                )
                if is_ready:
                    self.logger.info("Tesseract is ready. Proceeding with OCR action.")
                    actual_handler_method(*args, **kwargs)
                else:
                    self.logger.warning(f"Tesseract is not ready: {message}. OCR action aborted.")
                    action = uno_utils.show_message_box(
                        title=_("Missing OCR Dependencies"),
                        message=(
                            "{title}\n\n{message}\n\n"
                            "Environment diagnostics:\n{diag}\n\n"
                            "Suggested setup:\n{setup}\n\n"
                            "Click OK to open Settings, fix the path/language settings, then retry.\n\n"
                            "If you need details, open Settings → Settings and click View Logs."
                        ).format(
                            title=_("TejOCR cannot run OCR yet."),
                            message=message,
                            diag=_build_dependency_diagnostics(self.ctx),
                            setup=_get_tesseract_setup_guide()
                        ),
                        type="warningbox",
                        buttons="ok_cancel",
                        parent_frame=self.frame,
                        ctx=self.ctx,
                    )
                    if _message_box_positive_button_pressed(action):
                        self.logger.info("User requested Settings from OCR dependency prompt.")
                        self._handle_settings()
                        # Re-check dependencies after settings and retry once
                        try:
                            is_ready_after_settings, message_after_settings = _tejocr_engine_module.is_tesseract_ready(
                                self.ctx,
                                show_gui_errors=False,
                                parent_frame=self.frame
                            )
                            if is_ready_after_settings:
                                actual_handler_method(*args, **kwargs)
                            else:
                                self.logger.info(
                                    "OCR dependencies still not ready after settings: {message}"
                                    .format(message=message_after_settings)
                                )
                                uno_utils.show_message_box(
                                    _("Dependencies still not configured"),
                                    _(
                                        "OCR is still not ready: {message}\n\n"
                                        "Open Settings again, then click Test, and retry after installing the required components."
                                    ).format(message=_format_dependency_short_status(message_after_settings)),
                                    "errorbox",
                                    parent_frame=self.frame,
                                    ctx=self.ctx
                                )
                        except Exception as recheck_error:
                            self.logger.error(
                                f"Dependency re-check failed after settings: {recheck_error}",
                                exc_info=True
                            )
            else:
                self.logger.error("TejOCR Engine module or is_tesseract_ready function not found.")
                uno_utils.show_message_box(
                    title=_("Engine Error"),
                    message=_("The OCR engine module is not correctly loaded. Cannot perform OCR."),
                    type="errorbox", parent_frame=self.frame, ctx=self.ctx
                )
        except Exception as e_check:
            self.logger.critical(f"Exception during Tesseract readiness check: {e_check}", exc_info=True)
            uno_utils.show_message_box(
                title=_("OCR Error"),
                message=_("An unexpected error occurred while checking Tesseract status: {error}").format(error=str(e_check)),
                type="errorbox", parent_frame=self.frame, ctx=self.ctx
            )

    def _handle_toolbar_action(self):
        self.logger.info("Handling Toolbar Action")
        # Ensure core modules are loaded. Toolbar action might lead to OCR or Settings.
        if not _ensure_modules_loaded(self, engine=True, dialogs=True, output=True):
            self.logger.error("Toolbar Action: Critical modules could not be loaded.")
            return
        
        is_image_selected = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
        if is_image_selected:
            self.logger.debug("Toolbar action: Image selected, proceeding with OCR Selected Image logic.")
            self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image)
        else:
            self.logger.debug("Toolbar action: No image selected, proceeding with OCR From File logic.")
            self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file)
    
    def _handle_ocr_selected_image(self):
        self.logger.info("Handling OCR Selected Image action.")
        
        current_frame = uno_utils.get_current_frame(self.ctx)
        if not uno_utils.is_graphic_object_selected(current_frame, self.ctx):
            uno_utils.show_message_box(_("Selection Required"), _("Please select an image in your document first."), "warningbox", parent_frame=self.frame, ctx=self.ctx)
            return

        # Ensure interactive dialogs module is loaded (and engine for language list)
        if not _ensure_modules_loaded(self, dialogs=True, engine=True):
            self.logger.error("OCR Selected Image: Dialogs or Engine module could not be loaded.")
            # Message box would have been shown by _ensure_modules_loaded on failure
            return

        try:
            insertion_anchor = None
            replacement_target = None
            captured_anchor_info = self._capture_selected_image_anchor()
            if isinstance(captured_anchor_info, tuple):
                replacement_target, insertion_anchor = captured_anchor_info
            else:
                insertion_anchor = captured_anchor_info
            self.logger.info("Showing interactive OCR options dialog for selected image...")
            # Use the already loaded module via the global variable
            options_handler = _tejocr_interactive_dialogs_module.InteractiveOptionsDialogHandler(
                self.ctx, self.frame, "selected", None
            )
            try:
                dialog_result = options_handler.show_dialog()
            except Exception as dialog_error:
                self.logger.warning(
                    "Interactive OCR options dialog failed for selected image: {error}. "
                    "Falling back to saved/default settings.".format(error=dialog_error)
                )
                dialog_result = None
            defaults = _build_default_ocr_options(self.ctx)
            available_langs = _tejocr_engine_module.get_available_languages()
            ocr_options = _normalize_dialog_result(dialog_result, defaults, available_langs)
            if ocr_options is None:
                # Check if dialog model was unavailable vs user actually cancelled
                if dialog_result is not None and dialog_result[0] is None and dialog_result[1] is None:
                    # Dialog creation failed — proceed with saved settings
                    self.logger.info("OCR options dialog unavailable, proceeding with saved settings.")
                    ocr_options = _normalize_dialog_result(None, defaults, available_langs)
                else:
                    self.logger.info("OCR selected image operation cancelled by user.")
                    return

            language = ocr_options["lang"]
            output_mode = ocr_options["output_mode"]
            improve_image = ocr_options["improve_image"]
            language_warning = ocr_options.get("language_warning", "")
            if language_warning:
                self.logger.warning(
                    "OCR language warning for selected image: {warning}".format(
                        warning=language_warning
                    )
                )
                uno_utils.show_message_box(
                    _("Language Warning"),
                    language_warning,
                    "warningbox",
                    parent_frame=self.frame,
                    ctx=self.ctx,
                )
            
            self.logger.info(
                f"OCR Options (final): Lang='{language}', Mode='{output_mode}', "
                f"Improve='{improve_image}', PSM='{ocr_options['psm']}', OEM='{ocr_options['oem']}'"
            )
            if insertion_anchor is not None:
                self.logger.debug("Captured insertion anchor for selected-image output.")
            
            self._perform_ocr_with_options(
                "selected",
                None,
                language,
                output_mode,
                ocr_options,
                insertion_anchor=insertion_anchor,
                replacement_target=replacement_target,
            )
            
        except Exception as e:
            self.logger.error(f"Error during interactive OCR for selected image: {e}", exc_info=True)
            uno_utils.show_message_box(
                title=_("OCR Error"),
                message=_("An unexpected error occurred while processing the selected image: {error}").format(error=str(e)),
                type="errorbox", parent_frame=self.frame, ctx=self.ctx
            )

    def _capture_selected_image_anchor(self):
        """Capture a replacement target and anchor from the selected image/object."""
        try:
            controller = self.frame.getController()
            if not controller:
                return None, None
            selection = controller.getSelection()
            if not selection:
                return None, None

            replacement_target = selection
            anchor = None

            def _is_graphic_candidate(candidate):
                if not candidate:
                    return False
                try:
                    if candidate.supportsService("com.sun.star.text.TextGraphicObject"):
                        return True
                    if candidate.supportsService("com.sun.star.text.XTextContent"):
                        return True
                    if candidate.supportsService("com.sun.star.drawing.XShape"):
                        return True
                    if candidate.supportsService("com.sun.star.drawing.Shape"):
                        return True
                    if candidate.supportsService("com.sun.star.drawing.ShapeCollection"):
                        return True
                except Exception:
                    pass
                return (
                    hasattr(candidate, "Graphic")
                    or hasattr(candidate, "GraphicURL")
                    or hasattr(candidate, "GraphicObject")
                    or hasattr(candidate, "GraphicObjectURL")
                )

            def _extract_candidate_from_collection(selection_obj):
                try:
                    if hasattr(selection_obj, "getCount") and hasattr(selection_obj, "getByIndex"):
                        count = selection_obj.getCount()
                        if count is None or count < 1:
                            return selection_obj

                        # Prefer the first explicit graphic/shape-like object.
                        for index in range(count):
                            candidate = selection_obj.getByIndex(index)
                            if _is_graphic_candidate(candidate):
                                return candidate

                        # As a fallback, keep the first object in the collection when
                        # the collection contains only one item and it is not trivially
                        # classified.
                        return selection_obj.getByIndex(0)
                except Exception:
                    pass
                return selection_obj

            if hasattr(selection, "getCount") and hasattr(selection, "getByIndex"):
                replacement_target = _extract_candidate_from_collection(selection)

            if hasattr(selection, "supportsService"):
                try:
                    if selection.supportsService("com.sun.star.text.TextContent") and hasattr(selection, "Anchor"):
                        anchor = selection.Anchor
                except Exception:
                    pass

                try:
                    if selection.supportsService("com.sun.star.drawing.ShapeCollection"):
                        count = selection.getCount()
                        if count == 1:
                            shape = selection.getByIndex(0)
                            if hasattr(shape, "getAnchor"):
                                replacement_target = shape
                                anchor = shape.getAnchor()
                except Exception:
                    pass

            if replacement_target is not selection:
                try:
                    if hasattr(replacement_target, "getAnchor"):
                        anchor = replacement_target.getAnchor()
                except Exception:
                    pass
                if anchor is None and hasattr(replacement_target, "Anchor"):
                    try:
                        anchor = replacement_target.Anchor
                    except Exception:
                        pass

            if anchor is None and hasattr(selection, "getAnchor"):
                try:
                    anchor = selection.getAnchor()
                except Exception:
                    pass

            if replacement_target is not None and (
                anchor is None
                and hasattr(replacement_target, "getAnchor")
            ):
                try:
                    anchor = replacement_target.getAnchor()
                except Exception:
                    pass

            if anchor is None and hasattr(replacement_target, "supportsService"):
                try:
                    if replacement_target.supportsService("com.sun.star.text.TextGraphicObject"):
                        if hasattr(replacement_target, "Anchor"):
                            anchor = replacement_target.Anchor
                except Exception:
                    pass

            if replacement_target is not None and replacement_target.supportsService("com.sun.star.drawing.ShapeCollection"):
                try:
                    count = replacement_target.getCount()
                    if count >= 1:
                        shape = replacement_target.getByIndex(0)
                        replacement_target = shape
                        if anchor is None and hasattr(shape, "getAnchor"):
                            anchor = shape.getAnchor()
                except Exception:
                    pass

            # Fallback to view cursor position only when we still cannot determine
            # a reliable anchor from the selected image/shape itself.
            try:
                view_cursor = controller.getViewCursor()
                if anchor is None and view_cursor is not None:
                    if hasattr(view_cursor, "getStart"):
                        anchor = view_cursor.getStart()
                    else:
                        anchor = view_cursor
            except Exception:
                pass

            return replacement_target, anchor
        except Exception as e:
            self.logger.debug(f"Could not capture selected image anchor: {e}")
            return None, None

    def _handle_ocr_image_from_file(self):
        self.logger.info("Handling OCR Image/PDF from File action.")

        if not _ensure_modules_loaded(self, dialogs=True, engine=True):
            self.logger.error("OCR From File: Dialogs or Engine module could not be loaded.")
            return
        tr = _ if callable(globals().get("_")) else (lambda text: text)

        try:
            def _safe_constant(candidates):
                if not hasattr(uno, "getConstantByName"):
                    return None
                for candidate in candidates:
                    try:
                        return uno.getConstantByName(candidate)
                    except Exception:
                        continue
                return None

            def _initialize_file_picker(file_picker, picker_service):
                if not file_picker:
                    return False
                if not hasattr(file_picker, "initialize"):
                    self.logger.debug("File picker initialize skipped for {service}: no initialize() API".format(service=picker_service))
                    return False

                template_candidates = _safe_constant([
                    "com.sun.star.ui.dialogs.TemplateDescription.FILEOPEN",
                    "com.sun.star.ui.dialogs.TemplateDescription.FILE_OPEN",
                    "com.sun.star.ui.dialogs.TemplateDescription.FILEOPEN_SIMPLE",
                    "com.sun.star.ui.dialogs.TemplateDescription.FILE_OPEN_SIMPLE",
                    "com.sun.star.ui.dialogs.FilePickerAction.OPEN",
                    "com.sun.star.ui.dialogs.FilePickerAction.OPEN_SIMPLE",
                ])

                attempts = []
                if template_candidates is not None:
                    attempts.extend(
                        (
                            template_candidates,
                            (template_candidates,),
                            [template_candidates],
                        )
                    )

                attempts.append(())

                for attempt in attempts:
                    try:
                        file_picker.initialize(attempt)
                        self.logger.debug(
                            "File picker initialize succeeded for {service} with args={args}".format(
                                service=picker_service,
                                args=attempt,
                            )
                        )
                        return True
                    except Exception as initialize_error:
                        self.logger.debug(
                            "File picker initialize failed for {service} with args={args}: {error}".format(
                                service=picker_service,
                                args=attempt,
                                error=initialize_error,
                            )
                        )
                        continue

                return False

            selected_picker = None
            selected_picker_type = "unknown"
            picker_multi_enabled = False
            picker_multi_verified = False
            selected_picker_score = -1
            selected_picker_rating = -1

            for picker_service in (
                "com.sun.star.ui.dialogs.FilePicker2",
                "com.sun.star.ui.dialogs.FilePicker",
            ):
                candidate_picker = uno_utils.create_instance(picker_service, self.ctx)
                if not candidate_picker:
                    self.logger.debug(
                        "File picker creation failed for service: {service}".format(
                            service=picker_service
                        )
                    )
                    continue

                _initialize_file_picker(candidate_picker, picker_service)

                candidate_multi_enabled, candidate_multi_verified = _safe_enable_file_picker_multi_select(
                    candidate_picker, self.logger
                )

                candidate_score = 2 if candidate_multi_verified else (1 if candidate_multi_enabled else 0)
                candidate_rating = candidate_score
                if candidate_score > selected_picker_score or (
                    candidate_score == selected_picker_score and candidate_rating > selected_picker_rating
                ):
                    selected_picker = candidate_picker
                    selected_picker_type = picker_service
                    picker_multi_enabled = candidate_multi_enabled
                    picker_multi_verified = candidate_multi_verified
                    selected_picker_score = candidate_score
                    selected_picker_rating = candidate_rating
                    self.logger.debug(
                        "Evaluated file picker candidate '{service}' with multi-score={score}".format(
                            service=picker_service,
                            score=candidate_score,
                        )
                    )

            file_picker = selected_picker
            picker_type = selected_picker_type

            if not file_picker:
                uno_utils.show_message_box(
                    tr("Error"),
                    tr("Could not create file picker."),
                    "errorbox",
                    parent_frame=self.frame,
                    ctx=self.ctx,
                )
                return

            self.logger.debug("Using file picker type: {picker_type}".format(picker_type=picker_type))

            def _flatten_selection_value(value):
                if value is None:
                    return []
                if isinstance(value, bytes):
                    try:
                        return [value.decode("utf-8")]
                    except Exception:
                        return [str(value)]
                if isinstance(value, dict):
                    return [str(value)]
                if hasattr(value, "Value"):
                    try:
                        return _flatten_selection_value(value.Value)
                    except Exception:
                        pass
                if hasattr(value, "getValue") and callable(value.getValue):
                    try:
                        return _flatten_selection_value(value.getValue())
                    except Exception:
                        pass
                if isinstance(value, str):
                    return [value]
                if isinstance(value, (list, tuple, set, frozenset)):
                    values = []
                    for item in value:
                        if item is None:
                            continue
                        if isinstance(item, (list, tuple, set)):
                            values.extend(_flatten_selection_value(item))
                        else:
                            values.append(item)
                    return values
                if hasattr(value, "__iter__"):
                    try:
                        return _flatten_selection_value(list(value))
                    except Exception:
                        pass
                return [value]

            def _normalise_file_selection(selection):
                raw_entries = _flatten_selection_value(selection)
                normalised = []

                def _is_fragment_token(token):
                    token = token.strip()
                    if not token or not token.startswith("%"):
                        return False
                    if len(token) < 3:
                        return False
                    return all(c in "0123456789abcdefABCDEF" for c in token[1:3])

                def _is_source_token(token):
                    token_lower = token.lower()
                    return (
                        token_lower.startswith("file://")
                        or token_lower.startswith("vnd.sun.star.hierarchy://")
                        or token_lower.startswith("private:")
                        or token_lower.startswith("http://")
                        or token_lower.startswith("https://")
                    )

                def _split_entry(value):
                    if value is None:
                        return []
                    if not isinstance(value, str):
                        value = str(value)
                    value = value.strip().strip("()[]{}")
                    if not value:
                        return []

                    # Split only on explicit multi-url boundaries while preserving
                    # filenames that contain spaces/commas. This prevents accidental
                    # tokenization of valid URLs such as:
                    #   file:///.../ChatGPT%20Image%20May%203, 2025, ...png
                    #
                    # We avoid generic whitespace splitting because comma/space in
                    # paths is common on macOS/Windows file names.
                    if value.count("file://") > 1:
                        starts = []
                        cursor = 0
                        while True:
                            index = value.find("file://", cursor)
                            if index < 0:
                                break
                            starts.append(index)
                            cursor = index + len("file://")
                        if starts:
                            chunks_by_url = []
                            for idx, start in enumerate(starts):
                                end = starts[idx + 1] if idx + 1 < len(starts) else len(value)
                                chunk = value[start:end].strip()
                                if chunk:
                                    chunks_by_url.append(chunk)
                            if chunks_by_url:
                                return chunks_by_url

                    normalized_chunks = [value]
                    for delimiter in ("\x00", "\r", "\n", "|"):
                        expanded = []
                        for chunk in normalized_chunks:
                            if not isinstance(chunk, str):
                                chunk = str(chunk)
                            expanded.extend(chunk.split(delimiter))
                        normalized_chunks = expanded

                    tokens = []
                    for chunk in normalized_chunks:
                        if chunk is None:
                            continue
                        chunk = str(chunk).strip()
                        if not chunk:
                            continue
                        tokens.append(chunk)
                    return tokens

                def _append_selection_token(token, tokens_list):
                    if not token:
                        return
                    if tokens_list and _is_fragment_token(token):
                        previous = tokens_list[-1]
                        if _is_source_token(previous):
                            tokens_list[-1] = "{prefix}{suffix}".format(
                                prefix=previous,
                                suffix=token,
                            )
                            self.logger.debug(
                                "Merged picker URL fragment into source token: '{merged}'".format(
                                    merged=tokens_list[-1]
                                )
                            )
                            return
                    tokens_list.append(token)

                for entry in raw_entries:
                    if entry is None:
                        continue
                    if isinstance(entry, bytes):
                        try:
                            entry = entry.decode("utf-8")
                        except Exception:
                            entry = str(entry)
                    if not isinstance(entry, str):
                        entry = str(entry)
                    value = entry.strip()
                    if not value:
                        continue

                    # Defensive tokenization for runtimes that return multiple paths in one value.
                    for candidate in _split_entry(value):
                        if not isinstance(candidate, str):
                            candidate = str(candidate)
                        candidate = candidate.strip().strip('\"').strip("'")
                        if not candidate:
                            continue
                        _append_selection_token(candidate, normalised)

                deduped = []
                seen = set()
                for path_value in normalised:
                    if path_value in seen:
                        continue
                    seen.add(path_value)
                    deduped.append(path_value)
                return deduped

            def _to_system_path(candidate):
                if not candidate:
                    return None
                candidate = str(candidate).strip()
                if not candidate:
                    return None

                candidate_lower = candidate.lower()
                if candidate_lower.startswith("file://") or candidate_lower.startswith("vnd.sun.star.hierarchy://") or candidate_lower.startswith("private:"):
                    try:
                        return unohelper.fileUrlToSystemPath(candidate)
                    except Exception as convert_error:
                        self.logger.warning(
                            "Could not convert candidate path '{path}': {error}".format(
                                path=candidate,
                                error=convert_error,
                            )
                        )
                        return None

                if "://" in candidate:
                    try:
                        return unohelper.fileUrlToSystemPath(candidate)
                    except Exception as convert_error:
                        self.logger.debug(
                            "Skipping non-file candidate '{path}': {error}".format(
                                path=candidate,
                                error=convert_error,
                            )
                        )
                        return None

                return candidate

            def _extract_picker_selection(fp):
                collected = []
                seen = set()

                def _add_entries(raw, source_label):
                    for entry in _normalise_file_selection(raw):
                        if entry in seen:
                            continue
                        seen.add(entry)
                        collected.append(entry)
                        self.logger.debug(
                            "File picker selection contribution from {source}: {path}".format(
                                source=source_label,
                                path=entry,
                            )
                        )

                for method_name in (
                    "getSelectedFiles",
                    "getFiles",
                    "getSelectedFileURLs",
                    "getFileURLs",
                    "getFileFilter",
                    "getSelectedFile",
                    "getFile",
                ):
                    if not hasattr(fp, method_name):
                        continue
                    try:
                        raw = _flatten_selection_value(getattr(fp, method_name)())
                        self.logger.debug(
                            "File picker returned selection via {method_name}: type={type_name}, value={value}".format(
                                method_name=method_name,
                                type_name=type(raw).__name__,
                                value=raw,
                            )
                        )
                        if raw:
                            _add_entries(raw, method_name)
                    except Exception as exc:
                        self.logger.debug(
                            "File picker method {method_name} failed while reading selection: {error}".format(
                                method_name=method_name,
                                error=exc,
                            )
                        )

                if hasattr(fp, "getPropertyValue"):
                    for property_name in (
                        "Files",
                        "SelectedFiles",
                        "FilePath",
                        "FilePaths",
                        "FileNames",
                        "FileURLs",
                        "MultiSelection",
                        "FileList",
                        "FileName",
                        "FileURL",
                    ):
                        try:
                            raw = _flatten_selection_value(fp.getPropertyValue(property_name))
                            self.logger.debug(
                                "File picker returned selection property {property_name}: type={type_name}, value={value}".format(
                                    property_name=property_name,
                                    type_name=type(raw).__name__,
                                    value=raw,
                                )
                            )
                            if raw:
                                _add_entries(raw, "property:{name}".format(name=property_name))
                        except Exception as exc:
                            self.logger.debug(
                                "File picker property {property_name} failed while reading selection: {error}".format(
                                    property_name=property_name,
                                    error=exc,
                                )
                            )

                return collected

            if picker_multi_enabled:
                self.logger.debug(
                    "File picker multi-selection enabled."
                    " Verified: {verified}".format(verified=picker_multi_verified)
                )
            else:
                self.logger.debug(
                    "File picker multi-selection not confirmed by picker API; attempting single-select fallback."
                )
                try:
                    picker_methods = sorted(
                        [name for name in dir(file_picker) if "multi" in str(name).lower()]
                    )
                    self.logger.debug(
                        "FilePicker multi-related members: {members}".format(
                            members=", ".join(picker_methods[:20]) or tr("(none)")
                        )
                    )
                except Exception:
                    pass

            file_picker.setTitle(tr("Select Image(s) or PDF(s) for OCR"))
            file_picker.appendFilter(tr("Images and PDF Files"), constants.IMAGE_OR_PDF_DIALOG_FILTER)
            file_picker.appendFilter(
                tr("Image Files (*.png, *.jpg, *.jpeg, *.bmp, *.gif, *.tif, *.tiff, *.webp)"),
                constants.IMAGE_FILE_DIALOG_FILTER,
            )
            file_picker.appendFilter(tr("PDF Files"), constants.PDF_FILE_DIALOG_FILTER)
            file_picker.appendFilter(tr("All Files (*.*)"), "*.*")

            if file_picker.execute() == uno_utils.OK_BUTTON:
                selected_files = _normalise_file_selection(_extract_picker_selection(file_picker))
                self.logger.debug("Raw file picker selection: {count} entries".format(count=len(selected_files)))

                image_paths = []
                for selected_file in selected_files:
                    system_path = _to_system_path(selected_file)
                    if not system_path:
                        self.logger.warning(
                            "Skipping file picker entry that could not be converted: '{path}'".format(
                                path=selected_file,
                            )
                        )
                        continue
                    image_paths.append(system_path)
                    self.logger.debug(
                        "Resolved selected source #{index}: {path}".format(
                            index=len(image_paths),
                            path=system_path,
                        )
                    )

                if not image_paths:
                    self.logger.info("No valid file paths were returned by picker.")
                    return

                self.logger.info(f"Selected {len(image_paths)} file(s) for OCR.")
                preview_first_path = image_paths[0]

                self.logger.info("Showing interactive OCR options dialog for file...")
                options_handler = _tejocr_interactive_dialogs_module.InteractiveOptionsDialogHandler(
                    self.ctx, self.frame, "file", preview_first_path
                )
                try:
                    dialog_result = options_handler.show_dialog()
                except Exception as dialog_error:
                    self.logger.warning(
                        "Interactive OCR options dialog failed for file OCR: {error}. "
                        "Falling back to saved/default settings.".format(error=dialog_error)
                    )
                    dialog_result = None

                defaults = _build_default_ocr_options(self.ctx)
                available_langs = _tejocr_engine_module.get_available_languages()
                ocr_options = _normalize_dialog_result(dialog_result, defaults, available_langs)

                if ocr_options is None:
                    if dialog_result is not None and dialog_result[0] is None and dialog_result[1] is None:
                        self.logger.info("OCR options dialog unavailable, proceeding with saved settings.")
                        ocr_options = _normalize_dialog_result(None, defaults, available_langs)
                    else:
                        self.logger.info("OCR from file operation cancelled by user.")
                        return

                language = ocr_options["lang"]
                output_mode = ocr_options["output_mode"]
                improve_image = ocr_options["improve_image"]
                language_warning = ocr_options.get("language_warning", "")

                if language_warning:
                    self.logger.warning(
                        "OCR language warning for file image: {warning}".format(
                            warning=language_warning
                        )
                    )
                    uno_utils.show_message_box(
                        tr("Language Warning"),
                        language_warning,
                        "warningbox",
                        parent_frame=self.frame,
                        ctx=self.ctx,
                    )

                self.logger.info(
                    f"OCR Options for file (final): Lang='{language}', Mode='{output_mode}', "
                    f"Improve='{improve_image}', PSM='{ocr_options['psm']}', OEM='{ocr_options['oem']}', "
                    f"Source count={len(image_paths)}"
                )

                if len(image_paths) == 1 and not _is_pdf_path(image_paths[0]):
                    self._perform_ocr_with_options("file", image_paths[0], language, output_mode, ocr_options)
                else:
                    self._perform_batch_ocr("file", image_paths, language, output_mode, ocr_options)
            else:
                self.logger.info("File selection cancelled by user.")

        except Exception as e:
            self.logger.error(f"Error during interactive OCR from file: {e}", exc_info=True)
            uno_utils.show_message_box(
                title=tr("OCR Error"),
                message=tr("An unexpected error occurred while selecting the file or performing OCR: {error}").format(
                    error=str(e)
                ),
                type="errorbox",
                parent_frame=self.frame,
                ctx=self.ctx,
            )

    def _perform_batch_ocr(
        self,
        source_type,
        image_paths,
        language,
        output_mode,
        ocr_options=None,
        insertion_anchor=None,
        replacement_target=None,
    ):
        """Perform OCR on multiple image files or PDF pages and merge outputs."""
        tr = _ if callable(globals().get("_")) else (lambda text: text)
        try:
            if not _ensure_modules_loaded(self, engine=True, output=True):
                self.logger.error("Perform batch OCR: Engine or Output module could not be loaded.")
                return

            defaults = _build_default_ocr_options(self.ctx)
            if not ocr_options:
                ocr_options = defaults.copy()

            language = _normalize_language_request(language or ocr_options.get("lang"))
            if not language:
                language = defaults["lang"]
            output_mode = _coerce_output_mode(output_mode, defaults["output_mode"])
            if output_mode not in (
                constants.OUTPUT_MODE_CURSOR,
                constants.OUTPUT_MODE_CLIPBOARD,
                constants.OUTPUT_MODE_TEXTBOX,
                constants.OUTPUT_MODE_REPLACE,
            ):
                output_mode = defaults["output_mode"]
            if source_type != "selected" and output_mode == constants.OUTPUT_MODE_REPLACE:
                self.logger.debug("Replace Image output mode requested for file batch; falling back to cursor insertion.")
                output_mode = constants.OUTPUT_MODE_CURSOR

            pdf2image_install_cmd = None

            def _default_pdf_hints():
                if pdf2image_install_cmd:
                    runtime_hint = "Install PDF conversion runtime in this Python: {cmd}".format(
                        cmd=pdf2image_install_cmd
                    )
                else:
                    runtime_hint = "Install PDF conversion runtime in this Python (runtime package command not detected)"
                if os.name == "nt":
                    return [
                        "choco install poppler",
                        "scoop install poppler",
                        runtime_hint,
                    ]
                if os.name == "darwin":
                    return [
                        "brew install poppler",
                        "brew install mupdf",
                        runtime_hint,
                    ]
                if os.name == "posix":
                    return [
                        "apt-get install poppler-utils",
                        "apt-get install mupdf-tools",
                        "choco install poppler",
                        "scoop install poppler",
                        runtime_hint,
                    ]
                return [
                    "Install a PDF renderer such as poppler or MuPDF",
                    runtime_hint,
                ]

            try:
                from tejocr import tejocr_pdf as pdf_module
                pdf_renderer_status = pdf_module.get_pdf_renderer_status()
                try:
                    pdf2image_install_cmd = pdf_module.get_pdf2image_install_command()
                    if pdf2image_install_cmd:
                        hints = list(pdf_renderer_status.get("hints") or [])
                        cleaned_hints = [
                            line for line in hints if "pip install pdf2image" not in str(line).lower()
                        ]
                        cleaned_hints.append(
                            f"Install PDF conversion runtime in this Python: {pdf2image_install_cmd}"
                        )
                        pdf_renderer_status["hints"] = cleaned_hints
                except Exception:
                    pass
            except Exception as pdf_init_error:
                self.logger.debug(
                    "Batch OCR: failed to initialize PDF helper; PDF files may fail: {error}".format(
                        error=pdf_init_error
                    )
                )
                pdf_renderer_status = {
                    "available": False,
                    "engine": None,
                    "hints": _default_pdf_hints(),
                }
                pdf_module = None
            pdf_runtime_status = {"value": pdf_renderer_status}

            def _refresh_pdf_status():
                nonlocal pdf2image_install_cmd
                if not isinstance(pdf2image_install_cmd, str) or not pdf2image_install_cmd:
                    try:
                        pdf2image_install_cmd = pdf_module.get_pdf2image_install_command() if pdf_module else None
                    except Exception:
                        pass
                if pdf_module is None:
                    return {
                        "available": False,
                        "engine": None,
                        "hints": _default_pdf_hints(),
                    }
                try:
                    status = pdf_module.get_pdf_renderer_status()
                    if pdf2image_install_cmd:
                        existing_hints = list(status.get("hints") or [])
                        status_hints = [
                            entry for entry in existing_hints if "pip install pdf2image" not in str(entry).lower()
                        ]
                        status_hints.append(f"Install PDF conversion runtime in this Python: {pdf2image_install_cmd}")
                        status["hints"] = status_hints
                    return status
                except Exception as status_error:
                    logger.debug(
                        "Batch OCR: failed to refresh PDF renderer status during processing: {error}".format(
                            error=status_error
                        )
                    )
                    return {
                        "available": False,
                        "engine": None,
                        "hints": _default_pdf_hints(),
                        "error": str(status_error),
                    }

            options = {
                "lang": language,
                "psm": str(ocr_options.get("psm", defaults["psm"])).strip() or defaults["psm"],
                "oem": str(ocr_options.get("oem", defaults["oem"])).strip() or defaults["oem"],
                "scale": _coerce_scale(ocr_options.get("scale"), defaults.get("scale")),
                "grayscale": _coerce_bool(ocr_options.get("grayscale", defaults.get("grayscale", False))),
                "binarize": _coerce_bool(ocr_options.get("binarize", defaults.get("binarize", False))),
                "invert": _coerce_bool(ocr_options.get("invert", defaults.get("invert", False))),
                "improve_image": _coerce_bool(
                    ocr_options.get("improve_image", defaults.get("improve_image", False))
                ),
                "preset": _coerce_preset_request(ocr_options.get("preset"), defaults.get("preset")),
                "show_preview": _coerce_bool(ocr_options.get("show_preview", defaults.get("show_preview"))),
                "merge_batch_results": _coerce_bool(
                    ocr_options.get("merge_batch_results", defaults.get("merge_batch_results"))
                ),
            }

            _persist_last_ocr_preferences(
                self.ctx,
                options["lang"],
                output_mode,
                ocr_options.get("merge_batch_results"),
            )
            self.logger.info(
                f"Performing batch OCR: mode='{output_mode}', source='{source_type}', files={len(image_paths)}"
            )

            def _rasterize_pdf_file(pdf_path):
                if not _is_pdf_path(pdf_path):
                    return []
                if pdf_module is None:
                    raise RuntimeError(tr("PDF module is not loaded."))
                current_status = _refresh_pdf_status()
                pdf_runtime_status["value"] = current_status
                try:
                    return pdf_module.rasterize_pdf_pages(pdf_path)
                except Exception as pdf_error:
                    error_text = str(pdf_error)
                    if current_status and current_status.get("available"):
                        if current_status.get("hints"):
                            raise RuntimeError(
                                tr("PDF rendering failed. Install one of:\\n{hints}\\n\\nOriginal error: {error}").format(
                                    hints="\\n".join(
                                        " - {cmd}".format(cmd=entry) for entry in current_status["hints"]
                                    ),
                                    error=error_text,
                                )
                            )
                        raise RuntimeError(error_text)

                    if current_status and current_status.get("hints"):
                        hint_text = tr("No PDF renderer found. Install one of:\\n{hints}").format(
                            hints="\\n".join(" - {cmd}".format(cmd=entry) for entry in current_status["hints"])
                        )
                        if hint_text not in error_text:
                            raise RuntimeError(f"{hint_text}\n\nOriginal error: {error_text}")
                        raise RuntimeError(error_text)
                    raise RuntimeError(tr("No PDF renderer found."))

            def _clean_source_name(raw_path):
                if raw_path:
                    return os.path.basename(raw_path)
                return tr("Source")

            def _process_single_file(source_path):
                if not os.path.isfile(source_path):
                    return None, tr("File not found")

                if _is_pdf_path(source_path):
                    base_name = _clean_source_name(source_path)
                    try:
                        page_paths = _rasterize_pdf_file(source_path)
                    except Exception as pdf_error:
                        error_text = str(pdf_error)
                        nonlocal_pdf_renderer_hint["value"] = error_text
                        return None, error_text

                    if not page_paths:
                        return None, tr("No pages rasterized from PDF")

                    temp_image_paths.extend(page_paths)
                    total_pages = len(page_paths)
                    source_name = tr("{source} (PDF, {pages} page(s))").format(
                        source=base_name,
                        pages=total_pages,
                    )
                    page_sections = []
                    for index, page_image in enumerate(page_paths, start=1):
                        result = _tejocr_engine_module.perform_ocr(
                            self.ctx,
                            self.frame,
                            "file",
                            page_image,
                            options,
                        )
                        page_label = tr("Page {page} of {total} in {source}").format(
                            page=index, total=total_pages, source=source_name
                        )
                        if result.get("success"):
                            page_text = (result.get("text") or "").strip()
                            if page_text:
                                section = tr("{page_label}:\\n{page_text}").format(
                                    page_label=page_label,
                                    page_text=page_text,
                                )
                                page_sections.append(section)
                        else:
                            failed_sources.append((page_label, result.get("message", tr("OCR failed"))))
                    if page_sections:
                        return ((source_name, "\n\n".join(page_sections)), None)
                    return None, tr("No text recognized from PDF")

                result = _tejocr_engine_module.perform_ocr(
                    self.ctx,
                    self.frame,
                    "file",
                    source_path,
                    options,
                )
                if result.get("success"):
                    return ((os.path.basename(source_path), result.get("text") or "")), None
                return None, result.get("message", tr("OCR failed"))

            def _route_batch_output(target_text):
                if output_mode == constants.OUTPUT_MODE_CURSOR:
                    _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        target_text,
                        constants.OUTPUT_MODE_CURSOR,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                    )
                elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
                    _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, target_text, constants.OUTPUT_MODE_CLIPBOARD)
                elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
                    _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        target_text,
                        constants.OUTPUT_MODE_TEXTBOX,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                    )
                elif output_mode == constants.OUTPUT_MODE_REPLACE:
                    _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        target_text,
                        constants.OUTPUT_MODE_REPLACE,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                        replacement_target=replacement_target,
                    )
                else:
                    self.logger.warning(f"Unknown output mode '{output_mode}', defaulting to cursor.")
                    _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        target_text,
                        constants.OUTPUT_MODE_CURSOR,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                    )

            def _build_batch_failures_text(failed_sources):
                if not failed_sources:
                    return tr("No pages/files returned recognizable text.")
                failure_lines = [f"• {path}: {reason}" for path, reason in failed_sources[:8]]
                failed_message = "\n".join(failure_lines)
                if len(failed_sources) > 8:
                    failed_message += tr("\n... and {count} more.").format(count=len(failed_sources) - 8)
                return failed_message

            batch_results = []
            processed_sources = 0
            failed_sources = []
            temp_image_paths = []
            nonlocal_pdf_renderer_hint = {"value": None}
            total_requests = list(image_paths or [])

            def _format_pdf_renderer_hint():
                renderer_status = pdf_runtime_status.get("value")
                if not renderer_status:
                    return None
                if renderer_status.get("available"):
                    return None
                renderer_error = (renderer_status.get("error") or "").strip()
                hints = renderer_status.get("hints") or []
                if not hints:
                    return tr("No PDF renderer found.")
                if renderer_error:
                    return tr("{error}\\n\\nInstall one of:\\n{hints}").format(
                        error=renderer_error,
                        hints="\\n".join(" - {cmd}".format(cmd=entry) for entry in hints),
                    )
                return tr("No PDF renderer found. Install one of:\\n{hints}").format(
                    hints="\\n".join(" - {cmd}".format(cmd=entry) for entry in hints)
                )

            has_pdf_source = any(_is_pdf_path(entry) for entry in total_requests)
            has_non_pdf_source = any(not _is_pdf_path(entry) for entry in total_requests)
            pdf_status_hint = _format_pdf_renderer_hint()

            try:
                for input_path in total_requests:
                    if not input_path:
                        continue
                    processed, error = _process_single_file(input_path)
                    if error:
                        failed_sources.append((_clean_source_name(input_path), error))
                        self.logger.error(
                            "Batch OCR source failed: '{source}' -> {error}".format(
                                source=input_path,
                                error=error,
                            )
                        )
                        continue

                    if processed is None:
                        continue

                    if isinstance(processed, tuple):
                        batch_results.append(processed)
                    else:
                        batch_results.extend(processed)
                    processed_sources += 1

            finally:
                try:
                    from tejocr import tejocr_pdf as pdf_module
                    pdf_module.cleanup_temp_images(temp_image_paths)
                except Exception:
                    pass

            if not batch_results:
                self.logger.warning("Batch OCR completed with no successful recognition results.")
                failure_message = _build_batch_failures_text(failed_sources)
                pdf_hint = nonlocal_pdf_renderer_hint["value"]
                if pdf_hint:
                    if "No PDF renderer found" in str(pdf_hint):
                        runtime_hint = _format_pdf_renderer_hint() or str(pdf_hint)
                        if runtime_hint:
                            failure_message = tr("{hint}\n\n{details}").format(
                                hint=runtime_hint,
                                details=_build_batch_failures_text(failed_sources),
                            )
                    else:
                        failure_message = tr(
                            "PDF rendering is not available for at least one PDF input. "
                            "Original error: {error}"
                        ).format(error=pdf_hint)
                        if failure_message:
                            failure_message = tr("{hint}\n\n{details}").format(
                                hint=failure_message,
                                details=_build_batch_failures_text(failed_sources),
                            )
                elif pdf_status_hint and has_pdf_source:
                    failure_message = tr("{hint}\n\n{details}").format(
                        hint=pdf_status_hint,
                        details=_build_batch_failures_text(failed_sources),
                    )
                uno_utils.show_message_box(
                    tr("OCR Result"),
                    tr("OCR produced no text across {count} selected source(s).\\n\\n{failures}").format(
                        count=len(total_requests),
                        failures=failure_message,
                    ),
                    "warningbox",
                    parent_frame=self.frame,
                    ctx=self.ctx,
                )
                return

            combined_text = _build_output_text_for_batch(batch_results, tr=tr)
            total_chars = len(combined_text or "")
            source_summary = _build_preprocessing_summary(options)
            preview_text = combined_text
            source_overview = []
            for source_label, source_text in batch_results:
                try:
                    source_len = len((source_text or "").strip())
                except Exception:
                    source_len = 0
                source_overview.append((str(source_label), source_len))
            source_names = [item[0] for item in source_overview]
            if source_names:
                source_summary = tr("Sources processed:") + "\n" + "\n".join(
                    "• {source}".format(source=source_name) for source_name in source_names
                ) + "\n" + source_summary

            file_count, pdf_count, image_count = _count_files_by_type(total_requests)
            source_file_count_text = _format_batch_title(
                total_files=file_count,
                pdf_count=pdf_count,
                image_count=image_count,
            )

            merge_batch = _coerce_bool(options.get("merge_batch_results", True))
            show_preview = _coerce_bool(ocr_options.get("show_preview", None))
            if "show_preview" not in ocr_options:
                show_preview = _coerce_bool(
                    uno_utils.get_setting(
                        constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                        constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                        self.ctx,
                    )
                )

            force_merge_review = False
            if show_preview and len(total_requests) > 1:
                if not uno_utils.supports_uno_dialog_model(self.ctx):
                    force_merge_review = True
                elif len(total_requests) > 2:
                    force_merge_review = True

            if force_merge_review and not merge_batch:
                self.logger.info(
                    "Forcing merged batch review for {count} selected source(s) because per-source review would be impractical.".format(
                        count=len(total_requests)
                    )
                )
                merge_batch = True

            if show_preview:
                if not force_merge_review and len(combined_text or "") > 9000:
                    force_merge_review = True
                source_lines = [
                    tr("Source {index}: {source} ({length} chars)").format(
                        index=index,
                        source=source_label,
                        length=source_len,
                    )
                    for index, (source_label, source_len) in enumerate(source_overview, start=1)
                ]
                preview_title = source_file_count_text
                if force_merge_review:
                    preview_title = source_file_count_text + tr(" (single consolidated review)")
                merged_preview_max_chars = min(30000, max(2400, len(combined_text) + 120))
                preview_result = uno_utils.show_multiline_input_box(
                    title=preview_title,
                    message=tr(
                        "Review or edit the recognized text before inserting.\\n"
                        "Click OK to continue, Cancel to stop."
                    ),
                    default_text=combined_text,
                    ctx=self.ctx,
                    parent_frame=self.frame,
                )
                if preview_result is None:
                    preview_result = uno_utils.show_ocr_preview_fallback(
                        preview_title,
                        combined_text,
                        ctx=self.ctx,
                        parent_frame=self.frame,
                        max_chars=merged_preview_max_chars,
                        source_lines=source_lines,
                    )
                if preview_result is None:
                    self.logger.info("User cancelled OCR workflow at batch preview stage.")
                    uno_utils.show_message_box(
                        tr("OCR Canceled"),
                        tr("OCR output was cancelled by user."),
                        "infobox",
                        parent_frame=self.frame,
                        ctx=self.ctx,
                    )
                    return
                preview_text = preview_result

            if merge_batch:
                if output_mode == constants.OUTPUT_MODE_REPLACE and source_type == "selected":
                    merge_batch = False
                _route_batch_output(preview_text)
            else:
                if show_preview:
                    preview_note = (
                        tr("Merge mode is disabled for this run.\\n")
                        + tr("Will process {source_count} item(s) as separate insertions.").format(
                            source_count=len(batch_results)
                        )
                    )
                    uno_utils.show_message_box(
                        tr("Batch OCR"),
                        preview_note,
                        "infobox",
                        parent_frame=self.frame,
                        ctx=self.ctx,
                    )

                for source_label, source_text in batch_results:
                    item_text = source_text or ""
                    preview_result = item_text
                    if show_preview and item_text:
                        source_name = source_label or tr("Source")
                        preview_result = uno_utils.show_multiline_input_box(
                            title=tr("Review OCR result - {source}").format(source=source_label),
                            message=tr(
                                "Review or edit text for: {source}\\n\\nClick OK to continue, Cancel to stop."
                            ).format(source=source_label),
                            default_text=item_text,
                            ctx=self.ctx,
                            parent_frame=self.frame,
                        )
                        if preview_result is None:
                            preview_result = uno_utils.show_ocr_preview_fallback(
                                tr("Review OCR result - {source}").format(source=source_name),
                                item_text,
                                ctx=self.ctx,
                                parent_frame=self.frame,
                                max_chars=min(30000, max(2400, len(item_text) + 120)),
                                source_lines=[
                                    tr("Source: {source} ({length} chars)").format(
                                        source=source_name,
                                        length=len((item_text or "").strip()),
                                    )
                                ],
                            )
                        if preview_result is None:
                            self.logger.info("User cancelled OCR workflow during per-item batch preview.")
                            uno_utils.show_message_box(
                                tr("OCR Canceled"),
                                tr("OCR output was cancelled by user."),
                                "infobox",
                                parent_frame=self.frame,
                                ctx=self.ctx,
                            )
                            return

                    _route_batch_output(preview_result)

            mode_description = {
                constants.OUTPUT_MODE_CURSOR: tr("inserted at cursor"),
                constants.OUTPUT_MODE_CLIPBOARD: tr("copied to clipboard"),
                constants.OUTPUT_MODE_TEXTBOX: tr("added to new text box"),
                constants.OUTPUT_MODE_REPLACE: tr("replaced the selected image"),
            }.get(output_mode, tr("processed"))

            source_digest_lines = [
                tr("• {source} ({length} chars)").format(source=src, length=length)
                for src, length in source_overview[:40]
            ]
            if len(source_overview) > 40:
                source_digest_lines.append(
                    tr("• ... and {count} more source(s).").format(count=len(source_overview) - 40)
                )
            source_digest = "\n".join(source_digest_lines) if source_digest_lines else tr("No source details available.")

            extraction_summary = (
                tr("Language: {language}\nPreset: {preset}\nOptions:\n{processing}").format(
                    language=options["lang"],
                    preset=_format_preset_for_summary(options["preset"]),
                    processing=source_summary,
                )
            )
            failure_summary = (
                tr("\n\nSome sources failed:\n{failures}").format(
                    failures="\n".join([f"• {item}: {reason}" for item, reason in failed_sources[:5]])
                )
                if failed_sources
                else ""
            )

            uno_utils.show_message_box(
                tr("OCR Complete"),
                tr(
                    "Successfully extracted {char_count} characters from {file_count} source(s) and {mode_description}.\n\n"
                    "Source breakdown:\n{source_breakdown}\n\n{summary}{failures}"
                ).format(
                    char_count=total_chars,
                    file_count=processed_sources,
                    source_breakdown=source_digest,
                    mode_description=mode_description,
                    summary=extraction_summary,
                    failures=failure_summary,
                ),
                "infobox",
                parent_frame=self.frame,
                ctx=self.ctx,
            )
        except Exception as e:
            self.logger.error(f"Batch OCR failed: {e}", exc_info=True)
            uno_utils.show_message_box(
                tr("OCR Error"),
                tr("An unexpected error occurred during batch OCR: {error}").format(error=str(e)),
                "errorbox",
                parent_frame=self.frame,
                ctx=self.ctx,
            )

    def _perform_ocr_with_options(
        self,
        source_type,
        image_path,
        language,
        output_mode,
        ocr_options=None,
        insertion_anchor=None,
        replacement_target=None,
    ):
        """Perform OCR with the specified options, including image improvement."""
        try:
            if not _ensure_modules_loaded(self, engine=True, output=True):
                self.logger.error("Perform OCR: Engine or Output module could not be loaded.")
                return
            
            # Provide smart defaults for None values
            defaults = _build_default_ocr_options(self.ctx)
            if not ocr_options:
                ocr_options = defaults.copy()
            
            language = _normalize_language_request(language or ocr_options.get("lang"))
            if not language:
                language = defaults["lang"]
            output_mode = _coerce_output_mode(output_mode, defaults["output_mode"])
            if output_mode not in (constants.OUTPUT_MODE_CURSOR, constants.OUTPUT_MODE_CLIPBOARD, constants.OUTPUT_MODE_TEXTBOX, constants.OUTPUT_MODE_REPLACE):
                output_mode = defaults["output_mode"]
            if source_type != "selected" and output_mode == constants.OUTPUT_MODE_REPLACE:
                self.logger.debug("Replace Image output mode requested for file OCR; falling back to cursor insertion.")
                output_mode = constants.OUTPUT_MODE_CURSOR
            if ocr_options is None:
                ocr_options = defaults.copy()
            
            options = {
                "lang": language,
                "psm": str(ocr_options.get("psm", defaults["psm"])).strip() or defaults["psm"],
                "oem": str(ocr_options.get("oem", defaults["oem"])).strip() or defaults["oem"],
                "scale": _coerce_scale(ocr_options.get("scale"), defaults.get("scale")),
                "grayscale": _coerce_bool(ocr_options.get("grayscale", defaults.get("grayscale", False))),
                "binarize": _coerce_bool(ocr_options.get("binarize", defaults.get("binarize", False))),
                "invert": _coerce_bool(ocr_options.get("invert", defaults.get("invert", False))),
                "improve_image": _coerce_bool(ocr_options.get("improve_image", defaults.get("improve_image", False))),
                "preset": _coerce_preset_request(ocr_options.get("preset"), defaults.get("preset")),
                "show_preview": _coerce_bool(ocr_options.get("show_preview", defaults.get("show_preview"))),
                "merge_batch_results": _coerce_bool(
                    ocr_options.get("merge_batch_results", defaults.get("merge_batch_results"))
                ),
            }

            _persist_last_ocr_preferences(
                self.ctx,
                options["lang"],
                output_mode,
                options.get("merge_batch_results"),
            )
            
            self.logger.info(f"Using OCR settings: {options}")
            
            self.logger.info(
                f"Performing OCR: source='{source_type}', lang='{language}', mode='{output_mode}', "
                f"improve='{options['improve_image']}', invert='{options['invert']}', "
                f"psm='{options['psm']}', oem='{options['oem']}', scale='{options['scale']}'"
            )
            text = None # Initialize text
            source_description = _("unknown source") # Default source description

            # Perform OCR based on source type, now passing improve_image to engine methods
            source_message = ""
            if source_type == "selected":
                result = _tejocr_engine_module.perform_ocr(
                    self.ctx, self.frame, "selected", None, options
                )
                if result.get("success"):
                    text = result.get("text")
                    source_message = result.get("message", "") or ""
                else:
                    self.logger.error(f"perform_ocr failed for selected image: {result.get('message')}")
                source_description = _("selected image")
            elif source_type == "file": # Ensure this is 'elif' for clarity if more source types are added later
                result = _tejocr_engine_module.perform_ocr(
                    self.ctx, self.frame, "file", image_path, options
                )
                if result.get("success"):
                    text = result.get("text")
                    source_message = result.get("message", "") or ""
                else:
                    self.logger.error(f"perform_ocr failed for file image: {result.get('message')}")
                source_description = f"'{os.path.basename(image_path)}'"
            else:
                self.logger.error(f"Unknown source_type for OCR: {source_type}")
                uno_utils.show_message_box(
                    _("OCR Error"),
                    _("Internal error: Unknown OCR source specified."),
                    "errorbox", parent_frame=self.frame, ctx=self.ctx
                )
                return
            
            if text is not None and text != "": # Check for None, as empty string is a valid (no text found) result
                # Handle output based on chosen mode with proper fallback
                self.logger.info(f"OCR extracted {len(text)} characters, routing to output mode: {output_mode}")

                preview_text = text
                show_preview = _coerce_bool(ocr_options.get("show_preview", None))
                if "show_preview" not in ocr_options:
                    show_preview = _coerce_bool(
                        uno_utils.get_setting(
                            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                            constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                            self.ctx,
                        )
                    )
                if show_preview:
                    preview_result = uno_utils.show_multiline_input_box(
                        title=_("Review OCR result"),
                        message=_(
                            "Review or edit the recognized text before inserting.\n"
                            "Click OK to continue, Cancel to stop."
                        ),
                        default_text=text,
                        ctx=self.ctx,
                        parent_frame=self.frame,
                    )
                    if preview_result is None:
                        preview_result = uno_utils.show_ocr_preview_fallback(
                            _("Review OCR result"),
                            text,
                            ctx=self.ctx,
                            parent_frame=self.frame,
                        )

                    if preview_result is None:
                        self.logger.info("User cancelled OCR workflow at preview stage.")
                        uno_utils.show_message_box(
                            _("OCR Canceled"),
                            _("OCR output was cancelled by user."),
                            "infobox",
                            parent_frame=self.frame,
                            ctx=self.ctx,
                        )
                        return

                    preview_text = preview_result

                text = preview_text if preview_text is not None else text
                
            try:
                output_result = None
                if output_mode == constants.OUTPUT_MODE_CURSOR:
                    output_result = _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        text,
                        constants.OUTPUT_MODE_CURSOR,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                    )
                elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
                    output_result = _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CLIPBOARD)
                elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
                    output_result = _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        text,
                        constants.OUTPUT_MODE_TEXTBOX,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                    )
                elif output_mode == constants.OUTPUT_MODE_REPLACE:
                    output_result = _tejocr_output_module.handle_ocr_output(
                        self.ctx,
                        self.frame,
                        text,
                        constants.OUTPUT_MODE_REPLACE,
                        insertion_anchor=insertion_anchor if source_type == "selected" else None,
                        replacement_target=replacement_target,
                    )
                    if output_result is not True and source_type == "selected":
                        self.logger.warning(
                            "Replace image mode failed (no valid target). Falling back to cursor insertion."
                        )
                        output_mode = constants.OUTPUT_MODE_CURSOR
                        output_result = _tejocr_output_module.handle_ocr_output(
                            self.ctx,
                            self.frame,
                            text,
                            constants.OUTPUT_MODE_CURSOR,
                            insertion_anchor=insertion_anchor if source_type == "selected" else None,
                        )
                else:
                    # Fallback for unknown output modes
                    self.logger.warning(f"Unknown output mode '{output_mode}', defaulting to cursor")
                    output_result = _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CURSOR)
                    output_mode = constants.OUTPUT_MODE_CURSOR
            except Exception as output_error:
                self.logger.error(f"Error in output handling: {output_error}", exc_info=True)
                # Fallback: try clipboard as it's most universal
                try:
                    self.logger.info("Attempting clipboard fallback after output error")
                    _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CLIPBOARD)
                    output_mode = constants.OUTPUT_MODE_CLIPBOARD
                    uno_utils.show_message_box(
                        _("Output Warning"),
                        _("Primary output method failed. Text has been copied to clipboard instead."),
                        "warningbox", parent_frame=self.frame, ctx=self.ctx
                    )
                except Exception as fallback_error:
                    self.logger.error(f"Even clipboard fallback failed: {fallback_error}", exc_info=True)
                    uno_utils.show_message_box(
                        _("Output Error"),
                        _("Could not output OCR text. Extracted text:\n\n{text}").format(text=text[:200] + "..." if len(text) > 200 else text),
                        "errorbox", parent_frame=self.frame, ctx=self.ctx
                    )
                    return
            if text is not None and text != "": # OCR branch already true at this point
                char_count = len(text)
                mode_description = {
                    constants.OUTPUT_MODE_CURSOR: _("inserted at cursor"),
                    constants.OUTPUT_MODE_CLIPBOARD: _("copied to clipboard"), 
                    constants.OUTPUT_MODE_TEXTBOX: _("added to new text box"),
                    constants.OUTPUT_MODE_REPLACE: _("replaced the selected image"),
                }.get(output_mode, _("processed"))

                extraction_summary = (
                    _("Language: {language}\nPreset: {preset}\nOptions: {processing}").format(
                        language=options["lang"],
                        preset=_format_preset_for_summary(options["preset"]),
                        processing=_build_preprocessing_summary(options),
                    )
                )
                uno_utils.show_message_box(
                    _("OCR Complete"), 
                    _("Successfully extracted {char_count} characters from {source_description} and {mode_description}.\n\n{summary}").format(
                        char_count=char_count, 
                        source_description=source_description, 
                        mode_description=mode_description,
                        summary=extraction_summary,
                    ), 
                    "infobox", 
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
            elif text == "": # OCR completed but nothing recognized
                self.logger.warning(f"OCR engine returned empty text for {source_description}.")
                no_text_recommendations = [
                    _("Use a clearer image with higher contrast."),
                    _("Try scale 1.5 (or greater) with preset Accuracy."),
                    _("Enable grayscale and binarization, or improve_image=true."),
                    _("Confirm language code(s) match the document script, e.g. eng+hin."),
                ]
                recommendation_text = "\n".join([
                    _("Recommended next steps:"),
                    *[f"• {step}" for step in no_text_recommendations],
                ])
                source_summary = _build_preprocessing_summary(options)
                uno_utils.show_message_box(
                    _("OCR Result"), 
                    _("No text was extracted from {source_description}.\n\n{message}\n\n{recommendations}\n\n{summary}").format(
                        source_description=source_description,
                        message=(
                            _("Try a clearer image, higher scale, or different preset (for example Accuracy).")
                            if not source_message
                            else source_message
                        ),
                        recommendations=recommendation_text,
                        summary=source_summary
                    ),
                    "warningbox", # Changed to warningbox as this is more than just no text
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
            else: # This means OCR engine returned None (e.g. error during OCR)
                self.logger.warning(f"OCR engine returned None for {source_description}. An error might have occurred.")
                uno_utils.show_message_box(
                    _("OCR Result"), 
                    _("Could not extract text from {source_description}. The image might be invalid or an OCR error occurred. Check logs for details.").format(source_description=source_description), 
                    "warningbox", # Changed to warningbox as this is more than just no text
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
        except Exception as e:
            self.logger.error(f"OCR processing failed: {e}", exc_info=True)
            uno_utils.show_message_box(
                _("OCR Error"), 
                _("OCR processing failed: {error}").format(error=str(e)), 
                "errorbox", 
                parent_frame=self.frame, 
                ctx=self.ctx
            )

    def _handle_settings(self):
        self.logger.info("Handling Settings action.")
        
        # Ensure OCR engine is loaded for dependency checks inside the dialog code path.
        if not _ensure_modules_loaded(self, engine=True):
            self.logger.error("Settings: Critical module (Engine) could not be loaded.")
            # Message box would have been shown by _ensure_modules_loaded
            return

        try:
            self.logger.info("Opening settings with XDL-backed handler.")
            # Use the shared settings entrypoint from tejocr_dialogs.
            from tejocr import tejocr_dialogs
            success = tejocr_dialogs.show_settings_dialog(self.ctx, self.frame)
            
            if success: # show_dialog returns True if settings were saved
                uno_utils.show_message_box(
                    _("Settings Saved"), 
                    _("Settings have been saved successfully! Some changes may require a LibreOffice restart to take full effect."), 
                    "infobox", 
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
            else: # Dialog was cancelled or an explicit False was returned (e.g. no changes made and user confirmed not to save)
                self.logger.info("Settings dialog was cancelled or an explicit choice was made not to save settings.")
                # Optionally inform user settings were not saved if it wasn't just a cancel
                # uno_utils.show_message_box(
                #     _("Settings Unchanged"),
                #     _("Settings were not saved."),
                #     "infobox", parent_frame=self.frame, ctx=self.ctx
                # )
                
        except Exception as e_settings:
            self.logger.critical(f"Critical error displaying or processing interactive settings: {e_settings}", exc_info=True)
            uno_utils.show_message_box(
                title=_("Settings Error"), 
                message=_("An unexpected error occurred while trying to show settings: {error}. Please check logs for details.").format(error=str(e_settings)), 
                type="errorbox", 
                parent_frame=self.frame, 
                ctx=self.ctx
            )

    def addStatusListener(self, Listener, URL):
        self.logger.debug(f"addStatusListener CALLED for URL: {URL.Complete if URL else 'None'}")
        if not _ensure_modules_loaded(self): 
            self.logger.warning("addStatusListener: Critical modules not loaded, cannot determine status.")
            # Potentially disable the command if modules can't load
            if Listener and hasattr(Listener, "statusChanged"):
                status_event = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
                status_event.FeatureURL = URL
                status_event.IsEnabled = False
                status_event.State = None # No specific state to set
                Listener.statusChanged(status_event)
            return

        status_event = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
        status_event.FeatureURL = URL
        status_event.IsEnabled = False # Default to disabled
        status_event.State = None # No specific state to set, can be used for checkmarks etc.

        if self._matches_command_url(URL, DISPATCH_URL_OCR_SELECTED):
            # OCR Selected Image should be enabled only if a graphic is selected
            if self.frame and uno_utils.is_graphic_object_selected(self.frame, self.ctx):
                status_event.IsEnabled = True
            else:
                status_event.IsEnabled = False # Explicitly disable if no graphic selected
            self.logger.debug(f"Status for OCR_SELECTED: IsEnabled={status_event.IsEnabled}")

        elif self._matches_command_url(URL, DISPATCH_URL_OCR_FROM_FILE) or \
             self._matches_command_url(URL, DISPATCH_URL_SETTINGS):
            # OCR from File and Settings are always enabled if the service is active and document is TextDocument
            status_event.IsEnabled = True 
            self.logger.debug(f"Status for {URL.Complete}: IsEnabled=True (always on for TextDocument)")

        elif self._matches_command_url(URL, DISPATCH_URL_TOOLBAR_ACTION):
            # Toolbar action is always enabled, its behavior depends on selection.
            status_event.IsEnabled = True
            self.logger.debug(f"Status for TOOLBAR_ACTION: IsEnabled=True")
        else:
            self.logger.debug(f"Status for UNKNOWN URL {URL.Complete}: IsEnabled=False by default")

        if Listener and hasattr(Listener, "statusChanged"):
            Listener.statusChanged(status_event)
        else:
            self.logger.warning(f"Status listener invalid or missing statusChanged for URL: {URL.Complete}")

    def removeStatusListener(self, Listener, URL):
        self.logger.debug(f"removeStatusListener for URL: {URL.Complete if URL and hasattr(URL, 'Complete') else 'Invalid/None URL'}")
        # Standard implementation is often empty if not managing listeners explicitly.
        pass

# UNO Component Registration
# This is the function LibreOffice looks for when registering the component.
# It must be named exactly as specified (g_ImplementationHelper or createInstance).
# unohelper.ImplementationHelper is common for older style, direct function more modern.

# We need to ensure that this part is correctly picked up by LibreOffice.
# The manifest.xml points to this file as a "uno-component;type=Python".
# LibreOffice will then look for specific factory functions.
# Common ones are g_ImplementationHelper or createInstance.
# Let's use g_ImplementationHelper for broad compatibility, as it's well-established.

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    TejOCRService, # The class that implements the service
    IMPLEMENTATION_NAME, # The unique name of this implementation
    (SERVICE_NAME,), # Tuple of service names it supports
)

# For debugging: Confirm registration attempt.
# This print will only execute if the script itself is parsed correctly up to this point.
if logger: # Check if logger was successfully initialized earlier
    logger.debug(f"TejOCRService ADDED to ImplementationHelper: IMPL_NAME={IMPLEMENTATION_NAME}, SVC_NAME={SERVICE_NAME}")

# Final log message for script execution span
if logger:
    logger.debug("tejocr_service.py: Script execution finished parsing (bottom level).")
