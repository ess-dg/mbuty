#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 30 09:31:42 2021

@author: francescopiscitelli
"""

# import numpy as np
import os
import sys 

###############################################################################
############################################################################### 

class acquisitionStatus():
    def __init__(self, destPath):
        
        self.pathFile = destPath+'acquisition.status'

    def checkExist(self):   

        if os.path.isfile(self.pathFile) is True:
            # if the file already exists open it 
            flag = True
            # fo   = open(self.pathFile, "w+")
            
        else:    
            # open/create a new file and add the field names
            flag = False
            fo   = open(self.pathFile, "w")
            fo.writelines('recording')
            fo.close()
            
        return flag   
    
    def read(self):
        
        flag = self.checkExist()
        
        # print(flag)
        
        fo = open(self.pathFile, "r")
        lines = fo.readlines()
        # print(lines) 
            
        fo.close()
        
        return lines
    
    def set_RecStatus(self):
        
        lines = self.read()
   
        fo = open(self.pathFile, "w")
        fo.writelines('recording')
        fo.close()  
        
    def set_FinStatus(self):
        
        lines = self.read()
   
        fo = open(self.pathFile, "w")
        fo.writelines('finished')
        fo.close() 
        
    def flipStatus(self):
        
        lines = self.read()
        
        # print(lines) 
        
        if lines[0] == 'recording':
           flag = False
           fo = open(self.pathFile, "w")
           fo.writelines('finished')
           fo.close()
        elif lines[0] == 'finished' :
           flag = True
           fo = open(self.pathFile, "w")
           fo.writelines('recording')
           fo.close()   
           
        return flag   
      
    def checkStatus(self):
        
        if os.path.isfile(self.pathFile) is True:
            
            fo = open(self.pathFile, "r")
            lines = fo.readlines()
            # print(lines) 
            fo.close()
            
            if lines[0] == 'recording':
                acqOver = False
            elif lines[0] == 'finished' :
                acqOver = True
                
        else:
            
            acqOver = None
            print('status file does not exist')
            sys.exit()
    
            
        return acqOver
        
###############################################################################
###############################################################################

if __name__ == '__main__':

    destPath  = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'

    st = acquisitionStatus(destPath)   

    # st.checkExist()  
    
    # st.read()
    
    # flag = st.flipStatus()
   
    # print(flag)
    
    acqOver = st.checkStatus()
    
    print(acqOver)
    
    