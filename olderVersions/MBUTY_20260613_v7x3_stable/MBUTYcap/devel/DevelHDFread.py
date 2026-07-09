#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 13 15:45:19 2024

@author: francescopiscitelli
"""
import numpy as np
import time
import os
import sys
import matplotlib.pyplot as plt
import h5py

# import matplotlib
# # matplotlib.use(‘Qt5Agg’)
from PyQt5.QtWidgets import QApplication, QFileDialog, QDialog, QGridLayout, QLabel, QLineEdit
app = QApplication(sys.argv)

### import the library with all specific functions that this code uses 
from lib import libReadPcapngVMM as pcapr
from lib import libSampleData as sdat
from lib import libMappingMG as maps
from lib import libCluster as clu
from lib import libAbsUnitsAndLambdaMG as absu
from lib import libHistograms as hh
from lib import libFileManagmentUtil as fd
from lib import libParameters as para
from lib import libTerminal as ta
from lib import libPlottingMG as plo
from lib import libEventsSoftThresholds as thre
from lib import libReducedFileH5 as saveH5
from lib import libVMMcalibration as cal 


###############################################################################
###############################################################################
###############################################################################

pathAndFileName = '/Users/francescopiscitelli/Desktop/reducedFile/MGdata_reduced.h5'


sav = saveH5.readReducedDataFromHDF(pathAndFileName)
    
sav.read()   

events    = sav.events 
eventsMON = sav.eventsMON


# parameters = para.parameters()
# parameters.init_empty()
       
# events    = clu.events()
# eventsMON = clu.events()
   

       
# temp2 = os.path.split(pathAndFileName)
# filePath = temp2[0]+'/'
# fileName = temp2[1]




    
    
       
# if os.path.exists(pathAndFileName) is False:
#       print(' \033[1;31m---> File: '+fileName+' DOES NOT EXIST \033[1;37m')
#       print(' ---> in folder: '+filePath)
#       # print('  ---> in folder: '+self.filePath+' -> ... it will be skipped!')
#       print(' ---> Exiting ... \n')
#         # print('------------------------------------------------------------- \n')
#       sys.exit()
# else:
   
#     try:
    
#         fid    = h5py.File(pathAndFileName, "r")
        
#     except:
         
#           print('Unable to open h5 file')
#           sys.exit()
         

      
# showTree = True

# for key_main in fid.keys():
#     # self.dprint('1-',key_main) 
   
#     # entry1
#     main = fid[key_main] 
   
#     for key_gr in main.keys():
#         # self.dprint('2-\t',key_gr)
       
#         # detector, monitor, parameters
#         group = main[key_gr]
       
#         for key_subGr in group.keys():
#             # self.dprint('3-\t\t\t',key_subGr)
            
#             # events
#             subGr = group[key_subGr]
          
#             if key_gr == 'detector' and key_subGr == 'events':   
#                 for keyd in subGr.keys(): 
#                     # self.dprint('4-\t\t\t\t\t',keyd)
                       
#                     events.__dict__[keyd] = subGr[keyd][()]
                    
#             if key_gr == 'monitor' and key_subGr == 'events':   
#                 for keyd in subGr.keys(): 
#                     # self.dprint('4-\t\t\t\t\t',keyd)
                       
#                     eventsMON.__dict__[keyd] = subGr[keyd][()]

                    
#             # if key_gr == 'parameters':   
                
#             #     for keyd in subGr.keys(): 
#             #         self.dprint('4-\t\t\t\t\t',keyd)
                
#             #         self.parameters.__dict__[key_subGr].__dict__[keyd] = subGr[keyd][()]

#             #     for att, value in zip(subGr.attrs,subGr.attrs.values()):
#             #         self.dprint('4-\t\t\t\t\t',(att+' -> '+value))  
                    
#             #         self.parameters.__dict__[key_subGr].__dict__[att] = value


# fid.close()