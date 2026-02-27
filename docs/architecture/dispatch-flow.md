# Dispatch and Runtime Flow (UNO)

This file explains how a Writer command reaches the extension service and then traverses OCR/output execution.

## Protocol entry

```text
Addons.xcu + ProtocolHandler.xcu
   -> maps:
      - uno:org.libreoffice.TejOCR.Settings
      - uno:org.libreoffice.TejOCR.OCRSelectedImage
      - uno:org.libreoffice.TejOCR.OCRImageFromFile
      - uno:org.libreoffice.TejOCR.ToolbarAction
   -> TejOCRService queryDispatch()/dispatch()
```

```mermaid
flowchart TD
  A["Addons.xcu / ProtocolHandler.xcu"] --> B["command URL"]
  B --> C["queryDispatch(url)"]
  C --> D["dispatch(url, args)"]
```

## Dispatch matrix

```text
dispatch(url)
  -> _handle_settings()
  -> _handle_ocr_selected_image()
  -> _handle_ocr_image_from_file()
  -> _handle_toolbar_action()
```

```mermaid
flowchart TD
  A["dispatch(url)"] --> B{"URL"}
  B -->|Settings URL| C["_handle_settings()"]
  B -->|OCRSelectedImage URL| D["_handle_ocr_selected_image()"]
  B -->|OCRImageFromFile URL| E["_handle_ocr_image_from_file()"]
  B -->|ToolbarAction URL| F["_handle_toolbar_action()"]
  C --> C1["_show_settings()"]
  D --> D1["_capture_selected_image_anchor()"]
  E --> E1["show_file_picker()"]
  F --> F1["command specific action"]
```

## OCR dispatch internals

```text
_handle_ocr_selected_image()
  -> is_graphic_object_selected()
  -> _perform_ocr_with_options(source='selected')
  -> ensure_tesseract_is_ready_and_run(...)
  -> engine.perform_ocr(...)
  -> output.handle_ocr_output(...)

_handle_ocr_image_from_file()
  -> pick path via file picker
  -> _perform_ocr_with_options(source='file', image_path=...)
  -> ensure_tesseract_is_ready_and_run(...)
  -> engine.perform_ocr(...)
  -> output.handle_ocr_output(...)
```

```mermaid
flowchart TD
  A["_handle_ocr_selected_image"] --> B["is_graphic_object_selected"]
  B --> C["_perform_ocr_with_options(selected)"]
  D["_handle_ocr_image_from_file"] --> E["show_file_picker"]
  E --> F["_perform_ocr_with_options(file)"]
  C --> G["_ensure_tesseract_is_ready_and_run"]
  F --> G
  G --> H["engine.perform_ocr"]
  H --> I["output.handle_ocr_output"]
```

## Status enablement

```text
queryDispatch() decides command state
  Settings -> always for Writer contexts used by TejOCR
  OCRSelectedImage -> only enabled when image selection exists
  OCRImageFromFile -> generally enabled where file actions are supported
```

```mermaid
flowchart TD
  A["queryDispatch(url)"] --> B{"enablement check"}
  B -->|Settings| C["enabled true (frame context)"]
  B -->|OCRSelectedImage| D["is_graphic_object_selected()"]
  B -->|OCRImageFromFile| E["typically enabled"]
  D -->|false| F["addStatusListener -> disabled"]
  D -->|true| G["enabled"]
```

## Dependency and tesseract gate

```text
before OCR execution:
  -> dependency checks
     -> numpy/pytesseract/pillow availability
     -> tesseract executable/path check
  -> if missing:
     -> friendly error + settings path
  -> else:
     -> OCR pipeline continues
```

```mermaid
flowchart LR
  A["OCR request"] --> B["ensure dependencies"]
  B -->|missing| C["notify + settings route"]
  B -->|ok| D["perform OCR"]
```

