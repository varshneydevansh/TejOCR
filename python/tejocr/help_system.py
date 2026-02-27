# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/. 
#
# © 2025 Devansh (Author of TejOCR)

"""Help system for TejOCR with user guidance and troubleshooting."""
import sys

from tejocr import constants
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
            "TejOCR Installation Guide\n\n"
            "TejOCR requires Tesseract OCR for image text extraction.\n\n"
            "Installation steps:\n"
            "1) Windows: install from the official UB-Mannheim package.\n"
            "2) macOS: run `brew install tesseract`\n"
            "3) Linux: run `sudo apt install tesseract-ocr`\n"
            "4) Install packages in LibreOffice Python:\n"
            f"   `{sys.executable} -m pip install numpy pytesseract pillow`\n"
            "5) Keep your Tesseract language packs up to date.\n\n"
            "More reference:\n"
            "https://tesseract-ocr.github.io/tessdoc/Installation.html"
        )

        uno_utils.show_message_box(
            "Installation Help",
            help_text,
            "infobox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    @staticmethod
    def show_usage_help(ctx, parent_frame):
        """Show usage help for TejOCR."""
        help_text = _(
            "How to Use TejOCR\n\n"
            "TejOCR extracts text from images directly in LibreOffice documents.\n\n"
            "OCR from selected image:\n"
            "1) Insert an image in the document and select it\n"
            "2) Choose OCR Selected Image from the TejOCR top menu\n"
            "3) Select language and output destination\n"
            "4) Click Start OCR\n\n"
            "OCR from file:\n"
            "1) Choose OCR Image from File from the TejOCR top menu\n"
            "2) Pick the image file\n"
            "3) Select language and output destination\n"
            "4) Click Start OCR\n\n"
            "Output options:\n"
            "- Insert at cursor\n"
            "- Copy to clipboard\n"
            "- New text box\n"
            "- Replace image (only for selected images)"
        )

        uno_utils.show_message_box(
            "Usage Guide",
            help_text,
            "infobox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    @staticmethod
    def show_troubleshooting_help(ctx, parent_frame):
        """Show troubleshooting help."""
        help_text = _(
            "TejOCR Troubleshooting\n\n"
            "Tesseract not found:\n"
            "- Verify installation with: tesseract --version\n"
            "- If missing, install Tesseract using your OS package\n"
            "- Set the executable path in TejOCR settings if auto-detect fails\n\n"
            "Language package missing:\n"
            "- Install OCR language data for your target language\n"
            "- Verify with: tesseract --list-langs\n\n"
            "No text recognized:\n"
            "- Use a higher-resolution image\n"
            "- Confirm text is clear and correctly oriented\n\n"
            "Slow OCR or poor accuracy:\n"
            "- Try a simpler OCR mode (OEM/PSM options)\n"
            "- Reduce image size or enable only needed preprocessing\n\n"
            "Logs are available at /tmp/TejOCRLogs/tejocr.log"
        )

        uno_utils.show_message_box(
            "Troubleshooting",
            help_text,
            "infobox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    @staticmethod
    def show_language_help(ctx, parent_frame):
        """Show help about language selection."""
        help_text = _(
            "Language Selection Guide\n\n"
            "Use language codes to match the text in the image:\n"
            "eng, hin, fra, deu, spa, ita, por, rus, ara, jpn, chi_sim, chi_tra\n\n"
            "Mixed language OCR is supported by using `+`:\n"
            "eng+hin or eng+fra\n\n"
            "Install language data with your package manager and restart LibreOffice if required."
        )

        uno_utils.show_message_box(
            "Language Guide",
            help_text,
            "infobox",
            parent_frame=parent_frame,
            ctx=ctx,
        )

    @staticmethod
    def show_about_dialog(ctx, parent_frame):
        """Show about dialog."""
        about_text = _(
            "About TejOCR\n\n"
            f"Version: {constants.EXTENSION_VERSION}\n\n"
            "Optical character recognition extension for LibreOffice\n"
            "Built with LibreOffice UNO API and Python\n"
            "Supports multiple OCR modes and languages"
        )

        uno_utils.show_message_box(
            "About TejOCR",
            about_text,
            "infobox",
            parent_frame=parent_frame,
            ctx=ctx,
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
