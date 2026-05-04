# TejOCR UI Localization

TejOCR has two separate language concepts:

- **Extension UI language**: the language used by TejOCR dialogs, warnings, and status text.
- **OCR recognition language**: the Tesseract language data used to recognize document text, for example `eng`, `spa`, or `eng+hin`.

They are intentionally separate. Changing the extension UI language does not change OCR recognition language.

## Runtime Behavior

The Settings dialog exposes **Extension UI** with these modes:

- **Auto**: detect the LibreOffice UI locale first, then the system locale.
- **Manual language selection**: force any bundled UI catalog.

If Auto detects a language with no ready TejOCR catalog, the extension falls back to English.

```text
Saved setting: UiLanguage
  -> auto?
     -> LibreOffice UI locale
     -> system locale
     -> English fallback
  -> manual language?
     -> load exact catalog if ready
     -> load parent catalog if ready
     -> English fallback
```

## Catalog Readiness Rule

TejOCR only shows catalogs that are safe to load:

- `.mo` file exists,
- `.po` file is translated,
- plural-form header is valid,
- `X-TejOCR-Status: reviewed` is present in the `.po` header,
- gettext can load the catalog.

At the moment, the user-visible UI catalogs are:

- `ar` Arabic
- `bn` Bengali
- `de` German
- `fa` Persian
- `fr` French
- `hi` Hindi
- `id` Indonesian
- `it` Italian
- `ja` Japanese
- `ko` Korean
- `mr` Marathi
- `nl` Dutch
- `pa` Punjabi
- `pl` Polish
- `pt_BR` Portuguese (Brazil)
- `ru` Russian
- `sw` Swahili
- `ta` Tamil
- `te` Telugu
- `tr` Turkish
- `uk` Ukrainian
- `ur` Urdu
- `vi` Vietnamese
- `zh_CN` Simplified Chinese

The Spanish catalog came from the merged community contribution. The other newly added catalogs are initial generated translations with placeholder and gettext validation. Community/native-speaker review is still welcome, but they are intentionally selectable now.

## Adding Another UI Language

1. Create or update `l10n/<locale>/LC_MESSAGES/tejocr.po`.
2. Ensure the header has a valid `Language` and `Plural-Forms`.
3. Translate the messages.
4. Mark the reviewed catalog header:

```text
X-TejOCR-Status: reviewed
```

5. Compile:

```bash
msgfmt --check --check-format -o l10n/<locale>/LC_MESSAGES/tejocr.mo l10n/<locale>/LC_MESSAGES/tejocr.po
```

6. Run:

```bash
python3 -m unittest -q tests/test_locale_setup.py tests/test_tejocr_dialogs.py
```

If the catalog is valid and translated, it appears automatically in Settings.

To merge future POT updates into an existing locale:

```bash
msgmerge --update l10n/<locale>/LC_MESSAGES/tejocr.po l10n/tejocr.pot
```

After merging, recompile the `.mo` file and run tests.
