#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 13 09:48:10 2026

@author: francescopiscitelli
"""

import argparse
import os
import stat
from pathlib import Path

# Default values if no arguments are passed
DEFAULT_EXEC_PATH = "/home/essdaq/mg_tools/slow_control_vmm3a/build/vmmdcs"
DEFAULT_APP_NAME = "VMMDCS"
COMMENT = "Launch VMM3a Slow Control tool"
ICON = "utilities-terminal"  # Standard system terminal icon
RUN_IN_TERMINAL = True       # Set to False if vmmdcs opens its own GUI window


def create_desktop_shortcut(exec_path: str, app_name: str) -> None:
    exec_file = Path(exec_path).expanduser().resolve()

    if not exec_file.is_file():
        print(f"Warning: Executable path '{exec_file}' does not exist.")

    desktop_dir = Path.home() / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    shortcut_path = desktop_dir / f"{app_name.lower()}.desktop"
    working_dir = exec_file.parent

    desktop_entry_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment={COMMENT}
Exec={exec_file}
Path={working_dir}
Terminal={'true' if RUN_IN_TERMINAL else 'false'}
Icon={ICON}
Categories=Development;
"""

    # Write the .desktop file
    shortcut_path.write_text(desktop_entry_content)

    # Grant executable permissions (chmod +x)
    current_permissions = shortcut_path.stat().st_mode
    shortcut_path.chmod(current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Shortcut created successfully at: {shortcut_path}")
    print("\nNext step (GNOME/Ubuntu):")
    print("Go to your Desktop, right-click the shortcut, and select 'Allow Launching'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create an Ubuntu desktop shortcut icon for a given binary."
    )
    parser.add_argument(
        "exec_path",
        nargs="?",
        default=DEFAULT_EXEC_PATH,
        help="Path to the executable file (default: %(default)s)",
    )
    parser.add_argument(
        "--name",
        "-n",
        default=DEFAULT_APP_NAME,
        help="Name for the desktop icon (default: %(default)s)",
    )

    args = parser.parse_args()
    create_desktop_shortcut(args.exec_path, args.name)