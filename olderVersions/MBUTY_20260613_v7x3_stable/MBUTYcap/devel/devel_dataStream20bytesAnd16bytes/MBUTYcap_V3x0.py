#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V2.3 2021/11/24      francescopiscitelli     ######################
###############################################################################
###############################################################################

import numpy as np
import time
import os
import sys
import matplotlib.pyplot as plt

# import matplotlib
# # matplotlib.use(‘Qt5Agg’)
from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog, QGridLayout, QLabel, QLineEdit
app = QApplication(sys.argv)

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

###############################################################################
###############################################################################

# STILL TO IMPLEMENT:
#     - save reduced data - almost done 
#     - monitor lambda
#     - TDC and ADC calibration 
#     - now the mon events  stay in the events array,they need  to be taken out 

###############################################################################
###############################################################################
profiling = para.profiling()
print('----------------------------------------------------------------------')
print('\033[1;32mCiao '+os.environ['USER']+'! Welcome to MBUTY 3.0\033[1;37m')
print('----------------------------------------------------------------------')
plt.close("all")
### check version ###
para.checkPythonVersion()
### get current path ###
currentPath = os.path.abspath(os.path.dirname(__file__))+'/'
parameters  = para.parameters(currentPath)
###############################################################################
###############################################################################
### read json and create parameters for plotting and analisys ###

configFilePath  = currentPath+'config/'

# configFileName  = "MB300_AMOR_config1to2.json"
# configFileName  = "MB300_AMOR_config1to5.json"
# configFileName  = "MB300_AMOR_config6to10.json"
# configFileName  = "MB300_AMOR_config11to14.json"

# configFileName  = "MB300_AMOR_config.json"

# configFileName  = "MB300_AMOR_config_12.json"

# configFileName  = "MB300_AMOR_config_rev.json"
# configFileName  = "MB300_FREIA_config.json"
# configFileName  = "MB300_FREIA3_config.json"
# configFileName  = "MB300_FREIA_config_inverted.json"
# configFileName  = "Utgard_test.json"
# configFileName  = "Utgard_test_AssCrate.json"

configFileName  = "Utgard_test_H0.json"
# # configFileName  = "Utgard_test.json"
# configFileName  = "Utgard_test_5hyb.json"

# configFileName  = "Utgard_AMOR.json"

###############################################################################
###############################################################################
### read json and create parameters for plotting and analisys ###
config = maps.read_json_config(configFilePath+configFileName)
parameters.loadConfigParameters(config)
###############################################################################
###############################################################################
###############################################################################
###############################################################################
### edit parameters for plotting and analisys here ###
###############################################################################
### FILE MANAGMENT  PARAMETERS:
#################################

### ON/OFF if you want to rsync the data     
parameters.fileManagement.sync = True  

### from ... to  ... rsync the data

# test setup
parameters.fileManagement.sourcePath = 'essdaq@172.30.244.233:~/pcaps/'

# parameters.fileManagement.sourcePath = 'essdaq@192.168.0.1:~/pcaps/'

parameters.fileManagement.destPath   = '/Users/francescopiscitelli/Desktop/dataVMM/'
# parameters.fileManagement.destPath   = currentPath+'data/'
# parameters.fileManagement.destPath   = '/Users/francescopiscitelli/Desktop/dataVMMdatenere/'


# parameters.fileManagement.destPath   = '/Users/francescopiscitelli/Documents/DOC/DATA/202308_Utgard_MBnewAMOR_VMM_muons/DATA/'

###############

parameters.fileManagement.filePath = parameters.fileManagement.destPath 

### folder and file to open (file can be a list of files)
# parameters.fileManagement.filePath = parameters.fileManagement.destPath
parameters.fileManagement.fileName = ['freia_1k_pkts_ng.pcapng']
parameters.fileManagement.fileName = ['freiatest.pcapng']
# parameters.fileManagement.fileName = ['20230821_113026_duration_s_3_testinghybrdis-monitor_00000.pcapng']

# parameters.fileManagement.fileName = ['20230821_133733_pkts10_testinghybrdis-monitor_00000.pcapng']


parameters.fileManagement.fileName = ['20230821_135744_pkts10_testinghybrdis-monitor_00000.pcapng']

# parameters.fileManagement.fileSerials = np.arange(18,28,1)

### valid otions: 'window','fileName', 'latest', 'secondLast', 'wholeFolder', 'sequence' 
### window opens to selcet file, filename speficified  earlier, last or sencond last file crearted in folder, 
### entire  folder  opend  and analized and cumulated  all togheter 
### sequence opens all filens in     parameters.fileManagement.fileSerials and with fileName
parameters.fileManagement.openMode = 'window'
# parameters.fileManagement.openMode = 'fileName'
# parameters.fileManagement.openMode = 'latest'
# parameters.fileManagement.openMode = 'sequence'

###############
### path to threshold  file
parameters.fileManagement.thresholdFilePath = parameters.fileManagement.currentPath+'config/'
parameters.fileManagement.thresholdFileName = 'MB300L_thresholds.xlsx'

###############
### path to  Tshark, in case you open a pcap  it gets converted into pcapng 
parameters.fileManagement.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'

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

### cassettes to clusterize and to plot, if empty the cassettes in the config file are taken as default
# parameters.cassettes.cassettes = [1,2,3,4,5,6]
# parameters.cassettes.cassettes = np.arange(32,0,-1)

### timeWindow to search for clusters, timeWindow is max time between events in candidate cluster 
### and timeWindow/2 is the recursive time distance between adjacent hits
parameters.dataReduction.timeWindow = 3e-6

### 'OFF', 'fromFile' = File With Threhsolds Loaded, 'userDefined' = User defines the Thresholds in an array softTh
parameters.dataReduction.softThresholdType = 'off' 
# parameters.dataReduction.softThresholdType = 'fromFile' 

if parameters.dataReduction.softThresholdType == 'userDefined':
    
    parameters.dataReduction.createThArrays(parameters.cassettes.cassettes, parameters)    
    parameters.dataReduction.softThArray.ThW[:,0] = 15000
    parameters.dataReduction.softThArray.ThS[:,0] = 500   
          
###############################################################################
### WAVELENGTH PARAMETERS:
#################################

### distance in mm from chopper and wires 0 of detector
parameters.wavelength.distance = 8000

##ON/OFF
parameters.wavelength.calculateLambda = False

### ON/OFF plot X vs Lambda 2D plot
parameters.wavelength.plotXLambda   = False
### ON/OFF integrated over single cassettes
parameters.wavelength.plotLambdaDistr = False

parameters.wavelength.lambdaBins  = 128
parameters.wavelength.lambdaRange = [1, 16]   #A

parameters.wavelength.chopperPeriod = 0.15 #s (NOTE: only matters if multipleFramesPerRest > 1)

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
parameters.MONitor.MONDistance  = 0   

###############################################################################
### PLOTTING PARAMETERS:
#################################

###############     
### show stat during clustering, option  'globalStat'  stat for all cassettes together, 
### 'individualStat' stat per cassette or None for no stat
parameters.plotting.showStat = 'globalStat'
# parameters.plotting.showStat = 'individualStat'

###############     
### raw plots
parameters.plotting.plotRawReadouts         = True
parameters.plotting.plotReadoutsTimeStamps  = False
parameters.plotting.plotRawHits             = False
parameters.plotting.plotHitsTimeStamps      = False
parameters.plotting.plotHitsTimeStampsVSChannels = False
parameters.plotting.plotChopperResets       = True

# with True disables clustering and mapping for speed reasons, analisys stops at readouts 
bareReadoutsCalc = False

###############
### Instantaneous Rate
parameters.plotting.plotInstRate    = False
parameters.plotting.instRateBin     = 100e-6  # s
 
###############
### ToF plot integrated over individual cassette, one per cassette
parameters.plotting.plotToFDistr    = False

parameters.plotting.ToFrange       = 0.06    # s
parameters.plotting.ToFbinning      = 100e-6 # s
     
parameters.plotting.plotMultiplicity = False 

# parameters.configJsonFile.orientation = 'vertical'

### 'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG 
parameters.plotting.positionReconstruction = 'W.max-S.cog'
parameters.plotting.positionReconstruction = 'W.max-S.max'

### if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.
parameters.plotting.plotABSunits = False
 
### plot XY and XToF in log scale 
parameters.plotting.plotIMGlog = False

### ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False
parameters.plotting.coincidenceWS_ONOFF = True

### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
parameters.plotting.hitogOutBounds = True

### for absolute  units calculation in X, already loaded in config json file
# parameters.configJsonFile.offset1stWires = 10

##############################      
### PHS

### ON/OFF PHS per channel and global
parameters.pulseHeigthSpect.plotPHS = True

### plot PHS in log scale 
parameters.pulseHeigthSpect.plotPHSlog = False

parameters.pulseHeigthSpect.energyBins = 128
parameters.pulseHeigthSpect.maxEnerg   = 1025

### plot the PHS correaltion wires vs strips
parameters.pulseHeigthSpect.plotPHScorrelation = False

###############################################################################
###############################################################################
########    end of with all the settings you can choose   #####################
########        DO NOT EDIT BELOW THIS LINE!!!!           #####################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
### if you want to save reduced data, it must include lambda, 
### so lambda calculation is turned ON if not yet 
if parameters.fileManagement.saveReducedFileONOFF is True:       
    parameters.wavelength.calculateLambda = True
    print('\n \t Lambda calculation turned ON to save reduced DATA')
    
if parameters.wavelength.plotXLambda or parameters.wavelength.plotLambdaDistr is True:
    parameters.wavelength.calculateLambda = True
    print('\n \t Lambda calculation turned ON to plot Lambda')
###############################################################################
###############################################################################
parameters.update()
###############################################################################
###############################################################################
### create axes for plotting and histograms 

allAxis = hh.allAxis()
allAxis.createAllAxis(parameters)

### here eventually edit axes 
### then update axes with: allAxis.updateAllAxis()

###############################################################################
###############################################################################
### sync the data folder from remote computer to local folder 
if parameters.fileManagement.sync is True:
    transferData = ta.transferDataUtil()
    transferData.syncData(parameters.fileManagement.sourcePath, parameters.fileManagement.destPath)

###############################################################################
###############################################################################
### select data
fileDialogue = fd.fileDialogue(parameters)
fileDialogue.openFile()
###############################################################################
###############################################################################

### initialize readouts cumulated over file list
readouts = pcapr.readouts()
# hits   = maps.hits()
# events = clu.events()


for cont, fileName in enumerate(fileDialogue.fileName):

    print('\033[1;32m-> reading file {} of {}\033[1;37m'.format(cont+1,len(fileDialogue.fileName)))
    
    ### check if a file is pcapng otherwise pcap is converted into pcapng
    conv = ta.pcapConverter(parameters)
    conv.checkExtensionAndConvertPcap(fileDialogue.filePath+fileName)
    if conv.flag is False:
        fileName = conv.fileName_OUT
        
    ### check which Ring, Fen and Hybrid is present in the selected File 
    # pcapr.checkWhich_RingFenHybrid_InFile(fileDialogue.filePath+fileName,parameters.clockTicks.NSperClockTick).check()
    
    ### load data  
    pcap = pcapr.pcapng_reader(fileDialogue.filePath+fileName, parameters.clockTicks.NSperClockTick, timeResolutionType='fine', sortByTimeStampsONOFF = False)
    readouts.append(pcap.readouts)
    
    # md  = maps.mapDetector(pcap.readouts, config)
    # md.mappAllCassAndChannelsGlob()
    # hits.append(md.hits)
     
    # cc = clu.clusterHits(md.hits,parameters.plotting.showStat)
    # cc.clusterizeManyCassettes(parameters.cassettes.cassettes, parameters.dataReduction.timeWindow)
    # eve.append(cc.events)
    

readouts.checkChopperFreq()

# xax = np.arange(0,len(readouts.PulseT))
# yax = readouts.PulseT - readouts.PulseT[0]

# fig33445454, ax33545455 = plt.subplots(num=101445,figsize=(12,6), nrows=1, ncols=1)   
# ax33545455.plot(xax,yax,'+r')

# ax33545455.plot(xax,readouts.timeStamp - readouts.PulseT[0],'+b')

# delta = np.concatenate((np.diff(yax),[0]),axis=0)


# ax33545455.plot(xax,delta,'+b')

# aa=np.sort(delta)

# bb = np.diff(readouts.timeStamp)
      
####################    
### for debug, generate sample readouts
# aa = sdat.sampleReadouts_2()
# aa.fill()
# readouts = aa.readouts
####################

####################
### for debug, readouts in single array
readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
####################

if bareReadoutsCalc is False:
    
    
    md  = maps.mapDetector(readouts, config)
    md.mappAllCassAndChannelsGlob()
    hits = md.hits
    hitsArray  = hits.concatenateHitsInArrayForDebug()


    ####################
    ### getting the hits for the MONitor
    if parameters.MONitor.MONOnOff is True:
        MON = maps.mapMonitor(readouts, config)
        if MON.flagMONfound is True:
            hitsMON = MON.hits
            
            MONe = clu.hitsMON2events(hitsMON)
            eventsMON = MONe.events
            
            abMON = absu.calculateAbsUnits(eventsMON, parameters, 'MON')
            abMON.calculateToF()
            
            print('\033[1;32m\t MON events: {}\033[1;37m'.format(len(eventsMON.timeStamp)))
            
            
            # CALCULATION OF LAMBDA ON MON NOT YET IMPLEMENTED



    
    ###############################################################################
    ### map data
    # md  = maps.mapDetector(readouts, config)
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
    
    ###############################################################################
    ### clusterize
    cc = clu.clusterHits(hits,parameters.plotting.showStat)
    cc.clusterizeManyCassettes(parameters.cassettes.cassettes, parameters.dataReduction.timeWindow)
    events = cc.events
    
    ####################    
    ### for debug, events in single array 
    eventsArray = events.concatenateEventsInArrayForDebug() 
    ####################
       
    # ####################    
    # ### for debug, generate sample events 2
    # Nevents = 10000
    # dd = sdat.sampleEventsMultipleCassettes()
    # dd.generateGlob(Nevents)
    # events  = dd.events
    # eventsArray = events.concatenateEventsInArrayForDebug()
    # eventsArray = eventsArray[72:100,:]
    # ################### 
        
    
    ###############################################################################
    ### calculate abs units, ToF and lambda
    
    ab = absu.calculateAbsUnits(events, parameters)
    ab.calculatePositionAbsUnit()
    
    ab.calculateToF()
    
    if parameters.wavelength.calculateLambda is True:
        ab.calculateWavelength()
    
    # eventsBTh = ab.events 
    
    events = ab.events 
    
    ####################    
    ### for debug, events in single array 
    # eventsArrayBTh = eventsBTh.concatenateEventsInArrayForDebug() 
    # eventsArrayBTh = events.concatenateEventsInArrayForDebug() 
    ####################    
    
    ###############################################################################
    ###############################################################################
    ### software thresholds
    
    # asth = thre.applyThresholdsToEvents(eventsBTh, parameters.cassettes.cassettes, parameters, parameters.plotting.showStat)
    # asth.thresholdizeAllCassettes()
        
    # events  = asth.events 
    
    # eventsArrayAT = events.concatenateEventsInArrayForDebug()
    
    ###############################################################################
    ###############################################################################
    ### save reduced data to hdf5
      
    if parameters.fileManagement.saveReducedFileONOFF is True: 
        
        fileNameSave = 'temp'
    
        fileNameSave  = fileDialogue.fileName[0]+'_reduced'
        
        sav = saveH5.saveReducedDataToHDF(parameters,parameters.fileManagement.saveReducedPath,fileNameSave)
        # sav.save(eventsBTh)
        sav.save(events)

###############################################################################
###############################################################################
### plot
parameters.HistNotification()

######################
### readouts
if (parameters.plotting.plotRawReadouts  or  parameters.plotting.plotReadoutsTimeStamps) is True:
    plread = plo.plottingReadouts(readouts, config)
    if parameters.plotting.plotRawReadouts is True:
        plread.plotChRaw(parameters.cassettes.cassettes)
    if parameters.plotting.plotReadoutsTimeStamps is True:
        plread.plotTimeStamps(parameters.cassettes.cassettes)
        
if parameters.plotting.plotChopperResets is True:
    plread1 = plo.plottingReadouts(readouts, config)
    plread1.plotChoppResets()

         
######################

######################
if bareReadoutsCalc is False:
    ### hits
    if (parameters.plotting.plotRawHits or parameters.plotting.plotHitsTimeStamps or parameters.plotting.plotHitsTimeStampsVSChannels) is True:
        plhits = plo.plottingHits(hits, parameters)
        if parameters.plotting.plotRawHits is True:
            plhits.plotChRaw(parameters.cassettes.cassettes)
        if parameters.plotting.plotHitsTimeStamps is True:
            plhits.plotTimeStamps(parameters.cassettes.cassettes)
        if parameters.plotting.plotHitsTimeStampsVSChannels is True:    
            plhits.plotTimeStampsVSCh(parameters.cassettes.cassettes)    
    ######################

######################
### events

if bareReadoutsCalc is False:
    ### XY and XToF
    plev = plo.plottingEvents(events,allAxis,parameters.plotting.coincidenceWS_ONOFF)
    plev.plotXYToF(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits, orientation = parameters.configJsonFile.orientation)
    
    # ### ToF per cassette 
    if parameters.plotting.plotToFDistr is True:
        plev.plotToF(parameters.cassettes.cassettes)

    ### lambda
    if parameters.wavelength.plotXLambda is True:
        plev.plotXLambda(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits)
    ### lambda per cassette
    if parameters.wavelength.plotLambdaDistr is True:
        plev.plotLambda(parameters.cassettes.cassettes)
        
    ### multiplicity 
    if parameters.plotting.plotMultiplicity is True:
        plev.plotMultiplicity(parameters.cassettes.cassettes)

    # ### PHS
    if parameters.pulseHeigthSpect.plotPHS is True:
        plev.plotPHS(parameters.cassettes.cassettes, parameters, logScale = parameters.pulseHeigthSpect.plotPHSlog)
    if parameters.pulseHeigthSpect.plotPHScorrelation is True:
        plev.plotPHScorrelation(parameters.cassettes.cassettes, parameters.pulseHeigthSpect.plotPHSlog)
    
    ### instantaneous Rate per cassette
    if parameters.plotting.plotInstRate is True:
        plev.plotInstantaneousRate(parameters.cassettes.cassettes)

    ############
    # MON plots
    if parameters.MONitor.MONOnOff is True and parameters.MONitor.plotMONtofPHS is True and MON.flagMONfound is True:
        
        plMON = plo.plottingMON(eventsMON,allAxis)
        plMON.plot_ToF_PHS_MON()

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
if bareReadoutsCalc is False:     
    figl566, ax566 = plt.subplots(num=56767,figsize=(6,6), nrows=1, ncols=1) 
    ax566.plot(np.arange(0,len(events.ToF)),events.ToF/1e9,'b')   

###############################################################################
###############################################################################
plt.show()
profiling.stop()
print('----------------------------------------------------------------------')
###############################################################################
###############################################################################

