#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 09:19:11 2026

@author: francescopiscitelli
"""


import os

from MBUTY import MBUTYmain

from lib import libParameters as para
from lib import libReducedFileH5 as saveH5


###############################################################################
###############################################################################

class reduceFiles():
    
    def __init__(self,parameters,allTogether=False):
        
        self.mbuty = MBUTYmain(parameters)
        
    def reduce(self):

        if allTogether is True: 
       
            self.runAnalysis()
            
        else:
    
            if parameters.fileManagement.openMode == 'fileName':
                
                listOfFiles = parameters.fileManagement.fileName
                
                N = len(listOfFiles)
                    
                for ff, fname in enumerate(listOfFiles):
                    
                    print('\n\033[1;32m>>>>>>>>>>> Reading and reducing file {} of {} \n\033[1;37m'.format(ff+1,N)) 
                    
                    parameters.fileManagement.fileName = fname
                    self.runAnalysis()
                    
            elif parameters.fileManagement.openMode == 'sequence':  
                
    
                 parameters.fileManagement.parseFileSerialsList()
                 
                 serials = parameters.fileManagement.fileSerials
                 
                 print(serials)
                 
                 SS = len(serials)
    
                 for ss , fnameSerial in enumerate(serials):
                     
                     print('\n\033[1;32m>>>>>>>>>>> Reading and reducing file {} of {} (serial {})\n\033[1;37m'.format(ss+1,SS,fnameSerial)) 
                     
                     parameters.fileManagement.fileSerials  = [fnameSerial]
                     self.runAnalysis()
                     
            elif parameters.fileManagement.openMode  == 'wholeFolder' :
                
                 print('\n\033[1;33mWARNING: wholeFolder mode, files reduced in a single file! \n\033[1;37m') 
                 self.runAnalysis()
            
        
    def runAnalysis(self):
    
            try:
                self.mbuty.analysis()       
            except:
                print('\n\033[1;33mWARNING: File corrupted or not existing --> skipped! \n\033[1;37m') 
            
        
    
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
    currentPath = os.path.abspath(os.path.dirname(__file__))+os.sep
    parameters  = para.parameters(currentPath)
    ###############################################################################
    ###############################################################################
    ### read json and create parameters for plotting and analisys ###

    configFileName  = "AMOR.json"
    
    # configFileName  = "MGtestVessels.json"
    
    # configFileName  = "MGEMMA_2det.json"
    
    # configFileName  = "test1h.json"

    # configFileName  = "ESTIA.json"
    
    # configFileName  = "MIRACLES24.json"
    # configFileName  = "CSPEC.json"
    # configFileName  = "MIRACLES2.json"

    
    parameters.fileManagement.configFilePath  = currentPath+'config/'

    parameters.fileManagement.configFileName  = configFileName

    ###############################################################################
    ###############################################################################
    ### edit parameters for plotting and analisys here ###
    ###############################################################################

    ### ACQ MODES:
    #################################
    ### can only be only one of these 5 options: off, pcap-sync, pcap-local, pcap-local-overwrite or kafka

    parameters.acqMode = 'off'

    ###  then check parameters.fileManagement.openMode = 'window' for the open mode ...
    ###############################################################################
    ###############################################################################
    ### FILE MANAGMENT  PARAMETERS:
    #################################


    ###############################################################################

    parameters.fileManagement.filePath = r"/Users/francescopiscitelli/Desktop/dataVMM/"

    parameters.fileManagement.filePath = currentPath+'data/'


    ### folder and file to open (file can be a list of files)

    # parameters.fileManagement.fileName = ['ESSmask2023.pcapng']
    parameters.fileManagement.fileName = ['ESSmask2023_1000pkts.pcapng','freia_1k_pkts_ng.pcapng']
    # parameters.fileManagement.fileName = ['miracles_trig2.pcapng']
    # parameters.fileManagement.fileName = ['MG_2EMMAprototypes.pcapng']
    # parameters.fileManagement.fileName = ['miracles_source_mask_red.pcapng']
    # parameters.fileManagement.fileName = ['CSPEC1.pcapng']
    
    # parameters.fileManagement.fileName = ['20260122_113536_duration_s_600_FREIAsector1_00004.pcapng']
    
    
    parameters.fileManagement.fileSerials = [6,2,4,9]
    # OR
    # parameters.fileManagement.fileSerials = ["0-2","11-13",45]
    
    #
    ### valid otions: 'window','fileName', 'latest', 'secondLast', 'wholeFolder', 'sequence' 
    ### window opens to selcet file, filename speficified  earlier, last or sencond last file crearted in folder, 
    ### entire  folder  opend  and analized and cumulated  all togheter 
    ### sequence opens all filens in     parameters.fileManagement.fileSerials and with fileName
    # parameters.fileManagement.openMode = 'window'
    parameters.fileManagement.openMode = 'fileName'
    #parameters.fileManagement.openMode = 'latest'
    # parameters.fileManagement.openMode = 'secondLast'
    # parameters.fileManagement.openMode  = 'wholeFolder'
    # parameters.fileManagement.openMode = 'sequence'
    
    # define if in case of fname or sequence you want a signle file tiwht all failes reduced ina  single one or not 
    allTogether = False

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
    parameters.fileManagement.saveReducedPath = '/Users/francescopiscitelli/Desktop/reducedFile/'

    parameters.fileManagement.reducedNameMainFolder  = 'entry1'
    parameters.fileManagement.reducedCompressionHDFT  = 'gzip'  
    parameters.fileManagement.reducedCompressionHDFL  = 9    # gzip compression level 0 - 9

    ###############################################################################
    ### ANALISYS PARAMETERS:
    #################################

    ### calibration VMM ADC
    parameters.dataReduction.calibrateVMM_ADC_ONOFF = False

    ### sorting readouts by time stamp, if OFF they are as in RMM stream
    parameters.VMMsettings.sortReadoutsByTimeStampsONOFF = False

    ### time stamp is time HI + time LO or if fine corrected with TDC 
    parameters.VMMsettings.timeResolutionType = 'fine'
    # parameters.VMMsettings.timeResolutionType = 'coarse'

    ### timeWindow to search for clusters, timeWindow is max time between events in candidate cluster 
    ### and timeWindow/2 is the recursive time distance between adjacent hits
    parameters.dataReduction.timeWindow = 0.5e-6

    ### 'OFF', 'fromFile' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh
    parameters.dataReduction.softThresholdType = 'off' 
    # parameters.dataReduction.softThresholdType = 'fromFile' 
    # parameters.dataReduction.softThresholdType = 'userDefined' 

    if parameters.dataReduction.softThresholdType == 'userDefined':
        
        parameters.dataReduction.createThArrays(parameters)    
        parameters.dataReduction.softThArray.ThW[:,:] = 700
        parameters.dataReduction.softThArray.ThS[:,:] = 1000   
              
    ###############################################################################
    ### WAVELENGTH PARAMETERS:
    #################################

    ### distance in mm from chopper and wires 0 of detector
    parameters.wavelength.distance = 8000

    ##ON/OFF
    parameters.wavelength.calculateLambda = False

    ### ON/OFF plot X vs Lambda 2D plot
    parameters.wavelength.plotXLambda     = False
    ### ON/OFF integrated over single cassettes
    parameters.wavelength.plotLambdaDistr = False

    parameters.wavelength.lambdaBins  = 128
    parameters.wavelength.lambdaRange = [1, 16]   #A

    parameters.wavelength.chopperPeriod = 0.12 #s (NOTE: only matters if multipleFramesPerRest > 1)

    ### if chopper has two openings or more per reset of ToF
    parameters.wavelength.multipleFramePerReset = False  #ON/OFF (this only affects the lambda calculation)
    parameters.wavelength.numOfBunchesPerPulse  = 2
    parameters.wavelength.lambdaMIN             = 2.5     #A

    ### in seconds, time shift betweeen pickup and chopper edge 
    parameters.wavelength.chopperPickUpDelay =  13.5/(2.*180.) * parameters.wavelength.chopperPeriod/parameters.wavelength.numOfBunchesPerPulse 

      
    ###############################################################################
    ### MONITOR PARAMETERS:
    #################################

    # ### ON/OFF
    parameters.MONitor.MONOnOff = True   

    ### threshold on MON, th is OFF if 0, any other value is ON
    parameters.MONitor.MONThreshold = 0  

    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################

    red = reduceFiles(parameters,allTogether)
    red.reduce()
    
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################