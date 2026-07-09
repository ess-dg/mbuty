
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 27 16:38:55 2021

@author: francescopiscitelli
"""

import os 
# from lib import libParameters as para
import sys
# import time
from datetime import datetime
import subprocess
import numpy as np

###############################################################################
############################################################################### 

class findPathApp():
    
    def check(self, appName):
        
        comm = 'which '+appName
        
        app = subprocess.run(comm,shell=True,capture_output=True,encoding='utf-8')

        if app.returncode == 0:
            # found
            self.flag = True
            temp = os.path.split(app.stdout)
            self.path = temp[0]+'/'
            
        else: 
            # not found
            self.flag = False
            self.path = ''
            
            
        return self.path, self.flag

############################################################################### 

class transferDataUtil():
             
    def syncData(self,sourcePath,destPath,verbose=True):
        
        command = 'rsync -av --progress'

        # command = 'cp'
        
        comm = command + ' ' + sourcePath + ' ' + destPath
        
        # print(comm)
   
        if verbose is False:
            status = os.system(comm+ ' >/dev/null')
        else:
            print('\n ... syncing data ...')
            status = os.system(comm)
        
        # NOTE: it will ask for password 
        
        # disp(cmdout)
        
        if status == 0: 
            if verbose is True: 
              print('\n data sync completed')
        else:
              print('\n \033[1;31mERROR ... connection refused! \n\033[1;37m')
        
        # print(status)      
        if verbose is True:     
            print('\n-----')
        
        return status 
    
###############################################################################   

class pcapConverter():
    def __init__(self, parameters):
        
        self.parameters = parameters   
        
        self.flag  = None
        
        self.fileName_OUT = ''
     
    def convertPcap2Pcapng(self,pcapFile_PathAndFileName_IN,pcapngFile_PathAndFileName_OUT):
        
        # comm = 'tcpdump -r file_to_convert -w file_converted '
        
        # self.parameters.pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
        
        pathToTshark = self.parameters.fileManagement.pathToTshark
        
        if os.path.isfile(pathToTshark+'tshark') is False:
            
            # try first to find the path 
            pathToTshark, flag = findPathApp().check('wireshark')
            
            if flag is False:   
                print('\n \033[1;31mFile conversion pcap to pcapng cannot be performed. \n Tshark not found in your system, either set right path to Thark in parameters or install it.\033[1;37m\n')
                print('... exiting.')
                sys.exit()
        
        # if os.path.isfile(pathToTshark+'tshark') is False: 
        #     print('\n \033[1;31mFile conversion pcap to pcapng cannot be performed. \n Tshark not found in your system, either set right path to Thark in parameters or install it.\033[1;37m\n')
        #     print('... exiting.')
        #     sys.exit()
        
        else:
        
            print(' -> converting pcap to pcapng ...')

            status = os.system(pathToTshark+'tshark -F pcapng -r ' + pcapFile_PathAndFileName_IN + ' -w '+ pcapngFile_PathAndFileName_OUT )
        
            if status == 0: 
              print(' conversion completed!')
            else:
              print('\033[1;31mERROR ... \n\033[1;37m')

      
    def checkExtensionAndConvertPcap(self, pcapFile_PathAndFileName_IN):   
          
          if os.path.isfile(pcapFile_PathAndFileName_IN) is True:
              
             temp1 = os.path.split(pcapFile_PathAndFileName_IN)
             pcapFilePath    = temp1[0]+'/'
             pcapFileNameExt = temp1[1]
             
             temp2 = os.path.splitext(pcapFileNameExt)
             pcapFileName = temp2[0]
             pcapFileExt  = temp2[1]
   
             if pcapFileExt == '.pcap':
                 
                 self.flag = False
                 
                 print('pcap file selected')
                 
                 self.fileName_OUT = pcapFileName + '_convertedToPcapng.pcapng'
                 
                 # check if already converted 
                 if os.path.isfile(pcapFilePath+self.fileName_OUT) is False:
                 
                     self.convertPcap2Pcapng(pcapFile_PathAndFileName_IN, pcapFilePath+self.fileName_OUT)
                     
                 else:
                     print(' -> converted file already exists.')
              
             elif pcapFileExt == '.pcapng':
                 
                 self.flag = True
                 
                 self.fileName_OUT = pcapFileNameExt
                 
             # return self.flag    
                 
          else:
              
              temp1 = os.path.split(pcapFile_PathAndFileName_IN)
              pcapFilePath    = temp1[0]+'/'
              pcapFileNameExt = temp1[1]
              
              print('\n \033[1;31m---> File: ' + pcapFileNameExt + ' DOES NOT EXIST \033[1;37m')
              print('\n ---> in folder: ' + pcapFilePath + ' \n')
              print(' ---> Exiting ... \n')
              print('------------------------------------------------------------- \n')
              sys.exit()

############################################################################### 
    
class dumpToPcapngUtil():

    def __init__(self, pathToTshark, interface='en0', destPath='./', fileName='temp', numOfFiles=1):

        if os.path.isfile(pathToTshark+'tshark') is False:
            
            # try first to find the path 
            pathToTshark, flag = findPathApp().check('wireshark')
            
            if flag is False:   
                print('\n \033[1;31mFile Tshark not found in your system, either set right path to Thark in parameters or install it.\033[1;37m\n')
                print('... exiting.')
                sys.exit()

        self.pathToTshark = pathToTshark
        self.interface    = interface
        
        nowTime = datetime.now()
        current_date = nowTime.strftime("%Y%m%d")
        current_time = nowTime.strftime("%H%M%S")

        self.fileh    = destPath+current_date+'_'+current_time+'_'+fileName
        self.filehExt = '.pcapng'
        
        self.acqNum = np.arange(0,numOfFiles,1)
        
        format(self.acqNum[k],'05d')
        
    def dump(self,typeCapture='packets',extraArgs=100):
    
        self.typeCapture = typeCapture
        # comm = 'sudo tcpdump -1 eno1 -w filename udp port 9000'
        
        print('\n ... recording pcapng file ...')

        ###############################
        if self.typeCapture == 'packets':
            
            print(' by packets -> {} packets'.format(extraArgs))
            
            numOfPackets = extraArgs
            
            self.recordByNumOfPackets(numOfPackets)
            
        elif self.typeCapture == 'filesize':
            
            print(' by file size -> {} kbytes'.format(extraArgs))
            
            sizekbytes = extraArgs
            
            self.recordBySize(sizekbytes)
            
            
        elif self.typeCapture == 'duration':
            
            print(' by duration -> {} s'.format(extraArgs))
            
            duration_s = extraArgs
            
            self.recordByDuration(duration_s)  
            
        ###############################   
        
        string1 = self.pathToTshark+'tshark'+' -i '+str(self.interface)
        string2 = ' -w '+self.fileh
        
        self.command = string1+self.commandDetails+string2
        
        status = os.system(self.command)

        if status == 0: 
              print('\n recording completed!')
        else:
              print('\n \033[1;31mERROR ... \n\033[1;37m')
              
        return status      
              
 ###############################       
    def recordByNumOfPackets(self,numOfPackets):
          
        self.commandDetails = ' -c '+str(numOfPackets)

    def recordBySize(self,sizekbytes):  
        
        self.commandDetails = ' -a filesize:'+str(sizekbytes)
    
    def recordByDuration(self,duration_s):  
        
        self.commandDetails = ' -a duration:'+str(duration_s)
         
                 
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
                acqIsOver = False
            elif lines[0] == 'finished' :
                acqIsOver = True
                
        else:
            
            acqIsOver = None
            print('status file does not exist')
            sys.exit()
    
            
        return acqIsOver

        
###############################################################################
###############################################################################

if __name__ == '__main__':


   # path  = '/Users/francescopiscitelli/Documents/PYTHON/MBUTYcap/data/'
   # file1 = path+'freia_1k.pcap'
   
   # file2 = path+'freia_1k_converted.pcapng'
   
   # currentPath = os.path.abspath(os.path.dirname(__file__))+'/'

   # parameters = para.parameters(currentPath)
   
   # # a = tsharkUtil(parameters)
   
   # # a.convertPcan2Pcapng(file1, file2)
   
   # b = pcapConverter(parameters).checkExtensionAndConvertPcap(file1)
   
    # pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'

    # rec = dumpToPcapngUtil(pathToTshark, interface='en0', destPath='/Users/francescopiscitelli/Desktop/reducedFile/', fileName='temp')

    # # rec.dump('duration',2)
   
    # # rec.dump('filesize',130)
   
    # rec.dump('packets',15)
   
   # path, flag = findPathApp().check('wireshark')
   
    destPath  = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'

    st = acquisitionStatus(destPath)   

    # st.checkExist()  
    
    # st.read()
    
    # flag = st.flipStatus()
   
    # print(flag)
    
    acqOver = st.checkStatus()
    
    print(acqOver)
