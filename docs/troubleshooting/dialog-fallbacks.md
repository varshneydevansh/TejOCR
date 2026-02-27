# UI Dialog Fallbacks and Runtime Compatibility

## Why fallback appears

```text
Expected path:
  XDL dialogs create
  + DialogProvider + model
  + interactive controls

Observed in some sessions:
  service returns None for UnoControlDialogModel
  -> fallback path engaged
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["Expected path"] --> B["XDL dialogs create"]
    B --> C["DialogProvider + model"]
    C --> D["interactive controls"]
    A --> E["Observed: UnoControlDialogModel None"]
    E --> F["fallback path engaged"]
```

Common in constrained LibreOffice runtimes where:
- UNO dialog service is unavailable through context
- Extension is loaded in headless/limited UI mode
- Context provider in service factory lookup is unavailable

## Runtime behavior when fallback is active

1. Settings:
   - settings path opens a text-based prompt/editor view.
2. OCR options:
   - interactive option dialog cannot be shown
   - OCR continues with saved defaults
3. Preview:
   - OCR result preview dialog may not appear
   - output is inserted per configured output mode

## Why this is acceptable

Fallback mode keeps OCR functional:
- extraction, language, and preprocessing still work
- output still reaches target mode
- message path remains visible

If fallback is permanent:
- check log messages around `supports_uno_dialog_model`.
- confirm `com.sun.star.awt.UnoControlDialogModel` and `com.sun.star.awt.Toolkit` service availability.

## Debug log fingerprints

```text
supports_uno_dialog_model: Returning cached negative result
show_multiline_input_box: UnoControlDialogModel is unavailable
OCR options dialog unavailable, proceeding with saved settings
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
    A["supports_uno_dialog_model: cached negative"] --> B["show_* dialog fails"]
    B --> C["OCR options dialog unavailable"]
    C --> D["proceed with saved settings"]
    D --> E["OCR still runs"]
```

These are recoverable; escalate only if OCR output also fails after fallback.

## User-facing recommendation

- Keep a known-good default output mode:
  - `new_text_box` when cursor anchor reliability is poor
  - `replace_image` only when target image is actively selected
  - `clipboard` for manual insertion workflows
