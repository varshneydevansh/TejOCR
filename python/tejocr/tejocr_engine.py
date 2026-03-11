# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Core OCR processing, Tesseract interaction, and image handling."""

import os
import re
import sys
import platform
import subprocess
import time
import uno
import unohelper
import tempfile
import shutil # For shutil.which & tesseract path checking

from tejocr import uno_utils
from tejocr import constants
from tejocr import ocr_runtime
from tejocr import locale_setup # Added for i18n

try:
    _ = locale_setup.get_translator().gettext  # i18n
except Exception:
    def _(text):
        return text

# Initialize logger for this module
logger = uno_utils.get_logger("TejOCR.Engine")

_MODE_ALIAS_RE = re.compile(r"^([a-z0-9_]+)\s+(.+)$")


def _clean_mode_description(description):
    cleaned = str(description or "").strip()
    if not cleaned:
        return cleaned

    match = _MODE_ALIAS_RE.match(cleaned)
    if not match:
        return cleaned

    alias, remainder = match.groups()
    if "_" in alias or alias in {"auto", "default"}:
        return remainder.strip()
    return cleaned


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
    try:
        from tejocr import tejocr_pdf
        return tejocr_pdf.get_runtime_pip_install_command(
            ["pillow"]
        )
    except Exception:
        return f'"{sys.executable}" -m pip install pillow'


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
    """Check whether the direct CLI OCR runtime is ready for use."""
    session = create_ocr_session(ctx=ctx, frame=parent_frame, show_gui_errors=False)
    if session and session.ready:
        runtime_message = session.version or session.path_message or _("Tesseract ready")
        if not _has_module("pytesseract"):
            logger.info(
                "pytesseract is not installed in this LibreOffice runtime; continuing because direct CLI OCR is available."
            )
            runtime_message = "{message} ({note})".format(
                message=runtime_message,
                note=_("direct CLI OCR active; pytesseract not required"),
            )
        logger.debug("Tesseract ready check passed. %s", runtime_message)
        return True, runtime_message

    configured_path = ""
    try:
        if ctx:
            configured_path = (uno_utils.get_setting(constants.CFG_KEY_TESSERACT_PATH, "", ctx) or "").strip()
    except Exception:
        configured_path = ""

    title = "Tesseract Not Available"
    if configured_path:
        path_hint = _(
            "Configured path '{path}' is not valid or cannot be executed.\n"
        ).format(path=configured_path)
    else:
        path_hint = _("No Tesseract executable path could be detected.\n")

    error_message = (
        f"{path_hint}\n"
        "TejOCR cannot reach Tesseract from LibreOffice.\n\n"
        f"{_tesseract_install_recommendation()}\n\n"
        "Or set the exact executable path in: Settings -> Tesseract Path.\n\n"
        "Then restart LibreOffice if needed."
    )
    if session and getattr(session, "path_message", ""):
        error_message = "{message}\n\nDetails: {details}".format(
            message=error_message,
            details=session.path_message,
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

# Attempt to import pytesseract and Pillow, but handle if not available initially
PILLOW_AVAILABLE = False

try:
    from PIL import Image, ImageOps, ImageFilter, ImageDraw
    PILLOW_AVAILABLE = True
except ImportError:
    logger.warning("Pillow (PIL) library not found. Advanced image preprocessing will be disabled.")

class OCRSession(object):
    """Cache Tesseract and OCR runtime state for a run."""

    def __init__(self, tesseract_path, version="", available_languages=None, oem_support=None, executor_mode=None):
        self.tesseract_path = tesseract_path
        self.version = version or ""
        self.available_languages = list(available_languages or [])
        self.oem_support = dict(oem_support or {})
        self.executor_mode = ocr_runtime.coerce_executor_mode(
            executor_mode,
            constants.DEFAULT_OCR_EXECUTOR,
        )
        self.tessdata_prefix = _detect_tessdata_prefix(tesseract_path)
        self.ready = bool(tesseract_path)
        self.path_message = ""


def _detect_tessdata_prefix(tesseract_path):
    """Best-effort tessdata discovery based on the executable path."""
    if not tesseract_path:
        return os.environ.get("TESSDATA_PREFIX") or ""
    if os.environ.get("TESSDATA_PREFIX"):
        return os.environ.get("TESSDATA_PREFIX") or ""
    try:
        tess_dir = os.path.dirname(os.path.abspath(tesseract_path))
        candidates = [
            os.path.abspath(os.path.join(tess_dir, "..", "share", "tessdata")),
            os.path.abspath(os.path.join(tess_dir, "..", "..", "share", "tessdata")),
        ]
        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        return ""
    return ""


def _tesseract_env(session=None):
    env = os.environ.copy()
    prefix = ""
    if session is not None:
        prefix = getattr(session, "tessdata_prefix", "") or ""
    if prefix and not env.get("TESSDATA_PREFIX"):
        env["TESSDATA_PREFIX"] = prefix
    return env


def _run_tesseract_subprocess(command, session=None, timeout=120):
    """Execute a Tesseract command with a stable environment."""
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
        env=_tesseract_env(session),
    )


def _split_help_mode_line(raw_line):
    line = str(raw_line or "").strip()
    if not line or "|" not in line:
        return None, None
    left, right = line.split("|", 1)
    mode = left.strip()
    if not mode.isdigit():
        return None, None
    description = right.strip()
    return mode, description


def _extract_mode_descriptions(command):
    try:
        result = _run_tesseract_subprocess(command, timeout=8)
    except Exception:
        return {}
    output = "\n".join([result.stdout or "", result.stderr or ""]).splitlines()
    descriptions = {}
    pending_mode = None
    for raw_line in output:
        mode, description = _split_help_mode_line(raw_line)
        if mode:
            descriptions[mode] = description
            pending_mode = mode
            continue
        if pending_mode and raw_line.startswith(" "):
            descriptions[pending_mode] = "{current} {extra}".format(
                current=descriptions[pending_mode],
                extra=str(raw_line).strip(),
            ).strip()
        else:
            pending_mode = None
    return descriptions


def _build_oem_probe_image():
    if not PILLOW_AVAILABLE:
        return None
    try:
        probe_path = _get_temp_image_path(suffix=".png")
        image = Image.new("RGB", (220, 80), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((18, 16, 74, 64), outline="black", width=4)
        draw.line((106, 16, 136, 64), fill="black", width=4)
        draw.line((136, 16, 106, 64), fill="black", width=4)
        image.save(probe_path, "PNG")
        return probe_path
    except Exception:
        return None


def _probe_legacy_oem_support(session, language_code=None):
    """Probe whether legacy OEM modes can execute with the current runtime."""
    support = {"0": True, "1": True, "2": True, "3": True}
    if session is None or not session.tesseract_path:
        return support
    probe_image = _build_oem_probe_image()
    if not probe_image:
        return support

    probe_lang = language_code or constants.DEFAULT_OCR_LANGUAGE
    try:
        for mode in ("0", "2"):
            command = [
                session.tesseract_path,
                probe_image,
                "stdout",
                "-l",
                probe_lang,
                "--oem",
                mode,
                "--psm",
                "10",
            ]
            result = _run_tesseract_subprocess(command, session=session, timeout=12)
            output = "{stdout}\n{stderr}".format(stdout=result.stdout or "", stderr=result.stderr or "").lower()
            if result.returncode != 0 and any(
                token in output
                for token in (
                    "legacy engine requested, but components are not present",
                    "failed loading language",
                    "error opening data file",
                    "read_params_file",
                )
            ):
                support[mode] = False
    except Exception:
        pass
    finally:
        try:
            os.remove(probe_image)
        except Exception:
            pass

    return support


def create_ocr_session(ctx=None, frame=None, show_gui_errors=False, executor_mode=None):
    """Create a run-scoped OCR session with cached runtime state."""
    configured_path = ""
    if ctx:
        try:
            configured_path = uno_utils.get_setting(
                constants.CFG_KEY_TESSERACT_PATH,
                constants.DEFAULT_TESSERACT_PATH,
                ctx,
            )
        except Exception:
            configured_path = ""

    is_ready, path_message = check_tesseract_path(
        configured_path,
        ctx=ctx,
        parent_frame=frame,
        show_gui_errors=show_gui_errors,
    )
    if not is_ready:
        session = OCRSession(None, executor_mode=executor_mode)
        session.path_message = path_message
        session.ready = False
        return session

    tesseract_path = uno_utils.find_tesseract_executable(configured_path)
    version = ""
    if tesseract_path:
        try:
            version_result = _run_tesseract_subprocess([tesseract_path, "--version"], timeout=10)
            version = (version_result.stdout or "").strip().splitlines()[0] if version_result.returncode == 0 else ""
        except Exception:
            version = ""

    session = OCRSession(tesseract_path, version=version, executor_mode=executor_mode)
    session.path_message = path_message or version
    session.available_languages = get_available_languages(ctx=ctx, session=session)
    session.oem_support = get_supported_oem_modes(ctx=ctx, session=session)
    return session


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
    """Extract text from the selected image through the unified OCR path."""
    result = perform_ocr(
        ctx,
        frame,
        "selected",
        None,
        {
            "lang": lang,
            "psm": psm if psm is not None else constants.DEFAULT_PSM_MODE,
            "oem": oem if oem is not None else constants.DEFAULT_OEM_MODE,
            "grayscale": grayscale,
            "binarize": binarize,
            "scale": scale,
            "invert": invert,
            "improve_image": improve_image,
            "preset": constants.OCR_PRESET_CUSTOM,
        },
    )
    if result.get("success"):
        return (result.get("text") or "").strip()
    return None

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
    """Extract text from an image file through the unified OCR path."""
    result = perform_ocr(
        ctx,
        None,
        "file",
        image_path,
        {
            "lang": lang,
            "psm": psm if psm is not None else constants.DEFAULT_PSM_MODE,
            "oem": oem if oem is not None else constants.DEFAULT_OEM_MODE,
            "grayscale": grayscale,
            "binarize": binarize,
            "scale": scale,
            "invert": invert,
            "improve_image": improve_image,
            "preset": constants.OCR_PRESET_CUSTOM,
        },
    )
    if result.get("success"):
        return (result.get("text") or "").strip()
    return None

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
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        
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

def _build_default_plan_options():
    return {
        "lang": constants.DEFAULT_OCR_LANGUAGE,
        "psm": constants.DEFAULT_PSM_MODE,
        "oem": constants.DEFAULT_OEM_MODE,
        "scale": 1.0,
        "grayscale": False,
        "binarize": False,
        "invert": False,
        "improve_image": False,
        "preset": constants.DEFAULT_OCR_PRESET,
        "show_preview": False,
        "merge_batch_results": False,
    }


def _build_tesseract_command(tesseract_path, image_path, lang, oem_mode, psm_mode):
    return [
        tesseract_path,
        image_path,
        "stdout",
        "-l",
        lang,
        "--oem",
        str(oem_mode).strip(),
        "--psm",
        str(psm_mode).strip(),
    ]


def _is_missing_language_error(error_text):
    lowered = str(error_text or "").lower()
    return any(
        token in lowered
        for token in (
            "failed loading language",
            "error opening data file",
            "tessdata",
            "language data",
        )
    )


def _prepare_image_for_attempt(source_image_path, attempt_plan):
    preprocess_start = time.perf_counter()
    prepared_path = _preprocess_image(
        source_image_path,
        improve_quality=bool(attempt_plan.improve_image),
        grayscale=bool(attempt_plan.grayscale),
        binarize_method="otsu" if bool(attempt_plan.binarize) else None,
        scale_factor=float(attempt_plan.scale),
        invert=bool(attempt_plan.invert),
    )
    preprocess_seconds = time.perf_counter() - preprocess_start
    return prepared_path or source_image_path, preprocess_seconds


def _run_cli_ocr_attempt(session, image_path, attempt_plan):
    start = time.perf_counter()
    completed = _run_tesseract_subprocess(
        _build_tesseract_command(
            session.tesseract_path,
            image_path,
            attempt_plan.lang,
            attempt_plan.oem,
            attempt_plan.psm,
        ),
        session=session,
        timeout=120,
    )
    used_language = attempt_plan.lang
    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()

    if (
        completed.returncode != 0
        and attempt_plan.lang != constants.DEFAULT_OCR_LANGUAGE
        and constants.DEFAULT_OCR_LANGUAGE in (session.available_languages or [])
        and _is_missing_language_error(stderr_text)
    ):
        completed = _run_tesseract_subprocess(
            _build_tesseract_command(
                session.tesseract_path,
                image_path,
                constants.DEFAULT_OCR_LANGUAGE,
                attempt_plan.oem,
                attempt_plan.psm,
            ),
            session=session,
            timeout=120,
        )
        used_language = constants.DEFAULT_OCR_LANGUAGE
        stdout_text = (completed.stdout or "").strip()
        stderr_text = (completed.stderr or "").strip()

    return {
        "text": stdout_text,
        "error": stderr_text,
        "returncode": completed.returncode,
        "used_language": used_language,
        "seconds": time.perf_counter() - start,
    }


def _resolve_executor_mode(ocr_options=None, session=None, ctx=None):
    requested_mode = ""
    if isinstance(ocr_options, dict):
        requested_mode = ocr_options.get("executor_mode", "")
    if not requested_mode and session is not None:
        requested_mode = getattr(session, "executor_mode", "")
    if not requested_mode and ctx is not None:
        try:
            requested_mode = uno_utils.get_setting(
                constants.CFG_KEY_HIDDEN_OCR_EXECUTOR,
                constants.DEFAULT_OCR_EXECUTOR,
                ctx,
            )
        except Exception:
            requested_mode = constants.DEFAULT_OCR_EXECUTOR
    return ocr_runtime.coerce_executor_mode(
        requested_mode,
        constants.DEFAULT_OCR_EXECUTOR,
    )


def _supported_oem_values_for_executor(session, primary_oem, allow_fallback=False):
    candidates = [str(primary_oem or constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE]
    if allow_fallback:
        candidates = _fallback_oem_values(candidates[0])

    if not session or not getattr(session, "oem_support", None):
        return candidates

    supported = [mode for mode in candidates if session.oem_support.get(str(mode), True)]
    return supported or candidates


def _build_legacy_attempt_plans(execution_plan, session):
    effective_options = dict(execution_plan.effective_options or {})
    normalized_lang = effective_options.get("lang", constants.DEFAULT_OCR_LANGUAGE)
    language_chain = _dedupe_sequence(
        [normalized_lang] + _build_language_fallback_chain(normalized_lang)
    )
    psm_values = _fallback_psm_values(effective_options.get("psm", constants.DEFAULT_PSM_MODE))
    oem_values = _supported_oem_values_for_executor(
        session,
        effective_options.get("oem", constants.DEFAULT_OEM_MODE),
        allow_fallback=True,
    )

    attempts = []
    for lang in language_chain:
        for psm_value in psm_values:
            for oem_value in oem_values:
                attempts.append(
                    ocr_runtime.OcrAttemptPlan(
                        label="legacy-{index}".format(index=len(attempts) + 1),
                        lang=lang,
                        psm=psm_value,
                        oem=oem_value,
                        scale=float(effective_options.get("scale", 1.0)),
                        improve_image=bool(effective_options.get("improve_image", False)),
                        grayscale=bool(effective_options.get("grayscale", False)),
                        binarize=bool(effective_options.get("binarize", False)),
                        invert=bool(effective_options.get("invert", False)),
                        reason="legacy fallback chain",
                    )
                )

    enhanced_scale = max(float(effective_options.get("scale", 1.0)), 1.5)
    for lang in language_chain:
        for psm_value in psm_values:
            for oem_value in oem_values:
                attempts.append(
                    ocr_runtime.OcrAttemptPlan(
                        label="legacy-enhanced-{index}".format(index=len(attempts) + 1),
                        lang=lang,
                        psm=psm_value,
                        oem=oem_value,
                        scale=enhanced_scale,
                        improve_image=True,
                        grayscale=True,
                        binarize=True,
                        invert=bool(effective_options.get("invert", False)),
                        reason="legacy enhanced fallback chain",
                        enhanced=True,
                    )
                )

    return attempts


def perform_ocr(ctx, frame, source_type, image_path_or_selection_options, ocr_options, status_callback=None, session=None):
    """Main function to perform OCR.
    source_type: 'file' or 'selected'
    image_path_or_selection_options: file path if source_type is 'file', or dict of selection info (not used yet)
    ocr_options: dict containing lang, psm, oem, grayscale, binarize
    status_callback: function to update a status label (e.g., lambda msg: status_label.setText(msg))
    Returns a dict: {"success": True/False, "text": "recognized_text" or None, "message": "status_message"}
    """
    if status_callback:
        status_callback(_("Initializing OCR...")) # i18n
    logger.info(f"Performing OCR: source='{source_type}', options={ocr_options}")

    total_start = time.perf_counter()
    dependency_start = time.perf_counter()
    requested_executor_mode = _resolve_executor_mode(ocr_options=ocr_options, session=session, ctx=ctx)
    active_session = session or create_ocr_session(
        ctx=ctx,
        frame=frame,
        show_gui_errors=False,
        executor_mode=requested_executor_mode,
    )
    dependency_seconds = time.perf_counter() - dependency_start
    if active_session is None or not active_session.ready:
        message = getattr(active_session, "path_message", "") or _("Tesseract not found or not working. Please check settings.")
        logger.warning("Tesseract session creation failed during perform_ocr: %s", message)
        return {"success": False, "text": None, "message": message}
    active_session.executor_mode = requested_executor_mode

    execution_plan = ocr_runtime.resolve_execution_plan(
        ocr_options or {},
        available_languages=active_session.available_languages,
        default_options=_build_default_plan_options(),
        platform_name=platform.system(),
    )
    effective_oem = execution_plan.effective_options.get("oem", constants.DEFAULT_OEM_MODE)
    if (
        requested_executor_mode == constants.OCR_EXECUTOR_MODERN
        and active_session.oem_support
        and not active_session.oem_support.get(str(effective_oem), True)
    ):
        oem_message = _(
            "Selected OEM {oem} is not supported by the current Tesseract traineddata/runtime."
        ).format(oem=effective_oem)
        logger.warning(oem_message)
        return {"success": False, "text": None, "message": oem_message}

    run_stats = ocr_runtime.OcrRunStats(
        source_type=str(source_type or ""),
        source_label="selected image" if source_type == "selected" else os.path.basename(str(image_path_or_selection_options or "")),
        requested_options=execution_plan.requested_options,
        effective_options=execution_plan.effective_options,
        pdf_dpi=execution_plan.pdf_dpi,
        executor_mode=requested_executor_mode,
        dependency_probe_seconds=dependency_seconds,
        warning=execution_plan.language.warning,
        install_hint=execution_plan.language.install_hint,
    )
    temp_image_to_ocr = None
    original_image_path_for_cleanup = None
    final_image_for_ocr = None

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

        best_text = ""
        best_used_language = execution_plan.effective_options.get("lang", constants.DEFAULT_OCR_LANGUAGE)
        last_error = ""
        attempt_plans = list(execution_plan.attempts)
        if requested_executor_mode == constants.OCR_EXECUTOR_LEGACY:
            attempt_plans = _build_legacy_attempt_plans(execution_plan, active_session)
            logger.info(
                "Legacy OCR executor enabled; fallback chain contains %s attempts.",
                len(attempt_plans),
            )

        for attempt_index, attempt_plan in enumerate(attempt_plans, start=1):
            if status_callback:
                status_callback(
                    _("OCR attempt {index}/{count}: PSM {psm}, OEM {oem}").format(
                        index=attempt_index,
                        count=len(attempt_plans),
                        psm=attempt_plan.psm,
                        oem=attempt_plan.oem,
                    )
                )

            attempt_image = temp_image_to_ocr
            preprocess_seconds = 0.0
            try:
                attempt_image, preprocess_seconds = _prepare_image_for_attempt(temp_image_to_ocr, attempt_plan)
                run_stats.preprocessing_seconds += preprocess_seconds
                final_image_for_ocr = attempt_image
                attempt_result = _run_cli_ocr_attempt(active_session, attempt_image, attempt_plan)
                attempt_text = (attempt_result.get("text") or "").strip()
                attempt_error = attempt_result.get("error") or ""
                attempt_seconds = float(attempt_result.get("seconds", 0.0))
                used_language = attempt_result.get("used_language") or attempt_plan.lang
                low_signal = ocr_runtime.is_low_signal_text(
                    attempt_text,
                    min_chars=execution_plan.low_signal_char_count,
                ) if attempt_text else True

                run_stats.attempts.append(
                    ocr_runtime.OcrAttemptStats(
                        label=attempt_plan.label,
                        lang=used_language,
                        psm=attempt_plan.psm,
                        oem=attempt_plan.oem,
                        scale=float(attempt_plan.scale),
                        improve_image=bool(attempt_plan.improve_image),
                        grayscale=bool(attempt_plan.grayscale),
                        binarize=bool(attempt_plan.binarize),
                        invert=bool(attempt_plan.invert),
                        seconds=attempt_seconds,
                        output_length=len(attempt_text),
                        success=bool(attempt_text),
                        low_signal=bool(low_signal),
                        reason=attempt_plan.reason,
                        error=attempt_error,
                        enhanced=bool(attempt_plan.enhanced),
                    )
                )

                if attempt_text and len(attempt_text) > len(best_text):
                    best_text = attempt_text
                    best_used_language = used_language

                if attempt_text and not low_signal:
                    best_text = attempt_text
                    best_used_language = used_language
                    if requested_executor_mode == constants.OCR_EXECUTOR_MODERN:
                        break

                if attempt_error:
                    last_error = attempt_error

                if (
                    requested_executor_mode == constants.OCR_EXECUTOR_MODERN
                    and attempt_index >= len(attempt_plans)
                    and execution_plan.language.install_hint
                    and not attempt_text
                    and not last_error
                ):
                    last_error = execution_plan.language.install_hint
            finally:
                if (
                    attempt_image
                    and attempt_image != temp_image_to_ocr
                    and attempt_image.startswith(tempfile.gettempdir())
                    and os.path.exists(attempt_image)
                ):
                    try:
                        os.remove(attempt_image)
                    except Exception:
                        pass

        if status_callback:
            status_callback(_("OCR Complete.")) # i18n

        run_stats.used_language = best_used_language
        run_stats.total_seconds = time.perf_counter() - total_start
        diagnostics_text = ocr_runtime.build_run_diagnostics_text(run_stats)
        if diagnostics_text:
            logger.info("OCR diagnostics: %s", diagnostics_text)

        if not best_text:
            if last_error:
                msg = _("OCR completed with warnings: {details}").format(
                    details=str(last_error)[:200] + "..."
                )
            else:
                msg = _(
                    "OCR completed, but no text was recognized. "
                    "Try clearer source images, higher resolution, and 'Accuracy' preset."
                )
            return {
                "success": True,
                "text": "",
                "message": msg,
                "stats": run_stats.to_dict(),
                "diagnostics": diagnostics_text,
            }

        logger.info(
            f"Tesseract subprocess OCR successful. Output length: {len(best_text)}"
        )
        return {
            "success": True,
            "text": best_text,
            "message": _("OCR successful."),
            "stats": run_stats.to_dict(),
            "diagnostics": diagnostics_text,
        }

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
        if (
            final_image_for_ocr
            and final_image_for_ocr != temp_image_to_ocr
            and final_image_for_ocr.startswith(tempfile.gettempdir())
            and os.path.exists(final_image_for_ocr)
        ):
            logger.debug(f"Cleaning up processed temp image: {final_image_for_ocr}")
            try:
                os.remove(final_image_for_ocr)
            except OSError as e_rem_final:
                logger.warning(f"Could not remove processed temp image '{final_image_for_ocr}': {e_rem_final}")
        if original_image_path_for_cleanup and os.path.exists(original_image_path_for_cleanup) and \
           original_image_path_for_cleanup != final_image_for_ocr and \
           original_image_path_for_cleanup.startswith(tempfile.gettempdir()):
            logger.debug(f"Cleaning up original temp image (final pass): {original_image_path_for_cleanup}")
            try: os.remove(original_image_path_for_cleanup)
            except OSError as e_rem_orig_final:
                 logger.warning(f"Could not remove original temp image (final pass) '{original_image_path_for_cleanup}': {e_rem_orig_final}")
                 pass 

def get_runtime_psm_modes(ctx=None, session=None):
    """Return current PSM labels, preferring the local Tesseract help output."""
    runtime_session = session
    if runtime_session is None:
        runtime_session = OCRSession(_find_tesseract_executable(ctx=ctx))
    if not runtime_session or not runtime_session.tesseract_path:
        return dict(constants.TESSERACT_PSM_MODES)

    descriptions = _extract_mode_descriptions([runtime_session.tesseract_path, "--help-psm"])
    if not descriptions:
        return dict(constants.TESSERACT_PSM_MODES)

    runtime_map = {}
    for mode, fallback_text in constants.TESSERACT_PSM_MODES.items():
        description = descriptions.get(mode)
        if description:
            description = _clean_mode_description(description)
            if mode == "0":
                if "diagnostic mode" not in description.lower():
                    description = "{description} Diagnostic mode; no OCR text output.".format(
                        description=description.rstrip(".")
                    )
            elif mode == "2" and "diagnostic mode" not in description.lower():
                suffix = "Diagnostic mode; no OCR text output."
                if "not implemented" not in description.lower():
                    suffix = "Diagnostic mode; not implemented for text output."
                description = "{description} {suffix}".format(
                    description=description.rstrip("."),
                    suffix=suffix,
                )
            runtime_map[mode] = "{mode}: {description}".format(mode=mode, description=description)
        else:
            runtime_map[mode] = fallback_text
    return runtime_map


def get_supported_oem_modes(ctx=None, session=None):
    """Return a support map for OEM modes under the current runtime."""
    runtime_session = session
    if runtime_session is None:
        runtime_session = OCRSession(_find_tesseract_executable(ctx=ctx))
    if not runtime_session or not runtime_session.tesseract_path:
        return {mode: True for mode in constants.TESSERACT_OEM_MODES}

    descriptions = _extract_mode_descriptions([runtime_session.tesseract_path, "--help-oem"])
    support = {}
    for mode in constants.TESSERACT_OEM_MODES:
        support[mode] = mode in descriptions if descriptions else True

    legacy_probe = _probe_legacy_oem_support(runtime_session)
    for mode, is_supported in legacy_probe.items():
        if mode in support and not is_supported:
            support[mode] = False
    return support


def get_runtime_oem_modes(ctx=None, session=None):
    """Return OEM labels, annotating modes that cannot be honored."""
    runtime_session = session
    if runtime_session is None:
        runtime_session = OCRSession(_find_tesseract_executable(ctx=ctx))
    descriptions = {}
    if runtime_session and runtime_session.tesseract_path:
        descriptions = _extract_mode_descriptions([runtime_session.tesseract_path, "--help-oem"])
    support = get_supported_oem_modes(ctx=ctx, session=runtime_session)

    runtime_map = {}
    for mode, fallback_text in constants.TESSERACT_OEM_MODES.items():
        description = descriptions.get(mode)
        if description:
            description = _clean_mode_description(description)
            label = "{mode}: {description}".format(mode=mode, description=description)
        else:
            label = fallback_text
        if not support.get(mode, True):
            label = "{label} (unsupported by current traineddata/runtime)".format(label=label)
        runtime_map[mode] = label
    return runtime_map


def get_available_languages(ctx=None, session=None):
    """Return installed Tesseract languages using the CLI directly."""
    runtime_session = session
    if runtime_session is None:
        runtime_session = OCRSession(_find_tesseract_executable(ctx=ctx))
    if not runtime_session or not runtime_session.tesseract_path:
        return [constants.DEFAULT_OCR_LANGUAGE]

    if runtime_session.available_languages:
        return list(runtime_session.available_languages)

    try:
        result = _run_tesseract_subprocess(
            [runtime_session.tesseract_path, "--list-langs"],
            session=runtime_session,
            timeout=15,
        )
        output = result.stdout or result.stderr or ""
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines and lines[0].lower().startswith("list of available languages"):
            lines = lines[1:]
        available_langs = sorted(dedupe for dedupe in lines if dedupe)
        if "eng" in available_langs:
            available_langs.remove("eng")
            available_langs.insert(0, "eng")
        runtime_session.available_languages = available_langs or [constants.DEFAULT_OCR_LANGUAGE]
        return list(runtime_session.available_languages)
    except Exception as e:
        logger.warning(f"Could not detect available languages: {e}")
        return [constants.DEFAULT_OCR_LANGUAGE]


def is_language_available(language_code, ctx=None, session=None):
    """Check if a specific language pack is available."""
    try:
        available = get_available_languages(ctx=ctx, session=session)
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
