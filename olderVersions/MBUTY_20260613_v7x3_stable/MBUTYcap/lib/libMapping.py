#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 20 09:14:18 2021

@author: francescopiscitelli
"""

import numpy as np
import json
import time 
import os
import sys
import copy
from pathlib import Path 


# NOTE: THIS SUPPORTS ONLY 1 MONITOR
###############################################################################
###############################################################################

class hits():            
    def __init__(self): 
        
        datype = 'int64'
        
        self.Cassette    = np.zeros((0), dtype = datype)
        self.ADC         = np.zeros((0), dtype = datype)
        self.timeStamp   = np.zeros((0), dtype = datype)
        self.WorS        = -1*np.ones((0), dtype = datype)
        self.WiresStrips = -1*np.ones((0), dtype = datype)
        self.PulseT      = np.zeros((0), dtype = datype)
        self.PrevPT      = np.zeros((0), dtype = datype)
        self.Durations   = np.zeros((0), dtype = datype)
        self.Duration    = np.zeros((1), dtype = datype)
        self.WiresStrips1= -1*np.ones((0), dtype = datype)
        self.ADC1        = np.zeros((0), dtype = datype)
        self.mult0       = np.zeros((0), dtype = datype)
        self.mult1       = np.zeros((0), dtype = datype)
        
    def importReadouts(self,readouts):    
        
        self.ADC       = readouts.ADC
        self.ADC1      = readouts.ADC1
        self.timeStamp = readouts.timeStamp
        self.PulseT    = readouts.PulseT
        self.PrevPT    = readouts.PrevPT
        self.mult0     = readouts.mult0
        self.mult1     = readouts.mult1
        
        self.Durations = readouts.Durations
        self.Duration  = np.ones((1), dtype = 'int64')*(np.sum(readouts.Durations))
        
        leng = len(readouts.Channel)
        
        # 0 if wire, 1 if strip once mapped 
        # self.WorS = np.copy(readouts.ASIC)
        self.WorS = -1*np.ones((leng), dtype = 'int64') 
        
        self.Cassette     = -1*np.ones((leng), dtype = 'int64')        

        self.WiresStrips  = -1*np.ones((leng), dtype = 'int64')
        self.WiresStrips1 = -1*np.ones((leng), dtype = 'int64')
        
    def append(self, hit):
        
        self.Cassette    = np.concatenate((self.Cassette, hit.Cassette), axis=0)
        self.ADC         = np.concatenate((self.ADC, hit.ADC), axis=0)
        self.WorS        = np.concatenate((self.WorS, hit.WorS), axis=0)
        self.timeStamp   = np.concatenate((self.timeStamp, hit.timeStamp), axis=0)
        self.WiresStrips = np.concatenate((self.WiresStrips, hit.WiresStrips), axis=0)
        self.PulseT      = np.concatenate((self.PulseT, hit.PulseT), axis=0)
        self.PrevPT      = np.concatenate((self.PrevPT, hit.PrevPT), axis=0)
        self.ADC1         = np.concatenate((self.ADC1, hit.ADC1), axis=0)
        self.WiresStrips1 = np.concatenate((self.WiresStrips1, hit.WiresStrips1), axis=0)
        self.mult0        = np.concatenate((self.mult0, hit.mult0), axis=0)
        self.mult1        = np.concatenate((self.mult1, hit.mult1), axis=0)
        
        self.Durations   = np.append(self.Durations, hit.Durations)
        self.Duration    = self.Duration+hit.Duration
             
    def concatenateHitsInArrayForDebug(self):
        
        leng = len(self.WiresStrips)
        
        if leng >= 1:
        
            hitsArray = np.zeros((leng,11),dtype = 'int64')
            
            hitsArray[:,0] = self.timeStamp
            hitsArray[:,1] = self.Cassette
            hitsArray[:,2] = self.WorS
            hitsArray[:,3] = self.WiresStrips
            hitsArray[:,4] = self.ADC
            hitsArray[:,5] = self.PulseT
            hitsArray[:,6] = self.PrevPT
            hitsArray[:,7] = self.WiresStrips1
            hitsArray[:,8] = self.ADC1
            hitsArray[:,9] = self.mult0
            hitsArray[:,10] = self.mult1
            
        else:
            
            hitsArray = None
            

        return hitsArray
   
    def removeUnmappedData(self):
  

        toBeRemoved  = self.Cassette == -1

        self.timeStamp    = self.timeStamp[~toBeRemoved]
        self.Cassette     = self.Cassette[~toBeRemoved]
        self.WorS         = self.WorS[~toBeRemoved]
        self.WiresStrips   = self.WiresStrips[~toBeRemoved]
        self.ADC          = self.ADC[~toBeRemoved]
        self.PulseT       = self.PulseT[~toBeRemoved]
        self.PrevPT       = self.PrevPT[~toBeRemoved]
        self.WiresStrips1 = self.WiresStrips1[~toBeRemoved]
        self.ADC1         = self.ADC1[~toBeRemoved]
        self.mult0        = self.mult0[~toBeRemoved]
        self.mult1        = self.mult1[~toBeRemoved]
        
        if np.sum(toBeRemoved) >= 1:
            print('\t --> removing unmapped data from hits ...')
        else:
            print('\t --> no unmapped data in these hits ...')
            
class extractHitsPortion():
    
    def extract(self,hits,start,stop):
        
        hitsEx = hits
    
        hitsEx.Cassette  = hits.Cassette[start:stop]
        hitsEx.ADC       = hits.ADC[start:stop]
        hitsEx.WorS      = hits.WorS[start:stop]
        hitsEx.timeStamp = hits.timeStamp[start:stop]
        hitsEx.WiresStrips = hits.WiresStrips[start:stop]
        hitsEx.PulseT    = hits.PulseT[start:stop]
        hitsEx.PrevPT    = hits.PrevPT[start:stop]
        hitsEx.ADC1         = hits.ADC1[start:stop]
        hitsEx.WiresStrips1 = hits.WiresStrips1[start:stop]
        hitsEx.mult0        = hits.mult0[start:stop]
        hitsEx.mult1        = hits.mult1[start:stop]
        
        return hitsEx
    

###############################################################################
###############################################################################   

class MONmap():
    def __init__(self):
  
        self.ID       = None
        self.RingID   = None
        self.hardwareType   = None
        self.connectionType = None
        self.channel  = None
        
class DETmap():
    def __init__(self):
  
        self.cassettesMap = []
        
class cassMap():
    def __init__(self):
        
        self.RingID   = None
        self.FenID    = None
        self.hybridID = None
        self.hybridSerial = None
        
class channelMap():
    def __init__(self): 
         
        self.AdapterType = None
        self.WireASIC    = 0
        self.StripASIC   = 1
        
class DETparameters():
    def __init__(self):
        
        self.name     = None
        
        self.type     = None
        
        self.instrument     = None
        
        self.operationMode = 'empty'
        
        self.orientation = 'vertical'
        
        self.numOfWires  = 0
        self.numOfStrips = 0
        
        self.numOfCassettes = 0
        
        self.cassInConfig = []
        
        # in degrees 
        self.bladesInclination  = float(0)
        
        # in mm 
        self.offset1stWires  = float(0)
        
        # in mm
        self.wirePitch  = float(0)
        self.stripPitch = float(0)
      
################################################        

class read_json_config():
    
    
    # NOTE config for other detectors contains stuff for MB but also adds the specific for other detectors 
    
    def __init__(self, configFile_PathAndFileName, printFlag = True):
        
        self.configFile_PathAndFileName = configFile_PathAndFileName
    
        self.openFile(self.configFile_PathAndFileName)
        
        # Initialize other attributes
        self.MONmap        = MONmap()
        self.DETmap        = DETmap()
        self.DETparameters = DETparameters()
        self.cassMap       = cassMap()
        self.channelMap    = channelMap()
        
        self.printFlag = printFlag
        
        self.debug = False

            
        try:
            
                # Process parameters
                self.get_allParameters()
                
                self.checkRing11()
                        
                if self.printFlag is True:
                    self.print_DETname()
                    self.print_check_operationMode()
                        
                self.check_cassetteLabelling()

        
        except Exception as e:
                self.get_DETname()
                self.get_DETtype()
                self.get_instrumName()
                
       
    def openFile(self,configFile_PathAndFileName):  
        
        temp = os.path.split(configFile_PathAndFileName)
        self.configFilePath = temp[0] + os.sep
        self.configFileName = temp[1]
        
        # Open the file
        path = Path(self.configFileName)
        if len(path.suffixes) > 1 and path.suffixes[-1] == path.suffixes[-2]:
            print(f"'\n \033[1;31m---> Double extension detected in '{self.configFileName}'! Please check your file naming convention.\033[1;37m")
            time.sleep(2)
            sys.exit()
        
        
        try:
            self.ff   = open(configFile_PathAndFileName,'r') 
        except:
            print('\n \033[1;31m---> Config File: ' + self.configFileName + ' not found \033[1;37m')
            print('\n ---> in folder: ' + self.configFilePath + ' \n -> exiting.')
            time.sleep(2)
            sys.exit()
            
        # Load JSON data
        try:    
            self.conf = json.load(self.ff)
        except:
            print('\n \033[1;31m---> Error in config File: ' + self.configFileName + ' \033[1;37m',end='')
            print(' ---> common mistake: last line of Cassette2ElectronicsConfig: {"ID" : X, "Ring" : X, "Fen" : X, "Hybrid" : X} must not have comma! \n -> exiting.')
            time.sleep(2)
            sys.exit()
                
                
      # # Open the file
      #           try:
      #               self.ff   = open(configFile_PathAndFileName,'r') 
      #           except:
      #               print('\n \033[1;31m---> Config File: ' + self.configFileName + ' not found \033[1;37m')
      #               print('\n ---> in folder: ' + self.configFilePath + ' \n -> exiting.')
      #               time.sleep(2)               
      #               sys.exit()
                    
      #           # Load JSON data
      #           try:    
      #               self.conf = json.load(self.ff)
      #           except:
      #               print('\n \033[1;31m---> Error in config File: ' + self.configFileName + ' \033[1;37m',end='')
      #               print(' ---> common mistake: last line of Cassette2ElectronicsConfig: {"ID" : X, "Ring" : X, "Fen" : X, "Hybrid" : X} must not have comma! \n -> exiting.')
      #               time.sleep(2)            
      #               sys.exit()
              
        
    def __del__(self):
        try:
            self.ff.close()
        except AttributeError:
            pass

    
    def __deepcopy__(self, memo):
        # Create a shallow copy of the object
        copied_obj = copy.copy(self)
        # Deep copy all attributes except the file object
        copied_obj.MONmap = copy.deepcopy(self.MONmap, memo)
        copied_obj.DETmap = copy.deepcopy(self.DETmap, memo)
        copied_obj.DETparameters = copy.deepcopy(self.DETparameters, memo)
        copied_obj.cassMap = copy.deepcopy(self.cassMap, memo)
        copied_obj.channelMap = copy.deepcopy(self.channelMap, memo)
        # Skip copying the file object (self.ff) and JSON data (self.conf)
        copied_obj.ff = None  # Or reinitialize if needed
        copied_obj.conf = copy.deepcopy(self.conf, memo)  # Copy JSON data
        return copied_obj
        
    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))
            
    def get_allParameters(self):
        self.get_DETname()
        self.get_DETtype()
        self.get_instrumName()
        self.verifyTypeWithInstrument(self.DETparameters.instrument,self.DETparameters.type)
        self.get_DETparameters()
        self.get_DETmap()
        self.get_DETcassettesInConfig()
        self.get_channelMap()
        self.get_MONmap()

            
    def print_DETname(self):
        print('\033[1;36mConfiguration for Detector {}, type {}, instrument {}\033[1;37m'.format(self.DETparameters.name,self.DETparameters.type,self.DETparameters.instrument))
        
    def print_check_operationMode(self):
        
    
        if (self.DETparameters.type == 'MG') or (self.DETparameters.type == 'MB'): 
            if self.DETparameters.operationMode == "normal" or self.DETparameters.operationMode == "clustered":
                print('\033[1;36mOperation Mode: {}\033[1;37m'.format(self.DETparameters.operationMode))
            else:
                print('\n\t\033[1;31mERROR: Operation mode (found {}) can only be either normal or clustered for VMM-based detectors -> check config file! ---> Exiting ... \n\033[1;37m'.format(self.DETparameters.operationMode),end='') 
                time.sleep(2)
                sys.exit()
                
        else:    
             
             if self.DETparameters.operationMode == "normal":
                 print('\033[1;36mOperation Mode: {}\033[1;37m'.format(self.DETparameters.operationMode))
             else:
                 print('\n\t\033[1;31mERROR: Operation mode (found {}) can only be either normal for {} detectors -> check config file! ---> Exiting ... \n\033[1;37m'.format(self.DETparameters.operationMode,self.DETparameters.type),end='') 
                 time.sleep(2)
                 sys.exit()

        
    def get_DETname(self):
        self.DETparameters.name = self.conf.get('DetectorName')
        return self.DETparameters.name
    
    def get_DETtype(self):
        self.DETparameters.type = self.conf.get('DetectorType')
        
        if self.DETparameters.type != 'MB' and self.DETparameters.type != 'MG' and self.DETparameters.type != 'He3':
            print('\n\t\033[1;31mERROR: Detector type (found {}) can only be either MB, MG or He3 -> check config file! ---> Exiting ... \n\033[1;37m'.format(self.DETparameters.type),end='') 
            time.sleep(2)
            sys.exit()
        
        return self.DETparameters.type
    
    def get_instrumName(self):
        self.DETparameters.instrument = self.conf.get('InstrumentName')
        
        instruments = ["TBL", "AMOR", "ESTIA", "FREIA", "TREX", "MIRACLES", "CSPEC", "BIFROST", "VESPA"]
        
        if self.DETparameters.instrument not in instruments: 
            print("\n\t\033[1;31mERROR: Instrument name {} is invalid. Must be one of: {} \n\033[1;37m".format(self.DETparameters.instrument, ", ".join(instruments)))
            time.sleep(2)
            sys.exit()
 
        return self.DETparameters.instrument
    
    def verifyTypeWithInstrument(self,instr,detType):
            
        valid_mapping = {
            "TBL":      ["He3", "MB"],
            "CSPEC":    ["He3"],
            "MIRACLES": ["He3"],
            "VESPA":    ["He3"],
            "BIFROST":  ["He3"],
            "ESTIA":    ["MB"],
            "FREIA":    ["MB"],
            "AMOR":     ["MB"],
            "TREX":     ["MG"]
        }

        # instr    = self.DETparameters.instrument
        # det_type = self.DETparameters.type
    
        # 2. Perform the check
        allowed_types = valid_mapping.get(instr, [])
    
        if detType not in allowed_types:
            # Construct a clear warning message
            expected = " or ".join(allowed_types)
            print(f"\n\t\033[1;33mWARNING: Potential configuration mismatch!")
            print(f"\tInstrument '{instr}' usually uses type: {expected}.")
            print(f"\tCurrent config has: '{detType}'.")
            print(f"\tAnalysis will proceed, but please verify your JSON settings.\033[1;37m\n")
            
            # Optional: slight pause so the user sees the warning
            time.sleep(1)
        
    
    def get_DETparameters(self):
        self.DETparameters.numOfWires  = self.conf.get('wires')
        self.DETparameters.numOfStrips = self.conf.get('strips')
        self.DETparameters.wirePitch  = float(self.conf.get('wirePitch_mm'))
        self.DETparameters.stripPitch = float(self.conf.get('stripPitch_mm'))
        self.DETparameters.bladesInclination  = float(self.conf.get('bladesInclination_deg'))
        self.DETparameters.offset1stWires  = float(self.conf.get('offset1stWires_mm'))
        self.DETparameters.numOfCassettes  = self.conf.get('cassettes')
        self.DETparameters.orientation     = self.conf.get('orientation')
        self.DETparameters.operationMode   = self.conf.get('operationMode')
        
    def get_DETmap(self):  
        self.DETmap.cassettesMap = self.conf.get('Cassette2ElectronicsConfig')

    def get_DETcassettesInConfig(self):
                
        for cc in self.DETmap.cassettesMap:
            ID = cc.get("ID")
            self.DETparameters.cassInConfig.append(ID)
                
        self.dprint('cassettes in config file: {}'.format(self.DETparameters.cassInConfig))   
        
    def get_cassID2RingFenHybrid(self,cassetteID):

        if not cassetteID in self.DETparameters.cassInConfig:
                self.cassMap.RingID   = None
                self.cassMap.FenID    = None
                self.cassMap.hybridID = None
                self.cassMap.hybridSerial = None
                print('\t \033[1;33mWARNING: Cassette ID ',str(cassetteID),' not found! Skipped! This CONFIG file only contains cassettes:', end=' ')
                for cass in self.DETparameters.cassInConfig:
                    print(cass,end=' ')
                print('\033[1;37m')
                
        else:
              for cc in self.DETmap.cassettesMap:
                  if cc.get("ID") == cassetteID:
                      self.cassMap.RingID       = cc.get("Ring")
                      self.cassMap.FenID        = cc.get("Fen")
                      self.cassMap.hybridID     = cc.get("Hybrid")
                      self.cassMap.hybridSerial = cc.get("HybridSerial")
                      
                   
    def checkRing11(self):
        
        for cc in self.DETmap.cassettesMap:
            if cc.get("Ring") == 11:
                print('\t \033[1;31mERROR: Ring 11 found in config for detector and not associated to MONITOR! -> exiting! \033[1;31m', end=' ')
                time.sleep(2)
                sys.exit()
                     
    def check_cassetteLabelling(self):

        numOfCass               = np.shape(self.DETparameters.cassInConfig)[0]
        numOfCassFromConfigFile = self.DETparameters.numOfCassettes
        
        if numOfCass != numOfCassFromConfigFile:
            print('\033[1;31m CONFIG FILE JSON ERROR: Num of cassettes ({}) not matching num of cassettes in list ({}) in Config file\033[1;31m'.format(numOfCass,numOfCassFromConfigFile))
            print(' \n -> exiting.')
            time.sleep(2)
            sys.exit()
        
        # print(self.DETparameters.cassInConfig)
      
        # sortedCass = np.sort(self.DETparameters.cassInConfig)
        
        # sortedCass = self.DETparameters.cassInConfig
        
        # print(self.DETparameters.cassInConfig)
        
        # print(sortedCass)
        
        # if sortedCass[0] != 0:
        #     print('\033[1;31m CONFIG FILE JSON ERROR: Cassettes MUST be labelled from 0 -> please correct in JSON file\033[1;31m')
        #     print(' \n -> exiting.')
        #     time.sleep(2) 
        #     sys.exit()
            
                     
    def get_channelMap(self):  
        
        try:
            temp = self.conf.get('ChannelMapping')[0]
        except:
            temp = None
        
        # temp = temp[0]
        
        if temp is not None:
            # self.channelMap.AdapterType = temp.get("AdapterType")
            self.channelMap.WireASIC    = temp.get("WireASIC")
            self.channelMap.StripASIC   = temp.get("StripASIC")
 
    def get_MONmap(self):
             
        mapm = self.conf.get('Monitor')
        
        if mapm is None:
            print('\t \033[1;33mWARNING: No monitor config found in json file \033[1;37m')
        
        else:
            
              # for cc in self.mapm:
                 
                  # here supports only one monitor !!!
                 
                  cc = mapm[0]
            
                  self.MONmap.ID             = cc.get("ID")               
                  self.MONmap.hardwareType   = cc.get("hardwareType")
                  self.MONmap.connectionType = cc.get("connectionType")
                  self.MONmap.RingID         = cc.get("Ring")
                  self.MONmap.channel        = cc.get("Channel")
                                    
                  if self.printFlag is True:
                     self.checkBMsettings(self.MONmap.hardwareType, self.MONmap.connectionType,self.MONmap.RingID) 
                
              
###############################################################################


    def checkBMsettings(self,hardwareType,connectionType,RingID):
             
             if hardwareType == "GENERIC" or hardwareType == "IBM" : 
                 pass
             else:
                 print('\n\t\033[1;31mERROR: MON hardware (found {}) can only be either GENERIC or IBM  -> check config file! ---> Exiting ... \n\033[1;37m'.format(hardwareType),end='') 
                 time.sleep(2)
                 sys.exit()
                 
                 
             if connectionType == "LEMO" or connectionType == "RING" : 
                 pass
             else:
                 print('\n\t\033[1;31mERROR: MON connection type (found {}) can only be either LEMO or RING  -> check config file! ---> Exiting ... \n\033[1;37m'.format(connectionType),end='') 
                 time.sleep(2)
                 sys.exit()    

            # BM LEMO type can only be in rings that are not physical rings but created in thew RMM config RINGS >= 11, usually >= 12
             if connectionType == "LEMO" :
                 if RingID < 11:
                     print('\n\t\033[1;33mWARNING: MON mode {} selected with RING < 11 (ring {}) (can be any ring 11 - inf, but not < 11)-> check config file! ---> Exiting ... \n\033[1;37m'.format(connectionType,RingID),end='') 
                     time.sleep(1)
                     sys.exit()
                 
    
             # if the BM is on one ring can be in any ring but usually 11, if not 11 give a warning. 
             if connectionType == "RING" : 
                 if RingID != 11:
                     print('\n\t\033[1;33mWARNING: MON mode {} selected with RING != 11 (ring {} found in config file)\n\033[1;37m'.format(connectionType,RingID),end='') 
                     time.sleep(1)
                 # else:
                 #     print('\n\t\033[1;33mWARNING: MON mode {} selected with RING != 11 (must be ring 11) -> check config file! ---> Exiting ... \n\033[1;37m'.format(connectionType),end='') 
                 #     time.sleep(1)
                     
                     # sys.exit()

             
           
        
###############################################################################
###############################################################################     

class extractPartialConfig():

    @staticmethod
    
    def extract(config, start, stop):
        
        print('\033[1;36m \t Extracting Partial Configuration for Cassettes from {} to {} \033[1;37m'.format(start,stop-1))
        # Create a deep copy of the input config
        configOUT = copy.deepcopy(config)
        # Modify the copied object’s cassInConfig
        configOUT.DETparameters.cassInConfig = config.DETparameters.cassInConfig[start:stop]
    
        if not(configOUT.DETparameters.cassInConfig):
            configOUT.DETparameters.cassInConfig = [config.DETparameters.cassInConfig[-1]]
            print('\t \033[1;33mWARNING: range for config out of range, setting to last item in list!')
        
        if not isinstance(configOUT.DETparameters.cassInConfig,list):
            configOUT.DETparameters.cassInConfig = [configOUT.DETparameters.cassInConfig]
    
        return configOUT
        

###############################################################################
###############################################################################

                
class mapDetector():
    def __init__(self, readouts, config):
        
        print('\033[1;36m\nMapping Detector channels ... \033[1;37m')
    
        self.debug    = False
        
        self.readouts = readouts
        self.config   = config

        self.hits = hits()
        self.hits.importReadouts(copy.deepcopy(self.readouts))
        
     
    def initCatData(self):    # debug

        if self.debug:
            self.catData = np.zeros((len(self.readouts.Ring),10), dtype = 'int64')
            self.catData[:,0] = self.hits.Cassette
            self.catData[:,1] = self.readouts.Ring
            self.catData[:,2] = self.readouts.Fen
            self.catData[:,3] = self.readouts.hybrid
            self.catData[:,4] = self.readouts.ASIC
            self.catData[:,5] = self.readouts.Channel
            self.catData[:,6] = self.hits.WiresStrips
            self.catData[:,7] = self.hits.WorS
            self.catData[:,8] = self.readouts.Channel1
            self.catData[:,9] = self.hits.WiresStrips1
            # self.catData[:,8] = self.hits.WiresStripsGlob
            
    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))     
        
    def mapp1cass(self, cassette1ID):
        
        if self.debug:
            print(cassette1ID)
        
        self.config.get_cassID2RingFenHybrid(cassette1ID)
        
        if self.debug:
            print(self.config.cassMap.RingID,self.config.cassMap.FenID,self.config.cassMap.hybridID)
        
        RingLoc = self.readouts.Ring   == self.config.cassMap.RingID
        FenLoc  = self.readouts.Fen    == self.config.cassMap.FenID
        HyLoc   = self.readouts.hybrid == self.config.cassMap.hybridID
        
        # selection = RingLoc & FenLoc & HyLoc
        
        selection = np.logical_and(np.logical_and(RingLoc,FenLoc) , HyLoc)
        
        if np.any(selection):
            self.hits.Cassette[selection] = cassette1ID
            flag = True
        else:
            flag = False
            # print('\t \033[1;33m No data found for Cassette ID ',str(cassette1ID),'\033[1;37m')
            
        return flag    
            
    
    def mappAllCass(self):
        
        # mapped according to the json file
        cassettesIDs = self.config.DETparameters.cassInConfig
        
        cassNotFound = []
        
        for cass in cassettesIDs:
            flag = self.mapp1cass(cass)
            
            if flag is False:
                cassNotFound.append(cass)
        
        if len(cassNotFound) > 0:
            print('\t \033[1;33mWARNING: Cassette IDs: ', end=' ')
            for cass in cassNotFound:
                  print(cass,end=' ')
            print(' not found in DATA file. Mapping skipped for those. \033[1;37m')        
                

    def mapChannels(self):
        
        
        # if  self.config.channelMap.AdapterType is None:
        #     print('\t \033[1;33mWARNING: No adapter type in json config file, used reverse as default. Wires on ASIC 1 and Strips on ASIC 0', end=' ')
        #     self.config.channelMap.AdapterType = 'reverse'
        # else:    
        #     if self.config.channelMap.AdapterType != 'straight' and self.config.channelMap.AdapterType != 'reverse':
        #         print('\t \033[1;33mWARNING: Adapter type can only be straight or reverse, check json config file, used reverse as default.', end=' ')
        #         self.config.channelMap.AdapterType = 'reverse'
       
        if self.config.channelMap.WireASIC == self.config.channelMap.StripASIC:
            print('\t \033[1;31mWARNING: Wires and strips on same ASIC in config file ---> exiting!', end=' ')
            time.sleep(2)
            sys.exit()
            
        # if self.config.channelMap.WireASIC == 1 and self.config.channelMap.StripASIC == 0 and self.config.channelMap.AdapterType == 'straight' :
        #     print('\t \033[1;33mWARNING: Usually with straight adapter, wires are on ASIC 0 and strips on ASIC 1', end=' ')
        #     time.sleep(2) 
        #     sys.exit()
        # if self.config.channelMap.WireASIC == 0 and self.config.channelMap.StripASIC == 1 and self.config.channelMap.AdapterType == 'reverse' :
        #    print('\t \033[1;33mWARNING: Usually with reverse adapter, wires are on ASIC 1 and strips on ASIC 0', end=' ')
        #    time.sleep(2)
        #    sys.exit()
        
        #  here we define the adapter type if VMM1 is on wires the oprder o channels is reversed for strips 
        if self.config.channelMap.WireASIC == 0 and self.config.channelMap.StripASIC == 1 :
            AdapterType = 'straight'
        if self.config.channelMap.WireASIC == 1 and self.config.channelMap.StripASIC == 0 :
            AdapterType = 'reverse'
        
        if self.config.DETparameters.operationMode == 'normal':
            
                #############
                #  wires
                sel1 = self.readouts.ASIC == self.config.channelMap.WireASIC 
                sel2 = self.readouts.Channel >= 16
                sel3 = self.readouts.Channel <= 47
                
                selectionWires  = sel1 & sel2 & sel3
                
                if AdapterType == 'straight':
                    self.hits.WiresStrips[selectionWires] = 31 - (self.readouts.Channel[selectionWires] - 16)
                elif AdapterType == 'reverse':   
                    self.hits.WiresStrips[selectionWires] = self.readouts.Channel[selectionWires] - 16
        
                # self.hits.WiresStrips[~selectionWires] = np.ma.masked # same as np.nan for int64 instead of floats
                
                # after mapping wires are 0 and strips 1 
                self.hits.WorS[selectionWires] = 0 
                
                #############
                # strips
                sel1s = self.readouts.ASIC == self.config.channelMap.StripASIC 
                sel2s = self.readouts.Channel >= 0
                sel3s = self.readouts.Channel <= 63
                
                selectionStrips  = sel1s & sel2s & sel3s
                
                if AdapterType == 'straight':
                    self.hits.WiresStrips[selectionStrips] = self.readouts.Channel[selectionStrips]
                elif AdapterType == 'reverse':  
                    self.hits.WiresStrips[selectionStrips] = 63 - self.readouts.Channel[selectionStrips]
                    
                # after mapping wires are 0 and strips 1 
                self.hits.WorS[selectionStrips] = 1 
        
        #############
        
        # if some ch of vmm are not used then nan, it is not a wire or strip 
        # self.hits.WorS[~selectionWires & ~selectionStrips] = np.ma.masked # same as np.nan for int64 instead of floats
        
        # self.hits.WorS[~selectionWires & ~selectionStrips] = -1
        
        elif self.config.DETparameters.operationMode == 'clustered':
                
            #############
            #  wires
            if self.config.channelMap.WireASIC == 0:
                sel2 = self.readouts.Channel >= 16
                sel3 = self.readouts.Channel <= 47
            elif self.config.channelMap.WireASIC == 1:
                sel2 = self.readouts.Channel1 >= 16
                sel3 = self.readouts.Channel1 <= 47
            
            selectionWires  = sel2 & sel3
            
            # always for any adapter the wirestips is for wires !!! 
            if self.config.channelMap.WireASIC == 0:
                self.hits.WiresStrips[selectionWires] = 31 - (self.readouts.Channel[selectionWires] - 16)
                self.hits.ADC[selectionWires]         = self.readouts.ADC[selectionWires]
                self.hits.mult0[selectionWires]       = self.readouts.mult0[selectionWires]
                
            elif self.config.channelMap.WireASIC == 1: 
                self.hits.WiresStrips[selectionWires] = self.readouts.Channel1[selectionWires] - 16
                self.hits.ADC[selectionWires]         = self.readouts.ADC1[selectionWires]
                self.hits.mult0[selectionWires]       = self.readouts.mult1[selectionWires]
  
                
            #############
            # strips
            if self.config.channelMap.StripASIC == 0:  
                sel2s = self.readouts.Channel >= 0
                sel3s = self.readouts.Channel <= 63
            elif self.config.channelMap.StripASIC == 1:
                sel2s = self.readouts.Channel1 >= 0
                sel3s = self.readouts.Channel1 <= 63
            
            selectionStrips  = sel2s & sel3s
            
            # always for any adapter the wirestips1 is for strips !!! 
            if self.config.channelMap.StripASIC == 1:
                self.hits.WiresStrips1[selectionStrips] = self.readouts.Channel1[selectionStrips]
                self.hits.ADC1[selectionStrips]         = self.readouts.ADC1[selectionStrips]
                self.hits.mult1[selectionStrips]        = self.readouts.mult1[selectionStrips]
                
            elif self.config.channelMap.StripASIC == 0:  
                self.hits.WiresStrips1[selectionStrips] = 63 - self.readouts.Channel[selectionStrips]
                self.hits.ADC1[selectionStrips]         = self.readouts.ADC[selectionStrips]
                self.hits.mult1[selectionStrips]        = self.readouts.mult0[selectionStrips]
                
                
    def mapChannelsGlob(self):
        
        self.mapChannels()
        
        # # global coord
        # self.hits.WiresStripsGlob  = np.copy(self.hits.WiresStrips)
        # #  if one cassette is absent in eiither the config file or the data there will be a blank space for the wanted cassette
        
        # # for k, cass in enumerate(cassettesIDs):
        #     #  does not matter the cassette ID the cassettes are arrangted one after the other according to the order in cassettesIDs,   
        
        #  # in this case the order is the arrangement in the json file 
        # for k, cass in enumerate(self.config.presentCass): 
        #     selection = np.logical_and( self.hits.Cassette == cass , self.hits.WorS == 0 ) #  wires is WorS = 0
        #     self.hits.WiresStripsGlob[selection] = self.hits.WiresStrips[selection] + k*self.config.numOfWires
        
                  # in this case the order is the arrangement in the json file 
        for k, cass in enumerate(self.config.DETparameters.cassInConfig): 
            
            index = k
            
            if self.config.DETparameters.operationMode == 'normal':
                
                selection = np.logical_and( self.hits.Cassette == cass , self.hits.WorS == 0 ) #  wires is WorS = 0
                self.hits.WiresStrips[selection] = self.hits.WiresStrips[selection] + index*self.config.DETparameters.numOfWires
                
            elif self.config.DETparameters.operationMode == 'clustered':
                
                selection = self.hits.Cassette == cass
                
                # always for any adapter the wirestips is for wires !!! 
                
                # if self.config.channelMap.WireASIC == 0:
                #    self.hits.WiresStrips[selection] = self.hits.WiresStrips[selection] + index*self.config.DETparameters.numOfWires
                # elif self.config.channelMap.WireASIC == 1: 
                    
                self.hits.WiresStrips[selection] = self.hits.WiresStrips[selection] + index*self.config.DETparameters.numOfWires
            
            #  IMPORTANT NOTE 
            #  if just add +32 every cassette in json config does not matter the ID
            # index = k
            #  if the cassette ID drives the position in the space, 1 is the bottom cassette or the most left 
            # index = cass-1
            #  if the cassette ID drives the position in the space, 0 is the bottom cassette or the most left 
            # index = cass
                
            
        
    
    def mappAllCassAndChannels(self):
        
        self.mappAllCass()
        self.mapChannels()  
        
        self.hits.removeUnmappedData()
            
    def mappAllCassAndChannelsGlob(self):
        
        self.mappAllCass()
        self.mapChannelsGlob()
        
        self.hits.removeUnmappedData()

###############################################################################
###############################################################################

class mapMonitor():
    def __init__(self, readouts, config):
        
        self.readouts = readouts 
        self.hits     = hits
        self.config   = config
        self.config.get_MONmap()
        self.flagMONfound = False

        # 1. Define masks
        # Target specific selection from config
        RingLoc   = self.readouts.Ring    == self.config.MONmap.RingID
        ChLoc     = self.readouts.Channel == self.config.MONmap.channel
        selection = RingLoc & ChLoc

        # Identify all potential Monitor data (Ring >= 11)
        mon_mask = self.readouts.Ring >= 11
        # Get unique [Ring, Channel] pairs found in the data for Rings >= 11
        found_mon_pairs = np.unique(np.c_[self.readouts.Ring[mon_mask],self.readouts.Channel[mon_mask]], axis=0)
        
        num_found_pairs = len(found_mon_pairs)

        # --- Logic Branches ---

        # CASE 1: The specific selection exists in the data
        if np.any(selection):
            if num_found_pairs > 1:
                print(f"\t \033[1;33mWARNING: Found {num_found_pairs} monitor sources in data. MBUTY supports only one Monitor."
                      f"Mapping according to config file, but data contains (Ring, Channel): {found_mon_pairs}\033[1;37m")
            
            self._map_data(selection)
            self.flagMONfound = True

        # CASE 2: Selection is empty, but exactly ONE other monitor-valid pair exists
        elif num_found_pairs == 1:
            wrong_ring, wrong_ch = found_mon_pairs[0]
            print(f"\t \033[1;33mWARNING: mismatch -> One monitor candidate found, but it is NOT the selected one in config file."
                  f" Data contains Ring {wrong_ring} and Channel {wrong_ch}.\033[1;37m")
            self.flagMONfound = False

        # CASE 3: No monitor data (Ring >= 11) found at all
        else:
            print('\t \033[1;33mNo MONITOR data found in data file\033[1;37m')
            self.flagMONfound = False

    def _map_data(self, selection):
        print('\033[1;36mMapping Monitor ... \033[1;37m')
        self.hits.timeStamp = self.readouts.timeStamp[selection]
        self.hits.ADC       = self.readouts.ADC[selection]
        self.hits.PrevPT    = self.readouts.PrevPT[selection]
        self.hits.PulseT    = self.readouts.PulseT[selection]
        self.hits.Durations = self.readouts.Durations
        self.hits.Duration  = np.ones((1), dtype='int64') * (np.sum(self.readouts.Durations))
        
        leng = len(self.hits.timeStamp)
        # Populate metadata fields with -1 or config ID
        self.hits.Cassette     = self.config.MONmap.ID * np.ones((leng), dtype='int64') 
        self.hits.ADC1         = -1 * np.ones((leng), dtype='int64') 
        self.hits.WiresStrips  = -1 * np.ones((leng), dtype='int64') 
        self.hits.WiresStrips1 = -1 * np.ones((leng), dtype='int64') 
        self.hits.WorS         = -1 * np.ones((leng), dtype='int64') 
        self.hits.mult0        = -1 * np.ones((leng), dtype='int64') 
        self.hits.mult1        = -1 * np.ones((leng), dtype='int64')
        

      


###############################################################################
###############################################################################

if __name__ == '__main__':

   filePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"AMOR.json"
   # filePathD = './'+"VMM3a_Freia.pcapng"

   config1 = read_json_config(filePath)
   
   # print(config1.MONmap.type)
   
   # self.parameters.loadConfigAndUpdate(config)
   
   # print(config1.DETparameters.cassInConfig)
   
   # config2 = extractPartialConfig.extract(config1,11,55)

   # print(config2.DETparameters.cassInConfig)
   
   filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file = 'miracles_trig2.pcapng'
   file = 'ESSmask2023_1000pkts.pcapng'
   file = 'testALLON.pcapng'
   
   filePathAndFileName1 = filePath+file

   NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz
   
   typeOfLoading = 'allocate'
   
   # typeOfLoading = 'quick'
   
   # pcap = pcapr.pcapng_reader(filePathAndFileName1,NSperClockTick, MONtype='LEMO', MONring=11, timeResolutionType='fine', sortByTimeStampsONOFF=True, operationMode='normal',pcapLoadingMethod=typeOfLoading)

   # readouts = pcap.readouts

   # readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   
   # # change = readouts.Ring == 0
   # # readouts.Ring[change]    = 12
   # # readouts.Channel[change] = 5
   
   
   # md  = mapDetector(readouts, config1)
   # md.mappAllCassAndChannelsGlob()
   # hits = md.hits
   # hitsArray  = hits.concatenateHitsInArrayForDebug()
   
   # # readouts.
   
   # MON = mapMonitor(readouts, config1)
   
   # # print(MON.flagMONfound)
   
   # if MON.flagMONfound:
   #     hitsMON = MON.hits
   #     hitsArrayMON  = hitsMON.concatenateHitsInArrayForDebug()
   
   
   
   # MON = mapMonitor(readouts, config1)
   # hitsMON = MON.hits
   # hitsMONArray  = hitsMON.concatenateHitsInArrayForDebug()
   
   # print(config1.DETparameters.cassInConfig)
   
   # filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file = 'sampleData_NormalMode.pcapng'
   # # file = 'sampleData_ClusteredMode.pcapng'
   
   # filePathAndFileName = filePath+file
   
   # NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz
   
   # pcapng = pcapr.pcapng_reader(filePathAndFileName, NSperClockTick, config.MONmap.TTLtype, config.MONmap.RingID,  timeResolutionType='fine', sortByTimeStampsONOFF = False, operationMode=config.DETparameters.operationMode)

    
   # readouts = pcapng.readouts
   # readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   
   # md  = mapDetector(readouts, config)
   # md.mappAllCassAndChannelsGlob()
   # hits = md.hits
   # hitsArray  = hits.concatenateHitsInArrayForDebug()
   
   # parameters.loadConfigParameters(config)
   
   # config.check_cassetteLabelling()
   
   # name = config.get_DETname()
   # config.get_DETcassettesInConfig()
   
   # config.get_cassID2RingFenHybrid(5)
   # print(config.cassMap.RingID, config.cassMap.FenID, config.cassMap.hybridID, config.cassMap.hybridSerial)
   # # config.get_cassID2RingFenHybrid(55)
   # # print(config.RingID, config.FenID, config.hybridID)
   # # config.get_cassID2RingFenHybrid(1)
   # # print(config.RingID, config.FenID, config.hybridID)
   
   # # config.get_cassID2RingFenHybrid([1,41])
   
   # config.get_bladesInclination()
   # config.get_pitches()
   # config.get_offset1stWires()
   
   # pr = pcapr.pcap_reader(filePathD)
   #   # pr.debug = True
   #  pr.read()
   #  vmm1 = pr.readouts
   
   # vmm2 = sdat.sampleReadouts_2()
   # vmm2.fill()
   # readouts = vmm2.readouts

   
   
   # re  = mapDetector(readouts, config)
   # re.debug = True
   # re.initCatData()
   # data1 = re.catData
   

   # re.mapp1cass(1)
   # # # bb = re.mapp1cass(45)
   
   # aa  = re.mappAllCass([1,2,45,3,56])
   
   # # # cassettes = np.arange(0,34,1)
    
   # re.mappAllCassAndChannels()
   
   # re.mappAllCassAndChannelsGlob()
   
   # re.initCatData()
   # data = re.catData
   
   # re.mappAllCassAndChannelsGlob()
   # hits = re.hits
   
   # hits = re.hits
   # hitsArray = hits.concatenateHitsInArrayForDebug()
    
   # # # bb = re.mappAllCassAndChannels([345,6,25])
   
   # # aa = config.get_monitor()
   
   # bb = mapMonitor(vmm2, config)
   
   # ori = getALl