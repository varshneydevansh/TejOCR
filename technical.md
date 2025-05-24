# TejOCR - Technical Documentation

**Architecture, Implementation Details, and Development Guide**

---

## 🏗️ **System Architecture**

### **High-Level Overview**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LibreOffice   │    │   TejOCR Ext.    │    │   External      │
│     Writer      │◄──►│   (Python/UNO)   │◄──►│  Dependencies   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                         │                       │
        │                         │              ┌─────────────────┐
   User Actions              ┌────▼──────┐       │   Tesseract     │
   (Menu, Toolbar)           │   Core    │       │     Engine      │
                             │ Services  │       └─────────────────┘
                             └───────────┘       ┌─────────────────┐
                                                 │ Python Packages │
                                                 │ (numpy,pytess.. │
                                                 └─────────────────┘
```

### **Module Architecture**
```
python/tejocr/
├── tejocr_service.py      # UNO Service (Entry Point)
│   ├── XDispatchProvider  # Handles menu/toolbar actions
│   ├── XServiceInfo      # Service registration
│   └── Event Routing     # Dispatches to appropriate handlers
│
├── tejocr_engine.py       # OCR Processing Core
│   ├── Image Export      # Multi-strategy graphic extraction
│   ├── Tesseract Wrapper # Pytesseract integration
│   ├── Dependency Check  # Runtime validation
│   └── Error Handling    # Robust failure management
│
├── tejocr_output.py       # Text Output Management
│   ├── Text Insertion    # Multi-strategy text placement
│   ├── Cursor Management # Document navigation
│   ├── Clipboard Ops     # System clipboard integration
│   └── Output Modes      # Various insertion strategies
│
├── tejocr_dialogs.py      # User Interface
│   ├── Settings Dialog   # Configuration management
│   ├── Error Dialogs     # User-friendly error reporting
│   ├── Progress UI       # Operation feedback
│   └── Dependency Help   # Installation guidance
│
├── uno_utils.py           # UNO Framework Utilities
│   ├── Service Creation  # UNO service instantiation
│   ├── Selection Mgmt    # Document object selection
│   ├── Message Boxes     # User interaction
│   ├── Configuration     # Settings persistence
│   └── Logging System    # Comprehensive logging
│
├── constants.py           # Configuration & Constants
│   ├── Version Info      # Centralized version management
│   ├── Configuration     # Default settings
│   ├── UNO Constants     # Service names, URLs
│   └── OCR Parameters    # Default OCR settings
│
└── locale_setup.py        # Internationalization
    ├── Translation       # gettext integration
    ├── Locale Detection  # System language detection
    └── Fallback System   # English fallback handling
```

---

## 🔄 **Process Flow Diagrams**

### **OCR from File Workflow**
```
User: Tools → TejOCR → OCR Image from File
                    │
                    ▼
        tejocr_service.py:dispatch()
                    │
                    ▼
        _ensure_tesseract_is_ready_and_run()
                    │
          ┌─────────▼─────────┐
          │ Dependencies OK?  │
          └─────────┬─────────┘
                    │ Yes
                    ▼
        _handle_ocr_image_from_file()
                    │
                    ▼
        Show File Picker Dialog
                    │
                    ▼
        tejocr_engine.extract_text_from_image_file()
                    │
            ┌───────▼───────┐
            │ Load Image    │
            │ (PIL/Pillow)  │
            └───────┬───────┘
                    │
            ┌───────▼───────┐
            │ OCR Process   │
            │ (pytesseract) │
            └───────┬───────┘
                    │
                    ▼
        tejocr_output.insert_text_at_cursor()
                    │
          ┌─────────▼─────────┐
          │ Multi-Strategy    │
          │ Text Insertion    │
          └─────────┬─────────┘
                    │
                    ▼
        Success Dialog → User
```

### **OCR Selected Image Workflow**
```
User: Selects Image → Tools → TejOCR → OCR Selected Image
                    │
                    ▼
        tejocr_service.py:dispatch()
                    │
                    ▼
        uno_utils.is_graphic_object_selected()
                    │
          ┌─────────▼─────────┐
          │ Image Selected?   │
          └─────────┬─────────┘
                    │ Yes
                    ▼
        tejocr_engine.extract_text_from_selected_image()
                    │
                    ▼
        uno_utils.get_graphic_from_selection()
                    │
                    ▼
        uno_utils.create_temp_file_from_graphic()
                    │
          ┌─────────▼─────────┐
          │ Multi-Strategy    │
          │ Image Export      │
          │ (6 strategies)    │
          └─────────┬─────────┘
                    │
                    ▼
        [Continue with OCR Process as above]
```

---

## 🔧 **Multi-Strategy Fallback Systems**

### **Text Insertion Strategies** (tejocr_output.py)

**Strategy 1: View Cursor (Primary)**
```python
view_cursor = controller.getViewCursor()
text_range = view_cursor.getStart()
text_range.setString(text_to_insert)
```
- **Best for**: Active document with focused cursor
- **Fails when**: Document loses focus, no text selection context

**Strategy 2: Text Cursor at End (Fallback)**
```python
text_cursor = text_doc.createTextCursor()
text_cursor.gotoEnd(False)
text_cursor.setString("\n" + text_to_insert)
```
- **Best for**: When view cursor fails but document is accessible
- **Reliable**: Direct text model manipulation

**Strategy 3: Direct Insert String (Robust)**
```python
end_cursor = text_doc.createTextCursor()
text_doc.insertString(end_cursor, "\n" + text_to_insert, False)
```
- **Best for**: Maximum compatibility across LibreOffice versions
- **Most reliable**: Lowest-level text insertion

**Strategy 4: Focus + Retry (Recovery)**
```python
window.setFocus()
time.sleep(0.1)  # Allow focus to settle
# Retry Strategy 1
```
- **Best for**: Recovering from focus-related failures
- **Use case**: After file dialogs or long operations

### **Image Export Strategies** (uno_utils.py)

**Strategy 1: Standard GraphicExporter**
```python
exporter = create_instance("com.sun.star.drawing.GraphicExporter", ctx)
exporter.setSource(graphic_props)
exporter.filter(export_props)
```

**Strategy 2: Alternative Export Services**
```python
services = [
    "com.sun.star.drawing.GraphicExportFilter",
    "com.sun.star.graphic.GraphicExporter",
    "com.sun.star.graphic.GraphicExportFilter"
]
```

**Strategy 3: GraphicProvider.storeGraphic**
```python
provider = create_instance("com.sun.star.graphic.GraphicProvider", ctx)
provider.storeGraphic(graphic, properties)
```

**Strategy 4: Direct Bitmap Access**
```python
if hasattr(graphic, "Bitmap") and graphic.Bitmap:
    dib_data = graphic.Bitmap.DIB
    # Write raw bitmap data
```

**Strategy 5: URL-based File Copy**
```python
if hasattr(graphic, "URL") and graphic.URL.startswith("file://"):
    shutil.copy2(source_path, target_path)
```

**Strategy 6: PIL Placeholder (Graceful Degradation)**
```python
img = Image.new('RGB', (400, 200), color='lightgray')
draw.multiline_text((10, 10), error_message, fill='black')
```

---

## 📊 **Error Handling Philosophy**

### **Defensive Programming Principles**

1. **Multi-Strategy Approaches**: Every critical operation has multiple fallback methods
2. **Graceful Degradation**: Failures result in helpful user guidance, not crashes
3. **Comprehensive Logging**: All operations logged for debugging
4. **User-Friendly Messaging**: Technical errors translated to actionable user guidance

### **Error Categories**

**Category 1: Dependency Errors**
- **Detection**: Runtime checks for Tesseract, NumPy, Pytesseract, Pillow
- **Response**: Clear installation guidance with platform-specific instructions
- **Recovery**: Automatic retry after user installs dependencies

**Category 2: UNO Service Errors**
- **Detection**: Service creation failures, interface access errors
- **Response**: Multiple service name attempts, alternative approaches
- **Recovery**: Fallback to compatible methods across LibreOffice versions

**Category 3: Image Processing Errors**
- **Detection**: Graphic export failures, format incompatibilities
- **Response**: Multiple export strategies, format conversion attempts
- **Recovery**: PIL-based placeholder with clear error messaging

**Category 4: Text Insertion Errors**
- **Detection**: Cursor access failures, document context issues
- **Response**: Multiple insertion strategies, focus management
- **Recovery**: Alternative insertion points, clipboard fallback

---

## 🔍 **Development Debugging**

### **Logging System**

**Log Levels:**
```python
logger.debug()    # Detailed operation traces
logger.info()     # Major operation milestones  
logger.warning()  # Recoverable issues
logger.error()    # Operation failures
logger.critical() # System-level failures
```

**Log Locations:**
- **File Logs**: `/tmp/TejOCRLogs/tejocr.log` (persistent)
- **Console Logs**: Terminal output when LibreOffice launched from CLI
- **Format**: `timestamp - module - level - function:line - message`

### **Debug Mode Activation**

**Console Logging:**
```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --writer --norestore
```

**Strategy Testing:**
```python
# In uno_utils.py - enable testing mode
logger.debug("TESTING MODE: Forcing is_graphic_object_selected to return True")
return True
```

**Dependency Checking:**
```bash
# Test OCR dependencies outside LibreOffice
python3 test_ocr_setup.py
```

---

## 🛠️ **Development Environment**

### **Build Process**
```python
# build.py workflow:
1. Import version from constants.py
2. Clean temporary files
3. Validate XML structure
4. Package files into .oxt (ZIP format)
5. Verify manifest integrity
```

### **Testing Strategies**

**Unit Testing:**
```python
# tejocr_engine.py functions
test_pytesseract_availability()
test_image_format_support() 
test_ocr_accuracy_benchmarks()
```

**Integration Testing:**
```python
# UNO service interactions
test_service_registration()
test_menu_integration()
test_dialog_functionality()
```

**End-to-End Testing:**
```python
# Full user workflows
test_ocr_from_file_workflow()
test_ocr_selected_image_workflow()
test_error_recovery_scenarios()
```

### **Dependency Management**

**LibreOffice Python Environment:**
```bash
LO_PYTHON="/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3"

# Package installation
$LO_PYTHON -m pip install numpy pytesseract pillow

# Verification
$LO_PYTHON -c "import numpy, pytesseract, PIL; print('OK')"
```

**Cross-Platform Paths:**
```python
# macOS
"/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3"

# Linux
"/usr/lib/libreoffice/program/python"

# Windows  
"C:\\Program Files\\LibreOffice\\program\\python.exe"
```

---

## 📐 **UNO Integration Details**

### **Service Registration**
```python
# tejocr_service.py
IMPL_NAME = "org.libreoffice.TejOCR.PythonService.TejOCRService"
SERVICE_NAME = "com.sun.star.frame.ProtocolHandler"

# Registration in ImplementationHelper
g_ImplementationHelper.addImplementation(
    TejOCRService,
    IMPL_NAME,
    (SERVICE_NAME,)
)
```

### **Dispatch URL Handling**
```python
# URL patterns in Addons.xcu
"uno:org.libreoffice.TejOCR.OCRSelectedImage"
"uno:org.libreoffice.TejOCR.OCRImageFromFile"  
"uno:org.libreoffice.TejOCR.Settings"
"uno:org.libreoffice.TejOCR.ToolbarAction"
```

### **Interface Implementation**
```python
class TejOCRService(unohelper.Base, XDispatchProvider, XServiceInfo):
    def queryDispatch(self, URL, TargetFrameName, SearchFlags):
        # URL matching and dispatch object return
        
    def dispatch(self, URL, Arguments):
        # Action execution based on URL
        
    def addStatusListener(self, Listener, URL):
        # UI state management
```

---

## 🔬 **Performance Considerations**

### **Lazy Loading Strategy**
```python
# Modules loaded only when needed
def _ensure_modules_loaded(self):
    if not self._modules_loaded:
        import tejocr.tejocr_dialogs
        import tejocr.tejocr_engine  
        import tejocr.tejocr_output
        self._modules_loaded = True
```

### **Memory Management**
```python
# Temporary files cleanup
try:
    # OCR operations
    result = pytesseract.image_to_string(image)
finally:
    if temp_file and os.path.exists(temp_file):
        os.remove(temp_file)
```

### **Large Image Handling**
```python
# PIL optimization for large images
max_dimension = 2048
if image.width > max_dimension or image.height > max_dimension:
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
```

---

## 🔮 **Future Architecture Plans**

### **Phase 2: XDL Dialog System**
```
dialogs/
├── tejocr_settings_dialog.xdl    # Settings UI definition
├── tejocr_options_dialog.xdl     # OCR options UI
└── tejocr_progress_dialog.xdl    # Progress indicator UI
```

### **Phase 3: Async Processing**
```python
# Non-blocking OCR with progress callbacks
class AsyncOCRProcessor:
    def process_image_async(self, image_path, progress_callback):
        # Background OCR with UI updates
```

### **Phase 4: Plugin Architecture**
```python
# Extensible OCR engines
class OCREngineInterface:
    def extract_text(self, image_path, language, options):
        pass

# Implementations
class TesseractEngine(OCREngineInterface): pass
class GoogleVisionEngine(OCREngineInterface): pass
class AzureCognitiveEngine(OCREngineInterface): pass
```

---

## 📈 **Performance Metrics**

### **Current Benchmarks (v0.1.4)**
- **Startup Time**: <1s (lazy loading)
- **Image Export**: 0.1-2s (depending on strategy)
- **OCR Processing**: 1-10s (depends on image size/complexity)
- **Text Insertion**: <0.1s (with fallbacks)
- **Memory Usage**: ~50MB additional (during OCR operation)

### **Optimization Targets**
- **Startup**: <0.5s (Phase 2)
- **OCR Caching**: Avoid re-processing identical images
- **Batch Processing**: Multiple images in single operation
- **Progress Indicators**: Real-time feedback for operations >2s

---

*Technical documentation for TejOCR v0.1.4 - For user documentation, see documentation.md* 