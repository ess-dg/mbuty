#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 09:19:11 2026

@author: francescopiscitelli
"""


import os
import numpy as np 

from MBUTY import MBUTYOrchestrator

import lib.parameters as para
# import lib.save_reduced_file as saveH5
from lib.colors import INFO, OK, WARN, ERR, RESET


###############################################################################
###############################################################################

class reduceFiles():
    
    def __init__(self,parameters):
        
        self.parameters = parameters
        
        # self.skippedFiles  = []
        # self.reducedFiles  = []
        
        self.skippedFiles  = 0
        self.reducedFiles  = 0
        
    def reduce(self,allTogether=False):

        if allTogether is True: 
       
            self._runAnalysis()
            
        else:
    
            if self.parameters.fileManagement.openMode == 'fileName':
                
                listOfFiles = self.parameters.fileManagement.fileName
                
                N = len(listOfFiles)
                    
                for ff, fname in enumerate(listOfFiles):
                    
                    print('\n\033[1;32m>>>>>>>>>>> Reading and reducing file {} of {} \n\033[1;37m'.format(ff+1,N)) 
                    
                    self.parameters.fileManagement.fileName = fname
                    self._runAnalysis()
                    
            elif self.parameters.fileManagement.openMode == 'sequence':  
                
    
                 self.parameters.fileManagement.parseFileSerialsList()
                 
                 serials = self.parameters.fileManagement.fileSerials

                 for ss , fnameSerial in enumerate(serials):
                     
                     print('\n\033[1;32m>>>>>>>>>>> Reading and reducing file {} of {} (serial {})\n\033[1;37m'.format(ss+1,len(serials),fnameSerial)) 
                     
                     self.parameters.fileManagement.fileSerials  = [fnameSerial]
                     self._runAnalysis()
                     
            elif self.parameters.fileManagement.openMode  == 'wholeFolder' :
                
                 print('\n\033[1;33mWARNING: wholeFolder mode, files reduced in a single file! \n\033[1;37m') 
                 self._runAnalysis()
            

            print(f"{OK}Succesfully reduced files: {self.reducedFiles}, skipped: {self.skippedFiles}{RESET}")


        
        
    def _runAnalysis(self):
    
            try:
                MBUTYOrchestrator(self.parameters ,  plottingOnOff = 'off' ).run_pipeline()
                
                # if self.parameters.fileManagement.openMode == 'fileName':
                #     self.reducedFiles.append(self.parameters.fileManagement.fileName)
                # elif self.parameters.fileManagement.openMode == 'sequence':  
                #     self.reducedFiles.append(self.parameters.fileManagement.fileSerials)
                self.reducedFiles +=1 
                
            except:
                print('\n\033[1;33mWARNING: File corrupted or not existing --> skipped! \n\033[1;37m') 
                
                self.skippedFiles += 1
                # if self.parameters.fileManagement.openMode == 'fileName':
                #     self.skippedFiles.append(self.parameters.fileManagement.fileName)
                # elif self.parameters.fileManagement.openMode == 'sequence':  
                #     self.skippedFiles.append(self.parameters.fileManagement.fileSerials)
                    
        
    
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    ###############################################################################
    ###############################################################################
    ### get current path and init parameters ###
    current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
    parameters  = para.parameters(current_dir)
    ###############################################################################
    ###############################################################################
    ### read json and create parameters for plotting and analisys ###

    configFileName  = "AMOR.json"
    # configFileName  = "clustered.json"
    
    
    # configFileName  = "MGtestVessels2col.json"
    
    # configFileName  = "MGEMMA_2det.json"
    
    # configFileName  = "test1h.json"

    # configFileName  = "ESTIA.json"
    
    # configFileName  = "MIRACLES24.json"
    # configFileName  = "CSPEC.json"
    # configFileName  = "MIRACLES2.json"

    # configFileName  = "ESTIA_sect0.json"
    # configFileName  = "ESTIA_sect1.json"
    # configFileName  = "ESTIA_sect2.json"
    # configFileName  = "ESTIA_sect3.json"
    # configFileName  = "ESTIA_sect4.json"
    # configFileName  = "ESTIA_sect5.json"

    # configFileName  = "ESTIA_sect0and1.json"
    # configFileName  = "ESTIA_sect2and3.json"
    # configFileName  = "ESTIA_sect4and5.json"
    
    parameters.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep

    parameters.fileManagement.configFileName = configFileName

    ###############################################################################
    ###############################################################################
    ### edit parameters for plotting and analisys here ###
    ###############################################################################

    ### ACQ MODES:
    #################################
    ### can only be only one of these 5 options: off, pcap-sync, pcap-local, pcap-local-overwrite or kafka

    # parameters.acqMode = 'pcap-sync'
    # parameters.acqMode = 'pcap-local'
    # parameters.acqMode = 'pcap-local-overwrite'
    # parameters.acqMode = 'kafka'
    parameters.acqMode = 'off'

    ###  then check parameters.fileManagement.openMode = 'window' for the open mode ...
    ###############################################################################
    ###############################################################################
    ### FILE MANAGMENT  PARAMETERS:
    #################################

    # relevant for acqMode =  pcap-local, pcap-local-overwrite and kafka 

    parameters.dumpSettings.interface     = 'ens2'

    parameters.dumpSettings.typeOfCapture = 'packets'
    parameters.dumpSettings.quantity      =  100      #packets

    # parameters.dumpSettings.typeOfCapture = 'duration'
    # parameters.dumpSettings.quantity      = 1   #seconds

    parameters.fileManagement.fileNameSave = 'test'

    # NOTE
    # for acqMode =  pcap-local saves files in parameters.fileManagement.filePath 

    # relevant for acqMode =  kafka , num of packets to dump is in dumpSettings 
    parameters.kafkaSettings.broker       = '127.0.0.1:9092'
    parameters.kafkaSettings.topic        = 'freia_debug'
    parameters.kafkaSettings.numOfPackets =  100      #packets

    ###############################################################################

    # relevant for acqMode =  pcap-sync
    ### from ... to  ... rsync the data

    parameters.fileManagement.sourcePath = 'essdaq@172.30.244.50:/home/essdaq/pcaps/'

    parameters.fileManagement.destPath   = r"/Users/francescopiscitelli/Desktop/dataVMM/"

    ###############

    parameters.fileManagement.filePath = parameters.fileManagement.destPath 

    # relevant for acqMode =  off, pcap-sync and pcap-local

    parameters.fileManagement.filePath = current_dir+'data/'

   
    ### folder and file to open (file can be a list of files)

    parameters.fileManagement.fileName = ['ESSmask2023.pcapng','CSPEC1.pcapng']
    
    # parameters.fileManagement.fileName = ['20260522_153423_duration_s_5_fullyOpenAgain_00000_vkjaa.pcapng']
    
    
    # parameters.fileManagement.fileName = ['miracles_trig2.pcapng']
    # parameters.fileManagement.fileName = ['MG_2EMMAprototypes.pcapng']
    # parameters.fileManagement.fileName = ['miracles_source_mask_red.pcapng']
    # parameters.fileManagement.fileName = ['CSPEC1.pcapng']
    parameters.fileManagement.fileName = ['20260602_103110_duration_s_300_muons_00000.pcapng']
    
    # parameters.fileManagement.fileName = ['sampleData_ClusteredMode.pcapng']
    
    # parameters.fileManagement.fileName = ['MGtestVess.pcapng']
    
    parameters.fileManagement.fileSerials = [6,2,4,9,10,11,12]
    # OR
    # parameters.fileManagement.fileSerials = ["0-2","11-13",45]

    ### valid otions: 'window','fileName', 'latest', 'secondLast', 'wholeFolder', 'sequence' 
    ### window opens to selcet file, filename speficified  earlier, last or sencond last file crearted in folder, 
    ### entire  folder  opend  and analized and cumulated  all togheter 
    ### sequence opens all filens in     parameters.fileManagement.fileSerials and with fileName
    parameters.fileManagement.openMode = 'window'
    parameters.fileManagement.openMode = 'fileName'
    #parameters.fileManagement.openMode = 'latest'
    # parameters.fileManagement.openMode = 'secondLast'
    #parameters.fileManagement.openMode = 'wholeFolder'
    parameters.fileManagement.openMode = 'sequence'

    ###############
    ### type of pcap file loading, prealloc of memeory with allocate or quick, allocate is more rigorous, quick estimates the memory and it is faster 
    parameters.fileManagement.pcapLoadingMethod = 'allocate'
    parameters.fileManagement.pcapLoadingMethod = 'quick'

    ###############
    ### path to calibration file
    parameters.fileManagement.calibFilePath = parameters.fileManagement.currentPath+'calib/'
    parameters.fileManagement.calibFileName = 'AMOR_calib_20231111002842.json'

    ###############
    ### path to threshold  file
    parameters.fileManagement.thresholdFilePath = parameters.fileManagement.currentPath+'config/'
    parameters.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'

    ###############
    ### path to  Tshark, in case you open a pcap  it gets converted into pcapng 
    parameters.fileManagement.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
    # parameters.fileManagement.pathToTshark = '/usr/sbin/'

    ###############
    ### save a hdf file with clusters (reduced file)

    ### ON/OFF
    parameters.fileManagement.saveReducedFileONOFF = True   
    parameters.fileManagement.saveReducedPath = parameters.fileManagement.currentPath+'reduced/'

    parameters.fileManagement.reducedNameMainFolder   = 'entry1'
    parameters.fileManagement.reducedCompressionHDFT  = 'gzip'  
    parameters.fileManagement.reducedCompressionHDFL  = 9    # gzip compression level 0 - 9

    ###############################################################################
    ### ANALISYS PARAMETERS:
    #################################

    ### calibration VMM ADC TDC
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = False
    
    parameters.dataReduction.calibrateVMM_TDC_ONOFF = False

    ### sorting readouts by time stamp, if OFF they are as in RMM stream
    parameters.timeSettings.sortReadoutsByTimeStampsONOFF = True

    ### time stamp is time HI + time LO or if fine corrected with TDC 
    parameters.timeSettings.timeResolutionType = 'fine'
    # parameters.timeSettings.timeResolutionType = 'coarse'

    ### timeWindow to search for clusters, timeWindow is max time between events in candidate cluster 
    ### and timeWindow/2 is the recursive time distance between adjacent hits
    parameters.dataReduction.timeWindow = 0.13e-6

    ### 'OFF', 'fromFile' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh
    parameters.dataReduction.softThresholdType = 'off' 
    # parameters.dataReduction.softThresholdType = 'fromFile' 
    # parameters.dataReduction.softThresholdType = 'userDefined' 
    # parameters.dataReduction.softThresholdType = 'constants' 

    if parameters.dataReduction.softThresholdType == 'userDefined':
          
       parameters.dataReduction.softThArray = {
                  5: {'ch0': np.full(32, 1000.0)},   # cassette 1, wire thresholds only
                  6: {'ch0': np.full(32, 500.0), 'ch1': np.full(64, 700.0)},
              } 
        
    elif  parameters.dataReduction.softThresholdType == 'constants':
        
        parameters.dataReduction.softThArray = (150,100)
   
        
              
    ###############################################################################
    ### WAVELENGTH PARAMETERS:
    #################################

    ### distance in mm from chopper and wires 0 of detector
    parameters.wavelength.distance  = 32000

    ##ON/OFF
    parameters.wavelength.calculateLambda = False

    ### ON/OFF plot X vs Lambda 2D plot
    parameters.wavelength.plotXLambda     = True
    ### ON/OFF integrated over single cassettes
    parameters.wavelength.plotLambdaDistr = True

    parameters.wavelength.lambdaBins  = 128
    parameters.wavelength.lambdaRange = [1, 16]   #A

    parameters.wavelength.chopperPeriod = 0.12 #s (NOTE: only matters if multipleFramesPerRest > 1)

    ### if chopper has two openings or more per reset of ToF
    parameters.wavelength.multipleFramePerReset = True  #ON/OFF (this only affects the lambda calculation)
    parameters.wavelength.numOfBunchesPerPulse  = 2
    parameters.wavelength.lambdaMIN             = 2.5     #A

    ### in seconds, time shift betweeen pickup and chopper edge 
    parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 

      
    ###############################################################################
    ### MONITOR PARAMETERS:
    #################################

    ### ON/OFF
    parameters.MONitor.MONOnOff    = False   

    ### threshold on MON, th is OFF if 0, any other value is ON
    parameters.MONitor.MONThreshold = 0 

    ### ON/OFF plotting (MON ToF and Pulse Height) 
    parameters.MONitor.plotMONtofPHS = True  
    
    ### Pulse Height Spectr. settings for MON
    parameters.MONitor.energyBins = 256
    parameters.MONitor.maxEnerg   = 1000

    ### in mm, distance of MON from chopper if plotMONtofPH == 1 (needed for lambda calculation if ToF)
    parameters.MONitor.MONDistance  = 6000   
    

    ###############################################################################
    ### PLOTTING PARAMETERS:
    #################################

    ###############
    # with True disables clustering and mapping for speed reasons, analisys stops at readouts 
    parameters.plotting.bareReadoutsCalculation = False

    ###############     
    ### plotting in sections of cassettes to ease the visualization if True and in blocks of ...  
    parameters.plotting.plottingInSections       = False 
    parameters.plotting.plottingInSectionsBlocks = 5

    ###############     
    ### show stat during clustering, option  'globalStat'  stat for all cassettes together, 
    ### 'individualStat' stat per cassette or None for no stat
    parameters.plotting.showStat = 'globalStat'
    # parameters.plotting.showStat = 'individualStat'

    ###############     
    ### raw plots
    parameters.plotting.plotRawReadouts         = True
    parameters.plotting.plotReadoutsTimeStamps  = True
    parameters.plotting.plotADCvsCh             = True 
    parameters.plotting.plotADCvsChlog          = True 
    parameters.plotting.plotChopperResets       = True 

    parameters.plotting.plotRawHits             = True
    parameters.plotting.plotHitsTimeStamps      = True
    parameters.plotting.plotHitsTimeStampsVSChannels = True

    ###############
    ### time between events 
    parameters.plotting.plotTimeBetwEv    = True
    parameters.plotting.timeBetwEvBin     = 1e-6  # s
    
    ###############
    ### ToF plot integrated over individual cassette, one per cassette
    parameters.plotting.plotToFDistr    = True

    parameters.plotting.ToFrange        = 0.12    # s
    parameters.plotting.ToFbinning      = 100e-6 # s

    parameters.plotting.ToFGate         = False
    parameters.plotting.ToFGateRange    = [0.02,0.025]   # s
         
    parameters.plotting.plotMultiplicity = True 

    ### 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
    parameters.plotting.positionReconstruction = 'W.max-S.cog'
    # parameters.plotting.positionReconstruction = 'W.max-S.max'
    # parameters.plotting.positionReconstruction = 'W.cog-S.cog'

    ### if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.
    parameters.plotting.plotABSunits = True
     
    ### plot XY and XToF in log scale 
    parameters.plotting.plotIMGlog   = False

    ### ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False
    
    parameters.plotting.coincidenceWS_ONOFF = True

    ### ON/OFF, if  invalid ToFs Tofare included in the plots or removed from events 
    parameters.plotting.removeInvalidToFs   = True

    ### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
    parameters.plotting.histogOutBounds = True

    ###########################      
    ### PHS

    ### ON/OFF PHS per channel and global
    parameters.pulseHeigthSpect.plotPHS = True

    ### plot PHS in log scale 
    parameters.pulseHeigthSpect.plotPHSlog = False

    parameters.pulseHeigthSpect.energyBins = 256
    parameters.pulseHeigthSpect.maxEnerg   = 2000

    ### plot the PHS correaltion wires vs strips
    parameters.pulseHeigthSpect.plotPHScorrelation = True

    ###############################################################################
    ###############################################################################
    ###############################################################################

    allTogether = False
    
    red = reduceFiles(parameters)
    red.reduce(allTogether)
    
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################