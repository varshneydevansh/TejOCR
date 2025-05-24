# 🔧 CRITICAL FIX: Protocol Handler Registration

## ✅ ROOT CAUSE IDENTIFIED

**The menu items were disabled because LibreOffice couldn't connect the `uno:` URLs to your Python service.**

### What Was Wrong:

1. **ProtocolHandler.xcu**: Missing service mapping - it listed protocols but didn't tell LibreOffice which service handles them
2. **Addons.xcu**: Used `oor:op="replace"` instead of `oor:op="fuse"` and wrong toolbar resource path

### What Was Fixed:

#### 1. **ProtocolHandler.xcu** - Service Mapping Fixed
```xml
<!-- BEFORE (broken): -->
<node oor:name="org.libreoffice.TejOCR.ProtocolHandler" oor:op="replace">
    <prop oor:name="Protocols" oor:type="oor:string-list">
        <value>uno:org.libreoffice.TejOCR.*</value>
    </prop>
</node>

<!-- AFTER (fixed): -->
<node oor:name="org.libreoffice.TejOCR.PythonService.TejOCRService" oor:op="replace">
    <prop oor:name="Protocols" oor:type="oor:string-list">
        <value>uno:org.libreoffice.TejOCR.*</value>
    </prop>
</node>
```

**Key Change**: Node name now matches the `IMPLEMENTATION_NAME` from `tejocr_service.py`

#### 2. **Addons.xcu** - Proper LibreOffice Extension Format
```xml
<!-- BEFORE (problematic): -->
<node oor:name="org.libreoffice.TejOCR.TopLevelMenu" oor:op="replace">
<prop oor:name="MergeToolBar" oor:type="xs:string">
    <value>standardbar</value>
</prop>

<!-- AFTER (correct): -->
<node oor:name="org.libreoffice.TejOCR.TopLevelMenu" oor:op="fuse">
<prop oor:name="MergeToolBar" oor:type="xs:string">
    <value>private:resource/toolbar/standardbar</value>
</prop>
```

**Key Changes**: 
- `oor:op="fuse"` instead of `"replace"` for better integration
- Proper toolbar resource path with `private:resource/` prefix

## 🧪 CRITICAL TESTING

### Step 1: Clean Installation
```bash
# Remove old extension completely
# LibreOffice: Tools → Extension Manager → Select TejOCR → Remove

# Install new TejOCR-0.1.0.oxt
# LibreOffice: Tools → Extension Manager → Add → Select new .oxt

# RESTART LibreOffice completely (critical!)
```

### Step 2: Launch and Test
```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer --norestore
```

### Step 3: Expected Results

**NOW YOU SHOULD SEE:**
```bash
# When LibreOffice loads and you open Writer:
CONSOLE DEBUG: addStatusListener CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
CONSOLE DEBUG: Status for uno:org.libreoffice.TejOCR.OCRImageFromFile: IsEnabled=True
CONSOLE DEBUG: Status event sent to listener

# When you click menu items:
CONSOLE DEBUG: queryDispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
CONSOLE DEBUG: queryDispatch MATCHED URL 'uno:org.libreoffice.TejOCR.OCRImageFromFile', returning self
CONSOLE DEBUG: dispatch CALLED for URL: uno:org.libreoffice.TejOCR.OCRImageFromFile
```

**Menu Items Should Now Be:**
- ✅ **ENABLED** (not grayed out)
- ✅ **Clickable** and show debug output
- ✅ **Connected** to Python service

## 🔍 VERIFICATION CHECKLIST

- [ ] No ImportError messages (already fixed ✅)
- [ ] TejOCR menu appears in menu bar
- [ ] Menu items are **enabled** (not grayed out)
- [ ] Clicking menu items shows **CONSOLE DEBUG** output
- [ ] `addStatusListener` and `queryDispatch` calls appear in terminal
- [ ] Service responds with "returning self" for matched URLs

## 📊 WHAT THIS FIXES

**Before**: `LibreOffice → Menu Items → ??? → Python Service` (broken link)
**After**: `LibreOffice → Menu Items → ProtocolHandler.xcu → Python Service` (working!)

The **ProtocolHandler.xcu** now correctly maps:
- **Protocol Pattern**: `uno:org.libreoffice.TejOCR.*`
- **Handler Service**: `org.libreoffice.TejOCR.PythonService.TejOCRService`
- **Implementation**: Your Python class in `tejocr_service.py`

This creates the essential **connection chain** that makes LibreOffice ask your Python service about menu item status and dispatch clicks to your service.

## 🎯 SUCCESS CRITERIA

✅ **Service Loading**: Python service loads without ImportError  
✅ **Protocol Registration**: LibreOffice connects URLs to service  
✅ **Menu Functionality**: Items enabled and responsive  
✅ **Debug Output**: Console shows service interactions  
✅ **Full Integration**: Ready for OCR workflow testing

**This fix should resolve the disabled menu items issue completely.** 