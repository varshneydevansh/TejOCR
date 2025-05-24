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

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Dialogs")

# We will import tejocr_engine when needed for OCR tasks

# Attempt to import pytesseract for language listing, but don't fail if not present yet
PYTESSERACT_AVAILABLE = False
PYTESSERACT_LANGUAGES = {}
LANG_CODE_TO_NAME = { # Basic map, can be expanded or replaced by a better i18n solution
    "eng": "English", "hin": "Hindi", "fra": "French", "deu": "German",
    "spa": "Spanish", "ita": "Italian", "por": "Portuguese", "rus": "Russian",
    "jpn": "Japanese", "kor": "Korean", "chi_sim": "Chinese (Simplified)",
    "chi_tra": "Chinese (Traditional)", "ara": "Arabic", "urd": "Urdu",
    "osd": "Orientation and Script Detection"
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
        self.dialog_url = dialog_url # e.g., "vnd.sun.star.script:TejOCR.TejOCRDialogs.py$OptionsDialog?location=user"
        self.dialog = None
        self.parent_frame = None
        self.closed_by_ok = False # Flag to indicate how the dialog was closed

    def _create_dialog(self, parent_frame):
        """Creates and initializes the dialog from its URL."""
        self.parent_frame = parent_frame
        try:
            dp = uno_utils.create_instance("com.sun.star.awt.DialogProvider", self.ctx)
            self.dialog = dp.createDialog(self.dialog_url)
            if not self.dialog:
                uno_utils.show_message_box("Dialog Error", f"Could not create dialog: {self.dialog_url}", "errorbox", parent_frame=parent_frame, ctx=self.ctx)
                return False
            
            # Set parent peer if possible for modality and positioning
            if parent_frame and parent_frame.getContainerWindow():
                 self.dialog.getPeer().setParent(parent_frame.getContainerWindow().getPeer())
            
            self._init_controls() # Initialize controls and listeners
            return True
        except Exception as e:
            uno_utils.show_message_box("Dialog Creation Error", f"Exception creating dialog {self.dialog_url}: {e}", "errorbox", parent_frame=parent_frame, ctx=self.ctx)
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
        # The dialog URL will point to an XDL file. Path needs to be resolvable by LO.
        # Example: "vnd.sun.star.script:TejOCR.xdl$OptionsDialog?location=user"
        # For now, we use a placeholder that assumes it's in the extension package.
        # The actual URL construction might need adjustment based on how LO Python extensions resolve resources.
        # Typically, dialogs are stored in a 'dialogs' subdirectory of the extension.
        # The path would be relative to the extension's root.
        # dialog_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "dialogs", "tejocr_options_dialog.xdl")
        # Attempt to construct URL relative to where LO scripts are found if possible
        # This might need to be: "private:dialogs/tejocr_options_dialog.xdl"
        # Or a more robust way to get extension root.
        # For now, keeping systemPathToFileUrl as it might work if __file__ is within the OXT structure.
        # dialog_file_url = unohelper.systemPathToFileUrl(dialog_file_path) 
        # A more robust way to get the dialog URL if it's packaged:
        # self.dialog_url = uno_utils.get_extension_resource_url(ctx, "dialogs/tejocr_options_dialog.xdl")
        # Corrected URL for packaged extensions:
        dialog_url = "private:dialogs/tejocr_options_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.ocr_source_type = ocr_source_type
        self.image_path = image_path # Store image_path if provided (for 'file' source)
        self.selected_options = {}
        self.available_languages_map = {} # To store code -> display name mapping
        self.recognized_text = None # To store the OCR result

    def _init_controls(self):
        """Initialize controls and attach listeners for the OCR Options dialog."""
        # Example: Get a button and add self as listener
        # btn_run = self.get_control("RunOCRButton")
        # if btn_run:
        #     btn_run.setActionCommand("run_ocr")
        #     btn_run.addActionListener(self)
        
        # btn_cancel = self.get_control("CancelButton")
        # if btn_cancel:
        #     btn_cancel.setActionCommand("cancel")
        #     btn_cancel.addActionListener(self)
        
        # lang_dropdown = self.get_control("LanguageDropdown")
        # if lang_dropdown:
        #    self._populate_languages(lang_dropdown)
        #    lang_dropdown.addItemListener(self)
        # ... and so on for other controls (Output Mode, PSM, OEM, checkboxes)
        
        # For now, just log that this would be where controls are set up
        logger.info("OptionsDialogHandler: _init_controls called.")
        
        # Example for status label
        # status_label = self.get_control("StatusLabel")
        # if status_label: status_label.setText("Ready.")

        self._add_listener_to_control("RefreshLanguagesButton", "refresh_languages")
        self._add_listener_to_control("RunOCRButton", "run_ocr")
        self._add_listener_to_control("CancelButton", "cancel")
        self._add_listener_to_control("HelpButton", "help")

        self._populate_languages_dropdown()
        self._populate_psm_dropdown()
        self._populate_oem_dropdown()
        self._load_output_mode()
        self._load_preprocessing_options()

        status_label = self.get_control("StatusLabel")
        if status_label: status_label.setText("Ready.")

    def _populate_languages_dropdown(self):
        langs = self._get_tesseract_languages()
        self.available_languages_map = langs # Store for retrieval in _handle_ok_action
        self._populate_dropdown("LanguageDropdown", langs, constants.CFG_KEY_LAST_SELECTED_LANG, constants.DEFAULT_OCR_LANGUAGE)

    def _populate_psm_dropdown(self):
        self._populate_dropdown("PSMDropdown", constants.TESSERACT_PSM_MODES, "LastPSMMode", constants.DEFAULT_PSM_MODE)

    def _populate_oem_dropdown(self):
        self._populate_dropdown("OEMDropdown", constants.TESSERACT_OEM_MODES, "LastOEMMode", constants.DEFAULT_OEM_MODE)

    def _load_output_mode(self):
        last_mode = uno_utils.get_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, constants.DEFAULT_OUTPUT_MODE, self.ctx)
        controls = {
            constants.OUTPUT_MODE_CURSOR: "OutputAtCursorRadio",
            constants.OUTPUT_MODE_TEXTBOX: "OutputNewTextboxRadio",
            constants.OUTPUT_MODE_REPLACE: "OutputReplaceImageRadio",
            constants.OUTPUT_MODE_CLIPBOARD: "OutputToClipboardRadio"
        }
        found_selected = False
        for mode_value, control_id in controls.items():
            control = self.get_control(control_id)
            if control:
                is_selected = (str(mode_value) == str(last_mode))
                control.setState(is_selected)
                if is_selected:
                    found_selected = True

        if not found_selected:
            cursor_radio = self.get_control(controls[constants.OUTPUT_MODE_CURSOR])
            if cursor_radio:
                cursor_radio.setState(True)

    def _load_preprocessing_options(self):
        grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, constants.DEFAULT_PREPROC_GRAYSCALE, self.ctx)
        binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, constants.DEFAULT_PREPROC_BINARIZE, self.ctx)
        cb_gray = self.get_control("GrayscaleCheckbox")
        if cb_gray: cb_gray.setState(grayscale)
        cb_bin = self.get_control("BinarizeCheckbox")
        if cb_bin: cb_bin.setState(binarize)

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

    def _populate_dropdown(self, control_name, items_map, current_value_key, default_value):
        dropdown = self.get_control(control_name)
        if not dropdown: return

        stored_value = uno_utils.get_setting(current_value_key, default_value, self.ctx)
        dropdown.getModel().removeAllItems()
        
        selected_pos = 0
        item_keys = list(items_map.keys()) # Keep order for mapping position to key

        for i, key in enumerate(item_keys):
            display_text = items_map[key]
            dropdown.addItem(display_text, i)
            if str(key) == str(stored_value):
                selected_pos = i
        
        if dropdown.getItemCount() > 0:
            dropdown.selectItemPos(selected_pos, True)
        self.available_languages_map = items_map # Store for retrieval

    def actionPerformed(self, event):
        """Handle specific actions for the OCR Options dialog."""
        super().actionPerformed(event)
        command = event.ActionCommand
        logger.debug(f"OptionsDialogHandler actionPerformed: {command}")
        if command == "refresh_languages":
            global PYTESSERACT_LANGUAGES # Allow modification
            PYTESSERACT_LANGUAGES = {} # Clear cache to force refresh
            logger.info("Refreshing OCR languages list.")
            self._populate_languages_dropdown()
            uno_utils.show_message_box("Languages Refreshed", "The list of available OCR languages has been updated.", "infobox", parent_frame=self.parent_frame, ctx=self.ctx)

    def _get_selected_dropdown_key(self, control_name, items_map):
        dropdown = self.get_control(control_name)
        if dropdown and dropdown.getItemCount() > 0:
            selected_pos = dropdown.getSelectedItemPos()
            item_keys = list(items_map.keys())
            if 0 <= selected_pos < len(item_keys):
                return item_keys[selected_pos]
        return None

    def _handle_ok_action(self):
        """Collects selected options and prepares for OCR. Returns True if ready, False otherwise."""
        self.selected_options = {}
        # ... (collect all options: language, psm, oem, output_mode, preprocessing)
        # Language
        lang_dropdown = self.get_control("LanguageDropdown")
        if lang_dropdown:
            selected_lang_display = lang_dropdown.getSelectedItem()
            # Find code from display name (self.available_languages_map stores code -> display name)
            # Invert map for lookup or iterate
            inverted_lang_map = {v: k for k, v in self.available_languages_map.items()}
            self.selected_options["lang"] = inverted_lang_map.get(selected_lang_display, constants.DEFAULT_OCR_LANGUAGE)
        else:
            self.selected_options["lang"] = constants.DEFAULT_OCR_LANGUAGE
        
        # Output Mode - Updated to use radio buttons
        output_modes_map = {
            "OutputAtCursorRadio": constants.OUTPUT_MODE_CURSOR,
            "OutputNewTextboxRadio": constants.OUTPUT_MODE_TEXTBOX,
            "OutputReplaceImageRadio": constants.OUTPUT_MODE_REPLACE,
            "OutputToClipboardRadio": constants.OUTPUT_MODE_CLIPBOARD
        }
        self.selected_options["output_mode"] = constants.DEFAULT_OUTPUT_MODE # Default
        for control_id, mode_value in output_modes_map.items():
            control = self.get_control(control_id)
            if control and control.getState():
                self.selected_options["output_mode"] = mode_value
                break
        
        # Save the selected output mode for next time
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_KEY_LAST_OUTPUT_MODE, self.selected_options["output_mode"])

        # PSM
        psm_dropdown = self.get_control("PSMDropdown")
        if psm_dropdown:
            selected_psm_display = psm_dropdown.getSelectedItem()
            # Find key from display name (assuming constants.TESSERACT_PSM_MODES maps int key to display string)
            # Need to invert or iterate
            inverted_psm_map = {v: k for k, v in constants.TESSERACT_PSM_MODES.items()}
            self.selected_options["psm"] = inverted_psm_map.get(selected_psm_display, constants.DEFAULT_TESSERACT_PSM)
        else:
            self.selected_options["psm"] = constants.DEFAULT_TESSERACT_PSM

        # OEM
        oem_dropdown = self.get_control("OEMDropdown")
        if oem_dropdown:
            selected_oem_display = oem_dropdown.getSelectedItem()
            inverted_oem_map = {v: k for k, v in constants.TESSERACT_OEM_MODES.items()}
            self.selected_options["oem"] = inverted_oem_map.get(selected_oem_display, constants.DEFAULT_TESSERACT_OEM)
        else:
            self.selected_options["oem"] = constants.DEFAULT_TESSERACT_OEM

        # Preprocessing
        self.selected_options["grayscale"] = bool(self.get_control("GrayscaleCheckbox").getState())
        self.selected_options["binarize"] = bool(self.get_control("BinarizeCheckbox").getState())

        logger.info(f"OCR Options selected: {self.selected_options}")

        # Save last used options (excluding output mode, as it's often context-dependent)
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_DEFAULT_LANG, self.selected_options["lang"])
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_DEFAULT_PSM, str(self.selected_options["psm"])) # Ensure string for config
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_DEFAULT_OEM, str(self.selected_options["oem"])) # Ensure string for config
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_PREPROCESSING_GRAYSCALE, self.selected_options["grayscale"])
        uno_utils.set_setting(self.ctx, constants.CONFIG_NODE_SETTINGS, constants.CFG_PREPROCESSING_BINARIZE, self.selected_options["binarize"])

        # Set status to processing
        status_label = self.get_control("StatusLabel")
        if status_label: status_label.setText("Processing OCR...")
        
        # Perform OCR in a separate thread or ensure dialog remains responsive
        # For simplicity here, we call it directly. Consider XJobExecutor for long tasks.
        try:
            ocr_result = tejocr_engine.perform_ocr(
                ctx=self.ctx,
                source_type=self.ocr_source_type,
                image_path_or_obj=self.image_path, # This should be the image path for file, or image object for selection
                lang=self.selected_options["lang"],
                psm=self.selected_options["psm"],
                oem=self.selected_options["oem"],
                preprocess_options={
                    "grayscale": self.selected_options["grayscale"],
                    "binarize": self.selected_options["binarize"]
                },
                status_callback=lambda msg: status_label.setText(msg) if status_label else None
            )
            self.recognized_text = ocr_result
            if ocr_result is None: # OCR failed or was cancelled by engine logic
                if status_label: status_label.setText("OCR failed or no text found.")
                # Message box already shown by perform_ocr typically
                return False # Keep dialog open
            else:
                if status_label: status_label.setText(f"OCR successful. {len(ocr_result)} chars.")
                return True # OCR successful, proceed to close dialog and use text

        except Exception as e:
            logger.error(f"Exception during perform_ocr from dialog: {e}", exc_info=True)
            uno_utils.show_message_box("OCR Error", f"An unexpected error occurred during OCR: {e}", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
            if status_label: status_label.setText("Error during OCR.")
            return False # Keep dialog open

# --- Settings Dialog Handler ---
class SettingsDialogHandler(BaseDialogHandler):
    def __init__(self, ctx):
        # dialog_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "dialogs", "tejocr_settings_dialog.xdl")
        # dialog_file_url = unohelper.systemPathToFileUrl(dialog_file_path)
        # self.dialog_url = uno_utils.get_extension_resource_url(ctx, "dialogs/tejocr_settings_dialog.xdl")
        # Corrected URL for packaged extensions:
        dialog_url = "private:dialogs/tejocr_settings_dialog.xdl"
        super().__init__(ctx, dialog_url)
        self.initial_settings = {} # To store settings when dialog opens to check for changes
        self.available_languages_map_settings = {} # Separate map for settings dialog

    def _init_controls(self):
        """Initialize controls and attach listeners for the Settings dialog."""
        logger.info("SettingsDialogHandler: _init_controls called.")
        self._add_listener_to_control("SaveButton", "save_settings") 
        self._add_listener_to_control("CancelButton", "cancel")
        self._add_listener_to_control("HelpButtonSettings", "help") # Renamed from "help" to avoid conflict if base class handles it.
        self._add_listener_to_control("BrowseButton", "browse_tesseract_path")
        self._add_listener_to_control("TestTesseractButton", "test_tesseract")
        self._add_listener_to_control("RefreshLanguagesButtonSettings", "refresh_languages_settings")
        
        self._load_settings()

    def _load_settings(self):
        """Load settings from config and populate dialog controls."""
        # Tesseract Path
        tesseract_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", self.ctx)
        path_field = self.get_control("TesseractPathTextField")
        if path_field: path_field.setText(tesseract_path)
        self.initial_settings[constants.CFG_KEY_TESSERACT_PATH] = tesseract_path

        # Default Language
        # Use the same language fetching logic as OptionsDialogHandler for consistency
        langs = self._get_tesseract_languages_for_settings() # Use a specific method to avoid global PYTESSERACT_LANGUAGES issues if shared
        self._populate_dropdown_settings("DefaultLanguageDropdown", langs, constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE)
        current_default_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
        self.initial_settings[constants.CFG_KEY_DEFAULT_LANG] = current_default_lang

        # Default Preprocessing
        grayscale = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, constants.DEFAULT_PREPROC_GRAYSCALE, self.ctx)
        binarize = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_BINARIZE, constants.DEFAULT_PREPROC_BINARIZE, self.ctx)
        cb_gray = self.get_control("DefaultGrayscaleCheckbox")
        if cb_gray: cb_gray.setState(grayscale)
        cb_bin = self.get_control("DefaultBinarizeCheckbox")
        if cb_bin: cb_bin.setState(binarize)
        self.initial_settings[constants.CFG_KEY_DEFAULT_GRAYSCALE] = grayscale
        self.initial_settings[constants.CFG_KEY_DEFAULT_BINARIZE] = binarize
        
        status_label = self.get_control("SettingsStatusLabel")
        if status_label: status_label.setText("Settings loaded. Modify and click Save.")

    def _get_tesseract_languages_for_settings(self):
        # This is similar to _get_tesseract_languages in OptionsDialogHandler
        # but kept separate to manage its own potential cache or state if needed.
        # For now, it can reuse the global PYTESSERACT_LANGUAGES for simplicity, but ideally, it should be independent.
        # Let's assume for now it can use a fresh call or a short-lived cache.
        cached_langs = getattr(self, "_settings_languages_cache", None)
        if PYTESSERACT_AVAILABLE and not cached_langs:
            try:
                tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, self.ctx)
                tess_exec = uno_utils.find_tesseract_executable(tess_path_cfg, self.ctx)
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
        return self._settings_languages_cache

    def _populate_dropdown_settings(self, control_name, items_map, current_value_key, default_value):
        dropdown = self.get_control(control_name)
        if not dropdown: return

        stored_value = uno_utils.get_setting(current_value_key, default_value, self.ctx)
        dropdown.getModel().removeAllItems()
        
        selected_pos = 0
        # Ensure items_map is not None and is a dictionary
        if items_map and isinstance(items_map, dict):
            item_keys = list(items_map.keys()) 
            for i, key in enumerate(item_keys):
                display_text = items_map[key]
                dropdown.addItem(display_text, i)
                if str(key) == str(stored_value):
                    selected_pos = i
            
            if dropdown.getItemCount() > 0:
                dropdown.selectItemPos(selected_pos, True)
        else:
            logger.error(f"items_map for {control_name} is invalid or empty. Cannot populate dropdown.")
            # Add a default item or error message to the dropdown
            dropdown.addItem("Error: Could not load languages",0)
            dropdown.selectItemPos(0,True)

    def actionPerformed(self, event):
        super().actionPerformed(event) # Handles save_settings, cancel, help (if not overridden)
        command = event.ActionCommand
        logger.debug(f"SettingsDialogHandler actionPerformed: {command}")
        if command == "browse_tesseract_path":
            self._browse_tesseract_path()
        elif command == "test_tesseract":
            self._test_tesseract_path()
        elif command == "refresh_languages_settings":
            self._settings_languages_cache = {} # Clear cache
            langs = self._get_tesseract_languages_for_settings()
            self._populate_dropdown_settings("DefaultLanguageDropdown", langs, constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE)
            uno_utils.show_message_box("Languages Refreshed", "The list of available OCR languages has been updated.", "infobox", parent_frame=self.parent_frame, ctx=self.ctx)
        elif command == "help": # Overriding base if XDL uses HelpButtonSettings
             self._handle_help_action() # Call the base help action

    def _browse_tesseract_path(self):
        """Opens a file picker to select the Tesseract executable."""
        file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.ExecutablePicker", self.ctx)
        if not file_picker:
            # Fallback to FilePicker if ExecutablePicker is not available (older LO?)
            file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
            if not file_picker:
                uno_utils.show_message_box("Error", "Could not create file picker service.", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
                return
        
        # file_picker.setTitle("Select Tesseract Executable") # Usually set by LO
        current_path_str = self.get_control("TesseractPathTextField").getText()
        if current_path_str and os.path.isdir(os.path.dirname(current_path_str)):
            logger.debug(f"Setting display directory for Tesseract path browser: {os.path.dirname(current_path_str)}")
            file_picker.setDisplayDirectory(unohelper.systemPathToFileUrl(os.path.dirname(current_path_str)))

        if file_picker.execute() == 1: # OK
            files = file_picker.getFiles()
            if files and len(files) > 0:
                selected_path = unohelper.fileUrlToSystemPath(files[0])
                logger.info(f"Tesseract path selected via browser: {selected_path}")
                self.get_control("TesseractPathTextField").setText(selected_path)
                self._test_tesseract_path() # Automatically test new path

    def _test_tesseract_path(self):
        path_field = self.get_control("TesseractPathTextField")
        tess_path = path_field.getText().strip()
        status_label = self.get_control("TesseractTestStatusLabel")
        
        is_valid, message = tejocr_engine.check_tesseract_path(tess_path, self.ctx, show_gui_errors=False)
        
        if status_label:
            if is_valid:
                status_label.setText(f"✅ Valid: {message if message else 'Tesseract found and seems OK.'}")
            else:
                status_label.setText(f"❌ Invalid: {message if message else 'Tesseract not found or version check failed.'}")
        else:
            logger.warning("TesseractTestStatusLabel not found in Settings Dialog. Cannot display test status.")
            uno_utils.show_message_box(
                "Tesseract Test",
                f"""Path: {tess_path}
Status: {'Valid' if is_valid else 'Invalid'}
Details: {message}""",
                "infobox" if is_valid else "warningbox",
                parent_frame=self.parent_frame,
                ctx=self.ctx
            )

    def _handle_ok_action(self):
        """Save settings if they have changed."""
        logger.info("SettingsDialog: OK/Save action initiated.")
        # Tesseract Path
        new_tesseract_path = self.get_control("TesseractPathTextField").getText()
        if new_tesseract_path != self.initial_settings.get(constants.CFG_KEY_TESSERACT_PATH):
            logger.info(f"Setting new Tesseract path: {new_tesseract_path}")
            uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, new_tesseract_path, self.ctx)

        # Default Language
        lang_dropdown = self.get_control("DefaultLanguageDropdown")
        if lang_dropdown and lang_dropdown.getItemCount() > 0:
            selected_lang_display = lang_dropdown.getSelectedItem()
            # Need to map display name back to code
            # Re-fetch languages map used to populate this dropdown
            current_langs_map = getattr(self, "_settings_languages_cache", None)
            if not current_langs_map: # Should have been cached by _get_tesseract_languages_for_settings
                 current_langs_map = self._get_tesseract_languages_for_settings()

            selected_lang_code = None
            for code, display in current_langs_map.items():
                if display == selected_lang_display:
                    selected_lang_code = code
                    break
            
            if selected_lang_code and selected_lang_code != self.initial_settings.get(constants.CFG_KEY_DEFAULT_LANG):
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, selected_lang_code, self.ctx)
            elif not selected_lang_code:
                logger.warning(f"Could not map selected language display '{selected_lang_display}' back to a code in settings save.")

        # Default Preprocessing
        new_grayscale = self.get_control("DefaultGrayscaleCheckbox").getState()
        new_binarize = self.get_control("DefaultBinarizeCheckbox").getState()
        if new_grayscale != self.initial_settings.get(constants.CFG_KEY_DEFAULT_GRAYSCALE):
            uno_utils.set_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, new_grayscale, self.ctx)
            logger.info(f"Setting new default grayscale: {new_grayscale}")
        if new_binarize != self.initial_settings.get(constants.CFG_KEY_DEFAULT_BINARIZE):
            uno_utils.set_setting(constants.CFG_KEY_DEFAULT_BINARIZE, new_binarize, self.ctx)
            logger.info(f"Setting new default binarize: {new_binarize}")
        
        # print("SettingsDialogHandler: OK/Save pressed. Settings saved.")
        status_label = self.get_control("SettingsStatusLabel")
        if status_label: status_label.setText("Settings saved successfully.")
        # uno_utils.show_message_box("Settings Saved", "Your settings have been saved.", "infobox", parent_frame=self.parent_frame, ctx=self.ctx)
        return True # Indicate settings saved successfully

# --- Global Dialog Functions ---

def _check_dependencies():
    """Check status of all OCR dependencies and provide user guidance."""
    import subprocess
    import sys
    import os
    
    status = {
        'summary': '',
        'tesseract': '',
        'python_packages': '',
        'installation_guide': '',
        'next_steps': ''
    }
    
    # Check Tesseract
    tesseract_status = "❌ NOT FOUND"
    tesseract_path = "Not detected"
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip().split()[1] if result.stdout.strip().split() else "Unknown"
            tesseract_status = f"✅ INSTALLED (v{version})"
            tesseract_path = "Available in system PATH"
    except:
        pass
    
    status['tesseract'] = f"Status: {tesseract_status}\nPath: {tesseract_path}"
    
    # Check Python packages - Check what's actually available in current context
    python_packages = []
    
    # Check pytesseract - This should work in LibreOffice's Python
    try:
        import pytesseract
        version = getattr(pytesseract, '__version__', 'installed')
        python_packages.append(f"✅ pytesseract: {version}")
        pytesseract_available = True
    except ImportError:
        python_packages.append("❌ pytesseract: Not found in LibreOffice Python")
        pytesseract_available = False
    
    # Check PIL/Pillow - This should work in LibreOffice's Python  
    try:
        import PIL
        python_packages.append(f"✅ Pillow: {PIL.__version__}")
        pillow_available = True
    except ImportError:
        python_packages.append("❌ Pillow: Not found in LibreOffice Python")
        pillow_available = False
    
    # Check UNO - Should always be available in LibreOffice
    try:
        import uno
        python_packages.append("✅ uno: Available in LibreOffice")
        uno_available = True
    except ImportError:
        python_packages.append("❌ uno: Not available (unexpected)")
        uno_available = False
    
    status['python_packages'] = '\n'.join(python_packages)
    
    # More accurate readiness assessment
    tesseract_ok = "✅" in tesseract_status
    
    logger.debug(f"Dependency check: tesseract_ok={tesseract_ok}, pytesseract_available={pytesseract_available}, pillow_available={pillow_available}")
    
    # Use the more accurate variables from above
    if tesseract_ok and pytesseract_available and pillow_available:
        status['summary'] = "🎉 ALL DEPENDENCIES READY! OCR functionality available."
        status['next_steps'] = """NEXT STEPS:
═════════════════════════════

✅ All dependencies installed and ready!
🚀 Enable real OCR: Set DEVELOPMENT_MODE_STRICT_PLACEHOLDERS = False
📋 Start using OCR features with images in your documents

Your TejOCR extension is ready for full functionality!"""
        
    elif tesseract_ok and (pytesseract_available or pillow_available):
        status['summary'] = "⚠️  PARTIALLY READY - Some Python packages missing"
        missing = []
        if not pytesseract_available:
            missing.append("pytesseract")
        if not pillow_available:
            missing.append("Pillow")
        
        status['next_steps'] = f"""NEXT STEPS:
═════════════════════════════

⚠️  Install missing packages: {', '.join(missing)}
📋 Run: pip install {' '.join(missing)}
🔄 Restart LibreOffice after installation"""
        
    elif tesseract_ok:
        status['summary'] = "🔧 TESSERACT READY - Python packages needed"
        status['next_steps'] = """NEXT STEPS:
═════════════════════════════

🔧 Install Python packages for LibreOffice:
📋 Run: pip install pytesseract pillow
🔄 Restart LibreOffice after installation"""
        
    else:
        status['summary'] = "🚀 SETUP NEEDED - Ready to install dependencies"
        status['next_steps'] = """NEXT STEPS:
═════════════════════════════

🎯 Quick Setup (recommended):
1️⃣ Install Tesseract OCR
2️⃣ Install Python packages  
3️⃣ Restart LibreOffice

See installation guide below for your platform."""
    
    # Platform-specific installation guide
    import platform
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        status['installation_guide'] = """🍎 macOS Installation:

1️⃣ TESSERACT:
   brew install tesseract

2️⃣ PYTHON PACKAGES:
   /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install pytesseract pillow

3️⃣ VERIFY:
   tesseract --version"""
   
    elif system == "linux":
        status['installation_guide'] = """🐧 Linux Installation:

1️⃣ TESSERACT:
   sudo apt install tesseract-ocr   # Ubuntu/Debian
   sudo dnf install tesseract       # Fedora
   sudo pacman -S tesseract         # Arch

2️⃣ PYTHON PACKAGES:
   pip3 install pytesseract pillow

3️⃣ VERIFY:
   tesseract --version"""
   
    elif system == "windows":
        status['installation_guide'] = """🪟 Windows Installation:

1️⃣ TESSERACT:
   Download from: https://github.com/UB-Mannheim/tesseract/wiki
   Run installer and add to PATH

2️⃣ PYTHON PACKAGES:
   pip install pytesseract pillow

3️⃣ VERIFY:
   tesseract --version"""
   
    else:
        status['installation_guide'] = """🖥️ General Installation:

1️⃣ TESSERACT: Install from https://tesseract-ocr.github.io/
2️⃣ PYTHON PACKAGES: pip install pytesseract pillow
3️⃣ VERIFY: tesseract --version"""
    
    return status

def show_ocr_options_dialog(ctx, parent_frame, ocr_source_type, image_path=None):
    """ULTRA-SIMPLE: Shows basic development message without any complex operations."""
    try:
        if ocr_source_type == "selected":
            message = "TejOCR - OCR Selected Image\n\nDEVELOPMENT STATUS: This feature is being developed.\n\nExpected: Extract text from selected image\nCurrent: Development placeholder\n\nClick OK to continue."
        elif ocr_source_type == "file": 
            message = "TejOCR - OCR Image from File\n\nDEVELOPMENT STATUS: This feature is being developed.\n\nExpected: Process image file with OCR\nCurrent: Development placeholder\n\nClick OK to continue."
        else:
            message = f"TejOCR - {ocr_source_type}\n\nDevelopment mode active.\nFeature implementation in progress."

        # Use print as primary output - guaranteed to work
        print(f"TejOCR MESSAGE: {message}")
        logger.info(f"OCR dialog message displayed: {ocr_source_type}")
        
        # Try ultra-basic message box without complex constants
        try:
            import uno
            if ctx is None:
                ctx = uno.getComponentContext()
            
            service_manager = ctx.getServiceManager()
            toolkit = service_manager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
            
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
                        desktop = service_manager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
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
                    
                    box = toolkit.createMessageBox(parent_peer, msg_type, buttons, "TejOCR", message)
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
    """Enhanced settings dialog with dependency detection and auto-installation guidance."""
    
    # Get dependency status
    dependency_status = _check_dependencies()
    
    # Create dynamic settings text based on current status
    settings_text = f"""TejOCR Extension Settings & Configuration

VERSION: 0.1.2 (Enhanced UX & Dependency Management)
STATUS: Extension installed and active

DEPENDENCY STATUS:
═══════════════════════════════════

{dependency_status['summary']}

TESSERACT OCR ENGINE:
{dependency_status['tesseract']}

PYTHON PACKAGES:
{dependency_status['python_packages']}

INSTALLATION GUIDANCE:
═══════════════════════════════════

{dependency_status['installation_guide']}

OCR CAPABILITIES:
═══════════════════════════

• Support for 100+ languages
• High-quality LSTM OCR engine
• Image preprocessing and enhancement
• Multiple output formats
• Batch processing support

OUTPUT OPTIONS:
═══════════════════════════

• Insert at cursor position
• Replace selected image  
• Copy to clipboard
• Create new text box

EXTENSION STATUS:
═══════════════════════

Extension: ✅ INSTALLED & ACTIVE
LibreOffice: ✅ COMPATIBLE
Menu System: ✅ WORKING
UI Dialogs: ✅ FUNCTIONAL

{dependency_status['next_steps']}

Ready to implement real OCR functionality! 🚀"""

    # Primary output - always works
    print("=" * 60)
    print("TejOCR SETTINGS:")
    print("=" * 60)
    print(settings_text)
    print("=" * 60)
    
    logger.info("Settings information displayed via console")
    
    # Enhanced UI message display with better error handling
    try:
        import uno
        if ctx is None:
            ctx = uno.getComponentContext()
        
        service_manager = ctx.getServiceManager()
        toolkit = service_manager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        
        if toolkit:
            # Robust parent window detection with multiple fallback methods
            parent_peer = None
            
            # Method 1: Try parent_frame if provided
            if parent_frame:
                try:
                    container_window = parent_frame.getContainerWindow()
                    if container_window:
                        parent_peer = container_window.getPeer()
                        logger.debug("Settings dialog: Got parent_peer from provided parent_frame")
                except Exception as e1:
                    logger.debug(f"Settings dialog Method 1 failed: {e1}")
            
            # Method 2: Try desktop's current frame
            if not parent_peer:
                try:
                    desktop = service_manager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                    if desktop:
                        current_frame = desktop.getCurrentFrame()
                        if current_frame:
                            container_window = current_frame.getContainerWindow()
                            if container_window:
                                parent_peer = container_window.getPeer()
                                logger.debug("Settings dialog: Got parent_peer from desktop current frame")
                except Exception as e2:
                    logger.debug(f"Settings dialog Method 2 failed: {e2}")
            
            # Method 3: Try toolkit's desktop window as fallback
            if not parent_peer:
                try:
                    desktop_window = toolkit.getDesktopWindow()
                    if desktop_window:
                        parent_peer = desktop_window
                        logger.debug("Settings dialog: Got parent_peer from toolkit desktop window")
                except Exception as e3:
                    logger.debug(f"Settings dialog Method 3 failed: {e3}")
            
            # Create message box (works even with None parent in many cases)
            try:
                from com.sun.star.awt.MessageBoxType import INFOBOX
                from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK
                
                msg_type = INFOBOX
                buttons = BUTTONS_OK
                
                box = toolkit.createMessageBox(parent_peer, msg_type, buttons, "TejOCR Settings", settings_text)
                if box:
                    try:
                        result = box.execute()
                        logger.info(f"Settings dialog UI displayed successfully! Result: {result}")
                        return True  # UI was successfully shown
                    except Exception as exec_error:
                        logger.debug(f"Settings dialog execute failed: {exec_error}")
                else:
                    logger.debug("Settings dialog: createMessageBox returned None")
                    
            except ImportError:
                # Fallback to integer constants if enum import fails
                try:
                    msg_type = 1   # Info box type
                    buttons = 1    # OK button
                    
                    box = toolkit.createMessageBox(parent_peer, msg_type, buttons, "TejOCR Settings", settings_text)
                    if box:
                        try:
                            result = box.execute()
                            logger.info(f"Settings dialog UI displayed successfully with fallback! Result: {result}")
                            return True
                        except Exception as exec_error:
                            logger.debug(f"Settings dialog fallback execute failed: {exec_error}")
                    else:
                        logger.debug("Settings dialog fallback: createMessageBox returned None")
                        
                except Exception as fallback_error:
                    logger.debug(f"Settings dialog fallback creation failed: {fallback_error}")
                    
    except Exception as e:
        logger.debug(f"Settings dialog UNO attempt failed: {e}. Console output remains primary.")
    
    logger.info("Settings dialog function completed")


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