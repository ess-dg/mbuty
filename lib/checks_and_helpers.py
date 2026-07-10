#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 11:34:14 2026

@author: francescopiscitelli
"""
import importlib.metadata
import sys, time
###############################################################################

MIN_PYTHON_VERSION = (3, 12)

def checkPythonVersion():
    if sys.version_info < MIN_PYTHON_VERSION:
        print('\n \033[1;31mPython version too old, use at least Python 3.12! \033[1;37m\n')
        print(' ---> Exiting ... \n')
        print('------------------------------------------------------------- \n')
        time.sleep(2)
        sys.exit()

###############################################################################
# Checks for installed packages
###############################################################################
def _getInstalledPackages():
    installed = {dist.name for dist in importlib.metadata.distributions()}
    return {name.lower().replace('_', '-') for name in installed}


def checkPackagePcap():

    normalizedInstalled = _getInstalledPackages()

    required = {'python-pcapng'}
    normalizedRequired = {name.lower().replace('_', '-') for name in required}

    missing = normalizedRequired - normalizedInstalled

    if missing:
        print('\n \033[1;31mpython-pcapng package missing, install with command: pip install python-pcapng\033[1;37m\n')
        print(' ---> Exiting ... \n')
        print('------------------------------------------------------------- \n')
        time.sleep(2)
        sys.exit()

    return True


def checkPackageKafka():

    normalizedInstalled = _getInstalledPackages()

    required = {'flatbuffers', 'configargparse', 'confluent-kafka'}
    normalizedRequired = {name.lower().replace('_', '-') for name in required}

    missing = normalizedRequired - normalizedInstalled

    if missing:
        for pkg in missing:
            print('\n \033[1;31m{} package missing, install with command: pip install {}\033[1;37m\n'.format(pkg, pkg))
        print(' \033[1;31mor if you are not using kafka streaming mode, switch off mode')
        print(' ---> Exiting ... \n')
        print('------------------------------------------------------------- \n')
        time.sleep(2)
        sys.exit()

    return True

###############################################################################
 # Time stats helper          
###############################################################################
class timing():
    def __init__(self):
        self.start_time = time.time()
        self.last_lap   =  time.time()

    def restart(self):
        self.start_time = time.time()
        self.last_lap   = time.time()
        
    def lap(self):       
           elapsed_time  = time.time() - self.last_lap
           self.last_lap = time.time()
           print('\n lap time: %.2f s' % elapsed_time)
           
    def stop(self):       
           stop_time = time.time() - self.start_time
           print('\nCompleted --> elapsed time: %.2f s' % stop_time)
           
        
        
        
        
        
        
        
        
        
        
        