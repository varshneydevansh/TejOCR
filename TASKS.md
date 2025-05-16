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
-   [x] **OCR Output Handling (`tejocr_output.py`)**: **(Partially Complete)**
    -   [ ] Implement "Insert at Cursor".
    -   [ ] Implement "Insert into New Text Box".
    -   [ ] Implement "Replace Image with Text".
    -   [ ] Implement "Copy to Clipboard".
-   [x] **Service Integration (`tejocr_service.py`)**:
    -   [x] `XDispatchProvider` and `XServiceInfo` implementation.
    -   [x] Dispatch URLs for "OCR Selected", "OCR from File", "Settings".
    -   [x] Context-sensitive toolbar action.
    -   [x] Calling `tejocr_dialogs.show_ocr_options_dialog`.
    -   [x] Connect to `tejocr_output.py` for handling OCR results.
-   [ ] **Settings Dialog (`tejocr_dialogs.py`, `tejocr_settings_dialog.xdl`)**: **(Largely Complete)**
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

-   [x] **`META-INF/manifest.xml`**: Created, lists initial files. *(Needs ongoing updates as files are added/finalized)*
-   [x] **`Addons.xcu`**: Created, defines menus and toolbar button for Writer.
-   [x] **`description.xml`**: Created with extension metadata and localization placeholders.
-   [ ] **Build Process**: Define steps to package as `.oxt`. **(Not Started)**

## Internationalization (i18n)

-   [x] **Directory Structure**: `l10n/` with language subfolders created.
-   [ ] **`gettext` Implementation**:
    -   [ ] Setup `gettext` for string translation in Python code. **(Not Started)**
    -   [ ] Wrap all user-facing strings. **(Not Started)**
-   [ ] **`.po` files**:
    -   [ ] Generate `.pot` template. **(Not Started)**
    -   [ ] Create/Update `.po` files for English, Spanish, French, German, Chinese (Simplified), Hindi with translatable strings. **(Not Started - translations pending)**

## Documentation & Licensing

-   [x] **`LICENSE`**: MPL-2.0 text added.
-   [x] **`README.md`**: Created from template. *(Enhancements pending)*
-   [x] **`CHANGELOG.md`**: Created. *(Updates pending)*
-   [x] **`TASKS.md`**: This file.

## Icons & Visuals

-   [x] **`icons/` directory**: Created.
-   [x] **Icon Usage (PNG)**:
    -   [x] `icons/tejocr_icon_16.png` is referenced in `Addons.xcu` for the toolbar.
    -   [x] `icons/tejocr_icon_26.png` is referenced in `description.xml` for the extension icon.
-   [ ] **Optional Icon Creation (Manual Tasks)**:
    -   [ ] Create `tejocr_icon_16.svg` (optional, if desired). *(Manual Task)*
    -   [ ] Create `tejocr_icon_26.svg` (optional, if desired). *(Manual Task)*
    -   [x] Create `tejocr_icon_26_hc.png` (high-contrast version for `description.xml`, if desired). *(Manual Task - User Provided)*
-   [x] **Visual Identity**: Orange/saffron/yellow for icons, standard dialogs. (Decision made).

## Logging

-   [x] **File-based Logging**: Implement robust logging using Python's `logging` module, replacing/supplementing `print` statements. **(Complete)**

## Testing

-   [ ] **Unit Tests (`tests/test_tejocr_engine.py`)**: Write tests for `tejocr_engine.py`. **(Not Started)**

## Edge Cases & Refinements (Ongoing)

-   [ ] Review and handle unsupported image formats more explicitly.
-   [ ] Improve error reporting for Tesseract language file issues.
-   [ ] Consider linked vs. embedded image handling in selections.
-   [ ] Ensure graceful handling of file permission issues (temp files, log files).
-   [ ] Review UI feedback for clarity and completeness across all operations. 