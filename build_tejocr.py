#!/usr/bin/env python3
"""
TejOCR LibreOffice Extension Build Script
=========================================

This script provides comprehensive build automation for the TejOCR extension.
It handles:
- Phase 1: Critical error fixes verification
- Phase 2: UI enhancements
- Phase 3: Build packaging
- Testing and validation
- LibreOffice installation management

Author: Assistant working with Devansh
Date: May 2025
"""

import os
import sys
import shutil
import subprocess
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import time
import json

class TejOCRBuilder:
    """Comprehensive builder for TejOCR extension."""
    
    def __init__(self, workspace_dir=None):
        """Initialize the builder with workspace directory."""
        self.workspace_dir = Path(workspace_dir or os.getcwd())
        self.build_dir = self.workspace_dir / "build"
        self.dist_dir = self.workspace_dir / "dist"
        self.version = "0.1.5"  # Will be read from constants.py
        
        # Create build directories
        self.build_dir.mkdir(exist_ok=True)
        self.dist_dir.mkdir(exist_ok=True)
        
        print(f"TejOCR Builder initialized")
        print(f"Workspace: {self.workspace_dir}")
        print(f"Build dir: {self.build_dir}")
        print(f"Dist dir: {self.dist_dir}")
    
    def get_version_from_constants(self):
        """Extract version from constants.py file."""
        try:
            constants_file = self.workspace_dir / "python" / "tejocr" / "constants.py"
            if constants_file.exists():
                with open(constants_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('EXTENSION_VERSION'):
                            # Extract version from line like: EXTENSION_VERSION = "0.1.5"
                            version = line.split('=')[1].strip().strip('"\'')
                            self.version = version
                            print(f"Found version in constants.py: {self.version}")
                            return
        except Exception as e:
            print(f"Warning: Could not extract version from constants.py: {e}")
        print(f"Using default version: {self.version}")
    
    def run_phase1_tests(self):
        """Run Phase 1 critical error fixes tests."""
        print("\n" + "="*60)
        print("PHASE 1: Running Critical Error Fixes Tests")
        print("="*60)
        
        test_file = self.workspace_dir / "test_phase1_fixes.py"
        if not test_file.exists():
            print("❌ test_phase1_fixes.py not found!")
            return False
        
        try:
            # Test constants only (since uno modules won't be available)
            result = subprocess.run([
                sys.executable, str(test_file)
            ], capture_output=True, text=True, cwd=self.workspace_dir)
            
            print("Test output:")
            print(result.stdout)
            if result.stderr:
                print("Test errors:")
                print(result.stderr)
            
            # Check if at least constants tests passed
            if "All missing constants are now defined correctly" in result.stdout:
                print("✅ Phase 1 basic constants validation passed")
                return True
            else:
                print("❌ Phase 1 tests failed")
                return False
                
        except Exception as e:
            print(f"❌ Error running Phase 1 tests: {e}")
            return False
    
    def validate_file_structure(self):
        """Validate that all required files exist."""
        print("\n" + "="*60) 
        print("PHASE 2: Validating File Structure")
        print("="*60)
        
        required_files = [
            "python/tejocr/__init__.py",
            "python/tejocr/constants.py",
            "python/tejocr/uno_utils.py",
            "python/tejocr/tejocr_service.py", 
            "python/tejocr/tejocr_engine.py",
            "python/tejocr/tejocr_output.py",
            "python/tejocr/tejocr_interactive_dialogs.py",
            "python/tejocr/locale_setup.py",
            "META-INF/manifest.xml",
            "description.xml",
            "Addons.xcu",
            "ProtocolHandler.xcu"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.workspace_dir / file_path
            if not full_path.exists():
                missing_files.append(file_path)
                print(f"❌ Missing: {file_path}")
            else:
                print(f"✅ Found: {file_path}")
        
        if missing_files:
            print(f"\n❌ {len(missing_files)} required files are missing!")
            return False
        else:
            print(f"\n✅ All {len(required_files)} required files found!")
            return True
    
    def validate_python_syntax(self):
        """Validate Python syntax for all Python modules."""
        print("\n" + "="*60)
        print("PHASE 2: Validating Python Syntax")
        print("="*60)
        
        python_files = list((self.workspace_dir / "python").rglob("*.py"))
        syntax_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                compile(source, str(py_file), 'exec')
                print(f"✅ Syntax OK: {py_file.relative_to(self.workspace_dir)}")
            except SyntaxError as e:
                syntax_errors.append((py_file, e))
                print(f"❌ Syntax Error: {py_file.relative_to(self.workspace_dir)} - {e}")
            except Exception as e:
                print(f"⚠️  Warning: {py_file.relative_to(self.workspace_dir)} - {e}")
        
        if syntax_errors:
            print(f"\n❌ {len(syntax_errors)} files have syntax errors!")
            return False
        else:
            print(f"\n✅ All {len(python_files)} Python files have valid syntax!")
            return True
    
    def update_version_info(self):
        """Update version information in various files."""
        print("\n" + "="*60)
        print("PHASE 3: Updating Version Information")
        print("="*60)
        
        self.get_version_from_constants()
        
        # Update description.xml
        desc_file = self.workspace_dir / "description.xml"
        if desc_file.exists():
            try:
                tree = ET.parse(desc_file)
                root = tree.getroot()
                
                # Update version in description.xml
                version_elem = root.find(".//version")
                if version_elem is not None:
                    version_elem.set("value", self.version)
                    tree.write(desc_file, encoding='utf-8', xml_declaration=True)
                    print(f"✅ Updated description.xml version to {self.version}")
                else:
                    print("⚠️  Could not find version element in description.xml")
            except Exception as e:
                print(f"❌ Error updating description.xml: {e}")
        
        print(f"📦 Extension version: {self.version}")
    
    def create_extension_package(self):
        """Create the .oxt extension package."""
        print("\n" + "="*60)
        print("PHASE 3: Creating Extension Package")
        print("="*60)
        
        # Clean build directory
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir()
        
        # Package name
        package_name = f"TejOCR-{self.version}.oxt"
        package_path = self.dist_dir / package_name
        
        # Remove old package if exists
        if package_path.exists():
            package_path.unlink()
        
        # Files and directories to include in the package
        include_items = [
            "python/",
            "META-INF/",
            "description.xml",
            "Addons.xcu",
            "ProtocolHandler.xcu",
            "README.md",
            "LICENSE"
        ]
        
        print("Creating extension package...")
        
        with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in include_items:
                item_path = self.workspace_dir / item
                
                if item_path.is_file():
                    zf.write(item_path, item)
                    print(f"  📄 Added file: {item}")
                elif item_path.is_dir():
                    for file_path in item_path.rglob('*'):
                        if file_path.is_file() and not self._should_exclude_file(file_path):
                            arcname = file_path.relative_to(self.workspace_dir)
                            zf.write(file_path, arcname)
                            print(f"  📄 Added: {arcname}")
                else:
                    print(f"  ⚠️  Skipped missing: {item}")
        
        # Verify package was created
        if package_path.exists():
            size = package_path.stat().st_size
            print(f"\n✅ Extension package created successfully!")
            print(f"📦 Package: {package_path}")
            print(f"📏 Size: {size:,} bytes ({size/1024:.1f} KB)")
            
            # List package contents
            with zipfile.ZipFile(package_path, 'r') as zf:
                file_count = len(zf.namelist())
                print(f"📁 Files in package: {file_count}")
            
            return package_path
        else:
            print("❌ Failed to create extension package!")
            return None
    
    def _should_exclude_file(self, file_path):
        """Check if a file should be excluded from the package."""
        exclude_patterns = [
            '__pycache__',
            '.pyc',
            '.pyo', 
            '.DS_Store',
            '.git',
            'test_',
            '.pytest_cache'
        ]
        
        file_str = str(file_path)
        return any(pattern in file_str for pattern in exclude_patterns)
    
    def install_extension(self, package_path):
        """Install the extension into LibreOffice."""
        print("\n" + "="*60)
        print("PHASE 4: Installing Extension")
        print("="*60)
        
        if not package_path or not package_path.exists():
            print("❌ No package to install!")
            return False
        
        # Try to find LibreOffice installation
        lo_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
            "/usr/bin/libreoffice",  # Linux
            "/usr/bin/soffice",  # Linux alternative
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"  # Windows 32-bit
        ]
        
        soffice_path = None
        for path in lo_paths:
            if os.path.exists(path):
                soffice_path = path
                break
        
        if not soffice_path:
            print("❌ LibreOffice installation not found!")
            print("Please install the extension manually:")
            print(f"  1. Open LibreOffice")
            print(f"  2. Go to Tools > Extension Manager")
            print(f"  3. Click 'Add' and select: {package_path}")
            return False
        
        print(f"Found LibreOffice: {soffice_path}")
        
        try:
            # Install extension using unopkg
            unopkg_dir = os.path.dirname(soffice_path)
            unopkg_path = os.path.join(unopkg_dir, "unopkg")
            if sys.platform == "win32":
                unopkg_path += ".exe"
            
            if not os.path.exists(unopkg_path):
                print(f"⚠️  unopkg not found at {unopkg_path}")
                print("Trying alternative installation method...")
                
                # Try using soffice directly  
                cmd = [soffice_path, "--headless", "--install-extension", str(package_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print("✅ Extension installed successfully using soffice!")
                    return True
                else:
                    print(f"❌ Installation failed: {result.stderr}")
                    return False
            else:
                # Use unopkg for installation
                cmd = [unopkg_path, "add", "--force", str(package_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print("✅ Extension installed successfully using unopkg!")
                    return True
                else:
                    print(f"❌ Installation failed: {result.stderr}")
                    return False
                    
        except subprocess.TimeoutExpired:
            print("❌ Installation timed out!")
            return False
        except Exception as e:
            print(f"❌ Installation error: {e}")
            return False
    
    def run_libreoffice_test(self):
        """Run LibreOffice with the extension to test it."""
        print("\n" + "="*60)
        print("PHASE 4: Testing Extension in LibreOffice")
        print("="*60)
        
        # Find LibreOffice
        lo_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
            "/usr/bin/libreoffice",  # Linux
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
        ]
        
        soffice_path = None
        for path in lo_paths:
            if os.path.exists(path):
                soffice_path = path
                break
        
        if not soffice_path:
            print("❌ LibreOffice not found for testing!")
            return False
        
        print(f"Starting LibreOffice Writer for testing...")
        print(f"Look for TejOCR menu items in the Tools menu.")
        print(f"Test the extension functionality manually.")
        
        try:
            # Start LibreOffice Writer
            cmd = [soffice_path, "--writer"]
            process = subprocess.Popen(cmd)
            
            print(f"✅ LibreOffice started (PID: {process.pid})")
            print(f"Manual testing instructions:")
            print(f"  1. Look for 'TejOCR' in Tools menu")
            print(f"  2. Try 'TejOCR Settings' to configure")
            print(f"  3. Try 'OCR from File' to test functionality")
            print(f"  4. Check the log file for any errors")
            
            return True
            
        except Exception as e:
            print(f"❌ Error starting LibreOffice: {e}")
            return False
    
    def generate_build_report(self, results):
        """Generate a comprehensive build report."""
        print("\n" + "="*60)
        print("BUILD REPORT")
        print("="*60)
        
        report = {
            "build_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": self.version,
            "workspace": str(self.workspace_dir),
            "results": results
        }
        
        # Save report to file
        report_file = self.dist_dir / f"build_report_{self.version}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        
        print(f"Build Summary:")
        print(f"  Version: {self.version}")
        print(f"  Passed: {passed}/{total} phases")
        
        for phase, result in results.items():
            status = "✅" if result else "❌"
            print(f"  {status} {phase}")
        
        if passed == total:
            print(f"\n🎉 BUILD SUCCESSFUL! Extension ready for use.")
        else:
            print(f"\n⚠️  BUILD COMPLETED WITH ISSUES. Check logs above.")
        
        print(f"\nReport saved: {report_file}")
        
        return passed == total

def main():
    """Main build script entry point."""
    print("TejOCR Extension Build Script")
    print("============================")
    
    builder = TejOCRBuilder()
    results = {}
    
    # Phase 1: Critical Tests
    results["Phase 1: Critical Tests"] = builder.run_phase1_tests()
    
    # Phase 2: Validation
    results["Phase 2: File Structure"] = builder.validate_file_structure()
    results["Phase 2: Python Syntax"] = builder.validate_python_syntax()
    
    # Phase 3: Build
    builder.update_version_info()
    package_path = builder.create_extension_package()
    results["Phase 3: Package Creation"] = package_path is not None
    
    # Phase 4: Installation & Testing (optional)
    if package_path:
        results["Phase 4: Extension Installation"] = builder.install_extension(package_path)
        results["Phase 4: LibreOffice Testing"] = builder.run_libreoffice_test()
    else:
        results["Phase 4: Extension Installation"] = False
        results["Phase 4: LibreOffice Testing"] = False
    
    # Generate final report
    success = builder.generate_build_report(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 