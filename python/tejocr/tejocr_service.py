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

# --- Global variables for lazily loaded modules ---
_tejocr_dialogs_module = None
_tejocr_output_module = None
_tejocr_engine_module = None # Added for consistency if engine is also complex

# --- Helper functions for lazy loading ---
def _ensure_modules_loaded(service_instance):
    """Ensures all critical modules (dialogs, output, engine) are loaded."""
    global _tejocr_dialogs_module, _tejocr_output_module, _tejocr_engine_module
    
    if _tejocr_dialogs_module is None:
        service_instance.logger.debug("Lazily importing tejocr_dialogs module...")
        try:
            from tejocr import tejocr_dialogs as _dialogs_mod
            _tejocr_dialogs_module = _dialogs_mod
            service_instance.logger.debug("tejocr_dialogs module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_dialogs: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("Extension internal error: Dialogs module failed. Check logs."), "errorbox", parent_frame=service_instance.frame, ctx=service_instance.ctx)
            return False

    if _tejocr_output_module is None:
        service_instance.logger.debug("Lazily importing tejocr_output module...")
        try:
            from tejocr import tejocr_output as _output_mod
            _tejocr_output_module = _output_mod
            service_instance.logger.debug("tejocr_output module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_output: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("Extension internal error: Output module failed. Check logs."), "errorbox", parent_frame=service_instance.frame, ctx=service_instance.ctx)
            return False
            
    if _tejocr_engine_module is None:
        service_instance.logger.debug("Lazily importing tejocr_engine module...")
        try:
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
        self.logger.debug(f"queryDispatch CALLED for URL: {URL.Complete if URL else 'None'}, Target: {TargetFrameName}, Flags: {SearchFlags}")
        print(f"CONSOLE DEBUG: queryDispatch CALLED for URL: {URL.Complete if URL else 'None'}")
        dispatch = None
        if self._matches_command_url(URL, DISPATCH_URL_OCR_SELECTED) or \
           self._matches_command_url(URL, DISPATCH_URL_OCR_FROM_FILE) or \
           self._matches_command_url(URL, DISPATCH_URL_SETTINGS) or \
           self._matches_command_url(URL, DISPATCH_URL_TOOLBAR_ACTION):
            # We handle these URLs, so return self as the XDispatch object
            dispatch = self 
            self.logger.debug(f"queryDispatch: MATCHED URL '{URL.Complete}', returning self.")
            print(f"CONSOLE DEBUG: queryDispatch MATCHED URL '{URL.Complete}', returning self")
        else:
            self.logger.debug(f"queryDispatch: NOT MATCHED URL '{URL.Complete}', returning None.")
            print(f"CONSOLE DEBUG: queryDispatch NOT MATCHED URL '{URL.Complete}', returning None")
        return dispatch

    def queryDispatches(self, Requests):
        self.logger.debug(f"queryDispatches CALLED with {len(Requests) if Requests else 0} requests.")
        print(f"CONSOLE DEBUG: queryDispatches CALLED with {len(Requests) if Requests else 0} requests")
        dispatches = []
        for req in Requests:
            dispatches.append(self.queryDispatch(req.FeatureURL, req.FrameName, req.SearchFlags))
        return tuple(dispatches)

    def dispatch(self, URL, Arguments):
        self.logger.info(f"Dispatching URL: {URL.Complete if URL else 'None'}")
        print(f"CONSOLE DEBUG: dispatch CALLED for URL: {URL.Complete if URL else 'None'}")
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)
            if not self.frame:
                self.logger.error("Cannot perform action: No active document window for dispatch.")
                print("CONSOLE DEBUG: ERROR - No active document window for dispatch")
                return

        # CRITICAL: Ensure all necessary modules are loaded before proceeding
        if not _ensure_modules_loaded(self):
            self.logger.error("Dispatch aborted: Critical modules could not be loaded.")
            print("CONSOLE DEBUG: ERROR - Critical modules could not be loaded")
            return

        # Now use _tejocr_dialogs_module, _tejocr_output_module, _tejocr_engine_module
        action_map = {
            DISPATCH_URL_OCR_SELECTED: lambda: self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image),
            DISPATCH_URL_OCR_FROM_FILE: lambda: self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file),
            DISPATCH_URL_SETTINGS: self._handle_settings,
            DISPATCH_URL_TOOLBAR_ACTION: self._handle_toolbar_action # New handler for combined logic
        }

        if URL.Complete in action_map:
            print(f"CONSOLE DEBUG: Found action for URL '{URL.Complete}', executing...")
            action_map[URL.Complete]()
        else:
            self.logger.warning(f"No action mapped for dispatch URL: {URL.Complete}")
            print(f"CONSOLE DEBUG: WARNING - No action mapped for dispatch URL: {URL.Complete}")
            
    def _ensure_tesseract_is_ready_and_run(self, actual_action_callable):
        self.logger.debug(f"_ensure_tesseract_is_ready_and_run called for: {actual_action_callable.__name__}")
        if not _ensure_modules_loaded(self): return # Ensure engine is loaded
        
        tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, self.ctx)
        # Pass self.frame to check_tesseract_path
        if _tejocr_engine_module.check_tesseract_path(tess_path_cfg, self.ctx, self.frame, show_success=False, show_gui_errors=True):
            self.logger.debug("Tesseract check passed. Running action.")
            actual_action_callable()
        else:
            self.logger.warning("Tesseract check failed or user cancelled configuration. Action not run.")
            # User was prompted by check_tesseract_path if GUI errors were enabled.

    def _handle_toolbar_action(self):
        self.logger.info("Handling Toolbar Action")
        if not _ensure_modules_loaded(self): return
        
        is_image_selected = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
        if is_image_selected:
            self.logger.debug("Toolbar action: Image selected, proceeding with OCR Selected Image logic.")
            self._ensure_tesseract_is_ready_and_run(self._handle_ocr_selected_image)
        else:
            self.logger.debug("Toolbar action: No image selected, proceeding with OCR From File logic.")
            self._ensure_tesseract_is_ready_and_run(self._handle_ocr_image_from_file)

    def _handle_ocr_selected_image(self):
        self.logger.info("Handling OCR Selected Image")
        if not _ensure_modules_loaded(self): return

        if not uno_utils.is_graphic_object_selected(self.frame, self.ctx):
            uno_utils.show_message_box(_("OCR Selected Image"), 
                                       _("No suitable graphic object is currently selected. Please select an image."), 
                                       "infobox", parent_frame=self.frame, ctx=self.ctx)
            return
        
        recognized_text, selected_output_mode = _tejocr_dialogs_module.show_ocr_options_dialog(self.ctx, self.frame, "selected")
        if recognized_text is not None and selected_output_mode is not None:
            _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, recognized_text, selected_output_mode)
        else:
            self.logger.info("OCR on selected image cancelled or failed from dialog.")

    def _handle_ocr_image_from_file(self):
        self.logger.info("Handling OCR from file...")
        if not _ensure_modules_loaded(self): return

        file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
        if not file_picker:
            uno_utils.show_message_box(_("Error"), _("Could not create file picker service."), "errorbox", parent_frame=self.frame, ctx=self.ctx)
            return

        # Setup file picker (example for images)
        file_picker.appendFilter("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.tiff")
        file_picker.setCurrentFilter("Image Files")
        file_picker.setTitle(_("Select Image File for OCR"))

        if file_picker.execute() == 1: # OK pressed
            files = file_picker.getFiles()
            if files and len(files) > 0:
                image_path_url = files[0]
                image_path_system = unohelper.fileUrlToSystemPath(image_path_url)
                self.logger.info(f"Image selected from file: {image_path_system}")
                
                recognized_text, output_mode = _tejocr_dialogs_module.show_ocr_options_dialog(
                    self.ctx, self.frame, ocr_source_type="file", image_path=image_path_system
                )
                if recognized_text is not None and output_mode:
                    self.logger.info(f"OCR successful from file. Output mode: {output_mode}. Text length: {len(recognized_text)}")
                    _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, recognized_text, output_mode)
                else:
                    self.logger.info("OCR from file was cancelled or failed in options dialog.")
            else:
                self.logger.info("File picker executed OK, but no files returned.")
        else:
            self.logger.info("File picker cancelled by user.")

    def _handle_settings(self):
        self.logger.info("Handling Settings action.")
        if not _ensure_modules_loaded(self): return
        
        try:
            # Double-check that we have the dialogs module
            if not _tejocr_dialogs_module:
                self.logger.error("Dialogs module not available for settings.")
                return
                
            # Call the ultra-simplified settings dialog
            _tejocr_dialogs_module.show_settings_dialog(self.ctx, self.frame)
            self.logger.debug("Settings dialog call completed successfully.")
            
        except Exception as e_settings_dlg:
            self.logger.critical(f"Critical error in settings dialog: {e_settings_dlg}", exc_info=True)
            print(f"CONSOLE DEBUG: CRITICAL ERROR in settings: {e_settings_dlg}")
            
            # Try to show a basic error message, but don't let this crash either
            try:
                uno_utils.show_message_box(
                    title="Settings Error", 
                    message=f"Settings dialog unavailable: {str(e_settings_dlg)}", 
                    type="errorbox", 
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
            except Exception as e_nested:
                self.logger.critical(f"Even error message box failed: {e_nested}")
                print(f"CONSOLE DEBUG: Even error dialog failed: {e_nested}")

    def addStatusListener(self, Listener, URL):
        self.logger.debug(f"addStatusListener CALLED for URL: {URL.Complete if URL else 'None'}")
        print(f"CONSOLE DEBUG: addStatusListener CALLED for URL: {URL.Complete if URL else 'None'}")
        if not _ensure_modules_loaded(self): 
            self.logger.warning("addStatusListener: Critical modules not loaded, cannot determine status.")
            print("CONSOLE DEBUG: addStatusListener - Critical modules not loaded")
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
            print(f"CONSOLE DEBUG: Status for OCR_SELECTED: IsEnabled={status_event.IsEnabled}")

        elif self._matches_command_url(URL, DISPATCH_URL_OCR_FROM_FILE) or \
             self._matches_command_url(URL, DISPATCH_URL_SETTINGS):
            # OCR from File and Settings are always enabled if the service is active and document is TextDocument
            status_event.IsEnabled = True 
            self.logger.debug(f"Status for {URL.Complete}: IsEnabled=True (always on for TextDocument)")
            print(f"CONSOLE DEBUG: Status for {URL.Complete}: IsEnabled=True")

        elif self._matches_command_url(URL, DISPATCH_URL_TOOLBAR_ACTION):
            # Toolbar action is always enabled, its behavior depends on selection.
            status_event.IsEnabled = True
            self.logger.debug(f"Status for TOOLBAR_ACTION: IsEnabled=True")
            print(f"CONSOLE DEBUG: Status for TOOLBAR_ACTION: IsEnabled=True")
        else:
            self.logger.debug(f"Status for UNKNOWN URL {URL.Complete}: IsEnabled=False by default")
            print(f"CONSOLE DEBUG: Status for UNKNOWN URL {URL.Complete}: IsEnabled=False")

        if Listener and hasattr(Listener, "statusChanged"):
            Listener.statusChanged(status_event)
            print(f"CONSOLE DEBUG: Status event sent to listener for {URL.Complete}")
        else:
            self.logger.warning(f"Status listener invalid or missing statusChanged for URL: {URL.Complete}")
            print(f"CONSOLE DEBUG: WARNING - Invalid listener for {URL.Complete}")

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