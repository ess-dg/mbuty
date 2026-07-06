#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipelines.py
============
Object-Oriented Pipeline Tracks and Pipeline Factory Router Registry
for ESS Neutron Detectors.

Extracted from mbuty_new.py as part of a clean file separation.
"""
import os
import sys
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from newLib.colors import INFO, WARN, RESET

# Ingest engine libraries for modular workflows
from newLib.mapping_engine import MBMapper, MBClustMapper, MGMapper, He3Mapper
from newLib.clustering_engine import VMMNormalClusterer
from newLib.abs_units_engine import MBAbsUnitsCalculator

# Ingest split plotting architecture sub-modules
from newLib.plotting_readouts import MBReadoutsPlotter, MGReadoutsPlotter, R5560ReadoutsPlotter
from newLib.plotting_hits import MBHitsPlotter, MGHitsPlotter, R5560HitsPlotter
from newLib.plotting_events import MBEventsPlotter, MGEventsPlotter, R5560EventsPlotter


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


class MBPipeline(BasePipeline):
    """Clean execution track dedicated exclusively to Multi-Blade hardware in normal mode."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}Multi-Blade Readouts Container is empty — skipping pipeline pass.{RESET}")
            return

        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            print(f'{INFO}Running in-place vectorized VMM calibration pass...{RESET}')
            self.readouts_container.calibrate(self.parameters, self.config)

        print(f'{INFO}Executing Multi-Blade mapping engine pass...{RESET}')
        hits_container = MBMapper.map(self.readouts_container, self.config)
        
        print(f'{INFO}Executing coincidence clustering engine pass...{RESET}')
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 3e-6)
        events_container = VMMNormalClusterer.cluster(hits_container, self.config, time_window)
        
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        # 5. Build and initialize axis geometry via the modernized Multi-Blade set
        from newLib.histograms import MBAxisSet
        axis_set = MBAxisSet(self.parameters, self.config)

        topology = self.config.get('topology', [])
        num_wires = int(self.config['wires'])
        
        self.readout_plotter = MBReadoutsPlotter(self.readouts_container, topology, axis_set)
        self.hit_plotter = MBHitsPlotter(hits_container, num_wires)
        self.event_plotter = MBEventsPlotter(events_container, axis_set, self.config)


class MGPipeline(BasePipeline):
    """Clean execution track dedicated exclusively to Multi-Grid hardware in normal mode."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}Multi-Grid Readouts Container is empty — skipping pipeline pass.{RESET}")
            return

        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            print(f'{INFO}Running in-place vectorized VMM calibration pass...{RESET}')
            self.readouts_container.calibrate(self.parameters, self.config)

        print(f'{INFO}Executing Multi-Grid mapping engine pass...{RESET}')
        hits_container = MGMapper.map(self.readouts_container, self.config)
        
        print(f'{INFO}Executing coincidence clustering engine pass...{RESET}')
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 3e-6)
        events_container = VMMNormalClusterer.cluster(hits_container, self.config, time_window)
        
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        from newLib.plotting_readouts import VMMReadoutsPlotter
        from newLib.plotting_hits import VMMHitsPlotter
        from newLib.plotting_events import MGEventsPlotter
        # 5. Build and initialize axis geometry via the modernized Multi-Grid set
        from newLib.histograms import MGAxisSet
        axis_set = MGAxisSet(self.parameters)

        topology = self.config.get('topology', [])
        
        self.readout_plotter = MGReadoutsPlotter(self.readouts_container, topology, axis_set)
        self.hit_plotter = MGHitsPlotter(hits_container)
        self.event_plotter = MGEventsPlotter(events_container, axis_set, self.config)

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
        topology = self.config.get('topology', [])
        
        self.readout_plotter = R5560ReadoutsPlotter(self.readouts_container, topology)
        self.hit_plotter = R5560HitsPlotter(hits_container, axis_set)
        self.event_plotter = R5560EventsPlotter(events_container, axis_set, self.config)


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
        print(f'{INFO}Executing Generic Beam Monitor timeline filtering and binning pass...{RESET}')
        # Inizializzazione della pipeline monitor...


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
    """Maps (detector_type, opMode) cleanly to concrete execution classes without internal switching branches."""
    
    @classmethod
    def get_detector_pipeline(cls, detector_type: str, op_mode: str, readouts_container, parameters, config: dict) -> BasePipeline | None:
        if op_mode == 'normal':
            if detector_type == 'MB':
                return MBPipeline(readouts_container, parameters, config)
            elif detector_type == 'MG':
                return MGPipeline(readouts_container, parameters, config)
        elif op_mode == 'clustered' and detector_type in ['MB', 'MG']:
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