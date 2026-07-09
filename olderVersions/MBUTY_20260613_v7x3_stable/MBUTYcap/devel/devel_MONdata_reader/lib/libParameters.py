#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  3 11:34:33 2021

@author: francescopiscitelli
"""

# from lib import libMapping as maps
# import libMapping as maps
import numpy as np
import os
import sys
import time
# from lib import libEventsSoftThresholds as thre
# import libEventsSoftThresholds as thre

###############################################################################

class checkPythonVersion():
        # check version
        if sys.version_info < (3,5):
           print('\n \033[1;31mPython version too old, use at least Python 3.5! \033[1;37m\n')
           print(' ---> Exiting ... \n')
           print('------------------------------------------------------------- \n')
           sys.exit()
           
           
###############################################################################
class profiling():
    def __init__(self):
        
        self.tProfilingStart = time.time() 

    def restart(self):
        
        self.tProfilingStart = time.time()
        
    def lap(self):       
           tElapsedProfiling = time.time() - self.tProfilingStart
           print('\n lap time: %.2f s' % tElapsedProfiling)
           
    def stop(self):       
           tElapsedProfiling = time.time() - self.tProfilingStart
           print('\nCompleted --> elapsed time: %.2f s' % tElapsedProfiling)
           
###############################################################################

class fileManagement():
      def __init__(self, currentPath='./'):
  
            self.sync = False
            
            self.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
            
            self.currentPath = currentPath
            
            self.sourcePath = ''
            self.destPath   = ''
            
            self.filePath = self.currentPath+'data/'
            self.fileName = []
            self.fileSerials = []
                     
            self.configFilePath = self.currentPath+'config/'
            self.configFileName = 'temp.json'
            
            self.thresholdFilePath = self.currentPath+'config/'
            self.thresholdFileName = 'temp.xlsx'
            
            # self.openMode = 'window'
            self.openMode = 'latest'
            
            self.saveReducedFileONOFF = False
            self.saveReducedPath = './'
            self.reducedNameMainFolder  = 'entry1'

            self.reducedCompressionHDFT  = 'gzip'  
            self.reducedCompressionHDFL  = 9     # gzip compression level 0 - 9
            
      def importConfigFileDetails(self,config=None):
          
          if config is None:
              
             self.configFilePath = './'
             self.configFileName = './'
              
          else:
          
            self.configFilePath = config.configFilePath
            self.configFileName = config.configFileName
 
            
class configJsonFile():
      def __init__(self, config=None):
          
          if config is None:
              
              self.detectorName = 'empty'
              
              self.numOfCassettes = 0
              
              self.orientation = 'empty'
                        
              #  by default the cassettes are the ones present in the json file 
              self.cassInConfig = [0]
              
              self.numOfWires  = 0
              self.numOfStrips = 0
              
              self.wirePitch  = 0
              self.stripPitch = 0
              
              self.bladesInclination = 0
              self.offset1stWires    = 0
              
          else:
              
              self.detectorName = config.DETparameters.name
              
              self.numOfCassettes = config.DETparameters.numOfCassettes
              
              self.orientation = config.DETparameters.orientation
                        
              #  by default the cassettes are the ones present in the json file 
              self.cassInConfig = config.DETparameters.cassInConfig
              
              self.numOfWires  = config.DETparameters.numOfWires
              self.numOfStrips = config.DETparameters.numOfStrips
              
              self.wirePitch  = config.DETparameters.wirePitch
              self.stripPitch = config.DETparameters.stripPitch
              
              self.bladesInclination = config.DETparameters.bladesInclination
              self.offset1stWires    = config.DETparameters.offset1stWires
          
class cassettes():  
      def __init__(self, configJsonFile):  
          #  by default the cassettes are the ones present in the json file
          self.cassettes = configJsonFile.cassInConfig
          
class clockTicks():
      def __init__(self):      
          
          self.NSperClockTick =  11.356860963629653  #ns per clock tick ESS for 88.0525 MHz
          self.clockFreq      =  1/self.NSperClockTick
          
class MONitor():
      def __init__(self):
    
    # MONITOR (if present)
    # NOTE: if the MON does not have any ToF, lambda and ToF spectra can be
    # still calculated but perhaps meaningless

          self.MONOnOff = True       #ON/OFF
            
          self.MONThreshold = 0   #threshold on MON, th is OFF if 0, any other value is ON
             
          self.plotMONtofPHS = False   #ON/OFF plotting (MON ToF and Pulse Height) 
            
          self.MONDistance  = 0   #mm distance of MON from chopper if plotMONtofPH == 1 (needed for lambda calculation if ToF)

class dataReduction():
    def __init__(self):
        

          self.timeWindow = 3e-6  #s default is 3us for clustering
          
          # not implented yet
          # overflowcorr      = True   #ON/OFF (does not affect the MONITOR)
          # zerosuppression   = True   #ON/OFF (does not affect the MONITOR)

          # software thresholds
          # NOTE: they are applied to the flipped or swapped odd/even order of ch!
          # th on ch number: 32 w and 32 s, one row per cassette 
          # 'OFF', ''fromFile'' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh

          self.softThresholdType = 'off'
          
          self.softThArray = np.zeros((0))

         
    def createThArrays(self, cassettes, parameters):      
        
          self.softThArray = thre.softThresholds(cassettes, parameters)

class pulseHeigthSpect():
    def __init__(self):
        
          self.plotPHS = False
          self.plotPHSlog = False
          self.energyBins = 128
          self.maxEnerg   = 70e3
          self.plotPHScorrelation = False
          
class plotting():
      def __init__(self, configJsonFile):
          
          self.configJsonFile = configJsonFile
          #  is you want stats of clusters per cassette or for all at once, 0 no  stat, individualStat stat per cass, globalStat stat all cass glob
          self.showStat = 'globalStat'
                    
          self.plotRawReadouts         = False
          self.plotReadoutsTimeStamps  = False
          self.plotRawHits             = False
          self.plotHitsTimeStamps      = False
          self.plotHitsTimeStampsVSChannels   = False
          self.plotChopperResets       = False
           
          self.plotInstRate    = False
          self.instRateBin     = 1e-6  # s
          
          self.plotToFDistr    = False
           
          self.ToFrange        = 0.1   # s
          self.ToFbinning      = 100e-6 # s
                    
          self.plotMultiplicity = False 
          
          self.plotABSunits = False
                    
          # 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
          self.positionReconstruction = 'W.max-S.cog'
               
          self.plotIMGlog = False
          
          self.coincidenceWS_ONOFF = True
          
          self.removeInvalidToFs = False
          
          self.hitogOutBounds = True
          
      def calculateDerivedParam(self):
             
           if self.positionReconstruction == 'W.max-S.max': # w x s max max
                 self.posWbins = int(self.configJsonFile.numOfWires)
                 self.posSbins = int(self.configJsonFile.numOfStrips)
           elif self.positionReconstruction == 'W.cog-S.cog': # w x s CoG CoG
                 self.posWbins = int(self.configJsonFile.numOfWires*2)
                 self.posSbins = int(self.configJsonFile.numOfStrips*2) 
           elif self.positionReconstruction == 'W.max-S.cog': # w x s max CoG
                 self.posWbins = int(self.configJsonFile.numOfWires)
                 self.posSbins = int(self.configJsonFile.numOfStrips*2)
             
           self.ToFbins  = round(self.ToFrange/self.ToFbinning) 
          
          
class wavelength():          
          
      def __init__(self):
        
          self.distance  = 0 #mm from chopper to detector front wire

          self.calculateLambda = False  

          self.plotXLambda      = False   
          
          self.plotLambdaDistr   = False

          self.lambdaBins  = 127
          self.lambdaRange = [1, 16]   #A
          
          self.chopperPeriod = 0.06  #s
          
          self.chopperFreq  = 1/self.chopperPeriod    #Hz

          #if chopper has two openings or more per reset of ToF
          self.multipleFramePerReset = False  #ON/OFF (this only affects the lambda calculation)
          self.numOfBunchesPerPulse  = 2
          self.lambdaMIN             = 2.7     #A

            # PickUpTimeShift = -0.002 #s on chopper, time shift betweeen pickup and chopper edge 
          self.chopperPickUpDelay =  13.5/(2.*180.) * self.chopperPeriod/self.numOfBunchesPerPulse  #s  
          
      def update(self):
         
          self.chopperFreq  = 1/self.chopperPeriod    #Hz
          self.chopperPickUpDelay =  13.5/(2.*180.) * self.chopperPeriod/self.numOfBunchesPerPulse  #s  

###############################################################################
###############################################################################               

class parameters():
    def __init__(self, currentPath='./'):
                
        self.fileManagement = fileManagement(currentPath)
        
    def init_empty(self):
        
        self.loadConfigParameters(config=None)
        
    def loadConfigParameters(self,config=None):

        self.config = config
 
        # self.fileManagement = fileManagement(self.fileManagement.currentPath)
        self.fileManagement.importConfigFileDetails(self.config)
        
        self.configJsonFile = configJsonFile(self.config)
        
        self.cassettes = cassettes(self.configJsonFile)
        
        self.clockTicks = clockTicks()
        
        self.dataReduction  = dataReduction()
        
        self.pulseHeigthSpect = pulseHeigthSpect()
        
        self.plotting = plotting(self.configJsonFile)
        self.plotting.calculateDerivedParam()
        
        self.wavelength = wavelength()
        
        self.MONitor = MONitor()
        
    def update(self):
        
        self.plotting.calculateDerivedParam()
        self.wavelength.update()
    
    def HistNotification(self):
        
        if self.plotting.hitogOutBounds is True:
            print('\n\t histogram outBounds param set as True (Events out of bounds stored in first and last bin)')
        else:
            print('\n\t histogram outBounds param set as False (Events out of bounds not stored in any bin)')

###############################################################################
###############################################################################

if __name__ == '__main__' :
    
    # currentPath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/'
    
    # parameters = parameters(currentPath)

    # configFilePath  = currentPath+'config/'
    # configFileName  = "MB300_FREIA_config.json"
    # config = maps.read_json_config(configFilePath+configFileName)

    # parameters.loadConfigParameters(config)
    
    # configFilePath  = './'+"MB300_AMOR_config.json"
    # config = maps.read_json_config(configFilePath)
    
    # aa = parameters(config)
    
    # aa.cassettes.cassettes = [1,3,4]

    # aa.update()

    # bb = aa.dataReduction.sth
    
    # checkPythonVersion()
    
    # prof= profiling()
    
    # time.sleep(2)
    
    # prof.lap()
    
    # prof.restart()
    
    # time.sleep(1)
    
    # prof.lap()
    
    # time.sleep(1.3)
    
    # prof.stop()
    
    # parameters2  = parameters('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/')
    
    # configFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/'+'config/'
    # # configFileName  = "MB300_AMOR_config.json"
    # configFileName  = "MB300_FREIA3_config.json"
    
    # config = maps.read_json_config(configFilePath+configFileName)
    # # parameters.loadConfigParameters(config)
    
    # parameters2.loadConfigParameters()
    
    # parr = parameters()
    # parr.init_empty()
    
    # parameters  = parameters(configFilePath)
    
    # config = maps.read_json_config(configFilePath+configFileName)
    # parameters.loadConfigParameters(config)
    
    # parameters.dataReduction.softThArray.ThW[:,1] = 5000
    
    configFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'

    configFileName  = "AMOR.json"

    config = maps.read_json_config(configFilePath+configFileName)
    
    parameters  = parameters(configFilePath)
    parameters.loadConfigParameters(config)
    
    