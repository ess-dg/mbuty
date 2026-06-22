#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testing.py
==========
Precise cell-by-cell regression testing environment for MBUTY. 
Orchestrates runs between legacy libReadPcapng and refactored reader layers.
"""

import sys
import os
import argparse
import traceback
from types import SimpleNamespace
import numpy as np
import time

import libReadPcapng as old_lib

# from lib import libReadPcapng as old_lib

# =============================================================================
# ENVIRONMENT & REALIGNED PATH CONFIGURATION
# =============================================================================
# Locate parent workspace directory to establish clean absolute path anchors
# BASE_DIR    = r'C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap'

BASE_DIR    = r'/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/'



OLD_LIB_DIR = os.path.join(BASE_DIR, 'lib')
NEW_LIB_DIR = os.path.join(BASE_DIR, 'newLib')
DATA_DIR    = os.path.join(BASE_DIR, 'data')



MOCK_CONFIG_DICT = {
    "detectorType": "MB",
    "instrumentName": "AMOR",
    "DETparameters": {
        "instrument": "AMOR",
        "type": "MB"
    },
    "Monitor": [
        {
            "hardwareType": "GENERIC",
            "connectionType": "RING",
            "ring": 11
            
        }
    ],
    "Cassette2ElectronicsConfig": [
        {"ID": 0, "Ring": 0, "Fen": 0, "Hybrid": 0},
        {"ID": 1, "Ring": 0, "Fen": 0, "Hybrid": 1},
        {"ID": 2, "Ring": 0, "Fen": 0, "Hybrid": 2},
        {"ID": 3, "Ring": 0, "Fen": 0, "Hybrid": 3}
    ]
}

TEST_CASES = [
    {
        'pcap':           '20260611_083055_pkts100_Test-full_00000.pcapng',
        'runtime_mode':   'normal',
        'label':          'Full-Stream-Normal-Mode',
    },
    {
        'pcap':           '20260611_083146_pkts100_Test-half_00000.pcapng',
        'runtime_mode':   'normal',
        'label':          'Half-Stream-Normal-Mode',
    },
    {
        'pcap':           '20260611_083304_pkts100_Test-allEmpty_00000.pcapng',
        'runtime_mode':   'normal',
        'label':          'All-Empty-Packets-Stream',
    },
    {
        'pcap':           '20260611_083348_pkts100_Test-almostAllEmpty_00000.pcapng',
        'runtime_mode':   'normal',
        'label':          'Almost-All-Empty-Packets-Stream',
    },
    {
        'pcap':           'sampleData_ClusteredMode.pcapng',
        'runtime_mode':   'clustered',
        'label':          'Clustered-Legacy-Stream',
    }
]

TEST_CASES = [
    {
        'pcap':           'ESSmask2023_4pkts.pcapng',
        'runtime_mode':   'normal',
        'label':          'Full-Stream-Normal-Mode',
    }
    
    ]


# TEST_CASES = [
# {
#     'pcap':           'sampleData_ClusteredMode.pcapng',
#     'runtime_mode':   'clustered',
#     'label':          'Clustered-Legacy-Stream',
# }
    
#      ]


# TEST_CASES = [
# {
#     'pcap':           'MG_2EMMAprototypes.pcapng',
#     'runtime_mode':   'normal',
#     'label':          'mg',
# }
    
#      ]


# TEST_CASES = [
# {
#     'pcap':           'miracles_source_on_left_red.pcapng',
#     'runtime_mode':   'normal',
#     'label':          'mira',
# }
    
#      ]


NS_PER_CLOCK_TICK  = 11.356860963629653

VMM_NORMAL_FIELD_MAP = [
    ('Ring',       'ring'),
    ('Fen',        'fen'),
    ('VMM',        'vmm'),
    ('hybrid',     'hybrid'),
    ('ASIC',       'asic'),
    ('Channel',    'channel'),
    ('ADC',        'adc'),
    ('BC',         'bc'),
    ('OTh',        'oth'),
    ('TDC',        'tdc'),
    ('GEO',        'geo'),
    ('timeStamp',  'timeStamp'),
    ('PulseT',     'pulseT'),
    ('PrevPT',     'prevPT'),
    ('G0',         'g0'),
]

VMM_CLUSTERED_FIELD_MAP = [
    ('Ring',      'ring'),
    ('Fen',       'fen'),
    ('hybrid',    'hybrid'),
    ('GEO',       'geo'),
    ('G0',        'g0'),
    ('timeStamp', 'timeStamp'),
    ('PulseT',    'pulseT'),
    ('PrevPT',    'prevPT'),
    ('Channel',   'channel0'),
    ('ADC',       'adc0'),
    ('mult0',     'mult0'),
    ('Channel1',  'channel1'),
    ('ADC1',      'adc1'),
    ('mult1',     'mult1'),
]

CLR_PASS  = '\033[1;32m'
CLR_FAIL  = '\033[1;31m'
CLR_WARN  = '\033[1;33m'
CLR_INFO  = '\033[1;36m'
CLR_RESET = '\033[0m'


# =============================================================================
# EXECUTORS
# =============================================================================
def run_old_reader(pcap_path, runtime_mode):
    sys.path.insert(0, OLD_LIB_DIR)
    import importlib
    import libReadPcapng as old_lib
    importlib.reload(old_lib)
    
    tProfilingStart = time.time()
    
    pcap = old_lib.pcapng_reader(
        pcap_path,
        NSperClockTick        = NS_PER_CLOCK_TICK,
        MONhw                 = 'GENERIC',
        MONconn               = 'RING',
        MONring               =  11,
        timeResolutionType    = 'coarse',
        sortByTimeStampsONOFF = False,
        operationMode         = runtime_mode,
        pcapLoadingMethod     = 'allocate',
    )
    
    
    
    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 
    
    return pcap.readouts




def run_new_reader(pcap_path, runtime_mode):
    sys.path.insert(0, NEW_LIB_DIR)
    import importlib
    # Explicit Change: Replaced 'detector_types' reference with the updated module token 'reader'
    import reader as new_lib
    importlib.reload(new_lib)
    
    tProfilingStart = time.time()

    parameters = SimpleNamespace(
        acqMode        = 'pcap',
        clockTicks     = SimpleNamespace(NSperClockTick=NS_PER_CLOCK_TICK),
        VMMsettings    = SimpleNamespace(timeResolutionType='coarse'),
        config         = SimpleNamespace(DETparameters=SimpleNamespace(operationMode=runtime_mode)),
        fileManagement = SimpleNamespace(pcapLoadingMethod='allocate'),
    )

    injected_config = dict(MOCK_CONFIG_DICT)
    injected_config['operationMode'] = runtime_mode

    reader = new_lib.PcapngFileReader(
        file_path  = pcap_path,
        parameters = parameters,
        config     = injected_config,
    )
    reader.run()
    
    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 
    
    return reader.readouts_vmm_normal if runtime_mode == 'normal' else reader.readouts_vmm_clustered


# =============================================================================
# ANALYSIS LOGIC
# =============================================================================
def perform_deep_matrix_diff(old_container, new_container, runtime_mode, verbose=False):
    issues = []
    
    old_count = len(old_container.timeStamp) if hasattr(old_container, 'timeStamp') else 0
    new_count = new_container.fill_count
    
    print(f"  [Matrix Diagnostics]: Old Container Rows = {old_count} | Vectorized Matrix Rows = {new_count}")
    
    if old_count != new_count:
        issues.append(f"TOTAL ROWS COUNT MISMATCH: Old reader found {old_count} rows, new reader found {new_count} rows.")
        return False, issues

    if old_count == 0:
        return True, issues

    old_sort_idx = np.argsort(old_container.timeStamp)
    new_sort_idx = np.argsort(new_container.matrix['timeStamp'][:new_count])

    field_map = VMM_NORMAL_FIELD_MAP if runtime_mode == 'normal' else VMM_CLUSTERED_FIELD_MAP

    for old_attr, new_field in field_map:
        old_array = getattr(old_container, old_attr, None)
        if old_array is None or len(old_array) == 0:
            continue
            
        new_array = new_container.matrix[new_field][:new_count]

        old_sorted = old_array[old_sort_idx]
        new_sorted = new_array[new_sort_idx]

        if not np.array_equal(old_sorted, new_sorted):
            mismatched_indices = np.where(old_sorted != new_sorted)[0]
            qty = len(mismatched_indices)
            issues.append(f"Cell Mismatch in Column [{old_attr} -> {new_field}]: {qty}/{old_count} indices diverge.")
            
            if verbose:
                for idx in mismatched_indices[:3]:
                    issues.append(f"    ! Divergence at row index {idx}: Old value={old_sorted[idx]} | New value={new_sorted[idx]}")

    return len(issues) == 0, issues


def main():
    parser = argparse.ArgumentParser(description='MBUTY Aligned Data Matrix Regression')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print exact cell values when row elements diverge')
    args = parser.parse_args()

    print(f"{CLR_INFO}{'='*72}\n MBUTY Ingestion Automated Regression Framework\n{'='*72}{CLR_RESET}")

    total_runs = passed_runs = failed_runs = 0

    for tc in TEST_CASES:
        pcap_path = os.path.join(DATA_DIR, tc['pcap'])
        
        print(f"\nEvaluating Dataset Target: {tc['label']}")
        print(f"File Location: {tc['pcap']} | Mode: {tc['runtime_mode'].upper()}")
        print(f"{'-'*60}")

        if not os.path.exists(pcap_path):
            print(f" {CLR_WARN}⊘ SKIP: Data file target missing on local disk path: {pcap_path}{CLR_RESET}")
            continue

        total_runs += 1

        try:
            old_data = run_old_reader(pcap_path, tc['runtime_mode'])
            
            print('----------------')
            
            new_data = run_new_reader(pcap_path, tc['runtime_mode'])
            
            selection = old_data.instrIDpkt == 72
            
            olddatatrimmed = old_lib.extractReoudoutSelection().extract(old_data,selection)
                       
            old_dataarray = olddatatrimmed.concatenateReadoutsInArrayForDebug()

            
            passed, issues = perform_deep_matrix_diff(olddatatrimmed, new_data, tc['runtime_mode'], verbose=args.verbose)
            
            if passed:
                passed_runs += 1
                print(f" {CLR_PASS}✓ PASS: Data matrix matches 1-1 across all rows and columns.{CLR_RESET}")
            else:
                failed_runs += 1
                print(f" {CLR_FAIL}✗ FAILURE: Discrepancy caught in parsed matrix entries:{CLR_RESET}")
                for issue in issues:
                    print(f"    ! {issue}")
                    
        except Exception as err:
            failed_runs += 1
            print(f" {CLR_FAIL}✗ CRITICAL EXCEPTION DURING VERIFICATION BLOCK:{CLR_RESET} {err}")
            traceback.print_exc()

    print(f"\n{CLR_INFO}{'='*72}\n Macro Evaluation Telemetry Summary\n{'='*72}{CLR_RESET}")
    print(f"  Total Files Verified : {total_runs}")
    print(f"  {CLR_PASS}Successful Matches   : {passed_runs}{CLR_RESET}")
    print(f"  {CLR_FAIL}Mismatched Anomalies : {failed_runs}{CLR_RESET}")
    
    return old_data, new_data 

if __name__ == '__main__':
    # main()
    
    old_data, new_data  = main()
    
    selection = old_data.instrIDpkt == 76
    
    olddatatrimmed = old_lib.extractReoudoutSelection().extract(old_data,selection)
               
    old_dataarray = olddatatrimmed.concatenateReadoutsInArrayForDebug()
    
    # aa = np.column_stack((new_data.matrix['channel'], old_dataarray[:, 4]))
    
    # bb = np.column_stack((new_data.matrix['timeStamp'],new_data.matrix['channel'], old_dataarray[:, 8],old_dataarray[:, 4]))
    
    # timediff = old2[:,8] - new_data.matrix['timeStamp']
    
    # new_dataarray = 
    

    aa = new_data.get_data_frame