#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 19 13:07:17 2025

@author: francescopiscitelli
"""


import os 

from lib.libConfigGenerator import generateDefaultDetConfig, checkIfExists

###############################################################################
###############################################################################

currentPath = os.path.abspath(os.path.dirname(__file__))+os.sep

path  = os.path.join(currentPath,'config')
   
DetectorName = "test"
DetectorType = 'MB'
InstrumentName = 'ESTIA'
operationMode = 'normal'
cassettes = 5
orientation = 'vertical'

flag = checkIfExists(os.path.join(path,f"{DetectorName}.json"))

generateDefaultDetConfig(path, DetectorName, DetectorType, InstrumentName, cassettes, orientation, operationMode, overwrite=flag) 

        