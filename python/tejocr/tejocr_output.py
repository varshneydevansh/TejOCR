# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Handles outputting the recognized OCR text to the document or clipboard."""

import uno
import unohelper
from com.sun.star.datatransfer import XTransferable
from com.sun.star.datatransfer.clipboard import XClipboard

from . import uno_utils
from . import constants

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Output")

def insert_text_at_cursor(ctx, frame, text_to_insert):
    """Inserts the given text at the current cursor position in the document."""
    logger.info(f"Attempting to insert text at cursor (length: {len(text_to_insert)}).")
    if not frame:
        # uno_utils.show_message_box("Output Error", "No active document frame to insert text.", "errorbox", ctx=ctx)
        logger.error("Cannot insert text at cursor: No active document frame.")
        return False
    
    controller = frame.getController()
    if not controller.supportsService("com.sun.star.text.TextDocumentView"):
        # uno_utils.show_message_box("Output Error", "Cannot insert text into non-text document view.", "errorbox", parent_frame=frame, ctx=ctx)
        logger.error("Cannot insert text at cursor: Not a TextDocumentView.")
        return False

    try:
        view_cursor = controller.getViewCursor()
        text_cursor = view_cursor.getText().createTextCursorByRange(view_cursor.getStart())
        text_cursor.setString(str(text_to_insert))
        logger.info("Successfully inserted text at cursor.")
        return True
    except Exception as e:
        logger.error(f"Error inserting text at cursor: {e}", exc_info=True)
        uno_utils.show_message_box("Output Error", f"Failed to insert text at cursor: {e}", "errorbox", parent_frame=frame, ctx=ctx)
        return False


def insert_text_into_new_textbox(ctx, frame, text_to_insert):
    """Creates a new text box (TextFrame) and inserts the text into it."""
    logger.info(f"Attempting to insert text into new textbox (length: {len(text_to_insert)}).")
    if not frame:
        # uno_utils.show_message_box("Output Error", "No active document frame to insert textbox.", "errorbox", ctx=ctx)
        logger.error("Cannot insert textbox: No active document frame.")
        return False

    doc = frame.getController().getModel()
    if not doc.supportsService("com.sun.star.text.TextDocument"):
        # uno_utils.show_message_box("Output Error", "Cannot insert textbox into non-text document.", "errorbox", parent_frame=frame, ctx=ctx)
        logger.error("Cannot insert textbox: Not a TextDocument.")
        return False
    
    try:
        # Create a TextFrame
        text_frame = doc.createInstance("com.sun.star.text.TextFrame")
        
        # Set basic properties (size, position - these are examples, can be more sophisticated)
        # Size in 1/100th mm
        text_frame.setSize(uno.createUnoStruct("com.sun.star.awt.Size", 10000, 5000)) # 10cm x 5cm
        
        # Anchor type - e.g., AT_PARAGRAPH, AT_PAGE, AS_CHARACTER
        # Default anchor is usually to paragraph.
        # text_frame.setPropertyValue("AnchorType", com.sun.star.text.TextContentAnchorType.AT_PAGE)

        # Insert the text frame into the document
        text_range = doc.getText().getEnd() # Insert at the end of the document for now
        doc.getText().insertTextContent(text_range, text_frame, False)
        
        # Insert the text into the TextFrame
        text_frame.getText().setString(str(text_to_insert))
        logger.info("Successfully inserted text into new textbox.")
        return True
    except Exception as e:
        logger.error(f"Error inserting text into new textbox: {e}", exc_info=True)
        uno_utils.show_message_box("Output Error", f"Failed to insert text into new textbox: {e}", "errorbox", parent_frame=frame, ctx=ctx)
        return False

def replace_image_with_text(ctx, frame, text_to_insert):
    """Replaces the currently selected image with the given text."""
    logger.info(f"Attempting to replace image with text (length: {len(text_to_insert)}).")
    if not frame:
        # uno_utils.show_message_box("Output Error", "No active document frame.", "errorbox", ctx=ctx)
        logger.error("Cannot replace image: No active document frame.")
        return False

    controller = frame.getController()
    selection = controller.getSelection()

    # Check if a suitable graphic object is selected
    # It should ideally be the same object that was OCR'd
    # This check is basic; more robust checks might be needed depending on how images are embedded.
    is_suitable_graphic = False
    if selection:
        if selection.supportsService("com.sun.star.text.TextGraphicObject"):
            is_suitable_graphic = True
        elif selection.supportsService("com.sun.star.drawing.Shape") and \
             (hasattr(selection, "Graphic") or hasattr(selection, "GraphicURL")):
            is_suitable_graphic = True # Assuming a single selected shape that is an image
        # Add more specific checks if needed, e.g. for shapes within groups if that's a target

    if not is_suitable_graphic:
         logger.warning("No suitable image selected to replace.")
         uno_utils.show_message_box("Output Error", "No suitable image selected to replace. Please select an image.", "warningbox", parent_frame=frame, ctx=ctx)
         return False
    
    # This is a destructive action. A confirmation dialog might be good for future versions.
    logger.warning("Replace image action is destructive. User confirmation might be useful in future.")
    
    try:
        text_model = controller.getModel().getText()
        anchor = selection.getAnchor()
        
        # Insert text at the anchor point of the selected graphic
        text_model.insertString(anchor, str(text_to_insert), False)
        logger.info(f"Inserted text at image anchor prior to removal.")
        
        # Remove the graphic object itself
        if hasattr(selection, "dispose") and callable(selection.dispose):
            selection.dispose()
            logger.info("Successfully disposed selected graphic object after text insertion.")
            return True
        else:
            # This fallback is less ideal. If dispose() isn't available, removing might be complex.
            logger.warning("Selected object does not have a dispose method. Cannot reliably remove image.")
            uno_utils.show_message_box("Warning", "Could not reliably remove the original image after inserting text. The object may need to be manually deleted.", "warningbox", parent_frame=frame, ctx=ctx)
            return False # Or True if text insertion is considered partial success

    except Exception as e:
        logger.error(f"Error replacing image with text: {e}", exc_info=True)
        # import traceback # Handled by exc_info=True
        # traceback.print_exc()
        uno_utils.show_message_box("Output Error", f"Failed to replace image with text: {e}", "errorbox", parent_frame=frame, ctx=ctx)
        return False


class TextTransferable(unohelper.Base, XTransferable):
    """A simple XTransferable implementation for plain text."""
    def __init__(self, text):
        self.text = text
        # DataFlavor for plain text UTF-8
        logger.debug(f"TextTransferable created for text length: {len(text)}")
        self.flavor = uno.createUnoStruct("com.sun.star.datatransfer.DataFlavor")
        self.flavor.MimeType = "text/plain;charset=utf-8"
        self.flavor.HumanPresentableName = "Plain Text"

    def getTransferData(self, flavor):
        if flavor.MimeType == self.flavor.MimeType:
            logger.debug("getTransferData called for supported flavor (text/plain).")
            return self.text.encode('utf-8') # Return as bytes
        logger.warning(f"getTransferData called for unsupported flavor: {flavor.MimeType}")
        return None

    def getTransferDataFlavors(self):
        logger.debug("getTransferDataFlavors called.")
        return (self.flavor,)

    def isDataFlavorSupported(self, flavor):
        supported = flavor.MimeType == self.flavor.MimeType
        logger.debug(f"isDataFlavorSupported called for {flavor.MimeType}. Supported: {supported}")
        return supported


def copy_text_to_clipboard(ctx, frame, text_to_copy):
    """Copies the given text to the system clipboard."""
    logger.info(f"Attempting to copy text to clipboard (length: {len(text_to_copy)}).")
    try:
        # Get the system clipboard service
        clipboard_service = "com.sun.star.datatransfer.clipboard.SystemClipboard"
        clipboard = uno_utils.create_instance(clipboard_service, ctx)
        
        if not clipboard:
            # uno_utils.show_message_box("Clipboard Error", "Could not access system clipboard.", "errorbox", parent_frame=frame, ctx=ctx)
            logger.error("Could not access system clipboard service.")
            return False

        transferable = TextTransferable(str(text_to_copy))
        clipboard.setContents(transferable, None) # Second arg is XClipboardOwner, None is fine
        logger.info("Successfully copied text to clipboard.")
        return True
    except Exception as e:
        logger.error(f"Error copying to clipboard: {e}", exc_info=True)
        # import traceback # Handled by exc_info
        # traceback.print_exc()
        uno_utils.show_message_box("Clipboard Error", f"Failed to copy text to clipboard: {e}", "errorbox", parent_frame=frame, ctx=ctx)
        return False

# Main dispatcher function
def handle_ocr_output(ctx, frame, text_to_output, output_mode):
    """
    Dispatches the OCR text to the appropriate output handler.
    Returns True on success, False on failure.
    """
    if text_to_output is None: # Allow empty string, but not None
        text_to_output = ""
        logger.warning("handle_ocr_output received None for text_to_output, defaulting to empty string.")

    success = False
    logger.info(f"Handling OCR output. Mode: {output_mode}. Text length: {len(text_to_output)}.")
    if output_mode == constants.OUTPUT_MODE_CURSOR:
        success = insert_text_at_cursor(ctx, frame, text_to_output)
    elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
        success = insert_text_into_new_textbox(ctx, frame, text_to_output)
    elif output_mode == constants.OUTPUT_MODE_REPLACE:
        # This mode needs the selection to be the image that was OCR'd.
        # The service layer will need to ensure this context is still valid.
        success = replace_image_with_text(ctx, frame, text_to_output)
    elif output_mode == constants.OUTPUT_MODE_CLIPBOARD:
        success = copy_text_to_clipboard(ctx, frame, text_to_output)
    else:
        uno_utils.show_message_box("Output Error", f"Unknown output mode: {output_mode}", "errorbox", parent_frame=frame, ctx=ctx)
        return False

    if success:
        if output_mode != constants.OUTPUT_MODE_CLIPBOARD: # No success message for clipboard usually
             uno_utils.show_message_box("TejOCR", "Text processed successfully.", "infobox", parent_frame=frame, ctx=ctx)
    # else:
        # Error messages are shown by individual functions

    return success

if __name__ == "__main__":
    print("tejocr_output.py: This module is intended to be used by TejOCR service.")
    # Basic test for clipboard (outside LO, might use a different clipboard context if available)
    # class MockCtx: pass
    # class MockFrame: pass
    # mock_ctx = MockCtx()
    # mock_frame = MockFrame()
    # if copy_text_to_clipboard(mock_ctx, mock_frame, "Hello from TejOCR test!"):
    #     print("Text supposedly copied. Try pasting somewhere.")
    # else:
    #     print("Clipboard copy failed.") 