#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import time

from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule
from essrmmdriverlib.frontend.FrontEndGenericPortal import FrontEndGenericPortal

from ConfigVmm import configDetector, acqOnOff, loadConfig, setAssisterConfig, setVmmConfig, setChannelConfig, checkConfigNames


if __name__ == "__main__":
	parser = argparse.ArgumentParser(prog="slow_control_driver mini_assister")
	parser.add_argument("-r", "--cfg_ring", required=True, type=str, help="JSON config file (rings and fens)")
	parser.add_argument("-m", "--map_assister", required=True, type=str, help="User Space Register Map (assister and vmms)")
	parser.add_argument("-a", "--cfg_assister", required=True, type=str, help="JSON config file (assister and vmms)")
	args = parser.parse_args()

	# Create RMM instance as normal, topology defined in cfg_ring
	rmm = ReadoutMasterModule(cfg_json=args.cfg_ring)

	# Use this to create a generic interface to all FEN userspace
	fen_portal = FrontEndGenericPortal(RMMRegs=rmm.RMMRegs, regmap=args.map_assister)

	cfg = loadConfig(args.cfg_assister)
	checkConfigNames(cfg)
	
	for n in range(1, 6):
		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=0, name="sdp10", value=n*200)
		setVmmConfig(cfg, fen=0, hybrid=0, vmm_index=1, name="sdp10", value=n*200)
		configDetector(fen_portal,cfg)
		acqOnOff(fen_portal, cfg, on=True)
		time.sleep(5)
		acqOnOff(fen_portal, cfg, on=False)
