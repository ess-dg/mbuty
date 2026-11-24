#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 19 14:40:33 2026

@author: francescopiscitelli
"""

###############################################################################
###############################################################################
###############################################################################

import os
import numpy as np
import json

from collections import defaultdict
import pandas as pd

from lib.save_reduced_file import readReducedDataFromHDF 
import lib.parameters as para

import matplotlib.pyplot as plt

plt.close('all')
 
###############################################################################
###############################################################################
###############################################################################

current_dir = os.path.abspath(os.path.dirname(__file__)) + os.sep
parameters  = para.parameters(current_dir)

configFileName  = "MB_AMOR.json"

configFileName  = "MG_BOX.json"
   
parameters.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep

parameters.fileManagement.configFileName = configFileName

parameters.acqMode = 'off'

parameters.fileManagement.filePath = os.path.join(current_dir, 'reduced') + os.sep

parameters.fileManagement.fileName = ['ESSmask2023_reduced.h5']

# parameters.fileManagement.fileName = ['20261119_141328_duration_s_900_Box1_from_00000_to_00004.h5']


parameters.fileManagement.fileName = ['20261119_141328_duration_s_900_Box1_from_00000_to_00004.h5','20261119_141328_duration_s_900_Box1_from_00005_to_00007.h5']
    
###############################################################################
### ANALISYS PARAMETERS:
#################################

### calibration VMM ADC TDC
parameters.dataReduction.calibrateVMM_ADC_ONOFF = False
parameters.dataReduction.calibrateVMM_TDC_ONOFF = False

### sorting readouts by time stamp, if OFF they are as in RMM stream
parameters.timeSettings.sortReadoutsByTimeStampsONOFF = True

### time stamp is time HI + time LO or if fine corrected with TDC 
parameters.timeSettings.timeResolutionType   = 'fine'
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
       
       # for tubes
       # parameters.dataReduction.softThArray = {
       #            11: 13340,  
       #             12: 4566,
       #         } 
        
elif  parameters.dataReduction.softThresholdType == 'constants':
        
        # for MB or MG 
        parameters.dataReduction.softThArray = [300,0]
        
        # for tubes
        # parameters.dataReduction.softThArray[0] = [10000]
        
              
###############################################################################
### WAVELENGTH PARAMETERS:
#################################

### distance in mm from chopper and wires 0 of detector
parameters.wavelength.distance  = 32000

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
parameters.MONitor.MONOnOff    = True 

### ON/OFF plotting for MON
parameters.MONitor.activatePlots = True  

### threshold on MON, th is OFF if 0, any other value is ON
parameters.MONitor.MONThreshold = 0 

### Pulse Height Spectr. settings for MON
parameters.MONitor.energyBins = 256
parameters.MONitor.maxEnerg   = 1000

### position bins MON
parameters.MONitor.posBins    = 128

### in mm, distance of MON from chopper if plotMONtofPH == 1 (needed for lambda calculation if ToF)
parameters.MONitor.MONDistance  = 6000   


###############################################################################
### PLOTTING PARAMETERS:
#################################

###############
# with True disables clustering and mapping for speed reasons, analisys stops at readouts 
parameters.plotting.bareReadoutsCalculation = False

###############     
parameters.plotting.useDashboard            = True
###############   

###############   
### plotting in sections of cassettes to ease the visualization if True and in blocks of ...  
parameters.plotting.plottingInSections       = False 
parameters.plotting.plottingInSectionsBlocks = 5

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
### time between events 
parameters.plotting.plotTimeBetwEv    = False
parameters.plotting.timeBetwEvBin     = 1e-6  # s

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

### ON/OFF, if  invalid ToFs Tof are included in the plots or removed from events 
parameters.plotting.removeInvalidToFs   = True

### histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)
parameters.plotting.histogOutBounds = True

###########################      
### PHS

### ON/OFF PHS per channel and global
parameters.pulseHeigthSpect.plotPHS    = True

### plot PHS in log scale 
parameters.pulseHeigthSpect.plotPHSlog = False

parameters.pulseHeigthSpect.energyBins = 256
parameters.pulseHeigthSpect.maxEnerg   = 1700

### plot the PHS correaltion wires vs strips
parameters.pulseHeigthSpect.plotPHScorrelation = False

###############################################################################
###############################################################################
###############################################################################

container_lists = defaultdict(list)
keys_to_merge = ("detector_events", "detector_readouts", "detector_hits")

for filename in parameters.fileManagement.fileName:
    path_and_file = os.path.join(parameters.fileManagement.filePath, filename)
    data = readReducedDataFromHDF(path_and_file, showTree=False)

    if not data:
        continue

    for key in keys_to_merge:
        container = data.get(key)
        if container is not None:
            container_lists[key].append(container)

merged_containers = {
    key: (
        containers[0]
        if len(containers) == 1
        else type(containers[0]).merge(containers)
    )
    for key, containers in container_lists.items()
    if containers
}

eventsArray   = merged_containers["detector_events"].get_data_frame()   if "detector_events"   in merged_containers else pd.DataFrame()
readoutsArray = merged_containers["detector_readouts"].get_data_frame() if "detector_readouts" in merged_containers else pd.DataFrame()
hitsArray     = merged_containers["detector_hits"].get_data_frame()     if "detector_hits"     in merged_containers else pd.DataFrame()

merged_readouts = merged_containers["detector_readouts"] if "detector_readouts"   in merged_containers else pd.DataFrame()
merged_hits   = merged_containers["detector_hits"] if "detector_hits"   in merged_containers else pd.DataFrame()
merged_events = merged_containers["detector_events"] if "detector_events"   in merged_containers else pd.DataFrame()

###############################################################################

with open(os.path.join(parameters.fileManagement.configFilePath, parameters.fileManagement.configFileName), 'r') as f:
    config = json.load(f)

topology = config.get('topology', [])
unit_ids = [entry['ID'] for entry in topology]

detector = config.get('detectorType', [])
                
unit_ids     = np.sort(unit_ids)

#  for checking ID by ID 
# unit_ids     = [40] 
              
if detector == 'MB': 
    
    from lib.histograms import MBAxisSet
    from lib.plotting_readouts import MBReadoutsPlotter
    from lib.plotting_hits import MBHitsPlotter
    from lib.plotting_events import MBEventsPlotter 
    
    axis_set = MBAxisSet(parameters, config)

    readout_plotter = MBReadoutsPlotter(merged_readouts, parameters, config, axis_set, unit_ids)
    
    hit_plotter     = MBHitsPlotter(merged_hits, parameters, config, axis_set, unit_ids)

    event_plotter   = MBEventsPlotter(merged_events, parameters, config, axis_set, unit_ids)
    
    


elif detector == 'MG': 
    
   from lib.histograms import MGAxisSet
   from lib.plotting_readouts import MGReadoutsPlotter
   from lib.plotting_events import  MGEventsPlotter
   from lib.plotting_hits import MGHitsPlotter
   
   axis_set = MGAxisSet(parameters, config)
  
   readout_plotter = MGReadoutsPlotter(merged_readouts, parameters,config, axis_set, unit_ids)
   
   hit_plotter     = MGHitsPlotter(merged_hits, parameters, config, axis_set, unit_ids)

   event_plotter   = MGEventsPlotter(merged_events, parameters, config, axis_set, unit_ids)
   
   
   
   
event_plotter.plot_xy()
event_plotter.plot_tof_xy()

readout_plotter.plot_adc_vs_channel()

readout_plotter.plot_channels_raw()

hit_plotter.plot_channels_raw()


