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

# from lib import libMapping as mapsnew

from newLib import reader

from newLib.config_validator import validate_config, load_config

from newLib.mapping_engine import MBMapper, MBClustMapper, BMMapper, map_detector, He3Mapper

from newLib.clustering_engine import VMMNormalClusterer, VMMClusteredClusterer, R5560Clusterer

from newLib.abs_units_engine import MBAbsUnitsCalculator, MGAbsUnitsCalculator, R5560AbsUnitsCalculator

###############################################################################
###############################################################################

if __name__ == '__main__':
    
    tProfilingStart = time.time()
    
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/'
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

    from lib import libMapping_old as maps
    from lib import libCluster as clu 
    confFileName  = "AMOR.json"
    file = 'ESSmask2023_1000pkts.pcapng'
    
    
    
    
    from lib import libMappingR5560 as maps
    from lib import libClusterR5560 as clu 
    confFileName  = "CSPEC.json"
    file          = 'CSPEC1.pcapng'
    
    confFileName  = "MIRACLES24.json"
    file          = 'miracles_source_mask.pcapng'
    
    
    
    from lib import libMapping_old as maps
    from lib import libCluster as clu 
    confFileName  = "AMOR.json"
    file = 'ESSmask2023_1000pkts.pcapng'
    

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

   #######################################
   #######################################   
    
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = True

    parameters.VMMsettings.timeResolutionType = 'fine'
    
    parameters.fileManagement.pcapLoadingMethod = 'allocate'
    # parameters.fileManagement.pcapLoadingMethod = 'quick'
    
    parameters.dataReduction.timeWindow = 0.127e-6
    

    pcap = pcapr.pcapng_reader(filePath+file,NSperClockTick=parameters.clockTicks.NSperClockTick,
                               MONhw=config.MONmap.hardwareType, MONconn=config.MONmap.connectionType, MONring=parameters.config.MONmap.RingID, 
                               timeResolutionType=parameters.VMMsettings.timeResolutionType , 
                               sortByTimeStampsONOFF=parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, 
                               operationMode=parameters.config.DETparameters.operationMode,pcapLoadingMethod=parameters.fileManagement.pcapLoadingMethod)

    readouts = pcap.readouts

    readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
    
    # heartbeats1 = readouts.heartbeats
    # heartbeats2 = readouts.removeNonESSpacketsHeartbeats(readouts.heartbeats)
    
    readouts.checkChopperFreq()
    
    readouts.checkInvalidToFsInReadouts()
    
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
    
    md  = maps.mapDetector(readouts, config)
    md.mappAllCassAndChannelsGlob()
    hits = md.hits
    hitsArray  = hits.concatenateHitsInArrayForDebug()
    
    MON = maps.mapMonitor(readouts, config)
    hitsMON = MON.hits
  

    #######################################
    #######################################
    # CLUSTERING 
    
    if parameters.config.DETparameters.operationMode == 'normal':
        ###############################################################################
        ### clusterize
        cc = clu.clusterHits(hits,parameters.plotting.showStat)
        cc.clusterizeManyCassettes(parameters.config.DETparameters.cassInConfig, parameters.dataReduction.timeWindow, parameters.config.DETparameters.type)
        events = cc.events
        deltaTimeWS = cc.deltaTimeClusterWSall
        

    elif  parameters.config.DETparameters.operationMode == 'clustered':  
        ### do not clusterize
        events = clu.events()
        events.importClusteredHits(hits,parameters.config)
        deltaTimeWS = None
        
    eventsArray =  events.concatenateEventsInArrayForDebug()
    
    
    #######################################
    #######################################
    
    #######################################
    #######################################
    #ABS units 
    
    # MBAbsUnitsCalculator
    
    
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
    
    # readoutsNEW  = newreader.readouts_vmm_normal
    
    readoutsNEW  = newreader.readouts_r5560
    
    # readoutsNEW = newreader.readouts_vmm_clustered

    readoutsArrayNEW  = readoutsNEW.get_data_frame()
    

    
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
    
    # hitsNEW = map_detector(newreader.readouts_vmm_normal, confignew)
    
    hitsNEW = map_detector(newreader.readouts_r5560, confignew)
    
    # hitsNEW = He3Mapper.map(newreader.readouts_r5560, confignew)
    
    hitsArrayNEW = hitsNEW.get_data_frame()
    
    
    # tt = hitsNEW.matrix['timeStamp'] - hits.timeStamp
    
    
    # tt = hitsArrayNEW['timeStamp'] - hits.timeStamp
    
    # aa = hitsArrayNEW['adc'] - hits.ADC
    
    # pp = hitsArrayNEW['plane'] - hits.WorS
    
    #######################################
    #######################################
    
    
    #######################################
    #######################################
    # CLUSTERING 
    
    # eventsNEW = VMMNormalClusterer.cluster(hitsNEW, config=confignew, time_window_s=parameters.dataReduction.timeWindow)
    
    eventsNEW = R5560Clusterer.cluster(hitsNEW, config=confignew, time_window_s=parameters.dataReduction.timeWindow)
    
    
    eventsArrayNEW = eventsNEW.get_data_frame()
    
    #######################################
    #######################################
    #ABS units 
    
    # MBAbsUnitsCalculator
    
    
    #######################################
    #######################################

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)
    
    ###############################################################################
    ###############################################################################
   
    
    
    