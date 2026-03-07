# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pure OCR option planning and runtime metadata helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import platform
from typing import Any, Dict, List, Optional, Sequence

from tejocr import constants


DEFAULT_LOW_SIGNAL_CHAR_COUNT = 12
SCRIPT_LANGUAGE_PREFIX = "script/"


@dataclass
class LanguageValidationResult:
    requested: str
    normalized: str
    valid_codes: List[str]
    invalid_codes: List[str]
    validated: bool
    warning: str
    install_hint: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class OcrAttemptPlan:
    label: str
    lang: str
    psm: str
    oem: str
    scale: float
    improve_image: bool
    grayscale: bool
    binarize: bool
    invert: bool
    reason: str = ""
    enhanced: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class OcrExecutionPlan:
    preset: str
    requested_options: Dict[str, Any]
    effective_options: Dict[str, Any]
    requested_psm: str
    requested_oem: str
    effective_psm: str
    effective_oem: str
    pdf_dpi: int
    language: LanguageValidationResult
    attempts: List[OcrAttemptPlan] = field(default_factory=list)
    strict_user_config: bool = False
    low_signal_char_count: int = DEFAULT_LOW_SIGNAL_CHAR_COUNT

    def to_dict(self):
        data = asdict(self)
        data["language"] = self.language.to_dict()
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


@dataclass
class OcrAttemptStats:
    label: str
    lang: str
    psm: str
    oem: str
    scale: float
    improve_image: bool
    grayscale: bool
    binarize: bool
    invert: bool
    seconds: float
    output_length: int
    success: bool
    low_signal: bool
    reason: str = ""
    error: str = ""
    enhanced: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class OcrRunStats:
    source_type: str
    source_label: str
    requested_options: Dict[str, Any]
    effective_options: Dict[str, Any]
    pdf_dpi: int
    executor_mode: str = constants.DEFAULT_OCR_EXECUTOR
    attempt_count: int = 0
    renderer: str = ""
    total_seconds: float = 0.0
    dependency_probe_seconds: float = 0.0
    preprocessing_seconds: float = 0.0
    pdf_seconds: float = 0.0
    used_language: str = ""
    warning: str = ""
    install_hint: str = ""
    attempts: List[OcrAttemptStats] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


def dedupe_sequence(values: Sequence[Any]) -> List[str]:
    """Return a stable list of non-empty string values."""
    seen = set()
    output = []
    for value in values or ():
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        output.append(candidate)
    return output


def normalize_language_request(language_input, default_language=None):
    """Normalize comma or plus separated language codes."""
    default_code = default_language or constants.DEFAULT_OCR_LANGUAGE
    if not language_input:
        return default_code
    normalized = str(language_input).replace(",", "+").strip().lower()
    normalized = "+".join([token.strip() for token in normalized.split("+") if token.strip()])
    return normalized or default_code


def split_language_codes(language_input, default_language=None):
    """Split normalized language text into ordered codes."""
    normalized = normalize_language_request(language_input, default_language=default_language)
    return [token for token in normalized.split("+") if token]


def format_language_codes_for_display(language_input, default_language=None, separator="  +  "):
    """Return a UI-friendly language string with chip-like code markers."""
    codes = split_language_codes(language_input, default_language=default_language)
    if not codes:
        codes = [default_language or constants.DEFAULT_OCR_LANGUAGE]
    return separator.join("[{code}]".format(code=code) for code in codes)


def coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on", "enabled", "enable")
    return default


def coerce_float(value, default=1.0):
    try:
        parsed = float(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def coerce_scale(value, default=1.0):
    try:
        parsed = float(value if value is not None else default)
        return max(1.0, round(parsed, 2))
    except Exception:
        return max(1.0, round(float(default), 2))


def coerce_preset_request(preset_name, fallback=None):
    fallback_value = fallback or constants.DEFAULT_OCR_PRESET
    if not preset_name:
        return fallback_value
    normalized = str(preset_name).strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0].strip()
    return normalized if normalized in constants.OCR_PRESET_CHOICES else fallback_value


def coerce_executor_mode(executor_name, fallback=None):
    fallback_value = fallback or constants.DEFAULT_OCR_EXECUTOR
    if not executor_name:
        return fallback_value
    normalized = str(executor_name).strip().lower()
    return normalized if normalized in constants.OCR_EXECUTOR_CHOICES else fallback_value


def preferred_supported_oem(support_map, preferred=None, fallback=None):
    """Return the best supported OEM for the current runtime."""
    fallback_value = str(fallback or constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
    preferred_value = str(preferred or fallback_value).strip() or fallback_value
    normalized_support = {
        str(mode).strip(): bool(is_supported)
        for mode, is_supported in dict(support_map or {}).items()
        if str(mode).strip()
    }
    if not normalized_support:
        return preferred_value
    if normalized_support.get(preferred_value, True):
        return preferred_value
    for candidate in (constants.DEFAULT_OEM_MODE, "1", "3", "2", "0", fallback_value):
        candidate_value = str(candidate or "").strip()
        if candidate_value and normalized_support.get(candidate_value, False):
            return candidate_value
    for candidate_value, is_supported in normalized_support.items():
        if is_supported:
            return candidate_value
    return preferred_value


def coerce_supported_oem(requested_oem, support_map, fallback=None):
    """Coerce an OEM selection to a supported mode and return a warning when changed."""
    fallback_value = str(fallback or constants.DEFAULT_OEM_MODE).strip() or constants.DEFAULT_OEM_MODE
    requested_value = str(requested_oem or fallback_value).strip() or fallback_value
    normalized_support = {
        str(mode).strip(): bool(is_supported)
        for mode, is_supported in dict(support_map or {}).items()
        if str(mode).strip()
    }
    if not normalized_support or normalized_support.get(requested_value, True):
        return requested_value, ""

    replacement = preferred_supported_oem(
        normalized_support,
        preferred=fallback_value,
        fallback=fallback_value,
    )
    if replacement == requested_value:
        return requested_value, ""
    return (
        replacement,
        "Selected OEM {requested} is unsupported by the current traineddata/runtime. "
        "Using OEM {replacement} instead.".format(
            requested=requested_value,
            replacement=replacement,
        ),
    )


def is_script_language_code(language_code):
    candidate = str(language_code or "").strip().lower()
    return candidate.startswith(SCRIPT_LANGUAGE_PREFIX)


def build_language_install_hint(invalid_codes, platform_name=None):
    codes = [code for code in dedupe_sequence(invalid_codes) if not is_script_language_code(code)]
    if not codes:
        return ""

    system = (platform_name or platform.system() or "").lower()
    if system == "darwin":
        return "Install extra Tesseract languages with: brew install tesseract-lang"
    if system == "windows":
        return (
            "Install the missing Tesseract languages in the Windows installer or copy the"
            " traineddata files into your tessdata directory."
        )
    install_packages = " ".join("tesseract-ocr-{code}".format(code=code) for code in codes)
    return "Install missing Tesseract languages with: sudo apt install {packages}".format(
        packages=install_packages
    )


def build_language_validation_message(normalized_language, invalid_codes, validated, platform_name=None):
    if validated and invalid_codes:
        invalid_text = ", ".join(invalid_codes)
        install_hint = build_language_install_hint(invalid_codes, platform_name=platform_name)
        message = (
            "Some language codes are not installed and were skipped: {invalid_codes}. Using: {used_codes}."
        ).format(
            invalid_codes=invalid_text,
            used_codes=normalize_language_request(normalized_language),
        )
        if install_hint:
            message = "{message} {hint}".format(message=message, hint=install_hint)
        return message
    if not validated and normalized_language:
        return "Language availability could not be verified. Using: {used_codes}.".format(
            used_codes=normalize_language_request(normalized_language)
        )
    return ""


def validate_language_codes(language_input, available_languages, default_language=None, platform_name=None):
    """Validate requested language codes against installed language packs."""
    default_code = default_language or constants.DEFAULT_OCR_LANGUAGE
    normalized_codes = split_language_codes(language_input, default_language=default_code)
    normalized_value = "+".join(normalized_codes) if normalized_codes else default_code

    if not available_languages:
        warning = build_language_validation_message(
            normalized_value,
            [],
            False,
            platform_name=platform_name,
        )
        return LanguageValidationResult(
            requested=normalize_language_request(language_input, default_code),
            normalized=normalized_value,
            valid_codes=list(normalized_codes),
            invalid_codes=[],
            validated=False,
            warning=warning,
            install_hint="",
        )

    available_order = [
        str(language).strip().lower() for language in available_languages if str(language).strip()
    ]
    available_set = set(available_order)
    if not available_set:
        warning = build_language_validation_message(
            normalized_value,
            [],
            False,
            platform_name=platform_name,
        )
        return LanguageValidationResult(
            requested=normalize_language_request(language_input, default_code),
            normalized=normalized_value,
            valid_codes=list(normalized_codes),
            invalid_codes=[],
            validated=False,
            warning=warning,
            install_hint="",
        )

    valid_codes = [code for code in normalized_codes if code in available_set]
    invalid_codes = [code for code in normalized_codes if code not in available_set]

    if not valid_codes:
        if default_code in available_set:
            valid_codes = [default_code]
        elif available_order:
            valid_codes = [available_order[0]]
        else:
            valid_codes = [default_code]

    normalized_valid = "+".join(valid_codes)
    install_hint = build_language_install_hint(invalid_codes, platform_name=platform_name)
    warning = build_language_validation_message(
        normalized_valid,
        invalid_codes,
        True,
        platform_name=platform_name,
    )
    return LanguageValidationResult(
        requested=normalize_language_request(language_input, default_code),
        normalized=normalized_valid,
        valid_codes=valid_codes,
        invalid_codes=invalid_codes,
        validated=True,
        warning=warning,
        install_hint=install_hint,
    )


def build_language_preview(available_languages, limit=10):
    """Return a compact preview string with script packs separated."""
    cleaned = [str(language).strip() for language in (available_languages or []) if str(language).strip()]
    if not cleaned:
        return "Installed languages: not detected"

    script_codes = [code for code in cleaned if is_script_language_code(code)]
    normal_codes = [code for code in cleaned if not is_script_language_code(code)]

    preview_parts = []
    if normal_codes:
        preview = ", ".join(normal_codes[:limit])
        if len(normal_codes) > limit:
            preview += ", ..."
        preview_parts.append("Installed languages: {languages}".format(languages=preview))
    else:
        preview_parts.append("Installed languages: none")

    if script_codes:
        preview = ", ".join(script_codes[:limit])
        if len(script_codes) > limit:
            preview += ", ..."
        preview_parts.append("Script packs: {languages}".format(languages=preview))

    return "\n".join(preview_parts)


def alternate_recovery_psm(primary_psm):
    """Choose a single alternate PSM for balanced recovery."""
    candidate = str(primary_psm or constants.DEFAULT_PSM_MODE).strip() or constants.DEFAULT_PSM_MODE
    if candidate != "11":
        return "11"
    if candidate != "6":
        return "6"
    return candidate


def select_pdf_dpi(preset_name):
    preset = coerce_preset_request(preset_name, constants.DEFAULT_OCR_PRESET)
    return 300 if preset == constants.OCR_PRESET_ACCURATE else 200


def is_low_signal_text(text, min_chars=DEFAULT_LOW_SIGNAL_CHAR_COUNT):
    normalized = " ".join(str(text or "").split())
    if len(normalized) < int(min_chars):
        return True
    alnum_count = sum(1 for ch in normalized if ch.isalnum())
    return alnum_count < int(min_chars)


def _effective_options_from_preset(requested_options, preset_name):
    preset = coerce_preset_request(preset_name, constants.DEFAULT_OCR_PRESET)
    options = dict(requested_options or {})
    if preset == constants.OCR_PRESET_CUSTOM:
        return options
    profile = constants.OCR_QUALITY_PRESETS.get(preset, {})
    for key in ("psm", "oem", "scale", "grayscale", "binarize", "invert", "improve_image"):
        if key in profile:
            options[key] = profile[key]
    return options


def resolve_execution_plan(raw_options, available_languages=None, default_options=None, platform_name=None):
    """Resolve user OCR options into a bounded execution plan."""
    defaults = dict(default_options or {})
    options = dict(defaults)
    options.update(dict(raw_options or {}))

    requested_lang = normalize_language_request(
        options.get("lang", defaults.get("lang", constants.DEFAULT_OCR_LANGUAGE))
    )
    requested_psm = str(options.get("psm", defaults.get("psm", constants.DEFAULT_PSM_MODE))).strip() or constants.DEFAULT_PSM_MODE
    requested_oem = str(options.get("oem", defaults.get("oem", constants.DEFAULT_OEM_MODE))).strip() or constants.DEFAULT_OEM_MODE
    requested_scale = coerce_scale(options.get("scale", defaults.get("scale", constants.DEFAULT_SCALE_FACTOR)), defaults.get("scale", 1.0))
    requested_grayscale = coerce_bool(options.get("grayscale", defaults.get("grayscale", False)), defaults.get("grayscale", False))
    requested_binarize = coerce_bool(options.get("binarize", defaults.get("binarize", False)), defaults.get("binarize", False))
    requested_invert = coerce_bool(options.get("invert", defaults.get("invert", False)), defaults.get("invert", False))
    requested_improve = coerce_bool(options.get("improve_image", defaults.get("improve_image", False)), defaults.get("improve_image", False))
    selected_preset = coerce_preset_request(options.get("preset", defaults.get("preset", constants.DEFAULT_OCR_PRESET)))
    show_preview = coerce_bool(options.get("show_preview", defaults.get("show_preview", False)), defaults.get("show_preview", False))
    merge_batch_results = coerce_bool(
        options.get("merge_batch_results", defaults.get("merge_batch_results", False)),
        defaults.get("merge_batch_results", False),
    )

    requested_options = {
        "lang": requested_lang,
        "psm": requested_psm,
        "oem": requested_oem,
        "scale": requested_scale,
        "grayscale": requested_grayscale,
        "binarize": requested_binarize,
        "invert": requested_invert,
        "improve_image": requested_improve,
        "preset": selected_preset,
        "show_preview": show_preview,
        "merge_batch_results": merge_batch_results,
    }

    language_result = validate_language_codes(
        requested_lang,
        available_languages,
        default_language=defaults.get("lang", constants.DEFAULT_OCR_LANGUAGE),
        platform_name=platform_name,
    )

    effective_options = _effective_options_from_preset(requested_options, selected_preset)
    effective_options["lang"] = language_result.normalized or requested_lang
    effective_options["preset"] = selected_preset
    effective_options["show_preview"] = show_preview
    effective_options["merge_batch_results"] = merge_batch_results
    effective_options["psm"] = str(effective_options.get("psm", requested_psm)).strip() or requested_psm
    effective_options["oem"] = str(effective_options.get("oem", requested_oem)).strip() or requested_oem
    effective_options["scale"] = coerce_scale(effective_options.get("scale", requested_scale), requested_scale)
    effective_options["grayscale"] = coerce_bool(effective_options.get("grayscale", requested_grayscale), requested_grayscale)
    effective_options["binarize"] = coerce_bool(effective_options.get("binarize", requested_binarize), requested_binarize)
    effective_options["invert"] = coerce_bool(effective_options.get("invert", requested_invert), requested_invert)
    effective_options["improve_image"] = coerce_bool(effective_options.get("improve_image", requested_improve), requested_improve)
    effective_options["language_warning"] = language_result.warning
    effective_options["language_install_hint"] = language_result.install_hint

    attempts = [
        OcrAttemptPlan(
            label="exact",
            lang=effective_options["lang"],
            psm=effective_options["psm"],
            oem=effective_options["oem"],
            scale=float(effective_options["scale"]),
            improve_image=bool(effective_options["improve_image"]),
            grayscale=bool(effective_options["grayscale"]),
            binarize=bool(effective_options["binarize"]),
            invert=bool(effective_options["invert"]),
            reason="requested configuration",
        )
    ]

    if selected_preset == constants.OCR_PRESET_BALANCED:
        recovery_psm = alternate_recovery_psm(effective_options["psm"])
        if recovery_psm != effective_options["psm"]:
            attempts.append(
                OcrAttemptPlan(
                    label="recovery",
                    lang=effective_options["lang"],
                    psm=recovery_psm,
                    oem=effective_options["oem"],
                    scale=float(effective_options["scale"]),
                    improve_image=bool(effective_options["improve_image"]),
                    grayscale=bool(effective_options["grayscale"]),
                    binarize=bool(effective_options["binarize"]),
                    invert=bool(effective_options["invert"]),
                    reason="balanced recovery with alternate page segmentation",
                )
            )
    elif selected_preset == constants.OCR_PRESET_ACCURATE:
        attempts.append(
            OcrAttemptPlan(
                label="enhanced",
                lang=effective_options["lang"],
                psm=effective_options["psm"],
                oem=effective_options["oem"],
                scale=max(float(effective_options["scale"]), 1.5),
                improve_image=True,
                grayscale=True,
                binarize=True,
                invert=bool(effective_options["invert"]),
                reason="accuracy recovery with stronger preprocessing",
                enhanced=True,
            )
        )

    return OcrExecutionPlan(
        preset=selected_preset,
        requested_options=requested_options,
        effective_options=effective_options,
        requested_psm=requested_psm,
        requested_oem=requested_oem,
        effective_psm=effective_options["psm"],
        effective_oem=effective_options["oem"],
        pdf_dpi=select_pdf_dpi(selected_preset),
        language=language_result,
        attempts=attempts,
        strict_user_config=selected_preset in (constants.OCR_PRESET_FAST, constants.OCR_PRESET_CUSTOM),
    )


def build_run_diagnostics_text(stats):
    """Return a short user-facing summary for logs and preview messages."""
    if stats is None:
        return ""
    attempts = stats.attempts or []
    attempt_count = len(attempts) or int(getattr(stats, "attempt_count", 0) or 0)
    used_language = stats.used_language or stats.effective_options.get("lang", "")
    parts = [
        "Executor: {executor}".format(
            executor=coerce_executor_mode(stats.executor_mode, constants.DEFAULT_OCR_EXECUTOR)
        ),
        "Requested: PSM {psm}, OEM {oem}, preset {preset}".format(
            psm=stats.requested_options.get("psm", constants.DEFAULT_PSM_MODE),
            oem=stats.requested_options.get("oem", constants.DEFAULT_OEM_MODE),
            preset=stats.requested_options.get("preset", constants.DEFAULT_OCR_PRESET),
        ),
        "Effective: PSM {psm}, OEM {oem}, preset {preset}, lang {lang}".format(
            psm=stats.effective_options.get("psm", constants.DEFAULT_PSM_MODE),
            oem=stats.effective_options.get("oem", constants.DEFAULT_OEM_MODE),
            preset=stats.effective_options.get("preset", constants.DEFAULT_OCR_PRESET),
            lang=used_language or stats.effective_options.get("lang", constants.DEFAULT_OCR_LANGUAGE),
        ),
        "Attempts: {count}".format(count=attempt_count),
    ]
    if stats.pdf_dpi:
        parts.append("PDF DPI: {dpi}".format(dpi=stats.pdf_dpi))
    if stats.renderer:
        parts.append("Renderer: {renderer}".format(renderer=stats.renderer))
    return " | ".join(parts)
