 # This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile

# Add the parent directory of 'python' to sys.path to allow sibling imports if necessary
# This is often needed when running tests directly if the project isn't installed as a package.
import sys
# Assuming this test file is in tests/ and the code is in python/tejocr/
# We need to go up one level from tests/ to TejOCR.oxt/, then into python/
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # Goes to TejOCR.oxt/
sys.path.insert(0, os.path.join(project_root, 'python'))

from tejocr import tejocr_engine
from tejocr import constants
from tejocr import uno_utils # For things like create_temp_file, though it might also need mocks

# Mock the logger used within tejocr_engine and other modules if it's called during tests
# This prevents log file creation during tests unless specifically intended.
@patch('tejocr.uno_utils.get_logger')
class TestTejocrEngine(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test files if needed
        self.test_dir = tempfile.TemporaryDirectory()
        self.mock_ctx = MagicMock() # Mock for UNO context
        self.mock_frame = MagicMock() # Mock for LO frame

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('tejocr.tejocr_engine.PILLOW_AVAILABLE', True)
    @patch('tejocr.tejocr_engine.Image') # Mock Pillow's Image module
    def test_preprocess_image_grayscale(self, MockImage, mock_logger):
        mock_img_instance = MockImage.open.return_value
        mock_img_instance.format = 'PNG'
        
        # Create a dummy input image path
        dummy_image_path = os.path.join(self.test_dir.name, "test.png")
        with open(dummy_image_path, 'w') as f: f.write("dummy_content")

        processed_path = tejocr_engine._preprocess_image(dummy_image_path, grayscale=True)
        
        MockImage.open.assert_called_once_with(dummy_image_path)
        mock_img_instance.ImageOps.grayscale.assert_called_once()
        mock_img_instance.save.assert_called_once()
        self.assertNotEqual(processed_path, dummy_image_path) # Should save to a new file
        self.assertTrue(os.path.exists(processed_path))

    @patch('tejocr.tejocr_engine.PILLOW_AVAILABLE', True)
    @patch('tejocr.tejocr_engine.Image')
    def test_preprocess_image_binarize_otsu_placeholder(self, MockImage, mock_logger):
        mock_img_instance = MockImage.open.return_value
        mock_img_instance.format = 'JPEG'
        mock_gray_img = MagicMock()
        mock_img_instance.ImageOps.grayscale.return_value = mock_gray_img

        dummy_image_path = os.path.join(self.test_dir.name, "test.jpg")
        with open(dummy_image_path, 'w') as f: f.write("dummy_content")

        processed_path = tejocr_engine._preprocess_image(dummy_image_path, binarize_method='otsu')

        MockImage.open.assert_called_once_with(dummy_image_path)
        # It should grayscale first (even if grayscale=False, binarize='otsu' implies it)
        mock_img_instance.ImageOps.grayscale.assert_called_once()
        mock_gray_img.convert.assert_called_with('1') # Check that basic bilevel conversion is called
        mock_img_instance.save.assert_called_once()
        self.assertNotEqual(processed_path, dummy_image_path)
        self.assertTrue(os.path.exists(processed_path))

    @patch('tejocr.tejocr_engine.PILLOW_AVAILABLE', False)
    def test_preprocess_image_pillow_not_available(self, mock_logger):
        dummy_image_path = "test_path.png"
        processed_path = tejocr_engine._preprocess_image(dummy_image_path, grayscale=True)
        self.assertEqual(processed_path, dummy_image_path) # Should return original path

    @patch('tejocr.tejocr_engine.pytesseract')
    @patch('tejocr.uno_utils.find_tesseract_executable')
    def test_check_tesseract_path_success(self, mock_find_tess_exec, mock_pytesseract, mock_logger):
        mock_find_tess_exec.return_value = "/usr/bin/tesseract" # Mock a found path
        mock_pytesseract.get_tesseract_version.return_value = "5.0.0"
        
        result = tejocr_engine.check_tesseract_path("ignored_path", self.mock_ctx, self.mock_frame, show_success=True)
        
        self.assertTrue(result)
        mock_find_tess_exec.assert_called_once_with("ignored_path", self.mock_ctx)
        mock_pytesseract.get_tesseract_version.assert_called_once()
        # Check if show_message_box was called (indirectly, via uno_utils)
        # This requires uno_utils.show_message_box to be mockable or to check logger output

    @patch('tejocr.tejocr_engine.pytesseract')
    @patch('tejocr.uno_utils.find_tesseract_executable')
    @patch('tejocr.uno_utils.show_message_box') # Mock show_message_box directly
    def test_check_tesseract_path_not_found(self, mock_show_msg_box, mock_find_tess_exec, mock_pytesseract, mock_logger):
        mock_find_tess_exec.return_value = None # Tesseract not found by helper
        
        result = tejocr_engine.check_tesseract_path(None, self.mock_ctx, self.mock_frame)
        
        self.assertFalse(result)
        mock_show_msg_box.assert_called_once() # Should show a message

    @patch('tejocr.tejocr_engine.pytesseract')
    @patch('tejocr.uno_utils.find_tesseract_executable')
    @patch('tejocr.uno_utils.show_message_box')
    def test_check_tesseract_path_pytesseract_error(self, mock_show_msg_box, mock_find_tess_exec, mock_pytesseract, mock_logger):
        mock_find_tess_exec.return_value = "/fake/tesseract"
        mock_pytesseract.get_tesseract_version.side_effect = pytesseract.TesseractNotFoundError
        
        result = tejocr_engine.check_tesseract_path("/fake/tesseract", self.mock_ctx, self.mock_frame)
        
        self.assertFalse(result)
        # Potentially two calls: one from find_tesseract_executable if path invalid, one from check_tesseract_path itself
        self.assertGreaterEqual(mock_show_msg_box.call_count, 1) 

    # More tests needed for perform_ocr
    # These are more complex due to dependencies on _get_image_from_selection, _preprocess_image,
    # pytesseract.image_to_string, and file operations.
    # We'd need to mock these extensively.

    @patch('tejocr.tejocr_engine.PYTESSERACT_AVAILABLE', True)
    @patch('tejocr.tejocr_engine.check_tesseract_path', return_value=True) # Assume Tesseract is OK
    @patch('tejocr.tejocr_engine._get_image_from_selection')
    @patch('tejocr.tejocr_engine._preprocess_image', side_effect=lambda x, *args, **kwargs: x) # Bypass preprocessing
    @patch('tejocr.tejocr_engine.pytesseract.image_to_string')
    @patch('tejocr.tejocr_engine.Image.open') # Mock PIL.Image.open
    def test_perform_ocr_selected_image_success(self, mock_pil_image_open, mock_image_to_string, mock_preprocess, mock_get_selection, mock_check_tess, mock_logger):
        mock_get_selection.return_value = "/tmp/selected_image.png"
        mock_image_to_string.return_value = "Recognized Text"
        mock_pil_image_open.return_value = MagicMock() # Return a mock image object

        ocr_options = {
            'lang': 'eng', 'psm': constants.DEFAULT_PSM_MODE, 'oem': constants.DEFAULT_OEM_MODE,
            'grayscale': False, 'binarize': False
        }
        result = tejocr_engine.perform_ocr(self.mock_ctx, self.mock_frame, 'selected', None, ocr_options)

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Recognized Text")
        mock_get_selection.assert_called_once_with(self.mock_frame, self.mock_ctx)
        mock_preprocess.assert_called_once_with("/tmp/selected_image.png", False, None)
        mock_image_to_string.assert_called_once()

    @patch('tejocr.tejocr_engine.PYTESSERACT_AVAILABLE', True)
    @patch('tejocr.tejocr_engine.check_tesseract_path', return_value=True)
    @patch('os.path.isfile', return_value=True) # Assume image_path is a valid file
    @patch('tejocr.tejocr_engine._preprocess_image', side_effect=lambda x, *args, **kwargs: x)
    @patch('tejocr.tejocr_engine.pytesseract.image_to_string')
    @patch('tejocr.tejocr_engine.Image.open')
    def test_perform_ocr_file_success(self, mock_pil_image_open, mock_image_to_string, mock_preprocess, mock_isfile, mock_check_tess, mock_logger):
        test_image_path = "/path/to/user_image.png"
        mock_image_to_string.return_value = "Text From File"
        mock_pil_image_open.return_value = MagicMock()

        ocr_options = {
            'lang': 'deu', 'psm': '1', 'oem': '1',
            'grayscale': True, 'binarize': True
        }
        result = tejocr_engine.perform_ocr(self.mock_ctx, self.mock_frame, 'file', test_image_path, ocr_options)

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "Text From File")
        mock_preprocess.assert_called_once_with(test_image_path, True, 'otsu') # Binarize True maps to 'otsu'
        mock_image_to_string.assert_called_once()

    @patch('tejocr.tejocr_engine.PYTESSERACT_AVAILABLE', False) # Test when pytesseract is globally unavailable
    def test_perform_ocr_pytesseract_not_available(self, mock_logger):
        result = tejocr_engine.perform_ocr(self.mock_ctx, self.mock_frame, 'file', 'dummy.png', {})
        self.assertFalse(result["success"])
        self.assertIn("Pytesseract library not installed", result["message"])

    @patch('tejocr.tejocr_engine.PYTESSERACT_AVAILABLE', True)
    @patch('tejocr.tejocr_engine.check_tesseract_path', return_value=False) # Tesseract check fails
    def test_perform_ocr_tesseract_check_fails(self, mock_check_tess, mock_logger):
        result = tejocr_engine.perform_ocr(self.mock_ctx, self.mock_frame, 'file', 'dummy.png', {})
        self.assertFalse(result["success"])
        self.assertIn("Tesseract not found or not working", result["message"])

    # TODO: Add tests for perform_ocr failures (e.g., image extraction fails, pytesseract.image_to_string raises error)

if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # Ensure that the imports at the top correctly adjust sys.path
    # You might need to run as `python -m tests.test_tejocr_engine` from project root
    # or ensure TejOCR.oxt/python is in PYTHONPATH
    unittest.main()
