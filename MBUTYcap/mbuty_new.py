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
# Ingest new high-performance architecture modules
from newLib.reader import PcapngFileReader
from newLib.kafka_reader import KafkaReader
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
            self.detector_pipeline.execute()

        # 3. Conditionally Dispatch Beam Monitor Tracking Stream
        self.bm_pipeline = build_bm_pipeline(self.config, reader, self.parameters)
        if self.bm_pipeline:
            print(f'{OK}Executing verified pipeline track for Beam Monitor: {self.config.get("bm_hardware_type", "generic")}{RESET}')
            self.bm_pipeline.execute()


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

    # Run backend scientific computation track. Each pipeline's plot() runs
    # as part of execute(), as a side effect of analysis completing --
    # nothing else in this file decides what gets shown.
    pipeline_orchestrator = MBUTYOrchestrator(params)
    pipeline_orchestrator.run_pipeline()

    import matplotlib.pyplot as plt
    print(f"{INFO}\nPlots ready. Close the figure windows to continue...{RESET}")
    plt.show()  # blocks until every open figure window is closed