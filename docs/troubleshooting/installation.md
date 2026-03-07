# Troubleshooting Installation and Metadata Errors

This guide covers install-time and metadata problems in LibreOffice extension
installation and provides exact recovery steps.

```text
TejOCR .oxt install
  -> parse description.xml
  -> validate license, id, version, display metadata
  -> validate manifest resources
  -> register UNO service (ProtocolHandler)
  -> cache extension info
  -> show extension card / execute commands
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["Install TejOCR .oxt"] --> B["Parse description.xml"]
  B --> C["Validate registration tags"]
  C --> D["Validate LICENSE/resource paths"]
  D --> E["Load META-INF/manifest.xml"]
  E --> F["Verify every referenced file exists"]
  F --> G["Register protocol handler + UNO entry"]
  G --> H["Cache extension metadata"]
  H --> I["Extension Manager card shown"]
```

## 1) `DeploymentException: Could not obtain path to license`

Error family:
`com.sun.star.deployment.DeploymentException` with message containing
`Could not obtain path to license`  
or
`Possible error in description.xml`.

### Why

The install parser could not resolve the `<license-text>` path from `description.xml`.

In this repository it must resolve to:
`LICENSE` from extension root and be listed in `META-INF/manifest.xml`.

### Checks

- `description.xml` has valid XML syntax and UTF-8 header.
- `LICENSE` exists at extension root.
- `META-INF/manifest.xml` contains:
  - `manifest:full-path="LICENSE"` with text/plain media type.
- `description.xml` includes:
  - `<registration><simple-license ...><license-text xlink:href="LICENSE" .../></simple-license></registration>`
- If `simple-license` uses `default-license-id`, one `license-text` entry must have a matching `license-id`.
  If there is only one license file, do not set `default-license-id` at all.

### Recovery workflow

```text
1. Quit LibreOffice completely.
2. Delete stale extension cache:
   - macOS: ~/Library/Application Support/LibreOffice/*/user/uno_packages/cache/uno_packages/
   - Linux: ~/.config/libreoffice/*/user/uno_packages/cache/uno_packages/
3. Uninstall existing TejOCR.
4. Rebuild fresh OXT from current source.
5. Reinstall + restart LibreOffice.
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["License path error"] --> B["quit LibreOffice"]
  B --> C["clear uno_packages cache"]
  C --> D["uninstall old extension"]
  D --> E["rebuild TejOCR-*.oxt"]
  E --> F["reinstall from fresh package"]
  F --> G["restart and verify"]
```

## 2) Extension Manager displays raw XML block instead of card

### Symptom

The manager row shows the raw `<description>` XML block (display-name/dependencies),
instead of the parsed name/metadata.

### Why this happens

Most commonly caused by:
- malformed `description.xml`,
- wrong resource paths in `description.xml`,
- invalid `simple-license` metadata such as `default-license-id` without a matching `license-id`,
- manifest/resource mismatch,
- stale cached metadata after a broken install.

### Fix

```text
1. Quit LibreOffice.
2. Clear cache directory (same as above).
3. Uninstall previous TejOCR package.
4. Rebuild from clean source.
5. Reinstall and relaunch.
```

### What to verify

- `description.xml` has a valid opening and closing tag: `<?xml ...?>` and `</description>`.
- `identifier` remains stable: `org.libreoffice.TejOCR`.
- `icon` paths are valid and reachable (e.g. `icons/tejocr_48.png`).
- `version` in description file matches manifest/package release version.

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["Raw XML shown in Manager"] --> B{"Fresh package?"}
  B -->|No| C["Rebuild OXT from clean tree"]
  B -->|Yes| D["Validate description.xml parse"]
  C --> E["Clear extension cache"]
  D --> E
  E --> F["Reinstall and relaunch"]
```

## 3) `identifier` mismatch or upgrade settings issues

### Why

Extension upgrade relies on stable extension ID.
Changing it breaks settings migration and cache indexing.

### Required contract

- Keep `description.xml` identifier as:
  - `org.libreoffice.TejOCR`
- Keep protocol service registration stable:
  - `com.sun.star.frame.ProtocolHandler`

### If users report lost config

1. Remove stale cache.
2. Rebuild and reinstall.
3. Confirm identifier is unchanged in built archive + extension manager cache.

## 4) Setup/diagnostics unavailable on first launch

This is usually recoverable and may not block OCR.

### Quick runtime checks

```text
Settings command
 -> if XDL unavailable, fallback config editor path is used
 -> dependency status is shown with install command suggestion
 -> OCR still proceeds using saved defaults
```

### Logs to watch

- `com.sun.star.awt.UnoControlDialogModel` failures
- `supports_uno_dialog_model` result
- `Could not create OCR options dialog` / `fallback form skipped`

## 5) macOS crash popup mentioning `LibreOfficePython`

### Symptom

macOS shows a crash report for:

- `LibreOfficePython`
- `Code Signature Invalid`
- `Launch Constraint Violation`

while opening Settings, Setup & Diagnostics, or running PDF/file OCR.

### Why this happens

LibreOffice bundles helper launchers such as:

- `Contents/Resources/python`
- `python3-config`
- `python3.11-config`

Those are not safe interpreter targets for TejOCR runtime guidance. If a runtime probe executes them, macOS may kill the helper process even though LibreOffice itself stays open.

### Expected safe interpreter path

On macOS, install guidance should point to the real framework interpreter, for example:

`/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3`

not:

`/Applications/LibreOffice.app/Contents/Resources/python`

### Recovery workflow

```text
1. Quit LibreOffice fully.
2. Rebuild or reinstall the latest TejOCR package.
3. Reopen Settings and Setup & Diagnostics.
4. Verify copied install commands use the framework python3 path, not Resources/python.
5. If the popup still appears, capture the new crash report and the rebuilt package version.
```

## 5) Why replacement mode differs between selected-image and file-image

`replace_image` requires a selected replacement target.

Method flow:
- Selected image flow captures:
  - `insertion_anchor`
  - `replacement_target`
  via `_capture_selected_image_anchor()`.
- File image flow has only file path; no selected target exists.
- Therefore file flow cannot replace directly and is coerced to cursor output.

If users report "replace image" with file path mode, expected behavior is
stable cursor/text insertion, not in-place replacement.

## 6) Trusted executable path note

TejOCR allows a custom Tesseract executable path. That path is treated as trusted.

Practical meaning:

- if the path points to the real Tesseract binary, OCR works normally,
- if the path points to some other executable, TejOCR will run that executable.

This is a local trust boundary, not a remote exploit path, but it is still important operationally.

Recommendation:

- prefer auto-detect when possible,
- use custom path only for a known-good local Tesseract install,
- reset the field to blank if you are not sure.

## 7) Commands

### Rebuild and package

```bash
python3 build_tejocr.py
```

### Remove stale cache (macOS)

```bash
rm -rf "~/Library/Application Support/LibreOffice"/*/user/uno_packages/cache/uno_packages/
```

### Remove stale cache (Linux)

```bash
rm -rf ~/.config/libreoffice/*/user/uno_packages/cache/uno_packages/
```

Use these commands when:
- raw XML persists after reinstall,
- icon/card still stale after upgrade,
- dependency/metadata UI does not reflect fresh package state.

## 8) Capture data for support

When the issue persists, share:
- full install exception text,
- short `soffice` log around the install,
- extension package SHA/size,
- LO version and OS,
- whether cache clear + rebuild reproduces.

This usually separates metadata descriptor issues from runtime UNO service issues quickly.

## 9) Hidden OCR executor rollback for maintainers

For one-release rollout comparisons, TejOCR also supports a hidden executor setting in the fallback settings file:

```text
HiddenOcrExecutor=modern
HiddenOcrExecutor=legacy
```

Use `legacy` only for maintainer comparison and rollback checks. It is not intended as a normal user-facing mode.

Recommended validation flow:

```text
1. Keep normal runs on modern.
2. Generate a legacy baseline report with the local benchmark corpus.
3. Run the modern comparison against that baseline.
4. Switch back to modern after verification.
```
