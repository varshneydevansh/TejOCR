#!/usr/bin/env python3
"""Test Phase 1 Critical Error Fixes for TejOCR Extension."""

import sys
import os

# Add the python path for TejOCR
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

def test_missing_constants():
    """Test that all required constants are now defined."""
    print("Testing missing constants...")
    
    from tejocr import constants
    
    # Test CFG_KEY_IMPROVE_IMAGE_DEFAULT exists
    assert hasattr(constants, 'CFG_KEY_IMPROVE_IMAGE_DEFAULT'), "CFG_KEY_IMPROVE_IMAGE_DEFAULT missing"
    assert constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT == "DefaultImproveImageQuality", f"Unexpected value: {constants.CFG_KEY_IMPROVE_IMAGE_DEFAULT}"
    
    # Test DEFAULT_IMPROVE_IMAGE exists  
    assert hasattr(constants, 'DEFAULT_IMPROVE_IMAGE'), "DEFAULT_IMPROVE_IMAGE missing"
    assert constants.DEFAULT_IMPROVE_IMAGE is False, f"Expected False, got {constants.DEFAULT_IMPROVE_IMAGE}"
    
    print("✅ All missing constants are now defined correctly")

def test_output_mode_constants():
    """Test that output mode constants are consistent."""
    print("Testing output mode constants...")
    
    from tejocr import constants
    
    # Verify constants exist and have expected values
    assert constants.OUTPUT_MODE_CURSOR == "at_cursor", f"Expected 'at_cursor', got {constants.OUTPUT_MODE_CURSOR}"
    assert constants.OUTPUT_MODE_CLIPBOARD == "to_clipboard", f"Expected 'to_clipboard', got {constants.OUTPUT_MODE_CLIPBOARD}"
    assert constants.OUTPUT_MODE_TEXTBOX == "new_textbox", f"Expected 'new_textbox', got {constants.OUTPUT_MODE_TEXTBOX}"
    assert constants.OUTPUT_MODE_REPLACE == "replace_image", f"Expected 'replace_image', got {constants.OUTPUT_MODE_REPLACE}"
    
    assert constants.DEFAULT_OUTPUT_MODE == constants.OUTPUT_MODE_CURSOR, f"Default should be cursor mode"
    
    print("✅ Output mode constants are consistent")

def test_dialog_class_imports():
    """Test that interactive dialog classes can be imported."""
    print("Testing interactive dialog class imports...")
    
    from tejocr import tejocr_interactive_dialogs
    
    # Test that the handler classes exist
    assert hasattr(tejocr_interactive_dialogs, 'InteractiveSettingsDialogHandler'), "InteractiveSettingsDialogHandler missing"
    assert hasattr(tejocr_interactive_dialogs, 'InteractiveOptionsDialogHandler'), "InteractiveOptionsDialogHandler missing"
    
    # Test main functions exist
    assert hasattr(tejocr_interactive_dialogs, 'show_interactive_settings_dialog'), "show_interactive_settings_dialog missing"
    assert hasattr(tejocr_interactive_dialogs, 'show_interactive_ocr_options_dialog'), "show_interactive_ocr_options_dialog missing"
    
    print("✅ Interactive dialog classes can be imported")

def test_uno_utils_constants():
    """Test that uno_utils has required constants."""
    print("Testing uno_utils constants...")
    
    from tejocr import uno_utils
    
    # Test button constants exist
    assert hasattr(uno_utils, 'OK_BUTTON'), "OK_BUTTON missing from uno_utils"
    assert hasattr(uno_utils, 'CANCEL_BUTTON'), "CANCEL_BUTTON missing from uno_utils"
    
    assert uno_utils.OK_BUTTON == 1, f"Expected OK_BUTTON=1, got {uno_utils.OK_BUTTON}"
    assert uno_utils.CANCEL_BUTTON == 0, f"Expected CANCEL_BUTTON=0, got {uno_utils.CANCEL_BUTTON}"
    
    print("✅ uno_utils constants are defined correctly")

def test_output_module_functions():
    """Test that output module has required functions."""
    print("Testing output module functions...")
    
    from tejocr import tejocr_output
    
    # Test core output functions exist
    assert hasattr(tejocr_output, 'handle_ocr_output'), "handle_ocr_output missing"
    assert hasattr(tejocr_output, 'insert_text_at_cursor'), "insert_text_at_cursor missing"
    assert hasattr(tejocr_output, 'copy_text_to_clipboard'), "copy_text_to_clipboard missing"
    assert hasattr(tejocr_output, 'create_text_box'), "create_text_box missing"
    
    print("✅ Output module functions are available")

def test_engine_functions():
    """Test that engine module has required functions."""
    print("Testing engine module functions...")
    
    from tejocr import tejocr_engine
    
    # Test core engine functions exist
    assert hasattr(tejocr_engine, 'is_tesseract_ready'), "is_tesseract_ready missing"
    assert hasattr(tejocr_engine, 'find_tesseract_executable'), "find_tesseract_executable missing"
    assert hasattr(tejocr_engine, 'get_available_languages'), "get_available_languages missing"
    assert hasattr(tejocr_engine, 'perform_ocr_on_image'), "perform_ocr_on_image missing"
    
    print("✅ Engine module functions are available")

def run_all_tests():
    """Run all Phase 1 critical error fixes tests."""
    print("=" * 60)
    print("TejOCR Phase 1 Critical Error Fixes Test Suite")
    print("=" * 60)
    
    tests = [
        test_missing_constants,
        test_output_mode_constants, 
        test_dialog_class_imports,
        test_uno_utils_constants,
        test_output_module_functions,
        test_engine_functions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print(f"Phase 1 Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("🎉 Phase 1 critical error fixes are complete!")
        return True
    else:
        print("⚠️  Some Phase 1 fixes still need work")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 