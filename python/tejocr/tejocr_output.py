# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Handles the output of recognized OCR text into LibreOffice Writer."""

import uno
import unohelper
import time

# Safe import of UNO interfaces with fallbacks
print("DEBUG: tejocr_output.py: Attempting UNO interface imports...")
try:
    from com.sun.star.text import XTextDocument, XText, XTextRange, XTextContent
    print("DEBUG: tejocr_output.py: Successfully imported text interfaces")
except ImportError as e:
    print(f"DEBUG: tejocr_output.py: Warning - Could not import text interfaces: {e}")
    # Define dummy classes to prevent module loading failure
    class XTextDocument: pass
    class XText: pass
    class XTextRange: pass
    class XTextContent: pass

try:
    from com.sun.star.container import XNamed
    print("DEBUG: tejocr_output.py: Successfully imported XNamed")
except ImportError as e:
    print(f"DEBUG: tejocr_output.py: Warning - Could not import XNamed: {e}")
    class XNamed: pass

try:
    from com.sun.star.datatransfer import XTransferable, DataFlavor
    print("DEBUG: tejocr_output.py: Successfully imported datatransfer interfaces")
except ImportError as e:
    print(f"DEBUG: tejocr_output.py: Warning - Could not import datatransfer interfaces: {e}")
    class XTransferable: pass
    class DataFlavor: pass

try:
    from com.sun.star.datatransfer.clipboard import XClipboard
    print("DEBUG: tejocr_output.py: Successfully imported XClipboard")
except ImportError as e:
    print(f"DEBUG: tejocr_output.py: Warning - Could not import XClipboard: {e}")
    class XClipboard: pass

from tejocr import uno_utils
from tejocr import constants
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext
logger = uno_utils.get_logger("TejOCR.Output")

class TextTransferable(unohelper.Base, XTransferable):
    """A simple transferable for plain text for clipboard operations."""
    def __init__(self, text_content):
        self.text_content = text_content
        # Plain text DataFlavor
        self.flavor = DataFlavor()
        self.flavor.MimeType = "text/plain;charset=utf-16"
        self.flavor.HumanPresentableName = "Plain Text"
        # UNO passes strings as UTF-16. Python strings are sequences of Unicode code points.
        # The actual encoding to bytes for transfer will be handled by UNO if necessary,
        # or we need to ensure the data provided to setContents is in a format UNO expects for the MimeType.
        # For text/plain;charset=utf-16, a Python string should be fine.

    def getTransferData(self, flavor):
        if flavor.MimeType == self.flavor.MimeType:
            return self.text_content
        return None

    def getTransferDataFlavors(self):
        return (self.flavor,)

    def isDataFlavorSupported(self, flavor):
        return flavor.MimeType == self.flavor.MimeType

def _insert_text_at_cursor(ctx, frame, text_to_insert):
    logger.info("Output mode: Insert at cursor")
    try:
        model = frame.getController().getModel()
        if not model.supportsService("com.sun.star.text.TextDocument"):
            uno_utils.show_message_box(_("Error"), _("Cannot insert text: Active document is not a text document."), "errorbox", parent_frame=frame, ctx=ctx)
            return

        controller = frame.getController()
        text_doc = model.getText()
        
        # Strategy 1: Try to use view cursor normally
        try:
            view_cursor = controller.getViewCursor()
            if view_cursor:
                text_range = view_cursor.getStart() # Get XTextRange at cursor start
                text_range.setString(text_to_insert)
                view_cursor.collapseToEnd()
                logger.info(f"Strategy 1 SUCCESS: Inserted {len(text_to_insert)} characters at view cursor.")
                return
        except Exception as cursor_error:
            logger.debug(f"Strategy 1 FAILED (view cursor): {cursor_error}")
        
        # Strategy 2: Try to get text cursor and insert at current position
        try:
            text_cursor = text_doc.createTextCursor()
            if text_cursor:
                # Move cursor to end of document as fallback position
                text_cursor.gotoEnd(False)
                text_cursor.setString("\n" + text_to_insert)
                logger.info(f"Strategy 2 SUCCESS: Inserted {len(text_to_insert)} characters using text cursor at document end.")
                return
        except Exception as text_cursor_error:
            logger.debug(f"Strategy 2 FAILED (text cursor): {text_cursor_error}")
        
        # Strategy 3: Direct insertion at end of main text body
        try:
            if text_doc:
                # Get end position and insert there
                end_cursor = text_doc.createTextCursor()
                end_cursor.gotoEnd(False)
                text_doc.insertString(end_cursor, "\n" + text_to_insert, False)
                logger.info(f"Strategy 3 SUCCESS: Inserted {len(text_to_insert)} characters at document end via insertString.")
                return
        except Exception as insert_error:
            logger.debug(f"Strategy 3 FAILED (direct insert): {insert_error}")
        
        # Strategy 4: Try to focus the document and retry view cursor
        try:
            # Try to bring the document window to focus
            window = frame.getContainerWindow()
            if window:
                window.setFocus()
            
            # Small delay to allow focus to settle (not ideal but may help)
            time.sleep(0.1)
            
            view_cursor = controller.getViewCursor()
            if view_cursor:
                # Try to position cursor at end of document first
                view_cursor.gotoEnd(False)
                view_cursor.setString("\n" + text_to_insert)
                logger.info(f"Strategy 4 SUCCESS: Inserted {len(text_to_insert)} characters after focusing window.")
                return
        except Exception as focus_error:
            logger.debug(f"Strategy 4 FAILED (focus retry): {focus_error}")
        
        # If all strategies fail, show error
        raise RuntimeError("All text insertion strategies failed")

    except Exception as e:
        logger.error(f"Error inserting text at cursor: {e}", exc_info=True)
        # Provide helpful error message with troubleshooting
        error_msg = f"Could not insert text at cursor.\n\nTroubleshooting:\n• Click in the document to set cursor position\n• Ensure document has focus\n• Try copying text to clipboard instead\n\nTechnical error: {str(e)[:100]}"
        uno_utils.show_message_box(_("Insert Text Error"), error_msg, "errorbox", parent_frame=frame, ctx=ctx)

def _insert_text_into_new_textbox(ctx, frame, text_to_insert):
    logger.info("Output mode: Insert into new text box")
    try:
        controller = frame.getController()
        model = controller.getModel()
        
        if not model.supportsService("com.sun.star.text.TextDocument"):
            uno_utils.show_message_box(_("Error"), _("Cannot insert text box: Active document is not a text document."), "errorbox", parent_frame=frame, ctx=ctx)
            return

        # Create text frame using the document's service factory
        text_frame = model.createInstance("com.sun.star.text.TextFrame")
        if not text_frame:
            logger.error("Failed to create TextFrame instance.")
            uno_utils.show_message_box(_("Error"), _("Could not create text frame object."), "errorbox", parent_frame=frame, ctx=ctx)
            return

        # Set text frame properties
        try:
            # Set size (in 1/100mm units)
            text_frame.setPropertyValue("Width", 8000)   # 80mm width
            text_frame.setPropertyValue("Height", 3000)  # 30mm height
            
            # Set anchor type to "as character" so it flows with text
            try:
                anchor_type = uno.getConstantByName("com.sun.star.text.TextContentAnchorType.AS_CHARACTER")
                text_frame.setPropertyValue("AnchorType", anchor_type)
            except Exception:
                # Fallback to numeric value if constant not found
                text_frame.setPropertyValue("AnchorType", 1)  # AS_CHARACTER = 1
            
            # Set some visual properties
            text_frame.setPropertyValue("BorderDistance", 100)  # 1mm border distance
            text_frame.setPropertyValue("LeftBorderDistance", 100)
            text_frame.setPropertyValue("RightBorderDistance", 100)
            text_frame.setPropertyValue("TopBorderDistance", 100)
            text_frame.setPropertyValue("BottomBorderDistance", 100)
            
        except Exception as prop_error:
            logger.warning(f"Could not set all text frame properties: {prop_error}")
            # Continue anyway with default properties

        # Get document text and create proper cursor
        text_doc = model.getText()
        
        # Try to get view cursor first, then fallback to text cursor
        try:
            view_cursor = controller.getViewCursor()
            if view_cursor:
                # Ensure cursor is in the same document
                cursor_text = view_cursor.getText()
                if cursor_text == text_doc:
                    insertion_cursor = view_cursor
                else:
                    # Create new cursor at end of document
                    insertion_cursor = text_doc.createTextCursor()
                    insertion_cursor.gotoEnd(False)
            else:
                # Create new cursor at end of document
                insertion_cursor = text_doc.createTextCursor()
                insertion_cursor.gotoEnd(False)
        except Exception:
            # Fallback to document text cursor
            insertion_cursor = text_doc.createTextCursor()
            insertion_cursor.gotoEnd(False)

        # Insert the text frame into the document
        text_doc.insertTextContent(insertion_cursor, text_frame, False)

        # Add text to the text frame
        frame_text = text_frame.getText()
        frame_text.setString(text_to_insert)

        logger.info(f"Successfully inserted new text box with {len(text_to_insert)} characters.")
        
        # Show success message
        uno_utils.show_message_box(
            _("Text Box Created"), 
            _("Text has been inserted into a new text box."), 
            "infobox", 
            parent_frame=frame, 
            ctx=ctx
        )

    except Exception as e:
        logger.error(f"Error inserting text into new text box: {e}", exc_info=True)
        # Fallback to cursor insertion if text box fails
        logger.info("Text box creation failed, falling back to cursor insertion")
        try:
            _insert_text_at_cursor(ctx, frame, f"[Text Box Failed] {text_to_insert}")
            uno_utils.show_message_box(
                _("Text Box Error"), 
                _("Could not create text box, text inserted at cursor instead.\n\nError: {error}").format(error=str(e)[:100]), 
                "warningbox", 
                parent_frame=frame, 
                ctx=ctx
            )
        except Exception as fallback_error:
            logger.error(f"Even fallback insertion failed: {fallback_error}")
            uno_utils.show_message_box(
                _("Text Box Error"), 
                _("Could not insert text into new text box: {error}").format(error=e), 
                "errorbox", 
                parent_frame=frame, 
                ctx=ctx
            )

def _replace_image_with_text(ctx, frame, text_to_insert):
    logger.info("Output mode: Replace image with text")
    # This is complex: needs to identify the selected graphic object precisely and remove it.
    # Then insert text at its position, possibly within a new text frame or directly.
    try:
        controller = frame.getController()
        selection = controller.getSelection()

        if not selection or not selection.supportsService("com.sun.star.text.XTextContent") and not selection.supportsService("com.sun.star.drawing.XShape"):
            uno_utils.show_message_box(_("Error"), _("No suitable object selected to replace. Select an image or shape."), "warningbox", parent_frame=frame, ctx=ctx)
            return

        text_doc_model = controller.getModel()
        text_doc = text_doc_model.getText()
        
        # Attempt to remove the selected object
        # For XTextContent (like embedded images in Writer)
        if selection.supportsService("com.sun.star.text.XTextContent"):
            anchor = selection.getAnchor()
            text_doc.removeTextContent(selection)
            logger.info("Removed selected XTextContent (image). Attempting to insert text at anchor.")
            # Insert text at the anchor point (might need to be smarter about positioning)
            if anchor and hasattr(anchor, "setString"):
                 anchor.setString(text_to_insert)
            elif anchor: # If anchor is just a range/cursor
                view_cursor = controller.getViewCursor()
                view_cursor.gotoRange(anchor, False)
                view_cursor.setString(text_to_insert)
                view_cursor.collapseToEnd()
            else: # Fallback if anchor is weird, insert at current view cursor
                _insert_text_at_cursor(ctx, frame, text_to_insert)
                logger.warning("Could not determine precise anchor for replacement, inserted at view cursor.")

        # For XShape (more common in Draw/Impress, but can be in Writer)
        # This path might be less common for the typical "selected image" in Writer
        elif selection.supportsService("com.sun.star.drawing.XShape"):
            # Removing XShape usually involves getting its parent (DrawPage) and calling remove.
            # This is more complex and context-dependent (Writer vs Draw).
            # For Writer, shapes are often anchored. If it's a graphic shape from Draw tools.
            uno_utils.show_message_box(_("Not Implemented"), _("Replacing general drawing shapes is not fully implemented yet. Try with directly embedded images."), "infobox", parent_frame=frame, ctx=ctx)
            logger.warning("Replacement of XShape type objects is not fully implemented.")
            _insert_text_at_cursor(ctx, frame, "[Shape replacement not fully implemented] " + text_to_insert) # Fallback
            return
        else:
            uno_utils.show_message_box(_("Error"), _("Selected object cannot be directly replaced this way."), "warningbox", parent_frame=frame, ctx=ctx)
            return
        
        logger.info(f"Replaced selected image with {len(text_to_insert)} characters.")

    except Exception as e:
        logger.error(f"Error replacing image with text: {e}", exc_info=True)
        uno_utils.show_message_box(_("Replace Image Error"), _("Could not replace image with text: {error}").format(error=e), "errorbox", parent_frame=frame, ctx=ctx)

def _copy_text_to_clipboard(ctx, frame, text_to_insert):
    logger.info("Output mode: Copy to clipboard")
    try:
        # Get the system clipboard service
        clipboard = uno_utils.create_instance("com.sun.star.datatransfer.clipboard.SystemClipboard", ctx)
        if not clipboard:
            uno_utils.show_message_box(_("Error"), _("Could not access system clipboard service."), "errorbox", parent_frame=frame, ctx=ctx)
            return
        
        transferable = TextTransferable(text_to_insert)
        clipboard.setContents(transferable, None) # Second arg is XClipboardOwner, None is fine for simple set
        logger.info(f"Copied {len(text_to_insert)} characters to clipboard.")
        uno_utils.show_message_box(_("Copied to Clipboard"), _("Recognized text has been copied to the clipboard."), "infobox", parent_frame=frame, ctx=ctx)

    except Exception as e:
        logger.error(f"Error copying text to clipboard: {e}", exc_info=True)
        uno_utils.show_message_box(_("Clipboard Error"), _("Could not copy text to clipboard: {error}").format(error=e), "errorbox", parent_frame=frame, ctx=ctx)

def insert_text_at_cursor(ctx, frame, text_to_insert):
    """Simple function to insert text at the current cursor position."""
    return _insert_text_at_cursor(ctx, frame, text_to_insert)

def copy_text_to_clipboard(ctx, frame, text_to_insert):
    """Public function to copy text to clipboard."""
    return _copy_text_to_clipboard(ctx, frame, text_to_insert)

def create_text_box_with_text(ctx, frame, text_to_insert):
    """Public function to create a text box with text."""
    return _insert_text_into_new_textbox(ctx, frame, text_to_insert)

def handle_ocr_output(ctx, frame, recognized_text, output_mode):
    """Main dispatcher for handling OCR output based on the selected mode."""
    logger.info(f"Handling OCR output. Mode: {output_mode}, Text length: {len(recognized_text if recognized_text else '')}")
    if recognized_text is None: # Should not happen if dialog returned success, but check
        logger.warning("handle_ocr_output called with None text.")
        # uno_utils.show_message_box(_("OCR Result"), _("No text was recognized."), "infobox", parent_frame=frame, ctx=ctx)
        return

    if output_mode == constants.OUTPUT_MODE_CURSOR:
        _insert_text_at_cursor(ctx, frame, recognized_text)
    elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
        _insert_text_into_new_textbox(ctx, frame, recognized_text)
    elif output_mode == constants.OUTPUT_MODE_REPLACE:
        _replace_image_with_text(ctx, frame, recognized_text)
    elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
        _copy_text_to_clipboard(ctx, frame, recognized_text)
    else:
        logger.warning(f"Unknown OCR output mode: {output_mode}")
        uno_utils.show_message_box(_("Error"), _("Unknown output mode specified: {mode}").format(mode=output_mode), "errorbox", parent_frame=frame, ctx=ctx)

if __name__ == "__main__":
    # Basic mock for testing (very limited without real UNO context)
    class MockFrame: 
        def getController(self): return self
        def getModel(self): return self
        def supportsService(self, s): return s == "com.sun.star.text.TextDocument"
        def getText(self): return self
        def getViewCursor(self): return self
        def getStart(self): return self # Mocking XTextRange
        def setString(self, s): print(f"MockInsertAtCursor: {s[:50]}...")
        def collapseToEnd(self): pass
        def createInstance(self, s): 
            if s == "com.sun.star.text.TextFrame": return MockTextFrame()
            return None
        def insertTextContent(self, c, tf, b): print(f"MockInsertTextBox: Content inserted.")
        def getSelection(self): return None # Needs more for replace

    class MockTextFrame:
        def getText(self): return self
        def setString(self, s): print(f"MockTextBox: {s[:50]}...")
        def getSize(self): return MockSize()
        def setSize(self, s): pass

    class MockSize: Width=0; Height=0

    class MockCtx: pass

    mock_ctx = MockCtx()
    mock_frame = MockFrame()
    test_text = "This is a long test string from OCR result, meant to test different output mechanisms."
    
    print("--- Testing Insert at Cursor ---")
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_CURSOR)
    print("--- Testing Insert into New Textbox ---")
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_TEXTBOX)
    # Clipboard and Replace are harder to mock simply here.
    print("--- Testing Copy to Clipboard (will likely fail without UNO services) ---")
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_CLIPBOARD) 