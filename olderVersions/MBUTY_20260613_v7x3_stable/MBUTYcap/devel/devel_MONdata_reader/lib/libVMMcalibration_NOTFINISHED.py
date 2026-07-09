#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 24 11:05:36 2021

@author: francescopiscitelli
"""
import numpy as np
import json
import os

import sys

from lib import libMapping as maps
from lib import libReadPcapngVMM as pcapr

###############################################################################
###############################################################################

# NOTES for devel

# NOTES: in mapping already reading Hybrid Serial if needed and if present,
# here serial has to be loaded twice and do calib per asic 0 and 1.
#  load serial with get_cassID2RingFenHybrid(cassetteID)

###############################################################################
###############################################################################


class read_json_calib():
    def __init__(self, calibFile_PathAndFileName, config):
        
        temp =  os.path.split(calibFile_PathAndFileName)
            
        self.calibFilePath = temp[0]+'/'
        self.calibFileName = temp[1]
        
        self.calibFlag = True
        
        self.config = config
        
        try:
            self.ff   = open(calibFile_PathAndFileName,'r') 
            self.calib = json.load(self.ff)
        except:
            print('\n \033[1;31m---> Calibration File: ' + self.calibFileName + ' not found \033[1;37m')
            print(' ---> in folder: ' + self.calibFilePath + ' \n ---> calibration skipped.')
            self.calibFlag = False
        
        if self.calibFlag:
            
           self.print_calib()
  
    def __del__(self):
        try:
            self.ff.close()
        except:
            pass
        
    def print_calib(self):
        print('\033[1;36mCalibrating VMMs with file: {}\033[1;37m'.format(self.calibFileName))
        
    def calib1hybrid(self, cassetteID):
        
        # self.config.DETmap.cassettesMap
        
        self.config.get_cassID2RingFenHybrid(cassetteID)
        
        self.config.cassMap.RingID
        self.config.cassMap.FenID
        self.config.cassMap.hybridID
        self.config.cassMap.hybridSerial
        
    def calibMON(self):
        
        print(1)
        
        # self.config.MONmap.
        
        
###############################################################################
###############################################################################     

# class calibration():
      

class calibrateVMM():
    def __init__(self,readouts,calib):
        
        self.readouts = readouts
        self.calib    = calib
        
    def calibrateTimeStamp(self,timeResolution):
        
        time_offset = 1000
        
        time_slope  = 1
        
        TDC_calib = pcapr.VMM3A_convertCalibrate_TDCinSec(self.readouts.TDC,timeResolution,time_offset,time_slope).TDC_ns
          
        self.readouts.timeStamp  = self.readouts.timeCoarse  + TDC_calib
       
        
    def calibrateADC(self):  
        
        ADC_offset = 100
        
        ADC_slope = 1
        
        self.readouts.ADC = pcapr.VMM3A_calibrate_ADC(self.readouts.ADC,ADC_offset,ADC_slope).ADC_calibrated     
        
      
  
###############################################################################
###############################################################################

if __name__ == '__main__':

   filePathCalib   = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"TBCALIB.json"
   filePathConfig  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"MB300_AMOR_config2.json"
   pathData = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
   
   config = maps.read_json_config(filePathConfig)
   
   # filePath = path+'pcap_for_fra.pcapng'
   # filePath = path+'pcap_for_fra_ch2test.pcapng'
   # filePath = path+'pcap_for_fra_ch2test_take2.pcapng'
   # filePath = path+'pcap_for_fra_coinc.pcapng'
   # filePath = path+'freiatest.pcapng'
   # timeResolution = 11.356860963629653  #s per tick ESS for 88.0525 MHz
   # pcap = pcapr.pcapng_reader(filePath, timeResolution, sortByTimeStampsONOFF = True)
   # readouts = pcap.readouts 
   # readoutsArrayIn = readouts.concatenateReadoutsInArrayForDebug()
   
  

   calib = read_json_calib(filePathCalib, config)
   
   # cali = calibrateVMM(readouts,calib)
   # cali.calibrateADC()
   # cali.calibrateTimeStamp(timeResolution)
   
   # readoutsOut = cali.readouts
   # readoutsArrayOut = readoutsOut.concatenateReadoutsInArrayForDebug()
   
   # aa = readouts.ADC - readoutsOut.ADC
   
   # bb = readouts.timeStamp - readoutsOut.timeStamp
   
   # aa1 = readoutsArrayIn[0,8] - readoutsArrayOut[0,8]
   
   # bb1 = readoutsArrayIn[0,0] - readoutsArrayOut[0,0]