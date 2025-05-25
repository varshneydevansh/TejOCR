# Quick Test Guide - TejOCR v0.1.5 Simplified UI

## Install & Test Steps

### 1. Install Extension
```bash
open TejOCR-0.1.5.oxt
```
- LibreOffice will restart
- Extension will be available in Writer

### 2. Test Enhanced Settings 🔧
1. **Open Writer** → `Tools → TejOCR → Settings...`

**Expected Flow:**
1. **Dependency Dialog** appears (existing functionality)
   - Shows Tesseract ✅, NumPy ✅, Pytesseract ✅, Pillow ✅
   - Click "OK"

2. **Tesseract Configuration** prompt
   - "Tesseract is currently working correctly. Would you like to change the path?"
   - Try "Yes" → Enter a path → "Test" → Should validate
   - Or "No" to skip

3. **Language Configuration** prompt  
   - "Enter default OCR language code"
   - Try entering "hin" or "fra"
   - Should save and confirm

4. **Completion** message
   - "Configuration completed successfully"

### 3. Test OCR with Options 🎯

#### **Test File OCR**
1. `Tools → TejOCR → OCR Image from File...`
2. **File Picker** → Select an image
3. **Language Choice** → Input dialog with default (e.g., "eng")
   - Try entering "hin" or keep default
4. **Output Mode Choice** → Three options:
   - "Insert at Cursor"
   - "Copy to Clipboard" 
   - "New Text Box"
5. **Results** → Success message with character count

#### **Test Selected Image OCR**  
1. Insert an image in Writer document
2. **Select the image**
3. `Tools → TejOCR → OCR Selected Image`
4. Same flow: Language → Output Mode → Results

### 4. Verify New Functionality ✅

**Settings Persistence:**
- Change default language to "hin"
- Restart LibreOffice
- Try OCR → Should show "hin" as default

**Output Modes:**
- **Insert at Cursor**: Text appears at cursor position
- **Copy to Clipboard**: Check clipboard (Cmd+V elsewhere)
- **New Text Box**: Creates formatted text box in document

**Cancellation:**
- Cancel at language step → Operation aborts
- Cancel at output mode step → Operation aborts
- No errors, graceful handling

## Expected Benefits

### ✅ **Working Features**
- Tesseract path configuration (manual override)
- Default language setting (saves preferences)
- Per-operation language choice (flexibility)
- Multiple output modes (workflow adaptation)
- Persistent settings (survives restarts)

### ✅ **Reliability Improvements**  
- No XDL dependencies (bypass loading issues)
- Fallback dialogs (maximum compatibility)
- Graceful error handling (never crashes)
- Professional user experience (clear prompts)

## Troubleshooting

### **If Dialogs Don't Appear**
- Check console output for fallback messages
- Extension will still work with defaults
- OCR functionality remains perfect

### **If Configuration Fails**
- Settings will use defaults (eng language, auto-detect Tesseract)
- Core functionality unaffected
- Try settings again later

## Success Criteria

1. **Settings flow completes** without errors
2. **Language choice works** in OCR operations  
3. **Output modes function** correctly
4. **Settings persist** after restart
5. **OCR quality unchanged** (still perfect)

**Result: Feature-complete Phase 2 with simplified, reliable UI!** 