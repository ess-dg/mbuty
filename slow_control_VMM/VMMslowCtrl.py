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
    
# if essrmmdirver is not installed with pip -e 
sys.path.insert(0, '/home/essdaq/detg_git/slow_control_driver')
    
from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule
from essrmmdriverlib.frontend.FrontEndGenericPortal import FrontEndGenericPortal

from libVMM.VMM_configurator import configDetector, acqOnOff, loadConfig, checkConfigNames, acqOnOff_global, resetFec_global, hardReset_global

import lib.parameters as para

###############################################################################

class VMMSlowCtrl():
    
    def __init__(self, parameters):
        
        self.parameters = parameters
        
        cfg_path  = self.parameters.slowCtrl.cfg_path
        addr_path = self.parameters.slowCtrl.addr_path
        rbu_path  = self.parameters.slowCtrl.rbu_path
        
        cfg_file  = self.parameters.slowCtrl.cfg_file
        addr_file = self.parameters.slowCtrl.addr_file
        rbu_file  = self.parameters.slowCtrl.rbu_file
        
        # Create RMM instance as normal, topology defined in cfg_ring
        rmm = ReadoutMasterModule(cfg_json=os.path.join(rbu_path, rbu_file))
        
        # Use this to create a generic interface to all FEN userspace
        self.fen_portal = FrontEndGenericPortal(RMMRegs=rmm.RMMRegs, regmap=os.path.join(addr_path, addr_file))
        
        # VMM config 
        self.cfg = loadConfig(os.path.join(cfg_path, cfg_file))
        
    def acq_on(self):  
        acqOnOff_global(self.fen_portal, self.cfg, on=False)
        configDetector(self.fen_portal, self.cfg)
        acqOnOff_global(self.fen_portal, self.cfg, on=True)
        
    def acq_off(self):  
        acqOnOff_global(self.fen_portal, self.cfg, on=False)

    def warm_init(self): 
        acqOnOff_global(self.fen_portal, self.cfg, on=False)
        resetFec_global(self.fen_portal, self.cfg)
        
    def hard_reset(self): 
        acqOnOff_global(self.fen_portal, self.cfg, on=False)
        hardReset_global(self.fen_portal,self.cfg)
        time.sleep(1)
        # hard reset includes warm init 
        resetFec_global(self.fen_portal, self.cfg)
        

###############################################################################
###############################################################################
###############################################################################

if __name__ == "__main__":
    
    # current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + os.sep
  
    # cfg_path     = os.path.join(current_dir, 'config_VMM' )
    
    # addr_path    = os.path.join(current_dir, 'sys_regs_map' )
    
    # sys_regs_map = 'vmm_sys_regs_map_A0v1.txt'

    # VMM_cfg      = 'MB.FREIA.diagonalNoSymm.json'
    
    # ring_cfg     = '/home/essdaq/detg_git/slow_control_driver/freia/cfg.json'
    
    
    current_dir = '/home/essdaq/mbuty/'
    parameters  = para.parameters(current_dir)
    
    
    sc = VMMSlowCtrl(parameters)
    
    sc.acq_on()

# 	# Create RMM instance as normal, topology defined in cfg_ring
#     rmm = ReadoutMasterModule(cfg_json=ring_cfg)
    

# 	# Use this to create a generic interface to all FEN userspace
#     fen_portal = FrontEndGenericPortal(RMMRegs=rmm.RMMRegs, regmap=os.path.join(addr_path, sys_regs_map ))

    
# 	
#     cfg = loadConfig(os.path.join(cfg_path, VMM_cfg))
    
# 	
#     # checkConfigNames(cfg)
# 	
# # 	for n in range(1, 6):
# # 		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=0, name="sdp10", value=n*200)
# # 		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=1, name="sdp10", value=n*200)

#     acqOnOff_global(fen_portal, cfg, on=False)
    
#     # acqOff_allRings(fen_portal)

#     configDetector(fen_portal,cfg)
    
#     acqOnOff_global(fen_portal, cfg, on=True)
    
    
    
#     time.sleep(5)
    
#     acqOnOff_global(fen_portal, cfg, on=False)
    
#     resetFec_global(fen_portal, cfg)
    
#     time.sleep(2)
    
#     configDetector(fen_portal,cfg)
    
#     acqOnOff_global(fen_portal, cfg, on=True)
    
#     print('\n now hard reset')
    
#     acqOnOff_global(fen_portal, cfg, on=False)
#     time.sleep(5)
#     hardReset_global(fen_portal,cfg)
    
#     time.sleep(2)
    
#     configDetector(fen_portal,cfg)
    
#     acqOnOff_global(fen_portal, cfg, on=True)
    
# # 		time.sleep(5)
# # 		acqOnOff(fen_portal, cfg, on=False)
