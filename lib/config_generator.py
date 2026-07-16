#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 19 11:59:32 2025

@author: francescopiscitelli
"""

import json
import os
import sys
import time 
import numpy as np 

# import ipaddress

_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from lib.config_validator import match_instrument_and_detector

# from lib.colors import WARN, ERR, INFO, OK, RESET


###############################################################################
###############################################################################

# FOR MB
# The helper function (renamed from a method)
def _generateTopologyMB(num_units):
    unit_config = []
    ring = 0
    hybrid = 0
    for i in range(num_units):
        unit_config.append({
            "ID": i,
            "ring": ring,
            "fen": 0,
            "hybrid": hybrid,
            "serial": ''
        })
        hybrid += 1
        if hybrid >= 5:
            hybrid = 0
            ring += 1
    return unit_config


# FOR MG
# The helper function (renamed from a method)
def _generateTopologyMG(num_units):
    unit_config = []
    ring    = 0
    hybridW = 0
    hybridG = 1
    for i in range(num_units):
        unit_config.append({
            "ID": i,
            "ring": ring,
            "fen": 0,
            "hybridW": hybridW,
            "hybridG": hybridG,
            "serialHW": '',
            "serialHG": ''
        })
        hybridW += 2
        hybridG += 2
        if hybridG >= 4:
            ring += 1
            hybridW = 0
            hybridG = 1
            
    return unit_config



# FOR SKADI
# The helper function (renamed from a method)
def _generateTopologySKADI(num_units):
    unit_config = []
    # ring     = 0
    # IP       = ipaddress.IPv4Address("192.168.0.1") 
    IP         = 100
    # sysID    = 0
    rotation = 0
    # bank     = 0
    offset   = 1000
    for i in range(num_units):
        unit_config.append({
            "ID": offset+i,
            "IP": IP,
            # "IP": str(IP),
            "rotation": rotation,
            # "bank":     bank,
        })
        IP = IP+1
        # ring += 1
        # if np.mod(i,2) == 0 :
        #     rotation = 'flip'
        # else:
        #     rotation = 'normal'
      
    return unit_config


# FOR He3
# The helper function (renamed from a method)
def _generateTopologyHe3(num_units):
    unit_config = []
    ring    = 0
    tube    = 0
    for i in range(num_units):
        unit_config.append({
            "ID": i,
            "ring": ring,
            "fen": 0,
            "tube": tube,
        })
        tube += 1
        if i >= 11 :
            ring = 1
        if  i == 11 :    
            tube = 0
     
    return unit_config

# FOR NMX
# The helper function (renamed from a method)
def _generateTopologyNMX(num_units):
    unit_config = []
    # ring     = 0
    fenX      = 0
    fenY      = 1
    hybridsX = [0,1,2,3,4]
    hybridsY = [0,1,2,3,4]
    # start_ID = 10
    for i in range(num_units):
        currentID = (10*(i//4 + 1) + i % 4)
   
        
        unit_config.append({
            "ID": currentID,
            "ring": i,
            "fenX":  fenX,
            "fenY":  fenY,
            "hybridsX": hybridsX,
            "hybridsY": hybridsY,
        })
        # ring += 1
        # if np.mod(i,4) == 0:
        #     start_ID += 10
  
            
    return unit_config
###############################################################################
###############################################################################

# The main function to generate the config file
def generateDefaultDetConfig(path, detectorName, detectorType, instrumentName, units, orientation='horizontal' ,operationMode="normal",  overwrite=False):
    """
    Generates a default detector configuration JSON file based on provided parameters.

    Args:
        path (str): The directory where the config file will be saved.
        Detector (str): The detector type (e.g., "BAM").
        units (int): The number of units.
        orientation (str, optional): Detector orientation ("horizontal" or "vertical"). Defaults to 'horizontal'.
        operationMode (str, optional): Operational mode ("normal", "HighGain", "LowNoise"). Defaults to "normal".

    Returns:
        str: The full path to the generated JSON file, or None if an error occurred.
    """
    
    flag = match_instrument_and_detector(detectorType,instrumentName)

    file_name = _createFileName(detectorName)
    
    # print(file_name)

    filePathName = os.path.join(path, file_name)
    # Check for existing file
    if os.path.exists(filePathName) and not overwrite:
        print(f"File already exists: {filePathName} — skipping write.")
        return None
    
    # common monitor field
    monitor = [
        {"ID": 99, "hardwareType": "generic", "connectionType": "ring", "ring": 11, "channel": 0}
    ]
    
    # common fields 
    data = {
        "detectorName": detectorName,
        "detectorType": detectorType,
        "instrumentName": instrumentName,
        "units": units,
        "orientation": orientation,
     }
    
    if detectorType == 'MB':
        # Call the helper function
        topology = _generateTopologyMB(units)
        data.update({
            "operationMode": operationMode,
            "topology": topology,
            # "channelMapping": [{"wireASIC": 1, "stripASIC": 0}],
            "wires": 32,
            "strips": 64,
            "wirePitch_mm": 4,
            "stripPitch_mm": 4,
            "bladesInclination_deg": 5.1,
            "offset1stWires_mm": 10.5,
            "monitor" : monitor,
        })
        
        
        filePathName = makeFile(path,filePathName,data)
            
    elif  detectorType == 'MG':  
        
        # Call the helper function
        topology = _generateTopologyMG(units)
        data.update({
            "operationMode": operationMode,
            "topology": topology,
            "wires": 120,
            "grids": 12,
            "wirePitchX_mm": 22,
            "wirePitchZ_mm": 10,
            "gridPitchY_mm": 25,
            "wiresPerRow": 20,
            "angularOffset_deg": 10,
            "linearOffset1stWires_mm": 80,
            "monitor" : monitor,
        })
        
    
        filePathName = makeFile(path,filePathName,data)
    
    elif  detectorType == 'SKADI':  
        
        # Call the helper function
        topology = _generateTopologySKADI(units)
        data.update({
            "topology": topology,
            "tilesPerRow": 10,
            "pix"        : 16,
            "pix_size_mm": 5,
            "gapX_mm": 4,
            "gapY_mm": 4,
            "monitor" : monitor,
        })
    
        filePathName = makeFile(path,filePathName,data)
        
    
    elif  detectorType == 'He3':  
        
        # Call the helper function
       topology = _generateTopologyHe3(units)
       data.update({
            "topology": topology,
            "positionBins": 256,
            "tubesPerRow": 8,
            "tubeLength": 300,
            "tubeSpacing": 10,
            "monitor" : monitor,
        })
    
       filePathName = makeFile(path,filePathName,data)
       
    elif  detectorType == 'NMX':  
           
           # Call the helper function
          topology = _generateTopologyNMX(units)
          data.update({
               "topology": topology,
               "strips":   640,
               "monitor" : monitor,
           })
       
          filePathName = makeFile(path,filePathName,data)
       
    else:
        
        print('\n \t \033[1;33mWARNING: Detector type {} not supported (only MB, MG and He3 accepted) --> exiting!\033[1;37m\n'.format(detectorType))
        time.sleep(2)
        sys.exit()
        
    return filePathName  , flag 
##########################

def makeFile(path,filePathName,data):
    
    try:
        os.makedirs(path, exist_ok=True) # Ensure directory exists
        with open(filePathName, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Successfully config file generated '{filePathName}'")
        return filePathName # Return the path as required by the GUI
    except IOError as e:
        print(f"Error writing config file {filePathName}: {e}")
        return None # Return None on error

def _createFileName(detname):
    
    if detname.lower().endswith(".json"):
        # print('\n \t \033[1;33mWARNING: ---> Double extension detected in ',{detname},'! Please check your file naming convention.\033[1;37m\n')
        # The user already gave us a .json, so we don't need to add it
        final_filename = detname
    else:
        # The user didn't include it, so we add it safely
        final_filename = f"{detname}.json"

    # 3. Combine with your target directory
    return final_filename
    
 
    

###############################################################################
###############################################################################

def checkIfExists(pathFile):
    
    exists = os.path.exists(pathFile)

    if exists is True:

        print('\n --> \033[1;33mWARNING: File: '+pathFile+'already exist.\033[1;37m')
        
        inp = input('     press (y) to overwrite or (n or enter) to quit ')
        
        if inp == 'y':
            writeFile  = True
            print(' --> overwriting file.')
        else:    
            writeFile  = False
            print(' --> exiting.')
            time.sleep(2)
            sys.exit()
    else:
          
          writeFile = True
          
    return writeFile   




###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcapWorkInProgress/config/'
    
    path = '/Users/francescopiscitelli/git_repos/mbuty/config/'
    
    # path = '/Users/francescopiscitelli/git_repos/mbuty/MBUTYcap/config/'

    # detectorName = "AMOR"
    # detectorType = 'MB'
    # instrumentName = 'AMOR'
    
    # detectorName = "CAB"
    # detectorType = 'MB'
    # instrumentName = 'AMOR'
    
    # detectorName = "CSPEC"
    # detectorType = 'He3'
    # instrumentName = 'CSPEC'
    
    # detectorName = "ESTIA_sect0"
    # detectorType = 'MB'
    # instrumentName = 'ESTIA'
    
    # detectorName = "ESTIA_sect0and1"
    # detectorType = 'MB'
    # instrumentName = 'ESTIA'
    
    # detectorName = "ESTIA"
    # detectorType = 'MB'
    # instrumentName = 'ESTIA'
    
    
    
    # detectorName = "FREIA_sect0"
    # detectorType = 'MB'
    # instrumentName = 'FREIA'
    
    # detectorName = "FREIA_sect0and1"
    # detectorType = 'MB'
    # instrumentName = 'FREIA'
    
    # detectorName = "FREIA"
    # detectorType = 'MB'
    # instrumentName = 'FREIA'
    
    
    
    
    # detectorName = "MG1column"
    # detectorType = 'MG'
    # instrumentName = 'TREX'
    
    # detectorName = "MG_EMMA"
    # detectorType = 'MG'
    # instrumentName = 'TREX'

    
    # detectorName = "MIRACLES1"
    # detectorType = 'He3'
    # instrumentName = 'MIRACLES'
    
    # detectorName = "MIRACLES24"
    # detectorType = 'He3'
    # instrumentName = 'MIRACLES'
    
    # detectorName = "test1hybrid"
    # detectorType = 'MB'
    # instrumentName = 'ESTIA'
    
    
    detectorName = "SKADI48"
    detectorType = 'SKADI'
    instrumentName = 'SKADI'
    
    
    detectorName = "NMXtest"
    detectorType = 'NMX'
    instrumentName = 'NMX'
 
    
    operationMode = 'normal'
    units = 12
    orientation = 'horizontal'

    # Call the function directly
    generated_file, ok = generateDefaultDetConfig(path, detectorName, detectorType, instrumentName, units, orientation = orientation , operationMode = operationMode,  overwrite=True) # add overwrite=True to overwrite a file
    print(f"Generated file path: {generated_file}")

    if generated_file and os.path.exists(generated_file):
        with open(generated_file, 'r') as ff1:
            conf1 = json.load(ff1)
            print("Loaded config:", conf1)
    else:
        print("Config file not found or failed to generate.")
   
   
