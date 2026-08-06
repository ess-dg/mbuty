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
# -----------------------------------------------------------------------------
# Per-hybrid topology, one row per physical hybrid (matches ICD ESS-5472998
# sec. 4.3.1 "Hybrid configuration" shape instead of the old per-quadrant
# hybrid-list shape).
#
#   Each panel  = 4 quadrants (one ring per quadrant).
#   Each quadrant = 2 edges (fen 0 = X/plane 0, fen 1 = Y/plane 1).
#   Each edge   = 5 hybrids x 128 contiguous strips = 640 strips.
#
#   quadrant (ring % 4)           : 0      1      2      3
#   X offset  (QUADRANT_X_OFFSET) : 0      640    0      640
#   X flip    (QUADRANT_X_FLIP)   : True   True   False  False
#   Y offset  (QUADRANT_Y_OFFSET) : 0      0      640    640
#   Y flip    (QUADRANT_Y_FLIP)   : False  True   False  True
#
# "offset" below is the final absolute per-hybrid offset (quadrant offset
# + 128 * hybrid slot) — NMXMapper no longer needs any hardcoded
# quadrant tables at all, it just reads this straight out of config,
# same as MB reads offset1stWires_mm * uid.
# -----------------------------------------------------------------------------

_NMX_QUADRANT_X_OFFSET = [0, 640, 0, 640]
_NMX_QUADRANT_X_FLIP   = [True, True, False, False]
_NMX_QUADRANT_Y_OFFSET = [0, 0, 640, 640]
_NMX_QUADRANT_Y_FLIP   = [False, True, False, True]


def _generateTopologyNMX(num_quadrants):
    # To force config to be full pannels (all 4 quadrants) uncomment these lines
    # Otherwise we allow partial pannels in the config
    # if num_quadrants % 4 != 0:
    #     num_quadrants -= num_quadrants % 4

    topology = []
    for ring in range(num_quadrants):
        quadrant = ring % 4
        panel    = ring // 4

        x_quad_offset = _NMX_QUADRANT_X_OFFSET[quadrant]
        x_flip        = _NMX_QUADRANT_X_FLIP[quadrant]
        y_quad_offset = _NMX_QUADRANT_Y_OFFSET[quadrant]
        y_flip        = _NMX_QUADRANT_Y_FLIP[quadrant]

        hybrids_x = []
        hybrids_y = []
        for slot in range(5):
            h_x = slot if not x_flip else 4 - slot
            hybrids_x.append({
                "hybrid": h_x,
                "offset": x_quad_offset + 128 * slot,
                "reversedChannels": x_flip,
                "serial": ''
            })

            h_y = slot if not y_flip else 4 - slot
            hybrids_y.append({
                "hybrid": h_y,
                "offset": y_quad_offset + 128 * slot,
                "reversedChannels": y_flip,
                "serial": ''
            })

        topology.append({
            "ID": panel * 10 + quadrant,  # 0, 1, 2, 3 for Panel 0
            "ring": ring,
            "panel": panel,
            "quadrant": quadrant,
            "fenX": 0,
            "fenY": 1,
            "hybridsX": hybrids_x,
            "hybridsY": hybrids_y
        })

    return topology
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

               # --- clustering (ICD ESS-5472998 sec. 4.3.1 / sec. 7) ---
               "strips": 640,          # strips per edge per quadrant (both X and Y)
               "maxGapX": 1,           # allowed missing strips within an x space-cluster
               "maxGapY": 1,           # allowed missing strips within a y space-cluster
               "maxSpanX": 32,          # max number of strips in cluster
               "maxSpanY": 32,          # max number of strips in cluster
                              

               # --- abs units (not implemented yet — values below are from the ICD
               #     for whenever NMXAbsUnitsCalculator gets written) ---
               # ICD sec. 7: channel pitch 400 um, 0.4 mm
               "stripPitchX_mm": 0.4,
               "stripPitchY_mm": 0.4,
               "quadrantGapX_mm": 0,  # Set to actual gap once known
               "quadrantGapY_mm": 0,

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
    
    current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + os.sep
    
    path = current_dir + 'config'
    
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
    
    
    # detectorName = "SKADI48"
    # detectorType = 'SKADI'
    # instrumentName = 'SKADI'
    
    
    detectorName = "NMXtest"
    detectorType = 'NMX'
    instrumentName = 'NMX'
 
    
    operationMode = 'normal'
    units = 4   # 4 rings/quadrants = 1 panel. Use 8 for 2 panels, 12 for 3, etc.
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