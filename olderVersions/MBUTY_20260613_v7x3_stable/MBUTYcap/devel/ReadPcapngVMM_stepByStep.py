#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V1.4 2021/08/25     francescopiscitelli      ######################
########    script to read the pcapng file from VMM readout
###############################################################################
###############################################################################

# import argparse
import numpy as np
import pcapng as pg
import os
import time
import sys
# from lib import libPlotting as plo

from lib import libReadPcapngVMM as pcapr

###############################################################################
###############################################################################
        

class checkIfFileExistInFolder():
     def __init__(self, filePathAndFileName):
         
          if os.path.exists(filePathAndFileName) is False:
            temp2 = os.path.split(filePathAndFileName)
            filePath = temp2[0]+'/'
            fileName = temp2[1]
            print('\n \033[1;31m---> File: '+fileName+' DOES NOT EXIST \033[1;37m')
            print('\n ---> in folder: '+filePath+' \n')
            print(' ---> Exiting ... \n')
            print('------------------------------------------------------------- \n')
            sys.exit()
            
##################################################                         
##################################################  

class pcapng_reader_PreAlloc():
    def __init__(self, filePathAndFileName, NSperClockTick=11.356860963629653, timeResolutionType = 'coarse'):
        
        self.NSperClockTick = NSperClockTick 
        
        self.timeResolutionType  = timeResolutionType
        
        self.filePathAndFileName = filePathAndFileName
        
        checkIfFileExistInFolder(self.filePathAndFileName)
        
        temp2 = os.path.split(filePathAndFileName)
        fileName = temp2[1]
        
        self.fileSize   = os.path.getsize(self.filePathAndFileName) #bytes
        print('{} is {} kbytes'.format(fileName,self.fileSize/1000))
    
        self.readouts = pcapr.readouts()
          
        #############################
        
        self.debug = False

        self.offset              = 25  #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
        
        self.mainHeaderSize      = 42  #bytes (14 bytes of Ethernet header, 20 bytes of IPv4 header, and 8 bytes of UDP header)
        self.ESSheaderSize       = 30  #bytes
        
        self.headerSize          = self.mainHeaderSize+self.ESSheaderSize #bytes  (72 bytes)
        
        self.singleReadoutSize   = 20  #bytes
                
     
        #############################

        self.counterPackets           = 0
        self.counterCandidatePackets  = 0
        
        self.counterValidESSpackets   = 0
        self.counterNonESSpackets     = 0
        self.counterEmptyESSpackets   = 0
        
        self.totalReadoutCount = 0      


    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))

    def allocateMemory(self):  
        
        ff = open(self.filePathAndFileName, 'rb')
        scanner = pg.FileScanner(ff)
        
        packetsSizes = np.zeros((0),dtype='int64')
        
        for block in scanner:
    
           self.counterPackets += 1
           # self.dprint("packet {}".format(self.counterPackets))
    
           try:
                packetSize = block.packet_len
                # self.dprint("packetSize {} bytes".format(packetSize))
           except:
                self.dprint('--> other packet found No. {}'.format(self.counterPackets-self.counterCandidatePackets))
           else:
                self.counterCandidatePackets += 1
                packetsSizes = np.append(packetsSizes,packetSize)
                
        self.dprint('counterPackets {}, counterCandidatePackets {}'.format(self.counterPackets,self.counterCandidatePackets))    

        if self.debug:
            overallSize = np.sum(packetsSizes)
            self.dprint('overallSize {} bytes'.format(overallSize))

        numOfReadoutsInPackets = (packetsSizes - self.headerSize)/self.singleReadoutSize  #in principle this is 447 for every packet

        #  if negative there was a non ESS packetso length < 72bytes 
        #  and if much bigger wee anyhowallocate morethan needed and remove zeros aftyerwards at the end 
        numOfReadoutsTotal = np.sum(numOfReadoutsInPackets[ numOfReadoutsInPackets >= 0])
        
        self.preallocLength = round(numOfReadoutsTotal)
        self.dprint('preallocLength {}'.format(self.preallocLength))
        
        ff.close()
        
        
    def read(self):   
        
        self.data = np.zeros((self.preallocLength,15), dtype='int64') 
        
        ff = open(self.filePathAndFileName, 'rb')
        scanner = pg.FileScanner(ff)
        
        overallDataIndex = 0 
        
        stepsForProgress = int(self.counterCandidatePackets/4)+1  # 4 means 25%, 50%, 75% and 100%
        
        for block in scanner:
            
            try:
                packetLength = block.packet_len
                packetData   = block.packet_data
                
            except:
                self.dprint('--> other packet found')
                
            else:
                 # print(self.counterValidESSpackets)
                 
                
                     indexESS = packetData.find(b'ESS')
                     
                     # self.dprint('index where ESS word starts {}'.format(indexESS))
                     #  it should be always 44 = 42+2
            
                     if indexESS == -1:
                        # this happens if it not an ESS packet 
                        self.counterNonESSpackets += 1
                        
                     else: 
                         # there is an ESS packet but i can still be empty, i.e. 72 bytes only
                        self.counterValidESSpackets += 1
                        
                        if  self.counterValidESSpackets == 2 :
                     
                            print(self.counterValidESSpackets)
                         
                            indexDataStart = indexESS + self.offset + 3    #  this is 72 = 44+25+3
                            
                            #   give a warning if not 72,  check that ESS cookie is always in the same place
                            if indexDataStart != self.headerSize:
                                print('\n \033[1;31mWARNING ---> ESS cookie is not in position 72! \033[1;37m')
                                
                            ESSlength  = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes    
                            
                            PulseThigh = int.from_bytes(packetData[indexESS+8:indexESS+12], byteorder='little')*1000000000
                            PulseTlow  = int.from_bytes(packetData[indexESS+12:indexESS+16], byteorder='little')*self.NSperClockTick 
                            PrevPThigh = int.from_bytes(packetData[indexESS+16:indexESS+20], byteorder='little')*1000000000
                            PrevPTlow  = int.from_bytes(packetData[indexESS+20:indexESS+24], byteorder='little')*self.NSperClockTick 
                            
                            PulseT = int(round(PulseThigh + PulseTlow)) #time rounded at 1us precision is 6 decimals, 7 is 100ns, etc...
                            PrevPT = int(round(PrevPThigh + PrevPTlow))
                            
                            readoutsInPacket = (packetLength - indexDataStart) / self.singleReadoutSize
                            # or alternatively
                            # readoutsInPacket = (ESSlength - self.ESSheaderSize) / self.singleReadoutSize
                            
                            # ESSlength is only 30 if the packet is an ESS packet but empty= 72-42 =30
                            self.dprint('ESS packet length {} bytes, packetLength {} bytes, readouts in packet {}'.format(ESSlength, packetLength,readoutsInPacket))  
                        
                            if (packetLength - indexDataStart) == 0:
                                
                                self.counterEmptyESSpackets += 1
                                self.dprint('empty packet No. {}'.format(self.counterEmptyESSpackets))
                            
                            else:
                                
                                if readoutsInPacket.is_integer() is not True:
                                    print('\n \033[1;31mWARNING ---> something wrong with data bytes dimensions \033[1;37m')
                                    break
                                else:
                                
                                    readoutsInPacket = int(readoutsInPacket)
                                    self.totalReadoutCount += readoutsInPacket
                                    
                                    readoutsInPacket = 10
                                    
                                    for currentReadout in range(readoutsInPacket):
                                        
                                        overallDataIndex += 1 
                                    
                                        indexStart = indexDataStart + self.singleReadoutSize * currentReadout
                                        indexStop  = indexDataStart + self.singleReadoutSize * (currentReadout + 1)
                            
                                        vmm3 = pcapr.VMM3A(packetData[indexStart:indexStop], self.NSperClockTick)
                            
                                        index = overallDataIndex-1
                            
                                        self.data[index, 0] = vmm3.Ring
                                        self.data[index, 1] = vmm3.Fen
                                        self.data[index, 2] = vmm3.VMM
                                        self.data[index, 3] = vmm3.hybrid
                                        self.data[index, 4] = vmm3.ASIC
                                        self.data[index, 5] = vmm3.Channel
                                        self.data[index, 6] = vmm3.ADC
                                        self.data[index, 7] = vmm3.BC
                                        self.data[index, 8] = vmm3.OTh
                                        self.data[index, 9] = vmm3.TDC
                                        self.data[index, 10] = vmm3.GEO
                                        self.data[index, 11] = vmm3.timeCoarse
                                        self.data[index, 12] = PulseT
                                        self.data[index, 13] = PrevPT
                                        self.data[index, 14] = vmm3.G0  # if 1 is calibration
                                        
                                        print('\033[1;31m {} \033[1;37m'.format(vmm3.G0))
                                        
                                        # self.data[index, 7] = vmm3.timeStamp
                                     
                                        self.dprint(" \t Packet: {} ({} bytes), Readout: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time Coarse {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
                                                    .format(self.counterValidESSpackets,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeCoarse,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.GEO))
        
                        
                                        ###########
             
                                
         
                 # if np.mod(self.counterValidESSpackets,stepsForProgress) == 0 or np.mod(self.counterValidESSpackets,stepsForProgress) == 0:
                 #    percents = int(round(100.0 * self.counterValidESSpackets / float(self.counterCandidatePackets), 1))
                 #    print('['+format(percents,'01d') + '%]',end=' ')
         
        # print('[100%]',end=' ') 

        self.dprint('\n All Packets {}, Candidates for Data {} --> Valid ESS {} (empty {}), NonESS  {} '.format(self.counterPackets , self.counterCandidatePackets,self.counterValidESSpackets ,self.counterEmptyESSpackets,self.counterNonESSpackets))
            
        
        #######################################################       
             
        # here I remove  the rows that have been preallocated but no filled in case there were some packets big but no ESS
        if self.preallocLength > self.totalReadoutCount:
            
            datanew = np.delete(self.data,np.arange(self.totalReadoutCount,self.preallocLength),axis=0)
            print('removing extra allocated length not used ...')
            
        elif self.preallocLength < self.totalReadoutCount:
            print('something wrong with the preallocation: allocated length {}, total readouts {}'.format(self.preallocLength,self.totalReadoutCount))
            sys.exit()
       
        elif self.preallocLength == self.totalReadoutCount:
            
            datanew = self.data
        
        cz = checkIfDataHasZeros(datanew)
        datanew = cz.dataOUT
        
        self.readouts.transformInReadouts(datanew)
        
       
        
        # self.readouts.calculateTimeStamp(self.NSperClockTick)
        if self.timeResolutionType == 'fine':
            self.readouts.calculateTimeStampWithTDC(self.NSperClockTick)
        elif self.timeResolutionType == 'coarse':
            self.readouts.timeStamp = self.readouts.timeCoarse
            
          
        flag = self.readouts.checkIfCalibrationMode()
        
        if flag is True: 
            self.readouts.removeCalibrationData() 
        
        # self.readouts.timeStamp  = self.readouts.timeCoarse  + VMM3A_convertCalibrate_TDCinSec(self.readouts.TDC,timeResolution,time_offset=100e-9,time_slope=1).TDC_s
       
        # self.readouts.TDC =  VMM3A_convertCalibrate_TDCinSec(self.readouts.TDC,timeResolution,time_offset=100e-9,time_slope=1).TDC_s
        
        print('\ndata loaded - found {} readouts - Packets: all {} (candidates {}) --> valid ESS {} (of which empty {}), nonESS {})'.format(self.totalReadoutCount, self.counterPackets,self.counterCandidatePackets,self.counterValidESSpackets ,self.counterEmptyESSpackets,self.counterNonESSpackets))    
        # print('\n')
        
        ff.close()
        
        
class checkIfDataHasZeros():
     def __init__(self, data):
         
         self.dataIN = data
         
         self.OriginalLength = np.shape(self.dataIN)[0]
         
         datasum  = np.sum(data,axis=1)
         indexesIsNotZero  = np.argwhere(datasum>0)
        
         # self.trueLen  = np.shape(indexesIsNotZero[:,0]>0)[0]
    
         self.dataOUT = self.dataIN[indexesIsNotZero[:,0],:]
         self.NewLength = np.shape(self.dataOUT)[0]
         
         if self.NewLength  != self.OriginalLength :
             
            self.flag = True
            
            print('---> removing zeros left in in data')
            
         else :
  
             self.flag = False

###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == '__main__':

   tProfilingStart = time.time()
   
   NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz


   dataPath = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
    
   filePath = dataPath+'pcap_for_fra_270921_2hybrid_2fen_2000.pcapng'
   # filePath = dataPath+'pcap_for_fra_coinc.pcapng'
   # filePath = path+'freiatest.pcapng'
   
   # path = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # filePath = path+'VMM3a_Freia.pcapng'


   # cc = pcapr.checkWhich_RingFenHybrid_InFile(filePath,NSperClockTick).check()
   
   pcap = pcapng_reader_PreAlloc(filePath, NSperClockTick, timeResolutionType = 'coarse')
   pcap.debug = True
   pcap.allocateMemory()
   pcap.read()
    
   
   readouts = pcap.readouts 
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   

   tElapsedProfiling = time.time() - tProfilingStart
   print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 