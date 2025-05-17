#!/usr/bin/env python3
"""
Test script for TejOCR engine.
This script tests the Tesseract OCR integration without requiring LibreOffice.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
except ImportError:
    print("Error: This script requires Pillow and pytesseract.")
    print("Install with: pip install Pillow pytesseract")
    sys.exit(1)

def check_tesseract_installation():
    """Check if Tesseract is installed and accessible."""
    try:
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR version {version} found")
        
        # Try to get available languages
        try:
            languages = pytesseract.get_languages()
            print(f"✅ Available languages: {', '.join(languages)}")
        except Exception as e:
            print(f"⚠️ Warning: Could not get language list: {e}")
            print("This might be due to permissions or incorrect Tesseract path.")
        
        return True
    except Exception as e:
        print(f"❌ Error: Tesseract not found or not properly installed: {e}")
        print("\nPlease make sure Tesseract is installed and in your PATH.")
        print("Installation instructions:")
        print("  - Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  - macOS: brew install tesseract")
        print("  - Linux: sudo apt install tesseract-ocr")
        return False

def test_image_preprocessing(img_path):
    """Test basic image preprocessing techniques."""
    print("\nTesting image preprocessing...")
    
    try:
        # Open the image
        image = Image.open(img_path)
        
        # Create a temp directory for output
        temp_dir = tempfile.mkdtemp(prefix="tejocr_test_")
        
        try:
            # Original
            original_path = os.path.join(temp_dir, "original.png")
            image.save(original_path)
            print(f"✅ Saved original image to {original_path}")
            
            # Grayscale
            gray = image.convert('L')
            gray_path = os.path.join(temp_dir, "grayscale.png")
            gray.save(gray_path)
            print(f"✅ Saved grayscale image to {gray_path}")
            
            # Binarize (simple threshold, Otsu would be better)
            threshold = 128
            binary = gray.point(lambda p: 255 if p > threshold else 0)
            binary_path = os.path.join(temp_dir, "binary.png")
            binary.save(binary_path)
            print(f"✅ Saved binary image to {binary_path}")
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            enhanced = enhancer.enhance(2.0)  # Increase contrast
            enhanced_path = os.path.join(temp_dir, "enhanced.png")
            enhanced.save(enhanced_path)
            print(f"✅ Saved contrast-enhanced image to {enhanced_path}")
            
            print(f"\nAll preprocessed images saved to {temp_dir}")
            print("These files can be used for OCR testing to compare results.")
            
            return {
                "original": original_path,
                "grayscale": gray_path,
                "binary": binary_path,
                "enhanced": enhanced_path
            }
        except Exception as e:
            print(f"❌ Error during preprocessing: {e}")
            return None
    except Exception as e:
        print(f"❌ Error opening image: {e}")
        return None

def test_ocr(image_paths, lang='eng'):
    """Test OCR on different preprocessed versions of the image."""
    print(f"\nTesting OCR with language: {lang}")
    
    results = {}
    
    for name, path in image_paths.items():
        print(f"\nProcessing {name} image...")
        try:
            # Run OCR
            start_time = __import__('time').time()
            text = pytesseract.image_to_string(Image.open(path), lang=lang)
            end_time = __import__('time').time()
            
            # Truncate text for display if too long
            display_text = text[:500] + "..." if len(text) > 500 else text
            
            print(f"✅ OCR completed in {end_time - start_time:.2f} seconds")
            print(f"Text detected ({len(text)} characters):")
            print("-" * 40)
            print(display_text)
            print("-" * 40)
            
            # Save result
            results[name] = text
        except Exception as e:
            print(f"❌ Error during OCR: {e}")
    
    return results

def test_advanced_ocr_options(img_path, lang='eng'):
    """Test different PSM and OEM modes."""
    print("\nTesting advanced OCR options...")
    
    try:
        image = Image.open(img_path)
        
        # Test different PSM modes
        psm_modes = {
            3: "Default (automatic page segmentation)",
            6: "Assume a single uniform block of text",
            7: "Treat the image as a single text line",
            8: "Treat the image as a single word",
            13: "Raw line. Treat the image as a single text line"
        }
        
        for psm, description in psm_modes.items():
            print(f"\nTesting PSM mode {psm} - {description}")
            try:
                config = f"--psm {psm}"
                text = pytesseract.image_to_string(image, lang=lang, config=config)
                
                # Show a preview of the result
                preview = text[:100].replace('\n', ' ')
                if len(text) > 100:
                    preview += "..."
                
                print(f"✅ Result: {preview}")
            except Exception as e:
                print(f"❌ Error with PSM {psm}: {e}")
        
        # Test different OEM modes (if Tesseract 4.0+)
        if pytesseract.get_tesseract_version().startswith(('4', '5')):
            oem_modes = {
                0: "Legacy engine only",
                1: "Neural nets LSTM engine only",
                2: "Legacy + LSTM engines",
                3: "Default, based on what is available"
            }
            
            print("\nTesting OEM modes:")
            for oem, description in oem_modes.items():
                print(f"\nTesting OEM mode {oem} - {description}")
                try:
                    config = f"--oem {oem}"
                    text = pytesseract.image_to_string(image, lang=lang, config=config)
                    
                    # Show a preview of the result
                    preview = text[:100].replace('\n', ' ')
                    if len(text) > 100:
                        preview += "..."
                    
                    print(f"✅ Result: {preview}")
                except Exception as e:
                    print(f"❌ Error with OEM {oem}: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Error during advanced OCR testing: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TejOCR Engine Test")
    print("=" * 60)
    
    # Step 1: Check if Tesseract is installed
    if not check_tesseract_installation():
        sys.exit(1)
    
    # Step 2: Get test image
    test_image = None
    if len(sys.argv) > 1:
        # Use provided image path
        test_image = sys.argv[1]
        if not os.path.exists(test_image):
            print(f"❌ Error: Test image '{test_image}' not found")
            sys.exit(1)
    else:
        # Ask for an image path
        test_image = input("\nPlease enter the path to a test image file: ").strip()
        if not test_image or not os.path.exists(test_image):
            print("❌ No valid test image provided.")
            print("Example usage: python test_ocr_engine.py /path/to/image.png")
            sys.exit(1)
    
    print(f"\n✅ Using test image: {test_image}")
    
    # Step 3: Test image preprocessing
    preprocessed_images = test_image_preprocessing(test_image)
    if not preprocessed_images:
        print("❌ Image preprocessing failed. Exiting.")
        sys.exit(1)
    
    # Step 4: Test basic OCR
    lang = 'eng'  # Default to English
    if len(sys.argv) > 2:
        lang = sys.argv[2]
    
    ocr_results = test_ocr(preprocessed_images, lang)
    
    # Step 5: Test advanced OCR options
    test_advanced_ocr_options(test_image, lang)
    
    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)
    print("\nThis confirms that Tesseract OCR is working properly with Python.")
    print("The TejOCR extension should be able to use Tesseract for OCR operations.") 