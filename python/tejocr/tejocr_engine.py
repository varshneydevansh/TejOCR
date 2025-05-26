# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Core OCR processing, Tesseract interaction, and image handling."""

import os
import sys
import uno
import unohelper
import tempfile
import shutil # For shutil.which & tesseract path checking

from tejocr import uno_utils
from tejocr import constants
from tejocr import locale_setup # Added for i18n

_ = locale_setup.get_translator().gettext # Added for i18n

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Engine")

# Global variables for pytesseract state
PYTESSERACT_AVAILABLE = False
pytesseract = None

def _initialize_pytesseract():
    """Initialize pytesseract with robust error handling and path detection."""
    global PYTESSERACT_AVAILABLE, pytesseract
    
    if PYTESSERACT_AVAILABLE and pytesseract:
        return True
    
    # First, try to ensure numpy is available since pytesseract depends on it
    numpy_available = False
    try:
        import numpy
        numpy_available = True
        logger.debug(f"NumPy found: version {numpy.__version__}")
    except ImportError as numpy_err:
        logger.warning(f"NumPy import failed: {numpy_err}")
        
        # Try to add LibreOffice Python paths and check for numpy
        try:
            lo_python_paths = [
                "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/lib/python3.10/site-packages",
                "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.10/lib/python3.10/site-packages"
            ]
            
            for path in lo_python_paths:
                if os.path.exists(path) and path not in sys.path:
                    sys.path.insert(0, path)
                    logger.debug(f"Added {path} to sys.path for NumPy search")
            
            # Try numpy import again after path adjustment
            import numpy
            numpy_available = True
            logger.info(f"NumPy found after path adjustment: version {numpy.__version__}")
        except ImportError as numpy_err2:
            logger.error(f"NumPy still not found after path adjustment: {numpy_err2}")
            numpy_available = False
    
    if not numpy_available:
        logger.error("NumPy is required for pytesseract but not found in LibreOffice Python environment")
        return False
    
    try:
        # First attempt: Standard import (numpy is now confirmed available)
        import pytesseract as pt
        pytesseract = pt
        
        # Verify tesseract executable is accessible
        tesseract_path = _find_tesseract_executable()
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.info(f"Pytesseract initialized successfully with tesseract at: {tesseract_path}")
            
            # Set TESSDATA_PREFIX if not already set
            if not os.environ.get("TESSDATA_PREFIX"):
                tess_dir = os.path.dirname(tesseract_path)  # e.g., /opt/homebrew/bin
                potential_tessdata_prefix = os.path.abspath(os.path.join(tess_dir, "..", "share", "tessdata"))
                if os.path.isdir(potential_tessdata_prefix):
                    logger.info(f"Setting TESSDATA_PREFIX to: {potential_tessdata_prefix}")
                    os.environ["TESSDATA_PREFIX"] = potential_tessdata_prefix
                else:
                    logger.warning(f"Could not auto-determine TESSDATA_PREFIX from {tesseract_path}. Assumed path {potential_tessdata_prefix} not found.")
            
            # Test that it actually works
            try:
                version_info = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract version confirmed: {version_info}")
                PYTESSERACT_AVAILABLE = True
                return True
            except Exception as e:
                logger.warning(f"Pytesseract imported but tesseract not working: {e}")
                return False
        else:
            logger.warning("Pytesseract imported but tesseract executable not found")
            return False
            
    except ImportError as e:
        logger.error(f"Pytesseract import failed even with NumPy available: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error initializing pytesseract: {e}", exc_info=True)
        return False

def _find_tesseract_executable():
    """Find tesseract executable with multiple fallback strategies."""
    # Strategy 1: Check if already set
    if hasattr(pytesseract, 'pytesseract') and hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
        current_cmd = pytesseract.pytesseract.tesseract_cmd
        if current_cmd != 'tesseract' and os.path.isfile(current_cmd):
            return current_cmd
    
    # Strategy 2: Use shutil.which (respects PATH)
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        logger.debug(f"Found tesseract via shutil.which: {tesseract_path}")
        return tesseract_path
    
    # Strategy 3: Common macOS locations
    common_paths = [
        '/usr/local/bin/tesseract',
        '/opt/homebrew/bin/tesseract',
        '/usr/bin/tesseract'
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            logger.debug(f"Found tesseract at common location: {path}")
            return path
    
    logger.warning("Tesseract executable not found in any known location")
    return None

def is_tesseract_ready(ctx=None, show_gui_errors=True, parent_frame=None):
    """Check if Tesseract and pytesseract are ready for OCR operations."""
    if not _initialize_pytesseract():
        if show_gui_errors:
            # Check specifically what's missing to provide better error message
            numpy_available = False
            try:
                import numpy
                numpy_available = True
            except ImportError:
                pass
            
            if not numpy_available:
                error_message = "TejOCR requires NumPy for OCR functionality.\n\nNumPy is missing from LibreOffice's Python environment.\n\nTo install:\n• /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract\n\nThen restart LibreOffice."
                title = "NumPy Required"
            else:
                error_message = "Tesseract OCR is not properly installed or configured.\n\nPlease install tesseract and pytesseract:\n• brew install tesseract\n• /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install pytesseract numpy\n\nThen restart LibreOffice."
                title = "Tesseract Not Available"
                
            uno_utils.show_message_box(
                title,
                error_message,
                "errorbox",
                parent_frame=parent_frame,
                ctx=ctx
            )
        return False, "Pytesseract not available or tesseract not found"
    
    try:
        # Test actual OCR capability with a minimal operation
        version = pytesseract.get_tesseract_version()
        logger.debug(f"Tesseract ready check passed. Version: {version}")
        return True, f"Tesseract v{version} ready"
    except Exception as e:
        error_msg = f"Tesseract test failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if show_gui_errors:
            uno_utils.show_message_box(
                "Tesseract Test Failed",
                f"Tesseract is installed but not working properly:\n\n{error_msg}\n\nPlease check your installation.",
                "errorbox",
                parent_frame=parent_frame,
                ctx=ctx
            )
        return False, error_msg

# Attempt to import pytesseract and Pillow, but handle if not available initially
PILLOW_AVAILABLE = False

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

def _preprocess_image(image_path, improve_quality=False, grayscale=False, binarize_method=None):
    """Applies preprocessing steps to the image using Pillow.
    improve_quality: Applies a general set of enhancements if True.
    grayscale: Specifically convert to grayscale (can be part of improve_quality).
    binarize_method: None or 'otsu' (placeholder for more advanced binarization).
    Returns path to the processed image (might be same as input or a new temp file).
    """
    if not PILLOW_AVAILABLE:
        if improve_quality or grayscale or binarize_method:
            logger.info("Pillow not available, skipping all image preprocessing.")
        return image_path # Cannot preprocess

    try:
        logger.debug(f"Preprocessing image: '{image_path}'. Improve: {improve_quality}, Grayscale: {grayscale}, Binarize: {binarize_method}")
        img = Image.open(image_path)
        original_format = img.format
        processed_img = img # Start with the original image
        image_was_modified = False

        # Ensure image is in a mode that supports the filters (e.g., RGB, L)
        if processed_img.mode == 'P': # Palette mode
            logger.debug(f"Converting image from Palette mode (P) to RGB for preprocessing.")
            processed_img = processed_img.convert("RGB")
            image_was_modified = True # Conversion itself is a modification
        elif processed_img.mode == 'RGBA':
             logger.debug(f"Converting image from RGBA to RGB (removing alpha channel) for preprocessing.")
             background = Image.new("RGB", processed_img.size, (255, 255, 255)) # White background
             background.paste(processed_img, mask=processed_img.split()[3]) # 3 is the alpha channel
             processed_img = background
             image_was_modified = True

        if improve_quality:
            logger.debug("Applying general image quality improvements.")
            # 1. Convert to Grayscale (often good for OCR)
            processed_img = ImageOps.grayscale(processed_img)
            # 2. Apply a mild sharpen filter
            processed_img = processed_img.filter(ImageFilter.SHARPEN)
            # 3. Enhance contrast (simple auto-contrast)
            processed_img = ImageOps.autocontrast(processed_img, cutoff=1) # cutoff can be tuned
            image_was_modified = True
        
        if grayscale and not improve_quality: # Apply grayscale only if improve_quality didn't already do it
            logger.debug("Applying explicit grayscale conversion.")
            processed_img = ImageOps.grayscale(processed_img)
            image_was_modified = True
        
        if binarize_method == 'otsu': # Placeholder for Otsu, currently simple binarization
            logger.debug("Applying binarization (current: simple threshold).")
            # Ensure grayscale before binarizing if not already
            if processed_img.mode != 'L':
                img_for_binarize = ImageOps.grayscale(processed_img)
            else:
                img_for_binarize = processed_img
            
            processed_img = img_for_binarize.convert('1') # Convert to bilevel (1-bit pixels) using a default threshold
            image_was_modified = True

        if image_was_modified:
            # Save to a new temp file to avoid overwriting original if it was from user's disk
            # and to ensure the format is OCR-friendly (like PNG)
            processed_path = _get_temp_image_path(suffix=".png") # Save as PNG for consistency
            processed_img.save(processed_path, "PNG")
            logger.info(f"Image processed and saved to new temporary file: {processed_path}")
            
            # If the original image_path was a temp file (not the one we just created), remove it
            if image_path.startswith(tempfile.gettempdir()) and image_path != processed_path:
                 try: 
                     logger.debug(f"Removing original temporary image: {image_path}")
                     os.remove(image_path)
                 except OSError as e_remove:
                     logger.warning(f"Could not remove original temporary image '{image_path}': {e_remove}")
            return processed_path
        else:
            logger.debug("No preprocessing steps were applied or required modification.")
            return image_path # Return original if no changes made

    except Exception as e:
        logger.error(f"Error during image preprocessing for '{image_path}': {e}", exc_info=True)
        return image_path # Return original path if preprocessing fails

def extract_text_from_selected_image(ctx, frame, lang="eng", improve_image=False):
    """Extract text from currently selected image in LibreOffice."""
    if not _initialize_pytesseract():
        logger.error("Cannot extract text: Pytesseract not available")
        # uno_utils.show_message_box(_("Pytesseract Error"), _("Pytesseract library is not available. Please check installation."), "errorbox", parent_frame=frame, ctx=ctx)
        return None
    
    exported_temp_image_path = None # Path of the image exported from selection
    processed_image_path = None # Path of the image after preprocessing (if any)
    final_image_path_for_ocr = None

    try:
        controller = frame.getController()
        if not controller: logger.error("No controller available"); return None
        selection = controller.getSelection()
        if not selection: logger.error("No selection available"); return None
        
        graphic = uno_utils.get_graphic_from_selection(selection, ctx)
        if not graphic: logger.error("Could not extract graphic from selection"); return None
        
        exported_temp_image_path = uno_utils.create_temp_file_from_graphic(graphic, ctx)
        if not exported_temp_image_path:
            logger.error("Could not create temporary image file from graphic")
            # uno_utils.show_message_box(_("Image Export Error"), _("Failed to export selected image for OCR."), "errorbox", parent_frame=frame, ctx=ctx)
            return None
        
        final_image_path_for_ocr = exported_temp_image_path # Default to exported path

        if improve_image and PILLOW_AVAILABLE:
            logger.info(f"Preprocessing selected image (originally: {exported_temp_image_path}) as improve_image is True.")
            processed_image_path = _preprocess_image(exported_temp_image_path, improve_quality=True)
            if processed_image_path and processed_image_path != exported_temp_image_path:
                logger.debug(f"Using preprocessed image: {processed_image_path}")
                final_image_path_for_ocr = processed_image_path
            elif not processed_image_path:
                logger.warning(f"Preprocessing returned None for {exported_temp_image_path}. Using original temp image.")
            # If processed_image_path is same as exported_temp_image_path, no change, final_image_path_for_ocr is already correct
        elif improve_image and not PILLOW_AVAILABLE:
            logger.warning("Image improvement requested but Pillow is not available. OCR will proceed without it.")
            # uno_utils.show_message_box(_("Pillow Missing"), _("Image improvement requires Pillow library, which is not found. OCR will proceed on the original image."), "warningbox", parent_frame=frame, ctx=ctx)

        if not final_image_path_for_ocr or not os.path.exists(final_image_path_for_ocr):
            logger.error(f"Final image path for OCR is invalid or does not exist: {final_image_path_for_ocr}")
            return None

        logger.info(f"Performing OCR on selected image (using '{final_image_path_for_ocr}') with language: {lang}")
        text = pytesseract.image_to_string(final_image_path_for_ocr, lang=lang)
        logger.info(f"OCR completed. Extracted {len(text)} characters.")
        return text.strip()
        
    except pytesseract.TesseractError as tess_err:
        logger.error(f"Tesseract error for selected image: {tess_err}", exc_info=True)
        # Fallback for language error can be added here if desired, as before
        # uno_utils.show_message_box(_("Tesseract Error"), str(tess_err), "errorbox", parent_frame=frame, ctx=ctx)
        return None
    except Exception as e:
        logger.error(f"Error extracting text from selected image: {e}", exc_info=True)
        # uno_utils.show_message_box(_("OCR Error"), _("An unexpected error occurred: {error}").format(error=e), "errorbox", parent_frame=frame, ctx=ctx)
        return None
    finally:
        # Clean up: exported_temp_image_path is the one from create_temp_file_from_graphic
        if exported_temp_image_path and os.path.exists(exported_temp_image_path):
            try: 
                os.remove(exported_temp_image_path)
                logger.debug(f"Cleaned up temporary exported image: {exported_temp_image_path}")
            except Exception as e_remove:
                logger.warning(f"Could not remove temporary exported image {exported_temp_image_path}: {e_remove}")
        
        # Clean up: processed_image_path is the one from _preprocess_image
        # Only remove if it's different from exported_temp_image_path and exists
        if processed_image_path and processed_image_path != exported_temp_image_path and os.path.exists(processed_image_path):
            try: 
                os.remove(processed_image_path)
                logger.debug(f"Cleaned up temporary preprocessed image: {processed_image_path}")
            except Exception as e_remove:
                logger.warning(f"Could not remove temporary preprocessed image {processed_image_path}: {e_remove}")

def extract_text_from_image_file(ctx, image_path, lang="eng", improve_image=False):
    """Extract text from an image file."""
    if not _initialize_pytesseract():
        logger.error("Cannot extract text: Pytesseract not available")
        # uno_utils.show_message_box(_("Pytesseract Error"), _("Pytesseract library is not available. Please check installation."), "errorbox", ctx=ctx) # Assuming no frame here
        return None
    
    if not os.path.exists(image_path):
        logger.error(f"Image file does not exist: {image_path}")
        # uno_utils.show_message_box(_("File Not Found"), _("Image file not found: {path}").format(path=image_path), "errorbox", ctx=ctx)
        return None
    
    processed_image_path = None # Path of the image after preprocessing (if any)
    final_image_path_for_ocr = image_path # Default to original user-provided path

    try:
        if improve_image and PILLOW_AVAILABLE:
            logger.info(f"Preprocessing image file ('{image_path}') as improve_image is True.")
            # _preprocess_image will create a new temp file if it modifies the image
            processed_image_path = _preprocess_image(image_path, improve_quality=True)
            if processed_image_path and processed_image_path != image_path:
                logger.debug(f"Using preprocessed image: {processed_image_path}")
                final_image_path_for_ocr = processed_image_path
            elif not processed_image_path:
                logger.warning(f"Preprocessing returned None for {image_path}. Using original image.")
            # If processed_image_path is same as image_path, no change, final_image_path_for_ocr is already correct
        elif improve_image and not PILLOW_AVAILABLE:
            logger.warning("Image improvement requested but Pillow is not available. OCR will proceed on the original image file.")
            # uno_utils.show_message_box(_("Pillow Missing"), _("Image improvement requires Pillow library, which is not found. OCR will proceed on the original image."), "warningbox", ctx=ctx)

        if not final_image_path_for_ocr or not os.path.exists(final_image_path_for_ocr):
            logger.error(f"Final image path for OCR is invalid or does not exist: {final_image_path_for_ocr}")
            return None

        logger.info(f"Performing OCR on image file (using '{final_image_path_for_ocr}') with language: {lang}")
        text = pytesseract.image_to_string(final_image_path_for_ocr, lang=lang)
        logger.info(f"OCR completed. Extracted {len(text)} characters from {os.path.basename(final_image_path_for_ocr)}")
        return text.strip()
    except pytesseract.TesseractError as tess_err:
        logger.error(f"Tesseract error for {final_image_path_for_ocr}: {tess_err}", exc_info=True)
        # Fallback for language error can be added here if desired
        # uno_utils.show_message_box(_("Tesseract Error"), str(tess_err), "errorbox", ctx=ctx)
        return None
    except Exception as e:
        logger.error(f"Error extracting text from image file {final_image_path_for_ocr}: {e}", exc_info=True)
        # uno_utils.show_message_box(_("OCR Error"), _("An unexpected error occurred: {error}").format(error=e), "errorbox", ctx=ctx)
        return None
    finally:
        # If a separate processed image was created (i.e., it's a temp file and different from original user path)
        if processed_image_path and processed_image_path != image_path and os.path.exists(processed_image_path) and processed_image_path.startswith(tempfile.gettempdir()):
            try:
                os.remove(processed_image_path)
                logger.debug(f"Cleaned up temporary preprocessed image: {processed_image_path}")
            except Exception as e_remove:
                logger.warning(f"Could not remove temporary preprocessed image {processed_image_path}: {e_remove}")

def check_tesseract_path(tesseract_path, ctx=None, parent_frame=None, show_success=False, show_gui_errors=True):
    """Check if a given tesseract path is valid and working."""
    if not tesseract_path:
        return False, "No path provided"
    
    if not os.path.isfile(tesseract_path):
        return False, f"File not found: {tesseract_path}"
    
    try:
        # Test the tesseract executable
        import subprocess
        result = subprocess.run([tesseract_path, '--version'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            version_info = result.stdout.strip().split('\n')[0] if result.stdout.strip() else "Version info unavailable"
            if show_success and show_gui_errors:
                uno_utils.show_message_box(
                    "Tesseract Test Success",
                    f"✓ Tesseract is working!\n\n{version_info}\n\nPath: {tesseract_path}",
                    "infobox",
                    parent_frame=parent_frame,
                    ctx=ctx
                )
            return True, version_info
        else:
            error_msg = f"Tesseract returned error code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            return False, error_msg
            
    except FileNotFoundError:
        return False, "Tesseract executable not found or not executable"
    except subprocess.TimeoutExpired:
        return False, "Tesseract test timed out"
    except Exception as e:
        return False, f"Error testing tesseract: {str(e)}"

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

def get_available_languages():
    """Returns a list of available Tesseract languages."""
    try:
        # Ensure Pytesseract is available
        if not PYTESSERACT_AVAILABLE:
            logger.warning("Pytesseract not available, cannot get languages")
            return ["eng"]  # Default fallback
        
        # Initialize if needed
        if not _initialize_pytesseract():
            logger.warning("Could not initialize Pytesseract")
            return ["eng"]  # Default fallback
        
        # Get available languages from Tesseract
        langs = pytesseract.get_languages(config='')
        
        # Filter out empty strings and sort
        available_langs = [lang for lang in langs if lang.strip()]
        available_langs.sort()
        
        # Ensure English is first if available
        if "eng" in available_langs:
            available_langs.remove("eng")
            available_langs.insert(0, "eng")
        
        logger.debug(f"Available Tesseract languages: {available_langs}")
        return available_langs if available_langs else ["eng"]
        
    except Exception as e:
        logger.warning(f"Could not detect available languages: {e}")
        return ["eng"]  # Default fallback

def is_language_available(language_code):
    """Check if a specific language pack is available."""
    try:
        available = get_available_languages()
        return language_code in available
    except Exception as e:
        logger.warning(f"Error checking language availability: {e}")
        return language_code == "eng"  # Only guarantee English

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