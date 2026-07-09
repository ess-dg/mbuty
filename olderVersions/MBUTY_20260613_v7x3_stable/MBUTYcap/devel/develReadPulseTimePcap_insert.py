#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 22 12:47:09 2021

@author: francescopiscitelli
"""

import numpy as np
import pcapng as pg
import os
import time
import sys


path = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
   
   # filePath = path+'pcap_for_fra.pcapng'
   # filePath = path+'pcap_for_fra_ch2test.pcapng'
   # filePath = path+'pcap_for_fra_ch2test_take2.pcapng'
   # filePath = path+'pcap_for_fra_coinc.pcapng'
filePath = path+'freiatest.pcapng'
   
ff = open(filePath, 'rb')
scanner = pg.FileScanner(ff)

resolution = 11.25e-9

cont = 0

for block in scanner:
    
    cont += 1
    
    try:
        
       
       packetSize    = block.packet_len
       packetData1   = block.packet_data
       print(cont)
       print("packetSize {} bytes".format(packetSize))
       if cont == 3:
           packetData   = packetData1
           
           indexESS = packetData.find(b'ESS')
           
           PulseThigh = int.from_bytes(packetData[indexESS+8:indexESS+12], byteorder='little') # bytes
           PulseTlow  = int.from_bytes(packetData[indexESS+12:indexESS+16], byteorder='little') # bytes
           
           PrevPThigh = int.from_bytes(packetData[indexESS+16:indexESS+20], byteorder='little') # bytes
           PrevPTlow  = int.from_bytes(packetData[indexESS+20:indexESS+24], byteorder='little') # bytes
           
           TimeLO     = int.from_bytes(packetData[72+8:72+12], byteorder='little')*resolution
           
    except:
       print('--> other packet found')
    # else:
        
    #    packetsSizes = np.append(packetsSizes,packetSize)


