#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep  7 15:04:54 2021

@author: francescopiscitelli
"""


import numpy as np
import time
import os
import matplotlib.pyplot as plt
# from matplotlib.colors import LogNorm
import pandas as pd
import sys 


try:
####### if you run default
    from lib import libSampleData as sdat
    from lib import libMappingR5560 as maps
    from lib import libClusterR5560 as clu
    from lib import libParameters as para
    from lib import libAbsUnitsAndLambdaR5560 as absu
    from lib import libReadPcapng as pcapr


except ImportError:
    ####### if you run in lib 
    import libSampleData as sdat
    import libMappingR5560 as maps
    import libClusterR5560 as clu
    import libParameters as para
    import libAbsUnitsAndLambdaR5560 as absu
    import libReadPcapng as pcapr

###############################################################################
###############################################################################

class softThresholds():
    
    def __init__(self, cassettes, parameters):
        
        self.parameters = parameters

        self.ThW = np.zeros((self.parameters.config.DETparameters.numOfWires,len(cassettes)))
        self.ThS = np.zeros((self.parameters.config.DETparameters.numOfStrips,len(cassettes)))
        self.CassetteIDs  = cassettes
        
    

###############################

class thresholdDef():
    
    def __init__(self, parameters):
        
        self.parameters = parameters

    def load(self, cassettes):
        
        if self.parameters.dataReduction.softThresholdType == 'fromFile' : 
            
            self.softThresholds = softThresholds(cassettes, self.parameters)
            
            # print(self.parameters.fileManagement.thresholdFilePath+self.parameters.fileManagement.thresholdFileName)
             
            sthfullpath = os.path.join(self.parameters.fileManagement.thresholdFilePath,self.parameters.fileManagement.thresholdFileName)
            print('\t loading thresholds from file ...')
            
            if os.path.exists(sthfullpath) is False:
                print('\033[1;33m\t ---> WARNING ... Threshold File: '+sthfullpath+' NOT FOUND\033[1;37m')
                # print("\t ... software thresholds switched OFF ... ")
                self.parameters.dataReduction.softThresholdType = 'off'
                time.sleep(2)
                
            else:
                cassInFile  = pd.read_excel(sthfullpath).columns
                temp        = pd.read_excel(sthfullpath).values
                     
                cassNotFound = []
                cassFound    = []
                
                for k, cc in enumerate(cassettes):
               
                    if not(cc in cassInFile):
                         cassNotFound.append(cc)
                    else:
                         cassFound.append(cc)
                         index = np.where(cc == cassInFile)[0]
                         self.softThresholds.ThW[:,k] = temp[:self.parameters.config.DETparameters.numOfWires,index][:,0]
                         self.softThresholds.ThS[:,k] = temp[self.parameters.config.DETparameters.numOfWires:(self.parameters.config.DETparameters.numOfWires+self.parameters.config.DETparameters.numOfStrips),index][:,0]
                    
                if len(cassNotFound) > 0:
                    print('\t \033[1;33mWARNING ... Threshold File does NOT contain all the cassettes IDs')
                    print("\t ... software thresholds switched OFF for cassette IDs:  ",end='')
                    for cass in cassNotFound:
                        print(cass,end=' ')
                    print('\033[1;37m') 
                
        elif self.parameters.dataReduction.softThresholdType == 'userDefined' :
            
            print('\t loading user defined thresholds ...')
            self.softThresholds = self.parameters.dataReduction.softThArray
            
        elif self.parameters.dataReduction.softThresholdType == 'off' :
                
            # print('\t software thresholds OFF ... ')
            self.softThresholds = softThresholds(cassettes,self.parameters)
                
        return self.parameters.dataReduction.softThresholdType
    
    def get_thresholds1Cass(self, cassette1ID):
        
        if cassette1ID in self.softThresholds.CassetteIDs:
        
            index = self.softThresholds.CassetteIDs.index(cassette1ID)
            
            ThW = self.softThresholds.ThW[:,index]
            ThS = self.softThresholds.ThS[:,index]
            
        else:
            print("\t ... software thresholds switched OFF for cassette ID:  "+str(cassette1ID))
            ThW = np.zeros((self.parameters.config.DETparameters.numOfWires))
            ThS = np.zeros((self.parameters.config.DETparameters.numOfStrips))
            
        return ThW, ThS    
                
##############################################################

class applyThresholdsToEvents():
    
    def __init__(self, events, cassettes, parameters, showStat):
        
        clu.checkCassIDs.checkIfRepeatedIDs(cassettes)
        
        
        
        self.eventsBT   = events
        self.parameters = parameters 
        self.showStat   = showStat
        self.cassettes  = cassettes
        
        self.events = clu.events()
        
        if self.parameters.config.DETparameters.type == 'MB' or self.parameters.config.DETparameters.type == 'MG':
            pass
        else:
            print(f'\t \033[1;31mERROR: Software Thresholds not supported for detector type {self.parameters.config.DETparameters.type} -> turn OFF and run again!\033[0m')
            sys.exit()
    
        
        self.thresholds = thresholdDef(self.parameters) 
        self.parameters.dataReduction.softThresholdType = self.thresholds.load(self.cassettes)
        
        


    def thresholdize1Cass(self,cassette1ID):
        
        if self.parameters.dataReduction.softThresholdType == 'userDefined' or self.parameters.dataReduction.softThresholdType == 'fromFile' : 
            
            self.events1Cass = clu.events()
            
            selCass = self.eventsBT.Cassette == cassette1ID
            
            if np.any(selCass):

                ThW, ThS = self.thresholds.get_thresholds1Cass(cassette1ID)

                wireCh0to31Round = np.round(np.mod(self.eventsBT.positionW,self.parameters.config.DETparameters.numOfWires))
                    
                stripChRound     = np.round(self.eventsBT.positionS)         
                
                for ww in range(self.parameters.config.DETparameters.numOfWires):
                    
                    belowThW = np.logical_and(np.logical_and(selCass, wireCh0to31Round == ww) , self.eventsBT.PHW <= ThW[ww])
                    
                    self.eventsBT.multW[belowThW] = -1
                    
                for ss in range(self.parameters.config.DETparameters.numOfStrips):
                        
                    belowThS  =  np.logical_and(np.logical_and(selCass, stripChRound == ss) , self.eventsBT.PHS <= ThS[ss])
                    
                    self.eventsBT.multS[belowThS] = -1
                    
                selection = np.logical_and(np.logical_and( self.eventsBT.multW >= 0 ,  self.eventsBT.multS >= 0  ), selCass)
                
                self.events1Cass.appendSelection(self.eventsBT,selection)
                
                ################################
                if self.showStat == 'individualStat':
                    print('\n\t thresholdizing ... Cassette ID ',str(cassette1ID),' ',end='')
                    self.someIndStat(self.eventsBT,selection)
                ################################
        
        elif self.parameters.dataReduction.softThresholdType == 'off' :
            
            pass
            
        else:
            
           print('\n \033[1;31msoftware thresholds -> no valid method selected, check spelling ... \033[1;37m')
            
    def thresholdizeAllCassettes(self):
        
        if self.parameters.dataReduction.softThresholdType == 'userDefined' or self.parameters.dataReduction.softThresholdType == 'fromFile' : 
            
            print(" \t software thresholds applied ... ",end='')
            
            for cc in self.cassettes:
                
                  present = clu.checkCassIDs.checkIfPresentInEvents(self.eventsBT,cc)
                  
                  if present:
                      self.thresholdize1Cass(cc)
                      self.events.append(self.events1Cass)
                      # del self.events1Cass 
            
            try:         
                del self.events1Cass  
            except:   
                pass
             
            if self.showStat == 'globalStat':
                  self.someGlobStat(self.events)
                  
        elif self.parameters.dataReduction.softThresholdType == 'off' :
           
            print(" \t software thresholds OFF ... ",end='')
           
            self.events = self.eventsBT
 
        else:
            
            print('\n \033[1;31msoftware thresholds -> no valid method selected, check spelling ... \033[1;37m')
            
            
    def someGlobStat(self, events):
        
        NeventsNotRejAfterTh  = np.sum(events.NeventsNotRejAfterTh)
        
        selc = events.positionS >= 0 
        
        NeventsNotRej2D = np.sum(selc)
        NeventsNotRej1D = np.sum(~selc)
        if self.parameters.config.DETparameters.type == 'MB' or self.parameters.config.DETparameters.type == 'MG':
            print(" --> N of events after thresholds: %d (2D: %d, 1D: %d)" % (NeventsNotRejAfterTh,NeventsNotRej2D,NeventsNotRej1D))
        else:
            print(" --> N of events after thresholds: %d " % (NeventsNotRejAfterTh))
            
    def someIndStat(self, events, selection):
        
        NeventsNotRejAfterTh  = np.sum(selection)
        
        selc = events.positionS[selection] >= 0 
        
        NeventsNotRej2D = np.sum(selc)
        NeventsNotRej1D = np.sum(~selc)
        
        if self.parameters.config.DETparameters.type == 'MB' or self.parameters.config.DETparameters.type == 'MG':
            print(' --> N of events after thresholds: ',str(NeventsNotRejAfterTh),' (2D: ',str(NeventsNotRej2D),', 1D: ',str(NeventsNotRej1D),end='  ' )
        else:
            print(' --> N of events after thresholds: ',str(NeventsNotRejAfterTh),end='  ' )
            
        # print(" --> N of events after thresholds: %d (2D: %d, 1D: %d)" % (NeventsNotRejAfterTh,NeventsNotRej2D,NeventsNotRej1D))
        # print(end=' ')
      
  


###############################################################################
###############################################################################

if __name__ == '__main__':
    
    confFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'
    conFileName  = "MIRACLES2.json"
    # conFileName  = "MGEMMA.json"

    config = maps.read_json_config(confFilePath+conFileName)
    
    # print(config.DETparameters.numOfWires)
    
    currentPath = os.path.abspath(os.path.dirname(__file__))+os.sep
    parameters  = para.parameters(currentPath)
    
    parameters.fileManagement.configFilePath  = confFilePath

    parameters.fileManagement.configFileName  = conFileName
    
    parameters.loadConfigAndUpdate(config)


    ### 'OFF', 'fromFile' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh
    parameters.dataReduction.softThresholdType = 'off' 
    # parameters.dataReduction.softThresholdType = 'fromFile' 
    parameters.dataReduction.softThresholdType = 'userDefined' 

    if parameters.dataReduction.softThresholdType == 'userDefined':
        
        parameters.dataReduction.createThArrays(parameters)    
        parameters.dataReduction.softThArray.ThW[:,:] = 0
        parameters.dataReduction.softThArray.ThS[:,:] = 0  
        
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
    
    ### Pulse Height Spectr. settings for MON
    parameters.MONitor.energyBins = 256
    parameters.MONitor.maxEnerg   = 5000

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
    parameters.plotting.showStat = 'individualStat'

    ###############     
    ### raw plots
    parameters.plotting.plotRawReadouts         = True
    parameters.plotting.plotReadoutsTimeStamps  = False
    parameters.plotting.plotADCvsCh             = False 
    parameters.plotting.plotADCvsChlog          = False 
    parameters.plotting.plotChopperResets       = False 

    parameters.plotting.plotRawHits             = True
    parameters.plotting.plotHitsTimeStamps      = False
    parameters.plotting.plotHitsTimeStampsVSChannels = False

    ###############
    ### Instantaneous Rate
    parameters.plotting.plotInstRate    = False
    parameters.plotting.instRateBin     = 100e-6  # s
     
    ###############
    ### ToF plot integrated over individual cassette, one per cassette
    parameters.plotting.plotToFDistr    = False

    parameters.plotting.ToFrange        = 0.12    # s
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
    parameters.plotting.removeInvalidToFs   = False

    ### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
    parameters.plotting.histogOutBounds = True

    ##############################      
    ### PHS

    ### ON/OFF PHS per channel and global
    parameters.pulseHeigthSpect.plotPHS = True

    ### plot PHS in log scale 
    parameters.pulseHeigthSpect.plotPHSlog = False

    parameters.pulseHeigthSpect.energyBins = 256
    parameters.pulseHeigthSpect.maxEnerg   = 22000

    ### plot the PHS correaltion wires vs strips
    parameters.pulseHeigthSpect.plotPHScorrelation = False    
        
    
    
    ############################## 
    ############################## 
    ############################## 
    ############################## 
    
    filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
    # file = 'MG_2col_2clusters.pcapng'
    file = 'miracles_trig2.pcapng'
      
    # file = 'MG_2col_1cluster.pcapng'
    
    # file = 'miracles_source_mask.pcapng'

    filePathAndFileName = filePath+file
    
    pcapng = pcapr.pcapng_reader(filePathAndFileName)
    
    pcapr.checkIfDataIsSupported(pcapng.flagSupported)

    readouts = pcapng.readouts
    readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
    
    md  = maps.mapDetector(readouts, config)
    md.mappAllCassAndChannelsGlob()
    hits = md.hits
    hitsArray  = hits.concatenateHitsInArrayForDebug()
    
    
    cc = clu.clusterHits(hits,showStat='globalStat')
    cc.clusterizeManyCassettes(config.DETparameters.cassInConfig, timeWindow=1e-6)
    events = cc.events
    deltaTimeWS = cc.deltaTimeClusterWSall
    
    ab = absu.calculateAbsUnits(events, parameters)
    ab.calculatePositionAbsUnit()
    
    ab.calculateToF(parameters.plotting.removeInvalidToFs)
    
    if parameters.wavelength.calculateLambda is True:
        ab.calculateWavelength()

    events = ab.events 
    
    eventsArray = events.concatenateEventsInArrayForDebug()
 
    asth = applyThresholdsToEvents(events, parameters.config.DETparameters.cassInConfig, parameters, parameters.plotting.showStat)
    asth.thresholdizeAllCassettes()

    # plt.close("all")

    # configFilePath  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"MB300_AMOR_config.json"
    # filePathD       = './'+"VMM3a_Freia.pcapng"
   
    # tProfilingStart = time.time()
    # parameters  = para.parameters('/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/')
    # config = maps.read_json_config(configFilePath)
   
    # parameters.loadConfigParameters(config)
   
    # parameters.cassettes.cassettes = [1,2,3]
    
  
    # parameters.fileManagement.thresholdFilePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'
    # parameters.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'
    
    # # parameters.configJsonFile.offset1stWires = 10
    
    # parameters.dataReduction.softThresholdType = 'off'
    
    # parameters.dataReduction.softThresholdType = 'fromFile'
    
    # # parameters.dataReduction.softThresholdType = 'userDefined'
    
    # parameters.dataReduction.createThArrays(parameters.cassettes.cassettes, parameters)    
    # parameters.dataReduction.softThArray.ThW[:,0] = 5000
    # parameters.dataReduction.softThArray.ThS[:,0] = 2000 
    # parameters.dataReduction.softThArray.ThW[:,1] = 5000
    
    # # parameters.configJsonFile.numOfStrips = 32   
    
    # # thresholds = thresholdDef(parameters)
    # # thresholds.load([45,1,2,89,67,8])
    
    # # ThW, ThS = thresholds.get_thresholds(1)

    # #  generate sample hits 
    # Nhits = 1e4
    # cassettes1 = [1,2]
      
    # bb = sdat.sampleHitsMultipleCassettes(cassettes1)
    # bb.generateGlob(Nhits)
    # hits = bb.hits

    # cc = clu.clusterHits(hits,'globalStat')
    # cc.clusterizeManyCassettes(parameters.cassettes.cassettes, parameters.dataReduction.timeWindow)
    # events = cc.events
    
    # # vv = absu.calculateAbsUnits(events, parameters)
    # # vv.calculatePositionAbsUnit()
    # # vv.calculateToF()
    # # vv.calculateWavelength()
    
    # vv = absu.calculateAbsUnits(events, parameters)
    # vv.calculatePositionAbsUnit()
    # vv.calculateToFandWavelength()
    # events = vv.events
    # eventsArray = events.concatenateEventsInArrayForDebug()
    
    # # print(parameters.dataReduction.softThresholdType)
    
    # thre = applyThresholdsToEvents(events, parameters.cassettes.cassettes, parameters, 'globalStat')
    
    # # thre.thresholdize1Cass(1)
    
    # # print(parameters.dataReduction.softThresholdType)
    
    # thre.thresholdizeAllCassettes()
    
    # # print(parameters.dataReduction.softThresholdType)
    
    # eventsAT  = thre.events
    
    # eventsArrayAT = eventsAT.concatenateEventsInArrayForDebug()
    
    # # allAxis = hh.allAxis()
    # allAxis.createAllAxis(parameters)
    
    # pp = plo.plottingEvents(eventsAT,allAxis,True)
    # # pp.plotXYToF(logScale=True, absUnits = True)
    
    # # pp.plotXLambda(logScale=False, absUnits = False)
    
    # # aa = pp.plotMultiplicity([1,2,3])
    
    # pp.plotPHS(parameters.cassettes.cassettes,parameters)
    
    # pp.plotPHScorrelation([1,2,3])