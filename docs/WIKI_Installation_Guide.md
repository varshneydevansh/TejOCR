# TejOCR Installation and Dependency Guide

Use this guide to set up TejOCR and Tesseract OCR for each supported operating system.

## Contents

- [Prerequisites](#prerequisites)
- [Download and Install TejOCR](#download-and-install-tejocr)
- [Install Tesseract OCR](#install-tesseract-ocr)
- [Install LibreOffice Python Dependencies](#install-libreoffice-python-dependencies)
- [Verify Installation](#verify-installation)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Prerequisites

- LibreOffice installed
- Internet access for package downloads
- Permissions to install software/packages on your machine

## Download and Install TejOCR

1. Open LibreOffice.
2. Go to **Tools → Extension Manager → Add**.
3. Select the latest `TejOCR-0.1.7.oxt` file.
4. Restart LibreOffice after install.
5. Open Writer and confirm menu entry: **Tools → TejOCR**.

## Install Tesseract OCR

Install core OCR engine first. This is required by TejOCR.

### macOS

#### Homebrew

```bash
brew install tesseract
```

Check:

```bash
which tesseract
tesseract --version
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y tesseract-ocr
```

Check:

```bash
which tesseract
tesseract --version
```

### Fedora / RHEL / CentOS

```bash
sudo dnf install -y tesseract
```

Check:

```bash
which tesseract
tesseract --version
```

### Windows (PowerShell or CMD)

Use a Windows Tesseract installer build from:
https://github.com/UB-Mannheim/tesseract/wiki

After installation, verify:

```cmd
where tesseract
tesseract --version
```

### Optional language packs (Linux and macOS package managers)

Install extra language packages if needed (examples):

```bash
# Ubuntu/Debian
sudo apt install -y tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-deu

# macOS (formula specific languages may vary by package source)
brew install tesseract-lang
```

## Install LibreOffice Python Dependencies

TejOCR runs in LibreOffice’s embedded Python runtime, so dependencies must be installed there.

### Quick path discovery

Open a terminal and run:

#### macOS

```bash
"/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3" --version
```

If this path exists, install:

```bash
"/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3" -m pip install numpy pytesseract pillow
```

#### Windows (CMD/PowerShell)

```cmd
"C:\Program Files\LibreOffice\program\python.exe" --version
```

```cmd
"C:\Program Files\LibreOffice\program\python.exe" -m pip install numpy pytesseract pillow
```

#### Linux

Common paths vary by distribution:

```bash
/opt/libreoffice* /usr/bin/libreoffice /usr/lib/libreoffice/program
```

Find the exact binary, then:

```bash
/path/to/libreoffice/python -m pip install numpy pytesseract pillow
```

### Use repository helper script

From the TejOCR folder:

```bash
python3 install_dependencies.py
```

If script is not working in your environment, use the manual commands above.

## Verify Installation

Use TejOCR UI:

1. Open LibreOffice Writer.
2. Go to **Tools → TejOCR → Settings**.
3. Confirm:
   - Tesseract status shows installed version
   - Python dependency status shows NumPy, Pytesseract, Pillow as available

Use CLI quick check:

```bash
tesseract --version
```

```bash
python3 install_dependencies.py
```

Inside LibreOffice:
- open **Tools → TejOCR → Settings**
- test Tesseract path and dependencies directly from UI

## Troubleshooting

### 1) `Could not obtain path to license` or similar extension install error

Most often this is caused by invalid extension metadata or missing references.

Check:

- `description.xml` is valid XML
- License path is present and correct (referenced file exists in extension package)
- No malformed XML entities in metadata files
- Icon paths in `description.xml` are valid and point to existing files

Then rebuild and reinstall the `.oxt`.

### 2) OCR runs but dependencies are still red

- Ensure the same tesseract binary used in terminal is also reachable from LibreOffice runtime.
- Reinstall LO Python packages using the exact LO Python path.
- Restart LibreOffice and reopen the Settings page to force refreshed checks.

### 3) Image OCR output does not appear where expected

- If using image replacement mode, confirm selected object is a supported image/shape.
- For cursor insertion, keep cursor in a text area and avoid selection of unsupported elements.

## OCR Engine Tuning (Preset, PSM, OEM, Preview)

TejOCR has two places where these values are configured.

- **Settings** (`Tools → TejOCR → Settings`) stores defaults that persist across sessions.
  - `DefaultQualityPreset` (`fast`, `balanced`, `accurate`, `custom`)
  - `DefaultPSM`
  - `DefaultOEM`
  - `DefaultScaleFactor`
  - grayscale / binarize / invert / improve image flags
  - `ShowPreviewBeforeOutput`
- **OCR Options dialog** for each run (`OCR Selected Image` or `OCR Image from File`) can override the defaults
  with the same fields before execution.

This means users get stable defaults in Settings, and still can experiment per image in the options dialog.

### What each control means

#### Presets

Preset is a profile that applies an initial set of values to advanced controls.

- `fast` (`psm=11`, `oem=3`, scale `1.0`, grayscale off, binarize off)
- `balanced` (default): `psm=3`, `oem=3`, scale `1.0`, grayscale on
- `accurate`: `psm=6`, `oem=3`, scale `1.5`, grayscale on, binarize on, improve image on
- `custom`: uses the manual `psm`, `oem`, scale, and preprocessing values directly

When `custom` is chosen, the engine uses the current manual values from UI values.

#### PSM: Page Segmentation Mode

PSM controls how Tesseract prepares page layout before recognition.

| Mode | Meaning |
|---|---|
| `0` | Orientation and script detection only |
| `1` | Automatic page segmentation with OSD |
| `2` | Automatic page segmentation, no OSD |
| `3` | Fully automatic, no OSD (default) |
| `4` | Single column of text with variable sizes |
| `5` | Single uniform block of vertical text |
| `6` | Single uniform block of text |
| `7` | Single text line |
| `8` | Single word |
| `9` | Single word in a circle |
| `10` | Single character |
| `11` | Sparse text |
| `12` | Sparse text with OSD |
| `13` | Raw line |

#### OEM: OCR Engine Mode

| Mode | Meaning |
|---|---|
| `0` | Legacy engine only |
| `1` | Neural nets LSTM only |
| `2` | Legacy + LSTM |
| `3` | Auto selection (default) |

#### Output, preview, and fallback behavior

- `ShowPreviewBeforeOutput` controls whether OCR text is shown in a preview window before insertion.
- If the session does not support LibreOffice multiline dialog controls, TejOCR uses a compatibility preview summary and proceeds with insertion when allowed.
- If preview is disabled, text is inserted immediately in the selected output mode.

Preview can be toggled in **Settings** and for each run in OCR options UI.

### Runtime option resolution

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    classDef start fill:#0f62fe,color:#ffffff,stroke:#003cb3,stroke-width:1.5px
    classDef process fill:#1f6feb,color:#ffffff,stroke:#1347a0,stroke-width:1px
    classDef decision fill:#f7b731,color:#1f2937,stroke:#b5880a,stroke-width:1.5px
    classDef success fill:#22c55e,color:#ffffff,stroke:#15803d,stroke-width:1px
    classDef fallback fill:#ef4444,color:#ffffff,stroke:#991b1b,stroke-width:1px
    classDef preview fill:#fb7185,color:#ffffff,stroke:#be123c,stroke-width:1px

    A["User starts OCR action"]:::start --> B["Load default OCR options from settings"]:::process
    B --> C["Read current OCR options dialog values"]:::process
    C --> D{"Preset = custom?"}:::decision
    D -- No --> E["Apply preset profile (psm, oem, scale, preprocessing)"]:::process
    D -- Yes --> F["Use manual option values from dialog"]:::process
    E --> G["Final options object"]:::process
    F --> G
    G --> H["perform_ocr()"]:::process
    H --> I["Run OCR attempts: fallback OEM list and fallback PSM list"]:::fallback
    I --> J{"Text found?"}:::decision
    J -- yes --> K["Optional preview then insert in selected output mode"]:::success
    J -- no --> L["Auto-enhanced preprocessing fallback"]:::fallback
    L --> I
```

```text
+------------------------------+
| Start OCR action             |
+--------------+---------------+
               |
               v
+------------------------------+
| _build_default_ocr_options()
+--------------+---------------+
               |
               v
+-------------------------------+
| _normalize_dialog_result()
|  - preset/psm/oem/scale flags |
+---------------+---------------+
                |
   +------------+-----------+
   | Preset is custom?      |
   | no -> profile overrides|
   | yes -> manual values   |
   +------------+-----------+
                |
                v
       +----------------------+
       | _perform_ocr_with... |
       +----------+-----------+
                  |
       +----------------------+
       | _fallback_oem_values |
       | _fallback_psm_values |
       +----------+-----------+
                  |
                  v
          +---------------------+
          | Preview (if enabled)|
          | then output router  |
          +---------------------+
```

### Practical starting profiles

- Start with `balanced + psm=3 + oem=3`.
- For sparse text, try `psm=11` and `Preset=custom`.
- For noisy low-contrast scans, use `Preset=accurate`, `scale=1.5`, and keep grayscale/binarize on.

For a deeper method-level reference, see:

- `reference/ocr-options-and-engine-tuning.md`
- `python/tejocr/constants.py` (preset/mode constants)
- `python/tejocr/tejocr_service.py` (option resolution)
- `python/tejocr/tejocr_engine.py` (attempt and fallback loops)

## OS-specific dependency matrix

The commands below are the practical defaults used by TejOCR users.

### macOS

| Task | Command |
|---|---|
| Install OCR engine | `brew install tesseract` |
| Install LO Python dependencies | `/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract pillow` |
| Check OCR path | `which tesseract` |

### Windows

| Task | Command |
|---|---|
| Install OCR engine | Download and install from [UB-Mannheim release page](https://github.com/UB-Mannheim/tesseract/wiki) |
| Install LO Python dependencies | `"C:\\Program Files\\LibreOffice\\program\\python.exe" -m pip install numpy pytesseract pillow` |
| Check OCR path | `where tesseract` |

### Debian / Ubuntu

| Task | Command |
|---|---|
| Install OCR engine | `sudo apt update && sudo apt install -y tesseract-ocr` |
| Install LO Python dependencies | `sudo apt install -y python3-pip` then use LibreOffice Python path with pip |
| Check OCR path | `which tesseract` |

### Fedora / RHEL / Rocky / Alma / CentOS

| Task | Command |
|---|---|
| Install OCR engine | `sudo dnf install -y tesseract` |
| Install LO Python dependencies | Use your LibreOffice Python interpreter + pip |
| Check OCR path | `which tesseract` |

### Arch / Manjaro

| Task | Command |
|---|---|
| Install OCR engine | `sudo pacman -S tesseract` |
| Install LO Python dependencies | Use your distro package path for LibreOffice python |
| Check OCR path | `which tesseract` |

### Linux fallback discovery (if path is unknown)

```bash
which tesseract
python3 -c "import sys,subprocess; print(sys.executable)"
```

Then run pip via that exact interpreter for `numpy`, `pytesseract`, and `pillow`.

For exact OCR command references and project links:

- Tesseract upstream: https://github.com/tesseract-ocr/tesseract
- Tesseract docs: https://tesseract-ocr.github.io/

## References

- Tesseract OCR source repository: https://github.com/tesseract-ocr/tesseract
- Tesseract docs and usage guides: https://tesseract-ocr.github.io/
- TejOCR repository: https://github.com/varshneydevansh/TejOCR
