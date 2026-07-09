#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 17 08:43:03 2021

@author: francescopiscitelli
"""

import numpy as np
import libReadPcapngVMM as pcapr
import os
import pcapng as pg

path = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
# filePathAndFileName = path+'pcap_for_fra.pcapng'
# filePathAndFileName = path+'pcap_for_fra_ch2test.pcapng'
# filePathAndFileName = path+'pcap_for_fra_ch2test_take2.pcapng'
# filePathAndFileName = path+'pcap_for_fra_coinc.pcapng'
filePathAndFileName = path+'freiatest.pcapng'




ff = open(filePathAndFileName, 'rb')

readouts = pcapr.readouts()

fileSize   = os.path.getsize(filePathAndFileName) #bytes
print('data is {} kbytes'.format(fileSize/1e3))

debug = False

offset              = 25  #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53

mainHeaderSize      = 42  #bytes (14 bytes of Ethernet header, 20 bytes of IPv4 header, and 8 bytes of UDP header)
ESSheaderSize       = 30  #bytes
singleReadoutLength = 20  #bytes

# self.timeResolution = 11.25e-9  #s per tick for 88.888888 MHz
timeResolution = 11.35686096362965e-9  #s per tick ESS for 88.025 MHz

# numOfPacketsPerTransfer = 400 

numOfPacketsPerTransfer = 446 # 8950 bytes = 30+20*446

#  maybe 447 in future 
# numOfPacketsPerTransfer = 446

# extra 42 for ??  # 

expectedESSpacketSize = (numOfPacketsPerTransfer*singleReadoutLength) + ESSheaderSize + mainHeaderSize  #8992 bytes
preallocLength    =  round(fileSize/expectedESSpacketSize)*numOfPacketsPerTransfer

# I add a 20% *1.2 for safety

packetCount       = 0
truePacketCount   = 0
truePacketCount2   = 0
nonESSPacketCount = 0
totalReadoutCount = 0      

timeResolutionType = 'fine'


scanner = pg.FileScanner(ff)

#  check length

packetsLength = np.zeros((0),dtype='float64')

for block in scanner:
    
    packetCount += 1
    
    # print('packetCount = ',packetCount)
    
    try:
        packetLength = block.packet_len
        # print('packetLength= ',packetLength)
        # packetData   = block.packet_data
    except:
        # print(1)
        print('-->no ESS packet dedwddcdwc')
    
    else:
        truePacketCount += 1
        packetsLength = np.append(packetsLength,packetLength)
        

allPacketslengths = np.sum(packetsLength)

# allPacketslengths2 = np.sum(packetsLength) - truePacketCount*72

numOfRperPack = (packetsLength - 72)/20

numOfRperPackTot = np.sum(numOfRperPack[ numOfRperPack >= 0])

# packetsLength2 = []
# numOfRperPack  = []
# for k in range(truePacketCount):
#     packetsLength2.append(packetsLength[k]-(72))
#     numOfRperPack.append(packetsLength2[k]/20)
    
# numOfRperPack = np.array( numOfRperPack)     
        
# numOfRperPackTot = np.sum(numOfRperPack[ numOfRperPack >= 0])
 
# numOfRperPack = packetsLength2/20 

preallocLength2 = round(fileSize/(allPacketslengths/truePacketCount))*numOfPacketsPerTransfer

preallocLength3 = round(numOfRperPackTot)



data = np.zeros((preallocLength3,12), dtype='float64') 

ff.close()

ff1 = open(filePathAndFileName, 'rb')

scanner1 = pg.FileScanner(ff1)
# data = np.zeros((preallocLength,12), dtype='float64') 

# # currentIndex = 0

ESSlength = 0

count = 0

numOFEmptyESSPackets = 0

for block in scanner1:
    # packetCount += 1
    # print('packetCount = ',packetCount)
    # readoutCount      = 0
    
    # print('ciao')

    try:
        packetLength = block.packet_len
        # print('packetLength= ',packetLength)
        packetData   = block.packet_data
    except:
        print('-->no ESS packet')
    
    else:
        # print('dsdwdwd')
      
    
        # truePacketCount += 1
        # print('truePacketCount = ',truePacketCount)
        # dprint("packet {} - length {}".format(packetCount, packetLength))
    
        indexESS = packetData.find(b'ESS')
        
        # print(indexESS)
    
        if indexESS == -1:
            nonESSPacketCount += 1
            
        
        # if truePacketCount >= -np.inf:
    
        # if truePacketCount == 1:
        #     checkInstrumentID(packetData[indexESS+3])
        
        else:
            
            truePacketCount2 += 1
            
            indexDataStart = indexESS + 2 + offset + 1
            #  this is 72 = 42+30
            
            ESSlength = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes
        
            print(ESSlength,packetLength)
            
            # check that ESS is always in the same place
            # tempIndexDataStart.append(indexDataStart)
        
        
        
        
            readoutCount = (packetLength - indexDataStart) / singleReadoutLength
            
            if packetLength - indexDataStart == 0:
                
                numOFEmptyESSPackets += 1
                print('empty packet')
                
            else:
            
                # self.dprint("readoutCount {}".format(readoutCount))
            
                if readoutCount.is_integer() is not True:
                    print('something wrong with data bytes dimensions')
                    break
                else:
                    readoutCount = int(readoutCount)
                    totalReadoutCount += readoutCount
                    
                    for currentReadout in range(readoutCount):
                    # for currentReadout in [0]:
                        
                        # currentIndex += 1
                        
                        count += 1
                        
                        # print(currentIndex)
                    
                        indexStart = indexDataStart + singleReadoutLength * currentReadout
                        indexStop  = indexDataStart + singleReadoutLength * (currentReadout + 1)
            
                        vmm3 = pcapr.VMM3A(packetData[indexStart:indexStop], timeResolution, timeResolutionType)
                        
                        # print(vmm3.timeStamp)
                        # time.sleep(2)
                        
                        # self.data.append(vmm3)
                        # NOTE this append at every cycle is not efficient for speed so better to allocate the array and fill it, then append outside inner loop
                       
                        # index = (truePacketCount-1)*numOfPacketsPerTransfer+currentReadout
                        
                        index = count-1
                        
                        data[index, 0] = vmm3.Ring
                        data[index, 1] = vmm3.Fen
                        data[index, 2] = vmm3.VMM
                        data[index, 3] = vmm3.hybrid
                        data[index, 4] = vmm3.ASIC
                        data[index, 5] = vmm3.Channel
                        data[index, 6] = vmm3.ADC
                        data[index, 7] = vmm3.timeStamp
                        data[index, 8] = vmm3.BC
                        data[index, 9] = vmm3.OTh
                        data[index, 10] = vmm3.TDC
                        data[index, 11] = vmm3.GEO
            
                        # self.dprint(" \t Packet: {} ({} bytes), Readout: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
                                    # .format(self.truePacketCount,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeStamp,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.GEO))
        
                
                ###########
       
            # check 
            packetLength = readoutCount*singleReadoutLength + ESSheaderSize  # bytes
            if packetLength != ESSlength and truePacketCount == 1:
                print('something wrong with this packet: exp size {} bytes, found {} bytes.'.format(ESSlength,packetLength))
               
            roughNumOfPackets   = round(fileSize/ESSlength) 
            # steps = int(roughNumOfPackets/4)+1
            # if np.mod(truePacketCount,steps) == 0 or np.mod(truePacketCount,steps) == 0:
            #         percents = int(round(100.0 * self.truePacketCount / float(roughNumOfPackets), 1))
            #         print('['+format(percents,'01d') + '%]',end=' ')
 
print('[100%]',end=' ') 

# here I remove  the rows that have been preallocated but no filled 
# datanew = np.delete(data,np.arange(totalReadoutCount,preallocLength2),axis=0)

print('totalReadoutCount ',totalReadoutCount)

# datanew = np.delete(data, np.arange(currentIndex,self.preallocLength),axis=0)

print('alloc length len',np.shape(data)[0])

datasum  = np.sum(data,axis=1)
indexesIsNotZero  = np.argwhere(datasum>0)

trueLen  = np.shape(indexesIsNotZero[:,0]>0)[0]

print('true len',trueLen)

datanew = data[indexesIsNotZero[:,0],:]

# datanew = data

readouts.transformInReadouts(datanew)

# print('extra len',totalReadoutCount-trueLen)

print('a priori',preallocLength3)

sizeOfRealData = totalReadoutCount*20

# check 
if datanew.shape[0] != totalReadoutCount:
    print('\nsomething wrong ... mismatch between data exp. length {} and what was read {}'.format(totalReadoutCount,readouts.Ring.shape[0]))
  
print('\ndata loaded - found {} readouts ({} kbytes) - Packets: valid {} (empty {})), nonESS {}, All {})'.format(totalReadoutCount,sizeOfRealData/1e3,truePacketCount2,numOFEmptyESSPackets,nonESSPacketCount,packetCount))    
  
ff1.close()

readoutArray = readouts.concatenateReadoutsInArrayForDebug()