#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V1.2 2021/08/19     francescopiscitelli      ######################
########    script to read the pcapng file from VMM readout
###############################################################################
###############################################################################

import numpy as np
import pcapng as pg
import os

# import sys

import time

###############################################################################
###############################################################################

datapathinput = './'
# filename      = 'VMM3a.pcapng'
filename      = 'VMM3a_Freia.pcapng'

infoPrint = False

###########################################

offset = 25                  #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
ESSheaderSize    = 30        #bytes
dataPacketLength = 20        #bytes
resolution       = 11.25e-9  #s per tick 


###############################################################################
###############################################################################

tProfilingStart = time.time()
                
                
ff      = open(datapathinput+filename, 'rb')

fileSize   = os.path.getsize(datapathinput+filename) #bytes
print('loading data ({} kbytes)'.format(fileSize/1e3))

scanner = pg.FileScanner(ff)

howManyExtraPackets   = 0
howManyNonESSPackets  = 0 
howManyTruePackets    = 0

data = np.zeros((0,6),dtype = 'float64')

printa = True

for block in scanner:
            
        try:
            packetLength = block.packet_len
            packetData   = block.packet_data
        except:
            howManyExtraPackets += 1
            continue  

        indexESS = packetData.find(b'ESS')
            
        if indexESS == -1:
           howManyNonESSPackets += 1
           continue
        else:
           howManyTruePackets += 1
            
        # if howManyTruePackets == 1:
            
        # maybe here add a check that the data is coming from the ESS data stream 
        # if indexESS != -1 :
        #     print('data stream from ESS')
        indexDataStart = indexESS+2+offset+1
        
        # check that ESS is always in the same place
        # tempIndexDataStart.append(indexDataStart)
        
        # indexStartESSheader = indexESS-2
        
        instrumentID = packetData[indexESS+3]
        if instrumentID == 0x48:
            if printa is True:
                print('found Freia data stream')
                printa = False
                
        ESSlength = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes
        
        numOfHits = (packetLength-indexDataStart)/dataPacketLength
        if numOfHits.is_integer() is not True:
            print('something wrong with data bytes dimensions')
            break
        else:
            numOfHits = int(numOfHits)
            hitsInPacket = np.zeros((numOfHits,6),dtype = 'float64')
        
        #############################################################################
        
        buffer = packetData[indexDataStart:(indexDataStart + dataPacketLength*(numOfHits+1))]
        
        chunks = [buffer[i:i+dataPacketLength] for i in range(0, len(buffer), dataPacketLength)]
               
        Ring    = [int.from_bytes(chunks[k][0:1], byteorder='little') for k in range(0, len(chunks), 1)]
        Fen     = [int.from_bytes(chunks[k][1:2], byteorder='little') for k in range(0, len(chunks), 1)]
        Length  = [int.from_bytes(chunks[k][2:4], byteorder='little') for k in range(0, len(chunks), 1)]
        TimeHI  = [int.from_bytes(chunks[k][4:8], byteorder='little') for k in range(0, len(chunks), 1)]
        TimeLO  = [int.from_bytes(chunks[k][8:12], byteorder='little') for k in range(0, len(chunks), 1)]
        BC      = [int.from_bytes(chunks[k][12:14], byteorder='little') for k in range(0, len(chunks), 1)]
        
        # bDOTADC     = format(int.from_bytes(bOTADC, byteorder='little'),'#b')
        # bDOTADC     = format(int.from_bytes(bOTADC, byteorder='little'),'b')
        # #b with 0b and only b without 0b prefix 
        
        OTADC   = [int.from_bytes(chunks[k][14:16], byteorder='little') for k in range(0, len(chunks), 1)]
        ADC     = [OTADC[k] & 0x3FF for k in range(0, len(chunks), 1)]  #extract only 10 LSB
        OTh     = [OTADC[k] >> 15  for k in range(0, len(chunks), 1)]  #extract only 1 MSB
        
        G0GEO   = [int.from_bytes(chunks[k][16:17], byteorder='little') for k in range(0, len(chunks), 1)]
        G0      = [G0GEO[k] >> 7 for k in range(0, len(chunks), 1)] 
        GEO     = [G0GEO[k] & 0x3F for k in range(0, len(chunks), 1)] 

        TDC     = [int.from_bytes(chunks[k][17:18], byteorder='little') for k in range(0, len(chunks), 1)]
        VMM     = [int.from_bytes(chunks[k][18:19], byteorder='little') for k in range(0, len(chunks), 1)]
        Channel = [int.from_bytes(chunks[k][19:20], byteorder='little') for k in range(0, len(chunks), 1)]
        
        #############################################################################
 
        ###########
        whichIndex = 0
        if G0[whichIndex] == 0: # normal mode
           pass
        elif G0[whichIndex] == 1: # calibration mode
           pass
        
        ###########
        #  in seconds 
        # timeStamp =  TimeHI + TimeLO*resolution + ( resolution*2 - (TDC*(60/255))*1e-9 )  #fine time resolution 
        timeStamp =  [(TimeHI[k] + TimeLO[k]*resolution) for k in  range(0, len(TimeLO), 1)] # coarse time resolution
        
        if infoPrint is True:
            [print(" \t Packet: {} ({} bytes), Hit: {}, Ring {}, FEN {}, VMM {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} ".format(howManyTruePackets,ESSlength,k+1,Ring[k],Fen[k],VMM[k],Channel[k],timeStamp[k],BC[k],OTh[k],ADC[k],TDC[k],GEO[k])) for k in  range(0, numOfHits, 1)]
    
        hitsInPacket[:,0] = Ring
        hitsInPacket[:,1] = Fen
        hitsInPacket[:,2] = VMM
        hitsInPacket[:,3] = Channel
        hitsInPacket[:,4] = ADC
        hitsInPacket[:,5] = timeStamp
        
        #############################################################################
                
        data = np.append(data,hitsInPacket,axis=0)
    
        # check 
        packetLength = numOfHits*dataPacketLength + ESSheaderSize  # bytes
        if packetLength != ESSlength:
           print('something wrong ... with this packet: exp size {} bytes, found {} bytes.'.format(ESSlength,packetLength))
           
        roughNumOfPackets   = round(fileSize/ESSlength) 
        # roughNumOfTotalHits = round(roughNumOfPackets*numOfHits)
        steps = round(roughNumOfPackets/4)
        if np.mod(howManyTruePackets,steps) == 0:
                percents = int(round(100.0 * howManyTruePackets / float(roughNumOfPackets), 1))
                print('['+format(percents,'01d') + '%]',end=' ')
     
print('[100%]',end=' ') 
                 
# check 
dataExpectedLength = numOfHits*howManyTruePackets
if data.shape[0] != dataExpectedLength:
   print('something wrong ...')
                  
print('\ndata loaded - found {} hits ({} kbytes) - Packets: valid {}, nonESS {}, Extra {})'.format(np.shape(data)[0],howManyTruePackets*ESSlength/1e3,howManyTruePackets,howManyNonESSPackets,howManyExtraPackets))    
        
ff.close()       

tElapsedProfiling = time.time() - tProfilingStart
print('\n Completed --> elapsed time: %.2f s' % tElapsedProfiling) 