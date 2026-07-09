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

###############################################################################
###############################################################################

            
class readouts():            
    def __init__(self): 
        self.Ring    = np.zeros((0), dtype = 'float64')
        self.Fen     = np.zeros((0), dtype = 'float64')
        self.VMM     = np.zeros((0), dtype = 'float64')
        self.hybrid  = np.zeros((0), dtype = 'float64')
        self.ASIC    = np.zeros((0), dtype = 'float64')
        self.Channel = np.zeros((0), dtype = 'float64')
        self.ADC     = np.zeros((0), dtype = 'float64')
        self.timeStamp  = np.zeros((0), dtype = 'float64')
        self.BC      = np.zeros((0), dtype = 'float64')
        self.OTh     = np.zeros((0), dtype = 'float64')
        self.TDC     = np.zeros((0), dtype = 'float64')
        self.GEO     = np.zeros((0), dtype = 'float64')
        self.PulseT    = np.zeros((0), dtype = 'float64')
        self.PrevPT    = np.zeros((0), dtype = 'float64')
        self.Durations = np.zeros((0), dtype = 'float64')
               
    def transformInReadouts(self, data):
        self.Ring     = data[:,0]
        self.Fen      = data[:,1]
        self.VMM      = data[:,2]
        self.hybrid   = data[:,3]
        self.ASIC     = data[:,4]
        self.Channel  = data[:,5]
        self.ADC      = data[:,6]
        self.timeStamp  = data[:,7]
        self.BC       = data[:,8]
        self.OTh      = data[:,9]
        self.TDC      = data[:,10]
        self.GEO      = data[:,11]
        self.PulseT   = data[:,12]
        self.PrevPT   = data[:,13]
                
    # def list(self):
    #     print("Rings {}".format(self.Ring))
    #     print("Fens {}".format(self.Fen))
    
    def append(self, reado):
        
        self.Ring     = np.concatenate((self.Ring, reado.Ring), axis=0)
        self.Fen      = np.concatenate((self.Fen, reado.Fen), axis=0)
        self.VMM      = np.concatenate((self.VMM, reado.VMM), axis=0)
        self.hybrid   = np.concatenate((self.hybrid, reado.hybrid), axis=0)
        self.ASIC     = np.concatenate((self.ASIC, reado.ASIC), axis=0)
        self.Channel  = np.concatenate((self.Channel, reado.Channel), axis=0)
        self.ADC      = np.concatenate((self.ADC, reado.ADC), axis=0)
        self.timeStamp  = np.concatenate((self.timeStamp, reado.timeStamp), axis=0)
        self.BC   = np.concatenate((self.BC, reado.BC), axis=0)
        self.OTh  = np.concatenate((self.OTh, reado.OTh), axis=0)
        self.TDC  = np.concatenate((self.TDC, reado.TDC), axis=0)
        self.GEO  = np.concatenate((self.GEO, reado.GEO), axis=0)
        self.PulseT  = np.concatenate((self.PulseT, reado.PulseT), axis=0)
        self.PrevPT  = np.concatenate((self.PrevPT, reado.PrevPT), axis=0)
        self.Durations  = np.append(self.Durations, reado.Durations)
              
    def concatenateReadoutsInArrayForDebug(self):
        
        leng = len(self.timeStamp)
        
        readoutsArray = np.zeros((leng,9),dtype = 'float64')
        
        readoutsArray[:,0] = self.timeStamp
        readoutsArray[:,1] = self.Ring
        readoutsArray[:,2] = self.Fen
        readoutsArray[:,3] = self.hybrid
        readoutsArray[:,4] = self.ASIC
        readoutsArray[:,5] = self.Channel
        readoutsArray[:,6] = self.ADC
        readoutsArray[:,7] = self.PulseT
        readoutsArray[:,8] = self.PrevPT
        
        return readoutsArray
    
    def sortByTimeStamps(self):
        
        indexes = self.timeStamp.argsort(kind='quicksort')
        
        self.timeStamp =  self.timeStamp[indexes]
        self.Ring      =  self.Ring[indexes]
        self.Fen     =  self.Fen[indexes]
        self.VMM     =  self.VMM[indexes]
        self.hybrid  =  self.hybrid[indexes]
        self.ASIC    =  self.ASIC[indexes]
        self.Channel =  self.Channel[indexes]
        self.ADC     =  self.ADC[indexes]
        self.BC      =  self.BC[indexes]
        self.OTh     =  self.OTh[indexes]
        self.TDC     =  self.TDC[indexes]
        self.GEO     =  self.GEO[indexes]
        self.PulseT  =  self.PulseT[indexes]
        self.PrevPT  =  self.PrevPT[indexes]
        
    def calculateDuration(self):
         
         Tstart = np.min(self.timeStamp)
         Tstop  = np.max(self.timeStamp)
         self.Durations = np.round(Tstop-Tstart, decimals = 3)
         
         
        

###############################################################################
###############################################################################

class checkInstrumentID():
    def __init__(self, ID):
        self.FREIAID = 72
        self.EstiaID = 76
        
        self.printa = True
        
        if ID == self.FREIAID:
             print('found Freia data stream')
        elif ID == self.EstiaID:
             print('found Estia data stream')
        else:
             print('found some other data stream')
             
        print('loading ... [0%]',end=' ')
              
        self.printa = False
        
#################################################  

class  checkWhich_RingFenHybrid_InFile():
    def __init__(self, filePathAndFileName):
        
        pcap = pcapng_reader(filePathAndFileName, timeResolutionType='fine', sortByTimeStampsONOFF = True)
        self.readouts = pcap.readouts
        
        temp = os.path.split(filePathAndFileName)
        # filePath = temp[0]+'/'
        self.fileName = temp[1]

    def check(self):
        
        print("\nRings, Fens and Hybrids in file: {}".format(self.fileName))
        
        RingsInFile = np.unique(self.readouts.Ring)
        
        cont = 0 
        
        for RR in RingsInFile:
            
            # self.RFH['Ring'] = RR
            
            selectRING = self.readouts.Ring == RR
            
            Fens4Ring    = self.readouts.Fen[selectRING]
            Hybrids4Ring = self.readouts.hybrid[selectRING]
            
            FensInRing = np.unique(Fens4Ring)
            
            for FF in FensInRing:
                
                selectFEN = Fens4Ring == FF
                
                Hybrids4Fen = Hybrids4Ring[selectFEN]
                
                HybridsInFen = np.unique(Hybrids4Fen)
                
                for HH in HybridsInFen:
                    
                    cont += 1
                
                    print("\tNo. {}:     Ring {}, Fen {}, Hybrid {}".format(cont,int(RR),int(FF),int(HH)))

        
        
#################################################        
        
class VMM3A():
    def __init__(self, buffer, timeResolution, timeResolutionType):
        
        self.timeResolutionType = timeResolutionType
        
        # decode into little endian integers
        PhysicalRing = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen     = int.from_bytes(buffer[1:2], byteorder='little')
        self.Length  = int.from_bytes(buffer[2:4], byteorder='little')
        TimeHI    = int.from_bytes(buffer[4:8], byteorder='little')
        TimeLO    = int.from_bytes(buffer[8:12], byteorder='little')
        self.BC   = int.from_bytes(buffer[12:14], byteorder='little')
        OTADC     = int.from_bytes(buffer[14:16], byteorder='little')
        G0GEO     = int.from_bytes(buffer[16:17], byteorder='little')
        self.TDC  = int.from_bytes(buffer[17:18], byteorder='little')
        self.VMM  = int.from_bytes(buffer[18:19], byteorder='little')
        self.Channel = int.from_bytes(buffer[19:20], byteorder='little')
        
        #######################
        #  IMPORTANT NOTE: phys ring is 0 and 1 for logical ring 0 etc. Always 12 logical rings 
        self.Ring = np.floor(PhysicalRing/2)
        # self.Ring = PhysicalRing
        #######################

        self.ADC      = OTADC & 0x3FF  #extract only 10 LSB
        self.OTh      = OTADC >> 15    #extract only 1 MSB

        self.G0       = G0GEO >> 7
        self.GEO      = G0GEO & 0x3F
        
        self.ASIC     = self.VMM & 0x1           #extract only LSB
        self.hybrid   = (self.VMM & 0xE) >> 1    #extract only 1110 and shift right by one 

        # if bD0 == 0: # normal mode
        #    pass
        # elif bD0 == 1: # calibration mode
        #    pass

        #  in seconds
        if self.timeResolutionType == 'coarse':
            self.timeStamp =  TimeHI + TimeLO * timeResolution # coarse time resolution
        elif self.timeResolutionType == 'fine':
            # self.timeStamp =  TimeHI + TimeLO*timeResolution + ( timeResolution*2 - (self.TDC*(60/255))*1e-9 )  #fine time resolution
            self.timeStamp =  TimeHI + TimeLO*timeResolution + ( timeResolution*2*1.5 - (self.TDC*(60/255))*1e-9 )  #fine time resolution
            
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

class pcapng_reader():
    def __init__(self, filePathAndFileName, timeResolutionType='fine', sortByTimeStampsONOFF = True):
        
        self.readouts = readouts()
        
        try:
            # print('PRE-ALLOC method to load data ...')
            self.pcapng = pcapng_reader_PreAlloc(filePathAndFileName)
            self.pcapng.allocateMemory()
            self.pcapng.read(timeResolutionType)
            self.readouts = self.pcapng.readouts
            
        except:
            print('\n... PRE-ALLOC method failed, trying APPEND method to load data ...')
            
            #  HERE IS FUTURE DEVEL IF NEEDED 
            # self.pcapng = pcapng_reader_slowAppend(filePathAndFileName)
            # self.pcapng.read(timeResolutionType)
            # self.readouts = self.pcapng.readouts    
            
        finally:
             
             if sortByTimeStampsONOFF is True:
                 
                 print('Readouts are sorted by TimeStamp')
                 
                 self.readouts.sortByTimeStamps()
                 
            
             else:
                
                print('Readouts are NOT sorted by TimeStamp')
                
             self.readouts.calculateDuration()     
                        
##################################################  

class pcapng_reader_PreAlloc():
    def __init__(self, filePathAndFileName):
        
        self.filePathAndFileName = filePathAndFileName
        
        checkIfFileExistInFolder(self.filePathAndFileName)
        
        temp2 = os.path.split(filePathAndFileName)
        fileName = temp2[1]
        
        self.fileSize   = os.path.getsize(self.filePathAndFileName) #bytes
        print('{} is {} kbytes'.format(fileName,self.fileSize/1e3))
    
        self.readouts = readouts()
          
        #############################
        
        self.debug = False

        self.offset              = 25  #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
        
        self.mainHeaderSize      = 42  #bytes (14 bytes of Ethernet header, 20 bytes of IPv4 header, and 8 bytes of UDP header)
        self.ESSheaderSize       = 30  #bytes
        
        self.headerSize          = self.mainHeaderSize+self.ESSheaderSize #bytes  (72 bytes)
        
        self.singleReadoutSize   = 20  #bytes
        
        # self.timeResolution = 11.25e-9  #s per tick for 88.888888 MHz
        self.timeResolution = 11.35686096362965e-9  #s per tick ESS for 88.025 MHz
        
        # self.numOfPacketsPerTransfer = 447
        # self.expectedESSpacketSize = 72+NumOfReadoutsIN1PAcket*20 = max 9000bytes
        # self.preallocLength    =  round(self.fileSize*1.2/self.expectedESSpacketSize)*self.numOfPacketsPerTransfer
        
        #############################

        self.counterPackets           = 0
        self.counterCandidatePackets  = 0
        
        self.counterValidESSpackets   = 0
        self.counterNonESSpackets     = 0
        self.counterEmptyESSpackets   = 0
        
        self.totalReadoutCount = 0      

    # def __del__(self):
    #     try:
    #         self.ff.close()
    #     except:
    #         pass

    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))

    def allocateMemory(self):  
        
        ff = open(self.filePathAndFileName, 'rb')
        scanner = pg.FileScanner(ff)
        
        packetsSizes = np.zeros((0),dtype='float64')
        
        for block in scanner:
    
           self.counterPackets += 1
           self.dprint("packet {}".format(self.counterPackets))
    
           try:
                packetSize = block.packet_len
                self.dprint("packetSize {} bytes".format(packetSize))
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
        
        
    def read(self, timeResolutionType='fine'):   
        
        self.timeResolutionType = timeResolutionType
        
        self.data = np.zeros((self.preallocLength,14), dtype='float64') 
        
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
                
                 indexESS = packetData.find(b'ESS')
                 
                 self.dprint('index where ESS word starts {}'.format(indexESS))
                 #  it should be always 44 = 42+2
        
                 if indexESS == -1:
                    # this happens if it not an ESS packet 
                    self.counterNonESSpackets += 1
                    
                 else: 
                     # there is an ESS packet but i can still be ampty, i.e.72 bytes only
                    self.counterValidESSpackets += 1
                    
                    if self.counterValidESSpackets == 1:
                        checkInstrumentID(packetData[indexESS+3])
                     
                    indexDataStart = indexESS + 2 + self.offset + 1    #  this is 72 = 42+30
                    
                    #   give a warning if not 72,  check that ESS cookie is always in the same place
                    if indexDataStart != self.headerSize:
                        print('\n \033[1;31mWARNING ---> ESS cookie is not in position 72! \033[1;37m')
                        
                    ESSlength = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes    
                    
                    PulseThigh = int.from_bytes(packetData[indexESS+8:indexESS+12], byteorder='little') # s
                    PulseTlow  = int.from_bytes(packetData[indexESS+12:indexESS+16], byteorder='little')*self.timeResolution # s
                    PrevPThigh = int.from_bytes(packetData[indexESS+16:indexESS+20], byteorder='little') # s
                    PrevPTlow  = int.from_bytes(packetData[indexESS+20:indexESS+24], byteorder='little')*self.timeResolution # s
                    
                    PulseT = PulseThigh + PulseTlow
                    PrevPT = PrevPThigh + PrevPTlow
                    
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
                            
                            for currentReadout in range(readoutsInPacket):
                                
                                overallDataIndex += 1 
                            
                                indexStart = indexDataStart + self.singleReadoutSize * currentReadout
                                indexStop  = indexDataStart + self.singleReadoutSize * (currentReadout + 1)
                    
                                vmm3 = VMM3A(packetData[indexStart:indexStop], self.timeResolution, self.timeResolutionType)
                    
                                index = overallDataIndex-1
                    
                                self.data[index, 0] = vmm3.Ring
                                self.data[index, 1] = vmm3.Fen
                                self.data[index, 2] = vmm3.VMM
                                self.data[index, 3] = vmm3.hybrid
                                self.data[index, 4] = vmm3.ASIC
                                self.data[index, 5] = vmm3.Channel
                                self.data[index, 6] = vmm3.ADC
                                self.data[index, 7] = vmm3.timeStamp
                                self.data[index, 8] = vmm3.BC
                                self.data[index, 9] = vmm3.OTh
                                self.data[index, 10] = vmm3.TDC
                                self.data[index, 11] = vmm3.GEO
                                self.data[index, 12] = PulseT
                                self.data[index, 13] = PrevPT

                                self.dprint(" \t Packet: {} ({} bytes), Readout: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
                                            .format(self.counterValidESSpackets,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeStamp,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.GEO))

                
                                ###########
         
                            
         
                 if np.mod(self.counterValidESSpackets,stepsForProgress) == 0 or np.mod(self.counterValidESSpackets,stepsForProgress) == 0:
                    percents = int(round(100.0 * self.counterValidESSpackets / float(self.counterCandidatePackets), 1))
                    print('['+format(percents,'01d') + '%]',end=' ')
         
        print('[100%]',end=' ') 

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

#  NOTE THIS PART  BELOW IS  WITH APPEND METHOD IS SLOW BUT IT MIGHT BE NEEDED FOR  SPECIAL CASES, IT NEEDS A FIX FOR THE FUTURE 

             
# class pcapng_reader_slowAppend():
#     def __init__(self, filePathAndFileName):
        
#         if os.path.exists(filePathAndFileName) is False:
#             temp2 = os.path.split(filePathAndFileName)
#             filePath = temp2[0]+'/'
#             fileName = [temp2[1]]
#             print('\n \033[1;31m---> File: '+fileName+' DOES NOT EXIST \033[1;37m')
#             print('\n ---> in folder: '+filePath+' \n')
#             print(' ---> Exiting ... \n')
#             print('------------------------------------------------------------- \n')
#             sys.exit()

#         self.ff = open(filePathAndFileName, 'rb')
        
#         self.readouts = readouts()
        
#         self.fileSize   = os.path.getsize(filePathAndFileName) #bytes
#         print('data is {} kbytes'.format(self.fileSize/1e3))
        
#         self.debug = False

#         self.offset = 25            #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
#         self.ESSheaderSize    = 30  #bytes
#         self.dataPacketLength = 20  #bytes
        
#         # self.timeResolution = 11.25e-9  #s per tick
        
#         self.timeResolution = 11.35686096362965e-9  #s per tick ESS 
        
#         self.numOfPacketsPerTransfer = 400 
        
#         # self.numOfPacketsPerTransfer = 447

#         self.expectedESSpacketSize = self.numOfPacketsPerTransfer*self.dataPacketLength+self.ESSheaderSize #8970 bytes
#         self.preallocLength    =  round(self.fileSize*1.2/self.expectedESSpacketSize)*self.numOfPacketsPerTransfer
        
#         # I add a 20% *1.2 for safety

#         self.packetCount       = 0
#         self.truePacketCount   = 0
#         self.nonESSPacketCount = 0
#         self.totalReadoutCount = 0      

#     def __del__(self):
#         try:
#             self.ff.close()
#         except:
#             pass

#     def dprint(self, msg):
#         if self.debug:
#             print("{}".format(msg))

#     def read(self, timeResolutionType='fine'):    
    
#         self.timeResolutionType = timeResolutionType
        
#         scanner = pg.FileScanner(self.ff)
        
#         data = np.zeros((0,12), dtype='float64') 

#         for block in scanner:
#             self.packetCount += 1
#             readoutCount      = 0

#             try:
#                 packetLength = block.packet_len
#                 packetData   = block.packet_data
#             except:
#                 continue

#             self.truePacketCount += 1
#             self.dprint("packet {} - length {}".format(self.packetCount, packetLength))

#             indexESS = packetData.find(b'ESS')

#             if indexESS == -1:
#                 self.nonESSPacketCount += 1
#                 continue

#             if self.truePacketCount == 1:
#                 checkInstrumentID(packetData[indexESS+3])
            
#             indexDataStart = indexESS + 2 + self.offset + 1
            
#             ESSlength = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes

#             # check that ESS is always in the same place
#             # tempIndexDataStart.append(indexDataStart)

#             readoutCount = (packetLength - indexDataStart) / self.dataPacketLength
#             self.dprint("readoutCount {}".format(readoutCount))

#             if readoutCount.is_integer() is not True:
#                 print('something wrong with data bytes dimensions')
#                 break
#             else:
#                 readoutCount = int(readoutCount)
#                 self.totalReadoutCount += readoutCount
                
#                 for currentReadout in range(readoutCount):
                
#                     indexStart = indexDataStart + self.dataPacketLength * currentReadout
#                     indexStop  = indexDataStart + self.dataPacketLength * (currentReadout + 1)

#                     vmm3 = VMM3A(packetData[indexStart:indexStop], self.timeResolution, self.timeResolutionType)
                    
#                     # self.data.append(vmm3)
#                     # NOTE this append at every cycle is not efficient for speed so better to allocate the array and fill it, then append outside inner loop
                   
#                     index = (self.truePacketCount-1)*self.numOfPacketsPerTransfer+currentReadout
                    
#                     # print(vmm3.Channel)
                    
#                     # vmm3.Ring
                    
#                     temp = np.array([vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.ADC,vmm3.timeStamp,vmm3.BC,vmm3.OTh,vmm3.TDC,vmm3.GEO])
                    
#                     data = np.concatenate((data,temp[None,:]),axis=0)
                    
#                     del temp
                    
#                     # data[index, 1] = vmm3.Fen
#                     # data[index, 2] = vmm3.VMM
#                     # data[index, 3] = vmm3.hybrid
#                     # data[index, 4] = vmm3.ASIC
#                     # data[index, 5] = vmm3.Channel
#                     # data[index, 6] = vmm3.ADC
#                     # data[index, 7] = vmm3.timeStamp
#                     # data[index, 8] = vmm3.BC
#                     # data[index, 9] = vmm3.OTh
#                     # data[index, 10] = vmm3.TDC
#                     # data[index, 11] = vmm3.GEO

#                     self.dprint(" \t Packet: {} ({} bytes), Readout: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
#                                 .format(self.truePacketCount,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeStamp,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.GEO))

                
#                     ###########
           
#             # check 
#             packetLength = readoutCount*self.dataPacketLength + self.ESSheaderSize  # bytes
#             if packetLength != ESSlength and self.truePacketCount == 1:
#                print('something wrong with this packet: exp size {} bytes, found {} bytes.'.format(ESSlength,packetLength))
               
#             roughNumOfPackets   = round(self.fileSize/ESSlength) 
#             steps = int(roughNumOfPackets/4)+1
#             if np.mod(self.truePacketCount,steps) == 0 or np.mod(self.truePacketCount,steps) == 0:
#                     percents = int(round(100.0 * self.truePacketCount / float(roughNumOfPackets), 1))
#                     print('['+format(percents,'01d') + '%]',end=' ')
     
#         print('[100%]',end=' ') 

#         # here I remove  the rows that have been preallocated but no filled 
#         # datanew = np.delete(data,np.arange(self.totalReadoutCount,self.preallocLength),axis=0)
        
#         self.readouts.transformInReadouts(data)
        
         
        
#         # check 
#         if data.shape[0] != self.totalReadoutCount:
#             print('\nsomething wrong ... mismatch between data exp. length {} and what was read {}'.format(self.totalReadoutCount,self.readouts.Ring.shape[0]))
          
#         print('\ndata loaded - found {} readouts ({} kbytes) - Packets: valid {}, nonESS {}, All {})'.format(self.totalReadoutCount,self.truePacketCount*ESSlength/1e3,self.truePacketCount,self.nonESSPacketCount,self.packetCount))    
          
#         self.__del__()
        
#         return data
        
###############################################################################
###############################################################################

if __name__ == '__main__':
   # parser = argparse.ArgumentParser()
   # parser.add_argument("-f", metavar='file', help = "pcap file",
   #                     type = str, default = "VMM3a_Freia.pcapng")
   # parser.add_argument('-d', action='store_true', help = "add debug print")

   tProfilingStart = time.time()

   # arg = parser.parse_args()
   # filePath = './'+"VMM3a_Freia.pcapng"
   # filePath = './'+"VMM3a.pcapng"
   
   path = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
   
   # filePath = path+'pcap_for_fra.pcapng'
   # filePath = path+'pcap_for_fra_ch2test.pcapng'
   # filePath = path+'pcap_for_fra_ch2test_take2.pcapng'
   # filePath = path+'pcap_for_fra_coinc.pcapng'
   filePath = path+'freiatest.pcapng'

   # pr = pcapng_reader(filePath,timeResolutionType='fine')
   # # pr.debug = True
   # # pr.ret()
   # # data = pr.data
   # 
   
   # pr = pcapng_reader_PreAlloc(filePath)

   # # pr.debug = True
   
   # pr.allocateMemory()
   
   # pr.read(timeResolutionType='fine')
   
   # pcap = pcapng_reader(filePath,timeResolutionType='fine', sortByTimeStampsONOFF = True)
   # readouts = pcap.readouts
   
   # readouts.sortByTimeStamps()
   
   # readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   # 
   # ppp = plo.plottingReadouts(vmm3, config)
   # ppp.plotChRaw(parameters.cassettes.cassettes)
   # ppp.plotTimeStamps(parameters.cassettes.cassettes)
   
   # cc= checkWhich_RingFenHybrid_InFile(filePath)
   
   # aa = cc.check()
   
   # readouts = cc.readouts
   # r
   
   # cc= checkWhich_RingFenHybrid_InFile(filePath).check()
   
   # pcapng = pcapng_reader_PreAlloc(filePath)
   # pcapng.allocateMemory()
   # pcapng.read(timeResolutionType='fine')
   
   pcap = pcapng_reader(filePath,timeResolutionType='fine', sortByTimeStampsONOFF = True)
   readouts = pcap.readouts 
   readoutsArray = readouts.concatenateReadoutsInArrayForDebug()
   

   # aa = pr.d
   # bb = pr.e
   
   # aaa = aa[446900:,5:9]
   # bbb = bb[446900:,5:9]
   
   # for k in range(446900,447000,1):
   #      print(" \t Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
   #                               .format(vmm3.Ring[k],vmm3.Fen[k],vmm3.VMM[k],vmm3.hybrid[k],vmm3.ASIC[k],vmm3.Channel[k],vmm3.timeStamp[k],vmm3.BC[k],vmm3.OTh[k],vmm3.ADC[k],vmm3.TDC[k],vmm3.GEO[k]))
   
   tElapsedProfiling = time.time() - tProfilingStart
   print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 