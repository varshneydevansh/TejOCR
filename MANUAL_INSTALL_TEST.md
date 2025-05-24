# Manual Installation Test for Fixed Extension

## Installation Steps

1. LibreOffice should now be running
2. Go to **Tools > Extension Manager**
3. Click **Add** button
4. Navigate to and select: `/Users/devanshvarshney/TejOCR/TejOCR-0.1.0.oxt`
5. Click **Open** and follow installation prompts
6. Restart LibreOffice Writer

## Testing the Fixed OCR Selected Image

### Test Case 1: OCR from Selected Image
1. Insert an image with text into your Writer document:
   - Go to **Insert > Image > From File**
   - Choose any image file with text (PNG, JPG, etc.)
2. **Select the inserted image** by clicking on it
3. Go to **TejOCR > OCR Selected Image**
4. **Expected Result**: Should show confirmation dialog and perform OCR without crashing
5. **Previous Bug**: Would crash with RuntimeException

### Test Case 2: OCR from File (should still work)
1. Go to **TejOCR > OCR Image from File...**
2. Select an image file with text
3. **Expected Result**: Should work as before

## What Was Fixed

The crash was happening because the "OCR Selected Image" function was showing a placeholder message saying "use file instead" but then trying to access UNO objects that caused a RuntimeException.

The fix implements proper selected image OCR by:
1. Calling `tejocr_engine.perform_ocr()` with `source_type="selected"`
2. The engine extracts the image from the current selection
3. Performs OCR and returns results properly
4. No more placeholder messages that lead to crashes

## Expected Log Output (if running from terminal)

You should see logs like:
```
CONSOLE DEBUG: dispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRSelectedImage
CONSOLE DEBUG: Found action for URL 'uno:org.libreoffice.TejOCR.OCRSelectedImage', executing...
INFO: OCR successful on selected image! Text length: [number]
```

And **NO MORE** crash with:
```
libc++abi: terminating due to uncaught exception of type com::sun::star::uno::RuntimeException
``` 