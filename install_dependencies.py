#!/usr/bin/env python3
"""
TejOCR Dependency Installation Helper for macOS
This script helps install all required dependencies for the TejOCR LibreOffice extension.
"""

import os
import sys
import subprocess
import platform

def print_header():
    print("="*60)
    print("🚀 TejOCR Dependency Installation Helper")
    print("="*60)
    print()

def check_command_exists(command):
    """Check if a command exists in PATH."""
    try:
        subprocess.run([command, '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def run_command(command, description):
    """Run a command and show progress."""
    print(f"📋 {description}")
    print(f"   Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"   ✅ Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error: {e}")
        if e.stdout:
            print(f"   Output: {e.stdout}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return False

def install_tesseract():
    """Install Tesseract OCR."""
    print("\n🎯 Step 1: Installing Tesseract OCR")
    print("-" * 40)
    
    if check_command_exists('tesseract'):
        print("✅ Tesseract is already installed!")
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
            version = result.stdout.strip().split('\n')[0]
            print(f"   {version}")
        except:
            pass
        return True
    
    # Check if Homebrew is available
    if not check_command_exists('brew'):
        print("❌ Homebrew is not installed.")
        print("   Please install Homebrew first: https://brew.sh")
        print("   Run: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        return False
    
    return run_command('brew install tesseract', 'Installing Tesseract via Homebrew')

def install_python_packages():
    """Install Python packages for LibreOffice."""
    print("\n🎯 Step 2: Installing Python packages for LibreOffice")
    print("-" * 50)
    
    # Find LibreOffice Python
    lo_python_paths = [
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3",
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.10/bin/python3"
    ]
    
    lo_python = None
    for path in lo_python_paths:
        if os.path.exists(path):
            lo_python = path
            break
    
    if not lo_python:
        print("❌ LibreOffice Python not found.")
        print("   Please ensure LibreOffice is installed in /Applications/")
        return False
    
    print(f"✅ Found LibreOffice Python: {lo_python}")
    
    # Install packages
    packages = ['numpy', 'pytesseract', 'pillow']
    for package in packages:
        success = run_command(
            f'"{lo_python}" -m pip install {package}', 
            f'Installing {package} for LibreOffice Python'
        )
        if not success:
            print(f"❌ Failed to install {package}")
            return False
    
    return True

def verify_installation():
    """Verify that all dependencies are working."""
    print("\n🎯 Step 3: Verifying Installation")
    print("-" * 35)
    
    # Check Tesseract
    if check_command_exists('tesseract'):
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
            version = result.stdout.strip().split('\n')[0]
            print(f"✅ Tesseract: {version}")
        except:
            print("⚠️  Tesseract installed but version check failed")
    else:
        print("❌ Tesseract not found")
        return False
    
    # Check Python packages
    lo_python_paths = [
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3",
        "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.10/bin/python3"
    ]
    
    lo_python = None
    for path in lo_python_paths:
        if os.path.exists(path):
            lo_python = path
            break
    
    if not lo_python:
        print("❌ LibreOffice Python not found")
        return False
    
    packages = ['numpy', 'pytesseract', 'PIL']
    for package in packages:
        try:
            result = subprocess.run([lo_python, '-c', f'import {package}; print(f"{package}: OK")'], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            print(f"❌ {package}: Not found or not working")
            return False
    
    return True

def main():
    """Main installation process."""
    print_header()
    
    # Check OS
    if platform.system() != 'Darwin':
        print("❌ This script is designed for macOS only.")
        print("   For other platforms, please install dependencies manually:")
        print("   • Tesseract OCR")
        print("   • Python packages: numpy, pytesseract, pillow")
        sys.exit(1)
    
    # Check Python version
    if sys.version_info < (3, 6):
        print("❌ Python 3.6 or higher is required.")
        sys.exit(1)
    
    print("🔍 Installing dependencies for TejOCR LibreOffice extension...")
    print()
    
    success = True
    
    # Step 1: Install Tesseract
    if not install_tesseract():
        success = False
    
    # Step 2: Install Python packages
    if success and not install_python_packages():
        success = False
    
    # Step 3: Verify installation
    if success and not verify_installation():
        success = False
    
    print("\n" + "="*60)
    if success:
        print("🎉 SUCCESS! All dependencies installed successfully.")
        print()
        print("Next steps:")
        print("1. Restart LibreOffice completely")
        print("2. Install the TejOCR.oxt extension") 
        print("3. Test OCR functionality with Tools → TejOCR")
        print()
        print("If you encounter issues, check Tools → TejOCR → Settings")
        print("for dependency status.")
    else:
        print("❌ Installation completed with errors.")
        print()
        print("Please check the error messages above and:")
        print("1. Ensure Homebrew is installed (for Tesseract)")
        print("2. Ensure LibreOffice is installed in /Applications/")
        print("3. Try running this script again")
        print()
        print("For manual installation:")
        print("• brew install tesseract")
        print("• /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract pillow")
    
    print("="*60)

if __name__ == "__main__":
    main() 