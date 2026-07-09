#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 22 08:56:38 2023

@author: francescopiscitelli
"""

import numpy as np 

import libReadPcapngVMM as rr 

NSperClockTick = 11.356860963629653  #ns per tick ESS for 88.0525 MHz

path = '/Users/francescopiscitelli/Desktop/dataVMM/'

filePath=path+'20230821_135744_pkts10_testinghybrdis-monitor_00000.pcapng'


pcapng = rr.pcapng_reader_PreAlloc(filePath,NSperClockTick,'coarse')
pcapng.allocateMemory()
pcapng.read()
readouts = pcapng.readouts

readoutsArray_pre = readouts.concatenateReadoutsInArrayForDebug()

readouts_pre = pcapng.readouts

selVMMdata = readouts.Ring <= 10 

# print(selVMMdata)

# readouts.TDC[selVMMdata] = 33

# readouts.TDC[~selVMMdata] = 101


readouts.timeStamp[selVMMdata]  = readouts.timeCoarse[selVMMdata] + rr.VMM3A_convertCalibrate_TDC_ns(readouts.TDC[selVMMdata],NSperClockTick,time_offset=0,time_slope=1).TDC_ns

readouts.timeStamp[~selVMMdata] = readouts.timeCoarse[~selVMMdata]

readoutsArray = readouts.concatenateReadoutsInArrayForDebug()



