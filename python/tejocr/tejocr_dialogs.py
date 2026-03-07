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
                description = "{description} Diagnostic mode; no OCR text output.".format(
                    description=description.rstrip(".")
                )
            elif mode == "2" and "diagnostic mode" not in description.lower():
                description = "{description} Diagnostic mode; not implemented for text output.".format(
                    description=description.rstrip(".")
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
    def __init__(self, ctx):
        # Use extension URL scheme that LibreOffice recognizes for extension XDL files
        dialog_url = "vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/tejocr_settings_dialog_full.xdl"
        super().__init__(ctx, dialog_url)
        self.initial_settings = {} # To store settings when dialog opens to check for changes
        self.available_languages_map_settings = {} # Separate map for settings dialog
        self.dependency_status = None # Cache dependency check results
        self._settings_languages_cache = {}
        self._output_mode_code_order = []
        self._all_lang_keys = []
        self._all_lang_map = {}
        self._visible_lang_keys = []
        self._selected_codes = {constants.DEFAULT_OCR_LANGUAGE}

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

        # Force dropdown controls into compact mode across LO builds
        self._ensure_dropdown_mode("DefaultPresetDropdown")
        self._ensure_dropdown_mode("DefaultPSMDropdown")
        self._ensure_dropdown_mode("DefaultOEMDropdown")

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
                
            # Removed the listbox background override to preserve native dark mode contrast.
                
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
            
            # Tesseract status
            tess_ok = self.dependency_status.get('tesseract_ok', False)
            if tess_ok:
                self._set_label("TesseractStatusLabel",
                                "Tesseract: Available", self.COLOR_GREEN)
            else:
                self._set_label("TesseractStatusLabel",
                                "Tesseract: Not found", self.COLOR_RED)
            
            # Python packages status
            n   = self.dependency_status.get('numpy_ok', False)
            p   = self.dependency_status.get('pytesseract_ok', False)
            pil = self.dependency_status.get('pillow_ok', False)
            count = sum([n, p, pil])
            pdf_ok = bool(self.dependency_status.get('pdf_renderer_available', False))
            pdf_status = "PDF: ok" if pdf_ok else "PDF: missing"

            if count >= 3:
                python_status = "Py: 3/3"
            elif count > 0:
                python_status = f"Py: {count}/3"
            else:
                python_status = "Py: 0/3"

            if pdf_ok and count >= 3:
                status_color = self.COLOR_GREEN
            elif count == 0 and not pdf_ok:
                status_color = self.COLOR_RED
            else:
                status_color = self.COLOR_AMBER

            self._set_label(
                "PythonPackagesStatusLabel",
                f"{python_status} | {pdf_status}",
                status_color,
            )
            summary_label = self.get_control("SettingsStatusLabel")
            if summary_label:
                summary_label.setText(self.dependency_status.get("summary", "Dependency status refreshed"))
                    
        except Exception as e:
            logger.error(f"Error checking dependencies in settings: {e}", exc_info=True)
            self._set_label("TesseractStatusLabel",
                            "Tesseract: Check failed", self.COLOR_AMBER)
            self._set_label("PythonPackagesStatusLabel",
                            "Python: Check failed", self.COLOR_AMBER)

    def _load_settings(self):
        """Load settings from config and populate dialog controls."""
        # Tesseract Path
        tesseract_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", self.ctx)
        path_field = self.get_control("TesseractPathTextField")
        if path_field: 
            path_field.setText(tesseract_path)
        self.initial_settings[constants.CFG_KEY_TESSERACT_PATH] = tesseract_path

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
        preset_items = {
            constants.OCR_PRESET_FAST: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_FAST]["label"],
            constants.OCR_PRESET_BALANCED: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_BALANCED]["label"],
            constants.OCR_PRESET_ACCURATE: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_ACCURATE]["label"],
            constants.OCR_PRESET_CUSTOM: "Custom",
        }
        self._populate_dropdown_settings(
            "DefaultPresetDropdown",
            preset_items,
            constants.CFG_KEY_DEFAULT_PRESET,
            constants.DEFAULT_OCR_PRESET,
        )
        self._populate_dropdown_settings(
            "DefaultPSMDropdown",
            _get_runtime_psm_map(self.ctx),
            constants.CFG_KEY_DEFAULT_PSM,
            constants.DEFAULT_PSM_MODE,
        )
        self._populate_dropdown_settings(
            "DefaultOEMDropdown",
            _get_runtime_oem_map(self.ctx),
            constants.CFG_KEY_DEFAULT_OEM,
            constants.DEFAULT_OEM_MODE,
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
        self.initial_settings[constants.CFG_KEY_DEFAULT_PSM] = self._coerce_mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_PSM, constants.DEFAULT_PSM_MODE, self.ctx),
            constants.TESSERACT_PSM_MODES,
            constants.DEFAULT_PSM_MODE,
        )
        self.initial_settings[constants.CFG_KEY_DEFAULT_OEM] = self._coerce_mode_value(
            uno_utils.get_setting(constants.CFG_KEY_DEFAULT_OEM, constants.DEFAULT_OEM_MODE, self.ctx),
            constants.TESSERACT_OEM_MODES,
            constants.DEFAULT_OEM_MODE,
        )
        self.initial_settings[constants.CFG_KEY_DEFAULT_OEM], _oem_warning = _coerce_supported_oem_value(
            self.initial_settings[constants.CFG_KEY_DEFAULT_OEM],
            ctx=self.ctx,
            fallback=constants.DEFAULT_OEM_MODE,
        )
        self.initial_settings[constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT] = self._bool_to_state(preview)
        self.initial_settings[constants.CFG_KEY_MERGE_BATCH_RESULTS] = self._bool_to_state(merge_batch)
        
        status_label = self.get_control("SettingsStatusLabel")
        if status_label:
            status_label.setText("Settings loaded successfully")

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
        """Update the 'Selected: eng+hin+spa' label."""
        label = self.get_control("SelectedLangsLabel")
        if not label:
            return
        codes = sorted(self._selected_codes) if self._selected_codes else [constants.DEFAULT_OCR_LANGUAGE]
        label.setText(f"Selected: {'+'.join(codes)}")

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
                "Opening wiki...",
                "Opening TejOCR wiki...",
                self._open_wiki,
                "Wiki opened in browser.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "filtertube":
            _execute_with_feedback(
                source_control,
                "Opening FilterTube...",
                "Opening FilterTube site...",
                self._open_filtertube,
                "FilterTube opened in browser.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return
        elif command == "search_languages":
            _execute_with_feedback(
                source_control,
                "Filter",
                "Filtering languages...",
                self._filter_languages,
                "Language filter applied.",
                bg_color=self.COLOR_BTN_PRIMARY,
                fg_color=self.COLOR_TEXT_ON_DARK,
            )
            return

        super().actionPerformed(event)

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
        """Show help information for the Settings dialog."""
        help_text = f"""ℹ️ {constants.EXTENSION_FULL_NAME} - Settings Help

✅ DEPENDENCY STATUS:
• Current status of required components
• Open Setup & Diagnostics to test dependencies and view install commands

✅ TESSERACT CONFIGURATION:
• Set path to Tesseract executable manually
• Use 'Browse' to find installation folder
• Use 'Test' to verify the path works

✅ DEFAULT OPTIONS:
• Set preferences for OCR operations:
  - Language: Default language or multi-language list (ex: eng+spa)
  - Output: Default destination for OCR text insertion
  - Preprocessing: Image enhancement options like Grayscale or Binarize

⚠️ ADVANCED PARAMETERS (PRESET, PSM, OEM):
• Preset: Chooses a default quality profile for future OCR runs.
  - Fast: one exact attempt, no enhanced pass, PDF default 200 DPI
  - Balanced: one exact attempt plus one recovery attempt when output is weak
  - Accuracy: one exact attempt plus one enhanced-preprocessing recovery, PDF default 300 DPI
  - Custom: exact manual PSM/OEM/scale/preprocessing with no silent override

• PSM (Page Segmentation Mode): Layout behavior (0-13)
  - 0: OSD only (diagnostic; no OCR text output)
  - 3: Auto layout (Recommended default)
  - 6: Assume a single uniform text block

• OEM (OCR Engine Mode): Extraction behavior (0-3)
  - 0: Legacy engine only
  - 1: LSTM engine only
  - 2: Legacy + LSTM engines combined
  - 3: Auto (Recommended default)
  - Unsupported OEM modes are marked in the UI and fall back to a supported mode when saved as defaults.

💡 HOW IT IS USED:
• These settings are saved and applied automatically as defaults for new OCR runs.
• For single-run temporary changes, use the OCR Options dialog before text extraction.

✅ BATCH & PDF:
• You can select multiple image files or one/more PDFs in the "OCR Image/PDF from File" run.
• Check 'Merge bulk/PDF into single output' to combine all recognized text at once with page headers.
• Requires `pdftoppm` (poppler) or `mutool` installed for PDF support.
• PDFs are processed page-by-page, starting at 200 DPI for Fast/Balanced and 300 DPI for Accuracy.
• When merge is disabled, each image or each PDF page is treated as a separate OCR result and inserted
  using the selected output mode."""
        
        uno_utils.show_message_box("Settings Help", help_text, "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

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
            grayscale_control = self.get_control("DefaultGrayscaleCheckbox")
            binarize_control = self.get_control("DefaultBinarizeCheckbox")
            preset_control = self.get_control("DefaultPresetDropdown")
            psm_control = self.get_control("DefaultPSMDropdown")
            oem_control = self.get_control("DefaultOEMDropdown")
            preview_control = self.get_control("DefaultPreviewCheckbox")
            merge_batch_control = self.get_control("DefaultMergeBatchCheckbox")

            if grayscale_control:
                new_grayscale = grayscale_control.getState()
                if new_grayscale != self.initial_settings.get(constants.CFG_KEY_DEFAULT_GRAYSCALE):
                    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, new_grayscale, self.ctx)
                    changes_made = True

            if binarize_control:
                new_binarize = binarize_control.getState()
                if new_binarize != self.initial_settings.get(constants.CFG_KEY_DEFAULT_BINARIZE):
                    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_BINARIZE, new_binarize, self.ctx)
                    changes_made = True

            if preset_control:
                new_preset = self._coerce_preset_value(
                    self._extract_dropdown_key(
                        preset_control,
                        {
                            constants.OCR_PRESET_FAST: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_FAST]["label"],
                            constants.OCR_PRESET_BALANCED: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_BALANCED]["label"],
                            constants.OCR_PRESET_ACCURATE: constants.OCR_QUALITY_PRESETS[constants.OCR_PRESET_ACCURATE]["label"],
                            constants.OCR_PRESET_CUSTOM: "Custom",
                        },
                        constants.DEFAULT_OCR_PRESET,
                    ),
                    constants.DEFAULT_OCR_PRESET,
                )
                if new_preset != self.initial_settings.get(constants.CFG_KEY_DEFAULT_PRESET):
                    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PRESET, new_preset, self.ctx)
                    changes_made = True

            if psm_control:
                new_psm = self._coerce_mode_value(
                    self._extract_dropdown_key(psm_control, constants.TESSERACT_PSM_MODES, constants.DEFAULT_PSM_MODE),
                    constants.TESSERACT_PSM_MODES,
                    constants.DEFAULT_PSM_MODE,
                )
                if new_psm != self.initial_settings.get(constants.CFG_KEY_DEFAULT_PSM):
                    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_PSM, new_psm, self.ctx)
                    changes_made = True

            if oem_control:
                runtime_oem_map = _get_runtime_oem_map(self.ctx)
                new_oem = self._coerce_mode_value(
                    self._extract_dropdown_key(oem_control, runtime_oem_map, constants.DEFAULT_OEM_MODE),
                    constants.TESSERACT_OEM_MODES,
                    constants.DEFAULT_OEM_MODE,
                )
                new_oem, _oem_warning = _coerce_supported_oem_value(
                    new_oem,
                    ctx=self.ctx,
                    fallback=constants.DEFAULT_OEM_MODE,
                )
                if new_oem != self.initial_settings.get(constants.CFG_KEY_DEFAULT_OEM):
                    uno_utils.set_setting(constants.CFG_KEY_DEFAULT_OEM, new_oem, self.ctx)
                    changes_made = True

            if preview_control:
                new_preview = preview_control.getState()
                if new_preview != self.initial_settings.get(constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT):
                    uno_utils.set_setting(constants.CFG_KEY_SHOW_PREVIEW_BEFORE_OUTPUT, new_preview, self.ctx)
                    changes_made = True

            if merge_batch_control:
                new_merge_batch = merge_batch_control.getState()
                if new_merge_batch != self.initial_settings.get(constants.CFG_KEY_MERGE_BATCH_RESULTS):
                    uno_utils.set_setting(constants.CFG_KEY_MERGE_BATCH_RESULTS, new_merge_batch, self.ctx)
                    changes_made = True
            
            # Update status
            status_label = self.get_control("SettingsStatusLabel")
            if changes_made:
                if status_label: 
                    status_label.setText("Settings saved successfully")
                logger.info("Settings changes saved successfully")
            else:
                if status_label: 
                    status_label.setText("No changes to save")
            
            return True  # Settings saved successfully
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            status_label = self.get_control("SettingsStatusLabel")
            if status_label: 
                status_label.setText("Error saving settings")
            uno_utils.show_message_box("Save Error", f"Could not save settings: {e}", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
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

# --- Setup Dialog Handler ---

class TejOCRSetupDialogHandler(BaseDialogHandler):
    """Handler for the dedicated Setup & Diagnostics dialog."""

    COLOR_GREEN = 0x009900
    COLOR_RED = 0xCC0000
    COLOR_AMBER = 0xCC8800
    _SETUP_COMMAND_BY_NAME = {
        "CopyCommandButton": "copy_command",
        "ReCheckButton": "recheck",
        "CloseSetupButton": "close_setup",
        "copyCommand": "copy_command",
        "copycommandbutton": "copy_command",
        "recheckbutton": "recheck",
        "closesetupbutton": "close_setup",
        "recheck": "recheck",
        "close": "close_setup",
    }
    _SETUP_COMMAND_ALIASES = {
        "copy": "copy_command",
        "copycommand": "copy_command",
        "copy command": "copy_command",
        "copycommandbutton": "copy_command",
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
        
        # Show modal
        self.dialog.execute()

    def _run_check(self):
        """Run dependency checks and populate the dialog."""
        self._set_copy_status("Running dependency checks...", "info")
        self._copy_payload = ""
        self._install_command = ""
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

        # Parse per-package lines from python_packages string
        pkg_lines = ds.get('python_packages', '').split('\n')
        pkg_map = {}
        for line in pkg_lines:
            lower = line.lower()
            if 'numpy' in lower:
                pkg_map['numpy'] = line
            elif 'pytesseract' in lower:
                pkg_map['pytesseract'] = line
            elif 'pillow' in lower or 'pil' in lower:
                pkg_map['pillow'] = line

        # Color each component row
        rows = [
            ("TesseractRow", ds.get('tesseract_ok', False),
             f"✅ Tesseract OCR: {ds.get('tesseract', 'Unknown')}" if ds.get('tesseract_ok') else f"❌ Tesseract OCR: Not found"),
            ("NumpyRow", ds.get('numpy_ok', False),
             f"✅ {pkg_map.get('numpy')}" if ds.get('numpy_ok') else f"❌ Numpy: Missing"),
            ("PytesseractRow", ds.get('pytesseract_ok', False),
             f"✅ {pkg_map.get('pytesseract')}" if ds.get('pytesseract_ok') else f"❌ Pytesseract: Missing"),
            ("PillowRow", ds.get('pillow_ok', False),
             f"✅ {pkg_map.get('pillow')}" if ds.get('pillow_ok') else f"❌ Pillow: Missing"),
            ("PdfRendererRow", pdf_renderer_ok,
             f"✅ {pdf_renderer_status}" if pdf_renderer_ok else f"⚠ {pdf_renderer_status}"),
            ("UnoRow", True, "✅ uno: Built-in (always available)"),
        ]

        for ctrl_name, is_ok, text in rows:
            try:
                ctrl = self.dialog.getControl(ctrl_name)
                if ctrl:
                    ctrl.setText(text)
                    ctrl.getModel().TextColor = self.COLOR_GREEN if is_ok else self.COLOR_RED
            except Exception:
                pass

        next_steps = ds.get("next_steps", "") if isinstance(ds.get("next_steps"), str) else ""

        if pdf_renderer_ok:
            logger.debug("PDF renderer already available during setup diagnostics.")

        if command_candidates:
            self._copy_payload_commands = command_candidates
            self._install_command = command_candidates[0] if command_candidates else ""
            self._copy_payload = self._build_command_list_text(command_candidates)
        else:
            self._copy_payload = ""
            self._install_command = ""
            self._copy_payload_commands = []

        details_lines = []
        missing_components = []
        if not ds.get("tesseract_ok", False):
            missing_components.append("Tesseract OCR")
        missing_python_packages = list(ds.get("python_missing_packages") or [])
        if missing_python_packages:
            missing_components.append(
                "LibreOffice Python packages: {packages}".format(
                    packages=", ".join(missing_python_packages)
                )
            )
        if not pdf_renderer_ok:
            missing_components.append("PDF renderer for PDF OCR")

        if missing_components:
            details_lines.append("Missing components:")
            details_lines.extend(" - {item}".format(item=item) for item in missing_components)
        else:
            details_lines.append("All core OCR dependencies are available.")

        details_lines.append("")
        if ds.get("tesseract_ok", False):
            details_lines.append("Tesseract OCR is available.")
        else:
            tesseract_commands = list(ds.get("tesseract_install_commands") or [])
            if tesseract_commands:
                details_lines.append("Install Tesseract for this device:")
                details_lines.extend(" - {cmd}".format(cmd=cmd) for cmd in tesseract_commands)

        if missing_python_packages:
            details_lines.append("Install missing LibreOffice Python packages:")
            if ds.get("python_install_command"):
                details_lines.append(" - {cmd}".format(cmd=ds.get("python_install_command")))

        if pdf_renderer_ok:
            details_lines.append(
                f"PDF renderer detected: {pdf_renderer_engine}"
                if pdf_renderer_engine else "PDF renderer: Available"
            )
        else:
            details_lines.append("PDF OCR (PDF files) still needs a renderer.")
            if status_hint:
                details_lines.append(f"Current check: {status_hint}")

        if command_candidates:
            details_lines.append("")
            details_lines.append("Command(s) you can copy and run on this device:")
            details_lines.extend(f" - {command}" for command in command_candidates)
        if next_steps:
            details_lines.append("")
            details_lines.append(next_steps)

        details_text = "\n".join(details_lines).strip()

        try:
            cmd_field = self.dialog.getControl("InstallCommandField")
            helper_field = self.dialog.getControl("InstallInstructionsField")

            if not command_candidates:
                if cmd_field:
                    cmd_field.setText("No install command required.")
            else:
                if cmd_field:
                    if self._copy_payload:
                        cmd_field.setText(self._copy_payload)
                    else:
                        cmd_field.setText("Install command not available.")

            if helper_field:
                if details_text:
                    helper_field.setText(details_text)
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
                        "Copy Command(s)" + (f" ({cmd_count})" if cmd_count > 1 else "")
                    )
                else:
                    copy_btn.setText("Copy Command")
            recheck_btn = self.dialog.getControl("ReCheckButton")
            if recheck_btn:
                recheck_btn.setText("Validate")
                recheck_btn.setEnable(True)
        except Exception:
            pass

        if not missing_components:
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
        recheck_btn = None
        try:
            copy_btn = self.dialog.getControl("CopyCommandButton")
        except Exception:
            copy_btn = None
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
                self._set_copy_status("Copy failed. Use fallback text shown below.", "error")
                if copy_btn:
                    copy_btn.setText("Copy Command")
                    self._restore_control_feedback_state(copy_btn, baseline)
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
                    recheck_btn.setText("Validate")
                    self._set_control_feedback(
                        recheck_btn,
                        text="Validate",
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
        import subprocess
        import sys

        command_lines = list(self._copy_payload_commands) if self._copy_payload_commands else []
        if not command_lines and self._install_command:
            command_lines = [self._install_command]
        elif not command_lines and self._copy_payload:
            command_lines = [self._copy_payload]

        normalized_lines = []
        seen = set()
        for line in command_lines:
            candidate = _normalize_command_for_copy(line)
            if not candidate:
                continue
            candidate = candidate.strip()
            if not candidate:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_lines.append(candidate)

        text = "\n".join(normalized_lines).strip()

        if not text:
            self._set_copy_status("No install command available to copy.", "warn")
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

            # Fallback path for environments where UNO clipboard is unavailable
            if not copied:
                if sys.platform == "darwin":
                    # macOS
                    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    proc.communicate(text.encode("utf-8"))
                    copied = proc.returncode == 0
                elif sys.platform.startswith("linux"):
                    # Linux — try xclip first, then xsel
                    for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                        try:
                            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                            proc.communicate(text.encode("utf-8"))
                            if proc.returncode == 0:
                                copied = True
                                break
                        except FileNotFoundError:
                            continue
                elif sys.platform == "win32":
                    proc = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE)
                    proc.communicate(text.encode("utf-8"))
                    copied = proc.returncode == 0
                elif sys.platform.startswith("cygwin"):
                    proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
                    proc.communicate(text.encode("utf-8"))
                    copied = proc.returncode == 0
            logger.debug(f"Copy command succeeded: {copied}")
        except Exception as e:
            logger.error(f"Clipboard subprocess failed: {e}", exc_info=True)
            copied = False

        if not copied:
            self._set_copy_status("Copy failed. Use fallback text shown below.", "error")
            uno_utils.show_message_box("Copy",
                f"Could not access clipboard.\n\nPlease select and copy manually:\n{text}",
                "infobox", parent_frame=self.parent_frame, ctx=self.ctx)
        return copied

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
    if os.name == "nt":
        return f'"{python_path}" -m pip install' if " " in python_path else f"{python_path} -m pip install"
    try:
        return f"{shlex.quote(python_path)} -m pip install"
    except Exception:
        return f'"{python_path}" -m pip install' if " " in python_path else f"{python_path} -m pip install"


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
        r"(?P<exe>(?:\"[^\"]+\"|'[^']+'|/[^\s\"']+|\bpython(?:3)?\b))\s+-m\s+pip\s+install\s+pdf2image\b",
        r"(?P<exe>(?:\"[^\"]+\"|'[^']+'|/[^\s\"']+|\bpython(?:3)?\b))\s+pip\s+install\s+pdf2image\b",
        r"(?P<exe>\"[^\"]+\"|'[^']+'|[^\s\"']+)\s+-m\s+pip\s+install\s+pdf2image",
        r"(?P<exe>\"[^\"]+\"|'[^']+'|[^\s\"']+)\s+pip\s+install\s+pdf2image",
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
    
    # Dynamically detect the running LibreOffice's Python for pip commands
    pip_python = _get_lo_python_path()
    pip_cmd = _build_pip_command(pip_python)
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
        'tesseract_install_commands': [],
        'setup_commands': [],
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
    
    # Check Python packages with detailed diagnostics
    python_packages = []
    
    numpy_available, numpy_version = _package_status("numpy", "numpy")
    if numpy_available:
        python_packages.append(
            "numpy: {version} (OK)".format(version=numpy_version or "installed")
        )
    else:
        python_packages.append("numpy: Not found (required for pytesseract)")

    pytesseract_available, pytesseract_version = _package_status("pytesseract", "pytesseract")
    if pytesseract_available:
        if numpy_available:
            python_packages.append(
                "pytesseract: {version} (OK)".format(
                    version=pytesseract_version or "installed"
                )
            )
        else:
            python_packages.append("pytesseract: Installed but numpy is missing")
    else:
        if numpy_available:
            python_packages.append("pytesseract: Not found")
        else:
            python_packages.append("pytesseract: Cannot load due to missing numpy")

    pillow_available, pillow_version = _package_status("PIL", "Pillow")
    if pillow_available:
        python_packages.append(
            "Pillow: {version} (OK)".format(version=pillow_version or "installed")
        )
    else:
        python_packages.append("Pillow: Not found in LibreOffice Python")
    
    # Check UNO - Should always be available in LibreOffice
    try:
        import uno
        python_packages.append("uno: Available in LibreOffice (OK)")
        uno_available = True
    except ImportError:
        python_packages.append("uno: Not available (unexpected)")
        uno_available = False
    
    status['python_packages'] = '\n'.join(python_packages)
    
    # Store boolean flags for structured access
    status['tesseract_ok'] = tesseract_ok
    status['numpy_ok'] = numpy_available
    status['pytesseract_ok'] = pytesseract_available
    status['pillow_ok'] = pillow_available
    
    logger.debug(f"Dependency check: tesseract_ok={tesseract_ok}, numpy_available={numpy_available}, pytesseract_available={pytesseract_available}, pillow_available={pillow_available}")
    
    python_missing = []
    if not numpy_available:
        python_missing.append("numpy")
    if not pytesseract_available:
        python_missing.append("pytesseract")
    if not pillow_available:
        python_missing.append("pillow")

    python_install_command = ""
    if python_missing:
        python_install_command = "{cmd} {packages}".format(
            cmd=pip_cmd,
            packages=" ".join(python_missing),
        )

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
    if python_install_command:
        _add_setup_command(python_install_command)

    core_ready = (
        tesseract_ok
        and not python_missing
    )
    pdf_renderer_ready = bool(pdf_status.get("available"))
    # Use the more accurate variables from above
    if core_ready and pdf_renderer_ready:
        status['summary'] = "All dependencies ready. OCR functionality available."
        status['next_steps'] = """All dependencies installed and ready.
You can now use all OCR features."""
    elif core_ready and not pdf_renderer_ready:
        status['summary'] = "Core OCR dependencies installed; PDF renderer is missing."
        status['next_steps'] = """Core OCR dependencies are installed.
PDF OCR (PDF files) requires a PDF renderer."""
        
    elif tesseract_ok and (pytesseract_available or pillow_available or numpy_available):
        status['summary'] = "Partially ready -- some Python packages missing"
        status['next_steps'] = f"""Install missing packages: {', '.join(python_missing)}

Run in Terminal:
{python_install_command}

Restart LibreOffice after installation."""
        
    elif tesseract_ok:
        status['summary'] = "Tesseract ready -- Python packages needed"
        status['next_steps'] = f"""Install Python packages for LibreOffice:

Run in Terminal:
{python_install_command or f"{pip_cmd} numpy pytesseract pillow"}

Restart LibreOffice after installation."""
        
    else:
        status['summary'] = "Setup needed -- dependencies not installed"
        quick_steps = ["Quick Setup:"]
        if tesseract_install_commands:
            quick_steps.append("1. Install Tesseract OCR:")
            quick_steps.extend("   {cmd}".format(cmd=cmd) for cmd in tesseract_install_commands)
        if python_install_command:
            quick_steps.append("2. Install Python packages:")
            quick_steps.append("   {cmd}".format(cmd=python_install_command))
        quick_steps.append("3. Restart LibreOffice if the packages still do not appear in this session.")
        quick_steps.append("")
        quick_steps.append("See the Install Guide for your platform.")
        status['next_steps'] = "\n".join(quick_steps)

    if not pdf_status["available"]:
        missing_pdf_message = "PDF OCR (PDF files) also needs a PDF renderer:"
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
        existing_steps = (status['next_steps'] or "No setup steps currently available.").strip()
        if "Core OCR dependencies are installed" in existing_steps:
            pass
        elif "All dependencies installed" in existing_steps:
            existing_steps = "Core OCR dependencies are installed."
        if existing_steps:
            status['next_steps'] = "{existing}\n\n{missing}\n{hints}".format(
                existing=existing_steps,
                missing=missing_pdf_message,
                hints=pdf_hints_formatted,
            )
        else:
            status['next_steps'] = "{missing}\n{hints}".format(
                missing=missing_pdf_message,
                hints=pdf_hints_formatted,
            )
        if pdf_status.get("error"):
            status['next_steps'] += "\n\nCurrent check: {error}".format(error=pdf_status["error"])
        for command in pdf_renderer_commands:
            _add_setup_command(command)

    status['python_missing_packages'] = list(python_missing)
    status['python_install_command'] = python_install_command
    status['tesseract_install_commands'] = list(tesseract_install_commands)
    status['setup_commands'] = list(setup_commands)
    
    # Platform-specific installation guide
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        status['installation_guide'] = f"""macOS Installation:

1. TESSERACT:
   brew install tesseract

2. EXTRA LANGUAGES (optional):
   brew install tesseract-lang

3. PYTHON PACKAGES:
   {pip_cmd} numpy pytesseract pillow

4. PDF RENDERING (for PDFs):
   brew install poppler
   brew install mupdf
   {pip_cmd} pdf2image

4. VERIFY:
   tesseract --version"""
   
    elif system == "linux":
        status['installation_guide'] = f"""Linux Installation:

1. TESSERACT:
   sudo apt install tesseract-ocr   # Ubuntu/Debian
   sudo dnf install tesseract       # Fedora
   sudo pacman -S tesseract         # Arch

2. EXTRA LANGUAGES (optional):
   sudo apt install tesseract-ocr-all   # Ubuntu/Debian (all languages)
   sudo apt install tesseract-ocr-hin   # or individual: hin, fra, deu, etc.

3. PYTHON PACKAGES:
   {pip_cmd} numpy pytesseract pillow

4. PDF RENDERING (for PDFs):
   apt-get install poppler-utils
   apt-get install mupdf-tools
   {pip_cmd} pdf2image

4. VERIFY:
   tesseract --version"""
   
    elif system == "windows":
        status['installation_guide'] = f"""Windows Installation:

1. TESSERACT:
   Download from: https://github.com/UB-Mannheim/tesseract/wiki
   Run installer and add to PATH
   (Select additional languages during installation)

2. PYTHON PACKAGES:
   {pip_cmd} numpy pytesseract pillow

3. PDF RENDERING (for PDFs):
   choco install poppler
   {pip_cmd} pdf2image

3. VERIFY:
   tesseract --version"""
   
    else:
        status['installation_guide'] = f"""Installation:

1. TESSERACT: Install from https://tesseract-ocr.github.io/
2. EXTRA LANGUAGES: Install language data for your platform
3. PYTHON PACKAGES: {pip_cmd} numpy pytesseract pillow
4. VERIFY: tesseract --version"""
    
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

3. Install Python packages:
   {pip_cmd} numpy pytesseract pillow

4. Restart LibreOffice

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
• Check Python packages in LibreOffice Python
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
