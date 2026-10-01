#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 14:25:23 2026

@author: francescopiscitelli
"""


###############################################################################
###############################################################################
########    V1.0 2026/09/08      francescopiscitelli     ######################
###############################################################################
###############################################################################

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


# def manage_IOC_service(action: str, ioc_name: str) -> bool:
#     """Executes the systemctl command with sudo privileges. 
#     Returns True if successful, False otherwise without crashing.
#     """
#     # Ensure service name ends with .service if omitted
#     if not ioc_name.endswith(".service"):
#         ioc_name += ".service"

#     command = ["sudo", "systemctl", action, ioc_name]
#     print(f"Executing: {' '.join(command)}")

#     try:
#         subprocess.run(command, check=True)
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"Error executing command: {e}", file=sys.stderr)
#         # Removed sys.exit() to prevent crashing
#         return False
#     except FileNotFoundError:
#         print("Error: 'sudo' or 'systemctl' command not found.", file=sys.stderr)
#         # Removed sys.exit() to prevent crashing
#         return False

def manage_IOC_service(action: str, ioc_name: str) -> bool:
    """Executes the systemctl command with sudo privileges. 
    Returns True if successful, False otherwise without crashing.
    """
    if not ioc_name.endswith(".service"):
        ioc_name += ".service"

    command = ["sudo", "systemctl", action, ioc_name]
    print(f"Executing: {' '.join(command)}")

    try:
        # For 'status', non-zero exit codes are normal (e.g. service is stopped)
        # So we only enforce check=True for action commands like start/stop/restart
        use_check = action not in ["status", "is-active"]
        
        result = subprocess.run(command, check=use_check, capture_output=True, text=True)
        
        # If we didn't use check=True, we can manually check if it succeeded (exit code 0)
        if not use_check:
            print(result.stdout.strip())
            return result.returncode == 0
            
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: 'sudo' or 'systemctl' command not found.", file=sys.stderr)
        return False
    

# def manage_IOC_service(action: str, ioc_name: str) -> None:
    
#     print(f"I am doing this action {action} on this service {ioc_name}")
    
    
    
    