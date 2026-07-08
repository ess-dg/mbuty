#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 25 10:46:16 2021

@author: francescopiscitelli
"""

import numpy as np
import matplotlib.pyplot as plt
# from matplotlib.colors import LogNorm
# import time



try: 
    ####### if you run default
    from lib import libMappingR5560 as maps
    from lib import libPlotting
    from lib import libHistogramsR5560 as hh
    from lib import libClusterR5560 as clu
    from lib import libReadPcapng as pcapr
    from lib import libParameters as para
    from lib import libAbsUnitsAndLambdaR5560 as absu

except ImportError:
    ####### if you run in lib 
    import libMappingR5560 as maps
    import libPlotting
    import libHistogramsR5560 as hh
    import libClusterR5560 as clu
    import libReadPcapng as pcapr
    import libParameters as para
    import libAbsUnitsAndLambdaR5560 as absu

###############################################################################
############################################################################### 

# import default lib 

preparePlotMatrix  = libPlotting.preparePlotMatrix
checkReadoutsClass = libPlotting.checkReadoutsClass
checkHitsClass     = libPlotting.checkHitsClass
checkEventsClass   = libPlotting.checkEventsClass
logScaleMap        = libPlotting.logScaleMap
plottingMON        = libPlotting.plottingMON

###############################################################################
###############################################################################   
        
class plottingReadouts():
    
    def __init__(self,  readouts, parameters, allAxis, outOfBounds = True):
        """ Acts as a pointer/wrapper for the central library """
        return libPlotting.plottingReadouts.__init__(self,  readouts, parameters, allAxis, outOfBounds)   

    def plotChoppResets(self):
        """ Acts as a pointer/wrapper for the central library """
        return libPlotting.plottingReadouts.plotChoppResets(self)

    # def selectHybridFromCassetteID(self,cassette1ID):
    #     if self.flag is True:
    #          self.config.get_cassID2RingFenHybrid(cassette1ID)
    
    #          sel1 = self.readouts.Ring     == self.config.cassMap.RingID
    #          sel2 = self.readouts.Fen      == self.config.cassMap.FenID
    #          sel3 = self.readouts.Cassette == self.config.cassMap.TubeID
            
    #          selectedHybridfromCassID_BoolArrayW = sel1 & sel2 & sel3

    #          return selectedHybridfromCassID_BoolArrayW

    def histChRaw1hybrid(self,cassette1ID):
        
        if self.flag is True:
            
            self.config.get_cassID2RingFenHybrid(cassette1ID)
    
            # tube correpsonds to a particluar triplet of ring fen and tube ID 

            sel1 = self.readouts.Ring    == self.config.cassMap.RingID
            sel2 = self.readouts.Fen     == self.config.cassMap.FenID
            sel3 = self.readouts.Channel == self.config.cassMap.TubeID
            
            sel = sel1 & sel2 & sel3
            
            # prin(sel)

            if self.config.DETparameters.operationMode == 'normal':
                # self.ch    = (self.readouts.Channel[sel][0])
                self.ch    = cassette1ID
                self.count = np.shape(self.readouts.Channel[sel])[0]
            elif self.config.DETparameters.operationMode == 'clustered':
                print(f" --> other modes than normal are not supported for detector type {self.config.DETparameters.type}")
  
        
    def plotChRaw(self,cassetteIDs): 
        
        if self.flag is True:
        
            self.ploth = preparePlotMatrix(1001, 1, 1)
            
            self.ploth.figHandle.suptitle('Readouts - present tubes')
            
            sizze = np.shape(self.parameters.config.DETparameters.cassInConfig)[0]
            
            self.xbins  = np.zeros((sizze) , dtype='int64') 
            self.histo0 = np.zeros((sizze) , dtype='int64') 
            
            for k, cc in enumerate(cassetteIDs):
                
                self.histChRaw1hybrid(cc)
                
                self.xbins[k]  = self.ch
                self.histo0[k] = self.count

            # positions = np.arange(len(self.xbins))
            # self.ploth.axHandle[0][0].bar(positions,self.histo0,0.8,color='r') 
            # self.ploth.axHandle[0][0].set_xlabel('Tubes')
            # self.ploth.axHandle[0][0].set_ylabel('num of entries')
            # self.ploth.axHandle[0][0].set_xticks(positions)
            # self.ploth.axHandle[0][0].set_xticklabels(self.xbins)
    
            self.ploth.axHandle[0][0].bar(self.xbins,self.histo0,0.8,color='r') 
            self.ploth.axHandle[0][0].set_xlabel('Tubes')
            self.ploth.axHandle[0][0].set_ylabel('num of entries')
            self.ploth.axHandle[0][0].set_xticks(self.xbins)

   
            
    def extractTimeStamp1hybrid(self,cassette1ID):
        
        if self.flag is True:
        
            self.config.get_cassID2RingFenHybrid(cassette1ID)
    
            # tube correpsonds to a particluar triplet of ring fen and tube ID 

            sel1 = self.readouts.Ring    == self.config.cassMap.RingID
            sel2 = self.readouts.Fen     == self.config.cassMap.FenID
            sel3 = self.readouts.Channel == self.config.cassMap.TubeID
            
            sel = sel1 & sel2 & sel3
            
            if self.config.DETparameters.operationMode == 'normal':
                self.timeStamp0 = self.readouts.timeStamp[sel]
            elif self.config.DETparameters.operationMode == 'clustered':
                print(f" --> other modes than normal are not supported for detector type {self.config.DETparameters.type}")
            
          
            
    def plotTimeStamps(self,cassetteIDs):
        
        if self.flag is True:
        
            self.plotht = preparePlotMatrix(1002, 1, len(cassetteIDs))
            
            self.plotht.figHandle.suptitle('Readouts - raw tubes time stamps')
            
            for k, cc in enumerate(cassetteIDs):
                
                self.extractTimeStamp1hybrid(cc)  
                
                xx0 = np.arange(0,len(self.timeStamp0),1)
                
                self.plotht.axHandle[0][k].scatter(xx0,self.timeStamp0,0.8,color='r',marker='+') 
                self.plotht.axHandle[0][k].set_xlabel('trigger no.')
                self.plotht.axHandle[0][k].set_ylabel('time (ns)')
                self.plotht.axHandle[0][k].set_title('Tube ID.'+str(cc)) 
                self.plotht.axHandle[0][k].grid(axis='x', alpha=0.75)
                self.plotht.axHandle[0][k].grid(axis='y', alpha=0.75)

        
    def plotADCvsCh(self,cassetteIDs,logScale = False):
        print(f"\n\t \033[1;33mWARNING: ADC vs Ch not supported for {self.config.DETparameters.type} -> SKIPPING PLOT (use raw hits for ADC VS ADC).\033[0m")

                   
                   
###############################################################################
############################################################################### 
        
class plottingHits():
    
    def __init__(self,  hits, parameters, allAxis, outOfBounds = True):
        """ Acts as a pointer/wrapper for the central library """
        return libPlotting.plottingHits.__init__(self,  hits, parameters, allAxis, outOfBounds)   
    
    def plotChRaw(self,cassetteIDs): 
     # """ Acts as a pointer/wrapper for the central library """
     # return libPlotting.plottingHits.plotChRaw(self,cassetteIDs)
 
        if self.flag is True:
              
           normColors = logScaleMap(logScale=False).normColors

           self.plotPHScorr = preparePlotMatrix(1003, 1, len(cassetteIDs), figSize=(20, 20))

           self.plotPHScorr.figHandle.suptitle('Pulse Heigth Spectrum - Correlation A-B')
        
           for k, cass in enumerate(cassetteIDs):
    
                selc  = self.hits.Cassette  == cass
                
                PHScorr  = hh.histog(self.outOfBounds).hist2D(self.allAxis.axEnergy.axis,self.hits.ADC[selc],self.allAxis.axEnergy.axis,self.hits.ADC1[selc]) 
               
                self.plotPHScorr.axHandle[0][k].imshow(PHScorr,aspect='auto',norm=normColors,interpolation='none',extent=[self.allAxis.axEnergy.start,self.allAxis.axEnergy.stop,self.allAxis.axEnergy.start,self.allAxis.axEnergy.stop], origin='lower',cmap='jet')
                
                self.plotPHScorr.axHandle[0][k].set_title('ID '+str(cass))
                self.plotPHScorr.axHandle[0][k].set_xlabel('pulse height A (a.u.)')
                self.plotPHScorr.axHandle[0][k].set_box_aspect(1)
                if k == 0:
                    self.plotPHScorr.axHandle[0][k].set_ylabel('pulse height B (a.u.)')


    def plotTimeStamps(self,cassetteIDs): 
        if self.flag is True:
            print(f"\n\t \033[1;33mWARNING: Hits time stamp not supported for {self.config.DETparameters.type} -> SKIPPING PLOT (use raw readouts timestamp plots).\033[0m")

    
    def plotTimeStampsVSCh(self,cassetteIDs): 
        if self.flag is True:
            print(f"\n\t \033[1;33mWARNING: Hits time stamp VS Ch not supported for {self.config.DETparameters.type} -> SKIPPING PLOT (use raw readouts timestamp plots).\033[0m")



   
################################################################################################
################################################################################################


class plottingEvents():
  
    def __init__(self, events, parameters, allAxis, coincidenceWS_ONOFF=False, outOfBounds = True):
        
        self.parameters  = parameters
        self.config      = parameters.config
        self.allAxis     = allAxis
        self.coincidenceWS_ONOFF = coincidenceWS_ONOFF
        self.outOfBounds = outOfBounds 
        
        checkke = checkEventsClass(events)
        self.events = checkke.events
        self.flag   = checkke.flag

        # if self.flag is True:
        #     if self.coincidenceWS_ONOFF is True:
        #         print('\t building histograms ... coincidence W/S ON for ToF and Lambda ...')
        #         self.selc = events.positionS >= 0 
        #     else:
        #         print('\t building histograms ... coincidence W/S OFF for ToF and Lambda ...')
        #         self.selc = events.positionS >= - np.inf
        
    def plotInstantaneousRate(self,cassetteIDs): 
        if self.flag is True:
           
           self.plotInst = preparePlotMatrix(209, 1, len(cassetteIDs))
           
           self.plotInst.figHandle.suptitle('Instantaneous Rate')
           
           for k, cass in enumerate(cassetteIDs):
               
               selc  = self.events.Cassette  == cass
               diffeTime = np.diff(self.events.timeStamp[selc])
               
               # self.allAxis.axInstRate.axis = self.allAxis.axInstRate.axis*1000
               
               histRate = hh.histog(outBounds=False).hist1D(self.allAxis.axInstRate.axis,diffeTime/1000000000) 

               self.plotInst.axHandle[0][k].step(self.allAxis.axInstRate.axis*1e6,histRate,'k',where='mid',label='w')
               self.plotInst.axHandle[0][k].set_xlabel('delta time between events (us)')
               self.plotInst.axHandle[0][k].set_title('Tube ID '+str(cass))
               if k == 0:
                   self.plotInst.axHandle[0][k].set_ylabel('num of events')
                   
    def plotPHS(self, cassetteIDs, logScale = False):
       
       if self.flag is True:
      
           self.plotPHS = preparePlotMatrix(601, 1, len(cassetteIDs))
           
           self.plotPHS.figHandle.suptitle('Pulse Heigth Spectra')
           

           for k, cass in enumerate(cassetteIDs):
      
                   selc  = self.events.Cassette  == cass

                   PHSw  = hh.histog(self.outOfBounds).hist1D(self.allAxis.axEnergy.axis,self.events.PHW[selc]) 
              
                   self.plotPHS.axHandle[0][k].step(self.allAxis.axEnergy.axis,PHSw,'b',where='mid')
          
                   self.plotPHS.axHandle[0][k].set_title('Tube ID '+str(cass))
                   if k == 0:
                       self.plotPHS.axHandle[0][k].set_ylabel('counts')
                   self.plotPHS.axHandle[0][k].set_xlabel('pulse height (a.u.)')                
                 
    def plotMultiplicity(self, cassettes):   
        if self.flag is True:
            print(f"\n\t \033[1;33mWARNING: Multiplicity not supported for {self.config.DETparameters.type} -> SKIPPING PLOT.\033[0m")
               
                 
    def plotPHScorrelation(self, cassetteIDs, logScale = False):
        if self.flag is True:
             print(f"\t \033[1;33mWARNING: PHS correlation not supported for {self.config.DETparameters.type} -> SKIPPING PLOT (use raw hits for ADC VS ADC).\033[0m")

    def plotXLambda(self,logScale=False, absUnits = False): 
        if self.flag is True:
             print(f"\t \033[1;33mWARNING: X VS Wavelength not supported for {self.config.DETparameters.type} -> SKIPPING PLOT.\033[0m")

          
    def plotToF(self, cassetteIDs):
        
        if self.flag is True:
           
          self.plotTT = preparePlotMatrix(333, 1, len(cassetteIDs))
          
          self.plotTT.figHandle.suptitle('ToF distr per tube')
          
          for k, cass in enumerate(cassetteIDs):
               
               selc  = self.events.Cassette  == cass
               
               histTT  = hh.histog(self.outOfBounds).hist1D(self.allAxis.axToF.axis,self.events.ToF[selc]/1e9) 

               self.plotTT.axHandle[0][k].step(self.allAxis.axToF.axis*1e3,histTT,'b',where='mid')
               self.plotTT.axHandle[0][k].set_xlabel('ToF (ms)')
               self.plotTT.axHandle[0][k].set_title('Tube D '+str(cass))
               if k == 0:
                   self.plotTT.axHandle[0][k].set_ylabel('counts')
            
               
    def plotLambda(self, cassetteIDs):
          
        if self.flag is True:
           
          self.plotWA = preparePlotMatrix(339, 1, len(cassetteIDs))
          
          self.plotWA.figHandle.suptitle('Wavelength distr per tube')
          
          for k, cass in enumerate(cassetteIDs):
               
               selc  = self.events.Cassette  == cass
               
               histWA  = hh.histog(self.outOfBounds).hist1D(self.allAxis.axLambda.axis,self.events.wavelength[selc]) 
    
               self.plotWA.axHandle[0][k].step(self.allAxis.axLambda.axis,histWA,'r',where='mid')
              
               self.plotWA.axHandle[0][k].set_xlabel('wavelength (A)')
               self.plotWA.axHandle[0][k].set_title('Tube ID '+str(cass))
               if k == 0:
                   self.plotWA.axHandle[0][k].set_ylabel('counts')

       
    def plotXYToF(self, logScale = False, absUnits = False, orientation = 'vertical'):


        # READ ME 
        # here both plot 1D each tube and 2D all tubes together 
        # split at 50% the hist for visualiziation miracles 
        #  also split in different palces depending on self.config.DETparameters.type
        #  see below splitHistAccordingToDET
        
        if self.flag is True:
            
            cassetteIDs = self.config.DETparameters.cassInConfig
            
            normColors = logScaleMap(logScale).normColors
            
            fig2D, ax1   = plt.subplots(num=101,figsize=(6,6), nrows=1, ncols=1) 
            fig1D        = preparePlotMatrix(104, 1, len(cassetteIDs))
            figXtof, ax2 = plt.subplots(num=102,figsize=(6,6), nrows=1, ncols=1) 
  
            if absUnits == False:
                
                h2D, _, _ = hh.histog(self.outOfBounds).histXYZ(self.allAxis.axWires.axis, self.events.positionW, self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axToF.axis, self.events.ToF/1e9)
        
                _, _, hToF = hh.histog(self.outOfBounds).histXYZ(self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axToF.axis, self.events.ToF/1e9)
        
                for k, cass in enumerate(cassetteIDs):
                    sele = self.events.Cassette == cass
                    h1D = hh.histog(self.outOfBounds).hist1D(self.allAxis.axWires.axis, self.events.positionW[sele])
                    fig1D.axHandle[0][k].step(self.allAxis.axWires.axis,h1D,'k',where='mid')
                    fig1D.axHandle[0][k].set_xlabel('Position (a.u.)')
                    fig1D.axHandle[0][k].set_title('Tube ID '+str(cass))
                    if logScale is True:
                       fig1D.axHandle[0][k].set_yscale('log')
                    if k == 0:
                        fig1D.axHandle[0][k].set_ylabel('counts')
     
                pos2  = ax2.imshow(hToF,aspect='auto',norm=normColors,interpolation='nearest',extent=[self.allAxis.axToF.start*1e3,self.allAxis.axToF.stop*1e3,self.allAxis.axStrips.start-0.5,self.allAxis.axStrips.stop+0.5], origin='lower',cmap='viridis')       
                ax2.set_yticks(self.allAxis.axStrips.axis)
                ax2.set_yticklabels(self.allAxis.axStrips.axis.astype(int))
                
                ax2.set_ylabel('Tube ID')
                ax2.set_xlabel('ToF (ms)')
                figXtof.suptitle('DET ToF')
                
                if orientation == 'vertical':
                    
                    pos1  = ax1.imshow(np.rot90(h2D,1),aspect='auto',norm=normColors,interpolation='none',extent=[self.allAxis.axStrips.start-0.5,self.allAxis.axStrips.stop+0.5,self.allAxis.axWires.stop,self.allAxis.axWires.start], origin='upper',cmap='viridis')
                    ax1.set_xticks(self.allAxis.axStrips.axis)
                    ax1.set_xticklabels(self.allAxis.axStrips.axis.astype(int))
                    #  temporary fix because LogNorm crashes tihe imShow when Log 
                    try:
                        fig2D.colorbar(pos1, ax=ax1, orientation="vertical",fraction=0.07,anchor=(1.0,0.0))
                    except:
                        print('\n --> \033[1;33mWARNING: Cannot plot XY in Log scale, changed to linear\033[1;37m',end='')
                    
                    ax1.set_ylabel('Position (a.u.)')
                    ax1.set_xlabel('Tube ID')
                    fig2D.suptitle('DET image')
            
                
        
                elif orientation == 'horizontal':  
                    
                    pos1  = ax1.imshow(h2D,aspect='auto',norm=normColors,interpolation='none',extent=[self.allAxis.axWires.start,self.allAxis.axWires.stop,self.allAxis.axStrips.stop+0.5,self.allAxis.axStrips.start-0.5], origin='upper',cmap='viridis')
                    ax1.set_yticks(self.allAxis.axStrips.axis)
                    ax1.set_yticklabels(self.allAxis.axStrips.axis.astype(int))
                    try:
                        fig2D.colorbar(pos1, ax=ax1, orientation="vertical",fraction=0.07,anchor=(1.0,0.0))
                    except:
                        print('\n --> \033[1;33mWARNING: Cannot plot XY in Log scale, changed to linear\033[1;37m',end='')
                        
                    ax1.set_xlabel('Position (a.u.)')
                    ax1.set_ylabel('Tube ID')
                    fig2D.suptitle('DET image')
        
        
            elif absUnits == True:
                
                h2D, _, _ = hh.histog(self.outOfBounds).histXYZ(self.allAxis.axWires_mm.axis, self.events.positionWmm, self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axToF.axis, self.events.ToF/1e9)
        
                _, _, hToF = hh.histog(self.outOfBounds).histXYZ(self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axStrips.axis, self.events.positionS, self.allAxis.axToF.axis, self.events.ToF/1e9)
        
                for k, cass in enumerate(cassetteIDs):
                    
                    sele = self.events.Cassette == cass
                    
                    h1D = hh.histog(self.outOfBounds).hist1D(self.allAxis.axWires_mm.axis, self.events.positionWmm[sele])
                    fig1D.axHandle[0][k].step(self.allAxis.axWires_mm.axis,h1D,'k',where='mid')
                    fig1D.axHandle[0][k].set_xlabel('Position (mm)')
                    fig1D.axHandle[0][k].set_title('Tube ID '+str(cass))
                    if logScale is True:
                       fig1D.axHandle[0][k].set_yscale('log')
                    if k == 0:
                        fig1D.axHandle[0][k].set_ylabel('counts')
     
                pos2  = ax2.imshow(hToF,aspect='auto',norm=normColors,interpolation='nearest',extent=[self.allAxis.axToF.start*1e3,self.allAxis.axToF.stop*1e3,self.allAxis.axStrips.start-0.5,self.allAxis.axStrips.stop+0.5], origin='lower',cmap='viridis')       
                ax2.set_yticks(self.allAxis.axStrips.axis)
                ax2.set_yticklabels(self.allAxis.axStrips.axis.astype(int))
                
                ax2.set_ylabel('Tube ID')
                ax2.set_xlabel('ToF (ms)')
                figXtof.suptitle('DET ToF')
                
                if orientation == 'vertical':
                    
                    pos1  = ax1.imshow(np.rot90(h2D,1),aspect='auto',norm=normColors,interpolation='none',extent=[self.allAxis.axStrips.start-0.5,self.allAxis.axStrips.stop+0.5,self.allAxis.axWires_mm.stop,self.allAxis.axWires_mm.start], origin='upper',cmap='viridis')
                    ax1.set_xticks(self.allAxis.axStrips.axis)
                    ax1.set_xticklabels(self.allAxis.axStrips.axis.astype(int))
                    #  temporary fix because LogNorm crashes tihe imShow when Log 
                    try:
                        fig2D.colorbar(pos1, ax=ax1, orientation="vertical",fraction=0.07,anchor=(1.0,0.0))
                    except:
                        print('\n --> \033[1;33mWARNING: Cannot plot XY in Log scale, changed to linear\033[1;37m',end='')
                    
                    ax1.set_ylabel('Position (mm)')
                    ax1.set_xlabel('Tube ID')
                    fig2D.suptitle('DET image')
            
                
        
                elif orientation == 'horizontal':  
                    
                    pos1  = ax1.imshow(h2D,aspect='auto',norm=normColors,interpolation='none',extent=[self.allAxis.axWires_mm.start,self.allAxis.axWires_mm.stop,self.allAxis.axStrips.stop+0.5,self.allAxis.axStrips.start-0.5], origin='upper',cmap='viridis')
                    ax1.set_yticks(self.allAxis.axStrips.axis)
                    ax1.set_yticklabels(self.allAxis.axStrips.axis.astype(int))
                    try:
                        fig2D.colorbar(pos1, ax=ax1, orientation="vertical",fraction=0.07,anchor=(1.0,0.0))
                    except:
                        print('\n --> \033[1;33mWARNING: Cannot plot XY in Log scale, changed to linear\033[1;37m',end='')
                        
                    ax1.set_xlabel('Position (mm)')
                    ax1.set_ylabel('Tube ID')
                    fig2D.suptitle('DET image')
            
            
            

            
            
            
    def splitHistAccordingToInstr(self):
          
        # TO BE FINISHED .....
        
         instrument = self.config.DETparameters.intrument
         
         if instrument == 'CSPEC':
             pass
         
         elif instrument == 'BIFROST':
             print('\n --> \033[1;33mWARNING: Not yet supported to split plots\033[1;37m',end='')
             
             select  = self.events.positionW <= 0.33
             select2 = self.events.positionW > 0.66
             
         elif instrument == 'MIRACLES':
             
              select = self.events.positionW <= 0.5
          
              self.newX1 = self.events.positionW[select]
              self.newX2 = self.events.positionW[~select]

 
            
###############################################################################
###############################################################################

if __name__ == '__main__' :
    
    
    
    plt.close("all")
    
    confFile  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'
    fileName  = "MIRACLES24.json"
    # fileName  = "AMOR.json"
    # fileName  = "MGEMMA.json"
    fileName  = "MIRACLES2bis.json"
    fileName  = "CSPEC.json"

    config = maps.read_json_config(confFile+fileName)
    
    parameters  = para.parameters(confFile+fileName)
    parameters.loadConfigAndUpdate(config)
    
    ###############################################################################
    ### WAVELENGTH PARAMETERS:
    #################################

    ### distance in mm from chopper and wires 0 of detector
    parameters.wavelength.distance = 8000

    ##ON/OFF
    parameters.wavelength.calculateLambda = True

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
    # parameters.plotting.showStat = 'individualStat'

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
    parameters.plotting.histogOutBounds = False

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
    
    allAxis = hh.allAxis()
    allAxis.createAllAxis(parameters)
    
    filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
    # file = 'MG_2col_2clusters.pcapng'
    file = 'miracles_trig2.pcapng'
    # file = 'channel1.pcapng'
      
    # file = 'MG_2col_1cluster.pcapng'
    
    # file = 'miracles_source_mask_red.pcapng'
    
    # file = 'miracles_source_on_left_red.pcapng'

    filePathAndFileName = filePath+file
    
    NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz
    
    pcapng = pcapr.pcapng_reader(filePathAndFileName)
    
    # pcapr.checkIfDataIsSupported(pcapng.flagSupported)

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
 
    plread = plottingReadouts(readouts, parameters, allAxis, outOfBounds=True)
    
    # plread.plotChoppResets()
    
    # plread.plotChRaw(parameters.config.DETparameters.cassInConfig)
    
    # plread.plotTimeStamps(parameters.config.DETparameters.cassInConfig)

    # plread.plotADCvsCh(parameters.config.DETparameters.cassInConfig)
    
    plread = plottingHits(hits, parameters, allAxis, outOfBounds=True)
    
    # plread.plotChRaw(parameters.config.DETparameters.cassInConfig)
    
    
    # plread.plotTimeStamps(parameters.config.DETparameters.cassInConfig)

    
    # plread.plotTimeStampsVSCh(parameters.config.DETparameters.cassInConfig)

    plread = plottingEvents(events, parameters, allAxis, coincidenceWS_ONOFF=True, outOfBounds = True)

    # plread.plotInstantaneousRate(param3eters.config.DETparameters.cassInConfig)
    
    # plread.plotPHS(parameters.config.DETparameters.cassInConfig, logScale = False)
    
    # plread.plotPHScorrelation(parameters.config.DETparameters.cassInConfig, logScale = False)
    
    # plread.plotMultiplicity(parameters.config.DETparameters.cassInConfig)
    
    # plread.plotXLambda()
         
    # plread.plotToF(parameters.config.DETparameters.cassInConfig)

    # plread.plotLambda(parameters.config.DETparameters.cassInConfig)
    
    parameters.plotting.plotABSunits = False
       
    parameters.config.DETparameters.orientation = 'vertical'
    # parameters.config.DETparameters.orientation = 'horizontal'
    plread.plotXYToF(logScale = parameters.plotting.plotIMGlog, absUnits = parameters.plotting.plotABSunits, orientation = parameters.config.DETparameters.orientation)
      
      
   

    # allAxis = hh.allAxis()
    # allAxis.createAllAxis(parameters)
    

        
    ##################


    
    
    
    