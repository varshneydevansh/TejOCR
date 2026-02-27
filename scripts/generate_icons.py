#!/usr/bin/env python3
"""
Generate TejOCR extension icons from the single source image: icons/main_logo.png.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image
import argparse


DEFAULT_SOURCE = Path("icons/main_logo.png")
DEFAULT_OUTPUTS = {
    "tejocr_16.png": (16, False),
    "tejocr_26.png": (26, False),
    "tejocr_26_hc.png": (26, True),
    "tejocr_48.png": (48, False),
    "tejocr_48_hc.png": (48, True),
    "tejocr_64.png": (64, False),
    "tejocr_64_hc.png": (64, True),
}


def crop_alpha_bounds(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def fit_to_square(source: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Keep a tiny margin so logos do not touch the edge in tiny icon sizes.
    inset = max(1, int(size * 0.12))
    available = size - (2 * inset)
    scale = min(available / source.width, available / source.height)
    target_w = max(1, int(source.width * scale))
    target_h = max(1, int(source.height * scale))

    resized = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = (size - target_w) // 2
    y = (size - target_h) // 2

    canvas.paste(resized, (x, y), resized)
    return canvas


def make_high_contrast(img: Image.Image) -> Image.Image:
    # Preserve transparency but force a uniform foreground so the icon has maximum contrast
    # in environments that request a high-contrast asset.
    alpha = img.getchannel("A")
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(alpha)
    return black


def generate_icons(source_path: Path, outputs: dict[str, tuple[int, bool]]) -> None:
    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    source = Image.open(source_path).convert("RGBA")
    source = crop_alpha_bounds(source)

    for filename, (size, is_hc) in outputs.items():
        icon = fit_to_square(source, size)
        if is_hc:
            icon = make_high_contrast(icon)

        output_path = source_path.parent / filename
        icon.save(output_path, "PNG")
        print(f"[OK] {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate TejOCR extension icon files from icons/main_logo.png."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Path to source logo image. Default: icons/main_logo.png",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        help=(
            "Optional subset of output icon filenames to generate "
            "(eg: tejocr_16.png tejocr_64.png)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = DEFAULT_OUTPUTS

    if args.only:
        outputs = {k: v for k, v in outputs.items() if k in args.only}

    if not outputs:
        raise SystemExit("No output icons selected.")

    generate_icons(Path(args.source), outputs)


if __name__ == "__main__":
    main()
