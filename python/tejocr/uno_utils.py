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
import platform
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
_DIALOG_MODEL_SUPPORT_CACHE = {}

def get_logger(name="TejOCR"):
    """Gets a configured logger instance.
       Manages a dictionary of loggers to avoid re-configuration.
    """
    if name in _loggers:
        return _loggers[name]
    
    try:
        configured_level_name = getattr(constants, "CURRENT_LOG_LEVEL", "ERROR")
        configured_level = logging.ERROR
        try:
            configured_level = int(configured_level_name)
        except Exception:
            if isinstance(configured_level_name, str):
                configured_level = getattr(
                    logging,
                    configured_level_name.strip().upper(),
                    logging.ERROR,
                )
        enable_console_logging = bool(getattr(constants, "ENABLE_CONSOLE_LOGGING", False))

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
        logger_instance.setLevel(configured_level) # Set desired minimum level
        # Keep existing handlers aligned with the current log level.
        for existing_handler in logger_instance.handlers:
            if isinstance(existing_handler, (logging.FileHandler, logging.StreamHandler)):
                existing_handler.setLevel(configured_level)
        
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
            fh.setLevel(configured_level) # Level for this handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
            fh.setFormatter(formatter)
            logger_instance.addHandler(fh)
        
        # Add a console handler only when explicit console logging is enabled.
        if enable_console_logging and not has_console_handler:
            console = logging.StreamHandler()
            console.setLevel(configured_level)
            console_formatter = logging.Formatter('>>> %(name)s - %(levelname)s: %(message)s')
            console.setFormatter(console_formatter)
            logger_instance.addHandler(console)
        
        _loggers[name] = logger_instance
        return logger_instance
    
    except Exception as e_log_setup:
        noop_logger = logging.getLogger(f"{name}.noop")
        noop_logger.setLevel(logging.CRITICAL + 10)
        if not noop_logger.handlers:
            noop_logger.addHandler(logging.NullHandler())
        _loggers[name] = noop_logger
        return noop_logger

# Initialize the module-level logger *after* get_logger is defined.
# This is the primary logger for this module's own operations.
logger = get_logger("TejOCR.uno_utils") 
logger.debug("uno_utils.py: Module loaded and logger initialized.")


def get_log_file_path():
    """Return the canonical extension log path in the current user temp directory."""
    try:
        user_temp_dir = tempfile.gettempdir()
        log_dir = os.path.join(user_temp_dir, "TejOCRLogs")
        return os.path.join(log_dir, "tejocr.log")
    except Exception:
        return None


def read_log_file_tail(max_chars=12000):
    """Read the last part of the log file for diagnostics.

    Args:
        max_chars: Maximum number of characters to return.

    Returns:
        str: The latest log content, or an error message.
    """
    log_path = get_log_file_path()
    if not log_path:
        return "Log path is not available."
    if not os.path.exists(log_path):
        return _("No log file found yet at: {path}").format(path=log_path)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
            content = log_file.read()
        if max_chars and len(content) > max_chars:
            return _("... (showing last {max_chars} characters)\n\n").format(
                max_chars=max_chars
            ) + content[-max_chars:]
        return content
    except Exception as read_error:
        logger.warning(f"read_log_file_tail: unable to read '{log_path}': {read_error}")
        return _("Unable to read log file. {error}").format(error=read_error)


def _safe_set_property(control, property_name, value, context=""):
    """Set a UNO property while tolerating unsupported properties in a fallback-safe way."""
    try:
        control.setPropertyValue(property_name, value)
        return True
    except Exception as e:
        logger.debug(
            "Could not set property '{property_name}' on {context}: {error}".format(
                property_name=property_name,
                context=context or control,
                error=e,
            )
        )
        return False


def show_log_viewer(ctx=None, parent_frame=None, max_chars=12000, title=None):
    """Show a readonly diagnostics dialog with recent log output."""
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning("show_log_viewer: No ctx available; cannot open log viewer.")
            return False

    if title is None:
        title = _("TejOCR Logs")

    log_path = get_log_file_path()
    if not log_path:
        message = _("Could not resolve the log file path.")
        return show_message_box(
            title,
            message,
            type="errorbox",
            parent_frame=parent_frame,
            ctx=ctx,
        ) == uno_utils_result_ok()

    log_content = read_log_file_tail(max_chars=max_chars)
    editor_text = _("Log file: {path}\n\n{content}").format(
        path=log_path,
        content=log_content
    )

    # The multiline input box is used as a read-only log viewer (Save is intentionally disabled).
    result = show_multiline_input_box(
        title=title,
        message=_("Diagnostics"),
        default_text=editor_text,
        ctx=ctx,
        parent_frame=parent_frame,
        width=800,
        height=500,
    )
    if result is None:
        truncated_preview = log_content
        if len(truncated_preview) > 2500:
            truncated_preview = _("... (showing last 2,500 characters)\n\n") + truncated_preview[-2500:]
        show_message_box(
            title=title,
            message=_(
                "Diagnostics could not be edited in this build.\n\n"
                "Log file: {path}\n\n"
                "{preview}"
            ).format(path=log_path, preview=truncated_preview),
            type="infobox",
            parent_frame=parent_frame,
            ctx=ctx,
        )
    return result is not None


def uno_utils_result_ok():
    """Return the UNO OK result constant used by message boxes."""
    try:
        return uno.getConstantByName("com.sun.star.awt.MessageBoxResults.OK")
    except Exception:
        return 1


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

def _iter_service_contexts(ctx):
    """Yield candidate UNO contexts for service creation."""
    yielded = set()

    if ctx is not None:
        try:
            yielded.add(id(ctx))
            yield ctx
        except Exception:
            pass

    try:
        fallback_ctx = uno.getComponentContext()
    except Exception:
        fallback_ctx = None

    if fallback_ctx is not None:
        fallback_ctx_id = id(fallback_ctx)
        if fallback_ctx_id not in yielded:
            yielded.add(fallback_ctx_id)
            yield fallback_ctx

def create_instance(service_name, ctx=None):
    """Creates an instance of a UNO service using the provided component context."""
    if not service_name:
        logger.error("create_instance called without a service name.")
        return None

    attempted_contexts = []
    last_exception = None

    for candidate_ctx in _iter_service_contexts(ctx):
        attempted_contexts.append(_context_cache_key(candidate_ctx))
        try:
            # Get service manager directly from context for this specific call
            smgr = _get_service_manager(candidate_ctx)
            if not smgr:
                logger.error(
                    f"Could not get ServiceManager from context '{_context_cache_key(candidate_ctx)}' for '{service_name}'."
                )
                continue

            try:
                instance = smgr.createInstanceWithContext(service_name, candidate_ctx)
                if instance:
                    if candidate_ctx is not ctx:
                        logger.debug(
                            f"create_instance: '{service_name}' created with context "
                            f"{_context_cache_key(candidate_ctx)}."
                        )
                    return instance

                logger.debug(
                    f"createInstanceWithContext returned None for '{service_name}' in context "
                    f"{_context_cache_key(candidate_ctx)}."
                )
            except Exception as e:
                logger.debug(
                    f"createInstanceWithContext failed for '{service_name}' in context "
                    f"{_context_cache_key(candidate_ctx)}: {e}"
                )
                last_exception = e

            try:
                instance = smgr.createInstance(service_name)
                if instance:
                    if candidate_ctx is not ctx:
                        logger.debug(
                            f"create_instance: '{service_name}' created with fallback context "
                            f"{_context_cache_key(candidate_ctx)} via createInstance()."
                        )
                    return instance
            except Exception as fallback_error:
                last_exception = fallback_error
                logger.debug(
                    f"createInstance fallback failed for '{service_name}' in context "
                    f"{_context_cache_key(candidate_ctx)}: {fallback_error}"
                )
        except Exception as e:
            last_exception = e
            logger.debug(
                f"Failed to create '{service_name}' in context {_context_cache_key(candidate_ctx)}: {e}"
            )

    if attempted_contexts:
        logger.debug(
            f"create_instance exhausted contexts {attempted_contexts} for service '{service_name}'."
        )
    else:
        logger.error(f"create_instance called for '{service_name}' but no contexts were available.")

    if last_exception is not None:
        logger.debug(
            f"create_instance: last error for '{service_name}': {last_exception}"
        )
    return None


def _context_cache_key(ctx):
    """Create a stable cache key for a UNO context."""
    return f"id:{id(ctx)}" if ctx is not None else "no_ctx"


def _settings_file_path():
    """Returns the fallback settings file path."""
    return os.path.join(get_user_temp_dir(), "TejOCRSettings", "settings.txt")


def get_settings_file_path():
    """Public helper for callers that need to surface the settings file path."""
    return _settings_file_path()


def supports_uno_dialog_model(ctx):
    """Return whether dialog models can be created in this UNO context.

    This is a fast capability check used by fallback input handlers.
    """
    cache_key = _context_cache_key(ctx)

    # Cache only hard failures for this runtime. Some UNO builds can report
    # success once and fail later, so we re-check creation on each call unless we
    # already know the service is unavailable for this context.
    if _DIALOG_MODEL_SUPPORT_CACHE.get(cache_key, True) is False:
        logger.debug("supports_uno_dialog_model: Returning cached negative result for context.")
        return False

    if not ctx:
        logger.error("supports_uno_dialog_model called without a UNO context.")
        _DIALOG_MODEL_SUPPORT_CACHE[cache_key] = False
        return False

    try:
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        if not dialog_model:
            logger.error("supports_uno_dialog_model: Service returned None for com.sun.star.awt.UnoControlDialogModel")
            _DIALOG_MODEL_SUPPORT_CACHE[cache_key] = False
            return False

        logger.debug("supports_uno_dialog_model: Successfully created a dialog model probe instance.")

        # Verify we can also instantiate a dialog control and attach the model.
        # Some UNO environments can create the model service but fail when creating controls.
        dialog_ctrl = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        if not dialog_ctrl:
            logger.error("supports_uno_dialog_model: Service returned None for com.sun.star.awt.UnoControlDialog")
            _DIALOG_MODEL_SUPPORT_CACHE[cache_key] = False
            return False

        try:
            dialog_ctrl.setModel(dialog_model)
            logger.debug("supports_uno_dialog_model: Probe dialog control accepted model attachment.")
        except Exception as model_attach_error:
            logger.error(
                f"supports_uno_dialog_model: Probe failed to attach model: {model_attach_error}"
            )
            _DIALOG_MODEL_SUPPORT_CACHE[cache_key] = False
            return False

        # Dispose probe instances to avoid leaking UI resources.
        for instance in (dialog_ctrl, dialog_model):
            dispose_fn = getattr(instance, "dispose", None)
            if callable(dispose_fn):
                try:
                    dispose_fn()
                except Exception as dispose_error:
                    logger.debug(f"supports_uno_dialog_model: Probe dispose failed: {dispose_error}")

        return True

    except Exception as probe_error:
        logger.error(
            f"supports_uno_dialog_model: Dialog model capability check failed: {probe_error}",
            exc_info=True,
        )
        _DIALOG_MODEL_SUPPORT_CACHE[cache_key] = False
        return False


def show_file_picker(title, filters=None, default_directory="", ctx=None, parent_frame=None):
    """Shows a file picker and returns the selected file path.

    filters should be an iterable of (name, pattern) tuples.
    """
    logger.debug(f"show_file_picker called: title='{title}', filters='{filters}', default_directory='{default_directory}'")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning("show_file_picker: No context available and uno.getComponentContext() failed.")
            return None

    file_picker = create_instance("com.sun.star.ui.dialogs.FilePicker", ctx)
    if not file_picker:
        logger.error("show_file_picker: Failed to create FilePicker instance.")
        return None

    try:
        file_picker.setTitle(title)
        
        if filters:
            for filter_name, filter_pattern in filters:
                file_picker.appendFilter(filter_name, filter_pattern)
        else:
            file_picker.appendFilter(_("All Files"), "*.*")
        
        if default_directory:
            try:
                file_picker.setDisplayDirectory(unohelper.systemPathToFileUrl(default_directory))
            except Exception as e_dir:
                logger.debug(f"show_file_picker: Could not set default directory '{default_directory}': {e_dir}")
        
        if file_picker.execute() == OK_BUTTON:
            selected_files = file_picker.getFiles()
            if selected_files:
                return unohelper.fileUrlToSystemPath(selected_files[0])
    except Exception as e:
        logger.error(f"show_file_picker: Failed while showing picker: {e}", exc_info=True)
        uno_utils_error_hint = _("File picker failed: {error}").format(error=e)
        logger.debug(uno_utils_error_hint)
    
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

    # Normalize and normalize known aliases for message box type
    # Some older call sites pass query intent through button names by mistake,
    # so we map that to a plain message box to keep fallback UX predictable.
    type_normalized = "messagebox"
    if type is not None:
        try:
            type_normalized = str(type).strip().lower()
        except Exception:
            type_normalized = "messagebox"

    type_alias = {
        "ok_cancel": "messagebox",
        "okcancel": "messagebox",
        "yes_no": "messagebox",
        "yesno": "messagebox",
        "yes_no_cancel": "messagebox",
        "yesnocancel": "messagebox",
        "message": "messagebox",
        "query": "querybox",
    }

    type_lower = type_alias.get(type_normalized, type_normalized)

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
            logger.debug(f"MESSAGE BOX (CONSOLE FALLBACK - TOOLKIT FAIL): {title} - {message}")
            return msg_result_cancel_enum

        box = toolkit.createMessageBox(parent_peer, msg_type_enum, buttons_enum, str(title), str(message))
        if not box:
            logger.error(f"show_message_box: toolkit.createMessageBox returned None for: {title} - {message}")
            logger.debug(f"MESSAGE BOX (CONSOLE FALLBACK - CREATE FAIL): {title} - {message}")
            return msg_result_cancel_enum
            
        return box.execute()
    except Exception as e:
        logger.error(f"show_message_box: Exception during create/execute: {e} for {title} - {message}", exc_info=True)
        logger.debug(f"MESSAGE BOX (CONSOLE FALLBACK - EXECUTE ERROR): {title} - {message} - Exception: {e}")
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


def _show_minimal_input_fallback(title, message, default_text="", ctx=None, parent_frame=None):
    """Minimal fallback text-input dialog used when the full input dialog creation fails."""
    try:
        if ctx is None:
            return None

        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        if not dialog_model:
            logger.error(f"Fallback input dialog: Could not create dialog model for '{title}'")
            return None

        _safe_set_property(dialog_model, "PositionX", 140, f"{title}.model")
        _safe_set_property(dialog_model, "PositionY", 140, f"{title}.model")
        _safe_set_property(dialog_model, "Width", 320, f"{title}.model")
        _safe_set_property(dialog_model, "Height", 130, f"{title}.model")
        _safe_set_property(dialog_model, "Title", title, f"{title}.model")
        _safe_set_property(dialog_model, "Closeable", True, f"{title}.model")
        _safe_set_property(dialog_model, "Moveable", True, f"{title}.model")

        label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        _safe_set_property(label_model, "PositionX", 10, f"{title}.label")
        _safe_set_property(label_model, "PositionY", 10, f"{title}.label")
        _safe_set_property(label_model, "Width", 300, f"{title}.label")
        _safe_set_property(label_model, "Height", 40, f"{title}.label")
        _safe_set_property(label_model, "Label", message, f"{title}.label")
        dialog_model.insertByName("label", label_model)

        text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        _safe_set_property(text_model, "PositionX", 10, f"{title}.textfield")
        _safe_set_property(text_model, "PositionY", 55, f"{title}.textfield")
        _safe_set_property(text_model, "Width", 300, f"{title}.textfield")
        _safe_set_property(text_model, "Height", 15, f"{title}.textfield")
        _safe_set_property(text_model, "Text", default_text, f"{title}.textfield")
        dialog_model.insertByName("textfield", text_model)

        ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(ok_button_model, "PositionX", 190, f"{title}.ok")
        _safe_set_property(ok_button_model, "PositionY", 95, f"{title}.ok")
        _safe_set_property(ok_button_model, "Width", 55, f"{title}.ok")
        _safe_set_property(ok_button_model, "Height", 20, f"{title}.ok")
        _safe_set_property(ok_button_model, "Label", _("OK"), f"{title}.ok")
        _safe_set_property(ok_button_model, "PushButtonType", 1, f"{title}.ok")
        dialog_model.insertByName("ok_button", ok_button_model)

        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(cancel_button_model, "PositionX", 250, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PositionY", 95, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Width", 65, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Height", 20, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Label", _("Cancel"), f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PushButtonType", 2, f"{title}.cancel")
        dialog_model.insertByName("cancel_button", cancel_button_model)

        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error("Fallback input dialog: Failed to get toolkit.")
            return None

        dialog = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        if not dialog:
            logger.error("Fallback input dialog: Failed to create dialog control.")
            return None

        dialog.setModel(dialog_model)
        parent_peer = None
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except Exception:
                parent_peer = None
        if parent_peer is None:
            try:
                parent_peer = toolkit.getDesktopWindow()
            except Exception:
                parent_peer = None

        dialog.createPeer(toolkit, parent_peer)
        result = dialog.execute()

        user_text = default_text
        if result == 1:
            control = dialog.getControl("textfield")
            if control:
                user_text = control.getText()
        dialog.dispose()
        return user_text if result == 1 else None
    except Exception as e:
        logger.error(f"show_input_box fallback dialog failed: {e}", exc_info=True)
        return None

def show_input_box(title, message, default_text="", ctx=None, parent_frame=None):
    """Shows a truly interactive input dialog with an editable text field."""
    logger.debug(f"show_input_box called: {title} - {message} - default: {default_text}")
    
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning(f"show_input_box: No ctx provided and uno.getComponentContext() failed.")
            return None

    if not supports_uno_dialog_model(ctx):
        logger.error("show_input_box: UnoControlDialogModel is unavailable; interactive input dialog cannot be shown.")
        return None
    
    try:
        # Create dialog model
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        
        if not dialog_model:
            logger.error("Failed to create input dialog model")
            raise RuntimeError("Could not create dialog model")
        
        # Set dialog properties
        _safe_set_property(dialog_model, "PositionX", 100, f"{title}.model")
        _safe_set_property(dialog_model, "PositionY", 100, f"{title}.model")
        _safe_set_property(dialog_model, "Width", 300, f"{title}.model")
        _safe_set_property(dialog_model, "Height", 120, f"{title}.model")
        _safe_set_property(dialog_model, "Title", title, f"{title}.model")
        _safe_set_property(dialog_model, "Closeable", True, f"{title}.model")
        _safe_set_property(dialog_model, "Moveable", True, f"{title}.model")
        
        # Create label for message
        label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        _safe_set_property(label_model, "PositionX", 10, f"{title}.label")
        _safe_set_property(label_model, "PositionY", 10, f"{title}.label")
        _safe_set_property(label_model, "Width", 280, f"{title}.label")
        _safe_set_property(label_model, "Height", 30, f"{title}.label")
        _safe_set_property(label_model, "Label", message, f"{title}.label")
        _safe_set_property(label_model, "MultiLine", True, f"{title}.label")
        dialog_model.insertByName("label", label_model)
        
        # Create text input field
        text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        _safe_set_property(text_model, "PositionX", 10, f"{title}.textfield")
        _safe_set_property(text_model, "PositionY", 45, f"{title}.textfield")
        _safe_set_property(text_model, "Width", 280, f"{title}.textfield")
        _safe_set_property(text_model, "Height", 15, f"{title}.textfield")
        _safe_set_property(text_model, "Text", default_text, f"{title}.textfield")
        dialog_model.insertByName("textfield", text_model)
        
        # Create OK button
        ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(ok_button_model, "PositionX", 150, f"{title}.ok")
        _safe_set_property(ok_button_model, "PositionY", 75, f"{title}.ok")
        _safe_set_property(ok_button_model, "Width", 60, f"{title}.ok")
        _safe_set_property(ok_button_model, "Height", 20, f"{title}.ok")
        _safe_set_property(ok_button_model, "Label", "OK", f"{title}.ok")
        _safe_set_property(ok_button_model, "PushButtonType", 1, f"{title}.ok")  # OK button
        dialog_model.insertByName("ok_button", ok_button_model)
        
        # Create Cancel button
        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(cancel_button_model, "PositionX", 220, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PositionY", 75, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Width", 60, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Height", 20, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Label", "Cancel", f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PushButtonType", 2, f"{title}.cancel")
        dialog_model.insertByName("cancel_button", cancel_button_model)
        
        # Create dialog control
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            logger.error("Failed to create toolkit")
            return None

        dialog = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        if not dialog:
            logger.error("Failed to create dialog control")
            return None
        
        dialog.setModel(dialog_model)
        
        # Parent peer for dialog.
        parent_peer = None
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except Exception:
                parent_peer = None
        if parent_peer is None:
            try:
                parent_peer = toolkit.getDesktopWindow()
            except Exception:
                parent_peer = None
        if parent_peer is None:
            logger.warning("No parent peer available for input dialog")
        
        # Execute dialog
        dialog.createPeer(toolkit, parent_peer)
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
        logger.warning(
            "show_input_box: No fallback UI available in this UNO runtime. "
            "Returning None to indicate user input could not be collected."
        )
        return None


def show_multiline_input_box(title, message, default_text="", ctx=None, parent_frame=None, width=640, height=280):
    """Shows an editable multi-line text dialog and returns the entered text.

    This is intentionally defensive: if multi-line controls are not supported in
    a particular LibreOffice build, it falls back to a single-line dialog.
    """
    logger.debug(
        f"show_multiline_input_box called: {title} - {message} - default length: {len(default_text or '')}"
    )

    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            logger.warning(
                "show_multiline_input_box: No ctx provided and uno.getComponentContext() failed."
            )
            return None

    toolkit = None
    try:
        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
    except Exception:
        toolkit = None

    if not supports_uno_dialog_model(ctx):
        logger.error("show_multiline_input_box: UnoControlDialogModel is unavailable; multiline edit dialog cannot be shown.")
        return None

    safe_width = max(420, int(width))
    safe_height = max(220, int(height))
    try:
        if toolkit:
            screen_width = int(getattr(toolkit, "getScreenWidth", lambda: 1280)())
            screen_height = int(getattr(toolkit, "getScreenHeight", lambda: 900)())
            safe_width = max(420, min(920, screen_width - 180))
            safe_height = max(220, min(560, screen_height - 180))
    except Exception:
        safe_width = max(420, int(width))
        safe_height = max(220, int(height))

    window_x = 120
    window_y = 120
    try:
        if toolkit:
            screen_width = int(getattr(toolkit, "getScreenWidth", lambda: safe_width + 200)())
            screen_height = int(getattr(toolkit, "getScreenHeight", lambda: safe_height + 200)())
            window_x = max(12, (screen_width - safe_width) // 2)
            window_y = max(12, (screen_height - safe_height) // 2)
    except Exception:
        window_x = 120
        window_y = 120

    num_message_lines = len(str(message).split('\n'))
    label_height = int(max(32, min(safe_height * 0.35, num_message_lines * 14 + 10)))
    input_y = label_height + 8
    input_height = max(100, safe_height - label_height - 46)
    button_y = safe_height - 36

    try:
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        if not dialog_model:
            logger.error("Failed to create multiline input dialog model")
            raise RuntimeError("Could not create dialog model")

        _safe_set_property(dialog_model, "PositionX", window_x, f"{title}.model")
        _safe_set_property(dialog_model, "PositionY", window_y, f"{title}.model")
        _safe_set_property(dialog_model, "Width", safe_width, f"{title}.model")
        _safe_set_property(dialog_model, "Height", safe_height, f"{title}.model")
        _safe_set_property(dialog_model, "Title", title, f"{title}.model")
        _safe_set_property(dialog_model, "Closeable", True, f"{title}.model")
        _safe_set_property(dialog_model, "Moveable", True, f"{title}.model")

        label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        _safe_set_property(label_model, "PositionX", 10, f"{title}.label")
        _safe_set_property(label_model, "PositionY", 10, f"{title}.label")
        _safe_set_property(label_model, "Width", safe_width - 20, f"{title}.label")
        _safe_set_property(label_model, "Height", label_height, f"{title}.label")
        _safe_set_property(label_model, "MultiLine", True, f"{title}.label")
        _safe_set_property(label_model, "Label", message, f"{title}.label")
        dialog_model.insertByName("label", label_model)

        text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        _safe_set_property(text_model, "PositionX", 10, f"{title}.text")
        _safe_set_property(text_model, "PositionY", input_y, f"{title}.text")
        _safe_set_property(text_model, "Width", safe_width - 20, f"{title}.text")
        _safe_set_property(text_model, "Height", input_height, f"{title}.text")
        _safe_set_property(text_model, "Text", default_text, f"{title}.text")
        _safe_set_property(text_model, "MultiLine", True, f"{title}.text")
        _safe_set_property(text_model, "VScroll", True, f"{title}.text")
        _safe_set_property(text_model, "HScroll", True, f"{title}.text")
        # LineEndFormat 13 means standard line break parsing for text wrapping
        _safe_set_property(text_model, "LineEndFormat", 13, f"{title}.text")
        dialog_model.insertByName("textfield", text_model)

        ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(ok_button_model, "PositionX", safe_width - 150, f"{title}.ok")
        _safe_set_property(ok_button_model, "PositionY", button_y, f"{title}.ok")
        _safe_set_property(ok_button_model, "Width", 60, f"{title}.ok")
        _safe_set_property(ok_button_model, "Height", 20, f"{title}.ok")
        _safe_set_property(ok_button_model, "Label", _("OK"), f"{title}.ok")
        _safe_set_property(ok_button_model, "PushButtonType", 1, f"{title}.ok")
        dialog_model.insertByName("ok_button", ok_button_model)

        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(cancel_button_model, "PositionX", safe_width - 80, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PositionY", button_y, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Width", 70, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Height", 20, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Label", _("Cancel"), f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PushButtonType", 2, f"{title}.cancel")
        dialog_model.insertByName("cancel_button", cancel_button_model)

        if not toolkit:
            logger.error("Failed to create toolkit for multiline input dialog")
            raise RuntimeError("Toolkit unavailable")

        dialog = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        if not dialog:
            logger.error("Failed to create multiline dialog control")
            raise RuntimeError("Dialog control unavailable")

        dialog.setModel(dialog_model)

        parent_peer = None
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except Exception:
                parent_peer = None
        if parent_peer is None:
            try:
                parent_peer = toolkit.getDesktopWindow()
            except Exception:
                parent_peer = None

        dialog.createPeer(toolkit, parent_peer)
        result = dialog.execute()
        final_value = default_text
        if result == 1:
            control = dialog.getControl("textfield")
            if control:
                final_value = control.getText()
        dialog.dispose()
        return final_value if result == 1 else None
    except Exception as e:
        logger.error(
            f"show_multiline_input_box: Failed to create/edit multiline dialog: {e}",
            exc_info=True,
        )
        logger.error("show_multiline_input_box: Multiline dialog unavailable in this UNO runtime.")
        return None


def _show_ocr_preview_scrollable_dialog(title, text, header_lines, ctx=None, parent_frame=None):
    """Attempt a scrollable, fixed-size preview dialog for long OCR text."""
    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            return None

    try:
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        if not dialog_model:
            return None

        toolkit = create_instance("com.sun.star.awt.Toolkit", ctx)
        if not toolkit:
            return None

        preview_text = str(text) if text is not None else ""

        # Make dialog dimensions generous but not screen-clipping.
        safe_width = 760
        safe_height = 460
        try:
            screen_width = getattr(toolkit, "getScreenWidth", lambda: 1280)()
            screen_height = getattr(toolkit, "getScreenHeight", lambda: 920)()
            if isinstance(screen_width, int) and screen_width > 160:
                safe_width = max(420, min(920, screen_width - 160))
            if isinstance(screen_height, int) and screen_height > 200:
                safe_height = max(320, min(580, screen_height - 240))
        except Exception:
            safe_width = 760
            safe_height = 460

        window_x = 120
        window_y = 120
        try:
            screen_width = int(getattr(toolkit, "getScreenWidth", lambda: safe_width + 200)())
            screen_height = int(getattr(toolkit, "getScreenHeight", lambda: safe_height + 200)())
            window_x = max(12, (screen_width - safe_width) // 2)
            window_y = max(12, (screen_height - safe_height) // 2)
        except Exception:
            window_x = 120
            window_y = 120

        header_block = "\n".join(header_lines + ["", _("Click inside the OCR text area to scroll and review."), ""])
        num_header_lines = len(header_block.split('\n'))
        header_height = int(max(42, min(safe_height * 0.4, num_header_lines * 14 + 10)))
        edit_y = header_height + 10
        button_y = safe_height - 40
        left_pad = 10
        button_width = 80
        button_gap = 10

        _safe_set_property(dialog_model, "Width", safe_width, f"{title}.model")
        _safe_set_property(dialog_model, "Height", safe_height, f"{title}.model")
        _safe_set_property(dialog_model, "PositionX", window_x, f"{title}.model")
        _safe_set_property(dialog_model, "PositionY", window_y, f"{title}.model")
        _safe_set_property(dialog_model, "Title", title, f"{title}.model")
        _safe_set_property(dialog_model, "Closeable", True, f"{title}.model")
        _safe_set_property(dialog_model, "Moveable", True, f"{title}.model")

        label_model = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        _safe_set_property(label_model, "PositionX", left_pad, f"{title}.label")
        _safe_set_property(label_model, "PositionY", 12, f"{title}.label")
        _safe_set_property(label_model, "Width", safe_width - (left_pad * 2), f"{title}.label")
        _safe_set_property(label_model, "Height", header_height, f"{title}.label")
        _safe_set_property(label_model, "MultiLine", True, f"{title}.label")
        _safe_set_property(label_model, "Label", header_block, f"{title}.label")
        dialog_model.insertByName("label", label_model)

        text_model = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        _safe_set_property(text_model, "PositionX", left_pad, f"{title}.textfield")
        _safe_set_property(text_model, "PositionY", edit_y, f"{title}.textfield")
        _safe_set_property(text_model, "Width", safe_width - 20, f"{title}.textfield")
        _safe_set_property(text_model, "Height", button_y - (edit_y + 12), f"{title}.textfield")
        _safe_set_property(text_model, "Text", preview_text, f"{title}.textfield")
        _safe_set_property(text_model, "MultiLine", True, f"{title}.textfield")
        _safe_set_property(text_model, "ReadOnly", False, f"{title}.textfield")
        _safe_set_property(text_model, "VScroll", True, f"{title}.textfield")
        _safe_set_property(text_model, "HScroll", True, f"{title}.textfield")
        _safe_set_property(text_model, "LineEndFormat", 13, f"{title}.textfield")
        dialog_model.insertByName("review_text", text_model)

        ok_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(ok_button_model, "PositionX", safe_width - 2 * button_width - button_gap - left_pad, f"{title}.ok")
        _safe_set_property(ok_button_model, "PositionY", button_y, f"{title}.ok")
        _safe_set_property(ok_button_model, "Width", button_width, f"{title}.ok")
        _safe_set_property(ok_button_model, "Height", 20, f"{title}.ok")
        _safe_set_property(ok_button_model, "Label", _("OK"), f"{title}.ok")
        _safe_set_property(ok_button_model, "PushButtonType", 1, f"{title}.ok")
        dialog_model.insertByName("ok_button", ok_button_model)

        cancel_button_model = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        _safe_set_property(cancel_button_model, "PositionX", safe_width - button_width - left_pad, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PositionY", button_y, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Width", button_width, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Height", 20, f"{title}.cancel")
        _safe_set_property(cancel_button_model, "Label", _("Cancel"), f"{title}.cancel")
        _safe_set_property(cancel_button_model, "PushButtonType", 2, f"{title}.cancel")
        dialog_model.insertByName("cancel_button", cancel_button_model)

        dialog = create_instance("com.sun.star.awt.UnoControlDialog", ctx)
        if not dialog:
            return None

        dialog.setModel(dialog_model)

        parent_peer = None
        if parent_frame:
            try:
                container_window = parent_frame.getContainerWindow()
                if container_window and hasattr(container_window, "getPeer"):
                    parent_peer = container_window.getPeer()
            except Exception:
                parent_peer = None
        if parent_peer is None:
            try:
                parent_peer = toolkit.getDesktopWindow()
            except Exception:
                parent_peer = None

        dialog.createPeer(toolkit, parent_peer)
        result = dialog.execute()
        dialog.dispose()
        return bool(result == 1)
    except Exception as e:
        logger.debug(f"show_ocr_preview_fallback: scrollable preview dialog failed: {e}")
        return None


def _summarize_source_lines(source_lines, max_lines=6):
    """Create a compact source summary block for long fallback dialogs."""
    if not source_lines:
        return ""
    compact_lines = [str(item).strip() for item in source_lines if str(item).strip()]
    compact_lines = compact_lines[:max_lines]
    if len(source_lines) > max_lines:
        compact_lines.append(_("… and {count} more").format(count=len(source_lines) - max_lines))
    return "\n" + _("Source files and extraction sizes:\n{items}").format(
        items="\n".join(f"• {line}" for line in compact_lines)
    )


def _compact_text_with_tail(text, max_chars, max_lines=15):
    """Return a bounded compact preview preserving head and tail context."""
    if not text:
        return ""
    
    # First cap the vertical size by clipping lines
    lines = text.split('\n')
    if len(lines) > max_lines:
        head_lines = max(1, max_lines // 2 - 1)
        tail_lines = max(1, max_lines - head_lines - 1)
        text = "\n".join(lines[:head_lines]) + "\n\n... [content clipped for dialog size] ...\n\n" + "\n".join(lines[-tail_lines:])
    if len(text) <= max_chars:
        return text
    max_chars = max(220, int(max_chars))
    if max_chars < 220:
        return text[:max_chars]

    # Keep a readable head and tail; middle section is replaced with a clear marker.
    head_chars = max(140, max_chars // 2 - 20)
    tail_chars = max(80, max_chars - head_chars - len("\n\n... [content clipped for dialog size] ...\n\n"))
    if tail_chars < 80:
        tail_chars = 80
    compact = (
        text[:head_chars]
        + "\n\n... [content clipped for dialog size] ...\n\n"
        + text[-tail_chars:]
    )
    if len(compact) > max_chars:
        compact = compact[:max_chars]
    return compact


def show_ocr_preview_fallback(title, text, ctx=None, parent_frame=None, max_chars=2400, source_lines=None):
    """Fallback preview dialog for runtimes where multiline dialogs are unavailable.

    Returns the original text if user confirms insertion, or None if user cancels.
    """
    # Normalize and guard.
    preview = text or ""
    try:
        preview = str(preview)
    except Exception:
        preview = ""

    if ctx is None:
        try:
            ctx = uno.getComponentContext()
        except Exception:
            ctx = None

    if ctx is not None and not supports_uno_dialog_model(ctx):
        normalized_source_lines = []
        for item in source_lines or []:
            if not item:
                continue
            try:
                normalized_source_lines.append(str(item))
            except Exception:
                pass
        compact_preview = _compact_text_with_tail(preview, 600, max_lines=12)
        source_overview = _summarize_source_lines(normalized_source_lines)
        lines_to_show = [
            _("The multiline OCR review window is not supported in this LibreOffice session."),
            _("Please confirm insertion from the preview below:"),
            _("Output summary: {chars} chars, {lines} source lines.").format(
                chars=len(preview),
                lines=len(normalized_source_lines) if normalized_source_lines else len(preview.splitlines()),
            ),
        ]
        if source_overview:
            lines_to_show.append(source_overview.strip())
        lines_to_show.extend([
            "",
            _("-" * 58),
            compact_preview.strip(),
            _("-" * 58),
            _("Text is truncated for the in-session preview."),
            _("Review source documents if you need full text."),
            _("Click OK to insert this OCR result."),
        ])
        response = show_message_box(
            title,
            "\n".join(lines_to_show),
            type="querybox",
            parent_frame=parent_frame,
            ctx=ctx,
            buttons="ok_cancel",
        )
        if response in (None, 0, "0", "cancel", False):
            logger.debug("OCR preview fallback canceled by user.")
            return None
        return preview

    total_chars = len(preview)
    total_lines = len(preview.splitlines()) if preview else 0

    max_chars = max(400, int(max_chars or 0))
    if max_chars < 900:
        max_chars = 900

    normalized_source_lines = []
    for item in source_lines or []:
        if not item:
            continue
        try:
            line = str(item)
        except Exception:
            line = ""
        if line:
            normalized_source_lines.append(line)

    source_overview = _summarize_source_lines(normalized_source_lines)

    # Keep message-box fallback compact for very long text, but use one-pass
    # display whenever possible.
    lines = preview.splitlines() if preview else [""]
    needs_scrollable = total_chars > max_chars or len(lines) > 20
    compact_truncation_chars = min(max_chars, 600)
    compact_mode = False

    if needs_scrollable and ctx is not None:
        header_lines = [
            _("The multiline OCR review window is not supported in this LibreOffice session."),
            _("Please confirm insertion from the preview below:"),
            _("Output summary: {chars} chars, {lines} source lines.").format(
                chars=total_chars,
                lines=total_lines,
            ),
        ]
        result = _show_ocr_preview_scrollable_dialog(title, preview, header_lines, ctx=ctx, parent_frame=parent_frame)
        if result is True:
            return preview
        if result is False:
            logger.debug("OCR preview fallback canceled by user.")
            return None
        # Runtime cannot create a dialog model; keep going with message box fallback.
        logger.debug("show_ocr_preview_fallback: scrollable dialog unavailable; using compact messagebox fallback.")
        needs_scrollable = False
        compact_mode = True

    # Keep non-scrollable fallback as a single confirmation.
    if not needs_scrollable and (total_chars > max_chars or compact_mode):
        compact_preview = _compact_text_with_tail(preview, compact_truncation_chars, max_lines=12)
        compact_preview = compact_preview.strip()
        snippet_block = (
            _("\n{sep}\n{snippet}\n{sep}\n").format(
                sep="-" * min(72, 50 + max(0, total_chars // 150)),
                snippet=compact_preview,
            )
            if compact_preview
            else ""
        )
        message = _(
            "{unsupported}\n\n{summary}{source_info}{snippet_block}"
            "Output was truncated to keep the dialog within view (showing {shown} of {total} chars).\n"
            "Review the source document for full text, then click OK to insert."
        ).format(
            unsupported=_("The multiline OCR review window is not supported in this LibreOffice session."),
            summary=_("Output summary: {chars} chars, {lines} source lines.").format(
                chars=total_chars,
                lines=total_lines,
            ),
            source_info=source_overview,
            snippet_block=snippet_block,
            shown=len(compact_preview),
            total=total_chars,
        )
        response = show_message_box(
            title,
            message,
            type="querybox",
            parent_frame=parent_frame,
            ctx=ctx,
            buttons="ok_cancel",
        )
        if response in (None, 0, "0"):
            logger.debug("OCR preview fallback canceled by user.")
            return None
        return preview

    if not needs_scrollable:
        # In non-scrollable fallback mode, avoid putting very large payloads into
        # a message box that may render poorly in older LibreOffice sessions.
        full_preview = preview.strip()
        if len(full_preview) > max_chars:
            full_preview = preview[:max_chars] + "\n\n" + _("… output truncated")
            logger.debug(
                "show_ocr_preview_fallback: final non-scrollable preview truncated to {max_chars} chars.".format(
                    max_chars=max_chars,
                )
            )
        response = show_message_box(
            title,
            _(
                "{unsupported}\n\n{summary}\n{source_info}{sep}\n{full_text}\n{sep}\n"
                "{action_hint}"
            ).format(
                unsupported=_("The multiline OCR review window is not supported in this LibreOffice session."),
                summary=_("Output summary: {chars} chars, {lines} source lines.").format(
                    chars=total_chars,
                    lines=total_lines,
                ),
                source_info=source_overview + "\n" if source_overview else "",
                sep="-" * min(72, 50 + max(0, total_chars // 150)),
                full_text=full_preview,
                action_hint=_("Click OK to insert the text, or Cancel to stop."),
            ),
            type="querybox",
            parent_frame=parent_frame,
            ctx=ctx,
            buttons="ok_cancel",
        )
        if response in (None, 0, "0"):
            logger.debug("OCR preview fallback canceled by user.")
            return None
        return preview
    return preview

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
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        
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
        dialog_model = create_instance("com.sun.star.awt.UnoControlDialogModel", ctx)
        
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
        settings_file = _settings_file_path()
        if not settings_file:
            raise RuntimeError("Could not resolve settings file path")
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                file_settings = {}
                for line in f:
                    if '=' not in line:
                        continue
                    k, v = line.strip().split('=', 1)
                    if k:
                        file_settings[k.strip()] = v.strip()

            if key in file_settings:
                value = file_settings[key]

                # Compatibility rule for output mode:
                # If the canonical key exists but still points to the default value,
                # honor the legacy `output_mode` key when present because some
                # previous runtime snapshots may have only updated legacy output mode.
                if key == constants.CFG_KEY_DEFAULT_OUTPUT_MODE:
                    canonical_value = str(value).strip().lower()
                    legacy_value = file_settings.get("output_mode")
                    if legacy_value is not None:
                        legacy_value = str(legacy_value).strip()
                        legacy_normalized = legacy_value.replace(" ", "_").replace("-", "_").lower()
                        if canonical_value in ("", constants.DEFAULT_OUTPUT_MODE) and legacy_normalized:
                            logger.debug(
                                "get_setting: Found legacy output_mode={legacy} and default output setting is default cursor. "
                                "Using legacy value for compatibility.".format(legacy=legacy_value)
                            )
                            return legacy_value
                        if not value and legacy_value:
                            logger.debug(
                                "get_setting: Found empty default_output_mode; using legacy output_mode={legacy}.".format(
                                    legacy=legacy_value
                                )
                            )
                            return legacy_value

                logger.debug(f"get_setting: Found {key}={value} in file")
                return value

            # Backward-compatible alias for environments/docs that still use
            # `output_mode` instead of `default_output_mode` in the fallback file.
            if key == constants.CFG_KEY_DEFAULT_OUTPUT_MODE and "output_mode" in file_settings:
                value = file_settings["output_mode"]
                logger.debug(
                    "get_setting: Found legacy output_mode={value} while reading default_output_mode. Using legacy value.".format(
                        value=value
                    )
                )
                return value
    except Exception as e:
        logger.debug(f"get_setting: File fallback failed: {e}")
    
    logger.debug(f"get_setting: Using default for {key}: {default_value}")
    return default_value

def set_setting(key, value, ctx, node=constants.CFG_NODE_SETTINGS):
    """Writes a setting to TejOCR configuration with file-based fallback."""
    # Quick fallback to file-based settings due to configuration schema issues  
    try:
        settings_dir = os.path.dirname(_settings_file_path())
        if not settings_dir:
            raise RuntimeError("Could not resolve settings directory")
        os.makedirs(settings_dir, exist_ok=True)
        settings_file = _settings_file_path()
        
        # Read existing settings
        existing_settings = {}
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        existing_settings[k] = v

        serialized_value = str(value)

        # Keep both output mode keys in sync to remain compatible with older fallback UIs.
        # This prevents cases where a legacy `output_mode` edit overrides `default_output_mode` silently.
        if key == constants.CFG_KEY_DEFAULT_OUTPUT_MODE:
            existing_settings["output_mode"] = serialized_value
        if key == "output_mode":
            existing_settings[constants.CFG_KEY_DEFAULT_OUTPUT_MODE] = serialized_value

        # Update the specific setting
        existing_settings[key] = serialized_value
        
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
        logger.error(f"{_('Error creating temporary file:')} {e}")
        # Fallback if specific dir fails, try default temp location
        try:
            fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)
            return path
        except Exception as e_fallback:
            logger.error(f"{_('Fallback temporary file creation also failed:')} {e_fallback}")
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
    configured_path = (configured_path or "").strip() if isinstance(configured_path, str) else ""
    logger.debug(f"Searching for Tesseract. Configured path: '{configured_path}'")

    def _normalize_candidate(path_candidate):
        if not path_candidate:
            return ""
        expanded = os.path.expandvars(
            os.path.expanduser(str(path_candidate).strip())
        )
        expanded = expanded.strip().strip('"').strip("'")
        normalized = os.path.normpath(expanded)
        if os.path.isdir(normalized):
            return ""
        return normalized
    
    def _is_executable(path_candidate):
        if not path_candidate or not os.path.isfile(path_candidate):
            return False
        return os.access(path_candidate, os.X_OK) or os.path.splitext(path_candidate)[1].lower() in (".exe", ".bat", ".cmd")

    def _candidate_variants(base_path):
        normalized = _normalize_candidate(base_path)
        if not normalized:
            return ()

        if os.path.isdir(normalized):
            return (
                os.path.join(normalized, "tesseract"),
                os.path.join(normalized, "tesseract.exe"),
                os.path.join(normalized, "tesseract.bat"),
                os.path.join(normalized, "tesseract.cmd"),
            )

        if os.path.splitext(normalized)[1]:
            return (normalized,)
        return (
            normalized,
            f"{normalized}.exe",
            f"{normalized}.bat",
            f"{normalized}.cmd",
        )

    # 1) Check environment-provided overrides first.
    explicit_paths = [
        os.environ.get("TESSERACT_PATH"),
        os.environ.get("TESSERACT_CMD"),
        os.environ.get("TESSERACT_EXE")
    ]
    for explicit in explicit_paths:
        for candidate in _candidate_variants(explicit):
            if _is_executable(candidate):
                logger.debug(f"Tesseract found via environment variable: {candidate}")
                return candidate
    
    # 2) Check configured path if provided.
    if configured_path:
        for configured_candidate in _candidate_variants(configured_path):
            if _is_executable(configured_candidate):
                logger.debug(f"Tesseract found from configured path: {configured_candidate}")
                return configured_candidate
        configured_path_cmd = _normalize_candidate(shutil.which(configured_path))
        if _is_executable(configured_path_cmd):
            logger.debug(f"Tesseract found by resolving configured executable '{configured_path}' through PATH: {configured_path_cmd}")
            return configured_path_cmd
    
    # 3) Check current PATH and known wrappers.
    for candidate_name in ("tesseract", "tesseract.exe"):
        found_path = shutil.which(candidate_name)
        if _is_executable(found_path):
            logger.debug(f"Tesseract found on PATH ({candidate_name}): {found_path}")
            return found_path

    # 3b) Windows PATHEXT-aware PATH scan for tesseract command variants.
    if os.name == "nt":
        path_exts = [ext.strip().lower() for ext in (os.environ.get("PATHEXT") or ".exe;.bat;.cmd").split(";")]
        for path_entry in (os.environ.get("PATH") or "").split(os.pathsep):
            if not path_entry:
                continue
            for ext in path_exts:
                if not ext:
                    continue
                if not ext.startswith("."):
                    ext = f".{ext}"
                candidate = os.path.join(path_entry, f"tesseract{ext}")
                if _is_executable(candidate):
                    logger.debug(f"Tesseract found on PATH with extension {ext}: {candidate}")
                    return candidate
    
    # 4) Check common install locations (cross-platform)
    common_locations = [
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
        "/usr/bin/tesseract",
        "/usr/local/Cellar/tesseract/bin/tesseract",
        "/bin/tesseract",
        "/opt/homebrew/opt/tesseract/bin/tesseract",
    ]

    if os.name == "nt":
        windows_root_candidates = [
            os.getenv("ProgramFiles"),
            os.getenv("ProgramFiles(x86)"),
            os.getenv("ProgramW6432"),
            os.getenv("LOCALAPPDATA"),
            os.getenv("APPDATA"),
            os.getenv("USERPROFILE"),
            os.getenv("SCOOP"),
            os.getenv("SCOOP_GLOBAL"),
            os.getenv("ChocolateyInstall"),
        ]

        windows_crumbs = (
            "Tesseract-OCR\\tesseract.exe",
            "Tesseract-OCR\\bin\\tesseract.exe",
            "Programs\\Tesseract-OCR\\tesseract.exe",
            os.path.join("scoop", "apps", "tesseract", "current", "tesseract.exe"),
            os.path.join("scoop", "shims", "tesseract.exe"),
            os.path.join("tesseract", "tesseract.exe"),
            os.path.join("msys64", "mingw64", "bin", "tesseract.exe"),
            os.path.join("msys64", "usr", "bin", "tesseract.exe"),
            os.path.join("mingw64", "bin", "tesseract.exe"),
        )

        direct_windows_locations = (
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\tesseract-ocr\\tesseract.exe",
            r"C:\\tools\\tesseract\\tesseract.exe",
            r"C:\\msys64\\usr\\bin\\tesseract.exe",
            r"C:\\msys64\\mingw64\\bin\\tesseract.exe",
        )

        for root in windows_root_candidates:
            if not root:
                continue
            normalized_root = _normalize_candidate(root)
            if not normalized_root:
                continue
            for crumb in windows_crumbs:
                candidate = os.path.normpath(os.path.join(normalized_root, crumb))
                if _is_executable(candidate):
                    logger.debug(f"Tesseract found in windows install root {normalized_root}: {candidate}")
                    return candidate

        for location in direct_windows_locations:
            candidate = os.path.normpath(os.path.expandvars(location))
            if _is_executable(candidate):
                logger.debug(f"Tesseract found in direct windows location: {candidate}")
                return candidate
    
    for path in common_locations:
        expanded_candidate = os.path.expandvars(path)
        normalized_candidate = os.path.normpath(expanded_candidate)
        if _is_executable(normalized_candidate):
            logger.debug(f"Tesseract found in common location: {normalized_candidate}")
            return normalized_candidate
    
    logger.warning("Tesseract executable not found in common locations or PATH.")
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
