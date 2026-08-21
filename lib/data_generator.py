#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 20 21:21:39 2026

@author: francescopiscitelli
"""

from lib.container_hits import hitsVMMnormal


def hits_gen():
    
    n = 14
    
    h = hitsVMMnormal(size=n)
    
    h.fill_count = n
    
    h.matrix['ID'][0:] = 0
    
    h.matrix['adc'][0:] = 100
    
    h.matrix['pulseT'][0:] = 30000
    
    h.matrix['prevPT'][0:] = 15000

    
    h.matrix['plane'][0] = 0
    h.matrix['plane'][1] = 1
    h.matrix['plane'][2] = 0
    h.matrix['plane'][3] = 0
    h.matrix['plane'][4] = 1
    h.matrix['plane'][5] = 1
    h.matrix['plane'][6] = 1
    h.matrix['plane'][7] = 0
    h.matrix['plane'][8] = 1
    h.matrix['plane'][9] = 1
    h.matrix['plane'][10] = 1
    h.matrix['plane'][11] = 0
    h.matrix['plane'][12] = 1
    h.matrix['plane'][13] = 0
    
    
    
    h.matrix['index'][0] = 2     #ev 1 w
    h.matrix['index'][1] = 13    #ev 1 s
    
    h.matrix['index'][2] = 5
    h.matrix['index'][3] = 6
    h.matrix['index'][4] = 16
    h.matrix['index'][5] = 17
    h.matrix['index'][6] = 18
    
    h.matrix['index'][7] = 9
    h.matrix['index'][8] = 21
    h.matrix['index'][9] = 29
    h.matrix['index'][10] = 22
    
    h.matrix['index'][11] = 14
    
    h.matrix['index'][12] = 34
    
    h.matrix['index'][13] = 29
    
    
    # 4 ev 1d
    #  3 ev 1d s one rej 
    #  2 ev 2d 
    
    
    
    h.matrix['timeStamp'][0] = 1
    h.matrix['timeStamp'][1] = 3
    h.matrix['timeStamp'][2] = 2000
    h.matrix['timeStamp'][3] = 2010
    h.matrix['timeStamp'][4] = 2020
    h.matrix['timeStamp'][5] = 2010
    h.matrix['timeStamp'][6] = 2025
    h.matrix['timeStamp'][7] = 3000
    h.matrix['timeStamp'][8] = 3000
    h.matrix['timeStamp'][9] = 3000
    h.matrix['timeStamp'][10] = 3000
    h.matrix['timeStamp'][11] = 6000
    h.matrix['timeStamp'][12] = 8000
    h.matrix['timeStamp'][13] = 10000
    
    
    
    return h
    
    