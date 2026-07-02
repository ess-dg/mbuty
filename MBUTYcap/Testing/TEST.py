#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 22 00:29:02 2026

@author: francescopiscitelli
"""

import numpy as np
import pcapng as pg
import os
import time
import sys
import ipaddress
import matplotlib.pyplot as plt

import json

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)


from lib import libReadPcapng as pcapr

from lib import libVMMcalibration as cal 

from lib import libParameters as para

from lib import libAbsUnitsAndLambda


from newLib import reader

from newLib.config_validator import validate_config, load_config

from newLib.mapping_engine import MBMapper, MBClustMapper, BMMapper, map_detector, He3Mapper, IBMMonitorMapper, MGMapper

from newLib.clustering_engine import VMMNormalClusterer, VMMClusteredClusterer, R5560Clusterer

from newLib.abs_units_engine import MBAbsUnitsCalculator, MGAbsUnitsCalculator, R5560AbsUnitsCalculator



###############################################################################
###############################################################################

if __name__ == '__main__':
    
    tProfilingStart = time.time()
    
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/'
    
    path = '/Users/francescopiscitelli/git_repos/mbuty/MBUTYcap/'
    
    # Use a normal string with escaped backslashes to avoid a raw string ending with a single backslash
    # path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'
    

    calibPath   = path + 'calib/'
    calibFile   = 'AMOR_calib_20231111002842.json'
    # calibFile   =  'ill_efu_time_calib_mod.json'
    
    confPathOld = path + 'config_old/'
    confPath    = path + 'config/'
    
    filePath    = path + 'data/'
    

  ##############################################################################
  ##############################################################################

    from lib import libMapping as maps
    from lib import libCluster as clu 
    from lib import libAbsUnitsAndLambda as absu
    confFileName  = "AMOR.json"
    file = 'ESSmask2023_1000pkts.pcapng'
    
    # file = 'testIBM.pcapng'
    
    
    # confFileName  = "testClustered.json"
    # file = "sampleData_ClusteredMode.pcapng"
    
    
    
    
    # from lib import libMappingR5560 as maps
    # from lib import libClusterR5560 as clu 
    # confFileName  = "CSPEC.json"
    # file          = 'CSPEC1.pcapng'
    
    # confFileName  = "MIRACLES24.json"
    # file          = 'miracles_source_mask.pcapng'
    
    
    
    # from lib import libMappingMG as maps
    # from lib import libClusterMG as clu 
    # confFileName  = "MG_EMMA.json"
    # file = 'MG_2EMMAprototypes.pcapng'
    
    
    # confFileName  = "MGtestVessels2col.json"
    # file = 'MGtestVess.pcapng'
    
    
    
    
    

   ###############################
        
    
    # file = 'miracles_trig2.pcapng'
    
    # file = 'ESSmask2023.pcapng'
    
    # file = 'sampleData_NormalMode.pcapng'
    
    # file = 'sampleData_ClusteredMode.pcapng'
    
    # file = '20260611_083348_pkts100_Test-almostAllEmpty_00000.pcapng'
    
    # file = '20260611_083055_pkts100_Test-full_00000.pcapng'
    
    # file = 'testData.pcapng'
    
    # file = 'miracles_source_on_left_red.pcapng'

    #

   ##############################################################################
   ##############################################################################
   # LOAD CONFIG 
   
    config = maps.read_json_config(confPathOld+confFileName)
       
    parameters  = para.parameters(confPathOld+confFileName)
    parameters.loadConfigAndUpdate(config)

   # #######################################
   # #######################################   
    
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = True

    parameters.VMMsettings.timeResolutionType = 'fine'
    
    parameters.fileManagement.pcapLoadingMethod = 'allocate'
    parameters.fileManagement.pcapLoadingMethod = 'quick'
    
    parameters.dataReduction.timeWindow = 0.127e-6
    
    parameters.wavelength.calculateLambda = True
    

   #  pcap = pcapr.pcapng_reader(filePath+file,NSperClockTick=parameters.clockTicks.NSperClockTick,
   #                             MONhw=config.MONmap.hardwareType, MONconn=config.MONmap.connectionType, MONring=parameters.config.MONmap.RingID, 
   #                             timeResolutionType=parameters.VMMsettings.timeResolutionType , 
   #                             sortByTimeStampsONOFF=parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, 
   #                             operationMode=parameters.config.DETparameters.operationMode,pcapLoadingMethod=parameters.fileManagement.pcapLoadingMethod)

   #  readouts = pcap.readouts

   #  readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
    
   #  # heartbeats1 = readouts.heartbeats
   #  # heartbeats2 = readouts.removeNonESSpacketsHeartbeats(readouts.heartbeats)
    
   #  readouts.checkChopperFreq()
    
   #  readouts.checkInvalidToFsInReadouts()
    
    # parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = True
    
    
    #######################################
    #######################################
    # CALIBRATION 
    

    # 
    
    # calib = cal.read_json_calib(calibPath+calibFile,config)
    
    # if calib.calibFlag is True:
    #         ca = cal.calibrate(readouts,config,calib)
    #         ca.calibrateADC()
    #         readoutsOUT = ca.readouts
            
    # readoutsArrayOUT = readouts.concatenateReadoutsInArrayForDebug()      

    #######################################
    #######################################
    
    #######################################
    #######################################
    # MAPPING 
    
    # md  = maps.mapDetector(readouts, config)
    # md.mappAllCassAndChannelsGlob()
    # hits = md.hits
    # hitsArray  = hits.concatenateHitsInArrayForDebug()
    
    # parameters.MONitor.MONOnOff = True
    
    # if parameters.MONitor.MONOnOff is True:
        
    #     MON = maps.mapMonitor(readouts, config)
        
    #     if MON.flagMONfound is True:
    #         hitsMON = MON.hits
            
    #         MONe = clu.hitsMON2events(hitsMON)
    #         eventsMON = MONe.events
            
    #         abMON = absu.calculateAbsUnits(eventsMON, parameters, 'MON')
    #         abMON.calculateToF(parameters.plotting.removeInvalidToFs)
            
    #         print('\033[1;32m\t MON events: {}\033[1;37m'.format(eventsMON.Nevents[0]))

    #         if parameters.wavelength.calculateLambda is True:
    #             abMON.calculateWavelengthMON()

    #             eventsMON = abMON.events

  

    # #######################################
    # #######################################
    # # CLUSTERING 
    
    # if parameters.config.DETparameters.operationMode == 'normal':
    #     ###############################################################################
    #     ### clusterize
    #     cc = clu.clusterHits(hits,parameters.plotting.showStat)
    #     cc.clusterizeManyCassettes(parameters.config.DETparameters.cassInConfig, parameters.dataReduction.timeWindow, parameters.config.DETparameters.type)
    #     events = cc.events
    #     deltaTimeWS = cc.deltaTimeClusterWSall
        

    # elif  parameters.config.DETparameters.operationMode == 'clustered':  
    #     ### do not clusterize
    #     events = clu.events()
    #     events.importClusteredHits(hits,parameters.config)
    #     deltaTimeWS = None
        
    # eventsArray =  events.concatenateEventsInArrayForDebug()
    
    
    # #######################################
    # #######################################
    
    # #######################################
    # #######################################
    # #ABS units 
    
    # ab = absu.calculateAbsUnits(events, parameters)
    # ab.calculatePositionAbsUnit()
    
    # ab.calculateToF(parameters.plotting.removeInvalidToFs)
    
    # ab.calculateWavelength()

    # events = ab.events 
    
    # eventsArray =  events.concatenateEventsInArrayForDebug()
    
    
    #######################################
    #######################################
    
    
    

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)    
    
    print('\n ------------------------------------------------------ \n')
    
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    # HERE STARTS NEW CODE 

    tProfilingStart = time.time()
    
    confignew = load_config(confPath+confFileName)
    validate_config(confignew)
    
    newreader = reader.PcapngFileReader(
            file_path  = filePath+file,
            parameters = parameters,
            config     = confignew,
        )
    newreader.run()
    
    readoutsNEW  = newreader.readouts_vmm_normal
    
    # readoutsNEW  = newreader.readouts_r5560
    
    # readoutsNEW = newreader.readouts_vmm_clustered

    readoutsArrayNEW  = readoutsNEW.get_data_frame()
    
    MONreadoutsNEW      = newreader.readouts_bm
    
    MONreadoutsNEWi       = newreader.readouts_ibm
    
    MONreadoutsArrayNEW  = MONreadoutsNEW.get_data_frame()
    
    MONreadoutsArrayNEWi  = MONreadoutsNEWi.get_data_frame()
    
    # bb = readoutsNEWc.matrix['adc'] - readouts.ADC
    
    #######################################
    #######################################
    # CALIBRATION 
    
    # parameters.fileManagement.calibFilePath = calibPath
    # parameters.fileManagement.calibFileName = calibFile
    # parameters.dataReduction.calibrateVMM_ADC_ONOFF = True
    
    # parameters.dataReduction.calibrateVMM_TDC_ONOFF = True

    # newreader.readouts_vmm_normal.calibrate(parameters, confignew)
    # readoutsArrayNEW_OUT  = newreader.readouts_vmm_normal.get_data_frame()
    
    #######################################
    #######################################

    #######################################
    #######################################
    # MAPPING 
    
    hitsNEW = MBMapper.map(newreader.readouts_vmm_normal, confignew)
    
    # hitsNEW = MGMapper.map(newreader.readouts_vmm_normal, confignew)
 
    # hitsNEW = He3Mapper.map(newreader.readouts_r5560, confignew)
    
    # hitsNEW = MBClustMapper.map(newreader.readouts_vmm_clustered, confignew)

    
    hitsArrayNEW = hitsNEW.get_data_frame()
    
    MONeventsNEW = BMMapper.map(newreader.readouts_bm, confignew)
    
    # MONeventsNEW = IBMMonitorMapper.map(newreader.readouts_ibm, confignew)
    
    MONeventsArrayNEW = MONeventsNEW.get_data_frame()
    
    
    
    
    # MONhitsNEW = map_detector(newreader.readouts_bm, confignew)
    # MONhitsArrayNEW = hitsNEW.get_data_frame()
    
    # tt = hitsNEW.matrix['timeStamp'] - hits.timeStamp
    
    
    # tt = hitsArrayNEW['timeStamp'] - hits.timeStamp
    
    # aa = hitsArrayNEW['adc'] - hits.ADC
    
    # pp = hitsArrayNEW['plane'] - hits.WorS
    
    #######################################
    #######################################
    
    
    #######################################
    #######################################
    # CLUSTERING 
    
    eventsNEW = VMMNormalClusterer.cluster(hitsNEW, config=confignew, time_window_s=parameters.dataReduction.timeWindow)
    
    # eventsNEW = VMMClusteredClusterer.cluster(hitsNEW, config=confignew, time_window_s=parameters.dataReduction.timeWindow)
    
    # eventsNEW = R5560Clusterer.cluster(hitsNEW, config=confignew, time_window_s=parameters.dataReduction.timeWindow)
    
    
    eventsArrayNEW = eventsNEW.get_data_frame()
    
    #######################################
    #######################################
    #ABS units 
    
    aa = MBAbsUnitsCalculator(eventsNEW, confignew, parameters)  
    
    aa.process_pipeline(False)
    
    eventsArrayNEW = eventsNEW.get_data_frame()
    
    
    #######################################
    #######################################

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)
    
    ###############################################################################
    ###############################################################################
   
    
    
    