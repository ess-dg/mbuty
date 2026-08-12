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
        readouts/           (optional, if include_readouts=True)
            matrix          compound dataset
            fill_count      attr, int
            durations       dataset, int64
            instrumentIDs   dataset, int64 (sorted)
        hits/               (optional, if include_hits=True)
            matrix          compound dataset
            fill_count      attr, int
            durations       dataset, int64
            instrumentIDs   dataset, int64 (sorted)
    monitor/
        events/             ... same layout as detector/events, optional ...
        readouts/           (optional)
        hits/               (optional)
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
# generic container save / load (works for events, hits, readouts)
###############################################################################

def _save_container(grp, container_obj, compressionT, compressionL, has_stats=False):
    """Save one container (events, hits, or readouts): matrix (all fields, trimmed 
    to fill_count), fill_count, durations, and instrumentIDs.
    """
    n = getattr(container_obj, 'fill_count', len(container_obj.matrix))
    matrix = container_obj.matrix[:n]

    if matrix.size > 0:
        grp.create_dataset('matrix', data=matrix, shuffle=True, compression=compressionT, 
                          compression_opts=compressionL)
    else:
        grp.create_dataset('matrix', data=matrix)

    grp.attrs['fill_count'] = n

    durations = getattr(container_obj, 'durations', None)
    if durations is not None and len(durations) > 0:
        grp.create_dataset('durations', data=durations)

    instrumentIDs = getattr(container_obj, 'instrumentIDs', None)
    if instrumentIDs is not None:
        ids = np.array(sorted(instrumentIDs), dtype='int64') if len(instrumentIDs) else np.zeros(0, dtype='int64')
        grp.create_dataset('instrumentIDs', data=ids)

    # Only events have stats
    if has_stats:
        stats = getattr(container_obj, 'stats', None)
        if stats:
            statsGrp = grp.create_group('stats')
            for key, value in stats.items():
                statsGrp.attrs[key] = value


def _load_container(grp, container_class):
    """Load one container group back into a container instance."""
    obj = container_class()
    obj.matrix = grp['matrix'][()]
    obj.fill_count = int(grp.attrs.get('fill_count', len(obj.matrix)))

    if 'durations' in grp:
        obj.durations = grp['durations'][()]

    if 'instrumentIDs' in grp:
        obj.instrumentIDs = set(grp['instrumentIDs'][()].tolist())

    if 'stats' in grp:
        obj.stats = dict(grp['stats'].attrs)

    return obj


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


class ReducedReadouts():
    """Read-only container for readouts loaded back from a reduced file."""

    def __init__(self):
        self.matrix = np.zeros(0)
        self.fill_count = 0
        self.durations = np.zeros(0, dtype='int64')
        self.instrumentIDs = set()

    def get_data_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.matrix)

    def __repr__(self):
        fields = list(self.matrix.dtype.names) if self.matrix.dtype.names else []
        return f"<ReducedReadouts fill_count={self.fill_count} fields={fields}>"


class ReducedHits():
    """Read-only container for hits loaded back from a reduced file."""

    def __init__(self):
        self.matrix = np.zeros(0)
        self.fill_count = 0
        self.durations = np.zeros(0, dtype='int64')
        self.instrumentIDs = set()

    def get_data_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.matrix)

    def __repr__(self):
        fields = list(self.matrix.dtype.names) if self.matrix.dtype.names else []
        return f"<ReducedHits fill_count={self.fill_count} fields={fields}>"


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

def saveReducedDataToHDF(parameters, events, eventsMON=None, readouts=None, 
                         readoutsMON=None, hits=None,
                         include_readouts=False, include_hits=False,
                         saveReducedPath='./', fileName='temp'):
    """Create/overwrite a reduced-data HDF5 file and save detector [+ monitor] 
    events, and optionally detector readouts and hits.
    
    Monitor has events and readouts only; no monitor hits.
    
    Parameters
    ----------
    parameters : object
        Parameters object with fileManagement settings
    events : container object
        Detector events (always saved)
    eventsMON : container object, optional
        Monitor events
    readouts : container object, optional
        Detector readouts (saved only if include_readouts=True)
    readoutsMON : container object, optional
        Monitor readouts (saved only if include_readouts=True)
    hits : container object, optional
        Detector hits (saved only if include_hits=True). Monitor does not have hits.
    include_readouts : bool, default False
        If True, save detector and monitor readouts matrices
    include_hits : bool, default False
        If True, save detector hits matrix (monitor does not have hits)
    saveReducedPath : str, default './'
        Path where to save the HDF5 file
    fileName : str, default 'temp'
        Base name of the file (without extension)
    
    Returns
    -------
    str
        Path to the created HDF5 file
    """

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

    # Always save events
    _save_container(gdet, events, compressionHDFT, compressionHDFL, has_stats=True)
    if eventsMON is not None:
        _save_container(gmon, eventsMON, compressionHDFT, compressionHDFL, has_stats=True)

    # Optionally save readouts
    if include_readouts and readouts is not None:
        gdet_readouts = fid.create_group(mainFolder + '/detector/readouts')
        _save_container(gdet_readouts, readouts, compressionHDFT, compressionHDFL)
        
        if readoutsMON is not None:
            gmon_readouts = fid.create_group(mainFolder + '/monitor/readouts')
            _save_container(gmon_readouts, readoutsMON, compressionHDFT, compressionHDFL)

    # Optionally save hits (detector only, monitor does not have hits)
    if include_hits and hits is not None:
        gdet_hits = fid.create_group(mainFolder + '/detector/hits')
        _save_container(gdet_hits, hits, compressionHDFT, compressionHDFL)

    _save_parameters(gparam, parameters)

    print(f"{OK}-> reduced data saved to: {outfile}{RESET}")

    fid.close()

    return outfile


###############################################################################
###############################################################################

def readReducedDataFromHDF(pathAndFileName, showTree=False):
    """Read back a reduced-data HDF5 file written by saveReducedDataToHDF.
    Loads whatever is available in the file. Returns None for missing containers.
    
    Parameters
    ----------
    pathAndFileName : str
        Path to the HDF5 file
    showTree : bool, default False
        If True, print the file structure
    
    Returns
    -------
    dict
        Dictionary with keys: 'detector_events', 'monitor_events', 'detector_readouts', 
        'monitor_readouts', 'detector_hits', 'parameters'.
        Monitor does not have hits. Values are None if not present in the file.
    """

    detector_events   = None
    monitor_events    = None
    detector_readouts = None
    monitor_readouts  = None
    detector_hits     = None
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

    # Load detector events (always)
    if 'detector' in main and 'events' in main['detector'] and 'matrix' in main['detector']['events']:
        detector_events = _load_container(main['detector']['events'], ReducedEvents)

    # Load monitor events (if present)
    if 'monitor' in main and 'events' in main['monitor'] and 'matrix' in main['monitor']['events']:
        monitor_events = _load_container(main['monitor']['events'], ReducedEvents)

    # Load detector readouts (if present)
    if 'detector' in main and 'readouts' in main['detector'] and 'matrix' in main['detector']['readouts']:
        detector_readouts = _load_container(main['detector']['readouts'], ReducedReadouts)

    # Load monitor readouts (if present)
    if 'monitor' in main and 'readouts' in main['monitor'] and 'matrix' in main['monitor']['readouts']:
        monitor_readouts = _load_container(main['monitor']['readouts'], ReducedReadouts)

    # Load detector hits (if present) — monitor does not have hits
    if 'detector' in main and 'hits' in main['detector'] and 'matrix' in main['detector']['hits']:
        detector_hits = _load_container(main['detector']['hits'], ReducedHits)

    # Load parameters
    if 'parameters' in main:
        parameters = _load_parameters(main['parameters'])

    fid.close()

    return {
        'detector_events': detector_events,
        'monitor_events': monitor_events,
        'detector_readouts': detector_readouts,
        'monitor_readouts': monitor_readouts,
        'detector_hits': detector_hits,
        'parameters': parameters,
    }


###############################################################################
###############################################################################

if __name__ == '__main__':

    # Quick end-to-end test: build a small synthetic detector + monitor
    # events/readouts/hits objects with the real containers, save them, read them back,
    # and check that everything survived the round trip.

    import numpy as np

    try:
        from lib.container_events import eventsVMMnormal, eventsBM
        from lib.container_readouts import readoutsVMM
        from lib.container_hits import hitsVMMnormal
        from lib.parameters import parameters
    except ImportError:
        from container_events import eventsVMMnormal, eventsBM
        from container_readouts import readoutsVMM
        from container_hits import hitsVMMnormal
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

    # --- build synthetic detector readouts ----------------------------------
    nRO = 100
    ro = readoutsVMM(nRO)
    ro.fill_count = nRO
    ro.matrix['ring'] = np.random.randint(0, 3, nRO)
    ro.matrix['fen'] = np.random.randint(0, 2, nRO)
    ro.matrix['hybrid'] = np.random.randint(0, 4, nRO)
    ro.matrix['geo'] = np.random.randint(0, 10, nRO)
    ro.matrix['g0'] = np.random.randint(0, 3, nRO)
    ro.matrix['ch'] = np.random.randint(0, 512, nRO)
    ro.matrix['timeStamp'] = np.sort(np.random.randint(0, 1_000_000, nRO))
    ro.matrix['pulseT'] = np.zeros(nRO, dtype='int64')
    ro.matrix['prevPT'] = np.zeros(nRO, dtype='int64')
    ro.matrix['instrID'] = np.ones(nRO, dtype='int64')
    ro.instrumentIDs = {1}

    # --- build synthetic detector hits --------------------------------------
    nHits = 15
    h = hitsVMMnormal(nHits)
    h.fill_count = nHits
    h.matrix['ID'] = np.arange(nHits, dtype='int64')
    h.matrix['plane'] = np.random.randint(0, 2, nHits)
    h.matrix['index'] = np.random.randint(0, 256, nHits)
    h.matrix['adc'] = np.random.randint(100, 3000, nHits)
    h.matrix['timeStamp'] = np.sort(np.random.randint(0, 1_000_000, nHits))
    h.matrix['pulseT'] = np.zeros(nHits, dtype='int64')
    h.matrix['prevPT'] = np.zeros(nHits, dtype='int64')
    h.instrumentIDs = {1, 2}

    # --- parameters -----------------------------------------------------------
    pars = parameters()
    pars.acqMode = 'pcap-local'
    pars.dataReduction.calibrateVMM_ADC_ONOFF = True
    pars.dataReduction.softThresholdType = 'fromFile'
    pars.fileManagement.fileName = ['freiatest_00000.pcapng']

    # --- save with all options -----------------------------------------------
    print("\n=== SAVING WITH ALL OPTIONS ===")
    outfile = saveReducedDataToHDF(pars, ev, mon, readouts=ro, readoutsMON=None, 
                                    hits=h,
                                    include_readouts=True, include_hits=True,
                                    saveReducedPath=testPath, fileName=testName)

    # --- read back all ----------------------------------------------------------
    print("\n=== LOADING ===")
    result = readReducedDataFromHDF(outfile, showTree=True)
    
    detector = result['detector_events']
    monitor = result['monitor_events']
    detector_ro = result['detector_readouts']
    detector_h = result['detector_hits']
    parameters = result['parameters']

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

    if detector_ro is None or detector_ro.fill_count != ro.fill_count:
        print('FAIL: detector readouts did not round-trip correctly')
        ok = False

    if detector_h is None or detector_h.fill_count != h.fill_count:
        print('FAIL: detector hits did not round-trip correctly')
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

    print('\ndetector events:', detector)
    print('monitor events: ', monitor)
    print('detector readouts:', detector_ro)
    print('detector hits:', detector_h)
    print('\nsample of detector events data:')
    print(detector.get_data_frame().head())
    print('\nsample of detector readouts data:')
    if detector_ro:
        print(detector_ro.get_data_frame().head())
    print('\nsample of detector hits data:')
    if detector_h:
        print(detector_h.get_data_frame().head())