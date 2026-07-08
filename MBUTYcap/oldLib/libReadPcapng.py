#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V1.4 2021/08/25     francescopiscitelli      ######################
########    script to read the pcapng file from VMM readout
###############################################################################
###############################################################################

# import argparse
import numpy as np
import pcapng as pg
import os
import time
import sys
import ipaddress
import matplotlib.pyplot as plt

try: 
    ####### if you run default
    from lib import libMapping as maps
    from lib import libParameters as para

except ImportError:
    ####### if you run in lib 
    import libMapping as maps
    import libParameters as para

###############################################################################
###############################################################################

            
class readouts():            
    def __init__(self): 
        
        datype = 'int64'
        
        self.Ring    = -1*np.ones((0), dtype = datype)
        self.Fen     = -1*np.ones((0), dtype = datype)
        self.VMM     = -1*np.ones((0), dtype = datype)
        self.hybrid  = -1*np.ones((0), dtype = datype)
        self.ASIC    = -1*np.ones((0), dtype = datype)
        self.Channel = -1*np.ones((0), dtype = datype)
        self.ADC     = -1*np.ones((0), dtype = datype)
        self.Channel1 = -1*np.ones((0), dtype = datype)
        self.ADC1     = -1*np.ones((0), dtype = datype)     
        self.timeStamp   = np.zeros((0), dtype = datype)
        self.timeCoarse  = np.zeros((0), dtype = datype)
        self.BC      = -1*np.ones((0), dtype = datype)
        self.OTh     = -1*np.ones((0), dtype = datype)
        self.TDC     = -1*np.ones((0), dtype = datype)
        self.GEO     = -1*np.ones((0), dtype = datype)
        self.G0      = -1*np.ones((0), dtype = datype)
        self.PulseT    = np.zeros((0), dtype = datype)
        self.PrevPT    = np.zeros((0), dtype = datype)
        self.Durations = np.zeros((0), dtype = datype)
        self.mult0     = np.zeros((0), dtype = datype)
        self.mult1     = np.zeros((0), dtype = datype)
        self.heartbeats = np.zeros((0), dtype = datype)
        self.instrID    = np.zeros((0), dtype = datype)
        self.instrIDpkt = np.zeros((0), dtype = datype)
        self.instrIDUnique = np.zeros((0), dtype = datype)
                      
    
    def calculateUniqueInstrIDs(self):
        
        temp = np.unique(self.instrID)
        
        index1  = temp == ''
        index2  = temp < 0
        index = np.logical_or(index1,index2)
            
        self.instrIDUnique = temp[~index]
    
    
    def transformInReadouts(self, data):
        self.Ring       = data[:,0]
        self.Fen        = data[:,1]
        self.VMM        = data[:,2]
        self.hybrid     = data[:,3]
        self.ASIC       = data[:,4]
        self.Channel    = data[:,5]
        self.ADC        = data[:,6]
        self.BC         = data[:,7]
        self.OTh        = data[:,8]
        self.TDC        = data[:,9]
        self.GEO        = data[:,10]
        self.timeCoarse = data[:,11]
        self.PulseT     = data[:,12]
        self.PrevPT     = data[:,13]
        self.G0         = data[:,14]
        self.Channel1   = data[:,15]
        self.ADC1       = data[:,16]
        self.mult0      = data[:,17]
        self.mult1      = data[:,18]
        self.instrIDpkt = data[:,19]

    # def list(self):
    #     print("Rings {}".format(self.Ring))
    #     print("Fens {}".format(self.Fen))
    
    def append(self, reado):
        
        self.Ring     = np.concatenate((self.Ring, reado.Ring), axis=0)
        self.Fen      = np.concatenate((self.Fen, reado.Fen), axis=0)
        self.VMM      = np.concatenate((self.VMM, reado.VMM), axis=0)
        self.hybrid   = np.concatenate((self.hybrid, reado.hybrid), axis=0)
        self.ASIC     = np.concatenate((self.ASIC, reado.ASIC), axis=0)
        self.Channel  = np.concatenate((self.Channel, reado.Channel), axis=0)
        self.ADC      = np.concatenate((self.ADC, reado.ADC), axis=0)
        self.Channel1 = np.concatenate((self.Channel1, reado.Channel1), axis=0)
        self.ADC1     = np.concatenate((self.ADC1, reado.ADC1), axis=0)
        self.timeStamp  = np.concatenate((self.timeStamp, reado.timeStamp), axis=0)
        self.BC      = np.concatenate((self.BC, reado.BC), axis=0)
        self.OTh     = np.concatenate((self.OTh, reado.OTh), axis=0)
        self.TDC     = np.concatenate((self.TDC, reado.TDC), axis=0)
        self.GEO     = np.concatenate((self.GEO, reado.GEO), axis=0)
        self.G0      = np.concatenate((self.G0, reado.G0), axis=0)
        self.PulseT  = np.concatenate((self.PulseT, reado.PulseT), axis=0)
        self.PrevPT  = np.concatenate((self.PrevPT, reado.PrevPT), axis=0)
        self.timeCoarse = np.concatenate((self.timeCoarse, reado.timeCoarse), axis=0)
        self.Durations  = np.append(self.Durations, reado.Durations)
        self.mult0     = np.concatenate((self.mult0, reado.mult0), axis=0)
        self.mult1     = np.concatenate((self.mult1, reado.mult1), axis=0)
        self.heartbeats = np.concatenate((self.heartbeats, reado.heartbeats), axis=0)
        self.instrID    = np.concatenate((self.instrID , reado.instrID), axis=0)
        self.instrIDpkt    = np.concatenate((self.instrIDpkt , reado.instrIDpkt), axis=0)
        self.instrIDUnique = np.concatenate((self.instrIDUnique , reado.instrIDUnique), axis=0)
        
    def concatenateReadoutsInArrayForDebug(self):
        
        leng = len(self.timeStamp)
        
        if leng >= 1:
            readoutsArray = np.zeros((leng,20),dtype = 'int64')
            
            readoutsArray[:,0] = self.Ring
            readoutsArray[:,1] = self.Fen
            readoutsArray[:,2] = self.hybrid
            readoutsArray[:,3] = self.ASIC
            readoutsArray[:,4] = self.Channel
            readoutsArray[:,5] = self.ADC
            readoutsArray[:,6] = self.PulseT
            readoutsArray[:,7] = self.PrevPT
            readoutsArray[:,8] = self.timeStamp
            readoutsArray[:,9] = self.timeCoarse
            readoutsArray[:,10] = self.TDC
            readoutsArray[:,11] = self.G0      # G0 also for MON
            readoutsArray[:,12] = self.BC      # POS X for MON
            readoutsArray[:,13] = self.OTh     # POS Y for MON
            readoutsArray[:,14] = self.GEO     # type for MON
            readoutsArray[:,15] = self.Channel1 # for clustered mode 
            readoutsArray[:,16] = self.ADC1     # for clustered mode 
            readoutsArray[:,17] = self.mult0    # for clustered mode 
            readoutsArray[:,18] = self.mult1    # for clustered mode 
            readoutsArray[:,19] = self.instrIDpkt    
        
        else:
            
            readoutsArray = None
            
        return readoutsArray
    
    def sortByTimeStamps(self):
        
        indexes = self.timeStamp.argsort(kind='quicksort')
        
        self.timeStamp =  self.timeStamp[indexes]
        self.Ring      =  self.Ring[indexes]
        self.Fen       =  self.Fen[indexes]
        self.VMM       =  self.VMM[indexes]
        self.hybrid    =  self.hybrid[indexes]
        self.ASIC      =  self.ASIC[indexes]
        self.Channel   =  self.Channel[indexes]
        self.ADC       =  self.ADC[indexes]
        self.Channel1  =  self.Channel1[indexes]
        self.ADC1      =  self.ADC1[indexes]
        self.BC        =  self.BC[indexes]
        self.OTh       =  self.OTh[indexes]
        self.TDC       =  self.TDC[indexes]
        self.GEO       =  self.GEO[indexes]
        self.PulseT    =  self.PulseT[indexes]
        self.PrevPT    =  self.PrevPT[indexes]
        self.timeCoarse = self.timeCoarse[indexes]
        self.G0        =  self.G0[indexes]
        self.mult0     =  self.mult0[indexes]
        self.mult1     =  self.mult1[indexes]
        self.instrIDpkt     =  self.instrIDpkt[indexes]
        
    def calculateDuration(self):
         
         # Tstart = np.min(self.timeStamp)
         # Tstop  = np.max(self.timeStamp)
         try:
             Tstart = self.timeStamp[0]
             Tstop  = self.timeStamp[-1]
         except: 
             Tstart = 0
             Tstop  = 0
             print('\t \033[1;33mWARNING: Not able to calculate duration! (File might be empty)\033[1;37m')
             time.sleep(2)
         
         self.Durations = np.round(Tstop-Tstart, decimals = 3)
         
    def calculateTimeStampWithTDC(self,NSperClockTick,time_offset=0,time_slope=1):
        
         self.timeStamp = self.timeCoarse + VMM3A_convertCalibrate_TDC_ns(self.TDC,NSperClockTick,time_offset,time_slope).TDC_ns

    ###############

    def checkIfCalibrationMode(self):
        
        flag = False
        
        if np.any(self.G0 == 1) :
            
              flag = True
              
              qty = np.sum(self.G0 == 1)
              
              total = np.shape(self.G0)[0]
            
              print('\n\t\033[1;33mWARNING: {} calibration latency mode data found in READOUTS {}.\033[1;37m'.format(qty,total),end='')
              time.sleep(1)
             
        return flag     
    
    def checkIfClusteredMode(self):
        
        flag = False
        
        if np.any(self.G0 == 2) :
            
              flag = True
              
              qty = np.sum(self.G0 == 2)
              
              total = np.shape(self.G0)[0]
            
              print('\n\t\033[1;33mWARNING: {} clustered mode data found in READOUTS {}, whereas you selected normal hit mode!\033[1;37m'.format(qty,total),end='') 
              time.sleep(1)
             
        return flag     
    
    def checkIfNormalHitMode(self):
        
        flag = False
        
        if np.any(self.G0 == 0) :
            
              flag = True
              
              qty = np.sum(self.G0 == 0)
              
              total = np.shape(self.G0)[0]
            
              print('\n\t\033[1;33mWARNING: {} normal hit mode data found in READOUTS {}, whereas you selected clustered mode!\033[1;37m'.format(qty,total),end='')
              time.sleep(1)
             
        return flag     
    
     ###############        
            
    def removeCalibrationData(self):
        print('--> removing latency calib data from readouts ...')
        CalibData = self.G0 == 1
        self.removeData(CalibData)
        removedNum = np.sum(CalibData)
        return removedNum 
         
    def removeClusteredData(self):
        print('--> removing clustered data from readouts ...')
        ClusterData = self.G0 == 2
        self.removeData(ClusterData)
        removedNum = np.sum(ClusterData)
        return removedNum 
        
    def removeNormalHitData(self):
        print('--> removing normal hit data from readouts ...')
        NormalHitData = self.G0 == 0
        self.removeData(NormalHitData)     
        removedNum = np.sum(NormalHitData)
        return removedNum 
    
    def removeData(self, toBeRemoved):
        
        self.Ring    = self.Ring[~toBeRemoved]
        self.Fen     = self.Fen[~toBeRemoved]
        self.VMM     = self.VMM[~toBeRemoved]
        self.hybrid  = self.hybrid[~toBeRemoved]
        self.ASIC    = self.ASIC[~toBeRemoved]
        self.Channel = self.Channel[~toBeRemoved]
        self.ADC     = self.ADC[~toBeRemoved]
        self.Channel1 = self.Channel1[~toBeRemoved]
        self.ADC1     = self.ADC1[~toBeRemoved]
        self.timeStamp   = self.timeStamp[~toBeRemoved]
        self.timeCoarse  = self.timeCoarse[~toBeRemoved]
        self.BC      = self.BC[~toBeRemoved]
        self.OTh     = self.OTh[~toBeRemoved]
        self.TDC     = self.TDC[~toBeRemoved]
        self.GEO     = self.GEO[~toBeRemoved]
        self.G0      = self.G0[~toBeRemoved]
        self.PulseT  = self.PulseT[~toBeRemoved]
        self.PrevPT  = self.PrevPT[~toBeRemoved]
        self.mult0   = self.mult0[~toBeRemoved]
        self.mult1   = self.mult1[~toBeRemoved]
        self.instrIDpkt   = self.instrIDpkt[~toBeRemoved]
   
        
    ###############
    
    def checkChopperFreq(self):  
        
        try:    
            
            try:        
                # this extracts timing from all packets, also empty -> heartbeats 
                indexesIsNotZero2  = np.argwhere(self.heartbeats>0)
                heartbeats2        = self.heartbeats[indexesIsNotZero2]
                heartbeatsUnique   = np.unique(heartbeats2)
                
                deltaTime2         = np.diff(heartbeatsUnique - heartbeatsUnique[0])
                indexesIsNotZero3  = np.argwhere(deltaTime2>0)
                deltaTimeNoTZero3  = deltaTime2[indexesIsNotZero3]
                meanDelta2         = np.mean(deltaTimeNoTZero3)/1e9
                varianceDelta2     = np.var(deltaTimeNoTZero3)/1e9
                meanFreq2          = 1/meanDelta2
            
                if np.isnan(meanDelta2):
                    print('\nNo Chopper found or all data is in one single Pulse Time')
                else:
                    print('\nHeartbeats Period     (all unique packets: %d)       is %.6f s (variance %.6f s) --> frequency %.3f Hz' % ((len(deltaTimeNoTZero3)+1,meanDelta2,varianceDelta2,meanFreq2)))
           
            except:
                    print('\t \033[1;33mWARNING: Unable to calculate timing/chopper frequency from all packets!\033[1;37m')
                    time.sleep(2)   

        
            try:
                # this extract timing from non-empty packets 
                deltaTime         = np.diff(self.PulseT - self.PulseT[0])
                indexesIsNotZero  = np.argwhere(deltaTime>0)
                deltaTimeNoTZero  = deltaTime[indexesIsNotZero]
                meanDelta         = np.mean(deltaTimeNoTZero)/1e9
                varianceDelta     = np.var(deltaTimeNoTZero)/1e9
                meanFreq          = 1/meanDelta
                
              
                if np.isnan(meanDelta):
                    print('\nNo Chopper found or all data is in one single Pulse Time')
                else:
                   print('Timing/Chopper Period (not empty unique packets: %d) is %.6f s (variance %.6f s) --> frequency %.3f Hz' % ((len(deltaTimeNoTZero)+1,meanDelta,varianceDelta,meanFreq)))
            except:
                    print('\t \033[1;33mWARNING: Unable to calculate timing/chopper frequency from not empty packets! Packets might be all empty! \033[1;37m')
                    time.sleep(2)   

        except:
            
            print('\t \033[1;33mWARNING: Unable to calculate timing/chopper frequency!\033[1;37m')
            time.sleep(2)   

    
    def removeNonESSpacketsHeartbeats(self,heartbeats):
        indexesIsNotZero  = np.argwhere(heartbeats>0)
        heartbeats        = heartbeats[indexesIsNotZero[:,0]]
        return heartbeats
     
    # def removeNonESSpacketsHeartbeats(self):
    #     indexesIsNotZero = np.argwhere(self.heartbeats>0)
    #     self.heartbeats  = self.heartbeats[indexesIsNotZero[:,0]]

   
    def checkInvalidToFsInReadouts(self):
        
        NumReadouts = np.shape(self.timeStamp)[0]
        
        tempToF = self.timeStamp - self.PulseT
        
        invalidToFs = tempToF < 0
        
        invalidToFsCounter1 = np.sum(invalidToFs)
        
        invalidToFsCounter2 = 0
                  
        if invalidToFsCounter1 > 0:
            
            tempToF2 = self.timeStamp[invalidToFs] - self.PrevPT[invalidToFs]
            
            invalidToFsAgain = tempToF2 < 0
            
            invalidToFsCounter2 = np.sum(invalidToFsAgain)
            
        validToFs  = NumReadouts - invalidToFsCounter2
        validValid = NumReadouts - invalidToFsCounter1 
        validPrevP = invalidToFsCounter1 - invalidToFsCounter2 
           
        print('\n \033[1;33m\t Readouts %d: %d ToFs valid (%d valid, %d PrevPulse corrected) - invalid %d \033[1;37m' % (NumReadouts,validToFs,validValid,validPrevP,invalidToFsCounter2))
 
    
class extractReoudoutSelection():
           
           def extract(self,readouts1,selection):
                    
               readoutsEx = readouts()
               
               readoutsEx.Ring     = readouts1.Ring[selection]
               readoutsEx.Fen      = readouts1.Fen[selection]
               readoutsEx.VMM      = readouts1.VMM[selection]
               readoutsEx.hybrid   = readouts1.hybrid[selection]
               readoutsEx.ASIC     = readouts1.ASIC[selection]
               readoutsEx.Channel  = readouts1.Channel[selection]
               readoutsEx.ADC      = readouts1.ADC[selection]
               readoutsEx.Channel1 = readouts1.Channel1[selection]
               readoutsEx.ADC1     = readouts1.ADC1[selection]
               readoutsEx.timeStamp  = readouts1.timeStamp[selection]
               readoutsEx.BC      = readouts1.BC[selection]
               readoutsEx.OTh     = readouts1.OTh[selection]
               readoutsEx.TDC     = readouts1.TDC[selection]
               readoutsEx.GEO     = readouts1.GEO[selection]
               readoutsEx.G0      = readouts1.G0[selection]
               readoutsEx.PulseT  = readouts1.PulseT[selection] 
               readoutsEx.PrevPT  = readouts1.PrevPT[selection]
               readoutsEx.timeCoarse = readouts1.timeCoarse[selection]
               # readoutsEx.Durations  = readouts1.Durations[selection]
               readoutsEx.mult0     = readouts1.mult0[selection] 
               readoutsEx.mult1     = readouts1.mult1[selection]
               # readoutsEx.heartbeats = readouts1.heartbeats[selection]
               # readoutsEx.instrID    = readouts1.instrID[selection]
               readoutsEx.instrIDpkt    = readouts1.instrIDpkt[selection]
               # readoutsEx.instrIDUnique = readouts1.instrIDUnique[selection]
           
               return readoutsEx 
        
###############################################################################
###############################################################################

class checkInstrumentID():
    def __init__(self):
        
        self.instruments = {
            # ID:   {"name": Name, "hex": Hex, "tech": Type, "hw": Type, "bytes": N, "supported": Bool}
            72:  {"name": "FREIA",    "hex": "0x48", "type": "MB",    "hw": "VMM",      "bytes": 20, "supported": True, "readerSupported": True},
            76:  {"name": "ESTIA",    "hex": "0x4c", "type": "MB",    "hw": "VMM",      "bytes": 20, "supported": True, "readerSupported": True},
            78:  {"name": "AMOR",     "hex": "0x4e", "type": "MB",    "hw": "VMM",      "bytes": 20, "supported": True, "readerSupported": True},
            73:  {"name": "TBLMB",    "hex": "0x49", "type": "MB",    "hw": "VMM",      "bytes": 20, "supported": True, "readerSupported": True},
            
            64:  {"name": "TREX",     "hex": "0x40", "type": "MG",    "hw": "VMM",      "bytes": 20, "supported": True,  "readerSupported": True},
            68:  {"name": "NMX",      "hex": "0x44", "type": "GDG",   "hw": "VMM",      "bytes": 20, "supported": False, "readerSupported": True},
            
            60:  {"name": "CSPEC",    "hex": "0x3c", "type": "He3",   "hw": "R5560",    "bytes": 24, "supported": True, "readerSupported": True},
            52:  {"name": "BIFROST",  "hex": "0x34", "type": "He3",   "hw": "R5560",    "bytes": 24, "supported": True, "readerSupported": True},
            56:  {"name": "MIRACLES", "hex": "0x38", "type": "He3",   "hw": "R5560",    "bytes": 24, "supported": True, "readerSupported": True},
            00:  {"name": "VESPA",    "hex": "0x00", "type": "He3",   "hw": "R5560",    "bytes": 24, "supported": True, "readerSupported": True},
            
            48:  {"name": "LOKI",     "hex": "0x30", "type": "straw", "hw": "R5560bis", "bytes": 24, "supported": False, "readerSupported": False},
            16:  {"name": "BM",       "hex": "0x10", "type": "BM",    "hw": "BM",       "bytes": 20, "supported": True, "readerSupported": True},
            32:  {"name": "SKADI",    "hex": "0x20", "type": "SKADI", "hw": "SKADI",    "bytes": 20, "supported": False, "readerSupported": True},
            
            100: {"name": "MAGIC",    "hex": "0x64", "type": "JAL",   "hw": "CPIX",     "bytes": 20, "supported": False, "readerSupported": False},
            96:  {"name": "DREAM",    "hex": "0x60", "type": "JAL",   "hw": "CPIX",     "bytes": 20, "supported": False, "readerSupported": False}
        }
        
    def printInfoDataStream(self,ID):
        
        # print('checking intrument ID ... ',end='')
        self.getInfoFromID(ID)
        if self.instrName != "Unknown":
            print(f"found {self.instrName} data stream - {self.ROEtype}",end='')
        
    def getIDFromName(self, name):
        for instrument_id, info in self.instruments.items():
            if info["name"].upper() == name.upper():
                return instrument_id
        return None    
    
    def getInfoFromID(self, ID):
            # Retrieve the entry using the ID as a key
            data = self.instruments.get(ID)
        
            if data:
                self.instrName           = data["name"]
                self.detType             = data["type"]
                self.ROEtype             = data["hw"] 
                self.bytesPerReadout     = data["bytes"]
                self.flagSupported       = data["supported"]
                self.flagReadSupported   = data["readerSupported"]
                
            else:
                # Defaults if ID is unknown
                self.InstrName           = "Unknown"
                self.detType             = "N/A"
                self.ROEtype             = None
                self.bytesPerReadout     = 20
                self.flagSupported       = False
                self.flagReadSupported   = False
                
                # print('found some other data stream',end='')
            
            return self.bytesPerReadout, self.ROEtype
   
  
       
    def checkValidDataStream(self,IDs):

        print('checking intrument IDs and data streams ... ',end='')
        
        temp = np.unique(IDs)
        index  = temp < 0
        instrIDs = temp[~index]
    
        
        if len(instrIDs) == 0:
            print('\n---> no instr ID', end='')
            
        elif len(instrIDs) == 1: 
    
            target_id = instrIDs[0]    
            self.getInfoFromID(target_id)
            # info
            # print(f"found: {info.instrName} | Type: {info.detType} | Readout: {info.ROEtype}")
                 
            if self.instrName == "Unknown":
                print(f"\n\033[1;31mERROR: found unknown data stream with ID {target_id}\033[0m",end='')
                time.sleep(2)
                sys.exit()
                
            elif self.flagSupported is True and self.flagReadSupported is True:
                # print('---> OK.')
                print(f"---> OK: Valid instrument ({self.instrName}).")
                # pass
            
            elif self.flagSupported is False and self.flagReadSupported is True:
                print(f"\n\033[1;33mWARNING: found '{self.instrName}' data stream, analysis not supported, reader only! Analysis continues but questionable results are on the horizon.\033[0m")
                
            elif self.flagSupported is False and self.flagReadSupported is False:   
                print(f"\n\033[1;31mERROR: found '{self.instrName}' data stream, analysis nor reader supported! Exit.\033[0m")
                time.sleep(2)
                sys.exit()
                
            elif self.flagSupported is True and self.flagReadSupported is False:
                print(f"\n\033[1;31mERROR: found '{self.instrName}' data stream, supported but flag Reader supported is False -> check class checkInstrumentID() in pcapreader! Exit.\033[0m")
                time.sleep(2)
                sys.exit()
            
        elif len(instrIDs) == 2: 
            
            all_streams = []
            valid_for_analysis = []
            valid_for_reading = []
            has_BM = False
            
            for ids in instrIDs:
                 self.getInfoFromID(ids)

                 # print(f"found: {info.instrName} | Type: {info.detType} | Readout: {info.ROEtype}")
                 
                 if self.detType == "BM":
                    has_BM = True
                 
                 all_streams.append(self.instrName)
                 if self.flagSupported is True and self.flagReadSupported is True:
                    valid_for_analysis.append(self.instrName)
                 elif self.flagSupported is False and self.flagReadSupported is True:
                    valid_for_reading.append(self.instrName)
           
            valid_for_analysis = [n for n in valid_for_analysis if n != "BM"]
            valid_for_reading  = [n for n in valid_for_reading if n != "BM"]
            
            # Case 1: Ideal Pair (1 Main Detector + 1 Beam Monitor)
            if len(valid_for_analysis) == 1 and has_BM:
                print(f"---> OK: Valid instrument ({valid_for_analysis[0]}) with Beam Monitor detected.")
                
            # Case 2: Two Main Detectors (Both valid for analysis)
            elif len(valid_for_analysis) == 2:
                print(f"\033[1;33m---> WARNING: Two valid analysis streams found ({', '.join(valid_for_analysis)}). "
                      "Check RMM output queue config!\033[0m")
    
            # Case 3: One Analysis stream + One Unknown/Unsupported stream
            elif len(valid_for_analysis) == 1:
                other = [n for n in all_streams if n != valid_for_analysis[0]][0]
                print(f"\033[1;33m---> WARNING: Found {valid_for_analysis[0]}, but the second stream ({other}) "
                      "is not supported. Results might be affected.\033[0m")
    
            # Case 4: No Analysis streams, but Reader support exists (e.g., BM + SKADI)
            elif len(valid_for_reading) == 1:
                print(f"\033[1;33m---> WARNING: 2 data streams detected: ({', '.join(all_streams)}). "
                f"\033[1;33mNo analysis-ready streams. Only reader support for: "
                      f"({', '.join(valid_for_reading)}). Analysis continues but check config RMM.\033[0m")
                
            elif has_BM and len(valid_for_reading) == 0 and len(valid_for_analysis) == 0:
                other = [n for n in all_streams if n != "BM"][0]
                # print(f"\033[1;33m---> WARNING: 2 data streams detected: ({', '.join(all_streams)}). No analysis-ready streams nor reader found, but the second stream is BM"
                #       "Results might be affected.\033[0m")
                
                print(f"\033[1;33m---> WARNING: 2 data streams detected: ({', '.join(all_streams)}). "
                      f"No analysis-ready streams found. The non-BM stream ({other}) is unsupported. "
                      "Results might be affected.\033[0m")
                
                
            # Case 5: Total Failure
            else:
               print(f"\033[1;31m---> ERROR: 2 data streams detected: ({', '.join(all_streams)}). Neither of the 2 streams are valid for analysis or reading. Exit.\033[0m")
               time.sleep(2)
               sys.exit() 
            
        elif len(instrIDs) >= 3: 
            
            all_streams = []
            valid_for_analysis = []
            valid_for_reading = []
            
            for ids in instrIDs:
                 self.getInfoFromID(ids)
                 # print(f"found: {info.instrName} | Type: {info.detType} | Readout: {info.ROEtype}")
                 all_streams.append(self.instrName)
                 if self.flagSupported is True and self.flagReadSupported is True:
                    valid_for_analysis.append(self.instrName)
                 elif self.flagSupported is False and self.flagReadSupported is True:
                    valid_for_reading.append(self.instrName)
           
            print(f"\n\033[1;33mWARNING: {len(instrIDs)} data streams detected: ({', '.join(all_streams)})\033[0m")         
            # Final decision after checking all IDs
            if valid_for_analysis:
                print(f"\033[1;33m---> At least one valid stream found ({', '.join(valid_for_analysis)}). Analysis continues despite extra data. Data might be corrupted - check RMM output queue config! \033[0m")
            elif valid_for_reading:
                print(f"\033[1;33m---> WARNING: None of the {len(instrIDs)} ({', '.join(valid_for_reading)}) streams are valid for analysis but just reader. Analysis continues. Data might be corrupted - check RMM output queue config!\033[0m")
            else:
                print(f"\033[1;31m---> ERROR: None of the {len(instrIDs)} streams are valid for analysis nor just reader. Exit.\033[0m")
                time.sleep(2)
                sys.exit()       
                
                    
    def checkDetTypeExists(self, detType):
   
        flag  = False 
        
        existing_types = {info["type"] for info in self.instruments.values()}

        if detType in existing_types:
                # 2. Find the specific support status for this type
                # We look for the first instrument that matches this detType
                match = next((info for info in self.instruments.values() if info["type"] == detType), None)
                
                if match:
                    
                    flag  = True 
                    is_supp = match["supported"]
                    is_read_supp = match["readerSupported"]
        
                    # Logic for different warning messages
                    if not is_supp and is_read_supp:
                        print(f"\033[1;33mWARNING: detector type {detType} is supported only by the Reader, but not yet by the Main Analysis Pipeline.\033[0m")
                    
                    elif not is_supp and not is_read_supp:
                        print(f"\033[1;31mWERROR: detector type {detType} is currently not supported.\033[0m")
                        time.sleep(2)
                        sys.exit()

               
        else:
                print(f"\n\033[1;31mERROR: detector type {detType} in config file is not a possible type. Valid types: {', '.join(existing_types)}\033[0m")
                time.sleep(2)
                sys.exit()
                
        return flag 
            
        
    def matchDataStreamWithConfig(self, instrNameFromConf, detType, IDs):  
        
        # print('checking intrument IDs and data streams ... ')
        
        temp = np.unique(IDs)
        index  = temp < 0
        instrIDs = temp[~index]
    
        if len(instrIDs) == 0:
            print('\n---> no instr ID', end='')
            
        flagSupported = self.checkDetTypeExists(detType)

        foundFlag = False 

        all_streams  = []
        all_types    = []

        for ids in instrIDs:
             self.getInfoFromID(ids)
             all_streams.append(self.instrName)
             all_types.append(self.detType)
             
             # print(f"found: {self.instrName} | Type: {self.detType} | Readout: {self.ROEtype}")
             
             if self.detType == detType:
                 foundFlag = True 
                 
        # Remove duplicates from the stream list for a cleaner message
        unique_types   = ", ".join((all_types))
        unique_streams = ", ".join((all_streams))
        
        # print(all_types)
        # print(all_streams)

        if foundFlag:
            print(f"\n\t\033[1;33mFile containing data streams {unique_streams} for detector types {unique_types}\033[0m")
            print(f"\t\033[1;33manalyzchaoppered for instrument {instrNameFromConf} and type {detType}\033[0m")
            # print(f"\nSuccess: Configuration match found for {detType}.")

            # pass
            
        # Check if we found a Beam Monitor (BM) in the file streams
        elif "BM" in all_types:
            # print(f"\n\033[1;36mNOTE: Beam Monitor (BM) stream detected.\033[0m")
            # print(f"\033[1;36mSkipping standard mismatch warning. Ensure BM data is handled separately.\033[0m")
            print(f"\n\t\033[1;31mWARNING: CONFIGURATION MISMATCH!\033[0m",end='')
            print(f"\n\t\033[1;31mYou are trying to read a file containing data streams {unique_streams} for detector types {unique_types}\033[0m")
            print(f"\t\033[1;31mBut in your config file you have specified instrument {instrNameFromConf} and type {detType}\033[0m")
            
        else:

            print(f"\n\t\033[1;31mWARNING: CONFIGURATION MISMATCH!\033[0m",end='')
            print(f"\n\t\033[1;31mYou are trying to read a file containing data streams {unique_streams} for detector types {unique_types}\033[0m")
            print(f"\t\033[1;31mBut in your config file you have specified instrument {instrNameFromConf} and type {detType}\033[0m")
        
        

###############################################################################
###############################################################################

class checkBMtype():
    def __init__(self, instrIDspkt, GEO, BMhw):
           
         ID = checkInstrumentID().getIDFromName("BM")
         
         selectBM = (instrIDspkt == ID)
         
         if np.any(selectBM):
             
             actual_geos = np.unique(GEO[selectBM])
         
             for geo_val in actual_geos:
                    # Case 1: 0D event and GENERIC hw
                    if geo_val == 1:
                        
                        if BMhw == "IBM":
                            print(f"\n\t\033[1;33mWARNING: found BM data type 1 (GENERIC - 0D) but config says {BMhw}!")  
                            print("\tThe BM data may be parsed incorrectly.\033[0m")
                        else:
                            print(f"\n\tBM data is type 1 (GENERIC - 0D)")  
                            
                    # Case 2: GEO 2 is 1D or 2D events and GENERIC hw
                    elif geo_val == 2:
                        
                        if BMhw == "IBM":
                            print(f"\n\t\033[1;33mWARNING: found BM data type 2 (GENERIC - 1D or 2D) but config says {BMhw}!")  
                            print("\tThe BM data may be parsed incorrectly.\033[0m")
                        else:
                            print(f"\n\tBM data is type 2 (GENERIC - 1D or 2D)") 
          
                    # Case 3: GEO 3 is the "IBM" 
                    elif geo_val == 3:
                        
                        if BMhw == "GENERIC":
                            print(f"\n\t\033[1;33mWARNING: found BM data type 3 (IBM) but config says {BMhw}!")
                            print("\tThe BM data may be parsed incorrectly.\033[0m")
                        else:
                            print(f"\n\tBM data is type 3 (IBM)") 
                            
                    # Case 4: Unexpected GEO code for a Beam Monitor
                    else:
                        print(f"\n\t\033[1;31mWARNING: BM data found with unexpected type: {geo_val}.\033[0m")
                        print(f"\tValid BM types are usually only type 0 (GENERIC) or 3 (IBM).\033[0m")

        

###############################################################################
###############################################################################



class  checkWhich_RingFenHybrid_InFile():
    def __init__(self, filePathAndFileName, NSperClockTick):
                
        pcap = pcapng_reader(filePathAndFileName, NSperClockTick, timeResolutionType = 'coarse', sortByTimeStampsONOFF = False)
        self.readouts = pcap.readouts
        
        temp = os.path.split(filePathAndFileName)
        # filePath = temp[0]+'/'
        self.fileName = temp[1]

    def check(self):
        
        print("\nRings, Fens and Hybrids in file: {}".format(self.fileName))
        
        RingsInFile = np.unique(self.readouts.Ring)
        
        cont = 0 
        
        for RR in RingsInFile:
            
            # self.RFH['Ring'] = RR
            
            selectRING = self.readouts.Ring == RR
            
            Fens4Ring    = self.readouts.Fen[selectRING]
            Hybrids4Ring = self.readouts.hybrid[selectRING]
            
            FensInRing = np.unique(Fens4Ring)
            
            for FF in FensInRing:
                
                selectFEN = Fens4Ring == FF
                
                Hybrids4Fen = Hybrids4Ring[selectFEN]
                
                HybridsInFen = np.unique(Hybrids4Fen)
                
                for HH in HybridsInFen:
                    
                    cont += 1
                
                    print("\tNo. {}:     Ring {}, Fen {}, Hybrid {}".format(cont,int(RR),int(FF),int(HH)))

           
        
#################################################  
class SKADI():
    def __init__(self, buffer, NSperClockTick):
        
        # valid for MIRACLES, BIFROST and  CSPEC -- NOT LOKI!  
         
        # decode into little endian integers
        PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
        self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
        timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
        timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
        
        opModeFlags  = int.from_bytes(buffer[12:13], byteorder='little')
        self.sysID        = int.from_bytes(buffer[13:14], byteorder='little')
        self.IP           = int.from_bytes(buffer[14:15], byteorder='little')
        self.ASICchannel  = int.from_bytes(buffer[15:16], byteorder='little')
        self.column       = int.from_bytes(buffer[16:17], byteorder='little')
        self.row          = int.from_bytes(buffer[17:18], byteorder='little')
        self.ADC          = int.from_bytes(buffer[18:20], byteorder='little')
        
        
        #######################
        #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
        self.Ring = int(np.floor(PhysicalRing/2))
        # self.Ring = PhysicalRing
        #######################
        
        self.OpMod    = (opModeFlags & 0xF0) >> 4
        self.flags    = (opModeFlags & 0x0F) 

        timeHIns = int(round(timeHI * 1000000000))
        timeLOns = int(round(timeLO * NSperClockTick))
        
        self.timeCoarse  = timeHIns + timeLOns
        
#################################################
 
class R5560():
    def __init__(self, buffer, NSperClockTick):
        
        # valid for MIRACLES, BIFROST and  CSPEC -- NOT LOKI!  
         
        # decode into little endian integers
        PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
        self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
        timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
        timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
        
        self.tube         = int.from_bytes(buffer[13:14], byteorder='little')
        self.counter1     = int.from_bytes(buffer[14:16], byteorder='little')
        self.ampA         = int.from_bytes(buffer[16:18], byteorder='little')
        self.ampB         = int.from_bytes(buffer[18:20], byteorder='little')
        self.counter2     = int.from_bytes(buffer[20:24], byteorder='little')
        
        
        #######################
        #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
        self.Ring = int(np.floor(PhysicalRing/2))
        # self.Ring = PhysicalRing
        #######################

        timeHIns = int(round(timeHI * 1000000000))
        timeLOns = int(round(timeLO * NSperClockTick))
        
        self.timeCoarse  = timeHIns + timeLOns
        
#################################################

class MONdata():
    def __init__(self, buffer, NSperClockTick):
          
       # decode into little endian integers
       PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
       self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
       self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
       timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
       timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
       self.Type    = int.from_bytes(buffer[12:13], byteorder='little')
       self.Channel = int.from_bytes(buffer[13:14], byteorder='little')
       self.ADC     = int.from_bytes(buffer[14:16], byteorder='little')
       self.posX    = int.from_bytes(buffer[16:18], byteorder='little')
       self.posY    = int.from_bytes(buffer[18:20], byteorder='little')
       
       #######################
       #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
       self.Ring = int(np.floor(PhysicalRing/2))
       # self.Ring = PhysicalRing
       #######################

       timeHIns = int(round(timeHI * 1000000000))
       timeLOns = int(round(timeLO * NSperClockTick))
       
       self.timeCoarse  = timeHIns + timeLOns 
 
#################################################

class IBM_MONdata():
    def __init__(self, buffer, NSperClockTick):
          
       # decode into little endian integers
       PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
       self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
       self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
       timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
       timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
       self.Type    = int.from_bytes(buffer[12:13], byteorder='little')
       self.Channel = int.from_bytes(buffer[13:14], byteorder='little')
       self.UNSdebug  = int.from_bytes(buffer[14:16], byteorder='little')
       temp         = int.from_bytes(buffer[16:19], byteorder='little')
       self.MCAsum  = int.from_bytes(buffer[19:20], byteorder='little')
       
       
       if self.MCAsum > 0:
          self.ADC = int(temp / self.MCAsum)
       else:
          self.ADC = 0 
    
       
       #######################
       #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
       self.Ring = int(np.floor(PhysicalRing/2))
       # self.Ring = PhysicalRing
       #######################

       timeHIns = int(round(timeHI * 1000000000))
       timeLOns = int(round(timeLO * NSperClockTick))
       
       self.timeCoarse  = timeHIns + timeLOns 
 
#################################################

class VMM3A_modes():
    def __init__(self, buffer):
        
        self.G0 = -1
        
        # hybrid   = int.from_bytes(buffer[17:18], byteorder='little')
        
        G0GEO   = int.from_bytes(buffer[16:17], byteorder='little')
    
        temp  = (G0GEO & 0xC0) >> 6     #extract only first two MSB and shift right by 6
        
        geoBit6 = (temp & 0x1)          #bit 6 - if 0 either calib or normal mode, if 1 clustered mode 
        geoBit7 = (temp & 0x2) >> 1     #bit 7 - if 1 calib or 0 normal mode, if bit 6 is 0
        
        if geoBit6 == 1:
            # print('clustered mode')
            self.G0 = 2
        elif geoBit6 == 0:
            if geoBit7 == 1: 
                # print('calibration mode')
                self.G0 = 1
            elif geoBit7 == 0: 
                # print('normal hit mode')
                self.G0 = 0
                
        # self.G0 =  geoBit7      


class VMM3Aclustered():
    def __init__(self, buffer, NSperClockTick):
                 
        # decode into little endian integers
        PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
        self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
        timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
        timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
        
        ADC0temp    = int.from_bytes(buffer[12:14], byteorder='little')
        ADC1temp    = int.from_bytes(buffer[14:16], byteorder='little')
        
        # self.ADC      = int.from_bytes(buffer[12:14], byteorder='little')
        # self.ADC1     = int.from_bytes(buffer[14:16], byteorder='little')
        G0GEO         = int.from_bytes(buffer[16:17], byteorder='little')
        self.hybrid   = int.from_bytes(buffer[17:18], byteorder='little')
        self.Channel  = int.from_bytes(buffer[18:19], byteorder='little')
        self.Channel1 = int.from_bytes(buffer[19:20], byteorder='little')
        
        #######################
        #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
        self.Ring = int(np.floor(PhysicalRing/2))
        # self.Ring = PhysicalRing
        #######################

        self.ADC      = ADC0temp & 0x1FFF  #extract only 13 LSB
        self.ADC1     = ADC1temp & 0x1FFF  #extract only 13 LSB
        
        self.mult0    = (ADC0temp & 0xE000) >> 13 #extract only 3 MSB
        self.mult1    = (ADC1temp & 0xE000) >> 13 #extract only 3 MSB
        
        modes         = VMM3A_modes(buffer)
        self.G0       = modes.G0

        self.GEO      = G0GEO & 0x3F
        
        timeHIns = int(round(timeHI * 1000000000))
        timeLOns = int(round(timeLO * NSperClockTick))

        self.timeCoarse  = timeHIns + timeLOns
        
        self.VMM  = -1
        self.ASIC = -1
        self.BC   = -1
        self.OTh  = 1
        self.TDC  = 0
        
   
class VMM3A():
    def __init__(self, buffer, NSperClockTick):
                 
        # decode into little endian integers
        PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
        self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
        timeHI       = int.from_bytes(buffer[4:8], byteorder='little')
        timeLO       = int.from_bytes(buffer[8:12], byteorder='little')
        self.BC      = int.from_bytes(buffer[12:14], byteorder='little')
        OTADC        = int.from_bytes(buffer[14:16], byteorder='little')
        G0GEO        = int.from_bytes(buffer[16:17], byteorder='little')
        self.TDC     = int.from_bytes(buffer[17:18], byteorder='little')
        self.VMM     = int.from_bytes(buffer[18:19], byteorder='little')
        self.Channel = int.from_bytes(buffer[19:20], byteorder='little')
        
        self.Channel1 = -1
        self.ADC1     = -1
        self.mult0    = -1
        self.mult1    = -1
        
        #######################
        #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
        self.Ring = int(np.floor(PhysicalRing/2))
        # self.Ring = PhysicalRing
        #######################

        self.ADC      = OTADC & 0x3FF  #extract only 10 LSB
        self.OTh      = OTADC >> 15    #extract only 1 MSB

        # self.G0       = G0GEO >> 7
        modes         = VMM3A_modes(buffer)
        self.G0       = modes.G0
        
        self.GEO      = G0GEO & 0x3F
        
        self.ASIC     =  self.VMM & 0x1           #extract only LSB
        self.hybrid   = (self.VMM & 0xE) >> 1     #extract only 1110 and shift right by one 
        
        timeHIns = int(round(timeHI * 1000000000))
        timeLOns = int(round(timeLO * NSperClockTick))
        
        self.timeCoarse  = timeHIns + timeLOns
       

class VMM3A_convertCalibrate_TDC_ns(): 
    def __init__(self,TDC,NSperClockTick,time_offset=0,time_slope=1):
                
        # self.TDC = TDC
        # self.NSperClockTick = NSperClockTick
   
        self.pTAC = 60    #  in ns
        
    # def convert_ns(self):
        
    #     self.calibrate(time_offset=0, time_slope=1)
        
    # def calibrate(self,time_offset,time_slope):
        
         # time_offset in ns, time_slope adimensional
        
        aboveLimit = TDC > 255
        belowLimit = TDC < 0 
        
        if np.any(aboveLimit == True):
            TDC[aboveLimit] = 255
        elif np.any(belowLimit == True):
            TDC[belowLimit] = 0
        
        TDC_ns = np.around( ( (NSperClockTick*2*1.5 - TDC*self.pTAC/255 - time_offset) * time_slope ) )

        self.TDC_ns = TDC_ns.astype('int64')
        
        
class VMM3A_calibrate_ADC():  
    def __init__(self,ADC,ADC_offset=0,ADC_slope=1):      
            
        # accepts either arrays or single scalars as ADC 
        
        ADC_calibrated = np.around(( ADC - ADC_offset ) * ADC_slope)
        
        aboveLimit = ADC_calibrated > 1023
        belowLimit = ADC_calibrated < 0
        
        if type(ADC) is int:
            
            if aboveLimit == True:
                ADC_calibrated = 1023
            elif belowLimit == True:
                ADC_calibrated = 0
           
            self.ADC_calibrated  = int(ADC_calibrated)
                
        else:            
            if np.any(aboveLimit == True):
                ADC_calibrated[aboveLimit] = 1023
            elif np.any(belowLimit == True):
                ADC_calibrated[belowLimit] = 0
                
            self.ADC_calibrated  = ADC_calibrated.astype('int64')
            
        
 
        
        
###############################################################################
###############################################################################
        

class checkIfFileExistInFolder():
     def __init__(self, filePathAndFileName):
         
          if os.path.exists(filePathAndFileName) is False:
            temp2 = os.path.split(filePathAndFileName)
            filePath = temp2[0]+'/'
            fileName = temp2[1]
            print('\n \033[1;31m---> File: '+fileName+' DOES NOT EXIST \033[1;37m')
            print('\n ---> in folder: '+filePath+' \n')
            print('\n NOTE: file name must contain extension, e.g. *.pcapng\n')
            print(' ---> Exiting ... \n')
            print('------------------------------------------------------------- \n')
            time.sleep(2)
            sys.exit()
            
################################################## 

class pcapng_reader():
    def __init__(self, filePathAndFileName, NSperClockTick=11.356860963629653, MONhw = 'GENERIC', MONconn = 'RING' , MONring = 11, timeResolutionType = 'coarse', sortByTimeStampsONOFF = False, operationMode = 'normal', pcapLoadingMethod='allocate'):
 
        
        # self.flagSupported = True
        # try:
            # print('PRE-ALLOC method to load data ...')
        pcapng = pcapng_reader_PreAlloc(NSperClockTick,MONhw,MONconn,MONring,filePathAndFileName,timeResolutionType,operationMode, kafkaStream = False)
        pcapng.allocateMemory(pcapLoadingMethod)
        pcapng.read()
        self.readouts = pcapng.readouts
        checkInstrumentID().checkValidDataStream(self.readouts.instrIDUnique)
        
        # self.flagSupported = pcapng.flagSupported

        # except:
        #     # print('\n... PRE-ALLOC method failed, trying APPEND method to load data ...')
        #     print('\n\033[1;31m... PRE-ALLOC method failed, exiting ...\033[1;37m')
            
        #     sys.exit()
            
            #  HERE IS FUTURE DEVEL IF NEEDED 
            # self.pcapng = pcapng_reader_slowAppend(filePathAndFileName)
            # self.pcapng.read(timeResolutionType)
            # self.readouts = self.pcapng.readouts    
            
        # finally:
             
        if sortByTimeStampsONOFF is True:
            print('Readouts are sorted by TimeStamp')
            self.readouts.sortByTimeStamps()   
        else: 
            print('Readouts are NOT sorted by TimeStamp')
                
        self.readouts.calculateDuration()     
                        
##################################################  

class pcapng_reader_PreAlloc():
    def __init__(self, NSperClockTick, MONhw = 'GENERIC', MONconn = 'RING', MONring = 11, filePathAndFileName = '', timeResolutionType = 'fine', operationMode = 'normal', kafkaStream = False):
        
        # self.timeResolution = 11.25e-9  #s per tick for 88.888888 MHz
        # self.timeResolution = 11.356860963629653e-9  #s per tick ESS for 88.0525 MHz
        
        self.NSperClockTick      = NSperClockTick 
        self.MONhw               = MONhw
        self.MONconn             = MONconn
        self.MONring             = MONring
        self.timeResolutionType  = timeResolutionType
        self.kafkaStream         = kafkaStream

        # print('----->>>'+(self.timeResolutionType))
        
        # operation mode is either normal hit or clustered mode
        # in normal hit G0 is 0 and 1 for calib mode, or G0 is 2 for clustered mode 
        self.operationMode       = operationMode
        
        ##########################################################
        
        self.debug = False
        
        self.removeremoveOtherDataTypesONOFF = True
 
        self.readouts = readouts()
        
        self.warnedBM = False
        
        ##########################################################
        
        if self.kafkaStream is False:
            self.filePathAndFileName = filePathAndFileName
            
            checkIfFileExistInFolder(self.filePathAndFileName)
            
            temp2 = os.path.split(filePathAndFileName)
            fileName = temp2[1]
            
            self.fileSize   = os.path.getsize(self.filePathAndFileName) #bytes
            print(f"{fileName} is {self.fileSize/1000000:.4f} Mbytes")
            
            self.mainHeaderSize  = 42  #bytes only if pcap file otherise from kafka this is 0 
            
        else:    
            
            self.stepsForProgress = 1
            self.mainHeaderSize   = 0
    
        ##########################################################
        
        self.readoutsPerPacket   = 447 #packets NOT USED here and dinamically recalcualted in extractfrombytes but used as a default to init kafka 
        self.ESSheaderSize       = None  # 30 bytes if version is 0  or 32 bytes if version is 1   
        self.headerSize          = None  # self.mainHeaderSize+self.ESSheaderSize #bytes  (72 if mainHeaderSize = 42)
        self.singleReadoutSize   = 20  # bytes, dinamically recalcualted in extractfrombytes but used as a default to init kafka 
 
        self.ROEtype = None
    
       ##########################################################
        
        self.counterPackets           = 0
        self.counterCandidatePackets  = 0
        self.counterValidESSpackets   = 0
        self.counterNonESSpackets     = 0
        self.counterEmptyESSpackets   = 0
        self.totalReadoutCount        = 0  
        self.overallDataIndex         = 0 
        self.preallocLength           = 0   
        
        # self.flagSupported = True
        
        self.data = np.zeros((self.preallocLength,20), dtype='int64')
        
        ##########################################################

        # maps.checkBMsettings(self.MONhw,  self.MONconn, self.MONring)
   
        
    def calculateHeaderSize(self):
        self.headerSize  = self.mainHeaderSize+self.ESSheaderSize #bytes  (72 if mainHeaderSize = 42 and 74 if version 1)
        
    def extractFWversion(self,packetData,indexESS):
        version = int.from_bytes(packetData[indexESS-1:indexESS], byteorder='little') # bytes 
        return version

    def extractInstrID(self,packetData,indexESS):
        ID = int.from_bytes(packetData[indexESS+3:indexESS+4], byteorder='little') # 
        return ID
    
    def checkFWversionSetHeaders(self,packetsFWversion):
        
        print('\nchecking RMM firmware version ',end='')
        try:
            if np.any(packetsFWversion != packetsFWversion[0]):
                print('\n \033[1;31mWARNING ---> found different Firmware Versions in packets, use version 0 as default, data might be corrupted for other versions\033[1;37m')
                time.sleep(1)
            else:
                print('--> version: {}'.format(packetsFWversion[0]))   
        except: 
             print('--> unable to verify version.')   
             pass
        
        self.ESSheaderSize = 30  # 30 bytes if version is 0  or 32 bytes if version is 1   
        self.calculateHeaderSize()
        
        # packetsFWversion = np.atleast_1d(packetsFWversion)
        try:
            if packetsFWversion[0] == 0:
                    self.ESSheaderSize = 30  # 30 bytes if version is 0  or 32 bytes if version is 1   
                    self.calculateHeaderSize()  
                    
            elif packetsFWversion[0] >= 1:
                    self.ESSheaderSize = 32  # 30 bytes if version is 0  or 32 bytes if version is >= 1    
                    self.calculateHeaderSize()
        except:
            pass
   
        
    def checkTimeSrc(self, timeSourceBytes):
 
            # NOTE for now upper 4 bits unused 
            
            # print('timeSrc: {} {} {}'.format(timeSourceBytes,hex(timeSourceBytes),bin(timeSourceBytes)  ))
          
            # timeSourceBytes = int.from_bytes(timeSourceBytes, byteorder='little') # bytes 
          
          bit0 = (timeSourceBytes & 0x1) 
          bit1 = (timeSourceBytes & 0x2) >> 1
          bit2 = (timeSourceBytes & 0x4) >> 2
          bit3 = (timeSourceBytes & 0x8) >> 3

          if bit0 == 0:
              src = 'MRF timestamp'
          elif bit0 == 1:
              src = 'local timestamp'
          
          if bit1 == 0:
              iss = 'MRF sync'
          elif bit1 == 1:
              iss = 'local sync'
          
          if bit2 == 0:
              sm = 'internal'
          elif bit2 == 1:
              sm = 'external (TTL)'
              
          if bit3 == 0:
              status = 'OK'
          elif bit3 == 1:
              status = 'Error'

          print("checking time source --> source: {}, internal sync source: {}, sync method: {}, status: {}".format(src,iss,sm,status))
          # return tsrc
      
        
    def extractIP(self, packetData, indexESS):
        
                IPBytes = packetData[indexESS-2-8-20:indexESS-2]

                IPlen   = 20
                # portLen = 8
                
                indexIPstart = IPlen-8

                IPSourcebytes  = int.from_bytes(IPBytes[indexIPstart:indexIPstart+4], byteorder='big') 
                IPDestbytes    = int.from_bytes(IPBytes[indexIPstart+4:indexIPstart+8], byteorder='big') 
                
                
                IPSource = ipaddress.IPv4Address(IPSourcebytes)
                IPDest   = ipaddress.IPv4Address(IPDestbytes)
                
                indexUDPstart = IPlen
                   
                portSource  = int.from_bytes(IPBytes[indexUDPstart:indexUDPstart+2], byteorder='big') 
                portDest    = int.from_bytes(IPBytes[indexUDPstart+2:indexUDPstart+4], byteorder='big') 
                
                return IPSource, portSource, IPDest, portDest
       
    def checkIP(self,packetsIPs):
    
            print("checking IPs:ports ...")
            
            # 1. Convert the object array to a string array so NumPy can process it
            # this turns IPv4Address objects into '192.168.1.200' strings
            packets_str = packetsIPs.astype(str)
            
            # 2. Now unique with axis=0 will work!
            unique_conns, counts = np.unique(packets_str, axis=0, return_counts=True)
            
            # 3. Loop through and print
            for kk in range(len(unique_conns)):
                conn = unique_conns[kk]
                num  = counts[kk]
                # conn[0] is SrcIP, conn[1] is SrcPort, etc.
                print(f"\tConnection {kk} found ({num} pkts) --> "
                      f"Source: {conn[0]}:{conn[1]} | Dest: {conn[2]}:{conn[3]}")
                
    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))

    def allocateMemory(self, pcapLoadingMethod='allocate'):  
        
        # NOTE IMPORTANT: when load method is quick the check of FW version 
        # is done only on the first packet and not all of them !!!! 
        
        self.pcapLoadingMethod = pcapLoadingMethod
        
        if (self.pcapLoadingMethod != 'allocate') and (self.pcapLoadingMethod != 'quick') :
            print('\033[1;33mWARNING: Wrong data loading option: select either quick or allocate --> setting it to allocate method!\033[1;37m')
            self.pcapLoadingMethod = 'allocate'
            
        if self.pcapLoadingMethod == 'allocate':
            endCounter = np.inf
            print('pcap loading method: allocate')
        elif self.pcapLoadingMethod == 'quick':
            endCounter = 2
            print('pcap loading method: quick \033[1;33m---> WARNING: when load method is quick the check of FW version and IP is done only on the first packet and not all of them.\033[1;37m')    

        
        print('allocating memory...',end='')
        
        ff = open(self.filePathAndFileName, 'rb')
        scanner = pg.FileScanner(ff)
        
        packetsSizes       = np.zeros((0),dtype='int64')
        packetsFWversion   = np.zeros((0),dtype='int64')
        packetsIPs         = np.zeros((0,4),dtype='int64')
        # packetsInstrID     = np.zeros((0),dtype='int64')
        
        counter = 0
        
        try:
            for block in scanner:
                
                if counter <= endCounter:
                
                    counter+=1
        
                    if counter == 4 or np.mod(counter,5000) == 0:
                        print('.',end='')
            
                    self.counterPackets += 1
                    self.dprint("packet {}".format(self.counterPackets))
            
                    try:
                        packetSize = block.packet_len
                        self.dprint("packetSize {} bytes".format(packetSize))
                                                
                        packetData = block.packet_data
                        
                        indexESS   = packetData.find(b'ESS')
     
                        if indexESS != -1:
                            
                           FWversionTemp = self.extractFWversion(packetData, indexESS)
                           IPsTemp       = self.extractIP(packetData, indexESS)
                           # instrIDtemp   = self.extractInstrID(packetData, indexESS)
    
                    except:
                        self.dprint('--> other packet found No. {}'.format(self.counterPackets-self.counterCandidatePackets))
                    else:
                        self.counterCandidatePackets += 1
    
                        packetsSizes     = np.append(packetsSizes,packetSize)
                        try:
                            packetsFWversion  = np.append(packetsFWversion,FWversionTemp)
                            # packetsInstrID    = np.append(packetsInstrID,instrIDtemp)
                            packetsIPs  = np.append(packetsIPs,[IPsTemp], axis=0)
                        except:
                            # print('this data does not contain FW version')
                            pass
                            
        except Exception as e:
            print(f"\n\033[1;31mERROR: {e} ---> probably data is being created and file not closed -> exiting. \033[1;37m")
            time.sleep(2)
            sys.exit()  
        
      
        self.dprint('counterPackets {}, counterCandidatePackets {}'.format(self.counterPackets,self.counterCandidatePackets))    
        
        self.checkFWversionSetHeaders(packetsFWversion)

        self.checkTimeSrc(packetData[indexESS+7])
        
        # print(packetsIPs)
        
        if self.kafkaStream is False:
             self.checkIP(packetsIPs)


        if self.debug:
            overallSize = np.sum(packetsSizes)
            self.dprint('overallSize {} bytes'.format(overallSize))

        numOfReadoutsInPackets = (packetsSizes - self.headerSize)/self.singleReadoutSize  #in principle this is 446 for every packet
        
        
        if self.pcapLoadingMethod == 'allocate':
            # #  if negative there was a non ESS packetso length < 72bytes 
            # #  and if much bigger wee anyhowallocate morethan needed and remove zeros aftyerwards at the end 
            numOfReadoutsTotal = np.sum(numOfReadoutsInPackets[ numOfReadoutsInPackets >= 0])
        
        elif self.pcapLoadingMethod == 'quick':
            numOfReadoutsTotal  = self.fileSize/self.singleReadoutSize
            # need to initialize the counters even if the are quite off, but it gives an upper limit then will be overwritten after read  
            self.counterCandidatePackets = int(round(numOfReadoutsTotal))
            self.counterPackets          = self.counterCandidatePackets
     
        self.preallocLength = int(round(numOfReadoutsTotal))
        self.dprint('preallocLength {}'.format(self.preallocLength))
        
        ff.close()
                
        
    def read(self):   
        
        print('\n',end='')
        
        outOfPositionCounter = 0
        ICMPcounter          = 0 
        otherCounter         = 0 

        
        self.data                      = np.zeros((self.preallocLength,20), dtype='int64') 
        self.readouts.heartbeats       = np.zeros((self.counterCandidatePackets), dtype='int64')
        self.readouts.instrID          = -1*np.ones((self.counterCandidatePackets), dtype='int64') 
        
        ff = open(self.filePathAndFileName, 'rb')
        scanner = pg.FileScanner(ff)
        
        self.overallDataIndex = 0 
        
        self.stepsForProgress = int(self.counterCandidatePackets/5)+1  # 4 means 25%, 50%, 75% and 100%
        
        indexPackets = 0 
        
        for block in scanner:
            
            try:
                
                packetLength = block.packet_len
                packetData   = block.packet_data
                   
                
                # ### to write file from pcapr 
                # cont =+1 
                
                # if cont == 1 :
                #     # print(packetData)
                #     with open('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/lib/outputBin2', 'wb') as f: 
                #         f.write(packetData)
                        
                # else:
                #     with open('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/lib/outputBin2', 'ab') as f: 
                #         f.write(packetData) 
                
                
            except:
                self.dprint('--> other packet found')
                
            else:
                outOfPositionCounterTemp, ICMPcounterTemp, otherCounterTemp = self.extractFromBytes(packetData,packetLength,indexPackets,debugMode = self.debug)
                indexPackets += 1
                
                outOfPositionCounter = outOfPositionCounter + outOfPositionCounterTemp
                ICMPcounter          = ICMPcounter          + ICMPcounterTemp
                otherCounter         = otherCounter         + otherCounterTemp
         
        print('[100%]') 

        self.printDataWarnings(outOfPositionCounter,ICMPcounter,otherCounter)
        
        self.dprint('\n All Packets {}, Candidates for Data {} --> Valid ESS {} (empty {}), NonESS  {} '.format(self.counterPackets , self.counterCandidatePackets,self.counterValidESSpackets ,self.counterEmptyESSpackets,self.counterNonESSpackets))
             
        #######################################################       
             
        # here I remove  the rows that have been preallocated but no filled in case there were some packets big but no ESS
        if self.preallocLength > self.totalReadoutCount:
            
            datanew = np.delete(self.data,np.arange(self.totalReadoutCount,self.preallocLength),axis=0)
            print('removing extra allocated length not used ...',end='') 
            
        elif self.preallocLength < self.totalReadoutCount:
            print('something wrong with the preallocation: allocated length {}, total readouts {}'.format(self.preallocLength,self.totalReadoutCount))
            time.sleep(2)
            sys.exit()
       
        elif self.preallocLength == self.totalReadoutCount:
            
            datanew = self.data
        
        cz = checkIfDataHasZeros(datanew)
        datanew = cz.dataOUT
        
        self.readouts.transformInReadouts(datanew)
        
        # self.readouts.heartbeats = self.heartbeats
        # print(self.readouts.heartbeats)
        
        # self.readouts.removeNonESSpacketsHeartbeats()
        
        # print(self.readouts.heartbeats)
        
        ############
        
        self.checkTimeSettings()
          
        self.timeAdjustedWithResolution()
        
        ############

        
        # we overwrite the excess estimate of packets by the right amount 
        if self.pcapLoadingMethod == 'quick':
           self.counterCandidatePackets = self.counterValidESSpackets  +  self.counterNonESSpackets  
           self.counterPackets          = self.counterCandidatePackets 
                
        
        # print('\ndata loaded - found {} readouts - Packets: all {} (candidates {}) --> valid ESS {} (of which empty {}), nonESS {}'.format(self.totalReadoutCount, self.counterPackets,self.counterCandidatePackets,self.counterValidESSpackets ,self.counterEmptyESSpackets,self.counterNonESSpackets))    

        print('\ndata loaded - found {} readouts - Packets: all {} --> valid ESS {} (of which empty {}), nonESS {}'.format(self.totalReadoutCount, self.counterCandidatePackets,self.counterValidESSpackets ,self.counterEmptyESSpackets,self.counterNonESSpackets))    

        ############
        
        self.removeOtherDataTypes(removeONOFF=self.removeremoveOtherDataTypesONOFF)
        
        ff.close()
        
        self.readouts.calculateUniqueInstrIDs()
        for ids in self.readouts.instrIDUnique:
                print('\n---> ', end='')
                checkInstrumentID().printInfoDataStream(ids)
        print('\n')
        
        
    def printDataWarnings(self,outOfPositionCounter,ICMPcounter,otherCounter):
        
        if outOfPositionCounter != 0 :
           #   give a warning if not 72 or 74,  check that ESS cookie is always in the same place-> warning at the end of function 
           print(f"\n\033[1;33mWARNING ---> ESS cookie was found {outOfPositionCounter} times not in position! Data does not start at byte 72 or 74 or 42 or 44! ... \033[1;37m")
           
           if ICMPcounter ==  outOfPositionCounter:
              # this is the case where the packet is sent instead of UDP but as a ping from RMM ICMP message -> need to skip this package 
                print(f" \033[1;33m    ... ---> but it was an ICMP packet {ICMPcounter} times -> skipping those packets. \033[1;37m")
           else:
                print(f" \033[1;31m    ... ---> found {ICMPcounter} ICMP packets that can be skipped and {otherCounter} times not an ICMP packet, BUT DATA MIGHT BE CORRUPTED. \033[1;37m")

   
    def checkTimeSettings(self):
        
        if self.operationMode == 'normal' or self.operationMode == 'clustered':
            
            pass

        else:
            
            print('\n\t\033[1;31mERROR: Operation mode (found {}) not set either to normal or clustered ---> Exiting ... \n\033[1;37m'.format(self.operationMode),end='') 
            time.sleep(2)
            sys.exit()  
            
        if self.timeResolutionType == 'fine' or self.timeResolutionType == 'coarse':
                
            pass

        else:
                
            print('\n\t\033[1;31mERROR: Time resolution (found {}) not set either to fine or coarse ---> Exiting ... \n\033[1;37m'.format(self.operationMode),end='') 
            time.sleep(2)
            sys.exit()      
        
    def timeAdjustedWithResolution(self):

        # self.readouts.calculateTimeStamp(self.NSperClockTick)
        
        if self.ROEtype == 'VMM':

            if self.operationMode == 'normal':
                if self.timeResolutionType == 'fine':
                    self.readouts.calculateTimeStampWithTDC(self.NSperClockTick)
                elif self.timeResolutionType == 'coarse':
                    self.readouts.timeStamp = self.readouts.timeCoarse       
            elif self.operationMode == 'clustered': 
                # tere is no time fine in clustered mode is already one sigle time 
                        self.readouts.timeStamp = self.readouts.timeCoarse
                        
        else:     
             
             self.readouts.timeStamp = self.readouts.timeCoarse


    def removeOtherDataTypes(self,removeONOFF=True):
        
        flag = self.readouts.checkIfCalibrationMode() 
        if flag is True: 
           if removeONOFF == True:
              removedNum = self.readouts.removeCalibrationData()
              print('removed {} calibration readouts --> readouts left {}'.format(removedNum,self.totalReadoutCount-removedNum)) 
              self.totalReadoutCount = self.totalReadoutCount-removedNum
              

        if self.operationMode == 'normal':
 
            flag = self.readouts.checkIfClusteredMode()
            if flag is True: 
               if removeONOFF == True:
                  removedNum = self.readouts.removeClusteredData()
                  print('removed {} clustered readouts --> readouts left {}'.format(removedNum,self.totalReadoutCount-removedNum))
                  self.totalReadoutCount = self.totalReadoutCount-removedNum
                
        elif self.operationMode == 'clustered': 
                 
              flag = self.readouts.checkIfNormalHitMode()
              if flag is True: 
                 if removeONOFF == True:
                    removedNum = self.readouts.removeNormalHitData()
                    print('removed {} normal readouts --> readouts left {}'.format(removedNum,self.totalReadoutCount-removedNum))
                    self.totalReadoutCount = self.totalReadoutCount-removedNum
      
        
    def extractPulseTime(self,packetData,indexESS):
        
        ESSlength  = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes 
        
        PulseThigh = int.from_bytes(packetData[indexESS+8:indexESS+12], byteorder='little')*1000000000
        PulseTlow  = int.from_bytes(packetData[indexESS+12:indexESS+16], byteorder='little')*self.NSperClockTick 
        PrevPThigh = int.from_bytes(packetData[indexESS+16:indexESS+20], byteorder='little')*1000000000
        PrevPTlow  = int.from_bytes(packetData[indexESS+20:indexESS+24], byteorder='little')*self.NSperClockTick 
        
        #  IMPORTANT if you do int round after sum is off, needs to be done before then sum hi and low
        PulseThighR = int(round(PulseThigh))
        PulseTlowR  = int(round(PulseTlow))
        PrevPThighR = int(round(PrevPThigh))
        PrevPTlowR  = int(round(PrevPTlow))
        
        PulseT = PulseThighR + PulseTlowR
        PrevPT = PrevPThighR + PrevPTlowR
        
        return PulseT, PrevPT, ESSlength
        
        
    def extractFromBytes(self,packetData,packetLength,indexPackets,debugMode=False):
        
        # print('dsfxafaefxea')
        # print(self.operationMode)
        
        # ICMP packet has ESS data in it but must be discarded 
        # the ICMP protocal adds 28 bytes 
        ICMPbyteExtraLength  = 28 
        ICMPflag             = False 
        ICMPcounter          = 0
        outOfPositionCounter = 0
        otherCounter         = 0
        
        indexESS = packetData.find(b'ESS') # index of(cookie) ESS = 0x 45 53 53 it is always 44 with pcap 
        
        self.dprint('index where ESS word starts {}'.format(indexESS))
        #  it should be always 44 = 42+2
     
        if indexESS == -1:
           # this happens if it not an ESS packet 
           self.counterNonESSpackets += 1
           
        else: 
            # there is an ESS packet but i can still be empty, i.e. 72 bytes only
           self.counterValidESSpackets += 1
           
           if self.counterValidESSpackets == 1:
                   
               print('loading ... [0%]',end=' ')    
         
               
           # print('---')
           # print('indexESS '+str(indexESS))    
           # print('header '+str(self.ESSheaderSize))
           # print('full header '+str(self.headerSize))
    
           indexDataStart = self.ESSheaderSize +( indexESS - 2 )   # index after (cookie) ESS = 0x 45 53 53 where data starts (eg 44+30-2=72 or 44+32-2=74 )

           # print('data starts at: '+str(indexDataStart))

           #   give a warning if not 72 or 74,  check that ESS cookie is always in the same place-> warning at the end of function 
           if indexDataStart != self.headerSize:
               outOfPositionCounter += 1 
               if (indexDataStart == self.headerSize + ICMPbyteExtraLength):
                   # this is the case where the packet is sent instead of UDP but as a ping from RMM ICMP message -> need to skip this package 
                  ICMPcounter += 1
                  ICMPflag     = True
               else:
                   otherCounter += 1 
           
           # if the packet is a good packet then...
           if ICMPflag == False:
               # dinamically change readoutsize 20 or 24 bytes 
               instrID = self.extractInstrID(packetData,indexESS)
               self.singleReadoutSize, self.ROEtype = checkInstrumentID().getInfoFromID(instrID)   
               # print(self.ROEtype)
               
               readoutsInPacket = (packetLength - indexDataStart) / self.singleReadoutSize
               # or alternatively
               # readoutsInPacket = (ESSlength - self.ESSheaderSize) / self.singleReadoutSize
               
               if (packetLength - indexDataStart) == 0: #empty packet 72 bytes 
                   
                   self.counterEmptyESSpackets += 1
                   self.dprint('empty packet No. {}'.format(self.counterEmptyESSpackets))
                   
                   PulseT, _, _  = self.extractPulseTime(packetData,indexESS)
    
               else:
                   
                   if readoutsInPacket.is_integer() is not True:
                       print('\n\033[1;31mWARNING ---> something wrong with data bytes dimensions \033[1;37m')
                       time.sleep(1)
                   else:
                       
                       # only read header if there is no emplty packet
                       PulseT, PrevPT, ESSlength  = self.extractPulseTime(packetData,indexESS)
                     
                       # ESSlength is only 30 if the packet is an ESS packet but empty= 72-42 =30
                       self.dprint('ESS packet length {} bytes, packetLength {} bytes, readouts in packet {}'.format(ESSlength, packetLength,readoutsInPacket))  
                   
                       readoutsInPacket = int(readoutsInPacket)
                       self.totalReadoutCount += readoutsInPacket
                       
                       for currentReadout in range(readoutsInPacket):
                           
                       # for currentReadout in range(1):
                           
                           self.overallDataIndex += 1 
                       
                           indexStart = indexDataStart + self.singleReadoutSize * currentReadout
                           indexStop  = indexDataStart + self.singleReadoutSize * (currentReadout + 1)
               
                           if self.operationMode == 'normal':  # expected G0 is 0 or 1 
                               vmm3 = VMM3A(packetData[indexStart:indexStop], self.NSperClockTick)
                               # vmm3.G0 = 2
                           elif self.operationMode == 'clustered':  # expected G0 is 2
                               vmm3 = VMM3Aclustered(packetData[indexStart:indexStop], self.NSperClockTick)
                               # vmm3.G0 = 2
                           else:
                               print('\n\t\033[1;31mERROR: Operation mode ({} found) is not one of these: normal or clustered mode! --> Exiting!\033[1;37m'.format(self.operationMode),end='') 
                               time.sleep(2)
                               sys.exit()
                           
                           index = self.overallDataIndex-1   
   
                           # ring 11 reserved for MON
                           if vmm3.Ring < 11:
                               
                               self.data[index, 19] = instrID
                               
                               if self.ROEtype == 'VMM':
                               
                                    self.data[index, 0] = vmm3.Ring
                                    self.data[index, 1] = vmm3.Fen
                                    self.data[index, 2] = vmm3.VMM
                                    self.data[index, 3] = vmm3.hybrid
                                    self.data[index, 4] = vmm3.ASIC
                                    self.data[index, 5] = vmm3.Channel
                                    self.data[index, 6] = vmm3.ADC
                                    self.data[index, 7] = vmm3.BC
                                    self.data[index, 8] = vmm3.OTh
                                    self.data[index, 9] = vmm3.TDC
                                    self.data[index, 10] = vmm3.GEO
                                    self.data[index, 11] = vmm3.timeCoarse
                                    self.data[index, 12] = PulseT
                                    self.data[index, 13] = PrevPT
                                    self.data[index, 14] = vmm3.G0  # if 1 is calibration
                                    self.data[index, 15] = vmm3.Channel1
                                    self.data[index, 16] = vmm3.ADC1
                                    self.data[index, 17] = vmm3.mult0
                                    self.data[index, 18] = vmm3.mult1
                                    
                                    
                               elif  self.ROEtype == 'R5560':
                                   
                                    R5560data = R5560(packetData[indexStart:indexStop], self.NSperClockTick)
                                      
                                    self.data[index, 0] = R5560data.Ring
                                    self.data[index, 1] = R5560data.Fen
                                    self.data[index, 2] = 0 #VMM for R5560 always 0
                                    self.data[index, 3] = 0 #hybrid for R5560 always 0
                                    self.data[index, 4] = 0 #ASIC for R5560 always 0
                                    self.data[index, 5] = R5560data.tube   # tube = channel 
                                    self.data[index, 6] = R5560data.ampA   # ADC = AMP A
                                    self.data[index, 7] = R5560data.counter1 #BC == counter1 
                                    self.data[index, 8] = 1 #OTh for R5560 always 1
                                    self.data[index, 9] = 0 #TDC for R5560 always 0
                                    self.data[index, 10] = R5560data.counter2  #GEO == counter2 
                                    self.data[index, 11] = R5560data.timeCoarse
                                    self.data[index, 12] = PulseT
                                    self.data[index, 13] = PrevPT
                                    self.data[index, 14] = 0  # G0 if 1 is calibration so always 0 in R5560
                                    self.data[index, 15] = 0  # ch1 for R5560 always 0
                                    self.data[index, 16] = R5560data.ampB     # ADC1 = AMP B
                                    self.data[index, 17] = 1  #mult0 for R5560 always 1
                                    self.data[index, 18] = 1  #mult1 for R5560 always 1
                                 
                               elif self.ROEtype == 'SKADI':
                                   
                                   SKADIdata = SKADI(packetData[indexStart:indexStop], self.NSperClockTick)
                                     
                                   # SKADIdata.ASICchannel = 0
                                   
                                   self.data[index, 0] = SKADIdata.Ring
                                   self.data[index, 1] = SKADIdata.Fen
                                   self.data[index, 2] = SKADIdata.IP     #VMM 
                                   self.data[index, 3] = SKADIdata.sysID  #hybrid
                                   self.data[index, 4] = SKADIdata.ASICchannel #ASIC 
                                   self.data[index, 5] = SKADIdata.column      # channel 
                                   self.data[index, 6] = SKADIdata.ADC      # ADC 
                                   self.data[index, 7] = SKADIdata.flags # BC 
                                   self.data[index, 8] = 1 #OTh for SKADI always 1
                                   self.data[index, 9] = 0 #TDC for SKADI always 0
                                   self.data[index, 10] = SKADIdata.OpMod  #GEO 
                                   self.data[index, 11] = SKADIdata.timeCoarse
                                   self.data[index, 12] = PulseT
                                   self.data[index, 13] = PrevPT
                                   self.data[index, 14] = 0  # G0 if 1 is calibration so always 0 
                                   self.data[index, 15] = SKADIdata.row      # ch1 
                                   self.data[index, 16] = 0   # ADC1 is 0 for SKADI 
                                   self.data[index, 17] = 1  #mult0 for SKADI always 1
                                   self.data[index, 18] = 1  #mult1 for SKADI always 1
 
                               elif  self.ROEtype == 'BM':
                                   
                                    if self.warnedBM == False : 
                                        print('\n \033[1;33mWARNING ---> BM data found in ring < 11, treated as a detector and HW generic (not IBM)! \033[1;37m')
                                        self.warnedBM = True

                                    # this will read the BM data it comes from rings below 11 as a detector with hybrid 0
            
                                    mondata = MONdata(packetData[indexStart:indexStop], self.NSperClockTick)

                                    self.data[index, 0] = mondata.Ring
                                    self.data[index, 1] = mondata.Fen
                                    self.data[index, 2] = 0   # VMM for MON always 0
                                    self.data[index, 3] = 0   # hybrid for MON always 0
                                    self.data[index, 4] = 0   # ASIC for MON always 0
                                    self.data[index, 5] = mondata.Channel
                                    self.data[index, 6] = mondata.ADC
                                    self.data[index, 7] = mondata.posX
                                    self.data[index, 8] = mondata.posY
                                    self.data[index, 9] = 0     # TDC for MON always 0
                                    self.data[index, 10] = mondata.Type
                                    self.data[index, 11] = mondata.timeCoarse
                                    self.data[index, 12] = PulseT
                                    self.data[index, 13] = PrevPT
                                    self.data[index, 14] = 0  # if 1 is calibration
                                    self.data[index, 15] = -1
                                    self.data[index, 16] = -1
                                    self.data[index, 17] = -1
                                    self.data[index, 18] = -1
                                   
                               else:
                                        
                                     print('\n\t\033[1;31mERROR: Data format not supported ---> Exiting ... \n\033[1;37m',end='') 
                                     # time.sleep(2)
                                     # sys.exit() 
                           
                           
                        
                           # overwrite if MONITOR 
                           # is_lemo_mode = (self.MONconn == 'LEMO' and vmm3.Ring >= 11)
                           # is_ring_mode = (self.MONconn == 'RING' and vmm3.Ring == 11 and vmm3.Ring == self.MONring)

                           is_lemo_mode = (self.MONconn == 'LEMO' and vmm3.Ring >= 11)
                           is_ring_mode = (self.MONconn == 'RING' and vmm3.Ring == self.MONring)

                           if is_lemo_mode or is_ring_mode:
 
                               
                               self.data[index, 19] = instrID
                               
                               if self.MONhw == 'GENERIC':
                               
                                   mondata = MONdata(packetData[indexStart:indexStop], self.NSperClockTick)
                                  
                                   self.data[index, 0] = mondata.Ring
                                   self.data[index, 1] = mondata.Fen
                                   self.data[index, 2] = 0   # VMM for MON always 0
                                   self.data[index, 3] = 0   # hybrid for MON always 0
                                   self.data[index, 4] = 0   # ASIC for MON always 0
                                   self.data[index, 5] = mondata.Channel
                                   self.data[index, 6] = mondata.ADC
                                   self.data[index, 7] = mondata.posX
                                   self.data[index, 8] = mondata.posY
                                   self.data[index, 9] = 0     # TDC for MON always 0
                                   self.data[index, 10] = mondata.Type
                                   self.data[index, 11] = mondata.timeCoarse
                                   self.data[index, 12] = PulseT
                                   self.data[index, 13] = PrevPT
                                   self.data[index, 14] = 0  # if 1 is calibration
                                   self.data[index, 15] = -1
                                   self.data[index, 16] = -1
                                   self.data[index, 17] = -1
                                   self.data[index, 18] = -1
                                
                               elif  self.MONhw == 'IBM':  
                                   
                                   mondata = IBM_MONdata(packetData[indexStart:indexStop], self.NSperClockTick)
                                  
                                   self.data[index, 0] = mondata.Ring
                                   self.data[index, 1] = mondata.Fen
                                   self.data[index, 2] = 0   # VMM for MON always 0
                                   self.data[index, 3] = 0   # hybrid for MON always 0
                                   self.data[index, 4] = 0   # ASIC for MON always 0
                                   self.data[index, 5] = mondata.Channel
                                   self.data[index, 6] = mondata.ADC
                                   self.data[index, 7] = mondata.MCAsum
                                   self.data[index, 8] = 0
                                   self.data[index, 9] = 0     # TDC for MON always 0
                                   self.data[index, 10] = mondata.Type
                                   self.data[index, 11] = mondata.timeCoarse
                                   self.data[index, 12] = PulseT
                                   self.data[index, 13] = PrevPT
                                   self.data[index, 14] = 0  # if 1 is calibration
                                   self.data[index, 15] = -1
                                   self.data[index, 16] = -1
                                   self.data[index, 17] = -1
                                   self.data[index, 18] = -1
                                   
                               else:
                                    print('\n\t\033[1;31mERROR: BM Data format not supported ---> Exiting ... \n\033[1;37m',end='') 
                            
  
                        # valid for normal mode 
                           if debugMode is True:
                               print(" \t Packet: {} ({} bytes), Readout: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time Coarse {} ns, BC {}, OverTh {}, ADC {}, TDC {}, GO {} " \
                                           .format(self.counterValidESSpackets,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeCoarse,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.G0))
    
           
                 
                         ###########
                         
                         

               try:            
                   self.readouts.heartbeats[indexPackets]   = PulseT
                   self.readouts.instrID[indexPackets]      = instrID
                   
               except:
                   print('\033[1;31m        ---> probably rings are offline or data is corrupted \033[1;37m')
                   time.sleep(2)
                   sys.exit()
                     
            
            
           if np.mod(self.counterValidESSpackets,self.stepsForProgress) == 0:
                percents = int(round(100.0 * self.counterValidESSpackets / float(self.counterCandidatePackets), 1))
                print('['+format(percents,'01d') + '%]',end=' ')  
               
            # pb.progressBar(self.counterValidESSpackets,self.counterCandidatePackets)
           
        return outOfPositionCounter, ICMPcounter, otherCounter


            
        
class checkIfDataHasZeros():
     def __init__(self, data):
         
         self.dataIN = data
         
         self.OriginalLength = np.shape(self.dataIN)[0]
         
         datasum  = np.sum(data,axis=1)
         indexesIsNotZero  = np.argwhere(datasum>0)
        
         # self.trueLen  = np.shape(indexesIsNotZero[:,0]>0)[0]
    
         self.dataOUT = self.dataIN[indexesIsNotZero[:,0],:]
         self.NewLength = np.shape(self.dataOUT)[0]
         
         if self.NewLength  != self.OriginalLength :
             
            self.flag = True
            
            print('---> removing zeros left in data')
            
         else :
  
             self.flag = False
             


###############################################################################
###############################################################################

if __name__ == '__main__':


   tProfilingStart = time.time()



   confFile  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'
   fileName  = "MIRACLES24.json"
   fileName  = "AMOR.json"
    # fileName  = "MGEMMA.json"
   # fileName  = "MIRACLES2bis.json"
   
   # fileName  = "CSPEC.json"

   config = maps.read_json_config(confFile+fileName)
    
   parameters  = para.parameters(confFile+fileName)
   parameters.loadConfigAndUpdate(config)
    
    
   filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   file = 'miracles_trig2.pcapng'
   file = 'ESSmask2023_1000pkts.pcapng'
   # file = 'ESSmask2023.pcapng'
   
   file = 'sampleData_NormalMode.pcapng'
   
   file = 'sampleData_ClusteredMode.pcapng'
   
   # file = 'testData.pcapng'
   
   # file = 'miracles_source_on_left_red.pcapng'

   # file = 'CSPEC1.pcapng'


   filePathAndFileName = filePath+file
   
   
   typeOfLoading = 'allocate'
   # typeOfLoading = 'quick'
   
   
   temp = config.DETparameters.operationMode
   
   
   pcap = pcapng_reader(filePathAndFileName,NSperClockTick=11.356860963629653, MONhw=config.MONmap.hardwareType, MONconn=config.MONmap.connectionType, MONring=11, timeResolutionType='coarse', sortByTimeStampsONOFF=False, operationMode=temp,pcapLoadingMethod=typeOfLoading)

   readouts = pcap.readouts
   
   # pcap = pcapng_reader_PreAlloc(filePath,NSperClockTick)
   # pcap.allocateMemory()
   # pcap.read()
   
   # pcap = pcapng_reader(filePath, NSperClockTick, timeResolutionType = 'fine', sortByTimeStampsONOFF = False )

   
   # readouts = pcap.readouts 
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   
   heartbeats1 = readouts.heartbeats
   heartbeats2 = readouts.removeNonESSpacketsHeartbeats(readouts.heartbeats)
   
   readouts.checkChopperFreq()
   
   readouts.checkInvalidToFsInReadouts()
   
   # print(readouts.instrIDUnique)
   
   checkInstrumentID().checkValidDataStream(readouts.instrIDUnique)
   
   checkInstrumentID().matchDataStreamWithConfig(config.DETparameters.instrument, config.DETparameters.type, readouts.instrIDUnique)
   
   
   # parameters.config.MONmap.hardwareType = 'GENERIC'
    
   checkBMtype(readouts.instrIDpkt, readouts.GEO, parameters.config.MONmap.hardwareType)
   
   
   # pint =  readouts.packetsInstrID

   # checkIfDataIsSupported(pcap.flagSupported)
   
   
   # readouts.ROEtypeUnique = np.append(readouts.ROEtypeUnique, 'R5560')
   
   
   # instrType1 = np.zeros((4), dtype='U10') 
   # instrType1[0] = 'R5560'
   # instrType1[1] = 'VMeM'
   # instrType1[2] = 'BM'
   # instrType1[3] = 'BMe'
   
   # readouts.instrTypeUnique =  instrType1
   
   
   
   # checkInstrumentID().checkMatchConfigWithInstrType(config.DETparameters.type, readouts.instrTypeUnique)
   
   
   
   
   tElapsedProfiling = time.time() - tProfilingStart
   print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 