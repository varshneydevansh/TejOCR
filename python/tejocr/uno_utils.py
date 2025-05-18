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
import logging # Ensure logging is imported at the top
from tejocr import constants # For configuration node path
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext

# --- Logging Setup ---
# Centralized logger definition for the module
# This needs to be defined *before* it's used at the module level
_loggers = {}

def get_logger(name="TejOCR"):
    """Gets a configured logger instance.
       Manages a dictionary of loggers to avoid re-configuration.
    """
    if name in _loggers:
        return _loggers[name]
    
    try:
        # Standard library logging
        user_temp_dir = tempfile.gettempdir()
        # Use a more specific log file name for clarity
        log_file_path = os.path.join(user_temp_dir, f"{name.replace('.', '_')}_extension.log")
        
        # Create logger
        logger_instance = logging.getLogger(name)
        logger_instance.setLevel(logging.DEBUG) # Set desired minimum level
        
        # Create file handler if not already present for this logger to avoid duplicates
        # Check by handler type and baseFilename to be more specific
        has_file_handler = False
        for h in logger_instance.handlers:
            if isinstance(h, logging.FileHandler) and h.baseFilename == log_file_path:
                has_file_handler = True
                break
        
        if not has_file_handler:
            # 'w' mode overwrites the log file on each LO start for cleaner debugging sessions.
            # Use 'a' if you prefer to append.
            fh = logging.FileHandler(log_file_path, encoding='utf-8', mode='w') 
            fh.setLevel(logging.DEBUG) # Level for this handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
            fh.setFormatter(formatter)
            logger_instance.addHandler(fh)
            # Initial log message via the handler itself to confirm it's working.
            # Avoid calling logger_instance.info() here if it might re-enter get_logger via another module
            # before this instance is stored in _loggers. Direct print or handler log is safer for bootstrap.
            print(f"INFO: Logger '{name}' FileHandler configured. Logging to: {log_file_path}")
        
        _loggers[name] = logger_instance
        return logger_instance
    
    except Exception as e_log_setup:
        # Fallback to print if logger setup fails catastrophically
        print(f"CRITICAL ERROR: Failed to setup logger '{name}'. Reason: {e_log_setup}")
        # Return a dummy logger that does nothing or prints, to avoid NoneErrors
        class PrintLogger:
            def _log(self, level, msg, *args, **kwargs):
                exc_info = kwargs.pop('exc_info', False)
                message = f"{level}: {name} ({kwargs.get('module','unknown')}.{kwargs.get('funcName','unknown')}:{kwargs.get('lineno','unknown')}): {msg}"
                if args:
                    message = message % args
                print(message)
                if exc_info:
                    import traceback
                    traceback.print_exc()

            def info(self, msg, *args, **kwargs): self._log("INFO", msg, *args, **kwargs)
            def debug(self, msg, *args, **kwargs): self._log("DEBUG", msg, *args, **kwargs)
            def warning(self, msg, *args, **kwargs): self._log("WARNING", msg, *args, **kwargs)
            def error(self, msg, *args, **kwargs): self._log("ERROR", msg, *args, **kwargs)
            def critical(self, msg, *args, **kwargs): self._log("CRITICAL", msg, *args, **kwargs)

        # Ensure the dummy logger is also stored to prevent re-attempting setup on every call for this name
        _loggers[name] = PrintLogger()
        return _loggers[name]

# Initialize the module-level logger *after* get_logger is defined.
# This is the primary logger for this module's own operations.
logger = get_logger("TejOCR.uno_utils") 
logger.info("uno_utils.py: Module loaded and logger initialized.")


# --- UNO Service Creation & Access ---
# Removed global SMGR cache to ensure context-specific service managers
# logger = get_logger("TejOCR.uno_utils") # This was the problematic line, now logger is initialized above.

def _get_service_manager(ctx):
    """Gets the ServiceManager from the provided component context.
    This function is intended for in-process UNO components.
    
    Args:
        ctx: The UNO component context
        
    Returns:
        The ServiceManager or None if ctx is None or getServiceManager() fails
    """
    if not ctx:
        logger.error("_get_service_manager called without a valid context.")
        return None
        
    try:
        smgr = ctx.getServiceManager()
        if not smgr:
            logger.error("ctx.getServiceManager() returned None.")
        return smgr
    except Exception as e:
        logger.error(f"Failed to get ServiceManager from context: {e}", exc_info=True)
        return None

def create_instance(service_name, ctx):
    """Creates an instance of a UNO service using the provided component context."""
    if not ctx:
        logger.error(f"create_instance called for '{service_name}' without a valid UNO context.")
        return None

    try:
        # Get service manager directly from context for this specific call
        smgr = ctx.getServiceManager() # Assuming _get_service_manager is not needed here, direct call
        if not smgr:
            logger.error(f"Could not get ServiceManager from the provided context for '{service_name}'.")
            return None
            
        return smgr.createInstanceWithContext(service_name, ctx)
    except Exception as e:
        logger.error(f"Failed to create instance of '{service_name}': {e}", exc_info=True)
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
            logger.warning(f"show_message_box: {_('No ctx provided and uno.getComponentContext() failed. Cannot show:')} {title} - {message}")
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
            else: # If no window can be found
                logger.debug("show_message_box: Toolkit created but no suitable window found (getActiveTopWindow/getDesktopWindow).")

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
            logger.error(f"show_message_box: {_('Failed to create Toolkit. Cannot show:')} {title} - {message}")
            # Consider a non-UNO fallback here if essential, e.g., logging to a file or console.
            return uno.getConstantByName("com.sun.star.awt.MessageBoxResults.CANCEL") # Simulate a cancel

        box = toolkit.createMessageBox(parent_peer, msg_type_enum, buttons_enum, str(title), str(message))
        return box.execute()
    except Exception as e:
        logger.error(f"{_('Error showing message box')} '{title}': {e}", exc_info=True)
        # Fallback message using print if logger itself fails or to ensure visibility during critical errors
        print(f"MESSAGE BOX FALLBACK (ERROR): {title} - {message} - Exception: {e}")
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
        logger.error(f"{_('Error getting current frame:')} {e}", exc_info=True)
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
           (hasattr(selection, "Graphic") or hasattr(selection, "GraphicURL") or (hasattr(selection, "ShapeType") and selection.ShapeType == "com.sun.star.drawing.GraphicObjectShape")) : # Added GraphicObjectShape check
            return True
        # Check if it's a collection of shapes (e.g. grouped) and one is an image
        if selection.supportsService("com.sun.star.drawing.ShapeCollection") and selection.getCount() >= 1: # Allow for multiple shapes, check first
            # Iterate through shapes in collection if necessary, for now, check first as before
            # For simplicity, if any shape in a selection of one is an image, it's true.
            # A more robust check might iterate if getCount() > 1
            if selection.getCount() == 1:
                shape_in_collection = selection.getByIndex(0)
                if shape_in_collection.supportsService("com.sun.star.drawing.Shape") and \
                   (hasattr(shape_in_collection, "Graphic") or hasattr(shape_in_collection, "GraphicURL") or \
                    (hasattr(shape_in_collection, "ShapeType") and shape_in_collection.ShapeType == "com.sun.star.drawing.GraphicObjectShape")):
                    return True
        # Add more checks if needed for other types of embedded objects that can be images
    except Exception as e:
        logger.debug(f"Error or non-graphic selection in is_graphic_object_selected: {e}", exc_info=False) # Debug level, as this can be common
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
        # show_message_box(_("Configuration Error"), _("Cannot access ConfigurationProvider."), "errorbox", ctx=ctx)
        logger.error("Cannot access ConfigurationProvider for _get_config_access.")
        return None
    try:
        node_props = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        node_props.Name = "nodepath"
        node_props.Value = node_path
        params = (node_props,)
        service_name = "com.sun.star.configuration.ConfigurationUpdateAccess" if updatable else "com.sun.star.configuration.ConfigurationAccess"
        return cp.createInstanceWithArguments(service_name, params)
    except Exception as e:
        # show_message_box(_("Configuration Error"), _("Cannot access configuration node {node_path}: {e}").format(node_path=node_path), "errorbox", ctx=ctx)
        logger.error(f"Cannot access configuration node {node_path}: {e}", exc_info=True)
        return None

def get_setting(key, default_value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Reads a setting from TejOCR configuration."""
    full_node_path = f"org.libreoffice.Office.Addons/TejOCR.Configuration/{node}"
    config_access = _get_config_access(full_node_path, ctx)
    if config_access and hasattr(config_access, "getPropertyValue") and config_access.hasByName(key):
        try:
            return config_access.getPropertyValue(key)
        except Exception as e:
            logger.warning(f"Error reading setting '{key}' from '{full_node_path}': {e}. Returning default.", exc_info=True)
            return default_value
    # logger.debug(f"Setting '{key}' not found or config_access failed for node '{full_node_path}'. Returning default.")
    return default_value

def set_setting(key, value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Writes a setting to TejOCR configuration."""
    full_node_path = f"org.libreoffice.Office.Addons/TejOCR.Configuration/{node}"
    config_update_access = _get_config_access(full_node_path, ctx, updatable=True)
    if config_update_access:
        try:
            config_update_access.setPropertyValue(key, value)
            config_update_access.commitChanges()
            # logger.debug(f"Setting '{key}' to '{value}' in '{full_node_path}' successful.")
            return True
        except Exception as e:
            # show_message_box(_("Configuration Error"), _("Cannot write setting '{key}' to '{full_node_path}': {e}").format(key=key, full_node_path=full_node_path), "errorbox", ctx=ctx)
            logger.error(f"Cannot write setting '{key}' to '{full_node_path}': {e}", exc_info=True)
            return False
    # logger.warning(f"Failed to get config_update_access for node '{full_node_path}' when trying to set '{key}'.")
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

def create_temp_file_from_graphic(graphic, ctx):
    # Ensure create_temp_file is defined or imported if it's from this module or another
    path = create_temp_file(suffix=".png") # Assuming create_temp_file is in this module
    if not path:
        logger.error("Failed to create a temporary file name.")
        return None
    
    try:
        # Create a GraphicExporter
        exporter = create_instance("com.sun.star.drawing.GraphicExporter", ctx)
        if not exporter:
            logger.error("Failed to create GraphicExporter instance.")
            return None
        
        # Set the source graphic for the exporter
        props = (uno.createUnoStruct("com.sun.star.beans.PropertyValue"),)
        props[0].Name = "Graphic"
        props[0].Value = graphic
        exporter.setSource(props)
        
        # Prepare properties for export (export to PNG)
        export_props = (uno.createUnoStruct("com.sun.star.beans.PropertyValue"),
                        uno.createUnoStruct("com.sun.star.beans.PropertyValue"))
        export_props[0].Name = "URL"
        export_props[0].Value = unohelper.systemPathToFileUrl(path)
        export_props[1].Name = "MimeType"
        export_props[1].Value = "image/png"
        
        # Filter the export
        exporter.filter(export_props)
        logger.info(f"Graphic exported successfully to: {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to export graphic to PNG: {e}", exc_info=True)
        if os.path.exists(path):
            try:
                os.remove(path) # Clean up partially created file
            except OSError as oe:
                logger.error(f"Error cleaning up temporary file {path}: {oe}")
        return None
    
def get_graphic_from_selection(selection, ctx):
    """Extracts graphic object from selection. Supports TextGraphicObject and GraphicObjectShape."""
    graphic = None
    # Check if the selection itself is a TextGraphicObject
    if selection.supportsService("com.sun.star.text.TextGraphicObject"):
        graphic = selection.Graphic
        logger.debug("Found TextGraphicObject in selection.")
    # Check if the selection is a Shape and that shape is a GraphicObjectShape
    elif selection.supportsService("com.sun.star.drawing.Shape") and \
         hasattr(selection, 'ShapeType') and selection.ShapeType == 'com.sun.star.drawing.GraphicObjectShape':
        graphic = selection.Graphic
        logger.debug("Found GraphicObjectShape in selection.")
    # If it's a ShapeCollection, iterate and check for GraphicObjectShape
    elif selection.supportsService("com.sun.star.drawing.ShapeCollection"):
        logger.debug(f"Selection is a ShapeCollection with {selection.getCount()} elements.")
        for i in range(selection.getCount()):
            shape = selection.getByIndex(i)
            if shape.supportsService("com.sun.star.drawing.Shape") and \
               hasattr(shape, 'ShapeType') and shape.ShapeType == 'com.sun.star.drawing.GraphicObjectShape':
                graphic = shape.Graphic
                logger.debug(f"Found GraphicObjectShape at index {i} in ShapeCollection.")
                break # Use the first one found
            elif shape.supportsService("com.sun.star.text.TextGraphicObject"):
                 graphic = shape.Graphic # This case might be less common for ShapeCollection but check
                 logger.debug(f"Found TextGraphicObject at index {i} in ShapeCollection (less common). ")
                 break
    else:
        logger.debug("Selection is not a recognized graphic type for direct extraction.")
    
    if graphic is None:
        logger.warning("Could not extract graphic from selection.")
        
    return graphic


# --- System Utilities ---

def find_tesseract_executable(configured_path="", ctx=None):
    """Tries to find the Tesseract OCR executable.
    1. Checks the configured_path if provided.
    2. Checks common system PATH locations.
    Returns the path to the executable or None if not found.
    """
    # module_logger.debug(f"Searching for Tesseract. Configured path: '{configured_path}'")
    if configured_path and os.path.isfile(configured_path):
        # module_logger.debug(f"Tesseract found at configured path: {configured_path}")
        return configured_path
    
    # shutil.which checks the system's PATH environment variable.
    found_path = shutil.which("tesseract")
    if found_path:
        # module_logger.debug(f"Tesseract found in PATH: {found_path}")
        return found_path
    
    # module_logger.warning("Tesseract executable not found in configured path or system PATH.")
    return None


# --- Helper for graphic extraction from selected shape (if it's a drawing object) ---
def get_graphic_from_selected_shape(shape):
    """Retrieves the XGraphic object from a selected shape if it contains one."""
    if not shape: return None
    # Common case: Shape is a GraphicObject (e.g., image inserted via Insert > Image)
    if shape.supportsService("com.sun.star.drawing.GraphicObjectShape"):
        return shape.Graphic
    # Less common: Shape has a GraphicURL (e.g. linked image, or some complex shapes)
    # This might need conversion or further handling if it's just a URL.
    # For direct graphic data, .Graphic is usually the property.
    if hasattr(shape, "Graphic") and shape.Graphic:
        return shape.Graphic
    # Some shapes might have a FillBitmapURL or similar properties if they are filled with an image
    # This requires more complex handling to get an XGraphic object.
    # For now, focusing on direct .Graphic property.
    return None


# Initialize a global logger for the module. This is tricky because get_logger might not yet be fully defined
# when this line is executed if it's in the same file and has dependencies not yet processed.
# It's generally safer to call get_logger() from within functions after module initialization is complete,
# or ensure get_logger is defined early and has no complex dependencies.

# Centralized logger definition for the module
# This needs to be defined *before* it's used at the module level (like for `logger` instance above)
# or by other functions in this module if they don't get their own logger.

# Simplistic get_logger for now, can be expanded later
_loggers = {}

def get_logger(name="TejOCR"):
    """Gets a configured logger instance.
       Manages a dictionary of loggers to avoid re-configuration.
    """
    if name in _loggers:
        return _loggers[name]
    
    try:
        # Standard library logging
        import logging
        import tempfile # For default log file path
        import os # For path joining
        
        user_temp_dir = tempfile.gettempdir()
        log_file_path = os.path.join(user_temp_dir, "tejocr_extension.log")
        
        # Create logger
        logger_instance = logging.getLogger(name)
        logger_instance.setLevel(logging.DEBUG) # Set desired minimum level
        
        # Create file handler if not already present for this logger
        # This check prevents adding multiple handlers if get_logger is called multiple times for the same name
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file_path for h in logger_instance.handlers):
            fh = logging.FileHandler(log_file_path, encoding='utf-8')
            fh.setLevel(logging.DEBUG) # Level for this handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
            fh.setFormatter(formatter)
            logger_instance.addHandler(fh)
            logger_instance.info(f"FileHandler added. Logging to: {log_file_path}") # Log initialization
        
        # Optional: Console handler for immediate feedback during development if LO console shows it
        # if not any(isinstance(h, logging.StreamHandler) for h in logger_instance.handlers):
        #     ch = logging.StreamHandler()
        #     ch.setLevel(logging.DEBUG)
        #     ch.setFormatter(formatter)
        #     logger_instance.addHandler(ch)
        #     logger_instance.info("StreamHandler added for console output.")
        
        _loggers[name] = logger_instance
        return logger_instance
    
    except Exception as e_log_setup:
        # Fallback to print if logger setup fails catastrophically
        print(f"CRITICAL ERROR: Failed to setup logger '{name}'. Reason: {e_log_setup}")
        # Return a dummy logger that does nothing or prints, to avoid NoneErrors
        class PrintLogger:
            def info(self, msg, *args, **kwargs): print(f"INFO: {name}: {msg}")
            def debug(self, msg, *args, **kwargs): print(f"DEBUG: {name}: {msg}")
            def warning(self, msg, *args, **kwargs): print(f"WARNING: {name}: {msg}")
            def error(self, msg, *args, **kwargs): print(f"ERROR: {name}: {msg}")
            def critical(self, msg, *args, **kwargs): print(f"CRITICAL: {name}: {msg}")
        return PrintLogger()

# Initialize the module-level logger *after* get_logger is defined.
logger = get_logger("TejOCR.uno_utils_module_scope") # Renamed to avoid conflict with local 'logger' vars


print("DEBUG: uno_utils.py: Module loaded, logger should be available.") # For load confirmation