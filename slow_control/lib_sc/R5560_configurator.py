#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  6 09:10:54 2026

@author: francescopiscitelli
"""

###############################################################################

import json
import os
import time
import sys
import re

from lib.colors import WARN, RESET, ERR, INFO

###############################################################################



def sanitize_jsonc(json_str: str) -> str:
    """Preprocesses JSON with comments (JSONC), hex values, and trailing commas into standard JSON."""
    # 1. Strip single-line comments (// ...)
    cleaned = re.sub(r"//.*", "", json_str)
    # 2. Convert hexadecimal values (e.g., 0x38, 0x0) to decimal strings
    cleaned = re.sub(
        r"0x[0-9a-fA-F]+", lambda match: str(int(match.group(0), 16)), cleaned
    )
    # 3. Strip trailing commas before closing braces/brackets
    cleaned = re.sub(r",(\s*[\}\]])", r"\1", cleaned)
    return cleaned


def loadConfig(cfg):
    """Loads JSON/JSONC configuration from file path or returns dictionary directly."""
    if isinstance(cfg, dict):
        return cfg

    with open(cfg, "r") as f:
        content = f.read()
    clean_content = sanitize_jsonc(content)
    return json.loads(clean_content)


def parse_topology(cfg):
    data = loadConfig(cfg)
    topology = data.get("topology", {})

    # Build a list of dicts for each ring and its nodes
    rings = []
    total_nodes = 0

    for ring_id, ring_config in topology.items():
        # Handles string key converted to int or kept as str, matching key type
        ring_number = int(ring_id) if ring_id.isdigit() else ring_id
        node_count = ring_config.get("nodes", 0)

        rings.append({"ring": ring_number, "nodes": node_count})
        total_nodes += node_count

    return {
        "rings": rings,
        "total_rings": len(rings),
        "total_nodes": total_nodes,
    }


###############################################################################

# def configFEN(fen_portal, ring=0, fen=0): OLD FROM DORO
        
    # fen_portal.identify(ring, fen)    
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_RESET_CORE", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_RUN_EN", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_ESS_MODE", 0x00000001)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_T0SW", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_VETOSW", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_EXTTRG_EN", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_RAWOFS", 0x00000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_POL", 0x0000001)
    
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_TRG_SOURCE", 0x0000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_TRG_MODE", 0x0000002)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_THRS", 0x00000bb8)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_HIST", 0x000001f4)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_TRG_HOLD", 0x00000019)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_TRG_W", 0x0000000a)

    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_GATE_W", 0x00000064)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_FLT_CFG", 0x00001f66)    
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_C11", 0x00003bc9)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_C12", 0x00007bb6)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_C21", 0x00003c50)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_C22", 0x00007c36)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_CPZ", 0x00000100)    
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_PRB_SEL", 0x0000002)
    
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_RESET_CORE", 0x0000001)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_RESET_CORE", 0x0000000)
    # fen_portal.userRegWrite(ring, fen, "SCI_REG_RUN_EN", 0x0000001)    
    
    # dat=fen_portal.userRegRead(ring, fen, "SCI_REG_PCFG_THRS")
    # print(f"Threshold is set to {dat:#08x}, expected {0x00001770:#08x}")
 
def loadRegisters(cfg):
    """Loads register dictionary from file path or returns dictionary directly."""
    if isinstance(cfg, dict):
        return cfg

    with open(cfg, "r") as f:
        registers = json.load(f)
    return registers
    
def change_threshold(fen_portal, threshold=3000, ring=0, fen=0):
    """Changes the threshold register for a specific FEN, resets core, and verifies readback."""
    # Convert threshold decimal to 32-bit hex string (e.g. 3000 -> '0x00000bb8')
    threshold_hex = f"{int(threshold):#010x}"

    # Write threshold register
    fen_portal.userRegWrite(ring, fen, "SCI_REG_PCFG_THRS", threshold_hex)

    # Perform core reset sequence
    _core_reset(fen_portal, ring=ring, fen=fen)

    # Readback threshold to verify
    _readback_threshold(
        fen_portal, expected_threshold=threshold, ring=ring, fen=fen
    )
           
 
def reg_dict_from_registers(registers):
    # Extract dictionary if full config object is passed
    reg_dict = (
        registers.get("registers", registers)
        if isinstance(registers, dict)
        else registers
    )
    return reg_dict
    
 
def configFEN(fen_portal, registers, ring=0, fen=0):
    
    reg_dict = reg_dict_from_registers(registers)
    
    # 1. Identify device
    fen_portal.identify(ring, fen)

    # 2. Write configuration registers loaded from JSON (translated from decimal to hex)
    for reg_name, val in reg_dict.items():
        if reg_name not in ("SCI_REG_RESET_CORE", "SCI_REG_RUN_EN"):
            hex_val = f"{val:#010x}"  # Converts decimal (e.g. 3000) to '0x00000bb8'
            fen_portal.userRegWrite(ring, fen, reg_name, hex_val)

    # 3. Perform the core reset sequence and enable run in hex
    _core_reset(fen_portal, ring=ring, fen=fen)
    
    # 4. Optional readback verification if threshold exists in reg_dict
    if "SCI_REG_PCFG_THRS" in reg_dict:
        _readback_threshold(
            fen_portal,
            expected_threshold=reg_dict["SCI_REG_PCFG_THRS"],
            ring=ring,
            fen=fen,
        )

def _readback_threshold(fen_portal, expected_threshold=3000, ring=0, fen=0):
    # Readback verification
    dat = fen_portal.userRegRead(ring, fen, "SCI_REG_PCFG_THRS")

    # Normalize readback data to integer for formatted print
    dat_int = int(dat, 16) if isinstance(dat, str) else int(dat)
    expected_int = int(expected_threshold)

    print(
        f"  ---> [Ring {ring}, FEN {fen}] Threshold set to {dat_int:#010x} ({dat_int}), "
        f"expected {expected_int:#010x} ({expected_int})"
    )

def _core_reset(fen_portal, ring=0, fen = 0):
    # 3. Perform the core reset sequence and enable run in hex
    fen_portal.userRegWrite(ring, fen, "SCI_REG_RESET_CORE", f"{1:#010x}")
    fen_portal.userRegWrite(ring, fen, "SCI_REG_RESET_CORE", f"{0:#010x}")
    fen_portal.userRegWrite(ring, fen, "SCI_REG_RUN_EN", f"{1:#010x}")
    
###############################################################################################


def change_threshold_globally(fen_portal, topology, threshold=3000):
    """Parses topology and updates threshold across all FEN nodes on all rings."""
    topology_summary = parse_topology(topology)

    for ring_info in topology_summary["rings"]:
        ring = ring_info["ring"]
        num_nodes = ring_info["nodes"]

        for fen in range(num_nodes):
            print(
                f" ---> Updating threshold ({threshold}) on ring {ring} and fen {fen} ..."
            )
            change_threshold(fen_portal, threshold=threshold, ring=ring, fen=fen)
            print("\n")
    

def configAllFEN(fen_portal, topology, registers):
    """Parses topology and configures all FEN nodes across all rings."""
    # 1. Load register definitions using loadRegisters if a file path string is passed
    if isinstance(registers, str):
        registers = loadRegisters(registers)

    # 2. Extract topology configuration
    topology_summary = parse_topology(topology)

    # 3. Iterate through every ring and node
    for ring_info in topology_summary["rings"]:
        ring      = ring_info["ring"]
        num_nodes = ring_info["nodes"]

        # Loop from 0 to (num_nodes - 1)
        for fen in range(num_nodes):
            print(f" ---> Configuring ring {ring} and fen {fen} ...")
            configFEN(fen_portal, registers, ring=ring, fen=fen)
            print(f"\n")

###############################################################################################


# if essrmmdriver is not installed with pip -e
sys.path.insert(0, "/home/essdaq/detg_git/slow_control_driver")

try:
    from essrmmdriverlib.frontend.FrontEndGenericPortal import (
        FrontEndGenericPortal,
    )
    from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule
except ImportError:
    pass


class R5560SlowCtrl:

    def __init__(
        self,
        rbu_path,
        rbu_file,
        addr_path,
        addr_file,
        cfg_path,
        cfg_file,
        debug=False,
    ):
        self.debug = debug
        self.fen_portal = None

        if not self.debug:
            try:
                rmm = ReadoutMasterModule(
                    cfg_json=os.path.join(rbu_path, rbu_file)
                )
                self.fen_portal = FrontEndGenericPortal(
                    RMMRegs=rmm.RMMRegs,
                    regmap=os.path.join(addr_path, addr_file),
                )
            except Exception as err:
                print(
                    f"[WARN] Hardware connection to RMM failed. Switching R5560 to debug mode: {err}"
                )
                self.debug = True

        # Load configs safely
        reg_file_full = os.path.join(cfg_path, cfg_file)
        rbu_file_full = os.path.join(rbu_path, rbu_file)

        self.cfg_registers = (
            loadRegisters(reg_file_full)
            if os.path.exists(reg_file_full)
            else None
        )
        self.topology = (
            loadConfig(rbu_file_full) if os.path.exists(rbu_file_full) else None
        )

        print(f" ---> backend slow control R5560 initialized with config {cfg_file}")

    def configureR5560(self):
        print("\n----------------------------------------------------------------------")
        print("Configuring R5560 digitiser registers ...\n")

        if not self.debug and self.fen_portal:
            configAllFEN(self.fen_portal, self.topology, self.cfg_registers)
        else:
            print("\n")
            print("Debug mode active: skipping hardware write.")
    
    def changeThreshold(self, threshold=3000):
        print("\n----------------------------------------------------------------------")
        print(f"Changing threshold ({threshold}) on all R5560 digitisers ...\n")

        # Keep internal config state in sync if registers are loaded
        if self.cfg_registers:
            reg_dict = reg_dict_from_registers(self.cfg_registers)
            reg_dict["SCI_REG_PCFG_THRS"] = int(threshold)

        if not self.debug and self.fen_portal:
            change_threshold_globally(
                self.fen_portal, self.topology, threshold=threshold
            )
        else:
            print("Debug mode active: skipping hardware write.")
            
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
   
if __name__ == "__main__":
    current_dir = os.path.abspath(os.path.dirname(__file__))
    sc_dir   = os.path.dirname(current_dir)

    result = parse_topology(
        os.path.join(sc_dir, "rbu_cfg/MIRACLES_2rings", "cfg.json")
    )
    # print(result)
    # 
    
    reg = loadRegisters(os.path.join(sc_dir, "config_R5560", "example5560cfg.json"))
    
    # print(reg)
    
    
    
    # parser = argparse.ArgumentParser(prog="slow_control_driver cspec fen config")
    # parser.add_argument("-c", "--cfg_json", required=True, type=str, help="JSON config file")
    # parser.add_argument("-u", "--user_map", required=True, type=str, help="User Space Register Map")
    # parser.add_argument("-s", "--skip_bringup", action="store_true", help="Skip fresh bringup")
    # parser.add_argument("-t", "--skip_thresholds", action="store_true", help="Skip threshold setting")
  
    # args = parser.parse_args()
    # # Create RMM instance as normal, topology defined in cfg_json
    # rmm = ReadoutMasterModule(cfg_json=args.cfg_json)
    # # Use this to create a generic interface to all FEN userspace
    # fen_portal = FrontEndGenericPortal(RMMRegs=rmm.RMMRegs, regmap=args.user_map)

    # # Brings up the RMM and all rings in the configuration file
    # # Does not perform any Front End "userspace" config
    # # if not args.skip_bringup:
    # #     asyncio.run(rmm.configRMM(timing_mode="lcl"))   # 'mrf', 'lcl' or 'ext'
    
    # if not args.skip_thresholds:
    #     #Config FEN with thresholds etc.
    #     configFEN(fen_portal, 0, 0)
    #     configFEN(fen_portal, 1, 0) 
    #     #configFEN(fen_portal, 2, 0)
    #     #configFEN(fen_portal, 3, 0)
