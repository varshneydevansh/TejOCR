# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Core OCR processing, Tesseract interaction, and image handling."""

import uno
import unohelper
import os
import tempfile
import shutil # For shutil.which & tesseract path checking

from tejocr import uno_utils
from tejocr import constants
from tejocr import locale_setup # Added for i18n

_ = locale_setup.get_translator().gettext # Added for i18n

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Engine")

# Attempt to import pytesseract and Pillow, but handle if not available initially
PYTESSERACT_AVAILABLE = False
PILLOW_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    logger.warning("Pytesseract library not found. OCR functionality will be disabled.")

try:
    from PIL import Image, ImageOps, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    logger.warning("Pillow (PIL) library not found. Advanced image preprocessing will be disabled.")


def _get_temp_image_path(suffix=".png"):
    """Creates a temporary file path for image export."""
    return uno_utils.create_temp_file(suffix=suffix, prefix="tejocr_img_")

def _export_graphic_to_file(xgraphic, file_path, mime_type="image/png"):
    """Exports an XGraphic object to a file.
    Returns True on success, False on failure.
    """
    if not xgraphic:
        return False
    try:
        provider = uno_utils.create_instance("com.sun.star.graphic.GraphicProvider")
        if not provider:
            logger.error("Could not create GraphicProvider service for image export.")
            return False
        
        # Store properties
        prop_val = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        prop_val.Name = "URL"
        prop_val.Value = unohelper.systemPathToFileUrl(file_path)
        
        prop_val_mime = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        prop_val_mime.Name = "MimeType"
        prop_val_mime.Value = mime_type
        
        properties = (prop_val, prop_val_mime)
        provider.storeGraphic(xgraphic, properties)
        return True
    except Exception as e:
        logger.error(f"Error exporting graphic to {file_path}: {e}", exc_info=True)
        uno_utils.show_message_box(_("Image Export Error"), _("Failed to export image for OCR: {e}").format(e=e), "errorbox") # i18n
        return False

def _get_image_from_selection(frame, ctx):
    """Gets the selected graphic, exports it to a temp file, and returns the file path."""
    if not frame:
        return None

    controller = frame.getController()
    if not controller: return None
    selection = controller.getSelection()
    if not selection: return None

    graphic_shape = None
    # Simplified selection check; uno_utils.is_graphic_object_selected is more for UI enabling
    # Here we need the actual shape to extract the graphic from.
    if selection.supportsService("com.sun.star.drawing.Shape") and \
       (hasattr(selection, "Graphic") or hasattr(selection, "GraphicURL")):
        graphic_shape = selection
    elif selection.supportsService("com.sun.star.text.TextContent") and \
         hasattr(selection, "Graphic") and selection.Graphic is not None:
         graphic_shape = selection # e.g. image in text frame, or Math object
    elif selection.supportsService("com.sun.star.drawing.ShapeCollection") and selection.getCount() == 1:
        shape_in_collection = selection.getByIndex(0)
        if shape_in_collection.supportsService("com.sun.star.drawing.Shape") and \
           (hasattr(shape_in_collection, "Graphic") or hasattr(shape_in_collection, "GraphicURL")):
            graphic_shape = shape_in_collection
    
    if not graphic_shape:
        uno_utils.show_message_box(_("No Image"), _("Could not identify a valid graphic object in the selection."), "warningbox", parent_frame=frame, ctx=ctx) # i18n
        return None

    xgraphic = uno_utils.get_graphic_from_selected_shape(graphic_shape) # Use the refined helper
    if not xgraphic:
        # If get_graphic_from_selected_shape returns the shape itself (e.g. GraphicObjectShape with URL)
        # we need to use an exporter for the shape, not just XGraphic.
        # This part requires a more robust exporter that handles XShape directly.
        # For now, if we don't get a direct XGraphic, we might not be able to export easily here.
        # A full implementation would use com.sun.star.drawing.XGraphicExporter on the shape.
        uno_utils.show_message_box(_("No Image Data"), _("Could not extract usable image data from the selected object."), "warningbox", parent_frame=frame, ctx=ctx) # i18n
        return None # Placeholder for more complex export

    temp_image_file = _get_temp_image_path()
    if _export_graphic_to_file(xgraphic, temp_image_file):
        return temp_image_file
    else:
        if os.path.exists(temp_image_file): os.remove(temp_image_file) # Clean up failed export
        return None

def _preprocess_image(image_path, grayscale=False, binarize_method=None):
    """Applies preprocessing steps to the image using Pillow.
    binarize_method: None or 'otsu'.
    Returns path to the processed image (might be same as input or a new temp file).
    """
    if not PILLOW_AVAILABLE:
        if grayscale or binarize_method:
            logger.info("Pillow not available, skipping preprocessing.")
        return image_path # Cannot preprocess

    try:
        img = Image.open(image_path)
        original_format = img.format
        processed = False

        if grayscale:
            img = ImageOps.grayscale(img)
            processed = True
        
        if binarize_method == 'otsu':
            # For Otsu, typically image should be grayscale first
            if not grayscale:
                img_gray = ImageOps.grayscale(img)
            else:
                img_gray = img
            # Pillow doesn't have Otsu directly. A common way is via OpenCV or scikit-image.
            # For a pure Pillow approach, a simple thresholding or adaptive thresholding can be used.
            # For simplicity here, we'll just invert if it's dark text on light bg for some basic binarization effect
            # This is NOT Otsu, just a placeholder for a more advanced binarization step.
            # img = img_gray.point(lambda x: 0 if x < 128 else 255, '1') # Example simple threshold
            # A better placeholder for "binarization" without external libs for Otsu:
            img = img_gray.convert('1') # Convert to bilevel (1-bit pixels) using a default threshold
            processed = True

        if processed:
            # Save to a new temp file to avoid overwriting original if it was from user's disk
            processed_path = _get_temp_image_path(suffix=f".{original_format.lower() if original_format else 'png'}")
            img.save(processed_path)
            # If the original image_path was a temp file, remove it
            if image_path.startswith(tempfile.gettempdir()) and image_path != processed_path:
                 try: os.remove(image_path) # clean up intermediate temp file
                 except OSError: pass
            return processed_path
        else:
            return image_path

    except Exception as e:
        logger.error(f"Error during image preprocessing for '{image_path}': {e}", exc_info=True)
        return image_path # Return original path if preprocessing fails

def check_tesseract_path(tesseract_path, ctx=None, parent_frame=None, show_success=False):
    """Checks if Tesseract is available at the given path or via auto-detection."""
    if not PYTESSERACT_AVAILABLE:
        logger.error("Pytesseract library not installed. Cannot check Tesseract path.")
        uno_utils.show_message_box(_("Pytesseract Missing"), _("The 'pytesseract' Python library is not installed. TejOCR cannot function without it."), "errorbox", parent_frame=parent_frame, ctx=ctx) # i18n
        return False

    tess_exec = uno_utils.find_tesseract_executable(tesseract_path, ctx) # Pass ctx for potential messages
    
    if not tess_exec:
        logger.warning("Tesseract executable not found via find_tesseract_executable.")
        uno_utils.show_message_box(_("Tesseract Not Found"), 
                                 _("Tesseract OCR executable was not found at the specified path or in system PATH. Please configure the path in TejOCR Settings."), 
                                 "errorbox", parent_frame=parent_frame, ctx=ctx) # i18n
        return False

    # Try running tesseract --version
    original_cmd = pytesseract.pytesseract.tesseract_cmd
    pytesseract.pytesseract.tesseract_cmd = tess_exec
    try:
        version = pytesseract.get_tesseract_version()
        if show_success:
            logger.info(f"Tesseract version {version} found at {tess_exec}.")
            uno_utils.show_message_box(_("Tesseract Found"), _("Tesseract OCR (Version {version}) found and working at:\n{path}").format(version=version, path=tess_exec), "infobox", parent_frame=parent_frame, ctx=ctx) # i18n
        return True
    except pytesseract.TesseractNotFoundError:
        logger.warning(f"Pytesseract TesseractNotFoundError for path: {tess_exec}")
        uno_utils.show_message_box(_("Tesseract Not Found"), _("Pytesseract could not find Tesseract at {path} despite the file existing. Check permissions or Tesseract installation.").format(path=tess_exec), "errorbox", parent_frame=parent_frame, ctx=ctx) # i18n
        return False
    except Exception as e:
        logger.error(f"Error testing Tesseract at {tess_exec}: {e}", exc_info=True)
        uno_utils.show_message_box(_("Tesseract Error"), _("Error while testing Tesseract at {path}:\n{error}").format(path=tess_exec, error=e), "errorbox", parent_frame=parent_frame, ctx=ctx) # i18n
        return False
    finally:
        pytesseract.pytesseract.tesseract_cmd = original_cmd # Restore


def perform_ocr(ctx, frame, source_type, image_path_or_selection_options, ocr_options, status_callback=None):
    """Main function to perform OCR.
    source_type: 'file' or 'selected'
    image_path_or_selection_options: file path if source_type is 'file', or dict of selection info (not used yet)
    ocr_options: dict containing lang, psm, oem, grayscale, binarize
    status_callback: function to update a status label (e.g., lambda msg: status_label.setText(msg))
    Returns a dict: {"success": True/False, "text": "recognized_text" or None, "message": "status_message"}
    """
    if not PYTESSERACT_AVAILABLE:
        logger.error("perform_ocr called but Pytesseract library not installed.")
        return {"success": False, "text": None, "message": _("Pytesseract library not installed.")} # i18n

    if status_callback: status_callback(_("Initializing OCR...")) # i18n
    logger.info(f"Performing OCR: source='{source_type}', options={ocr_options}")

    tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, ctx)
    if not check_tesseract_path(tess_path_cfg, ctx, frame):
        logger.warning("Tesseract path check failed during perform_ocr.")
        return {"success": False, "text": None, "message": _("Tesseract not found or not working. Please check settings.")} # i18n
    
    # Ensure tesseract_cmd is set for this pytesseract session
    effective_tess_path = uno_utils.find_tesseract_executable(tess_path_cfg)
    if not effective_tess_path: # Should have been caught by check_tesseract_path, but double check
        logger.error("Effective Tesseract path could not be determined even after check_tesseract_path passed.")
        return {"success": False, "text": None, "message": _("Critical error: Tesseract path inconsistency.")} # i18n
    pytesseract.pytesseract.tesseract_cmd = effective_tess_path

    temp_image_to_ocr = None
    original_image_path_for_cleanup = None
    final_image_for_ocr = None # Initialize here for broader scope in finally block

    try:
        if source_type == 'file':
            if not image_path_or_selection_options or not os.path.isfile(str(image_path_or_selection_options)):
                logger.error(f"Invalid image file path for OCR: {image_path_or_selection_options}")
                return {"success": False, "text": None, "message": _("Invalid image file path provided.")} # i18n
            temp_image_to_ocr = str(image_path_or_selection_options)
            logger.info(f"OCR source is file: {temp_image_to_ocr}")
        elif source_type == 'selected':
            if status_callback: status_callback(_("Extracting selected image...")) # i18n
            logger.info("OCR source is selected image. Attempting extraction.")
            temp_image_to_ocr = _get_image_from_selection(frame, ctx)
            if not temp_image_to_ocr:
                logger.warning("Failed to extract image from selection for OCR.")
                return {"success": False, "text": None, "message": _("Failed to extract image from selection.")} # i18n
            original_image_path_for_cleanup = temp_image_to_ocr # Mark for cleanup after preprocessing
            logger.info(f"Selected image exported to temp file: {temp_image_to_ocr}")
        else:
            logger.error(f"Invalid OCR source type: {source_type}")
            return {"success": False, "text": None, "message": _("Invalid OCR source type.")} # i18n

        if status_callback: status_callback(_("Preprocessing image (if enabled)...")) # i18n
        logger.info(f"Preprocessing image '{temp_image_to_ocr}' with options: grayscale={ocr_options.get('grayscale')}, binarize={ocr_options.get('binarize')}")
        processed_image_path = _preprocess_image(temp_image_to_ocr, 
                                               ocr_options.get('grayscale', False), 
                                               'otsu' if ocr_options.get('binarize', False) else None)
        
        # If preprocessing created a new file and the original was a temp file, clean up original.
        if original_image_path_for_cleanup and processed_image_path != original_image_path_for_cleanup and \
           original_image_path_for_cleanup.startswith(tempfile.gettempdir()):
            logger.debug(f"Cleaning up original temp image: {original_image_path_for_cleanup}")
            try: os.remove(original_image_path_for_cleanup)
            except OSError as e_rem_orig:
                 logger.warning(f"Could not remove original temp image '{original_image_path_for_cleanup}': {e_rem_orig}")
                 pass

        final_image_for_ocr = processed_image_path
        logger.info(f"Image for Tesseract: {final_image_for_ocr}")

        if status_callback: status_callback(_("Performing OCR (Lang: {lang_code})...").format(lang_code=ocr_options.get('lang'))) # i18n
        
        custom_config = f"--oem {ocr_options.get('oem', constants.DEFAULT_OEM_MODE)} --psm {ocr_options.get('psm', constants.DEFAULT_PSM_MODE)}"
        logger.info(f"Tesseract config: lang='{ocr_options.get('lang')}', {custom_config}")
        
        # Check for low DPI (placeholder, actual DPI check from image file is more complex)
        # For now, assume if preprocessing is done, Pillow might have handled it to some extent.
        # A real DPI check would involve reading image metadata.
        # if image_resolution_is_low(final_image_for_ocr):
        #     if status_callback: status_callback(_("Warning: Image resolution may be too low for good results.")) # i18n
        #     uno_utils.show_message_box(_("Low Resolution"), _("Image resolution appears low (<150 DPI). OCR quality might be poor."), "warningbox", parent_frame=frame, ctx=ctx) # i18n

        text = pytesseract.image_to_string(Image.open(final_image_for_ocr), 
                                           lang=ocr_options.get('lang', constants.DEFAULT_OCR_LANGUAGE),
                                           config=custom_config)
        
        logger.info(f"Tesseract image_to_string successful. Output length: {len(text)}")
        if status_callback: status_callback(_("OCR Complete.")) # i18n
        return {"success": True, "text": text, "message": _("OCR successful.")} # i18n

    except pytesseract.TesseractNotFoundError:
        msg = _("Tesseract is not installed or not in your PATH. Please check settings.") # i18n
        logger.error(f"TesseractNotFoundError during OCR: {msg} (Effective path used: {effective_tess_path})")
        if status_callback: status_callback(_("Error: {message}").format(message=msg)) # i18n
        return {"success": False, "text": None, "message": msg}
    except pytesseract.TesseractError as tess_err:
        msg = _("Tesseract error: {error_details}").format(error_details=str(tess_err)[:200]+"...") # i18n
        logger.error(f"TesseractError during OCR: {msg}", exc_info=True)
        if status_callback: status_callback(_("Error: {message}").format(message=msg)) # i18n
        return {"success": False, "text": None, "message": msg}
    except FileNotFoundError:
        msg = _("Image file not found for OCR (it may have been a temporary file that was removed prematurely).") # i18n
        logger.error(f"FileNotFoundError during OCR. Expected image at: {final_image_for_ocr if 'final_image_for_ocr' in locals() else 'Unknown'}", exc_info=True)
        if status_callback: status_callback(_("Error: {message}").format(message=msg)) # i18n
        return {"success": False, "text": None, "message": msg}
    except Exception as e:
        import traceback
        logger.error(f"Generic error in perform_ocr: {e}", exc_info=True)
        # print(f"Generic error in perform_ocr: {e}\n{traceback.format_exc()}") # Replaced by logger
        msg = _("An unexpected error occurred during OCR: {error_details}").format(error_details=str(e)[:200]+"...") # i18n
        if status_callback: status_callback(_("Error: {message}").format(message=msg)) # i18n
        return {"success": False, "text": None, "message": msg}
    finally:
        # Clean up the final processed image if it was a temporary file
        if final_image_for_ocr and final_image_for_ocr.startswith(tempfile.gettempdir()): # Check final_image_for_ocr directly
            logger.debug(f"Cleaning up processed temp image: {final_image_for_ocr}")
            try: os.remove(final_image_for_ocr)
            except OSError as e_rem_final:
                 logger.warning(f"Could not remove processed temp image '{final_image_for_ocr}': {e_rem_final}")
                 pass
        # Ensure original temp file for selection is cleaned if not already handled and different from final
        if original_image_path_for_cleanup and os.path.exists(original_image_path_for_cleanup) and \
           original_image_path_for_cleanup != final_image_for_ocr and \
           original_image_path_for_cleanup.startswith(tempfile.gettempdir()):
            logger.debug(f"Cleaning up original temp image (final pass): {original_image_path_for_cleanup}")
            try: os.remove(original_image_path_for_cleanup)
            except OSError as e_rem_orig_final:
                 logger.warning(f"Could not remove original temp image (final pass) '{original_image_path_for_cleanup}': {e_rem_orig_final}")
                 pass 

if __name__ == "__main__":
    # This only runs if the script is executed directly.
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("TejOCR.Engine.__main__")
    main_logger.info("tejocr_engine.py: For testing, run relevant functions with mock objects or from within LibreOffice.")
    # Example (requires Tesseract installed and in PATH, and Pillow for preprocessing)
    # mock_options = {
    #     'lang': 'eng',
    #     'psm': constants.DEFAULT_PSM_MODE,
    #     'oem': constants.DEFAULT_OEM_MODE,
    #     'grayscale': True,
    #     'binarize': True
    # }
    # Create a dummy image file for testing
    # if PILLOW_AVAILABLE:
    #     try:
    #         img = Image.new('RGB', (600, 100), color = 'red')
    #         from PIL import ImageDraw
    #         d = ImageDraw.Draw(img)
    #         d.text((10,10), "Hello World from TejOCR Test", fill=(255,255,0))
    #         dummy_image_path = os.path.join(tempfile.gettempdir(), "tejocr_dummy_test.png")
    #         img.save(dummy_image_path)
    #         main_logger.info(f"Created dummy image: {dummy_image_path}")
            
    #         # Test check_tesseract_path
    #         # main_logger.info("\nChecking Tesseract path...")
    #         # check_tesseract_path(None, show_success=True) # Auto-detect

    #         # main_logger.info("\nPerforming OCR on dummy image...")
    #         # result = perform_ocr(None, None, 'file', dummy_image_path, mock_options, status_callback=main_logger.info)
    #         # main_logger.info(f"OCR Result: {result}")
            
    #         if os.path.exists(dummy_image_path):
    #             os.remove(dummy_image_path)
    #     except Exception as e:
    #         main_logger.error(f"Error in __main__ test: {e}", exc_info=True)
    # else:
    #     main_logger.warning("Pillow not available, cannot run full __main__ test.")

    if not PYTESSERACT_AVAILABLE:
        main_logger.warning("Pytesseract not available. Cannot run test for check_tesseract_path.")
    else:
        main_logger.info("Testing check_tesseract_path (will try to find Tesseract in PATH)...")
        check_tesseract_path(None, show_success=True) 