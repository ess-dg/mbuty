#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
threshold_engine.py
Created on Thu July 9 2026
@author: Sheila Monera Cabarique
--------------------
Software (pulse-height) threshold engine.

A threshold is a lower bound on pulse height: events whose pulse height
does not exceed the bound for their channel are rejected. Thresholds are
defined per physical unit (cassette / column / tube, i.e. matrix['ID'])
and per local channel within that unit.
"""
import os, sys
import numpy as np
import pandas as pd
import json

_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib.colors import INFO, WARN, ERR, RESET, OK

# =============================================================================
# 'ch0' refers to the channel selector derived from coordinate0 (wires),
# gating pulseHeight0.
# 'ch1' refers to the channel selector derived from coordinate1
# (strips/grids for MB/MG, tube ID for R5560).
# This mirrors the schema's own field naming (coordinate0/1, pulseHeight0/1)
# rather than introducing detector-specific vocabulary (wire/strip/grid/tube),
# so the same table/engine machinery works for every detector type.
#
# Tubes (R5560) are handled entirely separately below -- each tube is its
# own topology unit with a single scalar threshold, not an array of
# per-channel thresholds, so they don't share the ThresholdTable machinery.
# =============================================================================


def _read_threshold_file(filepath: str):
    """Read a .csv or .xlsx threshold file into a DataFrame, or None if missing."""

    if not os.path.exists(filepath):
        print(f"\t {WARN}WARNING: threshold file '{filepath}' not found -> software thresholds switched OFF{RESET}")
        return None

    print(f"\t {INFO}loading thresholds from file: {os.path.basename(filepath)} ...{RESET}")
    return pd.read_csv(filepath) if filepath.lower().endswith('.csv') else pd.read_excel(filepath)


###############################################################################

def validate_entries_in_th(unit_ids,unit_cols):
    missing = set(unit_ids) - set(unit_cols)
    if missing:
            print(f"\t {WARN}-> threshold file/arrays have no entries for unit IDs "
                  f"{sorted(missing)} -> software thresholds switched OFF for those IDs. "
                  f"\n\t config file contains IDs: {unit_ids}{RESET}")
    

###############################################################################
# Legacy threshold files label planes by physical name rather than schema
# field name; map them onto the ch0/ch1 selectors used by the engines.
_PLANE_TO_CHANNEL_TYPE = {'wire': 'ch0', 'strip': 'ch1', 'grid': 'ch1'}

###############################################################################
def _validate_wire_strip_threshold_file(df: pd.DataFrame, unit_ids, num_wires, num_strips) -> bool:
    """
    Checks the file's shape against what the config actually expects:
      - a plane column, a channel column, and at least one unit column
      - every plane label is recognized (wire/strip/grid)
      - each plane's row count matches config['wires'] (ch0) or
        config['strips']/config['grids'] (ch1)
      - every requested unit_id has a column for each plane present

    Prints every problem found (doesn't stop at the first) and returns
    False if anything is off, so the caller can switch thresholds off
    entirely rather than silently loading a partial/misshapen table.
    """
    ok = True
    
    if df.shape[1] < 3:
        ok = False
        print(f"\t {ERR}ERROR: threshold file needs a plane column, a channel column, "
              f"and at least one unit ID column -> software thresholds switched OFF{RESET}")
        return ok
    
    plane_col, channel_col, *unit_cols = df.columns
    
    # num_wires  = config['wires']
    # num_strips = config.get('strips', config.get('grids', None))
    # unit_ids = [item["ID"] for item in config.get("topology", [])]
  
    validate_entries_in_th(unit_ids,unit_cols)
     
    if not (len(df) == (num_wires+num_strips)):
        print(f"\t {ERR}-> threshold file it does not have the right number of wires or strips/grids -> exiting.{RESET}")
        ok = False
        sys.exit()
        
    if df.isna().sum().sum() > 0:
        print(f"\t {ERR}-> threshold file has EMPTY entries -> exiting.{RESET}")
        ok = False
        sys.exit()
        
    # label_array = df.groupby(plane_col).size().values
    
    label_array = df[plane_col]
    is_wire  = label_array == 'wire'
    is_strip = (label_array == 'strip') | (label_array == 'grid')
    
    if np.sum(is_wire) != num_wires:
        print(f"\t {ERR}-> threshold file it does not have the right number of wires -> exiting.{RESET}")
        ok = False
        sys.exit()
        
    if np.sum(is_strip) != num_strips:  
        print(f"\t {ERR}-> threshold file it does not have the right number strips/grids -> exiting.{RESET}")
        ok = False
        sys.exit()

    return ok
            
###############################################################################
class ThresholdTable:
    """
    Maps (unit_id, channel_type) -> 1D array of per-local-channel thresholds.
    channel_type is 'ch0' or 'ch1'. Missing (unit_id, channel_type) pairs
    mean "no threshold defined" -> that channel is never gated.
    """

    def __init__(self, config: dict):
        self.config = config  
        self.table  = {} 
        
        self.num_wires  = config['wires']
        self.num_strips = config.get('strips', config.get('grids', None))
        self.unit_ids   = [item["ID"] for item in config.get("topology", [])]

    def from_file(self, filepath: str):
        """
        Load a threshold table (.xlsx or .csv) in the established MBUTY layout:
        first column is the plane label ('wire' / 'strip' / 'grid'), second
        column is the local channel index within that plane, and every
        remaining column is a unit ID (cassette/column) with per-channel
        threshold values down the rows, e.g.

            <blank>   Cassette ID   1      2      3    ...
            wire      0             5000   12380  ...
            wire      1             5000   16190  ...
            ...
            strip     0             0      0      ...

        Despite the header, the second column is a channel index, not a
        cassette ID — the actual unit IDs are the remaining column headers.

        Row counts per plane are validated against config['wires'] /
        config['strips'] (or 'grids') -- any mismatch switches thresholds
        off entirely rather than loading a misshapen table.
        """
        df = _read_threshold_file(filepath)
        
        # self.df = df 
        
        if df is None:
            return 

        if not _validate_wire_strip_threshold_file(df,self.unit_ids,self.num_wires,self.num_strips):
            return 

        plane_col, channel_col, *unit_cols = df.columns
        table = {}
        for plane_label, group in df.groupby(plane_col):
            channel_type = _PLANE_TO_CHANNEL_TYPE[str(plane_label).strip().lower()]

            group      = group.sort_values(channel_col)
            channels   = group[channel_col].to_numpy(dtype='int64')
            n_channels = int(channels.max()) + 1

            for uid_col in unit_cols:
                try:
                    uid = int(uid_col)
                except (TypeError, ValueError):
                    continue

                # Create the inner dictionary for this unit ID if it doesn't exist yet
                if uid not in table:
                    table[uid] = {}

                # Build the flat NumPy array for this specific plane's channel layout
                arr = np.zeros(n_channels, dtype='float64')
                arr[channels] = group[uid_col].to_numpy(dtype='float64')
                
                # Assign to nested key 'ch0' or 'ch1' directly inside the UID profile
                table[uid][channel_type] = arr

        return table

    def from_arraysOrDict(self, arrays: dict) -> 'ThresholdTable':
        """
        Build directly from user-supplied arrays. Two equivalent shapes accepted:
            {(unit_id, 'ch0'): array, (unit_id, 'ch1'): array, ...}
            {unit_id: {'ch0': array, 'ch1': array}, ...}
        """
        
        DEFAULT_SIZES = {
        'ch0': self.num_wires,   # Wires
        'ch1': self.num_strips   # Strips/grids
         }
        
        unit_cols = list(arrays.keys())
  
        validate_entries_in_th(self.unit_ids,unit_cols)
        
        table = {}
        for uid, channels in arrays.items():
            table[uid] = {}
            
            for ch_type in ['ch0', 'ch1']:
                if ch_type in channels:
                    # If the channel array is provided, use it directly as a float64 array
                    table[uid][ch_type] = channels[ch_type].astype('float64')
                else:
                    # If missing, initialize a flat array of zeros matching the hardware size
                    table[uid][ch_type] = np.zeros(DEFAULT_SIZES[ch_type], dtype='float64')
                    
        return table



    def from_constants(self, values: list) -> 'ThresholdTable':
        """
        Build from a flat (ch0_value, ch1_value) pair, same bound for every
        unit_id. Pass None for a plane you don't want gated, e.g. (700, None)
        thresholds ch0 only, leaves ch1 ungated.
        """
        ch0_value = values[0]
        ch1_value = values[1]
        table = {}
        
        # Hardware channel lengths: ch0 (wires) = 32, ch1 (strips) = 64
        CH0_SIZE = self.num_wires
        CH1_SIZE = self.num_strips

        for uid in self.unit_ids:
            uid_int = int(uid)
            table[uid_int] = {}
            
            # Populate ch0 (wires)
            if ch0_value is not None:
                table[uid_int]['ch0'] = np.full(CH0_SIZE, float(ch0_value), dtype='float64')
            else:
                table[uid_int]['ch0'] = np.zeros(CH0_SIZE, dtype='float64')
                
            # Populate ch1 (strips)
            if ch1_value is not None:
                table[uid_int]['ch1'] = np.full(CH1_SIZE, float(ch1_value), dtype='float64')
            else:
                table[uid_int]['ch1'] = np.zeros(CH1_SIZE, dtype='float64')
                
        return table
        

###############################################################################
###############################################################################
# =============================================================================
# Tube Threshold Table + Engine (R5560) — fully standalone
# =============================================================================
#
# Each R5560 tube is its own topology unit (unit_id == tube_id), so a tube
# only ever needs a single scalar pulse-height cut -- not an array of
# per-channel thresholds.
#
# Expected tube threshold file layout: exactly two rows, no plane/channel
# columns -- tube IDs as the header, a single row of threshold values below:
#
#     1        2        3        4
#     6000.0   6200.0   5800.0   6100.0
# =============================================================================

def _validate_tube_threshold_file(df: pd.DataFrame, unit_ids) -> bool:
    """
    A tube file has no plane/channel columns -- just tube IDs as headers
    and exactly one row of threshold values, since each tube is its own
    unit with a single scalar cut, not an array of per-channel thresholds.
    """
    
    ok = True 
    
    if df.shape[0] != 1:
        ok = False
        print(f"\t {ERR}ERROR: tube threshold file must contain exactly one row of values, "
              f"found {df.shape[0]} -> software thresholds switched OFF{RESET}")
        return ok
    
    unit_cols = df.columns

    validate_entries_in_th(unit_ids,unit_cols)

    if not (len(df) == 1):
        print(f"\t {ERR}-> threshold file it does not have the right number rows, must be 1 threshold per tube -> exiting.{RESET}")
        ok = False
        sys.exit()      
          
    if df.isna().sum().sum() > 0:
        print(f"\t {ERR}-> threshold file has EMPTY entries -> exiting.{RESET}")
        ok = False
        sys.exit()          
        

    return ok

###############################################################################
###############################################################################
class TubeThresholdTable:
    """Maps tube_id -> a single scalar threshold. No channel arrays."""

    def __init__(self, config: dict):
        self.config = config  
        self.table  = {} 
        self.unit_ids   = [item["ID"] for item in config.get("topology", [])]

    def from_file(self, filepath: str):
        """Expects file in validated format above, just two rows 
        (one with IDs and one with columns)"""
        df = _read_threshold_file(filepath)
        
        # self.df = df 
        
        if df is None:
            return 
      
        if not _validate_tube_threshold_file(df, self.unit_ids):
            return 

        row = df.iloc[0]
        table = {}
        for col in df.columns:
            try:
                uid = int(col)
            except (TypeError, ValueError):
                continue
            table[uid] = float(row[col])
            
        return table

    def from_arraysOrDict(self, values: dict):
        """Expected dictionary format {ID: value , ...}
        parameters.dataReduction.softThArray = {1: 6000.0, 2: 6200.0, 3: 5800.0, 4: 6100.0}"""
   
        unit_cols = list(values.keys())
        validate_entries_in_th(self.unit_ids,unit_cols)
        table = {int(k): float(v) for k, v in values.items()}
        
        return table

    def from_constants(self, list):
        """Expected constant to be applied to all tubes:
        parameters.dataReduction.softThArray = 6000.0"""

        table = {int(uid): float(list[0]) for uid in self.unit_ids}
        
        return table


###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################

class BaseThresholdEngine:
    """
    Shared load/reject logic for wire/strip/grid detector types (MB, MG).
    Tubes (R5560) are handled entirely separately by TubeThresholdEngine
    below -- they don't share this base class.

    Parameters
    ----------
    events     : events container (eventsVMMnormal, eventsVMMclustered, ...)
    config     : flat dict loaded from JSON config file
    parameters : legacy parameters object (dot-notation access)
    """

    def __init__(self, events, config: dict, parameters):
        self.events     = events
        self.config     = config
        self.parameters = parameters
        self.unit_ids   = [entry['ID'] for entry in config['topology']]
        self.table      = {}
        self.thEngine   = None
        # self.table      = ThresholdTable.empty()

    def load(self) -> None:
        """Populate self.table according to parameters.dataReduction.softThresholdType."""
        mode = self.parameters.dataReduction.softThresholdType

        if mode == 'fromFile':
            path = os.path.join(
                self.parameters.fileManagement.thresholdFilePath,
                self.parameters.fileManagement.thresholdFileName,
            )
            self.table = self.thEngine.from_file(path)
            if not self.table:
                self.parameters.dataReduction.softThresholdType = 'off'

        elif mode == 'userDefined':
            print(f"\t {INFO}loading user-defined thresholds ...{RESET}")
            self.table = self.thEngine.from_arraysOrDict(self.parameters.dataReduction.softThArray)

        elif mode == 'constants':
            print(f"\t {INFO}loading constant thresholds ...{RESET}")
            self.table = self.thEngine.from_constants(self.parameters.dataReduction.softThArray)

        else:
            print(f"\t {ERR}ERROR: unknown softThresholdType '{mode}' -> software thresholds switched OFF{RESET}")
            self.table = {}
            self.parameters.dataReduction.softThresholdType = 'off'

    def apply(self) -> None:
        """Override in subclasses: build a keep_mask and reject the rest."""
        raise NotImplementedError(f'{self.__class__.__name__} must implement apply()')

    def process_pipeline(self) -> None:
        """Entry point: load thresholds (if enabled) then apply them."""
        
        print(f"{INFO}Software thresholds ...{RESET}")
        
        if self.parameters.dataReduction.softThresholdType == 'off':
            print(f"\t {INFO}detector software thresholds OFF ...{RESET}")
            return

        self.load()

        if self.parameters.dataReduction.softThresholdType == 'off':
            # load() may itself have switched thresholds off on error
            return

        self.apply()


# =============================================================================
# Wire / Strip / Grid Threshold Engine (Multi-Blade, Multi-Grid)
# =============================================================================

class VMMThresholdEngine(BaseThresholdEngine):
    """
    Dual-plane threshold engine for MB and MG.

    ch0 gates pulseHeight0 (wires), decoded to a per-unit local channel via
    coordinate0 mod n_wires. This mod decode is equivalent to MB's wrap-around
    numbering and to MG's per-unit subtraction (coordinate0 - k*n_wires),
    since both schemes assign coordinate0 = k*n_wires + local_channel.

    ch1 gates pulseHeight1 (strips for MB, grids for MG). coordinate1 is
    already a local, unit-relative index in both cases (see
    MBAbsUnitsCalculator / MGAbsUnitsCalculator in abs_units_engine.py),
    so no decoding is needed there.

    An event is rejected only on a channel it actually has (per the
    coordinate >= 0 sentinel) — a missing plane never gates the event.
    """
    
    def load(self):
        
        self.thEngine = ThresholdTable(self.config)
        
        super().load()
 

    def apply(self) -> None:
        print(f"\t {INFO}applying software thresholds ...{RESET}")

        n = self.events.fill_count
        if n == 0:
            return

        m       = self.events.matrix[:n]
        n_wires = int(self.config['wires'])

        has_ch0 = m['coordinate0'] >= 0
        has_ch1 = m['coordinate1'] >= 0

        safe_coord0 = np.nan_to_num(m['coordinate0'], nan=-1)
        ch0_local   = np.mod(safe_coord0.astype('int64'), n_wires)
        ch1_local   = np.nan_to_num(m['coordinate1'], nan=-1).astype('int64')

        keep_ch0 = np.ones(n, dtype=bool)
        keep_ch1 = np.ones(n, dtype=bool)
        
        for uid in self.unit_ids:
            # 1. Safely retrieve the nested dictionaries for the unit ID
            unit_data = self.table.get(uid)
            if not unit_data:
                continue  # No threshold rules defined for this unit ID, skip it

            sel_unit = m['ID'] == uid

            # --- Process Channel 0 (Wires) ---
            arr0 = unit_data.get('ch0')
            sel0 = sel_unit & has_ch0
            if arr0 is not None and np.any(sel0):
                idx = np.clip(ch0_local[sel0], 0, len(arr0) - 1)
                keep_ch0[sel0] = m['pulseHeight0'][sel0] > arr0[idx]

            # --- Process Channel 1 (Strips) ---
            arr1 = unit_data.get('ch1')
            sel1 = sel_unit & has_ch1
            if arr1 is not None and np.any(sel1):
                idx = np.clip(ch1_local[sel1], 0, len(arr1) - 1)
                keep_ch1[sel1] = m['pulseHeight1'][sel1] > arr1[idx]

        reject_mask = ~(keep_ch0 & keep_ch1)
        self.events.matrix['ID'][:self.events.fill_count][reject_mask] = -1
        self.events.remove_invalid()
       




###############################################################################
###############################################################################
class TubeThresholdEngine(BaseThresholdEngine):
    """
    threshold engine for the He-3 tube detector (CAEN R5560).
    Each tube is its own topology unit (unit_id == tube_id)
    """
    def load(self):
        
        self.thEngine = TubeThresholdTable(self.config)
        
        super().load()

    def apply(self) -> None:
        print(f"\t {INFO}applying per-tube software thresholds ...{RESET}")

        n = self.events.fill_count
        if n == 0:
            return

        m    = self.events.matrix[:n]
        keep = np.ones(n, dtype=bool)

        for uid in self.unit_ids:
            threshold = self.table.get(uid)
            if threshold is None:
                continue
            sel = m['ID'] == uid
            if np.any(sel):
                keep[sel] = m['pulseHeight0'][sel] > threshold

        self.events.matrix['ID'][:self.events.fill_count][~keep] = -1
        self.events.remove_invalid()

###############################################################################
###############################################################################
###############################################################################
###############################################################################
# =============================================================================
# Monitor threshold engine
# =============================================================================
def apply_monitor_threshold(events, threshold: float) -> None:
    """
    Flat threshold for the beam monitor: pulseHeight0 <= threshold is
    rejected. No units, no channels, no ThresholdTable — mirrors the
    legacy `if MONThreshold > 0: belowTh = PHW <= MONThreshold` check,
    just using the reject/remove_invalid path instead of removeData().
    """
    if threshold <= 0:
        print(f"\n\t {INFO}beam monitor software threshold OFF ...{RESET}")
        return

    print(f"\n\t {INFO}applying beam monitor software threshold ...{RESET}")

    n = events.fill_count
    if n == 0:
        return

    reject_mask = events.matrix['pulseHeight0'][:n] < threshold
    events.matrix['ID'][:n][reject_mask] = -1
    events.remove_invalid()

    print(f'{OK}\t MON events (after threshold): {events.fill_count}{RESET}')

###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
# =============================================================================
# Manual test / demo
# =============================================================================
if __name__ == '__main__':
    # from types import SimpleNamespace
    # from container_events import eventsVMMnormal, eventsR5560
 
    # pd.set_option('display.width', 160)
    # pd.set_option('display.max_columns', 20)
 
    REAL_XLSX_PATH = '/Users/francescopiscitelli/git_repos/mbuty/config/MB300L_thresholds.xlsx'
    TUBE_XLSX_PATH = '/Users/francescopiscitelli/git_repos/mbuty/config/tube_threshold_example.xlsx'
 
    # UNIT_IDS = [1, 2, 3, 4, 5, 8]   # unit IDs present as columns in MB300L_thresholds.xlsx
    # N_WIRES  = 32
    # N_STRIPS = 64
 
    # def make_params(filename, filepath):
    #     return SimpleNamespace(
    #         dataReduction=SimpleNamespace(softThresholdType='fromFile', softThArray=None),
    #         fileManagement=SimpleNamespace(thresholdFilePath=filepath, thresholdFileName=filename),
    #     )
 
    # def make_fake_vmm_events(n_per_unit=1000, seed=0):
    #     rng = np.random.default_rng(seed)
    #     n = n_per_unit * len(UNIT_IDS)
    #     ev = eventsVMMnormal(size=n)
 
    #     computed_fields = {
    #         'ID':           np.repeat(UNIT_IDS, n_per_unit),
    #         'coordinate0':  rng.integers(0, N_WIRES, size=n).astype('float64'),
    #         'coordinate1':  rng.integers(0, N_STRIPS, size=n).astype('float64'),
    #         'pulseHeight0': rng.integers(0, 25000, size=n),
    #         'pulseHeight1': rng.integers(0, 25000, size=n),
    #         'mult0':        np.ones(n, dtype='int64'),
    #         'mult1':        np.ones(n, dtype='int64'),
    #         'clusterTimeSpan': np.zeros(n, dtype='int64'),
    #     }
    #     timing_src = {
    #         'timeStamp': np.arange(n, dtype='int64'),
    #         'pulseT':    np.zeros(n, dtype='int64'),
    #         'prevPT':    np.zeros(n, dtype='int64'),
    #     }
    #     ev.absorb(computed_fields, timing_src)
    #     return ev
 
    # def make_fake_tube_events(tube_ids, n_per_unit=1000, seed=1):
    #     rng = np.random.default_rng(seed)
    #     n = n_per_unit * len(tube_ids)
    #     ev = eventsR5560(size=n)
 
    #     computed_fields = {
    #         'ID':           np.repeat(tube_ids, n_per_unit),
    #         'coordinate0':  np.full(n, -1.0),
    #         'coordinate1':  np.full(n, -1.0),
    #         'pulseHeight0': rng.integers(0, 25000, size=n),
    #     }
    #     timing_src = {
    #         'timeStamp': np.arange(n, dtype='int64'),
    #         'pulseT':    np.zeros(n, dtype='int64'),
    #         'prevPT':    np.zeros(n, dtype='int64'),
    #     }
    #     ev.absorb(computed_fields, timing_src)
    #     return ev
 
    # # --- Wire/strip (MB300L) ---
    # print('\n' + '=' * 80)
    # print('WIRE/STRIP thresholds from MB300L_thresholds.xlsx')
    # print('=' * 80)
 
    # vmm_config = {'wires': N_WIRES, 'strips': N_STRIPS, 'topology': [{'ID': uid} for uid in UNIT_IDS]}
    # vmm_params = make_params(os.path.basename(REAL_XLSX_PATH), os.path.dirname(REAL_XLSX_PATH))
    # vmm_events = make_fake_vmm_events()
    
    configFileName1  = "AMOR.json"
    
    configFileName2  = "MIRACLES1.json"
    
    current_dir = '/Users/francescopiscitelli/git_repos/mbuty/'

    config_path1 = os.path.join(current_dir, 'config') + os.sep +configFileName1

    config_path2 = os.path.join(current_dir, 'config') + os.sep +configFileName2
    
    with open(config_path1, 'r') as f:
        config1 = json.load(f)
        
    with open(config_path2, 'r') as f:
            config2 = json.load(f)
        
  
    
    # unit_ids = [item["ID"] for item in config.get("topology", [])]
    tht = ThresholdTable(config1)
     
    table1 = tht.from_file(REAL_XLSX_PATH)
    
    
    
    
    oftThArray = {
               5: {'ch0': np.full(32, 1000.0)},   # cassette 1, wire thresholds only
               6: {'ch0': np.full(32, 500.0), 'ch1': np.full(64, 700.0)},
           } 
    table2 = tht.from_arraysOrDict(oftThArray)
    
    oftThArray = {
               11: 1334,  
                6: 4566,
            } 
    
    softThArray = [15000, 5000]
    
    table3 = tht.from_constants(softThArray)
    
    
    
    
    
    tht20 = TubeThresholdTable(config2)
    
    table21 = tht20.from_file(TUBE_XLSX_PATH)
    # df = tht.df
    
    oftThArray = {
               11: 1334,  
                6: 4566,
            } 
    
    softThArray = [6666]
    
    table22 = tht20.from_arraysOrDict(oftThArray)
    
    table23 = tht20.from_constants(softThArray)
    
    
    # print(f'\nBEFORE ({vmm_events.fill_count} events):')
    # print(vmm_events.get_data_frame().head(10))
 
    # VMMThresholdEngine(vmm_events, vmm_config, vmm_params).process_pipeline()
 
    # print(f'\nAFTER ({vmm_events.fill_count} events):')
    # print(vmm_events.get_data_frame().head(10))
    # print(f'\nsoftThresholdType after run: {vmm_params.dataReduction.softThresholdType}')
 
    # # --- Tubes (R5560) ---
    # print('\n' + '=' * 80)
    # print('TUBE thresholds from tube_threshold_example.xlsx')
    # print('=' * 80)
 
    # tube_file_units = [int(c) for c in pd.read_excel(TUBE_XLSX_PATH).columns]
    # tube_config = {'topology': [{'ID': uid} for uid in tube_file_units]}
    # tube_params = make_params(os.path.basename(TUBE_XLSX_PATH), os.path.dirname(TUBE_XLSX_PATH))
    # tube_events = make_fake_tube_events(tube_file_units)
 
    # print(f'\nBEFORE ({tube_events.fill_count} events):')
    # print(tube_events.get_data_frame().head(10))
 
    # TubeThresholdEngine(tube_events, tube_config, tube_params).process_pipeline()
 
    # print(f'\nAFTER ({tube_events.fill_count} events):')
    # print(tube_events.get_data_frame().head(10))
    # print(f'\nsoftThresholdType after run: {tube_params.dataReduction.softThresholdType}')