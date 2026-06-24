#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST_hits_comparison.py

Compares hits output from the legacy libMapping pipeline against the new
mapping_engine pipeline for Multi-Blade (VMM normal) detector data.

Mirrors the structure of TEST.py (readouts comparison) but focuses on the
mapping phase: same readouts fed into both engines, hits arrays compared
field-by-field.

Run from repo root or any location where the path bootstrap finds the workspace.
"""

import numpy as np
import os
import sys
import time
import json

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

import pcapng as pg
from lib import libReadPcapng  as pcapr
from lib import libVMMcalibration as cal
from lib import libMapping_old  as maps       # legacy pipeline
from lib import libParameters   as para

from newLib import reader                     # new reader (produces readoutsVMMnormal)
from newLib.mapping_engine import MBMapper, MBClustMapper, MonitorMapper

# =============================================================================
# CONFIGURATION — edit these paths to match your environment
# =============================================================================
path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'

confPath = path + 'config/'
confPath_old = path + 'config_old/'
confFileName_old = 'AMOR.json'     # legacy config — fed to libMapping_old + libParameters
confFileName_new = 'AMOR.json'   # new-style config — fed to reader + mapping_engine

filePath = path + 'data/'
file     = 'ESSmask2023_1000pkts.pcapng'

calibPath = path + 'calib/'
calibFile = 'AMOR_calib_20231111002842.json'

filePathAndFileName = filePath + file
timeResolutionType  = 'coarse'

# =============================================================================
# TOLERANCE for numeric comparisons
# =============================================================================
ATOL = 0   # all fields are int64 — exact match expected

# =============================================================================
# HELPERS
# =============================================================================

def section(title: str):
    bar = '=' * 70
    print(f'\n{bar}')
    print(f'  {title}')
    print(bar)


def compare_arrays(name: str, old: np.ndarray, new: np.ndarray) -> bool:
    """
    Compare two int64 arrays element-wise and print a pass/fail summary.
    Returns True if they match.
    """
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


def compare_hits_MB_normal(old_hits, new_hits) -> bool:
    """
    Map legacy hits field names → new structured-array field names and compare.

    Legacy          New (hitsVMMnormal.matrix field)
    -------         --------------------------------
    timeStamp       timeStamp
    Cassette        ID
    WorS            plane
    WiresStrips     index      (global after mapChannelsGlob)
    ADC             adc
    PulseT          pulseT
    PrevPT          prevPT
    """
    section('Detector hits field-by-field comparison (MB normal)')

    m = new_hits.matrix   # structured array, already trimmed

    all_pass = True
    all_pass &= compare_arrays('timeStamp', old_hits.timeStamp,  m['timeStamp'])
    all_pass &= compare_arrays('ID/Cassette', old_hits.Cassette, m['ID'])
    all_pass &= compare_arrays('plane/WorS',  old_hits.WorS,     m['plane'])
    all_pass &= compare_arrays('index/WiresStrips', old_hits.WiresStrips, m['index'])
    all_pass &= compare_arrays('adc/ADC',     old_hits.ADC,      m['adc'])
    all_pass &= compare_arrays('pulseT/PulseT', old_hits.PulseT, m['pulseT'])
    all_pass &= compare_arrays('prevPT/PrevPT', old_hits.PrevPT, m['prevPT'])

    return all_pass


def compare_hits_MB_clustered(old_hits, new_hits) -> bool:
    """
    Clustered mode mapping.

    Legacy                  New (hitsVMMclustered.matrix field)
    ------                  -----------------------------------
    Cassette                ID
    timeStamp               timeStamp
    PulseT                  pulseT
    PrevPT                  prevPT
    WiresStrips             index0  (global wire coordinate)
    WiresStrips1            index1  (local strip coordinate)
    ADC                     adc0    (wire ADC)
    ADC1                    adc1    (strip ADC)
    mult0                   mult0
    mult1                   mult1

    NOTE: in clustered mode the legacy code only applies the global wire offset
    to WiresStrips (the wire coordinate), not to WiresStrips1 (strips). The new
    engine matches this behaviour: index0 is global, index1 is local.
    """
    section('Detector hits field-by-field comparison (MB clustered)')

    m = new_hits.matrix

    all_pass = True
    all_pass &= compare_arrays('timeStamp',  old_hits.timeStamp,   m['timeStamp'])
    all_pass &= compare_arrays('ID/Cassette', old_hits.Cassette,   m['ID'])
    all_pass &= compare_arrays('index0/WiresStrips', old_hits.WiresStrips, m['index0'])
    all_pass &= compare_arrays('index1/WiresStrips1', old_hits.WiresStrips1, m['index1'])
    all_pass &= compare_arrays('adc0/ADC',   old_hits.ADC,         m['adc0'])
    all_pass &= compare_arrays('adc1/ADC1',  old_hits.ADC1,        m['adc1'])
    all_pass &= compare_arrays('mult0',      old_hits.mult0,       m['mult0'])
    all_pass &= compare_arrays('mult1',      old_hits.mult1,       m['mult1'])
    all_pass &= compare_arrays('pulseT',     old_hits.PulseT,      m['pulseT'])
    all_pass &= compare_arrays('prevPT',     old_hits.PrevPT,      m['prevPT'])

    return all_pass


def compare_hits_monitor(old_mon_hits, new_mon_hits) -> bool:
    """
    Monitor hits comparison.

    Legacy                  New (hitsBM / hitsIBM .matrix field)
    ------                  ------------------------------------
    timeStamp               timeStamp
    Cassette (== MON ID)    ID
    ADC                     adc
    PulseT                  pulseT
    PrevPT                  prevPT

    NOTE: the legacy mapMonitor sets WorS, WiresStrips, WiresStrips1,
    ADC1, mult0, mult1 all to -1 for monitor rows — these have no
    equivalent in hitsBM/hitsIBM and are simply absent from the new
    container. That is correct and intentional.
    """
    section('Monitor hits field-by-field comparison')

    m = new_mon_hits.matrix

    all_pass = True
    all_pass &= compare_arrays('timeStamp',   old_mon_hits.timeStamp, m['timeStamp'])
    all_pass &= compare_arrays('ID/Cassette', old_mon_hits.Cassette,  m['ID'])
    all_pass &= compare_arrays('adc/ADC',     old_mon_hits.ADC,       m['adc'])
    all_pass &= compare_arrays('pulseT',      old_mon_hits.PulseT,    m['pulseT'])
    all_pass &= compare_arrays('prevPT',      old_mon_hits.PrevPT,    m['prevPT'])

    return all_pass


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':

    # -------------------------------------------------------------------------
    # Load JSON configs
    # -------------------------------------------------------------------------
    with open(confPath + confFileName_new, 'r') as ff:
        config_new = json.load(ff)
    # The old pipeline uses its own read_json_config wrapper.
    # AMOR26.json must be compatible with the old loader too; if it is not,
    # point confFileName_old at the legacy AMOR.json instead.
    config_old = maps.read_json_config(confPath_old + confFileName_old)
    parameters = para.parameters(confPath + confFileName_old)
    parameters.loadConfigAndUpdate(config_old)
    
    # -------------------------------------------------------------------------
    # NEW pipeline: read pcapng
    # -------------------------------------------------------------------------
    section('NEW pipeline: reading pcapng')
    t0 = time.time()

    parameters.VMMsettings.timeResolutionType = timeResolutionType
    parameters.fileManagement.calibFilePath   = calibPath
    parameters.fileManagement.calibFileName   = calibFile
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = True
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF  = False

    new_reader = reader.PcapngFileReader(
        file_path  = filePathAndFileName,
        parameters = parameters,
        config     = config_new,
    )
    new_reader.run()
    new_reader.readouts_vmm_normal.calibrate(parameters, config_new)

    print(f'  New reader done in {time.time() - t0:.2f}s')

    # -------------------------------------------------------------------------
    # OLD pipeline: read pcapng
    # -------------------------------------------------------------------------
    section('OLD pipeline: reading pcapng')
    t0 = time.time()

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

    print(f'  Old reader done in {time.time() - t0:.2f}s')

    # -------------------------------------------------------------------------
    # Row-count sanity check before mapping
    # -------------------------------------------------------------------------
    section('Row count sanity (readouts, pre-mapping)')

    n_old = len(old_readouts.timeStamp)
    n_new = new_reader.readouts_vmm_normal.fill_count
    if n_old == n_new:
        print(f'  [PASS]  Both pipelines have {n_old} readout rows')
    else:
        print(f'  [WARN]  Row count differs: old={n_old}  new={n_new}')
        print('  Hits comparison may fail or be misleading if row counts differ.')

    # -------------------------------------------------------------------------
    # NEW pipeline: map detector
    # -------------------------------------------------------------------------
    section('NEW pipeline: mapping detector')
    t0 = time.time()

    op_mode = config_new.get('operationMode', 'normal')
    if op_mode == 'clustered':
        new_hits = MBClustMapper.map(new_reader.readouts_vmm_normal, config_new)
    else:
        new_hits = MBMapper.map(new_reader.readouts_vmm_normal, config_new)

    new_mon_hits, new_mon_found = MonitorMapper.map(
        new_reader.readouts_bm, config_new
    )
    print(f'  New mapping done in {time.time() - t0:.2f}s')
    print(f'  new_hits rows         : {new_hits.fill_count}')
    print(f'  new_mon_hits rows     : {new_mon_hits.fill_count}  (found={new_mon_found})')

    # -------------------------------------------------------------------------
    # OLD pipeline: map detector
    # -------------------------------------------------------------------------
    section('OLD pipeline: mapping detector')
    t0 = time.time()

    md = maps.mapDetector(old_readouts, config_old)
    md.mappAllCassAndChannelsGlob()
    old_hits = md.hits

    old_mon = maps.mapMonitor(old_readouts, config_old)
    old_mon_found = old_mon.flagMONfound
    old_mon_hits  = old_mon.hits if old_mon_found else None

    print(f'  Old mapping done in {time.time() - t0:.2f}s')
    print(f'  old_hits rows         : {len(old_hits.timeStamp)}')
    if old_mon_found:
        print(f'  old_mon_hits rows     : {len(old_mon_hits.timeStamp)}  (found=True)')
    else:
        print(f'  old_mon_hits rows     : 0  (found=False)')

    # -------------------------------------------------------------------------
    # Compare detector hits
    # -------------------------------------------------------------------------
    if op_mode == 'clustered':
        det_pass = compare_hits_MB_clustered(old_hits, new_hits)
    else:
        det_pass = compare_hits_MB_normal(old_hits, new_hits)

    # -------------------------------------------------------------------------
    # Compare monitor hits
    # -------------------------------------------------------------------------
    section('Monitor found flags')
    if old_mon_found != new_mon_found:
        print(f'  [WARN]  Monitor found flag differs: old={old_mon_found}  new={new_mon_found}')
        mon_pass = False
    else:
        print(f'  [PASS]  Monitor found flag agrees: {new_mon_found}')
        mon_pass = True

    if old_mon_found and new_mon_found and old_mon_hits is not None:
        mon_pass &= compare_hits_monitor(old_mon_hits, new_mon_hits)
    elif not old_mon_found and not new_mon_found:
        section('Monitor hits comparison')
        print('  [SKIP]  No monitor data in file — nothing to compare')

    # -------------------------------------------------------------------------
    # Durations
    # -------------------------------------------------------------------------
    section('Durations comparison')
    if np.array_equal(old_hits.Durations, new_hits.durations):
        print(f'  [PASS]  durations match ({len(new_hits.durations)} entries)')
    else:
        print(f'  [FAIL]  durations mismatch')
        print(f'          old: {old_hits.Durations}')
        print(f'          new: {new_hits.durations}')

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    section('SUMMARY')
    status = 'ALL PASS' if (det_pass and mon_pass) else 'FAILURES DETECTED'
    print(f'  Detector hits : {"PASS" if det_pass else "FAIL"}')
    print(f'  Monitor hits  : {"PASS" if mon_pass else "FAIL"}')
    print(f'\n  >>> {status} <<<\n')

    # -------------------------------------------------------------------------
    # Quick-inspect DataFrames (useful in Spyder variable explorer)
    # -------------------------------------------------------------------------
    hitsArray_old = old_hits.concatenateHitsInArrayForDebug()
    hitsDF_new    = new_hits.get_data_frame()
