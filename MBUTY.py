#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbuty_new.py
============
High-Performance Master Ingestion Orchestrator for ESS Neutron Detectors.
"""

import os
import sys
import numpy as np
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

class MBUTYOrchestrator():
    """
    Main pipeline orchestrator managing data lifecycle:
    Path resolution -> Ingestion -> Guarded Multi-Key Routing -> Execution.
    """
    def __init__(self, parameters, run_from_gui: bool = False, main_thread_queue = None):
        self.main_thread_queue = main_thread_queue
        self.run_from_gui      = run_from_gui
        # NOTE: plot split out of exectute for run gui 

        self.parameters = parameters
        # self.parameters.validate()
        
        self.timing  = checks.timing()

        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        print('----------------------------------------------------------------------')
        print(f'{INFO}Ciao {user_name}! Welcome to MBUTY 8.0 {RESET}')
        print('----------------------------------------------------------------------')
        plt.close('all')
        
        ### check version ###
        checks.checkPythonVersion()
        
        self.parameters.validate()
        self.parameters.set_acqMode()
        
        config_path = os.path.join(
            self.parameters.fileManagement.configFilePath,
            self.parameters.fileManagement.configFileName
        )
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.detector_pipeline = None
        self.bm_pipeline       = None
        
        ###############################################################################
        if self.parameters.acqMode  == 'pcap-local-overwrite'  or self.parameters.acqMode  == 'pcap-local':
            from lib.terminal import dumpToPcapng
            _ , file_name = dumpToPcapng(self.parameters.dumpSettings.interface,
                                         self.parameters.fileManagement.filePath,
                                         self.parameters.dumpSettings.fileName,
                                         self.parameters.dumpSettings.typeOfCapture,
                                         self.parameters.dumpSettings.quantity,
                                         1, 0, 
                                         self.parameters.fileManagement.pathToTshark,
                                         self.parameters.dumpSettings.fileNameOnly)
            self.parameters.fileManagement.fileName = [file_name]
         
        # sync the data folder from remote computer to local folder 
        elif not self.run_from_gui and self.parameters.acqMode == 'pcap-sync':
            from lib.terminal import syncData
            syncData(self.parameters.fileManagement.sourcePath, self.parameters.fileManagement.destPath)   
        

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
            # check pcapng packages are installed, exit if not
            checks.checkPackagePcap()
            
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
    
        self.parameters.validateWavelengthDependencies()
        self.detector_pipeline = build_detector_pipeline(self.config, reader, self.parameters)
        if self.detector_pipeline:
            self.detector_pipeline.execute(run_from_gui=self.run_from_gui)

        # 3. Conditionally Dispatch Beam Monitor Tracking Stream
        self.bm_pipeline = build_bm_pipeline(self.config, reader, self.parameters)
        if self.bm_pipeline and self.parameters.MONitor.MONOnOff:
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
            
            
            
            # if self.run_from_gui:       
            #     self.main_thread_queue.put(lambda: self.plotting())



    # # Final plotting and display logic
    # plt.show(block= False)

        ###############################################################################
        ###############################################################################
        # plt.show(block= False)
        self.timing.stop()
        print('----------------------------------------------------------------------')
        ###############################################################################
        ###############################################################################

def _enable_all_plots(params) -> None:
    """Test-only helper: flips on every plotting flag BasePipeline.plot()
    and BeamMonitorPipeline.plot() check, so a single test run exercises
    every plot_* method across every plotter. Not meant for routine use --
    routine runs should set only the flags you actually want."""
    p, w, phs, mon = params.plotting, params.wavelength, params.pulseHeigthSpect, params.MONitor

    p.plotChopperResets            = True
    p.plotRawReadouts              = True
    p.plotReadoutsTimeStamps       = True
    p.plotADCvsCh                  = True

    p.plotRawHits                  = True
    p.plotHitsTimeStamps           = True
    p.plotHitsTimeStampsVSChannels = True

    p.plotToFDistr                 = True
    p.plotMultiplicity             = True
    p.plotTimeBetwEv               = True

    phs.plotPHS                    = True
    phs.plotPHScorrelation         = True

    # calculateLambda has to be True for plotXLambda/plotLambdaDistr to have
    # real wavelength data to plot -- it's what triggers the wavelength calc
    # in analyze(), not just a display toggle.
    # w.calculateLambda              = False
    w.plotXLambda                  = True
    w.plotLambdaDistr              = True

    mon.plotMONtofPHS = True
   
    
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    ###############################################################################
    ###############################################################################
    ### get current path and init parameters ###
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    parameters  = para.parameters(current_dir)
    ###############################################################################
    ###############################################################################
    ### read json and create parameters for plotting and analisys ###

    configFileName  = "AMOR2.json"
    
    # configFileName  = "MGtestVessels.json"
    
    # configFileName  = "MGEMMA_2det.json"
    
    # configFileName  = "test1h.json"

    # configFileName  = "ESTIA.json"
    
    # configFileName  = "MIRACLES24.json"
    # configFileName  = "CSPEC.json"
    # configFileName  = "MIRACLES2.json"

    # configFileName  = "ESTIA_sect0.json"
    # configFileName  = "ESTIA_sect1.json"
    # configFileName  = "ESTIA_sect2.json"
    # configFileName  = "ESTIA_sect3.json"
    # configFileName  = "ESTIA_sect4.json"
    # configFileName  = "ESTIA_sect5.json"

    # configFileName  = "ESTIA_sect0and1.json"
    # configFileName  = "ESTIA_sect2and3.json"
    # configFileName  = "ESTIA_sect4and5.json"
    
    parameters.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep

    parameters.fileManagement.configFileName = configFileName

    ###############################################################################
    ###############################################################################
    ### edit parameters for plotting and analisys here ###
    ###############################################################################

    ### ACQ MODES:
    #################################
    ### can only be only one of these 5 options: off, pcap-sync, pcap-local, pcap-local-overwrite or kafka

    # parameters.acqMode = 'pcap-sync'
    # parameters.acqMode = 'pcap-local'
    # parameters.acqMode = 'pcap-local-overwrite'
    # parameters.acqMode = 'kafka'
    parameters.acqMode = 'off'

    ###  then check parameters.fileManagement.openMode = 'window' for the open mode ...
    ###############################################################################
    ###############################################################################
    ### FILE MANAGMENT  PARAMETERS:
    #################################

    # relevant for acqMode =  pcap-local, pcap-local-overwrite and kafka 

    parameters.dumpSettings.interface     = 'ens2'

    parameters.dumpSettings.typeOfCapture = 'packets'
    parameters.dumpSettings.quantity      =  100      #packets

    # parameters.dumpSettings.typeOfCapture = 'duration'
    # parameters.dumpSettings.quantity      = 1   #seconds

    parameters.fileManagement.fileNameSave = 'test'

    # NOTE
    # for acqMode =  pcap-local saves files in parameters.fileManagement.filePath 

    # relevant for acqMode =  kafka , num of packets to dump is in dumpSettings 
    parameters.kafkaSettings.broker       = '127.0.0.1:9092'
    parameters.kafkaSettings.topic        = 'freia_debug'
    parameters.kafkaSettings.numOfPackets =  100      #packets

    ###############################################################################

    # relevant for acqMode =  pcap-sync
    ### from ... to  ... rsync the data

    parameters.fileManagement.sourcePath = 'essdaq@172.30.244.50:/home/essdaq/pcaps/'

    parameters.fileManagement.destPath   = r"/Users/francescopiscitelli/Desktop/dataVMM/"

    ###############

    parameters.fileManagement.filePath = parameters.fileManagement.destPath 

    # relevant for acqMode =  off, pcap-sync and pcap-local

    parameters.fileManagement.filePath = current_dir+'data/'

   
    ### folder and file to open (file can be a list of files)

    parameters.fileManagement.fileName = ['ESSmask2023.pcapng']
    
    # parameters.fileManagement.fileName = ['ESSmask2023_1000pkts.pcapng','ESSmask2023_1000pkts_2.pcapng']
    # parameters.fileManagement.fileName = ['miracles_trig2.pcapng']
    # parameters.fileManagement.fileName = ['MG_2EMMAprototypes.pcapng']
    # parameters.fileManagement.fileName = ['miracles_source_mask_red.pcapng']
    # parameters.fileManagement.fileName = ['CSPEC1.pcapng']
    # parameters.fileManagement.fileName = ['20260602_103110_duration_s_300_muons_00000.pcapng']
    
    parameters.fileManagement.fileSerials = [6,2,4,9]
    # OR
    # parameters.fileManagement.fileSerials = ["0-2","11-13",45]

    ### valid otions: 'window','fileName', 'latest', 'secondLast', 'wholeFolder', 'sequence' 
    ### window opens to selcet file, filename speficified  earlier, last or sencond last file crearted in folder, 
    ### entire  folder  opend  and analized and cumulated  all togheter 
    ### sequence opens all filens in     parameters.fileManagement.fileSerials and with fileName
    parameters.fileManagement.openMode = 'window'
    parameters.fileManagement.openMode = 'fileName'
    #parameters.fileManagement.openMode = 'latest'
    # parameters.fileManagement.openMode = 'secondLast'
    #parameters.fileManagement.openMode = 'wholeFolder'
    # parameters.fileManagement.openMode = 'sequence'

    ###############
    ### type of pcap file loading, prealloc of memeory with allocate or quick, allocate is more rigorous, quick estimates the memory and it is faster 
    parameters.fileManagement.pcapLoadingMethod = 'allocate'
    # parameters.fileManagement.pcapLoadingMethod = 'quick'

    ###############
    ### path to calibration file
    parameters.fileManagement.calibFilePath = parameters.fileManagement.currentPath+'calib/'
    parameters.fileManagement.calibFileName = 'AMOR_calib_20231111002842.json'

    ###############
    ### path to threshold  file
    parameters.fileManagement.thresholdFilePath = parameters.fileManagement.currentPath+'config/'
    parameters.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'

    ###############
    ### path to  Tshark, in case you open a pcap  it gets converted into pcapng 
    parameters.fileManagement.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
    # parameters.fileManagement.pathToTshark = '/usr/sbin/'

    ###############
    ### save a hdf file with clusters (reduced file)

    ### ON/OFF
    parameters.fileManagement.saveReducedFileONOFF = False   
    parameters.fileManagement.saveReducedPath = '/Users/francescopiscitelli/Desktop/reducedFile/'

    parameters.fileManagement.reducedNameMainFolder  = 'entry1'
    parameters.fileManagement.reducedCompressionHDFT  = 'gzip'  
    parameters.fileManagement.reducedCompressionHDFL  = 9    # gzip compression level 0 - 9

    ###############################################################################
    ### ANALISYS PARAMETERS:
    #################################

    ### calibration VMM ADC
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = False

    ### sorting readouts by time stamp, if OFF they are as in RMM stream
    parameters.timeSettings.sortReadoutsByTimeStampsONOFF = False

    ### time stamp is time HI + time LO or if fine corrected with TDC 
    parameters.timeSettings.timeResolutionType = 'fine'
    # parameters.VMMsettings.timeResolutionType = 'coarse'

    ### timeWindow to search for clusters, timeWindow is max time between events in candidate cluster 
    ### and timeWindow/2 is the recursive time distance between adjacent hits
    parameters.dataReduction.timeWindow = 0.13e-6

    ### 'OFF', 'fromFile' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh
    parameters.dataReduction.softThresholdType = 'off' 
    # parameters.dataReduction.softThresholdType = 'fromFile' 
    # parameters.dataReduction.softThresholdType = 'userDefined' 
    # parameters.dataReduction.softThresholdType = 'constants' 

    if parameters.dataReduction.softThresholdType == 'userDefined':
          
       parameters.dataReduction.softThArray = {
                  5: {'ch0': np.full(32, 1000.0)},   # cassette 1, wire thresholds only
                  6: {'ch0': np.full(32, 500.0), 'ch1': np.full(64, 700.0)},
              } 
        
    elif  parameters.dataReduction.softThresholdType == 'constants':
        
        parameters.dataReduction.softThArray = (150,100)
   
        
              
    ###############################################################################
    ### WAVELENGTH PARAMETERS:
    #################################

    ### distance in mm from chopper and wires 0 of detector
    parameters.wavelength.distance  = 32000

    ##ON/OFF
    parameters.wavelength.calculateLambda = False

    ### ON/OFF plot X vs Lambda 2D plot
    parameters.wavelength.plotXLambda     = False
    ### ON/OFF integrated over single cassettes
    parameters.wavelength.plotLambdaDistr = False

    parameters.wavelength.lambdaBins  = 128
    parameters.wavelength.lambdaRange = [1, 16]   #A

    parameters.wavelength.chopperPeriod = 0.12 #s (NOTE: only matters if multipleFramesPerRest > 1)

    ### if chopper has two openings or more per reset of ToF
    parameters.wavelength.multipleFramePerReset = False  #ON/OFF (this only affects the lambda calculation)
    parameters.wavelength.numOfBunchesPerPulse  = 2
    parameters.wavelength.lambdaMIN             = 2.5     #A

    ### in seconds, time shift betweeen pickup and chopper edge 
    parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 

      
    ###############################################################################
    ### MONITOR PARAMETERS:
    #################################

    ### ON/OFF
    parameters.MONitor.MONOnOff    = False   

    ### threshold on MON, th is OFF if 0, any other value is ON
    parameters.MONitor.MONThreshold =0 

    ### ON/OFF plotting (MON ToF and Pulse Height) 
    parameters.MONitor.plotMONtofPHS = True  
    
    ### Pulse Height Spectr. settings for MON
    parameters.MONitor.energyBins = 256
    parameters.MONitor.maxEnerg   = 1000

    ### in mm, distance of MON from chopper if plotMONtofPH == 1 (needed for lambda calculation if ToF)
    parameters.MONitor.MONDistance  = 6000   
    

    ###############################################################################
    ### PLOTTING PARAMETERS:
    #################################

    ###############
    # with True disables clustering and mapping for speed reasons, analisys stops at readouts 
    parameters.plotting.bareReadoutsCalculation = False

    ###############     
    ### plotting in sections of cassettes to ease the visualization if True and in blocks of ...  
    parameters.plottingInSections       = False 
    parameters.plottingInSectionsBlocks = 5

    ###############     
    ### show stat during clustering, option  'globalStat'  stat for all cassettes together, 
    ### 'individualStat' stat per cassette or None for no stat
    parameters.plotting.showStat = 'globalStat'
    # parameters.plotting.showStat = 'individualStat'

    ###############     
    ### raw plots
    parameters.plotting.plotRawReadouts         = True
    parameters.plotting.plotReadoutsTimeStamps  = False
    parameters.plotting.plotADCvsCh             = False 
    parameters.plotting.plotADCvsChlog          = False 
    parameters.plotting.plotChopperResets       = False 

    parameters.plotting.plotRawHits             = False
    parameters.plotting.plotHitsTimeStamps      = False
    parameters.plotting.plotHitsTimeStampsVSChannels = False

    ###############
    ### Instantaneous Rate
    parameters.plotting.plotInstRate    = False
    parameters.plotting.instRateBin     = 100e-6  # s
     
    ###############
    ### ToF plot integrated over individual cassette, one per cassette
    parameters.plotting.plotToFDistr    = False

    parameters.plotting.ToFrange        = 0.12    # s
    parameters.plotting.ToFbinning      = 100e-6 # s

    parameters.plotting.ToFGate         = False
    parameters.plotting.ToFGateRange    = [0.02,0.025]   # s
         
    parameters.plotting.plotMultiplicity = False 

    ### 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
    parameters.plotting.positionReconstruction = 'W.max-S.cog'
    # parameters.plotting.positionReconstruction = 'W.max-S.max'
    # parameters.plotting.positionReconstruction = 'W.cog-S.cog'

    ### if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.
    parameters.plotting.plotABSunits = False
     
    ### plot XY and XToF in log scale 
    parameters.plotting.plotIMGlog   = False

    ### ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False
    parameters.plotting.coincidenceWS_ONOFF = True

    ### ON/OFF, if  invalid ToFs Tofare included in the plots or removed from events 
    parameters.plotting.removeInvalidToFs   = True

    ### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
    parameters.plotting.histogOutBounds = True

    ###########################      
    ### PHS

    ### ON/OFF PHS per channel and global
    parameters.pulseHeigthSpect.plotPHS = True

    ### plot PHS in log scale 
    parameters.pulseHeigthSpect.plotPHSlog = False

    parameters.pulseHeigthSpect.energyBins = 256
    parameters.pulseHeigthSpect.maxEnerg   = 1700

    ### plot the PHS correaltion wires vs strips
    parameters.pulseHeigthSpect.plotPHScorrelation = False

    ###############################################################################
    ###############################################################################
    ###############################################################################

    
    pipeline_orchestrator = MBUTYOrchestrator(parameters)
    pipeline_orchestrator.run_pipeline()
    
    readouts = pipeline_orchestrator.readouts_container
    readoutsArray = readouts.get_data_frame()
    hits = pipeline_orchestrator.hits_container
    hitsArray = hits.get_data_frame()
    events = pipeline_orchestrator.events_container
    eventsArray = events.get_data_frame()
    
    config = pipeline_orchestrator.config

    # add containerf for BM 

    
#     ###############################################################################
#     ###############################################################################
# if __name__ == '__main__':
#     import numpy as np 
#     current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
#     params = para.parameters(current_dir)

#     params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
#     params.fileManagement.configFileName = "AMOR.json"
#     params.fileManagement.fileName = ["ESSmask2023.pcapng"]
    
    
#     # params.fileManagement.fileName = ["file1_15pk.pcapng","4freia.pcapng","8badpkt.pcapng",'file2_6pk.pcapng']
    
    
#     params.fileManagement.openMode = "fileName"
#     params.acqMode = 'off'
#     params.fileManagement.pcapLoadingMethod = 'allocate'
#     params.dataReduction.calibrateVMM_ADC_ONOFF = False
#     params.fileManagement.calibFilePath = os.path.join(current_dir, 'calib') + os.sep
#     params.fileManagement.calibFileName = "AMOR_calib.json"
#     params.plotting.plottingInSections = False
#     params.plotting.plottingInSectionsBlocks = 5
#     params.dataReduction.timeWindow = 0.127e-6
#     params.plotting.ToFrange        = 0.15
#     params.plotting.timeBetwEvBin   = 1e-6
    
#     params.timeSettings.sortReadoutsByTimeStampsONOFF = True
    
#     params.plotting.removeInvalidToFs = True


#     params.plotting.histogOutBounds = True
    
#     params.wavelength.calculateLambda = False
    
#     params.saveReducedFileONOFF = False
    
#     params.MONitor.MONOnOff = True
#     params.MONitor.plotMONtofPHS = True
#     params.MONitor.MONThreshold = 200
    
#     _enable_all_plots(params)

  
    
#     params.dataReduction.softThresholdType = 'fromFile'
#     params.fileManagement.thresholdFilePath = current_dir+'/confdg/'
#     params.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'
#     # params.dataReduction.softThArray = (500, 700)
#     params.dataReduction.softThArray = {
#         5: {'ch0': np.full(32, 1000.0)},   # cassette 1, wire thresholds only
#         6: {'ch0': np.full(32, 500.0), 'ch1': np.full(64, 700.0)},
#     }
#     # Run backend scientific computation track. Each pipeline's plot() runs
#     # as part of execute(), as a side effect of analysis completing --
#     # nothing else in this file decides what gets shown.
#     pipeline_orchestrator = MBUTYOrchestrator(params)
#     pipeline_orchestrator.run_pipeline()
    
#     readouts = pipeline_orchestrator.readouts_container
#     readoutsArray = readouts.get_data_frame()
#     hits = pipeline_orchestrator.hits_container
#     hitsArray = hits.get_data_frame()
#     events = pipeline_orchestrator.events_container
#     eventsArray = events.get_data_frame()
    
#     config = pipeline_orchestrator.config
    


# # Need to set this somewhere!!!
# # n_wires  = int(config['wires'])
# # n_strips = int(config['strips'])
# # unit_ids = [e['ID'] for e in config['topology']]

# # parameters.dataReduction.softThresholdType = 'userDefined'
# # parameters.dataReduction.softThArray = {
# #     uid: {
# #         'ch0': np.full(n_wires,  700.0),
# #         'ch1': np.full(n_strips, 1000.0),
# #     }
# #     for uid in unit_ids
# # }
