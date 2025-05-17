#!/usr/bin/env python3
"""
Build script for TejOCR LibreOffice extension.
This script creates a properly packaged .oxt file from the project directory.
"""

import os
import zipfile
import shutil
import tempfile
import re
from pathlib import Path
import sys

VERSION = "0.1.0"  # Should match version in description.xml

def clean_xml_files(temp_dir):
    """
    Ensure XML files have proper encoding (UTF-8 without BOM).
    This is critical for LibreOffice to properly parse the files.
    """
    xml_files = [
        os.path.join(temp_dir, "description.xml"),
        os.path.join(temp_dir, "Addons.xcu"),
        os.path.join(temp_dir, "META-INF", "manifest.xml"),
        *[os.path.join(temp_dir, "dialogs", f) for f in os.listdir(os.path.join(temp_dir, "dialogs")) 
          if f.endswith(".xdl")]
    ]
    
    for xml_file in xml_files:
        if os.path.exists(xml_file):
            # Read the file content
            with open(xml_file, 'rb') as f:
                content = f.read()
            
            # Remove BOM if present
            if content.startswith(b'\xef\xbb\xbf'):  # UTF-8 BOM
                print(f"Removing BOM from {os.path.basename(xml_file)}")
                content = content[3:]
            
            # Ensure XML declaration is correct and at the very beginning
            content_str = content.decode('utf-8')
            if not content_str.startswith('<?xml version="1.0" encoding="UTF-8"?>'):
                content_str = re.sub(r'<\?xml.*?\?>', '', content_str)
                content_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + content_str.lstrip()
            
            # Write back cleaned content
            with open(xml_file, 'wb') as f:
                f.write(content_str.encode('utf-8'))

def verify_required_files(temp_dir):
    """Check if all required files exist"""
    required_files = [
        "description.xml",
        "Addons.xcu",
        os.path.join("META-INF", "manifest.xml"),
        # Add other essential files
    ]
    
    missing = []
    for file_path in required_files:
        full_path = os.path.join(temp_dir, file_path)
        if not os.path.exists(full_path):
            missing.append(file_path)
    
    if missing:
        print("ERROR: Missing required files:", ", ".join(missing))
        return False
    return True

def verify_icons(temp_dir):
    """Check if icon files referenced in XML exist"""
    icon_dir = os.path.join(temp_dir, "icons")
    needed_icons = ["tejocr_16.png", "tejocr_26.png", "tejocr_26_hc.png"]
    
    missing = []
    for icon in needed_icons:
        if not os.path.exists(os.path.join(icon_dir, icon)):
            missing.append(icon)
    
    if missing:
        print("WARNING: Missing icon files:", ", ".join(missing))
        print("Some extension functionality may be limited without these icons.")
        return False
    return True

def create_extension(build_dir=None, output_name=None):
    """
    Package the TejOCR extension as an .oxt file.
    
    Args:
        build_dir: Directory to build in (temporary if None)
        output_name: Name of output file (default: TejOCR-{VERSION}.oxt)
    
    Returns:
        Path to the created .oxt file
    """
    # Get the project root directory (where this script is located)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create a clean temporary directory for building
    if build_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="tejocr_build_")
        should_cleanup = True
    else:
        temp_dir = build_dir
        os.makedirs(temp_dir, exist_ok=True)
        should_cleanup = False
    
    try:
        print(f"Building TejOCR v{VERSION} extension in {temp_dir}")
        
        # Copy all project files to the temporary directory
        for item in os.listdir(project_dir):
            # Skip .git, __pycache__, and other non-essential directories
            if item in ['.git', '__pycache__', '.vscode', '.idea', 'build.py', 'build']:
                continue
            
            src = os.path.join(project_dir, item)
            dst = os.path.join(temp_dir, item)
            
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        
        # Clean XML files to ensure proper encoding (UTF-8 without BOM)
        clean_xml_files(temp_dir)
        
        # Verify required files exist
        if not verify_required_files(temp_dir):
            print("ERROR: Extension cannot be built due to missing required files.")
            return None
        
        # Verify icon files
        verify_icons(temp_dir)
        
        # Create the .oxt file (which is just a ZIP file with .oxt extension)
        if output_name is None:
            output_name = f"TejOCR-{VERSION}.oxt"
        
        output_path = os.path.join(project_dir, output_name)
        
        # Remove existing file if it exists
        if os.path.exists(output_path):
            os.remove(output_path)
        
        # Create the ZIP file with all contents
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Get the path relative to temp_dir for proper structure in ZIP
                    rel_path = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, rel_path)
        
        print(f"Extension successfully built: {output_path}")
        return output_path
        
    finally:
        # Clean up temporary directory unless specified otherwise
        if should_cleanup and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # Allow specifying output filename from command line
    output_name = None
    if len(sys.argv) > 1:
        output_name = sys.argv[1]
    
    create_extension(output_name=output_name) 