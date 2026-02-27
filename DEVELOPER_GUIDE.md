# TejOCR Developer Guide

This guide focuses on implementation, packaging, and runtime-safe debugging.

## Documentation structure (recommended path)

```text
README.md
  -> TECHNICAL.md
      -> docs/architecture/*
      -> docs/flow/*
      -> docs/reference/*
      -> docs/troubleshooting/*
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart LR
  R["README.md"] --> T["TECHNICAL.md"]
  T --> A["docs/architecture"]
  T --> F["docs/flow"]
  T --> M["docs/reference"]
  T --> TD["docs/troubleshooting"]
```

## Build and packaging workflow

```text
Change code/config
  -> run build script
  -> validate manifest + metadata
  -> create TejOCR-<version>.oxt
  -> install/restart LibreOffice
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["Code/metadata change"] --> B["build_tejocr.py or build.py"]
  B --> C["Collect/copy extension files"]
  C --> D["Validate manifest/resources"]
  D --> E["Create .oxt"]
  E --> F["Install + restart LO"]
```

## Standard commands

### Build

- `python build_tejocr.py`
- `python build.py`

### Install quickly (after build)

- Extensions → Extension Manager → Add…
- select the generated `.oxt`
- restart LibreOffice

### Generate icons from single source

- `icons/main_logo.png` is the one source of truth.
- Generate consistent icon set with:
  - `python scripts/generate_icons.py`

```text
Single-truth icon path
  icons/main_logo.png
      |
      +--> 16, 26, 48, 64 (normal)
      +--> 26_hc, 48_hc, 64_hc (high-contrast)
```

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1f6feb","primaryTextColor":"#ffffff","primaryBorderColor":"#1347a0","lineColor":"#7c3aed","secondaryColor":"#22c55e","tertiaryColor":"#f59e0b","mainBkg":"#dbeafe","background":"#ffffff","textColor":"#0f172a"}}}%%
flowchart TD
  A["main_logo.png"] --> B["generate_icons.py"]
  B --> C["tejocr_16.png"]
  B --> D["tejocr_26.png + 26_hc"]
  B --> E["tejocr_48.png + 48_hc"]
  B --> F["tejocr_64.png + 64_hc"]
```

## Runtime and installation troubleshooting

See:
- `docs/troubleshooting/installation.md`
- `docs/troubleshooting/dialog-fallbacks.md`

## Known release checks

Before releasing:
- version bump where appropriate (`description.xml`, changelog/release notes),
- ensure `LICENSE` exists and is listed in manifest,
- ensure `description.xml` remains valid XML UTF-8,
- ensure icon paths resolve (at least `icons/tejocr_16.png`, `icons/tejocr_48.png`, and matching high-contrast entries),
- smoke test install in fresh LibreOffice user profile.

## Commit policy

- Do not commit:
  - `.oxt` artifacts,
  - logs,
  - cache/temp folders,
  - Python bytecode folders.
- Keep doc and method-map updates aligned with behavior changes.

