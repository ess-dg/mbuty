#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V1.0 2021/08/20     francescopiscitelli      ######################
########    script to read the pcapng file from VMM readout
###############################################################################
###############################################################################

import argparse
import numpy as np
import pcapng as pg
import os
import time



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
             
        self.printa = False
        
        
class VMM3A():
    def __init__(self, buffer, resolution):
        
        self.coarseTimeResolution = True
        
        # decode into little endian integers
        self.Ring = int.from_bytes(buffer[0:1], byteorder='little')
        self.Fen  = int.from_bytes(buffer[1:2], byteorder='little')
        Length    = int.from_bytes(buffer[2:4], byteorder='little')
        TimeHI    = int.from_bytes(buffer[4:8], byteorder='little')
        TimeLO    = int.from_bytes(buffer[8:12], byteorder='little')
        self.BC   = int.from_bytes(buffer[12:14], byteorder='little')
        OTADC     = int.from_bytes(buffer[14:16], byteorder='little')
        G0GEO     = int.from_bytes(buffer[16:17], byteorder='little')
        self.TDC       = int.from_bytes(buffer[17:18], byteorder='little')
        self.VMM  = int.from_bytes(buffer[18:19], byteorder='little')
        self.Channel = int.from_bytes(buffer[19:20], byteorder='little')

        self.ADC = OTADC & 0x3FF  #extract only 10 LSB
        self.OTh      = OTADC >> 15    #extract only 1 MSB

        self.G0       = G0GEO >> 7
        self.GEO      = G0GEO & 0x3F
        
        self.hybrid  = self.VMM & 0x1           #extract only LSB
        self.ASIC    = (self.VMM & 0xE) >> 1    #extract only 1110 and shift right by one 

        # if bD0 == 0: # normal mode
        #    pass
        # elif bD0 == 1: # calibration mode
        #    pass

        #  in seconds
        if self.coarseTimeResolution == True:
            self.timeStamp =  TimeHI + TimeLO * resolution # coarse time resolution
        else:
            self.timeStamp =  TimeHI + TimeLO*resolution + ( resolution*2 - (self.TDC*(60/255))*1e-9 )  #fine time resolution
            
            
class readout():            
    def __init__(self): 
        self.Ring  = np.zeros((0), dtype = 'float64')
        self.Fen   = np.zeros((0), dtype = 'float64')
        self.VMM   = np.zeros((0), dtype = 'float64')
        self.hybrid  = np.zeros((0), dtype = 'float64')
        self.ASIC    = np.zeros((0), dtype = 'float64')
        self.Channel = np.zeros((0), dtype = 'float64')
        self.ADC     = np.zeros((0), dtype = 'float64')
        self.timeStamp  = np.zeros((0), dtype = 'float64')
        self.BC      = np.zeros((0), dtype = 'float64')
        self.OTh     = np.zeros((0), dtype = 'float64')
        self.TDC     = np.zeros((0), dtype = 'float64')
        self.GEO     = np.zeros((0), dtype = 'float64')
               
    def append(self, data1packet):
        # self.Ring = np.append(self.Ring, vmm3.Ring)
        # self.Fen  = np.append(self.Fen, vmm3.Fen)
           
        # self.Ring = np.append(self.Ring, vmm3[:,0])
        # self.Fen  = np.append(self.Fen, vmm3[:,1])
        
        self.Ring   = np.concatenate((self.Ring, data1packet[:,0]), axis=0)
        self.Fen    = np.concatenate((self.Fen, data1packet[:,1]), axis=0)
        self.VMM    = np.concatenate((self.VMM, data1packet[:,2]), axis=0)
        self.hybrid = np.concatenate((self.hybrid, data1packet[:,3]), axis=0)
        self.ASIC   = np.concatenate((self.ASIC, data1packet[:,4]), axis=0)
        self.Channel  = np.concatenate((self.Channel, data1packet[:,5]), axis=0)
        self.ADC      = np.concatenate((self.ADC, data1packet[:,6]), axis=0)
        self.timeStamp  = np.concatenate((self.timeStamp, data1packet[:,7]), axis=0)
        self.BC   = np.concatenate((self.BC, data1packet[:,8]), axis=0)
        self.OTh  = np.concatenate((self.OTh, data1packet[:,9]), axis=0)
        self.TDC  = np.concatenate((self.TDC, data1packet[:,10]), axis=0)
        self.GEO  = np.concatenate((self.GEO, data1packet[:,11]), axis=0)
        
                
    # def list(self):
    #     print("Rings {}".format(self.Ring))
    #     print("Fens {}".format(self.Fen))

class pcap_reader():
    def __init__(self, filePath):

        self.ff = open(filePath, 'rb')
        
        self.fileSize   = os.path.getsize(filePath) #bytes
        print('data is {} kbytes'.format(self.fileSize/1e3))
        
        self.debug = False

        self.offset = 25            #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
        self.ESSheaderSize    = 30  #bytes
        self.dataPacketLength = 20  #bytes
        self.resolution = 11.25e-9  #s per tick
        
        # self.
        
        self.expectedESSpacketSize   = self.ESSheaderSize+self.dataPacketLength*447

        self.packetCount       = 0
        self.truePacketCount   = 0
        self.nonESSPacketCount = 0
        self.totalReadoutCount     = 0        

    def __del__(self):
        try:
            self.ff.close()
        except:
            pass

    def dprint(self, msg):
        if self.debug:
            print("{}".format(msg))

    def read(self):       
        scanner = pg.FileScanner(self.ff)
        
        self.data = readout()
        
        # ll = round(self.fileSize/ESSlength) 
        
        # here add estiamte for size of data to preallocate memory 

        for block in scanner:
            self.packetCount += 1
            readoutCount      = 0

            try:
                packetLength = block.packet_len
                packetData   = block.packet_data
            except:
                continue

            self.truePacketCount += 1
            self.dprint("packet {} - length {}".format(self.packetCount, packetLength))

            indexESS = packetData.find(b'ESS')

            if indexESS == -1:
                self.nonESSPacketCount += 1
                continue

            if self.truePacketCount == 1:
                checkInstrumentID(packetData[indexESS+3])
            
            indexDataStart = indexESS + 2 + self.offset + 1
            
            ESSlength = int.from_bytes(packetData[indexESS+4:indexESS+6], byteorder='little') # bytes

            # check that ESS is always in the same place
            # tempIndexDataStart.append(indexDataStart)

            readoutCount = (packetLength - indexDataStart) / self.dataPacketLength
            self.dprint("HitCount {}".format(readoutCount))

            if readoutCount.is_integer() is not True:
                print('something wrong with data bytes dimensions')
                break
            else:
                readoutCount = int(readoutCount)
                self.totalReadoutCount += readoutCount
                readoutInPacket = np.zeros((readoutCount,12), dtype = 'float64')
                # cont = 0
                
                for currentReadout in range(readoutCount):
                # for currentHit in range(1):
                    # print(currentHit)

                    # offset = 72
                    # buffe1          = datap[72:92]
                    # buffe2          = datap[92:112]
                    # buffeSecondLast = datap[8952:8972]
                    # buffeLast       = datap[8972:8992]

                    indexStart = indexDataStart + self.dataPacketLength * currentReadout
                    indexStop  = indexDataStart + self.dataPacketLength * (currentReadout + 1)

                    vmm3 = VMM3A(packetData[indexStart:indexStop], self.resolution)
                    
                    # self.data.append(vmm3)
                    # NOTE this append at every cycle is not efficient for speed so better to allocate the array and fill it, then append outside inner loop
                    
                    readoutInPacket[currentReadout, 0] = vmm3.Ring
                    readoutInPacket[currentReadout, 1] = vmm3.Fen
                    readoutInPacket[currentReadout, 2] = vmm3.VMM
                    readoutInPacket[currentReadout, 3] = vmm3.hybrid
                    readoutInPacket[currentReadout, 4] = vmm3.ASIC
                    readoutInPacket[currentReadout, 5] = vmm3.Channel
                    readoutInPacket[currentReadout, 6] = vmm3.ADC
                    readoutInPacket[currentReadout, 7] = vmm3.timeStamp
                    readoutInPacket[currentReadout, 8] = vmm3.BC
                    readoutInPacket[currentReadout, 9] = vmm3.OTh
                    readoutInPacket[currentReadout, 10] = vmm3.TDC
                    readoutInPacket[currentReadout, 11] = vmm3.GEO

                    self.dprint(" \t Packet: {} ({} bytes), Hit: {}, Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
                                .format(self.truePacketCount,ESSlength,currentReadout+1,vmm3.Ring,vmm3.Fen,vmm3.VMM,vmm3.hybrid,vmm3.ASIC,vmm3.Channel,vmm3.timeStamp,vmm3.BC,vmm3.OTh,vmm3.ADC,vmm3.TDC,vmm3.GEO))

                
                    ###########
                    
            self.data.append(readoutInPacket)

            # check 
            packetLength = readoutCount*self.dataPacketLength + self.ESSheaderSize  # bytes
            if packetLength != ESSlength and self.truePacketCount == 1:
               print('something wrong ... with this packet: exp size {} bytes, found {} bytes.'.format(ESSlength,packetLength))
               
            roughNumOfPackets   = round(self.fileSize/ESSlength) 
            # roughNumOfTotalHits = round(roughNumOfPackets*numOfHits)
            steps = round(roughNumOfPackets/4)
            if np.mod(self.truePacketCount,steps) == 0:
                    percents = int(round(100.0 * self.truePacketCount / float(roughNumOfPackets), 1))
                    print('['+format(percents,'01d') + '%]',end=' ')
     
        print('[100%]',end=' ') 
        
        # check 
        if self.data.Ring.shape[0] != self.totalReadoutCount:
            print('\nsomething wrong ... mismatch between data exp. length {} and what was read {}'.format(self.totalReadoutCount,self.data.Ring.shape[0]))
                          
        print('\ndata loaded - found {} hits ({} kbytes) - Packets: valid {}, nonESS {}, All {})'.format(self.totalReadoutCount,self.truePacketCount*ESSlength/1e3,self.truePacketCount,self.nonESSPacketCount,self.packetCount))    
                


if __name__ == '__main__':
   # parser = argparse.ArgumentParser()
   # parser.add_argument("-f", metavar='file', help = "pcap file",
   #                     type = str, default = "VMM3a_Freia.pcapng")
   # parser.add_argument('-d', action='store_true', help = "add debug print")

   tProfilingStart = time.time()

   # arg = parser.parse_args()
   filePath = './'+"VMM3a_Freia.pcapng"

   pr = pcap_reader(filePath)
   # pr.debug = True
   pr.read()
   vmm3 = pr.data
   
   # for k in range(446900,447000,1):
   #     print(" \t Ring {}, FEN {}, VMM {}, hybrid {}, ASIC {}, Ch {}, Time {} s, BC {}, OverTh {}, ADC {}, TDC {}, GEO {} " \
   #                              .format(vmm3.Ring[k],vmm3.Fen[k],vmm3.VMM[k],vmm3.hybrid[k],vmm3.ASIC[k],vmm3.Channel[k],vmm3.timeStamp[k],vmm3.BC[k],vmm3.OTh[k],vmm3.ADC[k],vmm3.TDC[k],vmm3.GEO[k]))

   
   
   tElapsedProfiling = time.time() - tProfilingStart
   print('\n Data Loading Completed in %.2f s' % tElapsedProfiling) 