#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 25 10:46:16 2021

@author: francescopiscitelli
"""

import numpy as np
import time
import os
import sys
import matplotlib.pyplot as plt


# import the library with all specific functions that this code uses 
from lib import libReadPcapngVMM as pcapr
from lib import libSampleData as sdat
from lib import libMapping as maps
from lib import libCluster as clu
from lib import libAbsUnitsAndLambda as absu
from lib import libHistograms as hh
from lib import libFileManagmentUtil as fd
from lib import libParameters as para
from lib import libTerminal as ta
from lib import libPlotting as plo


###############################################################################
###############################################################################

# STILL TO IMPLEMENT:
#     - soft theresholds 
#     - save reduced data
#     - monitor

###############################################################################
###############################################################################
profiling = para.profiling()
print('----------------------------------------------------------------------')
plt.close("all")
# check version
para.checkPythonVersion()
# get current path
currentPath = os.path.abspath(os.path.dirname(__file__))+'/'
###############################################################################
###############################################################################
# read json and create parameters for plotting and analisys 

parameters = para.parameters(currentPath)

configFilePath  = currentPath+'config/'
# configFileName  = "MB300_AMOR_config.json"
configFileName  = "MB300_FREIA_config.json"

config = maps.read_json_config(configFilePath+configFileName)

parameters.loadConfigParameters(config)

###############################################################################
###############################################################################
###############################################################################
###############################################################################
# edit parameters for plotting and analisys here:

parameters.fileManagement.sync = False

parameters.fileManagement.openMode = 'fileName'

parameters.fileManagement.fileName = 'freia_1k_pkts_ng.pcapng'

# parameters.fileManagement.fileName = 'vmm3a_Freia.pcapng'

# parameters.fileManagement.fileName = 'freia_1k.pcap'

parameters.cassettes.cassettes = [1,2,3,4,5,6]

parameters.cassettes.cassettes = [1]

parameters.MONitor.MONOnOff = False

parameters.wavelength.distance = 19000

parameters.dataReduction.timeWindow = 1.5e-6

parameters.plotting.showStat = 'globalStat'

parameters.configJsonFile.offset1stWires = 10

# self.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'

###############################################################################
###############################################################################
parameters.update()
###############################################################################
###############################################################################
#  create axes for plotting and histograms 

allAxis = hh.allAxis()
allAxis.createAllAxis(parameters)

#  here eventually edit axes 
# then update axes with: allAxis.updateAllAxis()

###############################################################################
###############################################################################
#  sync the data folder from remote computer to local folder 
if parameters.fileManagement.sync is True:
    terminal = ta.terminal()
    terminal.syncData(parameters.fileManagement.sourcePath, parameters.fileManagement.destPath)

###############################################################################
###############################################################################
# select data
fileDialogue = fd.fileDialogue(parameters)
fileDialogue.openFile()
###############################################################################
###############################################################################

cumulatedEvents = clu.events()

for fileName in fileDialogue.fileName:
    
    # # check if a file is pcapng otherwise pcap is converted into pcapng
    # conv = ta.pcapConverter(parameters)
    # conv.checkExtensionAndConvertPcap(fileDialogue.filePath+fileName)
    
    # if conv.flag is False:
    #     fileName = conv.fileName_OUT
        
    # ### load data 
    # pcap = pcapr.pcapng_reader(fileDialogue.filePath+fileName)
    
    # pcap.read(timeResolutionType='fine')
    # readouts = pcap.readouts
    
    ####################    
    # # for debug
    # # generate sample readouts
    # aa = sdat.sampleReadouts_1()
    # aa.fill()
    # readouts = aa.readouts
    ####################
    
    # ### map data
    # md  = maps.mapDetector(readouts, config)
    # md.mappAllCassAndChannelsGlob()
    # hits = md.hits
    
    # hitsArray = md.hits.concatenateHitsInArrayForDebug()
    
    # if parameters.MONitor.MONOnOff is True:
    #     MON = maps.mapMonitor(readouts, config)
    #     hitsMON = MON.hits
        
        
    # ####################    
    # # for debug
    # # generate sample hits 
    Nhits = 350
     
    bb = sdat.sampleHitsMultipleCassettes()
    bb.generateGlob(Nhits)
    # hitsArray = bb.hits.concatenateHitsInArrayForDebug()
    hits = bb.hits   
    # ####################
    
    hits2 = maps.extractHitsPortion.extract(hits,182,300)
    hitsArray = hits2.concatenateHitsInArrayForDebug()
  
    ### clusterize
    cc = clu.clusterHits(hits2,parameters.plotting.showStat)
    cc.clusterizeManyCassettes(parameters.cassettes.cassettes, parameters.dataReduction.timeWindow)
    
    cumulatedEvents.append(cc.events)

eventsArraycap = cumulatedEvents.concatenateEventsInArrayForDebug() 
    
####################    
# for debug
# generate sample events 
Nevents = 100
 
dd = sdat.sampleEventsMultipleCassettes(parameters.cassettes.cassettes,'./data/')
dd.generateGlob(Nevents)
events  = dd.events
eventsArray = events.concatenateEventsInArrayForDebug()
eventsArray = eventsArray[72:100,:]
#################### 
    
 

hitsArray = np.concatenate( ( np.zeros((1,np.shape(hitsArray)[1]), dtype = 'float64'), hitsArray ), axis=0) 

hitsArray[:,0] = np.around(hitsArray[:,0],decimals=6)

deltaTime = np.diff(hitsArray[:,0])
deltaTime = np.concatenate(([0],deltaTime),axis=0) 

# clusterlogic = (np.absolute(deltaTime) <= (parameters.dataReduction.timeWindow*1.01))

timeWindRec = np.ceil(2e-6*1e6/3)/1e6+0.01e-6

clusterlogic = (np.absolute(deltaTime) <= (timeWindRec))

hitsArray = np.append(hitsArray, deltaTime[:,None], axis=1)

hitsArray = np.append(hitsArray, clusterlogic[:,None], axis=1)






######################################
# calculate  abs units

# ab = absu.calculateAbsUnits(cumulatedEvents, parameters)

# ab.calculatePositionAbsUnit()

# T0 = 0
# ab.calculateToFandWavelength(T0)

# cumulatedEvents = ab.events 


###############################################################################
###############################################################################
### plot

# parameters.HistNotification()

# pp = plo.plottingEvents(cumulatedEvents,allAxis)
    
# pp.plotXYToF(logScale = False, absUnits = False)

# pp.plotXLambda(logScale = False, absUnits = False)


# ppp = plo.plottingReadouts(readouts, config)
# ppp.plotChRaw(parameters.cassettes.cassettes)
# ppp.plotTimeStamps(parameters.cassettes.cassettes)

###############################################################################
###############################################################################
plt.show()
profiling.stop()
print('----------------------------------------------------------------------')
###############################################################################
###############################################################################


