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
        # Create a separate logs directory under the temp directory
        log_dir = os.path.join(user_temp_dir, "TejOCRLogs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Use a clear log file name
        log_file_path = os.path.join(log_dir, "tejocr.log")
        
        # Create logger
        logger_instance = logging.getLogger(name)
        logger_instance.setLevel(logging.DEBUG) # Set desired minimum level
        
        # Create file handler if not already present for this logger to avoid duplicates
        has_file_handler = False
        has_console_handler = False
        for h in logger_instance.handlers:
            if isinstance(h, logging.FileHandler):
                has_file_handler = True
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                has_console_handler = True
        
        if not has_file_handler:
            # 'a' mode appends to the log file instead of overwriting
            fh = logging.FileHandler(log_file_path, encoding='utf-8', mode='a') 
            fh.setLevel(logging.DEBUG) # Level for this handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
            fh.setFormatter(formatter)
            logger_instance.addHandler(fh)
            print(f"INFO: Logger '{name}' FileHandler configured. Logging to: {log_file_path}")
        
        # Add a console handler for debugging (visible in terminal output)
        if not has_console_handler:
            console = logging.StreamHandler()
            console.setLevel(logging.DEBUG)
            console_formatter = logging.Formatter('>>> %(name)s - %(levelname)s: %(message)s')
            console.setFormatter(console_formatter)
            logger_instance.addHandler(console)
            print(f"INFO: Logger '{name}' ConsoleHandler added")
        
        # Log the initialization as confirmation
        logger_instance.info(f"TejOCR Logger initialized. Log file: {log_file_path}")
        
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
            print(f"MESSAGE BOX (CONSOLE FALLBACK - NO CONTEXT): {title} - {message}")
            return None # Or a specific error code like -1

    parent_peer = None
    
    # Safe extraction of parent peer
    if parent_frame:
        try:
            container_window = parent_frame.getContainerWindow()
            if container_window and hasattr(container_window, 'getPeer'):
                parent_peer = container_window.getPeer()
                logger.debug("show_message_box: Got parent_peer from parent_frame")
            else:
                logger.debug("show_message_box: parent_frame has no valid container window or getPeer method")
        except Exception as e:
            logger.debug(f"show_message_box: Error getting parent peer from parent_frame: {e}")
    
    # Fallback parent peer strategies
    if not parent_peer and ctx:
        try:
            toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
            if toolkit: # Check if toolkit was successfully created
                # Prefer getActiveTopWindow if available (newer API)
                try:
                    if hasattr(toolkit, "getActiveTopWindow"):
                        active_window = toolkit.getActiveTopWindow()
                        if active_window:
                            parent_peer = active_window
                            logger.debug("show_message_box: Got parent_peer from toolkit.getActiveTopWindow")
                except Exception as e:
                    logger.debug(f"show_message_box: getActiveTopWindow failed: {e}")
                
                # Fallback to getDesktopWindow
                if not parent_peer:
                    try:
                        if hasattr(toolkit, "getDesktopWindow"):
                            desktop_window = toolkit.getDesktopWindow()
                            if desktop_window:
                                parent_peer = desktop_window
                                logger.debug("show_message_box: Got parent_peer from toolkit.getDesktopWindow")
                    except Exception as e:
                        logger.debug(f"show_message_box: getDesktopWindow failed: {e}")
                        
                if not parent_peer:
                    logger.debug("show_message_box: Toolkit created but no suitable window found")
        except Exception as e:
            logger.debug(f"show_message_box: Error creating toolkit for parent peer: {e}")

    # Determine MessageBoxType dynamically
    box_type_str_map = {
        "infobox": "INFOBOX",
        "warningbox": "WARNINGBOX",
        "errorbox": "ERRORBOX",
        "querybox": "QUERYBOX",
        "messagebox": "MESSAGEBOX" # Default
    }
    msg_box_type_name = box_type_str_map.get(type.lower(), "MESSAGEBOX")
    actual_box_type_constant_str = f"com.sun.star.awt.MessageBoxType.{msg_box_type_name}"

    try:
        msg_type_enum = uno.getConstantByName(actual_box_type_constant_str)
    except Exception:
        logger.warning(f"Failed to get MessageBoxType constant '{actual_box_type_constant_str}'. Falling back to MESSAGEBOX.")
        try:
            msg_type_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxType.MESSAGEBOX")
        except Exception:
            # Ultimate fallback to numeric value
            msg_type_enum = 4  # MESSAGEBOX
            logger.warning("Using numeric fallback for MessageBoxType")

    # Determine buttons dynamically
    if isinstance(buttons, str):
        button_str_map = {
            "ok": "BUTTONS_OK",
            "ok_cancel": "BUTTONS_OK_CANCEL",
            "yes_no": "BUTTONS_YES_NO",
            "yes_no_cancel": "BUTTONS_YES_NO_CANCEL",
            "retry_cancel": "BUTTONS_RETRY_CANCEL",
            "abort_retry_ignore": "BUTTONS_ABORT_RETRY_IGNORE"
        }
        btn_name = button_str_map.get(buttons.lower(), "BUTTONS_OK")
        buttons_constant_str = f"com.sun.star.awt.MessageBoxButtons.{btn_name}"
        try:
            buttons_enum = uno.getConstantByName(buttons_constant_str)
        except Exception:
            logger.warning(f"Failed to get MessageBoxButtons constant '{buttons_constant_str}'. Falling back to BUTTONS_OK.")
            try:
                buttons_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK")
            except Exception:
                buttons_enum = 1  # BUTTONS_OK numeric fallback
    elif buttons is None: # Default to OK if not specified
        try:
            buttons_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK")
        except Exception:
            buttons_enum = 1  # BUTTONS_OK numeric fallback
    else: # Assume 'buttons' is already the UNO constant
        buttons_enum = buttons
        
    msg_result_cancel_enum = 0 # Default return for error/cancel
    try:
        msg_result_cancel_enum = uno.getConstantByName("com.sun.star.awt.MessageBoxResults.CANCEL")
    except Exception:
        logger.warning("Failed to get MessageBoxResults.CANCEL constant. Using 0 as fallback for cancel.")

    try:
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error(f"show_message_box: {_('Failed to create Toolkit (second attempt). Cannot show:')} {title} - {message}")
            print(f"MESSAGE BOX (CONSOLE FALLBACK - TOOLKIT FAIL): {title} - {message}")
            return msg_result_cancel_enum

        box = toolkit.createMessageBox(parent_peer, msg_type_enum, buttons_enum, str(title), str(message))
        if not box:
            logger.error(f"show_message_box: toolkit.createMessageBox returned None for: {title} - {message}")
            print(f"MESSAGE BOX (CONSOLE FALLBACK - CREATE FAIL): {title} - {message}")
            return msg_result_cancel_enum
            
        return box.execute()
    except Exception as e:
        logger.error(f"show_message_box: Exception during create/execute: {e} for {title} - {message}", exc_info=True)
        print(f"MESSAGE BOX (CONSOLE FALLBACK - EXECUTE ERROR): {title} - {message} - Exception: {e}")
        return msg_result_cancel_enum

def get_current_frame(ctx):
    """Gets the current desktop frame."""
    try:
        desktop = create_instance("com.sun.star.frame.Desktop", ctx)
        if desktop:
            return desktop.getCurrentFrame()
    except Exception as e:
        logger.error(f"{_('Error getting current frame:')} {e}", exc_info=True)
    return None

def show_input_box(title, message, default_text="", ctx=None, parent_frame=None):
    """Shows a real input dialog that allows user to edit text."""
    logger.debug(f"show_input_box called: {title} - {message} - default: {default_text}")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning(f"show_input_box: No ctx provided and uno.getComponentContext() failed.")
            return default_text
    
    try:
        # Method 1: Try XUserInputDialogFactory (modern approach)
        try:
            factory = create_instance("com.sun.star.awt.XUserInputDialogFactory", ctx)
            if factory and hasattr(factory, "createInputBox"):
                result = factory.createInputBox(title, message, default_text)
                if result is not None:
                    logger.debug(f"show_input_box: XUserInputDialogFactory returned: '{result}'")
                    return result
        except Exception as e:
            logger.debug(f"show_input_box: XUserInputDialogFactory failed: {e}")
        
        # Method 2: Create programmatic dialog with real text field
        try:
            # Create dialog model
            dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
            if not dialog_model:
                raise Exception("Could not create dialog model")
            
            # Set dialog properties
            dialog_model.setPropertyValue("PositionX", 100)
            dialog_model.setPropertyValue("PositionY", 100) 
            dialog_model.setPropertyValue("Width", 300)
            dialog_model.setPropertyValue("Height", 120)
            dialog_model.setPropertyValue("Title", title)
            
            # Create label for message
            label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlLabelModel")
            label_model.setPropertyValue("PositionX", 10)
            label_model.setPropertyValue("PositionY", 10)
            label_model.setPropertyValue("Width", 280)
            label_model.setPropertyValue("Height", 30)
            label_model.setPropertyValue("Label", message)
            label_model.setPropertyValue("MultiLine", True)
            dialog_model.insertByName("label1", label_model)
            
            # Create text field
            edit_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
            edit_model.setPropertyValue("PositionX", 10)
            edit_model.setPropertyValue("PositionY", 45)
            edit_model.setPropertyValue("Width", 280)
            edit_model.setPropertyValue("Height", 20)
            edit_model.setPropertyValue("Text", default_text)
            dialog_model.insertByName("edit1", edit_model)
            
            # Create OK button
            ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
            ok_button_model.setPropertyValue("PositionX", 130)
            ok_button_model.setPropertyValue("PositionY", 80)
            ok_button_model.setPropertyValue("Width", 60)
            ok_button_model.setPropertyValue("Height", 25)
            ok_button_model.setPropertyValue("Label", "OK")
            ok_button_model.setPropertyValue("PushButtonType", 1)  # OK button
            dialog_model.insertByName("ok_button", ok_button_model)
            
            # Create Cancel button
            cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
            cancel_button_model.setPropertyValue("PositionX", 200)
            cancel_button_model.setPropertyValue("PositionY", 80)
            cancel_button_model.setPropertyValue("Width", 60)
            cancel_button_model.setPropertyValue("Height", 25)
            cancel_button_model.setPropertyValue("Label", "Cancel")
            cancel_button_model.setPropertyValue("PushButtonType", 2)  # Cancel button
            dialog_model.insertByName("cancel_button", cancel_button_model)
            
            # Create dialog control
            dialog_control = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
            if not dialog_control:
                raise Exception("Could not create dialog control")
            
            dialog_control.setModel(dialog_model)
            
            # Get parent window
            parent_window = None
            if parent_frame:
                try:
                    parent_window = parent_frame.getContainerWindow()
                except:
                    pass
            
            if not parent_window:
                try:
                    toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
                    if toolkit:
                        parent_window = toolkit.getActiveTopWindow()
                        if not parent_window:
                            parent_window = toolkit.getDesktopWindow()
                except:
                    pass
            
            # Create dialog peer
            if parent_window:
                dialog_control.createPeer(None, parent_window)
            else:
                toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
                if toolkit:
                    dialog_control.createPeer(toolkit, None)
            
            # Execute dialog
            result = dialog_control.execute()
            
            if result == 1:  # OK pressed
                # Get text from edit control
                edit_control = dialog_control.getControl("edit1")
                if edit_control:
                    user_text = edit_control.getText()
                    logger.debug(f"show_input_box: User entered: '{user_text}'")
                    dialog_control.dispose()
                    return user_text
            
            dialog_control.dispose()
            logger.debug("show_input_box: User cancelled dialog")
            return None
                
        except Exception as e:
            logger.debug(f"show_input_box: Programmatic dialog failed: {e}")
        
        # Method 3: Enhanced fallback with better prompting
        enhanced_message = f"{message}\n\nCurrent value: {default_text}\n\nChoose an option:"
        
        # First ask if they want to change it
        change_result = show_message_box(
            title=title,
            message=enhanced_message + "\n\n• Keep Current Value\n• Enter New Value",
            type="querybox", 
            buttons="yes_no",
            parent_frame=parent_frame,
            ctx=ctx
        )
        
        if change_result != 1:  # Yes = 1, No = 2
            logger.debug(f"show_input_box: User chose to keep current value: '{default_text}'")
            return default_text
            
        # If they want to change, provide guided input
        input_message = f"{message}\n\nEnter new value:\n\nFor common languages:\n• English: eng\n• Hindi: hin\n• French: fra\n• German: deu\n• Spanish: spa\n\nOr leave blank to keep: {default_text}"
        
        # For now, show a simple prompt to enter in console/log and accept default
        logger.info(f"INPUT NEEDED: {title} - {input_message}")
        print(f"\n=== INPUT DIALOG ===")
        print(f"Title: {title}")
        print(f"Message: {message}")
        print(f"Current/Default: {default_text}")
        print(f"===================")
        
        # Return default for now - this gives user feedback about what input is needed
        logger.debug(f"show_input_box: Using current/default value: '{default_text}'")
        return default_text
        
    except Exception as e:
        logger.error(f"show_input_box: All methods failed: {e}")
        return default_text

def is_graphic_object_selected(frame, ctx):
    """Checks if a graphic object is currently selected in the frame."""
    # FOR TESTING: Uncomment the next line to force-return True
    # logger.debug("TESTING MODE: Forcing is_graphic_object_selected to return True");
    # return True
    
    if not frame:
        logger.debug("is_graphic_object_selected: No frame provided")
        return False
    try:
        controller = frame.getController()
        if not controller: 
            logger.debug("is_graphic_object_selected: No controller in frame")
            return False
        selection = controller.getSelection()
        if not selection: 
            logger.debug("is_graphic_object_selected: No selection in controller")
            return False

        # Safe logging of selection type
        try:
            selection_type = selection.__class__.__name__ if selection else "None"
            logger.debug(f"is_graphic_object_selected: Got selection of type {selection_type}")
        except AttributeError:
            logger.debug("is_graphic_object_selected: Selection object has no __class__ attribute")

        # Check for TextGraphicObject (common for images in Writer)
        try:
            if selection.supportsService("com.sun.star.text.TextGraphicObject"):
                logger.debug("is_graphic_object_selected: Found TextGraphicObject")
                return True
        except AttributeError:
            logger.debug("is_graphic_object_selected: Selection doesn't support supportsService method")
            return False
            
        # Check for Shape (can be an image in a drawing shape)
        try:
            if selection.supportsService("com.sun.star.drawing.Shape"):
                logger.debug("is_graphic_object_selected: Selection is a Shape")
                has_graphic = hasattr(selection, "Graphic")
                has_graphic_url = hasattr(selection, "GraphicURL")
                
                # Safe check for ShapeType
                is_graphic_shape = False
                try:
                    is_graphic_shape = (hasattr(selection, "ShapeType") and 
                                      selection.ShapeType == "com.sun.star.drawing.GraphicObjectShape")
                except AttributeError:
                    pass
                
                logger.debug(f"is_graphic_object_selected: Shape properties - has_graphic: {has_graphic}, has_graphic_url: {has_graphic_url}, is_graphic_shape: {is_graphic_shape}")
                
                if has_graphic or has_graphic_url or is_graphic_shape:
                    return True
        except AttributeError:
            logger.debug("is_graphic_object_selected: Selection doesn't support Shape service check")
                
        # Check if it's a collection of shapes (e.g. grouped) and one is an image
        try:
            if selection.supportsService("com.sun.star.drawing.ShapeCollection"):
                count = selection.getCount()
                logger.debug(f"is_graphic_object_selected: Found ShapeCollection with {count} items")
                
                # For simplicity, if any shape in a selection of one is an image, it's true.
                # A more robust check might iterate if getCount() > 1
                if count == 1:
                    shape_in_collection = selection.getByIndex(0)
                    shape_type = shape_in_collection.__class__.__name__ if shape_in_collection else "None"
                    logger.debug(f"is_graphic_object_selected: Checking single shape in collection of type {shape_type}")
                    
                    is_shape = shape_in_collection.supportsService("com.sun.star.drawing.Shape")
                    has_graphic = hasattr(shape_in_collection, "Graphic")
                    has_graphic_url = hasattr(shape_in_collection, "GraphicURL")
                    
                    # Safe check for ShapeType on collection item
                    is_graphic_shape = False
                    try:
                        is_graphic_shape = (hasattr(shape_in_collection, "ShapeType") and 
                                          shape_in_collection.ShapeType == "com.sun.star.drawing.GraphicObjectShape")
                    except AttributeError:
                        pass
                    
                    logger.debug(f"is_graphic_object_selected: Shape in collection - is_shape: {is_shape}, has_graphic: {has_graphic}, has_graphic_url: {has_graphic_url}, is_graphic_shape: {is_graphic_shape}")
                    
                    if is_shape and (has_graphic or has_graphic_url or is_graphic_shape):
                        return True
        except AttributeError:
            logger.debug("is_graphic_object_selected: Selection doesn't support ShapeCollection service check")
                    
        logger.debug("is_graphic_object_selected: No graphic object detected in selection")
        # Add more checks if needed for other types of embedded objects that can be images
    except Exception as e:
        logger.debug(f"Error or non-graphic selection in is_graphic_object_selected: {e}", exc_info=True) # Changed to include full traceback
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
    """Reads a setting from TejOCR configuration with file-based fallback."""
    # Quick fallback to file-based settings due to configuration schema issues
    try:
        settings_file = os.path.join(get_user_temp_dir(), "TejOCRSettings", "settings.txt")
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and line.strip().startswith(key + '='):
                        value = line.split('=', 1)[1].strip()
                        logger.debug(f"get_setting: Found {key}={value} in file")
                        return value
    except Exception as e:
        logger.debug(f"get_setting: File fallback failed: {e}")
    
    logger.debug(f"get_setting: Using default for {key}: {default_value}")
    return default_value

def set_setting(key, value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Writes a setting to TejOCR configuration with file-based fallback."""
    # Quick fallback to file-based settings due to configuration schema issues  
    try:
        settings_dir = os.path.join(get_user_temp_dir(), "TejOCRSettings")
        os.makedirs(settings_dir, exist_ok=True)
        settings_file = os.path.join(settings_dir, "settings.txt")
        
        # Read existing settings
        existing_settings = {}
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        existing_settings[k] = v
        
        # Update the specific setting
        existing_settings[key] = str(value)
        
        # Write back all settings
        with open(settings_file, 'w', encoding='utf-8') as f:
            for k, v in existing_settings.items():
                f.write(f"{k}={v}\n")
        
        logger.debug(f"set_setting: Saved {key}={value} to file")
        return True
    except Exception as e:
        logger.error(f"set_setting: File fallback failed: {e}")
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
    """Creates a temporary file from an XGraphic object with multiple fallback strategies."""
    path = create_temp_file(suffix=".png")
    if not path:
        logger.error("Failed to create a temporary file name.")
        return None
    
    # Strategy 1: Standard GraphicExporter approach
    try:
        exporter = create_instance("com.sun.star.drawing.GraphicExporter", ctx)
        if exporter:
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
            logger.info(f"Strategy 1 SUCCESS: Graphic exported successfully to: {path}")
            return path
    except Exception as e:
        logger.debug(f"Strategy 1 FAILED (GraphicExporter): {e}")
    
    # Strategy 2: Try alternative GraphicExporter service names
    alternative_exporters = [
        "com.sun.star.drawing.GraphicExportFilter",
        "com.sun.star.graphic.GraphicExporter", 
        "com.sun.star.graphic.GraphicExportFilter"
    ]
    
    for service_name in alternative_exporters:
        try:
            exporter = create_instance(service_name, ctx)
            if exporter:
                # Use same export logic as Strategy 1
                props = (uno.createUnoStruct("com.sun.star.beans.PropertyValue"),)
                props[0].Name = "Graphic"
                props[0].Value = graphic
                exporter.setSource(props)
                
                export_props = (uno.createUnoStruct("com.sun.star.beans.PropertyValue"),
                                uno.createUnoStruct("com.sun.star.beans.PropertyValue"))
                export_props[0].Name = "URL"
                export_props[0].Value = unohelper.systemPathToFileUrl(path)
                export_props[1].Name = "MimeType"
                export_props[1].Value = "image/png"
                
                exporter.filter(export_props)
                logger.info(f"Strategy 2 SUCCESS: Graphic exported using {service_name} to: {path}")
                return path
        except Exception as e:
            logger.debug(f"Strategy 2 FAILED ({service_name}): {e}")
    
    # Strategy 3: Try using GraphicProvider to store the graphic
    try:
        provider = create_instance("com.sun.star.graphic.GraphicProvider", ctx)
        if provider:
            # Store properties
            prop_val = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop_val.Name = "URL"
            prop_val.Value = unohelper.systemPathToFileUrl(path)
            
            prop_val_mime = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop_val_mime.Name = "MimeType"
            prop_val_mime.Value = "image/png"
            
            properties = (prop_val, prop_val_mime)
            provider.storeGraphic(graphic, properties)
            logger.info(f"Strategy 3 SUCCESS: Graphic stored using GraphicProvider to: {path}")
            return path
    except Exception as e:
        logger.debug(f"Strategy 3 FAILED (GraphicProvider): {e}")
    
    # Strategy 4: Try to get Bitmap property and use system export
    try:
        # Some graphics may have a Bitmap property that we can access
        if hasattr(graphic, "Bitmap") and graphic.Bitmap:
            bitmap = graphic.Bitmap
            
            # Try to get the bitmap data as a byte sequence
            if hasattr(bitmap, "DIB") and bitmap.DIB:
                # DIB (Device Independent Bitmap) data
                dib_data = bitmap.DIB
                
                # Write DIB data to temporary file
                # This is a basic approach - DIB format may need specific handling
                with open(path, 'wb') as f:
                    f.write(bytes(dib_data))
                logger.info(f"Strategy 4 SUCCESS: Bitmap DIB data written to: {path}")
                return path
                
            elif hasattr(bitmap, "Size") and bitmap.Size:
                # If we have size info, we might be able to construct a minimal image
                logger.debug(f"Bitmap size available: {bitmap.Size.Width}x{bitmap.Size.Height}")
                
        logger.debug("Strategy 4: No usable bitmap data found")
    except Exception as e:
        logger.debug(f"Strategy 4 FAILED (Bitmap export): {e}")
    
    # Strategy 5: Try to get URL property if it's a linked graphic
    try:
        if hasattr(graphic, "URL") and graphic.URL:
            graphic_url = graphic.URL
            logger.debug(f"Found graphic URL: {graphic_url}")
            
            # If it's a file URL, try to copy the file
            if graphic_url.startswith("file://"):
                import shutil
                source_path = unohelper.fileUrlToSystemPath(graphic_url)
                if os.path.exists(source_path):
                    shutil.copy2(source_path, path)
                    logger.info(f"Strategy 5 SUCCESS: Copied graphic file from {source_path} to {path}")
                    return path
                else:
                    logger.debug(f"Source file not found: {source_path}")
        else:
            logger.debug("No URL property found on graphic")
    except Exception as e:
        logger.debug(f"Strategy 5 FAILED (URL copy): {e}")
    
    # Strategy 6: Try to create a simple placeholder image with PIL if available
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple placeholder image
        img = Image.new('RGB', (400, 200), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        text = "OCR Error: Could not export\nselected image.\n\nTry saving the image as a\nfile and using 'OCR from File'\ninstead."
        
        # Use default font
        try:
            # Try to load a default font
            font = ImageFont.load_default()
        except:
            font = None
        
        # Draw text on placeholder
        draw.multiline_text((10, 10), text, fill='black', font=font)
        
        # Save placeholder
        img.save(path, 'PNG')
        logger.warning(f"Strategy 6 FALLBACK: Created placeholder image at {path}")
        return path
        
    except ImportError:
        logger.debug("Strategy 6 FAILED: PIL not available for placeholder creation")
    except Exception as e:
        logger.debug(f"Strategy 6 FAILED (PIL placeholder): {e}")
    
    # All strategies failed
    logger.error("All graphic export strategies failed")
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
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


print("DEBUG: uno_utils.py: Module loaded, logger should be available.") # For load confirmation