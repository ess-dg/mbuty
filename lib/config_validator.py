#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_validator.py

@author: Sheila Monera Cabarique
--------------------
Upfront validation for raw JSON config dicts before data ingestion.

These functions validate the config structure and values (instrument/detector
types, unit counts, monitor settings, operation modes, ID uniqueness) and do NOT
duplicate the post-read stream checks in `lib/instrument_registry.py`
(`check_valid_data_stream`, `match_data_stream_with_config`, `check_bm_type`).

New config uses lowerCamelCase keys throughout (e.g. `detectorType`, `topology`, `ring`).
Coloring applied via `lib/colors.py` (WARN / ERR / INFO / OK / RESET).
"""

import sys
import time
import os
import numpy as np
from pathlib import Path
import json


# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
    
from lib.colors import WARN, ERR, INFO, OK, RESET

# =============================================================================
# BASIC FILE LOADING CHECKS - (common file name errors e.g double extension)
# =============================================================================
def load_config(config_file_path: str) -> dict:
    """
    Load a JSON config file into a dict.
    Handles double extensions, missing files, and malformed JSON.
    """
    path     = Path(config_file_path)
    filename = path.name
    folder   = str(path.parent)

    # --- Double extension guard (e.g. 'AMOR26.json.json') -------------------
    if len(path.suffixes) > 1 and path.suffixes[-1] == path.suffixes[-2]:
        print(f"\n {ERR}Config File Error ---> Double extension detected in '{filename}'! Please check your file naming convention.{RESET}")
        time.sleep(2)
        sys.exit()

    # --- File not found ------------------------------------------------------
    try:
        fh = open(config_file_path, 'r')
    except (FileNotFoundError, OSError):
        print(f"\n {ERR}Config File Error ---> {filename} not found{RESET}")
        print(f"\n ---> in folder: {folder} \n -> exiting.")
        time.sleep(2)
        sys.exit()

    # --- Malformed JSON -------------------------------------------------------
    try:
        config = json.load(fh)
    except json.JSONDecodeError:
        print(f"\n {ERR}Config File Error --->: {filename}{RESET}", end='')
        print(' ---> common mistake: last entry in topology must not have a trailing comma! \n -> exiting.')
        time.sleep(2)
        sys.exit()
    finally:
        fh.close()

    return config
# =============================================================================
# Instrument <-> detectorType verification map
# =============================================================================

INSTRUMENT_TYPE_MAP = {
    "TBL":      ["He3", "MB"],
    "CSPEC":    ["He3"],
    "MIRACLES": ["He3"],
    "VESPA":    ["He3"],
    "BIFROST":  ["He3"],
    "ESTIA":    ["MB"],
    "FREIA":    ["MB"],
    "AMOR":     ["MB"],
    "TREX":     ["MG"],
    "SKADI":    ["SKADI"],
    "NMX":      ["NMX"]
}

VALID_DETECTOR_TYPES = ("MB", "MG", "He3", "SKADI", "NMX")
VALID_INSTRUMENT_NAMES = (
    "TBL", "AMOR", "ESTIA", "FREIA", "TREX",
    "MIRACLES", "CSPEC", "BIFROST", "VESPA",
    "SKADI", "NMX",
)


# =============================================================================
# validate_instrument_and_detector
# =============================================================================

def validate_instrument_and_detector(config: dict) -> None:
    """Validate 'detectorType', 'instrumentName', and their cross-mapping.

    Exits on invalid detector type or instrument name.
    Prints a non-fatal warning on instrument/type mismatch.
    """
    det_type   = config.get('detectorType')
    instrument = config.get('instrumentName')

    # --- detectorType check
    if det_type not in VALID_DETECTOR_TYPES:
        print(f"\n\t{ERR}Config File Error ---> Detector type (found {det_type}) can only be either MB, MG or He3 -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- instrumentName check
    if instrument not in VALID_INSTRUMENT_NAMES:
        allowed = ", ".join(VALID_INSTRUMENT_NAMES)
        print(f"\n\t{ERR}Config File Error ---> Instrument name {instrument} is invalid. Must be one of: {allowed} \n{RESET}")
        time.sleep(2)
        sys.exit()

    # --- Instrument <-> detectorType cross-check
    allowed_types = INSTRUMENT_TYPE_MAP.get(instrument, [])

    if det_type not in allowed_types:
        expected = " or ".join(allowed_types)
        print(f"\n\t{WARN}Config File WARNING: Potential configuration mismatch!")
        print(f"\tInstrument '{instrument}' usually uses type: {expected}.")
        print(f"\tCurrent config has: '{det_type}'.")
        print(f"\tAnalysis will proceed, but please verify your JSON settings.{RESET}\n")
        time.sleep(1)

    det_name = config.get('detectorName', None)
    print(f"{INFO}Configuration for Detector {det_name}, type {det_type}, instrument {instrument}{RESET}")
    
# =============================================================================

def match_instrument_and_detector(det_type,instrument) -> None:
    
    flag = True

    # --- detectorType check
    if det_type not in VALID_DETECTOR_TYPES:
        print(f"\n\t{ERR}Config File Error ---> Detector type (found {det_type}) can only be either MB, MG or He3 -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- instrumentName check
    if instrument not in VALID_INSTRUMENT_NAMES:
        allowed = ", ".join(VALID_INSTRUMENT_NAMES)
        print(f"\n\t{ERR}Config File Error ---> Instrument name {instrument} is invalid. Must be one of: {allowed} \n{RESET}")
        time.sleep(2)
        sys.exit()

    # --- Instrument <-> detectorType cross-check
    allowed_types = INSTRUMENT_TYPE_MAP.get(instrument, [])

    if det_type not in allowed_types:
        flag = False
        expected = " or ".join(allowed_types)
        print(f"\n\t{WARN}Config File WARNING: Potential configuration mismatch!")
        print(f"\tInstrument '{instrument}' usually uses type: {expected}.")
        print(f"\tCurrent config has: '{det_type}'.")
        print(f"\tAnalysis will proceed, but please verify your JSON settings.{RESET}\n")
        time.sleep(1)


    return flag
# =============================================================================
# validate_operation_mode
# =============================================================================

def validate_operation_mode(config: dict) -> None:
    """Validate 'operationMode' against 'detectorType'.

    Equivalent to legacy: print_check_operationMode().
    VMM-based detectors ('MB' or 'MG') must be 'normal' or 'clustered'.
    Other detector types must be 'normal'.
    Exits immediately on an invalid mode.
    """
    det_type       = config.get('detectorType')
    operation_mode = config.get('operationMode', 'normal')

    if det_type == 'MG' or det_type == 'MB':
        if operation_mode == "normal" or operation_mode == "clustered":
            print(f"{INFO}Operation Mode: {operation_mode}{RESET}")
        else:
            print(f"\n\t{ERR}Config File Error ---> Operation mode (found {operation_mode}) can only be either normal or clustered for VMM-based detectors -> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(2)
            sys.exit()
    else:
        if operation_mode == "normal":
            print(f"{INFO}Operation Mode: {operation_mode}{RESET}")
        else:
            print(f"\n\t{ERR}Config File Error ---> Operation mode (found {operation_mode}) can only be normal for {det_type} detectors -> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(2)
            sys.exit()

# =============================================================================
# validate_unit_configuration
# =============================================================================

def validate_unit_configuration(config: dict) -> None:
    """Validate unit count consistency and guard against ring 11 misuse.

    - 'units' (declared count) must match len('topology').
    - No entry in 'topology' may have "ring" == 11 (reserved for Beam Monitor).
    Exits on either violation.
    """
    topology       = config.get('topology', []) or []
    num_units_decl = config.get('units')

    # --- ring 11 guard
    for cc in topology:
        if cc.get("ring") == 11:
            print(f"\t {ERR}Config File Error ---> Ring 11 found in config for detector and not associated to MONITOR! -> exiting! {RESET}", end=' ')
            time.sleep(2)
            sys.exit()

    # --- unit count consistency
    units_in_config = [cc.get("ID") for cc in topology]
    num_units_found  = np.shape(units_in_config)[0]

    if num_units_found != num_units_decl:
        print(f"{ERR}Config File Error ---> Num of units ({num_units_found}) not matching num of units in list ({num_units_decl}) in Config file{RESET}")
        print(' \n -> exiting.')
        time.sleep(2)
        sys.exit()


# =============================================================================
# validate_monitor_configuration
# =============================================================================

def validate_monitor_configuration(config: dict) -> None:
    """Validate the 'monitor' block (hardwareType, connectionType, ring rules).

    Config-time validation only—distinct from `check_bm_type()` in
    instrument_registry.py, which validates the BM data array post-read.
    Processes the first monitor entry only.
    """
    monitor_block = config.get('monitor')

    if monitor_block is None:
        print(f"\t {WARN}Config File WARNING ---> No monitor config found in json file {RESET}")
        return

    # Process first monitor entry
    mon = monitor_block[0]

    hardware_type   = mon.get("hardwareType")
    connection_type = mon.get("connectionType")
    ring_id         = mon.get("ring")

    # --- hardwareType check ----------------------------------------------------
    if hardware_type == "generic" or hardware_type == "ibm":
        pass
    else:
        print(f"\n\t{ERR}Config File Error ---> MON hardware (found {hardware_type}) can only be either generic or ibm  -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- connectionType check ---------------------------------------------------
    if connection_type == "lemo" or connection_type == "ring":
        pass
    else:
        print(f"\n\t{ERR}Config File Error ---> MON connection type (found {connection_type}) can only be either lemo or ring  -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- lemo requires ring >= 11
    if connection_type == "lemo":
        if ring_id < 11:
            print(f"\n\t{WARN}Config File WARNING ---> MON mode {connection_type} selected with RING < 11 (ring {ring_id}) (can be any ring 11 - inf, but not < 11)-> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(1)
            sys.exit()

    # --- ring != 11 triggers a non-fatal warning only ---------------------------
    if connection_type == "ring":
        if ring_id != 11:
            print(f"\n\t{WARN}Config File WARNING ---> MON mode {connection_type} selected with RING != 11 (ring {ring_id} found in config file)\n{RESET}", end='')
            time.sleep(1)

# =============================================================================
# validate duplicate IDs and must be integers 
# =============================================================================

def validate_IDs(config: dict) -> None:
    
    # 1. Pull all IDs
    all_ids = [item["ID"] for item in config['topology'] if "ID" in item]
 
    # 2. Strict type check: Ensure every single ID is explicitly an int
    all_are_integers = all(type(i) is int for i in all_ids)
    
    # 3. Check for uniqueness
    all_are_unique = len(all_ids) == len(set(all_ids))
    
    # --- Validation Logic ---
    if not all_are_integers:
        print(f"\n\t{ERR}Config File Error ---> Config Validation Failed: One or more IDs are not strictly integers.\n{RESET}", end='')
        time.sleep(2)
        sys.exit()
        
    if not all_are_unique:
        print(f"\n\t{ERR}Config File Error ---> Config Validation Failed: One or more IDs are duplicated. IDs must be unique.\n{RESET}", end='')
        time.sleep(2)
        sys.exit()
        
 

# =============================================================================
# Convenience: run all upfront checks
# =============================================================================

def validate_config(config: dict) -> None:
    """Run all upfront validations: instrument/detector -> monitor -> 
    unit configuration -> operation mode.
    """
    validate_instrument_and_detector(config)
    validate_monitor_configuration(config)
    validate_unit_configuration(config)
    validate_IDs(config)
    validate_operation_mode(config)    

    
###############################################################################
############################################################################### 
###############################################################################
###############################################################################   
###############################################################################
###############################################################################   
###############################################################################
###############################################################################   
  
    
if __name__ == '__main__':
    # =============================================================================
    # STANDALONE COMPONENT TEST HARNESS
    # =============================================================================
    import os

    print(f"{INFO}--- Starting Standalone Config Validator Test ---{RESET}")

    # Define paths to test context files locally
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))

    # Target your specific lower-camelCase configuration profile
    test_config_path = os.path.join(project_root, "config", "AMOR.json")
  
    print(f"{INFO}Loading target test configuration: {test_config_path}{RESET}")

    test_config = load_config(test_config_path)
    print(f"{OK}JSON parsed successfully.{RESET}")

    print(f"\n{INFO}Executing functional validation pipeline passes...{RESET}")
    print("-------------------------------------------------------------")

    # Execute the global validation suite
    validate_config(test_config)

    print("-------------------------------------------------------------")
    print(f"{OK}Success: Configuration validation passes verified successfully!{RESET}")