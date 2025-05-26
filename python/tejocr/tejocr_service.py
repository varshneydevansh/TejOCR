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
_tejocr_interactive_dialogs_module = None
_tejocr_output_module = None
_tejocr_engine_module = None # Added for consistency if engine is also complex

# --- Helper functions for lazy loading ---
def _ensure_modules_loaded(service_instance, engine=False, dialogs=False, output=False):
    """Ensures all critical modules (dialogs, output, engine) are loaded."""
    global _tejocr_interactive_dialogs_module, _tejocr_output_module, _tejocr_engine_module
    
    if dialogs and _tejocr_interactive_dialogs_module is None:
        service_instance.logger.debug("Lazily importing tejocr_interactive_dialogs module...")
        try:
            from tejocr import tejocr_interactive_dialogs as _interactive_dialogs_mod
            _tejocr_interactive_dialogs_module = _interactive_dialogs_mod
            service_instance.logger.debug("tejocr_interactive_dialogs module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_interactive_dialogs: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("Extension internal error: Interactive Dialogs module failed. Check logs."), "errorbox", parent_frame=service_instance.frame, ctx=service_instance.ctx)
            return False

    if output and _tejocr_output_module is None:
        service_instance.logger.debug("Lazily importing tejocr_output module...")
        try:
            from tejocr import tejocr_output as _output_mod
            _tejocr_output_module = _output_mod
            service_instance.logger.debug("tejocr_output module loaded successfully.")
        except Exception as e:
            service_instance.logger.critical(f"CRITICAL ERROR: Failed to load tejocr_output: {e}", exc_info=True)
            uno_utils.show_message_box(_("Error"), _("Extension internal error: Output module failed. Check logs."), "errorbox", parent_frame=service_instance.frame, ctx=service_instance.ctx)
            return False
            
    if engine and _tejocr_engine_module is None:
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
            if not _ensure_modules_loaded(self, dialogs=True): # Still ensure dialogs module is loaded
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

        # Now that modules are loaded, attempt to use the engine's readiness check
        try:
            if _tejocr_engine_module and hasattr(_tejocr_engine_module, 'is_tesseract_ready'):
                is_ready, message = _tejocr_engine_module.is_tesseract_ready(self.ctx, show_gui_errors=True, parent_frame=self.frame)
                if is_ready:
                    self.logger.info("Tesseract is ready. Proceeding with OCR action.")
                    actual_handler_method(*args, **kwargs)
                else:
                    self.logger.warning(f"Tesseract is not ready: {message}. OCR action aborted.")
                    # Message already shown by is_tesseract_ready if show_gui_errors is True
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
            self.logger.info("Showing interactive OCR options dialog for selected image...")
            # Use the already loaded module via the global variable
            options_handler = _tejocr_interactive_dialogs_module.InteractiveOptionsDialogHandler(
                self.ctx, self.frame, "selected", None
            )
            dialog_result = options_handler.show_dialog()
            
            # Smart defaults when dialog fails or user cancels
            if dialog_result is None or dialog_result == (None, None, False):  # User cancelled or dialog error
                self.logger.info("Dialog failed or cancelled - using smart defaults for selected image OCR")
                # Use smart defaults from settings
                language = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
                output_mode = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, self.ctx)
                improve_image = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", self.ctx).lower() == "true"
            else:
                language, output_mode, improve_image = dialog_result
            
            self.logger.info(f"OCR Options (final): Lang='{language}', Mode='{output_mode}', Improve='{improve_image}'")
                        
            self._perform_ocr_with_options("selected", None, language, output_mode, improve_image)
            
        except Exception as e:
            self.logger.error(f"Error during interactive OCR for selected image: {e}", exc_info=True)
            uno_utils.show_message_box(
                title=_("OCR Error"),
                message=_("An unexpected error occurred while processing the selected image: {error}").format(error=str(e)),
                type="errorbox", parent_frame=self.frame, ctx=self.ctx
            )

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
                    if dialog_result is None or dialog_result == (None, None, False):  # User cancelled or dialog error
                        self.logger.info("Dialog failed or cancelled - using smart defaults for file OCR")
                        # Use smart defaults from settings
                        language = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
                        output_mode = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, self.ctx) 
                        improve_image = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", self.ctx).lower() == "true"
                    else:
                        language, output_mode, improve_image = dialog_result
                    
                    self.logger.info(f"OCR Options for file (final): Lang='{language}', Mode='{output_mode}', Improve='{improve_image}'")
                        
                    self._perform_ocr_with_options("file", image_path, language, output_mode, improve_image)
            else:
                self.logger.info("File selection cancelled by user.")
                
        except Exception as e:
            self.logger.error(f"Error during interactive OCR from file: {e}", exc_info=True)
            uno_utils.show_message_box(
                title=_("OCR Error"),
                message=_("An unexpected error occurred while selecting the file or performing OCR: {error}").format(error=str(e)),
                type="errorbox", parent_frame=self.frame, ctx=self.ctx
            )

    def _perform_ocr_with_options(self, source_type, image_path, language, output_mode, improve_image):
        """Perform OCR with the specified options, including image improvement."""
        try:
            if not _ensure_modules_loaded(self, engine=True, output=True):
                self.logger.error("Perform OCR: Engine or Output module could not be loaded.")
                return
            
            # Provide smart defaults for None values
            if language is None or language == "None":
                language = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx)
                self.logger.info(f"Using default language: {language}")
            
            if output_mode is None or output_mode == "None":
                output_mode = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, self.ctx)
                self.logger.info(f"Using default output mode: {output_mode}")
            
            if improve_image is None:
                improve_image = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", self.ctx).lower() == "true"
                self.logger.info(f"Using default image improvement: {improve_image}")
            
            self.logger.info(f"Performing OCR: source='{source_type}', lang='{language}', mode='{output_mode}', improve='{improve_image}'")
            
            text = None # Initialize text
            source_description = _("unknown source") # Default source description

            # Perform OCR based on source type, now passing improve_image to engine methods
            if source_type == "selected":
                text = _tejocr_engine_module.extract_text_from_selected_image(
                    self.ctx, self.frame, lang=language, improve_image=improve_image
                )
                source_description = _("selected image")
            elif source_type == "file": # Ensure this is 'elif' for clarity if more source types are added later
                text = _tejocr_engine_module.extract_text_from_image_file(
                    self.ctx, image_path, lang=language, improve_image=improve_image
                )
                source_description = f"'{os.path.basename(image_path)}'"
            else:
                self.logger.error(f"Unknown source_type for OCR: {source_type}")
                uno_utils.show_message_box(
                    _("OCR Error"),
                    _("Internal error: Unknown OCR source specified."),
                    "errorbox", parent_frame=self.frame, ctx=self.ctx
                )
                return
            
            if text is not None: # Check for None, as empty string is a valid (no text found) result
                # Handle output based on chosen mode with proper fallback
                self.logger.info(f"OCR extracted {len(text)} characters, routing to output mode: {output_mode}")
                
                try:
                    if output_mode == constants.OUTPUT_MODE_CURSOR:
                        _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CURSOR)
                    elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
                        _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CLIPBOARD)
                    elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
                        _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_TEXTBOX)
                    else:
                        # Fallback for unknown output modes
                        self.logger.warning(f"Unknown output mode '{output_mode}', defaulting to cursor")
                        _tejocr_output_module.handle_ocr_output(self.ctx, self.frame, text, constants.OUTPUT_MODE_CURSOR)
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
                
                char_count = len(text)
                mode_description = {
                    constants.OUTPUT_MODE_CURSOR: _("inserted at cursor"),
                    constants.OUTPUT_MODE_CLIPBOARD: _("copied to clipboard"), 
                    constants.OUTPUT_MODE_TEXTBOX: _("added to new text box")
                }.get(output_mode, _("processed"))
                
                uno_utils.show_message_box(
                    _("OCR Complete"), 
                    _("Successfully extracted {char_count} characters from {source_description} and {mode_description}.").format(
                        char_count=char_count, 
                        source_description=source_description, 
                        mode_description=mode_description
                    ), 
                    "infobox", 
                    parent_frame=self.frame, 
                    ctx=self.ctx
                )
            else: # This means OCR engine returned None (e.g. error during OCR, not just no text found)
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
        
        # Ensure interactive dialogs module is loaded (and engine/output for dependency checks within dialog)
        if not _ensure_modules_loaded(self, dialogs=True, engine=True, output=True):
            self.logger.error("Settings: Critical modules (Dialogs, Engine, Output) could not be loaded.")
            # Message box would have been shown by _ensure_modules_loaded
            return

        try:
            self.logger.info("Showing interactive settings dialog using _tejocr_interactive_dialogs_module...")
            # Use the already loaded module via the global variable
            settings_handler = _tejocr_interactive_dialogs_module.InteractiveSettingsDialogHandler(
                self.ctx, self.frame
            )
            # The show_dialog method in tejocr_interactive_dialogs.py returns True on save, False on Cancel.
            success = settings_handler.show_dialog()
            
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