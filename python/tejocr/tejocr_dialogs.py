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

# Diagnostic print
print(f"DEBUG: tejocr_dialogs.py: Right before UNO interface imports. uno module: {uno}")

# Import UNO interfaces directly from the uno module (safer than com.sun.star imports)
# These are commonly exposed by the uno module itself
try:
    from uno import XActionListener, XItemListener
    print("DEBUG: tejocr_dialogs.py: Successfully imported XActionListener, XItemListener from uno module")
except ImportError:
    # Fallback: Access via UNO type system
    print("DEBUG: tejocr_dialogs.py: Fallback - importing XActionListener, XItemListener via com.sun.star")
    try:
        from com.sun.star.awt import XActionListener, XItemListener
        print("DEBUG: tejocr_dialogs.py: Successfully imported XActionListener, XItemListener from com.sun.star.awt")
    except ImportError as e:
        print(f"DEBUG: tejocr_dialogs.py: CRITICAL - Could not import XActionListener, XItemListener: {e}")
        # This would be a critical failure, but we'll define dummy classes to prevent module loading failure
        class XActionListener: pass
        class XItemListener: pass

# Import other UNO types with similar safety
try:
    from com.sun.star.task import XJobExecutor
    print("DEBUG: tejocr_dialogs.py: Successfully imported XJobExecutor")
except ImportError as e:
    print(f"DEBUG: tejocr_dialogs.py: Warning - Could not import XJobExecutor: {e}")
    class XJobExecutor: pass

# Then your project's modules
from tejocr import uno_utils
from tejocr import constants
from tejocr import tejocr_engine # This also needs correct import order internally
from tejocr import locale_setup

_ = locale_setup.get_translation_function()

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Dialogs")

# We will import tejocr_engine when needed for OCR tasks

# Attempt to import pytesseract for language listing, but don't fail if not present yet
PYTESSERACT_AVAILABLE = False
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

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    logger.warning("Pytesseract not available. Language list will be limited.")

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

    def dispose(self):
        """Disposes of the dialog."""
        if self.dialog:
            self.dialog.dispose()
            self.dialog = None

    # --- XActionListener --- (Common actions)
    def actionPerformed(self, event):
        """Handles action events (e.g., button clicks)."""
        command = event.ActionCommand
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
        super().actionPerformed(event) # Handles run_ocr, cancel, help (if not overridden)
        command = event.ActionCommand
        logger.debug(f"OptionsDialogHandler actionPerformed: {command}")
        
        if command == "refresh_languages":
            self._refresh_languages()
        # NOTE: "help" is handled by super().actionPerformed() — do not duplicate here
        elif command == "run_ocr":
            # The base class will call _handle_ok_action()
            pass

    def _refresh_languages(self):
        """Refresh the language list."""
        self.available_languages_map = {}  # Clear cache
        self._populate_languages_dropdown()
        status_label = self.get_control("StatusLabel")
        if status_label:
            status_label.setText("Language list refreshed")

    def _show_help(self):
        """Show help for the OCR Options dialog."""
        help_text = f"""{constants.EXTENSION_FULL_NAME} - OCR Options Help

LANGUAGE SELECTION:
• Choose the language of text in your image
• Correct language selection improves accuracy
• Use 'Refresh' to update available languages

OUTPUT MODE:
• Cursor: Insert text at current cursor position
• Text Box: Create a new text box with the text
• Replace Image: Replace selected image with text
• Clipboard: Copy text to system clipboard

ADVANCED OPTIONS:
• Page Mode: How Tesseract should analyze the image
• Engine Mode: Which OCR engine to use
• Preprocessing: Basic image enhancement options

BUTTONS:
• Start OCR: Begin text recognition
• Cancel: Close without processing
• Help: Show this help message"""
        
        uno_utils.show_message_box("OCR Options Help", help_text, "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

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
            inverted_psm_map = {v: k for k, v in constants.TESSERACT_PSM_MODES.items()}
            self.selected_options["psm"] = inverted_psm_map.get(selected_psm_display, constants.DEFAULT_PSM_MODE)
        else:
            self.selected_options["psm"] = constants.DEFAULT_PSM_MODE

        # OEM (OCR Engine Mode)
        oem_dropdown = self.get_control("OEMDropdown")
        if oem_dropdown and oem_dropdown.getItemCount() > 0:
            selected_oem_display = oem_dropdown.getSelectedItem()
            inverted_oem_map = {v: k for k, v in constants.TESSERACT_OEM_MODES.items()}
            self.selected_options["oem"] = inverted_oem_map.get(selected_oem_display, constants.DEFAULT_OEM_MODE)
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
        self._populate_dropdown("PSMDropdown", constants.TESSERACT_PSM_MODES, "LastPSMMode", constants.DEFAULT_PSM_MODE)

    def _populate_oem_dropdown(self):
        self._populate_dropdown("OEMDropdown", constants.TESSERACT_OEM_MODES, "LastOEMMode", constants.DEFAULT_OEM_MODE)

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
        if PYTESSERACT_AVAILABLE and not PYTESSERACT_LANGUAGES:
            try:
                tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, self.ctx)
                tess_exec = uno_utils.find_tesseract_executable(tess_path_cfg, self.ctx)
                
                if tess_exec:
                    # Temporarily set tesseract_cmd for get_languages, then revert
                    original_cmd = pytesseract.pytesseract.tesseract_cmd
                    pytesseract.pytesseract.tesseract_cmd = tess_exec
                    try:
                        langs = pytesseract.get_languages(config="--list-langs") # some versions might need config
                        PYTESSERACT_LANGUAGES = {code: LANG_CODE_TO_NAME.get(code, code) for code in sorted(list(set(langs)))}
                    except Exception as e:
                        logger.warning(f"Pytesseract get_languages error: {e}. Falling back.", exc_info=True)
                        PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback
                    finally:
                        pytesseract.pytesseract.tesseract_cmd = original_cmd # Restore
                else:
                    PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback
            except Exception as e:
                logger.error(f"Error getting Tesseract languages: {e}", exc_info=True)
                PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback on any error
        elif not PYTESSERACT_LANGUAGES: # If pytesseract wasn't available or already tried and failed
             logger.info("Pytesseract not available or languages not fetched, using fallback list.")
             PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback
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
        # Legacy button names — listeners are no-ops if control doesn't exist
        self._add_listener_to_control("CheckDependenciesButton", "setup")
        self._add_listener_to_control("InstallGuideButton", "setup")
        self._add_listener_to_control("HelpMeInstallButton", "wiki")
        
        # Search button for language filtering
        self._add_listener_to_control("SearchLanguagesButton", "search_languages")
        
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

            if count >= 3:
                self._set_label("PythonPackagesStatusLabel",
                                "Python: All 3 packages OK", self.COLOR_GREEN)
            elif count > 0:
                self._set_label("PythonPackagesStatusLabel",
                                f"Python: {count}/3 packages installed", self.COLOR_AMBER)
            else:
                self._set_label("PythonPackagesStatusLabel",
                                "Python: No packages found", self.COLOR_RED)
                    
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
        if not current_default_lang:
            current_default_lang = constants.DEFAULT_OCR_LANGUAGE

        self._all_lang_keys = list(langs.keys())
        self._all_lang_map = langs
        self._selected_codes = set(current_default_lang.replace(',', '+').split('+'))
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
        
        status_label = self.get_control("SettingsStatusLabel")
        if status_label:
            status_label.setText("Settings loaded successfully")

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
        # This is similar to _get_tesseract_languages in OptionsDialogHandler
        # but kept separate to manage its own potential cache or state if needed.
        # For now, it can reuse the global PYTESSERACT_LANGUAGES for simplicity, but ideally, it should be independent.
        # Let's assume for now it can use a fresh call or a short-lived cache.
        cached_langs = getattr(self, "_settings_languages_cache", None)
        if PYTESSERACT_AVAILABLE and not cached_langs:
            try:
                tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, self.ctx)
                tess_exec = uno_utils.find_tesseract_executable(tess_path_cfg)
                if tess_exec:
                    original_cmd = pytesseract.pytesseract.tesseract_cmd
                    pytesseract.pytesseract.tesseract_cmd = tess_exec
                    try:
                        langs = pytesseract.get_languages(config="--list-langs")
                        cached_langs = {code: LANG_CODE_TO_NAME.get(code, code) for code in sorted(list(set(langs)))}
                    except Exception as e:
                        logger.warning(f"SettingsDialog: Pytesseract get_languages error: {e}. Falling back.", exc_info=True)
                        cached_langs = {k: v for k, v in LANG_CODE_TO_NAME.items()}
                    finally:
                        pytesseract.pytesseract.tesseract_cmd = original_cmd
                else:
                    cached_langs = {k: v for k, v in LANG_CODE_TO_NAME.items()}
            except Exception as e:
                logger.error(f"SettingsDialog: Error getting Tesseract languages: {e}", exc_info=True)
                cached_langs = {k: v for k, v in LANG_CODE_TO_NAME.items()}
        elif not cached_langs:
            logger.info("SettingsDialog: Pytesseract not available or languages not fetched, using fallback list.")
            cached_langs = {k: v for k, v in LANG_CODE_TO_NAME.items()}
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
                display_text = f"{items_map[key]} ({key})"
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
        super().actionPerformed(event)
        command = event.ActionCommand
        logger.debug(f"SettingsDialogHandler actionPerformed: {command}")
        
        if command == "browse_tesseract_path":
            self._browse_tesseract_path()
        elif command == "test_tesseract":
            self._test_tesseract_path()
        elif command == "refresh_languages_settings":
            self._refresh_languages()
        elif command == "setup":
            self._show_setup()
        elif command == "wiki":
            self._open_wiki()
        elif command == "search_languages":
            self._filter_languages()

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
            status_label = self.get_control("SettingsStatusLabel")
            if status_label:
                status_label.setText("Dependencies checked")
        except Exception as e:
            logger.error(f"Failed to open Setup dialog: {e}", exc_info=True)
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

    def _handle_help_action(self):
        """Show help information for the Settings dialog."""
        help_text = f"""{constants.EXTENSION_FULL_NAME} - Settings Help

DEPENDENCY STATUS:
- Shows current status of required components
- Click Setup to check and see install commands

TESSERACT CONFIGURATION:
• Set path to Tesseract executable
• Use 'Browse' to find installation
• Use 'Test' to verify it works

DEFAULT OPTIONS:
• Set preferences for OCR operations
• Language: Default language or multi-language list (ex: eng+spa)
• Output: Default destination for OCR text
• Preprocessing: Image enhancement options

BUTTONS:
• Save: Saves settings permanently
• Cancel: Discards changes
• Help: Shows this help message"""
        
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

            # Default Preprocessing
            grayscale_control = self.get_control("DefaultGrayscaleCheckbox")
            binarize_control = self.get_control("DefaultBinarizeCheckbox")
            
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

class TejOCRSetupDialogHandler(unohelper.Base, XActionListener):
    """Handler for the dedicated Setup & Diagnostics dialog."""
    
    COLOR_GREEN = 0x009900
    COLOR_RED   = 0xCC0000
    COLOR_AMBER = 0xCC8800

    def __init__(self, ctx, parent_frame=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
        self.dialog = None
        self.dependency_status = None
        self._install_command = ""

    def show(self):
        """Create and show the Setup dialog."""
        smgr = self.ctx.ServiceManager
        dp = smgr.createInstanceWithContext("com.sun.star.awt.ContainerWindowProvider", self.ctx)
        
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
                    ctrl.getModel().ActionCommand = cmd
                    ctrl.addActionListener(self)
            except Exception:
                pass

        # Run initial check
        self._run_check()
        
        # Show modal
        self.dialog.execute()

    def _run_check(self):
        """Run dependency checks and populate the dialog."""
        self.dependency_status = _check_dependencies()
        ds = self.dependency_status

        # Color each component row
        rows = [
            ("TesseractRow", ds.get('tesseract_ok', False),
             f"Tesseract OCR:  {ds.get('tesseract', 'Unknown')}"),
            ("NumpyRow", ds.get('numpy_ok', False), None),
            ("PytesseractRow", ds.get('pytesseract_ok', False), None),
            ("PillowRow", ds.get('pillow_ok', False), None),
            ("UnoRow", True, "uno: Built-in (always available)"),
        ]

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

        rows[1] = ("NumpyRow", ds.get('numpy_ok', False),
                   pkg_map.get('numpy', 'numpy: Unknown'))
        rows[2] = ("PytesseractRow", ds.get('pytesseract_ok', False),
                   pkg_map.get('pytesseract', 'pytesseract: Unknown'))
        rows[3] = ("PillowRow", ds.get('pillow_ok', False),
                   pkg_map.get('pillow', 'Pillow: Unknown'))

        for ctrl_name, is_ok, text in rows:
            try:
                ctrl = self.dialog.getControl(ctrl_name)
                if ctrl:
                    ctrl.setText(text)
                    ctrl.getModel().TextColor = self.COLOR_GREEN if is_ok else self.COLOR_RED
            except Exception:
                pass

        # Fill install instructions
        next_steps = ds.get('next_steps', '')
        self._install_command = next_steps

        try:
            cmd_field = self.dialog.getControl("InstallCommandField")
            if cmd_field:
                cmd_field.setText(next_steps)
        except Exception:
            pass

    def actionPerformed(self, event):
        command = event.ActionCommand
        if command == "copy_command":
            self._copy_to_clipboard()
        elif command == "recheck":
            self._run_check()
        elif command == "close_setup":
            if self.dialog:
                self.dialog.endExecute()

    def _copy_to_clipboard(self):
        """Copy install command to system clipboard using OS utilities."""
        import subprocess
        import sys
        
        text = self._install_command
        copied = False
        
        try:
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
        except Exception as e:
            logger.error(f"Clipboard subprocess failed: {e}", exc_info=True)
        
        # Visual feedback
        try:
            ctrl = self.dialog.getControl("InstallCommandField")
            if ctrl:
                if copied:
                    ctrl.setText("✓ Copied to clipboard!\n\n" + text)
                else:
                    ctrl.setText("⚠ Copy failed — select and copy manually:\n\n" + text)
        except Exception:
            pass
        
        if not copied:
            uno_utils.show_message_box("Copy",
                f"Could not access clipboard.\n\nPlease select and copy manually:\n{text}",
                "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def disposing(self, event):
        pass


# --- Global Dialog Functions ---

def _get_lo_python_path():
    """Dynamically detect the running LibreOffice's Python executable for pip commands.
    
    Walks up from sys.executable to find the LibreOfficePython.framework python3 binary.
    Works for both production (/Applications/LibreOffice.app) and dev builds.
    """
    import sys
    import os
    import glob
    
    exe = sys.executable
    
    # Walk up from sys.executable looking for LibreOfficePython.framework
    path = os.path.abspath(exe)
    for _ in range(15):  # max depth
        parent = os.path.dirname(path)
        if parent == path:
            break
        # Look for the framework python3 relative to this parent
        pattern = os.path.join(parent, "Frameworks", "LibreOfficePython.framework",
                               "Versions", "*", "bin", "python3")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
        path = parent
    
    # Fallback: try standard macOS paths
    for fallback in [
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3",
        "/Applications/LibreOfficeDev.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3",
    ]:
        if os.path.isfile(fallback):
            return fallback
    
    # Last resort: quote sys.executable itself
    return f'"{exe}"'

def _check_dependencies():
    """Check status of all OCR dependencies and provide user guidance."""
    import subprocess
    import sys
    import os
    import glob
    
    # Dynamically detect the running LibreOffice's Python for pip commands
    pip_python = _get_lo_python_path()
    pip_cmd = f'{pip_python} -m pip install'
    
    status = {
        'summary': '',
        'tesseract': '',
        'python_packages': '',
        'installation_guide': '',
        'next_steps': ''
    }
    
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
    
    # Check NumPy first since it's required for pytesseract
    numpy_available = False
    try:
        import numpy
        python_packages.append(f"numpy: {numpy.__version__} (OK)")
        numpy_available = True
    except ImportError:
        python_packages.append("numpy: Not found (required for pytesseract)")
        numpy_available = False
    
    # Check pytesseract using the new engine initialization
    pytesseract_available = False
    try:
        from tejocr import tejocr_engine
        if tejocr_engine._initialize_pytesseract():
            python_packages.append("pytesseract: Available and working (OK)")
            pytesseract_available = True
        else:
            if numpy_available:
                python_packages.append("pytesseract: Available but not working (check tesseract installation)")
            else:
                python_packages.append("pytesseract: Cannot load due to missing numpy")
            pytesseract_available = False
    except Exception as e:
        error_msg = str(e)[:50]
        if "numpy" in error_msg.lower():
            python_packages.append("pytesseract: Failed due to missing numpy")
        else:
            python_packages.append(f"pytesseract: Error checking - {error_msg}")
        pytesseract_available = False
    
    # Check PIL/Pillow
    try:
        import PIL
        python_packages.append(f"Pillow: {PIL.__version__} (OK)")
        pillow_available = True
    except ImportError:
        python_packages.append("Pillow: Not found in LibreOffice Python")
        pillow_available = False
    
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
    
    # Use the more accurate variables from above
    if tesseract_ok and numpy_available and pytesseract_available and pillow_available:
        status['summary'] = "All dependencies ready. OCR functionality available."
        status['next_steps'] = """All dependencies installed and ready.
You can now use all OCR features."""
        
    elif tesseract_ok and (pytesseract_available or pillow_available or numpy_available):
        status['summary'] = "Partially ready -- some Python packages missing"
        missing = []
        if not numpy_available:
            missing.append("numpy")
        if not pytesseract_available:
            missing.append("pytesseract") 
        if not pillow_available:
            missing.append("Pillow")
        
        status['next_steps'] = f"""Install missing packages: {', '.join(missing)}

Run in Terminal:
{pip_cmd} {' '.join(missing)}

Restart LibreOffice after installation."""
        
    elif tesseract_ok:
        status['summary'] = "Tesseract ready -- Python packages needed"
        status['next_steps'] = f"""Install Python packages for LibreOffice:

Run in Terminal:
{pip_cmd} numpy pytesseract pillow

Restart LibreOffice after installation."""
        
    else:
        status['summary'] = "Setup needed -- dependencies not installed"
        status['next_steps'] = """Quick Setup:
1. Install Tesseract OCR
2. Install Python packages
3. Restart LibreOffice

See the Install Guide for your platform."""
    
    # Platform-specific installation guide
    import platform
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        status['installation_guide'] = f"""macOS Installation:

1. TESSERACT:
   brew install tesseract

2. EXTRA LANGUAGES (optional):
   brew install tesseract-lang

3. PYTHON PACKAGES:
   {pip_cmd} numpy pytesseract pillow

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
    """ULTRA-SIMPLE: Shows basic development message without any complex operations."""
    try:
        if ocr_source_type == "selected":
            message = f"{constants.EXTENSION_FULL_NAME} - OCR Selected Image\n\nDEVELOPMENT STATUS: This feature is being developed.\n\nExpected: Extract text from selected image\nCurrent: Development placeholder\n\nClick OK to continue."
        elif ocr_source_type == "file": 
            message = f"{constants.EXTENSION_FULL_NAME} - OCR Image from File\n\nDEVELOPMENT STATUS: This feature is being developed.\n\nExpected: Process image file with OCR\nCurrent: Development placeholder\n\nClick OK to continue."
        else:
            message = f"{constants.EXTENSION_FULL_NAME} - {ocr_source_type}\n\nDevelopment mode active.\nFeature implementation in progress."

        # Use print as primary output - guaranteed to work
        print(f"TejOCR MESSAGE: {message}")
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
        print(f"TejOCR ERROR: {e}")
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
                print(message)
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
                print(message)
        else:
            print(message)
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
        print(f"TESSERACT CHECK: {message}")

def _show_installation_help_dialog(ctx, parent_frame, toolkit, parent_peer):
    """Show installation help dialog."""
    pip_python = _get_lo_python_path()
    help_text = f"""Installation Help - {constants.EXTENSION_FULL_NAME}

QUICK SETUP (macOS):

1. Install Tesseract:
   brew install tesseract

2. Install extra languages (optional):
   brew install tesseract-lang

3. Install Python packages:
   {pip_python} -m pip install numpy pytesseract pillow

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
        print(f"INSTALLATION HELP:\n{help_text}")


if __name__ == "__main__":
    # Setup a basic console logger for __main__ block
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("TejOCR.Dialogs.__main__")

    main_logger.info("tejocr_dialogs.py should be run by LibreOffice.")
    # Basic mock for testing URL generation (requires constants.py to be findable)
    # This will likely fail if constants.py isn't in the python path correctly
    try:
        import os
        # Assuming constants.py is in the same directory as this script if run directly
        # or one level up if this script is in a 'python/tejocr' structure
        # This direct run is mostly for syntax checking, real testing needs LO.
        
        # Attempt to construct a path to where dialogs *would* be
        # This is highly dependent on the current working directory when run directly
        mock_dialogs_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "dialogs")
        if not os.path.exists(mock_dialogs_dir):
            os.makedirs(mock_dialogs_dir)
        
        mock_options_xdl_path = os.path.join(mock_dialogs_dir, "tejocr_options_dialog.xdl")
        mock_settings_xdl_path = os.path.join(mock_dialogs_dir, "tejocr_settings_dialog.xdl")

        if not os.path.exists(mock_options_xdl_path):
            with open(mock_options_xdl_path, "w") as f:
                f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<dlg:window xmlns:dlg=\"http://openoffice.org/2000/dialog\" dlg:id=\"TejOCROptions\"><dlg:bulletinboard/></dlg:window>")
            main_logger.info(f"Created mock XDL: {mock_options_xdl_path}")

        if not os.path.exists(mock_settings_xdl_path):
            with open(mock_settings_xdl_path, "w") as f:
                f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<dlg:window xmlns:dlg=\"http://openoffice.org/2000/dialog\" dlg:id=\"TejOCRSettings\"><dlg:bulletinboard/></dlg:window>")
            main_logger.info(f"Created mock XDL: {mock_settings_xdl_path}")

        main_logger.info(f"Mock Options Dialog XDL should be at: {mock_options_xdl_path}")
        main_logger.info(f"Mock Settings Dialog XDL should be at: {mock_settings_xdl_path}")
        
        # The OptionsDialogHandler URL construction depends on __file__ which behaves differently 
        # when run directly vs imported by LO. So this direct test is limited.
        # handler = OptionsDialogHandler(None)
        # main_logger.info(f"Options Dialog URL (direct run, may be incorrect for LO): {handler.dialog_url}")

    except ImportError as ie:
        main_logger.error(f"ImportError, ensure constants.py is accessible: {ie}", exc_info=True)
    except Exception as e:
        main_logger.error(f"Error in direct run of tejocr_dialogs.py: {e}", exc_info=True) 
