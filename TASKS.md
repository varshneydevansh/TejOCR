# TejOCR Development Tasks

This file tracks the progress of features and components for the TejOCR LibreOffice Writer extension.

## Core Functionality

-   [x] **Project Setup & Structure**: Basic directory structure created (`python/tejocr`, `dialogs`, `icons`, `l10n`, `META-INF`).
-   [x] **OCR Engine Core (`tejocr_engine.py`)**:
    -   [x] Pytesseract integration.
    -   [x] Pillow integration for preprocessing (grayscale, binarize placeholder).
    -   [x] Image export from selection (`_get_image_from_selection`).
    -   [x] Image export from XGraphic (`_export_graphic_to_file`).
    -   [x] Tesseract path checking (`check_tesseract_path`).
    -   [x] Main `perform_ocr()` function.
    -   [x] Temporary file management.
-   [x] **OCR Options Dialog (`tejocr_dialogs.py`, `tejocr_options_dialog.xdl`)**:
    -   [x] XDL dialog definition created.
    -   [x] `OptionsDialogHandler` implemented.
    -   [x] Population of language, PSM, OEM dropdowns.
    -   [x] Loading/saving last used options to configuration.
    -   [x] "Refresh Languages" button.
    -   [x] Integration with `tejocr_engine.py` to run OCR.
    -   [x] Status label updates during OCR.
-   [x] **OCR Output Handling (`tejocr_output.py`)**:
    -   [x] Implement "Insert at Cursor".
    -   [x] Implement "Insert into New Text Box".
    -   [x] Implement "Replace Image with Text".
    -   [x] Implement "Copy to Clipboard".
-   [x] **Service Integration (`tejocr_service.py`)**:
    -   [x] `XDispatchProvider` and `XServiceInfo` implementation.
    -   [x] Dispatch URLs for "OCR Selected", "OCR from File", "Settings".
    -   [x] Context-sensitive toolbar action.
    -   [x] Calling `tejocr_dialogs.show_ocr_options_dialog`.
    -   [x] Connect to `tejocr_output.py` for handling OCR results.
-   [x] **Settings Dialog (`tejocr_dialogs.py`, `tejocr_settings_dialog.xdl`)**:
    -   [x] XDL dialog definition for settings created (`dialogs/tejocr_settings_dialog.xdl`).
    -   [x] Full implementation of `SettingsDialogHandler` in `python/tejocr/tejocr_dialogs.py`.
        -   [x] Load/save Tesseract path.
        -   [x] Implement Tesseract path browsing.
        -   [x] Implement Tesseract path testing.
        -   [x] Load/save other default settings (default language, preprocessing options).
-   [x] **UNO Utilities (`uno_utils.py`)**:
    -   [x] Helpers for service access, UI messages.
    -   [x] Selection checking (`is_graphic_object_selected`).
    -   [x] Configuration getters/setters.
    -   [x] File/path utilities (`get_user_temp_dir`, `create_temp_file`, `find_tesseract_executable`).
    -   [x] `get_graphic_from_selected_shape` (refined and used in `tejocr_engine.py`).
-   [x] **Constants (`constants.py`)**:
    -   [x] Configuration keys, default values, Tesseract modes, output modes, image formats, logging constants.

## Packaging & Configuration

-   [x] **`META-INF/manifest.xml`**: Created, lists initial files.
-   [x] **`Addons.xcu`**: Created, defines menus and toolbar button for Writer.
-   [x] **`description.xml`**: Created with extension metadata and localization placeholders.
-   [x] **Build Process**: 
    -   [x] Created `build.py` - Python script to package as `.oxt` with proper encoding.
    -   [x] Created `run_libreoffice_with_extension.py` - Script to test the extension with LibreOffice.

## Internationalization (i18n)

-   [x] **Directory Structure**: `l10n/` with language subfolders created.
-   [x] **`gettext` Implementation**:
    -   [x] Created `locale_setup.py` for integration with gettext.
    -   [x] Wrapped user-facing strings with `_()`.
-   [x] **`.po` files**:
    -   [x] Created `generate_translations.py` for `.pot` template generation and `.po` files.
    -   [x] Setup structure for English, Spanish, French, German, Chinese (Simplified), Hindi.

## Documentation & Licensing

-   [x] **`LICENSE`**: MPL-2.0 text added.
-   [x] **`README.md`**: Comprehensive README with setup, usage, and development instructions.
-   [x] **`CHANGELOG.md`**: Created and updated with version history.
-   [x] **`TASKS.md`**: This file, updated to reflect current status.

## Icons & Visuals

-   [x] **`icons/` directory**: Created.
-   [x] **Icon Generation**: 
    -   [x] Created `generate_icons.py` utility for creating properly sized icons.
    -   [x] Support for 16x16, 26x26, and high-contrast versions.
-   [x] **Visual Identity**: Orange/saffron/yellow for icons, standard dialogs. (Decision made).

## Logging

-   [x] **File-based Logging**: Implemented robust logging using Python's `logging` module.

## Testing

-   [x] **Test Script (`test_ocr_engine.py`)**: 
    -   [x] Created script for testing Tesseract OCR functionality.
    -   [x] Implemented checks for Tesseract installation and language data.
    -   [x] Added image preprocessing and OCR tests.

## Edge Cases & Refinements

-   [x] **XML Encoding Handling**: 
    -   [x] Added code to clean XML files and remove BOM markers.
    -   [x] Fixed XML parsing errors related to encoding.
-   [x] **Error Handling**: 
    -   [x] Improved error reporting for Tesseract issues.
    -   [x] Added fallbacks for missing dependencies.
-   [x] **Usability Improvements**:
    -   [x] Added testing utilities.
    -   [x] Improved documentation.

## Additional Tools

-   [x] **`generate_icons.py`**: Utility for creating properly sized icons from a source image.
-   [x] **`generate_translations.py`**: Utility for generating translation templates and `.po` files.
-   [x] **`test_ocr_engine.py`**: Script for testing Tesseract OCR functionality.
-   [x] **`run_libreoffice_with_extension.py`**: Script for testing the extension with LibreOffice. 