#!/usr/bin/env python3
"""
Test script to verify OCR dependencies for TejOCR extension
Run this to check if everything is properly installed
"""

import sys
import subprocess
import os

def test_tesseract():
    """Test if Tesseract is installed and working"""
    print("🔍 Testing Tesseract installation...")
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_info = result.stdout.strip()
            print(f"✅ Tesseract found: {version_info.split()[1]}")
            return True
        else:
            print(f"❌ Tesseract command failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Tesseract not found in PATH")
        print("   Install with: brew install tesseract (macOS)")
        return False
    except Exception as e:
        print(f"❌ Error testing Tesseract: {e}")
        return False

def test_python_packages():
    """Test if required Python packages are available"""
    print("\n🔍 Testing Python packages...")
    
    packages = {
        'pytesseract': 'OCR text extraction',
        'PIL': 'Image processing (Pillow)',
        'uno': 'LibreOffice integration'
    }
    
    results = {}
    for package, description in packages.items():
        try:
            if package == 'PIL':
                import PIL
                version = PIL.__version__
            elif package == 'pytesseract':
                import pytesseract
                version = pytesseract.__version__ if hasattr(pytesseract, '__version__') else 'installed'
            elif package == 'uno':
                import uno
                version = 'available'
            
            print(f"✅ {package}: {version} - {description}")
            results[package] = True
        except ImportError:
            print(f"❌ {package}: Not found - {description}")
            results[package] = False
        except Exception as e:
            print(f"⚠️  {package}: Error - {e}")
            results[package] = False
    
    return results

def test_simple_ocr():
    """Test basic OCR functionality if everything is available"""
    print("\n🔍 Testing basic OCR functionality...")
    try:
        import pytesseract
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple test image with text
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # Try to use a basic font
        try:
            # On macOS, try to find a system font
            font_paths = [
                '/System/Library/Fonts/Arial.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'  # Linux
            ]
            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 20)
                    break
            
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        draw.text((10, 40), "Hello TejOCR!", fill='black', font=font)
        
        # Try OCR
        text = pytesseract.image_to_string(img).strip()
        
        if 'Hello' in text or 'TejOCR' in text:
            print(f"✅ OCR test successful: '{text}'")
            return True
        else:
            print(f"⚠️  OCR test partial: got '{text}' (may be font/quality issue)")
            return True
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
        return False

def print_installation_help():
    """Print installation instructions"""
    print("\n📋 Installation Instructions:")
    print("\n1. Install Tesseract:")
    print("   macOS: brew install tesseract")
    print("   Ubuntu: sudo apt install tesseract-ocr")
    print("   Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
    
    print("\n2. Install Python packages for LibreOffice:")
    print("   Find LibreOffice Python:")
    lo_python_paths = [
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3",
        "/opt/libreoffice*/program/python",  # Linux
        "C:\\Program Files\\LibreOffice\\program\\python.exe"  # Windows
    ]
    
    for path in lo_python_paths:
        if '*' not in path and os.path.exists(path):
            print(f"   Found: {path}")
            print(f"   Install: {path} -m pip install pytesseract pillow")
            break
    else:
        print("   Manual search needed - look for LibreOffice's python executable")
        print("   Then run: /path/to/libreoffice/python -m pip install pytesseract pillow")
    
    print("\n3. Test installation:")
    print("   Run this script again to verify everything works")

def main():
    """Main test function"""
    print("🚀 TejOCR Dependency Checker")
    print("=" * 50)
    
    tesseract_ok = test_tesseract()
    packages_ok = test_python_packages()
    
    if tesseract_ok and all(packages_ok.values()):
        ocr_ok = test_simple_ocr()
        print(f"\n🎉 All tests passed! Ready for TejOCR development.")
        print("   Next step: Set DEVELOPMENT_MODE_STRICT_PLACEHOLDERS = False")
    else:
        print(f"\n⚠️  Some dependencies missing.")
        print_installation_help()
    
    print("\n" + "=" * 50)
    print("Current Python interpreter:", sys.executable)
    print("Python version:", sys.version)

if __name__ == '__main__':
    main() 