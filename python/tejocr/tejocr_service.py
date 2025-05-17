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
                is_image_selected = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
                if is_image_selected:
                    self._handle_ocr_selected_image()
                else:
                    self._handle_ocr_image_from_file()
                return

            if path == DISPATCH_URL_OCR_SELECTED[4:]:
                self._handle_ocr_selected_image()
            elif path == DISPATCH_URL_OCR_FROM_FILE[4:]:
                self._handle_ocr_image_from_file()
            elif path == DISPATCH_URL_SETTINGS[4:]:
                self._handle_settings()
    
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
        if logger: logger.info("Handling OCR Image from File")
        # ... (rest of your _handle_ocr_image_from_file method, ensure tejocr_dialogs and constants are imported correctly)
        file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
        if not file_picker:
            if logger: logger.error("Could not create file picker service for OCR from file.")
            return

        # Initialize filters list
        filters = []
        # Check for a structured IMAGE_FORMAT_FILTERS (dictionary)
        if hasattr(constants, "IMAGE_FORMAT_FILTERS") and isinstance(constants.IMAGE_FORMAT_FILTERS, dict):
            all_exts_list = []
            for desc, exts_str in constants.IMAGE_FORMAT_FILTERS.items():
                filters.append((desc, exts_str))
                all_exts_list.extend(ext.strip() for ext in exts_str.split(';') if ext.strip())
            
            if all_exts_list:
                unique_exts_str = ";".join(sorted(list(set(all_exts_list))))
                file_picker.appendFilter(f"All Supported Images ({unique_exts_str})", unique_exts_str)
            
            for desc, exts_str in filters: # Add individual filters
                file_picker.appendFilter(desc, exts_str)
        
        # Fallback to SUPPORTED_IMAGE_FORMATS_DIALOG_FILTER (single string) if the structured one isn't good
        elif hasattr(constants, "SUPPORTED_IMAGE_FORMATS_DIALOG_FILTER") and constants.SUPPORTED_IMAGE_FORMATS_DIALOG_FILTER:
            file_picker.appendFilter("Supported Images", constants.SUPPORTED_IMAGE_FORMATS_DIALOG_FILTER)
        else:
            # Default fallback if no constants are defined for filters
            file_picker.appendFilter("All Files (*.*)", "*.*")
            if logger: logger.warning("No image filters defined in constants.py, using 'All Files'.")


        file_picker.setTitle("Select Image File for OCR")
        # Set initial directory (optional, could be last used path or default pictures folder)
        # current_dir_url = unohelper.systemPathToFileUrl(os.path.expanduser("~")) # Example: User's home
        # file_picker.setDisplayDirectory(current_dir_url)

        if file_picker.execute() == 1: # OK is 1, Cancel is 0
            files = file_picker.getFiles()
            if files and len(files) > 0:
                image_file_path = unohelper.fileUrlToSystemPath(files[0])
                if logger: logger.info(f"Image selected from file: {image_file_path}")
                recognized_text, selected_output_mode = self.tejocr_dialogs.show_ocr_options_dialog(
                    self.ctx, self.frame, "file", image_path=image_file_path
                )
                if recognized_text is not None and selected_output_mode is not None:
                    self.tejocr_output.handle_ocr_output(self.ctx, self.frame, recognized_text, selected_output_mode)
                else:
                    if logger: logger.info(f"OCR on file '{image_file_path}' cancelled or failed from dialog.")
            else:
                if logger: logger.info("File picker dialog closed without selecting a file.")
        else:
            if logger: logger.info("File picker dialog was cancelled.")


    def _handle_settings(self):
        if logger: logger.info("Handling Settings")
        # ... (ensure tejocr_dialogs is imported correctly)
        self.tejocr_dialogs.show_settings_dialog(self.ctx, self.frame)
        
    def addStatusListener(self, Listener, URL):
        # This needs to be efficient. Only update if truly necessary.
        # Check if URL.Path matches one of our dynamic commands
        path_to_check = URL.Path
        if path_to_check == DISPATCH_URL_OCR_SELECTED[4:] or path_to_check == DISPATCH_URL_TOOLBAR_ACTION[4:]:
            if not self.frame:
                 self.frame = uno_utils.get_current_frame(self.ctx)

            status = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            status.FeatureURL = URL
            status.IsEnabled = uno_utils.is_graphic_object_selected(self.frame, self.ctx) if self.frame else False
            status.State = status.IsEnabled # For simple enable/disable, State can be same as IsEnabled
            # If you had a toggle button, State could be True/False for checked/unchecked
            try:
                Listener.statusChanged(status)
            except Exception as e_status:
                if logger: logger.warning(f"Error in addStatusListener for {URL.Path}: {e_status}", exc_info=False) # Avoid too much logging here


    def removeStatusListener(self, Listener, URL):
        pass

# LibreOffice Python script framework requires a global entry point
try:
    g_ImplementationHelper = unohelper.ImplementationHelper()
    g_ImplementationHelper.addImplementation(
        TejOCRService,
        IMPLEMENTATION_NAME,
        (SERVICE_NAME,), 
    )
    print(f"DEBUG: tejocr_service.py: Implementation '{IMPLEMENTATION_NAME}' added to helper.")
except Exception as e_impl:
    print(f"DEBUG: tejocr_service.py: ERROR adding implementation to helper: {e_impl}")
    import traceback
    print(traceback.format_exc())

# ... (rest of your __main__ block if any for direct testing, which won't run in LO) ...
print("DEBUG: tejocr_service.py: Script execution finished (bottom level).")