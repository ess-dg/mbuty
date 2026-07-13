#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
libReducedFileH5.py

Save/read the "reduced data" HDF5 file produced after clustering.

-------------------------------------------------------------------------
FILE LAYOUT
-------------------------------------------------------------------------
<mainFolder>/                  (e.g. 'entry1')
    detector/
        events/
            matrix          compound dataset, one row per event (ALL fields,
                             sliced to fill_count)
            fill_count      attr, int
            durations       dataset, int64
            instrumentIDs   dataset, int64 (sorted)
            stats/          group, attrs = clustering diagnostics (if any)
    monitor/
        events/             ... same layout as detector/events, optional ...
    parameters/
        <settingsName>/     attrs -- one group per parameters sub-object
                             (fileManagement, dataReduction, clockTicks,
                             wavelength, MONitor, plotting, ...), every
                             attribute of that object saved automatically
        acqMode             attr directly on parameters/ (it's a plain scalar,
                             not a sub-object)

"""

import os
import re
import sys
import time
import h5py
import numpy as np
import pandas as pd

_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from lib.colors import INFO, OK, WARN, ERR, RESET



###############################################################################

def prepareReducedFileBaseName(fileNameList):
    """Build the reduced-file base name from the list of raw file names loaded."""

    if len(fileNameList) == 1:
        base_name, extension = os.path.splitext(fileNameList[0])
        fileNameSave = "_".join([base_name, 'reduced'])

    elif len(fileNameList) > 1:
        base_name, extension = os.path.splitext(fileNameList[0])
        matched = re.search(r"(_\d+)$", base_name)

        if matched:
            try:
                prefix = base_name[:matched.start()]
                suffix = matched.group(0)
                base_name2, extension2 = os.path.splitext(fileNameList[-1])
                matched2 = re.search(r"(_\d+)$", base_name2)
                suffix2 = matched2.group(0)
                fileNameSave = "_".join([prefix, 'from' + suffix, 'to' + suffix2, 'reduced'])
            except Exception:
                nfiles = len(fileNameList)
                fileNameSave = "_".join([base_name, str(nfiles), 'files_reduced'])
        else:
            print(f"\n{WARN} --> WARNING: file name list does not match format goofy_XXXXX.pcapng "
                  "-> associated first file name for data reduction.{RESET}")
            nfiles = len(fileNameList)
            fileNameSave = "_".join([base_name, str(nfiles), 'files_reduced'])
    else:
        fileNameSave = None
        print(f"\n{WARN} --> WARNING: empty file name list!!!{RESET}")

    return fileNameSave


###############################################################################
# events save / load
###############################################################################

def _save_events(grp, events_obj, compressionT, compressionL):
    """Save one events container: matrix (all fields, trimmed to fill_count),
    fill_count, durations, instrumentIDs, and stats (if the object has them)."""

    n = getattr(events_obj, 'fill_count', len(events_obj.matrix))
    matrix = events_obj.matrix[:n]

    # fieldnames = list(matrix.dtype.names or [])
    # print(f"\t --> saving matrix: {n} rows, {len(fieldnames)} fields -> {fieldnames}")

    if matrix.size > 0:
        grp.create_dataset('matrix', data=matrix, shuffle=True, compression=compressionT, compression_opts=compressionL)
    else:
        grp.create_dataset('matrix', data=matrix)

    grp.attrs['fill_count'] = n

    durations = getattr(events_obj, 'durations', None)
    if durations is not None:
        grp.create_dataset('durations', data=durations)

    instrumentIDs = getattr(events_obj, 'instrumentIDs', None)
    if instrumentIDs is not None:
        ids = np.array(sorted(instrumentIDs), dtype='int64') if len(instrumentIDs) else np.zeros(0, dtype='int64')
        grp.create_dataset('instrumentIDs', data=ids)

    stats = getattr(events_obj, 'stats', None)
    if stats:
        statsGrp = grp.create_group('stats')
        for key, value in stats.items():
            statsGrp.attrs[key] = value


def _load_events(grp):
    """Load one events group back into a simple ReducedEvents container."""

    ev = ReducedEvents()
    ev.matrix = grp['matrix'][()]
    ev.fill_count = int(grp.attrs.get('fill_count', len(ev.matrix)))

    if 'durations' in grp:
        ev.durations = grp['durations'][()]

    if 'instrumentIDs' in grp:
        ev.instrumentIDs = set(grp['instrumentIDs'][()].tolist())

    if 'stats' in grp:
        ev.stats = dict(grp['stats'].attrs)

    return ev


class ReducedEvents():
    """Read-only container for events loaded back from a reduced file.
    Same attribute names as the real containers (matrix, fill_count,
    durations, instrumentIDs, stats), no clustering logic attached."""

    def __init__(self):
        self.matrix = np.zeros(0)
        self.fill_count = 0
        self.durations = np.zeros(0, dtype='int64')
        self.instrumentIDs = set()
        self.stats = {}

    def get_data_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.matrix)

    def __repr__(self):
        fields = list(self.matrix.dtype.names) if self.matrix.dtype.names else []
        return f"<ReducedEvents fill_count={self.fill_count} fields={fields}>"


###############################################################################
# parameters save / load
###############################################################################


def _save_parameters(grp, parameters):
    """
    Save the entire parameters tree: one HDF5 group per sub-settings object
    (fileManagement, dataReduction, clockTicks, wavelength, MONitor, ...),
    every attribute of that object stored directly as an attr. Top-level
    scalars (like acqMode) go straight onto the parameters group itself.

    No manual field list to maintain -- if a new settings field gets added
    anywhere in parameters.py, it's saved automatically.
    """

    for key, value in vars(parameters).items():

        if hasattr(value, '__dict__'):
            subgrp = grp.create_group(key)
            for k2, v2 in vars(value).items():
                if k2.startswith('__') or callable(v2):
                    continue
                subgrp.attrs[k2] = 'None' if v2 is None else v2
        else:
            grp.attrs[key] = 'None' if value is None else value


def _load_parameters(grp):
    """Inverse of _save_parameters: one dict per sub-settings group, plus
    top-level scalars, straight from attrs."""

    out = dict(grp.attrs)
    for groupName in grp.keys():
        out[groupName] = dict(grp[groupName].attrs)
    return out


###############################################################################
###############################################################################

def saveReducedDataToHDF(parameters, events, eventsMON=None, saveReducedPath='./', fileName='temp'):
    """Create/overwrite a reduced-data HDF5 file and save detector [+ monitor] events."""

    compressionHDFT = parameters.fileManagement.reducedCompressionHDFT
    compressionHDFL = parameters.fileManagement.reducedCompressionHDFL

    if not os.path.exists(saveReducedPath):
        print(f"{WARN}\n --> WARNING: folder '{saveReducedPath}' does not exist, creating it.{RESET}")
        os.makedirs(saveReducedPath, exist_ok=True)

    outfile = os.path.join(saveReducedPath, fileName + '.h5')

    if os.path.exists(outfile):
        print(f"{WARN}WARNING: reduced data file exists, it will be overwritten!{RESET}")
        os.remove(outfile)

    mainFolder = parameters.fileManagement.reducedNameMainFolder

    fid = h5py.File(outfile, 'w')
    fid.attrs['created'] = time.strftime('%Y-%m-%d %H:%M:%S')

    gdet   = fid.create_group(mainFolder + '/detector/events')
    gmon   = fid.create_group(mainFolder + '/monitor/events')
    gparam = fid.create_group(mainFolder + '/parameters')

    print(f"{OK}-> saving reduced data to h5 file ... {RESET}")

    _save_events(gdet, events, compressionHDFT, compressionHDFL)

    if eventsMON is not None:
        _save_events(gmon, eventsMON, compressionHDFT, compressionHDFL)

    _save_parameters(gparam, parameters)

    print(f"{OK}-> reduced data saved to: {outfile}{RESET}")

    fid.close()

    return outfile


###############################################################################
###############################################################################

def readReducedDataFromHDF(pathAndFileName, showTree=False):
    """Read back a reduced-data HDF5 file written by saveReducedDataToHDF.
    Returns (detector, monitor, parameters)."""

    detector   = None
    monitor    = None
    parameters = {}

    if not os.path.exists(pathAndFileName):
        print(f"{ERR} ---> File DOES NOT EXIST: {pathAndFileName}{RESET}")
        time.sleep(2)
        sys.exit()

    fid = h5py.File(pathAndFileName, 'r')

    mainFolder = list(fid.keys())[0]
    main = fid[mainFolder]

    if showTree:
        print(mainFolder)
        for key in main.keys():
            print('  ', key)

    detGrp = main['detector']['events'] if 'detector' in main and 'events' in main['detector'] else None
    if detGrp is not None and 'matrix' in detGrp:
        detector = _load_events(detGrp)

    monGrp = main['monitor']['events'] if 'monitor' in main and 'events' in main['monitor'] else None
    if monGrp is not None and 'matrix' in monGrp:
        monitor = _load_events(monGrp)

    if 'parameters' in main:
        parameters = _load_parameters(main['parameters'])

    fid.close()

    return detector, monitor, parameters


###############################################################################
###############################################################################

if __name__ == '__main__':

    # Quick end-to-end test: build a small synthetic detector + monitor
    # events object with the real containers, save them, read them back,
    # and check that everything survived the round trip.

    import numpy as np

    try:
        from lib.container_events import eventsVMMnormal, eventsBM
        from lib.parameters import parameters
    except ImportError:
        from container_events import eventsVMMnormal, eventsBM
        from parameters import parameters

    testPath = '/tmp/libReducedFileH5_test/'
    testName = 'test'

    # --- build synthetic detector events -----------------------------------
    n = 20
    ev = eventsVMMnormal(n)
    computed = {
        'ID':              np.random.randint(0, 6, n),
        'coordinate0':     np.random.rand(n) * 32,
        'coordinate1':     np.random.rand(n) * 32,
        'pulseHeight0':    np.random.randint(0, 4000, n),
        'pulseHeight1':    np.random.randint(0, 4000, n),
        'mult0':           np.random.randint(1, 4, n),
        'mult1':           np.random.randint(1, 4, n),
        'absCoordinate2':  np.zeros(n),
        'clusterTimeSpan': np.random.randint(0, 1000, n),
    }
    timing = {
        'timeStamp': np.sort(np.random.randint(0, 1_000_000, n)),
        'pulseT':    np.zeros(n, dtype='int64'),
        'prevPT':    np.zeros(n, dtype='int64'),
    }
    ev.absorb(computed, timing)
    ev.instrumentIDs = {1, 2, 3}

    # --- build synthetic monitor events --------------------------------------
    nMON = 6
    mon = eventsBM(nMON)
    mon.absorb(
        {'ID': np.zeros(nMON, dtype='int64'), 'type': np.zeros(nMON, dtype='int64')},
        {'timeStamp': np.sort(np.random.randint(0, 1_000_000, nMON)),
         'pulseT':    np.zeros(nMON, dtype='int64'),
         'prevPT':    np.zeros(nMON, dtype='int64')},
    )

    # --- parameters -----------------------------------------------------------
    pars = parameters()
    pars.acqMode = 'pcap-local'
    pars.dataReduction.calibrateVMM_ADC_ONOFF = True
    pars.dataReduction.softThresholdType = 'fromFile'
    pars.fileManagement.fileName = ['freiatest_00000.pcapng']

    # --- save -------------------------------------------------------------
    outfile = saveReducedDataToHDF(pars, ev, mon, saveReducedPath=testPath, fileName=testName)

    # --- read back ----------------------------------------------------------
    detector, monitor, parameters = readReducedDataFromHDF(outfile, showTree=True)

    print('\n--- checks ---')

    ok = True

    if detector.fill_count != ev.fill_count:
        print(f'FAIL: detector fill_count {detector.fill_count} != {ev.fill_count}')
        ok = False

    if set(detector.matrix.dtype.names) != set(ev.matrix.dtype.names):
        print('FAIL: detector fields do not match')
        ok = False
    elif not np.array_equal(detector.matrix, ev.matrix[:ev.fill_count]):
        print('FAIL: detector matrix values do not match')
        ok = False

    if detector.instrumentIDs != ev.instrumentIDs:
        print(f'FAIL: instrumentIDs {detector.instrumentIDs} != {ev.instrumentIDs}')
        ok = False

    if monitor is None or monitor.fill_count != mon.fill_count:
        print('FAIL: monitor did not round-trip correctly')
        ok = False

    if parameters['acqMode'] != 'pcap-local':
        print(f"FAIL: acqMode {parameters['acqMode']} != 'pcap-local'")
        ok = False

    if bool(parameters['dataReduction']['calibrateVMM_ADC_ONOFF']) is not True:
        print('FAIL: calibrateVMM_ADC_ONOFF did not round-trip correctly')
        ok = False

    if 'plotting' not in parameters:
        print('FAIL: plotting group missing (full parameters tree not saved)')
        ok = False

    print('ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED')

    print('\ndetector:', detector)
    print('monitor: ', monitor)
    print('\nsample of detector data:')
    print(detector.get_data_frame().head())