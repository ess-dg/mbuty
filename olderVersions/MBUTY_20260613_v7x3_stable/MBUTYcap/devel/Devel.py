#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 16 13:28:05 2024

@author: francescopiscitelli
"""

import numpy as np 


hitsCassette = np.array([0,1,2,3,4,5])


cassette1ID = 7

presentCassettes = np.unique(hitsCassette[~np.isnan(hitsCassette)])

if not(cassette1ID in presentCassettes):
    
    flag = False 
    
    if np.any(presentCassettes<=-1):
     # there is unmapped data in hits, might be MON
        print('\n \t \033[1;33mWARNING: Cassette ID ',str(cassette1ID),' not found! Skipped! These hits only contains Cassettes IDs:', end=' ')
        presentCassettes = presentCassettes[presentCassettes>=0]
        for cc in presentCassettes:
            print(int(cc),end=' ')
        print('and UNMAPPED data (maybe MON)\033[1;37m',end=' ')
        
    else:
        # there is NO unmapped data in hits
        print('\n \t \033[1;33mWARNING: Cassette ID ',str(cassette1ID),' not found! Skipped! These hits only contains Cassettes IDs:', end=' ')
        for cc in presentCassettes:
            print(int(cc),end=' ')
        print('\033[1;37m',end=' ')
    
else: 
    flag = True
    
print(flag) 