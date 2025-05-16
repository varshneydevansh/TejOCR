# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Handles the creation, display, and event logic for TejOCR dialogs."""

import uno
import unohelper
import os
from com.sun.star.awt import XActionListener, XItemListener, MessageBoxType
from com.sun.star.task import XJobExecutor

from . import uno_utils
from . import constants
from .tejocr_engine import perform_ocr

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
    print("TejOCR Dialogs: pytesseract not available. Language list will be limited.")

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
            if self._handle_ok_action(): # Only end execute if validation passes
                self.dialog.endExecute()
            else:
                self.closed_by_ok = False # Reset if validation failed
        elif command == "cancel":
            self.closed_by_ok = False
            self._handle_cancel_action()
            self.dialog.endExecute()
        elif command == "help":
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
        dialog_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "dialogs", "tejocr_options_dialog.xdl")
        dialog_file_url = unohelper.systemPathToFileUrl(dialog_file_path)
        super().__init__(ctx, dialog_file_url)
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
        print("OptionsDialogHandler: _init_controls would be setting up listeners and populating fields.")
        
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
        for mode_value, control_id in controls.items():
            control = self.get_control(control_id)
            if control:
                control.setState(mode_value == last_mode)

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
                        print(f"Pytesseract get_languages error: {e}. Falling back.")
                        PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback
                    finally:
                        pytesseract.pytesseract.tesseract_cmd = original_cmd # Restore
                else:
                    PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback
            except Exception as e:
                print(f"Error getting Tesseract languages: {e}")
                PYTESSERACT_LANGUAGES = {k: v for k, v in LANG_CODE_TO_NAME.items()} # Fallback on any error
        elif not PYTESSERACT_LANGUAGES: # If pytesseract wasn't available or already tried and failed
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
        if command == "refresh_languages":
            global PYTESSERACT_LANGUAGES # Allow modification
            PYTESSERACT_LANGUAGES = {} # Clear cache to force refresh
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
        """Handles the OK/Run OCR action. Retrieves options, executes OCR, and saves settings."""
        # print("OptionsDialogHandler: _handle_ok_action called")
        # Step 1: Retrieve and save selected options
        lang_dropdown = self.get_control("LanguageDropdown")
        selected_lang_display_name = lang_dropdown.getSelectedItem()
        selected_lang_code = self._get_selected_dropdown_key(selected_lang_display_name, self.available_languages_map)
        if not selected_lang_code: # Fallback if key not found (should not happen with proper map)
            selected_lang_code = lang_dropdown.getSelectedItem() # Use raw item if no key

        psm_dropdown = self.get_control("PSMDropdown")
        selected_psm_display = psm_dropdown.getSelectedItem()
        selected_psm_val = self._get_selected_dropdown_key(selected_psm_display, constants.TESSERACT_PSM_MODES)

        oem_dropdown = self.get_control("OEMDropdown")
        selected_oem_display = oem_dropdown.getSelectedItem()
        selected_oem_val = self._get_selected_dropdown_key(selected_oem_display, constants.TESSERACT_OEM_MODES)

        output_mode = constants.DEFAULT_OUTPUT_MODE # Default
        if self.get_control("OutputAtCursorRadio").getState(): output_mode = constants.OUTPUT_MODE_CURSOR
        elif self.get_control("OutputNewTextboxRadio").getState(): output_mode = constants.OUTPUT_MODE_TEXTBOX
        elif self.get_control("OutputReplaceImageRadio").getState(): output_mode = constants.OUTPUT_MODE_REPLACE
        elif self.get_control("OutputToClipboardRadio").getState(): output_mode = constants.OUTPUT_MODE_CLIPBOARD
        
        grayscale = self.get_control("GrayscaleCheckbox").getState()
        binarize = self.get_control("BinarizeCheckbox").getState()

        self.selected_options = {
            "lang": selected_lang_code,
            "psm": selected_psm_val,
            "oem": selected_oem_val,
            "output_mode": output_mode,
            "grayscale": grayscale,
            "binarize": binarize
        }
        # print(f"Selected options: {self.selected_options}")

        # Save these options for next time (except output mode, which is more session-specific)
        if selected_lang_code:
            uno_utils.set_setting(constants.CFG_KEY_LAST_SELECTED_LANG, selected_lang_code, self.ctx)
        if selected_psm_val is not None: # PSM can be integer 0
            uno_utils.set_setting("LastPSMMode", str(selected_psm_val), self.ctx) # Store as string
        if selected_oem_val is not None: # OEM can be integer 0
            uno_utils.set_setting("LastOEMMode", str(selected_oem_val), self.ctx) # Store as string
        uno_utils.set_setting(constants.CFG_KEY_LAST_OUTPUT_MODE, output_mode, self.ctx)
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_GRAYSCALE, grayscale, self.ctx)
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_BINARIZE, binarize, self.ctx)

        # Step 2: Execute OCR Job
        ocr_successful = self._execute_ocr_job()
        
        # Return True to close dialog if OCR was successful, False to keep it open if error
        return ocr_successful

    def _execute_ocr_job(self):
        """Executes the OCR process based on current dialog settings."""
        status_label = self.get_control("StatusLabel")
        def status_cb(message):
            if status_label:
                status_label.setText(str(message))
            # print(f"OCR Status: {message}") # For debugging if UI doesn't update

        status_cb("Preparing OCR...")
        self.recognized_text = None # Reset previous result

        # self.selected_options should be populated by _handle_ok_action before this is called.
        if not self.selected_options:
            status_cb("Error: OCR options not properly passed. Please close and retry.")
            # This indicates a programming error if this state is reached.
            uno_utils.show_message_box("Internal Error", "OCR options were not available. Please report this bug.", "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
            return False
            
        current_ocr_options = self.selected_options.copy() # Use the already populated options

        # image_path_or_selection_opts: For 'file', it's self.image_path.
        # For 'selected', tejocr_engine._get_image_from_selection uses the frame, so path can be None.
        image_arg = self.image_path if self.ocr_source_type == "file" else None
        
        # Log for debugging
        # print(f"Calling perform_ocr with: source_type='{self.ocr_source_type}', image_arg='{image_arg}', options={current_ocr_options}")

        try:
            result = perform_ocr(
                ctx=self.ctx,
                frame=self.parent_frame, # Use parent_frame of dialog
                source_type=self.ocr_source_type,
                image_path_or_selection_options=image_arg,
                ocr_options=current_ocr_options,
                status_callback=status_cb
            )

            if result and result.get("success"):
                self.recognized_text = result.get("text")
                status_cb(f"OCR successful. Text length: {len(self.recognized_text or '')}")
                # print(f"Recognized text: {self.recognized_text[:100]}...") # Debug
                return True
            else:
                error_msg = result.get("message", "OCR failed. Unknown error.")
                status_cb(f"Error: {error_msg}")
                uno_utils.show_message_box("OCR Error", error_msg, "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
                return False
        except Exception as e:
            # This catches exceptions within perform_ocr if not handled there, or issues calling it.
            error_msg = f"Critical error during OCR: {e}"
            status_cb(error_msg)
            # print(error_msg) # Debug
            import traceback
            traceback.print_exc()
            uno_utils.show_message_box("OCR Execution Error", error_msg, "errorbox", parent_frame=self.parent_frame, ctx=self.ctx)
            return False

# --- Settings Dialog Handler ---
class SettingsDialogHandler(BaseDialogHandler):
    def __init__(self, ctx):
        dialog_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "dialogs", "tejocr_settings_dialog.xdl")
        dialog_file_url = unohelper.systemPathToFileUrl(dialog_file_path)
        super().__init__(ctx, dialog_file_url)
        self.initial_settings = {} # To store settings when dialog opens

    def _init_controls(self):
        """Initialize controls and attach listeners for the Settings dialog."""
        # Example:
        # tesseract_path_field = self.get_control("TesseractPathTextField")
        # if tesseract_path_field:
        #     tesseract_path_field.setText(uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", self.ctx))
        #     self.initial_settings[constants.CFG_KEY_TESSERACT_PATH] = tesseract_path_field.getText()

        # btn_browse = self.get_control("BrowseButton")
        # if btn_browse: btn_browse.addActionListener(self)
        
        # btn_test = self.get_control("TestTesseractButton")
        # if btn_test: btn_test.addActionListener(self)

        # default_lang_dropdown = self.get_control("DefaultLanguageDropdown")
        # # Populate and set default lang
        # self.initial_settings[constants.CFG_KEY_DEFAULT_LANG] = ...
        
        # print("SettingsDialogHandler: _init_controls would be setting up listeners and populating fields.")

        self._add_listener_to_control("SaveButton", "save_settings") # Assuming XDL has SaveButton with ok_button=true
        self._add_listener_to_control("CancelButton", "cancel")
        self._add_listener_to_control("HelpButton", "help")
        # self._add_listener_to_control("BrowseButton", "browse_tesseract_path")
        # self._add_listener_to_control("TestTesseractButton", "test_tesseract")

    def actionPerformed(self, event):
        super().actionPerformed(event)
        command = event.ActionCommand
        # if command == "BrowseTesseractPath":
        #     self._browse_tesseract_path()
        # elif command == "TestTesseract":
        #     self._test_tesseract_path()

    def _browse_tesseract_path(self):
        """Opens a file picker to select the Tesseract executable."""
        # file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
        # ... set up picker ...
        # if file_picker.execute() == 1:
        #     files = file_picker.getFiles()
        #     if files and len(files) > 0:
        #         self.get_control("TesseractPathTextField").setText(uno.fileUrlToSystemPath(files[0]))
        print("SettingsDialogHandler: _browse_tesseract_path called.")

    def _test_tesseract_path(self):
        """Tests the configured Tesseract path."""
        # path = self.get_control("TesseractPathTextField").getText()
        # from . import tejocr_engine # Lazy import
        # if tejocr_engine.check_tesseract_path(path, self.ctx, self.parent_frame):
        #     uno_utils.show_message_box("Tesseract Test", "Tesseract found and seems to be working!", "infobox", parent_frame=self.parent_frame, ctx=self.ctx)
        # else:
        #     # Message already shown by check_tesseract_path
        #     pass
        print("SettingsDialogHandler: _test_tesseract_path called.")

    def _handle_ok_action(self):
        """Save settings if they have changed."""
        # new_tesseract_path = self.get_control("TesseractPathTextField").getText()
        # if new_tesseract_path != self.initial_settings.get(constants.CFG_KEY_TESSERACT_PATH):
        #     uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, new_tesseract_path, self.ctx)
        # ... save other settings ...
        print("SettingsDialogHandler: OK/Save pressed. Settings would be saved here.")
        return True # Indicate settings saved successfully


# --- Global functions to show dialogs (called from tejocr_service.py) ---
def show_ocr_options_dialog(ctx, parent_frame, ocr_source_type, image_path=None):
    """Creates, configures, and shows the OCR Options dialog."""
    # print(f"show_ocr_options_dialog called with: source_type='{ocr_source_type}', image_path='{image_path}'")
    dialog_handler = OptionsDialogHandler(ctx, ocr_source_type=ocr_source_type, image_path=image_path)
    
    # Set the parent frame for the dialog (important for modality and message boxes)
    # dialog_handler.parent_frame = parent_frame # This is now handled in _create_dialog

    if not dialog_handler._create_dialog(parent_frame): # Pass parent_frame here
        # Error creating dialog, message already shown by _create_dialog
        return None, None # Indicate failure

    # Execute the dialog
    success = dialog_handler.execute() # This will show the dialog and block

    recognized_text = None
    selected_output_mode = None

    if success: # This means "Run OCR" was clicked and OCR was successful
        recognized_text = dialog_handler.recognized_text
        selected_output_mode = dialog_handler.selected_options.get("output_mode")
        # print(f"Dialog closed OK. Text: '{recognized_text[:50] if recognized_text else 'None'}...', Output: {selected_output_mode}")
    else:
        # print("Dialog was cancelled or OCR failed.")
        pass # Dialog was cancelled or an error occurred during OCR

    dialog_handler.dispose() # Clean up the dialog
    return recognized_text, selected_output_mode

def show_settings_dialog(ctx, parent_frame):
    """Creates and shows the Settings dialog."""
    try:
        handler = SettingsDialogHandler(ctx)
        if handler._create_dialog(parent_frame):
            handler.execute() # Settings are saved within the handler's OK action
            handler.dispose()
    except Exception as e:
        uno_utils.show_message_box("Dialog Error", f"Cannot show Settings dialog: {e}\nURL attempted: {handler.dialog_url if 'handler' in locals() else 'Unknown'}", "errorbox", parent_frame=parent_frame, ctx=ctx)
    return None


if __name__ == "__main__":
    print("tejocr_dialogs.py should be run by LibreOffice.")
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
            print(f"Created mock XDL: {mock_options_xdl_path}")

        if not os.path.exists(mock_settings_xdl_path):
            with open(mock_settings_xdl_path, "w") as f:
                f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<dlg:window xmlns:dlg=\"http://openoffice.org/2000/dialog\" dlg:id=\"TejOCRSettings\"><dlg:bulletinboard/></dlg:window>")
            print(f"Created mock XDL: {mock_settings_xdl_path}")

        print(f"Mock Options Dialog XDL should be at: {mock_options_xdl_path}")
        print(f"Mock Settings Dialog XDL should be at: {mock_settings_xdl_path}")
        
        # The OptionsDialogHandler URL construction depends on __file__ which behaves differently 
        # when run directly vs imported by LO. So this direct test is limited.
        # handler = OptionsDialogHandler(None)
        # print(f"Options Dialog URL (direct run, may be incorrect for LO): {handler.dialog_url}")

    except ImportError as ie:
        print(f"ImportError, ensure constants.py is accessible: {ie}")
    except Exception as e:
        print(f"Error in direct run: {e}") 