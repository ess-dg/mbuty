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
from lib.reader import PcapngFileReader
from lib.colors import INFO, OK, WARN, ERR, RESET
import lib.checks_and_helpers as checks

# Ingest object-oriented pipeline tracks and their factory dispatchers
from lib.pipelines import build_detector_pipeline, build_bm_pipeline

# Ingest legacy file resolver as an isolated asset
from lib.file_managment import fileDialogue
import lib.parameters as para

# =============================================================================
# Master Ingestion Orchestrator
# =============================================================================

class MBUTYOrchestrator:
    """
    Main pipeline orchestrator managing data lifecycle:
    Path resolution -> Ingestion -> Guarded Multi-Key Routing -> Execution.
    """
    def __init__(self, parameters, run_from_gui: bool = False, main_thread_queue = None):
        self.main_thread_queue = main_thread_queue
        self.run_from_gui      = run_from_gui
        # NOTE: plot split out of exectute for run gui 
        
        self.parameters = parameters
        self.parameters.validate()
        
        self.timing  = checks.timing()

        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        print('----------------------------------------------------------------------')
        print(f'{INFO}Ciao {user_name}! Welcome to MBUTY 8.0 {RESET}')
        print('----------------------------------------------------------------------')
        plt.close('all')
        
        ### check version ###
        checks.checkPythonVersion()
        # # check packages installation 
        # check = para.checkPackageInstallation()
        # check.checkPackagePcap()
        
        
        config_path = os.path.join(
            self.parameters.fileManagement.configFilePath,
            self.parameters.fileManagement.configFileName
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.detector_pipeline = None
        self.bm_pipeline       = None
        
        ###############################################################################
        ###############################################################################
        # if self.parameters.acqMode  == 'pcap-local-overwrite'  or self.parameters.acqMode  == 'pcap-local':
            
        #     rec = ta.dumpToPcapngUtil(self.parameters.fileManagement.pathToTshark, self.parameters.dumpSettings.interface, \
        #     self.parameters.dumpSettings.destTestData, self.parameters.dumpSettings.fileName)
        
        #     # sta = ta.acquisitionStatus(self.parameters.dumpSettings.destTestData)  
        #     # sta.set_RecStatus()
            
        #     status = rec.dump(self.parameters.dumpSettings.typeOfCapture,self.parameters.dumpSettings.quantity,self.parameters.dumpSettings.numOfFiles,\
        #     self.parameters.dumpSettings.delay,self.parameters.dumpSettings.fileNameOnly)
        #     # if status == 0: 
        #     #      sta.set_FinStatus()
        #     # else:
        #     #      sta.set_RecStatus()
        
        # ### sync the data folder from remote computer to local folder 
        # elif not self.runFromGui and self.parameters.acqMode == 'pcap-sync':
        #     transferData = ta.transferDataUtil()
        #     transferData.syncData(self.parameters.fileManagement.sourcePath, self.parameters.fileManagement.destPath)   
        

    def run_pipeline(self) -> None:
        """Executes data frame ingestion and routes targeted tracks via explicit type matching gates."""
        
        # 1. Pipeline Data Ingestion Pass (Network Stream vs Disk Storage)
        if self.parameters.acqMode == 'kafka':
            # check kafka packages are installed, exit if not
            checks.checkPackageKafka()
            
            from lib.kafka_reader import KafkaReader
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
                # save containers, ovewrite reader in each pass

            merged = { # merge the lists of saved containers if you had multiple files
                name: containers[0] if len(containers) == 1 else type(containers[0]).merge(containers)
                for name, containers in container_lists.items()
            }
            reader = SimpleNamespace(**merged)

        # NOTE --- split this into analyze then plot!!!!
        # 2. Detector Pipeline Track Instantiation & Execution Pass via Factory
        self.detector_pipeline = build_detector_pipeline(self.config, reader, self.parameters)
        if self.detector_pipeline:
            print(f'{OK}Executing verified pipeline reduction track for: {self.config.get("detectorType")}{RESET}')
            self.detector_pipeline.execute(run_from_gui=self.run_from_gui)

        # 3. Conditionally Dispatch Beam Monitor Tracking Stream
        self.bm_pipeline = build_bm_pipeline(self.config, reader, self.parameters)
        if self.bm_pipeline and self.parameters.MONitor.MONOnOff:
            print(f'{OK}Executing verified pipeline track for Beam Monitor: {self.config.get("bm_hardware_type", "generic")}{RESET}')
            self.bm_pipeline.execute()
        
        

        plt.draw() 
        plt.pause(0.1)
        plt.show(block=False)
        # input(f"{INFO}\nPress Enter to close all figures...{RESET}")
        # plt.close('all')
        
        self.readouts_container = self.detector_pipeline.readouts_container
        self.hits_container     = self.detector_pipeline.hits_container
        self.events_container   = self.detector_pipeline.events_container

          # SAVE EVENTS CONTAINES BM AND DET IN HDF5 FILE 
          
            ### save reduced data to hdf5
              
            # if self.parameters.fileManagement.saveReducedFileONOFF is True: 
                
            #     fileNameSave = saveH5.prepareReducedFileBaseName(fileDialogue.fileName)
                
            #     sav = saveH5.saveReducedDataToHDF(self.parameters,self.parameters.fileManagement.saveReducedPath,fileNameSave)
                
            #     if (self.parameters.MONitor.MONOnOff is True) and (self.MON.flagMONfound is True):
            #         sav.save(self.events,self.eventsMON)
            #     else:
            #         sav.save(self.events)
            
            
            
            # if self.runFromGui:       
            #     self.main_thread_queue.put(lambda: self.plotting())



# # Final plotting and display logic
# plt.show(block= False)
# self.profiling.stop()
# print('----------------------------------------------------------------------')


def _enable_all_plots(params) -> None:
    """Test-only helper: flips on every plotting flag BasePipeline.plot()
    and BeamMonitorPipeline.plot() check, so a single test run exercises
    every plot_* method across every plotter. Not meant for routine use --
    routine runs should set only the flags you actually want."""
    p, w, phs, mon = params.plotting, params.wavelength, params.pulseHeigthSpect, params.MONitor

    p.plotChopperResets            = False
    p.plotRawReadouts              = False
    p.plotReadoutsTimeStamps       = False
    p.plotADCvsCh                  = False

    p.plotRawHits                  = False
    p.plotHitsTimeStamps           = False
    p.plotHitsTimeStampsVSChannels = False

    p.plotToFDistr                 = False
    p.plotMultiplicity             = False
    p.plotTimeBetwEv               = False

    phs.plotPHS                    = False
    phs.plotPHScorrelation         = False

    # calculateLambda has to be True for plotXLambda/plotLambdaDistr to have
    # real wavelength data to plot -- it's what triggers the wavelength calc
    # in analyze(), not just a display toggle.
    w.calculateLambda              = True
    w.plotXLambda                  = True
    w.plotLambdaDistr              = True

    

    # bareReadoutsCalculation off, or everything past readouts gets skipped.
    p.bareReadoutsCalculation      = False

    mon.MONOnOff   = True
    mon.plotMONtofPHS = False
    mon.energyBins = 128
    mon.maxEnerg   = 1000
    
    mon.MONDistance = 23000
    
    w.distance     = 32000
    w.chopperPeriod = 0.12
    
    w.multipleFramePerReset = True
    w.numOfBunchesPerPulse = 2
    
    w.lambdaMIN = 2.1
    

if __name__ == '__main__':
    import numpy as np 
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    params = para.parameters(current_dir)

    params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
    params.fileManagement.configFileName = "AMOR.json"
    params.fileManagement.fileName = ["ESSmask2023.pcapng"]
    
    
    # params.fileManagement.fileName = ["file1_15pk.pcapng","4freia.pcapng","8badpkt.pcapng",'file2_6pk.pcapng']
    
    
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
    params.plotting.timeBetwEvBin   = 1e-6
    
    params.timeSettings.sortReadoutsByTimeStampsONOFF = True


    params.plotting.histogOutBounds = True
    
    _enable_all_plots(params)

  
    
    params.dataReduction.softThresholdType = 'fromFile'
    params.fileManagement.thresholdFilePath = r'C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap\config'
    params.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'
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
    
    config = pipeline_orchestrator.config
    


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
