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


# --- Constants for dialog results ---
OK_BUTTON = 1  # Standard result for OK from FilePicker/Dialogs
CANCEL_BUTTON = 0  # Standard result for Cancel from dialogs

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

    # Determine MessageBoxType with better fallback handling
    box_type_numeric_map = {
        "infobox": 1,
        "warningbox": 2, 
        "errorbox": 3,
        "querybox": 4,
        "messagebox": 4  # Default
    }
    
    # Try to get the constant, with multiple fallback strategies
    msg_type_enum = None
    type_lower = type.lower()
    
    # Strategy 1: Try the exact constant name
    box_type_str_map = {
        "infobox": "INFOBOX",
        "warningbox": "WARNINGBOX",
        "errorbox": "ERRORBOX",
        "querybox": "QUERYBOX",
        "messagebox": "MESSAGEBOX"
    }

    if type_lower in box_type_str_map:
        try:
            constant_name = f"com.sun.star.awt.MessageBoxType.{box_type_str_map[type_lower]}"
            msg_type_enum = uno.getConstantByName(constant_name)
        except Exception:
            pass
    
    # Strategy 2: Try alternative constant names
    if msg_type_enum is None:
        alternative_names = [
            f"com.sun.star.awt.MessageBoxType.{type_lower.upper()}",
            f"com.sun.star.awt.MessageBoxType.{type_lower.capitalize()}",
        ]
        for alt_name in alternative_names:
            try:
                msg_type_enum = uno.getConstantByName(alt_name)
                break
            except Exception:
                continue
    
    # Strategy 3: Numeric fallback
    if msg_type_enum is None:
        msg_type_enum = box_type_numeric_map.get(type_lower, 4)
        logger.debug(f"Using numeric fallback for MessageBoxType '{type}': {msg_type_enum}")

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
    """Shows a truly interactive input dialog with an editable text field."""
    logger.debug(f"show_input_box called: {title} - {message} - default: {default_text}")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning(f"show_input_box: No ctx provided and uno.getComponentContext() failed.")
            return default_text
    
    try:
        # Create dialog model
        dialog_model = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
        
        if not dialog_model:
            logger.error("Failed to create dialog model")
            return default_text
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 100)
        dialog_model.setPropertyValue("PositionY", 100)
        dialog_model.setPropertyValue("Width", 300)
        dialog_model.setPropertyValue("Height", 120)
        dialog_model.setPropertyValue("Title", title)
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Create label for message
        label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        label_model.setPropertyValue("PositionX", 10)
        label_model.setPropertyValue("PositionY", 10)
        label_model.setPropertyValue("Width", 280)
        label_model.setPropertyValue("Height", 30)
        label_model.setPropertyValue("Label", message)
        label_model.setPropertyValue("MultiLine", True)
        dialog_model.insertByName("label", label_model)
        
        # Create text input field
        text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        text_model.setPropertyValue("PositionX", 10)
        text_model.setPropertyValue("PositionY", 45)
        text_model.setPropertyValue("Width", 280)
        text_model.setPropertyValue("Height", 15)
        text_model.setPropertyValue("Text", default_text)
        dialog_model.insertByName("textfield", text_model)
        
        # Create OK button
        ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        ok_button_model.setPropertyValue("PositionX", 150)
        ok_button_model.setPropertyValue("PositionY", 75)
        ok_button_model.setPropertyValue("Width", 60)
        ok_button_model.setPropertyValue("Height", 20)
        ok_button_model.setPropertyValue("Label", "OK")
        ok_button_model.setPropertyValue("PushButtonType", 1)  # OK button
        dialog_model.insertByName("ok_button", ok_button_model)
        
        # Create Cancel button
        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_button_model.setPropertyValue("PositionX", 220)
        cancel_button_model.setPropertyValue("PositionY", 75)
        cancel_button_model.setPropertyValue("Width", 60)
        cancel_button_model.setPropertyValue("Height", 20)
        cancel_button_model.setPropertyValue("Label", "Cancel")
        cancel_button_model.setPropertyValue("PushButtonType", 2)  # Cancel button
        dialog_model.insertByName("cancel_button", cancel_button_model)
        
        # Create dialog control
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error("Failed to create toolkit")
            return default_text
            
        dialog = toolkit.createWindow(dialog_model)
        if not dialog:
            logger.error("Failed to create dialog window")
            return default_text
        
        # Execute dialog
        result = dialog.execute()
        
        # Get the text if OK was pressed
        user_input = default_text
        if result == 1:  # OK button
            text_control = dialog.getControl("textfield")
            if text_control:
                user_input = text_control.getText()
        
        # Clean up
        dialog.dispose()
        
        logger.debug(f"show_input_box result: {user_input if result == 1 else 'cancelled'}")
        return user_input if result == 1 else None
        
    except Exception as e:
        logger.error(f"show_input_box: Failed to create interactive dialog: {e}", exc_info=True)
        # Fallback to simple message box approach for critical cases
        logger.info("Falling back to simplified choice-based input")
        
        # For language selection, offer common choices
        if "language" in message.lower() or "lang" in title.lower():
            try:
                from tejocr import tejocr_engine
                available_langs = tejocr_engine.get_available_languages()
                if "eng" in available_langs:
                    result = show_message_box(
                        title=title,
                        message=f"{message}\n\nUse English (recommended)?",
                        type="querybox",
                        buttons="yes_no_cancel",
                        parent_frame=parent_frame,
                        ctx=ctx
                    )
                    if result == 2:  # YES
                        return "eng"
                    elif result == 3:  # NO
                        return default_text
                    else:  # CANCEL
                        return None
            except Exception:
                pass
        
        # For paths, offer auto-detect
        elif "path" in message.lower() or "tesseract" in message.lower():
            result = show_message_box(
                title=title,
                message=f"{message}\n\nUse auto-detect?",
                type="querybox",
                buttons="yes_no_cancel",
                parent_frame=parent_frame,
                ctx=ctx
            )
            if result == 2:  # YES
                return ""  # Auto-detect
            elif result == 3:  # NO
                return default_text
            else:  # CANCEL
                return None
        
        # Generic fallback
        return default_text

# Note: Interactive dialog functions have been moved to tejocr_interactive_dialogs.py
def show_interactive_settings_dialog_deprecated(ctx, parent_frame=None):
    """Shows a comprehensive interactive settings dialog."""
    logger.debug("show_interactive_settings_dialog called")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning("No ctx provided and uno.getComponentContext() failed.")
            return False
    
    try:
        # Create dialog model
        dialog_model = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
        
        if not dialog_model:
            logger.error("Failed to create settings dialog model")
            return False
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 50)
        dialog_model.setPropertyValue("PositionY", 50)
        dialog_model.setPropertyValue("Width", 400)
        dialog_model.setPropertyValue("Height", 300)
        dialog_model.setPropertyValue("Title", "TejOCR Settings")
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Title label
        title_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        title_model.setPropertyValue("PositionX", 10)
        title_model.setPropertyValue("PositionY", 10)
        title_model.setPropertyValue("Width", 380)
        title_model.setPropertyValue("Height", 15)
        title_model.setPropertyValue("Label", "TejOCR Configuration")
        title_model.setPropertyValue("FontWeight", 150)  # Bold
        title_model.setPropertyValue("Align", 1)  # Center
        dialog_model.insertByName("title", title_model)
        
        # Dependencies status
        deps_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        deps_label_model.setPropertyValue("PositionX", 10)
        deps_label_model.setPropertyValue("PositionY", 35)
        deps_label_model.setPropertyValue("Width", 380)
        deps_label_model.setPropertyValue("Height", 40)
        
        # Check dependencies
        deps_status = "Checking dependencies..."
        try:
            from tejocr import tejocr_engine
            is_ready, message = tejocr_engine.is_tesseract_ready(ctx, show_gui_errors=False)
            if is_ready:
                deps_status = "✅ All dependencies ready! OCR functionality available."
            else:
                deps_status = f"❌ Dependencies missing: {message}"
        except Exception as e:
            deps_status = f"⚠️ Could not check dependencies: {e}"
        
        deps_label_model.setPropertyValue("Label", deps_status)
        deps_label_model.setPropertyValue("MultiLine", True)
        dialog_model.insertByName("deps_status", deps_label_model)
        
        # Tesseract path section
        path_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        path_label_model.setPropertyValue("PositionX", 10)
        path_label_model.setPropertyValue("PositionY", 85)
        path_label_model.setPropertyValue("Width", 100)
        path_label_model.setPropertyValue("Height", 15)
        path_label_model.setPropertyValue("Label", "Tesseract Path:")
        dialog_model.insertByName("path_label", path_label_model)
        
        # Get current path
        current_path = get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
        
        path_text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        path_text_model.setPropertyValue("PositionX", 120)
        path_text_model.setPropertyValue("PositionY", 85)
        path_text_model.setPropertyValue("Width", 200)
        path_text_model.setPropertyValue("Height", 15)
        path_text_model.setPropertyValue("Text", current_path)
        dialog_model.insertByName("path_text", path_text_model)
        
        # Auto-detect button
        auto_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        auto_button_model.setPropertyValue("PositionX", 330)
        auto_button_model.setPropertyValue("PositionY", 85)
        auto_button_model.setPropertyValue("Width", 60)
        auto_button_model.setPropertyValue("Height", 15)
        auto_button_model.setPropertyValue("Label", "Auto-detect")
        dialog_model.insertByName("auto_button", auto_button_model)
        
        # Default language section
        lang_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label_model.setPropertyValue("PositionX", 10)
        lang_label_model.setPropertyValue("PositionY", 115)
        lang_label_model.setPropertyValue("Width", 100)
        lang_label_model.setPropertyValue("Height", 15)
        lang_label_model.setPropertyValue("Label", "Default Language:")
        dialog_model.insertByName("lang_label", lang_label_model)
        
        # Get current language
        current_lang = get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
        
        lang_text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text_model.setPropertyValue("PositionX", 120)
        lang_text_model.setPropertyValue("PositionY", 115)
        lang_text_model.setPropertyValue("Width", 100)
        lang_text_model.setPropertyValue("Height", 15)
        lang_text_model.setPropertyValue("Text", current_lang)
        dialog_model.insertByName("lang_text", lang_text_model)
        
        # Language help
        lang_help_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_help_model.setPropertyValue("PositionX", 230)
        lang_help_model.setPropertyValue("PositionY", 115)
        lang_help_model.setPropertyValue("Width", 160)
        lang_help_model.setPropertyValue("Height", 15)
        lang_help_model.setPropertyValue("Label", "(e.g., eng, hin, fra, deu, spa)")
        dialog_model.insertByName("lang_help", lang_help_model)
        
        # Installation help button
        help_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        help_button_model.setPropertyValue("PositionX", 10)
        help_button_model.setPropertyValue("PositionY", 150)
        help_button_model.setPropertyValue("Width", 120)
        help_button_model.setPropertyValue("Height", 25)
        help_button_model.setPropertyValue("Label", "Installation Help")
        dialog_model.insertByName("help_button", help_button_model)
        
        # Test dependencies button
        test_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        test_button_model.setPropertyValue("PositionX", 140)
        test_button_model.setPropertyValue("PositionY", 150)
        test_button_model.setPropertyValue("Width", 120)
        test_button_model.setPropertyValue("Height", 25)
        test_button_model.setPropertyValue("Label", "Test Dependencies")
        dialog_model.insertByName("test_button", test_button_model)
        
        # Status label
        status_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        status_model.setPropertyValue("PositionX", 10)
        status_model.setPropertyValue("PositionY", 190)
        status_model.setPropertyValue("Width", 380)
        status_model.setPropertyValue("Height", 40)
        status_model.setPropertyValue("Label", "Ready to configure settings.")
        status_model.setPropertyValue("MultiLine", True)
        dialog_model.insertByName("status", status_model)
        
        # Save button
        save_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        save_button_model.setPropertyValue("PositionX", 200)
        save_button_model.setPropertyValue("PositionY", 250)
        save_button_model.setPropertyValue("Width", 80)
        save_button_model.setPropertyValue("Height", 25)
        save_button_model.setPropertyValue("Label", "Save Settings")
        save_button_model.setPropertyValue("PushButtonType", 1)  # OK button
        dialog_model.insertByName("save_button", save_button_model)
        
        # Cancel button
        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_button_model.setPropertyValue("PositionX", 290)
        cancel_button_model.setPropertyValue("PositionY", 250)
        cancel_button_model.setPropertyValue("Width", 80)
        cancel_button_model.setPropertyValue("Height", 25)
        cancel_button_model.setPropertyValue("Label", "Cancel")
        cancel_button_model.setPropertyValue("PushButtonType", 2)  # Cancel button
        dialog_model.insertByName("cancel_button", cancel_button_model)
        
        # Create dialog control
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error("Failed to create toolkit for settings dialog")
            return False
            
        dialog = toolkit.createWindow(dialog_model)
        if not dialog:
            logger.error("Failed to create settings dialog window")
            return False
        
        # Add action listeners for buttons
        class SettingsActionListener(unohelper.Base):
            def __init__(self, dialog_ref, ctx_ref):
                self.dialog = dialog_ref
                self.ctx = ctx_ref
            
            def actionPerformed(self, event):
                try:
                    button_name = event.Source.getModel().getName()
                    status_control = self.dialog.getControl("status")
                    
                    if button_name == "auto_button":
                        # Auto-detect Tesseract
                        detected_path = find_tesseract_executable()
                        if detected_path:
                            path_control = self.dialog.getControl("path_text")
                            path_control.setText(detected_path)
                            status_control.setText(f"✅ Auto-detected: {detected_path}")
                        else:
                            status_control.setText("❌ Could not auto-detect Tesseract path")
                    
                    elif button_name == "help_button":
                        # Show installation help
                        help_text = (
                            "TejOCR Installation Guide:\n\n"
                            "macOS: brew install tesseract tesseract-lang\n"
                            "Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-[lang]\n"
                            "Windows: Download from GitHub releases\n\n"
                            "For more languages:\n"
                            "Visit: https://tesseract-ocr.github.io/tessdoc/"
                        )
                        show_message_box("Installation Help", help_text, "infobox", ctx=self.ctx)
                    
                    elif button_name == "test_button":
                        # Test current settings
                        path_control = self.dialog.getControl("path_text")
                        test_path = path_control.getText().strip()
                        
                        try:
                            from tejocr import tejocr_engine
                            if test_path:
                                success, message = tejocr_engine.check_tesseract_path(
                                    test_path, ctx=self.ctx, show_success=False, show_gui_errors=False
                                )
                            else:
                                success, message = tejocr_engine.is_tesseract_ready(
                                    self.ctx, show_gui_errors=False
                                )
                            if not success:
                                status_control.setText(f"❌ Test failed: {message}")
                                return
                            
                            # Test language availability
                            langs = tejocr_engine.get_available_languages()
                            
                            if success:
                                status_control.setText("✅ Test successful! Dependencies are working.")
                            else:
                                status_control.setText(f"❌ Test failed: {message}")
                        except Exception as e:
                            status_control.setText(f"❌ Test error: {e}")
                    
                except Exception as e:
                    logger.error(f"Settings dialog action error: {e}")
        
        # Add listeners
        action_listener = SettingsActionListener(dialog, ctx)
        dialog.getControl("auto_button").addActionListener(action_listener)
        dialog.getControl("help_button").addActionListener(action_listener)
        dialog.getControl("test_button").addActionListener(action_listener)
        
        # Execute dialog
        result = dialog.execute()
        
        # Save settings if OK was pressed
        settings_saved = False
        if result == 1:  # OK/Save button
            try:
                # Save Tesseract path
                path_control = dialog.getControl("path_text")
                new_path = path_control.getText().strip()
                set_setting(constants.CFG_KEY_TESSERACT_PATH, new_path, ctx)
                
                # Save default language
                lang_control = dialog.getControl("lang_text")
                new_lang = lang_control.getText().strip().lower()
                if new_lang and len(new_lang) >= 2:
                    set_setting(constants.CFG_KEY_DEFAULT_LANG, new_lang, ctx)
                
                settings_saved = True
                logger.info(f"Settings saved: path='{new_path}', language='{new_lang}'")
                
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
        
        # Clean up
        dialog.dispose()
        
        return settings_saved
        
    except Exception as e:
        logger.error(f"show_interactive_settings_dialog: Failed to create dialog: {e}", exc_info=True)
        return False

def show_interactive_ocr_options_dialog_deprecated(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Shows an interactive OCR options dialog."""
    logger.debug(f"show_interactive_ocr_options_dialog called: {source_type}")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning("No ctx provided and uno.getComponentContext() failed.")
            return None, None
    
    try:
        # Create dialog model
        dialog_model = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
        
        if not dialog_model:
            logger.error("Failed to create OCR options dialog model")
            return None, None
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 100)
        dialog_model.setPropertyValue("PositionY", 100)
        dialog_model.setPropertyValue("Width", 350)
        dialog_model.setPropertyValue("Height", 200)
        dialog_model.setPropertyValue("Title", "OCR Options")
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Title
        title_text = "Extract Text from Image" if source_type == "selected" else f"Extract Text from {os.path.basename(image_path) if image_path else 'File'}"
        title_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        title_model.setPropertyValue("PositionX", 10)
        title_model.setPropertyValue("PositionY", 10)
        title_model.setPropertyValue("Width", 330)
        title_model.setPropertyValue("Height", 15)
        title_model.setPropertyValue("Label", title_text)
        title_model.setPropertyValue("FontWeight", 150)  # Bold
        title_model.setPropertyValue("Align", 1)  # Center
        dialog_model.insertByName("title", title_model)
        
        # Language section
        lang_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label_model.setPropertyValue("PositionX", 10)
        lang_label_model.setPropertyValue("PositionY", 40)
        lang_label_model.setPropertyValue("Width", 80)
        lang_label_model.setPropertyValue("Height", 15)
        lang_label_model.setPropertyValue("Label", "Language:")
        dialog_model.insertByName("lang_label", lang_label_model)
        
        # Get default language
        default_lang = get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
        # Prefer English if available
        if default_lang != "eng":
            try:
                from tejocr import tejocr_engine
                available_langs = tejocr_engine.get_available_languages()
                if "eng" in available_langs:
                    default_lang = "eng"
            except Exception:
                default_lang = "eng"
        
        lang_text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text_model.setPropertyValue("PositionX", 100)
        lang_text_model.setPropertyValue("PositionY", 40)
        lang_text_model.setPropertyValue("Width", 80)
        lang_text_model.setPropertyValue("Height", 15)
        lang_text_model.setPropertyValue("Text", default_lang)
        dialog_model.insertByName("lang_text", lang_text_model)
        
        # Language help
        lang_help_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_help_model.setPropertyValue("PositionX", 190)
        lang_help_model.setPropertyValue("PositionY", 40)
        lang_help_model.setPropertyValue("Width", 150)
        lang_help_model.setPropertyValue("Height", 15)
        lang_help_model.setPropertyValue("Label", "(eng, hin, fra, deu, spa, etc.)")
        dialog_model.insertByName("lang_help", lang_help_model)
        
        # Output mode section
        output_label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_label_model.setPropertyValue("PositionX", 10)
        output_label_model.setPropertyValue("PositionY", 70)
        output_label_model.setPropertyValue("Width", 100)
        output_label_model.setPropertyValue("Height", 15)
        output_label_model.setPropertyValue("Label", "Where to put text:")
        dialog_model.insertByName("output_label", output_label_model)
        
        # Radio buttons for output mode
        cursor_radio_model = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        cursor_radio_model.setPropertyValue("PositionX", 20)
        cursor_radio_model.setPropertyValue("PositionY", 90)
        cursor_radio_model.setPropertyValue("Width", 100)
        cursor_radio_model.setPropertyValue("Height", 15)
        cursor_radio_model.setPropertyValue("Label", "Insert at cursor")
        cursor_radio_model.setPropertyValue("State", 1)  # Selected by default
        dialog_model.insertByName("cursor_radio", cursor_radio_model)
        
        clipboard_radio_model = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        clipboard_radio_model.setPropertyValue("PositionX", 130)
        clipboard_radio_model.setPropertyValue("PositionY", 90)
        clipboard_radio_model.setPropertyValue("Width", 100)
        clipboard_radio_model.setPropertyValue("Height", 15)
        clipboard_radio_model.setPropertyValue("Label", "Copy to clipboard")
        dialog_model.insertByName("clipboard_radio", clipboard_radio_model)
        
        textbox_radio_model = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        textbox_radio_model.setPropertyValue("PositionX", 240)
        textbox_radio_model.setPropertyValue("PositionY", 90)
        textbox_radio_model.setPropertyValue("Width", 100)
        textbox_radio_model.setPropertyValue("Height", 15)
        textbox_radio_model.setPropertyValue("Label", "Create text box")
        dialog_model.insertByName("textbox_radio", textbox_radio_model)
        
        # Start OCR button
        start_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        start_button_model.setPropertyValue("PositionX", 150)
        start_button_model.setPropertyValue("PositionY", 130)
        start_button_model.setPropertyValue("Width", 80)
        start_button_model.setPropertyValue("Height", 25)
        start_button_model.setPropertyValue("Label", "Start OCR")
        start_button_model.setPropertyValue("PushButtonType", 1)  # OK button
        dialog_model.insertByName("start_button", start_button_model)
        
        # Cancel button
        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_button_model.setPropertyValue("PositionX", 240)
        cancel_button_model.setPropertyValue("PositionY", 130)
        cancel_button_model.setPropertyValue("Width", 80)
        cancel_button_model.setPropertyValue("Height", 25)
        cancel_button_model.setPropertyValue("Label", "Cancel")
        cancel_button_model.setPropertyValue("PushButtonType", 2)  # Cancel button
        dialog_model.insertByName("cancel_button", cancel_button_model)
        
        # Create dialog control
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error("Failed to create toolkit for OCR options dialog")
            return None, None
            
        dialog = toolkit.createWindow(dialog_model)
        if not dialog:
            logger.error("Failed to create OCR options dialog window")
            return None, None
        
        # Execute dialog
        result = dialog.execute()
        
        # Get results if OK was pressed
        language = None
        output_mode = None
        
        if result == 1:  # Start OCR button
            # Get language
            lang_control = dialog.getControl("lang_text")
            language = lang_control.getText().strip().lower()
            if not language:
                language = default_lang
            
            # Get output mode
            cursor_control = dialog.getControl("cursor_radio")
            clipboard_control = dialog.getControl("clipboard_radio")
            textbox_control = dialog.getControl("textbox_radio")
            
            if cursor_control.getState():
                output_mode = constants.OUTPUT_MODE_CURSOR
            elif clipboard_control.getState():
                output_mode = constants.OUTPUT_MODE_CLIPBOARD
            elif textbox_control.getState():
                output_mode = constants.OUTPUT_MODE_TEXTBOX
            else:
                output_mode = constants.OUTPUT_MODE_CURSOR  # Default
        
        # Clean up
        dialog.dispose()
        
        logger.debug(f"OCR options result: language={language}, output_mode={output_mode}")
        return language, output_mode
                
    except Exception as e:
        logger.error(f"show_interactive_ocr_options_dialog: Failed to create dialog: {e}", exc_info=True)
        return None, None

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

def find_tesseract_executable(configured_path=""):
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