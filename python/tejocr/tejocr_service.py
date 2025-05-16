# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

import uno
import unohelper
from com.sun.star.frame import XDispatchProvider, XDispatch
from com.sun.star.lang import XServiceInfo, XInitialization
from com.sun.star.beans import PropertyValue

# Import utilities, constants, and dialogs from our package
from . import uno_utils
from . import constants
from . import tejocr_dialogs # Import the dialogs module
from . import tejocr_output # Import the output module

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Service")

# Constants for dispatch URLs (centralize for easier management)
DISPATCH_URL_OCR_SELECTED = "uno:org.libreoffice.TejOCR.OCRSelectedImage"
DISPATCH_URL_OCR_FROM_FILE = "uno:org.libreoffice.TejOCR.OCRImageFromFile"
DISPATCH_URL_SETTINGS = "uno:org.libreoffice.TejOCR.Settings"
DISPATCH_URL_TOOLBAR_ACTION = "uno:org.libreoffice.TejOCR.ToolbarAction" # For context-sensitive toolbar

# Python specific service implementation name
IMPLEMENTATION_NAME = "org.libreoffice.TejOCR.PythonService.TejOCRService"
SERVICE_NAME = "com.sun.star.frame.ProtocolHandler" # Standard service for dispatch providers


class TejOCRService(unohelper.Base, XServiceInfo, XDispatchProvider, XDispatch, XInitialization):
    def __init__(self, ctx, *args):
        self.ctx = ctx
        self.frame = None
        # It's better to initialize logger here if ctx is available early
        # or ensure get_logger handles ctx=None gracefully for initial calls.
        # The current get_logger in uno_utils has a fallback if ctx isn't available for pathing.
        logger.info("TejOCRService initialized.")

    # XInitialization
    def initialize(self, args):
        if args:
            for arg in args:
                if arg.Name == "Frame":
                    self.frame = arg.Value
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)

    # XServiceInfo
    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, ServiceName):
        return ServiceName == SERVICE_NAME

    def getSupportedServiceNames(self):
        return (SERVICE_NAME,)

    # XDispatchProvider
    def queryDispatch(self, URL, TargetFrameName, SearchFlags):
        if URL.Protocol == "uno:":
            if URL.Path in ["org.libreoffice.TejOCR.OCRSelectedImage", 
                             "org.libreoffice.TejOCR.OCRImageFromFile", 
                             "org.libreoffice.TejOCR.Settings", 
                             "org.libreoffice.TejOCR.ToolbarAction"]:
                return self 
        return None

    def queryDispatches(self, Requests):
        dispatches = []
        for req in Requests:
            dispatch = self.queryDispatch(req.FeatureURL, req.FrameName, req.SearchFlags)
            dispatches.append(dispatch)
        return tuple(dispatches)

    # XDispatch
    def dispatch(self, URL, Arguments):
        if not self.frame:
            self.frame = uno_utils.get_current_frame(self.ctx)
            if not self.frame:
                # uno_utils.show_message_box("TejOCR Error", "Cannot perform action: No active document window.", "errorbox", ctx=self.ctx)
                logger.error("Cannot perform action: No active document window.")
                # Showing a message box here might be redundant if the action itself relies on an active window.
                return

        if URL.Protocol == "uno:":
            path = URL.Path
            
            if path == "org.libreoffice.TejOCR.ToolbarAction":
                is_image_selected = uno_utils.is_graphic_object_selected(self.frame, self.ctx)
                if is_image_selected:
                    self._handle_ocr_selected_image()
                else:
                    self._handle_ocr_image_from_file()
                return

            if path == "org.libreoffice.TejOCR.OCRSelectedImage":
                self._handle_ocr_selected_image()
            elif path == "org.libreoffice.TejOCR.OCRImageFromFile":
                self._handle_ocr_image_from_file()
            elif path == "org.libreoffice.TejOCR.Settings":
                self._handle_settings()

    def _handle_ocr_selected_image(self):
        if not uno_utils.is_graphic_object_selected(self.frame, self.ctx):
            uno_utils.show_message_box("OCR Selected Image", 
                                       "No suitable graphic object is currently selected. Please select an image.", 
                                       "infobox", parent_frame=self.frame, ctx=self.ctx)
            return
        
        # show_ocr_options_dialog now returns (recognized_text, selected_output_mode)
        recognized_text, selected_output_mode = tejocr_dialogs.show_ocr_options_dialog(self.ctx, self.frame, "selected")
        
        if recognized_text is not None and selected_output_mode is not None:
            # OCR was successful and dialog was not cancelled
            logger.info(f"OCR successful on selected image. Output mode: {selected_output_mode}. Text length: {len(recognized_text)}")
            tejocr_output.handle_ocr_output(self.ctx, self.frame, recognized_text, selected_output_mode)
        else:
            # Dialog was cancelled or OCR failed (message already shown by dialog/engine)
            logger.info("OCR on selected image cancelled or failed.")

    def _handle_ocr_image_from_file(self):
        # File selection will be handled by the dialog or a preceding step if we choose to implement a native file picker here first.
        # For now, tejocr_dialogs.show_ocr_options_dialog might need an image_path if source is 'file'.
        # This part needs clarification: show_ocr_options_dialog expects an image_path for "file" type.
        # We need a file picker here.

        file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
        if not file_picker:
            # uno_utils.show_message_box("Error", "Could not create file picker service.", "errorbox", parent_frame=self.frame, ctx=self.ctx)
            logger.error("Could not create file picker service for OCR from file.")
            return

        # Setup file picker
        # Using constants.SUPPORTED_IMAGE_FORMATS_DESC and constants.SUPPORTED_IMAGE_FORMATS_EXT
        filters = []
        for desc, exts_str in constants.IMAGE_FORMAT_FILTERS.items():
            filters.append((desc, exts_str))
        
        # Add an "All supported" filter first
        all_supported_exts = ";".join([exts.split(';')[0] for desc, exts in filters]) # Take primary extension for display
        file_picker.appendFilter("All Supported Images", ";".join([exts for desc, exts in filters]))
        for desc, exts in filters:
            file_picker.appendFilter(desc, exts)
        
        file_picker.setDefaultName("image.png")
        # file_picker.setTitle("Select Image for OCR") # Title is usually set by LO
        file_picker.setMultiSelectionMode(False)

        if file_picker.execute() == 1: # 1 for OK
            files = file_picker.getFiles()
            if files and len(files) > 0:
                image_file_path = unohelper.fileUrlToSystemPath(files[0])
                logger.info(f"Image selected from file: {image_file_path}")
                
                recognized_text, selected_output_mode = tejocr_dialogs.show_ocr_options_dialog(
                    self.ctx, self.frame, "file", image_path=image_file_path
                )
                
                if recognized_text is not None and selected_output_mode is not None:
                    logger.info(f"OCR successful on file '{image_file_path}'. Output: {selected_output_mode}. Text len: {len(recognized_text)}")
                    tejocr_output.handle_ocr_output(self.ctx, self.frame, recognized_text, selected_output_mode)
                else:
                    logger.info(f"OCR on file '{image_file_path}' cancelled or failed.")
            else:
                logger.info("No file selected from picker for OCR from file.")
        else:
            logger.info("File picker was cancelled for OCR from file.")

    def _handle_settings(self):
        tejocr_dialogs.show_settings_dialog(self.ctx, self.frame)
        
    def addStatusListener(self, Listener, URL):
        if URL.Path == "org.libreoffice.TejOCR.OCRSelectedImage" or URL.Path == "org.libreoffice.TejOCR.ToolbarAction":
            if not self.frame:
                 self.frame = uno_utils.get_current_frame(self.ctx)

            status = uno.createUnoStruct("com.sun.star.frame.FeatureStateEvent")
            status.FeatureURL = URL
            status.IsEnabled = uno_utils.is_graphic_object_selected(self.frame, self.ctx) if self.frame else False
            status.State = status.IsEnabled
            try:
                Listener.statusChanged(status)
            except Exception as e:
                pass

    def removeStatusListener(self, Listener, URL):
        pass

# LibreOffice Python script framework requires a global entry point
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    TejOCRService,
    IMPLEMENTATION_NAME,
    (SERVICE_NAME,), # Must be a tuple
)

# For debugging purposes if run directly (not how LO uses it)
if __name__ == "__main__":
    # This only runs if the script is executed directly, not when LO imports it.
    # Setup a basic console logger for __main__ block if needed for direct testing of mocks.
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("TejOCR.Service.__main__")
    main_logger.info("This script is intended to be run by LibreOffice's Python UNO bridge.")
    main_logger.info(f"Implementation Name: {IMPLEMENTATION_NAME}")
    main_logger.info(f"Supported Service Name: {SERVICE_NAME}")
    # The mock objects below are for extremely basic local testing and won't cover UNO interactions.
    class MockUnoStruct:
        def __init__(self, name="", **kwargs):
            self.Name = name
            self.__dict__.update(kwargs)
            # main_logger.debug(f"MockUnoStruct created: {name}, {kwargs}")

    class MockUnoContext:
        def getServiceManager(self):
            main_logger.debug("MockContext: getServiceManager called")
            return self 
        def createInstanceWithContext(self, name, ctx):
            main_logger.debug(f"MockContext: createInstanceWithContext for {name}")
            if name == "com.sun.star.awt.Toolkit":
                return MockToolkit()
            if name == "com.sun.star.frame.Desktop":
                return MockDesktop()
            # Need to mock DialogProvider for tejocr_dialogs import to work in this mock
            if name == "com.sun.star.awt.DialogProvider":
                return MockDialogProvider()
            return None
    
    class MockDesktop:
        def getCurrentFrame(self):
            main_logger.debug("MockDesktop: getCurrentFrame called")
            return MockFrame()

    class MockFrame:
        def getContainerWindow(self):
            main_logger.debug("MockFrame: getContainerWindow called")
            return self # Mocking peer provider
        def getPeer(self):
            main_logger.debug("MockFrame: getPeer called - returning None as it needs a real window")
            return None # No real peer in this mock
        def getController(self):
            main_logger.debug("MockFrame: getController called")
            return self # Mocking controller
        def getSelection(self):
            main_logger.debug("MockFrame: getSelection called - returning None")
            return None # No real selection

    class MockToolkit:
        def createMessageBox(self, parent, type, buttons, title, message):
            main_logger.info(f"MockMessageBox: Title='{title}', Message='{message}', Type='{type}', Buttons='{buttons}'")
            return MockMessageBoxInstance()

    class MockMessageBoxInstance:
        def execute(self):
            main_logger.debug("MockMessageBoxInstance: execute()")
            return 0
    
    class MockDialogProvider:
        def createDialog(self, url):
            main_logger.debug(f"MockDialogProvider: createDialog called with {url}")
            # Return a mock dialog that can be executed
            return MockDialog()

    class MockDialog:
        def execute(self):
            main_logger.debug("MockDialog: execute() called")
            return 1 # Simulate OK
        def dispose(self):
            main_logger.debug("MockDialog: dispose() called")
        def getPeer(self):
            # main_logger.debug("MockDialog: getPeer() called")
            return self # Needs to return something that has setParent
        def setParent(self, parent_peer):
            # main_logger.debug(f"MockDialog: setParent() called with {parent_peer}")
            pass
        def getControl(self, name):
            main_logger.debug(f"MockDialog: getControl('{name}') called - returning mock control")
            return MockControl(name)

    class MockControl:
        def __init__(self, name):
            self.name = name
            self._text = ""
            self._state = False
            self._items = []
            self._selected_pos = -1

        def setActionCommand(self, cmd):
            # print(f"MockControl ({self.name}): setActionCommand('{cmd}')")
            pass
        def addActionListener(self, listener):
            # print(f"MockControl ({self.name}): addActionListener()")
            pass
        def setText(self, text):
            # print(f"MockControl ({self.name}): setText('{text}')")
            self._text = text
        def getText(self):
            return self._text
        def setState(self, state):
            # print(f"MockControl ({self.name}): setState({state})")
            self._state = state
        def getState(self):
            return self._state
        def getModel(self):
            # print(f"MockControl ({self.name}): getModel()")
            return self # Simplistic model mock
        def removeAllItems(self):
            self._items = []
        def addItem(self, item, pos):
            self._items.insert(pos, item)
        def getItemCount(self):
            return len(self._items)
        def selectItemPos(self, pos, select):
            if 0 <= pos < len(self._items):
                self._selected_pos = pos
        def getSelectedItemPos(self):
            return self._selected_pos
        def getSelectedItem(self):
            if 0 <= self._selected_pos < len(self._items):
                return self._items[self._selected_pos]
            return ""

    print("\n--- Mocking TejOCRService Initialization ---")
    mock_ctx = MockUnoContext()
    service = TejOCRService(mock_ctx)
    service.initialize((MockUnoStruct(Name="Frame", Value=MockFrame()),))

    print("\n--- Mocking Dispatch Call (OCR Selected Image) ---")
    mock_url_ocr_selected = MockUnoStruct(Complete="uno:org.libreoffice.TejOCR.OCRSelectedImage", Protocol="uno:", Path="org.libreoffice.TejOCR.OCRSelectedImage")
    # Simulate an image is selected for this test path
    original_is_selected = uno_utils.is_graphic_object_selected
    uno_utils.is_graphic_object_selected = lambda frame, ctx: True 
    service.dispatch(mock_url_ocr_selected, ())
    uno_utils.is_graphic_object_selected = original_is_selected # Restore

    print("\n--- Mocking Dispatch Call (Settings) ---")
    mock_url_settings = MockUnoStruct(Complete="uno:org.libreoffice.TejOCR.Settings", Protocol="uno:", Path="org.libreoffice.TejOCR.Settings")
    service.dispatch(mock_url_settings, ()) 