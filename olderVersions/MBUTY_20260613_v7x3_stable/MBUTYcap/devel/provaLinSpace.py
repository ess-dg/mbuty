#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep  7 09:08:12 2021

@author: francescopiscitelli
"""

import numpy as np

import libHistograms as hh



positionReconstruction = 2

cass = [1,2,3]

  # binning position, do  not change otherwise binning with linspace wrong !!
if positionReconstruction == 0: # w x s max max
                posWbins = 32
                posSbins = 64
elif positionReconstruction == 1: # w x s CoG CoG
                posWbins = 64
                posSbins = 128 
elif positionReconstruction == 2: # w x s max CoG
                posWbins = 64
                posSbins = 128
       



# Ns = 64
# Nw = 32            
            
# ss = np.linspace(0, Ns-1, posSbins)
            
# Nc = len(cass)

# start = 0

# stop  = Nw*Nc-1

# # steps = (posWbins+1)*Nc-1-np.mod(posWbins+1,Nw)

# steps = (32)*Nc - 1
                
# ww =   np.linspace(start, stop, steps)  


# # print(ww) 

# step = 1

# aa =  np.arange(0,stop + step,step)  

# ww =   np.linspace(0, stop, steps)        

# Nc = 3
      
# wbins = 256

# nwires = 32

# start  = 0
# stop   = Nc*nwires-1
# steps  = Nc*wbins - int(wbins/nwires - 1)

# print(wbins/nwires - 1)

# # -round(wbins/nwires)

# # -int(wbins/nwires)

# # binSize = (aa.stop - aa.start)/(aa.steps-1)

# bb = np.linspace(start,stop,steps)

# print(binSize)

# aa.update()

# bb= aa.axis

# print(bb)