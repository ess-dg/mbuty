#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V6.0 2025/06/09      francescopiscitelli     ######################
###############################################################################
###############################################################################
#  includes streaming from kafka 

import numpy as np
# import time
import os
import sys
import re
# import matplotlib
# matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

# import matplotlib
# matplotlib.use(‘Qt5Agg’)
# from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog, QGridLayout, QLabel, QLineEdit
# app = QApplication(sys.argv)

### import the library with all specific functions that this code uses 
from lib import libReadPcapngVMM as pcapr
from lib import libSampleData as sdat
from lib import libMapping as maps
from lib import libCluster as clu
from lib import libAbsUnitsAndLambda as absu
from lib import libHistograms as hh
from lib import libFileManagmentUtil as fd
from lib import libParameters as para
from lib import libTerminal as ta
from lib import libPlotting as plo
from lib import libEventsSoftThresholds as thre
from lib import libReducedFileH5 as saveH5
from lib import libVMMcalibration as cal 

###############################################################################
###############################################################################

# STILL TO IMPLEMENT:
#     - monitor lambda
#     - TDC calibration 
#     - now the mon events stay in the events array,they need  to be taken out 

# NOTES:
    # in some sytems the command plt.show(block=False) at the end does not work for showing plots 
    # so try using plt.show() instead 
    
###############################################################################
###############################################################################
########    PARAMETERS CAN BE SET AT THE END OF THIS      #####################
########    SCRIPT IF RUN STANDALONE OR FROM GUI          #####################
########    IF RUN GUI                                    #####################
###############################################################################
###############################################################################   
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################

class MBUTYmain():
    
    def __init__(self,parameters, runFromGui=False, main_thread_queue = None):
        self.main_thread_queue = main_thread_queue
        self.parameters = parameters
        self.profiling = para.profiling()
        self.runFromGui = runFromGui
        #  config is embedded in parameters
        
        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        print('----------------------------------------------------------------------')
        print('\033[1;32mCiao '+user_name+'! Welcome to MBUTY 6.0\033[1;37m')
        print('----------------------------------------------------------------------')
        plt.close("all")
        ### check version ###
        para.checkPythonVersion()
        # check packages installation 
        check = para.checkPackageInstallation()
        check.checkPackagePcap()
        
        if self.parameters.acqMode == 'kafka':
            flag = check.checkPackageKafka()
            if flag is True:  
                from lib import libKafkaReader as kaf
                self.kaf = kaf
                
    def runFromBackEnd(self):
        self.analysis()
        self.plotting()

    def analysis(self):
        ###############################################################################
        ###############################################################################
        ### if you want to save reduced data, it must include lambda, 
        ### so lambda calculation is turned ON if not yet 
        if self.parameters.fileManagement.saveReducedFileONOFF is True:       
            if self.parameters.wavelength.calculateLambda == False:
                self.parameters.wavelength.calculateLambda = True
                print('\nLambda calculation turned ON to save reduced DATA')
            
        # if self.parameters.wavelength.plotXLambda or self.parameters.wavelength.plotLambdaDistr is True:
        #     if self.parameters.wavelength.calculateLambda == False:
        #         self.parameters.wavelength.calculateLambda = True
        #         print('\nLambda calculation turned ON to plot Lambda')
                
        if self.parameters.wavelength.calculateLambda == False:
             self.parameters.wavelength.plotXLambda     = False
             self.parameters.wavelength.plotLambdaDistr = False
             
        ###############################################################################
        ###############################################################################
        self.parameters.set_acqMode(self.parameters.acqMode)
        ### read json and create parameters for plotting and analisys ###
        config = maps.read_json_config(os.path.join(self.parameters.fileManagement.configFilePath , self.parameters.fileManagement.configFileName))
        self.parameters.loadConfigAndUpdate(config)
        # self.parameters.update()
        ###############################################################################
        ###############################################################################
        ### create axes for plotting and histograms 
        
        self.allAxis = hh.allAxis()
        self.allAxis.createAllAxis(self.parameters)
        
        ### here eventually edit axes 
        ### then update axes with: self.allAxis.updateself.allAxis()
        
        ###############################################################################
        ###############################################################################
        if self.parameters.acqMode  == 'pcap-local-overwrite'  or self.parameters.acqMode  == 'pcap-local':
            
            rec = ta.dumpToPcapngUtil(self.parameters.fileManagement.pathToTshark, self.parameters.dumpSettings.interface, \
            self.parameters.dumpSettings.destTestData, self.parameters.dumpSettings.fileName)
        
            # sta = ta.acquisitionStatus(self.parameters.dumpSettings.destTestData)  
            # sta.set_RecStatus()
            
            status = rec.dump(self.parameters.dumpSettings.typeOfCapture,self.parameters.dumpSettings.quantity,self.parameters.dumpSettings.numOfFiles,\
            self.parameters.dumpSettings.delay,self.parameters.dumpSettings.fileNameOnly)
            # if status == 0: 
            #      sta.set_FinStatus()
            # else:
            #      sta.set_RecStatus()
        
        ### sync the data folder from remote computer to local folder 
        elif not self.runFromGui and self.parameters.acqMode == 'pcap-sync':
            transferData = ta.transferDataUtil()
            transferData.syncData(self.parameters.fileManagement.sourcePath, self.parameters.fileManagement.destPath)   
        
        ###############################################################################
        ###############################################################################
        ### select data
        fileDialogue = fd.fileDialogue(self.parameters)
        fileDialogue.openFile()

        ###############################################################################
        ###############################################################################
        ### initialize readouts cumulated over file list
        self.readouts = pcapr.readouts()
        
        if self.parameters.acqMode == 'pcap-sync' or self.parameters.acqMode == 'pcap-local' or self.parameters.acqMode == 'pcap-local-overwrite' or self.parameters.acqMode == 'off':
            for cont, fileName in enumerate(fileDialogue.fileName):
                print('\033[1;32m-> reading file {} of {}\033[1;37m'.format(cont+1,len(fileDialogue.fileName)))
                ### check if a file is pcapng otherwise pcap is converted into pcapng
                conv = ta.pcapConverter(self.parameters)
                conv.checkExtensionAndConvertPcap(os.path.join(fileDialogue.filePath,fileName))
                if conv.flag is False:
                    fileName = conv.fileName_OUT
                ### check which Ring, Fen and Hybrid is present in the selected File
                # pcapr.checkWhich_RingFenHybrid_InFile(fileDialogue.filePath+fileName,self.parameters.clockTicks.NSperClockTick).check()
                ### load data
                pcap = pcapr.pcapng_reader(os.path.join(fileDialogue.filePath,fileName), self.parameters.clockTicks.NSperClockTick, MONTTLtype = self.parameters.config.MONmap.TTLtype, MONring = self.parameters.config.MONmap.RingID, \
                timeResolutionType = self.parameters.VMMsettings.timeResolutionType, sortByTimeStampsONOFF = self.parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, \
                operationMode = self.parameters.config.DETparameters.operationMode, pcapLoadingMethod=self.parameters.fileManagement.pcapLoadingMethod)
                self.readouts.append(pcap.readouts)
                
        elif self.parameters.acqMode == 'kafka':
            testing = False
            pcap = self.kaf.kafka_reader(self.parameters.clockTicks.NSperClockTick, nOfPackets = self.parameters.kafkaSettings.numOfPackets, \
            broker = self.parameters.kafkaSettings.broker, topic = self.parameters.kafkaSettings.topic, MONTTLtype = self.parameters.config.MONmap.TTLtype , MONring = self.parameters.config.MONmap.RingID, \
            timeResolutionType =self.parameters.VMMsettings.timeResolutionType, sortByTimeStampsONOFF=self.parameters.VMMsettings.sortReadoutsByTimeStampsONOFF, \
            operationMode=self.parameters.config.DETparameters.operationMode, testing=testing)
            self.readouts.append(pcap.readouts)
        
        self.heartbeats1 = self.readouts.heartbeats
        self.heartbeats2 = self.readouts.removeNonESSpacketsHeartbeats(self.readouts.heartbeats)
        
        self.readouts.checkChopperFreq()
        
        self.readouts.checkInvalidToFsInReadouts()
        
        ####################    
        ### for debug, generate sample readouts
        # aa = sdat.sampleReadouts_2()
        # aa.fill()
        # readouts = aa.readouts
        ####################
        
        ####################
        ### for debug, readouts in single array
        # readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
        ####################
        
        if self.parameters.plotting.bareReadoutsCalculation is False:
            
            ###########################################################################
            ### calibration ADC
            if self.parameters.dataReduction.calibrateVMM_ADC_ONOFF is True:
                self.calib = cal.read_json_calib(os.path.join(self.parameters.fileManagement.calibFilePath,self.parameters.fileManagement.calibFileName),self.parameters.config)
            
                if self.calib.calibFlag is True:
                    ca = cal.calibrate(self.readouts,self.parameters.config,self.calib)
                    ca.calibrateADC()
                    self.readouts = ca.readouts
               
            ########################################################################### 
            
            md  = maps.mapDetector(self.readouts, self.parameters.config)
            md.mappAllCassAndChannelsGlob()
            self.hits = md.hits
            # hitsArray  = hits.concatenateHitsInArrayForDebug()
        
        
            ####################
            ### getting the hits for the MONitor
            if self.parameters.MONitor.MONOnOff is True:
                self.MON = maps.mapMonitor(self.readouts, self.parameters.config)
                if self.MON.flagMONfound is True:
                    self.hitsMON = self.MON.hits
                    
                    self.MONe = clu.hitsMON2events(self.hitsMON)
                    self.eventsMON = self.MONe.events
                    
                    
                    ###############################################################################
                    ### MON thresholds
                    # 
                    
                    abMON = absu.calculateAbsUnits(self.eventsMON, self.parameters, 'MON')
                    abMON.calculateToF(self.parameters.plotting.removeInvalidToFs)
                    
                    print('\033[1;32m\t MON events: {}\033[1;37m'.format(self.eventsMON.Nevents[0]))
     
                    
                    if self.parameters.wavelength.calculateLambda is True:
                        
                        abMON.calculateWavelengthMON()
        
                    self.eventsMON = abMON.events
 
        
                    if self.parameters.MONitor.MONThreshold > 0:
                        
                        belowThMON = self.eventsMON.PHW <= self.parameters.MONitor.MONThreshold
                        self.eventsMON.removeData(belowThMON)
                        print('\033[1;32m\t MON events (after threshold): {}\033[1;37m'.format(self.eventsMON.Nevents[0]))

            
            ###############################################################################
            ### map data
            # md  = maps.mapDetector(readouts, self.parameters.config)
            # md.mappAllCassAndChannelsGlob()
            # hits = md.hits
            
            # for debug force all hits in a single cassetteno.1 even if from different hybrids
            # hits.Cassette = np.ones(len((hits.Cassette)),dtype='int64')
            
             
            ####################    
            ### for debug, generate sample hits 
            # Nhits = 5e4
            # bb = sdat.sampleHitsMultipleCassettes()
            # bb.generateGlob(Nhits)
            # hits = bb.hits   
            
            # bb = sdat.sampleHitsMultipleCassettes_2()
            # bb.generateGlob()
            # hits = bb.hits  
            ######################
            
            ####################    
            ### for debug, hits in single array 
            # hitsArray = hits.concatenateHitsInArrayForDebug()
            ####################
            
            
            if self.parameters.config.DETparameters.operationMode == 'normal':
                ###############################################################################
                ### clusterize
                cc = clu.clusterHits(self.hits,self.parameters.plotting.showStat)
                cc.clusterizeManyCassettes(self.parameters.config.DETparameters.cassInConfig, self.parameters.dataReduction.timeWindow)
                self.events = cc.events
                self.deltaTimeWS = cc.deltaTimeClusterWSall
                

                
            elif  self.parameters.config.DETparameters.operationMode == 'clustered':  
                ### do not clusterize
                self.events = clu.events()
                self.events.importClusteredHits(self.hits,self.parameters.config)
            
               
            ####################    
            ### for debug, generate sample events 2
            # dd = sdat.sampleEventsMultipleCassettes(self.parameters.config.DETparameters.cassInConfig,'./data/')
            # dd.generateGlob(Nevents)
            # events  = dd.events
            # eventsArray = events.concatenateEventsInArrayForDebug()
            # eventsArray = eventsArray[72:100,:]
            #################### 
                
            
            ###############################################################################
            ### calculate abs units, ToF and lambda
            
            ab = absu.calculateAbsUnits(self.events, self.parameters)
            ab.calculatePositionAbsUnit()
            
            ab.calculateToF(self.parameters.plotting.removeInvalidToFs)
            
            if self.parameters.wavelength.calculateLambda is True:
                ab.calculateWavelength()
 
            self.events = ab.events 
            
            ####################    
            ### for debug, events in single array 
            # eventsArrayBTh = eventsBTh.concatenateEventsInArrayForDebug() 
            # eventsArrayBTh = events.concatenateEventsInArrayForDebug() 
            ####################    
            
            ###############################################################################
            ###############################################################################
            ### software thresholds

            if self.parameters.dataReduction.softThresholdType == 'fromFile'  or self.parameters.dataReduction.softThresholdType == 'userDefined' :
                
              asth = thre.applyThresholdsToEvents(self.events, self.parameters.config.DETparameters.cassInConfig, self.parameters, self.parameters.plotting.showStat)
              asth.thresholdizeAllCassettes()
                
              self.events  = asth.events 
            
            ###############################################################################
            ###############################################################################
            ### save reduced data to hdf5
              
            if self.parameters.fileManagement.saveReducedFileONOFF is True: 
                
                # fileNameSave  = os.path.splitext(fileDialogue.fileName[0])[0]+'_reduced'
                
                base_name, extension = os.path.splitext(fileDialogue.fileName[0])

                match = re.search(r"(_\d+)$", base_name)
                
                if match:
                    prefix = base_name[:match.start()]
                    suffix = match.group(0) 
                    base_name2, extension2 = os.path.splitext(fileDialogue.fileName[-1])
                    match2 = re.search(r"(_\d+)$", base_name2)
                    suffix2 = match2.group(0)
                    fileNameSave  = "_".join([ prefix , 'from'+suffix , 'to'+suffix2 ,'reduced'])
                else:
                    fileNameSave  = "_".join([ base_name , 'reduced'])

                
                sav = saveH5.saveReducedDataToHDF(self.parameters,self.parameters.fileManagement.saveReducedPath,fileNameSave)
                
                if (self.parameters.MONitor.MONOnOff is True) and (self.MON.flagMONfound is True):
                    sav.save(self.events,self.eventsMON)
                else:
                    sav.save(self.events)
                    
        ###############################################################################
        ###############################################################################            
                    
        #  like this all ToFs get into reduced file, the gate is only in plotting 
            if self.parameters.plotting.ToFGate is True:
                abb = absu.gateToF(self.events,self.parameters.plotting.ToFGateRange)
                self.events = abb.events 
                
        if self.runFromGui:       
            self.main_thread_queue.put(lambda: self.plotting())
            
###############################################################################
###############################################################################      
###############################################################################
###############################################################################     

    def plotting(self):
        ###############################################################################
        ###############################################################################
        ### plots
        ######################
        if self.parameters.plottingInSections is False:
            self.parameters.plottingInSectionsBlocks = self.parameters.config.DETparameters.numOfCassettes
        else:
            print('\n\033[1;36m \t Plotting Cassettes in blocks of {} \033[1;37m\n'.format(self.parameters.plottingInSectionsBlocks)) 
            fullConfig = self.parameters.config
        
        self.parameters.HistNotification(self.parameters.plottingInSections)
        
            
        numOfLoops = int(np.ceil(self.parameters.config.DETparameters.numOfCassettes/self.parameters.plottingInSectionsBlocks))
            
        for loop in range(numOfLoops):
            
            plt.close("all")
            
               
            start = loop*self.parameters.plottingInSectionsBlocks
            stop  = (loop+1)*self.parameters.plottingInSectionsBlocks
            
            if self.parameters.plottingInSections is True:
                self.parameters.config  = maps.extractPartialConfig.extract(fullConfig,start,stop)
                print('\033[1;36m \t Plotting Cassettes from {} to {} \033[1;37m'.format(start,stop-1))
                
            self.parameters.loadConfig(self.parameters.config)
            self.allAxis.createAllAxis(self.parameters,cassOffset = start)
                
            ######################
            ### readouts
            
            if (self.parameters.plotting.plotRawReadouts  or  self.parameters.plotting.plotReadoutsTimeStamps or self.parameters.plotting.plotChopperResets or self.parameters.plotting.plotADCvsCh) is True:
                plread = plo.plottingReadouts(self.readouts, self.parameters.config, self.parameters.plotting.histogOutBounds)
                if self.parameters.plotting.plotRawReadouts is True:
                    plread.plotChRaw(self.parameters.config.DETparameters.cassInConfig)
                if self.parameters.plotting.plotReadoutsTimeStamps is True:
                    plread.plotTimeStamps(self.parameters.config.DETparameters.cassInConfig)
                if self.parameters.plotting.plotADCvsCh is True:
                    plread.plotADCvsCh(self.parameters.config.DETparameters.cassInConfig, self.allAxis , self.parameters.plotting.plotADCvsChlog)          
                if self.parameters.plotting.plotChopperResets is True:
                    plread.plotChoppResets()
                    
            ######################
            
            ######################
            if self.parameters.plotting.bareReadoutsCalculation is False:
                ### hits
                if (self.parameters.plotting.plotRawHits or self.parameters.plotting.plotHitsTimeStamps or self.parameters.plotting.plotHitsTimeStampsVSChannels) is True:
                    plhits = plo.plottingHits(self.hits, self.parameters, self.parameters.plotting.histogOutBounds)
                    if self.parameters.plotting.plotRawHits is True:
                        plhits.plotChRaw(self.parameters.config.DETparameters.cassInConfig)
                    if self.parameters.plotting.plotHitsTimeStamps is True:
                        plhits.plotTimeStamps(self.parameters.config.DETparameters.cassInConfig)
                    if self.parameters.plotting.plotHitsTimeStampsVSChannels is True:    
                        plhits.plotTimeStampsVSCh(self.parameters.config.DETparameters.cassInConfig)    
            ######################
            
            ######################
            ### events
            
            if self.parameters.plotting.bareReadoutsCalculation is False:
                ### XY and XToF
                plev = plo.plottingEvents(self.events,self.allAxis,self.parameters.plotting.coincidenceWS_ONOFF, self.parameters.plotting.histogOutBounds)
                plev.plotXYToF(logScale = self.parameters.plotting.plotIMGlog, absUnits = self.parameters.plotting.plotABSunits, orientation = self.parameters.config.DETparameters.orientation)
                
                # ### ToF per cassette 
                if self.parameters.plotting.plotToFDistr is True:
                    plev.plotToF(self.parameters.config.DETparameters.cassInConfig)
            
                ### lambda
                if self.parameters.wavelength.plotXLambda is True:
                    plev.plotXLambda(logScale = self.parameters.plotting.plotIMGlog, absUnits = self.parameters.plotting.plotABSunits)
                ### lambda per cassette
                if self.parameters.wavelength.plotLambdaDistr is True:
                    plev.plotLambda(self.parameters.config.DETparameters.cassInConfig)
                    
                ### multiplicity 
                if self.parameters.plotting.plotMultiplicity is True:
                    plev.plotMultiplicity(self.parameters.config.DETparameters.cassInConfig)
            
                # ### PHS
                if self.parameters.pulseHeigthSpect.plotPHS is True:
                    plev.plotPHS(self.parameters.config.DETparameters.cassInConfig, self.parameters, logScale = self.parameters.pulseHeigthSpect.plotPHSlog)
                if self.parameters.pulseHeigthSpect.plotPHScorrelation is True:
                    plev.plotPHScorrelation(self.parameters.config.DETparameters.cassInConfig, self.parameters.pulseHeigthSpect.plotPHSlog)
                
                ### instantaneous Rate per cassette
                if self.parameters.plotting.plotInstRate is True:
                    plev.plotInstantaneousRate(self.parameters.config.DETparameters.cassInConfig)
            
                ############
                # MON plots
                if self.parameters.MONitor.MONOnOff is True and self.parameters.MONitor.plotMONtofPHS is True and self.MON.flagMONfound is True:
                    
                    plMON = plo.plottingMON(self.eventsMON,self.allAxis, self.parameters.plotting.histogOutBounds)
                    plMON.plot_ToF_PHS_MON()
                    
                    if self.parameters.wavelength.calculateLambda is True: 
                        plMON.plotLambda_MON()
                        
            #########################################################          
            plt.show(block= False)
            #########################################################           
            if self.parameters.plottingInSections is True:
                if self.runFromGui:
                    from tkinter import messagebox
                    plt.pause(0.5)
                    result = messagebox.askquestion(
                        "Plot Next Section?",
                        "Click yes when you are ready to contine to next block of plots \n\n Click no to quit",
                        icon='warning'
                    )
                    if result == 'no':
                        plt.close()
                        self.profiling.stop()
                        print('----------------------------------------------------------------------')
                        return
                else:
                    # CLI mode: allow interactive plot navigation
                    plt.pause(0.5)
                    inp = input('\033[1;32m--> press (enter) to continue to the next block or (q + enter) to quit \033[1;37m')
                    if inp == 'q':
                        plt.close()
                        self.profiling.stop()
                        print('----------------------------------------------------------------------')
                        sys.exit()
                   
 
        ###############################################################################
        ###############################################################################
        # Final plotting and display logic
        plt.show(block= False)
        self.profiling.stop()
        print('----------------------------------------------------------------------')
        ###############################################################################
        ###############################################################################
        
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
    
    # configFileName  = "test1h.json"

    # configFileName  = "ESTIA.json"

    # configFileName  = "ESTIA_sect0.json"
    # configFileName  = "ESTIA_sect1.json"
    # configFileName  = "ESTIA_sect2.json"
    # configFileName  = "ESTIA_sect3.json"
    # configFileName  = "ESTIA_sect4.json"
    # configFileName  = "ESTIA_sect5.json"

    # configFileName  = "ESTIA_sect0and1.json"
    # configFileName  = "ESTIA_sect2and3.json"
    # configFileName  = "ESTIA_sect4and5.json"
    
    parameters.fileManagement.configFilePath  = currentPath+'config/'

    parameters.fileManagement.configFileName  = configFileName

    ###############################################################################
    ###############################################################################
    ### edit parameters for plotting and analisys here ###
    ###############################################################################

    ### ACQ MODES:
    #################################
    ### can only be only one of these 5 options: off, pcap-sync, pcap-local, pcap-local-overwrite or kafka

    parameters.acqMode = 'pcap-sync'
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
    # parameters.fileManagement.sourcePath = 'essdaq@172.30.244.233:~/pcaps/'
    parameters.fileManagement.destPath   = r"/Users/francescopiscitelli/Desktop/dataVMM/"

    ###############

    parameters.fileManagement.filePath = parameters.fileManagement.destPath 

    # relevant for acqMode =  off, pcap-sync and pcap-local

    parameters.fileManagement.filePath = currentPath+'data/'

    # parameters.fileManagement.filePath = '/Users/francescopiscitelli/Desktop/dataVMM'

    # parameters.fileManagement.filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap_develDataFormatClustered/data/'
    # parameters.fileManagement.fileName = [ 'sampleData_NormalMode.pcapng']
    # parameters.fileManagement.fileName = [ 'sampleData_ClusteredMode.pcapng']

    ### folder and file to open (file can be a list of files)

    # parameters.fileManagement.fileName = ['freia_1k_pkts_ng.pcapng']
    # parameters.fileManagement.fileName = ['freiatest.pcapng']
    #parameters.fileManagement.fileName = ['20231106_142811_duration_s_5_YESneutrons1240K1070Rth280_maskESS_00000.pcapng']
    parameters.fileManagement.fileName = ['ESSmask2023.pcapng']
    # parameters.fileManagement.fileName = ['ESSmask2023_1000pkts.pcapng']

    # parameters.fileManagement.fileName = ['20250307_101420_duration_s_1800_testCAB3_00006.pcapng']

    parameters.fileManagement.fileSerials = [6,2,4,9]

    ### valid otions: 'window','fileName', 'latest', 'secondLast', 'wholeFolder', 'sequence' 
    ### window opens to selcet file, filename speficified  earlier, last or sencond last file crearted in folder, 
    ### entire  folder  opend  and analized and cumulated  all togheter 
    ### sequence opens all filens in     parameters.fileManagement.fileSerials and with fileName
    parameters.fileManagement.openMode = 'window'
    parameters.fileManagement.openMode = 'fileName'
    #parameters.fileManagement.openMode = 'latest'
    # parameters.fileManagement.openMode = 'secondLast'
    #parameters.fileManagement.openMode = 'wholeFolder'
    # parameters.fileManagement.openMode = 'sequence'

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
    parameters.fileManagement.saveReducedFileONOFF = False   
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

    ### ON/OFF
    parameters.MONitor.MONOnOff = True   

    ### threshold on MON, th is OFF if 0, any other value is ON
    parameters.MONitor.MONThreshold = 0  

    ### ON/OFF plotting (MON ToF and Pulse Height) 
    parameters.MONitor.plotMONtofPHS = True  

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
    parameters.plottingInSections       = False 
    parameters.plottingInSectionsBlocks = 5

    ###############     
    ### show stat during clustering, option  'globalStat'  stat for all cassettes together, 
    ### 'individualStat' stat per cassette or None for no stat
    parameters.plotting.showStat = 'globalStat'
    # parameters.plotting.showStat = 'individualStat'

    ###############     
    ### raw plots
    parameters.plotting.plotRawReadouts         = True
    parameters.plotting.plotReadoutsTimeStamps  = False
    parameters.plotting.plotADCvsCh             = False 
    parameters.plotting.plotADCvsChlog          = False 
    parameters.plotting.plotChopperResets       = False 

    parameters.plotting.plotRawHits             = False
    parameters.plotting.plotHitsTimeStamps      = False
    parameters.plotting.plotHitsTimeStampsVSChannels = False

    ###############
    ### Instantaneous Rate
    parameters.plotting.plotInstRate    = False
    parameters.plotting.instRateBin     = 100e-6  # s
     
    ###############
    ### ToF plot integrated over individual cassette, one per cassette
    parameters.plotting.plotToFDistr    = False

    parameters.plotting.ToFrange        = 0.15    # s
    parameters.plotting.ToFbinning      = 100e-6 # s

    parameters.plotting.ToFGate         = False
    parameters.plotting.ToFGateRange    = [0.02,0.025]   # s
         
    parameters.plotting.plotMultiplicity = False 

    ### 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
    parameters.plotting.positionReconstruction = 'W.max-S.cog'
    # parameters.plotting.positionReconstruction = 'W.max-S.max'
    # parameters.plotting.positionReconstruction = 'W.cog-S.cog'

    ### if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.
    parameters.plotting.plotABSunits = False
     
    ### plot XY and XToF in log scale 
    parameters.plotting.plotIMGlog   = False

    ### ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False
    parameters.plotting.coincidenceWS_ONOFF = True

    ### ON/OFF, if  invalid ToFs Tofare included in the plots or removed from events 
    parameters.plotting.removeInvalidToFs   = True

    ### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
    parameters.plotting.histogOutBounds = True

    ##############################      
    ### PHS

    ### ON/OFF PHS per channel and global
    parameters.pulseHeigthSpect.plotPHS = True

    ### plot PHS in log scale 
    parameters.pulseHeigthSpect.plotPHSlog = False

    parameters.pulseHeigthSpect.energyBins = 128
    parameters.pulseHeigthSpect.maxEnerg   = 1700

    ### plot the PHS correaltion wires vs strips
    parameters.pulseHeigthSpect.plotPHScorrelation = False

    ###############################################################################
    ###############################################################################
    ###############################################################################

    mbuty = MBUTYmain(parameters)
    mbuty.runFromBackEnd()
    
    heartbeats1 = mbuty.heartbeats1
    heartbeats2 = mbuty.heartbeats2
    
    readouts      = mbuty.readouts
    readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
    
    if parameters.plotting.bareReadoutsCalculation == False:
        
        hits       = mbuty.hits
        hitsArray  = hits.concatenateHitsInArrayForDebug()
        
        # eventsMONarray = eventsMON.concatenateEventsInArrayForDebug()
        
        events      = mbuty.events
        eventsArray = events.concatenateEventsInArrayForDebug() 
        
        deltaTimeWS = mbuty.deltaTimeWS
        
        
        
        if parameters.MONitor.MONOnOff is True and mbuty.MON.flagMONfound is True:
            hitsMON   = mbuty.hitsMON
            eventsMON = mbuty.eventsMON

    
    ###############################################################################
    ###############################################################################
    #  any other plot that the user wants...
    
    # # sel = np.logical_or(hits.WiresStrips == 31,  hits.WiresStrips == 2)
    # sel = np.logical_or(hits.WiresStrips == 0,  hits.WiresStrips == 8)
    
    # diffe       = np.diff(hits.timeStamp[sel])
    
    # # print('\n',np.sum(~sel))
    
    # # sortedDiffe = diffe[diffe.argsort()]
    
    # # # print('freq injected in 1 ch '+str(1/(sortedDiffe[-1]*1e-9))+' Hz')
    
    # TD = np.arange(-2000,2000,1)
    
    # hist  = hh.histog().hist1D(TD,diffe) 
    # figl, ax = plt.subplots(num=567,figsize=(6,6), nrows=1, ncols=1) 
    # ax.step(TD,hist,'b',where='mid')   
    # ax.set_yscale('log')
    # ax.set_xlabel('delta time (ns)')
    # ax.set_ylabel('counts') 
    # ax.grid()
    # ax.set_xlim((-200,200))
    # # figl.suptitle('2FEN_2Hy')
          
    # ToF     = readouts.timeStamp - readouts.PulseT
    
    # # ToFprev = readouts.timeStamp - readouts.PrevPT
    
    # # delta =  readouts.PulseT -  readouts.PrevPT
    
    # # patth = 'ToFs.txt'
    
    
    # TofAxis  = np.linspace(0,5e7,1024)
            
    
    
    # histo = hh.histog().hist1D(TofAxis,ToF)
    
    
    # figl5666, ax5666 = plt.subplots(num=567655,figsize=(6,6), nrows=1, ncols=1)
               
    # # global PHS plot
    # # ax5666.step(self.allAxis.axEnergy.axis,PHSGw,'r',where='mid',label='w')
    # ax5666.step(TofAxis,histo,'k',where='mid',label='w/s')
    # # ax5666.set_xlabel('pulse height (a.u.)')
    # # ax5666.set_ylabel('counts')
    # # ax5666.set_xlim([0,1200])
    # ax5666.grid()
    # ax5666.set_yscale('log')
    
    
    # chaxis = np.linspace(0,63,64)
    
    
    # selHYB = readouts.hybrid  == 3
    
    # selVMM = readouts.VMM     == 6
    
    # selall = np.logical_and(selHYB,selVMM)
    
    
    
    # histo2D = hh.histog().hist2D( TofAxis, ToF[selall], chaxis, readouts.Channel[selall] ) 
    
    # from matplotlib.colors import LogNorm
    
    # figl5667, ax5667 = plt.subplots(num=567657,figsize=(6,6), nrows=1, ncols=1)
               
    # # global PHS plot
    # # ax5666.step(self.allAxis.axEnergy.axis,PHSGw,'r',where='mid',label='w')
    # pos1  = ax5667.imshow(histo2D,aspect='auto',norm=LogNorm(),interpolation='none',extent=[TofAxis[0],TofAxis[-1],chaxis[-1],chaxis[0]], origin='upper',cmap='viridis')
     
    # ax5667.grid()
    
    # aa = np.concatenate((ToF[:,None],ToFprev[:,None]),axis=1)
    
    
    # # bb = np.round(aa/100000)   
      
    # dataTemp = np.savetxt(patth,aa,delimiter='\t')
    
    

    # deltaTimeWSc = deltaTimeWS[ np.logical_and(deltaTimeWS[:,0]==7,deltaTimeWS[:,2]==2) , :]
    
    # xax = np.arange(-300,300,1)
    
    # hitows = hh.histog().hist1D(xax, deltaTimeWSc[:,1])

    
    # fig334, ax335 = plt.subplots(num=101445,figsize=(12,6), nrows=1, ncols=1)   
    # ax335.step(xax,hitows,'r')
    # ax335.set_yscale('log')
    
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    ###############################################################################
    