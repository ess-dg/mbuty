#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_validator.py
--------------------
Stateless, functional replacement for the upfront (pre-read) validation logic
formerly embedded in `read_json_config` / `MONmap` / `DETparameters` /
`DETmap` (lib/libMapping.py, first ~600 lines).

Scope: these functions validate the raw JSON `config: dict` BEFORE any data
ingestion starts. They do NOT duplicate the post-read stream checks that
already live in `newLib/instrument_registry.py`
(`check_valid_data_stream`, `match_data_stream_with_config`, `check_bm_type`).

Schema note: updated to match the current config generator / sample files
(`libConfigGenerator.py`, `AMOR26.json`), which use lowerCamelCase keys
throughout (e.g. `detectorType`, `topology`, `ring`) rather than the legacy
PascalCase keys (`DetectorType`, `Cassette2ElectronicsConfig`, `Ring`).

All legacy warning/error text and exit behavior are preserved; coloring now
goes through `newLib/colors.py` (WARN / ERR / INFO / OK / RESET) via f-strings
instead of inline ANSI escapes, for consistency with the rest of newLib.
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
    
    
from newLib.colors import WARN, ERR, INFO, OK, RESET


# =============================================================================
# BASIC FILE LOADING CHECKS - (common file name errors e.g double extension)
# =============================================================================
def load_config(config_file_path: str) -> dict:
    """
    Safely load a JSON config file into a plain dict.
    Equivalent to legacy openFile() — covers all three failure modes:
    double extension, file not found, and malformed JSON.
    """
    path     = Path(config_file_path)
    filename = path.name
    folder   = str(path.parent)

    # --- Double extension guard (e.g. 'AMOR26.json.json') -------------------
    if len(path.suffixes) > 1 and path.suffixes[-1] == path.suffixes[-2]:
        print(f"\n {ERR}---> Double extension detected in '{filename}'! Please check your file naming convention.{RESET}")
        time.sleep(2)
        sys.exit()

    # --- File not found ------------------------------------------------------
    try:
        fh = open(config_file_path, 'r')
    except (FileNotFoundError, OSError):
        print(f"\n {ERR}---> Config File: {filename} not found{RESET}")
        print(f"\n ---> in folder: {folder} \n -> exiting.")
        time.sleep(2)
        sys.exit()

    # --- Malformed JSON -------------------------------------------------------
    try:
        config = json.load(fh)
    except json.JSONDecodeError:
        print(f"\n {ERR}---> Error in config File: {filename}{RESET}", end='')
        print(' ---> common mistake: last entry in topology must not have a trailing comma! \n -> exiting.')
        time.sleep(2)
        sys.exit()
    finally:
        fh.close()

    return config
# =============================================================================
# Instrument <-> detectorType verification map (legacy verifyTypeWithInstrument)
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
}

VALID_DETECTOR_TYPES = ("MB", "MG", "He3")
VALID_INSTRUMENT_NAMES = (
    "TBL", "AMOR", "ESTIA", "FREIA", "TREX",
    "MIRACLES", "CSPEC", "BIFROST", "VESPA",
)


# =============================================================================
# validate_instrument_and_detector
# =============================================================================

def validate_instrument_and_detector(config: dict, printFlag: bool = True) -> None:
    """Validate 'detectorType', 'instrumentName', and their cross-mapping.

    Equivalent to legacy: get_DETtype() + get_instrumName() + verifyTypeWithInstrument().
    Exits on invalid detectorType or invalid instrumentName.
    Prints a (non-fatal) warning on instrument/type mismatch.
    The final success print is gated by printFlag.
    """
    det_type   = config.get('detectorType')
    instrument = config.get('instrumentName')

    # --- detectorType check (legacy get_DETtype) ------------------------------
    if det_type not in VALID_DETECTOR_TYPES:
        print(f"\n\t{ERR}ERROR: Detector type (found {det_type}) can only be either MB, MG or He3 -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- instrumentName check (legacy get_instrumName) -------------------------
    if instrument not in VALID_INSTRUMENT_NAMES:
        allowed = ", ".join(VALID_INSTRUMENT_NAMES)
        print(f"\n\t{ERR}ERROR: Instrument name {instrument} is invalid. Must be one of: {allowed} \n{RESET}")
        time.sleep(2)
        sys.exit()

    # --- Instrument <-> detectorType cross-check (legacy verifyTypeWithInstrument) ---
    allowed_types = INSTRUMENT_TYPE_MAP.get(instrument, [])

    if det_type not in allowed_types:
        expected = " or ".join(allowed_types)
        print(f"\n\t{WARN}WARNING: Potential configuration mismatch!")
        print(f"\tInstrument '{instrument}' usually uses type: {expected}.")
        print(f"\tCurrent config has: '{det_type}'.")
        print(f"\tAnalysis will proceed, but please verify your JSON settings.{RESET}\n")
        time.sleep(1)

    if printFlag:
        det_name = config.get('detectorName', None)
        print(f"{INFO}Configuration for Detector {det_name}, type {det_type}, instrument {instrument}{RESET}")


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
            print(f"\n\t{ERR}ERROR: Operation mode (found {operation_mode}) can only be either normal or clustered for VMM-based detectors -> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(2)
            sys.exit()
    else:
        if operation_mode == "normal":
            print(f"{INFO}Operation Mode: {operation_mode}{RESET}")
        else:
            print(f"\n\t{ERR}ERROR: Operation mode (found {operation_mode}) can only be normal for {det_type} detectors -> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(2)
            sys.exit()
# =============================================================================
# validate_channel_mapping
# =============================================================================

def validate_channel_mapping(config: dict) -> None:
    """Validate 'channelMapping' block for MB detectors only.

    Checks that wireASIC and stripASIC are each 0 or 1, and that
    they are not equal. The only valid pairs are (0, 1) and (1, 0).
    Exits immediately on any violation.
    """
    if config.get('detectorType') != 'MB':
        return

    channel_mapping = config.get('channelMapping')
    if not channel_mapping:
        print(f"\n\t{ERR}ERROR: 'channelMapping' block missing for MB detector -> check config file! ---> Exiting ...{RESET}")
        time.sleep(2)
        sys.exit()

    entry = channel_mapping[0]
    wire_asic  = entry.get('wireASIC')
    strip_asic = entry.get('stripASIC')

    for name, val in [('wireASIC', wire_asic), ('stripASIC', strip_asic)]:
        if val not in (0, 1):
            print(f"\n\t{ERR}ERROR: '{name}' (found {val!r}) must be 0 or 1 -> check config file! ---> Exiting ...{RESET}")
            time.sleep(2)
            sys.exit()

    if wire_asic == strip_asic:
        print(f"\n\t{ERR}ERROR: wireASIC and stripASIC are both {wire_asic}. "
              f"They must be different (valid pairs: (0,1) or (1,0)) -> check config file! ---> Exiting ...{RESET}")
        time.sleep(2)
        sys.exit()

    print(f"{INFO}Channel mapping: wireASIC={wire_asic}, stripASIC={strip_asic}{RESET}")

# =============================================================================
# validate_unit_configuration
# =============================================================================

def validate_unit_configuration(config: dict) -> None:
    """Validate unit count consistency and guard against ring 11 misuse.

    Equivalent to legacy: check_cassetteLabelling() + checkRing11().
    - 'units' (declared count) must match len('topology').
    - No entry in 'topology' may have "ring" == 11
      (ring 11 is reserved for the Beam Monitor).
    Exits on either violation.
    """
    topology       = config.get('topology', []) or []
    num_units_decl = config.get('units')

    # --- ring 11 guard (legacy checkRing11) -----------------------------------
    for cc in topology:
        if cc.get("ring") == 11:
            print(f"\t {ERR}ERROR: Ring 11 found in config for detector and not associated to MONITOR! -> exiting! {RESET}", end=' ')
            time.sleep(2)
            sys.exit()

    # --- unit count consistency (legacy check_cassetteLabelling) -------------
    units_in_config = [cc.get("ID") for cc in topology]
    num_units_found  = np.shape(units_in_config)[0]

    if num_units_found != num_units_decl:
        print(f"{ERR} CONFIG FILE JSON ERROR: Num of units ({num_units_found}) not matching num of units in list ({num_units_decl}) in Config file{RESET}")
        print(' \n -> exiting.')
        time.sleep(2)
        sys.exit()


# =============================================================================
# validate_monitor_configuration
# =============================================================================

def validate_monitor_configuration(config: dict, printFlag: bool = True) -> None:
    """Validate the 'monitor' block (hardwareType, connectionType, ring rules).

    Equivalent to legacy: get_MONmap() + checkBMsettings().
    NOTE: legacy code supports only ONE monitor entry (mapm[0]); preserved here.
    This is config-time validation only — distinct from `check_bm_type()` in
    instrument_registry.py, which validates the BM *data* array post-read.
    The "no monitor found" warning always prints; the hardwareType /
    connectionType / ring checks below it are gated by printFlag.
    """
    monitor_block = config.get('monitor')

    if monitor_block is None:
        print(f"\t {WARN}WARNING: No monitor config found in json file {RESET}")
        return

    if not printFlag:
        return

    # legacy only ever reads the first monitor entry
    mon = monitor_block[0]

    hardware_type   = mon.get("hardwareType")
    connection_type = mon.get("connectionType")
    ring_id         = mon.get("ring")

    # --- hardwareType check ----------------------------------------------------
    if hardware_type == "generic" or hardware_type == "ibm":
        pass
    else:
        print(f"\n\t{ERR}ERROR: MON hardware (found {hardware_type}) can only be either generic or ibm  -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- connectionType check ---------------------------------------------------
    if connection_type == "lemo" or connection_type == "ring":
        pass
    else:
        print(f"\n\t{ERR}ERROR: MON connection type (found {connection_type}) can only be either lemo or ring  -> check config file! ---> Exiting ... \n{RESET}", end='')
        time.sleep(2)
        sys.exit()

    # --- lemo requires ring >= 11 (legacy: prints WARNING text, but exits) -----
    # NOTE: preserved verbatim from legacy, including the inconsistency where
    # the message text says "WARNING" but the code still calls sys.exit().
    if connection_type == "lemo":
        if ring_id < 11:
            print(f"\n\t{WARN}WARNING: MON mode {connection_type} selected with RING < 11 (ring {ring_id}) (can be any ring 11 - inf, but not < 11)-> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(1)
            sys.exit()

    # --- ring != 11 triggers a non-fatal warning only ---------------------------
    if connection_type == "ring":
        if ring_id != 11:
            print(f"\n\t{WARN}WARNING: MON mode {connection_type} selected with RING != 11 (ring {ring_id} found in config file)\n{RESET}", end='')
            time.sleep(1)


# =============================================================================
# Convenience: run all upfront checks in legacy order
# =============================================================================

def validate_config(config: dict, printFlag: bool = True) -> None:
    """Run all upfront validations in the same order the legacy constructor did:
    instrument/detector -> monitor -> unit configuration -> operation mode.
    """
    validate_instrument_and_detector(config, printFlag)
    validate_monitor_configuration(config, printFlag)
    validate_unit_configuration(config)
    validate_channel_mapping(config)
    if printFlag:
        validate_operation_mode(config)
    
    
    
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
    test_config_path = os.path.join(project_root, "config", "AMOR26.json")
  
    print(f"{INFO}Loading target test configuration: {test_config_path}{RESET}")

    test_config = load_config(test_config_path)
    print(f"{OK}JSON parsed successfully.{RESET}")

    print(f"\n{INFO}Executing functional validation pipeline passes...{RESET}")
    print("-------------------------------------------------------------")

    # Execute the global validation suite
    validate_config(test_config)

    print("-------------------------------------------------------------")
    print(f"{OK}Success: Configuration validation passes verified successfully!{RESET}")