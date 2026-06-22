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

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
    
from newLib.colors import WARN, ERR, INFO, OK, RESET


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

def validate_instrument_and_detector(config: dict) -> None:
    """Validate 'detectorType', 'instrumentName', and their cross-mapping.

    Equivalent to legacy: get_DETtype() + get_instrumName() + verifyTypeWithInstrument().
    Exits on invalid detectorType or invalid instrumentName.
    Prints a (non-fatal) warning on instrument/type mismatch.
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


# =============================================================================
# validate_operation_mode
# =============================================================================

def validate_operation_mode(config: dict) -> None:
    """Validate 'operationMode' against 'detectorType'.

    Equivalent to legacy: print_check_operationMode().
    VMM-based detectors ('MB' or 'MG') must be 'normal' or 'clustered'.
    Other detector types must be 'normal'.
    Exits immediately on an invalid mode.

    NOTE: legacy version always prints the success line on the way out
    ('Operation Mode: {}'); kept here for behavioral parity.
    """
    det_type       = config.get('detectorType')
    operation_mode = config.get('operationMode')

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
            print(f"\n\t{ERR}ERROR: Operation mode (found {operation_mode}) can only be either normal for {det_type} detectors -> check config file! ---> Exiting ... \n{RESET}", end='')
            time.sleep(2)
            sys.exit()


# =============================================================================
# validate_cassette_configuration
# =============================================================================

def validate_cassette_configuration(config: dict) -> None:
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
        print(f"{ERR} CONFIG FILE JSON ERROR: Num of cassettes ({num_units_found}) not matching num of cassettes in list ({num_units_decl}) in Config file{RESET}")
        print(' \n -> exiting.')
        time.sleep(2)
        sys.exit()


# =============================================================================
# validate_monitor_configuration
# =============================================================================

def validate_monitor_configuration(config: dict) -> None:
    """Validate the 'monitor' block (hardwareType, connectionType, ring rules).

    Equivalent to legacy: get_MONmap() + checkBMsettings().
    NOTE: legacy code supports only ONE monitor entry (mapm[0]); preserved here.
    This is config-time validation only — distinct from `check_bm_type()` in
    instrument_registry.py, which validates the BM *data* array post-read.
    """
    monitor_block = config.get('monitor')

    if monitor_block is None:
        print(f"\t {WARN}WARNING: No monitor config found in json file {RESET}")
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

def validate_config(config: dict) -> None:
    """Run all upfront validations in the same order the legacy constructor did:
    instrument/detector -> operation mode -> cassette configuration -> monitor.
    """
    validate_instrument_and_detector(config)
    validate_operation_mode(config)
    validate_cassette_configuration(config)
    validate_monitor_configuration(config)
    
    
    
if __name__ == '__main__':
    # =============================================================================
    # STANDALONE COMPONENT TEST HARNESS
    # =============================================================================
    import os
    import json

    print(f"{INFO}--- Starting Standalone Config Validator Test ---{RESET}")

    # Define paths to test context files locally
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    
    # Target your specific lower-camelCase configuration profile
    test_config_path = os.path.join(project_root, "config", "AMOR26.json")

    print(f"{INFO}Loading target test configuration: {test_config_path}{RESET}")

    if not os.path.exists(test_config_path):
        print(f"{ERR}Test Aborted: Configuration file not found at {test_config_path}{RESET}")
        sys.exit(1)

    try:
        with open(test_config_path, 'r') as f:
            test_config = json.load(f)
        print(f"{OK}JSON parsed successfully.{RESET}")
    except Exception as e:
        print(f"{ERR}JSON Parsing Error: {e}{RESET}")
        sys.exit(1)

    print(f"\n{INFO}Executing functional validation pipeline passes...{RESET}")
    print("-------------------------------------------------------------")
    
    # Execute the global validation suite
    validate_config(test_config)
    
    print("-------------------------------------------------------------")
    print(f"{OK}Success: Configuration validation passes verified successfully!{RESET}")