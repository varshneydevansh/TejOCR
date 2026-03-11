# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""PDF to image conversion helpers used by batch OCR."""

from __future__ import annotations

import glob
import os
import platform
import sys
import shutil
import subprocess
import shlex
import tempfile

_OS_HINT_CACHE = None


def _is_rejected_python_launcher(path):
    """Reject known LibreOffice launcher scripts that exec the app wrapper binary."""
    if not path:
        return False

    normalized = os.path.abspath(os.path.expanduser(path))
    lowered = normalized.lower()
    resolved = os.path.realpath(normalized).lower()
    basename = os.path.basename(normalized).lower()

    if lowered.endswith("/contents/resources/python") or lowered.endswith("/contents/resources/python3"):
        return True
    if resolved.endswith("/python.app/contents/macos/libreofficepython"):
        return True
    if os.path.basename(resolved) == "libreofficepython":
        return True
    if basename.endswith("-config"):
        return True

    try:
        if (
            os.path.isfile(normalized)
            and os.path.getsize(normalized) <= 32768
            and basename.startswith("python")
        ):
            with open(normalized, "r", encoding="utf-8", errors="ignore") as handle:
                header = handle.read(2048).lower()
            if "libreofficepython" in header and "python.app/contents/macos" in header:
                return True
        return False
    except Exception:
        return False


def _python_package_command(package_name):
    """Return a pip install command using a known-good Python interpreter."""
    return get_runtime_pip_install_command([package_name])


def get_runtime_pip_install_command(packages=None, upgrade=False):
    """Return a pip install command using a known-good Python interpreter."""
    package_list = [str(package).strip() for package in (packages or []) if str(package).strip()]
    command = "{python} -m pip install".format(
        python=shlex.quote(_resolve_python_executable())
    )
    if upgrade:
        command += " -U"
    if package_list:
        command += " " + " ".join(package_list)
    return command


def get_pdf2image_install_command():
    """Return the currently detected pip install command for pdf2image."""
    return get_runtime_pip_install_command(["pdf2image"])


def _command_is_available(command_name):
    """Return whether a command resolves to an executable file."""
    return _resolve_command(command_name) is not None


def _command_works(command_name):
    """Return whether a command can execute successfully for a lightweight probe.

    Some binaries (especially from poppler) return non-zero for `--version` on certain
    builds even though they are available. This helper treats a command as working
    if it prints help/version-like output for common probe flags.
    """
    command_path = _resolve_command(command_name)
    if not command_path:
        return False

    probe_flags = (
        ("--version",),
        ("-v",),
        ("-h",),
        ("--help",),
    )

    for flags in probe_flags:
        ok, output = _run_command([command_path, *flags], timeout=3)
        if ok:
            return True
        if output:
            lowered = output.lower()
            if any(token in lowered for token in ("usage", "options", "help", "version")):
                return True

    # Final fallback for shells/binaries that require arguments.
    # If the command can be executed but exits with a usage-style message, treat as available.
    ok, output = _run_command([command_path], timeout=3)
    if ok:
        return True
    if output:
        lowered = output.lower()
        if any(token in lowered for token in ("usage", "options", "help", "version")):
            return True
    return False


def _resolve_common_command_dirs():
    """Return fallback directories where common CLI tools are typically installed."""
    return (
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/opt",
        "/opt/homebrew/opt/poppler/bin",
        "/usr/local/opt/poppler/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    )


def _is_poppler_available():
    """Return True only when required poppler binaries are available for pdf2image."""
    pdftoppm_path = _resolve_command("pdftoppm")
    if not pdftoppm_path:
        return False

    has_pdftoppm = os.access(pdftoppm_path, os.X_OK) or _command_works("pdftoppm")
    if not has_pdftoppm:
        return False

    # Prefer strict helper checks when available, but don't block OCR on non-critical helper
    # probe noise (some poppler builds return atypical return codes under certain locales/flags).
    has_auxiliary = False
    for aux in ("pdfinfo", "pdftocairo"):
        aux_path = _resolve_command(aux)
        if not aux_path:
            continue
        aux_ok = os.access(aux_path, os.X_OK) or _command_works(aux)
        if aux_ok:
            has_auxiliary = True
            break

    return has_pdftoppm or has_auxiliary


def _is_python_executable(path):
    """Return True if path points to an executable Python interpreter."""
    if not path:
        return False
    if not os.path.isfile(path) or not os.access(path, os.X_OK):
        return False
    if _is_rejected_python_launcher(path):
        return False

    base = os.path.basename(path).lower()
    if base in {"soffice", "soffice.bin", "soffice.exe", "libreofficepython"}:
        return False
    if base.endswith("-config"):
        return False
    stem = base[:-4] if base.endswith(".exe") else base
    if stem == "python":
        return True
    if stem.startswith("python"):
        suffix = stem[len("python") :]
        if not suffix:
            return True
        suffix = suffix.lstrip(".")
        if not suffix:
            return True
        return all(part.isdigit() for part in suffix.split(".") if part)
    return False


def _is_python_with_pip(path):
    """Return True only for interpreters that can execute pip."""
    try:
        proc = subprocess.run(
            [path, "-m", "pip", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=5,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0 and "python" in output.lower() and "pip" in output.lower()
    except Exception:
        return False


def _collect_python_candidates():
    """Build candidate interpreter paths from LibreOffice and common installs."""
    exe = os.path.expanduser(os.path.abspath(sys.executable or ""))
    candidates = []

    def add(path):
        if not path:
            return
        path = os.path.abspath(os.path.expanduser(path))
        if _is_python_executable(path) and path not in candidates:
            candidates.append(path)

    def add_from_contents(base_contents):
        if not base_contents or not os.path.isdir(base_contents):
            return
        add(os.path.join(base_contents, "Frameworks", "LibreOfficePython.framework", "Versions", "Current", "bin", "python3"))
        add(os.path.join(base_contents, "Resources", "python3"))
        add(os.path.join(base_contents, "Resources", "python"))
        add(os.path.join(base_contents, "Programs", "python3"))
        add(os.path.join(base_contents, "Programs", "python"))
        add(os.path.join(base_contents, "program", "python3"))
        add(os.path.join(base_contents, "program", "python"))
        for match in glob.glob(
            os.path.join(base_contents, "Frameworks", "LibreOfficePython.framework", "Versions", "*", "bin", "python*")
        ):
            add(match)

    exe_dir = os.path.dirname(exe)

    # Known roots
    for base in [
        "/Applications/LibreOffice.app/Contents",
        "/Applications/LibreOfficeDev.app/Contents",
        exe_dir,
        os.path.dirname(exe_dir),
        os.path.dirname(os.path.dirname(exe)),
    ]:
        add_from_contents(base)

    if _is_python_executable(exe):
        add(exe)

    # Search parent chain for bundle paths (covers nested dev layouts).
    walk = exe_dir
    for _ in range(12):
        parent = os.path.dirname(walk)
        if parent == walk:
            break
        if "Contents" in parent.split(os.sep):
            parent_parts = parent.split(os.sep)
            if "Contents" in parent_parts:
                idx = parent_parts.index("Contents")
                add_from_contents(os.sep.join(parent_parts[:idx + 1]))
        walk = parent

    # PATH fallback.
    for candidate in ("python3", "python"):
        add(shutil.which(candidate))

    return candidates


def _resolve_python_executable():
    """Return the best candidate python command for install guidance.

    This is used to build user-facing pip commands. Do not execute candidate
    interpreters here; probing LibreOffice-bundled helper scripts on macOS can
    trigger codesigning crashes even when we only need a printable command.
    """
    candidates = _collect_python_candidates()
    if candidates:
        return candidates[0]
    return "python3"


def _run_command(command, timeout=5):
    """Run a subprocess command and return (ok, combined_output)."""
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as exc:
        return False, str(exc)


def _resolve_command(command_name):
    """Find a usable command path for the current runtime."""
    found = shutil.which(command_name)
    if found:
        return found

    for root in _resolve_common_command_dirs():
        candidate = os.path.join(root, command_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # Resolve under package manager-specific opt/Cellar layout if direct paths are missing.
    package_root_patterns = (
        "/opt/homebrew/opt/*/bin",
        "/usr/local/opt/*/bin",
        "/usr/local/Cellar/*/bin",
        "/opt/homebrew/Cellar/*/bin",
    )
    for pattern in package_root_patterns:
        for candidate in glob.glob(pattern):
            direct = os.path.join(candidate, command_name)
            if os.path.isfile(direct) and os.access(direct, os.X_OK):
                return direct

    return None


def _os_hint():
    """Return OS-specific renderer install hints."""
    global _OS_HINT_CACHE
    if _OS_HINT_CACHE is not None:
        return list(_OS_HINT_CACHE)

    if os.name == "nt":
        hints = [
            "choco install poppler",
            "scoop install poppler",
            "Install MuPDF tools via official package distribution.",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    elif platform.system() == "Darwin":  # pragma: no cover - platform dependent
        hints = [
            "brew install poppler",
            "brew install mupdf",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    elif platform.system() == "Linux":
        hints = [
            "apt-get install poppler-utils",
            "apt-get install mupdf-tools",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    else:
        hints = [
            "Please install a PDF renderer such as:",
            "1) poppler-utils",
            "2) MuPDF",
            "3) {cmd}".format(cmd=_python_package_command("pdf2image")),
        ]

    _OS_HINT_CACHE = list(hints)
    return list(_OS_HINT_CACHE)


def get_pdf_renderer_status():
    """Return whether a PDF renderer is available in the current runtime."""
    pdftoppm_path = _resolve_command("pdftoppm")
    if pdftoppm_path and os.access(pdftoppm_path, os.X_OK):
        return {
            "available": True,
            "engine": "pdftoppm",
            "hints": [],
        }

    mutool_path = _resolve_command("mutool")
    if mutool_path and os.access(mutool_path, os.X_OK):
        return {
            "available": True,
            "engine": "mutool",
            "hints": [],
        }

    hints = _os_hint()
    poppler_available = _is_poppler_available()
    try:
        from pdf2image import convert_from_path  # noqa: F401
    except Exception:
        return {
            "available": False,
            "engine": None,
            "error": "pdf2image is not installed for this Python runtime.",
            "hints": hints,
        }

    if not poppler_available:
        return {
            "available": False,
            "engine": None,
            "error": (
                "pdf2image is installed, but poppler utilities are not available. "
                "Install poppler-utils so pdf2image can rasterize PDFs."
            ),
            "hints": [hint for hint in hints if isinstance(hint, str) and hint.strip()],
        }

    return {
        "available": True,
        "engine": "pdf2image",
        "error": None,
        "hints": hints,
    }


def _raster_error_message(base_error):
    """Build a compact renderer failure message with install hints."""
    hints = "\n".join(_os_hint())
    clean_error = (base_error or "").strip()

    if not clean_error:
        return "No PDF renderer found. Install one of:\n{hints}".format(hints=hints)

    if "No PDF renderer found" in clean_error:
        return clean_error

    if "Install one of:" in clean_error:
        return clean_error

    return "{error}\n\nInstall one of:\n{hints}".format(error=clean_error, hints=hints)


def _render_with_pdftoppm(pdf_path, output_prefix, dpi):
    """Render PDF pages using pdftoppm if available."""
    command = _resolve_command("pdftoppm")
    cmd = [
        command,
        "-png",
        "-r",
        str(dpi),
        pdf_path,
        output_prefix,
    ]
    ok, output = _run_command(cmd)
    if not ok:
        return []

    candidates = sorted(glob.glob(output_prefix + "-*.png"))
    return candidates


def _render_page_with_pdftoppm(pdf_path, output_prefix, dpi, page_number):
    """Render a single PDF page using pdftoppm."""
    command = _resolve_command("pdftoppm")
    cmd = [
        command,
        "-png",
        "-f",
        str(page_number),
        "-l",
        str(page_number),
        "-r",
        str(dpi),
        pdf_path,
        output_prefix,
    ]
    ok, output = _run_command(cmd, timeout=20)
    if not ok:
        return []
    return sorted(glob.glob(output_prefix + "-*.png"))


def _render_with_mutool(pdf_path, output_prefix, dpi):
    """Render PDF pages using mutool draw if available."""
    command = _resolve_command("mutool")
    output_pattern = output_prefix + "_%d.png"
    cmd = [
        command,
        "draw",
        "-r",
        str(dpi),
        "-F",
        "png",
        "-o",
        output_pattern,
        pdf_path,
    ]
    ok, output = _run_command(cmd)
    if not ok:
        return []

    candidates = sorted(glob.glob(output_prefix + "_*.png"))
    return candidates


def _render_page_with_mutool(pdf_path, output_prefix, dpi, page_number):
    """Render a single PDF page using mutool draw."""
    command = _resolve_command("mutool")
    output_path = output_prefix + ".png"
    cmd = [
        command,
        "draw",
        "-r",
        str(dpi),
        "-F",
        "png",
        "-o",
        output_path,
        pdf_path,
        str(page_number),
    ]
    ok, output = _run_command(cmd, timeout=20)
    if not ok:
        return []
    return [output_path] if os.path.isfile(output_path) else []


def _render_with_pdf2image(pdf_path, dpi, output_prefix):
    """Render PDF pages using pdf2image if available."""
    try:
        from pdf2image import convert_from_path
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "pdf2image is not installed. Install it in this Python environment: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            )
        ) from exc

    try:
        pages = convert_from_path(pdf_path, dpi=dpi)
    except Exception as exc:
        msg = str(exc)
        if ("pdftoppm" in msg.lower()) or ("pdfinfo" in msg.lower()) or ("poppler" in msg.lower()):
            raise RuntimeError(
                "pdf2image conversion failed because poppler tools are unavailable. "
                "Install poppler-utils and ensure its binaries are on PATH."
            ) from exc
        raise RuntimeError(f"pdf2image failed: {msg}") from exc

    output_paths = []
    for index, page in enumerate(pages, start=1):
        out_path = f"{output_prefix}_{index}.png"
        page.save(out_path, format="PNG")
        output_paths.append(out_path)

    return output_paths


def _render_page_with_pdf2image(pdf_path, dpi, output_prefix, page_number):
    """Render a single page through pdf2image when CLI renderers are unavailable."""
    try:
        from pdf2image import convert_from_path
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "pdf2image is not installed. Install it in this Python environment: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            )
        ) from exc

    try:
        pages = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
        )
    except Exception as exc:
        msg = str(exc)
        if ("pdftoppm" in msg.lower()) or ("pdfinfo" in msg.lower()) or ("poppler" in msg.lower()):
            raise RuntimeError(
                "pdf2image conversion failed because poppler tools are unavailable. "
                "Install poppler-utils and ensure its binaries are on PATH."
            ) from exc
        raise RuntimeError(f"pdf2image failed: {msg}") from exc

    output_paths = []
    for index, page in enumerate(pages, start=1):
        out_path = "{prefix}_{index}.png".format(prefix=output_prefix, index=index)
        page.save(out_path, format="PNG")
        output_paths.append(out_path)
    return output_paths


def get_pdf_page_count(pdf_path):
    """Return the page count for a PDF when a lightweight probe is available."""
    if not pdf_path or not os.path.isfile(pdf_path):
        return None

    command = _resolve_command("pdfinfo")
    if command:
        ok, output = _run_command([command, pdf_path], timeout=10)
        lines = (output or "").splitlines()
        for line in lines:
            if line.lower().startswith("pages:"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except Exception:
                    return None
        if ok:
            return None

    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path)
        pages = info.get("Pages")
        return int(pages) if pages else None
    except Exception:
        return None


def _count_true_runs(values, min_run_length=1):
    """Count sequences of truthy values, optionally filtering out tiny runs."""
    run_count = 0
    current_run = 0
    for value in values:
        if value:
            current_run += 1
            continue
        if current_run >= int(min_run_length):
            run_count += 1
        current_run = 0
    if current_run >= int(min_run_length):
        run_count += 1
    return run_count


def is_probably_small_text_page(image_path):
    """Return True when a rendered PDF page looks text-dense enough to justify 300 DPI."""
    if not image_path or not os.path.isfile(image_path):
        return False

    try:
        from PIL import Image
    except Exception:
        return False

    try:
        with Image.open(image_path) as image:
            grayscale = image.convert("L")
            if grayscale.width < 900 or grayscale.height < 1200:
                return False
            sample = grayscale.copy()
            sample.thumbnail((900, 1400))
            width, height = sample.size
            pixels = sample.tobytes()
    except Exception:
        return False

    if width <= 0 or height <= 0:
        return False

    threshold = 195
    dark_pixels = 0
    active_rows = 0
    row_densities = []
    row_flags = []
    for row_index in range(height):
        start = row_index * width
        row = pixels[start:start + width]
        dark_count = sum(1 for pixel in row if pixel < threshold)
        dark_fraction = float(dark_count) / float(width)
        row_densities.append(dark_fraction)
        dark_pixels += dark_count
        is_active = 0.012 <= dark_fraction <= 0.35
        row_flags.append(is_active)
        if is_active:
            active_rows += 1

    dark_ratio = float(dark_pixels) / float(width * height)
    active_ratio = float(active_rows) / float(height)
    line_runs = _count_true_runs(row_flags, min_run_length=2)
    active_densities = [density for density, is_active in zip(row_densities, row_flags) if is_active]
    average_active_density = (
        sum(active_densities) / float(len(active_densities))
        if active_densities
        else 0.0
    )

    if dark_ratio < 0.006 or dark_ratio > 0.28:
        return False
    if active_ratio < 0.14:
        return (
            line_runs >= 6
            and active_ratio >= 0.08
            and dark_ratio <= 0.018
            and average_active_density <= 0.14
        )
    if line_runs >= 18 and average_active_density <= 0.12:
        return True
    if line_runs >= 28 and dark_ratio >= 0.012:
        return True
    return False


def rasterize_pdf_page(pdf_path, page_number, dpi=300):
    """Render a single PDF page into a temporary PNG and return its path."""
    if not pdf_path:
        return []

    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"PDF path does not exist: {pdf_path}")

    if not str(pdf_path).lower().endswith(".pdf"):
        raise RuntimeError(f"Input is not a PDF file: {pdf_path}")

    work_dir = tempfile.mkdtemp(prefix="tejocr_pdf_page_")
    output_prefix = os.path.join(work_dir, "page_{page}".format(page=page_number))

    images = _render_page_with_pdftoppm(pdf_path, output_prefix, dpi, page_number)
    if images:
        return images[0]

    images = _render_page_with_mutool(pdf_path, output_prefix, dpi, page_number)
    if images:
        return images[0]

    try:
        images = _render_page_with_pdf2image(pdf_path, dpi, output_prefix, page_number)
        return images[0] if images else None
    except Exception as pdf_error:
        return _raise_or_rethrow(pdf_error)


def iter_rasterized_pdf_pages(pdf_path, dpi=300):
    """Yield ``(page_number, image_path)`` for a PDF one page at a time."""
    page_count = get_pdf_page_count(pdf_path)
    if not page_count:
        for index, path in enumerate(_rasterize_pdf_pages_all(pdf_path, dpi=dpi), start=1):
            yield index, path
        return

    for page_number in range(1, int(page_count) + 1):
        image_path = rasterize_pdf_page(pdf_path, page_number, dpi=dpi)
        if image_path:
            yield page_number, image_path


def _rasterize_pdf_pages_all(pdf_path, dpi=300):
    """Render all pages using the fastest available renderer."""
    if not pdf_path:
        return []

    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"PDF path does not exist: {pdf_path}")

    if not str(pdf_path).lower().endswith(".pdf"):
        raise RuntimeError(f"Input is not a PDF file: {pdf_path}")

    work_dir = tempfile.mkdtemp(prefix="tejocr_pdf_")
    output_prefix = os.path.join(work_dir, "page")

    images = _render_with_pdftoppm(pdf_path, output_prefix, dpi)
    if images:
        return images

    images = _render_with_mutool(pdf_path, output_prefix, dpi)
    if images:
        return images

    try:
        return _render_with_pdf2image(pdf_path, dpi, output_prefix)
    except Exception as pdf_error:
        return _raise_or_rethrow(pdf_error)


def rasterize_pdf_pages(pdf_path, dpi=300):
    """Convert PDF pages into temporary PNG files and return their paths."""
    page_paths = []
    for _, image_path in iter_rasterized_pdf_pages(pdf_path, dpi=dpi):
        page_paths.append(image_path)
    return page_paths


def _raise_or_rethrow(error):
    """Normalize PDF renderer errors into a stable user-facing message."""
    message = str(error or "")
    if not message:
        message = "No PDF renderer found."
    raise RuntimeError(_raster_error_message(message))


def cleanup_temp_images(image_paths):
    """Best-effort cleanup for temporary page images used for OCR."""
    for image_path in image_paths or []:
        try:
            os.remove(image_path)
        except FileNotFoundError:
            pass
        except Exception:
            continue

    # Also remove parent temp dirs created by the PDF renderer (safe best-effort).
    for image_path in image_paths or []:
        try:
            parent_dir = os.path.dirname(os.path.abspath(image_path))
            if os.path.isdir(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
                if (
                    parent_dir.startswith(tempfile.gettempdir() + os.sep + "tejocr_pdf_")
                    or parent_dir.startswith(tempfile.gettempdir() + os.sep + "tejocr_pdf_page_")
                ):
                    shutil.rmtree(parent_dir, ignore_errors=True)
        except Exception:
            continue
