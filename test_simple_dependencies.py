#!/usr/bin/env python3
"""
Simple test for TejOCR dependency checking functionality
"""

import subprocess
import sys
import os
import platform

def check_dependencies():
    """Standalone version of dependency checker"""
    status = {
        'summary': '',
        'tesseract': '',
        'python_packages': '',
        'installation_guide': '',
        'next_steps': ''
    }
    
    # Check Tesseract
    tesseract_status = "❌ NOT FOUND"
    tesseract_path = "Not detected"
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip().split()[1] if result.stdout.strip().split() else "Unknown"
            tesseract_status = f"✅ INSTALLED (v{version})"
            tesseract_path = "Available in system PATH"
    except:
        pass
    
    status['tesseract'] = f"Status: {tesseract_status}\nPath: {tesseract_path}"
    
    # Check Python packages
    python_packages = []
    
    # Check pytesseract
    try:
        import pytesseract
        version = getattr(pytesseract, '__version__', 'installed')
        python_packages.append(f"✅ pytesseract: {version}")
    except ImportError:
        python_packages.append("❌ pytesseract: Not found")
    
    # Check PIL/Pillow
    try:
        import PIL
        python_packages.append(f"✅ Pillow: {PIL.__version__}")
    except ImportError:
        python_packages.append("❌ Pillow: Not found")
    
    python_packages.append("⚪ uno: Available in LibreOffice (normal)")
    status['python_packages'] = '\n'.join(python_packages)
    
    # Determine overall status
    tesseract_ok = "✅" in tesseract_status
    pytesseract_ok = any("✅ pytesseract" in pkg for pkg in python_packages)
    pillow_ok = any("✅ Pillow" in pkg for pkg in python_packages)
    
    if tesseract_ok and pytesseract_ok and pillow_ok:
        status['summary'] = "🎉 ALL DEPENDENCIES READY! OCR functionality available."
        status['next_steps'] = "✅ Ready to enable real OCR functionality!"
    elif tesseract_ok and (pytesseract_ok or pillow_ok):
        missing = []
        if not pytesseract_ok:
            missing.append("pytesseract")
        if not pillow_ok:
            missing.append("Pillow")
        status['summary'] = f"⚠️  PARTIALLY READY - Missing: {', '.join(missing)}"
        status['next_steps'] = f"Install missing packages: {', '.join(missing)}"
    elif tesseract_ok:
        status['summary'] = "🔧 TESSERACT READY - Python packages needed"
        status['next_steps'] = "Install Python packages: pytesseract pillow"
    else:
        status['summary'] = "🚀 SETUP NEEDED - Ready to install dependencies"
        status['next_steps'] = "Install Tesseract and Python packages"
    
    return status

if __name__ == "__main__":
    print("🚀 TejOCR Simple Dependency Check")
    print("=" * 50)
    
    status = check_dependencies()
    
    print(f"📊 OVERALL STATUS: {status['summary']}")
    print()
    print("🔧 TESSERACT:")
    print(status['tesseract'])
    print()
    print("🐍 PYTHON PACKAGES:")
    print(status['python_packages'])
    print()
    print(f"📝 NEXT STEPS: {status['next_steps']}")
    
    print("\n" + "=" * 50)
    print("✅ Dependency check completed!") 