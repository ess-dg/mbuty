#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 10 15:19:19 2026

@author: francescopiscitelli
"""

import numpy as np 
import sys 
import os
# import libReadPcapng as pcapr

# from lib import libReadPcapng as pc

current_dir = os.path.dirname(os.path.abspath(__file__))

# Move up one level to 'main', then down into 'lib'
lib_path = os.path.join(current_dir, '..', 'lib')

# Add that path to sys.path
sys.path.append(os.path.abspath(lib_path))

# Now you can import your library
import libReadPcapng as pc

detType   = 'MG'

instrType1 = -1*np.ones((100), dtype='int64') 
# instrType1[0] = 1
instrType1[1] = 72
# instrType1[2] = 100
# instrType1[3] = 60


flagSupported = pc.checkInstrumentID().checkDetTypeExists(detType)

temp = np.unique(instrType1)
index1  = temp == ''
index2  = temp < 0
index = np.logical_or(index1,index2)
    
instrIDs = temp[~index]

foundFlag = False 

all_streams  = []
all_types    = []

for ids in instrIDs:
     info = pc.checkInstrumentID()
     info.getInfoFromID(ids)
     all_streams.append(info.detName)
     all_types.append(info.detType)
     
     # print(f"found: {info.detName} | Type: {info.detType} | Readout: {info.ROEtype}")
     
     if info.detType == detType:
         foundFlag = True 
         
# Remove duplicates from the stream list for a cleaner message
unique_types   = ", ".join(set(all_types))
unique_streams = ", ".join(set(all_streams))

if foundFlag:
    print(f"Success: Configuration match found for {detType}.")
    # Proceed with reading the file...
    
# Check if we found a Beam Monitor (BM) in the file streams
elif "BM" in all_types:
    # print(f"\n\033[1;36mNOTE: Beam Monitor (BM) stream detected.\033[0m")
    # print(f"\033[1;36mSkipping standard mismatch warning. Ensure BM data is handled separately.\033[0m")
    print(f"\n\033[1;33mWARNING: Configuration mismatch!\033[0m",end='')
    print(f"\n\033[1;33mWARNING:You are trying to read a file containing only detector types: {unique_types} for data streams {unique_streams}\033[0m")
    print(f"\033[1;33mBut in your config file, you have specified: {detType}\033[0m")
    
else:
   
    
    print(f"\n\033[1;33mWARNING: Configuration mismatch!\033[0m",end='')
    print(f"\033[1;33mYou are trying to read a file containing these detector types: {unique_types} for data streams {unique_streams}\033[0m")
    print(f"\033[1;33mBut in your config file, you have specified: {detType}\033[0m")