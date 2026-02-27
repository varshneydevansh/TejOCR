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
try:
    from com.sun.star.text import XTextDocument, XText, XTextRange, XTextContent
except ImportError as e:
    # Define dummy classes to prevent module loading failure
    class XTextDocument: pass
    class XText: pass
    class XTextRange: pass
    class XTextContent: pass

try:
    from com.sun.star.container import XNamed
except ImportError as e:
    class XNamed: pass

try:
    from com.sun.star.datatransfer import XTransferable, DataFlavor
except ImportError as e:
    class XTransferable: pass
    class DataFlavor: pass

try:
    from com.sun.star.datatransfer.clipboard import XClipboard
except ImportError as e:
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


def _resolve_insertion_cursor(text_doc, insertion_anchor):
    """Resolve a best-effort insertion cursor from a selected object anchor."""
    if not text_doc or not insertion_anchor:
        return None

    def _resolve_anchor(candidate):
        """Best-effort unwrap of wrappers/shape/text content to a concrete anchor range."""
        if candidate is None:
            return None

        # Check common anchor accessors first.
        try:
            if hasattr(candidate, "getAnchor"):
                anchor_candidate = candidate.getAnchor()
                if anchor_candidate is not None:
                    return anchor_candidate
        except Exception:
            pass

        try:
            if hasattr(candidate, "Anchor"):
                anchor_candidate = candidate.Anchor
                if anchor_candidate is not None:
                    return anchor_candidate
        except Exception:
            pass

        return candidate

    anchor_text = None
    target_doc = text_doc
    try:
        insertion_anchor = _resolve_anchor(insertion_anchor)
        if insertion_anchor is None:
            return None

        if hasattr(insertion_anchor, "getText"):
            anchor_text = insertion_anchor.getText()
            # Avoid strict identity checks for equality here, because Writer text object wrappers
            # can differ even when representing the same document in some UNO runtimes.
            if anchor_text is not None and text_doc is not None and anchor_text != text_doc:
                logger.debug(
                    "Resolved insertion anchor belongs to a different text object; switching insertion target context."
                )
                target_doc = anchor_text
    except Exception:
        # Continue with best-effort behavior if the anchor cannot be inspected safely.
        pass

    if hasattr(insertion_anchor, "setString"):
        try:
            return insertion_anchor
        except Exception:
            pass

    # Some anchors expose start/end ranges instead of direct setString.
    try:
        if hasattr(insertion_anchor, "getStart"):
            start_anchor = insertion_anchor.getStart()
            if start_anchor is not insertion_anchor:
                return _resolve_insertion_cursor(target_doc, start_anchor)
    except Exception as start_error:
        logger.debug(f"Could not read anchor start: {start_error}")

    try:
        if hasattr(insertion_anchor, "getEnd"):
            end_anchor = insertion_anchor.getEnd()
            if end_anchor is not insertion_anchor:
                return _resolve_insertion_cursor(target_doc, end_anchor)
    except Exception as end_error:
        logger.debug(f"Could not read anchor end: {end_error}")

    try:
        if target_doc is not None and hasattr(target_doc, "createTextCursorByRange"):
            return target_doc.createTextCursorByRange(insertion_anchor)
    except Exception as cursor_error:
        logger.debug(f"Could not create cursor from anchor range: {cursor_error}")

    # Last-resort explicit cursor creation from a generic range-like object.
    try:
        if target_doc is not None and hasattr(target_doc, "createTextCursor"):
            cursor = target_doc.createTextCursor()
            if hasattr(cursor, "gotoRange"):
                cursor.gotoRange(insertion_anchor, False)
                return cursor
    except Exception as fallback_error:
        logger.debug(f"Could not map insertion anchor using gotoRange fallback: {fallback_error}")

    # Some anchors may expose setString directly; return the anchor for direct write attempts.
    if hasattr(insertion_anchor, "setString"):
        return insertion_anchor

    return None


def _insert_text_at_cursor(ctx, frame, text_to_insert, insertion_anchor=None):
    logger.info("Output mode: Insert at cursor")
    try:
        model = frame.getController().getModel()
        if not model.supportsService("com.sun.star.text.TextDocument"):
            uno_utils.show_message_box(_("Error"), _("Cannot insert text: Active document is not a text document."), "errorbox", parent_frame=frame, ctx=ctx)
            return

        controller = frame.getController()
        text_doc = model.getText()
        insertion_cursor = _resolve_insertion_cursor(text_doc, insertion_anchor)

        # Strategy 0: Use a captured insertion anchor when available.
        if insertion_cursor is not None:
            try:
                if hasattr(insertion_cursor, "setString"):
                    insertion_cursor.setString(text_to_insert)
                    if hasattr(insertion_cursor, "collapseToEnd"):
                        insertion_cursor.collapseToEnd()
                    logger.info(
                        "Strategy 0 SUCCESS: Inserted {length} characters at captured insertion anchor.".format(
                            length=len(text_to_insert)
                        )
                    )
                    return
            except Exception as anchor_error:
                logger.debug(
                    f"Strategy 0 FAILED (captured anchor): {anchor_error}"
                )

        # Strategy 1 (Anchor-aware): Use a text cursor positioned at the captured anchor range.
        try:
            if insertion_anchor is not None:
                view_cursor = controller.getViewCursor()
                if view_cursor is not None and hasattr(view_cursor, "gotoRange"):
                    view_cursor.gotoRange(insertion_cursor or insertion_anchor, False)
                    view_cursor.setString(text_to_insert)
                    if hasattr(view_cursor, "collapseToEnd"):
                        view_cursor.collapseToEnd()
                    logger.info(
                        "Strategy 1 SUCCESS: Inserted {length} characters using anchor-aware view cursor.".format(
                            length=len(text_to_insert)
                        )
                    )
                    return
        except Exception as anchor_cursor_error:
            logger.debug(
                f"Strategy 1 FAILED (anchor-aware view cursor): {anchor_cursor_error}"
            )
        
        # Strategy 2: Try to use view cursor normally
        try:
            view_cursor = controller.getViewCursor()
            if view_cursor:
                text_range = view_cursor.getStart() # Get XTextRange at cursor start
                text_range.setString(text_to_insert)
                view_cursor.collapseToEnd()
                logger.info(f"Strategy 2 SUCCESS: Inserted {len(text_to_insert)} characters at view cursor.")
                return
        except Exception as cursor_error:
            logger.debug(f"Strategy 2 FAILED (view cursor): {cursor_error}")
        
        # Strategy 3: Try to get text cursor and insert at current position
        try:
            text_cursor = text_doc.createTextCursor()
            if text_cursor:
                # Move cursor to end of document as fallback position
                text_cursor.gotoEnd(False)
                text_cursor.setString("\n" + text_to_insert)
                logger.info(f"Strategy 3 SUCCESS: Inserted {len(text_to_insert)} characters using text cursor at document end.")
                return
        except Exception as text_cursor_error:
            logger.debug(f"Strategy 3 FAILED (text cursor): {text_cursor_error}")
        
        # Strategy 4: Direct insertion at end of main text body
        try:
            if text_doc:
                # Get end position and insert there
                end_cursor = text_doc.createTextCursor()
                end_cursor.gotoEnd(False)
                text_doc.insertString(end_cursor, "\n" + text_to_insert, False)
                logger.info(
                    f"Strategy 4 SUCCESS: Inserted {len(text_to_insert)} characters at document end via insertString."
                )
                return
        except Exception as insert_error:
            logger.debug(f"Strategy 4 FAILED (direct insert): {insert_error}")
        
        # Strategy 5: Try to focus the document and retry view cursor
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
                logger.info(f"Strategy 5 SUCCESS: Inserted {len(text_to_insert)} characters after focusing window.")
                return
        except Exception as focus_error:
            logger.debug(f"Strategy 5 FAILED (focus retry): {focus_error}")
        
        # If all strategies fail, show error
        raise RuntimeError("All text insertion strategies failed")

    except Exception as e:
        logger.error(f"Error inserting text at cursor: {e}", exc_info=True)
        # Provide helpful error message with troubleshooting
        error_msg = f"Could not insert text at cursor.\n\nTroubleshooting:\n• Click in the document to set cursor position\n• Ensure document has focus\n• Try copying text to clipboard instead\n\nTechnical error: {str(e)[:100]}"
        uno_utils.show_message_box(_("Insert Text Error"), error_msg, "errorbox", parent_frame=frame, ctx=ctx)

def _insert_text_into_new_textbox(ctx, frame, text_to_insert, insertion_anchor=None):
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
        
        # Try to use captured insertion anchor first, then fallback to view cursor.
        insertion_cursor = _resolve_insertion_cursor(text_doc, insertion_anchor)

        try:
            if insertion_cursor is None:
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

def _replace_image_with_text(ctx, frame, text_to_insert, replacement_target=None, insertion_anchor=None):
    logger.info("Output mode: Replace image with text")
    # This is complex: needs to identify the selected graphic object precisely and remove it.
    # Then insert text at its position, possibly within a new text frame or directly.
    try:
        controller = frame.getController()
        selection = replacement_target or controller.getSelection()
        anchor = insertion_anchor
        model = controller.getModel()
        text_doc = model.getText() if model is not None and hasattr(model, "getText") else None

        def _insert_text_via_anchor():
            if anchor is None:
                return False

            resolved_anchor = _resolve_insertion_cursor(text_doc, anchor)
            if resolved_anchor is not None:
                try:
                    if hasattr(resolved_anchor, "setString"):
                        resolved_anchor.setString(text_to_insert)
                        logger.info("Replaced selected target using resolved anchor.setString() fallback.")
                        return True
                except Exception as anchor_set_error:
                    logger.debug(f"Resolved anchor setString fallback failed in replace mode: {anchor_set_error}")

            try:
                view_cursor = controller.getViewCursor()
                if view_cursor is not None:
                    view_cursor.gotoRange(resolved_anchor or anchor, False)
                    view_cursor.setString(text_to_insert)
                    view_cursor.collapseToEnd()
                    logger.info("Replaced selected target using view-cursor anchor fallback.")
                    return True
            except Exception as anchor_cursor_error:
                logger.debug(f"Anchor fallback via view cursor failed in replace mode: {anchor_cursor_error}")
            return False

        if not selection:
            if _insert_text_via_anchor():
                logger.info(
                    "No explicit selection object; used insertion anchor fallback for replace mode."
                )
                return True
            uno_utils.show_message_box(_("Error"), _("No suitable object selected to replace. Select an image or shape."), "warningbox", parent_frame=frame, ctx=ctx)
            return False

        # Normalise selection containers and pick a single replacement candidate.
        if hasattr(selection, "getCount") and hasattr(selection, "getByIndex"):
            try:
                if selection.getCount() == 1:
                    selection = selection.getByIndex(0)
                elif selection.getCount() > 1:
                    logger.warning("Replace image mode received multi-selection; using first suitable graphic object.")
                    candidate = None
                    for i in range(selection.getCount()):
                        item = selection.getByIndex(i)
                        services = []
                        if hasattr(item, "supportsService"):
                            try:
                                if item.supportsService("com.sun.star.text.TextGraphicObject"):
                                    services.append("TextGraphicObject")
                                if item.supportsService("com.sun.star.text.XTextContent"):
                                    services.append("XTextContent")
                                if item.supportsService("com.sun.star.drawing.XShape"):
                                    services.append("XShape")
                            except Exception:
                                pass
                        if services:
                            candidate = item
                            break
                    if candidate is not None:
                        selection = candidate
                    else:
                        if _insert_text_via_anchor():
                            logger.info("Replace mode could not pick a single candidate; used anchor fallback.")
                            return True
                        uno_utils.show_message_box(
                            _("Error"),
                            _("No suitable object selected to replace. Select an image or shape."),
                            "warningbox",
                            parent_frame=frame,
                            ctx=ctx,
                        )
                        return False
            except Exception as selection_error:
                logger.debug(f"Could not normalize selection collection for replace mode: {selection_error}")
                if _insert_text_via_anchor():
                    logger.info("Collection normalization for replace mode failed; used anchor fallback.")
                    return True
                uno_utils.show_message_box(
                    _("Error"),
                    _("No suitable object selected to replace. Select an image or shape."),
                    "warningbox",
                    parent_frame=frame,
                    ctx=ctx,
                )
                return False

        if not selection:
            uno_utils.show_message_box(_("Error"), _("No suitable object selected to replace. Select an image or shape."), "warningbox", parent_frame=frame, ctx=ctx)
            return False

        has_supports_service = hasattr(selection, "supportsService")
        if not has_supports_service and not (
            hasattr(selection, "Graphic")
            or hasattr(selection, "GraphicURL")
            or hasattr(selection, "GraphicObject")
            or hasattr(selection, "GraphicObjectURL")
        ):
            if _insert_text_via_anchor():
                logger.info("Selection lacks service metadata for replace mode; used anchor fallback.")
                return True
            uno_utils.show_message_box(
                _("Error"),
                _("No suitable object selected to replace. Select an image or shape."),
                "warningbox",
                parent_frame=frame,
                ctx=ctx,
            )
            return False

        def _supports(service_name):
            try:
                if not has_supports_service:
                    return False
                return selection.supportsService(service_name)
            except Exception:
                return False

        # Prefer TextGraphicObject explicitly used by Writer inserted images.
        is_text_graphic_object = _supports("com.sun.star.text.TextGraphicObject")
        is_text_content = _supports("com.sun.star.text.XTextContent")
        is_text_shape = _supports("com.sun.star.drawing.XShape")
        is_text_shape_old = _supports("com.sun.star.drawing.Shape")
        is_graphic_attr_candidate = (
            hasattr(selection, "Graphic")
            or hasattr(selection, "GraphicURL")
            or hasattr(selection, "GraphicObject")
            or hasattr(selection, "GraphicObjectURL")
        )

        if not (is_text_graphic_object or is_text_content or is_text_shape or is_text_shape_old or is_graphic_attr_candidate):
            logger.warning("Selected object is not a supported image/shape replacement target.")
            if _insert_text_via_anchor():
                logger.info("Selection not recognized as image/shape in replace mode; used anchor fallback.")
                return True
            uno_utils.show_message_box(
                _("Error"),
                _("No suitable object selected to replace. Select an image or shape."),
                "warningbox",
                parent_frame=frame,
                ctx=ctx,
            )
            return False

        def _remove_graphic_candidate():
            if not (is_text_graphic_object or is_text_content):
                return False
            try:
                text_doc.removeTextContent(selection)
                logger.info("Removed selected graphic/text content before replacement.")
                return True
            except Exception as remove_error:
                logger.debug(f"removeTextContent failed in replace mode: {remove_error}")
            return False

        text_doc_model = controller.getModel()
        text_doc = text_doc_model.getText()

        # Capture anchor before removing the object (important for stable insertion point).
        anchor = insertion_anchor
        if anchor is None:
            try:
                if is_text_graphic_object or is_text_content or is_text_shape_old or is_text_shape:
                    if hasattr(selection, "getAnchor"):
                        anchor = selection.getAnchor()
            except Exception:
                anchor = insertion_anchor
            if anchor is None:
                try:
                    if hasattr(selection, "Anchor"):
                        anchor = selection.Anchor
                except Exception:
                    anchor = insertion_anchor
        
        # Attempt to remove the selected object
        # For XTextContent (like embedded images in Writer)
        if is_text_content:
            _remove_graphic_candidate()
            logger.info("Removed selected XTextContent (image). Attempting to insert text at anchor.")
            if _insert_text_via_anchor():
                return True
            logger.warning("Could not replace selected XTextContent at captured anchor.")
            return False

        if is_text_graphic_object:
            _remove_graphic_candidate()
            if _insert_text_via_anchor():
                logger.info("Replaced selected TextGraphicObject using anchor fallback.")
                return True
            logger.warning("Could not replace selected TextGraphicObject at captured anchor.")
            return False

        # For XShape (more common in Draw/Impress, but can be in Writer)
        # This path might be less common for the typical "selected image" in Writer
        elif is_text_shape or is_text_shape_old:
            # Removing XShape usually involves getting its parent (DrawPage) and calling remove.
            # This is more complex and context-dependent (Writer vs Draw).
            # For Writer, shapes are often anchored. If it's a graphic shape from Draw tools.
            try:
                text_doc.removeTextContent(selection)
                logger.info("Removed selected XShape object, inserting text at original anchor.")
                if _insert_text_via_anchor():
                    return True
            except Exception as remove_shape_error:
                logger.debug(f"Could not remove XShape as text content: {remove_shape_error}")
            try:
                if hasattr(selection, "dispose"):
                    selection.dispose()
                    logger.info("Disposed selected XShape for replacement.")
            except Exception as dispose_error:
                logger.debug(f"Could not dispose XShape: {dispose_error}")
            logger.warning("Could not determine precise anchor for shape replacement.")
            return False
        else:
            if _insert_text_via_anchor():
                logger.info("Fallback replaced selected content using anchor text insertion.")
                return True
            if is_graphic_attr_candidate:
                logger.warning("Image-like object could not be replaced through direct APIs.")
                return False

            uno_utils.show_message_box(_("Error"), _("Selected object cannot be directly replaced this way."), "warningbox", parent_frame=frame, ctx=ctx)
            return False
        
        return False

    except Exception as e:
        logger.error(f"Error replacing image with text: {e}", exc_info=True)
        uno_utils.show_message_box(_("Replace Image Error"), _("Could not replace image with text: {error}").format(error=e), "errorbox", parent_frame=frame, ctx=ctx)
        return False

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

def handle_ocr_output(ctx, frame, recognized_text, output_mode, insertion_anchor=None, replacement_target=None):
    """Main dispatcher for handling OCR output based on the selected mode."""
    logger.info(f"Handling OCR output. Mode: {output_mode}, Text length: {len(recognized_text if recognized_text else '')}")
    if recognized_text is None: # Should not happen if dialog returned success, but check
        logger.warning("handle_ocr_output called with None text.")
        # uno_utils.show_message_box(_("OCR Result"), _("No text was recognized."), "infobox", parent_frame=frame, ctx=ctx)
        return

    if output_mode == constants.OUTPUT_MODE_CURSOR:
        _insert_text_at_cursor(ctx, frame, recognized_text, insertion_anchor=insertion_anchor)
    elif output_mode == constants.OUTPUT_MODE_TEXTBOX:
        _insert_text_into_new_textbox(ctx, frame, recognized_text, insertion_anchor=insertion_anchor)
    elif output_mode == constants.OUTPUT_MODE_REPLACE:
        return _replace_image_with_text(
            ctx,
            frame,
            recognized_text,
            replacement_target=replacement_target,
            insertion_anchor=insertion_anchor,
        )
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
        def setString(self, s): pass
        def collapseToEnd(self): pass
        def createInstance(self, s): 
            if s == "com.sun.star.text.TextFrame": return MockTextFrame()
            return None
        def insertTextContent(self, c, tf, b): pass
        def getSelection(self): return None # Needs more for replace

    class MockTextFrame:
        def getText(self): return self
        def setString(self, s): pass
        def getSize(self): return MockSize()
        def setSize(self, s): pass

    class MockSize: Width=0; Height=0

    class MockCtx: pass

    mock_ctx = MockCtx()
    mock_frame = MockFrame()
    test_text = "This is a long test string from OCR result, meant to test different output mechanisms."
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_CURSOR)
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_TEXTBOX)
    # Clipboard and Replace are harder to mock simply here.
    handle_ocr_output(mock_ctx, mock_frame, test_text, constants.OUTPUT_MODE_CLIPBOARD) 
