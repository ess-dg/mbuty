#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 22 10:51:24 2026

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

# from lib import libVMMcalibration as cal 

from lib import libKafkaReader as kaf

try: 
    ####### if you run default
    from lib import libMapping_old as maps
    from lib import libParameters as para

except ImportError:
    ####### if you run in lib 
    import libMapping_old as maps
    import libParameters as para


# from newLib import kafka_reader

from newLib.kafka_reader import KafkaReader

from lib import libMapping as mapsnew

###############################################################################
###############################################################################

if __name__ == '__main__':
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/'
    # Use a normal string with escaped backslashes to avoid a raw string ending with a single backslash
    # path = 'C:\\Projects\\dg_MultiBlade_MBUTY_original\\MBUTYcap\\'
    tProfilingStart = time.time()

    confPath      = path + 'config/'
    confFileName  = "AMOR.json"
    
    # fileName  = "MIRACLES24.json"
    # fileName  = "MGEMMA.json"
    # fileName  = "MIRACLES2bis.json"
    
    # fileName  = "CSPEC.json"

    config = maps.read_json_config(confPath+confFileName)
        
    parameters  = para.parameters(confPath+confFileName)
    parameters.loadConfigAndUpdate(config)
    
    
    parameters.kafkaSettings.broker       = '127.0.0.1:9092'
    parameters.kafkaSettings.topic        = 'freia_debug'
    parameters.kafkaSettings.numOfPackets =  100      #packets
    
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF  = False
        
        
    testing = True 
         
    pcap = kaf.kafka_reader(NSperClockTick=parameters.clockTicks.NSperClockTick, nOfPackets = parameters.kafkaSettings.numOfPackets, \
            broker = parameters.kafkaSettings.broker, topic = parameters.kafkaSettings.topic,\
            MONhw = parameters.config.MONmap.hardwareType, MONconn = parameters.config.MONmap.connectionType, MONring = parameters.config.MONmap.RingID, \
            timeResolutionType =parameters.VMMsettings.timeResolutionType, sortByTimeStampsONOFF=parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, \
            operationMode=parameters.config.DETparameters.operationMode, testing=testing)
    

    readouts = pcap.readouts
    
    readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
    
    heartbeats1 = readouts.heartbeats
    heartbeats2 = readouts.removeNonESSpacketsHeartbeats(readouts.heartbeats)
    
    readouts.checkChopperFreq()
    
    readouts.checkInvalidToFsInReadouts()
  

    tElapsedProfiling = time.time() - tProfilingStart
    print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)    
    
    ###############################################################################

    tProfilingStart = time.time()

    confFileName  = 'AMOR26.json'
    
    
    ff   = open(confPath+confFileName,'r') 
    confignew = json.load(ff)


    newreader = KafkaReader(
            parameters = parameters,
            config     = confignew,
            testing = testing
        )
    newreader.run()

    readoutsArrayNEW  = newreader.readouts_vmm_normal.get_data_frame()
    
    
    
    aa = readoutsArrayNEW['tdc'] - readoutsArray[:,10]
    

    # tElapsedProfiling = time.time() - tProfilingStart
    # print('\n Data Loading Completed in %.2f s' % tElapsedProfiling)