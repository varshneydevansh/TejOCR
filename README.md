<!-- This Source Code Form is subject to the terms of the Mozilla Public -->
<!-- License, v. 2.0. If a copy of the MPL was not distributed with this -->
<!-- file, You can obtain one at https://mozilla.org/MPL/2.0/. -->
<!-- © 2025 Devansh (Author of TejOCR) -->

<div align="center">
  <img src="icons/main_logo.png" alt="TejOCR Logo" width="360" style="margin-bottom: -20px;"/>
</div>

# TejOCR – Modern OCR Extension for LibreOffice

**TejOCR** is a modern, lightweight, and user-friendly OCR (Optical Character Recognition) extension for LibreOffice Writer. Powered by [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), it allows you to extract editable text from images embedded in your documents or imported externally — all from within LibreOffice.

> ✨ "Tej" means light in Sanskrit – and just like light reveals, TejOCR reveals text hidden in images.

---

## 🧠 Features

- 🖼️ OCR any image (embedded or external) inside LibreOffice Writer
- 🤖 Powered by Tesseract with LSTM-based ML models
- 🌈 Clean, modern UI (dialogs use standard LibreOffice look & feel, icons provide branding)
- 🌍 Multilingual OCR support
- 📦 Cross-platform (macOS, Linux, Windows)
- 🧩 Packaged as a `.oxt` LibreOffice extension
- 🔐 Open Source (MPL-2.0)

---

## 🚀 Getting Started

### 📥 Installation

1.  Download the latest `TejOCR.oxt` release from the [Releases page](https://github.com/varshneydevansh/TejOCR/releases) (link to be updated once releases exist).
2.  Open **LibreOffice Writer**.
3.  Go to `Tools` → `Extension Manager…` → `Add…` and select the downloaded `TejOCR.oxt` file.
4.  Restart LibreOffice to complete the installation.

### 🔍 Usage

1.  **To OCR a selected image:**
    *   Select an image within your LibreOffice Writer document.
    *   Go to `Tools` → `TejOCR` → `OCR Selected Image` or click the **TejOCR** toolbar icon.
2.  **To OCR an image from a file:**
    *   Go to `Tools` → `TejOCR` → `OCR Image from File...` (or click the toolbar icon if no image is selected).
3.  In the **TejOCR Options** dialog that appears:
    *   Confirm/select the OCR language.
    *   Choose your desired output mode (Insert at Cursor, New Text Box, Replace Image, Copy to Clipboard).
    *   Adjust advanced options (PSM, OEM, preprocessing) if needed.
    *   Click "Run OCR".
4.  Extracted text will be processed according to your selected output mode.

### ⚙️ Settings

Access `Tools` → `TejOCR` → `Settings...` to:

*   Configure the path to your Tesseract OCR installation (if not auto-detected).
*   Set a default OCR language.
*   (Optional) Set default preprocessing options.

---

## 🔧 Requirements

*   **LibreOffice:** Version 7.3 or newer.
*   **Python:** Version 3.8 or newer (usually bundled with LibreOffice 7.3+).
*   **Tesseract OCR:** Version 4.x or 5.x. **This must be installed separately by the user.**
    *   Ensure Tesseract is in your system's PATH or configure the path in TejOCR's settings.
    *   Language data files (e.g., `eng.traineddata`) for Tesseract must be installed for the languages you intend to use.

#### Tesseract Installation Examples:

```bash
# macOS (using Homebrew)
brew install tesseract
brew install tesseract-lang # For all language packs, or install specific ones

# Ubuntu/Debian
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-eng # For English, replace 'eng' with other language codes as needed (e.g., tesseract-ocr-hin for Hindi)

# Windows
# Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
# During installation, ensure you select the desired language packs.
```

*   **pytesseract Python library:** TejOCR uses this to communicate with Tesseract. If packaging issues arise with LO's internal Python, users might need to install it manually into LO's Python environment or ensure their system Python (if used by LO) has it. (More specific guidance will be provided if this becomes a common issue).
*   **Pillow Python library:** Used for image preprocessing. Similar to pytesseract, this might require manual installation in specific scenarios.

---

## 📸 Screenshots (Placeholder)

*(Screenshots will be added once the UI is developed)*

| TejOCR Options Dialog                     | TejOCR Settings Dialog                    |
| :---------------------------------------- | :-------------------------------------- |
| `![TejOCR Options](./screenshots/options_dialog.png)` (To be added) | `![TejOCR Settings](./screenshots/settings_dialog.png)` (To be added) |

---

## 📜 License

This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**.
See the [LICENSE](./LICENSE) file for full details.

---

## 🙌 Acknowledgments

*   The [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) project and its contributors.
*   The LibreOffice community and developers of the UNO API.
*   The `pytesseract` and `Pillow` library developers.
*   Icons and logo concept by Devansh Varshney.

---

## ❤️ Contributing

Contributions, bug reports, and feature requests are welcome! Please feel free to open an issue or submit a pull request on the [GitHub repository](https://github.com/varshneydevansh/TejOCR).

```bash
# Clone for development
git clone https://github.com/varshneydevansh/TejOCR.git
cd TejOCR
# Further development instructions to be added (e.g., how to build/package .oxt)
```

---

## 🧠 About the Name

**Tej** (तेज) in Sanskrit and other Indian languages means *light*, *effulgence*, *sharpness*, or *brilliance*. **TejOCR** aims to bring clarity and insight to your documents by making the text within images accessible and editable.

---

## 📧 Contact

*   Maintainer: **Devansh Varshney**
*   GitHub: [varshneydevansh](https://github.com/varshneydevansh)
*   Twitter: [@varshneydevansh](https://x.com/varshneydevansh)