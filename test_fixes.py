#!/usr/bin/env python3
"""
Test script to verify critical bug fixes in TejOCR Phase 1
Run this before building to ensure fixes are working
"""

import sys
import os

# Add the python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# Mock UNO module for testing outside LibreOffice
class MockUno:
    def getComponentContext(self): return None
    def getConstantByName(self, name): return 1
    def createUnoStruct(self, name): 
        class MockStruct:
            def __init__(self): 
                self.Name = ""
                self.Value = ""
        return MockStruct()

class MockUnoHelper:
    def fileUrlToSystemPath(self, url): return "/tmp/test"
    def systemPathToFileUrl(self, path): return f"file://{path}"
    class Base: pass

# Install mocks
sys.modules['uno'] = MockUno()
sys.modules['unohelper'] = MockUnoHelper()

# Mock com.sun.star modules
class MockComSunStar:
    class awt:
        class MessageBoxType:
            INFOBOX = 1
            WARNINGBOX = 2
            ERRORBOX = 3
            QUERYBOX = 4
        class MessageBoxButtons:
            BUTTONS_OK = 1
            BUTTONS_YES_NO = 2
            BUTTONS_YES_NO_CANCEL = 3
        class MessageBoxResults:
            OK = 1
            YES = 1
            NO = 2
            CANCEL = 0
        class XActionListener: pass
        class XItemListener: pass
    class frame:
        class XJobExecutor: pass
    class text:
        class XTextDocument: pass
        class XText: pass
        class XTextRange: pass
        class XTextContent: pass
    class container:
        class XNamed: pass
    class datatransfer:
        class XTransferable: pass
        class DataFlavor: pass
        class clipboard:
            class XClipboard: pass

sys.modules['com'] = MockComSunStar()
sys.modules['com.sun'] = MockComSunStar()
sys.modules['com.sun.star'] = MockComSunStar()
sys.modules['com.sun.star.awt'] = MockComSunStar.awt()
sys.modules['com.sun.star.frame'] = MockComSunStar.frame()
sys.modules['com.sun.star.text'] = MockComSunStar.text()
sys.modules['com.sun.star.container'] = MockComSunStar.container()
sys.modules['com.sun.star.datatransfer'] = MockComSunStar.datatransfer()
sys.modules['com.sun.star.datatransfer.clipboard'] = MockComSunStar.datatransfer.clipboard()

def test_copy_to_clipboard_function():
    """Test 1: Verify copy_text_to_clipboard function exists"""
    print("🔍 Test 1: Checking copy_text_to_clipboard function...")
    try:
        from tejocr import tejocr_output
        
        # Check if the function exists
        if hasattr(tejocr_output, 'copy_text_to_clipboard'):
            print("✅ copy_text_to_clipboard function exists")
            return True
        else:
            print("❌ copy_text_to_clipboard function missing")
            return False
    except Exception as e:
        print(f"❌ Error importing tejocr_output: {e}")
        return False

def test_language_detection():
    """Test 2: Verify language detection works"""
    print("\n🔍 Test 2: Checking language detection...")
    try:
        from tejocr import tejocr_engine
        
        # Check if functions exist
        if hasattr(tejocr_engine, 'get_available_languages'):
            print("✅ get_available_languages function exists")
            
            if hasattr(tejocr_engine, 'is_language_available'):
                print("✅ is_language_available function exists")
                return True
            else:
                print("❌ is_language_available function missing")
                return False
        else:
            print("❌ get_available_languages function missing")
            return False
    except Exception as e:
        print(f"❌ Error testing language detection: {e}")
        return False

def test_imports():
    """Test 3: Verify all modules can be imported"""
    print("\n🔍 Test 3: Checking module imports...")
    modules_to_test = [
        'tejocr.uno_utils',
        'tejocr.tejocr_engine', 
        'tejocr.tejocr_output',
        'tejocr.constants'
    ]
    
    all_passed = True
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module} imported successfully")
        except Exception as e:
            print(f"❌ {module} import failed: {e}")
            all_passed = False
    
    return all_passed

def test_function_signatures():
    """Test 4: Verify function signatures are correct"""
    print("\n🔍 Test 4: Checking function signatures...")
    try:
        from tejocr import tejocr_engine, tejocr_output
        
        # Test engine functions
        engine_functions = [
            'is_tesseract_ready',
            'extract_text_from_selected_image', 
            'extract_text_from_image_file',
            'get_available_languages',
            'is_language_available'
        ]
        
        for func_name in engine_functions:
            if hasattr(tejocr_engine, func_name):
                print(f"✅ tejocr_engine.{func_name} exists")
            else:
                print(f"❌ tejocr_engine.{func_name} missing")
                return False
        
        # Test output functions
        output_functions = [
            'copy_text_to_clipboard',
            'insert_text_at_cursor',
            'handle_ocr_output'
        ]
        
        for func_name in output_functions:
            if hasattr(tejocr_output, func_name):
                print(f"✅ tejocr_output.{func_name} exists")
            else:
                print(f"❌ tejocr_output.{func_name} missing")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Error testing function signatures: {e}")
        return False

def main():
    """Run all tests and provide feedback"""
    print("🚀 TejOCR Phase 1 Critical Bug Fixes - Test Suite")
    print("=" * 60)
    
    tests = [
        test_copy_to_clipboard_function,
        test_language_detection,
        test_imports,
        test_function_signatures
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("\n🎉 Phase 1 fixes are ready!")
        print("💡 Ready for your feedback - should I proceed with python3 build.py?")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("\n🔧 Please fix the failing tests before building")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 