# Metadata and Packaging Notes

## `description.xml` contract

```text
description.xml
  -> version
  -> identifier
  -> display-name (localized)
  -> dependencies
  -> publisher
  -> release-notes + license path
  -> icon references
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["description.xml"] --> B["version"]
    A --> C["identifier"]
    A --> D["display-name (localized)"]
    A --> E["dependencies"]
    A --> F["publisher"]
    A --> G["release-notes + license path"]
    A --> H["icon references"]
```

Required sections are:
- `version`
- `identifier` (must remain stable for upgrades)
- `platform`
- `dependencies` (LibreOffice minimal)
- `registration` + license references
- `icon` with default and optional high-contrast asset

### Common failure causes

- Non-XML valid `description.xml` content (malformed tags/quotes)  
- Icon paths not found in archive
- License or release-note file path missing from manifest

## `META-INF/manifest.xml` contract

```text
manifest
  -> component registration
  -> python modules
  -> dialogs
  -> resources (icons, docs, license, help files)
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["manifest"] --> B["component registration"]
    A --> C["python modules"]
    A --> D["dialogs"]
    A --> E["resources"]
```

- Each file included at install time must have a manifest entry.
- Removing/renaming files without manifest updates causes parser/runtime mismatches.

## Distribution symptom: “Could not obtain path to license”

Observed as: `DeploymentException` or deployment/license path error.

Likely causes:
1. `LICENSE` missing from package root.
2. Manifest missing `LICENSE` resource entry.
3. Stale cache serving an older `.oxt` metadata set.

Fix:
- ensure `LICENSE` exists in source and manifest entry exists for it
- clean rebuild
- uninstall + restart LibreOffice and reinstall

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["Could not obtain path to license"] --> B["ensure LICENSE exists in package root"]
    B --> C["ensure LICENSE in manifest"]
    C --> D["clean rebuild"]
    D --> E["uninstall + restart + reinstall"]
```

## Extension Manager showing raw XML text

Symptoms:
- extension entry card displays raw `<?xml ...>` instead of parsed card.

Likely causes:
- cached stale descriptor from prior broken build
- package build with malformed descriptor or incomplete archive

Fix checklist:
```text
1) Quit LibreOffice completely
2) Remove extension cache entry under:
   ~/Library/Application Support/LibreOffice/*/user/uno_packages/cache/uno_packages/
3) Uninstall old TejOCR package
4) Rebuild with clean manifest + description
5) Reinstall latest .oxt
6) Relaunch LibreOffice
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["Quit LibreOffice completely"] --> B["Remove cache entry"]
    B --> C["Uninstall old TejOCR package"]
    C --> D["Rebuild with clean manifest + description"]
    D --> E["Reinstall latest .oxt"]
    E --> F["Relaunch LibreOffice"]
```

If issue persists:
- open debug log for `DeploymentException` details
- verify XML file content served by the package (not mangled local system path)

```text
Deployment validation sequence

install .oxt
  -> parse description.xml
  -> validate registration + license path
  -> validate manifest resource entries
  -> register services and UI resources
  -> cache metadata for extension manager
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
    A["install .oxt"] --> B["parse description.xml"]
    B --> C["validate registration + license path"]
    C --> D["validate manifest resource entries"]
    D --> E["register services and UI"]
    E --> F["cache metadata"]
```

Required sanity list for every release:
- `description.xml` is valid UTF-8 XML, no smart quotes or non-UTF-8 control characters in tags
- icon paths are present in package and manifest
- `LICENSE` path resolves in both description and manifest
- `META-INF/manifest.xml` includes every runtime/dialog/resource file

## Icon metadata

- `description.xml` references:
  - `icons/tejocr_48.png`
  - `icons/tejocr_48_hc.png`
- These must exist in package and be reachable via manifest.

Use `python scripts/generate_icons.py` whenever the brand mark changes.
