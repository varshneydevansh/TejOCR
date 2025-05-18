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
    print(f"DEBUG: tejocr_service.py: Current sys.path: {sys.path}")
except Exception as e_sys_path:
    print(f"DEBUG: tejocr_service.py: Error modifying sys.path: {e_sys_path}")
# --- End of Python Path Modification ---

try:
    print("DEBUG: tejocr_service.py: Attempting initial imports...")
    import uno
    import unohelper
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
    # from tejocr import tejocr_dialogs # DEFERRED
    # print("DEBUG: tejocr_service.py: tejocr_dialogs imported.") # DEFERRED
    # from tejocr import tejocr_output # DEFERRED
    # print("DEBUG: tejocr_service.py: tejocr_output imported.") # DEFERRED
    from tejocr import locale_setup
    print("DEBUG: tejocr_service.py: locale_setup imported.")
    print("DEBUG: tejocr_service.py: All 'from tejocr import ...' imports successful.")

except ImportError as e_imp:
    print(f"DEBUG: tejocr_service.py: IMPORT ERROR during initial imports: {e_imp}")
    import traceback
    print(traceback.format_exc())
    raise
except Exception as e_gen:
    print(f"DEBUG: tejocr_service.py: GENERAL ERROR during initial imports: {e_gen}")
    import traceback
    print(traceback.format_exc())
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
# Standard UNO MessageBoxResults (values might vary slightly by platform/LO version but names are standard)
MB_RESULT_OK = 1 # Typically OK or first button
MB_RESULT_YES = 2 # Typically "Yes" or first custom button if mapped to Yes/No/Cancel
MB_RESULT_NO = 3  # Typically "No" or second custom button
MB_RESULT_CANCEL = 4 # Typically "Cancel" or third custom button / close
# For a 3-button (Yes/No/Cancel) setup like "Open Settings" / "Guide" / "Cancel",
# YES might be "Open Settings", NO might be "Guide". We need to map them carefully.
# Let's define our own logical constants for clarity in the handler.
USER_CHOICE_OPEN_SETTINGS = MB_RESULT_YES # Map "Open Settings" to what YES button returns
USER_CHOICE_OPEN_GUIDE = MB_RESULT_NO    # Map "Open Guide" to what NO button returns
USER_CHOICE_CANCEL_PROMPT = MB_RESULT_CANCEL # Map "Cancel" to what CANCEL button returns


class TejOCRService(unohelper.Base, XServiceInfo, XDispatchProvider, XDispatch, XInitialization):
    def __init__(self, ctx, *args):
        self.ctx = ctx
        self.frame = None
        # --- DEFERRED IMPORTS ---
        # Import modules that depend on a fully initialized UNO environment here
        try:
            print("DEBUG: TejOCRService __init__: Attempting deferred imports...")
            from tejocr import tejocr_dialogs
            self.tejocr_dialogs = tejocr_dialogs
            print("DEBUG: TejOCRService __init__: tejocr_dialogs imported and assigned.")
            from tejocr import tejocr_output
            self.tejocr_output = tejocr_output
            print("DEBUG: TejOCRService __init__: tejocr_output imported and assigned.")
            print("DEBUG: TejOCRService __init__: Deferred imports successful.")
        except ImportError as e_imp_deferred:
            print(f"DEBUG: TejOCRService __init__: IMPORT ERROR during deferred imports: {e_imp_deferred}")
            if logger: logger.critical(f"Failed to import core modules (dialogs, output) in __init__: {e_imp_deferred}", exc_info=True)
            # Depending on severity, you might re-raise or disable functionality
            raise # Re-raise for now, as these are critical
        except Exception as e_gen_deferred:
            print(f"DEBUG: TejOCRService __init__: GENERAL ERROR during deferred imports: {e_gen_deferred}")
            if logger: logger.critical(f"Unexpected error during deferred imports in __init__: {e_gen_deferred}", exc_info=True)
            raise # Re-raise

        if logger: logger.info("TejOCRService __init__ called.") # Use the logger if available

    def _ensure_tesseract_is_ready_and_run(self, actual_action_callable, requires_select_image_variant=False):
        """
        Checks if Tesseract is configured and working. If not, prompts the user.
        If ready, executes the actual_action_callable.
        requires_select_image_variant is a boolean, if True, the prompt will mention selecting an image.
        """
        from tejocr import tejocr_engine # Import here as it's used by this method

        tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, self.ctx)
        
        # Perform the check without letting check_tesseract_path show its own GUI errors,
        # as we want to show a more specific prompt.
        if tejocr_engine.check_tesseract_path(tess_path_cfg, self.ctx, self.frame, show_success=False, show_gui_errors=False):
            if logger: logger.debug("Tesseract check passed in _ensure_tesseract_is_ready_and_run.")
            actual_action_callable() # Tesseract is ready, run the original action
            return

        if logger: logger.warning("Tesseract check failed in _ensure_tesseract_is_ready_and_run. Prompting user.")

        import platform
        os_name = platform.system()
        install_hint = ""
        if os_name == "Darwin": # macOS
            install_hint = _("On macOS, a common way to install Tesseract is using Homebrew: brew install tesseract")
        elif os_name == "Windows":
            install_hint = _("On Windows, you can find installers on the Tesseract GitHub page (search for 'UB Mannheim Tesseract').")
        elif os_name == "Linux":
            install_hint = _("On Linux, you can usually install Tesseract using your distribution's package manager (e.g., sudo apt install tesseract-ocr).")
        else:
            install_hint = _("Please refer to the Tesseract OCR documentation for installation instructions specific to your operating system.")

        title = _("TejOCR - Tesseract OCR Required")
        
        message_parts = [
            _("TejOCR requires Tesseract OCR to function."),
            _("Tesseract was not found at the configured path or in your system's PATH."),
            install_hint,
            _("What would you like to do?")
        ]
        message = "\\n\\n".join(filter(None, message_parts)) # Join with double newline, remove empty parts

        # We need 3 buttons: "Open Settings", "Installation Guide", "Cancel"
        # Using BUTTONS_YES_NO_CANCEL:
        # YES = Open Settings
        # NO = Installation Guide
        # CANCEL = Cancel
        # We'll need to define button labels if the API doesn't directly allow it for standard Yes/No/Cancel.
        # The standard show_message_box will use default "Yes", "No", "Cancel" labels.
        # For better UX, a custom dialog is better, but let's try with standard buttons first.
        # TODO: Enhance with custom button labels if possible, or a simple custom dialog.
        # For now, the prompt text should make it clear what Yes/No mean.

        # Re-phrasing message to align with Yes/No/Cancel buttons:
        message_for_yes_no_cancel = _(
            "Tesseract OCR is required but not found or not configured.\\n\\n"
            "{os_install_hint}\\n\\n"
            "Open TejOCR Settings to specify the Tesseract path? (Choose Yes)\\n"
            "Open the Tesseract installation guide in your browser? (Choose No)\\n"
            "Cancel the current operation? (Choose Cancel)"
        ).format(os_install_hint=install_hint)

        buttons_yes_no_cancel = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_YES_NO_CANCEL")
        
        # Ensure self.frame is available for the message box
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)

        choice = uno_utils.show_message_box(
            title,
            message_for_yes_no_cancel,
            type="querybox",
            buttons=buttons_yes_no_cancel,
            parent_frame=self.frame,
            ctx=self.ctx
        )

        if choice == MB_RESULT_YES: # User chose "Yes" (Open Settings)
            logger.info("User chose to open settings from Tesseract missing prompt.")
            self._handle_settings()
        elif choice == MB_RESULT_NO: # User chose "No" (Open Installation Guide)
            logger.info("User chose to open Tesseract installation guide.")
            try:
                import webbrowser
                webbrowser.open(TESSERACT_INSTALL_GUIDE_URL, new=2) # new=2: open in new tab if possible
            except Exception as e_wb:
                logger.error(f"Failed to open web browser for Tesseract guide: {e_wb}")
                uno_utils.show_message_box(
                    _("Error"),
                    _("Could not open the web browser. Please manually visit: {url}").format(url=TESSERACT_INSTALL_GUIDE_URL),
                    type="errorbox", parent_frame=self.frame, ctx=self.ctx
                )
        elif choice == MB_RESULT_CANCEL: # User chose "Cancel"
            logger.info("User cancelled from Tesseract missing prompt.")
            # Optionally, show a small confirmation that the action was cancelled
            # uno_utils.show_message_box(_("Action Cancelled"), _("The OCR operation was cancelled because Tesseract is not available."), type="infobox", parent_frame=self.frame, ctx=self.ctx)
        else:
            logger.info(f"Tesseract missing prompt closed with unexpected choice: {choice}")
            # Treat unknown as cancel
            
    def initialize(self, args):
        if logger: logger.info("TejOCRService initializing...")
        if args:
            for arg in args:
                if arg.Name == "Frame":
                    self.frame = arg.Value
        if not self.frame:
            # This get_current_frame call might happen before logger in uno_utils is fully set up
            # if uno_utils also relies on sys.path modifications for its own imports.
            # However, uno_utils.get_logger has a fallback print if its own logger setup fails.
            self.frame = uno_utils.get_current_frame(self.ctx) 
        if logger: logger.info(f"TejOCRService initialized with frame: {self.frame is not None}")

    # XServiceInfo
    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, ServiceName):
        return ServiceName == SERVICE_NAME

    def getSupportedServiceNames(self):
        return (SERVICE_NAME,)

    # XDispatchProvider (methods as you provided them, they look fine)
    def queryDispatch(self, URL, TargetFrameName, SearchFlags):
        if URL.Protocol == "uno:":
            if URL.Path in [DISPATCH_URL_OCR_SELECTED[4:], # Compare without "uno:" prefix
                             DISPATCH_URL_OCR_FROM_FILE[4:], 
                             DISPATCH_URL_SETTINGS[4:], 
                             DISPATCH_URL_TOOLBAR_ACTION[4:]]:
                if logger: logger.debug(f"queryDispatch: Supporting URL {URL.Path}")
                return self 
        if logger: logger.debug(f"queryDispatch: Not supporting URL {URL.Path}")
        return None

    def queryDispatches(self, Requests):
        dispatches = []
        for req in Requests:
            dispatch = self.queryDispatch(req.FeatureURL, req.FrameName, req.SearchFlags)
            dispatches.append(dispatch)
        return tuple(dispatches)

    # XDispatch (methods as you provided them, they look fine, ensure tejocr_dialogs uses 'from tejocr import ...')
    def dispatch(self, URL, Arguments):
        if logger: logger.info(f"Dispatching URL: {URL.Complete}")
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)
            if not self.frame:
                if logger: logger.error("Cannot perform action: No active document window for dispatch.")
                return

        if URL.Protocol == "uno:":
            path = URL.Path # This is the part after "uno:"
            
            if path == DISPATCH_URL_TOOLBAR_ACTION[4:]:
                # Toolbar action checks if an image is selected to decide which OCR to run
                is_image_selected = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
                if is_image_selected:
                    # self._handle_ocr_selected_image()
                    self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image)
                else:
                    # self._handle_ocr_image_from_file()
                    self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file)
                return

            if path == DISPATCH_URL_OCR_SELECTED[4:]:
                # self._handle_ocr_selected_image()
                self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image)
            elif path == DISPATCH_URL_OCR_FROM_FILE[4:]:
                # self._handle_ocr_image_from_file()
                self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file)
            elif path == DISPATCH_URL_SETTINGS[4:]:
                self._handle_settings() # Settings should not have the Tesseract pre-check
    
    def _handle_ocr_selected_image(self):
        if logger: logger.info("Handling OCR Selected Image")
        # ... (rest of your _handle_ocr_selected_image method, ensure tejocr_dialogs is imported correctly)
        if not uno_utils.is_graphic_object_selected(self.frame, self.ctx):
            uno_utils.show_message_box("OCR Selected Image", 
                                       "No suitable graphic object is currently selected. Please select an image.", 
                                       "infobox", parent_frame=self.frame, ctx=self.ctx)
            return
        recognized_text, selected_output_mode = self.tejocr_dialogs.show_ocr_options_dialog(self.ctx, self.frame, "selected")
        if recognized_text is not None and selected_output_mode is not None:
            self.tejocr_output.handle_ocr_output(self.ctx, self.frame, recognized_text, selected_output_mode)
        else:
            if logger: logger.info("OCR on selected image cancelled or failed from dialog.")


    def _handle_ocr_image_from_file(self):
        if logger: logger.info("Handling OCR from file...")
        try:
            file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
            if not file_picker:
                uno_utils.show_message_box(_("Error"), _("Could not create file picker service."), "errorbox", parent_frame=self.frame, ctx=self.ctx)
                return

            # Use the new constant for image file filters
            file_picker.appendFilter(_("All Supported Image Files"), constants.IMAGE_FILE_DIALOG_FILTER)
            # It's good practice to set a default filter that is also the one appended.
            file_picker.setCurrentFilter(_("All Supported Image Files"))
            # Also add an "All Files" filter as a fallback
            file_picker.appendFilter(_("All Files"), "*.*");

            # Set title for the dialog
            file_picker.setTitle(_("Select Image File for OCR"))

            if file_picker.execute() == 1: # OK button
                files = file_picker.getFiles()
                if files and len(files) > 0:
                    image_path_url = files[0]
                    image_path_system = unohelper.fileUrlToSystemPath(image_path_url)
                    if logger: logger.info(f"Image selected for OCR: {image_path_system}")

                    # Now use the Options Dialog
                    # Pass self.frame to the dialog show function
                    # Ensure tejocr_dialogs is imported and available as self.tejocr_dialogs
                    if not hasattr(self, 'tejocr_dialogs') or not self.tejocr_dialogs:
                        logger.error("tejocr_dialogs module not available in service.")
                        uno_utils.show_message_box(_("Error"), _("Dialog module not loaded."), "errorbox", parent_frame=self.frame, ctx=self.ctx)
                        return

                    recognized_text, output_mode = self.tejocr_dialogs.show_ocr_options_dialog(
                        self.ctx,
                        self.frame,
                        ocr_source_type="file",
                        image_path=image_path_system
                    )

                    if recognized_text is not None and output_mode:
                        if logger: logger.info(f"OCR successful from file. Output mode: {output_mode}. Text length: {len(recognized_text)}")
                        # Ensure tejocr_output is imported and available as self.tejocr_output
                        if not hasattr(self, 'tejocr_output') or not self.tejocr_output:
                            logger.error("tejocr_output module not available in service.")
                            uno_utils.show_message_box(_("Error"), _("Output module not loaded."), "errorbox", parent_frame=self.frame, ctx=self.ctx)
                            return
                        self.tejocr_output.process_ocr_result(self.ctx, self.frame, recognized_text, output_mode, image_path_system, None)
                    else:
                        if logger: logger.info("OCR from file was cancelled or failed in options dialog.")
            else:
                if logger: logger.info("File selection for OCR was cancelled by user.")

        except Exception as e:
            if logger: logger.error(f"Error in _handle_ocr_image_from_file: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("An unexpected error occurred while selecting image for OCR: {error_message}").format(error_message=str(e)), "errorbox", parent_frame=self.frame, ctx=self.ctx)


    def _handle_settings(self):
        logger.info("Handling Settings action.")
        # Ensure deferred import of tejocr_dialogs is available
        if not hasattr(self, 'tejocr_dialogs') or not self.tejocr_dialogs:
            logger.debug("Attempting to import tejocr_dialogs in _handle_settings (should have been deferred loaded).")
            from tejocr import tejocr_dialogs as deferred_dialogs # Re-import if necessary
            self.tejocr_dialogs = deferred_dialogs
            logger.debug("tejocr_dialogs imported and assigned in _handle_settings.")

        # Ensure frame is available for dialogs
        if not self.frame:
            logger.warning("Frame not available when trying to open settings. Attempting to get current.")
            self.frame = uno_utils.get_current_frame(self.ctx)
            if not self.frame:
                logger.error("Still no frame; cannot display settings dialog correctly.")
                uno_utils.show_message_box(_("Error"), _("Cannot open settings: No active document window found."), "errorbox", ctx=self.ctx)
                return
        
        try:
            self.tejocr_dialogs.show_settings_dialog(self.ctx, self.frame)
            logger.debug("Settings dialog call completed.")
        except Exception as e_settings_dlg:
            logger.critical(f"Error showing settings dialog: {e_settings_dlg}", exc_info=True)
            uno_utils.show_message_box(_("Settings Error"), _("Could not display the settings dialog: {error}").format(error=str(e_settings_dlg)), "errorbox", parent_frame=self.frame, ctx=self.ctx)


    # XDispatch (Status Update Part - Optional but good for dynamic menu states)
    def addStatusListener(self, Listener, URL):
        logger.debug(f"addStatusListener for URL: {URL.Path if URL and hasattr(URL, 'Path') else 'Invalid/None URL'}")
        # For TejOCR, a basic implementation: enable if an image is selected for OCR_SELECTED, always for others.
        if Listener and URL and hasattr(URL, 'Path') and URL.Path:
            status_event = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            status_event.FeatureURL = URL
            status_event.IsEnabled = True # Default to enabled
            status_event.Requery = False # Generally false unless state changes very rapidly

            is_selected_action = URL.Path == DISPATCH_URL_OCR_SELECTED or URL.Path == DISPATCH_URL_TOOLBAR_ACTION
            
            if is_selected_action: # For toolbar or direct select, enable based on selection
                # Ensure frame is available for is_graphic_object_selected
                current_frame = self.frame
                if not current_frame and self.ctx:
                    current_frame = uno_utils.get_current_frame(self.ctx)
                
                if current_frame: # Only check selection if frame is available
                    status_event.IsEnabled = uno_utils.is_graphic_object_selected(current_frame, self.ctx)
                    logger.debug(f"Status for '{URL.Path}': IsEnabled = {status_event.IsEnabled} (based on selection)")
                else:
                    status_event.IsEnabled = False # Cannot determine selection without a frame
                    logger.debug(f"Status for '{URL.Path}': IsEnabled = False (no frame for selection check)")
            else:
                 logger.debug(f"Status for '{URL.Path}': IsEnabled = True (not selection-dependent)")
            
            # You can also set .State if the command has a state (e.g., a checkbox menu item)
            # status_event.State = True # or some other value like a string for text display

            try:
                Listener.statusChanged(status_event)
            except Exception as e_stat_change:
                logger.error(f"Error calling statusChanged for {URL.Path}: {e_stat_change}", exc_info=True)
        else:
            logger.warning("addStatusListener called with invalid Listener or URL.")


    def removeStatusListener(self, Listener, URL):
        logger.debug(f"removeStatusListener for URL: {URL.Path if URL and hasattr(URL, 'Path') else 'Invalid/None URL'}")
        # If we were storing listeners (e.g., in a dictionary keyed by URL/Listener), we'd remove them here.
        # For this basic implementation, there's nothing to remove as we don't store them.
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