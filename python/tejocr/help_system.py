# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

"""Help system for TejOCR with user-friendly guidance and troubleshooting."""

from tejocr import uno_utils
from tejocr import locale_setup

_ = locale_setup.get_translator().gettext
logger = uno_utils.get_logger("TejOCR.Help")

class HelpSystem:
    """Comprehensive help system for TejOCR."""
    
    @staticmethod
    def show_installation_help(ctx, parent_frame):
        """Show installation help for dependencies."""
        help_text = _(
            "🔧 TejOCR Installation Guide\n\n"
            "TejOCR requires Tesseract OCR to extract text from images.\n\n"
            "📦 INSTALLATION INSTRUCTIONS:\n\n"
            "🍎 macOS:\n"
            "  • Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n"
            "  • Install Tesseract: brew install tesseract\n"
            "  • Install language packs: brew install tesseract-lang\n\n"
            "🐧 Ubuntu/Debian:\n"
            "  • Update packages: sudo apt update\n"
            "  • Install Tesseract: sudo apt install tesseract-ocr\n"
            "  • Install language packs: sudo apt install tesseract-ocr-hin tesseract-ocr-fra\n\n"
            "🪟 Windows:\n"
            "  • Download from: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  • Run installer and note installation path\n"
            "  • Add to PATH or configure manually in TejOCR settings\n\n"
            "🌐 More info: https://tesseract-ocr.github.io/tessdoc/Installation.html"
        )
        
        uno_utils.show_message_box(
            "Installation Help", help_text, "infobox",
            parent_frame=parent_frame, ctx=ctx
        )
    
    @staticmethod
    def show_usage_help(ctx, parent_frame):
        """Show usage help for TejOCR."""
        help_text = _(
            "📖 How to Use TejOCR\n\n"
            "TejOCR extracts text from images in your LibreOffice documents.\n\n"
            "🖼️ OCR FROM SELECTED IMAGE:\n"
            "1. Insert an image into your document (Insert → Image)\n"
            "2. Click on the image to select it\n"
            "3. Go to Tools → TejOCR → OCR Selected Image\n"
            "4. Choose language and output method\n"
            "5. Click 'Start OCR'\n\n"
            "📁 OCR FROM FILE:\n"
            "1. Go to Tools → TejOCR → OCR Image from File\n"
            "2. Select an image file (PNG, JPG, PDF, etc.)\n"
            "3. Choose language and output method\n"
            "4. Click 'Start OCR'\n\n"
            "📍 OUTPUT OPTIONS:\n"
            "• Insert at Cursor: Adds text where your cursor is\n"
            "• Copy to Clipboard: Copies text for pasting elsewhere\n"
            "• New Text Box: Creates a text box with the extracted text\n\n"
            "⚙️ SETTINGS:\n"
            "Go to Tools → TejOCR → Settings to configure Tesseract path and default language."
        )
        
        uno_utils.show_message_box(
            "Usage Guide", help_text, "infobox",
            parent_frame=parent_frame, ctx=ctx
        )
    
    @staticmethod
    def show_troubleshooting_help(ctx, parent_frame):
        """Show troubleshooting help."""
        help_text = _(
            "🔧 TejOCR Troubleshooting\n\n"
            "❌ TESSERACT NOT FOUND:\n"
            "• Check if Tesseract is installed: tesseract --version\n"
            "• On macOS: brew install tesseract\n"
            "• On Ubuntu: sudo apt install tesseract-ocr\n"
            "• Configure path manually in Settings\n\n"
            "🌍 LANGUAGE NOT AVAILABLE:\n"
            "• Install language packs for your language\n"
            "• macOS: brew install tesseract-lang\n"
            "• Ubuntu: sudo apt install tesseract-ocr-[lang]\n"
            "• Check available: tesseract --list-langs\n\n"
            "📝 NO TEXT RECOGNIZED:\n"
            "• Ensure image has clear, readable text\n"
            "• Try different language settings\n"
            "• Use high-resolution images\n"
            "• Avoid skewed or rotated text\n\n"
            "🐌 SLOW PERFORMANCE:\n"
            "• Use smaller images when possible\n"
            "• Close other applications\n"
            "• Try simpler OCR engine modes\n\n"
            "💬 NEED MORE HELP?\n"
            "Check the logs in /tmp/TejOCRLogs/ for detailed error messages."
        )
        
        uno_utils.show_message_box(
            "Troubleshooting", help_text, "infobox",
            parent_frame=parent_frame, ctx=ctx
        )
    
    @staticmethod
    def show_language_help(ctx, parent_frame):
        """Show help about language selection."""
        help_text = _(
            "🌍 Language Selection Guide\n\n"
            "Choosing the correct language improves OCR accuracy significantly.\n\n"
            "📋 COMMON LANGUAGE CODES:\n"
            "• eng - English\n"
            "• hin - Hindi\n"
            "• fra - French\n"
            "• deu - German\n"
            "• spa - Spanish\n"
            "• ita - Italian\n"
            "• por - Portuguese\n"
            "• rus - Russian\n"
            "• ara - Arabic\n"
            "• chi_sim - Chinese Simplified\n"
            "• chi_tra - Chinese Traditional\n"
            "• jpn - Japanese\n\n"
            "💡 TIPS:\n"
            "• Use the language of the text in your image\n"
            "• For mixed languages, try the primary language first\n"
            "• Some languages require special font support\n"
            "• Check available languages: tesseract --list-langs\n\n"
            "📦 INSTALLING LANGUAGE PACKS:\n"
            "• macOS: brew install tesseract-lang\n"
            "• Ubuntu: sudo apt install tesseract-ocr-[language]\n"
            "• Windows: Download from Tesseract releases"
        )
        
        uno_utils.show_message_box(
            "Language Guide", help_text, "infobox",
            parent_frame=parent_frame, ctx=ctx
        )
    
    @staticmethod
    def show_about_dialog(ctx, parent_frame):
        """Show about dialog."""
        about_text = _(
            "📄 About TejOCR\n\n"
            "TejOCR - Optical Character Recognition for LibreOffice\n"
            "Version 0.1.5\n\n"
            "© 2025 Devansh (Author of TejOCR)\n\n"
            "🎯 PURPOSE:\n"
            "Extract text from images directly within LibreOffice Writer documents.\n\n"
            "🔧 TECHNOLOGY:\n"
            "• Built with Python and LibreOffice UNO API\n"
            "• Powered by Google Tesseract OCR Engine\n"
            "• Supports 100+ languages\n\n"
            "📜 LICENSE:\n"
            "Mozilla Public License 2.0\n\n"
            "🌐 MORE INFO:\n"
            "Visit the project repository for documentation and updates.\n\n"
            "🙏 ACKNOWLEDGMENTS:\n"
            "Thanks to the Tesseract OCR team and LibreOffice community."
        )
        
        uno_utils.show_message_box(
            "About TejOCR", about_text, "infobox",
            parent_frame=parent_frame, ctx=ctx
        )

def show_contextual_help(ctx, parent_frame, help_type="usage"):
    """Show contextual help based on the situation."""
    help_system = HelpSystem()
    
    if help_type == "installation":
        help_system.show_installation_help(ctx, parent_frame)
    elif help_type == "troubleshooting":
        help_system.show_troubleshooting_help(ctx, parent_frame)
    elif help_type == "language":
        help_system.show_language_help(ctx, parent_frame)
    elif help_type == "about":
        help_system.show_about_dialog(ctx, parent_frame)
    else:
        help_system.show_usage_help(ctx, parent_frame) 