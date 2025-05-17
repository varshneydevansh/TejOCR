#!/usr/bin/env python3
"""
Translation template generation script for TejOCR LibreOffice extension.
This script extracts translatable strings from Python source files and 
generates a .pot template file. It can also create initial empty .po files.
"""

import os
import re
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Languages to generate .po files for
LANGUAGES = ["en", "es", "fr", "de", "zh_CN", "hi"]  # ISO codes
DOMAIN = "tejocr"  # Translation domain name

def find_python_files(src_dir="python/tejocr"):
    """Find all Python files in the given directory."""
    python_files = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files

def extract_strings(python_files, output_pot):
    """Extract translatable strings from Python files using xgettext."""
    # Check if xgettext is available
    if not shutil.which("xgettext"):
        print("Error: xgettext not found. Please install GNU gettext tools.")
        print("  - On macOS: brew install gettext")
        print("  - On Ubuntu/Debian: sudo apt install gettext")
        print("  - On Windows: install from https://mlocati.github.io/articles/gettext-iconv-windows.html")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_pot), exist_ok=True)
    
    # Build xgettext command
    cmd = [
        "xgettext",
        "--language=Python",
        "--keyword=_",
        "--package-name=TejOCR",
        f"--package-version=0.1.0",
        f"--copyright-holder=Devansh",
        "--msgid-bugs-address=https://github.com/varshneydevansh/TejOCR/issues",
        f"--output={output_pot}",
        *python_files
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated template at {output_pot}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running xgettext: {e}")
        
        # Fallback to manual extraction if xgettext fails
        print("Attempting manual extraction...")
        return manual_extract_strings(python_files, output_pot)

def manual_extract_strings(python_files, output_pot):
    """Manually extract translatable strings using regex (fallback method)."""
    string_pattern = re.compile(r'_\(\s*["\'](.+?)["\']\s*\)')
    strings = set()
    
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Find all strings within _("...") or _('...')
                matches = string_pattern.findall(content)
                strings.update(matches)
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    # Create .pot file manually
    try:
        os.makedirs(os.path.dirname(output_pot), exist_ok=True)
        with open(output_pot, 'w', encoding='utf-8') as f:
            f.write(f'''# TejOCR translation template.
# Copyright (C) {datetime.now().year} Devansh
# This file is distributed under the same license as the TejOCR package.
msgid ""
msgstr ""
"Project-Id-Version: TejOCR 0.1.0\\n"
"Report-Msgid-Bugs-To: https://github.com/varshneydevansh/TejOCR/issues\\n"
"POT-Creation-Date: {datetime.now().strftime('%Y-%m-%d %H:%M%z')}\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: LANGUAGE <LL@li.org>\\n"
"Language: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

''')
            
            # Write each extracted string
            for string in sorted(strings):
                escaped = string.replace('"', '\\"')
                f.write(f'msgid "{escaped}"\nmsgstr ""\n\n')
                
        print(f"Successfully created manual template at {output_pot} with {len(strings)} strings")
        return True
    except Exception as e:
        print(f"Error creating manual template: {e}")
        return False

def create_po_files(pot_file, out_dir="l10n"):
    """Create initial .po files for each language based on the .pot template."""
    for lang in LANGUAGES:
        # Create language directory if it doesn't exist
        lang_dir = os.path.join(out_dir, lang, "LC_MESSAGES")
        os.makedirs(lang_dir, exist_ok=True)
        
        po_file = os.path.join(lang_dir, f"{DOMAIN}.po")
        
        # If msginit is available, use it to create the .po file
        if shutil.which("msginit"):
            cmd = [
                "msginit",
                f"--input={pot_file}",
                f"--output={po_file}",
                f"--locale={lang}",
                "--no-translator"
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
                print(f"Created {lang} translation file at {po_file}")
            except subprocess.CalledProcessError:
                print(f"Error creating {lang} translation file using msginit")
                
                # Fallback to simply copying the .pot file to .po
                shutil.copy(pot_file, po_file)
                print(f"Created {lang} translation file by copying template")
        else:
            # Fallback to simply copying the .pot file to .po
            shutil.copy(pot_file, po_file)
            print(f"Created {lang} translation file at {po_file}")

def compile_po_files(out_dir="l10n"):
    """Compile .po files to .mo files if msgfmt is available."""
    if not shutil.which("msgfmt"):
        print("msgfmt not found. Cannot compile .po files to .mo files.")
        print("Translation files will still be included but not compiled.")
        return
    
    for lang in LANGUAGES:
        po_file = os.path.join(out_dir, lang, "LC_MESSAGES", f"{DOMAIN}.po")
        mo_file = os.path.join(out_dir, lang, "LC_MESSAGES", f"{DOMAIN}.mo")
        
        if os.path.exists(po_file):
            cmd = ["msgfmt", po_file, "-o", mo_file]
            try:
                subprocess.run(cmd, check=True)
                print(f"Compiled {lang} translation to {mo_file}")
            except subprocess.CalledProcessError:
                print(f"Error compiling {lang} translation")

if __name__ == "__main__":
    # Find Python files
    python_files = find_python_files()
    if not python_files:
        print("No Python files found in python/tejocr/")
        exit(1)
    
    print(f"Found {len(python_files)} Python files to extract strings from")
    
    # Extract strings to .pot template
    pot_file = os.path.join("l10n", f"{DOMAIN}.pot")
    if extract_strings(python_files, pot_file):
        # Create .po files for each language
        create_po_files(pot_file)
        
        # Compile .po files to .mo files
        compile_po_files()
        
        print("\nTranslation files successfully generated.")
        print("Next steps:")
        print("1. Edit the .po files in the l10n/<lang>/LC_MESSAGES/ directories with translations")
        print("2. Run this script again to compile the .po files to .mo files")
        print("3. Include the l10n directory in your LibreOffice extension")
    else:
        print("\nFailed to extract strings. Check errors above.") 