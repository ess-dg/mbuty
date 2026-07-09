#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 13:44:35 2026

@author: francescopiscitelli
"""

import numpy as np
import json
import os
import sys
import copy
import time


try:
####### if you run default
    from lib import libMapping 
    

except ImportError:
    ####### if you run in lib 
    import libMapping 
    import libReadPcapng as pcapr


# NOTE: THIS SUPPORTS ONLY 1 MONITOR

# hits and BM are loaded from the the default lib 
###############################################################################
###############################################################################   
""" Acts as a pointer/wrapper for the central library """
mapMonitor           = libMapping.mapMonitor
extractPartialConfig = libMapping.extractPartialConfig
# checkBMsettings      = libMapping.checkBMsettings

###############################################################################
###############################################################################   

        
class cassMap():
    def __init__(self):
        
        self.RingID   = None
        self.FenID    = None
        self.TubeID   = None

 
class DETparameters():
    def __init__(self):
        
        self.name     = None
        
        self.type     = None
        
        self.instrument     = None
        
        self.operationMode = 'empty'
        
        self.orientation   = 'vertical'
        
        self.numOfCassettes = 0
        
        self.positionBins  = 1
        
        self.cassInConfig = []

        self.tubesPerRow = 0
        
        self.tubeLength  = 0  # mm
      
        self.tubeSpacing  = 0  # mm
        
################################################        

class read_json_config():
    
    def __init__(self, configFile_PathAndFileName, printFlag = True):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.__init__(self, configFile_PathAndFileName, printFlag) 

    def openFile(self,configFile_PathAndFileName):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.openFile(self,configFile_PathAndFileName)    

    def __del__(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.__del__(self)  
        
    def __deepcopy__(self, memo):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.__deepcopy__(self, memo)  
        
    def dprint(self, msg): 
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.dprint(self, msg)
    
    def print_DETname(self): 
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.print_DETname(self)
 
    def print_check_operationMode(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.print_check_operationMode(self)

    def get_DETname(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_DETname(self)
    
    def get_DETtype(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_DETtype(self)
    
    def get_instrumName(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_instrumName(self)
    
    def get_DETmap(self):  
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_DETmap(self)
    
    def get_DETcassettesInConfig(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_DETcassettesInConfig(self)
    
    def checkRing11(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.checkRing11(self)
    
    def get_MONmap(self):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.get_MONmap(self)
    
    def checkBMsettings(self,hardwareType,connectionType,RingID):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.checkBMsettings(self,hardwareType,connectionType,RingID)
    
    def verifyTypeWithInstrument(self,instr,detType):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.read_json_config.verifyTypeWithInstrument(self,instr,detType)


        
    def checkOpModeHe3(self):
        if self.DETparameters.type == 'He3' and self.DETparameters.operationMode != "normal":
            print('\n\t\033[1;31mERROR: Operation mode (found {}) not supported yet for He3 type detectors, only normal mode -> check config file! \n\033[1;37m'.format(self.DETparameters.operationMode),end='') 
            time.sleep(2)
            sys.exit()
 
    
    def check_cassetteLabelling(self):

        numOfCass               = np.shape(self.DETparameters.cassInConfig)[0]
        numOfCassFromConfigFile = self.DETparameters.numOfCassettes
        
        if numOfCass != numOfCassFromConfigFile:
            print('\033[1;31m CONFIG FILE JSON ERROR: Num of tubes ({}) not matching num of tubes in list ({}) in Config file\033[1;31m'.format(numOfCass,numOfCassFromConfigFile))
            print(' \n -> exiting.')
            time.sleep(2)
            sys.exit()
            
    def get_allParameters(self):
        self.get_DETname()
        self.get_DETtype()
        self.get_instrumName()
        self.verifyTypeWithInstrument(self.DETparameters.instrument,self.DETparameters.type)
        self.get_DETparameters()
        self.get_DETmap()
        self.get_DETcassettesInConfig()
        self.get_MONmap()
        self.checkOpModeHe3()
        
    def get_DETparameters(self):
        self.DETparameters.numOfCassettes = self.conf.get('cassettes')
        self.DETparameters.orientation    = self.conf.get('orientation')
        self.DETparameters.operationMode  = self.conf.get('operationMode')
        self.DETparameters.positionBins   = self.conf.get('positionBins')
        self.DETparameters.tubesPerRow    = self.conf.get('tubesPerRow')
        self.DETparameters.tubeLength     = self.conf.get('tubeLength')
        self.DETparameters.tubeSpacing    = self.conf.get('tubeSpacing')
        
        # maybe here is needed to create soft thresholds arrayts and maybe numOfWires = 1 and also numOfStrips
        # self.DETparameters.numOfWires     = self.DETparameters.numOfCassettes
        # self.DETparameters.numOfStrips    = self.DETparameters.numOfCassettes
        

    def get_cassID2RingFenHybrid(self,cassetteID):

        if not cassetteID in self.DETparameters.cassInConfig:
                self.cassMap.RingID   = None
                self.cassMap.FenID    = None
                self.cassMap.TubeID   = None

                print('\t \033[1;33mWARNING: Tube ID ',str(cassetteID),' not found! Skipped! This CONFIG file only contains tubes:', end=' ')
                for cass in self.DETparameters.cassInConfig:
                    print(cass,end=' ')
                print('\033[1;37m')
                
        else:
             for cc in self.DETmap.cassettesMap:
                 if cc.get("ID") == cassetteID:
                     self.cassMap.RingID       = cc.get("Ring")
                     self.cassMap.FenID        = cc.get("Fen")
                     self.cassMap.TubeID       = cc.get("Tube")

                     


###############################################################################
###############################################################################

                
class mapDetector():
    def __init__(self, readouts, config):
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.mapDetector.__init__(self, readouts, config)
           
    def initCatData(self):    # debug
        """ Acts as a pointer/wrapper for the central library """
        return libMapping.mapDetector.initCatData(self)
    
            
    def dprint(self, msg):
       """ Acts as a pointer/wrapper for the central library """
       return libMapping.mapDetector.dprint(self,msg)
        
    def mapp1cass(self, cassette1ID):
        
        if self.debug:
            print(cassette1ID)
        
        self.config.get_cassID2RingFenHybrid(cassette1ID)
        
        if self.debug:
            print(self.config.cassMap.RingID,self.config.cassMap.FenID,self.config.cassMap.TubeID)
        
        RingLoc = self.readouts.Ring    == self.config.cassMap.RingID
        FenLoc  = self.readouts.Fen     == self.config.cassMap.FenID
        TubeLoc = self.readouts.Channel == self.config.cassMap.TubeID
          
        selectionRF = np.logical_and(RingLoc,FenLoc)

        selection   = np.logical_and(selectionRF , TubeLoc)
         
        if np.any(selection):
            self.hits.Cassette[selection] = cassette1ID
            flag = True
        else:
            flag = False
            # print('\t \033[1;33m No data found for Cassette ID ',str(cassette1ID),'\033[1;37m')

        #########################################
        # MAPPING CHANNELS HERE : 
        
        # after mapping wires are 0 and strips 1 
        self.hits.WorS[selection]         = 0 
        
        self.hits.WiresStrips[selection]  = self.readouts.Channel[selection]
        
        # self.hits.WiresStrips[selection]   =  cassette1ID
                
        #  NOTE there is no strip for MIRACLES only wires 
        
        # acceptW  =  tempW < self.config.DETparameters.numOfWires

        # if np.any(~acceptW):
        #      print('Warning: found Wires above {} in MG column {}'.format(self.config.DETparameters.numOfWires-1,cassette1ID))
       
             
        # tempW[~acceptW] = -1
        # temp1[~acceptW] = -1
        
 


        ########################################## 
        
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
            print('\t \033[1;33mWARNING: Tube IDs: ', end=' ')
            for cass in cassNotFound:
                  print(cass,end=' ')
            print(' not found in DATA file. Mapping skipped for those. \033[1;37m')        
                

            
    # def mapChannelsGlob(self):

    #     # in this case the order is the arrangement in the json file 
    #     for k, cass in enumerate(self.config.DETparameters.cassInConfig): 
            
    #         index = k

    #         selection = np.logical_and( self.hits.Cassette == cass , self.hits.WorS == 0 ) #  wires is WorS = 0
    #         self.hits.WiresStrips[selection] = self.hits.WiresStrips[selection] + index*self.config.DETparameters.numOfTubes
            
            
    def mappAllCassAndChannelsGlob(self):
        
        self.mappAllCass()
        # self.mapChannelsGlob()
        
        self.hits.removeUnmappedData()


    
###############################################################################
###############################################################################

if __name__ == '__main__':

   confFile  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"CSPEC.json"
   # filePathD = './'+"VMM3a_Freia.pcapng"

   config = read_json_config(confFile)
   
   print(config.DETparameters.numOfWires)
   
   filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file = 'MG_2col_2clusters.pcapng'
   file = 'miracles_trig2.pcapng'
     
   # file = 'MG_2col_1cluster.pcapng'
   
   # file = 'miracles_source_mask.pcapng'

   filePathAndFileName = filePath+file
   
   NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz
   
   pcapng = pcapr.pcapng_reader(filePathAndFileName)

   readouts = pcapng.readouts
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   

   md  = mapDetector(readouts, config)
   md.mappAllCassAndChannelsGlob()
   hits = md.hits
   hitsArray  = hits.concatenateHitsInArrayForDebug()
   
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