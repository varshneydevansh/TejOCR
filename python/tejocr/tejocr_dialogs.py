# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Handles the creation, display, and event logic for TejOCR dialogs."""

# CRITICAL: UNO bridge must be initialized first - these imports MUST come before anything else
import uno
import unohelper

# Standard Python imports
import os
import re
import site
import subprocess
import sys
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util

# Import UNO interfaces directly from the uno module (safer than com.sun.star imports)
# These are commonly exposed by the uno module itself
try:
    from uno import XActionListener, XItemListener
except ImportError:
    # Fallback: Access via UNO type system
    try:
        from com.sun.star.awt import XActionListener, XItemListener
    except ImportError as e:
        # This would be a critical failure, but we'll define dummy classes to prevent module loading failure
        class XActionListener: pass
        class XItemListener: pass

# Import other UNO types with similar safety
try:
    from com.sun.star.task import XJobExecutor
except ImportError as e:
    class XJobExecutor: pass

# Then your project's modules
from tejocr import uno_utils
from tejocr import constants
from tejocr import ocr_runtime
from tejocr import locale_setup

_ = locale_setup.get_translation_function()

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Dialogs")

_MODE_ALIAS_RE = re.compile(r"^([a-z0-9_]+)\s+(.+)$")


def _clean_mode_description(description):
    cleaned = str(description or "").strip()
    if not cleaned:
        return cleaned

    match = _MODE_ALIAS_RE.match(cleaned)
    if not match:
        return cleaned

    alias, remainder = match.groups()
    if "_" in alias or alias in {"auto", "default"}:
        return remainder.strip()
    return cleaned


def _get_runtime_psm_map(ctx=None):
    tesseract_path = _resolve_tesseract_path(ctx)
    if not tesseract_path:
        return dict(constants.TESSERACT_PSM_MODES)

    descriptions = _extract_mode_descriptions([tesseract_path, "--help-psm"])
    if not descriptions:
        return dict(constants.TESSERACT_PSM_MODES)

    runtime_map = {}
    for mode, fallback_text in constants.TESSERACT_PSM_MODES.items():
        description = descriptions.get(mode)
        if description:
            description = _clean_mode_description(description)
            if mode == "0":
                if "diagnostic mode" not in description.lower():
                    description = "{description} Diagnostic mode; no OCR text output.".format(
                        description=description.rstrip(".")
                    )
            elif mode == "2" and "diagnostic mode" not in description.lower():
                suffix = "Diagnostic mode; no OCR text output."
                if "not implemented" not in description.lower():
                    suffix = "Diagnostic mode; not implemented for text output."
                description = "{description} {suffix}".format(
                    description=description.rstrip("."),
                    suffix=suffix,
                )
            runtime_map[mode] = "{mode}: {description}".format(mode=mode, description=description)
        else:
            runtime_map[mode] = fallback_text
    return runtime_map


def _get_runtime_oem_map(ctx=None):
    tesseract_path = _resolve_tesseract_path(ctx)
    descriptions = _extract_mode_descriptions([tesseract_path, "--help-oem"]) if tesseract_path else {}
    support = _get_runtime_oem_support(ctx)

    runtime_map = {}
    for mode, fallback_text in constants.TESSERACT_OEM_MODES.items():
        description = descriptions.get(mode)
        if description:
            description = _clean_mode_description(description)
            label = "{mode}: {description}".format(mode=mode, description=description)
        else:
            label = fallback_text
        if not support.get(mode, True):
            label = "{label} (unsupported by current traineddata/runtime)".format(label=label)
        runtime_map[mode] = label
    return runtime_map


def _get_runtime_oem_support(ctx=None):
    tesseract_path = _resolve_tesseract_path(ctx)
    if not tesseract_path:
        return {mode: True for mode in constants.TESSERACT_OEM_MODES}

    descriptions = _extract_mode_descriptions([tesseract_path, "--help-oem"])
    if not descriptions:
        return {mode: True for mode in constants.TESSERACT_OEM_MODES}

    support = {}
    for mode in constants.TESSERACT_OEM_MODES:
        support[mode] = mode in descriptions
    return support


def _coerce_supported_oem_value(mode_value, ctx=None, support_map=None, fallback=None):
    fallback_value = str(fallback or constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
    candidate = str(mode_value or fallback_value).strip() or fallback_value
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0].strip() or fallback_value
    if candidate not in constants.TESSERACT_OEM_MODES:
        candidate = fallback_value
    return ocr_runtime.coerce_supported_oem(
        candidate,
        support_map or _get_runtime_oem_support(ctx),
        fallback=fallback_value,
    )

# We will import tejocr_engine when needed for OCR tasks.
PYTESSERACT_LANGUAGES = {}
LANG_CODE_TO_NAME = {
    "afr": "Afrikaans", "amh": "Amharic", "ara": "Arabic", "asm": "Assamese",
    "aze": "Azerbaijani", "bel": "Belarusian", "ben": "Bengali", "bod": "Tibetan",
    "bos": "Bosnian", "bre": "Breton", "bul": "Bulgarian", "cat": "Catalan",
    "ceb": "Cebuano", "ces": "Czech", "chi_sim": "Chinese (Simplified)",
    "chi_tra": "Chinese (Traditional)", "chr": "Cherokee", "cos": "Corsican",
    "cym": "Welsh", "dan": "Danish", "deu": "German", "div": "Dhivehi",
    "dzo": "Dzongkha", "ell": "Greek", "eng": "English", "enm": "English (Middle)",
    "epo": "Esperanto", "est": "Estonian", "eus": "Basque", "fao": "Faroese",
    "fas": "Persian", "fil": "Filipino", "fin": "Finnish", "fra": "French",
    "frm": "French (Middle)", "fry": "Frisian", "gla": "Scottish Gaelic",
    "gle": "Irish", "glg": "Galician", "grc": "Greek (Ancient)", "guj": "Gujarati",
    "hat": "Haitian Creole", "heb": "Hebrew", "hin": "Hindi", "hrv": "Croatian",
    "hun": "Hungarian", "hye": "Armenian", "iku": "Inuktitut", "ind": "Indonesian",
    "isl": "Icelandic", "ita": "Italian", "jav": "Javanese", "jpn": "Japanese",
    "kan": "Kannada", "kat": "Georgian", "kaz": "Kazakh", "khm": "Khmer",
    "kir": "Kyrgyz", "kmr": "Kurdish (Kurmanji)", "kor": "Korean",
    "lao": "Lao", "lat": "Latin", "lav": "Latvian", "lit": "Lithuanian",
    "ltz": "Luxembourgish", "mal": "Malayalam", "mar": "Marathi", "mkd": "Macedonian",
    "mlt": "Maltese", "mon": "Mongolian", "mri": "Maori", "msa": "Malay",
    "mya": "Myanmar (Burmese)", "nep": "Nepali", "nld": "Dutch", "nor": "Norwegian",
    "oci": "Occitan", "ori": "Odia", "osd": "Script Detection",
    "pan": "Punjabi", "pol": "Polish", "por": "Portuguese", "pus": "Pashto",
    "que": "Quechua", "ron": "Romanian", "rus": "Russian", "san": "Sanskrit",
    "sin": "Sinhala", "slk": "Slovak", "slv": "Slovenian", "snd": "Sindhi",
    "spa": "Spanish", "sqi": "Albanian", "srp": "Serbian", "sun": "Sundanese",
    "swa": "Swahili", "swe": "Swedish", "syr": "Syriac", "tam": "Tamil",
    "tat": "Tatar", "tel": "Telugu", "tgk": "Tajik", "tha": "Thai",
    "tir": "Tigrinya", "ton": "Tonga", "tur": "Turkish", "uig": "Uyghur",
    "ukr": "Ukrainian", "urd": "Urdu", "uzb": "Uzbek", "vie": "Vietnamese",
    "yid": "Yiddish", "yor": "Yoruba",
}

def _resolve_tesseract_path(ctx=None):
    configured = ""
    try:
        configured = uno_utils.get_setting(
            constants.CFG_KEY_TESSERACT_PATH,
            constants.DEFAULT_TESSERACT_PATH,
            ctx,
        )
    except Exception:
        configured = constants.DEFAULT_TESSERACT_PATH
    return uno_utils.find_tesseract_executable(configured) or ""


def _split_help_mode_line(raw_line):
    line = str(raw_line or "").strip()
    if not line or "|" not in line:
        return None, None
    left, right = line.split("|", 1)
    mode = left.strip()
    if not mode.isdigit():
        return None, None
    return mode, right.strip()


def _extract_mode_descriptions(command):
    if not command or not command[0]:
        return {}
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return {}

    output = "\n".join([result.stdout or "", result.stderr or ""]).splitlines()
    descriptions = {}
    pending_mode = None
    for raw_line in output:
        mode, description = _split_help_mode_line(raw_line)
        if mode:
            descriptions[mode] = description
            pending_mode = mode
            continue
        if pending_mode and str(raw_line).startswith(" "):
            descriptions[pending_mode] = "{current} {extra}".format(
                current=descriptions[pending_mode],
                extra=str(raw_line).strip(),
            ).strip()
        else:
            pending_mode = None
    return descriptions


def _get_tesseract_language_map(ctx=None):
    tesseract_path = _resolve_tesseract_path(ctx)
    if not tesseract_path:
        return {k: v for k, v in LANG_CODE_TO_NAME.items()}

    try:
        result = subprocess.run(
            [tesseract_path, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as error:
        logger.warning("Could not list Tesseract languages: %s", error)
        return {k: v for k, v in LANG_CODE_TO_NAME.items()}

    output = result.stdout or result.stderr or ""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if lines and lines[0].lower().startswith("list of available languages"):
        lines = lines[1:]
    languages = sorted(dict.fromkeys(line for line in lines if line))
    if not languages:
        return {k: v for k, v in LANG_CODE_TO_NAME.items()}
    return {code: LANG_CODE_TO_NAME.get(code, code) for code in languages}


def _package_status(module_name, distribution_name=None):
    if not importlib_util.find_spec(module_name):
        return False, ""
    try:
        version = importlib_metadata.version(distribution_name or module_name)
    except Exception:
        version = ""
    return True, version

# --- Dialog Base Class (Optional, but can be useful for common functionality) ---
class BaseDialogHandler(unohelper.Base, XActionListener, XItemListener):
    def __init__(self, ctx, dialog_url):
        self.ctx = ctx
        self.dialog_url = dialog_url # e.g., "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/..."
        self.dialog = None
        self.parent_frame = None
        self.closed_by_ok = False # Flag to indicate how the dialog was closed
        self._last_successful_dialog_url = None
        self._last_dialog_creation_error = None
        self._last_dialog_creation_errors = []
        self._feedback_cache = {}

        # Feedback colors
        self.COLOR_BTN_PRIMARY = 0x2d7bff
        self.COLOR_BTN_SUCCESS = 0x22C55E
        self.COLOR_BTN_WARNING = 0xF59E0B
        self.COLOR_BTN_DANGER = 0xEF4444
        self.COLOR_TEXT_ON_DARK = 0xFFFFFF

    @staticmethod
    def _bool_to_state(value):
        """Convert a setting value (string, bool, int) to an int suitable for setState (0 or 1)."""
        if isinstance(value, str):
            return 1 if value.lower() in ('true', '1', 'yes') else 0
        return 1 if value else 0

    @staticmethod
    def _state_to_setting_string(value):
        """Serialize a checkbox/radio state into the persisted true/false string form."""
        return "true" if BaseDialogHandler._bool_to_state(value) else "false"

    @staticmethod
    def _select_dropdown_item(dropdown, pos):
        """Select an item in a dropdown, auto-detecting MenuList vs ComboBox."""
        try:
            # MenuList (dlg:menulist) handles selectItemPos natively
            dropdown.selectItemPos(pos, True)
        except AttributeError:
            # ComboBox (dlg:combobox) uses setText
            try:
                item_text = dropdown.getItem(pos)
                dropdown.setText(item_text)
            except Exception:
                pass

    def _ensure_dropdown_mode(self, control_name):
        """Force a menulist control into closed-dropdown mode programmatically.
        Works around XDL dlg:dropdown='true' being ignored by some LO builds."""
        ctrl = self.get_control(control_name)
        if ctrl:
            try:
                ctrl.getModel().Dropdown = True
            except Exception:
                pass

    def _create_dialog(self, parent_frame):
        """Creates and initializes the dialog from its URL."""
        self._last_successful_dialog_url = None
        return self._create_dialog_with_urls(parent_frame, [self.dialog_url], suppress_user_message=False)

    def _create_dialog_with_urls(self, parent_frame, dialog_urls, suppress_user_message=False):
        """Try creating the dialog from one or more URLs and report detailed errors."""
        self.parent_frame = parent_frame
        self._last_successful_dialog_url = None
        self._last_dialog_creation_error = None
        self._last_dialog_creation_errors = []

        if not dialog_urls:
            self._last_dialog_creation_error = "No dialog URLs were provided."
            logger.warning(self._last_dialog_creation_error)
            return False

        try:
            dp = uno_utils.create_instance("com.sun.star.awt.DialogProvider", self.ctx)
            if not dp:
                self._last_dialog_creation_error = "Could not create DialogProvider."
                logger.warning(self._last_dialog_creation_error)
                uno_utils.show_message_box(
                    "Dialog Creation Error",
                    self._last_dialog_creation_error,
                    "errorbox",
                    parent_frame=parent_frame,
                    ctx=self.ctx,
                )
                return False
        except Exception as e:
            self._last_dialog_creation_error = f"DialogProvider creation failed: {e}"
            self._last_dialog_creation_errors.append(self._last_dialog_creation_error)
            logger.error(self._last_dialog_creation_error, exc_info=True)
            uno_utils.show_message_box(
                "Dialog Creation Error",
                f"Could not initialize dialog provider. {self._last_dialog_creation_error}",
                "errorbox",
                parent_frame=parent_frame,
                ctx=self.ctx,
            )
            return False

        for url in dialog_urls:
            try:
                logger.debug(f"Attempting to create dialog using URL: {url}")
                self.dialog = dp.createDialog(url)
                if not self.dialog:
                    err = f"Dialog provider returned None for URL: {url}"
                    self._last_dialog_creation_errors.append(err)
                    logger.warning(err)
                    continue

                logger.info(f"Dialog created successfully from URL: {url}")
                self._last_successful_dialog_url = url
                
                # Set parent peer if possible for modality and positioning
                # LibreOffice AWTPeer doesn't support setParent directly in Python for dialogs.
                # Dialog modality is handled by execute() anyway.
                # if parent_frame and parent_frame.getContainerWindow():
                #     self.dialog.getPeer().setParent(parent_frame.getContainerWindow().getPeer())
                
                self._init_controls() # Initialize controls and listeners
                return True

            except Exception as e:
                err = f"Exception creating dialog from URL '{url}': {e}"
                self._last_dialog_creation_errors.append(err)
                logger.error(err, exc_info=True)
                continue

        self._last_dialog_creation_error = "\n".join(self._last_dialog_creation_errors) if self._last_dialog_creation_errors else "Dialog could not be created for unknown reason."
        if not suppress_user_message:
            uno_utils.show_message_box(
                "Dialog Error",
                f"Could not create dialog. {self._last_dialog_creation_error}",
                "errorbox",
                parent_frame=parent_frame,
                ctx=self.ctx,
            )
        return False

    def _init_controls(self):
        """Initialize dialog controls and attach listeners. To be implemented by subclasses."""
        pass # Override in specific dialog handlers

    def execute(self):
        """Shows the dialog modally and returns True if OK was pressed, False otherwise."""
        if not self.dialog:
            return False
        self.closed_by_ok = False # Reset before execution
        result = self.dialog.execute()
        # Standard LibreOffice dialogs return 1 for OK-like buttons
        # Custom dialogs might vary, so we use our flag set by action listeners
        return self.closed_by_ok or result == 1 

    def _get_action_command(self, event):
        """Best-effort extraction of an action command from a LibreOffice event."""
        if event is None:
            return None

        # Common event payload path.
        for attr in ("ActionCommand", "actionCommand", "Actioncommand"):
            try:
                value = getattr(event, attr, None)
                if callable(value):
                    value = value()
                if value:
                    return str(value)
            except Exception:
                pass

        # Fallback to source model payload.
        try:
            source = getattr(event, "Source", None)
            if callable(source):
                source = source()
            if source:
                model = getattr(source, "getModel", None)
                if callable(model):
                    model = model()
                if model:
                    value = getattr(model, "ActionCommand", None)
                    if callable(value):
                        value = value()
                    if value:
                        return str(value)
                    value = getattr(model, "getActionCommand", None)
                    if callable(value):
                        value = value()
                        if value:
                            return str(value)
        except Exception:
            pass

        return None

    def _get_event_source_control(self, event):
        """Best-effort extraction of control object from action event."""
        if event is None:
            return None
        try:
            source = getattr(event, "Source", None)
            if callable(source):
                source = source()
            if source:
                return source
        except Exception:
            pass
        return None

    def _capture_control_feedback_state(self, control):
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

    def _restore_control_feedback_state(self, control, state):
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

    def _set_control_feedback(
        self,
        control,
        text=None,
        enabled=None,
        bg_color=None,
        fg_color=None,
    ):
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

    def dispose(self):
        """Disposes of the dialog."""
        if self.dialog:
            self.dialog.dispose()
            self.dialog = None

    # --- XActionListener --- (Common actions)
    def actionPerformed(self, event):
        """Handles action events (e.g., button clicks)."""
        command = self._get_action_command(event)
        # print(f"BaseDialog: ActionPerformed - {command}")
        if command == "ok" or command == "run_ocr" or command == "save_settings": # Common OK/Run commands
            self.closed_by_ok = True
            logger.debug(f"Dialog '{self.dialog_url}' OK/Run action started for command: {command}")
            if self._handle_ok_action(): # Only end execute if validation passes
                logger.debug(f"Dialog '{self.dialog_url}' _handle_ok_action successful, ending execute.")
                self.dialog.endExecute()
            else:
                logger.warning(f"Dialog '{self.dialog_url}' _handle_ok_action failed or returned False, not closing.")
                self.closed_by_ok = False # Reset if validation failed
        elif command == "cancel":
            self.closed_by_ok = False
            logger.debug(f"Dialog '{self.dialog_url}' Cancel action for command: {command}")
            self._handle_cancel_action()
            self.dialog.endExecute()
        elif command == "help":
            logger.debug(f"Dialog '{self.dialog_url}' Help action for command: {command}")
            self._handle_help_action()
        # Other commands to be handled by subclasses

    def _handle_ok_action(self):
        """Placeholder for OK action. Subclasses should override if specific data needs to be saved."""
        return True # Return True if OK, False if validation fails

    def _handle_cancel_action(self):
        """Placeholder for Cancel action."""
        pass

    def _handle_help_action(self):
        """Placeholder for Help action."""
        uno_utils.show_message_box("Help", "Help for this dialog is not yet implemented.", parent_frame=self.parent_frame, ctx=self.ctx)

    # --- XItemListener --- (Common for checkboxes, radio buttons, listboxes)
    def itemStateChanged(self, event):
        """Handles item state changes. To be implemented by subclasses if needed."""
        pass # Override in specific dialog handlers

    def get_control(self, name):
        """Helper to get a control from the dialog."""
        if self.dialog:
            return self.dialog.getControl(name)
        return None

    def _add_listener_to_control(self, control_name, action_command=None):
        control = self.get_control(control_name)
        if control:
            if action_command:
                control.setActionCommand(action_command)
            control.addActionListener(self)
        return control

    def _add_item_listener_to_control(self, control_name):
        control = self.get_control(control_name)
        if control:
            control.addItemListener(self)
        return control 

# --- OCR Options Dialog Handler ---
class OptionsDialogHandler(BaseDialogHandler):
    def __init__(self, ctx, ocr_source_type="file", image_path=None): # ocr_source_type: "file" or "selected"
        # Use extension URL scheme that LibreOffice recognizes for extension XDL files
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_options_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.ctx = ctx
        self.ocr_source_type = ocr_source_type  # "file" or "selected"
        self.image_path = image_path  # Path to image file (if ocr_source_type == "file") or None for selected
        self.selected_options = {}
        self.recognized_text = None
        self.available_languages_map = {}

    def _init_controls(self):
        """Initialize controls and attach listeners for the Options dialog."""
        logger.info(f"OptionsDialogHandler: _init_controls called for source type: {self.ocr_source_type}")
        
        # Attach button listeners
        self._add_listener_to_control("RunOCRButton", "run_ocr") 
        self._add_listener_to_control("CancelButton", "cancel")
        self._add_listener_to_control("HelpButton", "help")
        self._add_listener_to_control("RefreshLanguagesButton", "refresh_languages")
        
        # Force menulist controls into dropdown mode
        self._ensure_dropdown_mode("LanguageDropdown")
        self._ensure_dropdown_mode("PSMDropdown")
        self._ensure_dropdown_mode("OEMDropdown")
        
        # Initialize dialog content
        self._setup_source_information()
        self._load_default_settings()
        self._populate_dropdowns()
        self._enable_disable_controls()

    def _setup_source_information(self):
        """Set up the source information section based on OCR type."""
        source_desc_label = self.get_control("SourceDescriptionLabel")
        if source_desc_label:
            if self.ocr_source_type == "file":
                if self.image_path:
                    filename = os.path.basename(self.image_path)
                    source_desc_label.setText(f"Image file: {filename}")
                else:
                    source_desc_label.setText("Image file (to be selected)")
            elif self.ocr_source_type == "selected":
                source_desc_label.setText("Selected image in document")
            else:
                source_desc_label.setText(f"OCR source: {self.ocr_source_type}")

    def _load_default_settings(self):
        """Load default settings from configuration."""
        # Load language preference
        default_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
        
        # Load output mode preference
        default_output_mode = uno_utils.get_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, constants.DEFAULT_OUTPUT_MODE, self.ctx)
        self._load_output_mode(default_output_mode)
        
        # Load preprocessing defaults
        default_grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, constants.DEFAULT_PREPROC_GRAYSCALE, self.ctx)
        default_binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, constants.DEFAULT_PREPROC_BINARIZE, self.ctx)
        
        grayscale_cb = self.get_control("GrayscaleCheckbox")
        if grayscale_cb: grayscale_cb.setState(self._bool_to_state(default_grayscale))
        
        binarize_cb = self.get_control("BinarizeCheckbox")
        if binarize_cb: binarize_cb.setState(self._bool_to_state(default_binarize))

    def _populate_dropdowns(self):
        """Populate all dropdown controls with available options."""
        # Populate language dropdown
        self._populate_languages_dropdown()
        
        # Populate PSM dropdown
        self._populate_psm_dropdown()
        
        # Populate OEM dropdown
        self._populate_oem_dropdown()

    def _enable_disable_controls(self):
        """Enable/disable controls based on context."""
        # Disable "Replace Image" option if not processing a selected image
        replace_radio = self.get_control("OutputReplaceImageRadio")
        if replace_radio:
            replace_radio.setEnable(self.ocr_source_type == "selected")
            
        # If replace image is disabled and was selected, switch to cursor mode
        if self.ocr_source_type != "selected" and replace_radio and replace_radio.getState():
            cursor_radio = self.get_control("OutputAtCursorRadio")
            if cursor_radio:
                cursor_radio.setState(True)
                replace_radio.setState(False)

    def _load_output_mode(self, default_mode=None):
        """Load output mode selection."""
        if default_mode is None:
            default_mode = uno_utils.get_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, constants.DEFAULT_OUTPUT_MODE, self.ctx)
        
        controls = {
            constants.OUTPUT_MODE_CURSOR: "OutputAtCursorRadio",
            constants.OUTPUT_MODE_TEXTBOX: "OutputNewTextboxRadio",
            constants.OUTPUT_MODE_REPLACE: "OutputReplaceImageRadio",
            constants.OUTPUT_MODE_CLIPBOARD: "OutputToClipboardRadio"
        }
        
        # Reset all radio buttons first
        for control_id in controls.values():
            control = self.get_control(control_id)
            if control:
                control.setState(False)
        
        # Set the selected one
        selected_control_id = controls.get(default_mode, controls[constants.OUTPUT_MODE_CURSOR])
        selected_control = self.get_control(selected_control_id)
        if selected_control:
            selected_control.setState(True)
    def actionPerformed(self, event):
        source_control = self._get_event_source_control(event)
        command = self._get_action_command(event)
        if not command:
            logger.warning("OptionsDialog: action event missing command.")
            return

        # Give immediate visual feedback on user action.
        if command == "run_ocr":
            baseline = self._capture_control_feedback_state(source_control)
            status_label = self.get_control("StatusLabel")
            self._set_control_feedback(
                source_control,
                text="Processing...",
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            if status_label:
                status_label.setText("Starting OCR processing...")
            super().actionPerformed(event)  # Handles run_ocr/cancel/help (if not overridden)
            self._restore_control_feedback_state(source_control, baseline)
            return

        if command == "refresh_languages":
            baseline = self._capture_control_feedback_state(source_control)
            status_label = self.get_control("StatusLabel")
            self._set_control_feedback(
                source_control,
                text="Refreshing...",
                enabled=False,
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            if status_label:
                status_label.setText("Refreshing language list...")
            try:
                self._refresh_languages()
            finally:
                self._restore_control_feedback_state(source_control, baseline)
            return

        if command == "cancel":
            baseline = self._capture_control_feedback_state(source_control)
            status_label = self.get_control("StatusLabel")
            if status_label:
                status_label.setText("Cancelling...")
            self._set_control_feedback(
                source_control,
                text="Cancelling...",
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            super().actionPerformed(event)
            self._restore_control_feedback_state(source_control, baseline)
            return

        super().actionPerformed(event) # Handles run_ocr, cancel, help (if not overridden)
        logger.debug(f"OptionsDialogHandler actionPerformed: {command}")

        # NOTE: "help" is handled by super().actionPerformed() — do not duplicate here
        # "run_ocr" handling is already handled through super() above.

    def _refresh_languages(self):
        """Refresh the language list."""
        self.available_languages_map = {}  # Clear cache
        self._populate_languages_dropdown()
        status_label = self.get_control("StatusLabel")
        if status_label:
            status_label.setText("Language list refreshed")

    def _show_help(self):
        """Show help for the OCR Options dialog."""
        help_text = f"""ℹ️ {constants.EXTENSION_FULL_NAME} - OCR Options Help

✅ LANGUAGE SELECTION:
• Choose the language of text in your image
• Correct language selection improves accuracy

✅ BATCH & PDF OPTIONS:
• Select one or more image files and/or PDFs via the 'OCR File' menu.
• Merge bulk/PDF results combines all pages into one output block.
• Disable merge to insert each source/page separately.

✅ OUTPUT MODE:
• Cursor: Insert text at current cursor position
• Text Box: Create a new text box with the text
• Replace Image: Replace selected image with text
• Clipboard: Copy text to system clipboard

⚠️ ADVANCED OPTIONS:
• Preset defines a profile for extraction: Fast, Balanced, Accuracy.
• PSM: Page segments (0-13). 
  - 3: fully automatic layout (recommended default)
  - 6: single uniform text block
  - 11: sparse text anywhere
• OEM: Engine mode (0-3).
  - 1: LSTM engine only (good for modern)
  - 3: auto (recommended default)

💡 TIP:
• Change PSM/OEM/Preset defaults in the main TejOCR Settings dialog."""
        
        uno_utils.show_message_box("OCR Options Help", help_text, "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _handle_help_action(self):
        """Handle Help button for OCR options."""
        self._show_help()

    def _handle_ok_action(self):
        """Collect options and perform OCR."""
        logger.info("OCR Options: Starting OCR process...")
        
        try:
            # Collect all selected options
            self._collect_selected_options()
            
            # Update status
            status_label = self.get_control("StatusLabel")
            if status_label: 
                status_label.setText("Starting OCR processing...")
            
            # Perform OCR based on source type
            if self.ocr_source_type == "file":
                result = self._perform_file_ocr()
            elif self.ocr_source_type == "selected":
                result = self._perform_selected_image_ocr()
            else:
                raise ValueError(f"Unknown OCR source type: {self.ocr_source_type}")
            
            if result:
                self.recognized_text = result
                if status_label: 
                    status_label.setText(f"OCR completed! Found {len(result)} characters")
                
                # Process the output according to selected mode
                self._handle_output()
                return True  # Success - close dialog
            else:
                if status_label: 
                    status_label.setText("OCR failed or no text found")
                return False  # Keep dialog open
                
        except Exception as e:
            logger.error(f"Error in OCR options dialog: {e}", exc_info=True)
            status_label = self.get_control("StatusLabel")
            if status_label: 
                status_label.setText("Error during OCR processing")
            uno_utils.show_message_box("OCR Error", f"OCR processing failed: {e}", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
            return False  # Keep dialog open

    def _collect_selected_options(self):
        """Collect all user-selected options."""
        self.selected_options = {}
        
        # Language
        lang_dropdown = self.get_control("LanguageDropdown")
        if lang_dropdown and lang_dropdown.getItemCount() > 0:
            selected_lang_display = lang_dropdown.getSelectedItem()
            # Map display name back to code
            inverted_lang_map = {v: k for k, v in self.available_languages_map.items()}
            self.selected_options["lang"] = inverted_lang_map.get(selected_lang_display, constants.DEFAULT_OCR_LANGUAGE)
        else:
            self.selected_options["lang"] = constants.DEFAULT_OCR_LANGUAGE
        
        # Output Mode
        output_modes_map = {
            "OutputAtCursorRadio": constants.OUTPUT_MODE_CURSOR,
            "OutputNewTextboxRadio": constants.OUTPUT_MODE_TEXTBOX,
            "OutputReplaceImageRadio": constants.OUTPUT_MODE_REPLACE,
            "OutputToClipboardRadio": constants.OUTPUT_MODE_CLIPBOARD
        }
        
        self.selected_options["output_mode"] = constants.DEFAULT_OUTPUT_MODE
        for control_id, mode_value in output_modes_map.items():
            control = self.get_control(control_id)
            if control and control.getState():
                self.selected_options["output_mode"] = mode_value
                break
        
        # PSM (Page Segmentation Mode)
        psm_dropdown = self.get_control("PSMDropdown")
        if psm_dropdown and psm_dropdown.getItemCount() > 0:
            selected_psm_display = psm_dropdown.getSelectedItem()
            inverted_psm_map = {v: k for k, v in getattr(self, "psm_mode_map", constants.TESSERACT_PSM_MODES).items()}
            self.selected_options["psm"] = inverted_psm_map.get(selected_psm_display, constants.DEFAULT_PSM_MODE)
        else:
            self.selected_options["psm"] = constants.DEFAULT_PSM_MODE

        # OEM (OCR Engine Mode)
        oem_dropdown = self.get_control("OEMDropdown")
        if oem_dropdown and oem_dropdown.getItemCount() > 0:
            selected_oem_display = oem_dropdown.getSelectedItem()
            inverted_oem_map = {v: k for k, v in getattr(self, "oem_mode_map", constants.TESSERACT_OEM_MODES).items()}
            selected_oem = inverted_oem_map.get(selected_oem_display, constants.DEFAULT_OEM_MODE)
            selected_oem, _oem_warning = _coerce_supported_oem_value(
                selected_oem,
                ctx=self.ctx,
                fallback=constants.DEFAULT_OEM_MODE,
            )
            self.selected_options["oem"] = selected_oem
        else:
            self.selected_options["oem"] = constants.DEFAULT_OEM_MODE

        # Preprocessing
        grayscale_cb = self.get_control("GrayscaleCheckbox")
        binarize_cb = self.get_control("BinarizeCheckbox")
        
        self.selected_options["grayscale"] = bool(grayscale_cb.getState() if grayscale_cb else False)
        self.selected_options["binarize"] = bool(binarize_cb.getState() if binarize_cb else False)

        logger.info(f"Collected OCR options: {self.selected_options}")
        
        # Save last used options for next time
        uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, self.selected_options["output_mode"], self.ctx)

    def _perform_file_ocr(self):
        """Perform OCR on a file."""
        if not self.image_path:
            raise ValueError("No image file path provided for file OCR")
        
        # Import engine module
        from . import tejocr_engine
        return tejocr_engine.extract_text_from_image_file(
            self.image_path,
            self.ctx,
            language=self.selected_options.get("lang", constants.DEFAULT_OCR_LANGUAGE),
            psm=self.selected_options.get("psm", constants.DEFAULT_PSM_MODE),
            oem=self.selected_options.get("oem", constants.DEFAULT_OEM_MODE),
            preprocess_grayscale=self.selected_options.get("grayscale", False),
            preprocess_binarize=self.selected_options.get("binarize", False)
        )

    def _perform_selected_image_ocr(self):
        """Perform OCR on selected image."""
        # Import engine module
        from . import tejocr_engine
        return tejocr_engine.extract_text_from_selected_image(
            self.ctx,
            language=self.selected_options.get("lang", constants.DEFAULT_OCR_LANGUAGE),
            psm=self.selected_options.get("psm", constants.DEFAULT_PSM_MODE),
            oem=self.selected_options.get("oem", constants.DEFAULT_OEM_MODE),
            preprocess_grayscale=self.selected_options.get("grayscale", False),
            preprocess_binarize=self.selected_options.get("binarize", False)
        )

    def _handle_output(self):
        """Handle the recognized text according to selected output mode."""
        if not self.recognized_text:
            return
        
        # Import output module
        from . import tejocr_output
        
        output_mode = self.selected_options.get("output_mode", constants.OUTPUT_MODE_CURSOR)
        
        if output_mode == constants.OUTPUT_MODE_CURSOR:
            tejocr_output.insert_text_at_cursor(self.recognized_text, self.ctx)
        elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
            tejocr_output.create_text_box_with_text(self.recognized_text, self.ctx)
        elif output_mode == constants.OUTPUT_MODE_REPLACE:
            if self.ocr_source_type == "selected":
                tejocr_output.replace_selected_image_with_text(self.recognized_text, self.ctx)
            else:
                # Fallback to cursor if replace not applicable
                tejocr_output.insert_text_at_cursor(self.recognized_text, self.ctx)
        elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
            tejocr_output.copy_text_to_clipboard(self.recognized_text, self.ctx)
        
        logger.info(f"Text output handled with mode: {output_mode}")

    def _populate_languages_dropdown(self):
        langs = self._get_tesseract_languages()
        self.available_languages_map = langs # Store for retrieval in _handle_ok_action
        self._populate_dropdown("LanguageDropdown", langs, constants.CFG_KEY_LAST_SELECTED_LANG, constants.DEFAULT_OCR_LANGUAGE)

    def _populate_psm_dropdown(self):
        self.psm_mode_map = _get_runtime_psm_map(self.ctx)
        self._populate_dropdown("PSMDropdown", self.psm_mode_map, "LastPSMMode", constants.DEFAULT_PSM_MODE)

    def _populate_oem_dropdown(self):
        self.oem_mode_map = _get_runtime_oem_map(self.ctx)
        self._populate_dropdown("OEMDropdown", self.oem_mode_map, "LastOEMMode", constants.DEFAULT_OEM_MODE)

    def _populate_dropdown(self, control_name, items_map, current_value_key, default_value):
        dropdown = self.get_control(control_name)
        if not dropdown: return

        stored_value = uno_utils.get_setting(current_value_key, default_value, self.ctx)
        logger.info(f"Populating {control_name}: stored='{stored_value}', default='{default_value}'")

        model = dropdown.getModel()
        model.StringItemList = ()   # clear
        
        selected_pos = 0
        item_keys = list(items_map.keys())
        texts = []

        for i, key in enumerate(item_keys):
            display_text = f"{items_map[key]} ({key})"
            texts.append(display_text)
            if str(key) == str(stored_value):
                selected_pos = i

        model.StringItemList = tuple(texts)
        if len(texts) > 0:
            model.SelectedItems = (selected_pos,)
            # Also set via control API for cross-version compatibility
            try:
                dropdown.selectItemPos(selected_pos, True)
            except Exception:
                pass
        self.available_languages_map = items_map

    def _get_tesseract_languages(self):
        global PYTESSERACT_LANGUAGES
        if not PYTESSERACT_LANGUAGES:
            PYTESSERACT_LANGUAGES = _get_tesseract_language_map(self.ctx)
        return PYTESSERACT_LANGUAGES

# --- Settings Dialog Handler ---
class SettingsDialogHandler(BaseDialogHandler):
    SETTINGS_UI_TEXT = {
        "SectionDependency": "System Readiness",
        "SetupButton": "Setup & Diagnostics...",
        "WikiButton": "Open TejOCR Wiki",
        "FilterTubeButton": "FilterTube.in (Free Open Source)",
        "FilterTubeTagline2": "  Block/ WHITELIST Anything on YouTube",
        "SectionPath": "Tesseract Engine Path",
        "TesseractPathLabel": "Executable path (leave blank for automatic detection):",
        "BrowseButton": "...",
        "TestTesseractButton": "Test",
        "UiLanguageLabel": "Extension UI:",
        "SectionLanguage": "OCR Languages (Cmd/Ctrl + click to combine multiple)",
        "SearchLabel": "Search:",
        "SearchLanguagesButton": "Search",
        "RefreshLanguagesButtonSettings": "Refresh List",
        "SelectedLangsLabel": "Selected: (none)",
        "SectionOutput": "Default Quality & Insertion Settings",
        "DefaultPresetLabel": "Preset:",
        "OutputModeLabel": "Output:",
        "OutputRadioCursor": "Insert at cursor",
        "OutputRadioTextBox": "Create text box",
        "OutputRadioReplace": "Replace image",
        "OutputRadioClipboard": "Copy to clipboard",
        "DefaultGrayscaleCheckbox": "Grayscale filter",
        "DefaultBinarizeCheckbox": "Binarize (BW)",
        "DefaultPreviewCheckbox": "Preview OCR text before insert",
        "DefaultMergeBatchCheckbox": "Merge bulk/PDF into single output",
        "SectionParams": "Engine Performance Tuning",
        "AdvancedParamsButton": "Advanced Engine Parameters (Custom Preset Only)...",
        "SettingsStatusLabel": "Ready",
        "HelpButtonSettings": "Help...",
        "MessageButtonSettings": "A Message",
        "CancelButton": "Cancel",
        "SaveButton": "Save",
    }

    def __init__(self, ctx):
        # Use extension URL scheme that LibreOffice recognizes for extension XDL files
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_settings_dialog_full.xdl"
        super().__init__(ctx, dialog_url)
        try:
            locale_setup.configure(
                uno_utils.get_setting(constants.CFG_KEY_UI_LANGUAGE, constants.DEFAULT_UI_LANGUAGE, ctx),
                ctx=ctx,
            )
        except Exception:
            locale_setup.configure(constants.DEFAULT_UI_LANGUAGE)
        self.initial_settings = {} # To store settings when dialog opens to check for changes
        self.available_languages_map_settings = {} # Separate map for settings dialog
        self.dependency_status = None # Cache dependency check results
        self._settings_languages_cache = {}
        self._output_mode_code_order = []
        self._all_lang_keys = []
        self._all_lang_map = {}
        self._visible_lang_keys = []
        self._selected_codes = {constants.DEFAULT_OCR_LANGUAGE}

    def _settings_preset_items(self):
        return {
            constants.OCR_PRESET_FAST: _("Fast"),
            constants.OCR_PRESET_BALANCED: _("Balanced"),
            constants.OCR_PRESET_ACCURATE: _("Accuracy"),
            constants.OCR_PRESET_CUSTOM: _("Custom"),
        }

    def _set_dialog_title(self, title):
        if not self.dialog:
            return
        try:
            self.dialog.setTitle(title)
            return
        except Exception:
            pass
        try:
            self.dialog.getModel().Title = title
        except Exception:
            pass

    def _apply_ui_translations(self):
        """Translate static XDL labels after the selected catalog is configured."""
        self._set_dialog_title(_("TejOCR Settings"))
        for control_name, text in self.SETTINGS_UI_TEXT.items():
            ctrl = self.get_control(control_name)
            if not ctrl:
                continue
            try:
                ctrl.setText(_(text))
            except Exception:
                try:
                    ctrl.getModel().Label = _(text)
                except Exception:
                    pass

    def _create_dialog(self, parent_frame):
        """Try the new full settings dialog first, then fall back to legacy dialog."""
        fallback_urls = [
            "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_settings_dialog_full.xdl",
            "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_settings_dialog.xdl",
            "private:dialogs/tejocr_settings_dialog_full.xdl",
            "private:dialogs/tejocr_settings_dialog.xdl",
        ]

        try:
            dialog_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dialogs"))
            full_path = os.path.join(dialog_root, "tejocr_settings_dialog_full.xdl")
            if os.path.exists(full_path):
                fallback_urls.append(unohelper.systemPathToFileUrl(full_path))
            legacy_path = os.path.join(dialog_root, "tejocr_settings_dialog.xdl")
            if os.path.exists(legacy_path):
                legacy_url = unohelper.systemPathToFileUrl(legacy_path)
                if legacy_url not in fallback_urls:
                    fallback_urls.append(legacy_url)
        except Exception as e:
            msg = f"Could not compute dialog file fallback paths: {e}"
            logger.debug(msg)
            self._last_dialog_creation_errors.append(msg)

        return self._create_dialog_with_urls(parent_frame, fallback_urls, suppress_user_message=True)

    def _init_controls(self):
        """Initialize controls and attach listeners for the Settings dialog."""
        logger.info("SettingsDialogHandler: _init_controls called.")
        
        # Attach button listeners
        self._add_listener_to_control("SaveButton", "save_settings") 
        self._add_listener_to_control("CancelButton", "cancel")
        self._add_listener_to_control("HelpButtonSettings", "help")
        self._add_listener_to_control("MessageButtonSettings", "message")
        self._add_listener_to_control("BrowseButton", "browse_tesseract_path")
        self._add_listener_to_control("TestTesseractButton", "test_tesseract")
        self._add_listener_to_control("RefreshLanguagesButtonSettings", "refresh_languages_settings")
        self._add_listener_to_control("SetupButton", "setup")
        self._add_listener_to_control("WikiButton", "wiki")
        self._add_listener_to_control("FilterTubeButton", "filtertube")
        # Legacy button names — listeners are no-ops if control doesn't exist
        self._add_listener_to_control("CheckDependenciesButton", "setup")
        self._add_listener_to_control("InstallGuideButton", "setup")
        self._add_listener_to_control("HelpMeInstallButton", "wiki")
        
        # Search button for language filtering
        self._add_listener_to_control("SearchLanguagesButton", "search_languages")

        # Dynamic interactions for dropdowns and checkboxes
        self._add_item_listener_to_control("DefaultPresetDropdown")
        self._add_item_listener_to_control("DefaultMergeBatchCheckbox")
        self._add_item_listener_to_control("LanguagesListbox")

        # Force dropdown controls into compact mode across LO builds
        self._ensure_dropdown_mode("DefaultPresetDropdown")
        self._ensure_dropdown_mode("UiLanguageDropdown")

        self._add_listener_to_control("AdvancedParamsButton", "advanced_params")

        # XDL files are static English; apply the configured UI language at runtime.
        self._apply_ui_translations()

        # Load current settings — wrapped so a failure doesn't prevent dialog display
        try:
            self._load_settings()
        except Exception as e:
            logger.error(f"Error loading settings into dialog controls: {e}", exc_info=True)
            status_label = self.get_control("SettingsStatusLabel")
            if status_label:
                status_label.setText("Warning: Could not load some settings")
        
        # Check dependencies — also wrapped
        try:
            self._check_and_display_dependencies()
        except Exception as e:
            logger.error(f"Error checking dependencies: {e}", exc_info=True)
            
        # Apply modern UI styling via UNO models
        self._apply_modern_styling()

    def _apply_modern_styling(self):
        """Applies dynamic UNO colors and fonts to modernize the UI and highlight important actions."""
        try:
            # 1. Shrink promo tagline to make it subtle
            tagline = self.get_control("FilterTubeTagline2")
            if tagline:
                model = tagline.getModel()
                model.FontHeight = 8.5
                model.FontSlant = 2 # Italic
                model.TextColor = 0x666666 # Subtle grey

            # 2. Make Promo button strictly distinct
            filter_btn = self.get_control("FilterTubeButton")
            if filter_btn:
                model = filter_btn.getModel()
                model.BackgroundColor = 0x1D4ED8 # Dark blue promo color
                model.TextColor = 0xFFFFFF # White text
                model.FontWeight = 150 # Bold

            # 3. Make Save strictly a Primary Call to Action
            save_btn = self.get_control("SaveButton")
            if save_btn:
                model = save_btn.getModel()
                model.BackgroundColor = 0x22C55E # Crisp UI Green
                model.TextColor = 0xFFFFFF # White text
                model.FontWeight = 150 # Bold

            # 4. Keep Setup & Help visually distinct in their resting state too
            setup_btn = self.get_control("SetupButton")
            if setup_btn:
                model = setup_btn.getModel()
                model.BackgroundColor = self.COLOR_BTN_PRIMARY
                model.TextColor = self.COLOR_TEXT_ON_DARK
                model.FontWeight = 150

            help_btn = self.get_control("HelpButtonSettings")
            if help_btn:
                model = help_btn.getModel()
                model.BackgroundColor = self.COLOR_BTN_WARNING
                model.TextColor = 0xFFFFFF
                model.FontWeight = 150

            # 5. Style the Advanced params button
            adv_btn = self.get_control("AdvancedParamsButton")
            if adv_btn:
                model = adv_btn.getModel()
                model.BackgroundColor = 0x4B5563 # Slate grey
                model.TextColor = 0xFFFFFF # White text

            # 6. Distinct community-message button
            message_btn = self.get_control("MessageButtonSettings")
            if message_btn:
                model = message_btn.getModel()
                model.BackgroundColor = 0x7C3AED # Violet accent
                model.TextColor = 0xFFFFFF
                model.FontWeight = 150

        except Exception as e:
            logger.debug(f"Could not apply all modern stylings (UI may appear default): {e}")

    # Color constants for status labels (RGB integers)
    COLOR_GREEN = 0x009900   # OK / Available
    COLOR_RED = 0xCC0000     # Missing / Error
    COLOR_AMBER = 0xCC8800   # Partial / Warning

    def _set_label(self, control_name, text, color=None):
        """Set label text and optionally color it via the UNO model."""
        ctrl = self.get_control(control_name)
        if ctrl:
            ctrl.setText(text)
            if color is not None:
                try:
                    ctrl.getModel().TextColor = color
                except Exception:
                    pass

    def _apply_dependency_status_labels(self, status):
        """Apply a dependency-status payload to the Settings header labels."""
        status = status or {}

        tess_ok = bool(status.get('tesseract_ok', False))
        if tess_ok:
            self._set_label("TesseractStatusLabel", _("Tesseract: Available"), self.COLOR_GREEN)
        else:
            self._set_label("TesseractStatusLabel", _("Tesseract: Not found"), self.COLOR_RED)

        n = bool(status.get('numpy_ok', False))
        p = bool(status.get('pytesseract_ok', False))
        pil = bool(status.get('pillow_ok', False))
        count = sum([n, p, pil])
        pdf_ok = bool(status.get('pdf_renderer_available', False))
        extras_status = _("Extras: {count}/3").format(count=count)

        pdf_label = self.get_control("PdfStatusLabel")
        pdf_color = self.COLOR_GREEN if pdf_ok else self.COLOR_AMBER
        if pdf_label:
            self._set_label("PdfStatusLabel", _("PDF: ok") if pdf_ok else _("PDF: missing"), pdf_color)
        else:
            pdf_status = _("PDF: ok") if pdf_ok else _("PDF: missing")

        if count >= 3:
            extras_color = self.COLOR_GREEN
        else:
            extras_color = self.COLOR_AMBER

        python_label = self.get_control("PythonPackagesStatusLabel")
        if python_label:
            if pdf_label:
                self._set_label(
                    "PythonPackagesStatusLabel",
                    _("{extras_status} (optional)").format(extras_status=extras_status),
                    extras_color,
                )
            else:
                fallback_color = self.COLOR_GREEN if tess_ok and pdf_ok else (self.COLOR_AMBER if tess_ok or pdf_ok or count > 0 else self.COLOR_RED)
                self._set_label(
                    "PythonPackagesStatusLabel",
                    _("{extras_status} (optional) | {pdf_status}").format(
                        extras_status=extras_status,
                        pdf_status=pdf_status,
                    ),
                    fallback_color,
                )

        summary_label = self.get_control("SettingsStatusLabel")
        if summary_label:
            summary_label.setText(_(status.get("summary", "Dependency status refreshed")))

    def _check_and_display_dependencies(self):
        """Check all dependencies and update the status labels with color."""
        logger.info("Checking dependencies for Settings dialog...")
        
        try:
            # Refresh runtime detection so installs completed in this session are visible.
            try:
                import importlib
                importlib.invalidate_caches()
                try:
                    from tejocr import tejocr_pdf
                    importlib.reload(tejocr_pdf)
                except Exception:
                    pass
            except Exception:
                pass

            self.dependency_status = _check_dependencies()
            self._apply_dependency_status_labels(self.dependency_status)
                    
        except Exception as e:
            logger.error(f"Error checking dependencies in settings: {e}", exc_info=True)
            self._set_label("TesseractStatusLabel",
                            _("Tesseract: Check failed"), self.COLOR_AMBER)
            self._set_label("PythonPackagesStatusLabel",
                            _("Python: Check failed"), self.COLOR_AMBER)

    def _load_settings(self):
        """Load settings from config and populate dialog controls."""
        # Tesseract Path
        tesseract_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", self.ctx)
        path_field = self.get_control("TesseractPathTextField")
        if path_field: 
            path_field.setText(tesseract_path)
        self.initial_settings[constants.CFG_KEY_TESSERACT_PATH] = tesseract_path

        ui_language = uno_utils.get_setting(
            constants.CFG_KEY_UI_LANGUAGE,
            constants.DEFAULT_UI_LANGUAGE,
            self.ctx,
        )
        self._populate_ui_language_dropdown(ui_language)
        self.initial_settings[constants.CFG_KEY_UI_LANGUAGE] = self._coerce_ui_language_value(ui_language)

        # Languages — unified multi-select listbox
        langs = self._get_tesseract_languages_for_settings()
        current_default_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
        if not current_default_lang:
            current_default_lang = uno_utils.get_setting(constants.CFG_KEY_LAST_SELECTED_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
        current_default_lang = self._normalize_language_list(current_default_lang)
        if not current_default_lang:
            current_default_lang = constants.DEFAULT_OCR_LANGUAGE

        self._all_lang_keys = list(langs.keys())
        self._all_lang_map = langs
        self._selected_codes = {
            token for token in current_default_lang.split("+") if token
        } or {constants.DEFAULT_OCR_LANGUAGE}
        self._populate_language_listbox()
        
        self.initial_settings[constants.CFG_KEY_DEFAULT_LANG] = current_default_lang
        self.initial_settings[constants.CFG_KEY_LAST_SELECTED_LANG] = current_default_lang

        # Output Mode — radio buttons (4 options)
        default_output_mode = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OUTPUT_MODE, None, self.ctx)
        if not default_output_mode:
            default_output_mode = uno_utils.get_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, constants.DEFAULT_OUTPUT_MODE, self.ctx)
        if not default_output_mode:
            default_output_mode = constants.DEFAULT_OUTPUT_MODE
        default_output_mode = self._normalize_output_mode(default_output_mode)
        
        radio_map = {
            constants.OUTPUT_MODE_CURSOR: "OutputRadioCursor",
            constants.OUTPUT_MODE_TEXTBOX: "OutputRadioTextBox",
            constants.OUTPUT_MODE_REPLACE: "OutputRadioReplace",
            constants.OUTPUT_MODE_CLIPBOARD: "OutputRadioClipboard",
        }
        for mode_key, radio_id in radio_map.items():
            ctrl = self.get_control(radio_id)
            if ctrl:
                ctrl.setState(mode_key == default_output_mode)
        self.initial_settings[constants.CFG_KEY_DEFAULT_OUTPUT_MODE] = default_output_mode
        self.initial_settings[constants.CFG_KEY_LAST_OUTPUT_MODE] = default_output_mode

        # Preprocessing
        grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, constants.DEFAULT_PREPROC_GRAYSCALE, self.ctx)
        binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, constants.DEFAULT_PREPROC_BINARIZE, self.ctx)
        cb_gray = self.get_control("DefaultGrayscaleCheckbox")
        if cb_gray:
            cb_gray.setState(self._bool_to_state(grayscale))
        cb_bin = self.get_control("DefaultBinarizeCheckbox")
        if cb_bin:
            cb_bin.setState(self._bool_to_state(binarize))
        self.initial_settings[constants.CFG_KEY_DEFAULT_GRAYSCALE] = grayscale
        self.initial_settings[constants.CFG_KEY_DEFAULT_BINARIZE] = binarize

        # Preset / PSM / OEM / Preview defaults
        preset_items = self._settings_preset_items()
        self._populate_dropdown_settings(
            "DefaultPresetDropdown",
            preset_items,
            constants.CFG_KEY_DEFAULT_PRESET,
            constants.DEFAULT_OCR_PRESET,
        )

        self.current_psm = self._coerce_mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, self.ctx),
            constants.TESSERACT_PSM_MODES,
            constants.DEFAULT_PSM_MODE,
        )
        self.current_oem = self._coerce_mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, self.ctx),
            constants.TESSERACT_OEM_MODES,
            constants.DEFAULT_OEM_MODE,
        )
        self.current_oem, _oem_warning = _coerce_supported_oem_value(
            self.current_oem,
            ctx=self.ctx,
            fallback=constants.DEFAULT_OEM_MODE,
        )

        preview = uno_utils.get_setting(
            constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
            constants.DEFAULT_SHOW_PREVIEW_BEFORE_OUTPUT,
            self.ctx,
        )
        cb_preview = self.get_control("DefaultPreviewCheckbox")
        if cb_preview:
            cb_preview.setState(self._bool_to_state(preview))

        merge_batch = uno_utils.get_setting(
            constants.CFG_KEY_MERGE_BATCH_RESULTS,
            constants.DEFAULT_MERGE_BATCH_RESULTS,
            self.ctx,
        )
        cb_merge_batch = self.get_control("DefaultMergeBatchCheckbox")
        if cb_merge_batch:
            cb_merge_batch.setState(self._bool_to_state(merge_batch))

        self.initial_settings[constants.CFG_KEY_DEFAULT_PRESET] = self._coerce_preset_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PRESET, constants.DEFAULT_OCR_PRESET, self.ctx),
            constants.DEFAULT_OCR_PRESET,
        )
        self.initial_settings[constants.CFG_KEY_DEFAULT_PSM] = self.current_psm
        self.initial_settings[constants.CFG_KEY_DEFAULT_OEM] = self.current_oem
        self.initial_settings[constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT] = self._bool_to_state(preview)
        self.initial_settings[constants.CFG_KEY_MERGE_BATCH_RESULTS] = self._bool_to_state(merge_batch)
        
        status_label = self.get_control("SettingsStatusLabel")
        if status_label:
            status_label.setText(_("Settings loaded successfully"))
        
        # Initialize dynamic hint labels
        self._update_preset_hint()
        self._update_merge_hint()

    @staticmethod
    def _coerce_preset_value(value, fallback):
        normalized = str(value or "").strip().lower()
        if ":" in normalized:
            normalized = normalized.split(":", 1)[0].strip()
        return normalized if normalized in constants.OCR_PRESET_CHOICES else fallback

    @staticmethod
    def _coerce_mode_value(value, valid_map, fallback):
        normalized = str(value or "").strip()
        return normalized if normalized in valid_map else fallback

    @staticmethod
    def _extract_dropdown_key(control, items_map, fallback):
        if not control or not items_map:
            return fallback
        try:
            selected_items = control.getSelectedItemsPos()
            if selected_items:
                keys = list(items_map.keys())
                idx = int(selected_items[0])
                if 0 <= idx < len(keys):
                    return str(keys[idx])
        except Exception:
            pass

        try:
            raw_text = str(control.getText()).strip()
            if not raw_text:
                return fallback
            # Typical format: "<label> (<key>)"
            if raw_text.endswith(")") and "(" in raw_text:
                candidate = raw_text.rsplit("(", 1)[-1].rsplit(")", 1)[0].strip()
                if candidate in items_map:
                    return candidate
            if raw_text in items_map:
                return raw_text
            for key, value in items_map.items():
                if raw_text == f"{value} ({key})":
                    return str(key)
                if raw_text == key:
                    return str(key)
        except Exception:
            pass
        return fallback

    def _normalize_language_list(self, language_value):
        if not language_value:
            return ""
        normalized = str(language_value).replace(",", "+")
        tokens = []
        for token in normalized.split("+"):
            token = token.strip().replace(" ", "")
            if token:
                tokens.append(token)
        return "+".join(tokens) if tokens else ""

    def _populate_output_mode_dropdown(self, control_name, default_output_mode):
        """Populate the output mode dropdown with supported OCR output destinations."""
        dropdown = self.get_control(control_name)
        if not dropdown:
            return

        output_mode_items = [
            (constants.OUTPUT_MODE_CURSOR, "Insert at cursor"),
            (constants.OUTPUT_MODE_TEXTBOX, "Create a new text box"),
            (constants.OUTPUT_MODE_REPLACE, "Replace selected image"),
            (constants.OUTPUT_MODE_CLIPBOARD, "Copy to clipboard"),
        ]
        dropdown.getModel().removeAllItems()
        self._output_mode_code_order = [item[0] for item in output_mode_items]
        selected_pos = 0

        for i, (mode_code, mode_label) in enumerate(output_mode_items):
            dropdown.addItem(mode_label, i)
            if str(mode_code) == str(default_output_mode):
                selected_pos = i

        if dropdown.getItemCount() > 0:
            self._select_dropdown_item(dropdown, selected_pos)

    def _get_tesseract_languages_for_settings(self):
        cached_langs = getattr(self, "_settings_languages_cache", None)
        if not cached_langs:
            cached_langs = _get_tesseract_language_map(self.ctx)
        self._settings_languages_cache = cached_langs
        self.available_languages_map_settings = cached_langs
        return self._settings_languages_cache

    def _populate_dropdown_settings(self, control_name, items_map, current_value_key, default_value):
        dropdown = self.get_control(control_name)
        if not dropdown:
            return

        stored_value = uno_utils.get_setting(current_value_key, default_value, self.ctx)
        logger.info(f"Populating {control_name}: stored_value='{stored_value}', default='{default_value}'")

        # Use the Model API for menulist controls
        model = dropdown.getModel()
        model.StringItemList = ()   # clear all items

        selected_pos = 0
        if items_map and isinstance(items_map, dict):
            item_keys = list(items_map.keys())
            texts = []
            for i, key in enumerate(item_keys):
                display_text = str(items_map[key])
                texts.append(display_text)
                if str(key) == str(stored_value):
                    selected_pos = i
                    logger.info(f"  Matched '{key}' at position {i}")

            # Set all items at once via the model
            model.StringItemList = tuple(texts)
            
            if len(texts) > 0:
                # Select via model SelectedItems (tuple of selected indices)
                model.SelectedItems = (selected_pos,)
                # Also set via control API for cross-version compatibility
                try:
                    dropdown.selectItemPos(selected_pos, True)
                except Exception:
                    pass
                logger.info(f"  Selected position {selected_pos} of {len(texts)} items")
        else:
            logger.error(f"items_map for {control_name} is invalid or empty.")
            model.StringItemList = ("Error: Could not load items",)
            model.SelectedItems = (0,)

    def _ui_language_items(self):
        items = {constants.DEFAULT_UI_LANGUAGE: "Auto (LibreOffice/system)"}
        for code, label in locale_setup.get_available_ui_languages().items():
            items[code] = label
        return items

    def _coerce_ui_language_value(self, value):
        normalised = str(value or constants.DEFAULT_UI_LANGUAGE).strip().replace("-", "_")
        if not normalised:
            return constants.DEFAULT_UI_LANGUAGE
        if normalised.lower() == constants.DEFAULT_UI_LANGUAGE:
            return constants.DEFAULT_UI_LANGUAGE
        available = locale_setup.get_available_ui_languages()
        if normalised in available:
            return normalised
        parent = normalised.split("_", 1)[0].lower()
        if parent in available:
            return parent
        return constants.DEFAULT_UI_LANGUAGE

    def _populate_ui_language_dropdown(self, current_value):
        dropdown = self.get_control("UiLanguageDropdown")
        if not dropdown:
            return
        items = self._ui_language_items()
        selected_key = self._coerce_ui_language_value(current_value)
        model = dropdown.getModel()
        model.StringItemList = tuple(items.values())
        try:
            selected_pos = list(items.keys()).index(selected_key)
        except ValueError:
            selected_pos = 0
        model.SelectedItems = (selected_pos,)
        try:
            dropdown.selectItemPos(selected_pos, True)
        except Exception:
            pass

    def _get_selected_ui_language(self):
        return self._coerce_ui_language_value(
            self._extract_dropdown_key(
                self.get_control("UiLanguageDropdown"),
                self._ui_language_items(),
                constants.DEFAULT_UI_LANGUAGE,
            )
        )

    def _populate_language_listbox(self, filter_text=""):
        """Populate the unified LanguagesListbox, optionally filtered by search text."""
        lb = self.get_control("LanguagesListbox")
        if not lb:
            return
        
        model = lb.getModel()
        model.MultiSelection = True
        
        # Build filtered list
        filter_lower = filter_text.strip().lower()
        self._visible_lang_keys = []
        texts = []
        sel_indices = []
        
        for key in self._all_lang_keys:
            display = f"{self._all_lang_map[key]} ({key})"
            if filter_lower and filter_lower not in display.lower():
                continue
            texts.append(display)
            self._visible_lang_keys.append(key)
            if key in self._selected_codes:
                sel_indices.append(len(texts) - 1)
        
        model.StringItemList = tuple(texts)
        if sel_indices:
            model.SelectedItems = tuple(sel_indices)
        
        self._update_selected_langs_label()

    def _sync_selected_codes_from_listbox(self):
        """Read current listbox selections and update _selected_codes."""
        lb = self.get_control("LanguagesListbox")
        if not lb:
            return
        try:
            sel_positions = lb.getSelectedItemsPos()
            visible_keys = getattr(self, '_visible_lang_keys', [])
            # First, remove codes for visible items (they may have been deselected)
            visible_set = set(visible_keys)
            self._selected_codes -= visible_set
            # Then add back the ones that are selected
            for pos in sel_positions:
                if 0 <= pos < len(visible_keys):
                    self._selected_codes.add(visible_keys[pos])
        except Exception:
            pass
        self._update_selected_langs_label()

    def _get_selected_default_language_code(self):
        """Build language string from multi-select listbox selections."""
        self._sync_selected_codes_from_listbox()
        codes = sorted(self._selected_codes) if self._selected_codes else [constants.DEFAULT_OCR_LANGUAGE]
        return '+'.join(codes)

    def _update_selected_langs_label(self):
        """Update the selected-languages label with clearer visual separators."""
        label = self.get_control("SelectedLangsLabel")
        if not label:
            return
        codes = sorted(self._selected_codes) if self._selected_codes else [constants.DEFAULT_OCR_LANGUAGE]
        label.setText(
            _("Selected: {languages}").format(
                languages=ocr_runtime.format_language_codes_for_display(
                    "+".join(codes),
                    default_language=constants.DEFAULT_OCR_LANGUAGE,
                )
            )
        )

    def _get_selected_output_mode(self):
        """Read output mode from radio buttons (4 options)."""
        radio_map = {
            "OutputRadioCursor": "at_cursor",
            "OutputRadioTextBox": "new_text_box",
            "OutputRadioReplace": "replace",
            "OutputRadioClipboard": "clipboard",
        }
        for radio_id, mode_key in radio_map.items():
            ctrl = self.get_control(radio_id)
            if ctrl and ctrl.getState():
                return mode_key
        return "at_cursor"

    @staticmethod
    def _normalize_output_mode(mode_value):
        """Normalize UI output mode values into canonical constants."""
        normalized = str(mode_value).strip().lower().replace("-", "_").replace(" ", "_")
        alias_map = {
            "atcursor": constants.OUTPUT_MODE_CURSOR,
            "at_cursor": constants.OUTPUT_MODE_CURSOR,
            "cursor": constants.OUTPUT_MODE_CURSOR,
            "new_text_box": constants.OUTPUT_MODE_TEXTBOX,
            "newtextbox": constants.OUTPUT_MODE_TEXTBOX,
            "textbox": constants.OUTPUT_MODE_TEXTBOX,
            "replace": constants.OUTPUT_MODE_REPLACE,
            "replace_image": constants.OUTPUT_MODE_REPLACE,
            "clipboard": constants.OUTPUT_MODE_CLIPBOARD,
            "to_clipboard": constants.OUTPUT_MODE_CLIPBOARD,
        }
        return alias_map.get(normalized, str(mode_value).strip())

    def actionPerformed(self, event):
        source_control = self._get_event_source_control(event)
        command = self._get_action_command(event)
        if not command:
            logger.warning("SettingsDialog: action event missing command.")
            return

        status_label = self.get_control("SettingsStatusLabel")

        def _execute_with_feedback(
            control,
            run_text,
            start_status,
            action_callable,
            done_status=None,
            bg_color=None,
            fg_color=None,
        ):
            baseline = self._capture_control_feedback_state(control)
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
                status_label.setText(start_status)
            try:
                action_callable()
                if status_label and done_status:
                    status_label.setText(done_status)
            finally:
                self._restore_control_feedback_state(control, baseline)

        if command in {"save_settings", "cancel"}:
            baseline = self._capture_control_feedback_state(source_control)
            if command == "save_settings":
                self._set_control_feedback(
                    source_control,
                    text="Saving...",
                    enabled=False,
                    bg_color=self.COLOR_BTN_SUCCESS,
                    fg_color=self.COLOR_TEXT_ON_DARK,
                )
                if status_label:
                    status_label.setText("Saving settings...")
                super().actionPerformed(event)
                if status_label:
                    status_label.setText("Settings saved. Closing...")
                self._restore_control_feedback_state(source_control, baseline)
                return

            self._set_control_feedback(
                source_control,
                text="Canceling...",
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            if status_label:
                status_label.setText("Cancelling settings...")
            super().actionPerformed(event)
            self._restore_control_feedback_state(source_control, baseline)
            return

        logger.debug(f"SettingsDialogHandler actionPerformed: {command}")

        if command == "help":
            _execute_with_feedback(
                source_control,
                "Opening help...",
                "Opening Settings help...",
                self._handle_help_action,
                "Settings help opened.",
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return

        if command == "message":
            _execute_with_feedback(
                source_control,
                "Opening message...",
                "Opening message...",
                self._handle_message_action,
                "Message opened.",
                bg_color=0x7C3AED,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return

        if command == "browse_tesseract_path":
            _execute_with_feedback(
                source_control,
                "Browsing...",
                "Opening file picker...",
                self._browse_tesseract_path,
                "Tesseract path updated.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "test_tesseract":
            _execute_with_feedback(
                source_control,
                "Testing...",
                "Testing Tesseract...",
                self._test_tesseract_path,
                "Tesseract test completed.",
                bg_color=self.COLOR_BTN_SUCCESS,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "refresh_languages_settings":
            _execute_with_feedback(
                source_control,
                "Refreshing...",
                "Refreshing OCR language list...",
                self._refresh_languages,
                "OCR language list refreshed.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "setup":
            _execute_with_feedback(
                source_control,
                "Opening setup...",
                "Opening setup diagnostics...",
                self._show_setup,
                "Dependencies checked.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "wiki":
            _execute_with_feedback(
                source_control,
                _("Opening wiki..."),
                _("Opening TejOCR wiki..."),
                self._open_wiki,
                _("Wiki opened in browser."),
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "filtertube":
            _execute_with_feedback(
                source_control,
                _("Opening FilterTube..."),
                _("Opening FilterTube site..."),
                self._open_filtertube,
                _("FilterTube opened in browser."),
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "search_languages":
            _execute_with_feedback(
                source_control,
                _("Filter"),
                _("Filtering languages..."),
                self._filter_languages,
                _("Language filter applied."),
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "advanced_params":
            self._show_advanced_params_dialog()
            return

        super().actionPerformed(event)

    def _show_advanced_params_dialog(self):
        try:
            handler = TejOCRAdvancedParamsDialogHandler(self.ctx, self.parent_frame, getattr(self, "current_psm", 3), getattr(self, "current_oem", 3))
            if handler.show():
                self.current_psm = handler.selected_psm
                self.current_oem = handler.selected_oem
                status_label = self.get_control("SettingsStatusLabel")
                if status_label:
                    status_label.setText("Advanced parameters updated.")
        except Exception as e:
            logger.error(f"Failed to open advanced params dialog: {e}", exc_info=True)

    def itemStateChanged(self, event):
        """Handle changes in listboxes and checkboxes (XItemListener)."""
        source_control = self._get_event_source_control(event)
        if not source_control:
            return

        try:
            # We identify the control by its model name if possible
            model = source_control.getModel()
            name = model.Name
            
            if name == "DefaultPresetDropdown":
                self._update_preset_hint()
            elif name == "DefaultMergeBatchCheckbox":
                self._update_merge_hint()
            elif name == "LanguagesListbox":
                self._sync_selected_codes_from_listbox()
                
        except Exception as e:
            logger.debug(f"itemStateChanged exception: {e}")

    def _update_preset_hint(self):
        """Update the UI hint based on the selected Preset."""
        preset_control = self.get_control("DefaultPresetDropdown")
        if not preset_control:
            return
            
        preset_key = self._coerce_preset_value(
            self._extract_dropdown_key(
                preset_control,
                {
                    **self._settings_preset_items(),
                },
                constants.DEFAULT_OCR_PRESET,
            ),
            constants.DEFAULT_OCR_PRESET,
        )

        hint_label = self.get_control("PresetStatusLabel")
        # Advanced controls
        adv_button = self.get_control("AdvancedParamsButton")

        if preset_key == constants.OCR_PRESET_FAST:
            if hint_label: hint_label.setText(_("Fast: Single pass. Best for clean text. (PDFs rendered at 200 DPI)"))
            if adv_button: adv_button.setEnable(False)
        elif preset_key == constants.OCR_PRESET_BALANCED:
            if hint_label: hint_label.setText(_("Balanced: Retries if output is weak. (PDFs rendered at 200 DPI)"))
            if adv_button: adv_button.setEnable(False)
        elif preset_key == constants.OCR_PRESET_ACCURATE:
            if hint_label: hint_label.setText(_("Accurate: Fallbacks + enhanced preprocessing. (PDFs rendered at 300 DPI)"))
            if adv_button: adv_button.setEnable(False)
        elif preset_key == constants.OCR_PRESET_CUSTOM:
            if hint_label: hint_label.setText(_("Custom: Uses your exact PSM/OEM and scaling overrides below."))
            if adv_button: adv_button.setEnable(True)

    def _update_merge_hint(self):
        """Update the UI hint based on the Merge Batch Checkbox."""
        merge_cb = self.get_control("DefaultMergeBatchCheckbox")
        if not merge_cb:
            return
            
        hint_label = self.get_control("MergeStatusLabel")
        if not hint_label:
            return

        if merge_cb.getState():
            hint_label.setText(_("Outputs multi-page PDFs as a single consolidated block."))
            hint_label.getModel().TextColor = 0x666666  # Subtle grey
        else:
            hint_label.setText(_("Outputs each file and PDF page as a separate insertion."))
            hint_label.getModel().TextColor = self.COLOR_BTN_WARNING

    def _filter_languages(self):
        """Filter the language listbox based on search field text."""
        search_field = self.get_control("LanguageSearchField")
        if not search_field:
            return
        # Save current selections before filtering
        self._sync_selected_codes_from_listbox()
        # Re-populate with filter
        self._populate_language_listbox(search_field.getText())

    def _refresh_languages(self):
        """Refresh the language list by clearing cache and reloading."""
        self._settings_languages_cache = None
        langs = self._get_tesseract_languages_for_settings()
        self._all_lang_keys = list(langs.keys())
        self._all_lang_map = langs
        self._populate_language_listbox()
        uno_utils.show_message_box("Languages Refreshed", "The list of available OCR languages has been updated.", "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _show_setup(self):
        """Open the dedicated Setup & Diagnostics dialog."""
        try:
            setup_handler = TejOCRSetupDialogHandler(self.ctx, self.parent_frame)
            setup_handler.show()
            # Refresh our status labels after setup dialog closes
            if setup_handler.dependency_status:
                self.dependency_status = setup_handler.dependency_status
                self._apply_dependency_status_labels(self.dependency_status)
            else:
                self._check_and_display_dependencies()
        except Exception as e:
            import traceback
            logger.error(f"Failed to open Setup dialog: {e}\n{traceback.format_exc()}")
            # Fallback to message box
            self._check_and_display_dependencies()
            guide = self.dependency_status.get('next_steps', '') if self.dependency_status else ''
            summary = self.dependency_status.get('summary', '') if self.dependency_status else ''
            packages = self.dependency_status.get('python_packages', '') if self.dependency_status else ''
            uno_utils.show_message_box("TejOCR Setup", f"Status: {summary}\n\nPackages:\n{packages}\n\n{guide}", "infobox",
                                      parent_frame=self.parent_frame, ctx=self.ctx)

    def _open_wiki(self):
        """Open the TejOCR wiki page in the default browser."""
        import webbrowser
        url = "https://github.com/varshneydevansh/TejOCR/wiki"
        try:
            webbrowser.open(url)
            status_label = self.get_control("SettingsStatusLabel")
            if status_label:
                status_label.setText("Wiki opened in browser")
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            uno_utils.show_message_box(
                "Wiki",
                f"Could not open browser.\nVisit: {url}",
                "infobox", parent_frame=self.parent_frame, ctx=self.ctx
            )

    def _open_filtertube(self):
        """Open the FilterTube project website in the default browser."""
        import webbrowser
        url = "https://filtertube.in"
        try:
            webbrowser.open(url)
            status_label = self.get_control("SettingsStatusLabel")
            if status_label:
                status_label.setText("FilterTube opened in browser")
        except Exception as e:
            logger.error(f"Failed to open FilterTube site: {e}")
            uno_utils.show_message_box(
                "FilterTube",
                f"Could not open browser.\nVisit: {url}",
                "infobox",
                parent_frame=self.parent_frame,
                ctx=self.ctx,
            )

    def _handle_help_action(self):
        """Show the rich Help dialog."""
        try:
            help_handler = TejOCRHelpDialogHandler(self.ctx, self.parent_frame)
            help_handler.show()
        except Exception as e:
            logger.error(f"Fallback to message box help: {e}")
            help_text = f"""ℹ️ TejOCR - Settings Help
(Failed to open advanced help dialog)

✅ DEPENDENCY STATUS:
• Current status of required components
• Open Setup & Diagnostics to test dependencies and view install commands

✅ TESSERACT CONFIGURATION:
• Set path to Tesseract executable manually

✅ DEFAULT OPTIONS:
• Set preferences for OCR operations

⚠️ ADVANCED PARAMETERS (PRESET, PSM, OEM):
• Preset: Chooses a default quality profile for future OCR runs.

✅ BATCH & PDF:
• You can select multiple image files or one/more PDFs in the bulk run.
• Check 'Merge bulk/PDF into single output' to combine all recognized text at once."""
            uno_utils.show_message_box("Settings Help (Fallback)", help_text, "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _handle_message_action(self):
        """Show the message dialog about native OCR demand in LibreOffice."""
        try:
            message_handler = TejOCRMessageDialogHandler(self.ctx, self.parent_frame)
            message_handler.show()
        except Exception as e:
            logger.error(f"Fallback to message box advocacy dialog: {e}")
            message_text = (
                "A Message\n\n"
                "TejOCR is useful, but it is still a workaround rather than native LibreOffice OCR.\n\n"
                "Current extension limits:\n"
                "• OCR accuracy still depends on Tesseract and file quality.\n"
                "• Structure and layout retention are limited.\n"
                "• There is no native offline translation, chart understanding, or document insight layer.\n\n"
                "If this matters to you, please ask for native offline OCR and smart document understanding in "
                "LibreOffice core on forums, mailing lists, and enhancement discussions.\n\n"
                "Longer-term direction: https://github.com/varshneydevansh/aKriti"
            )
            uno_utils.show_message_box("A Message", message_text, "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _browse_tesseract_path(self):
        """Opens a file picker to browse for Tesseract executable."""
        try:
            # Create file picker for executable files
            fp = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
            if not fp:
                logger.warning("Could not create FilePicker for Tesseract browse")
                return
        
            fp.setTitle("Select Tesseract Executable")
            
            # Set filter for executable files (platform-specific)
            import platform
            system = platform.system().lower()
            if system == "windows":
                fp.appendFilter("Executable Files", "*.exe")
                fp.appendFilter("All Files", "*.*")
            else:
                fp.appendFilter("All Files", "*")
            
            # Set default directory (try common installation paths)
            default_paths = {
                "darwin": ["/usr/local/bin", "/opt/homebrew/bin", "/usr/bin"],
                "linux": ["/usr/bin", "/usr/local/bin"],
                "windows": ["C:\\Program Files\\Tesseract-OCR", "C:\\Program Files (x86)\\Tesseract-OCR"]
            }
            
            for path in default_paths.get(system, []):
                if os.path.exists(path):
                    try:
                        fp.setDisplayDirectory(unohelper.systemPathToFileUrl(path))
                        break
                    except:
                        continue
            
            # Execute the file picker
            if fp.execute() == 1:  # OK button pressed
                selected_files = fp.getFiles()
                if selected_files:
                    selected_path = unohelper.fileUrlToSystemPath(selected_files[0])
                    path_field = self.get_control("TesseractPathTextField")
                    if path_field:
                        path_field.setText(selected_path)
                        # Auto-test the selected path
                        self._test_tesseract_path()
                        
        except Exception as e:
            logger.error(f"Error in browse Tesseract path: {e}", exc_info=True)
            uno_utils.show_message_box("Browse Error", f"Could not open file browser: {e}", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _test_tesseract_path(self):
        """Test the currently entered Tesseract path."""
        path_field = self.get_control("TesseractPathTextField")
        if not path_field:
            return
            
        tess_path = path_field.getText().strip()
        status_label = self.get_control("TesseractTestStatusLabel")
        
        try:
            # Import tejocr_engine for testing
            from . import tejocr_engine
            is_valid, message = tejocr_engine.check_tesseract_path(tess_path, self.ctx, show_gui_errors=False)
            
            if status_label:
                if is_valid:
                    status_label.setText(f"✅ Valid: {message if message else 'Tesseract found and working'}")
                else:
                    status_label.setText(f"❌ Invalid: {message if message else 'Tesseract not found or failed'}")
            else:
                # Fallback to message box if label not found
                uno_utils.show_message_box(
                    "Tesseract Test",
                    f"""Path: {tess_path}
Status: {'Valid' if is_valid else 'Invalid'}
Details: {message}""",
                    "infobox" if is_valid else "warningbox",
                    parent_frame=self.parent_frame,
                    ctx=self.ctx
                )
                
        except Exception as e:
            logger.error(f"Error testing Tesseract path: {e}", exc_info=True)
            if status_label:
                status_label.setText(f"❌ Error: Could not test path")

    def _handle_ok_action(self):
        """Save settings if they have changed."""
        logger.info("SettingsDialog: Save action initiated.")
        
        try:
            changes_made = False
            grayscale_control = self.get_control("DefaultGrayscaleCheckbox")
            binarize_control = self.get_control("DefaultBinarizeCheckbox")
            preset_control = self.get_control("DefaultPresetDropdown")
            preview_control = self.get_control("DefaultPreviewCheckbox")
            merge_batch_control = self.get_control("DefaultMergeBatchCheckbox")
            preset_items = self._settings_preset_items()
            
            selected_ui_language = self._get_selected_ui_language()
            if selected_ui_language != self.initial_settings.get(constants.CFG_KEY_UI_LANGUAGE, constants.DEFAULT_UI_LANGUAGE):
                uno_utils.set_setting(constants.CFG_KEY_UI_LANGUAGE, selected_ui_language, self.ctx)
                locale_setup.configure(selected_ui_language, ctx=self.ctx)
                changes_made = True

            # Tesseract Path
            new_tesseract_path = self.get_control("TesseractPathTextField").getText().strip()
            if new_tesseract_path != self.initial_settings.get(constants.CFG_KEY_TESSERACT_PATH):
                logger.info(f"Updating Tesseract path: {new_tesseract_path}")
                uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, new_tesseract_path, self.ctx)
                changes_made = True

            # Default Language
            selected_lang_code = self._normalize_language_list(self._get_selected_default_language_code())
            if not selected_lang_code:
                selected_lang_code = constants.DEFAULT_OCR_LANGUAGE
            if selected_lang_code != self.initial_settings.get(constants.CFG_KEY_DEFAULT_LANG):
                logger.info(f"Updating default language: {selected_lang_code}")
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, selected_lang_code, self.ctx)
                uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, selected_lang_code, self.ctx)
                changes_made = True

            # Default Output Mode
            selected_output_mode = self._get_selected_output_mode()
            selected_output_mode = self._normalize_output_mode(selected_output_mode)
            if (
                selected_output_mode
                != self.initial_settings.get(constants.CFG_KEY_DEFAULT_OUTPUT_MODE)
                or selected_output_mode
                != self.initial_settings.get(constants.CFG_KEY_LAST_OUTPUT_MODE)
            ):
                logger.info(f"Updating default output mode: {selected_output_mode}")
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OUTPUT_MODE, selected_output_mode, self.ctx)
                uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, selected_output_mode, self.ctx)
                changes_made = True

            # Default Preprocessing, Preset, PSM, OEM, and preview settings
            selected_preset = self._coerce_preset_value(
                self._extract_dropdown_key(
                    preset_control,
                    preset_items,
                    self.initial_settings.get(constants.CFG_KEY_DEFAULT_PRESET, constants.DEFAULT_OCR_PRESET),
                ),
                constants.DEFAULT_OCR_PRESET,
            )
            if selected_preset != self.initial_settings.get(constants.CFG_KEY_DEFAULT_PRESET):
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PRESET, selected_preset, self.ctx)
                changes_made = True

            if grayscale_control:
                new_grayscale = grayscale_control.getState()
                if new_grayscale != self._bool_to_state(self.initial_settings.get(constants.CFG_KEY_DEFAULT_GRAYSCALE)):
                    uno_utils.set_setting(
                        constants.CFG_KEY_DEFAULT_GRAYSCALE,
                        self._state_to_setting_string(new_grayscale),
                        self.ctx,
                    )
                    changes_made = True

            if binarize_control:
                new_binarize = binarize_control.getState()
                if new_binarize != self._bool_to_state(self.initial_settings.get(constants.CFG_KEY_DEFAULT_BINARIZE)):
                    uno_utils.set_setting(
                        constants.CFG_KEY_DEFAULT_BINARIZE,
                        self._state_to_setting_string(new_binarize),
                        self.ctx,
                    )
                    changes_made = True

            if hasattr(self, "current_psm") and str(self.current_psm) != str(self.initial_settings.get(constants.CFG_KEY_DEFAULT_PSM)):
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PSM, str(self.current_psm), self.ctx)
                changes_made = True

            if hasattr(self, "current_oem") and str(self.current_oem) != str(self.initial_settings.get(constants.CFG_KEY_DEFAULT_OEM)):
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OEM, str(self.current_oem), self.ctx)
                changes_made = True

            if preview_control:
                new_preview = preview_control.getState()
                if new_preview != self.initial_settings.get(constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT):
                    uno_utils.set_setting(
                        constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT,
                        self._state_to_setting_string(new_preview),
                        self.ctx,
                    )
                    changes_made = True

            if merge_batch_control:
                new_merge_batch = merge_batch_control.getState()
                if new_merge_batch != self.initial_settings.get(constants.CFG_KEY_MERGE_BATCH_RESULTS):
                    uno_utils.set_setting(
                        constants.CFG_KEY_MERGE_BATCH_RESULTS,
                        self._state_to_setting_string(new_merge_batch),
                        self.ctx,
                    )
                    changes_made = True
            
            # Update status
            status_label = self.get_control("SettingsStatusLabel")
            if changes_made:
                if status_label: 
                    status_label.setText(_("Settings saved successfully"))
                logger.info("Settings changes saved successfully")
            else:
                if status_label: 
                    status_label.setText(_("No changes to save"))
            
            return True  # Settings saved successfully
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            status_label = self.get_control("SettingsStatusLabel")
            if status_label: 
                status_label.setText(_("Error saving settings"))
            uno_utils.show_message_box(_("Save Error"), _("Could not save settings: {error}").format(error=e), "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
            return False  # Keep dialog open


def _show_interactive_settings_fallback(ctx, parent_frame=None):
    """Fallback to pure-UNO interactive settings when XDL dialogs fail."""
    logger.info("Settings fallback path: interactive settings dialog selected.")
    logger.debug("XDL settings dialog creation failed; using interactive settings fallback.")
    try:
        from . import tejocr_interactive_dialogs

        if not uno_utils.supports_uno_dialog_model(ctx):
            logger.warning(
                "Interactive settings fallback is unavailable: "
                "UnoControlDialogModel service is not supported in this session."
            )
            uno_utils.show_message_box(
                "Settings Fallback Unavailable",
                "Settings editor controls are not available in this LibreOffice session.\n\n"
                f"Please use the TejOCRSettings file at:\n{uno_utils.get_settings_file_path()}\n"
                "and restart LibreOffice after editing.",
                "warningbox",
                parent_frame=parent_frame,
                ctx=ctx,
            )
            return False

        result = tejocr_interactive_dialogs.show_interactive_settings_dialog(ctx, parent_frame)
        logger.info(f"Interactive settings fallback result: {result}")
        return bool(result)
    except Exception as e:
        logger.error(f"Interactive settings fallback failed: {e}", exc_info=True)
        if ctx is not None:
            try:
                uno_utils.show_message_box(
                    "Settings UI Fallback Error",
                    "Could not open the interactive settings fallback. Check logs for full details.",
                    "errorbox",
                    parent_frame=parent_frame,
                    ctx=ctx,
                )
            except Exception:
                pass
        return False


def _build_settings_unavailable_message(reason=None):
    package_hint = f"TejOCR-{constants.EXTENSION_VERSION}.oxt"
    if isinstance(reason, (list, tuple)):
        reason = "\n".join(str(item) for item in reason if item)
    reason_text = f"\n\nTechnical details:\n{reason}" if reason else ""
    return (
        "TejOCR Settings dialog could not be opened.\n\n"
        "Please make sure the latest extension package is installed:\n"
        f"{package_hint}\n\n"
        "If this is happening after a fresh install, restart LibreOffice once and try again."
        + reason_text
    )

# --- Advanced Params Dialog Handler ---

class TejOCRAdvancedParamsDialogHandler(BaseDialogHandler):
    """Handler for the dedicated Advanced Engine Parameters dialog."""
    
    def __init__(self, ctx, parent_frame=None, current_psm=3, current_oem=3):
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_advanced_params_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.parent_frame = parent_frame
        self.selected_psm = str(current_psm)
        self.selected_oem = str(current_oem)
        self._is_saved = False
        
        self.psm_map = _get_runtime_psm_map(ctx)
        self.oem_map = _get_runtime_oem_map(ctx)

    def show(self):
        smgr = self.ctx.ServiceManager
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_advanced_params_dialog.xdl"
        try:
            dprov = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider2", self.ctx)
            self.dialog = dprov.createDialog(dialog_url)
            
            # Attach listeners
            ctrl_cancel = self.dialog.getControl("CancelButtonParams")
            if ctrl_cancel:
                ctrl_cancel.setActionCommand("cancel")
                ctrl_cancel.addActionListener(self)
                
            ctrl_save = self.dialog.getControl("SaveButtonParams")
            if ctrl_save:
                ctrl_save.setActionCommand("save")
                ctrl_save.addActionListener(self)
                
            # Populate dropdowns manually
            self._populate_dropdown("PSMDropdown", self.psm_map, self.selected_psm)
            self._populate_dropdown("OEMDropdown", self.oem_map, self.selected_oem)
            
            self._apply_modern_styling()
            
            self.dialog.execute()
            return self._is_saved
        except Exception as e:
            logger.error(f"Failed to show Advanced Params Dialog: {e}", exc_info=True)
            return False

    def _apply_modern_styling(self):
        try:
            # Save button (primary)
            save_btn = self.dialog.getControl("SaveButtonParams")
            if save_btn:
                model = save_btn.getModel()
                model.BackgroundColor = 0x22C55E # Crisp UI Green
                model.TextColor = 0xFFFFFF # White text
                model.FontWeight = 150 # Bold
                
            # Warning label
            warning_label = self.dialog.getControl("ParamsWarningLabel")
            if warning_label:
                model = warning_label.getModel()
                model.TextColor = 0xCC8800 # Warning amber

        except Exception as e:
            logger.debug(f"Could not apply modern styling to params dialog: {e}")

    def _populate_dropdown(self, control_name, items_map, selected_val):
        dropdown = self.dialog.getControl(control_name)
        if not dropdown: return

        model = dropdown.getModel()
        model.StringItemList = ()
        
        selected_pos = 0
        texts = []
        for i, key in enumerate(items_map.keys()):
            texts.append(str(items_map[key]))
            if str(key) == str(selected_val):
                selected_pos = i

        model.StringItemList = tuple(texts)
        if len(texts) > 0:
            model.SelectedItems = (selected_pos,)
            try:
                dropdown.selectItemPos(selected_pos, True)
            except Exception:
                pass

    def _extract_dropdown_key(self, control_name, valid_map, fallback):
        dropdown = self.dialog.getControl(control_name)
        if not dropdown: return fallback
        try:
            selected_pos_tuple = dropdown.getSelectedItemPos()
            # If nothing selected, or empty tuple returned, use fallback
            if not selected_pos_tuple and not isinstance(selected_pos_tuple, int):
                return fallback
                
            selected_pos = selected_pos_tuple[0] if isinstance(selected_pos_tuple, tuple) else int(selected_pos_tuple)
            
            if 0 <= selected_pos < len(valid_map):
                keys = list(valid_map.keys())
                return str(keys[selected_pos])
        except Exception as e:
            logger.debug(f"Error extracting dropdown key for {control_name}: {e}")
        return fallback

    def actionPerformed(self, event):
        command = event.ActionCommand
        logger.info(f"Advanced Params action: {command}")
        
        if command == "cancel":
            self.dialog.endExecute()
        elif command == "save":
            self.selected_psm = self._extract_dropdown_key("PSMDropdown", self.psm_map, self.selected_psm)
            self.selected_oem = self._extract_dropdown_key("OEMDropdown", self.oem_map, self.selected_oem)
            self._is_saved = True
            self.dialog.endExecute()


# --- Help Dialog Handler ---

class TejOCRHelpDialogHandler(BaseDialogHandler):
    """Handler for the dedicated formatted Help dialog."""
    def __init__(self, ctx, parent_frame=None):
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_help_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.parent_frame = parent_frame

    def show(self):
        smgr = self.ctx.ServiceManager
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_help_dialog.xdl"
        try:
            dprov = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider2", self.ctx)
            self.dialog = dprov.createDialog(dialog_url)
            
            ctrl_close = self.dialog.getControl("CloseHelpButton")
            if ctrl_close:
                ctrl_close.setActionCommand("close")
                ctrl_close.addActionListener(self)
                
            self._apply_modern_styling()
            self.dialog.execute()
        except Exception as e:
            logger.error(f"Failed to show Help Dialog: {e}", exc_info=True)
            raise e

    def _apply_modern_styling(self):
        try:
            # Color constants matching our theme
            COLOR_GREEN = 0x22C55E   # Operations/Dependencies
            COLOR_BLUE = 0x3B82F6    # Config/Tesseract
            COLOR_PURPLE = 0x8B5CF6  # Default Options
            COLOR_AMBER = 0xF59E0B   # Advanced/Warnings
            
            headers = [
                ("Header1", COLOR_GREEN),
                ("Header2", COLOR_BLUE),
                ("Header3", COLOR_PURPLE),
                ("Header4", COLOR_AMBER),
                ("Header5", COLOR_GREEN),
            ]
            for head_id, color in headers:
                ctrl = self.dialog.getControl(head_id)
                if ctrl:
                    model = ctrl.getModel()
                    model.TextColor = color
                    model.FontWeight = 150 # Bold
            
            close_btn = self.dialog.getControl("CloseHelpButton")
            if close_btn:
                model = close_btn.getModel()
                model.BackgroundColor = 0x4B5563 # Slate grey
                model.TextColor = 0xFFFFFF # White
                model.FontWeight = 150
        except Exception as e:
            logger.debug(f"Could not apply modern styling to help dialog: {e}")

    def actionPerformed(self, event):
        command = event.ActionCommand
        if command == "close":
            self.dialog.endExecute()


class TejOCRMessageDialogHandler(BaseDialogHandler):
    """Handler for the dedicated message dialog shown from Settings."""

    def __init__(self, ctx, parent_frame=None):
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_message_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.parent_frame = parent_frame

    def show(self):
        smgr = self.ctx.ServiceManager
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_message_dialog.xdl"
        try:
            dprov = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider2", self.ctx)
            self.dialog = dprov.createDialog(dialog_url)

            ctrl_open_akriti = self.dialog.getControl("OpenAKritiButton")
            if ctrl_open_akriti:
                ctrl_open_akriti.setActionCommand("open_akriti")
                ctrl_open_akriti.addActionListener(self)

            ctrl_close = self.dialog.getControl("CloseMessageButton")
            if ctrl_close:
                ctrl_close.setActionCommand("close")
                ctrl_close.addActionListener(self)

            self._apply_modern_styling()
            self.dialog.execute()
        except Exception as e:
            logger.error(f"Failed to show Message Dialog: {e}", exc_info=True)
            raise e

    def _apply_modern_styling(self):
        try:
            headers = [
                ("MessageHeader1", 0x22C55E),
                ("MessageHeader2", 0xEF4444),
                ("MessageHeader3", 0x3B82F6),
                ("MessageHeader4", 0xF59E0B),
                ("MessageHeader5", 0x8B5CF6),
            ]
            for control_id, color in headers:
                ctrl = self.dialog.getControl(control_id)
                if ctrl:
                    model = ctrl.getModel()
                    model.TextColor = color
                    model.FontWeight = 150

            close_btn = self.dialog.getControl("CloseMessageButton")
            if close_btn:
                model = close_btn.getModel()
                model.BackgroundColor = 0x4B5563
                model.TextColor = 0xFFFFFF
                model.FontWeight = 150

            open_btn = self.dialog.getControl("OpenAKritiButton")
            if open_btn:
                model = open_btn.getModel()
                model.BackgroundColor = 0x7C3AED
                model.TextColor = 0xFFFFFF
                model.FontWeight = 150
        except Exception as e:
            logger.debug(f"Could not apply modern styling to message dialog: {e}")

    def actionPerformed(self, event):
        command = event.ActionCommand
        if command == "open_akriti":
            import webbrowser

            url = "https://github.com/varshneydevansh/aKriti"
            try:
                webbrowser.open(url)
            except Exception as e:
                logger.error(f"Failed to open aKriti URL: {e}")
                uno_utils.show_message_box(
                    "Open aKriti",
                    f"Could not open browser.\nVisit: {url}",
                    "infobox",
                    parent_frame=self.parent_frame,
                    ctx=self.ctx,
                )
        elif command == "close":
            self.dialog.endExecute()


class TejOCRCompleteDialogHandler(BaseDialogHandler):
    """Structured OCR completion dialog with grouped sections similar to Settings Help."""

    def __init__(self, ctx, parent_frame=None, summary_text="", sources_text="", profile_text="", runtime_text=""):
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_ocr_complete_dialog_v2.xdl"
        super().__init__(ctx, dialog_url)
        self.parent_frame = parent_frame
        self.summary_text = summary_text or _("OCR finished successfully.")
        self.sources_text = sources_text or _("No source details available.")
        self.profile_text = profile_text or _("No OCR profile details available.")
        self.runtime_text = runtime_text or _("No runtime diagnostics recorded for this run.")

    @staticmethod
    def _normalize_block_text(text, fallback, max_chars=1800, max_lines=18):
        normalized = str(text or "").replace("\r\n", "\n").replace(" | ", "\n").strip()
        if not normalized:
            normalized = fallback

        lines = normalized.splitlines()
        if len(lines) > max_lines:
            normalized = "\n".join(lines[:max_lines] + ["..."])

        if len(normalized) > max_chars:
            normalized = normalized[: max_chars - 3].rstrip() + "..."
        return normalized

    @staticmethod
    def _split_profile_blocks(text):
        normalized = str(text or "").replace("\r\n", "\n").strip()
        if not normalized:
            return "", "", ""

        main_block, processing_block, recognition_block = normalized, "", ""
        if "\nProcessing:\n" in normalized:
            main_block, remainder = normalized.split("\nProcessing:\n", 1)
            processing_block = "Processing:\n"
            if "\nRecognition:\n" in remainder:
                processing_items, recognition_items = remainder.split("\nRecognition:\n", 1)
                processing_block += processing_items.strip()
                recognition_block = "Recognition:\n" + recognition_items.strip()
            else:
                processing_block += remainder.strip()
        return main_block.strip(), processing_block.strip(), recognition_block.strip()

    @staticmethod
    def _split_source_blocks(text):
        normalized = str(text or "").replace("\r\n", "\n").strip()
        if not normalized:
            return "", ""
        if "\n" not in normalized:
            return normalized, ""
        first_line, remainder = normalized.split("\n", 1)
        return first_line.strip(), remainder.strip()

    @staticmethod
    def _normalize_list_items(text, max_chars=120):
        normalized = str(text or "").replace("\r\n", "\n").strip()
        if not normalized:
            return ()

        items = []
        for raw_line in normalized.splitlines():
            line = str(raw_line or "").strip()
            if not line:
                continue
            if len(line) > max_chars:
                line = line[: max_chars - 3].rstrip() + "..."
            items.append(line)
        return tuple(items)

    @staticmethod
    def _split_runtime_blocks(text):
        normalized = str(text or "").replace("\r\n", "\n").strip()
        if not normalized:
            return "", "", ""

        summary_block, requested_block, effective_block = normalized, "", ""
        if "\n\nRequested:\n" in normalized:
            summary_block, remainder = normalized.split("\n\nRequested:\n", 1)
            requested_block = "Requested:\n"
            if "\n\nEffective:\n" in remainder:
                requested_items, effective_items = remainder.split("\n\nEffective:\n", 1)
                requested_block += requested_items.strip()
                effective_block = "Effective:\n" + effective_items.strip()
            else:
                requested_block += remainder.strip()
        return summary_block.strip(), requested_block.strip(), effective_block.strip()

    @staticmethod
    def _estimate_visual_lines(text, wrap_chars):
        total = 0
        for line in str(text or "").splitlines() or [""]:
            line_len = max(1, len(line))
            total += max(1, (line_len + max(1, wrap_chars) - 1) // max(1, wrap_chars))
        return total

    @staticmethod
    def _safe_get_bounds(control):
        try:
            bounds = control.getPosSize()
            return (
                int(getattr(bounds, "X", 0)),
                int(getattr(bounds, "Y", 0)),
                int(getattr(bounds, "Width", 0)),
                int(getattr(bounds, "Height", 0)),
            )
        except Exception:
            return (0, 0, 0, 0)

    @staticmethod
    def _safe_set_bounds(control, x, y, width, height):
        if not control:
            return
        try:
            control.setPosSize(int(x), int(y), int(width), int(height), 15)
            return
        except Exception:
            pass
        try:
            model = control.getModel()
            if hasattr(model, "PositionX"):
                model.PositionX = int(x)
            if hasattr(model, "PositionY"):
                model.PositionY = int(y)
            if hasattr(model, "Width"):
                model.Width = int(width)
            if hasattr(model, "Height"):
                model.Height = int(height)
        except Exception:
            pass

    def _apply_dynamic_layout(self, block_texts):
        section_specs = (
            (
                "HeaderSummary",
                (("SummaryText", 2, 26, 64, 44),),
            ),
            (
                "HeaderSources",
                (
                    ("SourcesSummaryText", 1, 18, 32, 50),
                    ("SourcesListBox", 4, 58, 100, 0),
                ),
            ),
            (
                "HeaderProfile",
                (
                    ("ProfileMainText", 4, 34, 92, 46),
                    ("ProfileProcessingText", 5, 42, 110, 46),
                    ("ProfileRecognitionText", 5, 42, 110, 46),
                ),
            ),
            (
                "HeaderRuntime",
                (
                    ("RuntimeSummaryText", 3, 28, 82, 46),
                    ("RuntimeRequestedText", 4, 34, 96, 46),
                    ("RuntimeEffectiveText", 5, 42, 120, 46),
                ),
            ),
        )

        line_height = 10
        wrap_chars = 52
        current_y = 10
        section_gap = 12
        header_to_text = 20
        text_padding = 8
        block_gap = 6

        for header_id, text_specs in section_specs:
            header = self.dialog.getControl(header_id)
            if not header:
                continue

            header_x, _header_y, header_w, header_h = self._safe_get_bounds(header)
            self._safe_set_bounds(header, header_x, current_y, header_w or 410, header_h or 10)

            block_top = current_y + header_to_text
            last_bottom = block_top
            for text_id, min_lines, min_height, max_height, wrap_adjust in text_specs:
                text_control = self.dialog.getControl(text_id)
                if not text_control:
                    continue

                text_x, _text_y, text_w, _text_h = self._safe_get_bounds(text_control)
                block_text = block_texts.get(text_id, "")
                if not block_text:
                    self._safe_set_bounds(text_control, text_x or 20, last_bottom, text_w or 390, 1)
                    continue

                if isinstance(block_text, (list, tuple)):
                    item_count = len(block_text)
                    visible_rows = min(6, max(min_lines, item_count))
                    desired_height = min(max_height, max(min_height, visible_rows * 12 + 10))
                    self._safe_set_bounds(text_control, text_x or 20, last_bottom, text_w or 390, desired_height)
                    last_bottom = last_bottom + desired_height + block_gap
                    continue

                estimated_lines = self._estimate_visual_lines(block_text, max(28, wrap_chars + wrap_adjust))
                estimated_lines = max(min_lines, estimated_lines)
                desired_height = min(max_height, max(min_height, estimated_lines * line_height + text_padding))
                self._safe_set_bounds(text_control, text_x or 20, last_bottom, text_w or 390, desired_height)
                last_bottom = last_bottom + desired_height + block_gap

            current_y = last_bottom + section_gap - block_gap

        footer = self.dialog.getControl("SectionFooter")
        close_btn = self.dialog.getControl("CloseResultButton")
        footer_x, _footer_y, footer_w, footer_h = self._safe_get_bounds(footer) if footer else (10, 0, 410, 10)
        close_x, _close_y, close_w, close_h = self._safe_get_bounds(close_btn) if close_btn else (170, 0, 90, 22)

        footer_y = current_y + 10
        close_y = footer_y + 16
        dialog_x, dialog_y, dialog_w, _dialog_h = self._safe_get_bounds(self.dialog)
        effective_close_h = max(close_h or 24, 24)
        dialog_h = max(440, min(720, close_y + effective_close_h + 34))

        if footer:
            self._safe_set_bounds(footer, footer_x or 10, footer_y, footer_w or 410, footer_h or 10)
        if close_btn:
            centered_x = max(20, ((dialog_w or 430) - (close_w or 90)) // 2)
            self._safe_set_bounds(close_btn, centered_x, close_y, close_w or 90, effective_close_h)
        self._safe_set_bounds(self.dialog, dialog_x, dialog_y, dialog_w or 430, dialog_h)

    def show(self):
        smgr = self.ctx.ServiceManager
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_ocr_complete_dialog_v2.xdl"
        try:
            dprov = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider2", self.ctx)
            self.dialog = dprov.createDialog(dialog_url)

            close_btn = self.dialog.getControl("CloseResultButton")
            if close_btn:
                close_btn.setActionCommand("close")
                close_btn.addActionListener(self)

            normalized_blocks = {}
            sources_summary, sources_list = self._split_source_blocks(self.sources_text)
            source_items = self._normalize_list_items(sources_list, max_chars=112)
            profile_main, profile_processing, profile_recognition = self._split_profile_blocks(self.profile_text)
            runtime_summary, runtime_requested, runtime_effective = self._split_runtime_blocks(self.runtime_text)

            for control_name, text, fallback, max_chars, max_lines in (
                ("SummaryText", self.summary_text, _("OCR finished successfully."), 320, 4),
                ("SourcesSummaryText", sources_summary, _("No source details available."), 320, 3),
                ("ProfileMainText", profile_main, _("No OCR profile details available."), 900, 8),
                ("ProfileProcessingText", profile_processing, "", 900, 10),
                ("ProfileRecognitionText", profile_recognition, "", 900, 10),
                ("RuntimeSummaryText", runtime_summary, _("No runtime diagnostics recorded for this run."), 900, 8),
                ("RuntimeRequestedText", runtime_requested, "", 900, 10),
                ("RuntimeEffectiveText", runtime_effective, "", 900, 12),
            ):
                control = self.dialog.getControl(control_name)
                if control:
                    normalized_text = self._normalize_block_text(text, fallback, max_chars=max_chars, max_lines=max_lines)
                    normalized_blocks[control_name] = normalized_text
                    control.setText(normalized_text)

            source_list_control = self.dialog.getControl("SourcesListBox")
            if source_list_control:
                normalized_blocks["SourcesListBox"] = source_items
                try:
                    source_list_control.getModel().StringItemList = tuple(source_items)
                except Exception:
                    pass

            self._apply_dynamic_layout(normalized_blocks)

            self._apply_modern_styling()
            self.dialog.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to show OCR Complete dialog: {e}", exc_info=True)
            return False

    def _apply_modern_styling(self):
        try:
            header_colors = (
                ("HeaderSummary", 0x22C55E),
                ("HeaderSources", 0x3B82F6),
                ("HeaderProfile", 0x8B5CF6),
                ("HeaderRuntime", 0xF59E0B),
            )
            for control_id, color in header_colors:
                control = self.dialog.getControl(control_id)
                if control:
                    model = control.getModel()
                    model.TextColor = color
                    model.FontWeight = 150

            summary_text = self.dialog.getControl("SummaryText")
            if summary_text:
                model = summary_text.getModel()
                model.FontHeight = 11
                model.FontWeight = 150

            close_btn = self.dialog.getControl("CloseResultButton")
            if close_btn:
                model = close_btn.getModel()
                model.BackgroundColor = 0x22C55E
                model.TextColor = 0xFFFFFF
                model.FontWeight = 150
        except Exception as e:
            logger.debug(f"Could not apply OCR Complete dialog styling: {e}")

    def actionPerformed(self, event):
        command = event.ActionCommand
        if command == "close":
            self.dialog.endExecute()


# --- Setup Dialog Handler ---

class TejOCRSetupDialogHandler(BaseDialogHandler):
    """Handler for the dedicated Setup & Diagnostics dialog."""

    COLOR_GREEN = 0x009900
    COLOR_RED = 0xCC0000
    COLOR_AMBER = 0xCC8800
    _SETUP_COMMAND_BY_NAME = {
        "CopyCommandButton": "copy_command",
        "SaveScriptButton": "save_script",
        "CopySnapshotButton": "copy_snapshot",
        "OpenGuideButton": "open_guide",
        "ReCheckButton": "recheck",
        "CloseSetupButton": "close_setup",
        "copyCommand": "copy_command",
        "savescriptbutton": "save_script",
        "copycommandbutton": "copy_command",
        "copysnapshotbutton": "copy_snapshot",
        "openguidebutton": "open_guide",
        "recheckbutton": "recheck",
        "closesetupbutton": "close_setup",
        "savescript": "save_script",
        "copysnapshot": "copy_snapshot",
        "openguide": "open_guide",
        "recheck": "recheck",
        "close": "close_setup",
    }
    _SETUP_COMMAND_ALIASES = {
        "copy": "copy_command",
        "copycommand": "copy_command",
        "copy command": "copy_command",
        "copycommandbutton": "copy_command",
        "save": "save_script",
        "save_script": "save_script",
        "savescript": "save_script",
        "save script": "save_script",
        "savescriptbutton": "save_script",
        "copysnapshot": "copy_snapshot",
        "copy snapshot": "copy_snapshot",
        "copysnapshotbutton": "copy_snapshot",
        "openguide": "open_guide",
        "open guide": "open_guide",
        "openguidebutton": "open_guide",
        "recheck": "recheck",
        "re-check": "recheck",
        "recheckbutton": "recheck",
        "re_check": "recheck",
        "close": "close_setup",
        "close_setup": "close_setup",
        "closebutton": "close_setup",
        "closesetupbutton": "close_setup",
        "close dialog": "close_setup",
    }
    
    def __init__(self, ctx, parent_frame=None):
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_setup_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.parent_frame = parent_frame
        self.dependency_status = None
        self._install_command = ""
        self._copy_payload = ""
        self._copy_payload_commands = []
        self._script_payload = ""
        self._script_filename = ""
        self._support_snapshot = ""
        self._install_guide_url = "https://github.com/varshneydevansh/TejOCR/blob/main/docs/troubleshooting/installation.md"

    def _collect_pdf_install_plan(self, status_payload):
        """Build deterministic install commands required for PDF OCR."""
        ds = status_payload or {}
        plans = []
        seen = set()

        def _add_cmd(cmd):
            clean = _normalize_command_for_copy(cmd)
            if not clean:
                return
            lowered = clean.lower()
            if lowered in seen:
                return
            seen.add(lowered)
            plans.append(clean)

        for source in (
            ds.get("pdf_renderer_hints") or [],
            ds.get("next_steps") or "",
            _renderer_install_hints_for_platform(),
            ds.get("pdf_renderer_error") or "",
        ):
            for cmd in _collect_system_renderer_commands(source):
                _add_cmd(cmd)

        _add_cmd(_resolve_pdf_install_command(ds))

        if not plans:
            fallback = _build_pip_command(_get_lo_python_path())
            if fallback:
                _add_cmd("{cmd} pdf2image".format(cmd=fallback))

        return plans

    @staticmethod
    def _build_command_list_text(commands):
        if not commands:
            return "Install command not available."
        return "\n".join("{idx}. {cmd}".format(idx=index + 1, cmd=command) for index, command in enumerate(commands))

    def show(self):
        """Create and show the Setup dialog."""
        smgr = self.ctx.ServiceManager
        
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_setup_dialog.xdl"
        try:
            # Try creating dialog via DialogProvider
            dprov = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider2", self.ctx)
            self.dialog = dprov.createDialog(dialog_url)
        except Exception as e:
            logger.error(f"Failed to create setup dialog: {e}", exc_info=True)
            raise

        # Attach button listeners
        for btn_name, cmd in [("CopyCommandButton", "copy_command"),
                              ("SaveScriptButton", "save_script"),
                              ("CopySnapshotButton", "copy_snapshot"),
                              ("OpenGuideButton", "open_guide"),
                              ("ReCheckButton", "recheck"),
                              ("CloseSetupButton", "close_setup")]:
            try:
                ctrl = self.dialog.getControl(btn_name)
                if ctrl:
                    try:
                        ctrl.setActionCommand(cmd)
                    except Exception:
                        ctrl.getModel().ActionCommand = cmd
                    try:
                        # Also keep a model-level tag for older/unreliable LO layouts.
                        ctrl.getModel().HelpText = cmd
                    except Exception:
                        pass
                    ctrl.addActionListener(self)
            except Exception:
                pass

        # Run initial check
        self._run_check()
        
        # Apply modern UI styling to buttons
        self._apply_modern_styling()
        
        # Show modal
        self.dialog.execute()

    def _apply_modern_styling(self):
        """Apply bold dynamic UNO styling to Setup dialog buttons."""
        try:
            from com.sun.star.awt import FontDescriptor
            from com.sun.star.awt.FontWeight import BOLD
            
            # ReCheck / Validate Button (Primary Action)
            recheck = self.dialog.getControl("ReCheckButton")
            if recheck:
                recheck_model = recheck.getModel()
                recheck_model.BackgroundColor = getattr(self, "COLOR_BTN_PRIMARY", 0x0066CC)
                recheck_model.TextColor = getattr(self, "COLOR_TEXT_ON_DARK", 0xFFFFFF)
                fd = recheck_model.FontDescriptor
                fd.Weight = BOLD
                recheck_model.FontDescriptor = fd

            # Copy Command Button (Emphasis Action)
            copy_cmd = self.dialog.getControl("CopyCommandButton")
            if copy_cmd:
                copy_model = copy_cmd.getModel()
                copy_model.BackgroundColor = getattr(self, "COLOR_BTN_DARK", 0x333333)
                copy_model.TextColor = getattr(self, "COLOR_TEXT_ON_DARK", 0xFFFFFF)
                fd = copy_model.FontDescriptor
                fd.Weight = BOLD
                copy_model.FontDescriptor = fd

            save_script = self.dialog.getControl("SaveScriptButton")
            if save_script:
                save_model = save_script.getModel()
                save_model.BackgroundColor = getattr(self, "COLOR_BTN_SUCCESS", 0x22C55E)
                save_model.TextColor = getattr(self, "COLOR_TEXT_ON_DARK", 0xFFFFFF)
                fd = save_model.FontDescriptor
                fd.Weight = BOLD
                save_model.FontDescriptor = fd

            copy_snapshot = self.dialog.getControl("CopySnapshotButton")
            if copy_snapshot:
                snapshot_model = copy_snapshot.getModel()
                snapshot_model.BackgroundColor = getattr(self, "COLOR_BTN_DARK", 0x333333)
                snapshot_model.TextColor = getattr(self, "COLOR_TEXT_ON_DARK", 0xFFFFFF)
                fd = snapshot_model.FontDescriptor
                fd.Weight = BOLD
                snapshot_model.FontDescriptor = fd

            open_guide = self.dialog.getControl("OpenGuideButton")
            if open_guide:
                guide_model = open_guide.getModel()
                guide_model.BackgroundColor = getattr(self, "COLOR_BTN_WARNING", 0xF59E0B)
                guide_model.TextColor = getattr(self, "COLOR_TEXT_ON_DARK", 0xFFFFFF)
                fd = guide_model.FontDescriptor
                fd.Weight = BOLD
                guide_model.FontDescriptor = fd
                
        except Exception as e:
            logger.debug(f"Setup dialog modern styling failed: {e}")

    def _run_check(self):
        """Run dependency checks and populate the dialog."""
        self._set_copy_status("Running dependency checks...", "info")
        self._copy_payload = ""
        self._install_command = ""
        self._script_payload = ""
        self._script_filename = ""
        # Ensure runtime PATH is fresh for PDF renderer probes during active
        # LibreOffice sessions.
        try:
            os_env_path = os.environ.get("PATH", "")
            extra_paths = (
                "/opt/homebrew/bin",
                "/opt/homebrew/opt/poppler/bin",
                "/usr/local/bin",
                "/usr/local/opt/poppler/bin",
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
            )
            merged_paths = []
            for p in (os_env_path.split(os.pathsep) + list(extra_paths)):
                if p and p not in merged_paths:
                    merged_paths.append(p)
            os.environ["PATH"] = os.pathsep.join(merged_paths)
        except Exception:
            pass

        # Refresh module caches before checking so installs done in this session are detected.
        try:
            import importlib
            importlib.invalidate_caches()
            try:
                from tejocr import tejocr_pdf
                importlib.reload(tejocr_pdf)
            except Exception:
                pass
        except Exception:
            pass

        self.dependency_status = _check_dependencies()
        ds = self.dependency_status or {}
        self._support_snapshot = self._build_support_snapshot(ds)
        status_hint = (ds.get("pdf_renderer_error") or "").strip()

        # Always re-scan the runtime for renderer binaries to avoid stale cached status after
        # in-session installations/updates (especially for poppler tools installed from Homebrew).
        runtime_renderer_ok, runtime_renderer_engine = _detect_pdf_renderer_binary()
        declared_renderer_ok = bool(ds.get("pdf_renderer_available", False))
        declared_renderer_engine = (ds.get("pdf_renderer_engine") or "").strip()

        if runtime_renderer_ok:
            ds["pdf_renderer_available"] = True
            ds["pdf_renderer_engine"] = runtime_renderer_engine
            ds["pdf_renderer_status"] = "PDF Renderer: Available ({})".format(
                runtime_renderer_engine
            )
            ds["pdf_renderer_error"] = ""
            logger.info(
                "Runtime PDF renderer probe detected engine=%s; refreshing setup status.",
                runtime_renderer_engine,
            )
        elif declared_renderer_ok:
            # Keep dependency view stable if the module probe is authoritative for the session.
            ds["pdf_renderer_available"] = True
            ds["pdf_renderer_engine"] = declared_renderer_engine
            if declared_renderer_engine:
                ds["pdf_renderer_status"] = "PDF Renderer: Available ({})".format(
                    declared_renderer_engine
                )
            else:
                ds["pdf_renderer_status"] = "PDF Renderer: Available"
            ds["pdf_renderer_error"] = ""
            logger.debug("Runtime renderer probe missed, keeping previously detected renderer as available.")
        else:
            ds["pdf_renderer_available"] = False
            ds["pdf_renderer_engine"] = ""
            ds["pdf_renderer_error"] = ds.get("pdf_renderer_error") or "No PDF renderer detected for PDF OCR"
            ds["pdf_renderer_status"] = "PDF Renderer: Not found"
        pdf_renderer_ok = bool(ds.get("pdf_renderer_available", False))
        pdf_renderer_engine = (ds.get("pdf_renderer_engine") or "").strip()
        if pdf_renderer_ok:
            pdf_renderer_status = (
                f"PDF Renderer: Available ({pdf_renderer_engine})"
                if pdf_renderer_engine
                else "PDF Renderer: Available"
            )
        else:
            pdf_renderer_status = "PDF Renderer: Not found"

        command_candidates = list(ds.get("setup_commands") or [])
        if not command_candidates and not pdf_renderer_ok:
            command_candidates = self._collect_pdf_install_plan(ds)

        # Color each component row using the new runtime model.
        rows = [
            (
                "TesseractRow",
                "ok" if ds.get("tesseract_ok", False) else "error",
                (
                    f"✅ Tesseract OCR: {ds.get('tesseract_version', 'Available')} | {ds.get('tesseract_path_label', 'Available in PATH')}"
                    if ds.get("tesseract_ok", False)
                    else "❌ Tesseract OCR: Not found"
                ),
            ),
            (
                "NumpyRow",
                "ok" if ds.get("lo_python_path_resolved", False) else "warn",
                "✅ LibreOffice Python: {path}".format(
                    path=ds.get("lo_python_path_display") or "Auto-detect unavailable; falling back to generic python command"
                ),
            ),
            (
                "PytesseractRow",
                "ok" if ds.get("pip_ok", False) else "warn",
                (
                    "✅ pip in LibreOffice Python: {version}".format(
                        version=ds.get("pip_version") or "available"
                    )
                    if ds.get("pip_ok", False)
                    else "⚠ pip in LibreOffice Python: not detected (bootstrap may be required before installing extras)"
                ),
            ),
            (
                "PillowRow",
                "ok" if ds.get("pillow_ok", False) else "warn",
                (
                    "✅ Pillow: {version} (advanced image preprocessing available)".format(
                        version=ds.get("pillow_version") or "installed"
                    )
                    if ds.get("pillow_ok", False)
                    else "⚠ Pillow: not installed (core OCR still works; preprocessing features are reduced)"
                ),
            ),
            (
                "PdfRendererRow",
                "ok" if pdf_renderer_ok else "warn",
                f"✅ {pdf_renderer_status}" if pdf_renderer_ok else f"⚠ {pdf_renderer_status}",
            ),
            (
                "UnoRow",
                "ok" if ds.get("optional_compat_ready", False) else "warn",
                ds.get("optional_compat_label") or "ℹ Compatibility extras: optional",
            ),
        ]

        for ctrl_name, level, text in rows:
            try:
                ctrl = self.dialog.getControl(ctrl_name)
                if ctrl:
                    ctrl.setText(text)
                    color = self.COLOR_AMBER
                    if level == "ok":
                        color = self.COLOR_GREEN
                    elif level == "error":
                        color = self.COLOR_RED
                    ctrl.getModel().TextColor = color
            except Exception:
                pass

        next_steps = ds.get("next_steps", "") if isinstance(ds.get("next_steps"), str) else ""

        if pdf_renderer_ok:
            logger.debug("PDF renderer already available during setup diagnostics.")

        if command_candidates:
            self._copy_payload_commands = command_candidates
            self._install_command = command_candidates[0] if command_candidates else ""
            self._copy_payload = self._build_command_list_text(command_candidates)
            self._script_payload, self._script_filename = _build_setup_script_payload(command_candidates)
        else:
            self._copy_payload = ""
            self._install_command = ""
            self._copy_payload_commands = []
            self._script_payload = ""
            self._script_filename = ""

        detail_sections = []

        def _append_detail_section(title, lines):
            clean_lines = [str(line).rstrip() for line in (lines or []) if str(line or "").strip()]
            if not clean_lines:
                return
            detail_sections.append("{title}\n{body}".format(
                title=str(title or "").strip(),
                body="\n".join(clean_lines),
            ))

        missing_components = []
        if not ds.get("tesseract_ok", False):
            missing_components.append("Tesseract OCR")
        if not pdf_renderer_ok:
            missing_components.append("PDF renderer for PDF OCR")

        optional_components = []
        if not ds.get("pip_ok", False):
            optional_components.append("pip bootstrap in LibreOffice Python")
        if not ds.get("pillow_ok", False):
            optional_components.append("Pillow for preprocessing")
        optional_missing_packages = list(ds.get("optional_missing_packages") or [])
        if optional_missing_packages:
            optional_components.append(
                "Compatibility packages: {packages}".format(
                    packages=", ".join(optional_missing_packages)
                )
            )

        if missing_components:
            _append_detail_section(
                "REQUIRED NOW",
                ["- {item}".format(item=item) for item in missing_components],
            )
        else:
            _append_detail_section("REQUIRED NOW", ["- Image OCR is ready."])

        runtime_lines = [
            "- Python:",
            "  {path}".format(path=ds.get("lo_python_path_display") or "Unknown"),
        ]
        if ds.get("pip_ok", False):
            runtime_lines.append("- pip: {version}".format(version=ds.get("pip_version") or "available"))
        else:
            runtime_lines.append("- pip: not detected in this runtime")
        _append_detail_section("LIBREOFFICE RUNTIME", runtime_lines)

        if not ds.get("tesseract_ok", False):
            tesseract_commands = list(ds.get("tesseract_install_commands") or [])
            if tesseract_commands:
                tesseract_lines = []
                for index, cmd in enumerate(tesseract_commands, start=1):
                    tesseract_lines.append("- Command {idx}:".format(idx=index))
                    tesseract_lines.append("  {cmd}".format(cmd=cmd))
                _append_detail_section("INSTALL TESSERACT FOR THIS DEVICE", tesseract_lines)

        if optional_components:
            _append_detail_section(
                "RECOMMENDED / OPTIONAL SETUP",
                ["- {item}".format(item=item) for item in optional_components],
            )

        python_install_commands = list(ds.get("python_install_commands") or [])
        if python_install_commands:
            package_lines = []
            for index, cmd in enumerate(python_install_commands, start=1):
                package_lines.append("- Command {idx}:".format(idx=index))
                package_lines.append("  {cmd}".format(cmd=cmd))
            _append_detail_section("LIBREOFFICE PYTHON PACKAGE COMMANDS", package_lines)

        pip_bootstrap_commands = list(ds.get("pip_bootstrap_commands") or [])
        if pip_bootstrap_commands:
            bootstrap_lines = []
            for index, cmd in enumerate(pip_bootstrap_commands, start=1):
                bootstrap_lines.append("- Step {idx}:".format(idx=index))
                bootstrap_lines.append("  {cmd}".format(cmd=cmd))
            _append_detail_section("IF pip IS MISSING, RUN", bootstrap_lines)

        if pdf_renderer_ok:
            _append_detail_section(
                "PDF STATUS",
                [
                    "- {status}".format(
                        status=(
                            "PDF renderer detected: {engine}".format(engine=pdf_renderer_engine)
                            if pdf_renderer_engine else "PDF renderer: Available"
                        )
                    )
                ],
            )
        else:
            pdf_status_lines = ["- PDF OCR (PDF files) still needs a renderer."]
            if status_hint:
                pdf_status_lines.append("- Current check: {status}".format(status=status_hint))
            _append_detail_section("PDF STATUS", pdf_status_lines)

        if command_candidates:
            copy_lines = []
            for index, command in enumerate(command_candidates, start=1):
                copy_lines.append("- Command {idx}:".format(idx=index))
                copy_lines.append("  {command}".format(command=command))
            _append_detail_section("READY-TO-COPY COMMANDS", copy_lines)
        if next_steps:
            _append_detail_section("NEXT STEPS", next_steps.splitlines())

        details_text = "\n\n".join(detail_sections).strip()

        try:
            cmd_field = self.dialog.getControl("InstallCommandField")
            helper_field = self.dialog.getControl("InstallInstructionsField")
            cmd_label = self.dialog.getControl("InstallCommandLabel")
            helper_label = self.dialog.getControl("InstallInstructionsLabel")
            
            if cmd_label:
                cmd_label.setText("Recommended terminal command:")
            if helper_label:
                helper_label.setText("Platform Reference Guide:")

            if not command_candidates:
                if cmd_field:
                    cmd_field.setText("No install command required. Check complete.")
            else:
                if cmd_field:
                    if self._copy_payload:
                        cmd_field.setText(self._copy_payload)
                    else:
                        cmd_field.setText("Install command not available.")

            if helper_field:
                ref_text = ds.get("installation_guide", "")
                if details_text and ref_text:
                     helper_field.setText(f"{ref_text}\n\n---\nSystem Details:\n{details_text}")
                elif ref_text:
                     helper_field.setText(ref_text)
                elif details_text:
                    helper_field.setText(f"System Details:\n{details_text}")
                elif next_steps:
                    helper_field.setText(next_steps)
                else:
                    helper_field.setText("No additional setup notes.")
            elif cmd_field and next_steps:
                # Fallback for older dialog templates.
                if not self._copy_payload:
                    cmd_field.setText(next_steps or "(No install command available.)")
            if helper_field and not details_text and not next_steps:
                # Always keep instructions visible in fallback scenarios.
                helper_field.setText("No additional setup notes.")
        except Exception:
            pass

        can_copy_command = bool(self._copy_payload and self._copy_payload.strip())
        payload_lines = [line for line in self._copy_payload.split("\n") if line.strip()]
        payload_count = len(payload_lines)

        # Keep copy control states explicit so users can tell when copy is meaningful.
        try:
            copy_btn = self.dialog.getControl("CopyCommandButton")
            if copy_btn:
                copy_btn.setEnable(can_copy_command)
                if can_copy_command:
                    cmd_count = max(len(self._copy_payload_commands), 1)
                    copy_btn.setText(
                        "Copy Command to Clipboard" + (f" ({cmd_count})" if cmd_count > 1 else "")
                    )
                else:
                    copy_btn.setText("Copy Command to Clipboard")
            save_btn = self.dialog.getControl("SaveScriptButton")
            if save_btn:
                save_btn.setEnable(can_copy_command and bool(self._script_payload.strip()))
                save_btn.setText("Save Script...")
            snapshot_btn = self.dialog.getControl("CopySnapshotButton")
            if snapshot_btn:
                snapshot_btn.setEnable(bool(self._support_snapshot.strip()))
                snapshot_btn.setText("Copy Support Snapshot")
            guide_btn = self.dialog.getControl("OpenGuideButton")
            if guide_btn:
                guide_btn.setEnable(bool(self._install_guide_url))
                guide_btn.setText("Open Install Guide")
            recheck_btn = self.dialog.getControl("ReCheckButton")
            if recheck_btn:
                recheck_btn.setText("Validate / Refresh")
                recheck_btn.setEnable(True)
        except Exception:
            pass

        if not missing_components and optional_components:
            self._set_copy_status(
                "Core OCR is ready. Optional Python extras are still missing.",
                "warn",
            )
        elif not missing_components:
            self._set_copy_status("Dependency check complete: all required components are available.", "ok")
        elif can_copy_command:
            if payload_count > 1:
                self._set_copy_status(
                    "Dependency check complete. Copy the recommended commands for this device.",
                    "warn",
                )
            else:
                self._set_copy_status(
                    "Dependency check complete. Copy the recommended command for this device.",
                    "warn",
                )
        else:
            self._set_copy_status("Dependency check complete: setup is still incomplete.", "warn")

    def _set_copy_status(self, text, level="info"):
        """Update the status text shown beneath install actions."""
        if not self.dialog:
            return
        try:
            status_label = self.dialog.getControl("CopyStatusLabel")
            if status_label:
                status_label.setText(text or "")
                try:
                    normalized = (level or "").lower()
                    if normalized == "ok":
                        status_label.getModel().TextColor = self.COLOR_GREEN
                    elif normalized in {"warn", "warning"}:
                        status_label.getModel().TextColor = self.COLOR_AMBER
                    elif normalized in {"error", "bad", "fail", "failed"}:
                        status_label.getModel().TextColor = self.COLOR_RED
                    else:
                        status_label.getModel().TextColor = self.COLOR_AMBER
                except Exception:
                    pass
        except Exception:
            pass

    def actionPerformed(self, event):
        command = self._get_action_command(event)
        if not command:
            # Fallback to control name if action command metadata is not available.
            source = self._get_event_source_control(event)
            try:
                if source and command is None:
                    model = source.getModel()
                    command = getattr(model, "Name", None)
                    if callable(command):
                        command = command()
                    if not command:
                        command = getattr(model, "HelpText", None)
                        if callable(command):
                            command = command()
            except Exception:
                command = None

        if command:
            command = str(command).strip()
            mapped_command = self._SETUP_COMMAND_BY_NAME.get(command)
            if mapped_command:
                command = mapped_command
            else:
                normalized = command.lower().replace(" ", "")
                mapped_command = self._SETUP_COMMAND_BY_NAME.get(normalized)
                if mapped_command:
                    command = mapped_command
                else:
                    mapped_command = self._SETUP_COMMAND_ALIASES.get(normalized)
                    if not mapped_command:
                        mapped_command = self._SETUP_COMMAND_ALIASES.get(command.lower())
                    if mapped_command:
                        command = mapped_command

        if not command:
            self._set_copy_status("No action command found for this control.", "error")
            return

        copy_btn = None
        save_btn = None
        snapshot_btn = None
        guide_btn = None
        recheck_btn = None
        try:
            copy_btn = self.dialog.getControl("CopyCommandButton")
        except Exception:
            copy_btn = None
        try:
            save_btn = self.dialog.getControl("SaveScriptButton")
        except Exception:
            save_btn = None
        try:
            snapshot_btn = self.dialog.getControl("CopySnapshotButton")
        except Exception:
            snapshot_btn = None
        try:
            guide_btn = self.dialog.getControl("OpenGuideButton")
        except Exception:
            guide_btn = None
        try:
            recheck_btn = self.dialog.getControl("ReCheckButton")
        except Exception:
            recheck_btn = None

        if command == "copy_command":
            baseline = self._capture_control_feedback_state(copy_btn)
            if copy_btn:
                copy_btn.setFocus()
            payload_lines = [line for line in (self._copy_payload or "").split("\n") if line.strip()]
            payload_count = max(1, len(payload_lines))
            copy_label = (
                "Copying {} command(s)...".format(payload_count)
                if payload_count > 1
                else "Copying command..."
            )
            self._set_control_feedback(
                copy_btn,
                text=copy_label,
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            self._set_copy_status("Copying command to clipboard...", "info")
            copied = self._copy_to_clipboard()
            if copied:
                if payload_count > 1:
                    self._set_copy_status(
                        "Copied {} commands to clipboard.".format(payload_count),
                        "ok",
                    )
                    copied_label = "Copied {} ✓".format(payload_count)
                else:
                    self._set_copy_status("Copied command to clipboard.", "ok")
                    copied_label = "Copied ✓"
                if copy_btn:
                    self._restore_control_feedback_state(copy_btn, baseline)
                    copy_btn.setText(copied_label)
                    copy_btn.setEnable(True)
                    try:
                        copy_btn.getModel().BackgroundColor = self.COLOR_GREEN
                    except Exception:
                        pass
            else:
                self._set_copy_status("Copy failed. Select the text above and copy it manually.", "error")
                if copy_btn:
                    copy_btn.setText("Copy Command to Clipboard")
                    self._restore_control_feedback_state(copy_btn, baseline)
            return

        if command == "copy_snapshot":
            baseline = self._capture_control_feedback_state(snapshot_btn)
            if snapshot_btn:
                snapshot_btn.setFocus()
            self._set_control_feedback(
                snapshot_btn,
                text="Copying...",
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            self._set_copy_status("Copying support snapshot...", "info")
            copied = self._copy_text_to_clipboard(
                self._support_snapshot,
                "No support snapshot is available to copy.",
            )
            if copied:
                self._set_copy_status("Copied support snapshot to clipboard.", "ok")
                if snapshot_btn:
                    self._restore_control_feedback_state(snapshot_btn, baseline)
                    snapshot_btn.setText("Copied ✓")
                    snapshot_btn.setEnable(True)
                    try:
                        snapshot_btn.getModel().BackgroundColor = self.COLOR_GREEN
                    except Exception:
                        pass
            else:
                self._set_copy_status("Support snapshot copy failed.", "error")
                if snapshot_btn:
                    self._restore_control_feedback_state(snapshot_btn, baseline)
            return

        if command == "open_guide":
            baseline = self._capture_control_feedback_state(guide_btn)
            self._set_control_feedback(
                guide_btn,
                text="Opening...",
                enabled=False,
                bg_color=self.COLOR_BTN_WARNING,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            self._set_copy_status("Opening install guide...", "info")
            opened = self._open_install_guide()
            if opened:
                self._set_copy_status("Opened install guide in your browser.", "ok")
                if guide_btn:
                    self._restore_control_feedback_state(guide_btn, baseline)
                    guide_btn.setText("Opened ✓")
                    guide_btn.setEnable(True)
            else:
                self._set_copy_status("Could not open browser. Copy the install guide URL instead.", "warn")
                copied = self._copy_text_to_clipboard(
                    self._install_guide_url,
                    "Install guide URL is not available.",
                )
                if copied:
                    self._set_copy_status("Browser open failed. Copied install guide URL instead.", "warn")
                if guide_btn:
                    self._restore_control_feedback_state(guide_btn, baseline)
            return

        if command == "save_script":
            baseline = self._capture_control_feedback_state(save_btn)
            self._set_control_feedback(
                save_btn,
                text="Saving...",
                enabled=False,
                bg_color=self.COLOR_BTN_SUCCESS,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            self._set_copy_status("Preparing setup script export...", "info")
            try:
                saved_path = self._save_script_to_disk()
                if saved_path:
                    self._set_copy_status(
                        "Saved setup script: {path}".format(path=saved_path),
                        "ok",
                    )
                    if save_btn:
                        self._restore_control_feedback_state(save_btn, baseline)
                        save_btn.setText("Saved ✓")
                        save_btn.setEnable(True)
                        try:
                            save_btn.getModel().BackgroundColor = self.COLOR_GREEN
                        except Exception:
                            pass
                else:
                    self._set_copy_status("Script export cancelled.", "warn")
                    if save_btn:
                        self._restore_control_feedback_state(save_btn, baseline)
            except Exception as export_error:
                logger.error("Failed to export setup script: %s", export_error, exc_info=True)
                self._set_copy_status("Script export failed.", "error")
                if save_btn:
                    self._restore_control_feedback_state(save_btn, baseline)
            return

        if command == "recheck":
            self._set_control_feedback(
                recheck_btn,
                text="Checking...",
                enabled=False,
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            self._set_copy_status("Running dependency checks...", "info")
            try:
                self._run_check()
            finally:
                if recheck_btn:
                    recheck_btn.setText("Validate / Refresh")
                    self._set_control_feedback(
                        recheck_btn,
                        text="Validate / Refresh",
                        enabled=True,
                        bg_color=self.COLOR_BTN_PRIMARY,
                        fg_color=self.COLOR_TEXT_ON_DARK,
                    )
            return

        if command == "close_setup":
            close_btn = None
            try:
                close_btn = self.dialog.getControl("CloseSetupButton")
            except Exception:
                close_btn = None
            baseline = self._capture_control_feedback_state(close_btn)
            self._set_copy_status("Closing setup dialog.", "info")
            self._set_control_feedback(
                close_btn,
                text="Closing...",
                enabled=False,
                bg_color=self.COLOR_BTN_DANGER,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            if self.dialog:
                self.dialog.endExecute()
            self._restore_control_feedback_state(close_btn, baseline)

    def _copy_to_clipboard(self):
        """Copy install command to system clipboard using OS utilities."""
        command_lines = list(self._copy_payload_commands) if self._copy_payload_commands else []
        if not command_lines and self._install_command:
            command_lines = [self._install_command]
        elif not command_lines and self._copy_payload:
            command_lines = [self._copy_payload]
        return self._copy_lines_to_clipboard(
            command_lines,
            "No install command available to copy.",
            normalize_commands=True,
        )

    def _copy_text_to_clipboard(self, text, empty_message="Nothing available to copy."):
        payload = str(text or "").strip()
        return self._copy_lines_to_clipboard(
            [payload] if payload else [],
            empty_message,
            normalize_commands=False,
        )

    def _copy_lines_to_clipboard(self, command_lines, empty_message, normalize_commands):
        """Copy provided text lines to the system clipboard using UNO or OS fallbacks."""
        import os
        import shutil
        import subprocess
        import sys

        normalized_lines = []
        seen = set()
        for line in command_lines:
            candidate = _normalize_command_for_copy(line) if normalize_commands else str(line or "")
            candidate = candidate.strip()
            if not candidate:
                continue
            key = candidate.lower() if normalize_commands else candidate
            if key in seen:
                continue
            seen.add(key)
            normalized_lines.append(candidate)

        text = "\n".join(normalized_lines).strip()

        if not text:
            self._set_copy_status(empty_message, "warn")
            return False

        copied = False

        try:
            logger.debug(f"Copy command requested: {text}")
            # Primary path: UNO system clipboard (works inside LibreOffice across OSes)
            try:
                from tejocr import tejocr_output
                clipboard = uno_utils.create_instance(
                    "com.sun.star.datatransfer.clipboard.SystemClipboard",
                    self.ctx,
                )
                if clipboard:
                    transferable = tejocr_output.TextTransferable(text)
                    clipboard.setContents(transferable, None)
                    copied = True
            except Exception as clipboard_error:
                logger.debug(f"UNO clipboard copy failed, trying OS fallback: {clipboard_error}")

            # Fallback path for environments where UNO clipboard is unavailable.
            # Use absolute command paths where possible because LibreOffice app
            # bundles often run with a reduced PATH.
            if not copied:
                if sys.platform == "darwin":
                    # macOS
                    pbcopy_candidates = []
                    for candidate in ("/usr/bin/pbcopy", shutil.which("pbcopy"), "/bin/pbcopy"):
                        if candidate and candidate not in pbcopy_candidates:
                            pbcopy_candidates.append(candidate)
                    for candidate in pbcopy_candidates:
                        try:
                            result = subprocess.run(
                                [candidate],
                                input=text.encode("utf-8"),
                                capture_output=True,
                                check=False,
                            )
                            if result.returncode == 0:
                                copied = True
                                break
                        except FileNotFoundError:
                            continue
                elif sys.platform.startswith("linux"):
                    # Linux — try xclip first, then xsel
                    for cmd in (
                        ([shutil.which("xclip") or "xclip", "-selection", "clipboard"]),
                        ([shutil.which("xsel") or "xsel", "--clipboard", "--input"]),
                    ):
                        try:
                            result = subprocess.run(
                                cmd,
                                input=text.encode("utf-8"),
                                capture_output=True,
                                check=False,
                            )
                            if result.returncode == 0:
                                copied = True
                                break
                        except FileNotFoundError:
                            continue
                elif sys.platform == "win32":
                    clip_candidates = []
                    system_root = os.environ.get("SystemRoot", r"C:\Windows")
                    for candidate in (os.path.join(system_root, "System32", "clip.exe"), shutil.which("clip.exe"), "clip.exe"):
                        if candidate and candidate not in clip_candidates:
                            clip_candidates.append(candidate)
                    for candidate in clip_candidates:
                        try:
                            result = subprocess.run(
                                [candidate],
                                input=text.encode("utf-8"),
                                capture_output=True,
                                check=False,
                            )
                            if result.returncode == 0:
                                copied = True
                                break
                        except FileNotFoundError:
                            continue
                elif sys.platform.startswith("cygwin"):
                    for candidate in (shutil.which("clip"), "clip"):
                        if not candidate:
                            continue
                        try:
                            result = subprocess.run(
                                [candidate],
                                input=text.encode("utf-8"),
                                capture_output=True,
                                check=False,
                            )
                            if result.returncode == 0:
                                copied = True
                                break
                        except FileNotFoundError:
                            continue
            logger.debug(f"Copy command succeeded: {copied}")
        except Exception as e:
            logger.error(f"Clipboard subprocess failed: {e}", exc_info=True)
            copied = False

        if not copied:
            self._set_copy_status("Copy failed. Select the text above and copy it manually.", "error")
            uno_utils.show_message_box("Copy",
                f"Could not access clipboard.\n\nPlease select and copy manually:\n{text}",
                "infobox", parent_frame=self.parent_frame, ctx=self.ctx)
        return copied

    def _build_support_snapshot(self, status_payload):
        """Build a compact support snapshot users can share in issues or forums."""
        import platform

        ds = status_payload or {}
        lines = [
            "TejOCR Setup Snapshot",
            "Summary: {summary}".format(summary=ds.get("summary") or "Unknown"),
            "Platform: {platform}".format(platform=platform.platform()),
            "LibreOffice Python: {path}".format(path=ds.get("lo_python_path_display") or "Unknown"),
            "pip: {status}".format(
                status=("available ({version})".format(version=ds.get("pip_version") or "version unknown")
                        if ds.get("pip_ok", False)
                        else "not detected")
            ),
            "Tesseract: {status}".format(
                status=("available ({version})".format(version=ds.get("tesseract_version") or "installed")
                        if ds.get("tesseract_ok", False)
                        else "missing")
            ),
            "Pillow: {status}".format(
                status=("installed ({version})".format(version=ds.get("pillow_version") or "installed")
                        if ds.get("pillow_ok", False)
                        else "missing")
            ),
            "pdf2image: {status}".format(
                status="installed" if ds.get("pdf2image_ok", False) else "missing"
            ),
            "PDF renderer: {status}".format(
                status=(ds.get("pdf_renderer_status") or "Unknown")
            ),
            "Compatibility extras: {status}".format(
                status=(ds.get("optional_compat_label") or "Unknown")
            ),
        ]

        commands = list(ds.get("setup_commands") or [])
        if commands:
            lines.append("")
            lines.append("Recommended commands:")
            lines.extend(" - {command}".format(command=command) for command in commands)

        next_steps = (ds.get("next_steps") or "").strip()
        if next_steps:
            lines.append("")
            lines.append("Guidance:")
            lines.append(next_steps)

        return "\n".join(lines).strip()

    def _open_install_guide(self):
        """Open the install guide in the default browser, with a copy fallback."""
        url = str(self._install_guide_url or "").strip()
        if not url:
            return False
        try:
            import webbrowser
            return bool(webbrowser.open(url))
        except Exception:
            logger.debug("Failed to open install guide URL.", exc_info=True)
            return False

    def _save_script_to_disk(self):
        """Export the current remediation commands to a shell/PowerShell script."""
        payload = (self._script_payload or "").strip()
        if not payload:
            return ""

        folder_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FolderPicker", self.ctx)
        if not folder_picker:
            raise RuntimeError("Folder picker is not available in this LibreOffice session.")

        try:
            folder_picker.setTitle("Choose a folder for the TejOCR setup script")
        except Exception:
            pass

        if folder_picker.execute() != uno_utils.OK_BUTTON:
            return ""

        selected_dir = folder_picker.getDirectory()
        target_dir = unohelper.fileUrlToSystemPath(selected_dir) if selected_dir else ""
        if not target_dir:
            return ""

        filename = self._script_filename or _default_setup_script_filename()
        output_path = os.path.join(target_dir, filename)
        with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        return output_path

    def disposing(self, event):
        pass


# --- Global Dialog Functions ---

def _get_lo_python_path():
    """Return a safe Python executable for runtime package install commands.

    This delegates to the hardened PDF/runtime resolver so the dialog layer never
    executes LibreOffice's `Contents/Resources/python` launcher script, which can
    be killed by macOS codesigning checks.
    """
    try:
        from tejocr import tejocr_pdf

        resolver = getattr(tejocr_pdf, "_resolve_python_executable", None)
        if callable(resolver):
            resolved = str(resolver() or "").strip()
            if resolved:
                return resolved
    except Exception:
        logger.debug("Falling back to generic python command for dialog pip helpers.", exc_info=True)

    return "python3"


def _build_pip_command(python_path):
    """Build a safe pip install command for the detected Python executable."""
    import shlex
    import os

    if not python_path:
        return "python3 -m pip install"
    base = os.path.basename(python_path).lower()
    if not (base == "python" or base.startswith("python") or "python" in base):
        return "python3 -m pip install"
    looks_like_windows = bool(re.match(r"^[A-Za-z]:\\", str(python_path or "")))
    if os.name == "nt" or looks_like_windows:
        if " " in python_path:
            return f'& "{python_path}" -m pip install'
        return f"& {python_path} -m pip install"
    try:
        return f"{shlex.quote(python_path)} -m pip install"
    except Exception:
        return f'"{python_path}" -m pip install' if " " in python_path else f"{python_path} -m pip install"


def _build_python_package_install_command(packages, python_path=None):
    """Return a runtime-specific package install command."""
    clean_packages = [str(package).strip() for package in (packages or []) if str(package).strip()]
    command = _build_pip_command(python_path or _get_lo_python_path())
    if clean_packages:
        command += " " + " ".join(clean_packages)
    return command


def _detect_pip_status(python_path=None):
    """Return whether pip is available in the active LibreOffice Python runtime."""
    python_path = python_path or _get_lo_python_path()
    available, version = _package_status("pip", "pip")
    if available:
        return {"available": True, "version": version, "path": python_path}
    try:
        from tejocr import tejocr_pdf

        checker = getattr(tejocr_pdf, "_is_python_with_pip", None)
        if callable(checker) and checker(python_path):
            return {"available": True, "version": "", "path": python_path}
    except Exception:
        logger.debug("pip runtime probe fallback failed.", exc_info=True)
    return {"available": False, "version": "", "path": python_path}


def _pip_bootstrap_commands_for_platform(python_path=None):
    """Return best-effort pip bootstrap commands for the active OS."""
    import platform

    python_path = python_path or _get_lo_python_path()
    system = (platform.system() or "").lower()
    if system == "windows":
        raw_python = str(python_path or "").strip()
        lo_dir = raw_python.replace("/", "\\").rsplit("\\", 1)[0] or r"C:\Program Files\LibreOffice\program"
        exe_name = raw_python.replace("\\", "/").split("/")[-1] or "python.exe"
        local_exe = ".\\{name}".format(name=exe_name)
        return [
            'cd "{path}"'.format(path=lo_dir),
            "(Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -UseBasicParsing).Content | {exe} -".format(
                exe=local_exe
            ),
        ]

    bootstrap_cmd = "{python} -m ensurepip --upgrade".format(
        python=_build_pip_command(python_path).rsplit(" -m pip install", 1)[0]
    )
    return [bootstrap_cmd]


def _default_setup_script_filename():
    import platform

    system = (platform.system() or "").lower()
    if system == "windows":
        return "tejocr-setup.ps1"
    return "tejocr-setup.sh"


def _build_setup_script_payload(commands):
    """Build an exportable setup script for the current platform."""
    import platform

    normalized_commands = []
    seen = set()
    for command in commands or []:
        clean = _normalize_command_for_copy(command)
        if not clean:
            clean = str(command or "").strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized_commands.append(clean)

    if not normalized_commands:
        return "", ""

    system = (platform.system() or "").lower()
    if system == "windows":
        lines = [
            "# TejOCR setup helper for LibreOffice PowerShell",
            "$ErrorActionPreference = 'Stop'",
            "",
        ]
        for command in normalized_commands:
            lines.append(command)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n", _default_setup_script_filename()

    lines = [
        "#!/usr/bin/env bash",
        "set -e",
        "",
        "# TejOCR setup helper for LibreOffice",
        "",
    ]
    for command in normalized_commands:
        lines.append(command)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", _default_setup_script_filename()


def _format_setup_steps(title, steps):
    """Format setup guidance as spaced step blocks for plain-text dialogs."""
    blocks = [str(title or "").strip()]
    step_no = 1
    for raw_title, raw_lines in steps or []:
        lines = [str(line).rstrip() for line in (raw_lines or []) if str(line or "").strip()]
        if not lines:
            continue
        heading = str(raw_title or "").strip()
        if heading:
            blocks.append("")
            blocks.append("{idx}. {heading}".format(idx=step_no, heading=heading))
        else:
            blocks.append("")
            blocks.append("{idx}.".format(idx=step_no))
        for line in lines:
            blocks.append("   {line}".format(line=line))
        step_no += 1
    return "\n".join(blocks).strip()


def _extract_pdf2image_command_from_text_v2(raw_command):
    """Extract a clean `python -m pip install pdf2image` command from mixed text."""
    if not raw_command:
        return ""
    if not isinstance(raw_command, str):
        return ""

    import re

    lo_python = _get_lo_python_path()
    fallback_command = _build_pip_command(lo_python)

    normalized = (
        (raw_command or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
        .replace("\u2007", " ")
        .replace("\u202f", " ")
    )
    lines = []
    for line in normalized.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\s•\-*]+", "", line)
        line = re.sub(r"^\d+[\.)]\s*", "", line)
        if (
            ("pdf2image" in line.lower() or "pdf image" in line.lower() or "pdfimage" in line.lower())
            and "install" in line.lower()
            and ":" in line
        ):
            line = line.split(":", 1)[1].strip()
        lines.append(line)

    flattened = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if not flattened:
        return ""

    flattened = re.sub(r"\bpdfimage\b", "pdf2image", flattened, flags=re.IGNORECASE)
    flattened = re.sub(r"\bpip\s+image\b", "pdf2image", flattened, flags=re.IGNORECASE)
    flattened = re.sub(r"pdf[ -]?image", "pdf2image", flattened, flags=re.IGNORECASE)
    flattened = flattened.replace("`", "").replace("“", "").replace("”", "")

    # Explicit parser for the common status format used in setup hints.
    explicit = re.search(
        r"Install\s+PDF\s+conversion\s+runtime\s+in\s+this\s+Python\s*:\s*(?P<cmd>.+?)\s*pdf2image",
        flattened,
        flags=re.IGNORECASE,
    )
    if explicit:
        explicit_cmd = (explicit.group("cmd") or "").strip()
        if explicit_cmd:
            return "{} pdf2image".format(explicit_cmd.strip().strip("\"'"))

    patterns = [
        r"(?:&\s+)?(?P<exe>(?:\"[^\"]+\"|'[^']+'|/[^\s\"']+|\bpython(?:3)?\b))\s+-m\s+pip\s+install\s+pdf2image\b",
        r"(?:&\s+)?(?P<exe>(?:\"[^\"]+\"|'[^']+'|/[^\s\"']+|\bpython(?:3)?\b))\s+pip\s+install\s+pdf2image\b",
        r"(?:&\s+)?(?P<exe>\"[^\"]+\"|'[^']+'|[^\s\"']+)\s+-m\s+pip\s+install\s+pdf2image",
        r"(?:&\s+)?(?P<exe>\"[^\"]+\"|'[^']+'|[^\s\"']+)\s+pip\s+install\s+pdf2image",
    ]
    for pattern in patterns:
        match = re.search(pattern, flattened, flags=re.IGNORECASE)
        if not match:
            continue
        exe = ""
        if match.groupdict():
            exe = (match.group("exe") or "").strip().strip('"\'')
        if not exe:
            exe = match.group(0)
        exe = exe.strip()
        if not exe:
            continue
        exe_lower = exe.lower()
        if exe_lower in {"pip", "python", "python3"}:
            return f"{fallback_command} pdf2image" if fallback_command else ""
        if "soffice" in exe.lower():
            return f"{fallback_command} pdf2image" if fallback_command else ""
        return f"{exe} -m pip install pdf2image"

    if "pdf2image" in flattened.lower() and "-m pip install" in flattened.lower() and fallback_command:
        return f"{fallback_command} pdf2image"

    return ""


def _extract_system_renderer_command(raw_hint):
    """Extract a direct PDF renderer install command from diagnostic hint text."""
    if not raw_hint or not isinstance(raw_hint, str):
        return ""

    import re

    lines = (
        raw_hint
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
        .replace("\u2007", " ")
        .replace("\u202f", " ")
    ).split("\n")

    manager_tokens = (
        "brew install",
        "apt-get install",
        "apt install",
        "dnf install",
        "yum install",
        "zypper install",
        "pacman -s",
        "choco install",
        "scoop install",
        "pkg install",
    )

    for line in lines:
        if not line:
            continue
        line = re.sub(r"^[\s•\-*]+\s*", "", line.strip())
        if not line:
            continue
        lower = line.lower()

        if lower.startswith("install pdf conversion runtime in this python:"):
            candidate = line.split(":", 1)[-1].strip()
            if candidate:
                return _normalize_command_for_copy(candidate)
            continue

        if not any(token in lower for token in ("pdf", "poppler", "mutool", "pdftoppm", "mupdf", "pdf2image")):
            continue
        if any(lower.startswith(token) for token in manager_tokens):
            return line

    return ""


def _collect_system_renderer_commands(raw_hints):
    """Collect unique renderer install commands from hints or status text."""
    import platform
    import re

    if isinstance(raw_hints, str):
        raw_lines = raw_hints.split("\n")
    elif isinstance(raw_hints, (list, tuple, set)):
        raw_lines = list(raw_hints)
    else:
        return []

    manager_tokens = {
        "brew install",
        "apt-get install",
        "apt install",
        "dnf install",
        "yum install",
        "zypper install",
        "pacman -s",
        "choco install",
        "scoop install",
        "pkg install",
    }

    normalized_system = (platform.system() or "").lower()
    preferred_prefix = ("brew install", "apt-get install", "apt install", "choco install", "scoop install")
    if normalized_system == "darwin":
        preferred_prefix = ("brew install",)
    elif normalized_system == "windows":
        preferred_prefix = ("choco install", "scoop install")
    elif normalized_system == "linux":
        preferred_prefix = ("apt-get install", "apt install")

    def _looks_like_command(line):
        if not line:
            return False
        l = line.lower()
        return any(l.startswith(prefix) for prefix in manager_tokens)

    all_candidates = []
    for raw_line in raw_lines:
        if not isinstance(raw_line, str):
            continue
        line = raw_line.strip()
        line = re.sub(r"^\s*[\d]+[.)]\s*", "", line)
        line = line.strip().strip("• ").strip("- ")
        if not line:
            continue
        if "pdf conversion runtime in this python" in line.lower():
            continue
        if _looks_like_command(line):
            all_candidates.append(line)

    def _dedupe(items):
        seen = set()
        out = []
        for item in items:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    all_candidates = _dedupe(all_candidates)
    if not all_candidates:
        return []

    def _rank(item):
        lowered = item.lower()
        for idx, prefix in enumerate(preferred_prefix):
            if lowered.startswith(prefix):
                return idx
        return len(preferred_prefix) + 10

    # Keep UI output focused on OS-relevant package-manager commands.
    preferred_candidates = []
    for item in all_candidates:
        lowered = item.lower()
        if any(lowered.startswith(prefix) for prefix in preferred_prefix):
            preferred_candidates.append(item)
    if preferred_candidates:
        all_candidates = _dedupe(preferred_candidates)
        all_candidates = sorted(all_candidates, key=_rank)
        return all_candidates

    return sorted(all_candidates, key=_rank)


def _renderer_install_hints_for_platform():
    """Return OS-specific renderer system package install commands."""
    import platform

    normalized_system = (platform.system() or "").lower()
    if normalized_system == "darwin":
        return ["brew install poppler", "brew install mupdf"]
    if normalized_system == "windows":
        return ["choco install poppler", "scoop install poppler"]
    if normalized_system == "linux":
        return ["apt-get install poppler-utils", "apt-get install mupdf-tools"]
    return ["brew install poppler", "apt-get install poppler-utils"]


def _tesseract_install_commands_for_platform():
    """Return OS-specific install commands for Tesseract itself."""
    import platform

    normalized_system = (platform.system() or "").lower()
    if normalized_system == "darwin":
        return ["brew install tesseract", "brew install tesseract-lang"]
    if normalized_system == "windows":
        return ["choco install tesseract"]
    if normalized_system == "linux":
        return ["sudo apt install tesseract-ocr tesseract-ocr-eng"]
    return ["brew install tesseract", "sudo apt install tesseract-ocr tesseract-ocr-eng"]


def _refresh_dependency_import_state():
    """Refresh import state so in-session installs are visible without restarting."""
    try:
        import importlib
        importlib.invalidate_caches()
    except Exception:
        pass

    site_dirs = []
    try:
        site_dirs.extend(site.getsitepackages() or [])
    except Exception:
        pass
    try:
        user_site = site.getusersitepackages()
        if user_site:
            site_dirs.append(user_site)
    except Exception:
        pass

    seen = set()
    for candidate in site_dirs:
        clean = os.path.abspath(os.path.expanduser(str(candidate or "").strip()))
        if not clean or clean in seen or not os.path.isdir(clean):
            continue
        seen.add(clean)
        try:
            site.addsitedir(clean)
        except Exception:
            if clean not in sys.path:
                sys.path.append(clean)


def _runtime_binary_search_paths():
    """Paths checked when probing for PDF rendering binaries in runtime sessions."""
    return (
        "/opt/homebrew/bin",
        "/opt/homebrew/opt/poppler/bin",
        "/opt/homebrew/opt/poppler/bin",
        "/opt/homebrew/opt/mupdf/bin",
        "/opt/homebrew/opt/",
        "/usr/local/bin",
        "/usr/local/opt/poppler/bin",
        "/usr/local/opt/poppler/bin",
        "/usr/local/opt/mupdf/bin",
        "/usr/local/opt/",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    )


def _find_runtime_binary(binary_name):
    """Find a runtime binary path by PATH and common fallback locations."""
    if not binary_name:
        return None

    import shutil
    import glob

    found = shutil.which(binary_name)
    if found:
        return found

    for root in _runtime_binary_search_paths():
        candidate = os.path.join(root, binary_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    for pattern in (
        "/opt/homebrew/Cellar/*/bin",
        "/opt/homebrew/Cellar/*/*/bin",
        "/opt/homebrew/opt/*/bin",
        "/opt/homebrew/opt/*/*/bin",
        "/usr/local/Cellar/*/bin",
        "/usr/local/opt/*/bin",
        "/usr/local/opt/*/*/bin",
        "/opt/homebrew/Caskroom/*/*/bin",
        "/usr/local/Caskroom/*/*/bin",
    ):
        for candidate_root in glob.glob(pattern):
            candidate = os.path.join(candidate_root, binary_name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

    return None


def _detect_pdf_renderer_binary():
    """Probe for pdf renderer engines directly from the active runtime."""
    try:
        from tejocr import tejocr_pdf

        pdf_status = tejocr_pdf.get_pdf_renderer_status()
        if isinstance(pdf_status, dict):
            if bool(pdf_status.get("available")):
                engine = (pdf_status.get("engine") or "").strip() or "pdf_renderer"
                return True, engine
            # Keep current behavior when poppler binary is missing.
            if pdf_status.get("engine"):
                return True, str(pdf_status.get("engine"))
    except Exception:
        logger.debug("PDF runtime check fallback to direct binary probe.", exc_info=True)

    for binary_name, engine_name in (
        ("pdftoppm", "pdftoppm"),
        ("mutool", "mutool"),
    ):
        if _find_runtime_binary(binary_name):
            return True, engine_name
    return False, ""


def _resolve_pdf_install_command(status_payload):
    """Resolve the best available PDF-related install command from diagnostics payload."""
    if not isinstance(status_payload, dict):
        return _build_pip_command(_get_lo_python_path()) + " pdf2image"

    ds = status_payload
    status_error = (ds.get("pdf_renderer_error") or "").lower()

    raw_command = ds.get("pdf2image_install_command", "")
    clean = _normalize_command_for_copy(raw_command)
    if clean and not (
        "pdf2image is installed, but poppler utilities are not available" in status_error
    ):
        return clean

    if not ds.get("pdf_renderer_available", False):
        renderer_commands = _collect_system_renderer_commands(
            ds.get("pdf_renderer_hints") or ds.get("next_steps")
        )
        if renderer_commands:
            return renderer_commands[0]

        next_steps = ds.get("next_steps", "")
        if isinstance(next_steps, str):
            renderer_commands = _collect_system_renderer_commands(next_steps)
            if renderer_commands:
                return renderer_commands[0]

    for hint in (ds.get("pdf_renderer_hints") or []):
        if not isinstance(hint, str):
            continue
        candidate = _extract_pdf2image_command_from_text(hint)
        if candidate:
            return candidate

    next_steps = ds.get("next_steps", "")
    if isinstance(next_steps, str):
        candidate = _extract_pdf2image_command_from_text(next_steps)
        if candidate:
            return candidate

    candidate = _normalize_command_for_copy(" ".join(ds.get("pdf_renderer_hints") or []))
    if candidate:
        return candidate

    fallback = _build_pip_command(_get_lo_python_path())
    if ds.get("pdf_renderer_available", False):
        return ""
    return f"{fallback} pdf2image" if fallback else "python3 -m pip install pdf2image"


def _normalize_command_for_copy(raw_command):
    """Keep only a single executable line suitable for copying."""
    if not raw_command or not isinstance(raw_command, str):
        return ""

    candidate = _extract_pdf2image_command_from_text_v2(raw_command)
    if candidate:
        return candidate

    import re

    normalized = (
        raw_command
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
        .replace("\u2007", " ")
        .replace("\u202f", " ")
    )
    lines = [re.sub(r"^[\s•\-*]+\s*", "", line).strip() for line in normalized.split("\n")]
    for line in lines:
        if not line:
            continue
        lower = line.lower()
        if "install pdf conversion runtime in this python:" in lower:
            candidate = line.split(":", 1)[-1].strip()
            if candidate:
                return candidate
        if any(lower.startswith(token) for token in (
            "brew install",
            "apt-get install",
            "apt install",
            "dnf install",
            "yum install",
            "zypper install",
            "pacman -s",
            "choco install",
            "scoop install",
            "pkg install",
        )):
            return line
        if " pdf2image" in lower and "pip install" in lower and "-m" in lower:
            return line
    return ""


def _extract_pdf2image_command_from_text(text):
    """Fallback extraction of the PDF install command from explanatory text."""
    return _extract_pdf2image_command_from_text_v2(text)

def _check_dependencies():
    """Check status of all OCR dependencies and provide user guidance."""
    import platform

    _refresh_dependency_import_state()

    pip_python = _get_lo_python_path()
    pip_cmd = _build_pip_command(pip_python)
    pip_status = _detect_pip_status(pip_python)
    pdf2image_install_command = f"{pip_cmd} pdf2image"

    status = {
        'summary': '',
        'tesseract': '',
        'python_packages': '',
        'installation_guide': '',
        'next_steps': '',
        'pdf2image_install_command': pdf2image_install_command,
        'pdf_renderer_available': False,
        'pdf_renderer_engine': None,
        'pdf_renderer_hints': [],
        'pdf_renderer_status': '',
        'pdf_renderer_error': '',
        'python_missing_packages': [],
        'python_install_command': '',
        'python_install_commands': [],
        'tesseract_install_commands': [],
        'pip_bootstrap_commands': [],
        'setup_commands': [],
        'lo_python_path': pip_python,
        'lo_python_path_display': pip_python or "python3",
        'lo_python_path_resolved': bool(pip_python and pip_python != "python3"),
        'pip_ok': pip_status["available"],
        'pip_version': pip_status["version"],
        'required_python_packages': [],
        'optional_missing_packages': [],
        'optional_compat_ready': False,
        'optional_compat_label': "",
        'pdf2image_ok': False,
        'pillow_version': '',
        'tesseract_version': '',
        'tesseract_path_label': '',
    }

    def _default_pdf_hints(pip_cmd):
        """Build OS-aware renderer installation guidance with LO-python pip command."""
        os_hints = _renderer_install_hints_for_platform()
        if not os_hints:
            os_hints = ["Please install a PDF renderer (poppler or MuPDF)"]
        return os_hints + [f"Install PDF conversion runtime in this Python: {pip_cmd} pdf2image"]

    def _status_from_pdf_renderer(renderer_status, pip_cmd):
        if not isinstance(renderer_status, dict):
            return {
                "available": False,
                "engine": None,
                "hints": _default_pdf_hints(pip_cmd),
                "status": "PDF Renderer: Not found",
                "error": str(renderer_status),
            }

        available = bool(renderer_status.get("available"))
        engine = (renderer_status.get("engine") or "").strip()
        raw_hints = renderer_status.get("hints")
        hints = _collect_system_renderer_commands(raw_hints)
        if not hints:
            hints = [hint for hint in (raw_hints or _default_pdf_hints(pip_cmd))
                     if isinstance(hint, str) and hint.strip()]
            if not hints:
                hints = _default_pdf_hints(pip_cmd)
        status_error = (renderer_status.get("error") or "").strip()
        if available:
            if engine:
                status_text = f"PDF Renderer: Available ({engine})"
            else:
                status_text = "PDF Renderer: Available"
            error_text = ""
        else:
            if status_error:
                status_text = "PDF Renderer: Not found"
            else:
                status_text = "PDF Renderer: Not found"
            error_text = status_error or "No PDF renderer detected for PDF OCR"
        return {
            "available": available,
            "engine": engine,
            "hints": hints,
            "status": status_text,
            "error": error_text,
        }

    # PDF renderer check (for OCRing PDF files from file mode)
    pdf_renderer_status = {"available": False, "engine": None, "hints": []}
    try:
        from tejocr import tejocr_pdf as pdf_module
        pdf_renderer_status = pdf_module.get_pdf_renderer_status()
    except Exception as pdf_error:
        pdf_renderer_status = {
            "available": False,
            "engine": None,
            "hints": _default_pdf_hints(pip_cmd),
            "status": "PDF renderer check failed",
            "error": str(pdf_error),
        }

    pdf_status = _status_from_pdf_renderer(pdf_renderer_status, pip_cmd)
    status.update({
        'pdf_renderer_available': pdf_status["available"],
        'pdf_renderer_engine': pdf_status["engine"],
        'pdf_renderer_hints': pdf_status["hints"],
        'pdf_renderer_status': pdf_status["status"],
        'pdf_renderer_error': pdf_status["error"],
    })
    
    # Check Tesseract
    tesseract_status = "NOT FOUND"
    tesseract_path = "Not detected"
    tesseract_ok = False
    tesseract_commands = ['tesseract']
    configured_ctx = None
    configured_path = ""
    try:
        import uno
        configured_ctx = uno.getComponentContext()
        configured_path = uno_utils.get_setting(
            constants.CFG_KEY_TESSERACT_PATH,
            "",
            configured_ctx
        ).strip()
        if configured_path and configured_path not in tesseract_commands:
            tesseract_commands.insert(0, configured_path)
    except Exception:
        configured_path = ""

    for command in tesseract_commands:
        try:
            result = subprocess.run([command, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip().split()[1] if result.stdout.strip().split() else "Unknown"
                tesseract_status = f"Installed (v{version})"
                tesseract_ok = True
                if command == configured_path:
                    tesseract_path = configured_path
                else:
                    tesseract_path = "Available in system PATH"
                break
        except Exception:
            continue

    status['tesseract'] = f"Status: {tesseract_status}\nPath: {tesseract_path}"
    status['tesseract_version'] = tesseract_status.replace("Installed ", "").strip() if tesseract_ok else ""
    status['tesseract_path_label'] = tesseract_path

    python_packages = []
    pillow_available, pillow_version = _package_status("PIL", "Pillow")
    pdf2image_available, pdf2image_version = _package_status("pdf2image", "pdf2image")
    pytesseract_available, pytesseract_version = _package_status("pytesseract", "pytesseract")
    numpy_available, numpy_version = _package_status("numpy", "numpy")

    python_packages.append("LibreOffice Python: {path}".format(path=status['lo_python_path_display']))
    if pip_status["available"]:
        python_packages.append(
            "pip: {version} (OK)".format(version=pip_status["version"] or "available")
        )
    else:
        python_packages.append("pip: Not found in LibreOffice Python")

    if pillow_available:
        python_packages.append(
            "Pillow: {version} (recommended preprocessing; OK)".format(
                version=pillow_version or "installed"
            )
        )
    else:
        python_packages.append("Pillow: Not found (core OCR still works; preprocessing is reduced)")

    if pdf2image_available:
        python_packages.append(
            "pdf2image: {version} (optional PDF fallback; OK)".format(
                version=pdf2image_version or "installed"
            )
        )
    else:
        python_packages.append("pdf2image: Not found (optional PDF fallback)")

    python_packages.append(
        "Compatibility extras: pytesseract={pt} | numpy={np}".format(
            pt=(pytesseract_version or "installed") if pytesseract_available else "not installed",
            np=(numpy_version or "installed") if numpy_available else "not installed",
        )
    )

    status['python_packages'] = '\n'.join(python_packages)
    status['tesseract_ok'] = tesseract_ok
    status['numpy_ok'] = numpy_available
    status['pytesseract_ok'] = pytesseract_available
    status['pillow_ok'] = pillow_available
    status['pillow_version'] = pillow_version or ""
    status['pdf2image_ok'] = pdf2image_available

    logger.debug(
        "Dependency check: tesseract_ok=%s, pip_ok=%s, pillow_available=%s, pdf2image_available=%s, pytesseract_available=%s, numpy_available=%s",
        tesseract_ok,
        pip_status["available"],
        pillow_available,
        pdf2image_available,
        pytesseract_available,
        numpy_available,
    )

    required_python_packages = []
    recommended_python_packages = []
    optional_python_packages = []

    if not pillow_available:
        recommended_python_packages.append("pillow")
    if not pdf2image_available:
        optional_python_packages.append("pdf2image")
    if not pytesseract_available:
        optional_python_packages.append("pytesseract")
    if not numpy_available:
        optional_python_packages.append("numpy")

    python_install_commands = []
    if pip_status["available"]:
        if recommended_python_packages:
            python_install_commands.append(
                _build_python_package_install_command(recommended_python_packages, pip_python)
            )
    else:
        status['pip_bootstrap_commands'] = _pip_bootstrap_commands_for_platform(pip_python)

    tesseract_install_commands = [] if tesseract_ok else _tesseract_install_commands_for_platform()
    setup_commands = []
    seen_commands = set()

    def _add_setup_command(command):
        clean = _normalize_command_for_copy(command)
        if not clean:
            clean = str(command or "").strip()
        if not clean:
            return
        key = clean.lower()
        if key in seen_commands:
            return
        seen_commands.add(key)
        setup_commands.append(clean)

    for command in tesseract_install_commands:
        _add_setup_command(command)
    for command in status['pip_bootstrap_commands']:
        _add_setup_command(command)
    for command in python_install_commands:
        _add_setup_command(command)

    core_ready = tesseract_ok
    pdf_renderer_ready = bool(pdf_status.get("available"))
    if core_ready and pdf_renderer_ready:
        status['summary'] = "Image + PDF OCR ready."
        status['next_steps'] = (
            "✅ Image OCR and PDF OCR are ready in this LibreOffice session.\n"
            "Optional extras such as Pillow preprocessing and compatibility packages can still be installed later."
        )
    elif core_ready and not pdf_renderer_ready:
        status['summary'] = "Image OCR ready; PDF OCR still needs runtime support."
        status['next_steps'] = (
            "✅ Image OCR is ready now.\n"
            "⚠ PDF OCR still needs a renderer toolchain (Poppler or MuPDF) and may also use pdf2image as a compatibility fallback."
        )
    else:
        status['summary'] = "Setup required: Tesseract OCR is missing."
        quick_steps = ["⚠️ Action Required: OCR Engine not found."]
        quick_steps.append("\nRun the commands below in your system Terminal:")
        if tesseract_install_commands:
            quick_steps.append("1. Install Tesseract OCR Database:")
            quick_steps.extend("   {cmd}".format(cmd=cmd) for cmd in tesseract_install_commands)
        if status['pip_bootstrap_commands']:
            quick_steps.append("\n2. Bootstrap pip in LibreOffice Python (if needed):")
            quick_steps.extend("   {cmd}".format(cmd=cmd) for cmd in status['pip_bootstrap_commands'])
        if python_install_commands:
            quick_steps.append("\n3. Install recommended LibreOffice Python extras:")
            quick_steps.extend("   {cmd}".format(cmd=cmd) for cmd in python_install_commands)
        quick_steps.append("\nRestart LibreOffice after installations or use Validate / Refresh in this dialog.")
        status['next_steps'] = "\n".join(quick_steps)

    if not pdf_status["available"]:
        missing_pdf_message = "Optional: To enable PDF processing, install a renderer:"
        pdf_renderer_commands = _collect_system_renderer_commands(
            pdf_status.get("hints") or _default_pdf_hints(pip_cmd)
        )
        if not pdf_renderer_commands:
            pdf_renderer_commands = _collect_system_renderer_commands(
                _default_pdf_hints(pip_cmd)
            )
        pdf_hints_formatted = "\n".join(
            "  - {cmd}".format(cmd=entry) for entry in pdf_renderer_commands
        )
        existing_steps = (status['next_steps'] or "").strip()
        
        # Adjust messaging flow so it's clean and doesn't conflict
        if existing_steps and "Optional PDF renderer missing" not in existing_steps and "All dependencies installed" not in existing_steps:
             status['next_steps'] = "{existing}\n\n{missing}\n{hints}".format(
                existing=existing_steps,
                missing=missing_pdf_message,
                hints=pdf_hints_formatted,
            )
        elif "All dependencies installed" not in existing_steps:
             status['next_steps'] = "{existing}\n{hints}".format(
                existing=existing_steps,
                hints=pdf_hints_formatted,
            )
            
        if pdf_status.get("error"):
            status['next_steps'] += "\n\nCurrent check data: {error}".format(error=pdf_status["error"])
        for command in pdf_renderer_commands:
            _add_setup_command(command)

    if not pdf_renderer_ready and pip_status["available"] and not pdf2image_available:
        pdf2image_command = _build_python_package_install_command(["pdf2image"], pip_python)
        if pdf2image_command not in python_install_commands:
            python_install_commands.append(pdf2image_command)
            _add_setup_command(pdf2image_command)

    compatibility_missing = [pkg for pkg in ("pytesseract", "numpy") if pkg in optional_python_packages]
    if compatibility_missing and pip_status["available"]:
        compatibility_command = _build_python_package_install_command(compatibility_missing, pip_python)
        python_install_commands.append(compatibility_command)

    status['python_missing_packages'] = list(required_python_packages + recommended_python_packages)
    status['required_python_packages'] = list(required_python_packages)
    status['optional_missing_packages'] = list(optional_python_packages)
    status['python_install_command'] = python_install_commands[0] if python_install_commands else ""
    status['python_install_commands'] = list(dict.fromkeys(python_install_commands))
    status['tesseract_install_commands'] = list(tesseract_install_commands)
    status['setup_commands'] = list(setup_commands)

    status['optional_compat_ready'] = not compatibility_missing
    if compatibility_missing:
        status['optional_compat_label'] = "⚠ Compatibility extras (optional): missing {items}".format(
            items=", ".join(compatibility_missing)
        )
    else:
        status['optional_compat_label'] = "✅ Compatibility extras (optional): pytesseract and numpy available"

    system = platform.system().lower()

    if system == "darwin":
        status['installation_guide'] = _format_setup_steps(
            "macOS Reference",
            [
                ("LibreOffice Python used by TejOCR", [
                    "Path:",
                    "{python}".format(python=status['lo_python_path_display']),
                ]),
                ("Core OCR", [
                    "Command:",
                    "brew install tesseract tesseract-lang",
                ]),
                ("Recommended preprocessing", [
                    "Command:",
                    "{pillow}".format(
                        pillow=_build_python_package_install_command(["pillow"], pip_python)
                    ),
                ]),
                ("PDF OCR (optional)", [
                    "Command:",
                    "brew install poppler",
                ]),
                ("PDF Python fallback (optional)", [
                    "Command:",
                    "{pdf2image}".format(
                        pdf2image=_build_python_package_install_command(["pdf2image"], pip_python)
                    ),
                ]),
                ("If pip is missing", [
                    "Command:",
                    "{ensurepip}".format(
                        ensurepip=status['pip_bootstrap_commands'][0] if status['pip_bootstrap_commands'] else "pip already available"
                    ),
                ]),
            ],
        )
    elif system == "linux":
        status['installation_guide'] = _format_setup_steps(
            "Linux Reference",
            [
                ("LibreOffice Python used by TejOCR", [
                    "Path:",
                    "{python}".format(python=status['lo_python_path_display']),
                ]),
                ("Core OCR", [
                    "Command:",
                    "sudo apt install tesseract-ocr tesseract-ocr-all",
                ]),
                ("Recommended preprocessing", [
                    "Command:",
                    "{pillow}".format(
                        pillow=_build_python_package_install_command(["pillow"], pip_python)
                    ),
                ]),
                ("PDF OCR (optional)", [
                    "Command:",
                    "sudo apt install poppler-utils mupdf-tools",
                ]),
                ("PDF Python fallback (optional)", [
                    "Command:",
                    "{pdf2image}".format(
                        pdf2image=_build_python_package_install_command(["pdf2image"], pip_python)
                    ),
                ]),
            ],
        )
    elif system == "windows":
        windows_bootstrap = status['pip_bootstrap_commands']
        bootstrap_lines = list(windows_bootstrap) if windows_bootstrap else ["pip already available in LibreOffice Python"]
        status['installation_guide'] = _format_setup_steps(
            "Windows Reference (PowerShell)",
            [
                ("LibreOffice Python used by TejOCR", [
                    "Path:",
                    "{python}".format(python=status['lo_python_path_display']),
                ]),
                ("Core OCR", [
                    "Install Tesseract from UB-Mannheim or use:",
                    "choco install tesseract",
                ]),
                ("If pip is missing in LibreOffice Python", bootstrap_lines),
                ("Recommended preprocessing", [
                    "Command:",
                    "{pillow}".format(
                        pillow=_build_python_package_install_command(["pillow"], pip_python)
                    ),
                ]),
                ("PDF OCR (optional)", [
                    "Install Poppler, then run:",
                    "{pdf2image}".format(
                        pdf2image=_build_python_package_install_command(["pdf2image"], pip_python)
                    ),
                ]),
                ("Compatibility extras only if needed", [
                    "Command:",
                    "{compat}".format(
                        compat=_build_python_package_install_command(["numpy", "pytesseract"], pip_python)
                    ),
                ]),
            ],
        )
    else:
        status['installation_guide'] = _format_setup_steps(
            "Reference",
            [
                ("Core OCR", [
                    "Install Tesseract for your OS.",
                ]),
                ("LibreOffice Python used by TejOCR", [
                    "Path:",
                    "{python}".format(python=status['lo_python_path_display']),
                ]),
                ("Recommended preprocessing", [
                    "Command:",
                    "{pillow}".format(
                        pillow=_build_python_package_install_command(["pillow"], pip_python)
                    ),
                ]),
                ("PDF Python fallback (optional)", [
                    "Command:",
                    "{pdf2image}".format(
                        pdf2image=_build_python_package_install_command(["pdf2image"], pip_python)
                    ),
                ]),
            ],
        )

    return status

def show_ocr_options_dialog(ctx, parent_frame, ocr_source_type, image_path=None):
    """Fallback OCR options hint shown when full dialogs are not available."""
    try:
        if ocr_source_type == "selected":
            message = f"{constants.EXTENSION_FULL_NAME} - OCR Selected Image\n\nProcessing selected image OCR.\n\nThe full OCR options dialog is not available in this runtime.\nClick OK to continue with stored defaults."
        elif ocr_source_type == "file":
            message = f"{constants.EXTENSION_FULL_NAME} - OCR Image/PDF from File\n\nProcessing file-based OCR.\n\nYou can OCR image files and PDFs in this mode.\nClick OK to continue with stored defaults."
        else:
            message = f"{constants.EXTENSION_FULL_NAME} - {ocr_source_type}\n\nFallback OCR mode is active.\nFeature dialogs are currently unavailable."

        logger.info(f"OCR dialog message displayed: {ocr_source_type}")
        
        # Try ultra-basic message box without complex constants
        try:
            import uno
            if ctx is None:
                ctx = uno.getComponentContext()
            
            service_manager = ctx.getServiceManager()
            toolkit = uno_utils.create_instance("com.sun.star.awt.Toolkit", ctx)
            
            if toolkit:
                # Robust message box creation with multiple fallback methods
                parent_peer = None
                
                # Method 1: Try parent_frame if provided
                if parent_frame:
                    try:
                        container_window = parent_frame.getContainerWindow()
                        if container_window:
                            parent_peer = container_window.getPeer()
                            logger.debug("Got parent_peer from provided parent_frame")
                    except Exception as e1:
                        logger.debug(f"Method 1 failed: {e1}")
                
                # Method 2: Try desktop's current frame
                if not parent_peer:
                    try:
                        desktop = uno_utils.create_instance("com.sun.star.frame.Desktop", ctx)
                        if desktop:
                            current_frame = desktop.getCurrentFrame()
                            if current_frame:
                                container_window = current_frame.getContainerWindow()
                                if container_window:
                                    parent_peer = container_window.getPeer()
                                    logger.debug("Got parent_peer from desktop current frame")
                    except Exception as e2:
                        logger.debug(f"Method 2 failed: {e2}")
                
                # Method 3: Try toolkit's desktop window as fallback
                if not parent_peer:
                    try:
                        desktop_window = toolkit.getDesktopWindow()
                        if desktop_window:
                            parent_peer = desktop_window
                            logger.debug("Got parent_peer from toolkit desktop window")
                    except Exception as e3:
                        logger.debug(f"Method 3 failed: {e3}")
                
                # Create message box (works even with None parent in many cases)
                try:
                    msg_type = 1  # Info type
                    buttons = 1   # OK button
                    
                    box = toolkit.createMessageBox(parent_peer, msg_type, buttons, f"{constants.EXTENSION_FULL_NAME}", message)
                    if box:
                        try:
                            result = box.execute()
                            logger.info(f"UI Message box displayed successfully! Result: {result}")
                            return 1, None  # Success - UI was shown!
                        except Exception as exec_error:
                            logger.debug(f"Message box execute failed: {exec_error}")
                    else:
                        logger.debug("createMessageBox returned None")
                        
                except Exception as box_error:
                    logger.debug(f"Message box creation failed: {box_error}")
                    
        except Exception as e:
            logger.debug(f"UNO message box attempt failed generally: {e}. Console output remains primary.")
        
        return 1, None  # Simple success return
        
    except Exception as e:
        logger.error(f"Error in show_ocr_options_dialog: {e}")
        return None, None


def show_ocr_complete_dialog(ctx, parent_frame, summary_text, sources_text, profile_text, runtime_text):
    """Show the structured OCR completion dialog. Returns True when displayed."""
    dialog_handler = None
    try:
        dialog_handler = TejOCRCompleteDialogHandler(
            ctx,
            parent_frame=parent_frame,
            summary_text=summary_text,
            sources_text=sources_text,
            profile_text=profile_text,
            runtime_text=runtime_text,
        )
        return dialog_handler.show()
    except Exception as e:
        logger.error(f"show_ocr_complete_dialog failed: {e}", exc_info=True)
        return False
    finally:
        if dialog_handler is not None:
            dialog_handler.dispose()


def show_settings_dialog(ctx, parent_frame):
    """Show the full settings XDL dialog and show a clear error if it fails."""
    settings_handler = None
    try:
        settings_handler = SettingsDialogHandler(ctx)
        if settings_handler._create_dialog(parent_frame):
            logger.info(
                "Settings dialog path: XDL backend succeeded. "
                f"Dialog URL: {settings_handler._last_successful_dialog_url}"
            )
            return settings_handler.execute()

        # XDL-based settings failed. Fall back to pure-UNO interactive UI instead of blocking users.
        logger.warning(
            "Settings dialog path: XDL backend failed after attempts. "
            f"Attempts: {settings_handler._last_dialog_creation_errors}"
        )
        fallback_result = _show_interactive_settings_fallback(ctx, parent_frame)
        if fallback_result:
            logger.info("Settings dialog path: interactive fallback saved settings.")
            return True
        if fallback_result is False:
            # False can mean either explicit cancel or fallback failure. Keep UX simple and avoid false-negative errors.
            logger.info(
                "Settings dialog path: interactive fallback returned without a successful save "
                "(user cancelled or no changes)."
            )
            return False

        failure_reason = settings_handler._last_dialog_creation_error
        if not failure_reason and getattr(settings_handler, "_last_dialog_creation_errors", None):
            failure_reason = settings_handler._last_dialog_creation_errors

        logger.warning(
            "Settings dialogs could not be created from any configured URL."
        )
        message = _build_settings_unavailable_message(
            _("Could not create settings dialog. {error}").format(error=failure_reason)
        )
        try:
            if ctx is not None:
                uno_utils.show_message_box(
                    _("Settings Unavailable"),
                    message,
                    "errorbox",
                    parent_frame=parent_frame,
                    ctx=ctx,
                )
            else:
                logger.debug(message)
        except Exception:
            logger.debug("Could not display settings unavailable dialog. Falling back to console output.")
        return False
    except Exception as e:
        logger.error(f"show_settings_dialog failed: {e}", exc_info=True)
        message = _build_settings_unavailable_message(
            _("Failed to open Settings UI: {error}").format(error=e)
        )
        if ctx is not None:
            try:
                uno_utils.show_message_box(
                    _("Settings Error"),
                    message,
                    "errorbox",
                    parent_frame=parent_frame,
                    ctx=ctx,
                )
            except Exception:
                logger.debug(message)
        else:
            logger.debug(message)
        return False
    finally:
        if settings_handler is not None:
            settings_handler.dispose()

def _show_tesseract_check_dialog(ctx, parent_frame, toolkit, parent_peer):
    """Show Tesseract installation check dialog."""
    try:
        import subprocess
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_info = result.stdout.strip().split('\n')[0] if result.stdout.strip() else "Version info unavailable"
            message = f"✓ Tesseract Found!\n\n{version_info}\n\nTesseract is properly installed and accessible."
            title = "Tesseract Check - SUCCESS"
            msg_type = 1  # Info box
        else:
            message = f"✗ Tesseract Error\n\nReturn code: {result.returncode}\nError: {result.stderr[:200] if result.stderr else 'Unknown error'}\n\nPlease check your Tesseract installation."
            title = "Tesseract Check - ERROR"
            msg_type = 2  # Warning box
    except FileNotFoundError:
        message = "✗ Tesseract Not Found\n\nTesseract is not installed or not in PATH.\n\nInstall with: brew install tesseract"
        title = "Tesseract Check - NOT FOUND"
        msg_type = 2  # Warning box
    except Exception as e:
        message = f"✗ Check Failed\n\nError checking Tesseract: {str(e)[:200]}\n\nPlease verify your installation manually."
        title = "Tesseract Check - ERROR"
        msg_type = 2  # Warning box
    
    try:
        box = toolkit.createMessageBox(parent_peer, msg_type, 1, title, message)  # 1 = OK button
        if box:
            box.execute()
    except Exception as dialog_error:
        logger.warning(f"Could not show Tesseract check dialog: {dialog_error}")
        logger.debug(f"TESSERACT CHECK: {message}")

def _show_installation_help_dialog(ctx, parent_frame, toolkit, parent_peer):
    """Show installation help dialog."""
    pip_python = _get_lo_python_path()
    pip_cmd = _build_pip_command(pip_python)
    help_text = f"""Installation Help - {constants.EXTENSION_FULL_NAME}

QUICK SETUP (macOS):

1. Install Tesseract:
   brew install tesseract

2. Install extra languages (optional):
   brew install tesseract-lang

3. Install recommended preprocessing package:
   {pip_cmd} pillow

4. Optional compatibility extras:
   {pip_cmd} numpy pytesseract

5. Restart LibreOffice

OTHER PLATFORMS:
• Linux: sudo apt install tesseract-ocr tesseract-ocr-all
• Windows: Download from github.com/UB-Mannheim/tesseract/wiki
  (select languages during install)

VERIFICATION:
• Open Terminal
• Run: tesseract --version
• Should show version 5.x or higher

TROUBLESHOOTING:
• Ensure Homebrew is installed (macOS)
• Check packages in LibreOffice Python
• Restart LibreOffice after installation

Need more help? Check the extension documentation."""

    try:
        box = toolkit.createMessageBox(parent_peer, 1, 1, "Installation Help", help_text)  # 1 = Info, 1 = OK
        if box:
            box.execute()
    except Exception as dialog_error:
        logger.warning(f"Could not show installation help dialog: {dialog_error}")
        logger.debug(f"INSTALLATION HELP:\n{help_text}")


if __name__ == "__main__":
    # This module is intended to be loaded by LibreOffice. No-op main entry.
    pass
