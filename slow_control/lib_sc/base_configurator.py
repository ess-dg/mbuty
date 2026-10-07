#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@authors: Dorothea Pfeiffer, Francesco Piscitelli
"""
###############################################################################

import json
import os
import time
import sys

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)


from lib.colors import WARN, RESET, ERR, INFO

###############################################################################

# if essrmmdriver is not installed with pip -e
sys.path.insert(0, "/home/essdaq/detg_git/slow_control_driver")
    
    
try:
        from essrmmdriverlib.frontend.FrontEndGenericPortal import (
            FrontEndGenericPortal,
        )
        from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule
except ImportError:
        pass



class BaseSlowCtrl():

    def __init__(self,rbu_path,rbu_file,addr_path,addr_file,cfg_path,cfg_file,debug=False):
        
        self.debug      = debug
        self.fen_portal = None

        if not self.debug:
            try:
                rmm = ReadoutMasterModule(cfg_json=os.path.join(rbu_path, rbu_file))
                self.fen_portal = FrontEndGenericPortal(
                    RMMRegs=rmm.RMMRegs,
                    regmap=os.path.join(addr_path, addr_file),
                )
            except Exception as err:
                print(f"[WARNING] Hardware connection to RMM failed. Switching to debug mode.")
                print(f"---------> Either RBU folder does not exist or give a valid RBU path! ")
                self.debug = True