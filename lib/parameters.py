#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  3 11:34:33 2021

@author: francescopiscitelli
"""

import numpy as np
import os
import sys
import time 

           
###############################################################################

class dumpSettings():
    def __init__(self,currentPath='./'):
        
        # self.auto = False
        
        self.interface = 'p4p1'
        
        self.destTestData  = os.path.join(currentPath,'data')
        
        self.typeOfCapture = 'packets'
        
        self.quantity   = 500
        
        self.numOfFiles = 1
        self.delay      = 0
        
        self.fileName   = 'testData'
        
        self.fileNameOnly = True

class fileManagement():
      def __init__(self, currentPath='./'):
  
            self.fileNameSave = 'test'
            
            # self.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
            self.pathToTshark = '/usr/sbin/'
            
            self.currentPath = currentPath
            
            self.sourcePath = ''
            self.destPath   = ''
            
            self.filePath = os.path.join(self.currentPath,'data')
            self.fileName = []
            self.fileSerials = []
                     
            self.configFilePath = os.path.join(self.currentPath,'config')
            self.configFileName = 'temp.json'
                        
            self.calibFilePath  = os.path.join(self.currentPath,'calib')
            self.calibFileName  = 'temp.json'
            
            self.thresholdFilePath = os.path.join(self.currentPath,'config')
            self.thresholdFileName = 'temp.xlsx'
            
            # self.openMode = 'window'
            self.openMode = 'latest'
            
            self.pcapLoadingMethod = 'allocate'
            
            self.saveReducedFileONOFF = False
            self.saveReducedPath = './'
            self.reducedNameMainFolder  = 'entry1'

            self.reducedCompressionHDFT  = 'gzip'  
            self.reducedCompressionHDFL  = 9     # gzip compression level 0 - 9

      def parseFileSerialsList(self):
          
            input_list = self.fileSerials
            result = []
            for item in input_list:
                if isinstance(item, int):
                    # It's already a number, just add it
                    result.append(item)
                elif isinstance(item, str) and '-' in item:
                    # It's a range string like "0-4"
                    start, end = map(int, item.split('-'))
                    # Use range(start, end + 1) to make it inclusive
                    result.extend(range(start, end + 1))
                elif isinstance(item, str):
                    # It's a string digit like "5"
                    result.append(int(item))
                    
            # Sort and remove duplicates if necessary
            self.fileSerials =  sorted(list(set(result)))     
            
 
    
class kafkaSettings():
    def __init__(self):
          
        self.broker       = '127.0.0.1:9092'
        self.topic        = 'freia_debug'
        self.numOfPackets = 100
            
class timeSettings(): 
    def __init__(self):
        
        self.timeResolutionType            = 'fine'
        self.sortReadoutsByTimeStampsONOFF = True

          
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
          
          # for PHS hists 
          self.energyBins = 128
          self.maxEnerg   = 1700

class dataReduction():
    def __init__(self):
        

          self.timeWindow = 0.5e-6  #s default is 0.5us for clustering
          
          # not implented yet
          # overflowcorr      = True   #ON/OFF (does not affect the MONITOR)
          # zerosuppression   = True   #ON/OFF (does not affect the MONITOR)

          # software thresholds
          # NOTE: they are applied to the flipped or swapped odd/even order of ch!
          # th on ch number: 32 w and 32 s, one row per cassette 
          
          # 'OFF', ''fromFile'' = File With Threhsolds Loaded, 
          # 'userDefined' = User defines the Thresholds in an array softTh, 
          # 'constants' = User defines a single threshold applied to all wires, and another for all the strips 
          self.softThresholdType = 'off'
          
          self.softThArray = np.zeros((0))
          
          self.calibrateVMM_ADC_ONOFF = False

class pulseHeigthSpect():
    def __init__(self):
        
          self.plotPHS    = False
          self.plotPHSlog = False
          self.energyBins = 128
          self.maxEnerg   = 2048
          self.plotPHScorrelation = False
          
class plotting():
      def __init__(self):
     
          # self.config = config
          
          #  is you want stats of clusters per cassette or for all at once, 0 no  stat, individualStat stat per cass, globalStat stat all cass glob
          self.showStat = 'globalStat'

          # Primary plotting surface is the PySide6 dashboard. Flip this off
          # to fall back to plain matplotlib windows (one per active plot,
          # via plt.show()) without the dashboard's extra moving parts --
          # useful as a backup if the dashboard itself is misbehaving.
          self.useDashboard = True

          self.plottingInSections       = False
          self.plottingInSectionsBlocks = 5
                    
          self.plotRawReadouts         = False
          self.plotReadoutsTimeStamps  = False
          self.plotADCvsCh             = False
          self.plotADCvsChlog          = False
          self.plotChopperResets       = False
          
          self.plotRawHits             = False
          self.plotHitsTimeStamps      = False
          self.plotHitsTimeStampsVSChannels   = False

          self.plotTimeBetwEv    = False
          self.timeBetwEvBin     = 1e-6  # s
          
          self.plotToFDistr    = False
           
          self.ToFrange        = 0.1   # s
          self.ToFbinning      = 100e-6 # s
          
          self.ToFGate         = False
          self.ToFGateRange    = [0.0,0.5]   # s
                    
          self.plotMultiplicity = False 
          
          self.plotABSunits = False
                    
          # 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
          self.positionReconstruction = 'W.max-S.cog'
               
          self.plotIMGlog = False
          
          self.coincidenceWS_ONOFF = True
          
          self.removeInvalidToFs = False
          
          self.histogOutBounds = True
          
          self.bareReadoutsCalculation = False                  
             
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

            # PickUpTimeShift = -0.002 #s on chopper, time shift betweeen chopper edge 
          self.chopperPickUpDelay =  13.5/(2.*180.) * self.chopperPeriod/self.numOfBunchesPerPulse  #s  
          
###############################################################################
###############################################################################               

class parameters():
    def __init__(self, currentPath='./'):
                
        self.fileManagement = fileManagement(currentPath)
        
        self.acqMode = None
        
        self.dumpSettings   = dumpSettings(self.fileManagement.currentPath)
         
        self.clockTicks     = clockTicks()
        
        self.dataReduction  = dataReduction()
        
        self.pulseHeigthSpect = pulseHeigthSpect()
        
        self.plotting = plotting()
        
        self.wavelength = wavelength()
        
        self.MONitor = MONitor()
        
        self.kafkaSettings = kafkaSettings()
        
        self.timeSettings   = timeSettings()
        
    def validate(self):
        """
        Validates and normalizes parameter combinations, forcing dependent
        flags and printing info about any overrides before the pipeline runs.
        """
        self._validateWavelengthDependencies()
        self._validateHistNotification()
        self._set_acqMode()
        # future checks go here

    def _validateWavelengthDependencies(self):
        if self.fileManagement.saveReducedFileONOFF and not self.wavelength.calculateLambda:
            self.wavelength.calculateLambda = True
            print('\nLambda calculation turned ON to save reduced DATA')

        if not self.wavelength.calculateLambda:
            self.wavelength.plotXLambda = False
            self.wavelength.plotLambdaDistr = False

    def _validateHistNotification(self):
        if self.plotting.plottingInBlocks and self.plotting.histogOutBounds:
            print('\n\t histogram outBounds param set as True (Events out of bounds stored in first and last bin) -> overridden with False since plottingInSections is True')
            self.plotting.histogOutBounds = False

        elif self.plotting.histogOutBounds:
            print('\n\t histogram outBounds param set as True (Events out of bounds stored in first and last bin)')
        else:
            print('\n\t histogram outBounds param set as False (Events out of bounds not stored in any bin)')
            
 
      
    def _set_acqMode(self):
                    
            if self.acqMode == 'pcap-sync':
                
                print('Acquisition mode: {} - Sync turned ON to retrieve data from remote computer'.format(self.acqMode))
                
            elif self.acqMode == 'pcap-local':
                
                print('Acquisition mode: {} -  Sync turned OFF since you selected pcap-local mode'.format(self.acqMode))
                
                self.dumpSettings.destTestData = self.fileManagement.filePath
                
                self.dumpSettings.fileName     = self.fileManagement.fileNameSave
                
                self.dumpSettings.numOfFiles = 1
                self.dumpSettings.delay      = 0
                
                self.dumpSettings.fileNameOnly = False
            
                self.fileManagement.openMode = 'latest'  
                self.fileManagement.filePath =  self.dumpSettings.destTestData
                # self.fileManagement.fileName =  [self.dumpSettings.fileName]

    
                
            elif self.acqMode == 'pcap-local-overwrite':
                
                print('Acquisition mode: {} - Sync turned OFF since you selected pcap-local-overwrite mode'.format(self.acqMode))
                
                self.dumpSettings.destTestData = os.path.join(self.fileManagement.currentPath , 'data')
                
                self.dumpSettings.fileName     = 'testData'
                
                self.dumpSettings.numOfFiles = 1
                self.dumpSettings.delay      = 0
                
                self.dumpSettings.fileNameOnly = True
            
                self.fileManagement.openMode = 'fileName'  
                self.fileManagement.filePath =  self.dumpSettings.destTestData
                self.fileManagement.fileName =  [self.dumpSettings.fileName]
                
 
            elif self.acqMode == 'kafka':
            
                self.fileManagement.openMode = None
                print('Acquisition mode: {} - Acquisition through kafka stream'.format(self.acqMode))
        
                
            elif self.acqMode == 'off':
                
                print('Acquisition mode: {} - No acquisition is performed, just open a file and visualize'.format(self.acqMode))
            
            else:
                
                print('\n\t\033[1;31mERROR: Acquisition mode (found {}) can only be only one of these 5 options: off, pcap-sync, pcap-local, pcap-local-overwrite or kafka ---> Exiting ... \n\033[1;37m'.format(self.acqMode),end='') 
                time.sleep(2)
                sys.exit()        

 