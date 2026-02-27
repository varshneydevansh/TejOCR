# -*- coding: utf-8 -*-
print("DEBUG: tejocr_service.py: Script execution started (top level)")

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
        print(f"DEBUG: tejocr_service.py: Added '{python_dir_in_oxt}' to sys.path.")
    else:
        print(f"DEBUG: tejocr_service.py: '{python_dir_in_oxt}' already in sys.path.")
except Exception as e_sys_path:
    print(f"DEBUG: tejocr_service.py: Error modifying sys.path: {e_sys_path}")
# --- End of Python Path Modification ---

try:
    print("DEBUG: tejocr_service.py: Attempting initial imports...")
    import uno
    import unohelper
    import os
    print("DEBUG: tejocr_service.py: uno, unohelper imported.")
    from com.sun.star.frame import XDispatchProvider, XDispatch
    from com.sun.star.lang import XServiceInfo, XInitialization
    from com.sun.star.beans import PropertyValue
    print("DEBUG: tejocr_service.py: com.sun.star imports successful.")

    print("DEBUG: tejocr_service.py: Attempting package imports (should be absolute from 'tejocr')...")
    # Now that 'python/' (containing 'tejocr/') should be on sys.path,
    # we can import 'tejocr' as if it's a top-level package.
    from tejocr import uno_utils
    print("DEBUG: tejocr_service.py: uno_utils imported.")
    from tejocr import constants
    print("DEBUG: tejocr_service.py: constants imported.")
    from tejocr import locale_setup
    print("DEBUG: tejocr_service.py: locale_setup imported.")
    
    # Set up internationalization function
    try:
        _ = locale_setup.get_translation_function()
    except:
        # Fallback if locale setup fails
        def _(text):
            return text
    
    print("DEBUG: tejocr_service.py: All 'from tejocr import ...' imports successful.")

except ImportError as e_imp:
    print(f"DEBUG: tejocr_service.py: IMPORT ERROR during initial imports: {e_imp}")
    import traceback
    print(traceback.format_exc())
    # Set up fallback _ function
    def _(text):
        return text
    raise
except Exception as e_gen:
    print(f"DEBUG: tejocr_service.py: GENERAL ERROR during initial imports: {e_gen}")
    import traceback
    print(traceback.format_exc())
    # Set up fallback _ function
    def _(text):
        return text
    raise

# Initialize logger for this module
try:
    logger = uno_utils.get_logger("TejOCR.Service") # This now uses the imported uno_utils
    print("DEBUG: tejocr_service.py: Logger initialized.")
except Exception as e_log:
    print(f"DEBUG: tejocr_service.py: Error initializing logger: {e_log}")
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


def _build_default_ocr_options(ctx):
    """Load OCR defaults from settings for dialog pre-fills and OCR fallback."""
    output_mode_preference = _resolve_output_mode_preference(ctx)
    return {
        "lang": _normalize_language_request(
            uno_utils.get_setting(
                constants.CFG_KEY_LAST_SELECTED_LANG,
                uno_utils.get_setting(
                    constants.CFG_KEY_DEFAULT_LANG,
                    constants.DEFAULT_OCR_LANGUAGE,
                    ctx,
                ),
                ctx,
            )
        ),
        "psm": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, ctx),
        "oem": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, ctx),
        "scale": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx),
        "grayscale": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, constants.DEFAULT_PREPROC_GRAYSCALE, ctx),
        "binarize": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, constants.DEFAULT_PREPROC_BINARIZE, ctx),
        "invert": uno_utils.get_setting(constants.CFG_KEY_DEFAULT_INVERT, str(constants.DEFAULT_PREPROC_INVERT), ctx),
        "improve_image": uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx),
        "output_mode": output_mode_preference,
        "preset": _coerce_preset_request(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PRESET, constants.DEFAULT_OCR_PRESET, ctx),
            constants.DEFAULT_OCR_PRESET,
        ),
        "show_preview": uno_utils.get_setting(
            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
            constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
            ctx,
        ),
    }


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
        return bool(value)
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
        "preset": selected_preset,
        "language_warning": language_warning,
    }


def _persist_last_ocr_preferences(ctx, language, output_mode):
    """Persist run-time choices so next time dialogs open with user's last used values."""
    try:
        normalized_lang = _normalize_language_request(language)
        if normalized_lang:
            uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, normalized_lang, ctx)
        normalized_output = _coerce_output_mode(output_mode, constants.DEFAULT_OUTPUT_MODE)
        if normalized_output:
            uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, normalized_output, ctx)
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
        print("=" * 50)
        print("DIRECT PRINT: _test_url_matching called")
        self.logger.debug("_test_url_matching: Testing URL matching...")
        try:
            # Create a mock URL for testing
            from com.sun.star.util import URL as UnoURL
            test_url = UnoURL()
            test_url.Complete = DISPATCH_URL_OCR_SELECTED
            test_url.Protocol = "uno:"
            test_url.Path = DISPATCH_URL_OCR_SELECTED[4:] # Without protocol
            test_url.Main = DISPATCH_URL_OCR_SELECTED[4:] # Without protocol
            
            print(f"DIRECT PRINT: Created test URL: {test_url.Complete}")
            
            # Now test our matching method
            for cmd in [DISPATCH_URL_OCR_SELECTED, DISPATCH_URL_OCR_FROM_FILE, DISPATCH_URL_SETTINGS, DISPATCH_URL_TOOLBAR_ACTION]:
                result = self._matches_command_url(test_url, cmd)
                print(f"DIRECT PRINT: _matches_command_url result for {cmd}: {result}")
                self.logger.debug(f"_test_url_matching: matching '{test_url.Complete}' against '{cmd}': {result}")
                
            # Test our dispatch method
            result = self.queryDispatch(test_url, "_self", 0)
            print(f"DIRECT PRINT: queryDispatch returned: {result is not None}")
            self.logger.debug(f"_test_url_matching: queryDispatch test URL result: {result is not None}")
            
            # Also test with a different command
            test_url.Complete = DISPATCH_URL_OCR_FROM_FILE
            test_url.Path = DISPATCH_URL_OCR_FROM_FILE[4:]
            result = self.queryDispatch(test_url, "_self", 0)
            print(f"DIRECT PRINT: queryDispatch with OCR_FROM_FILE returned: {result is not None}")
            
        except Exception as e:
            print(f"DIRECT PRINT: _test_url_matching error: {e}")
            self.logger.error(f"_test_url_matching error: {e}", exc_info=True)
        print("=" * 50)

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
            dialog_result = options_handler.show_dialog()
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
        self.logger.info("Handling OCR Image from File action.")

        # Ensure interactive dialogs module is loaded (and engine for language list)
        if not _ensure_modules_loaded(self, dialogs=True, engine=True):
            self.logger.error("OCR From File: Dialogs or Engine module could not be loaded.")
            return
        
        try:
            file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
            if not file_picker:
                uno_utils.show_message_box(_("Error"), _("Could not create file picker."), "errorbox", parent_frame=self.frame, ctx=self.ctx)
                return

            file_picker.setTitle(_("Select Image for OCR"))
            file_picker.appendFilter(_("Image Files (*.png, *.jpg, *.jpeg, *.bmp, *.gif, *.tif, *.tiff)"), constants.IMAGE_FILE_DIALOG_FILTER)
            file_picker.appendFilter(_("All Files (*.*)"), "*.*") # Corrected filter string
            
            if file_picker.execute() == uno_utils.OK_BUTTON:  # Use constant for clarity
                selected_files = file_picker.getFiles()
                if selected_files:
                    image_path = unohelper.fileUrlToSystemPath(selected_files[0]) # Fixed: use unohelper, not uno_utils
                    self.logger.info(f"Selected image file: {image_path}")
                    
                    self.logger.info("Showing interactive OCR options dialog for file...")
                    options_handler = _tejocr_interactive_dialogs_module.InteractiveOptionsDialogHandler(
                        self.ctx, self.frame, "file", image_path
                    )
                    dialog_result = options_handler.show_dialog()
                    
                    # Smart defaults when dialog fails or user cancels
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
                            _("Language Warning"),
                            language_warning,
                            "warningbox",
                            parent_frame=self.frame,
                            ctx=self.ctx,
                        )
                    
                    self.logger.info(
                        f"OCR Options for file (final): Lang='{language}', Mode='{output_mode}', "
                        f"Improve='{improve_image}', PSM='{ocr_options['psm']}', OEM='{ocr_options['oem']}'"
                    )
                        
                    self._perform_ocr_with_options("file", image_path, language, output_mode, ocr_options)
            else:
                self.logger.info("File selection cancelled by user.")
                
        except Exception as e:
            self.logger.error(f"Error during interactive OCR from file: {e}", exc_info=True)
            uno_utils.show_message_box(
                title=_("OCR Error"),
                message=_("An unexpected error occurred while selecting the file or performing OCR: {error}").format(error=str(e)),
                type="errorbox", parent_frame=self.frame, ctx=self.ctx
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
            }

            _persist_last_ocr_preferences(self.ctx, options["lang"], output_mode)
            
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
    logger.info(f"TejOCRService ADDED to ImplementationHelper: IMPL_NAME={IMPLEMENTATION_NAME}, SVC_NAME={SERVICE_NAME}")
else: # Fallback if logger is still not initialized (shouldn't happen ideally)
    print(f"CRITICAL FALLBACK PRINT: tejocr_service.py: Logger not available at component registration. Attempting to register TejOCRService. IMPL_NAME={IMPLEMENTATION_NAME}, SVC_NAME={SERVICE_NAME}")

# Final log message for script execution span
if logger:
    logger.info("tejocr_service.py: Script execution finished parsing (bottom level).")
else:
    print("INFO FALLBACK PRINT: tejocr_service.py: Script execution finished parsing (bottom level, logger not available).")
