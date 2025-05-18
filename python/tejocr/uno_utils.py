# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Utility functions for interacting with LibreOffice UNO API and system tasks."""

import uno
import unohelper
import os
import tempfile
import shutil # For shutil.which
from tejocr import constants # For configuration node path
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext

# --- UNO Service Creation & Access ---
# Removed global SMGR cache to ensure context-specific service managers

def _get_service_manager(ctx):
    """Gets the ServiceManager from the provided component context.
    This function is intended for in-process UNO components.
    
    Args:
        ctx: The UNO component context
        
    Returns:
        The ServiceManager or None if ctx is None or getServiceManager() fails
    """
    if not ctx:
        print("ERROR: _get_service_manager called without a valid context.")
        return None
        
    try:
        smgr = ctx.getServiceManager()
        if not smgr:
            print("ERROR: ctx.getServiceManager() returned None.")
        return smgr
    except Exception as e:
        print(f"ERROR: Failed to get ServiceManager from context: {e}")
        return None

def create_instance(service_name, ctx):
    """Creates an instance of a UNO service using the provided component context."""
    if not ctx:
        print(f"ERROR: create_instance called for '{service_name}' without a valid UNO context.")
        return None

    try:
        # Get service manager directly from context for this specific call
        smgr = ctx.getServiceManager()
        if not smgr:
            print(f"ERROR: Could not get ServiceManager from the provided context for '{service_name}'.")
            return None
            
        return smgr.createInstanceWithContext(service_name, ctx)
    except Exception as e:
        print(f"ERROR: Failed to create instance of '{service_name}': {e}")
        return None

# --- UI Utilities ---
def show_message_box(title, message, type="infobox", parent_frame=None, ctx=None, buttons=None):
    """Displays a message box.
    type: "infobox", "warningbox", "errorbox", "querybox"
    buttons: UNO constant for buttons, e.g., com.sun.star.awt.MessageBoxButtons.BUTTONS_OK,
             com.sun.star.awt.MessageBoxButtons.BUTTONS_YES_NO_CANCEL, etc.
             If None, defaults to OK for infobox/warningbox/errorbox, or OK for querybox.
    Returns the result of box.execute() which can be compared against com.sun.star.awt.MessageBoxResults constants.
    """
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            print(f"show_message_box: {_('No ctx provided and uno.getComponentContext() failed. Cannot show:')} {title} - {message}")
            return None # Or a specific error code like -1

    parent_peer = None
    if parent_frame and hasattr(parent_frame, "getContainerWindow") and parent_frame.getContainerWindow():
        parent_peer = parent_frame.getContainerWindow().getPeer()
    elif ctx:
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if toolkit: # Check if toolkit was successfully created
            # Prefer getActiveTopWindow if available (newer API)
            if hasattr(toolkit, "getActiveTopWindow") and toolkit.getActiveTopWindow():
                 parent_peer = toolkit.getActiveTopWindow()
            elif hasattr(toolkit, "getDesktopWindow"): # Fallback to getDesktopWindow
                 parent_peer = toolkit.getDesktopWindow()

    # Determine MessageBoxType from string
    actual_box_type_str = "com.sun.star.awt.MessageBoxType.MESSAGEBOX" # Default
    if type.lower() == "infobox":
        actual_box_type_str = "com.sun.star.awt.MessageBoxType.INFOBOX"
    elif type.lower() == "warningbox":
        actual_box_type_str = "com.sun.star.awt.MessageBoxType.WARNINGBOX"
    elif type.lower() == "errorbox":
        actual_box_type_str = "com.sun.star.awt.MessageBoxType.ERRORBOX"
    elif type.lower() == "querybox":
        actual_box_type_str = "com.sun.star.awt.MessageBoxType.QUERYBOX"

    try:
        msg_type_enum = uno.getConstantByName(actual_box_type_str)
    except Exception:
        msg_type_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxType.MESSAGEBOX")


    # Determine buttons
    if buttons is None:
        if type.lower() == "querybox":
            # Default for querybox could be Yes/No if not specified, or just OK.
            # For our specific enhanced Tesseract prompt, we'll pass explicit buttons.
            # If used as a generic querybox without specific buttons, OK is a safe default.
            buttons_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK")
        else:
            buttons_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK")
    else:
        buttons_enum = buttons # Assume 'buttons' is already the UNO constant

    try:
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            print(f"show_message_box: {_('Failed to create Toolkit. Cannot show:')} {title} - {message}")
            # Consider a non-UNO fallback here if essential, e.g., logging to a file or console.
            return uno.getConstantByName("com.sun.star.awt.MessageBoxResults.CANCEL") # Simulate a cancel

        box = toolkit.createMessageBox(parent_peer, msg_type_enum, buttons_enum, str(title), str(message))
        return box.execute()
    except Exception as e:
        print(f"{_('Error showing message box')} '{title}': {e}")
        print(f"{_('MESSAGE BOX FALLBACK:')} {title} - {message}")
        # Return a value indicating failure, e.g., equivalent to Cancel or a custom error code.
        # Using MessageBoxResults.CANCEL makes sense as the operation was effectively cancelled.
        try:
            return uno.getConstantByName("com.sun.star.awt.MessageBoxResults.CANCEL")
        except Exception:
            return 0 # Fallback if even getting CANCEL constant fails.

def get_current_frame(ctx):
    """Gets the current desktop frame."""
    try:
        desktop = create_instance("com.sun.star.frame.Desktop", ctx)
        if desktop:
            return desktop.getCurrentFrame()
    except Exception as e:
        print(f"{_('Error getting current frame:')} {e}")
    return None

def is_graphic_object_selected(frame, ctx):
    """Checks if a graphic object is currently selected in the frame."""
    if not frame:
        return False
    try:
        controller = frame.getController()
        if not controller: return False
        selection = controller.getSelection()
        if not selection: return False

        # Check for TextGraphicObject (common for images in Writer)
        if selection.supportsService("com.sun.star.text.TextGraphicObject"):
            return True
        # Check for Shape (can be an image in a drawing shape)
        if selection.supportsService("com.sun.star.drawing.Shape") and \
           (hasattr(selection, "Graphic") or hasattr(selection, "GraphicURL")):
            return True
        # Check if it's a collection of shapes (e.g. grouped) and one is an image
        if selection.supportsService("com.sun.star.drawing.ShapeCollection") and selection.getCount() == 1:
            shape_in_collection = selection.getByIndex(0)
            if shape_in_collection.supportsService("com.sun.star.drawing.Shape") and \
               (hasattr(shape_in_collection, "Graphic") or hasattr(shape_in_collection, "GraphicURL")):
                return True
        # Add more checks if needed for other types of embedded objects that can be images
    except Exception as e:
        # print(f"Error checking selection: {e}")
        return False
    return False

# --- Configuration Utilities ---
_CONFIG_PROVIDER = None

def _get_config_provider(ctx):
    global _CONFIG_PROVIDER
    if _CONFIG_PROVIDER is None:
        _CONFIG_PROVIDER = create_instance("com.sun.star.configuration.ConfigurationProvider", ctx)
    return _CONFIG_PROVIDER

def _get_config_access(node_path, ctx, updatable=False):
    cp = _get_config_provider(ctx)
    if not cp:
        show_message_box(_("Configuration Error"), _("Cannot access ConfigurationProvider."), "errorbox", ctx=ctx)
        return None
    try:
        node_props = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        node_props.Name = "nodepath"
        node_props.Value = node_path
        params = (node_props,)
        service_name = "com.sun.star.configuration.ConfigurationUpdateAccess" if updatable else "com.sun.star.configuration.ConfigurationAccess"
        return cp.createInstanceWithArguments(service_name, params)
    except Exception as e:
        show_message_box(_("Configuration Error"), _("Cannot access configuration node {node_path}: {e}").format(node_path=node_path), "errorbox", ctx=ctx)
        return None

def get_setting(key, default_value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Reads a setting from TejOCR configuration."""
    full_node_path = f"org.libreoffice.Office.Addons/TejOCR.Configuration/{node}"
    config_access = _get_config_access(full_node_path, ctx)
    if config_access and hasattr(config_access, "getPropertyValue") and config_access.hasByName(key):
        try:
            return config_access.getPropertyValue(key)
        except Exception as e:
            # print(f"Error reading setting '{key}' from '{full_node_path}': {e}. Returning default.")
            return default_value
    return default_value

def set_setting(key, value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Writes a setting to TejOCR configuration."""
    full_node_path = f"org.libreoffice.Office.Addons/TejOCR.Configuration/{node}"
    config_update_access = _get_config_access(full_node_path, ctx, updatable=True)
    if config_update_access:
        try:
            config_update_access.setPropertyValue(key, value)
            config_update_access.commitChanges()
            return True
        except Exception as e:
            show_message_box(_("Configuration Error"), _("Cannot write setting '{key}' to '{full_node_path}': {e}").format(key=key, full_node_path=full_node_path), "errorbox", ctx=ctx)
            return False
    return False

# --- File/Path Utilities ---
def get_user_profile_path(ctx):
    """Gets the path to the user's LibreOffice profile directory."""
    path_sub = create_instance("com.sun.star.util.PathSubstitution", ctx)
    if path_sub:
        return unohelper.fileUrlToSystemPath(path_sub.getSubstituteVariableValue("$(user)"))
    return None

def get_user_temp_dir():
    """Gets the system's temporary directory."""
    return tempfile.gettempdir()

def create_temp_file(suffix=".tmp", prefix="tejocr_tmp_", dir=None):
    """Creates a temporary file and returns its path."""
    if dir is None:
        dir = get_user_temp_dir()
    try:
        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        os.close(fd) # Close the file handle, we just need the path
        return path
    except Exception as e:
        print(f"{_('Error creating temporary file:')} {e}")
        # Fallback if specific dir fails, try default temp location
        try:
            fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)
            return path
        except Exception as e_fallback:
            print(f"{_('Fallback temporary file creation also failed:')} {e_fallback}")
            return None

def find_tesseract_executable(configured_path="", ctx=None):
    """Finds the Tesseract executable.
    Checks configured_path, then system PATH.
    Returns the path if found, None otherwise.
    """
    # 1. Check configured path if provided
    if configured_path and os.path.isfile(configured_path) and os.access(configured_path, os.X_OK):
        return configured_path
    elif configured_path: # Path was configured but not valid
        msg = _("Configured Tesseract path is not a valid executable: {path}").format(path=configured_path)
        if ctx: show_message_box(_("Tesseract Path"), msg, "warningbox", ctx=ctx)
        else: print(f"Warning: {msg}")

    # 2. Check common names in system PATH
    common_names = ["tesseract"]
    if os.name == 'nt': # Windows
        common_names.append("tesseract.exe")
    
    for name in common_names:
        found_path = shutil.which(name)
        if found_path:
            return found_path
            
    # 3. (Optional for future) Check platform-specific common installation locations
    # macOS: /usr/local/bin/tesseract, /opt/homebrew/bin/tesseract
    # Linux: /usr/bin/tesseract
    # Windows: C:\Program Files\Tesseract-OCR\tesseract.exe
    platform_paths = []
    if os.name == 'posix': # Linux or macOS
        platform_paths.extend(["/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract", "/usr/bin/tesseract"])
    elif os.name == 'nt':
        pf = os.environ.get("ProgramFiles", "C:\\Program Files")
        pf_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        platform_paths.extend([
            os.path.join(pf, "Tesseract-OCR", "tesseract.exe"),
            os.path.join(pf_x86, "Tesseract-OCR", "tesseract.exe")
        ])
    
    for p_path in platform_paths:
        if os.path.isfile(p_path) and os.access(p_path, os.X_OK):
            return p_path

    return None

def get_graphic_from_selected_shape(shape):
    """Extracts XGraphic from a shape if possible."""
    if not shape: return None
    try:
        # Case 1: Shape itself has a Graphic property (e.g. GraphicObjectShape)
        if hasattr(shape, "Graphic") and shape.Graphic is not None:
            return shape.Graphic
        
        # Case 2: Shape has a GraphicURL and we need to load it via GraphicProvider
        # This is more complex if the URL is internal (e.g. "private:graphicrepository/...")
        # For simplicity, we assume if Graphic is not directly there, it might be harder to get
        # without knowing the context (document, graphic provider instance etc.)
        # The tejocr_engine._get_image_from_selection uses GraphicProvider separately
        # if it gets a graphic URL.
        # print(f"Shape type: {shape.ShapeType}") # For debugging
        if hasattr(shape, "GraphicURL") and shape.GraphicURL not in [None, ""]:
            # This indicates an image, but getting the XGraphic object from URL needs a provider
            # For now, this utility focuses on direct XGraphic access. The engine handles URL loading.
            # print(f"Shape has GraphicURL: {shape.GraphicURL}. XGraphic extraction from URL is handled by engine.")
            pass

        # Case 3: Shape is a container or has other ways to get graphic (e.g. DrawPage shapes)
        # This can be expanded based on specific shape types encountered.
    except Exception as e:
        print(f"Error getting graphic from shape: {e}")
    return None


# --- Logging Setup (Placeholder, to be expanded) ---
_TEJOCR_LOGGER = None

def get_logger(name="TejOCR"):
    global _TEJOCR_LOGGER
    if _TEJOCR_LOGGER is None:
        # This is a very basic setup. Real setup would handle levels, formatters, file rotation etc.
        import logging
        _TEJOCR_LOGGER = logging.getLogger(name)
        if not _TEJOCR_LOGGER.handlers: # Setup handler only if not already configured
            log_dir = None
            log_file_path = None
            try:
                # Try to get user profile for log storage (preferred)
                # Need a context for get_user_profile_path. If called early without ctx, this might fail.
                # For now, let's assume it might be called without ctx and fallback.
                # This part is tricky as logger setup ideally happens once with a context.
                # A better approach is to have an init_logging(ctx) function called by the service.
                
                # Simple fallback for now if this util is called without ctx during logger setup:
                log_dir = os.path.join(get_user_temp_dir(), "TejOCRLogs")
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                log_file_path = os.path.join(log_dir, constants.LOG_FILE_NAME)
            except Exception as e_logpath:
                print(f"{_('Error determining log path:')} {e_logpath}. {_('Using default temp dir.')}")
                log_file_path = os.path.join(get_user_temp_dir(), constants.LOG_FILE_NAME)

            handler = logging.FileHandler(log_file_path, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            _TEJOCR_LOGGER.addHandler(handler)
            _TEJOCR_LOGGER.setLevel(logging.INFO) # Default level, can be made configurable
            _TEJOCR_LOGGER.info("TejOCR Logger initialized. Log file: %s", log_file_path)
        # else:
        #     _TEJOCR_LOGGER.info("TejOCR Logger already initialized.")

    return _TEJOCR_LOGGER


if __name__ == "__main__":
    # This part is for basic, non-UNO testing of some utils
    print(_("uno_utils.py: For testing non-UNO functions or with mock UNO context."))
    
    # Test find_tesseract_executable
    print(_("\nTesting Tesseract executable finder:"))
    tess_path = find_tesseract_executable()
    if tess_path:
        print(f"  {_('Found Tesseract at:')} {tess_path}")
    else:
        print(_("  Tesseract not found in PATH or common locations."))
    # Test with a dummy configured path
    find_tesseract_executable("/dummy/path/to/tesseract") 

    # Test temp file creation
    print(_("\nTesting temp file creation:"))
    tmp_file = create_temp_file(suffix=".txt", prefix="test_util_")
    if tmp_file and os.path.exists(tmp_file):
        print(f"  {_('Created temp file:')} {tmp_file}")
        os.remove(tmp_file)
        print(f"  {_('Removed temp file:')} {tmp_file}")
    else:
        print(f"  {_('Failed to create temp file or it does not exist:')} {tmp_file}")

    # Test logger (basic, will log to temp dir)
    print(_("\nTesting logger initialization (will log to a file in temp dir):"))
    logger = get_logger("TejOCR.TestUtil")
    logger.info("This is an informational message from uno_utils self-test.")
    logger.warning("This is a warning message from uno_utils self-test.")
    logger.error("This is an error message from uno_utils self-test.")
    print(_("  Logger test messages sent. Check log file for 'TejOCR.TestUtil' entries."))

    # Cannot test UNO-dependent functions (create_instance, show_message_box, config, etc.)
    # without a running LibreOffice instance and proper context.
    print(_("\nUNO-dependent functions require a LibreOffice environment to test.")) 