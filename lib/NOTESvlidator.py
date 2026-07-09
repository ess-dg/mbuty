#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 11:34:14 2026

@author: francescopiscitelli
"""
import importlib.metadata
###############################################################################

class checkPythonVersion():
        # check version
        if sys.version_info < (3,12):
           print('\n \033[1;31mPython version too old, use at least Python 3.8! \033[1;37m\n')
           print(' ---> Exiting ... \n')
           print('------------------------------------------------------------- \n')
           time.sleep(2)
           sys.exit()
           
           
###############################################################################


class checkPackageInstallation():
    
    def __init__(self):
    
        # self.installed = {pkg.key for pkg in pkg_resources.working_set}
  
        # for pyhton <3.10
        if sys.version_info < (3,12):
            self.installed = {dist.metadata['Name'] for dist in importlib.metadata.distributions()}
        elif sys.version_info >= (3,12):
            self.installed = {dist.name for dist in importlib.metadata.distributions()}
        
        self.normalizedInstalled = {name.lower().replace('_', '-') for name in self.installed}
        
    def checkPackagePcap(self):
 
           required = {'python-pcapng'}
           
           normalizedRequired = {name.lower().replace('_', '-') for name in required}
           
           missing = normalizedRequired - self.normalizedInstalled
           
           if missing: 
               
               print('\n \033[1;31mpython-pcapng package missing, install with command: pip install python-pcapng\033[1;37m\n')
               print(' ---> Exiting ... \n')
               print('------------------------------------------------------------- \n')
               
               time.sleep(2)
           
    def checkPackageKafka(self):
        
         flag = True   
         
         required = {'flatbuffers','configargparse','confluent-kafka'}
         
         normalizedRequired = {name.lower().replace('_', '-') for name in required}
         
         missing = normalizedRequired - self.normalizedInstalled
        
         if missing:
             
             flag = False
             
             for pkg in missing:
             
                 print('\n \033[1;31m{} package missing, install with command: pip install {}\033[1;37m\n'.format(pkg,pkg))
             print(' \033[1;31mor if you are not using kafka streaming mode, switch off mode')
             
             print(' ---> Exiting ... \n')
             print('------------------------------------------------------------- \n')
             time.sleep(2)
             sys.exit()
             
             
         return flag     
           
###############################################################################
class profiling():
    def __init__(self):
        
        self.tProfilingStart = time.time() 

    def restart(self):
        
        self.tProfilingStart = time.time()
        
    def lap(self):       
           tElapsedProfiling = time.time() - self.tProfilingStart
           print('\n lap time: %.2f s' % tElapsedProfiling)
           
    def stop(self):       
           tElapsedProfiling = time.time() - self.tProfilingStart
           print('\nCompleted --> elapsed time: %.2f s' % tElapsedProfiling)
           
   ###############################################################################

     # goes in param validation 
     
if self.parameters.fileManagement.saveReducedFileONOFF is True:       
    if self.parameters.wavelength.calculateLambda == False:
        self.parameters.wavelength.calculateLambda = True
        print('\nLambda calculation turned ON to save reduced DATA')
        
        
if self.parameters.wavelength.calculateLambda  == False:
             self.parameters.wavelength.plotXLambda     = False
             self.parameters.wavelength.plotLambdaDistr = False        
        
        
   def HistNotification(self, plottingInBlocks=False):
       # Check if we need to perform the override
       if plottingInBlocks and self.plotting.histogOutBounds:
           print('\n\t histogram outBounds param set as True (Events out of bounds stored in first and last bin) -> overridden with False since plottingInSections is True')
           self.plotting.histogOutBounds = False
       
       # Standard notification for other states
       elif self.plotting.histogOutBounds:
           print('\n\t histogram outBounds param set as True (Events out of bounds stored in first and last bin)')
       else:
           print('\n\t histogram outBounds param set as False (Events out of bounds not stored in any bin)')
           
           
           
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        