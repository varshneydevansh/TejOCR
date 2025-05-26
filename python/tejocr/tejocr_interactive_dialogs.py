# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Working interactive dialogs for TejOCR using UNO dialog toolkit."""

import uno
import unohelper
import os
from com.sun.star.awt import XActionListener, XTextListener
from com.sun.star.ui.dialogs import TemplateDescription

from tejocr import uno_utils
from tejocr import constants
from tejocr import tejocr_engine 
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext
logger = uno_utils.get_logger("TejOCR.InteractiveDialogs")

class SettingsActionListener(unohelper.Base, XActionListener):
    """Action listener for settings dialog buttons."""
    
    def __init__(self, dialog_ref, ctx_ref):
        self.dialog = dialog_ref
        self.ctx = ctx_ref
    
    def actionPerformed(self, event):
        try:
            button_name = event.Source.getModel().getName()
            status_control = self.dialog.getControl("status")
            
            if button_name == "auto_button":
                # Auto-detect Tesseract
                detected_path = uno_utils.find_tesseract_executable()
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
                uno_utils.show_message_box("Installation Help", help_text, "infobox", ctx=self.ctx)
            
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
                    
                    if success:
                        status_control.setText("✅ Test successful! Dependencies are working.")
                    else:
                        status_control.setText(f"❌ Test failed: {message}")
                except Exception as e:
                    status_control.setText(f"❌ Test error: {e}")
            
        except Exception as e:
            logger.error(f"Settings dialog action error: {e}")
    
    def disposing(self, event):
        pass

# =============================================================================
# SIMPLIFIED WORKING DIALOGS WITH FALLBACK APPROACH
# =============================================================================

def create_settings_dialog(ctx, parent_frame=None):
    """Creates the actual UNO settings dialog with proper controls."""
    try:
        # Create dialog model
        dialog_model = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 100)
        dialog_model.setPropertyValue("PositionY", 100) 
        dialog_model.setPropertyValue("Width", 450)
        dialog_model.setPropertyValue("Height", 320)
        dialog_model.setPropertyValue("Title", _("TejOCR v0.1.6 - Settings"))
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Create status group box
        status_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        status_group.setPropertyValue("PositionX", 10)
        status_group.setPropertyValue("PositionY", 10)
        status_group.setPropertyValue("Width", 430)
        status_group.setPropertyValue("Height", 80)
        status_group.setPropertyValue("Label", _("System & Dependency Status"))
        dialog_model.insertByName("status_group", status_group)
        
        # Tesseract status label
        tesseract_status = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        tesseract_status.setPropertyValue("PositionX", 20)
        tesseract_status.setPropertyValue("PositionY", 30)
        tesseract_status.setPropertyValue("Width", 200)
        tesseract_status.setPropertyValue("Height", 12)
        tesseract_status.setPropertyValue("Label", _("Tesseract OCR: Checking..."))
        dialog_model.insertByName("tesseract_status", tesseract_status)
        
        # Refresh button
        refresh_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        refresh_btn.setPropertyValue("PositionX", 250)
        refresh_btn.setPropertyValue("PositionY", 60)
        refresh_btn.setPropertyValue("Width", 80)
        refresh_btn.setPropertyValue("Height", 20)
        refresh_btn.setPropertyValue("Label", _("Refresh Status"))
        refresh_btn.setPropertyValue("ActionCommand", "refresh_action")
        dialog_model.insertByName("refresh_btn", refresh_btn)
        
        # Help button
        help_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        help_btn.setPropertyValue("PositionX", 340)
        help_btn.setPropertyValue("PositionY", 60)
        help_btn.setPropertyValue("Width", 90)
        help_btn.setPropertyValue("Height", 20)
        help_btn.setPropertyValue("Label", _("Installation Help..."))
        help_btn.setPropertyValue("ActionCommand", "help_action")
        dialog_model.insertByName("help_btn", help_btn)
        
        # Tesseract config group
        tesseract_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        tesseract_group.setPropertyValue("PositionX", 10)
        tesseract_group.setPropertyValue("PositionY", 100)
        tesseract_group.setPropertyValue("Width", 430)
        tesseract_group.setPropertyValue("Height", 80)
        tesseract_group.setPropertyValue("Label", _("Tesseract OCR Configuration"))
        dialog_model.insertByName("tesseract_group", tesseract_group)
        
        # Path label
        path_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        path_label.setPropertyValue("PositionX", 20)
        path_label.setPropertyValue("PositionY", 120)
        path_label.setPropertyValue("Width", 100)
        path_label.setPropertyValue("Height", 12)
        path_label.setPropertyValue("Label", _("Path to Tesseract:"))
        dialog_model.insertByName("path_label", path_label)
        
        # Path text field
        path_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        path_text.setPropertyValue("PositionX", 20)
        path_text.setPropertyValue("PositionY", 135)
        path_text.setPropertyValue("Width", 280)
        path_text.setPropertyValue("Height", 15)
        current_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
        path_text.setPropertyValue("Text", current_path)
        dialog_model.insertByName("path_text", path_text)
        
        # Browse button
        browse_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        browse_btn.setPropertyValue("PositionX", 310)
        browse_btn.setPropertyValue("PositionY", 135)
        browse_btn.setPropertyValue("Width", 40)
        browse_btn.setPropertyValue("Height", 15)
        browse_btn.setPropertyValue("Label", _("Browse..."))
        browse_btn.setPropertyValue("ActionCommand", "browse_action")
        dialog_model.insertByName("browse_btn", browse_btn)
        
        # Auto-detect button
        auto_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        auto_btn.setPropertyValue("PositionX", 355)
        auto_btn.setPropertyValue("PositionY", 135)
        auto_btn.setPropertyValue("Width", 40)
        auto_btn.setPropertyValue("Height", 15)
        auto_btn.setPropertyValue("Label", _("Auto-Detect"))
        auto_btn.setPropertyValue("ActionCommand", "auto_action")
        dialog_model.insertByName("auto_btn", auto_btn)
        
        # Test button
        test_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        test_btn.setPropertyValue("PositionX", 400)
        test_btn.setPropertyValue("PositionY", 135)
        test_btn.setPropertyValue("Width", 30)
        test_btn.setPropertyValue("Height", 15)
        test_btn.setPropertyValue("Label", _("Test"))
        test_btn.setPropertyValue("ActionCommand", "test_action")
        dialog_model.insertByName("test_btn", test_btn)
        
        # Test result label
        test_result = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        test_result.setPropertyValue("PositionX", 20)
        test_result.setPropertyValue("PositionY", 155)
        test_result.setPropertyValue("Width", 400)
        test_result.setPropertyValue("Height", 12)
        test_result.setPropertyValue("Label", _("Test Result: Ready to test"))
        dialog_model.insertByName("test_result", test_result)
        
        # Preferences group
        prefs_group = dialog_model.createInstance("com.sun.star.awt.UnoControlGroupBoxModel")
        prefs_group.setPropertyValue("PositionX", 10)
        prefs_group.setPropertyValue("PositionY", 190)
        prefs_group.setPropertyValue("Width", 430)
        prefs_group.setPropertyValue("Height", 80)
        prefs_group.setPropertyValue("Label", _("Default OCR Preferences"))
        dialog_model.insertByName("prefs_group", prefs_group)
        
        # Language label
        lang_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label.setPropertyValue("PositionX", 20)
        lang_label.setPropertyValue("PositionY", 210)
        lang_label.setPropertyValue("Width", 100)
        lang_label.setPropertyValue("Height", 12)
        lang_label.setPropertyValue("Label", _("Default Language:"))
        dialog_model.insertByName("lang_label", lang_label)
        
        # Language text field
        lang_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text.setPropertyValue("PositionX", 120)
        lang_text.setPropertyValue("PositionY", 210)
        lang_text.setPropertyValue("Width", 60)
        lang_text.setPropertyValue("Height", 15)
        current_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
        lang_text.setPropertyValue("Text", current_lang)
        dialog_model.insertByName("lang_text", lang_text)
        
        # Output mode label
        output_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_label.setPropertyValue("PositionX", 200)
        output_label.setPropertyValue("PositionY", 210)
        output_label.setPropertyValue("Width", 80)
        output_label.setPropertyValue("Height", 12)
        output_label.setPropertyValue("Label", _("Default Output:"))
        dialog_model.insertByName("output_label", output_label)
        
        # Output combo box
        output_combo = dialog_model.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        output_combo.setPropertyValue("PositionX", 285)
        output_combo.setPropertyValue("PositionY", 210)
        output_combo.setPropertyValue("Width", 140)
        output_combo.setPropertyValue("Height", 15)
        output_combo.setPropertyValue("Dropdown", True)
        output_combo.setPropertyValue("ReadOnly", True)
        # Fix StringItemList type error - ensure all items are strings
        output_items = ["Insert at Cursor", "Copy to Clipboard", "New Text Box"]
        output_combo.setPropertyValue("StringItemList", tuple(output_items))
        # Set current selection
        current_output = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, ctx)
        if current_output == constants.OUTPUT_MODE_CURSOR:
            output_combo.setPropertyValue("Text", output_items[0])
        elif current_output == constants.OUTPUT_MODE_CLIPBOARD:
            output_combo.setPropertyValue("Text", output_items[1])
        else:
            output_combo.setPropertyValue("Text", output_items[2])
        dialog_model.insertByName("output_combo", output_combo)
        
        # Improve image checkbox
        improve_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        improve_check.setPropertyValue("PositionX", 20)
        improve_check.setPropertyValue("PositionY", 235)
        improve_check.setPropertyValue("Width", 300)
        improve_check.setPropertyValue("Height", 15)
        improve_check.setPropertyValue("Label", _("Improve low-quality images by default"))
        current_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
        improve_check.setPropertyValue("State", 1 if current_improve else 0)
        dialog_model.insertByName("improve_check", improve_check)
        
        # Save button
        save_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        save_btn.setPropertyValue("PositionX", 280)
        save_btn.setPropertyValue("PositionY", 280)
        save_btn.setPropertyValue("Width", 70)
        save_btn.setPropertyValue("Height", 25)
        save_btn.setPropertyValue("Label", _("Save"))
        save_btn.setPropertyValue("DefaultButton", True)
        save_btn.setPropertyValue("ActionCommand", "save_action")
        dialog_model.insertByName("save_btn", save_btn)
        
        # Cancel button
        cancel_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_btn.setPropertyValue("PositionX", 360)
        cancel_btn.setPropertyValue("PositionY", 280)
        cancel_btn.setPropertyValue("Width", 70)
        cancel_btn.setPropertyValue("Height", 25)
        cancel_btn.setPropertyValue("Label", _("Cancel"))
        cancel_btn.setPropertyValue("ActionCommand", "cancel_action")
        dialog_model.insertByName("cancel_btn", cancel_btn)
        
        return dialog_model
        
    except Exception as e:
        logger.error(f"Failed to create settings dialog model: {e}")
        return None

def show_interactive_settings_dialog(ctx, parent_frame=None):
    """Shows the interactive settings dialog."""
    logger.debug("show_interactive_settings_dialog called")
    
    try:
        dialog_model = create_settings_dialog(ctx, parent_frame)
        if not dialog_model:
            raise Exception("Failed to create dialog model")
        
        # Create dialog control
        dialog_control = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        dialog_control.setModel(dialog_model)
        
        # Create parent peer
        toolkit = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except:
                parent_peer = toolkit.getDesktopWindow()
        else:
            parent_peer = toolkit.getDesktopWindow()
        
        dialog_control.createPeer(toolkit, parent_peer)
        
        # Update status immediately
        try:
            is_ready, msg = tejocr_engine.is_tesseract_ready(ctx, show_gui_errors=False)
            status_icon = "✅" if is_ready else "❌"
            status_text = f"Tesseract OCR: {status_icon} {msg}"
            dialog_control.getControl("tesseract_status").setText(status_text)
        except Exception as e:
            dialog_control.getControl("tesseract_status").setText(f"❌ Error checking status: {e}")
        
        # Add action listeners
        class SettingsDialogListener(unohelper.Base, XActionListener):
            def __init__(self, dialog_ctrl, ctx_ref):
                self.dialog = dialog_ctrl
                self.ctx = ctx_ref
                self.result = False
            
            def actionPerformed(self, event):
                try:
                    # Use ActionCommand instead of getName to fix the error
                    action_command = event.ActionCommand
                    
                    if action_command == "save_action":
                        # Save all settings
                        path_text = self.dialog.getControl("path_text").getText().strip()
                        lang_text = self.dialog.getControl("lang_text").getText().strip()
                        output_text = self.dialog.getControl("output_combo").getText()
                        improve_state = self.dialog.getControl("improve_check").getState()
                        
                        # Save path
                        uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, path_text, self.ctx)
                        
                        # Save language
                        if lang_text and len(lang_text) >= 3:
                            uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, lang_text.lower(), self.ctx)
                        
                        # Save output mode
                        if "Insert at Cursor" in output_text:
                            uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, self.ctx)
                        elif "Copy to Clipboard" in output_text:
                            uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_CLIPBOARD, self.ctx)
                        else:
                            uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_TEXTBOX, self.ctx)
                        
                        # Save improve setting
                        uno_utils.set_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "true" if improve_state else "false", self.ctx)
                        
                        self.result = True
                        self.dialog.endExecute()
                    
                    elif action_command == "cancel_action":
                        self.result = False
                        self.dialog.endExecute()
                    
                    elif action_command == "auto_action":
                        # Auto-detect Tesseract
                        detected_path = uno_utils.find_tesseract_executable()
                        if detected_path:
                            self.dialog.getControl("path_text").setText(detected_path)
                            self.dialog.getControl("test_result").setText(f"✅ Auto-detected: {detected_path}")
                        else:
                            self.dialog.getControl("test_result").setText("❌ Could not auto-detect Tesseract path")
                    
                    elif action_command == "test_action":
                        # Test current path
                        test_path = self.dialog.getControl("path_text").getText().strip()
                        try:
                            if test_path:
                                success, message = tejocr_engine.check_tesseract_path(
                                    test_path, ctx=self.ctx, show_success=False, show_gui_errors=False
                                )
                            else:
                                success, message = tejocr_engine.is_tesseract_ready(
                                    self.ctx, show_gui_errors=False
                                )
                            
                            if success:
                                self.dialog.getControl("test_result").setText("✅ Test successful! Dependencies are working.")
                            else:
                                self.dialog.getControl("test_result").setText(f"❌ Test failed: {message}")
                        except Exception as e:
                            self.dialog.getControl("test_result").setText(f"❌ Test error: {e}")
                    
                    elif action_command == "refresh_action":
                        # Refresh status
                        try:
                            is_ready, msg = tejocr_engine.is_tesseract_ready(self.ctx, show_gui_errors=False)
                            status_icon = "✅" if is_ready else "❌"
                            status_text = f"Tesseract OCR: {status_icon} {msg}"
                            self.dialog.getControl("tesseract_status").setText(status_text)
                        except Exception as e:
                            self.dialog.getControl("tesseract_status").setText(f"❌ Error checking status: {e}")
                    
                    elif action_command == "browse_action":
                        # Browse for Tesseract executable
                        try:
                            file_path = uno_utils.show_file_picker(
                                title="Select Tesseract Executable",
                                filter_name="Executable Files",
                                filter_pattern="*",
                                ctx=self.ctx
                            )
                            if file_path:
                                self.dialog.getControl("path_text").setText(file_path)
                                self.dialog.getControl("test_result").setText(f"Selected: {file_path}")
                        except Exception as e:
                            self.dialog.getControl("test_result").setText(f"❌ Browse error: {e}")
                    
                    elif action_command == "help_action":
                        # Show installation help
                        help_text = (
                            "TejOCR Installation Guide:\n\n"
                            "macOS: brew install tesseract tesseract-lang\n"
                            "Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-[lang]\n"
                            "Windows: Download from GitHub releases\n\n"
                            "For more languages:\n"
                            "Visit: https://tesseract-ocr.github.io/tessdoc/"
                        )
                        uno_utils.show_message_box("Installation Help", help_text, "infobox", ctx=self.ctx)
                
                except Exception as e:
                    logger.error(f"Settings dialog action error: {e}")
            
            def disposing(self, event):
                pass
        
        listener = SettingsDialogListener(dialog_control, ctx)
        
        # Add listeners to buttons
        for btn_name in ["save_btn", "cancel_btn", "auto_btn", "test_btn", "refresh_btn", "help_btn", "browse_btn"]:
            try:
                dialog_control.getControl(btn_name).addActionListener(listener)
            except:
                pass
        
        # Execute dialog
        result = dialog_control.execute()
        
        # Clean up
        dialog_control.dispose()
        
        return listener.result
        
    except Exception as e:
        logger.error(f"Failed to show interactive settings dialog: {e}")
        # Fallback to simple prompts
        return _show_fallback_settings_prompts(ctx, parent_frame)

def _show_fallback_settings_prompts(ctx, parent_frame=None):
    """Fallback to simple input prompts if dialog creation fails."""
    logger.info("Using fallback individual setting prompts")
    
    # Get current settings
    current_path = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx)
    current_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
    
    # Show dependency status first
    try:
        is_ready, msg = tejocr_engine.is_tesseract_ready(ctx, show_gui_errors=False)
        status_icon = "✅" if is_ready else "❌"
        status_msg = f"Tesseract Status: {status_icon} {msg}\n\nWould you like to configure TejOCR settings?"
        
        result = uno_utils.show_message_box(
            title=_("TejOCR Settings"),
            message=status_msg,
            type="querybox",
            buttons="yes_no_cancel",
            parent_frame=parent_frame,
            ctx=ctx
        )
        
        if result != 2:  # Not YES
            return False
            
    except Exception:
        # Even simpler fallback
        result = uno_utils.show_message_box(
            title=_("TejOCR Settings"), 
            message=_("Configure TejOCR settings?"),
            type="querybox",
            buttons="yes_no_cancel", 
            parent_frame=parent_frame,
            ctx=ctx
        )
        if result != 2:
            return False
    
    # Tesseract Path Configuration
    new_path = uno_utils.show_input_box(
        title=_("Tesseract Path"),
        message=_("Enter path to Tesseract executable (leave blank for auto-detect):"),
        default_text=current_path,
        ctx=ctx,
        parent_frame=parent_frame
    )
    
    if new_path is not None:  # User didn't cancel
        uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, new_path, ctx)
    
    # Default Language Configuration  
    new_lang = uno_utils.show_input_box(
        title=_("Default OCR Language"),
        message=_("Enter default language code for OCR (e.g., eng, hin, fra, deu):"),
        default_text=current_lang,
        ctx=ctx,
        parent_frame=parent_frame
    )
    
    if new_lang is not None and len(new_lang.strip()) >= 3:
        uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, new_lang.strip().lower(), ctx)
    
    # Output mode preference
    output_choice = uno_utils.show_message_box(
        title=_("Default Output Mode"),
        message=_("Choose default output mode:\n\nYES = Insert at cursor\nNO = Copy to clipboard\nCANCEL = Create text box"),
        type="querybox",
        buttons="yes_no_cancel",
        parent_frame=parent_frame,
        ctx=ctx
    )
    
    if output_choice == 2:  # YES
        uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, ctx)
    elif output_choice == 3:  # NO  
        uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_CLIPBOARD, ctx)
    elif output_choice == 4:  # CANCEL
        uno_utils.set_setting("default_output_mode", constants.OUTPUT_MODE_TEXTBOX, ctx)
    
    # Image improvement preference
    improve_choice = uno_utils.show_message_box(
        title=_("Image Quality"),
        message=_("Improve low-quality images by default?\n(This makes OCR slower but more accurate)"),
        type="querybox", 
        buttons="yes_no_cancel",
        parent_frame=parent_frame,
        ctx=ctx
    )
    
    if improve_choice == 2:  # YES
        uno_utils.set_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "true", ctx)
    elif improve_choice == 3:  # NO
        uno_utils.set_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx)
    
    return True

def create_ocr_options_dialog(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Creates the actual UNO OCR options dialog with proper controls."""
    try:
        # Create dialog model
        dialog_model = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        
        # Set dialog properties
        dialog_model.setPropertyValue("PositionX", 150)
        dialog_model.setPropertyValue("PositionY", 150) 
        dialog_model.setPropertyValue("Width", 320)
        dialog_model.setPropertyValue("Height", 200)
        dialog_model.setPropertyValue("Title", _("OCR Options"))
        dialog_model.setPropertyValue("Closeable", True)
        dialog_model.setPropertyValue("Moveable", True)
        
        # Source info label
        source_desc = _("selected image") if source_type == "selected" else f"'{os.path.basename(image_path)}'" if image_path else _("file")
        source_info = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        source_info.setPropertyValue("PositionX", 10)
        source_info.setPropertyValue("PositionY", 10)
        source_info.setPropertyValue("Width", 300)
        source_info.setPropertyValue("Height", 12)
        source_info.setPropertyValue("Label", f"Processing: {source_desc}")
        dialog_model.insertByName("source_info", source_info)
        
        # Language label
        lang_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_label.setPropertyValue("PositionX", 10)
        lang_label.setPropertyValue("PositionY", 35)
        lang_label.setPropertyValue("Width", 60)
        lang_label.setPropertyValue("Height", 12)
        lang_label.setPropertyValue("Label", _("Language:"))
        dialog_model.insertByName("lang_label", lang_label)
        
        # Language text field
        lang_text = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
        lang_text.setPropertyValue("PositionX", 75)
        lang_text.setPropertyValue("PositionY", 35)
        lang_text.setPropertyValue("Width", 80)
        lang_text.setPropertyValue("Height", 15)
        default_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
        lang_text.setPropertyValue("Text", default_lang)
        dialog_model.insertByName("lang_text", lang_text)
        
        # Language hint
        lang_hint = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lang_hint.setPropertyValue("PositionX", 165)
        lang_hint.setPropertyValue("PositionY", 35)
        lang_hint.setPropertyValue("Width", 140)
        lang_hint.setPropertyValue("Height", 12)
        lang_hint.setPropertyValue("Label", _("(e.g., eng, hin, fra)"))
        dialog_model.insertByName("lang_hint", lang_hint)
        
        # Output label
        output_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        output_label.setPropertyValue("PositionX", 10)
        output_label.setPropertyValue("PositionY", 60)
        output_label.setPropertyValue("Width", 60)
        output_label.setPropertyValue("Height", 12)
        output_label.setPropertyValue("Label", _("Output As:"))
        dialog_model.insertByName("output_label", output_label)
        
        # Radio button group for output modes
        current_output = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, ctx)
        
        # Insert at cursor radio
        cursor_radio = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        cursor_radio.setPropertyValue("PositionX", 10)
        cursor_radio.setPropertyValue("PositionY", 75)
        cursor_radio.setPropertyValue("Width", 140)
        cursor_radio.setPropertyValue("Height", 12)
        cursor_radio.setPropertyValue("Label", _("Insert at current cursor"))
        cursor_radio.setPropertyValue("State", 1 if current_output == constants.OUTPUT_MODE_CURSOR else 0)
        dialog_model.insertByName("cursor_radio", cursor_radio)
        
        # New text box radio
        textbox_radio = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        textbox_radio.setPropertyValue("PositionX", 160)
        textbox_radio.setPropertyValue("PositionY", 75)
        textbox_radio.setPropertyValue("Width", 140)
        textbox_radio.setPropertyValue("Height", 12)
        textbox_radio.setPropertyValue("Label", _("New Text Box"))
        textbox_radio.setPropertyValue("State", 1 if current_output == constants.OUTPUT_MODE_TEXTBOX else 0)
        dialog_model.insertByName("textbox_radio", textbox_radio)
        
        # Copy to clipboard radio
        clipboard_radio = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
        clipboard_radio.setPropertyValue("PositionX", 10)
        clipboard_radio.setPropertyValue("PositionY", 90)
        clipboard_radio.setPropertyValue("Width", 140)
        clipboard_radio.setPropertyValue("Height", 12)
        clipboard_radio.setPropertyValue("Label", _("Copy to clipboard"))
        clipboard_radio.setPropertyValue("State", 1 if current_output == constants.OUTPUT_MODE_CLIPBOARD else 0)
        dialog_model.insertByName("clipboard_radio", clipboard_radio)
        
        # Replace image radio (only for selected images)
        if source_type == "selected":
            replace_radio = dialog_model.createInstance("com.sun.star.awt.UnoControlRadioButtonModel")
            replace_radio.setPropertyValue("PositionX", 160)
            replace_radio.setPropertyValue("PositionY", 90)
            replace_radio.setPropertyValue("Width", 140)
            replace_radio.setPropertyValue("Height", 12)
            replace_radio.setPropertyValue("Label", _("Replace Image"))
            replace_radio.setPropertyValue("State", 1 if current_output == constants.OUTPUT_MODE_REPLACE else 0)
            dialog_model.insertByName("replace_radio", replace_radio)
        
        # Improve image checkbox
        improve_check = dialog_model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        improve_check.setPropertyValue("PositionX", 10)
        improve_check.setPropertyValue("PositionY", 115)
        improve_check.setPropertyValue("Width", 250)
        improve_check.setPropertyValue("Height", 15)
        improve_check.setPropertyValue("Label", _("Improve image quality"))
        default_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
        improve_check.setPropertyValue("State", 1 if default_improve else 0)
        dialog_model.insertByName("improve_check", improve_check)
        
        # Status label
        status_label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        status_label.setPropertyValue("PositionX", 10)
        status_label.setPropertyValue("PositionY", 140)
        status_label.setPropertyValue("Width", 300)
        status_label.setPropertyValue("Height", 12)
        status_label.setPropertyValue("Label", _("Status: Ready"))
        dialog_model.insertByName("status_label", status_label)
        
        # Start OCR button
        start_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        start_btn.setPropertyValue("PositionX", 160)
        start_btn.setPropertyValue("PositionY", 165)
        start_btn.setPropertyValue("Width", 70)
        start_btn.setPropertyValue("Height", 25)
        start_btn.setPropertyValue("Label", _("Start OCR"))
        start_btn.setPropertyValue("DefaultButton", True)
        start_btn.setPropertyValue("ActionCommand", "start_ocr_action")
        dialog_model.insertByName("start_btn", start_btn)
        
        # Cancel button
        cancel_btn = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel_btn.setPropertyValue("PositionX", 240)
        cancel_btn.setPropertyValue("PositionY", 165)
        cancel_btn.setPropertyValue("Width", 70)
        cancel_btn.setPropertyValue("Height", 25)
        cancel_btn.setPropertyValue("Label", _("Cancel"))
        cancel_btn.setPropertyValue("ActionCommand", "cancel_ocr_action")
        dialog_model.insertByName("cancel_btn", cancel_btn)
        
        return dialog_model
        
    except Exception as e:
        logger.error(f"Failed to create OCR options dialog model: {e}")
        return None

def show_interactive_ocr_options_dialog(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Shows the interactive OCR options dialog."""
    logger.debug(f"show_interactive_ocr_options_dialog called for source: {source_type}")
    
    try:
        dialog_model = create_ocr_options_dialog(ctx, parent_frame, source_type, image_path)
        if not dialog_model:
            raise Exception("Failed to create dialog model")
        
        # Create dialog control
        dialog_control = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        dialog_control.setModel(dialog_model)
        
        # Create parent peer
        toolkit = ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        
        if parent_frame:
            try:
                parent_peer = parent_frame.getContainerWindow().getPeer()
            except:
                parent_peer = toolkit.getDesktopWindow()
        else:
            parent_peer = toolkit.getDesktopWindow()
        
        dialog_control.createPeer(toolkit, parent_peer)
        
        # Add action listeners
        class OCROptionsDialogListener(unohelper.Base, XActionListener):
            def __init__(self, dialog_ctrl, ctx_ref, source_type_ref):
                self.dialog = dialog_ctrl
                self.ctx = ctx_ref
                self.source_type = source_type_ref
                self.result_lang = None
                self.result_output = None
                self.result_improve = False
                self.cancelled = True
            
            def actionPerformed(self, event):
                try:
                    # Use ActionCommand instead of getName to fix the error
                    action_command = event.ActionCommand
                    
                    if action_command == "start_ocr_action":
                        # Get selected options
                        self.result_lang = self.dialog.getControl("lang_text").getText().strip()
                        if not self.result_lang:
                            self.result_lang = constants.DEFAULT_OCR_LANGUAGE
                        
                        # Determine output mode from radio buttons
                        if self.dialog.getControl("cursor_radio").getState():
                            self.result_output = constants.OUTPUT_MODE_CURSOR
                        elif self.dialog.getControl("clipboard_radio").getState():
                            self.result_output = constants.OUTPUT_MODE_CLIPBOARD
                        elif self.dialog.getControl("textbox_radio").getState():
                            self.result_output = constants.OUTPUT_MODE_TEXTBOX
                        elif self.source_type == "selected" and hasattr(self.dialog, "getControl"):
                            try:
                                if self.dialog.getControl("replace_radio").getState():
                                    self.result_output = constants.OUTPUT_MODE_REPLACE
                            except:
                                pass
                        
                        if not self.result_output:
                            self.result_output = constants.OUTPUT_MODE_CURSOR
                        
                        self.result_improve = bool(self.dialog.getControl("improve_check").getState())
                        self.cancelled = False
                        self.dialog.endExecute()
                    
                    elif action_command == "cancel_ocr_action":
                        self.cancelled = True
                        self.dialog.endExecute()
                
                except Exception as e:
                    logger.error(f"OCR options dialog action error: {e}")
            
            def disposing(self, event):
                pass
        
        listener = OCROptionsDialogListener(dialog_control, ctx, source_type)
        
        # Add listeners to buttons
        for btn_name in ["start_btn", "cancel_btn"]:
            try:
                dialog_control.getControl(btn_name).addActionListener(listener)
            except:
                pass
        
        # Execute dialog
        result = dialog_control.execute()
        
        # Clean up
        dialog_control.dispose()
        
        if listener.cancelled:
            return None, None, False
        else:
            return listener.result_lang, listener.result_output, listener.result_improve
        
    except Exception as e:
        logger.error(f"Failed to show interactive OCR options dialog: {e}")
        # Fallback to simple prompts
        return _show_fallback_ocr_options_prompts(ctx, parent_frame, source_type, image_path)

def _show_fallback_ocr_options_prompts(ctx, parent_frame=None, source_type="selected", image_path=None):
    """Fallback to simple input prompts if dialog creation fails."""
    logger.info("Using fallback OCR options prompts")
    
    # Smart defaults from settings 
    default_lang = uno_utils.get_setting(constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, ctx)
    default_output = uno_utils.get_setting("default_output_mode", constants.OUTPUT_MODE_CURSOR, ctx)
    default_improve = uno_utils.get_setting(constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT, "false", ctx).lower() == "true"
    
    # Check if user wants to use defaults or customize this operation
    source_desc = _("selected image") if source_type == "selected" else f"'{os.path.basename(image_path)}'" if image_path else _("file")
    
    quick_msg = _(
        "Ready to extract text from {source}\n\n"
        "Default settings:\n"
        "• Language: {lang}\n" 
        "• Output: {output}\n"
        "• Improve quality: {improve}\n\n"
        "YES = Use these defaults\n"
        "NO = Customize for this operation\n"
        "CANCEL = Abort OCR"
    ).format(
        source=source_desc,
        lang=default_lang,
        output=_("Insert at cursor") if default_output == constants.OUTPUT_MODE_CURSOR 
               else _("Copy to clipboard") if default_output == constants.OUTPUT_MODE_CLIPBOARD
               else _("Create text box"),
        improve=_("Yes") if default_improve else _("No")
    )
    
    quick_choice = uno_utils.show_message_box(
        title=_("OCR Options"),
        message=quick_msg,
        type="querybox",
        buttons="yes_no_cancel",
        parent_frame=parent_frame,
        ctx=ctx
    )
    
    if quick_choice == 4:  # CANCEL
        return None, None, False
    elif quick_choice == 2:  # YES - use defaults
        return default_lang, default_output, default_improve
    
    # NO - customize this operation
    logger.debug("User chose to customize OCR options")
    
    # Language customization
    custom_lang = uno_utils.show_input_box(
        title=_("Language for This OCR"),
        message=_("Enter language code for this OCR operation:"),
        default_text=default_lang,
        ctx=ctx,
        parent_frame=parent_frame
    )
    
    if custom_lang is None:  # User cancelled
        return None, None, False
    
    final_lang = custom_lang.strip().lower() if custom_lang.strip() else default_lang
    
    # Output mode customization
    output_msg = _(
        "Where should the extracted text go?\n\n"
        "YES = Insert at cursor position\n"
        "NO = Copy to clipboard\n"
        "CANCEL = Create new text box"
    )
    
    if source_type == "selected":
        output_msg += _("\n\n(Note: 'Replace image' option available in advanced settings)")
    
    output_choice = uno_utils.show_message_box(
        title=_("Output Destination"),
        message=output_msg,
        type="querybox",
        buttons="yes_no_cancel", 
        parent_frame=parent_frame,
        ctx=ctx
    )
    
    if output_choice == 2:  # YES
        final_output = constants.OUTPUT_MODE_CURSOR
    elif output_choice == 3:  # NO
        final_output = constants.OUTPUT_MODE_CLIPBOARD  
    elif output_choice == 4:  # CANCEL
        final_output = constants.OUTPUT_MODE_TEXTBOX
    else:
        final_output = default_output  # Fallback
    
    # Image improvement customization
    improve_msg = _(
        "Improve image quality for better OCR?\n\n"
        "YES = Enhance image (slower but more accurate)\n"
        "NO = Use image as-is (faster)\n"
        "CANCEL = Use default setting"
    )
    
    improve_choice = uno_utils.show_message_box(
        title=_("Image Quality"),
        message=improve_msg,
        type="querybox",
        buttons="yes_no_cancel",
        parent_frame=parent_frame,
        ctx=ctx
    )
    
    if improve_choice == 2:  # YES
        final_improve = True
    elif improve_choice == 3:  # NO
        final_improve = False
    else:  # CANCEL or other
        final_improve = default_improve
    
    logger.info(f"Custom OCR options: lang='{final_lang}', mode='{final_output}', improve={final_improve}")
    return final_lang, final_output, final_improve

# =============================================================================
# PUBLIC WRAPPER CLASSES FOR TEJOCR_SERVICE.PY INTEGRATION  
# =============================================================================

class InteractiveSettingsDialogHandler:
    """Public wrapper for the interactive settings dialog."""
    
    def __init__(self, ctx, parent_frame=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
    
    def show_dialog(self):
        """Shows the interactive settings dialog and returns True if settings were saved."""
        return show_interactive_settings_dialog(self.ctx, self.parent_frame)

class InteractiveOptionsDialogHandler:
    """Public wrapper for the interactive OCR options dialog."""
    
    def __init__(self, ctx, parent_frame=None, source_type="selected", image_path=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
        self.source_type = source_type
        self.image_path = image_path
        
    def show_dialog(self):
        """Shows the OCR options dialog and returns (language, output_mode, improve_image)."""
        return show_interactive_ocr_options_dialog(self.ctx, self.parent_frame, self.source_type, self.image_path)