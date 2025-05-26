# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Constants used throughout the TejOCR extension."""

# --- Version Information ---
EXTENSION_VERSION = "0.1.6"
EXTENSION_NAME = "TejOCR"
EXTENSION_FULL_NAME = f"{EXTENSION_NAME} v{EXTENSION_VERSION}"

# --- Configuration Keys (for UNO ConfigurationProvider) ---
# Path: org.libreoffice.Office.Addons/TejOCR.Configuration/Settings
CFG_NODE_SETTINGS = "Settings"
CFG_KEY_TESSERACT_PATH = "TesseractPath"
CFG_KEY_DEFAULT_LANG = "DefaultOcrLanguage"
CFG_KEY_DEFAULT_GRAYSCALE = "DefaultPreprocessingGrayscale"
CFG_KEY_DEFAULT_BINARIZE = "DefaultPreprocessingBinarize"
CFG_KEY_IMPROVE_IMAGE_DEFAULT = "DefaultImproveImageQuality" # For image enhancement options
CFG_KEY_LAST_SELECTED_LANG = "LastSelectedOcrLanguage" # For OCR Options Dialog
CFG_KEY_LAST_OUTPUT_MODE = "LastOutputMode" # For OCR Options Dialog

# --- Default Values ---
DEFAULT_OCR_LANGUAGE = "eng"  # Default to English
DEFAULT_PREPROC_GRAYSCALE = False
DEFAULT_PREPROC_BINARIZE = False
DEFAULT_IMPROVE_IMAGE = False # Default to no image enhancement
DEFAULT_TESSERACT_PATH = "" # Empty, to trigger auto-detection or user input

# --- Tesseract PSM (Page Segmentation Modes) --- 
# (Value: Description for UI)
TESSERACT_PSM_MODES = {
    "0": "0: Orientation and script detection (OSD) only.",
    "1": "1: Automatic page segmentation with OSD.",
    "2": "2: Automatic page segmentation, but no OSD, or OCR.",
    "3": "3: Fully automatic page segmentation, but no OSD. (Default)",
    "4": "4: Assume a single column of text of variable sizes.",
    "5": "5: Assume a single uniform block of vertically aligned text.",
    "6": "6: Assume a single uniform block of text.",
    "7": "7: Treat the image as a single text line.",
    "8": "8: Treat the image as a single word.",
    "9": "9: Treat the image as a single word in a circle.",
    "10": "10: Treat the image as a single character.",
    "11": "11: Sparse text. Find as much text as possible in no particular order.",
    "12": "12: Sparse text with OSD.",
    "13": "13: Raw line. Treat the image as a single text line, bypassing hacks that are Tesseract-specific."
}
DEFAULT_PSM_MODE = "3"

# --- Tesseract OEM (OCR Engine Modes) --- 
# (Value: Description for UI)
TESSERACT_OEM_MODES = {
    "0": "0: Legacy engine only.",
    "1": "1: Neural nets LSTM engine only.",
    "2": "2: Legacy + LSTM engines.",
    "3": "3: Default, based on what is available."
}
DEFAULT_OEM_MODE = "3"

# --- Output Modes (for OCR Options Dialog) ---
# These can be simple strings, as their primary use is for programmatic logic
# and to be stored in config. UI labels will come from i18n strings.
OUTPUT_MODE_CURSOR = "at_cursor"
OUTPUT_MODE_TEXTBOX = "new_textbox"
OUTPUT_MODE_REPLACE = "replace_image"
OUTPUT_MODE_CLIPBOARD = "to_clipboard"
DEFAULT_OUTPUT_MODE = OUTPUT_MODE_CURSOR

# --- Image Formats ---
# Used for file dialog filters. Should be a semicolon-separated string of wildcards.
IMAGE_FILE_DIALOG_FILTER = "*.png;*.jpg;*.jpeg;*.tiff;*.tif;*.bmp;*.gif;*.webp"

# List of wildcards for internal checks if needed, derived from the above string.
IMAGE_WILDCARDS = [f.strip() for f in IMAGE_FILE_DIALOG_FILTER.split(';') if f.strip()]

# MIME types corresponding to the above wildcards, for clipboard or other type checks.
# This mapping might need to be more robust or comprehensive based on specific needs.
IMAGE_MIMETYPES = {
    "*.png": "image/png",
    "*.jpg": "image/jpeg",
    "*.jpeg": "image/jpeg",
    "*.tiff": "image/tiff",
    "*.tif": "image/tiff",
    "*.bmp": "image/bmp",
    "*.gif": "image/gif",
    "*.webp": "image/webp"
}

# Fallback/general list of supported MIME types if direct mapping isn't used.
SUPPORTED_IMAGE_MIMETYPES_LIST = list(set(IMAGE_MIMETYPES.values()))

# Format for temporarily saving/converting images for Tesseract if needed.
TEMP_IMAGE_FORMAT_FOR_TESSERACT = "PNG" # PNG is lossless and widely supported.

# --- Deprecated / To be reviewed ---
# SUPPORTED_IMAGE_FORMATS_DIALOG_FILTER = "*.png;*.jpg;*.jpeg;*.tiff;*.tif;*.bmp;*.webp" # Replaced by IMAGE_FILE_DIALOG_FILTER
# SUPPORTED_IMAGE_MIMETYPES = ["image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"] # Replaced by SUPPORTED_IMAGE_MIMETYPES_LIST
# TEMP_IMAGE_FORMAT = "PNG" # Replaced by TEMP_IMAGE_FORMAT_FOR_TESSERACT


# --- Logging ---
LOG_FILE_NAME = "tejocr.log"
# Consider making log level configurable in settings in the future

# --- UI Related ---
DIALOG_MODAL_DEPENDENT = 1 # For com.sun.star.awt.MessageBoxType & Dialog behavior 

# Current Log Level (can be overridden by user config if implemented)
# Possible values: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
CURRENT_LOG_LEVEL = "DEBUG"

# --- Development Flags ---
# When True, bypasses certain checks for placeholder UI testing
# When False, enables real OCR functionality
DEVELOPMENT_MODE_STRICT_PLACEHOLDERS = False

# Default file for logging, relative to user's temp directory subfolder
LOG_FILENAME = "tejocr.log"

# --- DEBUG CONSTANT FOR TESTING UPDATES ---
DEBUG_CONSTANT_VERSION = "v2_constants_test" 