#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 25 13:44:17 2024

@author: francescopiscitelli
"""

timeSourceBytes = int.to_bytes(0xD5, length=1, byteorder='little')

timeSourceBytes = 0b0101

bit0 = (timeSourceBytes & 0x1) 
bit1 = (timeSourceBytes & 0x2) >> 1
bit2 = (timeSourceBytes & 0x4) >> 2
bit3 = (timeSourceBytes & 0x8) >> 3

print(bin(timeSourceBytes))

if bit0 == 0:
    src = 'MRF timestamp'
elif bit0 == 1:
    src = 'local timestamp'

if bit1 == 0:
    iss = 'MRF sync'
elif bit1 == 1:
    iss = 'local sync'

if bit2 == 0:
    sm = 'internal'
elif bit2 == 1:
    sm = 'external (TTL)'
    
if bit3 == 0:
    status = 'OK'
elif bit3 == 1:
    status = 'Error'

print("checking time source --> source: {}, internal sync source: {}, sync method: {}, status: {}".format(src,iss,sm,status))
# return tsrc