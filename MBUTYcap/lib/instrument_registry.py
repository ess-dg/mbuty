#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
instrument_registry.py
-----------------------
Central registry of ESS instrument identifiers and associated hardware metadata.

Replaces the original checkInstrumentID and checkBMtype classes. All state and
mutation has been removed; the registry is a module-level constant and all logic
is in plain functions.
"""

import sys
import numpy as np
from .colors import WARN, ERR, RESET

# =============================================================================
# Registry
# =============================================================================

INSTRUMENTS = {
    # ---- Multi-Blade (VMM3A) ------------------------------------------------
    72:  {'name': 'FREIA',    'hex': '0x48', 'type': 'MB',    'hw': 'VMM',      'bytes': 20, 'supported': True,  'reader_supported': True},
    76:  {'name': 'ESTIA',    'hex': '0x4c', 'type': 'MB',    'hw': 'VMM',      'bytes': 20, 'supported': True,  'reader_supported': True},
    78:  {'name': 'AMOR',     'hex': '0x4e', 'type': 'MB',    'hw': 'VMM',      'bytes': 20, 'supported': True,  'reader_supported': True},
    73:  {'name': 'TBLMB',    'hex': '0x49', 'type': 'MB',    'hw': 'VMM',      'bytes': 20, 'supported': True,  'reader_supported': True},
    # ---- Multi-Grid (VMM3A) -------------------------------------------------
    64:  {'name': 'TREX',     'hex': '0x40', 'type': 'MG',    'hw': 'VMM',      'bytes': 20, 'supported': True,  'reader_supported': True},
    68:  {'name': 'NMX',      'hex': '0x44', 'type': 'GDG',   'hw': 'VMM',      'bytes': 20, 'supported': False, 'reader_supported': True},
    # ---- Helium-3 (CAEN R5560) ----------------------------------------------
    60:  {'name': 'CSPEC',    'hex': '0x3c', 'type': 'He3',   'hw': 'R5560',    'bytes': 24, 'supported': True,  'reader_supported': True},
    52:  {'name': 'BIFROST',  'hex': '0x34', 'type': 'He3',   'hw': 'R5560',    'bytes': 24, 'supported': True,  'reader_supported': True},
    56:  {'name': 'MIRACLES', 'hex': '0x38', 'type': 'He3',   'hw': 'R5560',    'bytes': 24, 'supported': True,  'reader_supported': True},
    0:   {'name': 'VESPA',    'hex': '0x00', 'type': 'He3',   'hw': 'R5560',    'bytes': 24, 'supported': True,  'reader_supported': True},
    # ---- Straw (R5560bis) — reader not yet supported ------------------------
    48:  {'name': 'LOKI',     'hex': '0x30', 'type': 'straw', 'hw': 'R5560bis', 'bytes': 24, 'supported': False, 'reader_supported': False},
    # ---- Beam Monitor -------------------------------------------------------
    16:  {'name': 'BM',       'hex': '0x10', 'type': 'BM',    'hw': 'BM',       'bytes': 20, 'supported': True,  'reader_supported': True},
    # ---- SKADI --------------------------------------------------------------
    32:  {'name': 'SKADI',    'hex': '0x20', 'type': 'SKADI', 'hw': 'SKADI',    'bytes': 20, 'supported': False, 'reader_supported': True},
    # ---- JAL / CPIX — not supported -----------------------------------------
    100: {'name': 'MAGIC',    'hex': '0x64', 'type': 'JAL',   'hw': 'CPIX',     'bytes': 20, 'supported': False, 'reader_supported': False},
    96:  {'name': 'DREAM',    'hex': '0x60', 'type': 'JAL',   'hw': 'CPIX',     'bytes': 20, 'supported': False, 'reader_supported': False},
}


# =============================================================================
# Core lookup functions
# =============================================================================

def get_info(instr_id: int) -> dict | None:
    """Return a copy of the registry entry for instr_id, or None if unknown."""
    entry = INSTRUMENTS.get(int(instr_id))
    return dict(entry) if entry is not None else None


def get_id_from_name(name: str) -> int | None:
    """Reverse lookup: return the integer ID for a given instrument name, or None."""
    name_upper = name.upper()
    for instr_id, info in INSTRUMENTS.items():
        if info['name'].upper() == name_upper:
            return instr_id
    return None


def get_readout_spec(instr_id: int) -> tuple[int, str | None]:
    """Return (bytes_per_readout, hw) for the given instrument ID."""
    entry = INSTRUMENTS.get(int(instr_id))
    if entry is not None:
        return entry['bytes'], entry['hw']
    return 20, None


def print_info_data_stream(instr_id: int) -> None:
    """Print a one-line description of the data stream for the given ID."""
    info = get_info(instr_id)
    if info is not None:
        print(f"found {info['name']} data stream - {info['hw']}", end='')


# =============================================================================
# Post-read stream validation
# =============================================================================

def check_valid_data_stream(instr_ids_found: set, unknown_instr_ids: set) -> None:
    """Validate instrument IDs seen during reading and print a summary."""
    all_ids = instr_ids_found | unknown_instr_ids

    print('checking instrument IDs and data streams ... ', end='')
    
    # for iid in sorted(all_ids):
    #     info = get_info(iid)
    #     name = info['name'] if info is not None else f'Unknown(0x{iid:02x})'
    #     print(f'\n---> found {name} (ID {iid})', end='')
    # print()

    temp            = np.unique(np.array(list(all_ids), dtype='int64'))
    instr_ids_clean = temp[temp >= 0]

    # --- 0 IDs ---------------------------------------------------------------
    if len(instr_ids_clean) == 0:
        print('\n---> no instr ID', end='')

    # --- 1 ID ----------------------------------------------------------------
    elif len(instr_ids_clean) == 1:
        target_id = int(instr_ids_clean[0])
        info = get_info(target_id)

        if info is None:
            print(f"\n{ERR}ERROR: found unknown data stream with ID {target_id}{RESET}", end='')
            sys.exit(1)

        name = info['name']
        if info['supported'] and info['reader_supported']:
            print(f"---> OK: Valid instrument ({name}).")
        elif not info['supported'] and info['reader_supported']:
            print(f"\n{WARN}WARNING: found '{name}' data stream, analysis not supported, "
                  f"reader only! Analysis continues but questionable results are on the horizon.{RESET}")
        elif not info['supported'] and not info['reader_supported']:
            print(f"\n{ERR}ERROR: found '{name}' data stream, analysis nor reader supported! Exit.{RESET}")
            sys.exit(1)
        elif info['supported'] and not info['reader_supported']:
            print(f"\n{ERR}ERROR: found '{name}' data stream, supported but reader_supported "
                  f"is False — check INSTRUMENTS registry. Exit.{RESET}")
            sys.exit(1)

    # --- 2 IDs ---------------------------------------------------------------
    elif len(instr_ids_clean) == 2:
        all_streams        = []
        valid_for_analysis = []
        valid_for_reading  = []
        has_bm             = False

        for iid in instr_ids_clean:
            info = get_info(int(iid))
            if info is None:
                # Append placeholder string to ensure index sizes match context counts
                all_streams.append(f'Unknown(0x{int(iid):02x})')
                continue
            if info['type'] == 'BM':
                has_bm = True
            all_streams.append(info['name'])
            if info['supported'] and info['reader_supported']:
                valid_for_analysis.append(info['name'])
            elif not info['supported'] and info['reader_supported']:
                valid_for_reading.append(info['name'])

        valid_for_analysis = [n for n in valid_for_analysis if n != 'BM']
        valid_for_reading  = [n for n in valid_for_reading  if n != 'BM']

        if len(valid_for_analysis) == 1 and has_bm:
            print(f"---> OK: Valid instrument ({valid_for_analysis[0]}) with Beam Monitor detected.")
        elif len(valid_for_analysis) == 2:
            print(f"{WARN}---> WARNING: Two valid analysis streams found "
                  f"({', '.join(valid_for_analysis)}). Check RMM output queue config!{RESET}")
        elif len(valid_for_analysis) == 1:
            other = [n for n in all_streams if n != valid_for_analysis[0]][0]
            print(f"{WARN}---> WARNING: Found {valid_for_analysis[0]}, but the second stream "
                  f"({other}) is not supported. Results might be affected.{RESET}")
        elif len(valid_for_reading) == 1:
            print(f"{WARN}---> WARNING: 2 data streams detected: ({', '.join(all_streams)}). "
                  f"No analysis-ready streams. Only reader support for: "
                  f"({', '.join(valid_for_reading)}). Analysis continues but check config RMM.{RESET}")
        elif has_bm and not valid_for_reading and not valid_for_analysis:
            other = [n for n in all_streams if n != 'BM'][0]
            print(f"{WARN}---> WARNING: 2 data streams detected: ({', '.join(all_streams)}). "
                  f"No analysis-ready streams found. The non-BM stream ({other}) is unsupported. "
                  f"Results might be affected.{RESET}")
        else:
            print(f"{ERR}---> ERROR: 2 data streams detected: ({', '.join(all_streams)}). "
                  f"Neither of the 2 streams are valid for analysis or reading. Exit.{RESET}")
            sys.exit(1)

    # --- 3+ IDs --------------------------------------------------------------
    else:
        all_streams        = []
        valid_for_analysis = []
        valid_for_reading  = []

        for iid in instr_ids_clean:
            info = get_info(int(iid))
            if info is None:
                all_streams.append(f'Unknown(0x{int(iid):02x})')
                continue
            all_streams.append(info['name'])
            if info['supported'] and info['reader_supported']:
                valid_for_analysis.append(info['name'])
            elif not info['supported'] and info['reader_supported']:
                valid_for_reading.append(info['name'])

        print(f"\n{WARN}WARNING: {len(instr_ids_clean)} data streams detected: "
              f"({', '.join(all_streams)}){RESET}")

        if valid_for_analysis:
            print(f"{WARN}---> At least one valid stream found ({', '.join(valid_for_analysis)}). "
                  f"Analysis continues despite extra data. Data might be corrupted - "
                  f"check RMM output queue config! {RESET}")
        elif valid_for_reading:
            print(f"{WARN}---> WARNING: None of the {len(instr_ids_clean)} "
                  f"({', '.join(valid_for_reading)}) streams are valid for analysis but just reader. "
                  f"Analysis continues. Data might be corrupted - check RMM output queue config!{RESET}")
        else:
            print(f"{ERR}---> ERROR: None of the {len(instr_ids_clean)} streams are valid "
                  f"for analysis nor just reader. Exit.{RESET}")
            sys.exit(1)


# =============================================================================
# Application-layer functions
# =============================================================================

def _check_det_type_exists(det_type: str) -> bool:
    """Verify that det_type is a known type string in the registry."""
    existing_types = {info['type'] for info in INSTRUMENTS.values()}

    if det_type not in existing_types:
        print(f"\n{ERR}ERROR: detector type {det_type} in config file is not a "
              f"possible type. Valid types: {', '.join(sorted(existing_types))}{RESET}")
        sys.exit(1)

    match = next((info for info in INSTRUMENTS.values() if info['type'] == det_type), None)
    if match and not match['supported'] and match['reader_supported']:
        print(f"{WARN}WARNING: detector type {det_type} is supported only by "
              f"the Reader, but not yet by the Main Analysis Pipeline.{RESET}")
    elif match and not match['supported'] and not match['reader_supported']:
        print(f"{ERR}ERROR: detector type {det_type} is currently not supported.{RESET}")
        sys.exit(1)

    return True


def match_data_stream_with_config(instr_name_from_conf: str, det_type: str, instr_ids_found: set) -> None:
    """Cross-check instrument IDs found in the file against config statements."""
    ids_arr   = np.array(list(instr_ids_found), dtype='int64')
    valid_ids = np.unique(ids_arr[ids_arr >= 0])

    if len(valid_ids) == 0:
        print('\n---> no instr ID', end='')

    _check_det_type_exists(det_type)

    all_streams = []
    all_types   = []
    found_flag  = False

    for iid in valid_ids:
        info = get_info(iid)
        if info is None:
            all_streams.append(f'Unknown(0x{int(iid):02x})')
            all_types.append('Unknown')
            continue
        all_streams.append(info['name'])
        all_types.append(info['type'])
        if info['type'] == det_type:
            found_flag = True

    unique_streams = ', '.join(all_streams)
    unique_types   = ', '.join(all_types)

    if found_flag:
        print(f"\n\t{WARN}File containing data streams {unique_streams} for detector types {unique_types}{RESET}")
        print(f"\t{WARN}analyzed for instrument {instr_name_from_conf} and type {det_type}{RESET}")
    else:
        print(f"\n\t{ERR}WARNING: CONFIGURATION MISMATCH!{RESET}", end='')
        print(f"\n\t{ERR}You are trying to read a file containing data streams {unique_streams} for detector types {unique_types}{RESET}")
        print(f"\t{ERR}But in your config file you have specified instrument {instr_name_from_conf} and type {det_type}{RESET}")


def check_bm_type(geo: np.ndarray, bm_hw: str) -> None:
    """Cross-check the type field of Beam Monitor readouts against configuration targets."""
    if len(geo) == 0:
        return

    for geo_val in np.unique(geo):
        if geo_val == 1:
            if bm_hw == 'ibm':
                print(f"\n\t{WARN}WARNING: found BM data type 1 (GENERIC - 0D) but config says {bm_hw}!")
                print("\tThe BM data may be parsed incorrectly.{RESET}")
            else:
                print(f"\n\tBM data is type 1 (GENERIC - 0D)")
        elif geo_val == 2:
            if bm_hw == 'ibm':
                print(f"\n\t{WARN}WARNING: found BM data type 2 (GENERIC - 1D or 2D) but config says {bm_hw}!")
                print("\tThe BM data may be parsed incorrectly.{RESET}")
            else:
                print(f"\n\tBM data is type 2 (GENERIC - 1D or 2D)")
        elif geo_val == 3:
            if bm_hw == 'generic':
                print(f"\n\t{WARN}WARNING: found BM data type 3 (IBM) but config says {bm_hw}!")
                print("\tThe BM data may be parsed incorrectly.{RESET}")
            else:
                print(f"\n\tBM data is type 3 (IBM)")
        else:
            print(f"\n\t{ERR}WARNING: BM data found with unexpected type: {geo_val}.{RESET}")
            print(f"\tValid BM types are usually only type 0 (GENERIC) or 3 (IBM).{RESET}")