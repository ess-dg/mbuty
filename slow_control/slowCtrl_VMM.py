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
    
from lib_sc.VMM_configurator import VMMSlowCtrl
# import lib.parameters as para

###############################################################################



###############################################################################
###############################################################################
###############################################################################

if __name__ == "__main__":
    
    current_dir = os.path.abspath(os.path.dirname(__file__)) 

    mbuty_dir = os.path.dirname(current_dir)
    

    # parameters  = para.parameters(mbuty_dir)
    
    # parameters.slowCtrl.doSlowCtrl = False
    
    # parameters.slowCtrl.hardReset = False 
    
    # parameters.slowCtrl.warmInit  = False 
    
    # parameters.slowCtrl.acqOnOff  = False
    
    # parameters.slowCtrl.cfg_path  =  os.path.join(mbuty_dir,'slow_control_VMM','config_VMM')
    # parameters.slowCtrl.cfg_file  = 'MB.FREIA.diagonalNoSymm.json'
    
    # parameters.slowCtrl.addr_path = os.path.join(mbuty_dir,'slow_control_VMM','sys_regs_map')
    # parameters.slowCtrl.addr_file = 'vmm_sys_regs_map_A0v1.txt'
    
    # parameters.slowCtrl.rbu_path  = '/home/essdaq/detg_git/slow_control_driver/freia/'
    # parameters.slowCtrl.rbu_file  = 'cfg.json'
   
    # sc = VMMSlowCtrl(parameters)
    
    # sc.acq_on()
    
    # sc.hard_reset( 0, 0, 2)
    
    
    cfg_path  =  os.path.join(mbuty_dir,'slow_control','config_VMM')
    cfg_file  = 'MB.FREIA.diagonalNoSymm.json'
    
    addr_path = os.path.join(mbuty_dir,'slow_control','sys_regs_map')
    addr_file = 'vmm_sys_regs_map_A0v1.txt'
    
    rbu_path  = '/home/essdaq/detg_git/slow_control_driver/freia/'
    rbu_file  = 'cfg.json'
    
    sc = VMMSlowCtrl(rbu_path, rbu_file, addr_path, addr_file, cfg_path, cfg_file)
    sc.acq_on()
