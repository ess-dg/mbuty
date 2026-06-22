#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbuty_new.py
============
High-Performance Master Ingestion Orchestrator for ESS Neutron Detectors.
"""

import os
import sys
import time
import json
from types import SimpleNamespace

# Ingest new high-performance architecture modules
from newLib.reader import PcapngFileReader
from newLib.kafka_reader import KafkaReader
from newLib.calibration import load_calibration_map
from newLib.colors import INFO, OK, WARN, ERR, RESET

# Ingest legacy file resolver as an isolated asset
from lib.libFileManagmentUtil import fileDialogue
import newLib.libParameters as para


class MBUTYOrchestrator:
    """
    Main pipeline orchestrator managing data lifecycle:
    Path resolution -> Ingestion -> Telemetry Checking -> Calibration.
    """
    def __init__(self, parameters, run_from_gui: bool = False):
        self.parameters = parameters
        self.run_from_gui = run_from_gui
        
        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        print('----------------------------------------------------------------------')
        print(f'{INFO}Ciao {user_name}! Welcome to MBUTY 8.3 {RESET}')
        print('----------------------------------------------------------------------')
        
        # Load JSON geometry and instrument configuration mappings
        config_path = os.path.join(
            self.parameters.fileManagement.configFilePath,
            self.parameters.fileManagement.configFileName
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

    def run_pipeline(self) -> None:
        """Executes the ingestion and preprocessing stages of the data reduction line."""
        
        # 1. Pipeline Branch: Network Live Kafka Stream vs Disk Storage Files
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
            # Execute legacy path selection utility to resolve self.parameters.fileManagement.fileName
            file_resolver = fileDialogue(self.parameters)
            file_resolver.openFile()
            
            # Guard against empty selection passes
            if not file_resolver.fileName:
                print(f'{ERR}Pipeline Aborted: No valid target files found.{RESET}')
                return
                
            # Iterate through resolved sequence of pcapng target files
            for idx, filename in enumerate(file_resolver.fileName):
                print(f'{INFO}\nProcessing file [{idx + 1}/{len(file_resolver.fileName)}]: {filename}{RESET}')
                
                full_file_path = os.path.join(file_resolver.filePath, filename)
                
                reader = PcapngFileReader(
                    file_path  = full_file_path,
                    parameters = self.parameters,
                    config     = self.config
                )
                reader.run()

        # 2. In-Place Vectorized Calibration Pass
        # Currently executed on the normal data container; can be expanded across flavors.
        if getattr(self.parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', False):
            print(f'{INFO}Initiating vectorized hardware calibration pass...{RESET}')
            reader.readouts_vmm_normal.calibrate(self.parameters, self.config)

        # Expose active data containers for upstream reduction blocks (Mapping, Clustering)
        self.readouts_vmm_normal = reader.readouts_vmm_normal
        print(f'{OK}\nIngestion and Calibration Stage Complete.{RESET}')


if __name__ == '__main__':
    # Workspace bootstrap stub mimicking standalone standalone testing parameters
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    params = para.parameters(current_dir)
    
    # Configure run environment profiles
    params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
    params.fileManagement.configFileName = "AMOR26.json"
    params.acqMode = 'off'  # Set to 'kafka' to trigger live network streaming
    params.fileManagement.pcapLoadingMethod = 'allocate'
    params.dataReduction.calibrateVMM_ADC_ONOFF = True
    params.fileManagement.calibFilePath = os.path.join(current_dir, 'calib') + os.sep
    params.fileManagement.calibFileName = "AMOR_calib.json"
    
    pipeline = MBUTYOrchestrator(params)
    pipeline.run_pipeline()