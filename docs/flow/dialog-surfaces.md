# Dialog Surface Flow

This document covers the user-facing dialog surfaces that changed most in `0.2.0`.

It focuses on:

- the main Settings surface,
- the new `Advanced Engine Parameters (Custom Preset Only)...` dialog,
- the supporting Settings-side dialogs (`Setup & Diagnostics`, `Help`, `A Message`),
- and the OCR review/completion flow.

## ASCII flow

```text
User opens TejOCR Settings
  |
  v
Main Settings dialog
  |
  +-- Save defaults and close
  |
  +-- Setup & Diagnostics
  |     -> dependency probe
  |     -> install guidance / copy command / re-check
  |
  +-- Help
  |     -> settings help dialog
  |
  +-- A Message
  |     -> advocacy dialog
  |     -> Open aKriti
  |
  +-- Advanced Engine Parameters (Custom Preset Only)
        -> PSM selection
        -> OEM selection
        -> Use Settings / Cancel
```

## Settings family flow

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["Open TejOCR Settings"] --> B["Main Settings dialog"]
  B -->|Save| C["Persist defaults + close"]
  B -->|Setup & Diagnostics| D["Dependency/setup dialog"]
  B -->|Help| E["Settings Help dialog"]
  B -->|A Message| F["Advocacy dialog"]
  B -->|Advanced Engine Parameters| G["PSM/OEM dialog"]
  D --> D1["Re-check / copy commands / install hints"]
  F --> F1["Open aKriti"]
  G --> G1["Use Settings / Cancel"]

## OCR run dialog flow

```text
OCR command
  |
  v
OCR options dialog (or fallback defaults)
  |
  v
OCR engine execution
  |
  +-- preview enabled?
  |     +-- yes -> Review dialog / fallback confirm
  |     +-- no  -> direct output
  |
  v
Output insertion / clipboard / replace-image
  |
  v
OCR Complete dialog
  |
  +-- Result Summary
  +-- Source Breakdown (scrollable for larger batches)
  +-- OCR Profile
  +-- Runtime Diagnostics
```

## OCR review and completion flow

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["OCR Selected Image / OCR Image from File"] --> B["OCR options dialog or fallback"]
  B --> C["engine.perform_ocr()"]
  C --> D{"Preview enabled?"}
  D -->|Yes| E["Review dialog or fallback confirm"]
  D -->|No| F["Direct output"]
  E --> F
  F --> G["handle_ocr_output()"]
  G --> H["OCR Complete dialog"]
  H --> I["Close and return focus to Writer"]

## Notes

- The advanced-parameters dialog is a Settings-side dialog and is intended for `Custom` tuning, even though the visible button is always reachable from Settings.
- `OCR Complete` is now a dedicated structured dialog, not just a debug-style message box.
- For larger batches, the source list is intentionally scrollable instead of forcing the dialog to grow indefinitely.
