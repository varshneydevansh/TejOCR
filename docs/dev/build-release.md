# Build and Release Workflow

## Build entry points

```text
Developer change
  -> run build.py OR build_tejocr.py
  -> copy/collect extension files
  -> manifest + description validation
  -> zip -> TejOCR-<version>.oxt
  -> install into LibreOffice
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["Developer change"] --> B["run build.py OR build_tejocr.py"]
    B --> C["copy/collect extension files"]
    C --> D["manifest + description validation"]
    D --> E["zip -> TejOCR-<version>.oxt"]
    E --> F["install into LibreOffice"]
    F --> G["restart"]
```

### Legacy `build.py`

- Purpose: straightforward package assembly.
- Use case: local builds and fast iterations.
- Output path is the current default packaging output.

### `build_tejocr.py`

- Purpose: structured build with validation and summary logs.
- Useful for release branches when you need report + reproducibility.

## Release flow checklist

1. Update version markers:
   - `description.xml`
   - `README`/release notes (`CHANGELOG.md`) where applicable
2. Run icon generation if logo changed (or before release sanity check).
3. Run packaging script and inspect generated file:
   - confirm `description.xml` and `META-INF/manifest.xml` are inside.
4. Validate included resources:
   - Python files and entry point
   - all required dialogs
   - LICENSE and metadata files
5. Install `.oxt` into LibreOffice -> restart.
6. Verify in Extension Manager:
   - display name
   - icon rendering
   - install state and no install-time XML parser errors.

## Build quality guardrail checks

```text
manifest entries
  -> every file listed in zip manifest entry table
  -> every required file exists in archive
  -> service entry points resolve without import errors
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["manifest entries"] --> B["every file listed in zip manifest table"]
    B --> C["every required file exists in archive"]
    C --> D["service entry points resolve"]
    D --> E["build/reinstall safe"]
```

- `build.py` and `build_tejocr.py` both rely on manifest file list consistency.
- A stale manifest entry causes install/extension manager parse errors.

## Debugging install/runtime

- If installed extension card shows raw XML:
  - stale cache may be serving old metadata
  - rebuild and clear extension cache
  - ensure description paths use valid XML and matching file paths
- If dependencies show missing despite install:
  - check that extension was installed from latest rebuilt `.oxt` (older cache is common).

## Useful commands

- Install from package directory:
  - `python build_tejocr.py`
- Open LibreOffice package install flow:
  - Extensions → Extension Manager → Add… → pick `.oxt`
- Fresh restart after install/reinstall.

## Icon generation at release time

- Source image of truth:
  - `icons/main_logo.png`
- Generate all standard icon files with:
  - `python scripts/generate_icons.py`

## Release output artifacts

- `TejOCR-<version>.oxt` (current semver in the build)
- Temporary install cache updates in LibreOffice user profile

Keep build artifacts uncommitted unless required for distribution publishing.
