#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 11 15:28:16 2023

@author: francescopiscitelli
"""
import pcapng as pg
import os

filePath = '/Users/francescopiscitelli/Desktop/data4Testing/'
  
file = '20230911_103911_pkts100_intpulser-H0-vmm1ch5-12-18-H1-vmm0ch20-21-22-cfg-0x2_00000.pcapng'


filePathAndFileName = filePath+file


# ff = open(filePathAndFileName, 'rb')
# scanner = pg.FileScanner(ff)



fileSize   = os.path.getsize(filePathAndFileName) #bytes
print('{} bytes'.format(fileSize))