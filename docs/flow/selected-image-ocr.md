# Selected Image OCR Flow (Writer content)

## Trigger

User explicitly selects an image object in Writer and executes:
`OCR Selected Image`.

## Complete flow

```text
User selected image in Writer
    |
    v
TejOCRService._handle_ocr_selected_image()
    |
    v
Selection guard: is_graphic_object_selected()
    |
    +-- false -> message + stop (no selected image)
    |
    +-- true  -> capture anchor for output stability
                 -> _perform_ocr_with_options(source='selected')
                     -> _show_ocr_options_dialog() (or fallback)
                     -> _ensure_tesseract_is_ready_and_run(...)
                     -> _handle_ocr_with_options callback
                     -> engine.extract_text_from_selected_image()
                           -> _get_image_from_selection()
                           -> _export_graphic_to_file()
                           -> _preprocess_image()
                           -> OCR attempts (PSM/OEM chain)
                     -> output.handle_ocr_output(... insertion_anchor + replacement_target)
                     -> success notification
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["User selects image"] --> B["_handle_ocr_selected_image"]
  B --> C["is_graphic_object_selected"]
  C -->|False| D["no suitable object message"]
  C -->|True| E["_capture_selected_image_anchor"]
  E --> F["_perform_ocr_with_options('selected')"]
  F --> G["_show_ocr_options_dialog"]
  G --> H["_ensure_tesseract_is_ready_and_run"]
  H --> I["engine.extract_text_from_selected_image"]
  I --> J["_get_image_from_selection"]
  J --> K["_export_graphic_to_file"]
  K --> L["_preprocess_image"]
  L --> M["OCR attempt loop"]
  M --> N["handle_ocr_output(anchor,target)"]
  N --> O{output mode}
  O -->|at_cursor| P["_resolve_insertion_cursor/_insert_text_at_cursor"]
  O -->|new_text_box| Q["create_text_box_with_text"]
  O -->|clipboard| R["copy_text_to_clipboard"]
  O -->|replace_image| S["_replace_image_with_text"]
  D --> T["Stop"]
  P --> U["Success"]
  Q --> U
  R --> U
  S --> U
  D --> U
```

## Important output semantics for selected-image flow

- `replace_image` requires a real replacement target (selected graphic).
- If user selected image disappears before output:
  - fallback output path is used (cursor insertion).
- Cursor strategy has fallback-to-end behavior to avoid hard failure.

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["replace_image request"] --> B{"selection still valid?"}
  B -->|yes| C["remove target + insert text"]
  B -->|no| D["cursor fallback path"]
  D --> E["insert at cursor or doc end"]
```

