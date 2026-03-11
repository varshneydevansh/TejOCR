# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from tejocr import tejocr_pdf


class TestTejocrPdf(unittest.TestCase):
    def test_run_command_forces_utf8_decoding(self):
        with patch.object(tejocr_pdf.subprocess, "run", return_value=type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()) as run_mock:
            ok, output = tejocr_pdf._run_command(["pdftoppm", "-h"])

        self.assertTrue(ok)
        self.assertEqual(output, "")
        kwargs = run_mock.call_args.kwargs
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_renderer_status_uses_fast_path_when_pdftoppm_exists(self):
        with patch.object(tejocr_pdf, "_resolve_command", side_effect=lambda name: "/usr/bin/pdftoppm" if name == "pdftoppm" else None), \
             patch("os.access", return_value=True), \
             patch.object(tejocr_pdf, "_os_hint", side_effect=AssertionError("hints should not be needed")):
            status = tejocr_pdf.get_pdf_renderer_status()

        self.assertTrue(status["available"])
        self.assertEqual(status["engine"], "pdftoppm")
        self.assertEqual(status["hints"], [])

    def test_small_text_fixture_triggers_high_dpi_heuristic(self):
        image_path = os.path.join(PROJECT_ROOT, "tests", "fixtures", "small_text_block.png")
        self.assertTrue(tejocr_pdf.is_probably_small_text_page(image_path))

    def test_single_line_fixture_does_not_trigger_high_dpi_heuristic(self):
        image_path = os.path.join(PROJECT_ROOT, "tests", "fixtures", "single_line.png")
        self.assertFalse(tejocr_pdf.is_probably_small_text_page(image_path))

    def test_rejects_libreofficepython_wrapper_as_install_python(self):
        temp_dir = tempfile.mkdtemp(prefix="tejocr_lo_py_")
        self.addCleanup(lambda: os.path.isdir(temp_dir) and os.rmdir(temp_dir))
        wrapper_path = os.path.join(temp_dir, "LibreOfficePython")
        with open(wrapper_path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nexit 0\n")
        os.chmod(wrapper_path, 0o755)
        self.addCleanup(lambda: os.path.exists(wrapper_path) and os.remove(wrapper_path))

        self.assertFalse(tejocr_pdf._is_python_executable(wrapper_path))

    def test_rejects_libreoffice_resources_python_launcher_script(self):
        temp_dir = tempfile.mkdtemp(prefix="tejocr_lo_bundle_")
        contents_dir = os.path.join(temp_dir, "LibreOffice.app", "Contents", "Resources")
        os.makedirs(contents_dir)
        self.addCleanup(lambda: os.path.isdir(temp_dir) and shutil.rmtree(temp_dir))

        wrapper_path = os.path.join(contents_dir, "python")
        with open(wrapper_path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                'exec "${0%/Resources/python}/Frameworks/LibreOfficePython.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/LibreOfficePython" "$@"\n'
            )
        os.chmod(wrapper_path, 0o755)

        self.assertFalse(tejocr_pdf._is_python_executable(wrapper_path))

    def test_rejects_python_config_helper_scripts(self):
        temp_dir = tempfile.mkdtemp(prefix="tejocr_lo_pyconfig_")
        self.addCleanup(lambda: os.path.isdir(temp_dir) and shutil.rmtree(temp_dir))

        wrapper_path = os.path.join(temp_dir, "python3-config")
        with open(wrapper_path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/usr/bin/env bash\n"
                'exec "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/LibreOfficePython" "$@"\n'
            )
        os.chmod(wrapper_path, 0o755)

        self.assertTrue(tejocr_pdf._is_rejected_python_launcher(wrapper_path))
        self.assertFalse(tejocr_pdf._is_python_executable(wrapper_path))

    def test_runtime_pip_install_command_uses_resolved_python(self):
        with patch.object(tejocr_pdf, "_resolve_python_executable", return_value="/opt/libreoffice/python3"):
            command = tejocr_pdf.get_runtime_pip_install_command(["numpy", "pillow"], upgrade=True)

        self.assertEqual(command, "/opt/libreoffice/python3 -m pip install -U numpy pillow")

    def test_resolve_python_executable_does_not_probe_candidates(self):
        with patch.object(tejocr_pdf, "_collect_python_candidates", return_value=["/safe/libreoffice/python3"]), \
             patch.object(tejocr_pdf, "_is_python_with_pip", side_effect=AssertionError("should not probe")):
            resolved = tejocr_pdf._resolve_python_executable()

        self.assertEqual(resolved, "/safe/libreoffice/python3")
