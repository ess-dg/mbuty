#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipelines.py
============
Object-Oriented Pipeline Tracks and Pipeline Factory Router Registry
for ESS Neutron Detectors.

Extracted from mbuty_new.py as part of a clean file separation.

Routing model
-------------
Each detector_type maps to a small dict of opMode -> (PipelineClass, readouts_attr).
Only VMM-based hardware (MB, MG) carries an 'opMode' config key at all -- those
are keyed by 'normal'/'clustered'. Every other detector type (different hardware
entirely) has no such key and is keyed under None instead. MB is the only track
with a working clustered mode right now; MG is VMM hardware too and will likely
grow a 'clustered' entry the same way in the future, but for now only supports
'normal'.

PipelineFactory.build_detector_pipeline() / build_bm_pipeline() are the *only*
places config gets inspected to make this decision -- one lookup resolves the
opMode validity, the active readouts container, and the concrete pipeline class
together, so callers never re-derive any of that themselves.

Each pipeline's execute() lazily imports the mapper/clusterer/plotter modules
it actually needs, right before constructing them, so an inactive pipeline
never pays for imports it doesn't use.
"""
import os
import sys

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.colors import INFO, WARN, ERR, RESET


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

        from newLib.mapping_engine import MBMapper
        print(f'{INFO}Executing Multi-Blade mapping engine pass...{RESET}')
        hits_container = MBMapper.map(self.readouts_container, self.config)

        from newLib.clustering_engine import VMMNormalClusterer
        print(f'{INFO}Executing coincidence clustering engine pass...{RESET}')
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 3e-6)
        events_container = VMMNormalClusterer.cluster(hits_container, self.config, time_window)

        from newLib.abs_units_engine import MBAbsUnitsCalculator
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        # Build and initialize axis geometry via the modernized Multi-Blade set
        from newLib.histograms import MBAxisSet
        axis_set = MBAxisSet(self.parameters, self.config)

        topology = self.config.get('topology', [])
        num_wires = int(self.config['wires'])

        from newLib.plotting_readouts import MBReadoutsPlotter
        from newLib.plotting_hits import MBHitsPlotter
        from newLib.plotting_events import MBEventsPlotter

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

        from newLib.mapping_engine import MGMapper
        print(f'{INFO}Executing Multi-Grid mapping engine pass...{RESET}')
        hits_container = MGMapper.map(self.readouts_container, self.config)

        from newLib.clustering_engine import VMMNormalClusterer
        print(f'{INFO}Executing coincidence clustering engine pass...{RESET}')
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 3e-6)
        events_container = VMMNormalClusterer.cluster(hits_container, self.config, time_window)

        from newLib.abs_units_engine import MBAbsUnitsCalculator
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        # Build and initialize axis geometry via the modernized Multi-Grid set
        from newLib.histograms import MGAxisSet
        axis_set = MGAxisSet(self.parameters)

        topology = self.config.get('topology', [])

        from newLib.plotting_readouts import MGReadoutsPlotter
        from newLib.plotting_hits import MGHitsPlotter
        from newLib.plotting_events import MGEventsPlotter

        self.readout_plotter = MGReadoutsPlotter(self.readouts_container, topology, axis_set)
        self.hit_plotter = MGHitsPlotter(hits_container)
        self.event_plotter = MGEventsPlotter(events_container, axis_set, self.config)


class MBClusteredPipeline(BasePipeline):
    """Execution track for pre-clustered VMM3A hardware tracking streams (opMode == 'clustered').
    MB-only for now -- MG has no clustered track yet.

    VMMClusteredClusterer is a firmware passthrough (the ASIC already did the
    time-window clustering on-board), so this pipeline is: map -> passthrough
    absorb -> abs units -> plot. Same shape as MBPipeline, just missing the
    VMMNormalClusterer stage since there's nothing left for software to cluster."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}VMM Clustered Readouts Container is empty — skipping pipeline pass.{RESET}")
            return

        from newLib.mapping_engine import MBClustMapper
        print(f'{INFO}Executing hardware-clustered VMM mapping pass...{RESET}')
        hits_container = MBClustMapper.map(self.readouts_container, self.config)

        from newLib.clustering_engine import VMMClusteredClusterer
        print(f'{INFO}Absorbing hardware-clustered events (firmware passthrough)...{RESET}')
        events_container = VMMClusteredClusterer.cluster(hits_container, self.config)

        from newLib.abs_units_engine import MBAbsUnitsCalculator
        print(f'{INFO}Calculating absolute physical coordinates and spectroscopy vectors...{RESET}')
        abs_calc = MBAbsUnitsCalculator(events_container, self.config, self.parameters)
        abs_calc.process_pipeline(remove_invalid_tofs=True)

        from newLib.histograms import MBAxisSet
        axis_set = MBAxisSet(self.parameters, self.config)

        topology = self.config.get('topology', [])
        num_wires = int(self.config['wires'])

        from newLib.plotting_readouts import MBReadoutsPlotter
        from newLib.plotting_hits import MBClusteredHitsPlotter
        from newLib.plotting_events import MBEventsPlotter

        self.readout_plotter = MBReadoutsPlotter(self.readouts_container, topology, axis_set)
        self.hit_plotter = MBClusteredHitsPlotter(hits_container, num_wires)
        self.event_plotter = MBEventsPlotter(events_container, axis_set, self.config)


class R5560Pipeline(BasePipeline):
    """Execution track for CAEN R5560 Helium-3 continuous gas tube detectors."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return

        from newLib.mapping_engine import He3Mapper
        print(f'{INFO}Executing R5560 Helium-3 mapping and customized tube clustering...{RESET}')
        hits_container = He3Mapper.map(self.readouts_container, self.config)

        from newLib.clustering_engine import He3Clusterer
        events_container = He3Clusterer.cluster(hits_container, self.config)

        axis_set = getattr(self.parameters, 'axis_set', None)
        topology = self.config.get('topology', [])

        from newLib.plotting_readouts import R5560ReadoutsPlotter
        from newLib.plotting_hits import R5560HitsPlotter
        from newLib.plotting_events import R5560EventsPlotter

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
    """ BMMapper maps readouts straight into a
    fully-formed eventsBM container. A lightweight abs-units pass then
    fills in ToF (generic, from the events base class) and wavelength
    (monitor-specific: fixed distance, no depth correction) before plotting."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return

        from newLib.mapping_engine import BMMapper
        print(f'{INFO}Executing Generic Beam Monitor mapping pass...{RESET}')
        events_container = BMMapper.map(self.readouts_container, self.config)

        print(f'{INFO}Calculating Beam Monitor ToF/wavelength...{RESET}')
        events_container.compute_and_filter_tof(remove_invalid=True)
        if self.parameters.wavelength.calculateLambda:
            from newLib.abs_units_engine import calculate_monitor_wavelength
            calculate_monitor_wavelength(events_container, self.parameters)

        axis_set = getattr(self.parameters, 'axis_set', None)

        from newLib.plotting_events import MonitorEventsPlotter
        self.event_plotter = MonitorEventsPlotter(events_container, axis_set)


class IBMPipeline(BasePipeline):
    """ IBMMonitorMapper maps readouts
    straight into a fully-formed eventsIBM container, then the same
    generic ToF + monitor-wavelength pass runs before plotting."""
    def execute(self) -> None:
        if self.readouts_container.fill_count == 0:
            return

        from newLib.mapping_engine import IBMMonitorMapper
        print(f'{INFO}Executing Ionization Beam Monitor mapping pass...{RESET}')
        events_container = IBMMonitorMapper.map(self.readouts_container, self.config)

        print(f'{INFO}Calculating Beam Monitor ToF/wavelength...{RESET}')
        events_container.compute_and_filter_tof(remove_invalid=True)
        if self.parameters.wavelength.calculateLambda:
            from newLib.abs_units_engine import calculate_monitor_wavelength
            calculate_monitor_wavelength(events_container, self.parameters)

        axis_set = getattr(self.parameters, 'axis_set', None)

        from newLib.plotting_events import MonitorEventsPlotter
        self.event_plotter = MonitorEventsPlotter(events_container, axis_set)


# =============================================================================
# Pipeline Factory Router Registry
# =============================================================================

class PipelineFactory:
    """Single-pass config routing for both detector and beam-monitor tracks.

    Each build_* method is the *only* place that inspects config for its
    respective decision -- it resolves opMode validity (where applicable),
    the active readouts container, and the concrete pipeline class together
    in one lookup, and returns a ready-to-execute pipeline instance (or None,
    having already printed/exited on any error). Callers never re-check
    detector_type/opMode/bm_hardware_type themselves.
    """

    # detector_type -> { opMode -> (PipelineClass, readouts_attr) }
    # Non-VMM hardware has no 'opMode' config key at all and is keyed under None.
    _DETECTOR_REGISTRY = {
        'MB': {
            'normal':    (MBPipeline, 'readouts_vmm_normal'),
            'clustered': (MBClusteredPipeline, 'readouts_vmm_clustered'),
        },
        # VMM hardware too, but clustered mode isn't implemented for MG yet --
        # add a 'clustered' entry here the same way MB's when it lands.
        'MG': {
            'normal': (MGPipeline, 'readouts_vmm_normal'),
        },
        'He3': {
            None: (R5560Pipeline, 'readouts_r5560'),
        },
        'SKADI': {
            None: (SkadiPipeline, 'readouts_skadi'),
        },
    }

    # bm_hardware_type (lowercased) -> (PipelineClass, readouts_attr)
    _BM_REGISTRY = {
        'ibm':     (IBMPipeline, 'readouts_ibm'),
        'generic': (GenericBMPipeline, 'readouts_bm'),
    }

    @classmethod
    def build_detector_pipeline(cls, config: dict, reader, parameters) -> BasePipeline | None:
        """Pulls detector_type (+ opMode, for VMM hardware) straight from `config`,
        resolves it against the registry, pulls the matching readouts container off
        `reader`, and instantiates the correct pipeline -- in one pass. Callers just
        check the result and call .execute(); they never touch config themselves.
        Fatal misconfiguration exits; a merely unpopulated readouts container
        returns None with a warning."""
        detector_type = config.get('detectorType')
        print(f'{INFO}\nEvaluating hardware metrics: detector_type = "{detector_type}"...{RESET}')

        modes = cls._DETECTOR_REGISTRY.get(detector_type)
        if modes is None:
            print(f'\n{ERR}FATAL ERROR: Configuration mismatch. detector_type "{detector_type}" '
                  f'is completely unrecognized by the pipeline registry hardware definitions! Exit.{RESET}')
            sys.exit(1)

        # Only VMM-based hardware (MB/MG) carries an 'opMode' config key.
        is_vmm_hardware = None not in modes
        op_mode = config.get('opMode', 'normal') if is_vmm_hardware else None

        entry = modes.get(op_mode)
        if entry is None:
            valid = ', '.join(repr(m) for m in modes)
            print(f'\n{ERR}FATAL ERROR: Unrecognized/unsupported opMode "{op_mode}" for detector_type '
                  f'"{detector_type}" (supported: {valid}). Exit.{RESET}')
            sys.exit(1)

        pipeline_cls, readouts_attr = entry
        active_readouts = getattr(reader, readouts_attr, None)
        if active_readouts is None:
            print(f'{WARN}Target readout container "{readouts_attr}" for "{detector_type}" '
                  f'was not populated during ingestion.{RESET}')
            return None

        return pipeline_cls(active_readouts, parameters, config)

    @classmethod
    def build_bm_pipeline(cls, config: dict, reader, parameters) -> BasePipeline | None:
        """Pulls beam_monitor_present/bm_hardware_type straight from `config`, resolves
        the type against the registry, pulls the matching readouts container off
        `reader`, and instantiates the correct pipeline -- in one pass. Returns None
        (no pipeline to run) whenever the beam monitor isn't flagged as present at all."""
        if not config.get('beam_monitor_present', False):
            return None

        bm_hardware_type = config.get('bm_hardware_type', 'generic')
        entry = cls._BM_REGISTRY.get(bm_hardware_type.lower())
        if entry is None:
            print(f'{WARN}WARNING: Beam monitor type "{bm_hardware_type}" is not recognized.{RESET}')
            return None

        pipeline_cls, readouts_attr = entry
        bm_readouts = getattr(reader, readouts_attr, None)
        if bm_readouts is None:
            print(f'{WARN}Beam Monitor flagged as active, but associated BM readouts '
                  f'("{readouts_attr}") are empty.{RESET}')
            return None

        return pipeline_cls(bm_readouts, parameters, config)