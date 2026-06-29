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

try: 
    ####### if you run default
    from lib import libMapping_old as maps
    from lib import libParameters as para

except ImportError:
    ####### if you run in lib 
    import libMapping_old as maps
    import libParameters as para


from newLib import reader

from lib import libMapping as mapsnew

from newLib.config_validator import validate_config, load_config

from newLib.mapping_engine import MBMapper, MBClustMapper, BMMapper

###############################################################################
###############################################################################

if __name__ == '__main__':
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/'
    # Use a normal string with escaped backslashes to avoid a raw string ending with a single backslash
    path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'
    tProfilingStart = time.time()

    confPath      = path + 'config_old/'
    confFileName  = "AMOR.json"
    
    # confFileName  = "test1h.json"
    
    # fileName  = "MIRACLES24.json"
    # fileName  = "MGEMMA.json"
    # fileName  = "MIRACLES2bis.json"
    
    # fileName  = "CSPEC.json"

    config = maps.read_json_config(confPath+confFileName)
        
    parameters  = para.parameters(confPath+confFileName)
    parameters.loadConfigAndUpdate(config)
        
        
    filePath = path + 'data/'
    # file = 'miracles_trig2.pcapng'
    file = 'ESSmask2023_1000pkts.pcapng'
    # file = 'ESSmask2023.pcapng'
    
    # file = 'sampleData_NormalMode.pcapng'
    
    # file = 'sampleData_ClusteredMode.pcapng'
    
    # file = '20260611_083348_pkts100_Test-almostAllEmpty_00000.pcapng'
    
    # file = '20260611_083055_pkts100_Test-full_00000.pcapng'
    
    # file = 'testData.pcapng'
    
    # file = 'miracles_source_on_left_red.pcapng'

    # file = 'CSPEC1.pcapng'

   ########################
    
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = False
    
    typeOfLoading = 'allocate'
    # # typeOfLoading = 'quick'
    
    timeResolutionType='fine'
    
    
    operationMode = config.DETparameters.operationMode

    pcap = pcapr.pcapng_reader(filePath+file,NSperClockTick=11.356860963629653,
                               MONhw=config.MONmap.hardwareType, MONconn=config.MONmap.connectionType, MONring=11, 
                               timeResolutionType=timeResolutionType, 
                               sortByTimeStampsONOFF=parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, 
                               operationMode=operationMode,pcapLoadingMethod=typeOfLoading)

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
    
    calibPath = path + 'calib/'
    calibFile = 'AMOR_calib_20231111002842.json'
    
    
    # calibFile =  'ill_efu_time_calib_mod.json'
    
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
    
    

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)    
    
    print('\n ------------------------------------------------------ \n')
    
    ###############################################################################
    ###############################################################################
    # HERE STARTS NEW CODE 

    tProfilingStart = time.time()
    
    confPath      = path + 'config/'
    
    confFileName  = 'AMOR.json'
    
    # confFileName  = 'test1hybrid.json'
    
    # ff   = open(confPath+confFileName,'r') 
    # confignew = json.load(ff)
    
    confignew = load_config(confPath+confFileName)
    validate_config(confignew)
    
    
    
    parameters.VMMsettings.timeResolutionType = timeResolutionType

    newreader = reader.PcapngFileReader(
            file_path  = filePath+file,
            parameters = parameters,
            config     = confignew,
        )
    newreader.run()
    
    readoutsNEW  = newreader.readouts_vmm_normal
    # readoutsNEWc = newreader.readouts_vmm_clustered

    readoutsArrayNEW  = readoutsNEW.get_data_frame()
    
    # readoutsArrayNEWc  = readoutsNEWc.get_data_frame()
    
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
    
    hitsArrayNEW = hitsNEW.get_data_frame()
    
    
    tt = hitsNEW.matrix['timeStamp'] - hits.timeStamp
    
    
    # tt = hitsArrayNEW['timeStamp'] - hits.timeStamp
    
    aa = hitsArrayNEW['adc'] - hits.ADC
    
    pp = hitsArrayNEW['plane'] - hits.WorS
    
    #######################################
    #######################################

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)
    
    ###############################################################################
    ###############################################################################
   
    
    
    