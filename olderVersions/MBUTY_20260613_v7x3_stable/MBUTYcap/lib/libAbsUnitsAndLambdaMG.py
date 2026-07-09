#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 30 14:18:41 2021

@author: francescopiscitelli
"""

import numpy as np
import time
import matplotlib.pyplot as plt

try:

    from lib import libMappingMG as maps
    from lib import libCluster as clu
    from lib import libParameters as para
    from lib import libReadPcapng as pcapr
    from lib import libAbsUnitsAndLambda

except ImportError:

    import libMappingMG as maps
    import libCluster as clu
    import libParameters as para
    import libReadPcapng as pcapr
    import libAbsUnitsAndLambda


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
         
         # IF glob coordinates :
         #  wires are in global coord !!! so mod 20 to bring it back from 0 to 19 on each row 
         # wireChforZ = np.mod(self.events.positionW,numOfWiresPerRow)
         #  
         # rowNumGlob  = np.floor_divide(self.events.positionW,numOfWiresPerRow)
         # cassetteNum = np.floor_divide(self.events.positionW,self.parameters.config.DETparameters.numOfWires)
         
         # bring back global coordinates into local in each column
         
         tempPosW  = np.copy(self.events.positionW)
           
         for k, cass in enumerate(self.parameters.config.DETparameters.cassInConfig):     
              index = k
              indexes = np.argwhere(self.events.Cassette == cass)
              # self.events.positionW[selection] = self.events.positionW[selection] - index*self.parameters.config.DETparameters.numOfWires
              tempPosW[indexes]  = self.events.positionW[indexes] - index*self.parameters.config.DETparameters.numOfWires
        ########################
                 
         numOfWiresPerRow = self.parameters.config.DETparameters.wiresPerRow
         
         linearOffset  = self.parameters.config.DETparameters.linearOffset1stWires    #mm
         angularOffset = self.parameters.config.DETparameters.angularOffset    #deg
         
         # sine = np.sin(np.deg2rad(angularOffset)) 
         # cosi = np.cos(np.deg2rad(angularOffset)) 
  
         #   mod 20 to bring it back from 0 to 19 on each row 
         wireChforZ = np.mod(tempPosW,numOfWiresPerRow)
         #  this identifies the row in each column 
         wireChforX = np.floor_divide(tempPosW,numOfWiresPerRow)
         

         #mm per row of 20wires along X  this loop is not needed 
         # for k, cass in enumerate(self.parameters.config.DETparameters.cassInConfig):
             
         #     selectW = self.events.Cassette == cass
         #     self.events.positionWmm[selectW]  = np.round(  (wireChforX[selectW] * (self.parameters.config.DETparameters.wirePitchX)), decimals=2 )  #mm
            
         
         self.events.positionWmm  = np.round(  (wireChforX * (self.parameters.config.DETparameters.wirePitchX)), decimals=2 )  #mm
  
         #mm Y grids
         selectS = self.events.positionS >= 0
         self.events.positionSmm[selectS]  = np.round((self.events.positionS[selectS] * self.parameters.config.DETparameters.stripPitchY ), decimals = 2) #mm
         self.events.positionSmm[~selectS] = -1                             
           
         #mm Z in depth across wires , approx is circular arrangement 
         self.events.positionZmm = np.round(( wireChforZ * (self.parameters.config.DETparameters.wirePitchZ)), decimals = 2) #mm 
         
         ########################
         # now add columns relative position  ... 
         
         for k, cass in enumerate(self.parameters.config.DETparameters.cassInConfig):
             selectCass = self.events.Cassette == cass
             
             # here do trigonometry ... 
     

###############################################################################
###############################################################################

if __name__ == '__main__':
    
   plt.close("all")
   
   configFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/config/'+"MG.json"
   filePathD       = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/data/'+'freiatest.pcapng'
   
   tProfilingStart = time.time()
   parameters  = para.parameters('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_MGdevel/')

   config = maps.read_json_config(configFilePath)
   parameters.loadConfigAndSetParameters(config)
   
       ## distance in mm from chopper and wires 0 of detector
   parameters.wavelength.distance = 8038
    
    ##ON/OFF
   parameters.wavelength.calculateLambda = True
    
    ##ON/OFF
   parameters.wavelength.plotLambda = True
    
   parameters.wavelength.lambdaBins  = 127
   parameters.wavelength.lambdaRange = [1, 25]   #A
    
   parameters.wavelength.chopperPeriod = 0.06 #s
    
    #if chopper has two openings or more per reset of ToF
   parameters.wavelength.multipleFramePerReset = True  #ON/OFF (this only affects the lambda calculation)
   parameters.wavelength.numOfBunchesPerPulse  = 2
   parameters.wavelength.lambdaMIN             = 2.7     #A
    
    # #s on chopper, time shift betweeen pickup and chopper edge 
   parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 
    
    ###############
   parameters.plotting.ToFrange        = 0.1   # s
   parameters.plotting.ToFbinning      = 100e-6 # s
   

   
   # pcapng = pcapr.pcapng_reader(filePathD, NSperClockTick, config.MONmap.TTLtype, config.MONmap.RingID,  timeResolutionType='fine', sortByTimeStampsONOFF = False, operationMode=config.DETparameters.operationMode)

   pcapng = pcapr.pcapng_reader(filePathD, parameters.clockTicks.NSperClockTick, MONTTLtype = config.MONmap.TTLtype, MONring = config.MONmap.RingID, \
   timeResolutionType = parameters.VMMsettings.timeResolutionType, sortByTimeStampsONOFF = parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, operationMode=config.DETparameters.operationMode)


   readouts = pcapng.readouts
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()

   md  = maps.mapDetector(readouts, config)
   md.mappAllCassAndChannelsGlob()
   hits = md.hits
   hitsArray  = hits.concatenateHitsInArrayForDebug()
   
   
   parameters.dataReduction.timeWindow = 0.3e-6
   
   cc = clu.clusterHits(hits,parameters.plotting.showStat)
   cc.clusterizeManyCassettes(parameters.config.DETparameters.cassInConfig, parameters.dataReduction.timeWindow)
   events1 = cc.events
   eventsArray1 = events1.concatenateEventsInArrayForDebug()


   ab = calculateAbsUnits(events1, parameters)
   ab.calculatePositionAbsUnit()
   
   ab.calculateToF(parameters.plotting.removeInvalidToFs)
   

   ab.calculateWavelength()
   

   
   events2 = ab.events 
   
    # ab.calculateWavelength()
   
   

   # events = ab.events 
   eventsArray2 = events2.concatenateEventsInArrayForDebug()
   
   
   # allAxis = hh.allAxis()
   # allAxis.createAllAxis(parameters)
   
   # #  XY and XToF
   # plev = plo.plottingEvents(events,allAxis,True)
   # plev.plotXYToF(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits)
    
   #  #  lambda
  
   # plev.plotXLambda(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits)
   
   
   
   tElapsedProfiling = time.time() - tProfilingStart
   print('\n Completed in %.2f s' % tElapsedProfiling) 