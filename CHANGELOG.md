<!-- This Source Code Form is subject to the terms of the Mozilla Public -->
<!-- License, v. 2.0. If a copy of the MPL was not distributed with this -->
<!-- file, You can obtain one at https://mozilla.org/MPL/2.0/. -->
<!-- © 2025 Devansh (Author of TejOCR) -->

# Changelog

All notable changes to the "TejOCR" extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Initial project scaffolding: directory structure, core Python files (`tejocr_service.py`, `tejocr_dialogs.py`, `tejocr_engine.py`, `uno_utils.py`, `constants.py`), configuration files (`manifest.xml`, `Addons.xcu`, `description.xml`), and documentation (`LICENSE`, `README.md`, `CHANGELOG.md`).
- Implemented OCR options dialog (`tejocr_options_dialog.xdl` and `OptionsDialogHandler`) with language, PSM, OEM selection, preprocessing options, and persistence of last-used settings.
- Integrated `tejocr_engine.py` with `tejocr_dialogs.py` to perform OCR based on dialog choices, including image extraction from selection and file, preprocessing, and Tesseract calls.
- Basic Tesseract path detection and version checking.
- Added `TASKS.md` for detailed feature tracking.

### Added
- Initial project structure for TejOCR.
- Basic `tejocr_service.py` with XDispatchProvider and XServiceInfo implementations.
- `Addons.xcu` for menu and toolbar integration in LibreOffice Writer.
- `description.xml` and `META-INF/manifest.xml` for extension metadata.
- `LICENSE` file (MPL-2.0).
- `README.md` with project overview, features, and setup instructions.
- Placeholder `l10n` directory structure for internationalization.

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

## [0.1.0] - YYYY-MM-DD (To be released)
- First official pre-release/alpha version (details to be filled in upon release). 