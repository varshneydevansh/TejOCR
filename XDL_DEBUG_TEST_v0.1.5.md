# XDL Dialog Loading Debug Test - TejOCR v0.1.5

## What We're Testing

**Goal**: Identify the correct URL scheme for loading XDL dialogs in your LibreOffice environment

**Problem**: Even the ultra-minimal `test_dialog.xdl` fails to load with `private:dialogs/test_dialog.xdl`

## Current Test Setup

### Multiple URL Schemes Test
The extension now tests **4 different URL schemes** in sequence:

1. `private:dialogs/test_dialog.xdl` (Standard)
2. `vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/test_dialog.xdl` (Extension-specific)
3. `private:resource/dialogs/test_dialog.xdl` (Alternative private scheme)
4. `dialogs/test_dialog.xdl` (Relative path)

### Improved Test Dialog
**File**: `dialogs/test_dialog.xdl`
- **Size**: 250x100 for better visibility
- **Content**: Clear success message "XDL Dialog Loading Test Successful!"
- **Proper attributes**: `dlg:button-type="ok"` and `dlg:align="center"`

### Enhanced Logging
- Each URL scheme attempt is logged separately
- Clear success/failure indicators
- Exception details for each failed attempt

## Testing Instructions

### Step 1: Install Extension
```bash
open TejOCR-0.1.5.oxt
```

### Step 2: Trigger Test
1. Open LibreOffice Writer
2. Go to **Tools → TejOCR → Settings...**

### Step 3: Check Results

#### ✅ SUCCESS Scenario
- **Dialog appears**: XDL dialog with "XDL Dialog Loading Test Successful!" message
- **Message box**: "XDL Test Success - Dialog loaded successfully with URL: [working_url]"
- **Log shows**: `✅ SUCCESS! Dialog created with URL: [working_url]`

#### ❌ FAILURE Scenario  
- **Error message**: "XDL Test Failed - Could not create TEST_DIALOG.XDL with any URL scheme"
- **Log shows**: `❌ ALL URL schemes failed to create TEST_DIALOG.XDL`

### Step 4: Examine Logs
Check the detailed logs for each URL scheme attempt:
- `Trying URL scheme: private:dialogs/test_dialog.xdl`
- `Trying URL scheme: vnd.sun.star.extension://org.libreoffice.TejOCR/dialogs/test_dialog.xdl`
- etc.

## Potential Outcomes & Next Steps

### If ANY URL Scheme Works ✅
1. **Immediate**: Update all dialog handlers to use the working URL scheme
2. **Deploy**: Replace current XDLs with the full-featured versions
3. **Implement**: Complete Phase 2 dialog functionality
4. **Success**: Professional configurable OCR interface ready

### If ALL URL Schemes Fail ❌
**Possible Causes**:
1. **Build packaging issue**: `dialogs/` folder not properly included in OXT
2. **LibreOffice version issue**: Your LO version has different XDL requirements  
3. **macOS-specific issue**: Platform-specific DialogProvider behavior
4. **Extension caching**: LO not recognizing new manifest entries

**Debug Steps**:
1. **Verify OXT contents**: Extract and check `dialogs/test_dialog.xdl` exists
2. **Try Basic dialog**: Create programmatic dialog instead of XDL
3. **Check LO version**: Test with different LibreOffice versions
4. **Clear cache**: Complete LO restart and extension reinstall

## Current Status

- **Extension builds successfully** ✅
- **All manifest entries correct** ✅  
- **Test dialog XDL is valid** ✅
- **Fallback OCR works perfectly** ✅ (users not blocked)
- **Full UI/UX designs ready** ✅ (waiting for loading fix)

## Success Criteria

**Minimum Success**: One URL scheme loads the test dialog
**Full Success**: Can load the complete settings/options dialogs
**User Impact**: Zero downtime - fallbacks ensure full OCR functionality

This systematic approach will definitively identify the correct method for loading XDL dialogs in your environment. 