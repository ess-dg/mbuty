#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST_plotting_pipeline.py

Runs the modernized vectorized pipeline end-to-end (reader -> mapping ->
hits -> clustering -> events) on a real pcapng file, then exercises every
plot method across the three new distinct hierarchy files:
plotting_readouts.py, plotting_hits.py, and plotting_events.py.
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

from lib import libMapping as maps
from lib import libParameters as para

from newLib import reader
from newLib.mapping_engine import MBMapper
from newLib.clustering_engine import VMMNormalClusterer
from newLib.histograms import MBAxisSet

# CHANGED: Import from your new targeted plotting hierarchy files instead of the single unified layout
from newLib.plotting_readouts import BaseReadoutsPlotter, MBReadoutsPlotter
from newLib.plotting_hits import MBHitsPlotter
from newLib.plotting_events import MBEventsPlotter

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

SAVE_FIGURES = False
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
    axis_set = MBAxisSet(parameters, config_new)
    print(f'  ax_wires steps={axis_set.ax_wires.steps}, ax_strips steps={axis_set.ax_strips.steps}, '
          f'ax_tof steps={axis_set.ax_tof.steps}')

    # Extract geometry topology list straight out of our loaded config file
    topology_list = config_new.get('topology', [])

    # -------------------------------------------------------------------------
    # READOUTS plots
    # -------------------------------------------------------------------------
    section('READOUTS DIAGNOSTICS')
    # CHANGED: Instantiate the specific Multi-Blade readout child class and pass the required configuration topology list
    readouts_plotter = MBReadoutsPlotter(new_reader.readouts_vmm_normal, topology=topology_list, axis_set=axis_set)
    unit_ids = readouts_plotter.topology_unit_ids()
    print(f'  Configured Unit IDs in topology mapping layout: {unit_ids}')

    readouts_plotter.plot_channels_raw(unit_ids)
    readouts_plotter.plot_timestamps(unit_ids)
    readouts_plotter.plot_adc_vs_channel(unit_ids, logScale=True)

    BaseReadoutsPlotter(new_reader.readouts_vmm_normal, topology=topology_list).plot_chopper_resets()
    print('  Readouts plots done.')

    # -------------------------------------------------------------------------
    # HITS plots
    # -------------------------------------------------------------------------
    section('HITS DIAGNOSTICS')
    # CHANGED: Use the concrete MBHitsPlotter and read physical wire bounds directly from the configuration parameters
    num_wires_mb = config_new['wires']
    hits_plotter = MBHitsPlotter(new_hits, num_wires=num_wires_mb)
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
    # CHANGED: Instantiate the dedicated MBEventsPlotter concrete layout class
    events_plotter = MBEventsPlotter(new_ev, axis_set, config_new)
    ev_unit_ids = events_plotter.unit_ids()
    print(f'  Found {len(ev_unit_ids)} physical unit IDs in events: {ev_unit_ids}')

    events_plotter.plot_tof(ev_unit_ids)
    events_plotter.plot_lambda(ev_unit_ids)
    events_plotter.plot_instantaneous_rate(ev_unit_ids)
    events_plotter.plot_multiplicity(ev_unit_ids)
    events_plotter.plot_xy_tof(abs_units=False, orientation='vertical')
    events_plotter.plot_phs(ev_unit_ids)
    events_plotter.plot_phs_correlation(ev_unit_ids)
    print('  Events plots done.')

    section('SKIPPED (abs-units stage not yet implemented)')
    print('  plot_wire_vs_lambda()          -- needs events.wavelength')
    print('  plot_xy_tof(abs_units=True)    -- needs absCoordinate0/1')
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