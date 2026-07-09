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

###############################################################################
###############################################################################

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

###############################################################################
###############################################################################

# The main function to generate the config file
def generateDefaultDetConfig(path, Detector, cassettes, orientation='horizontal', operationMode="normal", overwrite=False):
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

    file_name = f"{Detector}.json"
    filePathName = os.path.join(path, file_name)
    # Check for existing file
    if os.path.exists(filePathName) and not overwrite:
        print(f"File already exists: {filePathName} — skipping write.")
        return None
    # Call the helper function
    cassette2electronics_config = _generateCassette2ElectronicsConfig(cassettes)

    data = {
        "Detector": Detector,
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
            {"ID": 99, "TTLtype": "True", "Ring": 11, "Fen": 0, "Hybrid": 0, "ASIC": 0, "Channel": 1}
        ]
    }

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
            sys.exit()
    else:
          
          writeFile = True
          
    return writeFile   

###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':
    path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTY_develJSON/'

    Detector = "B.AM"
    operationMode = 'normal'
    cassettes = 14
    orientation = 'vertical'

    # Call the function directly
    generated_file = generateDefaultDetConfig(path, Detector, cassettes, orientation, operationMode) # add overwrite=True to overwrite a file
    print(f"Generated file path: {generated_file}")

    if generated_file and os.path.exists(generated_file):
        with open(generated_file, 'r') as ff1:
            conf1 = json.load(ff1)
            print("Loaded config:", conf1)
    else:
        print("Config file not found or failed to generate.")
   
   
