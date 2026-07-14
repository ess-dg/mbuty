#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipelines.py
============
Object-Oriented Pipeline Tracks for ESS Neutron Detectors.

Routing model
-------------
build_detector_pipeline() / build_bm_pipeline() are plain if/elif dispatchers:
they look at detector_type (+ opMode, for VMM hardware) or bm_hardware_type,
pick the matching pipeline class and readouts container off `readout_source`,
and return a ready-to-execute pipeline instance (or None, having already
printed/exited on any error). This is the *only* place config gets inspected
to make this decision -- callers never re-derive any of that themselves.

To add a new detector: copy the closest branch in build_detector_pipeline()
and the closest pipeline class, then adjust the mapper/clusterer/plotter
names. No registry table to update anywhere else.

Two independent pipeline families
----------------------------------
Detector pipelines (MB / MB-clustered / MG / He3 / SKADI) all go through
BasePipeline. They share a mapping -> clustering -> abs-units analyze()
shape, and -- because the physicist's plotting parameters mean the same
thing regardless of which of these detectors is active -- they share a
single plot() if-chain, written once on BasePipeline itself.

Beam Monitor pipelines (Generic BM / IBM) do NOT go through BasePipeline
at all. They don't cluster (mapping goes straight to events), they have
no hits stage, and only two plots exist for them, gated by MONitor
parameters that don't apply to any detector pipeline. Forcing them through
the detector if-chain would mean reading fifteen checks against fields
that don't exist for a monitor stream just to find the two that matter --
so BeamMonitorPipeline is its own small, standalone base class with its
own analyze()/plot()/execute(), duplicating the trivial empty-container
guard rather than sharing it. Tracing "what does the beam monitor do" now
means opening exactly one self-contained class hierarchy.

Pipeline shape (detector pipelines)
------------------------------------
    analyze()        readouts -> hits -> events (mapping, clustering, abs
                      units). Populates self.hits_container /
                      self.events_container.
    build_plotters()  constructs the axis set and the three plotter
                      objects from whatever analyze() produced. No
                      plotting decisions here -- construction only.
    plot()            defined once, on BasePipeline: builds the plotters,
                      then walks parameters.plotting / .wavelength /
                      .pulseHeigthSpect exactly once and calls whichever
                      plot_* methods are switched on. A detector whose
                      plotter doesn't implement a given plot_* method is
                      safe -- it just falls through to that stage's base
                      stub (prints "not supported", does nothing).

execute() (defined once per family) runs analyze() then plot(), after
checking the readouts container isn't empty. Callers normally only ever
call execute(); analyze()/plot() are there as a seam for anyone who wants
to run analysis without plotting (batch jobs, notebooks, etc).

Each pipeline lazily imports the mapper/clusterer/plotter modules it
actually needs, inside analyze()/build_plotters(), so an inactive pipeline
never pays for imports it doesn't use.
"""
import os
import sys
import matplotlib.pyplot as plt
import numpy as np 

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib.colors import INFO, WARN, ERR, RESET

def _chunk(seq: list, size: int) -> list:
    size = max(1, int(size))
    return [seq[i:i + size] for i in range(0, len(seq), size)]
# =============================================================================
# Detector pipelines (MB / MB-clustered / MG / He3 / SKADI)
# =============================================================================

class BasePipeline:
    """Non-negotiable contract for all detector hardware instrument workflows.

    Subclasses implement analyze() (the science) and build_plotters() (just
    constructing the three plotter objects). plot() is shared -- it is the
    *only* place parameters.plotting/.wavelength/.pulseHeigthSpect get read
    to decide what to show, so every detector runs the exact same checklist
    and nothing is duplicated per subclass. execute() is shared too and
    should not need to be overridden.
    """
    def __init__(self, readouts_container, parameters, config: dict):
        self.readouts_container = readouts_container
        self.parameters = parameters
        self.config = config
        
        self.out_of_bounds = self.parameters.plotting.histogOutBounds

        # Filled in by analyze()
        self.hits_container = None
        self.events_container = None

        # Filled in by build_plotters()
        self.readout_plotter = None
        self.hit_plotter = None
        self.event_plotter = None
        self.axis_set = None

    def analyze(self) -> None:
        raise NotImplementedError

    def build_plotters(self) -> None:
        """Subclasses set self.readout_plotter / hit_plotter / event_plotter
        here -- construction only, no plotting decisions."""
        raise NotImplementedError

    def make_plots(self, unit_ids=None) -> None:
        """The one and only place plotting parameters get read. A call to a
        given detector's plotter that isn't implemented just falls through
        to that plotter's inherited stub (prints a "not supported" notice,
        does nothing) instead of needing to be listed or excluded here.

        unit_ids, if given, scopes every per-cassette/per-tube panel plot
        to that block (used by run_detector_pipeline() in mbuty_new.py for
        plottingInSections). It is only ever passed to the per-unit panel
        calls -- the whole-detector composite images (plot_xy, plot_tof_xy,
        plot_x_lambda, plot_position_per_tube) never accepted a unit_ids
        argument in the first place, so they're left unconditional here.
        """
        
        self.parameters.validateHistNotification()
        
        self.build_plotters(unit_ids)

        p = self.parameters.plotting
        w = self.parameters.wavelength
        phs = self.parameters.pulseHeigthSpect

        if self.readout_plotter is not None:
            if p.plotChopperResets:
                self.readout_plotter.plot_chopper_resets()
            if p.plotRawReadouts:
                self.readout_plotter.plot_channels_raw()
            if p.plotReadoutsTimeStamps:
                self.readout_plotter.plot_timestamps()
            if p.plotADCvsCh:
                self.readout_plotter.plot_adc_vs_channel()

        # Matches legacy: bareReadoutsCalculation stops at readouts, no
        # hits/events plots at all.
        if p.bareReadoutsCalculation:
            return

        if self.hit_plotter is not None:
            if p.plotRawHits:
                self.hit_plotter.plot_channels_raw()
            if p.plotHitsTimeStamps:
                self.hit_plotter.plot_timestamps()
            if p.plotHitsTimeStampsVSChannels:
                self.hit_plotter.plot_timestamps_vs_channel()

        if self.event_plotter is not None:
            # Each detector defines the plots that are always shown for that detector
            self.plot_always()

            if p.plotToFDistr:
                self.event_plotter.plot_tof()
            if w.plotXLambda:
                self.event_plotter.plot_x_lambda()
            if w.plotLambdaDistr:
                self.event_plotter.plot_lambda()
            if p.plotMultiplicity:
                self.event_plotter.plot_multiplicity()
            if phs.plotPHS:
                self.event_plotter.plot_phs()
            if phs.plotPHScorrelation:
                self.event_plotter.plot_phs_correlation()
            if p.plotTimeBetwEv:
                self.event_plotter.plot_time_between_events()

    def plot_always(self):
        """Plots that are always show no matter the detector. 
        Subclasses can overwrite this function and add more plots"""
        self.event_plotter.plot_xy()
        self.event_plotter.plot_tof_xy()

    def plot_section(self, unit_ids) -> None:
        """Plots a single section (one block of unit IDs), closing the
        previous section's figures first. Shared by execute()'s CLI loop
        and, later, a GUI's per-click handler."""
        plt.close('all')
        self.make_plots(unit_ids=unit_ids)
        plt.show(block=False)
        
    def check_empty(self):
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}{type(self).__name__}: readouts container is empty — skipping pipeline pass.{RESET}")
            return

    def plot(self, run_from_gui: bool = False) -> None:
        """Runs either a single make_plots() pass or, when
        parameters.plotting.plottingInSections is set, a per-block
        sectioned pass -- mirrors legacy's plottingInSections behaviour,
        including 'q' to quit early in CLI mode.

        run_from_gui=True skips the console input()/sys.exit step-through:
        every section still gets plotted, just without blocking on stdin.
        Once a GUI exists it should drive sectioning itself (build_plotters()
        + readout_plotter.topology_unit_ids() + plot_section() per click)
        rather than calling this with run_from_gui=True; the flag is a
        stopgap for the interim.
        """
        topology = self.config.get('topology', [])
        unit_ids = [entry['ID'] for entry in topology]
                
        # sort here to have plots sorted by ID ascending otherwise as they are in config file 
        unit_ids     = np.sort(unit_ids)
        
        if not self.parameters.plotting.plottingInSections:
            self.make_plots(unit_ids)
            return
        
        blocks = _chunk(unit_ids, self.parameters.plotting.plottingInSectionsBlocks)

        print(f'{INFO}\nPlotting in {len(blocks)} section(s) of '
              f'{self.parameters.plotting.plottingInSectionsBlocks} unit(s) each.{RESET}')

        for i, block in enumerate(blocks):
            print(f'{INFO}\n\tSection {i + 1}/{len(blocks)} -- unit IDs {block[0]} to {block[-1]}{RESET}')
            self.plot_section(block)

            if run_from_gui or i == len(blocks) - 1:
                continue

            plt.pause(0.5)
            answer = input('press (enter) to continue to the next section, or (q + enter) to quit: ')
            if answer.strip().lower() == 'q':
                plt.close('all')
                sys.exit(0)


class MBPipeline(BasePipeline):
    """Multi-Blade hardware, normal mode."""
    def analyze(self) -> None:
        
        self.check_empty()
        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            # Calibrate readouts 
            self.readouts_container.calibrate(self.parameters, self.config)

        # Mapping
        from lib.mapping_engine import MBMapper
        print(f"{INFO}Mapping MB detector (units mapped according to IDs){RESET}")
        self.hits_container = MBMapper.map(self.readouts_container, self.config)
        # Clustering 
        from lib.clustering_engine import VMMNormalClusterer
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 0.15e-6)
        self.events_container = VMMNormalClusterer.cluster(self.hits_container, self.config, time_window)
        # Calculate abs units
        from lib.abs_units_engine import MBAbsUnitsCalculator

        
        MBAbsUnitsCalculator(self.events_container, self.config, self.parameters).process_pipeline(remove_invalid_tofs=self.parameters.plotting.removeInvalidToFs)
        # Apply soft thresholds
        from lib.threshold_engine import VMMThresholdEngine
        VMMThresholdEngine(self.events_container, self.config, self.parameters).process_pipeline()
        
    def build_plotters(self, unit_ids) -> None:
        from lib.histograms import MBAxisSet
        self.axis_set = MBAxisSet(self.parameters, self.config)
        from lib.plotting_readouts import MBReadoutsPlotter
        self.readout_plotter = MBReadoutsPlotter(self.readouts_container, self.parameters, self.config, self.axis_set, unit_ids)

        if self.hits_container is not None: 
            from lib.plotting_hits import MBHitsPlotter
            self.hit_plotter     = MBHitsPlotter(self.hits_container, self.parameters,self.config, self.axis_set,unit_ids)
        
        if self.events_container is not None: 
            from lib.plotting_events import MBEventsPlotter
            self.event_plotter   = MBEventsPlotter(self.events_container, self.parameters,self.config, self.axis_set, unit_ids)


class MBClusteredPipeline(BasePipeline):
    """Pre-clustered VMM3A hardware tracking streams (opMode == 'clustered').
    MB-only for now -- MG has no clustered track yet.

    VMMClusteredClusterer is a firmware passthrough (the ASIC already did the
    time-window clustering on-board), so analyze() is: map -> passthrough
    absorb -> abs units. Same shape as MBPipeline, just missing the
    VMMNormalClusterer stage since there's nothing left for software to cluster.
    """

    def analyze(self) -> None:
        self.check_empty()
        # No calibration for clustered pipeline go straight into 
        # Mapping
        from lib.mapping_engine import MBClustMapper
        print(f"{INFO}Mapping MB detector clustered (units mapped according to IDs){RESET}")
        self.hits_container = MBClustMapper.map(self.readouts_container, self.config)
        # Clustering 
        from lib.clustering_engine import VMMClusteredClusterer
        self.events_container = VMMClusteredClusterer.cluster(self.hits_container, self.config)
        # Calculate abs units
        from lib.abs_units_engine import MBAbsUnitsCalculator
        MBAbsUnitsCalculator(self.events_container, self.config, self.parameters).process_pipeline(remove_invalid_tofs=self.parameters.plotting.removeInvalidToFs)
        # Apply soft thresholds
        from lib.threshold_engine import VMMThresholdEngine
        VMMThresholdEngine(self.events_container, self.config, self.parameters).process_pipeline()

    def build_plotters(self, unit_ids) -> None:
        from lib.histograms import MBAxisSet
        self.axis_set = MBAxisSet(self.parameters, self.config)

        from lib.plotting_readouts import MBReadoutsPlotter
        self.readout_plotter = MBReadoutsPlotter(self.readouts_container, self.parameters,self.config, self.axis_set, unit_ids)

        if self.hits_container is not None:
            from lib.plotting_hits import MBClusteredHitsPlotter
            self.hit_plotter = MBClusteredHitsPlotter(self.hits_container, self.parameters,self.config, self.axis_set, unit_ids)
        if self.events_container is not None:
            from lib.plotting_events import MBEventsPlotter
            self.event_plotter = MBEventsPlotter(self.events_container, self.parameters,self.config, self.axis_set, unit_ids)


class MGPipeline(BasePipeline):
    """Multi-Grid hardware, normal mode."""

    def analyze(self) -> None:
        self.check_empty()
        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            # Calibrate readouts 
            self.readouts_container.calibrate(self.parameters, self.config)
        # Mapping
        from lib.mapping_engine import MGMapper
        print(f"{INFO}Mapping MG detector (units mapped according to IDs){RESET}")
        self.hits_container = MGMapper.map(self.readouts_container, self.config)
        # Clustering
        from lib.clustering_engine import VMMNormalClusterer
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 0.2e-6)
        self.events_container = VMMNormalClusterer.cluster(self.hits_container, self.config, time_window)
        # Calculate abs units
        from lib.abs_units_engine import MGAbsUnitsCalculator
        MGAbsUnitsCalculator(self.events_container, self.config, self.parameters).process_pipeline(remove_invalid_tofs=self.parameters.plotting.removeInvalidToFs)
        # Apply soft thresholds
        from lib.threshold_engine import VMMThresholdEngine
        VMMThresholdEngine(self.events_container, self.config, self.parameters).process_pipeline()

    def build_plotters(self,unit_ids) -> None:
        from lib.histograms import MGAxisSet
        self.axis_set = MGAxisSet(self.parameters, self.config)

        from lib.plotting_readouts import MGReadoutsPlotter
        self.readout_plotter = MGReadoutsPlotter(self.readouts_container, self.parameters,self.config, self.axis_set, unit_ids)

        if self.hits_container is not None:
            from lib.plotting_hits import MGHitsPlotter
            self.hit_plotter = MGHitsPlotter(self.hits_container, self.parameters,self.config, self.axis_set, unit_ids)
        if self.events_container is not None:
            from lib.plotting_events import MGEventsPlotter
            self.event_plotter = MGEventsPlotter(self.events_container, self.parameters,self.config, self.axis_set,unit_ids)


class R5560Pipeline(BasePipeline):
    """CAEN R5560 Helium-3 gas tube detectors."""

    def analyze(self) -> None:
        self.check_empty()
        # Mapping
        from lib.mapping_engine import He3Mapper
        print(f"{INFO}Mapping He3 detector (units mapped according to IDs){RESET}")
        self.hits_container = He3Mapper.map(self.readouts_container, self.config)
        # Clustering
        from lib.clustering_engine import R5560Clusterer
        time_window = getattr(self.parameters.dataReduction, 'timeWindow', 1e-6)
        self.events_container = R5560Clusterer.cluster(self.hits_container, self.config, time_window)
        # absolute units 
        from lib.abs_units_engine import R5560AbsUnitsCalculator
        R5560AbsUnitsCalculator(self.events_container, self.config, self.parameters).process_pipeline(remove_invalid_tofs=self.parameters.plotting.removeInvalidToFs)
        # Apply soft thresholds
        from lib.threshold_engine import TubeThresholdEngine
        TubeThresholdEngine(self.events_container, self.config, self.parameters).process_pipeline()

    def build_plotters(self,unit_ids) -> None:
        from lib.histograms import R5560AxisSet
        self.axis_set = R5560AxisSet(self.parameters, self.config)

        from lib.plotting_readouts import R5560ReadoutsPlotter
        self.readout_plotter = R5560ReadoutsPlotter(self.readouts_container, self.parameters,self.config, self.axis_set,unit_ids)

        if self.hits_container is not None:
            from lib.plotting_hits import R5560HitsPlotter
            self.hit_plotter = R5560HitsPlotter(self.hits_container, self.parameters,self.config, self.axis_set,unit_ids)

        if self.events_container is not None:
            from lib.plotting_events import R5560EventsPlotter
            self.event_plotter = R5560EventsPlotter(self.events_container, self.parameters,self.config, self.axis_set,unit_ids)
  

    def plot_always(self):
        super().plot_always()
        self.event_plotter.plot_position_per_tube()

class SkadiPipeline(BasePipeline):
    """SKADI detector layout streams -- not yet implemented."""

    def analyze(self) -> None:
        print(f'{INFO}SKADI pipeline not yet implemented...{RESET}')

    def build_plotters(self,unit_ids) -> None:
        pass

    def plot(self) -> None:
        pass


# =============================================================================
# Beam Monitor pipelines -- independent of BasePipeline entirely
# =============================================================================

class BeamMonitorPipeline:
    """Non-negotiable contract for beam-monitor workflows.

    Deliberately does NOT inherit BasePipeline: monitors map straight to
    events (no hits stage, no clustering), and only two plots exist for
    them (plot_tof_phs_mon, plot_lambda_mon), gated by parameters.MONitor
    rather than the detector-side plotting/wavelength/pulseHeigthSpect
    checklist. Sharing BasePipeline here would mean tracing a monitor's
    behaviour through a 15-branch if-chain built for a different kind of
    hardware -- worse than the small amount of duplication below (an
    __init__ and an empty-container guard, both a few lines).

    Subclasses implement analyze() (map -> ToF/wavelength) and
    build_plotter() (construct self.event_plotter). plot() is shared here
    since both monitor hardware types show exactly the same two plots.
    """

    def __init__(self, readouts_container, parameters, config: dict):
        self.readouts_container = readouts_container
        self.parameters = parameters
        self.config = config

        self.events_container = None
        self.event_plotter = None

    def analyze(self) -> None:
        raise NotImplementedError

    def build_plotter(self) -> None:
        from lib.histograms import BaseAxisSet
        self.axis_set = BaseAxisSet(self.parameters, self.config)
        if self.events_container is not None:
            from lib.plotting_events import MonitorEventsPlotter
            self.event_plotter = MonitorEventsPlotter(self.events_container, self.parameters, self.config, self.axis_set, [])

    def plot(self) -> None:
        self.build_plotter()
        if self.event_plotter is not None:
            if self.parameters.MONitor.plotMONtofPHS:
                self.event_plotter.plot_tof_phs_mon()
                if self.parameters.wavelength.plotLambdaDistr:
                    self.event_plotter.plot_lambda_mon()
            
                
    def check_empty(self):
        if self.readouts_container.fill_count == 0:
            print(f"{WARN}\t WARNING: BM readouts container is empty — skipping pipeline: {type(self).__name__}.{RESET}")
            return
# not used anymore
    # def execute(self) -> None:
    #     self.check_empty()
    #     self.analyze()
    #     self.plot()


class GenericBMPipeline(BeamMonitorPipeline):
    """Generic Beam Monitor. BMMapper maps readouts straight into a
    fully-formed eventsBM container. A lightweight abs-units pass then
    fills in ToF (generic, from the events base class) and wavelength
    (monitor-specific: fixed distance, no depth correction) before plotting."""

    def analyze(self) -> None:

        self.check_empty()
        # Map directly into events
        from lib.mapping_engine import BMMapper
        
        self.events_container = BMMapper.map(self.readouts_container, self.config)
        print(f'{INFO}Calculating Beam Monitor ToF/wavelength...{RESET}')
        self.events_container.compute_and_filter_tof(remove_invalid=True)
        if self.parameters.wavelength.calculateLambda:
            from lib.abs_units_engine import calculate_monitor_wavelength
            calculate_monitor_wavelength(self.events_container, self.parameters)
            
        # Apply monitor thresholds 
        from lib.threshold_engine import apply_monitor_threshold
        apply_monitor_threshold(self.events_container, self.parameters.MONitor.MONThreshold)


class IBMPipeline(BeamMonitorPipeline):
    """Ionization Beam Monitor. IBMMonitorMapper maps readouts straight into
    a fully-formed eventsIBM container, then the same generic ToF +
    monitor-wavelength pass runs before plotting."""

    def analyze(self) -> None:
        
        self.check_empty()
        # Map directly into events
        from lib.mapping_engine import IBMMonitorMapper
        self.events_container = IBMMonitorMapper.map(self.readouts_container, self.config)

        print(f'{INFO}Calculating Beam Monitor ToF/wavelength...{RESET}')
        self.events_container.compute_and_filter_tof(remove_invalid=True)
        if self.parameters.wavelength.calculateLambda:
            from lib.abs_units_engine import calculate_monitor_wavelength
            calculate_monitor_wavelength(self.events_container, self.parameters)
            
        # Apply monitor thresholds 
        from lib.threshold_engine import apply_monitor_threshold
        apply_monitor_threshold(self.events_container, self.parameters.MONitor.MONThreshold)


# =============================================================================
# Dispatchers -- plain if/elif, no registry table
# =============================================================================

def build_detector_pipeline(config: dict, readout_source, parameters) -> BasePipeline | None:
    """Picks the pipeline class + matching readouts container for this
    config's detector_type (+ opMode, for VMM hardware), and returns a
    ready-to-execute pipeline instance. Fatal misconfiguration exits; a
    merely unpopulated readouts container is still returned -- execute()
    itself is what prints the warning and skips.

    To add a new detector, add a branch here and a matching pipeline class
    above. Nothing else in the codebase needs to change.

    opMode is only ever consulted for MB -- MG, He3, and SKADI don't have
    a clustered/normal distinction in hardware, so their branches never
    look at op_mode at all.
    """
    detector_type = config.get('detectorType')
    op_mode = config.get('operationMode', 'normal')
    
    if detector_type == 'MB' and op_mode == 'normal':
        pipeline_cls, readouts_container = MBPipeline, readout_source.readouts_vmm_normal

    elif detector_type == 'MB' and op_mode == 'clustered':
        pipeline_cls, readouts_container = MBClusteredPipeline, readout_source.readouts_vmm_clustered

    elif detector_type == 'MG':
        pipeline_cls, readouts_container = MGPipeline, readout_source.readouts_vmm_normal

    elif detector_type == 'He3':
        pipeline_cls, readouts_container = R5560Pipeline, readout_source.readouts_r5560

    elif detector_type == 'SKADI':
        pipeline_cls, readouts_container = SkadiPipeline, readout_source.readouts_skadi

    else:
        print(f'\n{ERR}FATAL ERROR: Configuration mismatch. detector_type "{detector_type}" '
              f'/ opMode "{op_mode}" is not recognized by the pipeline dispatcher. Exit.{RESET}')
        sys.exit(1)

    return pipeline_cls(readouts_container, parameters, config)


def build_bm_pipeline(config: dict, readout_source, parameters) -> BeamMonitorPipeline | None:
    """Picks the beam-monitor pipeline class + matching readouts container
    for this config's bm_hardware_type. Returns None (no pipeline to run)
    whenever the beam monitor isn't flagged as present at all, or its
    hardware type isn't recognized.
    """
    if not config.get('monitor', False):
        return None
    
    monitor_list = config.get('monitor') or [{}]

    bm_hardware_type = monitor_list[0].get('hardwareType', 'generic').lower()

    if bm_hardware_type == 'ibm':
        pipeline_cls, readouts_container = IBMPipeline, readout_source.readouts_ibm
        

    elif bm_hardware_type == 'generic':
 
        pipeline_cls, readouts_container = GenericBMPipeline, readout_source.readouts_bm

    else:
        print(f'{WARN}WARNING: Beam monitor type "{bm_hardware_type}" is not recognized.{RESET}')
        return None

    return pipeline_cls(readouts_container, parameters, config)