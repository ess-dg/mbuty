#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 19 11:59:32 2025

@author: francescopiscitelli
"""
# lib/libConfigGenerator.py
import json
import os
import sys
import time 
import numpy as np 

###############################################################################
###############################################################################

# FOR MB
# The helper function (renamed from a method)
def _generateCassette2ElectronicsConfig(num_cassettes):
    cassette_config = []
    ring = 0
    hybrid = 0
    for i in range(num_cassettes):
        cassette_config.append({
            "ID": i,
            "Ring": ring,
            "Fen": 0,
            "Hybrid": hybrid
        })
        hybrid += 1
        if hybrid >= 5:
            hybrid = 0
            ring += 1
    return cassette_config


# FOR MG
# The helper function (renamed from a method)
def _generateCassette2ElectronicsConfigMG(num_cassettes):
    cassette_config = []
    ring    = 0
    hybridW = 0
    hybridS = 1
    for i in range(num_cassettes):
        cassette_config.append({
            "ID": i,
            "Ring": ring,
            "Fen": 0,
            "HybridW": hybridW,
            "HybridS": hybridS
        })
        hybridW += 2
        hybridS += 2
        if hybridS >= 4:
            ring += 1
            hybridW = 0
            hybridS = 1
            
    return cassette_config



# FOR SKADI
# The helper function (renamed from a method)
def _generateCassette2ElectronicsConfigSKADI(num_cassettes):
    cassette_config = []
    ring    = 0
    IP      = 0
    sysID      = 0
    rotation = 'normal'
    for i in range(num_cassettes):
        cassette_config.append({
            "ID": i,
            "Ring": ring,
            "Fen": 0,
            "IP": IP,
            "sysID": sysID,
            "rotation": rotation,
        })
        ring += 1
        if np.mod(i,2) == 0 :
            rotation = 'flip'
        else:
            rotation = 'normal'
            
            
            
    return cassette_config


# FOR He3
# The helper function (renamed from a method)
def _generateCassette2ElectronicsConfigHe3(num_cassettes):
    cassette_config = []
    ring    = 0
    tube    = 0
    for i in range(num_cassettes):
        cassette_config.append({
            "ID": i,
            "Ring": ring,
            "Fen": 0,
            "Tube": tube,
        })
        tube += 1
        if i >= 11 :
            ring = 1
        if  i == 11 :    
            tube = 0
     
    return cassette_config


###############################################################################
###############################################################################

# The main function to generate the config file
def generateDefaultDetConfig(path, DetectorName, DetectorType, InstrumentName, cassettes, orientation='horizontal', operationMode="normal", overwrite=False):
    """
    Generates a default detector configuration JSON file based on provided parameters.

    Args:
        path (str): The directory where the config file will be saved.
        Detector (str): The detector type (e.g., "BAM").
        cassettes (int): The number of cassettes.
        orientation (str, optional): Detector orientation ("horizontal" or "vertical"). Defaults to 'horizontal'.
        operationMode (str, optional): Operational mode ("normal", "HighGain", "LowNoise"). Defaults to "normal".

    Returns:
        str: The full path to the generated JSON file, or None if an error occurred.
    """
    

    file_name = f"{DetectorName}.json"
    filePathName = os.path.join(path, file_name)
    # Check for existing file
    if os.path.exists(filePathName) and not overwrite:
        print(f"File already exists: {filePathName} — skipping write.")
        return None
    
    
    if DetectorType == 'MB':
            # Call the helper function
            cassette2electronics_config = _generateCassette2ElectronicsConfig(cassettes)
        
            data = {
                "DetectorName": DetectorName,
                "DetectorType": DetectorType,
                "InstrumentName"  : InstrumentName,
                "operationMode": operationMode,
                "cassettes": cassettes,
                "orientation": orientation,
                "Cassette2ElectronicsConfig": cassette2electronics_config,
                "ChannelMapping": [
                    {"WireASIC": 1, "StripASIC": 0}
                ],
                "wires": 32,
                "strips": 64,
                "wirePitch_mm": 4,
                "stripPitch_mm": 4,
                "bladesInclination_deg": 5.1,
                "offset1stWires_mm": 10.5,
                "Monitor": [
                    # {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Fen": 0, "Hybrid": 0, "ASIC": 0, "Channel": 1}
                    {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Channel": 0}
                ]
            }
        
            filePathName = makeFile(path,filePathName,data)
            
    elif  DetectorType == 'MG':  
        
        # Call the helper function
        cassette2electronics_config = _generateCassette2ElectronicsConfigMG(cassettes)
    
        data = {
            "DetectorName": DetectorName,
            "DetectorType": DetectorType,
            "InstrumentName"  : InstrumentName,
            "operationMode": operationMode,
            "cassettes": cassettes,
            "orientation": orientation,
            "Cassette2ElectronicsConfig": cassette2electronics_config,
            "wires": 120,
            "strips": 12,
            	"wirePitchX_mm" : 22,
            	"wirePitchZ_mm" : 10,
            	"stripPitchY_mm" : 25,
            	"wiresPerRow" : 20,
            	"angularOffset_deg" : 10,
            	"linearOffset1stWires_mm" : 80,
            "Monitor": [
                # {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Fen": 0, "Hybrid": 0, "ASIC": 0, "Channel": 1}
                {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Channel": 0}
            ]
        }
    
        filePathName = makeFile(path,filePathName,data)
    
    elif  DetectorType == 'SKADI':  
        
        # Call the helper function
        cassette2electronics_config = _generateCassette2ElectronicsConfigSKADI(cassettes)
    
        data = {
            "DetectorName": DetectorName,
            "DetectorType": DetectorType,
            "InstrumentName"  : InstrumentName,
            "operationMode": operationMode,
            "cassettes": cassettes,
            "orientation": orientation,
            "Cassette2ElectronicsConfig": cassette2electronics_config,
            "Xpix": 16,
            "Ypix": 16,
            	"PitchX_mm" : 4,
            	"PitchY_mm" : 4,
            	"tilesPerRow" : 20,
            "Monitor": [
                {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Channel": 0}
            ]
        }
    
        filePathName = makeFile(path,filePathName,data)
        
    
    elif  DetectorType == 'He3':  
        
        # Call the helper function
        cassette2electronics_config = _generateCassette2ElectronicsConfigHe3(cassettes)
    
        data = {
            "DetectorName": DetectorName,
            "DetectorType": DetectorType,
            "InstrumentName"  : InstrumentName,
            "operationMode": operationMode,
            "cassettes": cassettes,
            "orientation": orientation,
            "Cassette2ElectronicsConfig": cassette2electronics_config,
            "positionBins" : 256,
            # "wires":  256,
            # "strips": 16,
            "tubesPerRow" : 8,
            "tubeLength" : 300,
            "tubeSpacing" : 10,
            "Monitor": [
                {"ID": 99, "hardwareType": "GENERIC", "connectionType": "RING", "Ring": 11, "Channel": 0}
            ]
        }
    
        filePathName = makeFile(path,filePathName,data)
    else:
        
        print('\n \t \033[1;33mWARNING: Detector type {} not supported (only MB, MG and He3 accepted) --> exiting!\033[1;37m\n'.format(DetectorType))
        time.sleep(2)
        sys.exit()
        
    return filePathName  
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
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/config/'

    DetectorName = "MIRACLES2"
    DetectorType = 'He3'
    InstrumentName = 'MIRACLES'
    operationMode = 'normal'
    cassettes = 24
    orientation = 'vertical'

    # Call the function directly
    generated_file = generateDefaultDetConfig(path, DetectorName, DetectorType, InstrumentName, cassettes, orientation, operationMode, overwrite=True) # add overwrite=True to overwrite a file
    print(f"Generated file path: {generated_file}")

    if generated_file and os.path.exists(generated_file):
        with open(generated_file, 'r') as ff1:
            conf1 = json.load(ff1)
            print("Loaded config:", conf1)
    else:
        print("Config file not found or failed to generate.")
   
   
