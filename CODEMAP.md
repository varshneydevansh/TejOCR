# TejOCR Code Map

Use this as a first-pass map from user intent to module and method.

## Top-level architecture

```text
Addons.xcu / ProtocolHandler.xcu
    |
    v
tejocr_service.py
    |--> dialogs (tejocr_dialogs.py, te jocr_dialogs_enhanced.py)
    |--> engine (tejocr_engine.py)
    |--> output (tejocr_output.py)
    |--> utilities (uno_utils.py)
    |--> settings/resources (description.xml, manifest, xcu)
```

```mermaid
flowchart TD
  A["Addons.xcu + ProtocolHandler.xcu"] --> B["tejocr_service.py"]
  B --> C["tejocr_dialogs.py / enhanced"]
  B --> D["tejocr_engine.py"]
  B --> E["tejocr_output.py"]
  B --> F["uno_utils.py"]
  B --> G["build/runtime metadata"]
```

## Module-to-function map

### 1) `python/tejocr/tejocr_service.py`
- `queryDispatch` / `dispatch`
- `_handle_settings()`
- `_handle_ocr_selected_image()`
- `_handle_ocr_image_from_file()`
- `_perform_ocr_with_options()`
- `_ensure_tesseract_is_ready_and_run()`

### 2) `python/tejocr/tejocr_engine.py`
- `perform_ocr`
- `extract_text_from_selected_image`
- `extract_text_from_image_file`
- `_get_image_from_selection`
- `_export_graphic_to_file`
- `_preprocess_image`

### 3) `python/tejocr/tejocr_output.py`
- `handle_ocr_output`
- `_resolve_insertion_cursor`
- `_insert_text_at_cursor`
- `create_text_box_with_text`
- `_replace_image_with_text`
- `copy_text_to_clipboard`

### 4) `python/tejocr/uno_utils.py`
- `show_message_box`
- `show_input_box` / `show_multiline_input_box`
- `create_instance` + `supports_uno_dialog_model`
- `get_setting` / `set_setting`
- `is_graphic_object_selected` / `get_graphic_from_selection`
- `show_file_picker`

### 5) `python/tejocr/tejocr_dialogs.py` (+ enhanced variant)
- `SettingsDialogHandler`
- `OCRDialogHandler`
- `SetupDialog` (dependencies + instructions + command text)

## Flow map by command

```text
Commands from UI
  -> Settings
     -> settings dialog + dependency checks + persist defaults
  -> OCR Selected Image
     -> capture anchor -> options -> OCR -> output
  -> OCR Image from File
     -> picker -> options -> OCR -> output
  -> ToolbarAction
     -> command-specific dispatch branch
```

```mermaid
flowchart TD
  A["UI command"] --> B{"type"}
  B -->|Settings| C["settings workflow"]
  B -->|OCR Selected Image| D["selected workflow"]
  B -->|OCR Image from File| E["file workflow"]
  B -->|ToolbarAction| F["toolbar workflow"]
  C --> C1["_handle_settings"]
  D --> D1["_handle_ocr_selected_image"]
  E --> E1["_handle_ocr_image_from_file"]
  F --> F1["_handle_toolbar_action"]
```

## Deep docs

- `TECHNICAL.md` (runtime traces)
- `docs/architecture/overview.md`
- `docs/architecture/dispatch-flow.md`
- `docs/reference/method-map.md`
- `docs/reference/uno-apis.md`
- `docs/reference/output-modes.md`
- `docs/flow/selected-image-ocr.md`
- `docs/flow/file-image-ocr.md`
- `docs/troubleshooting/installation.md`
- `docs/troubleshooting/dialog-fallbacks.md`

