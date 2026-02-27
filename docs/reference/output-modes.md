# Output Modes and Runtime Semantics

This document maps every output mode to:
- what code path is used,
- what method writes output,
- how `selected` and `file` OCR differ,
- what happens in fallback conditions.

Canonical output mode values are stored in `constants` as:
- `at_cursor` (`OUTPUT_MODE_CURSOR`)
- `new_text_box` (`OUTPUT_MODE_TEXTBOX`)
- `to_clipboard` (`OUTPUT_MODE_CLIPBOARD`)
- `replace_image` (`OUTPUT_MODE_REPLACE`)

`_coerce_output_mode()` in `tejocr_service.py` also accepts aliases:
- `cursor`, `insert`, `insert_at_cursor`, `new_textbox`, `textbox`, `clipboard`, `replace`, etc.

## Runtime call chain

```text
_handle_ocr_selected_image
  -> _capture_selected_image_anchor
  -> _perform_ocr_with_options(...)

_handle_ocr_image_from_file
  -> _perform_batch_ocr(...)
     -> (rasterizes PDFs if needed)
     -> loops over items calling _perform_ocr_with_options(...) natively
     -> handle_ocr_output(...) in tejocr_output.py (merged or loop individual)
        -> _insert_text_at_cursor / _insert_text_into_new_textbox /
           _replace_image_with_text / _copy_text_to_clipboard
```

## Service-to-output mapping

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["_perform_ocr_with_options / _perform_batch_ocr"]
  A --> B{"source_type / batch mode"}
  B -->|"selected image"| C["pass insertion_anchor + replacement_target to handle_ocr_output"]
  B -->|"file / batch"| D["pass only insertion_anchor=None"]

  C --> E["mode = at_cursor | new_text_box | to_clipboard | replace_image"]
  D --> E

  E --> F[handle_ocr_output(ctx, frame, text, mode, ...)]
  F --> G{mode}
  G -->|at_cursor| H[_insert_text_at_cursor]
  G -->|new_text_box| I[_insert_text_into_new_textbox]
  G -->|to_clipboard| J[_copy_text_to_clipboard]
  G -->|replace_image| K[_replace_image_with_text]

  H --> L["Strategy 0-5 fallback chain"]
  I --> M["TextFrame + AS\_CHARACTER anchor"]
  J --> N["SystemClipboard + TextTransferable"]
  K --> O["Remove/replace selection if valid"]
```

## Behavior matrix (selected vs file source)

| Mode | `selected` source | `file` source | Notes |
|---|---|---|---|
| `at_cursor` | Uses captured anchor if valid, else anchor-aware fallback | Inserts at current cursor when file is processed | Never disappears silently; fallback tries view cursor, doc-end insertion, then focus retry |
| `new_text_box` | Creates `TextFrame` using captured anchor, else view cursor/doc-end | Same as selected insertion path, using active document position | If TextFrame creation fails, falls back to cursor insertion |
| `to_clipboard` | Copies text to LO system clipboard | Same | `TEXT` transferable, non-blocking insert-independent mode |
| `replace_image` | Requires selected graphic/text-shape target | Not possible for file-only source, fallback handled in `_perform_ocr_with_options` | File OCR automatically coerces to `at_cursor` |

## Detailed per-mode semantics

### 1) `at_cursor` (`OUTPUT_MODE_CURSOR`)
- Entry: `_perform_ocr_with_options` passes `insertion_anchor` only for selected-image path.
- Output: `handle_ocr_output` calls `_insert_text_at_cursor`.
- Fallback chain in `_resolve_insertion_cursor` and `_insert_text_at_cursor`:
  - Strategy 0: direct anchor (`setString`) insertion.
  - Strategy 1: anchor-aware view cursor (`gotoRange`).
  - Strategy 2: active view cursor.
  - Strategy 3: create text cursor and go to end.
  - Strategy 4: direct `insertString` at document end.
  - Strategy 5: focus window + retry at doc-end.
- Why this exists: prevent hard failures when the anchor is stale or selection changes before output.

### 2) `new_text_box` (`OUTPUT_MODE_TEXTBOX`)
- Entry: `_perform_ocr_with_options` passes `insertion_anchor` for selected flow.
- Output: `create_text_box_with_text` / `_insert_text_into_new_textbox`.
- Behavior:
  - Creates `com.sun.star.text.TextFrame`.
  - Applies AS\_CHARACTER anchor and margin properties.
  - Inserts content as frame text.
  - Fallback: if frame creation fails, falls back to cursor insertion.

### 3) `to_clipboard` (`OUTPUT_MODE_CLIPBOARD`)
- Output: `copy_text_to_clipboard` uses `com.sun.star.datatransfer.clipboard.SystemClipboard`.
- Purpose: deterministic mode when insertion context is unreliable.
- Failure behavior: show message if `SystemClipboard` service is unavailable.

### 4) `replace_image` (`OUTPUT_MODE_REPLACE`)
- This mode is only meaningful for selected image flow because it needs:
  - `replacement_target` from `_capture_selected_image_anchor`
  - an `insertion_anchor` position for fallback insert.
- If target is missing/invalid:
  - `_replace_image_with_text` returns failure.
  - `_perform_ocr_with_options` logs warning and falls back to `at_cursor`.
- File flow:
  - `_perform_ocr_with_options` coerces `replace_image` → `at_cursor` before calling output.

## Replace mode and file flow in practice

```text
User runs OCR on file
  -> source_type = file
  -> output_mode requested = replace_image
  -> _perform_ocr_with_options:
     if source_type != "selected" and output_mode == replace_image:
       output_mode = at_cursor
  -> output inserted by cursor strategy
```

This matches runtime safety: file OCR has no selected object handle to remove/replace.

## Output mode keys used in settings

- Settings layer:
  - `default_output_mode` (stored canonical output mode).
  - `LastOutputMode` (last user choice; UI-sync compatibility).
  - Legacy `output_mode` is still accepted for older settings files via compatibility in `uno_utils.py`.
- The runtime summary message prints a human label:
  - Insert at cursor / Copy to clipboard / Create a new text box / Replace selected image.

## Recommended choice by user intent

- Use `replace_image`: quick clean-up when image is explicitly selected and you want text in its place.
- Use `new_text_box`: stable placement for noisy documents where cursor moves.
- Use `at_cursor`: default, predictable for edits-in-place.
- Use `to_clipboard`: when editing should be manual/controlled.

## Related files

- `python/tejocr/tejocr_service.py`
  - `_perform_ocr_with_options`
  - `_coerce_output_mode`
  - `_handle_ocr_selected_image` / `_handle_ocr_image_from_file`
  - `_capture_selected_image_anchor`
- `python/tejocr/tejocr_output.py`
  - `handle_ocr_output`
  - `_resolve_insertion_cursor`
  - `_insert_text_at_cursor`
  - `_insert_text_into_new_textbox`
  - `_replace_image_with_text`
  - `_copy_text_to_clipboard`
