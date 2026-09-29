#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import time
import os 
import sys 
from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule
from essrmmdriverlib.frontend.FrontEndGenericPortal import FrontEndGenericPortal

from ConfigVmm import configDetector, acqOnOff, loadConfig, setAssisterConfig, setVmmConfig, setChannelConfig, checkConfigNames


# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)




if __name__ == "__main__":
# 	parser = argparse.ArgumentParser(prog="slow_control_driver mini_assister")
# 	parser.add_argument("-r", "--cfg_ring", required=True, type=str, help="JSON config file (rings and fens)")
# 	parser.add_argument("-m", "--map_assister", required=True, type=str, help="User Space Register Map (assister and vmms)")
# 	parser.add_argument("-a", "--cfg_assister", required=True, type=str, help="JSON config file (assister and vmms)")
# 	args = parser.parse_args()

    VMMcfgFile  = 'MB.FREIA.diagonalNoSymm.json'
    
    # VMMcfgPath  = '/Users/francescopiscitelli/gitlab_repos/mb_configs/VMM slow ctrl/' 
    
    current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + os.sep
    
    VMMcfgPath  = current_dir + 'config_slowCtrlVMM'
    
    VMMcfg         = os.path.join(VMMcfgPath, VMMcfgFile)
    
    ringcfg = '/home/essdaq/detg_git/slow_control_driver/freia/cfg.json'
    
    map_assister = os.path.join(VMMcfgPath, 'vmm_sys_regs_map_A0v1.txt') 


	# Create RMM instance as normal, topology defined in cfg_ring
    rmm = ReadoutMasterModule(cfg_json=ringcfg)
    

	# Use this to create a generic interface to all FEN userspace
    fen_portal = FrontEndGenericPortal(RMMRegs=rmm.RMMRegs, regmap=map_assister)

	
    cfg = loadConfig(VMMcfg)
	
    checkConfigNames(cfg)
	
# 	for n in range(1, 6):
# 		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=0, name="sdp10", value=n*200)
# 		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=1, name="sdp10", value=n*200)


    configDetector(fen_portal,cfg)
    acqOnOff(fen_portal, cfg, on=True)
# 		time.sleep(5)
# 		acqOnOff(fen_portal, cfg, on=False)
