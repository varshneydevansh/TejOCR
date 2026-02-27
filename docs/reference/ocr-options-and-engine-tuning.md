# OCR Options and Engine Tuning (Preset, PSM, OEM, and Preview)

TejOCR exposes four OCR behavior layers in the same workflow:

- OCR quality and extraction preset
- Page segmentation mode (`psm`)
- OCR engine mode (`oem`)
- Preview/edit behavior before insertion

This document explains where each control is set, what it changes internally, and how it behaves at runtime.

## Where the user sees and sets these options

For each OCR run (`OCR Selected Image` and `OCR Image from File`):

1. Open the OCR action.
2. Use the OCR options dialog.
3. Set:
   - Language
   - Output mode
   - Preset
   - `psm`
   - `oem`
   - preprocessing flags (`grayscale`, `binarize`, `invert`, `scale`, `improve_image`)
4. Confirm to execute.

Defaults are stored and prefilled from extension settings:

- `default_output_mode`
- `LastOutputMode`
- `DefaultQualityPreset`
- `DefaultPSM`
- `DefaultOEM`
- `DefaultScaleFactor`
- `DefaultPreprocessingGrayscale`
- `DefaultPreprocessingBinarize`
- `DefaultPreprocessingInvert`
- `DefaultImproveImageQuality`
- `ShowPreviewBeforeOutput`

If the dialog framework is unavailable in the current LibreOffice runtime, OCR still proceeds from saved defaults.

## Preset behavior

Preset controls are applied as a profile bundle over the selected base options.

| Preset key | Label | Description | Core override |
|---|---|---|---|
| `fast` | Fast | faster extraction path | `psm=11`, `oem=3`, scale `1.0`, preprocessing off |
| `balanced` | Balanced | default profile | `psm=3`, `oem=3`, scale `1.0`, `grayscale=on` |
| `accurate` | Accuracy | quality-first profile | `psm=6`, `oem=3`, scale `1.5`, `grayscale=on`, `binarize=on`, `improve_image=on` |
| `custom` | Custom | no profile override | uses manual values from dropdowns/checkboxes |

Implementation detail:
- In `default` mode, user selection is resolved first.
- If preset is not `custom`, corresponding profile values replace manual values.
- If preset is `custom`, manual values from UI are used as-is.

## What PSM means

`psm` controls layout segmentation before OCR.

TejOCR accepts these values directly from UI and settings:

| `psm` | Meaning |
|---|---|
| `0` | Orientation and script detection only |
| `1` | Full page segmentation with OSD |
| `2` | Full page segmentation, OSD off |
| `3` | Fully automatic, OSD off *(default)* |
| `4` | Single column of varying text height |
| `5` | Single uniform block of vertically aligned text |
| `6` | Single uniform block of text |
| `7` | Single text line |
| `8` | Single word |
| `9` | Single word in circle |
| `10` | Single character |
| `11` | Sparse text |
| `12` | Sparse text with OSD |
| `13` | Raw line |

## What OEM means

`oem` selects the Tesseract recognition engine path.

| `oem` | Meaning |
|---|---|
| `0` | Legacy engine only |
| `1` | LSTM engine only |
| `2` | Legacy + LSTM |
| `3` | Auto selection *(default)* |

## Runtime call flow for these options

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    classDef start fill:#0f62fe,color:#ffffff,stroke:#003cb3,stroke-width:1.5px
    classDef process fill:#1f6feb,color:#ffffff,stroke:#1347a0,stroke-width:1px
    classDef decision fill:#f7b731,color:#1f2937,stroke:#b5880a,stroke-width:1.5px
    classDef success fill:#22c55e,color:#ffffff,stroke:#15803d,stroke-width:1px
    classDef fallback fill:#ef4444,color:#ffffff,stroke:#991b1b,stroke-width:1px
    classDef preview fill:#fb7185,color:#ffffff,stroke:#be123c,stroke-width:1px
    classDef output fill:#8b5cf6,color:#ffffff,stroke:#6d28d9,stroke-width:1px

    A["OCR command selected"]:::start --> B["_build_default_ocr_options()"]:::process
    B --> C["_normalize_dialog_result()"]:::process
    C --> D{"Preset == custom?"}:::decision
    D -- no --> E["apply selected preset profile (psm/oem/scale/preprocessing)"]:::process
    D -- yes --> F["use manual psm/oem/scale/options values"]:::process
    E --> G["options = {lang, psm, oem, scale, preprocessing...}"]:::process
    F --> G
    G --> H["_perform_ocr_with_options()"]:::process
    H --> I["perform_ocr() in engine"]:::process
    I --> J["_build_tesseract_config('--oem X --psm Y')"]:::process
    J --> K["attempt loop over OEM/PSM + language fallback"]:::fallback
    K --> L{"show_preview"}:::decision
    L -->|off| M["insert to selected output mode"]:::success
    L -->|on| N["show_multiline_input_box or fallback preview"]:::preview
    N --> M
    M --> O["OCR Complete"]:::output
```

```text
+------------------------+
| OCR action invoked     |
+----------+-------------+
           |
           v
+--------------------------+
| _build_default_ocr_options |
+----------+---------------+
           |
           v
+----------------------------+
| _normalize_dialog_result   |
| - output mode             |
| - preset / psm / oem      |
+-----------+----------------+
            |
+-----------+-----------+
| Preset custom?        |
| no -> profile values  |
| yes -> manual values  |
+-----------+-----------+
            |
            v
   +--------------------+
   | _perform_ocr_with_ |
   | _options()         |
   +--------+-----------+
            |
            v
   +--------------------+
   | engine.perform_ocr  |
   +--------+-----------+
            |
            v
+----------------------+
| _build_tesseract_config|
| and retry attempts     |
+----------+-----------+
           |
           v
+---------------------+
| preview (if enabled) |
| then output handler  |
+---------------------+
```

## Runtime fallback behavior

Preset/PSM/OEM are not absolute. TejOCR performs controlled fallback for resilience:

- `_fallback_oem_values(primary)` adds default OEM alternatives
- `_fallback_psm_values(primary)` tries default/sparse options next
- `lang` fallback order is also applied when a language is unavailable
- If first pass returns empty text, engine runs an enhanced preprocessing recovery pass

This is why the same input may be retried with more than one `--oem --psm` combination internally.

## Preview workflow details

Preview is controlled by `ShowPreviewBeforeOutput`:

- If enabled, OCR returns extracted text to a multi-line preview/input step.
- If the session does not support the multi-line UNO dialog, TejOCR uses fallback preview summary output.
- If user cancels at preview stage, text is not inserted.

## Recommended first-pass profiles

- Start with `Balanced + PSM 3 + OEM 3`.
- If lines are merged or skewed: try `Preset=Custom`, `psm=7`, maybe `scale=1.3`, `binarize=on`.
- If text is sparse/noisy: try `PSM 11`, keep `binarize` on, then compare.
- If noisy scans remain weak: start from `Preset=accurate` and increase scale gradually (1.5+).

## Method-to-method references

- `python/tejocr/constants.py`  
  - `CFG_KEY_DEFAULT_PSM`, `CFG_KEY_DEFAULT_OEM`, `CFG_KEY_DEFAULT_PRESET`
  - `OCR_QUALITY_PRESETS`
  - `TESSERACT_PSM_MODES`, `TESSERACT_OEM_MODES`
- `python/tejocr/tejocr_service.py`
  - `_build_default_ocr_options`
  - `_normalize_dialog_result`
  - `_perform_ocr_with_options`
  - `_coerce_preset_request`, `_coerce_preset_profile`
  - `_build_preprocessing_summary`
- `python/tejocr/tejocr_interactive_dialogs.py`
  - option collection and preview-safe defaults
- `python/tejocr/tejocr_engine.py`
  - `perform_ocr`
  - `_build_tesseract_config`
  - `_fallback_oem_values`, `_fallback_psm_values`
  - `_run_ocr_attempts` loop logic

## Related documentation

- `docs/WIKI_Installation_Guide.md` (installation, dependency setup, and user-facing tuning entry point)
- `docs/reference/output-modes.md` (where output mode routing happens)
- `docs/reference/method-map.md` (full dispatch-to-runtime path)
