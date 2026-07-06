#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbuty_new.py
============
High-Performance Master Ingestion Orchestrator and Pipeline Factory Pattern
for ESS Neutron Detectors.
"""

import os
import sys
import json
import numpy as np

# Ingest new high-performance architecture modules
from newLib.reader import PcapngFileReader
from newLib.kafka_reader import KafkaReader
from newLib.colors import INFO, OK, WARN, ERR, RESET

# Ingest object-oriented pipeline tracks and factory router registry
from newLib.pipelines import PipelineFactory

# Ingest legacy file resolver as an isolated asset
from lib.libFileManagmentUtil import fileDialogue
import newLib.libParameters as para


# =============================================================================
# Master Ingestion Orchestrator
# =============================================================================

class MBUTYOrchestrator:
    """
    Main pipeline orchestrator managing data lifecycle:
    Path resolution -> Ingestion -> Guarded Multi-Key Routing -> Execution.
    """
    def __init__(self, parameters, run_from_gui: bool = False):
        self.parameters = parameters
        self.run_from_gui = run_from_gui
        
        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        print('----------------------------------------------------------------------')
        print(f'{INFO}Ciao {user_name}! Welcome to MBUTY 8.0 {RESET}')
        print('----------------------------------------------------------------------')
        
        config_path = os.path.join(
            self.parameters.fileManagement.configFilePath,
            self.parameters.fileManagement.configFileName
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.detector_pipeline = None
        self.bm_pipeline = None

    def run_pipeline(self) -> None:
        """Executes data frame ingestion and routes targeted tracks via explicit type matching gates."""
        
        # 1. Pipeline Data Ingestion Pass (Network Stream vs Disk Storage)
        if self.parameters.acqMode == 'kafka':
            reader = KafkaReader(
                parameters = self.parameters,
                config     = self.config,
                broker     = self.parameters.kafkaSettings.broker,
                topic      = self.parameters.kafkaSettings.topic,
                n_packets  = self.parameters.kafkaSettings.numOfPackets,
                testing    = False
            )
            reader.run()
        else:
            file_resolver = fileDialogue(self.parameters)
            file_resolver.openFile()
            
            if not file_resolver.fileName:
                print(f'{ERR}Pipeline Aborted: No valid target files found.{RESET}')
                return
                
            for idx, filename in enumerate(file_resolver.fileName):
                print(f'{INFO}\nProcessing file [{idx + 1}/{len(file_resolver.fileName)}]: {filename}{RESET}')
                full_file_path = os.path.join(file_resolver.filePath, filename)
                
                reader = PcapngFileReader(
                    file_path  = full_file_path,
                    parameters = self.parameters,
                    config     = self.config
                )
                reader.run()

        # 2. Detector Pipeline Track Instantiation & Execution Pass via Factory-
        self.detector_pipeline = PipelineFactory.build_detector_pipeline(self.config, reader, self.parameters)
        if self.detector_pipeline:
            print(f'{OK}Executing verified pipeline reduction track for: {self.config.get("detectorType")}{RESET}')
            self.detector_pipeline.execute()

        # 3. Conditionally Dispatch Beam Monitor Tracking Stream
        self.bm_pipeline = PipelineFactory.build_bm_pipeline(self.config, reader, self.parameters)
        if self.bm_pipeline:
            print(f'{OK}Executing verified pipeline track for Beam Monitor: {self.config.get("bm_hardware_type", "generic")}{RESET}')
            self.bm_pipeline.execute()

        print(f'{OK}\nIngestion, Guarded Factory Routing, and Vector Processing Complete.{RESET}')

from newLib.mbuty_dashboard import DashboardDataSource, MbutyDashboard
from newLib.plotting_base import resolve_active_plots, global_ui_kwargs_from_parameters
from PySide6.QtWidgets import QApplication

class OrchestratorDataSource(DashboardDataSource):
    """Bridges the executed MBUTYOrchestrator pipeline data directly to the PySide6 layout shell.

    section_unit_ids: when set, scopes every plot call to this block of
    unit IDs (cassettes/tubes) -- used for plottingInSections, one
    dashboard window per block. Methods that don't accept a unit_ids
    kwarg (whole-detector composite images like plot_xy_tof/plot_x_lambda)
    silently ignore it, same signature-filtering mechanism as everything
    else in render_plot().

    include_bm: lets the orchestrator show the Beam Monitor tab on only
    one of several sequential section windows, since the monitor stream
    doesn't vary per cassette block and would otherwise be duplicated in
    every window.
    """
    def __init__(self, orchestrator: MBUTYOrchestrator, section_unit_ids=None, include_bm: bool = True):
        self.orch = orchestrator
        self.section_unit_ids = section_unit_ids
        self.include_bm = include_bm

    def beam_monitor_present(self) -> bool:
        return self.include_bm and bool(self.orch.config.get('beam_monitor_present', False))

    def _resolve_plotter(self, tab_key: str):
        """Single lookup shared by get_available_plots/render_plot/render_plot_headless,
        so the tab_key -> plotter mapping only exists in one place. Returns None for
        anything unavailable (unbuilt pipeline, or a stage deliberately left as None --
        bareReadoutsCalculation, or MBClusteredPipeline's hit_plotter, etc.)."""
        pipeline = self.orch.bm_pipeline if tab_key == "beam_monitor" else self.orch.detector_pipeline
        if not pipeline:
            return None
        if tab_key == "readouts":
            return getattr(pipeline, "readout_plotter", None)
        if tab_key == "mapped_hits":
            return getattr(pipeline, "hit_plotter", None)
        if tab_key in ("coincidence_events", "beam_monitor"):
            return getattr(pipeline, "event_plotter", None)
        return None

    def get_dataframe_array(self, tab_key: str) -> tuple[np.ndarray, int]:
        """Routes structured matrix arrays and active row count counters straight to QTableViews."""
        if tab_key == "readouts":
            pipeline = self.orch.detector_pipeline
            container = getattr(pipeline, "readouts_container", None) if pipeline else None
        else:
            plotter = self._resolve_plotter(tab_key)
            container = plotter.container if plotter is not None else None

        if container is None:
            return np.empty(0, dtype=[("_", "i4")]), 0

        return container.matrix[:container.fill_count], container.fill_count

    def get_available_plots(self, tab_key: str) -> list[str]:
        """Queries public methods starting with 'plot_' on the active plotter instances via inspection.
        Returns [] whenever the backing plotter is None -- this doubles as the tab-availability
        signal MbutyDashboard uses to decide whether to build a tab at all."""
        plotter = self._resolve_plotter(tab_key)
        if plotter is None:
            return []
        # Dynamically discover all public plotting functions implemented on this concrete instance
        return [method for method in dir(plotter) if method.startswith('plot_') and callable(getattr(plotter, method))]

    def _dispatch(self, tab_key: str, plot_name: str, figure=None) -> None:
        """Shared dispatch for both the GUI (figure=Qt Figure) and headless
        (figure=None -> method opens its own standalone matplotlib window
        via its default int fig_num) rendering paths."""
        plotter = self._resolve_plotter(tab_key)
        if plotter is None:
            return

        method = getattr(plotter, plot_name, None)
        if method is None:
            print(f"{WARN}WARNING: Plotting method '{plot_name}' not supported by {type(plotter).__name__}.{RESET}")
            return

        import inspect

        if figure is not None:
            figure.clear()  # Clear the dashboard layout's single-source figure canvas directly

        global_ui_kwargs = global_ui_kwargs_from_parameters(
            self.orch.parameters, self.orch.config,
            unit_ids=self.section_unit_ids, figure=figure,
        )

        # Filter keywords through method signature inspection to prevent argument mismatch crashes
        sig = inspect.signature(method)
        filtered_kwargs = {k: v for k, v in global_ui_kwargs.items() if k in sig.parameters}

        method(**filtered_kwargs)

    def render_plot(self, tab_key: str, plot_name: str, figure) -> None:
        """Dynamically passes the dashboard target figure canvas context straight to the active plotter."""
        self._dispatch(tab_key, plot_name, figure=figure)

    def render_plot_headless(self, tab_key: str, plot_name: str) -> None:
        """Backup plotting path (parameters.plotting.useDashboard = False): lets each
        plot method open its own standalone matplotlib window instead of drawing onto
        a Qt canvas. Same selection/kwargs logic as the dashboard -- only the output
        surface differs."""
        self._dispatch(tab_key, plot_name, figure=None)
        
        
def _chunk(seq: list, size: int) -> list[list]:
    size = max(1, int(size))
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def _section_blocks(orchestrator: MBUTYOrchestrator, params) -> list:
    """Returns a list of unit-ID blocks to iterate over. A single-element
    list containing None means "no sectioning -- one pass over everything",
    which is both the default (plottingInSections == False) and the
    fallback whenever there's no readout_plotter to pull a topology from
    (e.g. detector_pipeline never got built)."""
    if not params.plotting.plottingInSections:
        return [None]

    pipeline = orchestrator.detector_pipeline
    readout_plotter = getattr(pipeline, "readout_plotter", None) if pipeline else None
    if readout_plotter is None:
        return [None]

    unit_ids = readout_plotter.topology_unit_ids()
    blocks = _chunk(unit_ids, params.plotting.plottingInSectionsBlocks)
    return blocks if blocks else [None]


def run_dashboard(orchestrator: MBUTYOrchestrator, params, dashboard_config: dict) -> None:
    """Primary plotting path: one MbutyDashboard window per section block,
    opened sequentially -- the next window only appears once the current
    one is closed (closer to legacy's blocking 'next section?' prompt than
    popping every window at once). With plottingInSections off, this is
    just the single window it always was."""
    app = QApplication(sys.argv)
    blocks = _section_blocks(orchestrator, params)

    for i, block in enumerate(blocks):
        # Beam Monitor doesn't vary per cassette/tube block, so it's only
        # attached to the first section window rather than duplicated in each.
        data_bridge = OrchestratorDataSource(orchestrator, section_unit_ids=block, include_bm=(i == 0))
        window = MbutyDashboard(data_bridge, config=dashboard_config)

        title = "MBUTY Dashboard"
        if block is not None:
            title += f" -- section {i + 1}/{len(blocks)} (unit IDs {block[0]}-{block[-1]})"
        window.setWindowTitle(title)
        window.resize(1400, 850)
        window.show()
        app.exec()  # returns once this window (the only one open) is closed

    sys.exit(0)


def run_headless(orchestrator: MBUTYOrchestrator, params, dashboard_config: dict) -> None:
    """Backup plotting path (parameters.plotting.useDashboard = False):
    same plot selection as the dashboard, but each plot opens its own
    plain matplotlib window via plt.show(). Mirrors legacy's behaviour,
    including plottingInSections' block-by-block "press Enter to continue".
    """
    import matplotlib.pyplot as plt

    data_bridge = OrchestratorDataSource(orchestrator)
    blocks = _section_blocks(orchestrator, params)

    tab_plot_pairs = [
        ("readouts", dashboard_config["readouts_active_plots"]),
        ("mapped_hits", dashboard_config["hits_active_plots"]),
        ("coincidence_events", dashboard_config["events_active_plots"]),
    ]
    if orchestrator.bm_pipeline is not None:
        tab_plot_pairs.append(("beam_monitor", dashboard_config["bm_active_plots"]))

    for i, block in enumerate(blocks):
        data_bridge.section_unit_ids = block
        for tab_key, plot_names in tab_plot_pairs:
            # Beam Monitor doesn't vary per section -- only plot it once, on the first pass.
            if tab_key == "beam_monitor" and block is not None and i > 0:
                continue
            if not data_bridge.get_available_plots(tab_key):
                continue
            for plot_name in plot_names:
                data_bridge.render_plot_headless(tab_key, plot_name)

        section_note = f" (section {i + 1}/{len(blocks)})" if block is not None else ""
        print(f"{INFO}\nPlots ready{section_note}. Close the figure windows to continue...{RESET}")
        plt.show()  # blocks until every open figure window is closed
        if i < len(blocks) - 1:
            input("Press Enter for the next section... ")


if __name__ == '__main__':
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    params = para.parameters(current_dir)
    
    params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
    params.fileManagement.configFileName = "AMOR.json"
    params.acqMode = 'off'
    params.fileManagement.pcapLoadingMethod = 'allocate'
    params.dataReduction.calibrateVMM_ADC_ONOFF = True
    params.fileManagement.calibFilePath = os.path.join(current_dir, 'calib') + os.sep
    params.fileManagement.calibFileName = "AMOR_calib.json"
    
    # Run backend scientific computation track
    pipeline_orchestrator = MBUTYOrchestrator(params)
    pipeline_orchestrator.run_pipeline()
    
    detector_pipeline = pipeline_orchestrator.detector_pipeline
    bm_pipeline = pipeline_orchestrator.bm_pipeline
    dashboard_config = resolve_active_plots(
        params,
        readout_plotter=getattr(detector_pipeline, "readout_plotter", None) if detector_pipeline else None,
        hit_plotter=getattr(detector_pipeline, "hit_plotter", None) if detector_pipeline else None,
        event_plotter=getattr(detector_pipeline, "event_plotter", None) if detector_pipeline else None,
        bm_plotter=getattr(bm_pipeline, "event_plotter", None) if bm_pipeline else None,
    )

    if params.plotting.useDashboard:
        print(f"\n{INFO}Launching PySide6 Interactive Dashboard...{RESET}")
        run_dashboard(pipeline_orchestrator, params, dashboard_config)
    else:
        print(f"\n{INFO}useDashboard is False -- falling back to plain matplotlib windows...{RESET}")
        run_headless(pipeline_orchestrator, params, dashboard_config)