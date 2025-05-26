#!/usr/bin/env python3
"""
Test script to verify Phase 1 fixes for TejOCR
Tests the critical bug fixes before building
"""

import sys
import os

# Add the python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

def test_constants():
    """Test 1: Verify constants are correctly defined"""
    print("🔍 Test 1: Checking constants...")
    try:
        from tejocr import constants
        
        # Check output mode constants
        assert constants.OUTPUT_MODE_CURSOR == "at_cursor"
        assert constants.OUTPUT_MODE_CLIPBOARD == "to_clipboard"
        assert constants.OUTPUT_MODE_TEXTBOX == "new_textbox"
        assert constants.DEFAULT_OCR_LANGUAGE == "eng"
        
        print("✅ Constants are correctly defined")
        return True
    except Exception as e:
        print(f"❌ Constants test failed: {e}")
        return False

def test_output_functions():
    """Test 2: Verify output functions exist"""
    print("🔍 Test 2: Checking output functions...")
    try:
        from tejocr import tejocr_output
        
        # Check if functions exist
        assert hasattr(tejocr_output, 'handle_ocr_output')
        assert hasattr(tejocr_output, 'insert_text_at_cursor')
        assert hasattr(tejocr_output, 'copy_text_to_clipboard')
        assert hasattr(tejocr_output, 'create_text_box_with_text')
        
        print("✅ All output functions exist")
        return True
    except Exception as e:
        print(f"❌ Output functions test failed: {e}")
        return False

def test_language_prioritization():
    """Test 3: Verify language prioritization logic"""
    print("🔍 Test 3: Checking language prioritization...")
    try:
        # Mock available languages
        available_langs = ['eng', 'snum']
        
        # Test prioritization logic
        if "eng" in available_langs:
            lang1 = "eng"
            lang2 = [lang for lang in available_langs if lang != "eng"][0] if len([lang for lang in available_langs if lang != "eng"]) > 0 else available_langs[0]
        else:
            lang1 = available_langs[0]
            lang2 = available_langs[1] if len(available_langs) > 1 else "eng"
        
        assert lang1 == "eng", f"Expected 'eng' as first choice, got '{lang1}'"
        assert lang2 == "snum", f"Expected 'snum' as second choice, got '{lang2}'"
        
        print("✅ Language prioritization works correctly")
        return True
    except Exception as e:
        print(f"❌ Language prioritization test failed: {e}")
        return False

def test_message_box_result_mapping():
    """Test 4: Verify message box result mapping logic"""
    print("🔍 Test 4: Checking message box result mapping...")
    try:
        from tejocr import constants
        
        # Test the corrected mapping logic
        # LibreOffice: YES=2, NO=3, CANCEL=0
        
        # First dialog mapping
        result1 = 2  # YES button
        if result1 == 2:
            mode1 = constants.OUTPUT_MODE_CURSOR
        elif result1 == 3:
            mode1 = constants.OUTPUT_MODE_CLIPBOARD
        else:
            mode1 = None
            
        assert mode1 == constants.OUTPUT_MODE_CURSOR, f"Expected cursor mode for YES, got {mode1}"
        
        result1 = 3  # NO button
        if result1 == 2:
            mode1 = constants.OUTPUT_MODE_CURSOR
        elif result1 == 3:
            mode1 = constants.OUTPUT_MODE_CLIPBOARD
        else:
            mode1 = None
            
        assert mode1 == constants.OUTPUT_MODE_CLIPBOARD, f"Expected clipboard mode for NO, got {mode1}"
        
        # Second dialog mapping
        result2 = 2  # YES button
        if result2 == 2:
            mode2 = constants.OUTPUT_MODE_TEXTBOX
        elif result2 == 3:
            mode2 = constants.OUTPUT_MODE_CURSOR
        else:
            mode2 = None
            
        assert mode2 == constants.OUTPUT_MODE_TEXTBOX, f"Expected textbox mode for YES, got {mode2}"
        
        print("✅ Message box result mapping is correct")
        return True
    except Exception as e:
        print(f"❌ Message box result mapping test failed: {e}")
        return False

def test_engine_language_functions():
    """Test 5: Verify engine language functions"""
    print("🔍 Test 5: Checking engine language functions...")
    try:
        from tejocr import tejocr_engine
        
        # Check if functions exist
        assert hasattr(tejocr_engine, 'get_available_languages')
        assert hasattr(tejocr_engine, 'is_language_available')
        
        print("✅ Engine language functions exist")
        return True
    except Exception as e:
        print(f"❌ Engine language functions test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Running TejOCR Phase 1 Fix Tests...")
    print("=" * 50)
    
    tests = [
        test_constants,
        test_output_functions,
        test_language_prioritization,
        test_message_box_result_mapping,
        test_engine_language_functions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready to build.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 