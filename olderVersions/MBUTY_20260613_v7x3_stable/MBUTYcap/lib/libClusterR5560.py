#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 23:02:18 2026

@author: francescopiscitelli
"""


import numpy as np
# import time
# import sys


try:
####### if you run default
    from lib import libCluster 


except ImportError:
    ####### if you run in lib 
    import libCluster 


# NOTE  IF YOU CLUSTERIZE AGAIN THE SAME CASSETTE -> exit

###############################################################################
###############################################################################
""" Acts as a pointer/wrapper for the central library """
events              = libCluster.events
multiplicityCount   = libCluster.multiplicityCount
hitsMON2events      = libCluster.hitsMON2events
checkCassIDs        = libCluster.checkCassIDs
###############################################################################
###############################################################################

class clusterHits():
    
     def __init__(self, hits, showStat):
        """ Acts as a pointer/wrapper for the central library """
        return libCluster.clusterHits.__init__(self, hits, showStat) 
         
         
     def clusterize1cassette(self, cassette1ID, timeWindow, text = 'Tube'):
         
         present = checkCassIDs.checkIfPresentInHits(self.hits,cassette1ID,text=text)
         
         # init an empty event obj
         self.events1Cass  = libCluster.events()
         
         # 0 is counter good clusters , 1 is rejected 
         self.rejCounter = np.zeros((3),dtype='int64')
         
         if present:
 
            print('\n \t calculating position ... Tube ID ',str(cassette1ID),' ',end='')
                    
            selectCassette = self.hits.Cassette == cassette1ID
        
            NumCandidates = np.shape(self.hits.timeStamp[selectCassette])[0]
        
            self.TPHM = np.zeros((NumCandidates,7),dtype='int64')  
            self.PO   = np.zeros((NumCandidates,2),dtype='float64')
        
        
            self.TPHM[:,0]  = self.hits.timeStamp[selectCassette].astype(int) # timeStamp      
            self.TPHM[:,1]  = self.hits.PulseT[selectCassette].astype(int)    # PulseT   
            self.TPHM[:,2]  = self.hits.PrevPT[selectCassette].astype(int)    # PrevPT
            self.TPHM[:,3]  = 1  # mult0
            self.TPHM[:,4]  = 1  # mult1
            self.TPHM[:,5]  = (self.hits.ADC[selectCassette] + self.hits.ADC1[selectCassette]).astype(int)
            self.TPHM[:,6]  = 0    # PH strips
            
            nonzero_mask = (self.TPHM[:, 5] != 0)
            self.PO[nonzero_mask, 0]  = np.round(self.hits.ADC[selectCassette][nonzero_mask] / self.TPHM[nonzero_mask, 5], 3)
            self.PO[~nonzero_mask, 0] = -1
            # self.PO[:,0]    = np.round(self.hits.ADC[selectCassette]/(self.TPHM[:,5]),3).astype(float)
            self.PO[:,1]    = self.hits.Cassette[selectCassette].astype(float)  # pos strips is tube ID 
        
            # denom = self.TPHM[:,5]
            # self.PO[:, 0] = np.divide(self.hits.ADC[selectCassette], denom, 
            #               out=np.zeros_like(denom), 
            #               where=denom!=0)
            # self.PO[:, 0] = np.round(self.PO[:, 0], 3).astype(float)
            #################################
            
            # One could do this below to avoid pile up ....
            
        
            # Time window is in s but we all do here in ns int64
            # timeWindow converted in ns
            timeWindow_ns        = int(round(timeWindow*1e9))
        
            TimeWindowRecursive  = int(round(timeWindow_ns*1.01))
            # TimeWindowMax        = int(round(TimeWindowRecursive*1.5))

            # ##########
                     
            deltaTime = np.diff(self.hits.timeStamp[selectCassette])   #1st derivative of time 
            deltaTime = np.concatenate(([0],deltaTime),axis=0) #add a zero at top to restore length of vector
            
            self.deltaTimeClusterWS = -1*np.ones((NumCandidates,3),dtype='int64')
            self.deltaTimeClusterWS[:,0] = cassette1ID*np.ones((NumCandidates),dtype='int64')
            self.deltaTimeClusterWS[:,1] = deltaTime
            self.deltaTimeClusterWS[:,2] = 1 # always 1D
        
            clusterlogic = (np.absolute(deltaTime) <= TimeWindowRecursive) #is zero when a new cluster starts 
            
            clusterlogic[0] = False #first element is fake and need to be reset 
            
            # index = np.argwhere(clusterlogic == False) #find the index where a new cluster may start 
            
            rejected =  clusterlogic == True   #remove rejected from data in rejCoiunter[4] it is when only strips and wire and sgtrip mult is 0, whole row in POPH is 0 actually 
                
            self.TPHM     = self.TPHM[np.logical_not(rejected),:]    #remove rejected from data
            self.PO       = self.PO[np.logical_not(rejected),:]      #remove rejected from data
            
            
            ##########
            # check if there are some 0 PH and remove
            theZeroADCOnes = self.TPHM[:,5] == 0
            
            self.rejCounter[2] = np.sum(theZeroADCOnes)
            
            if np.sum(theZeroADCOnes) > 0:
                print('\n --> \033[1;33mWARNING: Some Pulse Height Zero found in clustering -> removed from events.\033[1;37m',end='')

            self.TPHM     = self.TPHM[np.logical_not(theZeroADCOnes),:]    #remove nan from data
            self.PO       = self.PO[np.logical_not(theZeroADCOnes),:]      #remove nan from data
            
            ##########

            ##########
            # check if there are some NaN 
            theNanOnes = np.logical_or(np.isnan(self.PO[:,0]),np.isnan(self.PO[:,1])) 
            
            self.rejCounter[2] = self.rejCounter[2] + np.sum(theNanOnes)
            
            if np.sum(theNanOnes) > 0:
                print('\n --> \033[1;33mWARNING: Some NaN (invalid value) values found in clustering -> removed from events.\033[1;37m',end='')

            self.TPHM     = self.TPHM[np.logical_not(theNanOnes),:]    #remove nan from data
            self.PO       = self.PO[np.logical_not(theNanOnes),:]      #remove nan from data
            
            ##########
            
            self.rejCounter[0] = NumCandidates
            self.rejCounter[1] = np.sum(clusterlogic) 
            
            self.events1Cass.transform(cassette1ID, self.TPHM, self.PO)
            
            self.events1Cass.Nevents = NumCandidates
            self.events1Cass.NeventsNotRejAll = NumCandidates - self.rejCounter[1] - self.rejCounter[2]
            self.events1Cass.NeventsNotRej2D  = NumCandidates - self.rejCounter[1] - self.rejCounter[2]
    
            ################################
            if self.showStat == 'individualStat':
                self.someStat(self.events1Cass,self.rejCounter)
            ################################
    
            del self.TPHM
            del self.PO
                
                # if NumClusters == len(self.hits.timeStamp[selectCassette]):
                #     print('--> \033[1;33mWARNING: time window for clustering might be too small!\033[1;37m',end='')
                #     time.sleep(1)
                
   
        
     
     def someStat(self, events, rejCounter):
         
            Ncandidates      = np.sum(events.Nevents)
            NeventsNotRejAll = np.sum(events.NeventsNotRejAll)
            # some stats  
            
            # multi  = multiplicityCount(events)
                      
            if NeventsNotRejAll != 0 :
                print("\n\n\t N of candidates: %d -> not rejected events %d (%.1f%%), rejected because of pile up %d (%.1f%%), rejected for 0 ADC or NaN %d (%.1f%%)" % (Ncandidates,NeventsNotRejAll,100*NeventsNotRejAll/Ncandidates,rejCounter[1],100*rejCounter[1]/Ncandidates,rejCounter[2],100*rejCounter[2]/Ncandidates))
               
            # else:
            #         print("\n\t N of candidates: %d -> not rejected events %d (2D: %d, 1D: %d)" % (Ncandidates,NeventsNotRejAll,rejCounter[0],rejCounter[2]))
                    
                


     def clusterizeManyCassettes(self, cassettesIDs, timeWindow, detType='He3'):
            
             checkCassIDs.checkIfRepeatedIDs(cassettesIDs)
             
             self.rejCounterAll = np.zeros((3),dtype='int64')

             for cc in cassettesIDs:
                 
                 self.clusterize1cassette(cc, timeWindow, text='Tube')

                 self.deltaTimeClusterWSall = np.concatenate((self.deltaTimeClusterWSall,self.deltaTimeClusterWS),axis=0)

                 self.events.append(self.events1Cass)
                 
                 self.rejCounterAll += self.rejCounter
                 
                 
             del self.events1Cass   
             
             if self.showStat == 'globalStat':
                 self.someStat(self.events,self.rejCounterAll)
            
  

         

###############################################################################
###############################################################################

if __name__ == '__main__':
    
   confFile  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'+"MIRACLES2.json"
   # filePathD = './'+"VMM3a_Freia.pcapng"

   config = maps.read_json_config(confFile)
   
   filePath = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file = 'MG_2col_2clusters.pcapng'
   file = 'miracles_trig2.pcapng'
     
   # file = 'MG_2col_1cluster.pcapng'
   
   file = 'miracles_source_mask.pcapng'

   filePathAndFileName = filePath+file
   
   NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz
   
   pcapng = pcapr.pcapng_reader(filePathAndFileName)
   
   pcapr.checkIfDataIsSupported(pcapng.flagSupported)

   readouts = pcapng.readouts
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   

   md  = maps.mapDetector(readouts, config)
   md.mappAllCassAndChannelsGlob()
   hits = md.hits
   hitsArray  = hits.concatenateHitsInArrayForDebug()
   
   
   cc = clusterHits(hits,showStat='globalStat')
   cc.clusterizeManyCassettes(config.DETparameters.cassInConfig, timeWindow=1e-6)
   events = cc.events
   deltaTimeWS = cc.deltaTimeClusterWSall
   
   eventsArray = events.concatenateEventsInArrayForDebug()
   
   