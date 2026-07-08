#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbuty_new.py
============
High-Performance Master Ingestion Orchestrator for ESS Neutron Detectors.
"""

import os
import sys
import json
from collections import defaultdict
from types import SimpleNamespace
import matplotlib.pyplot as plt
# Ingest new high-performance architecture modules
from newLib.reader import PcapngFileReader
from newLib.colors import INFO, OK, WARN, ERR, RESET

# Ingest object-oriented pipeline tracks and their factory dispatchers
from newLib.pipelines import build_detector_pipeline, build_bm_pipeline

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
        
        plt.close('all')
        
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
            from newLib.kafka_reader import KafkaReader
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
            print(self.parameters.fileManagement.fileName)
            file_resolver = fileDialogue(self.parameters)
            file_resolver.openFile()
            print(file_resolver.fileName)

            if not file_resolver.fileName:
                print(f'{ERR}Pipeline Aborted: No valid target files found.{RESET}')
                return

            container_lists = defaultdict(list)

            for idx, filename in enumerate(file_resolver.fileName):
                print(f'{INFO}\nProcessing file [{idx + 1}/{len(file_resolver.fileName)}]: {filename}{RESET}')
                full_file_path = os.path.join(file_resolver.filePath, filename)

                reader = PcapngFileReader(
                    file_path  = full_file_path,
                    parameters = self.parameters,
                    config     = self.config
                )
                for name, container in reader.run().items():
                    container_lists[name].append(container)
                # `reader` is rebound next iteration and dropped -- nothing
                # about it survives except the containers pulled into
                # container_lists above.

            merged = {
                name: containers[0] if len(containers) == 1 else type(containers[0]).merge(containers)
                for name, containers in container_lists.items()
            }
            reader = SimpleNamespace(**merged)

        # 2. Detector Pipeline Track Instantiation & Execution Pass via Factory
        self.detector_pipeline = build_detector_pipeline(self.config, reader, self.parameters)
        if self.detector_pipeline:
            print(f'{OK}Executing verified pipeline reduction track for: {self.config.get("detectorType")}{RESET}')
            self.detector_pipeline.execute(run_from_gui=self.run_from_gui)

        # 3. Conditionally Dispatch Beam Monitor Tracking Stream
        self.bm_pipeline = build_bm_pipeline(self.config, reader, self.parameters)
        if self.bm_pipeline:
            print(f'{OK}Executing verified pipeline track for Beam Monitor: {self.config.get("bm_hardware_type", "generic")}{RESET}')
            self.bm_pipeline.execute()

        
        plt.draw() 
        plt.pause(0.1)
        plt.show(block=False)
        input(f"{INFO}\nPress Enter to close all figures...{RESET}")
        plt.close('all')
        
        self.readouts_container = self.detector_pipeline.readouts_container
        self.hits_container     = self.detector_pipeline.hits_container
        self.events_container   = self.detector_pipeline.events_container


def _enable_all_plots(params) -> None:
    """Test-only helper: flips on every plotting flag BasePipeline.plot()
    and BeamMonitorPipeline.plot() check, so a single test run exercises
    every plot_* method across every plotter. Not meant for routine use --
    routine runs should set only the flags you actually want."""
    p, w, phs, mon = params.plotting, params.wavelength, params.pulseHeigthSpect, params.MONitor

    p.plotChopperResets            = True
    p.plotRawReadouts              = False
    p.plotReadoutsTimeStamps       = False
    p.plotADCvsCh                  = False

    p.plotRawHits                  = False
    p.plotHitsTimeStamps           = False
    p.plotHitsTimeStampsVSChannels = False

    p.plotToFDistr                 = False
    p.plotMultiplicity             = False
    p.plotTimeBetwEv               = False

    phs.plotPHS                    = True
    phs.plotPHScorrelation         = False

    # calculateLambda has to be True for plotXLambda/plotLambdaDistr to have
    # real wavelength data to plot -- it's what triggers the wavelength calc
    # in analyze(), not just a display toggle.
    w.calculateLambda              = False
    w.plotXLambda                  = False
    w.plotLambdaDistr              = False

    # Only takes effect if a beam monitor stream is actually present in the file.
    mon.plotMONtofPHS              = False

    # bareReadoutsCalculation off, or everything past readouts gets skipped.
    p.bareReadoutsCalculation      = False


if __name__ == '__main__':
    import numpy as np 
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    params = para.parameters(current_dir)

    params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
    params.fileManagement.configFileName = "AMOR.json"
    params.fileManagement.fileName = "ESSmask2023.pcapng"
    params.fileManagement.openMode = "fileName"
    params.acqMode = 'off'
    params.fileManagement.pcapLoadingMethod = 'allocate'
    params.dataReduction.calibrateVMM_ADC_ONOFF = False
    params.fileManagement.calibFilePath = os.path.join(current_dir, 'calib') + os.sep
    params.fileManagement.calibFileName = "AMOR_calib.json"
    params.plotting.plottingInSections = False
    params.plotting.plottingInSectionsBlocks = 5
    params.dataReduction.timeWindow = 0.127e-6
    params.plotting.ToFrange        = 0.15
    params.plotting.timeBetwEvBin = 1e-6
    
    params.plotting.histogOutBounds = True
    
    _enable_all_plots(params)

  
    
    params.dataReduction.softThresholdType = 'userDefined'
    # params.dataReduction.softThArray = (500, 700)
    params.dataReduction.softThArray = {
        5: {'ch0': np.full(32, 1000.0)},   # cassette 1, wire thresholds only
        6: {'ch0': np.full(32, 500.0), 'ch1': np.full(64, 700.0)},
    }
    # Run backend scientific computation track. Each pipeline's plot() runs
    # as part of execute(), as a side effect of analysis completing --
    # nothing else in this file decides what gets shown.
    pipeline_orchestrator = MBUTYOrchestrator(params)
    pipeline_orchestrator.run_pipeline()
    
    readouts = pipeline_orchestrator.readouts_container
    readoutsArray = readouts.get_data_frame()
    hits = pipeline_orchestrator.hits_container
    hitsArray = hits.get_data_frame()
    events = pipeline_orchestrator.events_container
    eventsArray = events.get_data_frame()
    


# Need to set this somewhere!!!
# n_wires  = int(config['wires'])
# n_strips = int(config['strips'])
# unit_ids = [e['ID'] for e in config['topology']]

# parameters.dataReduction.softThresholdType = 'userDefined'
# parameters.dataReduction.softThArray = {
#     uid: {
#         'ch0': np.full(n_wires,  700.0),
#         'ch1': np.full(n_strips, 1000.0),
#     }
#     for uid in unit_ids
# }
