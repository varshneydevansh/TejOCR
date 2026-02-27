# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Core OCR processing, Tesseract interaction, and image handling."""

import os
import sys
import platform
import uno
import unohelper
import tempfile
import shutil # For shutil.which & tesseract path checking

from tejocr import uno_utils
from tejocr import constants
from tejocr import locale_setup # Added for i18n

try:
    _ = locale_setup.get_translator().gettext  # i18n
except Exception:
    def _(text):
        return text

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Engine")


def _platform_name():
    """Return a normalized platform label for platform-specific messages."""
    name = (platform.system() or "").lower()
    if name == "darwin":
        return "mac"
    if name == "linux":
        return "linux"
    if name == "windows":
        return "windows"
    return name or "unknown"


def _has_module(module_name):
    """Check module import availability without importing hard dependencies."""
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _lo_python_dependency_command():
    """Return a practical install command for the active LibreOffice Python interpreter."""
    return f'"{sys.executable}" -m pip install numpy pytesseract pillow'


def _tesseract_install_recommendation():
    """Return platform-safe install guidance for Tesseract."""
    platform_name = _platform_name()
    if platform_name == "windows":
        return (
            "Install Tesseract:\n"
            "• https://github.com/UB-Mannheim/tesseract/wiki\n"
            "• or from a package manager (winget/choco) in an elevated console\n"
            "• Select additional languages during installation"
        )
    if platform_name == "linux":
        return (
            "Install Tesseract:\n"
            "• sudo apt install tesseract-ocr tesseract-ocr-eng\n"
            "• Extra languages: sudo apt install tesseract-ocr-all\n"
            "• Or use your distro package manager equivalent"
        )
    return (
        "Install Tesseract:\n"
        "• brew install tesseract\n"
        "• Extra languages: brew install tesseract-lang\n"
    )

# Global variables for pytesseract state
PYTESSERACT_AVAILABLE = False
pytesseract = None
_LAST_PYTESSERACT_INIT_ERROR = None

def _initialize_pytesseract(ctx=None):
    """Initialize pytesseract with robust error handling and path detection."""
    global PYTESSERACT_AVAILABLE, pytesseract, _LAST_PYTESSERACT_INIT_ERROR
    _LAST_PYTESSERACT_INIT_ERROR = None
    
    if PYTESSERACT_AVAILABLE and pytesseract:
        return True
    
    try:
        import pytesseract as pt
        pytesseract = pt
        
        # Verify tesseract executable is accessible
        tesseract_path = _find_tesseract_executable(ctx=ctx)
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
                _LAST_PYTESSERACT_INIT_ERROR = (
                    f"Tesseract executable initialization failed: {e}"
                )
                return False
        else:
            logger.warning("Pytesseract imported but tesseract executable not found")
            _LAST_PYTESSERACT_INIT_ERROR = "Configured or detected Tesseract executable was not found."
            return False
            
    except ImportError as e:
        logger.error(f"Pytesseract import failed: {e}")
        _LAST_PYTESSERACT_INIT_ERROR = f"ImportError while loading pytesseract: {e}"
        return False
    except Exception as e:
        logger.error(f"Unexpected error initializing pytesseract: {e}", exc_info=True)
        _LAST_PYTESSERACT_INIT_ERROR = f"Unexpected initialization error: {e}"
        return False

def _find_tesseract_executable(ctx=None):
    """Find tesseract executable with multiple fallback strategies."""
    configured_path = ""
    if ctx:
        try:
            configured_path = uno_utils.get_setting(
                constants.CFG_KEY_TESSERACT_PATH,
                "",
                ctx,
            )
        except Exception as e_path:
            logger.debug(f"Could not read configured Tesseract path for detection: {e_path}")
            configured_path = ""

    # 1) If pytesseract has a previously configured command, validate and use it.
    if hasattr(pytesseract, 'pytesseract') and hasattr(pytesseract.pytesseract, 'tesseract_cmd'):
        current_cmd = pytesseract.pytesseract.tesseract_cmd
        if current_cmd and os.path.isfile(current_cmd):
            return current_cmd
    
    # Strategy 2: Delegate to UNO utility for robust discovery.
    discovered = uno_utils.find_tesseract_executable(configured_path)
    if discovered:
        return discovered
    
    logger.warning("Tesseract executable not found in any known location")
    return None

def is_tesseract_ready(ctx=None, show_gui_errors=True, parent_frame=None):
    """Check if Tesseract and pytesseract are ready for OCR operations."""
    if not _initialize_pytesseract(ctx):
        configured_path = ""
        try:
            if ctx:
                configured_path = (uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx) or "").strip()
        except Exception:
            configured_path = ""

        try:
            pytesseract_available = _has_module("pytesseract")
            tesseract_path = _find_tesseract_executable(ctx=ctx)
        except Exception:
            pytesseract_available = False
            tesseract_path = None

        if not pytesseract_available:
            title = "Missing pytesseract"
            error_message = (
                "TejOCR cannot access pytesseract in LibreOffice's Python environment.\n\n"
                "Run this command from a terminal:\n"
                f"{_lo_python_dependency_command()}\n\n"
                "Then restart LibreOffice."
            )
        elif not tesseract_path:
            title = "Tesseract Not Available"
            if configured_path:
                path_hint = _(
                    "Configured path '{path}' is not valid or cannot be executed.\n"
                ).format(path=configured_path)
            else:
                path_hint = _("No Tesseract executable path could be detected.\n")
            error_message = (
                f"{path_hint}\n"
                "TejOCR can load Python dependencies, but it cannot reach Tesseract from LibreOffice.\n\n"
                f"{_tesseract_install_recommendation()}\n\n"
                "Or set the exact executable path in: Settings → Tesseract Path.\n\n"
                "Then restart LibreOffice if needed."
            )
        else:
            title = "OCR Engine Not Ready"
            error_message = (
                "OCR dependencies are partly available, but initialization failed.\n\n"
                "Details:\n"
                f"{_LAST_PYTESSERACT_INIT_ERROR or _('No internal details available.')}\n\n"
                "Try:\n"
                f"1) {_lo_python_dependency_command()}\n"
                f"2) {_tesseract_install_recommendation()}\n"
                f"3) Confirm the path shown in Settings{' (Current: ' + configured_path + ')' if configured_path else ''}.\n\n"
                "Then restart LibreOffice."
            )

        if show_gui_errors:
            uno_utils.show_message_box(
                title,
                error_message,
                "errorbox",
                parent_frame=parent_frame,
                ctx=ctx
            )

        return False, error_message
    
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

def _export_graphic_to_file(xgraphic, file_path, mime_type="image/png", ctx=None):
    """Exports an XGraphic object to a file.
    Returns True on success, False on failure.
    """
    if not xgraphic:
        return False
    try:
        provider = uno_utils.create_instance("com.sun.star.graphic.GraphicProvider", ctx)
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
        uno_utils.show_message_box(_("Image Export Error"), _("Failed to export image for OCR: {e}").format(e=e), "errorbox", ctx=ctx) # i18n
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
    if _export_graphic_to_file(xgraphic, temp_image_file, ctx=ctx):
        return temp_image_file
    else:
        if os.path.exists(temp_image_file): os.remove(temp_image_file) # Clean up failed export
        return None

def _preprocess_image(
    image_path,
    improve_quality=False,
    grayscale=False,
    binarize_method=None,
    scale_factor=1.0,
    invert=False,
):
    """Applies preprocessing steps to the image using Pillow.
    improve_quality: Applies a general set of enhancements if True.
    grayscale: Specifically convert to grayscale (can be part of improve_quality).
    binarize_method: None or 'otsu' (placeholder for more advanced binarization).
    invert: True to invert color values after other processing steps.
    scale_factor: Optional scale multiplier to improve small-font text.
    Returns path to the processed image (might be same as input or a new temp file).
    """
    if not PILLOW_AVAILABLE:
        if improve_quality or grayscale or binarize_method:
            logger.info("Pillow not available, skipping all image preprocessing.")
        return image_path # Cannot preprocess

    try:
        logger.debug(
            f"Preprocessing image: '{image_path}'. Improve: {improve_quality}, "
            f"Grayscale: {grayscale}, Binarize: {binarize_method}, Scale: {scale_factor}"
        )
        img = Image.open(image_path)
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

        if invert:
            if processed_img.mode != 'L':
                processed_img = ImageOps.grayscale(processed_img)
                image_was_modified = True
            processed_img = ImageOps.invert(processed_img)
            image_was_modified = True

        # Optional upscale to improve OCR on low-resolution captures.
        try:
            scale_float = float(scale_factor)
        except (TypeError, ValueError):
            scale_float = 1.0
        if scale_float > 1.05:
            new_width = int(processed_img.width * scale_float)
            new_height = int(processed_img.height * scale_float)
            if new_width > 0 and new_height > 0:
                resample_method = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS
                processed_img = processed_img.resize((new_width, new_height), resample_method)
                image_was_modified = True
                logger.debug(f"Scaled image to {new_width}x{new_height} (factor={scale_float})")

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

def extract_text_from_selected_image(
    ctx,
    frame,
    lang="eng",
    improve_image=False,
    psm=None,
    oem=None,
    grayscale=False,
    binarize=False,
    scale=1.0,
    invert=False,
):
    """Extract text from currently selected image in LibreOffice."""
    if not _initialize_pytesseract(ctx):
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

        lang_code = _normalize_lang_codes(lang)
        psm_mode = str(psm if psm is not None else constants.DEFAULT_PSM_MODE).strip() or constants.DEFAULT_PSM_MODE
        oem_mode = str(oem if oem is not None else constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
        should_grayscale = _coerce_bool(grayscale, False)
        should_binarize = _coerce_bool(binarize, False)
        should_invert = _coerce_bool(invert, False)
        should_scale = _coerce_float(scale, 1.0)

        if (improve_image or should_grayscale or should_binarize) and PILLOW_AVAILABLE:
            logger.info(f"Preprocessing selected image (originally: {exported_temp_image_path}) as improvement was requested.")
            processed_image_path = _preprocess_image(
                exported_temp_image_path,
                improve_quality=bool(improve_image),
                grayscale=should_grayscale,
                binarize_method='otsu' if should_binarize else None,
                scale_factor=should_scale,
                invert=should_invert,
            )
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

        language_chain = _build_language_fallback_chain(lang_code)
        if not language_chain:
            language_chain = [constants.DEFAULT_OCR_LANGUAGE]

        logger.info(
            f"Performing OCR on selected image (using '{final_image_path_for_ocr}') "
            f"with language chain: {language_chain}"
        )
        custom_config = f"--oem {oem_mode} --psm {psm_mode}"
        text = ""
        last_error = None
        for attempt_lang in language_chain:
            try:
                text = pytesseract.image_to_string(
                    final_image_path_for_ocr,
                    lang=attempt_lang,
                    config=custom_config,
                )
                text = text.strip() if text is not None else ""
                if text:
                    logger.info(
                        f"OCR completed. Extracted {len(text)} characters using lang='{attempt_lang}'."
                    )
                    break
            except pytesseract.TesseractError as tess_err:
                last_error = tess_err
                logger.warning(
                    f"Tesseract selected-image extraction failed for lang='{attempt_lang}': {tess_err}"
                )
                text = ""

        if not text and last_error:
            logger.warning(f"OCR selected-image extraction completed with no text. Last error: {last_error}")

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

def extract_text_from_image_file(
    ctx,
    image_path,
    lang="eng",
    improve_image=False,
    psm=None,
    oem=None,
    grayscale=False,
    binarize=False,
    scale=1.0,
    invert=False,
):
    """Extract text from an image file."""
    if not _initialize_pytesseract(ctx):
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
        lang_code = _normalize_lang_codes(lang)
        psm_mode = str(psm if psm is not None else constants.DEFAULT_PSM_MODE).strip() or constants.DEFAULT_PSM_MODE
        oem_mode = str(oem if oem is not None else constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
        should_grayscale = _coerce_bool(grayscale, False)
        should_binarize = _coerce_bool(binarize, False)
        should_invert = _coerce_bool(invert, False)
        should_scale = _coerce_float(scale, 1.0)

        if (improve_image or should_grayscale or should_binarize) and PILLOW_AVAILABLE:
            logger.info(f"Preprocessing image file ('{image_path}') as improvement was requested.")
            # _preprocess_image will create a new temp file if it modifies the image
            processed_image_path = _preprocess_image(
                image_path,
                improve_quality=bool(improve_image),
                grayscale=should_grayscale,
                binarize_method='otsu' if should_binarize else None,
                scale_factor=should_scale,
                invert=should_invert,
            )
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

        language_chain = _build_language_fallback_chain(lang_code)
        if not language_chain:
            language_chain = [constants.DEFAULT_OCR_LANGUAGE]

        logger.info(
            f"Performing OCR on image file (using '{final_image_path_for_ocr}') "
            f"with language chain: {language_chain}"
        )
        custom_config = f"--oem {oem_mode} --psm {psm_mode}"
        text = ""
        last_error = None
        for attempt_lang in language_chain:
            try:
                text = pytesseract.image_to_string(
                    final_image_path_for_ocr,
                    lang=attempt_lang,
                    config=custom_config
                )
                text = text.strip() if text is not None else ""
                if text:
                    logger.info(
                        f"OCR completed. Extracted {len(text)} characters from "
                        f"{os.path.basename(final_image_path_for_ocr)} using lang='{attempt_lang}'."
                    )
                    break
            except pytesseract.TesseractError as tess_err:
                last_error = tess_err
                logger.warning(
                    f"Tesseract file extraction failed for lang='{attempt_lang}': {tess_err}"
                )
                text = ""

        if not text and last_error:
            logger.warning(f"OCR file extraction completed with no text. Last error: {last_error}")

        logger.info(
            f"OCR completed. Extracted {len(text)} characters from {os.path.basename(final_image_path_for_ocr)}"
        )
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
    candidate_path = (tesseract_path or "").strip()
    if not candidate_path:
        candidate_path = uno_utils.find_tesseract_executable()
        if not candidate_path:
            return False, "No tesseract executable found. Configure path or install Tesseract."
    
    if not os.path.isfile(candidate_path):
        # If a plain command was passed, try one final PATH lookup.
        candidate_lookup = shutil.which(candidate_path)
        if candidate_lookup:
            candidate_path = candidate_lookup
        elif os.path.sep not in candidate_path and candidate_path in ("tesseract", "tesseract.exe"):
            return False, "Tesseract not found in PATH"
        elif not candidate_path:
            return False, f"File not found: {tesseract_path}"
    
    try:
        # Test the tesseract executable
        import subprocess
        result = subprocess.run([candidate_path, '--version'], 
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


def _split_lang_codes(lang_value):
    """Split normalized language strings to an ordered list of tokens."""
    if not lang_value:
        return [constants.DEFAULT_OCR_LANGUAGE]

    if isinstance(lang_value, str):
        lang_value = lang_value.lower()
    lang_value = str(lang_value).replace(",", "+")
    split_codes = [code.strip() for code in lang_value.split("+") if code.strip()]
    return split_codes or [constants.DEFAULT_OCR_LANGUAGE]


def _build_language_fallback_chain(raw_language):
    """Build practical language fallbacks for OCR robustness."""
    requested = _split_lang_codes(raw_language)
    requested = list(dict.fromkeys([code.lower() for code in requested if code]))

    available_languages = []
    try:
        available_languages = get_available_languages()
    except Exception:
        available_languages = [constants.DEFAULT_OCR_LANGUAGE]

    available_set = {str(code).lower() for code in available_languages if str(code).strip()}
    if not available_set:
        available_set = {constants.DEFAULT_OCR_LANGUAGE}

    valid_codes = [code for code in requested if code in available_set]
    if not valid_codes:
        valid_codes = [constants.DEFAULT_OCR_LANGUAGE] if constants.DEFAULT_OCR_LANGUAGE in available_set else [requested[0]]

    fallback_chain = []
    for i in range(len(valid_codes), 0, -1):
        candidate = "+".join(valid_codes[:i])
        if candidate:
            fallback_chain.append(candidate)

    if (
        constants.DEFAULT_OCR_LANGUAGE in available_set
        and constants.DEFAULT_OCR_LANGUAGE != valid_codes[0]
    ):
        fallback_chain.append(constants.DEFAULT_OCR_LANGUAGE)

    return _dedupe_sequence(fallback_chain)


def _coerce_bool(value, default=False):
    """Normalize boolean-like values coming from settings storage."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on", "enabled", "enable")
    return default


def _coerce_float(value, default=1.0):
    """Normalize float-like values from storage."""
    try:
        parsed = float(value)
        if parsed <= 0:
            return default
        return parsed
    except Exception:
        return default


def _build_tesseract_config(oem_mode, psm_mode):
    """Construct a compact pytesseract config string."""
    return f"--oem {str(oem_mode).strip()} --psm {str(psm_mode).strip()}"


def _dedupe_sequence(values):
    """Return an ordered list with duplicate blank/empty values removed."""
    seen = set()
    output = []
    for value in values:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        output.append(candidate)
    return output


def _fallback_psm_values(primary_psm):
    """Build practical fallback PSM modes when text extraction is weak."""
    return _dedupe_sequence(
        [
            primary_psm,
            constants.DEFAULT_PSM_MODE,
            "11",
            "6",
        ]
    )


def _fallback_oem_values(primary_oem):
    """Build practical fallback OEM modes when text extraction is weak."""
    return _dedupe_sequence(
        [
            primary_oem,
            constants.DEFAULT_OEM_MODE,
        ]
    )


def _normalize_lang_codes(lang_value):
    """Normalize user-supplied language string for pytesseract."""
    normalized = _split_lang_codes(lang_value)
    normalized = _dedupe_sequence(normalized)
    return "+".join(normalized)

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

    if status_callback:
        status_callback(_("Initializing OCR...")) # i18n
    logger.info(f"Performing OCR: source='{source_type}', options={ocr_options}")

    ocr_options = ocr_options or {}
    lang_code = _normalize_lang_codes(ocr_options.get("lang", constants.DEFAULT_OCR_LANGUAGE))
    psm_mode = str(ocr_options.get("psm", constants.DEFAULT_PSM_MODE)).strip() or constants.DEFAULT_PSM_MODE
    oem_mode = str(ocr_options.get("oem", constants.DEFAULT_OEM_MODE)).strip() or constants.DEFAULT_OEM_MODE
    grayscale = _coerce_bool(ocr_options.get("grayscale"), False)
    binarize = _coerce_bool(ocr_options.get("binarize"), False)
    scale_factor = _coerce_float(ocr_options.get("scale"), 1.0)
    improve_image = _coerce_bool(ocr_options.get("improve_image"), False)
    invert = _coerce_bool(ocr_options.get("invert"), False)

    tess_path_cfg = uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, constants.DEFAULT_TESSERACT_PATH, ctx)
    is_ready, path_message = check_tesseract_path(tess_path_cfg, ctx, frame)
    if not is_ready:
        logger.warning(f"Tesseract path check failed during perform_ocr: {path_message}")
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
        logger.info(
            f"Preprocessing image '{temp_image_to_ocr}' with options: "
            f"improve_image={improve_image}, grayscale={grayscale}, binarize={binarize}, scale={scale_factor}"
        )
        processed_image_path = _preprocess_image(
            temp_image_to_ocr,
            improve_quality=improve_image,
            grayscale=grayscale,
            binarize_method='otsu' if binarize else None,
            scale_factor=scale_factor,
            invert=invert,
        )
        
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

        language_chain = _build_language_fallback_chain(lang_code)
        if not language_chain:
            language_chain = [constants.DEFAULT_OCR_LANGUAGE]

        def _build_ocr_attempts(current_oem_mode, current_psm_mode):
            attempts = []
            for attempt_oem in _fallback_oem_values(current_oem_mode):
                for attempt_psm in _fallback_psm_values(current_psm_mode):
                    attempts.append((attempt_oem, attempt_psm))
            return attempts

        ocr_attempts = _build_ocr_attempts(oem_mode, psm_mode)

        logger.info(
            "OCR engine will try %s configuration(s) for extraction. "
            "Primary config: %s",
            len(ocr_attempts),
            _build_tesseract_config(oem_mode, psm_mode),
        )

        def _run_ocr_attempts(image_path, attempt_label, attempts, languages):
            last_text = ""
            last_error = None
            last_language = None

            if status_callback:
                status_callback(
                    _("OCR {attempt_label}: trying {count} configurations...").format(
                        attempt_label=attempt_label,
                        count=len(attempts),
                        
                    )
                )

            for attempt_lang in languages:
                for attempt_index, (attempt_oem, attempt_psm) in enumerate(attempts, start=1):
                    attempt_config = _build_tesseract_config(attempt_oem, attempt_psm)
                    if status_callback:
                        status_callback(
                            _("OCR attempt {index}/{count}: {config}").format(
                                index=attempt_index,
                                count=len(attempts),
                                config=attempt_config,
                            )
                        ) # i18n
                    logger.info(
                        "OCR attempt %s/%s using %s with lang=%s",
                        attempt_index,
                        len(attempts),
                        attempt_config,
                        attempt_lang,
                    )
                    try:
                        last_text = pytesseract.image_to_string(
                            image_path,
                            lang=attempt_lang,
                            config=attempt_config,
                        )
                        last_text = last_text.strip() if last_text is not None else ""
                        logger.info(
                            "Tesseract attempt %s output length: %s (lang=%s)",
                            attempt_index,
                            len(last_text),
                            attempt_lang,
                        )
                        if last_text:
                            logger.info(
                                "Tesseract attempt %s produced non-empty output; stopping attempts.",
                                attempt_index,
                            )
                            last_language = attempt_lang
                            break
                    except pytesseract.TesseractError as attempt_error:
                        last_error = attempt_error
                        logger.warning(
                            "Tesseract attempt %s failed (lang=%s, OEM=%s, PSM=%s): %s",
                            attempt_index,
                            attempt_lang,
                            attempt_oem,
                            attempt_psm,
                            attempt_error,
                        )
                        last_text = ""

                if last_text:
                    break

            return last_text, last_error, last_language

        text, last_error, used_language = _run_ocr_attempts(
            final_image_for_ocr,
            _("Pass"),
            ocr_attempts,
            language_chain,
        )
        if used_language:
            logger.info("OCR language selected for final text: %s", used_language)

        # Automatic quality recovery: try a stronger preprocessing pass when first pass
        # returns empty text. This often improves results on noisy or low-res scans.
        if not text and (
            not improve_image
            or not grayscale
            or not binarize
            or scale_factor < 1.5
        ):
            try:
                if status_callback:
                    status_callback(
                        _("No text found. Trying enhanced preprocessing fallback...")
                    ) # i18n
                enhanced_scale = max(scale_factor, 1.5)
                enhanced_image = _preprocess_image(
                    final_image_for_ocr,
                    improve_quality=True,
                    grayscale=True,
                    binarize_method="otsu",
                    scale_factor=enhanced_scale,
                    invert=invert,
                )
                if enhanced_image and enhanced_image != final_image_for_ocr:
                    if final_image_for_ocr and final_image_for_ocr.startswith(tempfile.gettempdir()):
                        try:
                            os.remove(final_image_for_ocr)
                            logger.debug(f"Removed primary temp image before enhanced pass: {final_image_for_ocr}")
                        except OSError as _err:
                            logger.debug(f"Could not remove primary temp image '{final_image_for_ocr}': {_err}")
                    final_image_for_ocr = enhanced_image
                    ocr_attempts = _build_ocr_attempts(oem_mode, psm_mode)
                    text, retry_error, retry_lang = _run_ocr_attempts(
                        final_image_for_ocr,
                        _("Enhanced pass"),
                        ocr_attempts,
                        language_chain,
                    )
                    if retry_error:
                        last_error = retry_error
            except Exception as enhance_error:
                logger.warning("Enhanced OCR pass failed: %s", enhance_error, exc_info=True)

        if status_callback:
            status_callback(_("OCR Complete.")) # i18n

        if not text:
            if last_error is not None:
                msg = _("OCR completed with warnings: {details}").format(
                    details=str(last_error)[:200] + "..."
                )
            else:
                msg = _(
                    "OCR completed, but no text was recognized. "
                    "Try clearer source images, higher resolution, and 'Accuracy' preset."
                )
            return {"success": True, "text": "", "message": msg} # i18n

        logger.info(
            f"Tesseract image_to_string successful. Output length: {len(text)}"
        )
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
