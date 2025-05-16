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
from . import constants # For configuration node path

# --- UNO Service Creation & Access ---
SMGR = None

def _get_service_manager(ctx=None):
    global SMGR
    if SMGR is None:
        if ctx is None:
            # Try to get a default context (e.g., from a running office instance)
            # This is a simplified approach; robust context acquisition might be more complex outside a service.
            try:
                resolver = uno.getComponentContext().getServiceManager().createInstanceWithContext(
                    "com.sun.star.bridge.UnoUrlResolver", uno.getComponentContext())
                SMGR = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ServiceManager")
                if SMGR is None:
                    raise Exception("Failed to resolve ServiceManager via UnoUrlResolver")
            except Exception as e:
                # Fallback for scripts not running in a context that can resolve like above
                # (e.g. macro context where ctx is passed directly)
                # This path is less likely to be hit if ctx is always provided where needed.
                print(f"_get_service_manager: Error getting default context/SM via resolver: {e}. Requires ctx.")
                # In a real extension, ctx should always be available from __init__ or initialize
                # If this error occurs, it means a function needing SMGR was called without ctx.
                return None # Cannot proceed without a context in this case
        else:
            SMGR = ctx.getServiceManager()
    return SMGR

def create_instance(service_name, ctx):
    """Creates an instance of a UNO service."""
    smgr = _get_service_manager(ctx)
    if not smgr:
        # print(f"Error: ServiceManager not available, cannot create instance of {service_name}")
        # Fallback to component context if ctx is available and smgr somehow failed.
        if ctx:
            try:
                return ctx.getServiceManager().createInstanceWithContext(service_name, ctx)
            except Exception as e_ctx_smgr:
                print(f"Error creating {service_name} via ctx.getServiceManager(): {e_ctx_smgr}")
                return None
        return None
    return smgr.createInstanceWithContext(service_name, ctx)

# --- UI Utilities ---
def show_message_box(title, message, type="infobox", parent_frame=None, ctx=None):
    """Displays a message box.
    type: "infobox", "warningbox", "errorbox", "querybox"
    """
    if ctx is None:
        # Try to get a component context if None is provided (e.g. for simple script calls)
        try:
            ctx = uno.getComponentContext()
        except Exception:
            print(f"show_message_box: No ctx provided and uno.getComponentContext() failed. Cannot show: {title} - {message}")
            return None # Cannot show message box without context

    parent_peer = None
    if parent_frame and hasattr(parent_frame, "getContainerWindow") and parent_frame.getContainerWindow():
        parent_peer = parent_frame.getContainerWindow().getPeer()
    elif ctx: # Fallback if no frame, try to get a default parent from toolkit
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if toolkit and hasattr(toolkit, "getDesktopWindow"): # getTopWindow is older API
            parent_peer = toolkit.getDesktopWindow()

    box_type_map = {
        "infobox": constants.DIALOG_MODAL_DEPENDENT,
        "warningbox": constants.DIALOG_MODAL_DEPENDENT,
        "errorbox": constants.DIALOG_MODAL_DEPENDENT,
        "querybox": constants.DIALOG_MODAL_DEPENDENT # querybox typically needs button choices
    }
    # Actual service names for message box types
    service_type_map = {
        "infobox": "com.sun.star.awt.MessageBoxType.INFOBOX",
        "warningbox": "com.sun.star.awt.MessageBoxType.WARNINGBOX",
        "errorbox": "com.sun.star.awt.MessageBoxType.ERRORBOX",
        "querybox": "com.sun.star.awt.MessageBoxType.QUERYBOX"
    }
    msg_type = getattr(uno.getConstantByName(service_type_map.get(type.lower(), "com.sun.star.awt.MessageBoxType.MESSAGEBOX")), "value", 1) # Default to simple MESSAGEBOX if type invalid

    try:
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            print(f"show_message_box: Failed to create Toolkit. Cannot show: {title} - {message}")
            return None
            
        # Buttons: 1 for OK. For querybox, might be (e.g.) com.sun.star.awt.MessageBoxButtons.BUTTONS_YES_NO_CANCEL
        buttons = 1 # Default to OK button
        # TODO: Make buttons configurable if querybox is used more extensively

        box = toolkit.createMessageBox(parent_peer, msg_type, buttons, str(title), str(message))
        return box.execute()
    except Exception as e:
        print(f"Error showing message box '{title}': {e}")
        # Fallback to console if UI fails catastrophically
        print(f"MESSAGE BOX FALLBACK: {title} - {message}")
        return None

def get_current_frame(ctx):
    """Gets the current desktop frame."""
    try:
        desktop = create_instance("com.sun.star.frame.Desktop", ctx)
        if desktop:
            return desktop.getCurrentFrame()
    except Exception as e:
        print(f"Error getting current frame: {e}")
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
        show_message_box("Configuration Error", "Cannot access ConfigurationProvider.", "errorbox", ctx=ctx)
        return None
    try:
        node_props = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        node_props.Name = "nodepath"
        node_props.Value = node_path
        params = (node_props,)
        service_name = "com.sun.star.configuration.ConfigurationUpdateAccess" if updatable else "com.sun.star.configuration.ConfigurationAccess"
        return cp.createInstanceWithArguments(service_name, params)
    except Exception as e:
        show_message_box("Configuration Error", f"Cannot access configuration node {node_path}: {e}", "errorbox", ctx=ctx)
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
            show_message_box("Configuration Error", f"Cannot write setting '{key}' to '{full_node_path}': {e}", "errorbox", ctx=ctx)
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
        print(f"Error creating temporary file: {e}")
        # Fallback if specific dir fails, try default temp location
        try:
            fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)
            return path
        except Exception as e_fallback:
            print(f"Fallback temporary file creation also failed: {e_fallback}")
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
        if ctx: show_message_box("Tesseract Path", f"Configured Tesseract path is not a valid executable: {configured_path}", "warningbox", ctx=ctx)
        else: print(f"Warning: Configured Tesseract path is not valid: {configured_path}")

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
                print(f"Error determining log path: {e_logpath}. Using default temp dir.")
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
    print("uno_utils.py: For testing non-UNO functions or with mock UNO context.")
    
    # Test find_tesseract_executable
    print("\nTesting Tesseract executable finder:")
    tess_path = find_tesseract_executable()
    if tess_path:
        print(f"  Found Tesseract at: {tess_path}")
    else:
        print("  Tesseract not found in PATH or common locations.")
    # Test with a dummy configured path
    find_tesseract_executable("/dummy/path/to/tesseract") 

    # Test temp file creation
    print("\nTesting temp file creation:")
    tmp_file = create_temp_file(suffix=".txt", prefix="test_util_")
    if tmp_file and os.path.exists(tmp_file):
        print(f"  Created temp file: {tmp_file}")
        os.remove(tmp_file)
        print(f"  Removed temp file: {tmp_file}")
    else:
        print(f"  Failed to create temp file or it does not exist: {tmp_file}")

    # Test logger (basic, will log to temp dir)
    print("\nTesting logger initialization (will log to a file in temp dir):")
    logger = get_logger("TejOCR.TestUtil")
    logger.info("This is an informational message from uno_utils self-test.")
    logger.warning("This is a warning message from uno_utils self-test.")
    logger.error("This is an error message from uno_utils self-test.")
    print(f"  Logger test messages sent. Check log file for 'TejOCR.TestUtil' entries.")

    # Cannot test UNO-dependent functions (create_instance, show_message_box, config, etc.)
    # without a running LibreOffice instance and proper context.
    print("\nUNO-dependent functions require a LibreOffice environment to test.") 