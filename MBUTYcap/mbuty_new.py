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
import time
import json
import numpy as np

# Ingest new high-performance architecture modules
from newLib.reader import PcapngFileReader
from newLib.kafka_reader import KafkaReader
from newLib.colors import INFO, OK, WARN, ERR, RESET
from newLib.instrument_registry import get_info

# Ingest engine libraries for modular workflows
from newLib.mapping_engine import MBMapper, MBClustMapper, MGMapper, He3Mapper
from newLib.clustering_engine import VMMNormalClusterer
from newLib.abs_units_engine import MBAbsUnitsCalculator

# Ingest legacy file resolver as an isolated asset
from lib.libFileManagmentUtil import fileDialogue
import newLib.libParameters as para


# Ingest split plotting architecture sub-modules
from newLib.plotting_readouts import MBReadoutsPlotter, MGReadoutsPlotter, R5560ReadoutsPlotter
from newLib.plotting_hits import MBHitsPlotter, MGHitsPlotter, R5560HitsPlotter
from newLib.plotting_events import MBEventsPlotter, MGEventsPlotter, R5560EventsPlotter, MonitorEventsPlotter
# =============================================================================
# Object-Oriented Pipeline Tracks
# =============================================================================

class BasePipeline:
    """Non-negotiable contract for all hardware instrument workflows."""
    def __init__(self, readouts_container, parameters, config_dict: dict):
        self.readouts_container = readouts_container
        self.parameters = parameters
        self.config = config_dict
        
        # Public plotter properties bound dynamically for direct Dashboard inspection
        self.readout_plotter = None
        self.hit_plotter = None
        self.event_plotter = None

    def execute(self) -> None:
        raise NotImplementedError


class VMMNormalPipeline(BasePipeline):
    """Execution track for Multi-Blade / Multi-Grid VMM3A normal hardware channels (opMode == 'normal')."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}VMM Normal Readouts Container is empty — skipping pipeline pass.{RESET}")
            return

        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            print(f'{INFO}Running in-place vectorized VMM calibration pass...{RESET}')
            self.readouts_container.calibrate(self.parameters, self.config)

        print(f'{INFO}Executing normal mapping engine pass...{RESET}')
        detector_type = self.config.get('detectorType', 'MB')
        if detector_type == 'MG':
            hits_container = MGMapper.map(self.readouts_container, self.config)
        else:
            hits_container = MBMapper.map(self.readouts_container, self.config)
        
        print(f'{INFO}Executing coincidence clustering engine pass...{RESET}')
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 3e-6)
        events_container = VMMNormalClusterer.cluster(hits_container, self.config, time_window)
        # Note this is wrong need to check if mb or mg 
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        axis_set = getattr(self.parameters, 'axis_set', None)
        
        self.readout_plotter = VMMReadoutsPlotter(self.readouts_container, axis_set)
        self.hit_plotter = VMMHitsPlotter(hits_container)
        self.event_plotter = VMMEventsPlotter(events_container, axis_set)


class VMMClusteredPipeline(BasePipeline):
    """Execution track for pre-clustered VMM3A hardware tracking streams (opMode == 'clustered')."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}VMM Clustered Readouts Container is empty — skipping pipeline pass.{RESET}")
            return
            
        print(f'{INFO}Executing hardware-clustered VMM mapping pass...{RESET}')
        hits_container = MBClustMapper.map(self.readouts_container, self.config)
        
        print(f'{INFO}Routing to clustered coincidence matching layout tracks...{RESET}')
        # Downstream clustered engine execution calls go here...


class R5560Pipeline(BasePipeline):
    """Execution track for CAEN R5560 Helium-3 continuous gas tube detectors."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return
            
        print(f'{INFO}Executing R5560 Helium-3 mapping and customized tube clustering...{RESET}')
        hits_container = He3Mapper.map(self.readouts_container, self.config)
        
        from newLib.clustering_engine import He3Clusterer
        events_container = He3Clusterer.cluster(hits_container, self.config)
        
        axis_set = getattr(self.parameters, 'axis_set', None)
        
        self.readout_plotter = BaseReadoutsPlotter(self.readouts_container)
        self.hit_plotter = BaseHitsPlotter(hits_container)
        self.event_plotter = R5560EventsPlotter(events_container, axis_set)


class SkadiPipeline(BasePipeline):
    """Execution track for specialized SKADI detector layout streams."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return
        print(f'{INFO}Not yet implemented...{RESET}')


class GenericBMPipeline(BasePipeline):
    """Telemetry pipeline track for Standard/Passthrough Beam Monitors."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return
        print(f'{INFO}Not yet implemented...{RESET}')
        


class IBMPipeline(BasePipeline):
    """Telemetry pipeline track for Ionization Beam Monitors (IBM)."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return
        print(f'{INFO}Not yet implemented...{RESET}')


# =============================================================================
# Pipeline Factory Router Registry
# =============================================================================

class PipelineFactory:
    """Maps (detector_type, opMode) cleanly to concrete execution classes."""
    
    @classmethod
    def get_detector_pipeline(cls, detector_type: str, op_mode: str, readouts_container, parameters, config: dict) -> BasePipeline | None:
        # Resolve combinations cleanly to matching workflow architectures
        if detector_type in ['MB', 'MG']:
            if op_mode == 'normal':
                return VMMNormalPipeline(readouts_container, parameters, config)
            elif op_mode == 'clustered':
                return VMMClusteredPipeline(readouts_container, parameters, config)
        elif detector_type == 'He3':
            return R5560Pipeline(readouts_container, parameters, config)
        elif detector_type == 'SKADI':
            return SkadiPipeline(readouts_container, parameters, config)
        return None

    @classmethod
    def get_bm_pipeline(cls, bm_hardware_type: str, readouts_container, parameters, config: dict) -> BasePipeline:
        if bm_hardware_type.lower() == 'ibm':
            return IBMPipeline(readouts_container, parameters, config)
        return GenericBMPipeline(readouts_container, parameters, config)


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
        print(f'{INFO}Ciao {user_name}! Welcome to MBUTY 8.3 [Guarded Architecture] {RESET}')
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

        # 2. Extract Registry Definitions via Configuration Parameters
        detector_type = self.config.get('detectorType') 
        op_mode = self.config.get('opMode', 'normal')
        print(f'{INFO}\nEvaluating hardware metrics: detector_type = "{detector_type}", opMode = "{op_mode}"...{RESET}')

        # 3. Guarded Multi-Key Detector Container Switching Pass
        if detector_type in ['MB', 'MG']:
            if op_mode == 'normal':
                active_readouts = getattr(reader, 'readouts_vmm_normal', None)
            elif op_mode == 'clustered':
                active_readouts = getattr(reader, 'readouts_vmm_clustered', None)
            else:
                print(f'\n{ERR}FATAL ERROR: Unrecognized opMode "{op_mode}" for VMM detector systems! Exit.{RESET}')
                sys.exit(1)
        elif detector_type == 'He3':
            active_readouts = getattr(reader, 'readouts_r5560', None)
        elif detector_type == 'SKADI':
            active_readouts = getattr(reader, 'readouts_skadi', None)
        else:
            # Absolute Gate Guard: Reject unmapped configurations instantly
            print(f'\n{ERR}FATAL ERROR: Configuration mismatch. detector_type "{detector_type}" '
                  f'is completely unrecognized by the pipeline registry hardware definitions! Exit.{RESET}')
            sys.exit(1)

        # 4. Pipeline Track Instantiation & Execution Pass via Factory
        if active_readouts is not None:
            self.detector_pipeline = PipelineFactory.get_detector_pipeline(
                detector_type, op_mode, active_readouts, self.parameters, self.config
            )
            if self.detector_pipeline:
                print(f'{OK}Executing verified pipeline reduction track for: {detector_type} [{op_mode}]{RESET}')
                self.detector_pipeline.execute()
        else:
            print(f'{WARN}Target readout container for "{detector_type}" was not populated during ingestion.{RESET}')

        # 5. Conditionally Dispatch Beam Monitor Tracking Stream
        if self.config.get('beam_monitor_present', False):
            bm_type = self.config.get('bm_hardware_type', 'generic')
            
            if bm_type.lower() == 'ibm':
                bm_readouts = getattr(reader, 'readouts_ibm', None)
            else:
                bm_readouts = getattr(reader, 'readouts_bm', None)
            
            if bm_readouts is not None:
                self.bm_pipeline = PipelineFactory.get_bm_pipeline(
                    bm_type, bm_readouts, self.parameters, self.config
                )
                print(f'{OK}Executing verified pipeline track for Beam Monitor: {bm_type}{RESET}')
                self.bm_pipeline.execute()
            else:
                print(f'{WARN}Beam Monitor flagged as active, but associated BM readouts are empty.{RESET}')

        print(f'{OK}\nIngestion, Guarded Factory Routing, and Vector Processing Complete.{RESET}')

from newLib.mbuty_dashboard import DashboardDataSource, MbutyDashboard
from PySide6.QtWidgets import QApplication

class OrchestratorDataSource(DashboardDataSource):
    """Bridges the executed MBUTYOrchestrator pipeline data directly to the PySide6 layout shell."""
    def __init__(self, orchestrator: MBUTYOrchestrator):
        self.orch = orchestrator

    def beam_monitor_present(self) -> bool:
        return bool(self.orch.config.get('beam_monitor_present', False))

    def get_dataframe_array(self, tab_key: str) -> tuple[np.ndarray, int]:
        """Routes structured matrix arrays and active row count counters straight to QTableViews."""
        if tab_key == "readouts":
            container = self.orch.detector_pipeline.readouts_container
        elif tab_key == "mapped_hits":
            container = self.orch.detector_pipeline.hit_plotter.container
        elif tab_key == "coincidence_events":
            container = self.orch.detector_pipeline.event_plotter.container
        elif tab_key == "beam_monitor" and self.orch.bm_pipeline:
            container = self.orch.bm_pipeline.event_plotter.events
        else:
            return np.empty(0, dtype=[("_", "i4")]), 0
            
        return container.matrix, container.fill_count

    def get_available_plots(self, tab_key: str) -> list[str]:
        """Queries public methods starting with 'plot_' on the active plotter instances via inspection."""
        pipeline = self.orch.bm_pipeline if tab_key == "beam_monitor" else self.orch.detector_pipeline
        if not pipeline:
            return []
            
        if tab_key == "readouts":
            plotter = pipeline.readout_plotter
        elif tab_key == "mapped_hits":
            plotter = pipeline.hit_plotter
        elif tab_key == "coincidence_events" or tab_key == "beam_monitor":
            plotter = pipeline.event_plotter
        else:
            plotter = None
            
        if plotter is None:
            return []
            
        # Dynamically discover all public plotting functions implemented on this concrete instance
        return [method for method in dir(plotter) if method.startswith('plot_') and callable(getattr(plotter, method))]

    def render_plot(self, tab_key: str, plot_name: str, figure) -> None:
        """Dynamically passes the dashboard target figure canvas context straight to the active plotter."""
        pipeline = self.orch.bm_pipeline if tab_key == "beam_monitor" else self.orch.detector_pipeline
        if not pipeline:
            return
            
        if tab_key == "readouts":
            plotter = pipeline.readout_plotter
        elif tab_key == "mapped_hits":
            plotter = pipeline.hit_plotter
        elif tab_key == "coincidence_events" or tab_key == "beam_monitor":
            plotter = pipeline.event_plotter
        else:
            return

        method = getattr(plotter, plot_name, None)
        if method is None:
            print(f"{WARN}WARNING: Plotting method '{plot_name}' not supported by {type(plotter).__name__}.{RESET}")
            return

        import matplotlib.pyplot as plt
        import inspect

        # Target the single-source figure context allocated by the dashboard grid layout
        plt.figure(figure.number)
        figure.clear()

        # Gather current runtime arguments from the parameter structures
        global_ui_kwargs = {
            "logScale": getattr(self.orch.parameters.dataReduction, "logScale", False),
            "absUnits": getattr(self.orch.parameters.dataReduction, "absUnits", False),
            "orientation": self.orch.config.get("orientation", "vertical"),
            "fig": figure
        }

        # Filter keywords through method signature inspection to prevent argument mismatch crashes
        sig = inspect.signature(method)
        filtered_kwargs = {k: v for k, v in global_ui_kwargs.items() if k in sig.parameters}

        method(**filtered_kwargs)
        
        
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
    
    # Initialize the PySide6 Application layout shell environment
    print(f"\n{INFO}Launching PySide6 Interactive Dashboard...{RESET}")
    app = QApplication(sys.argv)
    
    # Bind data source adapter to dashboard initialization specifications
    data_bridge = OrchestratorDataSource(pipeline_orchestrator)
    
    # Build demo dictionary mapping for user active plot views (passed directly to sub-tab generator)
    dashboard_config = {
        "readouts_active_plots": ["plot_channels_raw", "plot_adc_vs_channel"],
        "hits_active_plots": ["plot_channels_raw", "plot_timestamps_vs_channel"],
        "events_active_plots": ["plot_detector_image", "plot_tof", "plot_wavelength", "plot_phs"],
        "bm_active_plots": ["plot_tof_and_phs", "plot_wavelength"]
    }
    
    window = MbutyDashboard(data_bridge, config=dashboard_config)
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())