#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mbuty_new.py
============
High-Performance Master Ingestion Orchestrator for ESS Neutron Detectors.
"""

import os
# os.environ["QT_API"] = "pyside6"
import sys
import numpy as np
import json
from collections import defaultdict
from types import SimpleNamespace
import matplotlib.pyplot as plt
# Ingest new high-performance architecture modules
from lib.colors import INFO, OK, WARN, ERR, RESET
import lib.checks_and_helpers as checks
from lib.config_validator import validate_config
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
    def __init__(self, parameters, plottingOnOff: str = 'on', main_thread_queue = None):
        self.main_thread_queue = main_thread_queue
        self.plottingOnOff          = plottingOnOff
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
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
                print(f"{ERR}Error: Configuration file not found at '{config_path}'{RESET}")
                sys.exit()
                
        validate_config(self.config)
        
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
        elif not self.plottingOnOff == 'gui' and self.parameters.acqMode == 'pcap-sync':
            from lib.terminal import syncData
            syncData(self.parameters.fileManagement.sourcePath, self.parameters.fileManagement.destPath)   
        

    def run_pipeline(self) -> None:
        """Executes data frame ingestion and routes targeted tracks via explicit type matching gates."""
        try:
            # 1. Pipeline Data Ingestion Pass (Network Stream vs Disk Storage)
            if self.parameters.acqMode == 'kafka':
                checks.checkPackageKafka()
                from lib.kafka_reader import KafkaReader
                
                reader = KafkaReader(
                    parameters = self.parameters,
                    config     = self.config,  
                    testing    = False
                )
                reader.run()
            else:
                checks.checkPackagePcap()
                from lib.reader import PcapngFileReader
                
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
                    
                    readout_containers = reader.run()
                    for name, container in readout_containers.items():
                        container_lists[name].append(container)
                
                merged = {
                    name: containers[0] if len(containers) == 1 else type(containers[0]).merge(containers)
                    for name, containers in container_lists.items()
                }

                reader = SimpleNamespace(**merged)
       
            # 2. Detector Pipeline Track Instantiation & Execution Pass via Factory
            self.parameters.validateDependencies()
            self.detector_pipeline = build_detector_pipeline(self.config, reader, self.parameters)
            if self.detector_pipeline:
                if not self.parameters.plotting.bareReadoutsCalculation:
                    self.detector_pipeline.analyze()
                    
            # 3. Conditionally Dispatch Beam Monitor Tracking Stream
            self.bm_pipeline = build_bm_pipeline(self.config, reader, self.parameters)
            if self.bm_pipeline and self.parameters.MONitor.MONOnOff:
                if not self.parameters.plotting.bareReadoutsCalculation:
                    self.bm_pipeline.analyze()
                    
            if self.plottingOnOff == 'on':
                dashboard_shown = False
                if self.parameters.plotting.useDashboard:
                    try:
                        from lib.mbuty_dashboard import launch_dashboard
                        self._dashboard = launch_dashboard(self.detector_pipeline, self.bm_pipeline, self.parameters, theme_mode='light')
                        dashboard_shown = True
                    except Exception as e:
                        print(f"{WARN}Dashboard failed ({e}) -- falling back to standard plotting.{RESET}")
                        self.detector_pipeline.plot()
                        if self.bm_pipeline and self.parameters.MONitor.MONOnOff:
                            self.bm_pipeline.plot()
                else:
                    self.detector_pipeline.plot()
                    if self.bm_pipeline and self.parameters.MONitor.MONOnOff:
                        self.bm_pipeline.plot()

                if not dashboard_shown and (self.detector_pipeline or (self.bm_pipeline and self.parameters.MONitor.MONOnOff)): 
                    plt.draw() 
                    plt.pause(0.1)
                    plt.show(block=False)
                    input(f"{INFO}\nPress Enter to close all figures...{RESET}")
                    plt.close('all')
            
            self.readouts_container = self.detector_pipeline.readouts_container
            self.hits_container     = self.detector_pipeline.hits_container
            self.events_container   = self.detector_pipeline.events_container
            
            self.readouts_BM_container = self.bm_pipeline.readouts_container
            self.events_BM_container   = self.bm_pipeline.events_container
            
            self.axis_set = self.detector_pipeline.axis_set
            
            ### save reduced data to hdf5
            if self.parameters.fileManagement.saveReducedFileONOFF is True:
                import lib.save_reduced_file as saveH5
                fileNameSave = saveH5.prepareReducedFileBaseName(file_resolver.fileName)

                if (self.parameters.MONitor.MONOnOff is True) and self.bm_pipeline:
                    saveH5.saveReducedDataToHDF(
                        self.parameters,
                        self.events_container,
                        self.bm_pipeline.events_container,
                        self.parameters.fileManagement.saveReducedPath,
                        fileNameSave
                    )
                else:
                    saveH5.saveReducedDataToHDF(
                        self.parameters,
                        self.events_container,
                        saveReducedPath=self.parameters.fileManagement.saveReducedPath,
                        fileName=fileNameSave
                    )

            self.timing.stop()
            print('----------------------------------------------------------------------')

        except Exception as e:
            print(f"\n{ERR}Analysis aborted due to error: {e}{RESET}")
            raise e  # Re-raise so MBUTY_GUI worker thread catches it and stops cleanly
            # self.timing.lap()
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

    configFileName  = "AMOR.json"
    # configFileName  = "clustered.json"
    
    # configFileName  = "skadi48.json"
    # configFileName  = "skadi_full.json"
    
    # configFileName  = "MGtestVessels2col.json"
    
    # configFileName  = "MGEMMA_2det.json"
    
    # configFileName  = "test1h.json"

    # configFileName  = "ESTIA.json"
    
    # configFileName  = "MIRACLES24.json"
    # configFileName  = "CSPEC.json"
    # configFileName  = "MIRACLES1.json"

    # configFileName  = "ESTIA_sect0.json"
    # configFileName  = "ESTIA_sect1.json"
    # configFileName  = "ESTIA_sect2.json"
    # configFileName  = "ESTIA_sect3.json"
    # configFileName  = "ESTIA_sect4.json"
    # configFileName  = "ESTIA_sect5.json"

    # configFileName  = "ESTIA_sect0and1.json"
    # configFileName  = "ESTIA_sect2and3.json"
    # configFileName  = "ESTIA_sect4and5.json"
    
    configFileName  = "NMXtest.json"
    
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
    
    parameters.fileManagement.sourcePath = 'essdaq@det-efu-devel01.cslab.esss.lu.se:/home/essdaq/pcaps/'

    parameters.fileManagement.destPath   = r"/Users/francescopiscitelli/Desktop/dataVMM/"

    ###############

    parameters.fileManagement.filePath = parameters.fileManagement.destPath 

    # relevant for acqMode =  off, pcap-sync and pcap-local

    parameters.fileManagement.filePath = current_dir+'data/'

   
    ### folder and file to open (file can be a list of files)

    parameters.fileManagement.fileName = ['ESSmask2023.pcapng']
    
    # parameters.fileManagement.fileName = ['20260522_153423_duration_s_5_fullyOpenAgain_00000_vkjaa.pcapng']
    
    
    # parameters.fileManagement.fileName = ['miracles_trig2.pcapng']
    # parameters.fileManagement.fileName = ['MG_2EMMAprototypes.pcapng']
    # parameters.fileManagement.fileName = ['miracles_source_mask_red.pcapng']
    # parameters.fileManagement.fileName = ['CSPEC1.pcapng']
    # parameters.fileManagement.fileName = ['20260602_103110_duration_s_300_muons_00000.pcapng']
    
    # parameters.fileManagement.fileName = ['sampleData_ClusteredMode.pcapng']
    
    # parameters.fileManagement.fileName = ['MGtestVess.pcapng']
    
    # parameters.fileManagement.fileName = ['skadi_1tile.pcapng']
    
    # parameters.fileManagement.fileName = ['skadiDataQ.pcapng']
    
    # parameters.fileManagement.fileName = ['triggertime-1000V-30a11_July8th.pcapng']
    
    # parameters.fileManagement.fileName = ['skadi_48tiles.pcapng']
    
    parameters.fileManagement.fileName = ['tim_4p5mVfC_130mV_4700V_00031_20250829130938.pcapng']

    
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
    parameters.fileManagement.pcapLoadingMethod = 'quick'

    ###############
    ### path to calibration file
    parameters.fileManagement.calibFilePath = parameters.fileManagement.currentPath+'calib/'
    parameters.fileManagement.calibFileName = 'AMOR_calib_20231111002842.json'

    ###############
    ### path to threshold  file
    parameters.fileManagement.thresholdFilePath = parameters.fileManagement.currentPath+'config/'
    parameters.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'
    # parameters.fileManagement.thresholdFileName = 'tube_threshold_example.xlsx'

    ###############
    ### path to  Tshark, in case you open a pcap  it gets converted into pcapng 
    parameters.fileManagement.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
    # parameters.fileManagement.pathToTshark = '/usr/sbin/'

    ###############
    ### save a hdf file with clusters (reduced file)

    ### ON/OFF
    parameters.fileManagement.saveReducedFileONOFF = False   
    parameters.fileManagement.saveReducedPath = parameters.fileManagement.currentPath+'reduced/'

    parameters.fileManagement.reducedNameMainFolder   = 'entry1'
    parameters.fileManagement.reducedCompressionHDFT  = 'gzip'  
    parameters.fileManagement.reducedCompressionHDFL  = 9    # gzip compression level 0 - 9

    ###############################################################################
    ### ANALISYS PARAMETERS:
    #################################

    ### calibration VMM ADC TDC
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = False
    parameters.dataReduction.calibrateVMM_TDC_ONOFF = False

    ### sorting readouts by time stamp, if OFF they are as in RMM stream
    parameters.timeSettings.sortReadoutsByTimeStampsONOFF = True

    ### time stamp is time HI + time LO or if fine corrected with TDC 
    parameters.timeSettings.timeResolutionType = 'fine'
    # parameters.timeSettings.timeResolutionType = 'coarse'

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
       
       # for tubes
       # parameters.dataReduction.softThArray = {
       #            11: 13340,  
       #             12: 4566,
       #         } 
        
    elif  parameters.dataReduction.softThresholdType == 'constants':
        
        # for MB or MG 
        parameters.dataReduction.softThArray = [300,0]
        
        # for tubes
        # parameters.dataReduction.softThArray[0] = [10000]
        
              
    ###############################################################################
    ### WAVELENGTH PARAMETERS:
    #################################

    ### distance in mm from chopper and wires 0 of detector
    parameters.wavelength.distance  = 32000

    ##ON/OFF
    parameters.wavelength.calculateLambda = True

    ### ON/OFF plot X vs Lambda 2D plot
    parameters.wavelength.plotXLambda     = True
    ### ON/OFF integrated over single cassettes
    parameters.wavelength.plotLambdaDistr = True

    parameters.wavelength.lambdaBins  = 128
    parameters.wavelength.lambdaRange = [1, 16]   #A

    parameters.wavelength.chopperPeriod = 0.12 #s (NOTE: only matters if multipleFramesPerRest > 1)

    ### if chopper has two openings or more per reset of ToF
    parameters.wavelength.multipleFramePerReset = True  #ON/OFF (this only affects the lambda calculation)
    parameters.wavelength.numOfBunchesPerPulse  = 2
    parameters.wavelength.lambdaMIN             = 2.5     #A

    ### in seconds, time shift betweeen pickup and chopper edge 
    parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 

      
    ###############################################################################
    ### MONITOR PARAMETERS:
    #################################

    ### ON/OFF
    parameters.MONitor.MONOnOff    = True   

    ### threshold on MON, th is OFF if 0, any other value is ON
    parameters.MONitor.MONThreshold = 0 

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
    parameters.plotting.useDashboard = True
    ###############   
    
    ###############   
    ### plotting in sections of cassettes to ease the visualization if True and in blocks of ...  
    parameters.plotting.plottingInSections       = True 
    parameters.plotting.plottingInSectionsBlocks = 5

    ###############     
    ### raw plots
    parameters.plotting.plotRawReadouts         = True
    parameters.plotting.plotReadoutsTimeStamps  = True
    parameters.plotting.plotADCvsCh             = True 
    parameters.plotting.plotADCvsChlog          = True 
    parameters.plotting.plotChopperResets       = True 

    parameters.plotting.plotRawHits             = True
    parameters.plotting.plotHitsTimeStamps      = True
    parameters.plotting.plotHitsTimeStampsVSChannels = True

    ###############
    ### time between events 
    parameters.plotting.plotTimeBetwEv    = True
    parameters.plotting.timeBetwEvBin     = 1e-6  # s
    
    ###############
    ### ToF plot integrated over individual cassette, one per cassette
    parameters.plotting.plotToFDistr    = True

    parameters.plotting.ToFrange        = 0.12    # s
    parameters.plotting.ToFbinning      = 100e-6 # s

    parameters.plotting.ToFGate         = False
    parameters.plotting.ToFGateRange    = [0.02,0.025]   # s
         
    parameters.plotting.plotMultiplicity = True 

    ### 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
    parameters.plotting.positionReconstruction = 'W.max-S.cog'
    # parameters.plotting.positionReconstruction = 'W.max-S.max'
    # parameters.plotting.positionReconstruction = 'W.cog-S.cog'

    ### if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.
    parameters.plotting.plotABSunits = True
     
    ### plot XY and XToF in log scale 
    parameters.plotting.plotIMGlog   = True

    ### ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False
    
    parameters.plotting.coincidenceWS_ONOFF = True

    ### ON/OFF, if  invalid ToFs Tofare included in the plots or removed from events 
    parameters.plotting.removeInvalidToFs   = False

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
    parameters.pulseHeigthSpect.plotPHScorrelation = True

    ###############################################################################
    ###############################################################################
    ###############################################################################

    
    try:
        pipeline_orchestrator = MBUTYOrchestrator(parameters)
        pipeline_orchestrator.run_pipeline()
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user or window closure.")
    except Exception as e:
        print(f"\n{ERR}Execution aborted: {e}{RESET}")
        sys.exit(1)

    config = pipeline_orchestrator.config
    
    axis_set = pipeline_orchestrator.axis_set
    
    readouts = pipeline_orchestrator.readouts_container
    readoutsArray = readouts.get_data_frame()
    hits   = pipeline_orchestrator.hits_container
    events = pipeline_orchestrator.events_container
    
    
    readoutsBM       = pipeline_orchestrator.readouts_BM_container
    readoutsArrayBM  = readoutsBM.get_data_frame()
    eventsBM         = pipeline_orchestrator.events_BM_container

    if hits is not None:
        hitsArray     = hits.get_data_frame()
    if events is not None:
        eventsArray   = events.get_data_frame()
    if eventsBM is not None:
        eventsBMArray = eventsBM.get_data_frame()
        
    



    
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
