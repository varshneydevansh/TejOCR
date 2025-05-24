<!-- This Source Code Form is subject to the terms of the Mozilla Public -->
<!-- License, v. 2.0. If a copy of the MPL was not distributed with this -->
<!-- file, You can obtain one at https://mozilla.org/MPL/2.0/. -->
<!-- © 2025 Devansh (Author of TejOCR) -->

<div align="center">
  <img src="icons/main_logo.png" alt="TejOCR Logo" width="360" style="margin-bottom: -20px;"/>
</div>

# TejOCR v0.1.4 - LibreOffice OCR Extension

🎉 **Phase 1 Complete: Core OCR Functionality Stable!** 

TejOCR is a powerful LibreOffice extension that adds Optical Character Recognition (OCR) capabilities to your documents. Extract text from images directly within LibreOffice Writer.

## ✅ What's Working in v0.1.4

**🚀 BOTH OCR WORKFLOWS FULLY FUNCTIONAL:**
- ✅ **OCR from File**: Select image files and extract text
- ✅ **OCR Selected Image**: Extract text from images already in your document
- ✅ **Robust Error Handling**: Multi-strategy fallbacks prevent crashes
- ✅ **Smart Text Insertion**: Automatically inserts extracted text in your document

**🔧 CRITICAL ISSUES RESOLVED:**
- **No More Crashes**: Extension handles all error conditions gracefully
- **Text Insertion Works**: Multiple fallback strategies ensure text gets inserted
- **Image Export Fixed**: Selected images export reliably with GraphicProvider fallbacks
- ✅ **Dependency Detection**: Accurate detection of Tesseract, NumPy, Pytesseract, Pillow

## 🎯 Current Status

**Phase 1 (Stability & Core OCR)**: ✅ **COMPLETE**
- Core crashes eliminated
- OCR engine fully functional
- Dependency detection working
- Safe error handling implemented

**Phase 2 (UI/UX Enhancement)**: 🚧 **Next Priority**
- Real settings dialog (XDL-based)
- OCR options dialog with language selection  
- Output mode selection (cursor/textbox/replace/clipboard)
- Progress indicators and enhanced user experience

## 🚀 Quick Start

### Prerequisites

1. **Tesseract OCR** (Required):
   ```bash
   # macOS
   brew install tesseract
   
   # Ubuntu/Debian
   sudo apt install tesseract-ocr
   
   # Windows
   # Download from: https://github.com/UB-Mannheim/tesseract/wiki
   ```

2. **Python Dependencies** (for LibreOffice's Python):
   
   **Automated Installation** (Recommended):
   ```bash
   python3 install_dependencies.py
   ```
   
   **Manual Installation**:
   ```bash
   # Get LibreOffice's Python path first
   /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract pillow
   ```

### Installation

1. **Download**: Get the latest `TejOCR-0.1.4.oxt` from releases
2. **Install**: LibreOffice → Tools → Extension Manager → Add → Select the .oxt file
3. **Restart**: Close and restart LibreOffice completely
4. **Verify**: Look for "TejOCR" in the top menu bar

### Usage

1. **Open LibreOffice Writer**
2. **For File OCR**: Tools → TejOCR → OCR Image from File...
3. **For Selected Image**: Insert image → Select it → Tools → TejOCR → OCR Selected Image
4. **Check Settings**: Tools → TejOCR → Settings (shows dependency status)

## 🔧 Troubleshooting

### Check Dependencies
Go to **Tools → TejOCR → Settings** to see current status:
- ✅ Tesseract: Should show installed version
- ✅ Python packages: Should show NumPy, Pytesseract, Pillow as available

### Common Issues

**"Tesseract not found"**:
- Install Tesseract using package manager
- Check that `tesseract --version` works in terminal

**"NumPy not found"**:
- Run the dependency installer: `python3 install_dependencies.py`
- Or install manually to LibreOffice's Python as shown above

**Extension doesn't appear**:
- Restart LibreOffice completely
- Check Extension Manager to verify installation
- Look for error messages in terminal when starting LibreOffice

### Debug Mode
Start LibreOffice from terminal to see detailed logs:
```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer
```

## 🏗️ Development

### Building from Source
```bash
git clone <repository>
cd TejOCR
python3 build.py
```

### Project Structure
```
TejOCR/
├── python/tejocr/          # Main Python package
│   ├── constants.py        # Version and configuration constants
│   ├── tejocr_service.py   # Main UNO service
│   ├── tejocr_engine.py    # OCR processing engine
│   ├── tejocr_output.py    # Text insertion handling
│   ├── tejocr_dialogs.py   # User interface dialogs
│   └── uno_utils.py        # UNO utilities and helpers
├── icons/                  # Extension icons
├── description.xml         # Extension metadata
├── Addons.xcu             # LibreOffice menu/toolbar integration
└── build.py               # Build script
```

## 📝 License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Tesseract OCR team for the excellent OCR engine
- LibreOffice community for extension development resources
- Python community for pytesseract and imaging libraries

---

**Note**: This is v0.1.4 with Phase 1 (core stability) complete. Phase 2 (enhanced UI/UX) is coming next!

For detailed changes and technical information, see [CHANGELOG.md](CHANGELOG.md).

## 🧠 About the Name

**Tej** (तेज) in Sanskrit and other Indian languages means *light*, *effulgence*, *sharpness*, or *brilliance*. **TejOCR** aims to bring clarity and insight to your documents by making the text within images accessible and editable.

## 📧 Contact

*   Maintainer: **Devansh Varshney**
*   GitHub: [varshneydevansh](https://github.com/varshneydevansh)
*   Twitter: [@varshneydevansh](https://x.com/varshneydevansh)