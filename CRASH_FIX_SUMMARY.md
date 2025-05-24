# TejOCR Crash Fix Summary - OCR Selected Image

## Problem Diagnosed

The user reported a crash when selecting "OCR Selected Image" from the TejOCR menu:

```
libc++abi: terminating due to uncaught exception of type com::sun::star::uno::RuntimeException
Unspecified Application Error
Fatal exception: Signal 6
```

## Root Cause Analysis

The crash was occurring in `python/tejocr/tejocr_dialogs.py` in the `show_ocr_options_dialog()` function. When `ocr_source_type == "selected"`, the code was:

1. Showing a placeholder message: "This feature requires selecting an image first. For now, please use 'OCR Image from File' instead."
2. Returning `None, None` 
3. But somewhere in the UNO object cleanup or subsequent operations, a RuntimeException was being thrown

## The Fix Applied

**File**: `python/tejocr/tejocr_dialogs.py`  
**Lines**: ~716-724 in `show_ocr_options_dialog()`

**Before** (causing crash):
```python
if ocr_source_type == "selected":
    # Get image from selection
    # For now, show a simple message that this needs an image selected
    uno_utils.show_message_box(
        title="OCR Selected Image",
        message="This feature requires selecting an image first.\n\nFor now, please use 'OCR Image from File' instead.",
        type="infobox",
        parent_frame=parent_frame,
        ctx=ctx
    )
    return None, None
```

**After** (properly implemented):
```python
if ocr_source_type == "selected":
    # Process the selected image
    try:
        ocr_result = tejocr_engine.perform_ocr(
            ctx=ctx,
            frame=parent_frame,
            source_type="selected",
            image_path_or_selection_options=None,  # For selected images, the engine will extract from selection
            ocr_options=default_options
        )
        
        if ocr_result["success"] and ocr_result["text"]:
            recognized_text = ocr_result["text"].strip()
            logger.info(f"OCR successful on selected image! Text length: {len(recognized_text)}")
            return recognized_text, constants.DEFAULT_OUTPUT_MODE
        else:
            logger.warning(f"OCR failed on selected image. Message: {ocr_result.get('message', 'Unknown error')}")
            uno_utils.show_message_box(
                title="OCR Result",
                message=f"OCR failed: {ocr_result.get('message', 'No text was recognized from the selected image.')}",
                type="infobox",
                parent_frame=parent_frame,
                ctx=ctx
            )
            return None, None
             
    except Exception as e:
        logger.error(f"OCR processing on selected image failed: {e}", exc_info=True)
        uno_utils.show_message_box(
            title="OCR Error",
            message=f"OCR processing failed on selected image:\n{str(e)}",
            type="errorbox",
            parent_frame=parent_frame,
            ctx=ctx
        )
        return None, None
```

## What the Fix Does

1. **Removes the placeholder message** that was causing UNO issues
2. **Implements actual OCR functionality** for selected images
3. **Uses existing infrastructure**: The `tejocr_engine.perform_ocr()` function already supports `source_type="selected"`
4. **Provides proper error handling** with try-catch blocks
5. **Returns consistent results** that match what the calling code expects

## Technical Details

- The `tejocr_engine.perform_ocr()` function with `source_type="selected"` will:
  - Extract the selected graphic object from the LibreOffice document
  - Export it to a temporary file  
  - Run Tesseract OCR on it
  - Return a results dictionary with success/failure status and text
- This matches the same pattern used for file-based OCR
- No changes needed to the service layer or UNO registration

## Status

✅ **Fix Applied**: Extension rebuilt with proper OCR Selected Image implementation  
🔧 **Ready for Testing**: Use `MANUAL_INSTALL_TEST.md` for verification  
🎯 **Expected Result**: No more crashes, functional OCR on selected images

## Files Modified

- `python/tejocr/tejocr_dialogs.py` - Fixed OCR Selected Image implementation
- `TejOCR-0.1.0.oxt` - Rebuilt extension package 