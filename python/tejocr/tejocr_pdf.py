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


def _python_package_command(package_name):
    """Return a pip install command using a known-good Python interpreter."""
    return "{python} -m pip install {package}".format(
        python=shlex.quote(_resolve_python_executable()), package=package_name
    )


def get_pdf2image_install_command():
    """Return the currently detected pip install command for pdf2image."""
    return _python_package_command("pdf2image")


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

    has_pdftoppm = _command_works("pdftoppm")
    if not has_pdftoppm:
        # Loosened probe: if command exists but does not answer with classic probes,
        # still accept executable presence to avoid false negatives on unusual builds.
        has_pdftoppm = os.access(pdftoppm_path, os.X_OK)
    if not has_pdftoppm:
        return False

    # Prefer strict helper checks when available, but don't block OCR on non-critical helper
    # probe noise (some poppler builds return atypical return codes under certain locales/flags).
    has_auxiliary = False
    for aux in ("pdfinfo", "pdftocairo"):
        aux_path = _resolve_command(aux)
        if not aux_path:
            continue
        aux_ok = _command_works(aux)
        if not aux_ok:
            aux_ok = os.access(aux_path, os.X_OK)
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

    base = os.path.basename(path).lower()
    if base in {"soffice", "soffice.bin", "soffice.exe", "soffice.bin"}:
        return False
    return (base == "python" or base.startswith("python") or "python" in base)


def _is_python_with_pip(path):
    """Return True only for interpreters that can execute pip."""
    try:
        proc = subprocess.run(
            [path, "-m", "pip", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
    """Return the best candidate python command for installing PDF helper packages."""
    for candidate in _collect_python_candidates():
        if _is_python_with_pip(candidate):
            return candidate
    return "python3"


def _run_command(command, timeout=5):
    """Run a subprocess command and return (ok, combined_output)."""
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
    if os.name == "nt":
        return [
            "choco install poppler",
            "scoop install poppler",
            "Install MuPDF tools via official package distribution.",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    if platform.system() == "Darwin":  # pragma: no cover - platform dependent
        return [
            "brew install poppler",
            "brew install mupdf",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    if platform.system() == "Linux":
        return [
            "apt-get install poppler-utils",
            "apt-get install mupdf-tools",
            "Install PDF conversion runtime in this Python: {cmd}".format(
                cmd=_python_package_command("pdf2image")
            ),
        ]
    return [
        "Please install a PDF renderer such as:",
        "1) poppler-utils",
        "2) MuPDF",
        "3) {cmd}".format(cmd=_python_package_command("pdf2image")),
    ]


def get_pdf_renderer_status():
    """Return whether a PDF renderer is available in the current runtime."""
    hints = _os_hint()

    pdftoppm_path = _resolve_command("pdftoppm")
    if pdftoppm_path and (_command_works("pdftoppm") or os.access(pdftoppm_path, os.X_OK)):
        return {
            "available": True,
            "engine": "pdftoppm",
            "hints": hints,
        }

    mutool_path = _resolve_command("mutool")
    if mutool_path and _command_works("mutool"):
        return {
            "available": True,
            "engine": "mutool",
            "hints": hints,
        }

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


def rasterize_pdf_pages(pdf_path, dpi=300):
    """Convert PDF pages into temporary PNG files and return their paths."""
    if not pdf_path:
        return []

    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"PDF path does not exist: {pdf_path}")

    if not str(pdf_path).lower().endswith(".pdf"):
        raise RuntimeError(f"Input is not a PDF file: {pdf_path}")

    work_dir = tempfile.mkdtemp(prefix="tejocr_pdf_")
    output_prefix = os.path.join(work_dir, "page")

    # Try pdftoppm first
    images = _render_with_pdftoppm(pdf_path, output_prefix, dpi)
    if images:
        return images

    # Fallback to mutool
    images = _render_with_mutool(pdf_path, output_prefix, dpi)
    if images:
        return images

    # Final fallback: pdf2image
    try:
        return _render_with_pdf2image(pdf_path, dpi, output_prefix)
    except Exception as pdf_error:
        return _raise_or_rethrow(pdf_error)


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
                if parent_dir.startswith(tempfile.gettempdir() + os.sep + "tejocr_pdf_"):
                    shutil.rmtree(parent_dir, ignore_errors=True)
        except Exception:
            continue
