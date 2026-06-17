#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_dataframe_view.py
======================
Verification scratchpad to test the newly implemented get_data_frame() 
method inside Spyder's Variable Explorer environment.
"""

import os
import sys
from types import SimpleNamespace

# Adjust these path configurations to match your local setup
BASE_DIR = r'C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap'
NEW_LIB_DIR = os.path.join(BASE_DIR, 'newLib')
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Add newLib to the search path so we grab your updated files
if NEW_LIB_DIR not in sys.path:
    sys.path.insert(0, NEW_LIB_DIR)

import reader as new_lib

# Setup a clean test run target
PCAP_FILENAME = 'sampleData_ClusteredMode.pcapng'
RUNTIME_MODE = 'clustered'  # Options: 'normal' or 'clustered'
NS_PER_CLOCK_TICK = 11.356860963629653

MOCK_CONFIG_DICT = {
    "DetectorType": "MB",
    "InstrumentName": "AMOR",
    "DETparameters": {"instrument": "AMOR", "type": "MB"},
    "Monitor": [{"hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11}],
    "Cassette2ElectronicsConfig": [{"ID": 0, "Ring": 0, "Fen": 0, "Hybrid": 0}]
}

def test_dataframe_extraction():
    pcap_path = os.path.join(DATA_DIR, PCAP_FILENAME)
    if not os.path.exists(pcap_path):
        raise FileNotFoundError(f"Target PCAP file missing at: {pcap_path}")

    # Set up parameters and mock configuration
    parameters = SimpleNamespace(
        acqMode        = 'pcap',
        clockTicks     = SimpleNamespace(NSperClockTick=NS_PER_CLOCK_TICK),
        VMMsettings    = SimpleNamespace(timeResolutionType='coarse'),
        fileManagement = SimpleNamespace(pcapLoadingMethod='allocate'),
    )
    injected_config = dict(MOCK_CONFIG_DICT)
    injected_config['operationMode'] = RUNTIME_MODE

    # Run the parsing engine
    print(f"Ingesting file: {PCAP_FILENAME}...")
    reader = new_lib.PcapngFileReader(pcap_path, parameters, injected_config)
    reader.run()

    # Get the target container that filled up with data
    container = reader.readouts_vmm_normal if RUNTIME_MODE == 'normal' else reader.readouts_vmm_clustered

    print("\nExecuting inherited get_data_frame() method...")
    
    # --- THIS EXERCISES THE NEW CODE LINE ---
    df_view = container.get_data_frame()
    
    print("\nVerification Test Successful!")
    print(f"DataFrame dimensions: {df_view.shape[0]} rows x {df_view.shape[1]} columns.")
    print("\n--- FIRST 5 ROWS VIEW ---")
    print(df_view.head(5))
    
    return df_view

if __name__ == '__main__':
    # Running this exposes 'df_result' to your Spyder Variable Explorer panel
    df_result = test_dataframe_extraction()
    print("\n--> Done! Go to your Spyder Variable Explorer panel and double-click 'df_result'.")