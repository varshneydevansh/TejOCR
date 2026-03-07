# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Working interactive dialogs for TejOCR using UNO dialog toolkit."""

import uno
import unohelper
import os
import sys
import platform
from com.sun.star.awt import XActionListener

from tejocr import uno_utils
from tejocr import constants
from tejocr import ocr_runtime
from tejocr import tejocr_engine 
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext
logger = uno_utils.get_logger("TejOCR.InteractiveDialogs")


def _build_mode_items(mode_map):
    return tuple([f"{key}: {value.split(':', 1)[1].strip() if ':' in value else value}" for key, value in mode_map.items()])


def _get_psm_mode_map(ctx=None):
    try:
        return dict(tejocr_engine.get_runtime_psm_modes(ctx=ctx) or constants.TESSERACT_PSM_MODES)
    except Exception:
        return dict(constants.TESSERACT_PSM_MODES)


def _get_oem_mode_map(ctx=None):
    try:
        return dict(tejocr_engine.get_runtime_oem_modes(ctx=ctx) or constants.TESSERACT_OEM_MODES)
    except Exception:
        return dict(constants.TESSERACT_OEM_MODES)


def _get_oem_support_map(ctx=None):
    try:
        return dict(
            tejocr_engine.get_supported_oem_modes(ctx=ctx)
            or {mode: True for mode in constants.TESSERACT_OEM_MODES}
        )
    except Exception:
        return {mode: True for mode in constants.TESSERACT_OEM_MODES}


def _coerce_supported_oem_value(mode_value, ctx=None, support_map=None, fallback=None):
    fallback_value = str(fallback or constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
    candidate = _mode_value(mode_value, fallback_value)
    if candidate not in constants.TESSERACT_OEM_MODES:
        candidate = fallback_value
    return ocr_runtime.coerce_supported_oem(
        candidate,
        support_map or _get_oem_support_map(ctx),
        fallback=fallback_value,
    )


def _get_psm_items(ctx=None):
    return _build_mode_items(_get_psm_mode_map(ctx))


def _get_oem_items(ctx=None):
    return _build_mode_items(_get_oem_mode_map(ctx))


def _get_mode_text(mode_map, mode_value, fallback_value):
    candidate = str(mode_value or fallback_value).strip() or fallback_value
    if candidate not in mode_map:
        candidate = str(fallback_value or "").strip() or candidate
    label = mode_map.get(candidate, "{mode}: {text}".format(mode=candidate, text=candidate))
    if ":" not in label:
        label = "{mode}: {text}".format(mode=candidate, text=label)
    return candidate, label


def _mode_value(raw_value, fallback):
    if not raw_value:
        return fallback
    candidate = str(raw_value).strip()
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0].strip()
    return candidate if candidate else fallback


def _output_mode_label(mode_value):
    mapping = {
        constants.OUTPUT_MODE_CURSOR: _("Insert at cursor"),
        constants.OUTPUT_MODE_CLIPBOARD: _("Copy to clipboard"),
        constants.OUTPUT_MODE_TEXTBOX: _("New text box"),
        constants.OUTPUT_MODE_REPLACE: _("Replace image"),
    }
    return mapping.get(mode_value, _("New text box"))


def _output_mode_combo_item(mode_value):
    return f"{mode_value}: {_output_mode_label(mode_value)}"


def _output_mode_from_text(raw_text, fallback):
    if not raw_text:
        return fallback
    raw_text_str = str(raw_text).strip()
    if not raw_text_str:
        return fallback

    token = raw_text_str.split(":", 1)[0].strip().lower().replace("-", "_").replace("  ", " ")
    token = " ".join(token.split())
    text = raw_text_str.lower().replace("-", "_").replace("  ", " ")
    text = " ".join(text.split())
    normalized_token = token.replace(" ", "_")
    token = normalized_token
    normalized_text = text.replace(" ", "_")
    normalized = {
        "at_cursor": constants.OUTPUT_MODE_CURSOR,
        "cursor": constants.OUTPUT_MODE_CURSOR,
        "insert": constants.OUTPUT_MODE_CURSOR,
        "insert at cursor": constants.OUTPUT_MODE_CURSOR,
        "insert_at_cursor": constants.OUTPUT_MODE_CURSOR,
        "clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "copy": constants.OUTPUT_MODE_CLIPBOARD,
        "copy to clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "copy_to_clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "new_textbox": constants.OUTPUT_MODE_TEXTBOX,
        "textbox": constants.OUTPUT_MODE_TEXTBOX,
        "text box": constants.OUTPUT_MODE_TEXTBOX,
        "new text box": constants.OUTPUT_MODE_TEXTBOX,
        "new_text_box": constants.OUTPUT_MODE_TEXTBOX,
        "to_clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        "replace_image": constants.OUTPUT_MODE_REPLACE,
        "replace": constants.OUTPUT_MODE_REPLACE,
        "replace image": constants.OUTPUT_MODE_REPLACE,
        "replace_image": constants.OUTPUT_MODE_REPLACE,
        constants.OUTPUT_MODE_CURSOR: constants.OUTPUT_MODE_CURSOR,
        constants.OUTPUT_MODE_TEXTBOX: constants.OUTPUT_MODE_TEXTBOX,
        constants.OUTPUT_MODE_CLIPBOARD: constants.OUTPUT_MODE_CLIPBOARD,
        constants.OUTPUT_MODE_REPLACE: constants.OUTPUT_MODE_REPLACE,
    }
    return normalized.get(normalized_text, normalized.get(token, fallback))


def _coerce_scale_text(raw_text, default):
    try:
        value = float(str(raw_text).strip()) if raw_text is not None else float(default)
        if value <= 0:
            return default
        return round(value, 2)
    except Exception:
        try:
            return float(default)
        except Exception:
            return 1.0


def _coerce_bool_text(raw_value, default=False):
    """Normalize yes/no style user input into a boolean with safe fallback."""
    if raw_value is None:
        return default
    normalized = str(raw_value).strip().lower()
    if not normalized:
        return default
    if normalized in ("true", "1", "yes", "y", "on", "enabled", "enable"):
        return True
    if normalized in ("false", "0", "no", "n", "off", "disabled", "disable"):
        return False
    return default


def _coerce_bool(raw_value, default=False):
    """Compatibility wrapper kept for internal callers and older runtime paths."""
    return _coerce_bool_text(raw_value, default)


def _parse_fallback_form_fields(raw_text):
    """Parse KEY=VALUE text entered in a fallback form."""
    key_aliases = {
        "default_language": "language",
        "default_lang": "language",
        "langs": "language",
        "languages": "language",
        "language_codes": "language",
        "lang": "language",
        "ocr_lang": "language",
        "ocr_language": "language",
        "preview": "show_preview",
        "preview_before_output": "show_preview",
        "preview_text": "show_preview",
        "path": "tesseract_path",
        "tesseract": "tesseract_path",
        "tess_path": "tesseract_path",
        "path_to_tesseract": "tesseract_path",
        "output": "output_mode",
        "dest": "output_mode",
        "destination": "output_mode",
        "merge_batch": "merge_batch_results",
        "merge_batch_results": "merge_batch_results",
        "merge_results": "merge_batch_results",
        "merge": "merge_batch_results",
    }

    fields = {}
    for raw_line in (raw_text or "").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower().replace(" ", "_").replace("-", "_")
        key = key_aliases.get(key, key)
        if key not in fields:
            fields[key] = value.strip()
    return fields


def _build_fallback_form_message(title, rows):
    """Build compact message text shown by fallback multiline forms."""
    return (
        "{title}\n\n"
        "Edit values as KEY=VALUE lines and click OK.\n"
        "Keep keys as-is so settings are parsed correctly.\n\n"
        "{rows}\n\n"
        "Examples:\n"
        "  output_mode=cursor | clipboard | textbox | replace\n"
        "  show_preview=true\n"
        "  merge_batch_results=true | false\n"
        "  scale=1.2\n"
        "  tesseract_path=C:/Program Files/Tesseract-OCR/tesseract.exe\n"
        "  language=eng+hin (or comma-separated: eng,hin)\n"
    ).format(title=title, rows="\n".join(rows))


def _show_dialog_unavailable_warning(title, parent_frame, ctx):
    """Show a warning when no UNO dialog-model controls can be created."""
    settings_file = uno_utils.get_settings_file_path()
    message = _(
        "The LibreOffice UI controls required for this editor are not available in this session.\n\n"
        "You can edit TejOCR settings directly in:\n{path}\n\n"
        "Keep this window open and restart LibreOffice after saving manual edits."
    ).format(path=settings_file or _("not available"))
    logger.warning("Interactive fallback form unavailable because dialog models are not supported in this runtime.")
    return uno_utils.show_message_box(
        title,
        message,
        "warningbox",
        parent_frame=parent_frame,
        ctx=ctx,
    )


def _normalize_form_output_mode(raw_value, fallback):
    if not raw_value:
        return fallback
    return _output_mode_from_text(raw_value, fallback)


def _preset_display_name(preset_key):
    if not preset_key:
        return _("Custom")
    normalized = str(preset_key).strip().lower()
    if normalized == constants.OCR_PRESET_FAST:
        return _("Fast")
    if normalized == constants.OCR_PRESET_BALANCED:
        return _("Balanced")
    if normalized == constants.OCR_PRESET_ACCURATE:
        return _("Accuracy")
    return _("Custom")


def _coerce_preset_value(raw_value, fallback):
    if raw_value is None:
        return fallback
    normalized = str(raw_value).strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0].strip()
    if normalized in constants.OCR_PRESET_CHOICES:
        return normalized
    return fallback


def _preset_combo_item(preset_value):
    normalized = _coerce_preset_value(preset_value, constants.DEFAULT_OCR_PRESET)
    profile = constants.OCR_QUALITY_PRESETS.get(normalized, {})
    description = profile.get("description", "")
    return f"{normalized}: {_preset_display_name(normalized)}" + (f" - {description}" if description else "")


def _installed_languages_preview(ctx, limit=10):
    try:
        languages = list((tejocr_engine.get_available_languages(ctx=ctx) or []))
        return ocr_runtime.build_language_preview(languages, limit=limit)
    except Exception:
        return _("Installed languages: not detected")


def _runtime_python_package_command(packages, upgrade=False):
    try:
        from tejocr import tejocr_pdf
        return tejocr_pdf.get_runtime_pip_install_command(packages, upgrade=upgrade)
    except Exception:
        upgrade_flag = " -U" if upgrade else ""
        return f'"{sys.executable}" -m pip install{upgrade_flag} ' + " ".join(packages)


def _format_tesseract_install_help():
    name = (platform.system() or "").lower()
    package_cmd = _runtime_python_package_command(
        ["numpy", "pytesseract", "pillow"],
        upgrade=True,
    )
    if name == "darwin":
        return (
            "Install Tesseract:\n"
            "  brew install tesseract\n"
            "Install Python dependencies in LibreOffice Python:\n"
            "%s" % package_cmd
        )
    if name == "windows":
        return (
            "Install Tesseract:\n"
            "  https://github.com/UB-Mannheim/tesseract/wiki\n"
            "Install Python dependencies in LibreOffice Python:\n"
            "%s" % package_cmd
        )
    return (
        "Install Tesseract:\n"
        "  sudo apt install tesseract-ocr tesseract-ocr-eng\n"
        "Install Python dependencies in LibreOffice Python:\n"
        "%s" % package_cmd
    )


def _safe_set_property(control, property_name, value, context=""):
    """Set a UNO property without failing the entire dialog on unsupported properties."""
    try:
        control.setPropertyValue(property_name, value)
        return True
    except Exception as e:
        logger.debug(
            "Could not set property '{property_name}' on {context}: {error}".format(
                property_name=property_name,
                context=context or control,
                error=e,
            )
        )
        return False


def _add_control(model, name, control_type, properties, required=False):
    """Create and insert a UNO control model with safe property assignment."""
    try:
        control = model.createInstance(control_type)
        for prop_name, prop_value in properties.items():
            _safe_set_property(control, prop_name, prop_value, f"{name}.{prop_name}")
        model.insertByName(name, control)
        return control
    except Exception as e:
        if required:
            raise
        logger.debug(f"Non-required control '{name}' failed to create: {e}")
        return None


def _build_settings_snapshot(ctx):
    return {
        "path": uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx),
        "lang": _normalize_lang_codes(
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
        "output": _output_mode_from_text(
            uno_utils.get_setting(
                constants.CFG_KEY_LAST_OUTPUT_MODE,
                uno_utils.get_setting(
                    constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
                    constants.DEFAULT_OUTPUT_MODE,
                    ctx,
                ),
                ctx,
            ),
            constants.DEFAULT_OUTPUT_MODE,
        ),
        "preset": _coerce_preset_value(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_PRESET,
                constants.DEFAULT_OCR_PRESET,
                ctx,
            ),
            constants.DEFAULT_OCR_PRESET,
        ),
        "scale": str(
            _coerce_scale_text(
                uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx),
                constants.DEFAULT_SCALE_FACTOR,
            )
        ),
        "improve": (
            uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower()
            == "true"
        ),
        "preview": (
            uno_utils.get_setting(
                constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                ctx,
            ).lower()
            == "true"
        ),
    }


def _format_tesseract_ready_status(is_ready, message):
    """Return a plain-English status summary for status labels."""
    status_label = _("Ready") if is_ready else _("Needs setup")
    message = (message or "").strip()
    if not message:
        return _("Tesseract OCR: {status}").format(status=status_label)
    return _("Tesseract OCR: {status} - {message}").format(status=status_label, message=message)


def _format_path_validation_status(path_status_text, is_ready):
    """Return user-facing path validation text used by settings and options UIs."""
    state_label = _("Valid") if is_ready else _("Invalid")
    if not path_status_text:
        path_status_text = _("No status available")
    return _("ℹ Path check: {state}. {details}").format(state=state_label, details=path_status_text)


def _format_validation_warning(message):
    message = (message or "").strip()
    if not message:
        return ""
    return _("⚠️ Note: {message}").format(message=message)


def _format_settings_snapshot(snapshot):
    return _(
        "ℹ Path: {path}\n"
        "Language: {lang}\n"
        "Output: {output}\n"
        "Preset: {preset} | Scale: {scale} | Improve: {improve} | Preview: {preview}"
    ).format(
        path=snapshot.get("path") or _("Auto-detect"),
        lang=snapshot.get("lang") or constants.DEFAULT_OCR_LANGUAGE,
        output=_output_mode_label(snapshot.get("output") or constants.DEFAULT_OUTPUT_MODE),
        preset=_preset_display_name(snapshot.get("preset") or constants.DEFAULT_OCR_PRESET),
        scale=snapshot.get("scale") or constants.DEFAULT_SCALE_FACTOR,
        improve=_("yes") if snapshot.get("improve") else _("no"),
        preview=_("yes") if snapshot.get("preview") else _("no"),
    )


def _build_settings_snapshot_from_controls(dialog):
    """Build a best-effort settings snapshot from dialog controls."""
    try:
        path_text = dialog.getControl("path_text").getText().strip()
    except Exception:
        path_text = ""

    try:
        lang_text = dialog.getControl("lang_text").getText().strip()
    except Exception:
        lang_text = ""

    try:
        output_text = dialog.getControl("output_combo").getText()
    except Exception:
        output_text = constants.DEFAULT_OUTPUT_MODE

    try:
        preset_text = dialog.getControl("preset_combo").getText()
    except Exception:
        preset_text = constants.DEFAULT_OCR_PRESET

    try:
        scale_text = dialog.getControl("scale_text").getText()
    except Exception:
        scale_text = constants.DEFAULT_SCALE_FACTOR

    try:
        improve_state = bool(dialog.getControl("improve_check").getState())
    except Exception:
        improve_state = False
    try:
        preview_state = bool(dialog.getControl("preview_check").getState())
    except Exception:
        preview_state = False

    return {
        "path": path_text,
        "lang": _normalize_lang_codes(lang_text) or constants.DEFAULT_OCR_LANGUAGE,
        "output": _output_mode_from_text(output_text, constants.DEFAULT_OUTPUT_MODE),
        "preset": _coerce_preset_value(preset_text, constants.DEFAULT_OCR_PRESET),
        "scale": _coerce_scale_text(scale_text, constants.DEFAULT_SCALE_FACTOR),
        "improve": improve_state,
        "preview": preview_state,
    }


def _split_lang_codes(language_input):
    """Split comma/plus-separated language input into normalized list."""
    return ocr_runtime.split_language_codes(
        language_input,
        default_language=constants.DEFAULT_OCR_LANGUAGE,
    )


def _normalize_lang_codes(language_input):
    """Return canonical plus-delimited language code string."""
    return ocr_runtime.normalize_language_request(
        language_input,
        default_language=constants.DEFAULT_OCR_LANGUAGE,
    )


def _validate_language_codes(language_input, available_languages):
    """Validate requested language codes against available languages.

    Returns tuple ``(normalized_codes, invalid_codes, validated)`` where ``validated``
    is ``False`` when language availability could not be checked.
    """
    result = ocr_runtime.validate_language_codes(
        language_input,
        available_languages,
        default_language=constants.DEFAULT_OCR_LANGUAGE,
        platform_name=platform.system(),
    )
    return result.normalized, result.invalid_codes, result.validated


def _build_language_validation_message(language_input, invalid_codes, validated):
    return ocr_runtime.build_language_validation_message(
        language_input,
        invalid_codes,
        validated,
        platform_name=platform.system(),
    )


def _preset_values_help():
    """Human-readable preset list used in fallback prompts."""
    return "\n".join(
        [
            f"{preset_key}: {_preset_display_name(preset_key)} - {constants.OCR_QUALITY_PRESETS.get(preset_key, {}).get('description', '')}"
            for preset_key in constants.OCR_PRESET_CHOICES
        ]
    )


def _check_tesseract_path_status(ctx, tesseract_path):
    """Return `(is_ready, message)` for a provided tesseract path."""
    try:
        return tejocr_engine.check_tesseract_path(
            (tesseract_path or "").strip(),
            ctx=ctx,
            show_gui_errors=False,
        )
    except Exception as e:
        return False, _("Could not verify path: {error}").format(error=e)


def _resolve_tesseract_path(ctx, configured_path=""):
    """Resolve executable path from the user input or auto-detection."""
    configured = (configured_path or "").strip()
    if configured:
        return configured

    try:
        return uno_utils.find_tesseract_executable() or ""
    except Exception as e:
        logger.debug(f"Failed to auto-detect tesseract path: {e}")
        return ""


_PRESET_ITEMS = tuple(_preset_combo_item(key) for key in constants.OCR_PRESET_CHOICES)

class SettingsActionListener(unohelper.Base, XActionListener):
    """Action listener for settings dialog buttons."""
    
    def __init__(self, dialog_ref, ctx_ref):
        self.dialog = dialog_ref
        self.ctx = ctx_ref
    
    def actionPerformed(self, event):
        try:
            button_name = event.Source.getModel().getName()
            status_control = self.dialog.getControl("status")
            
            if button_name == "auto_button":
                # Auto-detect Tesseract
                detected_path = uno_utils.find_tesseract_executable()
                if detected_path:
                    path_control = self.dialog.getControl("path_text")
                    path_control.setText(detected_path)
                    status_control.setText(_("Auto-detected path: {path}").format(path=detected_path))
                else:
                    status_control.setText(_("Could not auto-detect the Tesseract path."))
            
            elif button_name == "help_button":
                # Show installation help
                help_text = (
                    "TejOCR Installation Guide:\n\n"
                    "Install Tesseract and Python dependencies for LibreOffice:\n"
                    "{commands}\n\n"
                    "For more languages:\n"
                    "Visit: https://tesseract-ocr.github.io/tessdoc/"
                )
                if "{commands}" in help_text:
                    help_text = help_text.replace("{commands}", _format_tesseract_install_help())
                uno_utils.show_message_box(_("Installation Help"), help_text, "infobox", ctx=self.ctx)

            elif button_name in ("logs_button", "logs_btn", "logs_action"):
                # Open the diagnostics log viewer
                uno_utils.show_log_viewer(ctx=self.ctx, parent_frame=self.dialog)
            
            elif button_name == "test_button":
                # Test current settings
                path_control = self.dialog.getControl("path_text")
                test_path = path_control.getText().strip()
                
                try:
                    from tejocr import tejocr_engine
                    if test_path:
                        success, message = tejocr_engine.check_tesseract_path(
                            test_path, ctx=self.ctx, show_success=False, show_gui_errors=False
                        )
                    else:
                        success, message = tejocr_engine.is_tesseract_ready(
                            self.ctx, show_gui_errors=False
                        )
                    
                    if success:
                        status_control.setText(_("Test successful. Dependencies are working."))
                    else:
                        status_control.setText(_("Test failed: {message}").format(message=message))
                except Exception as e:
                    status_control.setText(_("Test error: {error}").format(error=e))
            
        except Exception as e:
            logger.error(f"Settings dialog action error: {e}")
    
    def disposing(self, event):
        pass

# =============================================================================
# SIMPLIFIED WORKING DIALOGS WITH FALLBACK APPROACH
# =============================================================================

def create_settings_dialog(ctx, parent_frame=None):
    """Creates the actual UNO settings dialog with proper controls."""
    try:
        # Create dialog model
        dialog_model = uno_utils.create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 100)
        dialog_model.setPropertyValue("PositionY", 100) 
        dialog_model.setPropertyValue("Width", 450)
        dialog_model.setPropertyValue("Height", 560)
        dialog_model.setPropertyValue("Title", _("TejOCR {version} - Settings").format(version=constants.EXTENSION_VERSION))
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Create status group box
        status_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        status_group.setPropertyValue("PositionX", 10)
        status_group.setPropertyValue("PositionY", 10)
        status_group.setPropertyValue("Width", 430)
        status_group.setPropertyValue("Height", 80)
        status_group.setPropertyValue("Label", _("System & Dependency Status"))
        dialog_model.insertByName("status_group", status_group)
        
        # Tesseract status label
        tesseract_status = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        tesseract_status.setPropertyValue("PositionX", 20)
        tesseract_status.setPropertyValue("PositionY", 30)
        tesseract_status.setPropertyValue("Width", 300)
        tesseract_status.setPropertyValue("Height", 12)
        tesseract_status.setPropertyValue("Label", _("ℹ Tesseract OCR: Checking..."))
        dialog_model.insertByName("tesseract_status", tesseract_status)

        # Current configuration snapshot
        settings_snapshot = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        settings_snapshot.setPropertyValue("PositionX", 20)
        settings_snapshot.setPropertyValue("PositionY", 48)
        settings_snapshot.setPropertyValue("Width", 395)
        settings_snapshot.setPropertyValue("Height", 28)
        settings_snapshot.setPropertyValue("MultiLine", True)
        settings_snapshot.setPropertyValue("Label", _format_settings_snapshot(_build_settings_snapshot(ctx)))
        dialog_model.insertByName("settings_snapshot", settings_snapshot)
        
        # Refresh button
        refresh_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        refresh_btn.setPropertyValue("PositionX", 250)
        refresh_btn.setPropertyValue("PositionY", 60)
        refresh_btn.setPropertyValue("Width", 80)
        refresh_btn.setPropertyValue("Height", 20)
        refresh_btn.setPropertyValue("Label", _("Refresh Status"))
        refresh_btn.setPropertyValue("ActionCommand", "refresh_action")
        dialog_model.insertByName("refresh_btn", refresh_btn)
        
        # Help button
        help_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        help_btn.setPropertyValue("PositionX", 340)
        help_btn.setPropertyValue("PositionY", 60)
        help_btn.setPropertyValue("Width", 90)
        help_btn.setPropertyValue("Height", 20)
        help_btn.setPropertyValue("Label", _("Installation Help..."))
        help_btn.setPropertyValue("ActionCommand", "help_action")
        dialog_model.insertByName("help_btn", help_btn)

        # Logs button
        logs_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        logs_btn.setPropertyValue("PositionX", 160)
        logs_btn.setPropertyValue("PositionY", 60)
        logs_btn.setPropertyValue("Width", 80)
        logs_btn.setPropertyValue("Height", 20)
        logs_btn.setPropertyValue("Label", _("View Logs"))
        logs_btn.setPropertyValue("ActionCommand", "logs_action")
        dialog_model.insertByName("logs_btn", logs_btn)
        
        # Tesseract config group
        tesseract_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        tesseract_group.setPropertyValue("PositionX", 10)
        tesseract_group.setPropertyValue("PositionY", 100)
        tesseract_group.setPropertyValue("Width", 430)
        tesseract_group.setPropertyValue("Height", 80)
        tesseract_group.setPropertyValue("Label", _("Tesseract OCR Configuration"))
        dialog_model.insertByName("tesseract_group", tesseract_group)
        
        # Path label
        path_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        path_label.setPropertyValue("PositionX", 20)
        path_label.setPropertyValue("PositionY", 120)
        path_label.setPropertyValue("Width", 100)
        path_label.setPropertyValue("Height", 12)
        path_label.setPropertyValue("Label", _("Path to Tesseract:"))
        dialog_model.insertByName("path_label", path_label)
        
        # Path text field
        path_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        path_text.setPropertyValue("PositionX", 20)
        path_text.setPropertyValue("PositionY", 135)
        path_text.setPropertyValue("Width", 280)
        path_text.setPropertyValue("Height", 15)
        current_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
        path_text.setPropertyValue("Text", current_path)
        dialog_model.insertByName("path_text", path_text)
        
        # Browse button
        browse_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        browse_btn.setPropertyValue("PositionX", 310)
        browse_btn.setPropertyValue("PositionY", 135)
        browse_btn.setPropertyValue("Width", 40)
        browse_btn.setPropertyValue("Height", 15)
        browse_btn.setPropertyValue("Label", _("Browse..."))
        browse_btn.setPropertyValue("ActionCommand", "browse_action")
        dialog_model.insertByName("browse_btn", browse_btn)
        
        # Auto-detect button
        auto_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        auto_btn.setPropertyValue("PositionX", 355)
        auto_btn.setPropertyValue("PositionY", 135)
        auto_btn.setPropertyValue("Width", 40)
        auto_btn.setPropertyValue("Height", 15)
        auto_btn.setPropertyValue("Label", _("Auto-Detect"))
        auto_btn.setPropertyValue("ActionCommand", "auto_action")
        dialog_model.insertByName("auto_btn", auto_btn)
        
        # Test button
        test_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        test_btn.setPropertyValue("PositionX", 400)
        test_btn.setPropertyValue("PositionY", 135)
        test_btn.setPropertyValue("Width", 30)
        test_btn.setPropertyValue("Height", 15)
        test_btn.setPropertyValue("Label", _("Test"))
        test_btn.setPropertyValue("ActionCommand", "test_action")
        dialog_model.insertByName("test_btn", test_btn)

        # Path hint
        path_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        path_hint.setPropertyValue("PositionX", 20)
        path_hint.setPropertyValue("PositionY", 175)
        path_hint.setPropertyValue("Width", 410)
        path_hint.setPropertyValue("Height", 12)
        path_hint.setPropertyValue("Label", _("Leave path empty to auto-detect from system PATH."),)
        dialog_model.insertByName("path_hint", path_hint)
        
        # Test result label
        test_result = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        test_result.setPropertyValue("PositionX", 20)
        test_result.setPropertyValue("PositionY", 188)
        test_result.setPropertyValue("Width", 400)
        test_result.setPropertyValue("Height", 12)
        test_result.setPropertyValue("Label", _("Test Result: Ready to test"))
        dialog_model.insertByName("test_result", test_result)
        
        # Preferences group
        prefs_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        prefs_group.setPropertyValue("PositionX", 10)
        prefs_group.setPropertyValue("PositionY", 190)
        prefs_group.setPropertyValue("Width", 430)
        prefs_group.setPropertyValue("Height", 330)
        prefs_group.setPropertyValue("Label", _("Default OCR Preferences"))
        dialog_model.insertByName("prefs_group", prefs_group)

        # Installed language hint
        available_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        available_label.setPropertyValue("PositionX", 20)
        available_label.setPropertyValue("PositionY", 205)
        available_label.setPropertyValue("Width", 390)
        available_label.setPropertyValue("Height", 12)
        available_label.setPropertyValue("Label", _installed_languages_preview(ctx))
        dialog_model.insertByName("available_label", available_label)
        
        # Language label
        lang_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label.setPropertyValue("PositionX", 20)
        lang_label.setPropertyValue("PositionY", 225)
        lang_label.setPropertyValue("Width", 100)
        lang_label.setPropertyValue("Height", 12)
        lang_label.setPropertyValue("Label", _("Default Language:"))
        dialog_model.insertByName("lang_label", lang_label)

        # Language text field
        lang_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text.setPropertyValue("PositionX", 120)
        lang_text.setPropertyValue("PositionY", 225)
        lang_text.setPropertyValue("Width", 130)
        lang_text.setPropertyValue("Height", 15)
        current_lang = uno_utils.get_setting(
            constants.CFG_KEY_LAST_SELECTED_LANG,
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_LANG,
                constants.DEFAULT_OCR_LANGUAGE,
                ctx,
            ),
            ctx,
        )
        lang_text.setPropertyValue("Text", current_lang)
        dialog_model.insertByName("lang_text", lang_text)

        lang_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_hint.setPropertyValue("PositionX", 260)
        lang_hint.setPropertyValue("PositionY", 225)
        lang_hint.setPropertyValue("Width", 160)
        lang_hint.setPropertyValue("Height", 12)
        lang_hint.setPropertyValue("Label", _("Examples: eng, hin, eng+hin, fra"))
        dialog_model.insertByName("lang_hint", lang_hint)

        # Quality preset
        preset_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        preset_label.setPropertyValue("PositionX", 20)
        preset_label.setPropertyValue("PositionY", 250)
        preset_label.setPropertyValue("Width", 80)
        preset_label.setPropertyValue("Height", 12)
        preset_label.setPropertyValue("Label", _("Quality preset:"))
        dialog_model.insertByName("preset_label", preset_label)

        preset_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        preset_combo.setPropertyValue("PositionX", 120)
        preset_combo.setPropertyValue("PositionY", 250)
        preset_combo.setPropertyValue("Width", 165)
        preset_combo.setPropertyValue("Height", 15)
        preset_combo.setPropertyValue("Dropdown", True)
        preset_combo.setPropertyValue("ReadOnly", True)
        preset_combo.setPropertyValue("StringItemList", _PRESET_ITEMS)
        current_preset = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PRESET, constants.DEFAULT_OCR_PRESET, ctx)
        preset_combo.setPropertyValue("Text", _preset_combo_item(current_preset))
        dialog_model.insertByName("preset_combo", preset_combo)

        preset_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        preset_hint.setPropertyValue("PositionX", 295)
        preset_hint.setPropertyValue("PositionY", 250)
        preset_hint.setPropertyValue("Width", 120)
        preset_hint.setPropertyValue("Height", 12)
        preset_hint.setPropertyValue("Label", _("Quick start, then fine tune below"))
        dialog_model.insertByName("preset_hint", preset_hint)
        
        # Output mode label
        output_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_label.setPropertyValue("PositionX", 200)
        output_label.setPropertyValue("PositionY", 275)
        output_label.setPropertyValue("Width", 80)
        output_label.setPropertyValue("Height", 12)
        output_label.setPropertyValue("Label", _("Default Output:"))
        dialog_model.insertByName("output_label", output_label)
        
        # Output combo box
        output_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        output_combo.setPropertyValue("PositionX", 285)
        output_combo.setPropertyValue("PositionY", 275)
        output_combo.setPropertyValue("Width", 140)
        output_combo.setPropertyValue("Height", 15)
        output_combo.setPropertyValue("Dropdown", True)
        output_combo.setPropertyValue("ReadOnly", True)
        # Fix StringItemList type error - ensure all items are strings
        output_items = [
            _output_mode_combo_item(constants.OUTPUT_MODE_CURSOR),
            _output_mode_combo_item(constants.OUTPUT_MODE_CLIPBOARD),
            _output_mode_combo_item(constants.OUTPUT_MODE_TEXTBOX),
            _output_mode_combo_item(constants.OUTPUT_MODE_REPLACE),
        ]
        output_combo.setPropertyValue("StringItemList", tuple(output_items))
        # Set current selection
        current_output = uno_utils.get_setting(
            constants.CFG_KEY_LAST_OUTPUT_MODE,
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
                constants.OUTPUT_MODE_CURSOR,
                ctx,
            ),
            ctx,
        )
        if current_output not in (
            constants.OUTPUT_MODE_CURSOR,
            constants.OUTPUT_MODE_CLIPBOARD,
            constants.OUTPUT_MODE_TEXTBOX,
            constants.OUTPUT_MODE_REPLACE,
        ):
            current_output = constants.OUTPUT_MODE_CURSOR
        output_combo.setPropertyValue("Text", _output_mode_combo_item(current_output))
        dialog_model.insertByName("output_combo", output_combo)
        
        # Improve image checkbox
        improve_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        improve_check.setPropertyValue("PositionX", 20)
        improve_check.setPropertyValue("PositionY", 305)
        improve_check.setPropertyValue("Width", 300)
        improve_check.setPropertyValue("Height", 15)
        improve_check.setPropertyValue("Label", _("Improve low-quality images by default"))
        current_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
        improve_check.setPropertyValue("State", 1 if current_improve else 0)
        dialog_model.insertByName("improve_check", improve_check)

        # Grayscale checkbox
        grayscale_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        grayscale_check.setPropertyValue("PositionX", 20)
        grayscale_check.setPropertyValue("PositionY", 325)
        grayscale_check.setPropertyValue("Width", 200)
        grayscale_check.setPropertyValue("Height", 15)
        grayscale_check.setPropertyValue("Label", _("Force grayscale"))
        current_grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, str(constants.DEFAULT_PREPROC_GRAYSCALE), ctx).lower() == "true"
        grayscale_check.setPropertyValue("State", 1 if current_grayscale else 0)
        dialog_model.insertByName("grayscale_check", grayscale_check)

        # Binarize checkbox
        binarize_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        binarize_check.setPropertyValue("PositionX", 20)
        binarize_check.setPropertyValue("PositionY", 345)
        binarize_check.setPropertyValue("Width", 200)
        binarize_check.setPropertyValue("Height", 15)
        binarize_check.setPropertyValue("Label", _("Apply binarization"))
        current_binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, str(constants.DEFAULT_PREPROC_BINARIZE), ctx).lower() == "true"
        binarize_check.setPropertyValue("State", 1 if current_binarize else 0)
        dialog_model.insertByName("binarize_check", binarize_check)

        # Invert checkbox
        invert_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        invert_check.setPropertyValue("PositionX", 20)
        invert_check.setPropertyValue("PositionY", 365)
        invert_check.setPropertyValue("Width", 200)
        invert_check.setPropertyValue("Height", 15)
        invert_check.setPropertyValue("Label", _("Invert colors"))
        current_invert = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_INVERT,
            str(constants.DEFAULT_PREPROC_INVERT),
            ctx,
        ).lower() == "true"
        invert_check.setPropertyValue("State", 1 if current_invert else 0)
        dialog_model.insertByName("invert_check", invert_check)

        # PSM label
        psm_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        psm_label.setPropertyValue("PositionX", 20)
        psm_label.setPropertyValue("PositionY", 390)
        psm_label.setPropertyValue("Width", 40)
        psm_label.setPropertyValue("Height", 12)
        psm_label.setPropertyValue("Label", _("PSM:"))
        dialog_model.insertByName("psm_label", psm_label)

        # PSM combo
        psm_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        psm_combo.setPropertyValue("PositionX", 55)
        psm_combo.setPropertyValue("PositionY", 390)
        psm_combo.setPropertyValue("Width", 370)
        psm_combo.setPropertyValue("Height", 15)
        psm_combo.setPropertyValue("Dropdown", True)
        psm_combo.setPropertyValue("ReadOnly", True)
        psm_mode_map = _get_psm_mode_map(ctx)
        psm_combo.setPropertyValue("StringItemList", _get_psm_items(ctx))
        current_psm = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, ctx)
        current_psm, current_psm_text = _get_mode_text(psm_mode_map, current_psm, constants.DEFAULT_PSM_MODE)
        psm_combo.setPropertyValue("Text", current_psm_text)
        dialog_model.insertByName("psm_combo", psm_combo)

        # OEM label
        oem_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        oem_label.setPropertyValue("PositionX", 20)
        oem_label.setPropertyValue("PositionY", 415)
        oem_label.setPropertyValue("Width", 40)
        oem_label.setPropertyValue("Height", 12)
        oem_label.setPropertyValue("Label", _("OEM:"))
        dialog_model.insertByName("oem_label", oem_label)

        # OEM combo
        oem_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        oem_combo.setPropertyValue("PositionX", 55)
        oem_combo.setPropertyValue("PositionY", 415)
        oem_combo.setPropertyValue("Width", 370)
        oem_combo.setPropertyValue("Height", 15)
        oem_combo.setPropertyValue("Dropdown", True)
        oem_combo.setPropertyValue("ReadOnly", True)
        oem_mode_map = _get_oem_mode_map(ctx)
        oem_support_map = _get_oem_support_map(ctx)
        oem_combo.setPropertyValue("StringItemList", _get_oem_items(ctx))
        current_oem = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, ctx)
        current_oem, _current_oem_warning = _coerce_supported_oem_value(
            current_oem,
            ctx=ctx,
            support_map=oem_support_map,
            fallback=constants.DEFAULT_OEM_MODE,
        )
        current_oem, current_oem_text = _get_mode_text(oem_mode_map, current_oem, constants.DEFAULT_OEM_MODE)
        oem_combo.setPropertyValue("Text", current_oem_text)
        dialog_model.insertByName("oem_combo", oem_combo)

        # Scale label
        scale_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        scale_label.setPropertyValue("PositionX", 20)
        scale_label.setPropertyValue("PositionY", 440)
        scale_label.setPropertyValue("Width", 40)
        scale_label.setPropertyValue("Height", 12)
        scale_label.setPropertyValue("Label", _("Scale:"))
        dialog_model.insertByName("scale_label", scale_label)

        # Scale field
        scale_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        scale_text.setPropertyValue("PositionX", 55)
        scale_text.setPropertyValue("PositionY", 440)
        scale_text.setPropertyValue("Width", 50)
        scale_text.setPropertyValue("Height", 15)
        current_scale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx)
        scale_text.setPropertyValue("Text", str(current_scale))
        dialog_model.insertByName("scale_text", scale_text)
        scale_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        scale_hint.setPropertyValue("PositionX", 110)
        scale_hint.setPropertyValue("PositionY", 440)
        scale_hint.setPropertyValue("Width", 315)
        scale_hint.setPropertyValue("Height", 12)
        scale_hint.setPropertyValue("Label", _("1.0 = no scale"))
        dialog_model.insertByName("scale_hint", scale_hint)

        preview_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        preview_check.setPropertyValue("PositionX", 20)
        preview_check.setPropertyValue("PositionY", 460)
        preview_check.setPropertyValue("Width", 400)
        preview_check.setPropertyValue("Height", 15)
        preview_check.setPropertyValue("Label", _("Preview OCR result before inserting"))
        preview_check.setPropertyValue(
            "State",
            1
            if uno_utils.get_setting(
                constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                ctx,
            ).lower()
            == "true"
            else 0,
        )
        dialog_model.insertByName("preview_check", preview_check)
        
        # Save button
        save_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        save_btn.setPropertyValue("PositionX", 280)
        save_btn.setPropertyValue("PositionY", 500)
        save_btn.setPropertyValue("Width", 70)
        save_btn.setPropertyValue("Height", 25)
        save_btn.setPropertyValue("Label", _("Save"))
        save_btn.setPropertyValue("DefaultButton", True)
        save_btn.setPropertyValue("ActionCommand", "save_action")
        dialog_model.insertByName("save_btn", save_btn)
        
        # Cancel button
        cancel_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_btn.setPropertyValue("PositionX", 360)
        cancel_btn.setPropertyValue("PositionY", 500)
        cancel_btn.setPropertyValue("Width", 70)
        cancel_btn.setPropertyValue("Height", 25)
        cancel_btn.setPropertyValue("Label", _("Cancel"))
        cancel_btn.setPropertyValue("ActionCommand", "cancel_action")
        dialog_model.insertByName("cancel_btn", cancel_btn)
        
        return dialog_model
        
    except Exception as e:
        logger.error(f"Failed to create settings dialog model: {e}")
        return None


def create_compat_settings_dialog(ctx, parent_frame=None):
    """Compatibility-safe settings dialog used when the full dialog model is unsupported."""
    try:
        dialog_model = uno_utils.create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        if not dialog_model:
            logger.error("Failed to create compatibility settings dialog model")
            return None

        _safe_set_property(dialog_model, "Width", 460, "settings_dialog.model")
        _safe_set_property(dialog_model, "Height", 500, "settings_dialog.model")
        _safe_set_property(
            dialog_model,
            "Title",
            _("TejOCR {version} - Settings").format(version=constants.EXTENSION_VERSION),
            "settings_dialog.model"
        )
        _safe_set_property(dialog_model, "Closeable", True, "settings_dialog.model")
        _safe_set_property(dialog_model, "Moveable", True, "settings_dialog.model")

        _add_control(
            dialog_model,
            "tesseract_status",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 12,
                "Width": 370,
                "Height": 14,
                "Label": _("Tesseract OCR: Checking..."),
            },
            required=True,
        )
        settings_snapshot = _build_settings_snapshot(ctx)
        _add_control(
            dialog_model,
            "settings_snapshot",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 30,
                "Width": 435,
                "Height": 30,
                "Label": _format_settings_snapshot(settings_snapshot),
            },
            required=True,
        )

        _add_control(
            dialog_model,
            "refresh_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 320,
                "PositionY": 10,
                "Width": 55,
                "Height": 18,
                "Label": _("Refresh"),
                "ActionCommand": "refresh_action",
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "help_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 380,
                "PositionY": 10,
                "Width": 70,
                "Height": 18,
                "Label": _("Help"),
                "ActionCommand": "help_action",
            },
            required=False,
        )
        _add_control(
            dialog_model,
            "logs_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 380,
                "PositionY": 30,
                "Width": 70,
                "Height": 18,
                "Label": _("Logs"),
                "ActionCommand": "logs_action",
            },
            required=True,
        )

        # Tesseract path row
        _add_control(
            dialog_model,
            "path_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 66,
                "Width": 100,
                "Height": 14,
                "Label": _("Tesseract Path:"),
            },
            required=True,
        )
        current_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
        _add_control(
            dialog_model,
            "path_text",
            "com.sun.star.awt.UnoControlEditModel",
            {
                "PositionX": 12,
                "PositionY": 82,
                "Width": 300,
                "Height": 15,
                "Text": current_path,
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "auto_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 320,
                "PositionY": 82,
                "Width": 50,
                "Height": 15,
                "Label": _("Auto"),
                "ActionCommand": "auto_action",
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "browse_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 374,
                "PositionY": 82,
                "Width": 40,
                "Height": 15,
                "Label": _("Browse"),
                "ActionCommand": "browse_action",
            },
            required=False,
        )
        _add_control(
            dialog_model,
            "test_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 418,
                "PositionY": 82,
                "Width": 32,
                "Height": 15,
                "Label": _("Test"),
                "ActionCommand": "test_action",
            },
            required=False,
        )

        _add_control(
            dialog_model,
            "path_hint",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 101,
                "Width": 430,
                "Height": 12,
                "Label": _("Leave empty to auto-detect from PATH."),
            },
            required=False,
        )

        _add_control(
            dialog_model,
            "test_result",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 116,
                "Width": 430,
                "Height": 14,
                "Label": _("Test Result: Ready to test"),
            },
            required=True,
        )

        # Language and output
        _add_control(
            dialog_model,
            "lang_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 140,
                "Width": 90,
                "Height": 14,
                "Label": _("Default Language:"),
            },
            required=True,
        )
        current_lang = _normalize_lang_codes(
            uno_utils.get_setting(
                constants.CFG_KEY_LAST_SELECTED_LANG,
                uno_utils.get_setting(
                    constants.CFG_KEY_DEFAULT_LANG,
                    constants.DEFAULT_OCR_LANGUAGE,
                    ctx,
                ),
                ctx,
            )
        )
        _add_control(
            dialog_model,
            "lang_text",
            "com.sun.star.awt.UnoControlEditModel",
            {
                "PositionX": 106,
                "PositionY": 140,
                "Width": 105,
                "Height": 15,
                "Text": current_lang,
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "available_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 220,
                "PositionY": 140,
                "Width": 220,
                "Height": 28,
                "Label": _installed_languages_preview(ctx),
            },
            required=False,
        )

        _add_control(
            dialog_model,
            "output_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 170,
                "Width": 90,
                "Height": 14,
                "Label": _("Output Mode:"),
            },
            required=True,
        )
        current_output = _output_mode_from_text(
            uno_utils.get_setting(
                constants.CFG_KEY_LAST_OUTPUT_MODE,
                uno_utils.get_setting(
                    constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
                    constants.DEFAULT_OUTPUT_MODE,
                    ctx,
                ),
                ctx,
            ),
            constants.DEFAULT_OUTPUT_MODE,
        )
        _add_control(
            dialog_model,
            "output_combo",
            "com.sun.star.awt.UnoControlComboBoxModel",
            {
                "PositionX": 106,
                "PositionY": 170,
                "Width": 330,
                "Height": 15,
                "Dropdown": True,
                "ReadOnly": True,
                "StringItemList": tuple(
                    [
                        _output_mode_combo_item(constants.OUTPUT_MODE_CURSOR),
                        _output_mode_combo_item(constants.OUTPUT_MODE_CLIPBOARD),
                        _output_mode_combo_item(constants.OUTPUT_MODE_TEXTBOX),
                        _output_mode_combo_item(constants.OUTPUT_MODE_REPLACE),
                    ]
                ),
                "Text": _output_mode_combo_item(current_output),
            },
            required=True,
        )

        _add_control(
            dialog_model,
            "preset_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 192,
                "Width": 90,
                "Height": 14,
                "Label": _("Preset:"),
            },
            required=True,
        )
        current_preset = _coerce_preset_value(
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_PRESET,
                constants.DEFAULT_OCR_PRESET,
                ctx,
            ),
            constants.DEFAULT_OCR_PRESET,
        )
        _add_control(
            dialog_model,
            "preset_combo",
            "com.sun.star.awt.UnoControlComboBoxModel",
            {
                "PositionX": 106,
                "PositionY": 192,
                "Width": 170,
                "Height": 15,
                "Dropdown": True,
                "ReadOnly": True,
                "StringItemList": _PRESET_ITEMS,
                "Text": _preset_combo_item(current_preset),
            },
            required=True,
        )

        # Preprocessing controls
        current_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
        current_grayscale = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_GRAYSCALE,
            str(constants.DEFAULT_PREPROC_GRAYSCALE),
            ctx,
        ).lower() == "true"
        current_binarize = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_BINARIZE,
            str(constants.DEFAULT_PREPROC_BINARIZE),
            ctx,
        ).lower() == "true"
        current_invert = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_INVERT,
            str(constants.DEFAULT_PREPROC_INVERT),
            ctx,
        ).lower() == "true"

        _add_control(
            dialog_model,
            "improve_check",
            "com.sun.star.awt.UnoControlCheckBoxModel",
            {
                "PositionX": 12,
                "PositionY": 214,
                "Width": 300,
                "Height": 14,
                "Label": _("Improve image by default"),
                "State": 1 if current_improve else 0,
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "grayscale_check",
            "com.sun.star.awt.UnoControlCheckBoxModel",
            {
                "PositionX": 12,
                "PositionY": 232,
                "Width": 160,
                "Height": 14,
                "Label": _("Grayscale"),
                "State": 1 if current_grayscale else 0,
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "binarize_check",
            "com.sun.star.awt.UnoControlCheckBoxModel",
            {
                "PositionX": 176,
                "PositionY": 232,
                "Width": 160,
                "Height": 14,
                "Label": _("Binarize"),
                "State": 1 if current_binarize else 0,
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "invert_check",
            "com.sun.star.awt.UnoControlCheckBoxModel",
            {
                "PositionX": 344,
                "PositionY": 232,
                "Width": 90,
                "Height": 14,
                "Label": _("Invert"),
                "State": 1 if current_invert else 0,
            },
            required=False,
        )

        _add_control(
            dialog_model,
            "psm_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 256,
                "Width": 40,
                "Height": 14,
                "Label": _("PSM:"),
            },
            required=True,
        )
        current_psm = _mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, ctx),
            constants.DEFAULT_PSM_MODE,
        )
        psm_mode_map = _get_psm_mode_map(ctx)
        current_psm, current_psm_text = _get_mode_text(psm_mode_map, current_psm, constants.DEFAULT_PSM_MODE)
        _add_control(
            dialog_model,
            "psm_combo",
            "com.sun.star.awt.UnoControlComboBoxModel",
            {
                "PositionX": 56,
                "PositionY": 256,
                "Width": 180,
                "Height": 15,
                "Dropdown": True,
                "ReadOnly": True,
                "StringItemList": _get_psm_items(ctx),
                "Text": current_psm_text,
            },
            required=True,
        )

        _add_control(
            dialog_model,
            "oem_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 244,
                "PositionY": 256,
                "Width": 40,
                "Height": 14,
                "Label": _("OEM:"),
            },
            required=True,
        )
        current_oem = _mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, ctx),
            constants.DEFAULT_OEM_MODE,
        )
        oem_mode_map = _get_oem_mode_map(ctx)
        oem_support_map = _get_oem_support_map(ctx)
        current_oem, _current_oem_warning = _coerce_supported_oem_value(
            current_oem,
            ctx=ctx,
            support_map=oem_support_map,
            fallback=constants.DEFAULT_OEM_MODE,
        )
        current_oem, current_oem_text = _get_mode_text(oem_mode_map, current_oem, constants.DEFAULT_OEM_MODE)
        _add_control(
            dialog_model,
            "oem_combo",
            "com.sun.star.awt.UnoControlComboBoxModel",
            {
                "PositionX": 286,
                "PositionY": 256,
                "Width": 150,
                "Height": 15,
                "Dropdown": True,
                "ReadOnly": True,
                "StringItemList": _get_oem_items(ctx),
                "Text": current_oem_text,
            },
            required=True,
        )

        _add_control(
            dialog_model,
            "scale_label",
            "com.sun.star.awt.UnoControlFixedTextModel",
            {
                "PositionX": 12,
                "PositionY": 278,
                "Width": 40,
                "Height": 14,
                "Label": _("Scale:"),
            },
            required=True,
        )
        current_scale = _coerce_scale_text(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx),
            constants.DEFAULT_SCALE_FACTOR,
        )
        _add_control(
            dialog_model,
            "scale_text",
            "com.sun.star.awt.UnoControlEditModel",
            {
                "PositionX": 56,
                "PositionY": 278,
                "Width": 70,
                "Height": 15,
                "Text": str(current_scale),
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "preview_check",
            "com.sun.star.awt.UnoControlCheckBoxModel",
            {
                "PositionX": 12,
                "PositionY": 300,
                "Width": 380,
                "Height": 14,
                "Label": _("Preview before output"),
                "State": 1
                if uno_utils.get_setting(
                    constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                    constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                    ctx,
                ).lower()
                == "true"
                else 0,
            },
            required=True,
        )

        _add_control(
            dialog_model,
            "save_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 320,
                "PositionY": 460,
                "Width": 60,
                "Height": 24,
                "Label": _("Save"),
                "DefaultButton": True,
                "ActionCommand": "save_action",
            },
            required=True,
        )
        _add_control(
            dialog_model,
            "cancel_btn",
            "com.sun.star.awt.UnoControlButtonModel",
            {
                "PositionX": 386,
                "PositionY": 460,
                "Width": 60,
                "Height": 24,
                "Label": _("Cancel"),
                "ActionCommand": "cancel_action",
            },
            required=True,
        )

        return dialog_model

    except Exception as e:
        logger.error(f"Failed to create compatibility settings dialog model: {e}", exc_info=True)
        return None

def show_interactive_settings_dialog(ctx, parent_frame=None):
    """Shows the interactive settings dialog."""
    logger.debug("show_interactive_settings_dialog called")
    
    try:
        if not uno_utils.supports_uno_dialog_model(ctx):
            logger.error(
                "show_interactive_settings_dialog: UnoControlDialogModel is unavailable; "
                "skipping full interactive settings dialog."
            )
            _show_dialog_unavailable_warning(
                _("TejOCR Settings"),
                parent_frame=parent_frame,
                ctx=ctx,
            )
            return False

        dialog_model = create_compat_settings_dialog(ctx, parent_frame)
        if not dialog_model:
            logger.warning("Compatibility settings dialog failed; trying legacy dialog model.")
            dialog_model = create_settings_dialog(ctx, parent_frame)
        if not dialog_model:
            raise Exception("Failed to create dialog model")
        
        # Create dialog control
        dialog_control = uno_utils.create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        dialog_control.setModel(dialog_model)
        
        # Create parent peer
        toolkit = uno_utils.create_instance("com.sun.star.awt.Toolkit", ctx)
        
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except:
                parent_peer = toolkit.getDesktopWindow()
        else:
            parent_peer = toolkit.getDesktopWindow()
        
        dialog_control.createPeer(toolkit, parent_peer)
        
        # Update status immediately
        try:
            is_ready, msg = tejocr_engine.is_tesseract_ready(ctx, show_gui_errors=False)
            dialog_control.getControl("tesseract_status").setText(_format_tesseract_ready_status(is_ready, msg))
        except Exception as e:
            dialog_control.getControl("tesseract_status").setText(_("Tesseract status check failed: {error}").format(error=e))
        
        # Add action listeners
        class SettingsDialogListener(unohelper.Base, XActionListener):
            def __init__(self, dialog_ctrl, ctx_ref):
                self.dialog = dialog_ctrl
                self.ctx = ctx_ref
                self.result = False
                try:
                    self.status_control = self.dialog.getControl("test_result")
                except Exception:
                    self.status_control = None
                try:
                    self.snapshot_control = self.dialog.getControl("settings_snapshot")
                except Exception:
                    self.snapshot_control = None

                self._update_settings_snapshot()

            def _update_settings_snapshot(self):
                try:
                    if self.snapshot_control is not None:
                        snapshot = _build_settings_snapshot_from_controls(self.dialog)
                        self.snapshot_control.setText(_format_settings_snapshot(snapshot))
                except Exception:
                    # Best effort only; this is a helpful-only status field.
                    pass

            def _refresh_status(self):
                try:
                    is_ready, msg = tejocr_engine.is_tesseract_ready(self.ctx, show_gui_errors=False)
                    self.dialog.getControl("tesseract_status").setText(_format_tesseract_ready_status(is_ready, msg))
                except Exception as e:
                    self.dialog.getControl("tesseract_status").setText(
                        _("Tesseract status check failed: {error}").format(error=e)
                    )

            def actionPerformed(self, event):
                try:
                    action_command = event.ActionCommand

                    if action_command == "save_action":
                        # Save all settings
                        path_text = self.dialog.getControl("path_text").getText().strip()
                        resolved_path = _resolve_tesseract_path(self.ctx, path_text)
                        if not resolved_path and path_text:
                            resolved_path = path_text
                        elif not resolved_path:
                            resolved_path = ""

                        path_ready, path_status = _check_tesseract_path_status(self.ctx, resolved_path)
                        available_languages = ()
                        try:
                            available_languages = tuple(tejocr_engine.get_available_languages() or ())
                        except Exception:
                            available_languages = ()

                        lang_text = self.dialog.getControl("lang_text").getText().strip()
                        normalized_lang = _normalize_lang_codes(lang_text)
                        normalized_lang, invalid_codes, validated = _validate_language_codes(
                            normalized_lang,
                            available_languages,
                        )
                        lang_warning = _build_language_validation_message(normalized_lang, invalid_codes, validated)

                        status_text = _format_path_validation_status(path_status, path_ready)
                        if lang_warning:
                            status_text = status_text + " " + _format_validation_warning(lang_warning)
                        if self.status_control is not None:
                            self.status_control.setText(status_text)

                        output_text = self.dialog.getControl("output_combo").getText()
                        preset_text = self.dialog.getControl("preset_combo").getText()
                        improve_state = self.dialog.getControl("improve_check").getState()
                        grayscale_state = self.dialog.getControl("grayscale_check").getState()
                        binarize_state = self.dialog.getControl("binarize_check").getState()
                        invert_state = self.dialog.getControl("invert_check").getState()
                        preview_state = self.dialog.getControl("preview_check").getState()
                        psm_raw = self.dialog.getControl("psm_combo").getText()
                        oem_raw = self.dialog.getControl("oem_combo").getText()
                        scale_raw = self.dialog.getControl("scale_text").getText()
                        selected_preset = _coerce_preset_value(preset_text, constants.DEFAULT_OCR_PRESET)
                        preset_profile = constants.OCR_QUALITY_PRESETS.get(selected_preset, {})
                        oem_support_map = _get_oem_support_map(self.ctx)

                        # Save path
                        uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, resolved_path, self.ctx)
                        if not path_text and resolved_path:
                            self.dialog.getControl("path_text").setText(resolved_path)

                        # Save language
                        final_output_mode = _output_mode_from_text(output_text, constants.OUTPUT_MODE_CURSOR)
                        if normalized_lang:
                            uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, normalized_lang, self.ctx)
                            uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, normalized_lang, self.ctx)
                        else:
                            uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
                            uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)

                        # Save output mode
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OUTPUT_MODE, final_output_mode, self.ctx)
                        uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, final_output_mode, self.ctx)

                        # Save quality preset
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PRESET, selected_preset, self.ctx)

                        if selected_preset != constants.OCR_PRESET_CUSTOM and preset_profile:
                            psm_value = str(preset_profile.get("psm", _mode_value(psm_raw, constants.DEFAULT_PSM_MODE))).strip()
                            oem_value = str(preset_profile.get("oem", _mode_value(oem_raw, constants.DEFAULT_OEM_MODE))).strip()
                            scale_value = _coerce_scale_text(
                                preset_profile.get("scale", scale_raw), constants.DEFAULT_SCALE_FACTOR
                            )
                            improve_state = bool(preset_profile.get("improve_image", improve_state))
                            grayscale_state = bool(preset_profile.get("grayscale", grayscale_state))
                            binarize_state = bool(preset_profile.get("binarize", binarize_state))
                            invert_state = bool(preset_profile.get("invert", invert_state))
                        else:
                            psm_value = _mode_value(psm_raw, constants.DEFAULT_PSM_MODE)
                            oem_value = _mode_value(oem_raw, constants.DEFAULT_OEM_MODE)
                            scale_value = _coerce_scale_text(scale_raw, constants.DEFAULT_SCALE_FACTOR)

                        # Persist preview choice
                        uno_utils.set_setting(
                            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                            "true" if bool(preview_state) else "false",
                            self.ctx,
                        )
                        # Save processing controls
                        uno_utils.set_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "true" if improve_state else "false", self.ctx)
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, "true" if grayscale_state else "false", self.ctx)
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_BINARIZE, "true" if binarize_state else "false", self.ctx)
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_INVERT, "true" if invert_state else "false", self.ctx)

                        # Save engine mode controls
                        if psm_value not in constants.TESSERACT_PSM_MODES:
                            psm_value = constants.DEFAULT_PSM_MODE
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PSM, psm_value, self.ctx)
                        oem_value, oem_warning = _coerce_supported_oem_value(
                            oem_value,
                            ctx=self.ctx,
                            support_map=oem_support_map,
                            fallback=constants.DEFAULT_OEM_MODE,
                        )
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OEM, oem_value, self.ctx)
                        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_SCALE, str(scale_value), self.ctx)

                        if not path_ready and self.status_control is not None:
                            self.status_control.setText(
                                _("Saved with unresolved path. Please install or point OCR to Tesseract.")
                            )
                        elif oem_warning and self.status_control is not None:
                            self.status_control.setText(oem_warning)
                        self._refresh_status()
                        self._update_settings_snapshot()
                        self.result = True
                        self.dialog.endExecute()

                    elif action_command == "cancel_action":
                        self.result = False
                        self.dialog.endExecute()

                    elif action_command == "auto_action":
                        # Auto-detect Tesseract
                        detected_path = _resolve_tesseract_path(self.ctx)
                        if detected_path:
                            self.dialog.getControl("path_text").setText(detected_path)
                            if self.status_control is not None:
                                self.status_control.setText(_("Auto-detected path: {path}").format(path=detected_path))
                        else:
                            if self.status_control is not None:
                                self.status_control.setText(_("Auto-detect failed: no executable found."))
                        self._refresh_status()
                        self._update_settings_snapshot()

                    elif action_command == "test_action":
                        # Test current path
                        test_path = self.dialog.getControl("path_text").getText().strip()
                        try:
                            if test_path:
                                success, message = tejocr_engine.check_tesseract_path(
                                    test_path, ctx=self.ctx, show_success=False, show_gui_errors=False
                                )
                            else:
                                success, message = tejocr_engine.is_tesseract_ready(
                                    self.ctx, show_gui_errors=False
                                )

                            if self.status_control is not None:
                                if success:
                                    self.status_control.setText(_("Path test passed."))
                                else:
                                    self.status_control.setText(_("Path test failed: {message}").format(message=message))
                        except Exception as e:
                            if self.status_control is not None:
                                self.status_control.setText(_("Path test error: {error}").format(error=e))
                        self._refresh_status()
                        self._update_settings_snapshot()

                    elif action_command == "refresh_action":
                        # Refresh status
                        self._refresh_status()
                        self._update_settings_snapshot()

                    elif action_command == "browse_action":
                        # Browse for Tesseract executable
                        try:
                            file_path = uno_utils.show_file_picker(
                                title="Select Tesseract Executable",
                                filters=[(_("Executable Files"), "*")],
                                ctx=self.ctx
                            )
                            if file_path:
                                self.dialog.getControl("path_text").setText(file_path)
                                if self.status_control is not None:
                                    self.status_control.setText(_("Path selected: {path}").format(path=file_path))
                                self._refresh_status()
                                self._update_settings_snapshot()
                        except Exception as e:
                            if self.status_control is not None:
                                self.status_control.setText(_("Browse error: {error}").format(error=e))

                    elif action_command == "help_action":
                        # Show installation help
                        help_text = (
                            _format_tesseract_install_help()
                            + _(
                                "\n\nNeed to install Python dependencies in LibreOffice:\n{command}\n\n"
                                "For more languages: https://tesseract-ocr.github.io/tessdoc/"
                            ).format(
                                command=_runtime_python_package_command(
                                    ["numpy", "pytesseract", "pillow"],
                                    upgrade=True,
                                )
                            )
                        )
                        uno_utils.show_message_box(_("Installation Help"), help_text, "infobox", ctx=self.ctx)

                    elif action_command == "logs_action":
                        # Show recent TejOCR logs in a read-only dialog
                        uno_utils.show_log_viewer(ctx=self.ctx, parent_frame=self.dialog)

                except Exception as e:
                    logger.error(f"Settings dialog action error: {e}")

            def disposing(self, event):
                pass
        
        listener = SettingsDialogListener(dialog_control, ctx)
        
        # Add listeners to buttons
        for btn_name in [
            "save_btn",
            "cancel_btn",
            "auto_btn",
            "test_btn",
            "refresh_btn",
            "help_btn",
            "logs_btn",
            "browse_btn",
        ]:
            try:
                dialog_control.getControl(btn_name).addActionListener(listener)
            except:
                pass
        
        # Execute dialog
        result = dialog_control.execute()
        
        # Clean up
        dialog_control.dispose()
        
        return listener.result
        
    except Exception as e:
        logger.error(f"Failed to show interactive settings dialog: {e}", exc_info=True)
        try:
            uno_utils.show_message_box(
                _("Settings UI Error"),
                _(
                    "The full settings dialog could not be opened. "
                    "Opening the fallback editor instead.\n\n"
                    "If this repeats, use the View Logs action for full details."
                ),
                "errorbox",
                ctx=ctx,
                parent_frame=parent_frame,
            )
        except Exception:
            pass
        # Fallback to simple prompts
        return _show_fallback_settings_prompts(ctx, parent_frame)

def _show_fallback_settings_prompts(ctx, parent_frame=None):
    """Fallback to a single editable form when full dialog creation fails."""
    logger.info("Using fallback individual setting prompts")

    if not uno_utils.supports_uno_dialog_model(ctx):
        logger.warning(
            "Fallback settings form skipped because the UNO dialog model service is unavailable."
        )
        _show_dialog_unavailable_warning(
            _("TejOCR Settings (Fallback)"),
            parent_frame=parent_frame,
            ctx=ctx,
        )
        return False
    
    # Get current settings
    current_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
    current_lang = uno_utils.get_setting(
        constants.CFG_KEY_LAST_SELECTED_LANG,
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_LANG,
            constants.DEFAULT_OCR_LANGUAGE,
            ctx,
        ),
        ctx,
    )
    current_output = uno_utils.get_setting(
        constants.CFG_KEY_LAST_OUTPUT_MODE,
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
            constants.OUTPUT_MODE_CURSOR,
            ctx,
        ),
        ctx,
    )
    current_preview = (
        uno_utils.get_setting(
            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
            constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
            ctx,
        ).lower()
        == "true"
    )
    current_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
    current_grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, str(constants.DEFAULT_PREPROC_GRAYSCALE), ctx).lower() == "true"
    current_binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, str(constants.DEFAULT_PREPROC_BINARIZE), ctx).lower() == "true"
    current_invert = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_INVERT, str(constants.DEFAULT_PREPROC_INVERT), ctx).lower() == "true"
    current_psm = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, ctx)
    current_oem = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, ctx)
    current_preset = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PRESET, constants.DEFAULT_OCR_PRESET, ctx)
    current_scale = _coerce_scale_text(
        uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx),
        constants.DEFAULT_SCALE_FACTOR
    )
    preview_languages = _installed_languages_preview(ctx)
    available_languages = ()
    try:
        available_languages = tuple(tejocr_engine.get_available_languages() or ())
    except Exception:
        available_languages = ()

    # Read current dependency status to display clearly in fallback context.
    dependency_status = None
    try:
        is_ready, msg = tejocr_engine.is_tesseract_ready(ctx, show_gui_errors=False)
        dependency_status = _format_tesseract_ready_status(is_ready, msg)
    except Exception:
        dependency_status = _("Tesseract status unavailable")

    # Resolve working defaults for the editor.
    current_scale = _coerce_scale_text(current_scale, constants.DEFAULT_SCALE_FACTOR)
    current_preset = _coerce_preset_value(current_preset, constants.DEFAULT_OCR_PRESET)
    active_profile = constants.OCR_QUALITY_PRESETS.get(current_preset, {})
    active_profile = dict(active_profile) if active_profile else {}
    if current_preset == constants.OCR_PRESET_CUSTOM:
        preset_psm = current_psm
        preset_oem = current_oem
        preset_scale = str(current_scale)
        preset_improve = current_improve
        preset_grayscale = current_grayscale
        preset_binarize = current_binarize
        preset_invert = current_invert
    else:
        preset_psm = str(active_profile.get("psm", current_psm))
        preset_oem = str(active_profile.get("oem", current_oem))
        preset_scale = str(active_profile.get("scale", current_scale))
        preset_improve = bool(active_profile.get("improve_image", current_improve))
        preset_grayscale = bool(active_profile.get("grayscale", current_grayscale))
        preset_binarize = bool(active_profile.get("binarize", current_binarize))
        preset_invert = bool(active_profile.get("invert", current_invert))

    form_text = _build_fallback_form_message(
        _("TejOCR Settings"),
        [
            "# " + _("Current status"),
            "dependency={status}".format(status=dependency_status),
            "installed_languages={langs}".format(langs=preview_languages),
            "log_file={path}".format(path=uno_utils.get_log_file_path() or _("not available")),
            "",
            "# " + _("Editable settings"),
            "tesseract_path={path}".format(path=current_path or ""),
            "language={lang}".format(lang=current_lang),
            "output_mode={output}".format(output=current_output),
            "preview_before_output={preview}".format(preview="true" if current_preview else "false"),
            "",
            "# " + _("Quality defaults"),
            "preset={preset}".format(preset=current_preset),
            "psm={psm}".format(psm=preset_psm),
            "oem={oem}".format(oem=preset_oem),
            "scale={scale}".format(scale=preset_scale),
            "improve_image={improve}".format(improve="true" if preset_improve else "false"),
            "grayscale={grayscale}".format(grayscale="true" if preset_grayscale else "false"),
            "binarize={binarize}".format(binarize="true" if preset_binarize else "false"),
            "invert={invert}".format(invert="true" if preset_invert else "false"),
        ],
    )

    form_input = uno_utils.show_multiline_input_box(
        title=_("TejOCR Settings (Fallback)"),
        message=form_text,
        default_text=form_text,
        ctx=ctx,
        parent_frame=parent_frame,
        width=700,
        height=420,
    )
    if form_input is None:
        logger.warning(
            "Fallback settings form could not be displayed or returned no input; "
            "delegating to settings file guidance." 
        )
        _show_dialog_unavailable_warning(
            _("TejOCR Settings (Fallback)"),
            parent_frame=parent_frame,
            ctx=ctx,
        )
        return False

    values = _parse_fallback_form_fields(form_input)
    resolved_path = _resolve_tesseract_path(ctx, values.get("tesseract_path", current_path or ""))
    path_ready, path_status = _check_tesseract_path_status(ctx, resolved_path)
    uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, resolved_path or "", ctx)
    if path_status:
        try:
            uno_utils.show_message_box(
                _("Tesseract Path"),
                _("Path status: {status}").format(status=_format_path_validation_status(path_status, path_ready)),
                "infobox" if path_ready else "warningbox",
                parent_frame=parent_frame,
                ctx=ctx
            )
        except Exception:
            pass

    # Language list
    normalized_lang = _normalize_lang_codes(values.get("language", values.get("lang", current_lang)))
    normalized_lang, invalid_codes, validated = _validate_language_codes(normalized_lang, available_languages)
    if normalized_lang:
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, normalized_lang, ctx)
        uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, normalized_lang, ctx)
    else:
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
        uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
    lang_warning = _build_language_validation_message(normalized_lang, invalid_codes, validated)
    if lang_warning:
        uno_utils.show_message_box(
            title=_("Language Validation"),
            message=lang_warning,
            type="warningbox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    output_mode = _normalize_form_output_mode(values.get("output_mode", current_output), current_output)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OUTPUT_MODE, output_mode, ctx)
    uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, output_mode, ctx)

    current_preview = _coerce_bool_text(
        values.get("preview_before_output", values.get("preview", str(current_preview).lower())),
        current_preview,
    )

    # Preset selection
    current_preset = _coerce_preset_value(
        current_preset,
        constants.DEFAULT_OCR_PRESET
    )
    current_preset = _coerce_preset_value(
        values.get("preset", current_preset),
        constants.DEFAULT_OCR_PRESET,
    )
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PRESET, current_preset, ctx)
    selected_profile = constants.OCR_QUALITY_PRESETS.get(current_preset, {})
    oem_support_map = _get_oem_support_map(ctx)

    # Quality controls
    if current_preset != constants.OCR_PRESET_CUSTOM:
        psm_value = str(selected_profile.get("psm", current_psm)).strip() or constants.DEFAULT_PSM_MODE
        oem_value = str(selected_profile.get("oem", current_oem)).strip() or constants.DEFAULT_OEM_MODE
        scale_value = _coerce_scale_text(selected_profile.get("scale", current_scale), current_scale)
        current_improve = bool(selected_profile.get("improve_image", current_improve))
        current_grayscale = bool(selected_profile.get("grayscale", current_grayscale))
        current_binarize = bool(selected_profile.get("binarize", current_binarize))
        current_invert = bool(selected_profile.get("invert", current_invert))
    else:
        psm_value = _mode_value(values.get("psm", current_psm), current_psm)
        if psm_value not in constants.TESSERACT_PSM_MODES:
            psm_value = constants.DEFAULT_PSM_MODE

        oem_value = _mode_value(values.get("oem", current_oem), current_oem)
        oem_value, _oem_warning = _coerce_supported_oem_value(
            oem_value,
            ctx=ctx,
            support_map=oem_support_map,
            fallback=constants.DEFAULT_OEM_MODE,
        )

        scale_value = _coerce_scale_text(
            values.get("scale", str(current_scale)),
            current_scale,
        )
        current_improve = current_improve

        # Improve toggles
        current_improve = _coerce_bool_text(
            values.get("improve_image", str(current_improve).lower()),
            current_improve,
        )
        current_grayscale = _coerce_bool_text(
            values.get("grayscale", str(current_grayscale).lower()),
            current_grayscale,
        )
        current_binarize = _coerce_bool_text(
            values.get("binarize", str(current_binarize).lower()),
            current_binarize,
        )
        current_invert = _coerce_bool_text(
            values.get("invert", str(current_invert).lower()),
            current_invert,
        )

    # Apply quality settings
    if psm_value not in constants.TESSERACT_PSM_MODES:
        psm_value = constants.DEFAULT_PSM_MODE
    oem_value, _oem_warning = _coerce_supported_oem_value(
        oem_value,
        ctx=ctx,
        support_map=oem_support_map,
        fallback=constants.DEFAULT_OEM_MODE,
    )

    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PSM, psm_value, ctx)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OEM, oem_value, ctx)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_SCALE, str(scale_value), ctx)
    uno_utils.set_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "true" if current_improve else "false", ctx)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, "true" if current_grayscale else "false", ctx)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_BINARIZE, "true" if current_binarize else "false", ctx)
    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_INVERT, "true" if current_invert else "false", ctx)
    uno_utils.set_setting(
        constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
        "true" if current_preview else "false",
        ctx,
    )

    return True

def create_ocr_options_dialog(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Creates the actual UNO OCR options dialog with proper controls."""
    try:
        # Create dialog model
        dialog_model = uno_utils.create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 150)
        dialog_model.setPropertyValue("PositionY", 150)
        dialog_model.setPropertyValue("Width", 520)
        dialog_model.setPropertyValue("Height", 450)
        dialog_title = _("OCR Options")
        if source_type == "selected":
            dialog_title = _("OCR Options — Selected Image")
        elif image_path:
            dialog_title = _("OCR Options — {filename}").format(filename=os.path.basename(image_path))
        else:
            dialog_title = _("OCR Options — Image File")
        dialog_model.setPropertyValue("Title", dialog_title)
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Source info label
        source_desc = _("selected image") if source_type == "selected" else f"'{os.path.basename(image_path)}'" if image_path else _("file")
        source_info = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        source_info.setPropertyValue("PositionX", 10)
        source_info.setPropertyValue("PositionY", 10)
        source_info.setPropertyValue("Width", 500)
        source_info.setPropertyValue("Height", 12)
        source_info.setPropertyValue("Label", f"Processing: {source_desc}")
        dialog_model.insertByName("source_info", source_info)
        
        # Language label
        lang_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label.setPropertyValue("PositionX", 10)
        lang_label.setPropertyValue("PositionY", 35)
        lang_label.setPropertyValue("Width", 80)
        lang_label.setPropertyValue("Height", 12)
        lang_label.setPropertyValue("Label", _("Language:"))
        dialog_model.insertByName("lang_label", lang_label)
        
        # Language text field
        lang_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text.setPropertyValue("PositionX", 75)
        lang_text.setPropertyValue("PositionY", 35)
        lang_text.setPropertyValue("Width", 170)
        lang_text.setPropertyValue("Height", 15)
        default_lang = uno_utils.get_setting(
            constants.CFG_KEY_LAST_SELECTED_LANG,
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_LANG,
                constants.DEFAULT_OCR_LANGUAGE,
                ctx,
            ),
            ctx,
        )
        lang_text.setPropertyValue("Text", default_lang)
        dialog_model.insertByName("lang_text", lang_text)
        
        # Language hint
        lang_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_hint.setPropertyValue("PositionX", 210)
        lang_hint.setPropertyValue("PositionY", 35)
        lang_hint.setPropertyValue("Width", 255)
        lang_hint.setPropertyValue("Height", 12)
        lang_hint.setPropertyValue("Label", _("Use language codes like: eng, hin, fra (use + for mixed)"))
        dialog_model.insertByName("lang_hint", lang_hint)
        
        # Output label
        output_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_label.setPropertyValue("PositionX", 10)
        output_label.setPropertyValue("PositionY", 58)
        output_label.setPropertyValue("Width", 80)
        output_label.setPropertyValue("Height", 12)
        output_label.setPropertyValue("Label", _("Output As:"))
        dialog_model.insertByName("output_label", output_label)

        # Output mode combo
        current_output = uno_utils.get_setting(
            constants.CFG_KEY_LAST_OUTPUT_MODE,
            uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
                constants.OUTPUT_MODE_CURSOR,
                ctx,
            ),
            ctx,
        )
        if source_type != "selected" and current_output == constants.OUTPUT_MODE_REPLACE:
            current_output = constants.OUTPUT_MODE_CURSOR

        output_items = [
            _output_mode_combo_item(constants.OUTPUT_MODE_CURSOR),
            _output_mode_combo_item(constants.OUTPUT_MODE_CLIPBOARD),
            _output_mode_combo_item(constants.OUTPUT_MODE_TEXTBOX),
        ]
        if source_type == "selected":
            output_items.append(_output_mode_combo_item(constants.OUTPUT_MODE_REPLACE))
        output_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        output_combo.setPropertyValue("PositionX", 75)
        output_combo.setPropertyValue("PositionY", 58)
        output_combo.setPropertyValue("Width", 140)
        output_combo.setPropertyValue("Height", 15)
        output_combo.setPropertyValue("Dropdown", True)
        output_combo.setPropertyValue("ReadOnly", True)
        output_combo.setPropertyValue("StringItemList", tuple(output_items))
        output_combo.setPropertyValue("Text", _output_mode_combo_item(current_output))
        dialog_model.insertByName("output_combo", output_combo)

        output_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_hint.setPropertyValue("PositionX", 20)
        output_hint.setPropertyValue("PositionY", 315)
        output_hint.setPropertyValue("Width", 480)
        output_hint.setPropertyValue("Height", 12)
        output_hint.setPropertyValue(
            "Label",
            _(
                "Cursor: insert at caret • Clipboard: copy only • Text box: add new frame • Replace image: overwrite selected image"
            ),
        )
        dialog_model.insertByName("output_hint", output_hint)

        # Installed languages (short preview)
        installed_languages = _installed_languages_preview(ctx, limit=6)
        available_languages_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        available_languages_label.setPropertyValue("PositionX", 220)
        available_languages_label.setPropertyValue("PositionY", 58)
        available_languages_label.setPropertyValue("Width", 250)
        available_languages_label.setPropertyValue("Height", 28)
        available_languages_label.setPropertyValue("MultiLine", True)
        available_languages_label.setPropertyValue("Label", installed_languages)
        dialog_model.insertByName("available_languages_label", available_languages_label)
        
        # Improve image checkbox
        improve_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        improve_check.setPropertyValue("PositionX", 10)
        improve_check.setPropertyValue("PositionY", 105)
        improve_check.setPropertyValue("Width", 250)
        improve_check.setPropertyValue("Height", 15)
        improve_check.setPropertyValue("Label", _("Improve image quality"))
        default_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
        improve_check.setPropertyValue("State", 1 if default_improve else 0)
        dialog_model.insertByName("improve_check", improve_check)

        # Grayscale checkbox
        grayscale_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        grayscale_check.setPropertyValue("PositionX", 10)
        grayscale_check.setPropertyValue("PositionY", 125)
        grayscale_check.setPropertyValue("Width", 250)
        grayscale_check.setPropertyValue("Height", 15)
        grayscale_check.setPropertyValue("Label", _("Force grayscale"))
        current_grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, str(constants.DEFAULT_PREPROC_GRAYSCALE), ctx).lower() == "true"
        grayscale_check.setPropertyValue("State", 1 if current_grayscale else 0)
        dialog_model.insertByName("grayscale_check", grayscale_check)

        # Binarize checkbox
        binarize_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        binarize_check.setPropertyValue("PositionX", 10)
        binarize_check.setPropertyValue("PositionY", 145)
        binarize_check.setPropertyValue("Width", 250)
        binarize_check.setPropertyValue("Height", 15)
        binarize_check.setPropertyValue("Label", _("Apply binarization"))
        current_binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, str(constants.DEFAULT_PREPROC_BINARIZE), ctx).lower() == "true"
        binarize_check.setPropertyValue("State", 1 if current_binarize else 0)
        dialog_model.insertByName("binarize_check", binarize_check)

        # Invert checkbox
        invert_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        invert_check.setPropertyValue("PositionX", 10)
        invert_check.setPropertyValue("PositionY", 165)
        invert_check.setPropertyValue("Width", 250)
        invert_check.setPropertyValue("Height", 15)
        invert_check.setPropertyValue("Label", _("Invert colors"))
        current_invert = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_INVERT,
            str(constants.DEFAULT_PREPROC_INVERT),
            ctx,
        ).lower() == "true"
        invert_check.setPropertyValue("State", 1 if current_invert else 0)
        dialog_model.insertByName("invert_check", invert_check)

        # Quality preset
        preset_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        preset_label.setPropertyValue("PositionX", 10)
        preset_label.setPropertyValue("PositionY", 190)
        preset_label.setPropertyValue("Width", 80)
        preset_label.setPropertyValue("Height", 12)
        preset_label.setPropertyValue("Label", _("Quality preset:"))
        dialog_model.insertByName("preset_label", preset_label)

        preset_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        preset_combo.setPropertyValue("PositionX", 95)
        preset_combo.setPropertyValue("PositionY", 190)
        preset_combo.setPropertyValue("Width", 180)
        preset_combo.setPropertyValue("Height", 15)
        preset_combo.setPropertyValue("Dropdown", True)
        preset_combo.setPropertyValue("ReadOnly", True)
        preset_combo.setPropertyValue("StringItemList", _PRESET_ITEMS)
        current_preset = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_PRESET,
            constants.DEFAULT_OCR_PRESET,
            ctx,
        )
        preset_combo.setPropertyValue("Text", _preset_combo_item(current_preset))
        dialog_model.insertByName("preset_combo", preset_combo)

        preset_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        preset_hint.setPropertyValue("PositionX", 225)
        preset_hint.setPropertyValue("PositionY", 190)
        preset_hint.setPropertyValue("Width", 260)
        preset_hint.setPropertyValue("Height", 28)
        preset_hint.setPropertyValue("MultiLine", True)
        preset_hint.setPropertyValue("Label", _("💡 Fast / Balanced / Accuracy presets (custom for manual control)"))
        dialog_model.insertByName("preset_hint", preset_hint)

        # PSM label
        psm_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        psm_label.setPropertyValue("PositionX", 10)
        psm_label.setPropertyValue("PositionY", 225)
        psm_label.setPropertyValue("Width", 40)
        psm_label.setPropertyValue("Height", 12)
        psm_label.setPropertyValue("Label", _("PSM:"))
        dialog_model.insertByName("psm_label", psm_label)

        # PSM combo
        psm_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        psm_combo.setPropertyValue("PositionX", 55)
        psm_combo.setPropertyValue("PositionY", 225)
        psm_combo.setPropertyValue("Width", 180)
        psm_combo.setPropertyValue("Height", 15)
        psm_combo.setPropertyValue("Dropdown", True)
        psm_combo.setPropertyValue("ReadOnly", True)
        psm_mode_map = _get_psm_mode_map(ctx)
        psm_combo.setPropertyValue("StringItemList", _get_psm_items(ctx))
        current_psm = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, ctx)
        current_psm, current_psm_text = _get_mode_text(psm_mode_map, current_psm, constants.DEFAULT_PSM_MODE)
        psm_combo.setPropertyValue("Text", current_psm_text)
        dialog_model.insertByName("psm_combo", psm_combo)

        psm_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        psm_hint.setPropertyValue("PositionX", 245)
        psm_hint.setPropertyValue("PositionY", 225)
        psm_hint.setPropertyValue("Width", 250)
        psm_hint.setPropertyValue("Height", 12)
        psm_hint.setPropertyValue("Label", _("💡 PSM 3 = Auto, 11 = Sparse"))
        dialog_model.insertByName("psm_hint", psm_hint)

        # OEM label
        oem_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        oem_label.setPropertyValue("PositionX", 10)
        oem_label.setPropertyValue("PositionY", 245)
        oem_label.setPropertyValue("Width", 40)
        oem_label.setPropertyValue("Height", 12)
        oem_label.setPropertyValue("Label", _("OEM:"))
        dialog_model.insertByName("oem_label", oem_label)

        # OEM combo
        oem_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        oem_combo.setPropertyValue("PositionX", 55)
        oem_combo.setPropertyValue("PositionY", 245)
        oem_combo.setPropertyValue("Width", 180)
        oem_combo.setPropertyValue("Height", 15)
        oem_combo.setPropertyValue("Dropdown", True)
        oem_combo.setPropertyValue("ReadOnly", True)
        oem_mode_map = _get_oem_mode_map(ctx)
        oem_support_map = _get_oem_support_map(ctx)
        oem_combo.setPropertyValue("StringItemList", _get_oem_items(ctx))
        current_oem = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, ctx)
        current_oem, _current_oem_warning = _coerce_supported_oem_value(
            current_oem,
            ctx=ctx,
            support_map=oem_support_map,
            fallback=constants.DEFAULT_OEM_MODE,
        )
        current_oem, current_oem_text = _get_mode_text(oem_mode_map, current_oem, constants.DEFAULT_OEM_MODE)
        oem_combo.setPropertyValue("Text", current_oem_text)
        dialog_model.insertByName("oem_combo", oem_combo)
        
        oem_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        oem_hint.setPropertyValue("PositionX", 245)
        oem_hint.setPropertyValue("PositionY", 245)
        oem_hint.setPropertyValue("Width", 250)
        oem_hint.setPropertyValue("Height", 12)
        oem_hint.setPropertyValue("Label", _("💡 OEM 3 = Default, 1 = LSTM (Modern)"))
        dialog_model.insertByName("oem_hint", oem_hint)

        # Scale label
        scale_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        scale_label.setPropertyValue("PositionX", 10)
        scale_label.setPropertyValue("PositionY", 270)
        scale_label.setPropertyValue("Width", 40)
        scale_label.setPropertyValue("Height", 12)
        scale_label.setPropertyValue("Label", _("Scale:"))
        dialog_model.insertByName("scale_label", scale_label)

        # Scale text
        scale_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        scale_text.setPropertyValue("PositionX", 55)
        scale_text.setPropertyValue("PositionY", 270)
        scale_text.setPropertyValue("Width", 80)
        scale_text.setPropertyValue("Height", 15)
        current_scale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_SCALE, constants.DEFAULT_SCALE_FACTOR, ctx)
        scale_text.setPropertyValue("Text", str(current_scale))
        dialog_model.insertByName("scale_text", scale_text)

        scale_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        scale_hint.setPropertyValue("PositionX", 140)
        scale_hint.setPropertyValue("PositionY", 270)
        scale_hint.setPropertyValue("Width", 265)
        scale_hint.setPropertyValue("Height", 12)
        scale_hint.setPropertyValue("Label", _("💡 1.0 = original size (1.5+ can help blurry scans)"))
        dialog_model.insertByName("scale_hint", scale_hint)

        preview_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        preview_check.setPropertyValue("PositionX", 10)
        preview_check.setPropertyValue("PositionY", 335)
        preview_check.setPropertyValue("Width", 390)
        preview_check.setPropertyValue("Height", 15)
        preview_check.setPropertyValue("Label", _("Preview OCR text before inserting"))
        default_preview = (
            uno_utils.get_setting(
                constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
                ctx,
            ).lower()
            == "true"
        )
        preview_check.setPropertyValue("State", 1 if default_preview else 0)
        dialog_model.insertByName("preview_check", preview_check)

        default_merge_batch = _coerce_bool_text(
            uno_utils.get_setting(
                constants.CFG_KEY_MERGE_BATCH_RESULTS,
                constants.DEFAULT_MERGE_BATCH_RESULTS,
                ctx,
            )
        )
        if source_type != "selected":
            merge_batch_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
            merge_batch_check.setPropertyValue("PositionX", 10)
            merge_batch_check.setPropertyValue("PositionY", 355)
            merge_batch_check.setPropertyValue("Width", 500)
            merge_batch_check.setPropertyValue("Height", 15)
            merge_batch_check.setPropertyValue("Label", _("Merge all file/PDF results into a single output block"))
            merge_batch_check.setPropertyValue("State", 1 if default_merge_batch else 0)
            dialog_model.insertByName("merge_batch_check", merge_batch_check)

        # Status label
        status_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        status_label.setPropertyValue("PositionX", 10)
        status_label.setPropertyValue("PositionY", 380 if source_type != "selected" else 355)
        status_label.setPropertyValue("Width", 280)
        status_label.setPropertyValue("Height", 12)
        status_label.setPropertyValue("Label", _("Status: Ready"))
        dialog_model.insertByName("status_label", status_label)
        
        # Start OCR button
        start_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        start_btn.setPropertyValue("PositionX", 290)
        start_btn.setPropertyValue("PositionY", 415)
        start_btn.setPropertyValue("Width", 70)
        start_btn.setPropertyValue("Height", 20)
        start_btn.setPropertyValue("Label", _("Start OCR"))
        start_btn.setPropertyValue("DefaultButton", True)
        start_btn.setPropertyValue("ActionCommand", "start_ocr_action")
        # Modern crisp green styling
        start_btn.setPropertyValue("BackgroundColor", 0x1F883D)
        start_btn.setPropertyValue("TextColor", 0xFFFFFF)
        start_btn.setPropertyValue("FontWeight", 150.0) # Bold weight
        dialog_model.insertByName("start_btn", start_btn)
        
        # Cancel button
        cancel_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_btn.setPropertyValue("PositionX", 370)
        cancel_btn.setPropertyValue("PositionY", 415)
        cancel_btn.setPropertyValue("Width", 70)
        cancel_btn.setPropertyValue("Height", 20)
        cancel_btn.setPropertyValue("Label", _("Cancel"))
        cancel_btn.setPropertyValue("ActionCommand", "cancel_ocr_action")
        dialog_model.insertByName("cancel_btn", cancel_btn)
        
        return dialog_model
        
    except Exception as e:
        logger.error(f"Failed to create OCR options dialog model: {e}")
        return None

def show_interactive_ocr_options_dialog(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Shows the interactive OCR options dialog."""
    logger.debug(f"show_interactive_ocr_options_dialog called for source: {source_type}")
    
    try:
        dialog_model = create_ocr_options_dialog(ctx, parent_frame, source_type, image_path)
        if not dialog_model:
            raise Exception("Failed to create dialog model")
        
        # Create dialog control
        dialog_control = uno_utils.create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        dialog_control.setModel(dialog_model)
        
        # Create parent peer
        toolkit = uno_utils.create_instance("com.sun.star.awt.Toolkit", ctx)
        
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except:
                parent_peer = toolkit.getDesktopWindow()
        else:
            parent_peer = toolkit.getDesktopWindow()
        
        dialog_control.createPeer(toolkit, parent_peer)
        
        # Add action listeners
        class OCROptionsDialogListener(unohelper.Base, XActionListener):
            def __init__(self, dialog_ctrl, ctx_ref, source_type_ref):
                self.dialog = dialog_ctrl
                self.ctx = ctx_ref
                self.source_type = source_type_ref
                self.result_lang = None
                self.result_output = None
                self.result_improve = False
                self.result_extra = {}
                self.cancelled = True
                self.COLOR_BTN_PRIMARY = 0x2d7bff
                self.COLOR_BTN_SUCCESS = 0x22c55e
                self.COLOR_BTN_WARNING = 0xf59e0b
                self.COLOR_BTN_DANGER = 0xef4444
                self.COLOR_TEXT_ON_DARK = 0xffffff
                self.COLOR_OK = 0x16a34a
                self.COLOR_WARN = 0xd97706
                self.COLOR_ERROR = 0xdc2626

            def _capture_control_state(self, control):
                if not control:
                    return {}
                state = {}
                try:
                    state["text"] = control.getText()
                except Exception:
                    state["text"] = None
                try:
                    state["enabled"] = control.isEnabled()
                except Exception:
                    state["enabled"] = None
                try:
                    model = control.getModel()
                    state["bg"] = getattr(model, "BackgroundColor", None)
                    state["fg"] = getattr(model, "TextColor", None)
                except Exception:
                    state["bg"] = None
                    state["fg"] = None
                return state

            def _restore_control_state(self, control, state):
                if not control or not isinstance(state, dict):
                    return
                try:
                    if state.get("text") is not None:
                        control.setText(state["text"])
                except Exception:
                    pass
                try:
                    if state.get("enabled") is not None:
                        control.setEnable(state["enabled"])
                except Exception:
                    pass
                try:
                    model = control.getModel()
                    if state.get("bg") is not None:
                        model.BackgroundColor = state["bg"]
                    if state.get("fg") is not None:
                        model.TextColor = state["fg"]
                except Exception:
                    pass

            def _set_control_feedback(self, control, text=None, enabled=None, bg_color=None, fg_color=None):
                if not control:
                    return
                if text is not None:
                    try:
                        control.setText(text)
                    except Exception:
                        pass
                if enabled is not None:
                    try:
                        control.setEnable(enabled)
                    except Exception:
                        pass
                try:
                    model = control.getModel()
                    if bg_color is not None:
                        model.BackgroundColor = bg_color
                    if fg_color is not None:
                        model.TextColor = fg_color
                except Exception:
                    pass

            def _set_status(self, text, color=None):
                try:
                    status = self.dialog.getControl("status_label")
                    if status:
                        status.setText(text or "")
                        if color is not None:
                            try:
                                status.getModel().TextColor = color
                            except Exception:
                                pass
                except Exception:
                    pass
            
            def actionPerformed(self, event):
                try:
                    def _extract_action_command(event_obj):
                        if event_obj is None:
                            return None
                        for attr in ("ActionCommand", "actionCommand"):
                            try:
                                value = getattr(event_obj, attr)
                                if value:
                                    return str(value)
                            except Exception:
                                pass
                        try:
                            source = getattr(event_obj, "Source", None)
                            if source:
                                command = getattr(source, "getActionCommand", None)
                                if callable(command):
                                    value = command()
                                    if value:
                                        return str(value)
                        except Exception:
                            pass
                        return None

                    action_command = _extract_action_command(event)
                    if not action_command:
                        return

                    start_btn = None
                    cancel_btn = None
                    status_label = None
                    try:
                        start_btn = self.dialog.getControl("start_btn")
                        cancel_btn = self.dialog.getControl("cancel_btn")
                        status_label = self.dialog.getControl("status_label")
                    except Exception:
                        pass

                    def _run_feedback(
                        control,
                        run_text,
                        start_status,
                        execute_callable,
                        done_status=None,
                        bg_color=None,
                        fg_color=None,
                    ):
                        state = self._capture_control_state(control)
                        if control:
                            try:
                                control.setFocus()
                            except Exception:
                                pass
                        self._set_control_feedback(
                            control,
                            text=run_text,
                            enabled=False,
                            bg_color=bg_color,
                            fg_color=fg_color,
                        )
                        if status_label and start_status:
                            self._set_status(start_status, self.COLOR_OK)
                        try:
                            result = execute_callable()
                            if status_label and done_status:
                                self._set_status(done_status, self.COLOR_OK)
                            return result
                        except Exception:
                            if status_label and start_status:
                                self._set_status("OCR options action failed.", self.COLOR_ERROR)
                            raise
                        finally:
                            self._restore_control_state(control, state)
                    
                    if action_command == "start_ocr_action":
                        def _collect_options():
                            # Get selected options
                            self.result_lang = self.dialog.getControl("lang_text").getText().strip()
                            if not self.result_lang:
                                self.result_lang = constants.DEFAULT_OCR_LANGUAGE
                            available_languages = ()
                            try:
                                available_languages = tuple(tejocr_engine.get_available_languages() or ())
                            except Exception:
                                available_languages = ()

                            validated_lang, invalid_codes, validated = _validate_language_codes(
                                self.result_lang,
                                available_languages,
                            )
                            self.result_lang = validated_lang or constants.DEFAULT_OCR_LANGUAGE
                            language_warning = _build_language_validation_message(
                                self.result_lang,
                                invalid_codes,
                                validated,
                            )
                            if language_warning:
                                self._set_status(language_warning, self.COLOR_WARN)

                            preset_text = self.dialog.getControl("preset_combo").getText()
                            selected_preset = _coerce_preset_value(
                                preset_text,
                                constants.DEFAULT_OCR_PRESET
                            )
                            preset_profile = constants.OCR_QUALITY_PRESETS.get(selected_preset, {})
                            oem_support_map = _get_oem_support_map(self.ctx)
                            
                            self.result_output = _output_mode_from_text(
                                self.dialog.getControl("output_combo").getText(),
                                constants.OUTPUT_MODE_CURSOR
                            )
                            if self.source_type != "selected" and self.result_output == constants.OUTPUT_MODE_REPLACE:
                                self.result_output = constants.OUTPUT_MODE_CURSOR
                            if not self.result_output:
                                self.result_output = constants.OUTPUT_MODE_CURSOR

                            self.result_improve = bool(self.dialog.getControl("improve_check").getState())

                            psm_raw = self.dialog.getControl("psm_combo").getText()
                            psm_value = _mode_value(psm_raw, constants.DEFAULT_PSM_MODE)
                            if psm_value not in constants.TESSERACT_PSM_MODES:
                                psm_value = constants.DEFAULT_PSM_MODE

                            oem_raw = self.dialog.getControl("oem_combo").getText()
                            oem_value = _mode_value(oem_raw, constants.DEFAULT_OEM_MODE)
                            if oem_value not in constants.TESSERACT_OEM_MODES:
                                oem_value = constants.DEFAULT_OEM_MODE

                            scale_raw = self.dialog.getControl("scale_text").getText()
                            scale_value = _coerce_scale_text(scale_raw, constants.DEFAULT_SCALE_FACTOR)
                            result_improve = bool(self.dialog.getControl("improve_check").getState())
                            result_grayscale = bool(self.dialog.getControl("grayscale_check").getState())
                            result_binarize = bool(self.dialog.getControl("binarize_check").getState())
                            result_invert = bool(self.dialog.getControl("invert_check").getState())
                            result_preview = bool(self.dialog.getControl("preview_check").getState())
                            result_merge_batch = False
                            if self.source_type != "selected":
                                try:
                                    result_merge_batch = bool(self.dialog.getControl("merge_batch_check").getState())
                                except Exception:
                                    result_merge_batch = constants.DEFAULT_MERGE_BATCH_RESULTS

                            if selected_preset != constants.OCR_PRESET_CUSTOM and preset_profile:
                                psm_value = str(
                                    preset_profile.get("psm", psm_value)
                                ).strip() or psm_value
                                oem_value = str(
                                    preset_profile.get("oem", oem_value)
                                ).strip() or oem_value
                                scale_value = _coerce_scale_text(
                                    preset_profile.get("scale", scale_value),
                                    scale_value
                                )
                                result_improve = bool(
                                    preset_profile.get("improve_image", result_improve)
                                )
                                result_grayscale = bool(
                                    preset_profile.get("grayscale", result_grayscale)
                                )
                                result_binarize = bool(
                                    preset_profile.get("binarize", result_binarize)
                                )
                                result_invert = bool(
                                    preset_profile.get("invert", result_invert)
                                )

                            oem_value, oem_warning = _coerce_supported_oem_value(
                                oem_value,
                                ctx=self.ctx,
                                support_map=oem_support_map,
                                fallback=constants.DEFAULT_OEM_MODE,
                            )
                            if oem_warning:
                                self._set_status(oem_warning, self.COLOR_WARN)
                                return False

                            self.result_extra = {
                                "show_preview": result_preview,
                                "preset": selected_preset,
                                "psm": psm_value,
                                "oem": oem_value,
                                "scale": scale_value,
                                "grayscale": result_grayscale,
                                "binarize": result_binarize,
                                "invert": result_invert,
                                "merge_batch_results": result_merge_batch,
                                "language_warning": language_warning,
                            }
                            self.result_improve = result_improve
                            self.cancelled = False
                            return True

                        should_close = _run_feedback(
                            start_btn,
                            "Starting OCR...",
                            "Collecting OCR options...",
                            _collect_options,
                            "Launching OCR...",
                            bg_color=self.COLOR_BTN_SUCCESS,
                            fg_color=self.COLOR_TEXT_ON_DARK,
                        )
                        if should_close:
                            self.dialog.endExecute()
                    
                    elif action_command == "cancel_ocr_action":
                        def _cancel_operation():
                            self.cancelled = True

                        _run_feedback(
                            cancel_btn,
                            "Cancelling...",
                            "Cancelling OCR...",
                            _cancel_operation,
                            "OCR cancelled.",
                            bg_color=self.COLOR_BTN_DANGER,
                            fg_color=self.COLOR_TEXT_ON_DARK,
                        )
                        self.cancelled = True
                        self.dialog.endExecute()
                
                except Exception as e:
                    logger.error(f"OCR options dialog action error: {e}")
            
            def disposing(self, event):
                pass
        
        listener = OCROptionsDialogListener(dialog_control, ctx, source_type)
        
        # Add listeners to buttons
        for btn_name in ["start_btn", "cancel_btn"]:
            try:
                dialog_control.getControl(btn_name).addActionListener(listener)
            except:
                pass
        
        # Execute dialog
        result = dialog_control.execute()
        
        # Clean up
        dialog_control.dispose()
        
        if listener.cancelled:
            return None, None, False, {}
        else:
            return listener.result_lang, listener.result_output, listener.result_improve, listener.result_extra
        
    except Exception as e:
        logger.error(f"Failed to show interactive OCR options dialog: {e}")
        # Fallback to simple prompts
        return _show_fallback_ocr_options_prompts(ctx, parent_frame, source_type, image_path)

def _show_fallback_ocr_options_prompts(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Fallback to a single editable option form if dialog creation fails."""
    logger.info("Using fallback OCR options prompts")
    
    # Smart defaults from settings
    default_lang = uno_utils.get_setting(
        constants.CFG_KEY_LAST_SELECTED_LANG,
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_LANG,
            constants.DEFAULT_OCR_LANGUAGE,
            ctx,
        ),
        ctx
    )
    default_output = uno_utils.get_setting(
        constants.CFG_KEY_LAST_OUTPUT_MODE,
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_OUTPUT_MODE,
            constants.OUTPUT_MODE_CURSOR,
            ctx,
        ),
        ctx
    )
    if source_type != "selected" and default_output == constants.OUTPUT_MODE_REPLACE:
        default_output = constants.OUTPUT_MODE_CURSOR
    default_grayscale = (
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_GRAYSCALE,
            str(constants.DEFAULT_PREPROC_GRAYSCALE),
            ctx
        ).lower()
        == "true"
    )
    default_binarize = _coerce_bool_text(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_BINARIZE,
            str(constants.DEFAULT_PREPROC_BINARIZE),
            ctx
        )
    )
    default_invert = _coerce_bool_text(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_INVERT,
            str(constants.DEFAULT_PREPROC_INVERT),
            ctx,
        )
    )
    default_preview = _coerce_bool_text(
        uno_utils.get_setting(
            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
            constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
            ctx,
        )
    )
    default_improve = _coerce_bool_text(
        uno_utils.get_setting(
            constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT,
            "false",
            ctx
        )
    )
    default_psm = uno_utils.get_setting(
        constants.CFG_KEY_DEFAULT_PSM,
        constants.DEFAULT_PSM_MODE,
        ctx
    )
    default_oem = uno_utils.get_setting(
        constants.CFG_KEY_DEFAULT_OEM,
        constants.DEFAULT_OEM_MODE,
        ctx
    )
    default_scale = _coerce_scale_text(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_SCALE,
            constants.DEFAULT_SCALE_FACTOR,
            ctx
        ),
        constants.DEFAULT_SCALE_FACTOR
    )
    default_preset = _coerce_preset_value(
        uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_PRESET,
            constants.DEFAULT_OCR_PRESET,
            ctx
        ),
        constants.DEFAULT_OCR_PRESET
    )
    raw_default_merge_batch = uno_utils.get_setting(
        constants.CFG_KEY_MERGE_BATCH_RESULTS,
        constants.DEFAULT_MERGE_BATCH_RESULTS,
        ctx,
    )
    default_merge_batch = _coerce_bool_text(raw_default_merge_batch, constants.DEFAULT_MERGE_BATCH_RESULTS == "true")

    if not uno_utils.supports_uno_dialog_model(ctx):
        logger.warning(
            "Fallback OCR options form skipped because the UNO dialog model service is unavailable."
        )
        if source_type != "selected" and default_output == constants.OUTPUT_MODE_REPLACE:
            default_output = constants.OUTPUT_MODE_CURSOR
        return (
            default_lang,
            default_output,
            default_improve,
            {
                "show_preview": default_preview,
                "preset": default_preset,
                "psm": str(default_psm).strip() or constants.DEFAULT_PSM_MODE,
                "oem": str(default_oem).strip() or constants.DEFAULT_OEM_MODE,
                "scale": default_scale,
                "grayscale": default_grayscale,
                "binarize": default_binarize,
                "invert": default_invert,
                "merge_batch_results": default_merge_batch,
                "language_warning": "",
            },
        )

    try:
        available_languages = tuple(tejocr_engine.get_available_languages() or ())
    except Exception:
        available_languages = ()

    form_text = _build_fallback_form_message(
        _("OCR Options"),
        [
            "# " + _("Editable options"),
            "language={lang}".format(lang=default_lang),
            "output_mode={output}".format(output=default_output),
            "show_preview={preview}".format(preview="true" if default_preview else "false"),
            "preset={preset}".format(preset=default_preset),
            "merge_batch_results={merge}".format(merge="true" if default_merge_batch else "false"),
            "",
            "# " + _("Advanced controls (preset=custom to apply as-is)"),
            "psm={psm}".format(psm=default_psm),
            "oem={oem}".format(oem=default_oem),
            "scale={scale}".format(scale=default_scale),
            "improve_image={improve}".format(improve="true" if default_improve else "false"),
            "grayscale={grayscale}".format(grayscale="true" if default_grayscale else "false"),
            "binarize={binarize}".format(binarize="true" if default_binarize else "false"),
            "invert={invert}".format(invert="true" if default_invert else "false"),
        ],
    )
    form_input = uno_utils.show_multiline_input_box(
        title=_("OCR Options (Fallback)"),
        message=form_text,
        default_text=form_text,
        ctx=ctx,
        parent_frame=parent_frame,
        width=640,
        height=380,
    )
    if form_input is None:
        return None, None, False, {}

    values = _parse_fallback_form_fields(form_input)
    final_lang = _normalize_lang_codes(values.get("language", default_lang))
    final_lang, invalid_lang_codes, validated_langs = _validate_language_codes(final_lang, available_languages)
    lang_warning = _build_language_validation_message(final_lang, invalid_lang_codes, validated_langs)
    if not final_lang:
        final_lang = default_lang or constants.DEFAULT_OCR_LANGUAGE
    if lang_warning:
        uno_utils.show_message_box(
            _("Language Validation"),
            lang_warning,
            "warningbox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    final_output = _normalize_form_output_mode(
        values.get("output_mode", default_output),
        default_output,
    )
    if source_type != "selected" and final_output == constants.OUTPUT_MODE_REPLACE:
        final_output = constants.OUTPUT_MODE_CURSOR

    final_preview = _coerce_bool_text(
        values.get("show_preview", str(default_preview).lower()),
        default_preview,
    )
    final_merge_batch = _coerce_bool_text(
        values.get("merge_batch_results", str(default_merge_batch).lower()),
        default_merge_batch,
    )

    selected_preset = _coerce_preset_value(values.get("preset", default_preset), default_preset)
    selected_profile = constants.OCR_QUALITY_PRESETS.get(selected_preset, {})

    if selected_preset == constants.OCR_PRESET_CUSTOM:
        final_improve = _coerce_bool_text(
            values.get("improve_image", str(default_improve).lower()),
            default_improve,
        )

        final_psm = _mode_value(values.get("psm", default_psm), default_psm)
        if final_psm not in constants.TESSERACT_PSM_MODES:
            final_psm = constants.DEFAULT_PSM_MODE

        final_oem = _mode_value(values.get("oem", default_oem), default_oem)
        if final_oem not in constants.TESSERACT_OEM_MODES:
            final_oem = constants.DEFAULT_OEM_MODE

        final_scale = _coerce_scale_text(values.get("scale", default_scale), default_scale)
        final_grayscale = _coerce_bool_text(
            values.get("grayscale", str(default_grayscale).lower()),
            default_grayscale,
        )
        final_binarize = _coerce_bool_text(
            values.get("binarize", str(default_binarize).lower()),
            default_binarize,
        )
        final_invert = _coerce_bool_text(
            values.get("invert", str(default_invert).lower()),
            default_invert,
        )
    else:
        final_improve = bool(selected_profile.get("improve_image", default_improve))
        final_psm = str(selected_profile.get("psm", default_psm)).strip() or constants.DEFAULT_PSM_MODE
        final_oem = str(selected_profile.get("oem", default_oem)).strip() or constants.DEFAULT_OEM_MODE
        final_scale = _coerce_scale_text(selected_profile.get("scale", default_scale), default_scale)
        final_grayscale = bool(selected_profile.get("grayscale", default_grayscale))
        final_binarize = bool(selected_profile.get("binarize", default_binarize))
        final_invert = bool(selected_profile.get("invert", default_invert))
        if final_psm not in constants.TESSERACT_PSM_MODES:
            final_psm = constants.DEFAULT_PSM_MODE
        if final_oem not in constants.TESSERACT_OEM_MODES:
            final_oem = constants.DEFAULT_OEM_MODE

    logger.info(
        f"Custom OCR options: lang='{final_lang}', mode='{final_output}', improve={final_improve}, "
        f"psm='{final_psm}', oem='{final_oem}', scale='{final_scale}', "
        f"grayscale={final_grayscale}, binarize={final_binarize}, invert={final_invert}, preview={final_preview}, "
        f"preset={selected_preset}"
    )
    # Persist "last used for this run" hints so the next interaction opens where users left off.
    try:
        uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, final_lang, ctx)
        uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, final_output, ctx)
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_INVERT, "true" if final_invert else "false", ctx)
        uno_utils.set_setting(
            constants.CFG_KEY_MERGE_BATCH_RESULTS,
            "true" if final_merge_batch else "false",
            ctx,
        )
    except Exception:
        pass

    return (
        final_lang,
        final_output,
        final_improve,
        {
            "show_preview": final_preview,
            "merge_batch_results": final_merge_batch,
            "preset": selected_preset,
            "psm": final_psm,
            "oem": final_oem,
            "scale": final_scale,
            "grayscale": final_grayscale,
            "binarize": final_binarize,
            "invert": final_invert,
            "language_warning": lang_warning,
        }
    )

# =============================================================================
# PUBLIC WRAPPER CLASSES FOR TEJOCR_SERVICE.PY INTEGRATION  
# =============================================================================

class InteractiveSettingsDialogHandler:
    """Public wrapper for the interactive settings dialog."""
    
    def __init__(self, ctx, parent_frame=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
    
    def show_dialog(self):
        """Shows the interactive settings dialog and returns True if settings were saved."""
        return show_interactive_settings_dialog(self.ctx, self.parent_frame)

class InteractiveOptionsDialogHandler:
    """Public wrapper for the interactive OCR options dialog."""
    
    def __init__(self, ctx, parent_frame=None, source_type="selected", image_path=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
        self.source_type = source_type
        self.image_path = image_path
        
    def show_dialog(self):
        """Shows the OCR options dialog and returns (language, output_mode, improve_image, extra_options)."""
        return show_interactive_ocr_options_dialog(self.ctx, self.parent_frame, self.source_type, self.image_path)
