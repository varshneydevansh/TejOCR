# Method and Module Mapping

This file tracks how user commands map to exact methods and where each subsystem is crossed.

## Top-level dispatch map

```text
User command URL
  -> queryDispatch(url)
  -> dispatch(url, args)
  -> handler
      -> options normalization
      -> OCR engine
      -> output strategy
      -> feedback/log
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
  A["queryDispatch(url)"] --> B["dispatch(url, args)"]
  B --> C{"command"}
  C -->|Settings| D["_handle_settings()"]
  C -->|OCRSelectedImage| E["_handle_ocr_selected_image()"]
  C -->|OCRImageFromFile| F["_handle_ocr_image_from_file()"]
  C -->|ToolbarAction| G["_handle_toolbar_action()"]
  D --> D1["_show_settings()"]
  E --> E1["_capture_selected_image_anchor()"]
  F --> F1["_perform_ocr_with_options(source='file')"]
  E1 --> E2["_perform_ocr_with_options(source='selected')"]
  G --> G1["command-specific branch"]
```

## `tejocr_service.py` map

### Settings flow

```text
_handle_settings()
  -> _ensure_modules_loaded(dialogs=True)
  -> _show_settings()
  -> _apply_settings()
  -> _dialog success -> persist default keys
  -> error -> warning
```

### OCR (selected image) flow

```text
_handle_ocr_selected_image()
  -> _capture_selected_image_anchor()
  -> _is_graphic_candidate(...)
  -> _perform_ocr_with_options(source='selected', ...)
```

### OCR (file image) flow

```text
_handle_ocr_image_from_file()
  -> show_file_picker()
  -> selection/validation
  -> _perform_ocr_with_options(source='file', image_path=...)
```

### Option execution pipeline

```text
_perform_ocr_with_options(
    source_type, image_path, language, output_mode, default_output_mode,
    legacy_output_mode, scale, psm, oem, improve_image, preprocessing)
  -> _build_default_ocr_options(ctx)
  -> _coerce_bool / _coerce_scale / _coerce_output_mode
  -> _normalize_language_request
  -> _persist_last_ocr_preferences
  -> _show_ocr_options_dialog (preferred XDL)
  -> if unavailable, fallback prompt path
  -> _ensure_tesseract_is_ready_and_run(callback)
  -> output.handle_ocr_output(...)
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["_perform_ocr_with_options"] --> B["_build_default_ocr_options"]
  B --> C["_coerce helpers"]
  C --> D["_normalize request + settings"]
  D --> E["_persist_last_ocr_preferences"]
  E --> F["_show_ocr_options_dialog"]
  F -->|yes| G["_ensure_tesseract_is_ready_and_run"]
  F -->|fallback path| H["use saved defaults"]
  H --> G
  G --> I["engine.perform_ocr"]
  I --> J["output.handle_ocr_output"]
```

## `tejocr_engine.py` map

```text
perform_ocr(ctx, frame, source, image_path_or_selection, ocr_options)
   -> source branch
      +-- selected image: extract_text_from_selected_image
          +-- _get_image_from_selection
          +-- _export_graphic_to_file
      +-- file image: extract_text_from_image_file
   -> _preprocess_image
   -> attempt loop:
      - ocr language list
      - PSM attempts
      - OEM attempts
   -> return recognized text and diagnostics
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["perform_ocr"] --> B{"source_type"}
  B -->|selected| C["extract_text_from_selected_image"]
  B -->|file| D["extract_text_from_image_file"]
  C --> E["_get_image_from_selection"]
  E --> F["_export_graphic_to_file"]
  F --> G["_preprocess_image"]
  D --> G
  G --> H["OCR attempt loop (PSM + OEM)"]
  H --> I["text / error"]
```

## `tejocr_output.py` map

```text
handle_ocr_output(ctx, frame, text, output_mode, insertion_anchor, replacement_target)
  -> switch(output_mode)
  |-- at_cursor: _resolve_insertion_cursor + _insert_text_at_cursor
  |-- new_text_box: create_text_box_with_text
  |-- clipboard: copy_text_to_clipboard
  |-- replace_image:
      |-- target exists: _replace_image_with_text
      |-- target missing: safe fallback to insertion route
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["handle_ocr_output"] --> B{"output_mode"}
  B -->|at_cursor| C["_resolve_insertion_cursor"]
  C --> C2["_insert_text_at_cursor"]
  B -->|new_text_box| D["create_text_box_with_text"]
  B -->|clipboard| E["copy_text_to_clipboard"]
  B -->|replace_image| F{"replacement target exists?"}
  F -->|yes| G["_replace_image_with_text"]
  F -->|no| C
```

## `uno_utils.py` map

```text
create_instance(service_name, ctx)
  -> multi-context factory helper

supports_uno_dialog_model(ctx)
  -> caches support result
  -> guards dialog fallback path

get_setting/set_setting
  -> persistent config file for extension defaults

is_graphic_object_selected(frame, ctx)
  -> selection type checks before enabling selected-image command
```

## Full module cross-call map

```text
te jocr_service.py
  -> constants.py
  -> help_system.py
  -> uno_utils.py
      -> settings + dialogs + service utilities
  -> tejocr_dialogs.py (+ enhanced)
  -> tejocr_interactive_dialogs.py
  -> tejocr_engine.py
  -> tejocr_output.py
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  S["tejocr_service.py"] --> U["uno_utils.py"]
  S --> D["tejocr_dialogs.py"]
  S --> I["tejocr_interactive_dialogs.py"]
  S --> E["tejocr_engine.py"]
  S --> O["tejocr_output.py"]
  U --> P["get/set settings"]
  U --> Q["create_instance + service helpers"]
  U --> R["message/input fallbacks"]
```

## Error recovery mapping

```text
dispatch path failure
  -> settings/options exception
  -> OCR exception
  -> output insertion exception
     -> attempt cursor fallback
     -> continue with non-fatal status to keep extension usable
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["dispatch path"] --> B{"Error type?"}
  B -->|options dialog| C["fallback editor defaults"]
  B -->|engine error| D["OCR failed message + logs"]
  B -->|output error| E["cursor fallback strategies"]
  C --> F["continue if possible"]
  D --> F
  E --> F
```

