# TejOCR Extension - Testing Instructions

## Critical Fixes Applied

The following critical fixes have been applied to resolve the UI functionality issues:

### 1. **ProtocolHandler.xcu** (NEW FILE)
- **Purpose**: Explicitly registers the TejOCRService as the handler for `uno:org.libreoffice.TejOCR.*` protocol URLs
- **Why needed**: LibreOffice needs explicit registration to know which service handles which protocol patterns
- **File location**: `ProtocolHandler.xcu` (root level)

### 2. **Addons.xcu** (FIXED)
- **Menu structure**: Changed `oor:op="fuse"` to `oor:op="replace"` for cleaner registration
- **Toolbar integration**: Fixed `OfficeToolbarMerging` structure with correct properties:
  - `MergeToolBar`: Changed from `private:resource/toolbar/standardbar` to `standardbar`
  - Added `MergePoint`, `MergeCommand` properties for proper integration
- **Separator**: Fixed separator definition with proper `Type` property

### 3. **META-INF/manifest.xml** (UPDATED)
- Added `ProtocolHandler.xcu` entry
- Fixed malformed entries

### 4. **Enhanced Debugging** (tejocr_service.py)
- Added console output to `queryDispatch`, `dispatch`, and `addStatusListener` methods
- These will appear in terminal output for verification

## Testing Steps

### Step 1: Rebuild and Install Extension

```bash
# 1. Rebuild the extension
python build.py

# 2. Remove old extension (if installed)
# In LibreOffice: Tools → Extension Manager → Select TejOCR → Remove

# 3. Install new extension
# In LibreOffice: Tools → Extension Manager → Add → Select new .oxt file

# 4. Restart LibreOffice completely
```

### Step 2: Launch LibreOffice from Terminal

**Critical**: Launch LibreOffice from terminal to see debug output:

```bash
# On macOS:
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer

# On Linux:
libreoffice --writer

# On Windows:
"C:\Program Files\LibreOffice\program\soffice.exe" --writer
```

### Step 3: Verify Menu Functionality

1. **Open a Writer document**
2. **Check menu appearance**:
   - Menu "TejOCR" should be visible in the main menu bar
   - Click on "TejOCR" menu - it should expand showing 3 items

3. **Check menu item status**:
   - All items should now be **ENABLED** (not grayed out)
   - You should see console output like:
     ```
     CONSOLE DEBUG: addStatusListener CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
     CONSOLE DEBUG: Status for uno:org.libreoffice.TejOCR.OCRImageFromFile: IsEnabled=True
     ```

4. **Test menu item clicks**:
   - Click "OCR Image from File..." 
   - You should see console output like:
     ```
     CONSOLE DEBUG: queryDispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
     CONSOLE DEBUG: queryDispatch MATCHED URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', returning self
     CONSOLE DEBUG: dispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
     CONSOLE DEBUG: Found action for URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', executing...
     ```

### Step 4: Verify Toolbar Integration

1. **Check toolbar button**:
   - The TejOCR button should now appear on the **standard toolbar** (not in a separate floating window)
   - It should be positioned after the Zoom control or at the end of the toolbar

2. **Test toolbar button click**:
   - Click the toolbar button
   - Should see similar console debug output as menu items

### Step 5: Test Full OCR Workflow

1. **Insert an image** in the Writer document
2. **Select the image**
3. **Use "OCR Selected Image"** - should be enabled when image is selected
4. **Test the complete dialog workflow**

## Expected Console Output

When the fix is working correctly, you should see output like this in the terminal:

```
CONSOLE DEBUG: addStatusListener CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
CONSOLE DEBUG: Status for uno:org.libreoffice.TejOCR.OCRImageFromFile: IsEnabled=True
CONSOLE DEBUG: Status event sent to listener for uno:org.libreoffice.TejOCR.OCRImageFromFile

CONSOLE DEBUG: queryDispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
CONSOLE DEBUG: queryDispatch MATCHED URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', returning self

CONSOLE DEBUG: dispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
CONSOLE DEBUG: Found action for URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', executing...
```

## Troubleshooting

### If Menu Items Are Still Grayed Out:
1. Check terminal for any error messages
2. Verify ProtocolHandler.xcu is included in the OXT package
3. Ensure LibreOffice was completely restarted after installing the new extension

### If No Console Debug Output:
1. The service might not be loading - check for Python errors in terminal
2. The ProtocolHandler.xcu registration might not be working
3. Try removing and reinstalling the extension

### If Toolbar Button Still Detached:
1. Check for configmgr warnings in terminal output
2. The toolbar merging configuration might need adjustment
3. Try closing/reopening Writer documents

## Configuration Warnings to Watch For

These warnings should now be **RESOLVED**:
- ❌ `warn:configmgr: ignoring modify of unknown set member node "standardbar"`
- ❌ Menu items being grayed out/disabled
- ❌ No `queryDispatch` calls being logged

## Success Criteria

✅ **Menu items are enabled and clickable**
✅ **Console debug output appears when clicking menu items**
✅ **Toolbar button appears on standard toolbar**
✅ **No configmgr warnings about unknown nodes**
✅ **Full OCR workflow functions correctly**

## Log File Location

In addition to console output, detailed logs are written to:
- **Linux/macOS**: `/tmp/TejOCRLogs/tejocr.log`
- **Windows**: `%TEMP%\TejOCRLogs\tejocr.log`

Check this file for detailed information about service initialization and operations. 