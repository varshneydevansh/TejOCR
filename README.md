<!-- This Source Code Form is subject to the terms of the Mozilla Public -->
<!-- License, v. 2.0. If a copy of the MPL was not distributed with this -->
<!-- file, You can obtain one at https://mozilla.org/MPL/2.0/. -->
<!-- © 2025 Devansh (Author of TejOCR) -->

<div align="center">
  <img src="icons/main_logo.png" alt="TejOCR Logo" width="360" style="margin-bottom: -20px;"/>
</div>

# TejOCR – OCR Extension for LibreOffice Writer

**TejOCR** is a modern, lightweight OCR (Optical Character Recognition) extension for LibreOffice Writer. It allows you to extract text from images embedded in your documents or imported from the file system.

> ✨ "Tej" means light in Sanskrit – and just like light reveals, TejOCR reveals text hidden in images.

## ✨ Features

- **OCR from Selected Images**: Extract text from images embedded in your Writer document
- **OCR from File**: Process images from your file system
- **Multiple Output Options**:
  - Insert text at cursor position
  - Create a new text box with recognized text
  - Replace the selected image with the recognized text
  - Copy the recognized text to clipboard
- **Configurable Settings**:
  - Tesseract path configuration
  - Default language selection
  - Preprocessing options (grayscale, binarize)
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Internationalization**: Support for English, Spanish, French, German, Chinese (Simplified), and Hindi

## 📋 Requirements

- LibreOffice 7.3 or later
- Tesseract OCR (4.x or 5.x) installed on your system
- Python 3.x (as available in LibreOffice)

### Installing Tesseract OCR

TejOCR requires Tesseract OCR to be installed on your system:

**Windows:**
1. Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer and note the installation path
3. Add Tesseract to your PATH or specify the path in TejOCR settings

**macOS:**
```bash
# Using Homebrew
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install tesseract-ocr
```

## 📥 Installation

1. Download the latest `.oxt` package from the [Releases](https://github.com/varshneydevansh/TejOCR/releases) page
2. In LibreOffice, go to **Tools → Extension Manager**
3. Click **Add** and select the downloaded `.oxt` file
4. Restart LibreOffice

## 🚀 Usage

### OCR Selected Image

1. Insert or select an image in your LibreOffice Writer document
2. Go to **Tools → TejOCR → OCR Selected Image** (or use the toolbar button)
3. Choose your OCR options (language, output mode, etc.)
4. Click **Run OCR**
5. The recognized text will be processed according to your chosen output mode

### OCR from File

1. Go to **Tools → TejOCR → OCR Image from File**
2. Select an image file from your computer
3. Choose your OCR options
4. Click **Run OCR**
5. The recognized text will be processed according to your chosen output mode

### Settings

Configure TejOCR by going to **Tools → TejOCR → Settings**:
- Set the path to Tesseract OCR executable
- Test if Tesseract is correctly installed
- Set default language and preprocessing options

## 🛠️ Development

### Project Structure

```
TejOCR/
├── META-INF/
│   └── manifest.xml
├── Addons.xcu
├── description.xml
├── python/
│   └── tejocr/
│       ├── __init__.py
│       ├── tejocr_service.py     # Main entry (XDispatchProvider)
│       ├── tejocr_dialogs.py     # Dialog lifecycle logic & event handlers
│       ├── tejocr_engine.py      # OCR processing, Tesseract interaction
│       ├── tejocr_output.py      # Text insertion, replacement, clipboard logic
│       ├── uno_utils.py          # Reusable UNO helpers
│       ├── constants.py          # Configuration constants
│       └── locale_setup.py       # Internationalization support
├── dialogs/
│   ├── tejocr_options_dialog.xdl
│   └── tejocr_settings_dialog.xdl
├── icons/
│   ├── tejocr_16.png
│   ├── tejocr_26.png
│   └── tejocr_26_hc.png
├── l10n/                       # Localization files
│   ├── en/
│   ├── es/
│   └── ...
├── build.py                    # Build script for packaging
├── generate_icons.py           # Icon generation utility
├── generate_translations.py    # Translation template generator
├── LICENSE
├── README.md
└── CHANGELOG.md
```

### Building from Source

1. Clone this repository:
   ```bash
   git clone https://github.com/varshneydevansh/TejOCR.git
   cd TejOCR
   ```

2. Generate icons (requires Pillow):
   ```bash
   pip install Pillow
   python generate_icons.py /path/to/source/image.png
   ```

3. Generate translation templates (requires GNU gettext):
   ```bash
   python generate_translations.py
   ```

4. Build the `.oxt` extension package:
   ```bash
   python build.py
   ```

The extension package will be created as `TejOCR-{version}.oxt` in the project root directory.

### Development Tools

- **build.py**: Packages the extension as an `.oxt` file, ensuring proper encoding and file structure
- **generate_icons.py**: Creates properly sized icons from a source image
- **generate_translations.py**: Extracts translatable strings and generates `.pot`/`.po` files

## 📜 License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0).
See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Improve documentation
- Submit pull requests

Please ensure your changes adhere to the project's code style and include tests where appropriate.

## 🙏 Acknowledgements

- The incredible LibreOffice project and community
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for the powerful OCR engine
- [pytesseract](https://github.com/madmaze/pytesseract) for the Python wrapper
- All contributors and users of this extension

---

## 🧠 About the Name

**Tej** (तेज) in Sanskrit and other Indian languages means *light*, *effulgence*, *sharpness*, or *brilliance*. **TejOCR** aims to bring clarity and insight to your documents by making the text within images accessible and editable.

---

## 📧 Contact

*   Maintainer: **Devansh Varshney**
*   GitHub: [varshneydevansh](https://github.com/varshneydevansh)
*   Twitter: [@varshneydevansh](https://x.com/varshneydevansh)