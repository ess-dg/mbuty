#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST_clustering_engine.py
Compares the output of the legacy clustering logic against the modernized 
vectorized ClusteringEngine using identical pcapng raw data streams.
"""

import numpy as np
import os
import sys
import json
import time

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib import libReadPcapng as pcapr
from lib import libVMMcalibration as cal
from lib import libMapping_old as maps
from lib import libParameters as para
from lib import libCluster as legacy_engine

from newLib import reader
from newLib.mapping_engine import MBMapper
from newLib.clustering_engine import VMMNormalClusterer

# =============================================================================
# CONFIGURATION — Matches your environment setup
# =============================================================================
path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'

confPath = path + 'config/'
confPath_old = path + 'config_old/'
confFileName_old = 'AMOR.json'
confFileName_new = 'AMOR.json'

filePath = path + 'data/'
file     = 'ESSmask2023_1000pkts.pcapng'

calibPath = path + 'calib/'
calibFile = 'AMOR_calib_20231111002842.json'

filePathAndFileName = filePath + file
timeResolutionType  = 'coarse'
time_window_seconds = 2e-6  # 2000 ns

def section(title: str):
    bar = '=' * 70
    print(f'\n{bar}')
    print(f'  {title}')
    print(bar)

def compare_arrays(name: str, old: np.ndarray, new: np.ndarray) -> bool:
    """Compare two numeric arrays element-wise and print summary."""
    if old.shape != new.shape:
        print(f'  [FAIL]  {name}: shape mismatch — old {old.shape} vs new {new.shape}')
        return False
    if not np.array_equal(old, new):
        diffs = np.where(old != new)[0]
        print(f'  [FAIL]  {name}: {len(diffs)} mismatches '
              f'(first at index {diffs[0]}: old={old[diffs[0]]} new={new[diffs[0]]})')
        return False
    print(f'  [PASS]  {name}: {len(old)} rows match exactly')
    return True

# =============================================================================
# MAIN PIPELINE COMPARISON
# =============================================================================
if __name__ == '__main__':

    # -------------------------------------------------------------------------
    # Load parameters and configs
    # -------------------------------------------------------------------------
    with open(confPath + confFileName_new, 'r') as ff:
        config_new = json.load(ff)

    config_old = maps.read_json_config(confPath_old + confFileName_old)
    parameters = para.parameters(confPath + confFileName_old)
    parameters.loadConfigAndUpdate(config_old)

    # Force identical sorting options upfront
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = False
    parameters.VMMsettings.timeResolutionType = timeResolutionType
    parameters.fileManagement.calibFilePath   = calibPath
    parameters.fileManagement.calibFileName   = calibFile
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = True

    # -------------------------------------------------------------------------
    # Run New Pipeline Up to Hits
    # -------------------------------------------------------------------------
    new_reader = reader.PcapngFileReader(filePathAndFileName, parameters, config_new)
    new_reader.run()
    new_reader.readouts_vmm_normal.calibrate(parameters, config_new)
    new_hits = MBMapper.map(new_reader.readouts_vmm_normal, config_new)

    # -------------------------------------------------------------------------
    # Run Old Pipeline Up to Hits
    # -------------------------------------------------------------------------
    pcap = pcapr.pcapng_reader(
        filePathAndFileName,
        NSperClockTick        = 11.356860963629653,
        MONhw                 = config_old.MONmap.hardwareType,
        MONconn               = config_old.MONmap.connectionType,
        MONring               = 11,
        timeResolutionType    = timeResolutionType,
        sortByTimeStampsONOFF = False,
        operationMode         = config_old.DETparameters.operationMode,
        pcapLoadingMethod     = 'allocate',
    )
    old_readouts = pcap.readouts
    calib = cal.read_json_calib(calibPath + calibFile, config_old)
    if calib.calibFlag:
        ca = cal.calibrate(old_readouts, config_old, calib)
        ca.calibrateADC()

    md = maps.mapDetector(old_readouts, config_old)
    md.mappAllCassAndChannelsGlob()
    old_hits = md.hits

    # -------------------------------------------------------------------------
    # Pre-Clustering Diagnostics Pass
    # -------------------------------------------------------------------------
    section('PRE-CLUSTERING HITS INPUT COUNT CHECK')
    print(f'  Legacy Input Hits Matrix Size : {len(old_hits.timeStamp)}')
    print(f'  Modern Input Hits Matrix Size : {new_hits.fill_count}')
    if len(old_hits.timeStamp) != new_hits.fill_count:
        print('  [WARN] Incoming hits row counts differ BEFORE clustering begins!')

    # -------------------------------------------------------------------------
    # Run Legacy Iterative Loop Clustering
    # -------------------------------------------------------------------------
    section('Running Legacy Iterative Loop Clustering')
    t0 = time.time()
    cassettes_in_data = config_old.DETparameters.cassInConfig
    legacy_clust = legacy_engine.clusterHits(old_hits, showStat='globalStat')
    legacy_clust.clusterizeManyCassettes(cassettes_in_data, time_window_seconds, detType='MB')
    legacy_ev = legacy_clust.events
    print(f'  Legacy clustering done in {time.time() - t0:.2f}s')

    # -------------------------------------------------------------------------
    # Run New Modernized Vectorized Clustering
    # -------------------------------------------------------------------------
    section('Running New Vectorized Clustering Engine')
    t0 = time.time()
    new_ev = VMMNormalClusterer.cluster(new_hits, config=config_new, time_window_s=time_window_seconds)
    print(f'  Vectorized clustering done in {time.time() - t0:.2f}s')

    # -------------------------------------------------------------------------
    # Field-by-Field Matrix Evaluation
    # -------------------------------------------------------------------------
    section('Evaluating Reconstructed Event Correctness')

    print(f'  Legacy Reconstructed Rows : {len(legacy_ev.timeStamp)}')
    print(f'  New Vectorized Rows        : {new_ev.fill_count}')

    if len(legacy_ev.timeStamp) == new_ev.fill_count:
        all_pass = True
        all_pass &= compare_arrays('ID/Cassette',    legacy_ev.Cassette,  new_ev.matrix['ID'])
        all_pass &= compare_arrays('timeStamp',      legacy_ev.timeStamp, new_ev.matrix['timeStamp'])
        all_pass &= compare_arrays('coordinate0/W',  legacy_ev.positionW, new_ev.matrix['coordinate0'])
        all_pass &= compare_arrays('coordinate1/S',  legacy_ev.positionS, new_ev.matrix['coordinate1'])
        all_pass &= compare_arrays('pulseHeight0/W', legacy_ev.PHW,       new_ev.matrix['pulseHeight0'])
        all_pass &= compare_arrays('pulseHeight1/S', legacy_ev.PHS,       new_ev.matrix['pulseHeight1'])
        all_pass &= compare_arrays('mult0/Wires',    legacy_ev.multW,     new_ev.matrix['mult0'])
        all_pass &= compare_arrays('mult1/Strips',   legacy_ev.multS,     new_ev.matrix['mult1'])
        
        section('SUMMARY')
        print(f'  Clustering Engine Validation: {"SUCCESS (ALL PASS)" if all_pass else "FAILURE"}')
    else:
        section('SUMMARY')
        print('  [FAIL] Matrix shapes mismatch. Cannot evaluate arrays element-wise.')