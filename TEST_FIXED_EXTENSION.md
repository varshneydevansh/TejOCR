# TejOCR Extension - CRITICAL FIXES APPLIED - TESTING GUIDE

## ✅ CRITICAL ISSUES FIXED

### 1. **ImportError Resolution**
- **Problem**: `ImportError: No module named 'com'` in `tejocr_dialogs.py` and `tejocr_output.py`
- **Root Cause**: Module-level com.sun.star imports failing during Python-UNO bridge initialization
- **Fix Applied**: 
  - Wrapped all com.sun.star imports in try-catch blocks with fallbacks
  - Added progressive import attempts (uno module first, then com.sun.star)
  - Added dummy classes to prevent module loading failures

### 2. **Safe Import Strategy**
- `tejocr_dialogs.py`: Fixed XActionListener, XItemListener imports
- `tejocr_output.py`: Fixed XTextDocument, XTransferable, DataFlavor imports
- All imports now have debug output and graceful fallbacks

## 🧪 TESTING INSTRUCTIONS

### Step 1: Clean Installation

```bash
# 1. Remove old extension completely
# In LibreOffice: Tools → Extension Manager → Select TejOCR → Remove

# 2. Install the new extension
# In LibreOffice: Tools → Extension Manager → Add → Select TejOCR-0.1.0.oxt

# 3. Restart LibreOffice COMPLETELY (quit all instances)
```

### Step 2: Launch with Terminal Debugging

**CRITICAL**: Always launch LibreOffice from terminal to see debug output:

```bash
# On macOS:
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer --norestore

# Expected DEBUG output on successful fix:
# DEBUG: tejocr_service.py: Script execution started (top level)
# DEBUG: tejocr_service.py: Added '...' to sys.path.
# DEBUG: tejocr_service.py: uno, unohelper imported.
# DEBUG: tejocr_service.py: com.sun.star imports successful.
# INFO: Logger 'TejOCR.uno_utils' FileHandler configured
# DEBUG: tejocr_service.py: Logger initialized.
```

### Step 3: Verify Service Loading

Look for these SUCCESS indicators in terminal output:

```bash
✅ SUCCESS: tejocr_service.py: All 'from tejocr import ...' imports successful.
✅ SUCCESS: tejocr_service.py: Logger initialized.
✅ SUCCESS: TejOCRService ADDED to ImplementationHelper
```

**NO LONGER SHOULD SEE**:
```bash
❌ ImportError: No module named 'com'
❌ IMPORT ERROR during initial imports
❌ Could not import XActionListener, XItemListener
```

### Step 4: Test Menu Functionality

1. **Open Writer document**
2. **Check menu appearance**:
   - "TejOCR" menu should be visible in menu bar
   - Click "TejOCR" → Should expand with 3 items

3. **Test menu status** (with terminal open):
   - You should see debug output like:
   ```bash
   CONSOLE DEBUG: addStatusListener CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
   CONSOLE DEBUG: Status for uno:org.libreoffice.TejOCR.OCRImageFromFile: IsEnabled=True
   ```

4. **Test menu clicks**:
   - Click "OCR Image from File..."
   - Should see:
   ```bash
   CONSOLE DEBUG: queryDispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
   CONSOLE DEBUG: queryDispatch MATCHED URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', returning self
   CONSOLE DEBUG: dispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
   CONSOLE DEBUG: Found action for URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', executing...
   ```

### Step 5: Test Lazy Module Loading

When you click a menu item for the first time, you should see:

```bash
DEBUG: tejocr_dialogs.py: Right before UNO interface imports. uno module: <module 'uno'...>
DEBUG: tejocr_dialogs.py: Successfully imported XActionListener, XItemListener from uno module
DEBUG: tejocr_dialogs.py: Successfully imported XJobExecutor
DEBUG: tejocr_output.py: Attempting UNO interface imports...
DEBUG: tejocr_output.py: Successfully imported text interfaces
DEBUG: tejocr_output.py: Successfully imported XNamed
DEBUG: tejocr_output.py: Successfully imported datatransfer interfaces
DEBUG: tejocr_output.py: Successfully imported XClipboard
```

## 🔍 DIAGNOSTIC CHECKLIST

### ✅ Success Indicators:
- [ ] No ImportError messages in terminal
- [ ] TejOCR menu appears and expands
- [ ] Menu items are **ENABLED** (not grayed out)
- [ ] Clicking menu items shows debug output
- [ ] "Successfully imported" messages for all interfaces
- [ ] Log file created at `/tmp/TejOCRLogs/tejocr.log`

### ❌ Failure Indicators:
- [ ] ImportError messages still appearing
- [ ] Menu items remain grayed out
- [ ] No debug output when clicking menu items
- [ ] "Could not import" or "CRITICAL" error messages

## 🚨 IF ISSUES PERSIST

### 1. Check Log File
```bash
# View detailed logs:
tail -f /tmp/TejOCRLogs/tejocr.log

# Or check full log:
cat /tmp/TejOCRLogs/tejocr.log
```

### 2. Clean Profile Test
If issues persist, test with a clean LibreOffice profile:

```bash
# Create clean profile for testing:
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer --norestore -env:UserInstallation=file:///tmp/lo_test_profile

# Install extension in clean profile and test
```

### 3. Verify Extension Structure
```bash
# Check if extension files are correctly packaged:
unzip -l TejOCR-0.1.0.oxt | grep -E "(Addons\.xcu|ProtocolHandler\.xcu|tejocr_service\.py)"
```

## 📊 EXPECTED RESULTS

After applying these fixes:

1. **Service Loading**: ✅ Python service loads without ImportError
2. **Menu Registration**: ✅ TejOCR menu appears with all items enabled
3. **Dispatch Handling**: ✅ Menu clicks trigger proper dispatch calls
4. **Module Loading**: ✅ Dialogs and output modules load on-demand without errors
5. **Full Functionality**: ✅ OCR workflow should complete successfully

## 🎯 NEXT STEPS

Once menu items are enabled and clicking:

1. Test full OCR workflow with actual images
2. Verify settings dialog functionality
3. Test all output modes (cursor, textbox, replace, clipboard)
4. Confirm toolbar button integration
5. Test multilingual support

The ImportError fix is the **critical foundation** - everything else should work once this is resolved. 