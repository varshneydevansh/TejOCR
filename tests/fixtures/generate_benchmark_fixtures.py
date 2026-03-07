# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Generate reproducible OCR benchmark fixtures for local development."""

from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw, ImageFont


FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))
CANVAS = (1800, 1200)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _font_candidates():
    return {
        "base": [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ],
        "devanagari": [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
            "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
            "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
        ],
    }


def _load_font(role, size):
    for path in _font_candidates().get(role, []) + _font_candidates()["base"]:
        if not os.path.isfile(path):
            continue
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _save_image(image, filename):
    path = os.path.join(FIXTURE_DIR, filename)
    image.save(path, format="PNG")
    return path


def _save_pdf(images, filename):
    path = os.path.join(FIXTURE_DIR, filename)
    first = images[0].convert("RGB")
    rest = [image.convert("RGB") for image in images[1:]]
    first.save(path, format="PDF", save_all=True, append_images=rest, resolution=200.0)
    return path


def _draw_multiline_block(lines, fonts, starts, spacing=18, size=CANVAS):
    image = Image.new("RGB", size, WHITE)
    draw = ImageDraw.Draw(image)
    y = starts[1]
    for line, font in zip(lines, fonts):
        draw.text((starts[0], y), line, fill=BLACK, font=font)
        bbox = draw.textbbox((starts[0], y), line, font=font)
        line_height = (bbox[3] - bbox[1]) if bbox else int(getattr(font, "size", 24) * 1.2)
        y += line_height + spacing
    return image


def _english_paragraph_image():
    title_font = _load_font("base", 72)
    body_font = _load_font("base", 48)
    lines = [
        "TejOCR benchmark fixture",
        "Fast text extraction should stay readable.",
        "PDF latency matters for single and multi page documents.",
        "Requested and effective settings must be visible.",
    ]
    return _draw_multiline_block(
        lines,
        [title_font, body_font, body_font, body_font],
        (120, 140),
        spacing=26,
    ), "\n".join(lines)


def _mixed_language_image():
    title_font = _load_font("base", 64)
    body_font = _load_font("devanagari", 50)
    lines = [
        "Invoice total 2500 rupees.",
        "हिंदी पंक्ति परीक्षण के लिए है।",
        "English and Hindi mixed together.",
        "कृपया गति और सटीकता दोनों जांचें।",
    ]
    return _draw_multiline_block(
        lines,
        [title_font, body_font, title_font, body_font],
        (120, 160),
        spacing=28,
    ), "\n".join(lines)


def _sparse_layout_image():
    image = Image.new("RGB", CANVAS, WHITE)
    draw = ImageDraw.Draw(image)
    font = _load_font("base", 54)
    draw.text((90, 90), "TOP LEFT 101", fill=BLACK, font=font)
    draw.text((640, 420), "MIDDLE NOTE 202", fill=BLACK, font=font)
    draw.text((90, 980), "LOWER LEFT 404", fill=BLACK, font=font)
    draw.text((1160, 980), "BOTTOM RIGHT 303", fill=BLACK, font=font)
    return image, "TOP LEFT 101\nMIDDLE NOTE 202\nLOWER LEFT 404\nBOTTOM RIGHT 303"


def _single_line_image():
    image = Image.new("RGB", (1800, 260), WHITE)
    draw = ImageDraw.Draw(image)
    font = _load_font("base", 76)
    text = "SINGLE LINE OCR TEST 12345"
    draw.text((90, 85), text, fill=BLACK, font=font)
    return image, text


def _small_text_image():
    title_font = _load_font("base", 48)
    body_font = _load_font("base", 30)
    lines = [
        "Small text PDF fixture",
        "This page is intentionally denser and smaller.",
        "Adaptive DPI should help when text comes back weak.",
        "Measure both speed and accuracy on this page.",
        "The quick brown fox jumps over the lazy dog 1234567890.",
    ]
    return _draw_multiline_block(
        lines,
        [title_font, body_font, body_font, body_font, body_font],
        (120, 120),
        spacing=16,
        size=(1800, 1400),
    ), "\n".join(lines)


def generate():
    english_image, english_text = _english_paragraph_image()
    mixed_image, mixed_text = _mixed_language_image()
    sparse_image, sparse_text = _sparse_layout_image()
    single_line_image, single_line_text = _single_line_image()
    small_text_image, small_text_text = _small_text_image()

    _save_image(english_image, "english_paragraph.png")
    _save_image(mixed_image, "mixed_english_hindi.png")
    _save_image(sparse_image, "sparse_layout.png")
    _save_image(single_line_image, "single_line.png")
    _save_image(small_text_image, "small_text_block.png")

    _save_pdf([english_image], "single_page_document.pdf")
    _save_pdf([english_image, small_text_image, mixed_image], "multi_page_document.pdf")

    manifest = {
        "cases": [
            {
                "label": "english-image-fast",
                "path": "english_paragraph.png",
                "type": "image",
                "preset": "fast",
                "lang": "eng",
                "expected_text": english_text,
            },
            {
                "label": "english-image",
                "path": "english_paragraph.png",
                "type": "image",
                "preset": "balanced",
                "lang": "eng",
                "expected_text": english_text,
            },
            {
                "label": "mixed-language-image",
                "path": "mixed_english_hindi.png",
                "type": "image",
                "preset": "balanced",
                "lang": "eng+hin",
                "expected_text": mixed_text,
            },
            {
                "label": "sparse-layout-image",
                "path": "sparse_layout.png",
                "type": "image",
                "preset": "balanced",
                "lang": "eng",
            },
            {
                "label": "single-line-image",
                "path": "single_line.png",
                "type": "image",
                "preset": "custom",
                "lang": "eng",
                "psm": "7",
                "oem": "3",
                "scale": 1.2,
                "expected_text": single_line_text,
            },
            {
                "label": "small-text-image",
                "path": "small_text_block.png",
                "type": "image",
                "preset": "accurate",
                "lang": "eng",
                "expected_text": small_text_text,
            },
            {
                "label": "single-page-pdf",
                "path": "single_page_document.pdf",
                "type": "pdf",
                "preset": "balanced",
                "lang": "eng",
                "expected_text": english_text,
            },
            {
                "label": "multi-page-pdf",
                "path": "multi_page_document.pdf",
                "type": "pdf",
                "preset": "accurate",
                "lang": "eng+hin",
                "expected_text": "\n\n".join([english_text, small_text_text, mixed_text]),
            },
        ]
    }

    manifest_path = os.path.join(FIXTURE_DIR, "benchmark_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    return manifest_path


if __name__ == "__main__":
    output = generate()
    print(output)
