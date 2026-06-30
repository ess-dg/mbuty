#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST_plotting_pipeline.py

Runs the modernized vectorized pipeline end-to-end (reader -> mapping ->
hits -> clustering -> events) on a real pcapng file, then exercises every
plot method in newLib.plotting / newLib.histograms to visually confirm the
new plotting layer renders correctly against real data.

This does NOT compare against the legacy engine -- that was already
validated field-by-field in TEST_clustering_engine.py. This script is purely
a "does it run and does it look right" pass over the plotting stage.

Scope note: only readouts -> hits -> events (clustering output) is run here.
The abs-units stage (wavelength, absCoordinate0/1, positionWmm/Smm) has not
been rewritten yet, so wavelength- and mm-axis-dependent plots are skipped
rather than plotted against all-zero data. ToF IS populated here via
events.compute_and_filter_tof(), since that method already exists on the
base events class.
"""

import os
import sys
import json
import time

import matplotlib.pyplot as plt

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib import libMapping_old as maps
from lib import libParameters as para

from newLib import reader
from newLib.mapping_engine import MBMapper
from newLib.clustering_engine import VMMNormalClusterer
from newLib.histograms import VMMAxisSet
from newLib.plotting import (
    VMMReadoutsPlotter,
    BaseReadoutsPlotter,
    VMMHitsPlotter,
    VMMEventsPlotter,
)

# =============================================================================
# CONFIGURATION — same environment as TEST_clustering_engine.py
# =============================================================================
path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'

confPath          = path + 'config/'
confPath_old      = path + 'config_old/'
confFileName_old  = 'AMOR.json'
confFileName_new  = 'AMOR.json'

filePath = path + 'data/'
file     = 'ESSmask2023_1000pkts.pcapng'

calibPath = path + 'calib/'
calibFile = 'AMOR_calib_20231111002842.json'

filePathAndFileName = filePath + file
timeResolutionType  = 'coarse'
time_window_seconds = 2e-6  # 2000 ns

SAVE_FIGURES = True
SHOW_FIGURES = True
OUTPUT_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plot_test_output')


def section(title: str):
    bar = '=' * 70
    print(f'\n{bar}')
    print(f'  {title}')
    print(bar)


def save_all_open_figures(out_dir: str, prefix: str = ''):
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        title = fig._suptitle.get_text() if fig._suptitle else f'fig{num}'
        safe_title = ''.join(c if c.isalnum() else '_' for c in title)
        fname = os.path.join(out_dir, f'{prefix}{num:04d}_{safe_title}.png')
        fig.savefig(fname, dpi=120, bbox_inches='tight')
        saved.append(fname)
    return saved


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':

    # -------------------------------------------------------------------------
    # Load parameters and configs
    # -------------------------------------------------------------------------
    section('LOADING CONFIG / PARAMETERS')

    with open(confPath + confFileName_new, 'r') as ff:
        config_new = json.load(ff)

    config_old = maps.read_json_config(confPath_old + confFileName_old)
    parameters = para.parameters(confPath + confFileName_old)
    parameters.loadConfigAndUpdate(config_old)

    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = False
    parameters.VMMsettings.timeResolutionType       = timeResolutionType
    parameters.fileManagement.calibFilePath         = calibPath
    parameters.fileManagement.calibFileName         = calibFile
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = True

    print(f'  Config + parameters loaded OK')

    # -------------------------------------------------------------------------
    # Run the modernized pipeline: readouts -> calibrate -> hits -> events
    # -------------------------------------------------------------------------
    section('RUNNING MODERN PIPELINE (reader -> mapping -> clustering)')

    t0 = time.time()
    new_reader = reader.PcapngFileReader(filePathAndFileName, parameters, config_new)
    new_reader.run()
    new_reader.readouts_vmm_normal.calibrate(parameters, config_new)
    print(f'  Readouts ready  : {new_reader.readouts_vmm_normal.fill_count} rows')

    new_hits = MBMapper.map(new_reader.readouts_vmm_normal, config_new)
    print(f'  Hits mapped     : {new_hits.fill_count} rows')

    new_ev = VMMNormalClusterer.cluster(new_hits, config=config_new, time_window_s=time_window_seconds)
    print(f'  Events clustered: {new_ev.fill_count} rows')
    print(f'  Pipeline done in {time.time() - t0:.2f}s')

    # Populate ToF -- already implemented on the base events class.
    new_ev.compute_and_filter_tof()

    # -------------------------------------------------------------------------
    # Build the shared axis set for histogramming / plotting
    # -------------------------------------------------------------------------
    section('BUILDING AXIS SET')
    axis_set = VMMAxisSet(parameters)
    print(f'  ax_wires steps={axis_set.ax_wires.steps}, ax_strips steps={axis_set.ax_strips.steps}, '
          f'ax_tof steps={axis_set.ax_tof.steps}')

    # -------------------------------------------------------------------------
    # READOUTS plots
    # -------------------------------------------------------------------------
    section('READOUTS DIAGNOSTICS')
    readouts_plotter = VMMReadoutsPlotter(new_reader.readouts_vmm_normal, axis_set=axis_set)
    hybrids = readouts_plotter.hybrid_table()
    print(f'  Found {len(hybrids)} (ring, fen, hybrid) triplets in readouts: {hybrids}')

    readouts_plotter.plot_channels_raw(hybrids)
    readouts_plotter.plot_timestamps(hybrids)
    readouts_plotter.plot_adc_vs_channel(hybrids, logScale=True)

    BaseReadoutsPlotter(new_reader.readouts_vmm_normal).plot_chopper_resets()
    print('  Readouts plots done.')

    # -------------------------------------------------------------------------
    # HITS plots
    # -------------------------------------------------------------------------
    section('HITS DIAGNOSTICS')
    hits_plotter = VMMHitsPlotter(new_hits)
    hit_unit_ids = hits_plotter.unit_ids()
    print(f'  Found {len(hit_unit_ids)} physical unit IDs in hits: {hit_unit_ids}')

    hits_plotter.plot_channels_raw(hit_unit_ids)
    hits_plotter.plot_timestamps(hit_unit_ids)
    hits_plotter.plot_timestamps_vs_channel(hit_unit_ids)
    print('  Hits plots done.')

    # -------------------------------------------------------------------------
    # EVENTS plots (raw-channel domain only -- abs-units stage not built yet)
    # -------------------------------------------------------------------------
    section('EVENTS DIAGNOSTICS (raw channel domain)')
    events_plotter = VMMEventsPlotter(new_ev, axis_set)
    ev_unit_ids = events_plotter.unit_ids()
    print(f'  Found {len(ev_unit_ids)} physical unit IDs in events: {ev_unit_ids}')

    events_plotter.plot_tof(ev_unit_ids)
    events_plotter.plot_instantaneous_rate(ev_unit_ids)
    events_plotter.plot_multiplicity(ev_unit_ids)
    events_plotter.plot_phs_global(ev_unit_ids)
    events_plotter.plot_detector_image(absUnits=False, orientation='vertical')
    events_plotter.plot_phs(ev_unit_ids)
    events_plotter.plot_phs_correlation(ev_unit_ids)
    print('  Events plots done.')

    section('SKIPPED (abs-units stage not yet implemented)')
    print('  plot_wavelength()              -- needs events.wavelength')
    print('  plot_wire_vs_lambda()          -- needs events.wavelength')
    print('  plot_detector_image(absUnits=True) -- needs absCoordinate0/1')
    print('  Re-enable these once the abs-units engine is wired in.')

    # -------------------------------------------------------------------------
    # Save / show
    # -------------------------------------------------------------------------
    n_figs = len(plt.get_fignums())
    section('SUMMARY')
    print(f'  Total figures generated: {n_figs}')

    if SAVE_FIGURES:
        saved = save_all_open_figures(OUTPUT_DIR)
        print(f'  Saved {len(saved)} figures to: {OUTPUT_DIR}')

    if SHOW_FIGURES:
        plt.show()