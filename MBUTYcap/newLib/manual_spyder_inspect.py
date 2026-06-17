#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
manual_spyder_inspect.py
========================
Interactive script for Spyder Variable Explorer analysis.
Extracts data blocks into formatted Pandas DataFrames with explicit headers.
"""

import os
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd

# =============================================================================
# WORKSPACE ENVIRONMENT SETUP
# =============================================================================
BASE_DIR    = r'C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap'
OLD_LIB_DIR = os.path.join(BASE_DIR, 'lib')
NEW_LIB_DIR = os.path.join(BASE_DIR, 'newLib')
DATA_DIR    = os.path.join(BASE_DIR, 'data')

# Set your target file and mode here
PCAP_FILENAME = 'sampleData_ClusteredMode.pcapng'
RUNTIME_MODE  = 'clustered'  # Options: 'normal' or 'clustered'

NS_PER_CLOCK_TICK = 11.356860963629653

MOCK_CONFIG_DICT = {
    "DetectorType": "MB",
    "InstrumentName": "AMOR",
    "DETparameters": {"instrument": "AMOR", "type": "MB"},
    "Monitor": [{"hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11}],
    "Cassette2ElectronicsConfig": [
        {"ID": 0, "Ring": 0, "Fen": 0, "Hybrid": 0},
    ]
}

# Mapping schema to match column orders dynamically
VMM_NORMAL_FIELDS = ['ring', 'fen', 'vmm', 'hybrid', 'asic', 'channel', 'adc', 'bc', 'oth', 'tdc', 'geo', 'timeStamp', 'pulseT', 'prevPT', 'g0']
VMM_CLUSTERED_FIELDS = ['ring', 'fen', 'hybrid', 'geo', 'g0', 'timeStamp', 'pulseT', 'prevPT', 'channel0', 'adc0', 'mult0', 'channel1', 'adc1', 'mult1']


def run_pipelines():
    pcap_path = os.path.join(DATA_DIR, PCAP_FILENAME)
    if not os.path.exists(pcap_path):
        raise FileNotFoundError(f"Target PCAP data file missing at: {pcap_path}")

    # -------------------------------------------------------------------------
    # 1. RUN OLD PIPELINE
    # -------------------------------------------------------------------------
    if OLD_LIB_DIR in sys.path: sys.path.remove(OLD_LIB_DIR)
    sys.path.insert(0, OLD_LIB_DIR)
    import libReadPcapng as old_lib
    
    print("Running legacy parsing loop...")
    old_pcap = old_lib.pcapng_reader(
        pcap_path,
        NSperClockTick        = NS_PER_CLOCK_TICK,
        MONhw                 = 'GENERIC',
        MONconn               = 'RING',
        MONring               = 11,
        timeResolutionType    = 'coarse',
        sortByTimeStampsONOFF = False,
        operationMode         = RUNTIME_MODE,
        pcapLoadingMethod     = 'allocate',
    )
    old_obj = old_pcap.readouts

    # -------------------------------------------------------------------------
    # 2. RUN NEW PIPELINE
    # -------------------------------------------------------------------------
    if NEW_LIB_DIR in sys.path: sys.path.remove(NEW_LIB_DIR)
    sys.path.insert(0, NEW_LIB_DIR)
    import reader as new_lib
    
    print("Running refactored contiguous vector pipeline...")
    parameters = SimpleNamespace(
        acqMode        = 'pcap',
        clockTicks     = SimpleNamespace(NSperClockTick=NS_PER_CLOCK_TICK),
        VMMsettings    = SimpleNamespace(timeResolutionType='coarse'),
        fileManagement = SimpleNamespace(pcapLoadingMethod='allocate'),
    )
    injected_config = dict(MOCK_CONFIG_DICT)
    injected_config['operationMode'] = RUNTIME_MODE

    new_reader = new_lib.PcapngFileReader(pcap_path, parameters, injected_config)
    new_reader.run()
    
    new_obj = new_reader.readouts_vmm_normal if RUNTIME_MODE == 'normal' else new_reader.readouts_vmm_clustered
    return old_obj, new_obj

# %%
if __name__ == '__main__':
    old_container, new_container = run_pipelines()
    
    print("\nProcessing DataFrame translations for Spyder visualization...")
    fields = VMM_NORMAL_FIELDS if RUNTIME_MODE == 'normal' else VMM_CLUSTERED_FIELDS

    # --- DATAFRAME 1: UNPACK OLD OBJECT ---
    # Explicit Change: Re-mapped the unique lowercase keys to exact legacy cased attributes
    old_attr_map = {
        'ring': 'Ring',
        'fen': 'Fen',
        'vmm': 'VMM',
        'hybrid': 'hybrid',
        'asic': 'ASIC',
        'channel': 'Channel',
        'adc': 'ADC',
        'bc': 'BC',
        'oth': 'OTh',
        'tdc': 'TDC',
        'geo': 'GEO',
        'timestamp': 'timeStamp',
        'pulset': 'PulseT',
        'prevpt': 'PrevPT',
        'g0': 'G0',
        # Clustered specific name re-mappings
        'channel0': 'Channel',
        'adc0': 'ADC',
        'mult0': 'mult0',
        'channel1': 'Channel1',
        'adc1': 'ADC1',
        'mult1': 'mult1'
    }
    
    old_dict = {}
    for f in fields:
        attr_name = old_attr_map.get(f.lower(), f)
        old_dict[f] = getattr(old_container, attr_name)
    
    df_old_view = pd.DataFrame(old_dict)
    if 'timeStamp' in df_old_view.columns:
        df_old_view = df_old_view.sort_values(by='timeStamp').reset_index(drop=True)

    # --- DATAFRAME 2: UNPACK NEW CONTIGUOUS MATRIX ---
    new_count = new_container.fill_count
    new_active_slice = new_container.matrix[:new_count]
    
    new_dict = {f: new_active_slice[f] for f in fields}
    df_new_view = pd.DataFrame(new_dict)
    if 'timeStamp' in df_new_view.columns:
        df_new_view = df_new_view.sort_values(by='timeStamp').reset_index(drop=True)

    print(f"\n{'-'*60}\nTransformation Complete!\n{'-'*60}")
    print("--> Go to your Spyder Variable Explorer panel.")
    print("--> Double-click 'df_old_view' to see the legacy data grid with headers.")
    print("--> Double-click 'df_new_view' to see the refactored data grid with headers.\n")