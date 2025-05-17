<!-- This Source Code Form is subject to the terms of the Mozilla Public -->
<!-- License, v. 2.0. If a copy of the MPL was not distributed with this -->
<!-- file, You can obtain one at https://mozilla.org/MPL/2.0/. -->
<!-- © 2025 Devansh (Author of TejOCR) -->

# Changelog

All notable changes to the TejOCR extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support for internationalization (i18n) with initial language support for English, Spanish, French, German, Chinese (Simplified), and Hindi
- Build script (`build.py`) for packaging the extension as `.oxt`
- Icon generation utility (`generate_icons.py`)
- Translation template generator (`generate_translations.py`)
- Test script for verifying Tesseract OCR functionality (`test_ocr_engine.py`)

### Changed
- Improved XML file handling for better compatibility with LibreOffice

### Fixed
- XML parsing errors related to encoding and format

## [0.1.0] - 2025-01-15 (Initial Release)

### Added
- Core functionality for OCR from selected images in Writer documents
- OCR from external image files
- Multiple output options: insert at cursor, in text box, replace image, or clipboard
- Settings dialog for configuring Tesseract path and default options
- Support for various image formats (PNG, JPG, TIFF, BMP)
- Text preprocessing options (grayscale, binarize)
- Integration with LibreOffice Writer via menu items and toolbar button

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A 