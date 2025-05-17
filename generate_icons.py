#!/usr/bin/env python3
"""
Icon generation script for TejOCR LibreOffice extension.
This script creates properly sized icons from a source image.
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: This script requires Pillow. Install with 'pip install Pillow'")
    sys.exit(1)

def create_icons(source_image_path, output_dir="icons"):
    """
    Create various sized icons from the source image.
    
    Args:
        source_image_path: Path to source image
        output_dir: Directory to save generated icons
    """
    if not os.path.exists(source_image_path):
        print(f"Error: Source image '{source_image_path}' not found.")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Open the source image
        source_img = Image.open(source_image_path)
        
        # Define required icon sizes and names
        icon_sizes = {
            "tejocr_16.png": (16, 16),
            "tejocr_26.png": (26, 26),
            "tejocr_32.png": (32, 32),  # Optional larger size
        }
        
        # Generate each icon size
        for icon_name, size in icon_sizes.items():
            output_path = os.path.join(output_dir, icon_name)
            
            # Resize the image with antialiasing
            resized_img = source_img.resize(size, Image.Resampling.LANCZOS)
            
            # Save the resized image
            resized_img.save(output_path)
            print(f"Created {icon_name} ({size[0]}x{size[1]}) at {output_path}")
        
        # Create a high-contrast version (simple grayscale for demonstration)
        hc_size = (26, 26)  # High contrast icon size
        hc_path = os.path.join(output_dir, "tejocr_26_hc.png")
        
        hc_img = source_img.resize(hc_size, Image.Resampling.LANCZOS)
        # Convert to grayscale and increase contrast (simplified high contrast)
        hc_img = hc_img.convert('L')
        
        # Save high contrast version
        hc_img.save(hc_path)
        print(f"Created high-contrast icon at {hc_path}")
        
        return True
        
    except Exception as e:
        print(f"Error generating icons: {e}")
        return False

if __name__ == "__main__":
    # Default source is the provided logo path
    source_path = "/Users/devanshvarshney/LibreOCR/main_logo.png"
    
    # Allow specifying a different source image path
    if len(sys.argv) > 1:
        source_path = sys.argv[1]
    
    # Specify output directory (default: icons/ in current directory)
    output_dir = "icons"
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    success = create_icons(source_path, output_dir)
    
    if success:
        print("\nAll icons successfully generated.")
        print("These icons will be used in Addons.xcu and description.xml.")
    else:
        print("\nFailed to generate some or all icons.")
        print("Please ensure the source image exists and Pillow is installed.") 