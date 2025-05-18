#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# © 2025 Devansh (Author of TejOCR)

import os
import sys
import shutil
import subprocess
import tempfile
import time
import platform
from pathlib import Path

try:
    from build import create_extension # Use your build script and function
except ImportError:
    print("❌ Error: Could not import 'create_extension' from build.py.")
    print("Ensure build.py is in the project root and defines create_extension.")
    sys.exit(1)

def find_libreoffice_executable():
    system = platform.system()
    dev_build_path_mac = "/Users/devanshvarshney/lode/dev/libreoffice/instdir/LibreOffice.app/Contents/MacOS/soffice"
    common_paths = []
    if system == "Darwin":
        common_paths = [dev_build_path_mac, "/Applications/LibreOffice.app/Contents/MacOS/soffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice"]
    # Add other OS paths if needed

    for path_candidate in common_paths:
        if path_candidate:
            path = Path(path_candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
    
    for exe_name in ["soffice", "libreoffice", "libreoffice-dev"]:
         found_path_str = shutil.which(exe_name)
         if found_path_str and Path(found_path_str).is_file():
             return found_path_str
    return None

def run_test_session(extension_oxt_path_obj: Path, lo_exe_path_str: str):
    extension_oxt_path_str = str(extension_oxt_path_obj)
    temp_profile_dir_obj = None
    temp_profile_path_for_cleanup = None # Define for finally block

    try:
        temp_profile_dir_obj = tempfile.TemporaryDirectory(prefix="tejocr_profile_")
        temp_profile_path = Path(temp_profile_dir_obj.name)
        temp_profile_path_for_cleanup = temp_profile_path # Assign for finally
        print(f"✅ Created temporary LibreOffice user profile directory at {temp_profile_path}")
        (temp_profile_path / "user").mkdir(parents=True, exist_ok=True)
        user_installation_url = temp_profile_path.as_uri()

        print(f"📦 Installing extension {Path(extension_oxt_path_str).name} into temporary profile...")
        install_cmd_soffice = [
            str(lo_exe_path_str),
            f"-env:UserInstallation={user_installation_url}",
            "--headless", "--nologo", "--nofirststartwizard", "--norestore",
            f"--install-extension={extension_oxt_path_str}",
            "--terminate_after_init"
        ]
        print(f"  Attempting install using soffice: {' '.join(map(str,install_cmd_soffice))}")
        try:
            process_install = subprocess.run(install_cmd_soffice, check=True, capture_output=True, text=True, timeout=90, env=os.environ.copy())
            print(f"  Soffice install stdout: {process_install.stdout.strip() if process_install.stdout else '(empty)'}")
            if process_install.stderr and process_install.stderr.strip():
                print(f"  Soffice install stderr: {process_install.stderr.strip()}")
            print(f"✅ Extension {Path(extension_oxt_path_str).name} installation command executed.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during soffice extension installation (Exit code: {e.returncode}):")
            print(f"  Command: {' '.join(map(str, e.cmd))}")
            if e.stdout: print(f"  Stdout: {e.stdout.strip()}")
            if e.stderr: print(f"  Stderr: {e.stderr.strip()}")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Timeout during soffice extension installation.")
            return False

        launch_cmd_list = [
            str(lo_exe_path_str),
            f"-env:UserInstallation={user_installation_url}",
            "--writer", "--norestore", "--nologo"
        ]
        print(f"🚀 Launching LibreOffice Writer ('{' '.join(map(str,launch_cmd_list))}')...")
        process = subprocess.Popen(launch_cmd_list)
        print("\n✅ LibreOffice Writer started.")
        print(f"   - Using temporary profile: {temp_profile_path}")
        print("\n⚙️  Testing tips: Verify TejOCR menu under Tools and test functionality.")
        print("\n🛑 Press Enter or Ctrl+C to end the test session.")
        try:
            input()
            print("Shutting down LibreOffice...")
        except KeyboardInterrupt:
            print("\n⚠️ Test session interrupted. Terminating LibreOffice...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        print("✅ LibreOffice process handled.")
        return True
    except Exception as e:
        print(f"❌ An unexpected error in run_test_session: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if temp_profile_dir_obj: # Check if TemporaryDirectory object was created
            # Cleanup is handled by the TemporaryDirectory context manager on exit
            # but if we assigned the name for manual cleanup:
            print(f"✅ Cleaned up temporary user profile (or will be by context manager): {temp_profile_path_for_cleanup}")
        elif temp_profile_path_for_cleanup and temp_profile_path_for_cleanup.exists(): # Manual cleanup if not using context manager fully
             try:
                 shutil.rmtree(temp_profile_path_for_cleanup)
                 print(f"✅ Manually Cleaned up temporary user profile: {temp_profile_path_for_cleanup}")
             except Exception as e_cleanup:
                 print(f"⚠️ Warning: Could not remove temp profile {temp_profile_path_for_cleanup}: {e_cleanup}")


if __name__ == "__main__":
    print("=" * 60)
    print("TejOCR Extension Tester")
    print("=" * 60)

    ext_oxt_path_arg = None
    if len(sys.argv) > 1 and sys.argv[1].endswith(".oxt"):
        ext_oxt_path_arg = Path(sys.argv[1])
        if not ext_oxt_path_arg.is_file():
            print(f"❌ Provided extension path does not exist: {ext_oxt_path_arg}")
            sys.exit(1)
        print(f"Using provided extension file: {ext_oxt_path_arg}")
    else:
        print("Building TejOCR extension using build.py...")
        oxt_file_path_obj_or_str = create_extension(output_name="TejOCR-test.oxt") # CALL YOUR FUNCTION
        # Ensure it's a Path object
        if isinstance(oxt_file_path_obj_or_str, str):
            ext_oxt_path_arg = Path(oxt_file_path_obj_or_str)
        else: # Assuming it's already a Path object if not str
            ext_oxt_path_arg = oxt_file_path_obj_or_str

        if not ext_oxt_path_arg or not ext_oxt_path_arg.is_file():
            print(f"❌ Extension build failed. Path: {ext_oxt_path_arg}")
            sys.exit(1)
        print(f"✅ Extension built: {ext_oxt_path_arg}")

    lo_exe_str = find_libreoffice_executable()
    if not lo_exe_str:
        lo_exe_manual_str = input("LO executable not found. Enter full path to soffice: ").strip()
        if Path(lo_exe_manual_str).is_file():
            lo_exe_str = lo_exe_manual_str
        else:
            print("❌ Invalid path. Exiting.")
            sys.exit(1)
    print(f"✅ Using LibreOffice at: {lo_exe_str}")

    if run_test_session(ext_oxt_path_arg, lo_exe_str):
        print("\n✅ Test session finished.")
    else:
        print("\n❌ Test session failed or had issues.")