# TejOCR Installation and Dependency Guide

Use this guide to set up TejOCR and Tesseract OCR for each supported operating system.

## Contents

- [Prerequisites](#prerequisites)
- [Download and Install TejOCR](#download-and-install-tejocr)
- [Install Tesseract OCR](#install-tesseract-ocr)
- [Install LibreOffice Python Dependencies](#install-libreoffice-python-dependencies)
- [Install PDF Renderer Dependencies](#install-pdf-renderer-dependencies)
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
3. Select the latest `TejOCR-*.oxt` file.
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
   - PDF renderer status row in Setup & Diagnostics

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

## Install PDF Renderer Dependencies

PDF support in **OCR Image/PDF from File** requires a PDF renderer in the environment.

If no renderer is installed, TejOCR shows:

```
No PDF renderer found. Install one of:
 - poppler / pdftoppm
 - mupdf / mutool
 - pdf2image in this LibreOffice Python
```

### macOS

```bash
brew install poppler
brew install mupdf
"/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3" -m pip install pdf2image
```

### Windows

```cmd
choco install poppler
```

or

```cmd
scoop install poppler
```

```cmd
"C:\\Program Files\\LibreOffice\\program\\python.exe" -m pip install pdf2image
```

### Linux (Debian/Ubuntu family)

```bash
sudo apt-get install poppler-utils
sudo apt-get install mupdf-tools
/path/to/libreoffice/python -m pip install pdf2image
```

### Linux (RPM family)

```bash
sudo dnf install poppler-utils  # Fedora
sudo dnf install mupdf-tools     # Fedora
```

Then install `pdf2image` in LibreOffice Python if renderer tools are unavailable.

### Why this is needed

- `poppler` or `mupdf` is the fastest option because TejOCR renders PDF pages directly with native tools.
- `pdf2image` is used as a compatibility fallback when native tools are not available.
- In multi-file runs, each PDF page is converted and processed as an image.

The setup diagnostics page now includes:

- PDF renderer name (when detected)
- `Install` section with exact commands for the current OS/runtime
- One-click copy for the recommended command

## Current diagnostics behavior (current runtime)

TejOCR now performs a runtime dependency check against the actual LibreOffice Python interpreter used by the extension. The check includes:

- Tesseract executable path
- NumPy
- Pytesseract
- Pillow
- PDF renderer stack:
  - `pdftoppm` (Poppler)
  - `mutool` (MuPDF)
  - `pdf2image` fallback + `poppler` binaries in the same environment

The diagnostics screen now follows this behavior:

```text
Dependency check requested
  |
  +-- Tesseract checked from stored path (fallback to PATH)
  +-- Python package checks (numpy / pytesseract / pillow)
  +-- PDF renderer check:
  |      - success -> status becomes "pdf2image + poppler" / "pdftoppm" / "mutool"
  |      - fail    -> status becomes "Not found" with explicit missing component
  |
  +-- if missing:
         build install commands for current platform/runtime
         show each command as numbered copy targets
         show summary line:
           "PDF renderer missing. Copy the command(s) and install a PDF renderer."
         OR "PDF renderer missing. Copy the command and install a PDF renderer."
```

```mermaid
flowchart TD
  A[Setup & Diagnostics opened] --> B[Run dependency probe against LO Python]
  B --> C{PDF renderer detected?}
  C -->|Yes| D[Show row: ✅ PDF renderer available]
  C -->|No| E[Build deduplicated install plan]
  E --> F[Display numbered command payload]
  F --> G[Copy Command(s) button enabled]
  G --> H[Copy status updates: Copying... -> Copied ✓]
  C -->|No| I[Re-Check available]
  I --> B
  D --> H2[Copy Command hidden/disabled]
```

### Copy command behavior in Setup & Diagnostics

- **One or more commands needed:** the button label now shows how many commands are available (for example: `Copy Command(s) (3)`).
- **Copy action status:** button text changes from `Copy Command` (or `Copy Command(s) (N)`) → `Copying...` and then to `Copied ✓` / `Copied N ✓` on success.
- **Copy behavior:** when multiple install commands are needed (for example, OS hint + runtime pip path), the command payload is deduplicated, line-separated, and copied as a single clipboard block.
- **Re-check behavior:** Re-check runs immediately in-session, re-queries the active LibreOffice Python runtime, and updates renderer checks and button states without requiring dialog reopen.
- **Command payload:** full shell commands are copied line-by-line with platform/runtime exactness; includes spaces and interpreter path quoting when needed.
- **Re-Check semantics:** `Re-Check` immediately recalculates the diagnostic state in-session and updates labels/status without reopening the Settings dialog.

```text
Re-check sequence
1) click Re-Check
2) dependency probe reruns (PATH refreshed + module cache refresh)
3) PDF row + install command list updates in-place
4) copy label returns to "Copy Command" state if still missing
```

```text
macOS example payload
1) /Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install pdf2image
2) brew install poppler
3) brew install mupdf
```

```text
Windows example payload
1) "C:\Program Files\LibreOffice\program\python.exe" -m pip install pdf2image
2) choco install poppler
3) scoop install poppler
```

```text
Linux example payload
1) /path/to/libreoffice/python -m pip install pdf2image
2) sudo apt-get install poppler-utils
3) sudo apt-get install mupdf-tools
```

## Bulk Image + PDF OCR behavior

From the `OCR Image/PDF from File` flow, TejOCR now supports mixed batches of image files and PDF files in one picker selection.

### What happens at runtime

```text
User selects files → Normalized path list
  |
  +-- each entry is converted from UNO URL (file://) to system path
  +-- duplicates removed and missing files are reported
  |
  +-- file loop:
      |
      +-- Image (png/jpg/jpeg/bmp/gif/tif/tiff/webp)
      |     -> direct OCR image
      |
      +-- PDF
            -> rasterize each page
            -> OCR each extracted PNG page
  |
  +-- merged or per-source output depending on Merge Batch Results
  +-- final success/error summary shown in OCR Complete popup
```

### Batch preview semantics

- Preview is shown before output when **Show Preview** is enabled.
- For 1 source: preview is that source's text.
- For multi-source runs: preview uses a **single consolidated text block** when:
  - more than two sources are selected, or
  - the combined content is large (>9,000 chars), or
  - UNO multiline dialog is unavailable in current LO runtime.
- The review title includes source count and file/PDF mix, for example:
  - `Review OCR result — 4 files, 1 PDFs`

```text
Batch run behavior (OCR Image/PDF from File)
If merge_batch_results=true:
  * all successful sources/pages are merged into one output payload
  * failure entries are shown in summary only

If merge_batch_results=false:
  * each successful item/page is inserted independently (subject to per-item cancel)
  * failed items are still listed in final report
```

### Install command handling in Setup & Diagnostics

When PDF renderer checks fail, Setup & Diagnostics now:

1. Re-checks renderer hints dynamically (PATH refresh + module reload).
2. Builds a **de-duplicated command list** (platform binaries + python runtime pip command).
3. Enables copy only when there is at least one command to run.
4. Shows a **single numbered list** so users can copy exact commands for their runtime.
5. Can be re-run immediately after installation so users can confirm fixes in one open session.

```text
Examples:
Copy Command(s) (2)
1. brew install poppler
2. /Applications/LibreOffice.app/.../python3 -m pip install pdf2image
```

### Filename safety note

File picker candidates can include URLs with spaces and commas (for example:
`ChatGPT Image May 3, 2025, 10_19_30 PM.png`).

Normalization contract in this version:

- normalize by splitting on explicit multi-URL markers (`file://...`) and payload delimiters only,
- merge obvious URL fragments that are split into percent-encoded pieces,
- keep any still-unresolved tokens as explicit failures (`File not found`) instead of silently skipping.

```text
Example failure path currently preserved:
Selected:
• ChatGPT Image May 3, 2025, 10_19_30 PM.png
Resulting status:
• ChatGPT Image May 3 -> File not found
• %202025 -> File not found
• %2010_19_30 PM.png -> File not found
```

This explicit failure behavior is intentional so users can retry after renaming files or installing runtime fixes.

### Runtime verification for mixed batches

In mixed image+PDF runs, a PDF source is validated against renderer availability independently of image files:

- If renderers are present, each PDF page is converted and OCR’d in sequence.
- If a PDF page source fails, the failure is included in the final summary while successfully processed images continue.
- Image entries keep processing even when PDFs fail.

```text
Selected:
  • ChatGPT_Image.png (image) -> processed
  • invoice.pdf (PDF) -> fails: No PDF renderer found
  • Aadhaar.png (image) -> processed

Summary:
  • 2 success, 1 failed source
  • failed source remains actionable for retry after installing PDF renderer
```

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
- Re-run **Re-Check** in the same Settings session first (it now re-evaluates all diagnostics immediately).  
  If the session is very old, close/reopen Settings or restart LibreOffice as a fallback.

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

TejOCR probes OEM support once per OCR session. If the current runtime cannot honor legacy modes,
`0` and `2` are marked unsupported in the UI and are rejected before OCR runs.

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
    H --> I["Resolve bounded execution plan"]:::process
    I --> J["Run exact attempt, then optional recovery"]:::fallback
    J --> K{"Text found?"}:::decision
    K -- yes --> L["Optional preview then insert in selected output mode"]:::success
    K -- no --> M["Return warning or install hint"]:::fallback
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
