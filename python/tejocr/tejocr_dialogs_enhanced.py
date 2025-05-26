# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Enhanced dialog handlers for TejOCR with XDL-based user interfaces."""

import uno
import unohelper
import os
import threading
import time

from com.sun.star.awt import XActionListener, XItemListener
from com.sun.star.lang import XEventListener

from tejocr import uno_utils
from tejocr import constants
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext
logger = uno_utils.get_logger("TejOCR.EnhancedDialogs")

class SettingsDialogHandler(unohelper.Base, XActionListener, XItemListener):
    """Handler for the enhanced settings dialog."""
    
    def __init__(self, ctx, parent_frame):
        self.ctx = ctx
        self.parent_frame = parent_frame
        self.dialog = None
        self.dialog_provider = None
        self.settings_changed = False
        
    def show_dialog(self):
        """Show the settings dialog."""
        try:
            # Create dialog provider
            self.dialog_provider = uno_utils.create_instance(
                "com.sun.star.awt.DialogProvider", self.ctx
            )
            
            if not self.dialog_provider:
                logger.error("Could not create DialogProvider")
                return self._fallback_to_message_boxes()
            
            # Get dialog URL - try multiple paths
            dialog_paths = [
                "vnd.sun.star.script:TejOCR.dialogs.tejocr_settings_dialog?location=application",
                "file:///dialogs/tejocr_settings_dialog.xdl",
                os.path.join(os.path.dirname(__file__), "..", "..", "dialogs", "tejocr_settings_dialog.xdl")
            ]
            
            dialog_url = None
            for path in dialog_paths:
                try:
                    if path.startswith("file://") or path.startswith("vnd.sun.star.script:"):
                        dialog_url = path
                    else:
                        # Convert local path to file URL
                        if os.path.exists(path):
                            dialog_url = unohelper.systemPathToFileUrl(path)
                    
                    if dialog_url:
                        self.dialog = self.dialog_provider.createDialog(dialog_url)
                        if self.dialog:
                            logger.info(f"Successfully loaded dialog from: {path}")
                            break
                except Exception as e:
                    logger.debug(f"Failed to load dialog from {path}: {e}")
                    continue
            
            if not self.dialog:
                logger.warning("Could not load XDL dialog, falling back to message boxes")
                return self._fallback_to_message_boxes()
            
            # Initialize dialog controls
            self._initialize_dialog()
            
            # Show dialog
            result = self.dialog.execute()
            
            # Clean up
            self.dialog.dispose()
            
            return result == 1  # OK button
            
        except Exception as e:
            logger.error(f"Error showing settings dialog: {e}", exc_info=True)
            return self._fallback_to_message_boxes()
    
    def _initialize_dialog(self):
        """Initialize dialog controls with current settings."""
        try:
            # Update dependency status
            self._update_dependency_status()
            
            # Load current settings
            current_tesseract_path = uno_utils.get_setting(
                constants.CFG_KEY_TESSERACT_PATH, "", self.ctx
            )
            current_language = uno_utils.get_setting(
                constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx
            )
            
            # Set Tesseract path
            path_field = self.dialog.getControl("txtTesseractPath")
            if path_field:
                path_field.setText(current_tesseract_path)
            
            # Set default language
            lang_combo = self.dialog.getControl("cmbDefaultLanguage")
            if lang_combo:
                self._populate_language_combo(lang_combo, current_language)
            
            # Set up event listeners
            self._setup_event_listeners()
            
        except Exception as e:
            logger.error(f"Error initializing dialog: {e}", exc_info=True)
    
    def _update_dependency_status(self):
        """Update the dependency status indicators."""
        try:
            # Check dependencies
            from tejocr import tejocr_engine
            
            # Check Tesseract
            tesseract_ready, tesseract_msg = tejocr_engine.is_tesseract_ready(
                self.ctx, show_gui_errors=False
            )
            
            # Update Tesseract status
            tesseract_label = self.dialog.getControl("lblTesseractStatus")
            if tesseract_label:
                if tesseract_ready:
                    tesseract_label.setText("✅ Tesseract: Ready")
                else:
                    tesseract_label.setText("❌ Tesseract: Not found")
            
            # Check Python packages
            python_status = "✅ Python packages: Ready"
            try:
                import pytesseract
                import PIL
                import numpy
            except ImportError as e:
                python_status = f"❌ Python packages: Missing ({e.name})"
            
            python_label = self.dialog.getControl("lblPythonStatus")
            if python_label:
                python_label.setText(python_status)
                
        except Exception as e:
            logger.error(f"Error updating dependency status: {e}", exc_info=True)
    
    def _populate_language_combo(self, combo, current_language):
        """Populate language combo with available languages."""
        try:
            # Get available languages
            from tejocr import tejocr_engine
            available_langs = tejocr_engine.get_available_languages()
            
            # Clear existing items
            combo.removeItems(0, combo.getItemCount())
            
            # Add available languages
            selected_index = 0
            for i, lang in enumerate(available_langs):
                display_name = self._get_language_display_name(lang)
                combo.addItem(display_name, i)
                if lang == current_language:
                    selected_index = i
            
            # Set selected item
            combo.selectItemPos(selected_index, True)
            
        except Exception as e:
            logger.error(f"Error populating language combo: {e}", exc_info=True)
    
    def _get_language_display_name(self, lang_code):
        """Get display name for language code."""
        lang_names = {
            "eng": "eng - English",
            "hin": "hin - Hindi", 
            "fra": "fra - French",
            "deu": "deu - German",
            "spa": "spa - Spanish",
            "snum": "snum - Sanskrit"
        }
        return lang_names.get(lang_code, f"{lang_code} - {lang_code.upper()}")
    
    def _setup_event_listeners(self):
        """Set up event listeners for dialog controls."""
        try:
            # Browse button
            browse_btn = self.dialog.getControl("btnBrowsePath")
            if browse_btn:
                browse_btn.addActionListener(self)
            
            # Test button
            test_btn = self.dialog.getControl("btnTestPath")
            if test_btn:
                test_btn.addActionListener(self)
            
            # Auto-detect button
            auto_btn = self.dialog.getControl("btnAutoDetect")
            if auto_btn:
                auto_btn.addActionListener(self)
            
            # Install help button
            help_btn = self.dialog.getControl("btnInstallHelp")
            if help_btn:
                help_btn.addActionListener(self)
            
            # Save button
            save_btn = self.dialog.getControl("btnSave")
            if save_btn:
                save_btn.addActionListener(self)
            
            # Cancel button
            cancel_btn = self.dialog.getControl("btnCancel")
            if cancel_btn:
                cancel_btn.addActionListener(self)
                
        except Exception as e:
            logger.error(f"Error setting up event listeners: {e}", exc_info=True)
    
    def actionPerformed(self, event):
        """Handle button clicks."""
        try:
            control_name = event.Source.getModel().getName()
            
            if control_name == "btnBrowsePath":
                self._browse_tesseract_path()
            elif control_name == "btnTestPath":
                self._test_tesseract_path()
            elif control_name == "btnAutoDetect":
                self._auto_detect_tesseract()
            elif control_name == "btnInstallHelp":
                self._show_install_help()
            elif control_name == "btnSave":
                self._save_settings()
            elif control_name == "btnCancel":
                self.dialog.endExecute()
                
        except Exception as e:
            logger.error(f"Error handling action: {e}", exc_info=True)
    
    def _browse_tesseract_path(self):
        """Browse for Tesseract executable."""
        try:
            file_picker = uno_utils.create_instance("com.sun.star.ui.dialogs.FilePicker", self.ctx)
            if file_picker:
                file_picker.setTitle("Select Tesseract Executable")
                if file_picker.execute() == 1:
                    files = file_picker.getFiles()
                    if files:
                        path = unohelper.fileUrlToSystemPath(files[0])
                        path_field = self.dialog.getControl("txtTesseractPath")
                        if path_field:
                            path_field.setText(path)
        except Exception as e:
            logger.error(f"Error browsing for path: {e}", exc_info=True)
    
    def _test_tesseract_path(self):
        """Test the current Tesseract path."""
        try:
            path_field = self.dialog.getControl("txtTesseractPath")
            if path_field:
                path = path_field.getText()
                
                # Update status
                status_label = self.dialog.getControl("lblStatus")
                if status_label:
                    status_label.setText("Testing Tesseract...")
                
                # Test in background thread
                def test_thread():
                    try:
                        from tejocr import tejocr_engine
                        success, message = tejocr_engine.check_tesseract_path(
                            path, ctx=self.ctx, show_success=False, show_gui_errors=False
                        )
                        
                        # Update UI on main thread
                        if status_label:
                            if success:
                                status_label.setText("✅ Tesseract test successful")
                            else:
                                status_label.setText(f"❌ Test failed: {message}")
                    except Exception as e:
                        if status_label:
                            status_label.setText(f"❌ Test error: {e}")
                
                threading.Thread(target=test_thread, daemon=True).start()
                
        except Exception as e:
            logger.error(f"Error testing path: {e}", exc_info=True)
    
    def _auto_detect_tesseract(self):
        """Auto-detect Tesseract path."""
        try:
            status_label = self.dialog.getControl("lblStatus")
            if status_label:
                status_label.setText("Auto-detecting Tesseract...")
            
            # Auto-detect
            detected_path = uno_utils.find_tesseract_executable()
            
            path_field = self.dialog.getControl("txtTesseractPath")
            if path_field and detected_path:
                path_field.setText(detected_path)
                if status_label:
                    status_label.setText(f"✅ Found: {detected_path}")
            else:
                if status_label:
                    status_label.setText("❌ Tesseract not found automatically")
                    
        except Exception as e:
            logger.error(f"Error auto-detecting: {e}", exc_info=True)
    
    def _show_install_help(self):
        """Show installation help."""
        help_text = _(
            "TejOCR requires Tesseract OCR to be installed.\n\n"
            "Installation instructions:\n\n"
            "• macOS: brew install tesseract\n"
            "• Ubuntu: sudo apt install tesseract-ocr\n"
            "• Windows: Download from GitHub releases\n\n"
            "For language packs:\n"
            "• macOS: brew install tesseract-lang\n"
            "• Ubuntu: sudo apt install tesseract-ocr-[lang]\n\n"
            "Visit: https://tesseract-ocr.github.io/tessdoc/Installation.html"
        )
        
        uno_utils.show_message_box(
            "Installation Help", help_text, "infobox",
            parent_frame=self.parent_frame, ctx=self.ctx
        )
    
    def _save_settings(self):
        """Save current settings."""
        try:
            # Save Tesseract path
            path_field = self.dialog.getControl("txtTesseractPath")
            if path_field:
                path = path_field.getText().strip()
                uno_utils.set_setting(constants.CFG_KEY_TESSERACT_PATH, path, self.ctx)
            
            # Save default language
            lang_combo = self.dialog.getControl("cmbDefaultLanguage")
            if lang_combo:
                selected_text = lang_combo.getText()
                # Extract language code (e.g., "eng" from "eng - English")
                lang_code = selected_text.split(" - ")[0] if " - " in selected_text else selected_text
                uno_utils.set_setting(constants.CFG_KEY_DEFAULT_LANG, lang_code, self.ctx)
            
            self.settings_changed = True
            
            # Update status
            status_label = self.dialog.getControl("lblStatus")
            if status_label:
                status_label.setText("✅ Settings saved successfully")
            
            # Close dialog after short delay
            def close_dialog():
                time.sleep(1)
                self.dialog.endExecute()
            
            threading.Thread(target=close_dialog, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
    
    def _fallback_to_message_boxes(self):
        """Fallback to the original message box implementation."""
        logger.info("Using fallback message box settings dialog")
        
        # Import the original dialogs module
        from tejocr import tejocr_dialogs
        return tejocr_dialogs.show_settings_dialog(self.ctx, self.parent_frame)

class OCROptionsDialogHandler(unohelper.Base, XActionListener, XItemListener):
    """Handler for the OCR options dialog."""
    
    def __init__(self, ctx, parent_frame, source_type="selected", image_path=None):
        self.ctx = ctx
        self.parent_frame = parent_frame
        self.source_type = source_type
        self.image_path = image_path
        self.dialog = None
        self.dialog_provider = None
        self.selected_language = None
        self.selected_output_mode = None
        self.ocr_cancelled = False
        
    def show_dialog(self):
        """Show the OCR options dialog."""
        try:
            # For now, fallback to message boxes until XDL dialog is fully integrated
            return self._fallback_to_message_boxes()
            
            # TODO: Implement XDL dialog loading similar to SettingsDialogHandler
            # This will be completed in the next iteration
            
        except Exception as e:
            logger.error(f"Error showing OCR options dialog: {e}", exc_info=True)
            return self._fallback_to_message_boxes()
    
    def _fallback_to_message_boxes(self):
        """Fallback to the current working message box implementation."""
        logger.debug("Using fallback message box OCR options")
        
        # Get language choice
        default_lang = uno_utils.get_setting(
            constants.CFG_KEY_DEFAULT_LANG, constants.DEFAULT_OCR_LANGUAGE, self.ctx
        )
        
        # Ensure English is preferred if available
        if default_lang != "eng":
            try:
                from tejocr import tejocr_engine
                available_langs = tejocr_engine.get_available_languages()
                if "eng" in available_langs:
                    default_lang = "eng"
            except Exception:
                default_lang = "eng"
        
        language = uno_utils.show_input_box(
            title=_("OCR Language"),
            message=_("Enter OCR language for this operation (default: {default}):").format(default=default_lang),
            default_text=default_lang,
            ctx=self.ctx,
            parent_frame=self.parent_frame
        )
        
        if language is None:
            return None, None  # User cancelled
            
        if not language.strip():
            language = default_lang
        
        # Get output mode choice
        output_mode = self._get_output_mode_choice()
        if output_mode is None:
            return None, None  # User cancelled
        
        return language, output_mode
    
    def _get_output_mode_choice(self):
        """Get user's choice for output mode using chained query boxes."""
        try:
            # First choice: Primary options
            message1 = _(
                "Choose output method:\n\n"
                "YES = Insert at Cursor\n"
                "NO = Copy to Clipboard\n" 
                "CANCEL = More Options..."
            )
            
            result1 = uno_utils.show_message_box(
                title=_("OCR Output Mode"),
                message=message1,
                type="querybox",
                buttons="yes_no_cancel",
                parent_frame=self.parent_frame,
                ctx=self.ctx
            )
            
            if result1 == 2:  # YES button
                return constants.OUTPUT_MODE_CURSOR
            elif result1 == 3:  # NO button
                return constants.OUTPUT_MODE_CLIPBOARD
            elif result1 == 0:  # CANCEL - More Options
                # Second choice: Additional options
                message2 = _(
                    "More output options:\n\n"
                    "YES = New Text Box\n"
                    "NO = Insert at Cursor (default)\n"
                    "CANCEL = Cancel operation"
                )
                
                result2 = uno_utils.show_message_box(
                    title=_("More Output Options"),
                    message=message2,
                    type="querybox",
                    buttons="yes_no_cancel",
                    parent_frame=self.parent_frame,
                    ctx=self.ctx
                )
                
                if result2 == 2:  # YES button
                    return constants.OUTPUT_MODE_TEXTBOX
                elif result2 == 3:  # NO button
                    return constants.OUTPUT_MODE_CURSOR
                else:  # CANCEL
                    return None
            else:
                return constants.OUTPUT_MODE_CURSOR  # Default
                
        except Exception as e:
            logger.error(f"Error getting output mode choice: {e}")
            return constants.OUTPUT_MODE_CURSOR  # Default fallback

def show_enhanced_settings_dialog(ctx, parent_frame):
    """Show the enhanced settings dialog."""
    handler = SettingsDialogHandler(ctx, parent_frame)
    return handler.show_dialog()

def show_enhanced_ocr_options_dialog(ctx, parent_frame, source_type="selected", image_path=None):
    """Show the enhanced OCR options dialog."""
    handler = OCROptionsDialogHandler(ctx, parent_frame, source_type, image_path)
    return handler.show_dialog() 