# TejOCR Architecture Overview

## What runs where

## ASCII flow

```text
User action (Writer UI)
     |
     v
UI XML registration (Addons.xcu / ProtocolHandler.xcu)
     |
     v
Python dispatch service in process:
TejOCRService (te jocr_service.py)
     |
     +-- settings surface
     |     -> Settings
     |     -> Advanced Engine Parameters
     |     -> Setup & Diagnostics
     |     -> Help
     |     -> A Message
     |
     +-- OCR run surface
     |     -> OCR options dialog/fallback
     |     -> preview/review
     |     -> OCR Complete
     |
     +-- OCR orchestration
     +-- engine/output handoff
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["Writer menu/toolbar"] --> B["Addons.xcu / ProtocolHandler.xcu"]
  B --> C["TejOCRService (Python)"]
  C --> D["Settings surface"]
  D --> D1["Settings / Advanced Params / Setup / Help / A Message"]
  C --> E["OCR run surface"]
  E --> E1["Options / Preview / OCR Complete"]
  C --> F["OCR Engine"]
  C --> G["Output Engine"]
```

## Core runtime clusters

```text
UI cluster:
  xcu / dispatch URLs / status handlers
  -> tejocr_service.py
  -> settings/help/setup/message/result dialogs
  -> advanced engine parameter dialog for Custom preset tuning
  -> interactive fallback helpers

OCR cluster:
  -> tejocr_engine.py
  -> preprocessing + OCR attempts + language checks

Output cluster:
  -> tejocr_output.py
  -> cursor/textbox/replace/clipboard insertion
  -> 6 pt default OCR Writer text styling

Persistence cluster:
  -> settings store and configuration helpers
  -> uno_utils.get_setting / set_setting
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
  UI["UI cluster"] --> S["tejocr_service.py"]
  S --> DLG["Dialog handlers"]
  S --> ENG["OCR cluster: tejocr_engine.py"]
  S --> OUT["Output cluster: tejocr_output.py"]
  S --> CFG["Persistence: uno_utils settings helpers"]
  CFG --> P["settings file"]
```

## Method-level architecture (complete chain)

```text
queryDispatch(url)
  -> dispatch(url, args)
  -> command route
     +-- Settings  -> _handle_settings -> _show_settings
     +-- OCRSelectedImage -> _handle_ocr_selected_image
     +-- OCRImageFromFile -> _handle_ocr_image_from_file
  -> _perform_ocr_with_options
  -> engine.perform_ocr
  -> preview/review (if enabled)
  -> output.handle_ocr_output
  -> OCR Complete dialog
  -> status messages/logs
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["queryDispatch(url)"] --> B["dispatch(url, args)"]
  B --> C{"command"}
  C -->|Settings| D["_handle_settings"]
  C -->|OCRSelectedImage| E["_handle_ocr_selected_image"]
  C -->|OCRImageFromFile| F["_handle_ocr_image_from_file"]
  D --> G["_show_settings"]
  E --> H["_perform_ocr_with_options selected"]
  F --> I["_perform_ocr_with_options file"]
  H --> J["engine.perform_ocr"]
  I --> J
  J --> K["preview/review if enabled"]
  K --> L["output.handle_ocr_output"]
  L --> M["OCR Complete dialog"]
  M --> N["status/logging"]
```

## Deployment and install contract

```text
build scripts
   -> package files
   -> description.xml
   -> META-INF/manifest.xml
   -> zip -> .oxt
   -> LibreOffice installer validation
      -> extension manager card + icon/license + registration
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["build_tejocr.py / build.py"] --> B["copy extension assets"]
  B --> C["description.xml"]
  C --> D["META-INF/manifest.xml"]
  D --> E["TejOCR-*.oxt"]
  E --> F["LibreOffice deploy"]
  F --> G["extension manager + runtime registration"]
```

## Why selected vs file modes differ

```text
selected image:
  has a live UNO target object
  -> can attempt replace_image by replacing that target

file image:
  no target object in Writer model
  -> cannot perform true replace
  -> use insertion-style output
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
  A["OCR source"] --> B{"target object exists?"}
  B -->|selected| C["replace_image allowed"]
  B -->|file| D["insert path only"]
```
