#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 30 14:18:41 2021

@author: francescopiscitelli
"""

import numpy as np
# import time
# import matplotlib.pyplot as plt


try: 
    ####### if you run default
    from lib import libAbsUnitsAndLambda
    from lib import libMappingR5560 as maps
    # from lib import libPlotting
    # from lib import libHistogramsR5560 as hh
    from lib import libClusterR5560 as clu
    from lib import libReadPcapng as pcapr
    from lib import libParameters as para

except ImportError:
    ####### if you run in lib 
    import libAbsUnitsAndLambda
    import libMappingR5560 as maps
    # import libPlotting
    # import libHistogramsR5560 as hh
    import libClusterR5560 as clu
    import libReadPcapng as pcapr
    import libParameters as para
    
    
###############################################################################
###############################################################################
#  import std dewfault class 

Tof2LambdaConverter = libAbsUnitsAndLambda.Tof2LambdaConverter
gateToF             = libAbsUnitsAndLambda.gateToF

###############################################################################
###############################################################################


class calculateAbsUnits():
    
    def __init__(self, events, parameters, text=''):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.__init__(self, events, parameters, text)    

    def calculateToF(self, removeInvalidToFs = False):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.calculateToF(self, removeInvalidToFs)

    def calculateWavelength(self):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.calculateWavelength(self)     

    def calculateWavelengthMON(self):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.calculateWavelengthMON(self)    
    
    def calculateToFandWavelength(self,removeInvalidToFs = False):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.calculateToFandWavelength(self,removeInvalidToFs) 

    def cleanInvalidToFs(self):
        """ Acts as a pointer/wrapper for the central library """
        return libAbsUnitsAndLambda.calculateAbsUnits.cleanInvalidToFs(self) 
    
    
    def calculatePositionAbsUnit(self):
        
        print('\033[1;36m\nCalculating positions ... \033[1;37m',end='')

        self.events.positionWmm = np.round(self.events.positionW*self.parameters.config.DETparameters.tubeLength,3)
        self.events.positionSmm = np.round(self.events.positionS*self.parameters.config.DETparameters.tubeSpacing,3)
        # self.events.positionZmm[:,:] = 0
        
     

###############################################################################
###############################################################################

if __name__ == '__main__':
    
   
   confFile  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'
   fileName  = "MIRACLES2.json"

   config = maps.read_json_config(confFile+fileName)
   
   parameters  = para.parameters(confFile+fileName)
   parameters.loadConfigAndUpdate(config)
   
   parameters.wavelength.distance = 6000
   
   filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file = 'MG_2col_2clusters.pcapng'
   file = 'miracles_trig2.pcapng'
     
   # file = 'MG_2col_1cluster.pcapng'
   
   # file = 'miracles_source_mask.pcapng'

   filePathAndFileName = filePath+file
   
   pcapng = pcapr.pcapng_reader(filePathAndFileName)
   
   pcapr.checkIfDataIsSupported(pcapng.flagSupported)

   readouts = pcapng.readouts
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   
   
   md  = maps.mapDetector(readouts, config)
   md.mappAllCassAndChannelsGlob()
   hits = md.hits
   hitsArray  = hits.concatenateHitsInArrayForDebug()
    
    
   cc = clu.clusterHits(hits,showStat='globalStat')
   cc.clusterizeManyCassettes(config.DETparameters.cassInConfig, timeWindow=1e-6)
   events = cc.events
   deltaTimeWS = cc.deltaTimeClusterWSall
    
   eventsArray = events.concatenateEventsInArrayForDebug()
 
   
   ab = calculateAbsUnits(events, parameters)
   ab.calculatePositionAbsUnit()
   
   ab.calculateToF(removeInvalidToFs=False)

   ab.calculateWavelength()

   events2 = ab.events 
   eventsArray2 = events.concatenateEventsInArrayForDebug()
   
   
   
   # configFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/config/'+"MG.json"
   # filePathD       = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/data/'+'freiatest.pcapng'
   
   # tProfilingStart = time.time()
   # parameters  = para.parameters('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/')

   # config = maps.read_json_config(configFilePath)
   # parameters.loadConfigAndSetParameters(config)
   
   #     ## distance in mm from chopper and wires 0 of detector
   # parameters.wavelength.distance = 8038
    
   #  ##ON/OFF
   # parameters.wavelength.calculateLambda = True
    
   #  ##ON/OFF
   # parameters.wavelength.plotLambda = True
    
   # parameters.wavelength.lambdaBins  = 127
   # parameters.wavelength.lambdaRange = [1, 25]   #A
    
   # parameters.wavelength.chopperPeriod = 0.06 #s
    
   #  #if chopper has two openings or more per reset of ToF
   # parameters.wavelength.multipleFramePerReset = True  #ON/OFF (this only affects the lambda calculation)
   # parameters.wavelength.numOfBunchesPerPulse  = 2
   # parameters.wavelength.lambdaMIN             = 2.7     #A
    
   #  # #s on chopper, time shift betweeen pickup and chopper edge 
   # parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 
    
   #  ###############
   # parameters.plotting.ToFrange        = 0.1   # s
   # parameters.plotting.ToFbinning      = 100e-6 # s
   

   
   # # pcapng = pcapr.pcapng_reader(filePathD, NSperClockTick, config.MONmap.TTLtype, config.MONmap.RingID,  timeResolutionType='fine', sortByTimeStampsONOFF = False, operationMode=config.DETparameters.operationMode)

   # pcapng = pcapr.pcapng_reader(filePathD, parameters.clockTicks.NSperClockTick, MONTTLtype = config.MONmap.TTLtype, MONring = config.MONmap.RingID, \
   # timeResolutionType = parameters.VMMsettings.timeResolutionType, sortByTimeStampsONOFF = parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, operationMode=config.DETparameters.operationMode)


   # readouts = pcapng.readouts
   # readoutsArray = readouts.concatenateReadoutsInArrayForDebug()

   # md  = maps.mapDetector(readouts, config)
   # md.mappAllCassAndChannelsGlob()
   # hits = md.hits
   # hitsArray  = hits.concatenateHitsInArrayForDebug()
   
   
   # parameters.dataReduction.timeWindow = 0.3e-6
   
   # cc = clu.clusterHits(hits,parameters.plotting.showStat)
   # cc.clusterizeManyCassettes(parameters.config.DETparameters.cassInConfig, parameters.dataReduction.timeWindow)
   # events1 = cc.events
   # eventsArray1 = events1.concatenateEventsInArrayForDebug()


   # ab = calculateAbsUnits(events1, parameters)
   # ab.calculatePositionAbsUnit()
   
   # ab.calculateToF(parameters.plotting.removeInvalidToFs)
   

   # ab.calculateWavelength()
   

   
   # events2 = ab.events 
   
    # ab.calculateWavelength()
   
   

   # events = ab.events 
   # eventsArray2 = events2.concatenateEventsInArrayForDebug()
   # 
   
   # allAxis = hh.allAxis()
   # allAxis.createAllAxis(parameters)
   
   # #  XY and XToF
   # plev = plo.plottingEvents(events,allAxis,True)
   # plev.plotXYToF(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits)
    
   #  #  lambda
  
   # plev.plotXLambda(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits)
   
   
   
   # tElapsedProfiling = time.time() - tProfilingStart
   # print('\n Completed in %.2f s' % tElapsedProfiling) 