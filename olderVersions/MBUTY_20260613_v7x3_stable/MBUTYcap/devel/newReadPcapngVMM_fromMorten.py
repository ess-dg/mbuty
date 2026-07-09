#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
########    V1.0 2021/08/17     francescopiscitelli      ######################
########    script to read the pcapng file from VMM readout
###############################################################################
###############################################################################

import argparse
import numpy as np
import pcapng as pg

# import sys
# import time


class VMM3a():
    def __init__(self, buffer, resolution):
        # decode into little endian integers
        self.bDRingID = int.from_bytes(buffer[0:1], byteorder='little')
        self.bDFenID  = int.from_bytes(buffer[1:2], byteorder='little')
        bDLength = int.from_bytes(buffer[2:4], byteorder='little')
        bDTimeHI = int.from_bytes(buffer[4:8], byteorder='little')
        bDTimeLO = int.from_bytes(buffer[8:12], byteorder='little')
        bDBC     = int.from_bytes(buffer[12:14], byteorder='little')
        bDOTADC  = int.from_bytes(buffer[14:16], byteorder='little')
        bD0GEO   = int.from_bytes(buffer[16:17], byteorder='little')
        bDTDC    = int.from_bytes(buffer[17:18], byteorder='little')
        self.bDVMM = int.from_bytes(buffer[18:19], byteorder='little')
        self.bDChannel = int.from_bytes(buffer[19:20], byteorder='little')

        self.bDADC = bDOTADC & 0x3FF  #extract only 10 LSB
        bDOT = bDOTADC >> 15    #extract only 1 MSB

        # NOT CLEAR bDOT HOW IT TURNS OUT TO BE  1

        bD0       = bD0GEO >> 7
        bDGEO     = bD0GEO & 0x3F

        # if bD0 == 0: # normal mode
        #    pass
        # elif bD0 == 1: # calibration mode
        #    pass

        #  in seconds
        # timeStamp =  bDTimeHI + bDTimeLO*resolution + ( resolution*2 - (bDTDC*(60/255))*1e-9 )  #fine time resolution
        self.timeStamp =  bDTimeHI + bDTimeLO * resolution # coarse time resolution


class pcap_reader():
    def __init__(self, args):
        self.datapathinput = './'
        self.ff = open(self.datapathinput + args.f, 'rb')
        self.debug = args.d

        self.offset = 25            #bytes Num of bytes after the word (cookie) ESS = 0x 45 53 53
        self.dataPacketLength = 20  #bytes
        self.resolution = 11.25e-9  #s per tick

        self.PacketCount = 0
        self.TruePacketCount = 0
        self.NonESSCount = 0
        self.TotalHitCount = 0


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

        data = np.zeros((0,6),dtype = 'float64')

        for block in scanner:
            self.PacketCount += 1
            HitCount = 0

            try:
                packetLength = block.packet_len
                packetData   = block.packet_data
            except:
                continue

            self.TruePacketCount += 1
            self.dprint("packet {} - length {}".format(self.PacketCount, packetLength))

            indexESS = packetData.find(b'ESS')

            if indexESS == -1:
                self.NonESSCount += 1
                continue

            indexDataStart = indexESS + 2 + self.offset + 1

            # check that ESS is always in the same place
            # tempIndexDataStart.append(indexDataStart)

            HitCount = (packetLength - indexDataStart) / self.dataPacketLength
            self.dprint("HitCount {}".format(HitCount))

            if HitCount.is_integer() is not True:
                print('something wrong with data bytes dimensions')
                break
            else:
                HitCount = int(HitCount)
                self.TotalHitCount += HitCount
                hitsInPacket = np.zeros((HitCount, 6), dtype = 'float64')
                # cont = 0
                for currentHit in range(HitCount):
                # for currentHit in range(1):
                    # print(currentHit)

                    # offset = 72
                    # buffe1          = datap[72:92]
                    # buffe2          = datap[92:112]
                    # buffeSecondLast = datap[8952:8972]
                    # buffeLast       = datap[8972:8992]

                    indexStart = indexDataStart + self.dataPacketLength * currentHit
                    indexStop  = indexDataStart + self.dataPacketLength * (currentHit + 1)

                    buffer = packetData[indexStart:indexStop]

                    vmm3 = VMM3a(buffer, self.resolution)

                    hitsInPacket[currentHit, 0] = vmm3.bDRingID
                    hitsInPacket[currentHit, 1] = vmm3.bDFenID
                    hitsInPacket[currentHit, 2] = vmm3.bDVMM
                    hitsInPacket[currentHit, 3] = vmm3.bDChannel
                    hitsInPacket[currentHit, 4] = vmm3.bDADC
                    hitsInPacket[currentHit, 5] = vmm3.timeStamp

                    self.dprint("Ring {}, FEN {}, VMM {}, ADC {}, Channel {}, Time {}".format( \
                      vmm3.bDRingID, vmm3.bDFenID, vmm3.bDVMM, vmm3.bDChannel, vmm3.bDADC, vmm3.timeStamp))

                    # ADD ALSO RING AND FEN

                    ###########
            data = np.append(data, hitsInPacket, axis = 0)

        # check
        if data.shape[0] != self.TotalHitCount:
           print('something wrong ...')

        print('data loaded - found ' + str(np.shape(data)[0])+' hits')

        print("PacketCount     {}".format(self.PacketCount))
        print("TruePacketCount {}".format(self.TruePacketCount))
        print("Not ESS Readout {}".format(self.NonESSCount))
        print("TotalHitCount   {}".format(self.TotalHitCount))


if __name__ == '__main__':
   parser = argparse.ArgumentParser()
   parser.add_argument("-f", metavar='file', help = "pcap file", type = str, default = "VMM3a_Freia.pcapng")
   parser.add_argument('-d', action='store_true', help = "add debug print")

   pr = pcap_reader(parser.parse_args())
   pr.read()
