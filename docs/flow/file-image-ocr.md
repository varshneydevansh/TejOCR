# File Image OCR Flow (No Writer selection required)

## Trigger

User executes:
`OCR Image from File`.

## Complete flow

```text
Command OCR Image from File
  |
  v
_handle_ocr_image_from_file()
  |
  +-- user cancels picker -> return
  |
  +-- image selected
       |
       v
  _perform_ocr_with_options(source='file', image_path)
       |
       +-- _show_ocr_options_dialog() (or fallback prompt)
       +-- _ensure_tesseract_is_ready_and_run(...)
       +-- engine.extract_text_from_image_file()
             +-- _preprocess_image()
             +-- OCR attempt chain
       +-- output.handle_ocr_output(replacement_target=None)
             +-- at_cursor/new_text_box/clipboard
             +-- replace_image -> mapped to safe insertion branch
       +-- success notification
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["OCR Image from File command"] --> B["_handle_ocr_image_from_file"]
  B --> C["show_file_picker"]
  C -->|Cancelled| D["Exit cleanly"]
  C -->|File path| E["_perform_ocr_with_options('file')"]
  E --> F["_show_ocr_options_dialog/fallback"]
  F --> G["_ensure_tesseract_is_ready_and_run"]
  G --> H["extract_text_from_image_file"]
  H --> I["_preprocess_image"]
  I --> J["OCR attempt loop"]
  J --> K["handle_ocr_output(replacement_target=None)"]
  K --> L{mode}
  L -->|at_cursor| M["insert at cursor"]
  L -->|new_text_box| N["insert text box"]
  L -->|clipboard| O["copy text"]
  L -->|replace_image| P["insert-compatible path"]
  M --> Q["Done"]
  N --> Q
  O --> Q
  P --> Q
  D --> Q
```

## Source mismatch note

```text
File flow has no selected Writer image object
-> replace_image is not true in-place replacement
-> implementation keeps behavior safe and visible by using insertion/clipboard modes
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
  A["file source OCR"] --> B{"replacement target exists?"}
  B -->|no| C["replace_image treated as insertion branch"]
  C --> D["at_cursor / new_text_box / clipboard"]
```

