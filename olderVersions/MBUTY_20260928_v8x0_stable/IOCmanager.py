#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep  8 14:14:34 2026

@author: francescopiscitelli
"""

###############################################################################
###############################################################################
########    V1.0 2026/09/08      francescopiscitelli     ######################
###############################################################################
###############################################################################

import argparse
import os
import subprocess
import sys

_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

############################################################################### 
###############################################################################

# DEFAULT_IOC = "ioc-TBL-DtCmn_SC-IOC-002.service"

DEFAULT_IOC = "ioc-ESTIA-DtCmn_SC-IOC-002.service"


def manage_service(action: str, ioc_name: str) -> None:
    """Executes the systemctl command with sudo privileges."""
    # Ensure service name ends with .service if omitted
    if not ioc_name.endswith(".service"):
        ioc_name += ".service"

    command = ["sudo", "systemctl", action, ioc_name]
    print(f"Executing: {' '.join(command)}")

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: 'sudo' or 'systemctl' command not found.", file=sys.stderr)
        sys.exit(1)


###############################################################################
###############################################################################

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="tool to start, stop, or check status of system IOC services."
    )

    parser.add_argument(
        "-a",
        "--action",
        choices=["start", "stop", "status", "restart"],
        help="Systemctl action to perform on the service.",
    )

    parser.add_argument(
        "-i",
        "--ioc",
        type=str,
        default=DEFAULT_IOC,
        help=f"Name of the IOC service (default: {DEFAULT_IOC})",
    )

    args = parser.parse_args()

    manage_service(action=args.action, ioc_name=args.ioc)
    
    # command = ["sudo", "systemctl", action, ioc_name]