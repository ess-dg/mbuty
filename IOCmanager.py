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
    
from lib.IOC_manager_lib import manage_IOC_service

############################################################################### 
###############################################################################

# DEFAULT_IOC = "ioc-TBL-DtCmn_SC-IOC-002.service"

DEFAULT_IOC    = "ioc-ESTIA-DtCmn_SC-IOC-002.service"


###############################################################################
###############################################################################

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Tool to start, stop, restart, or check status of system IOC services."
    )

    parser.add_argument(
        "-a",
        "--action",
        choices=["start", "stop", "status", "restart"],
        default="status",
        help=f"Systemctl action to perform on the service (default: status).",
    )

    parser.add_argument(
        "-i",
        "--ioc",
        type=str,
        default=DEFAULT_IOC,
        help=f"Name of the IOC service (default: {DEFAULT_IOC})",
    )

    args = parser.parse_args()

    manage_IOC_service(action=args.action, ioc_name=args.ioc)