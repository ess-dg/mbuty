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
   
Detector      =  "MB1"
operationMode = 'normal'
cassettes     =  14
orientation   = 'vertical'

flag = checkIfExists(os.path.join(path,f"{Detector}.json"))

generateDefaultDetConfig(path,Detector,cassettes,orientation,operationMode,overwrite=flag)
       
