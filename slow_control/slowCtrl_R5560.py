#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@authors: Dorothea Pfeiffer, Francesco Piscitelli
"""
###############################################################################
###############################################################################

# import argparse
import time
import os 
import sys 


# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from lib_sc.R5560_configurator import R5560SlowCtrl
# import lib.parameters as para

###############################################################################



###############################################################################
###############################################################################
###############################################################################

if __name__ == "__main__":
    
    current_dir = os.path.abspath(os.path.dirname(__file__)) 

    mbuty_dir = os.path.dirname(current_dir)

 
    reg_cfg_path  =  os.path.join(mbuty_dir,'slow_control','config_R5560')
    reg_cfg_file  = 'example5560cfg.json'
    
    addr_path = os.path.join(mbuty_dir,'slow_control','sys_regs_map')
    addr_file = 'r5560_001_regs_addrmap.txt'
    
    rbu_path  = '/home/essdaq/detg_git/slow_control_driver/miracles/'
    rbu_file  = 'cfg.json'
    
    sc = R5560SlowCtrl(rbu_path, rbu_file, addr_path, addr_file, reg_cfg_path, reg_cfg_file)
    sc.configureR5560()