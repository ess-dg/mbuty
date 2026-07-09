#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 28 14:24:18 2021

@author: francescopiscitelli
"""
import argparse
import os
import sys
from datetime import datetime
import subprocess

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

class dumpToPcapngUtil():

    def __init__(self, pathToTshark, interface='en0', destPath='./', fileName='temp'):

        
        if os.path.isfile(pathToTshark+'tshark') is False:
            
            # try first to find the path 
            pathToTshark, flag = findPathApp().check('wireshark')
            
            if flag is False:   
                print('\n \033[1;31mFile Tshark not found in your system, either set right path to Thark in parameters or install it.\033[1;37m\n')
                print('... exiting.')
                sys.exit()

        self.pathToTshark = pathToTshark
        self.interface    = interface
        self.destPath     = destPath
        
        nowTime = datetime.now()
        current_date = nowTime.strftime("%Y%m%d")
        current_time = nowTime.strftime("%H%M%S")

        self.fileh = destPath+current_date+'_'+current_time+'_'+fileName+'.pcapng'
        
    def dump(self,typeCapture='packets',extraArgs=100):
    
        self.typeCapture = typeCapture
        # comm = 'sudo tcpdump -1 eno1 -w filename udp port 9000'
        
        print('\n ... recording pcapng file ...')
        
        st = acquisitionStatus(self.destPath)  
        st.setRecStatus()

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
              st.setFinStatus()
        else:
              print('\n \033[1;31mERROR ... \n\033[1;37m')
              st.setRecStatus()
              
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
        
        self.pathFile = destPath+'dataAcquisition.status.txt'
        # self.fo = None

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
            
    # def __del__(self):
    #     self.fo.close()
    
    def read(self):
        
        flag = self.checkExist()
        
        # print(flag)
        
        fo = open(self.pathFile, "r")
        lines = fo.readlines()
        # print(lines) 
            
        fo.close()
        
        return lines
    
    def setRecStatus(self):
        
        lines = self.read()
   
        fo = open(self.pathFile, "w")
        fo.writelines('recording')
        fo.close()  
        
    def setFinStatus(self):
        
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
    
   # parser = argparse.ArgumentParser()
   # # parser.add_argument("-i", metavar='interface', help = "interface", type = str, default = "enp0s25")
   # parser.add_argument("-f", "--file", metavar='fileName', help = "pcapng file", type = str, default = "temp")
   # parser.add_argument("-i", "--interface", metavar='interface', help = "interface", type = str, default = "en0")
   # parser.add_argument("-t", "--tshark", metavar='pathToTshark', help = "tshark path", type = str, default = "/Applications/Wireshark.app/Contents/MacOS/")
   # parser.add_argument("-d", "--destination", metavar='dest path', help = "dest path", type = str, default = "/Users/francescopiscitelli/Desktop/reducedFile/")
   
   # parser.add_argument("-c", "--captureType", metavar='captureType', help = "captureType: packets, filesize (kb) or duration (s)", type = str, default = "packets")
   
   # parser.add_argument("-q", "--quantity", metavar='quantity', help = "quantity: num ofpackets, or kb filesize, or s for duration", type = str, default = "100")
   
   parser = argparse.ArgumentParser()
   # parser.add_argument("-i", metavar='interface', help = "interface", type = str, default = "enp0s25")
   parser.add_argument("-f", "--file", metavar='fileName', help = "pcapng file", type = str, default = "temp")
   parser.add_argument("-i", "--interface", metavar='interface', help = "interface", type = str, default = "p4p1")
   parser.add_argument("-t", "--tshark", metavar='pathToTshark', help = "tshark path", type = str, default = "/usr/sbin/")
   parser.add_argument("-d", "--destination", metavar='dest path', help = "dest path", type = str, default = "/home/essdaq/pcaps/")
   
   parser.add_argument("-c", "--captureType", metavar='captureType', help = "captureType: packets, filesize (kb) or duration (s)", type = str, default = "packets")
   
   parser.add_argument("-q", "--quantity", metavar='quantity', help = "quantity: num ofpackets, or kb filesize, or s for duration", type = str, default = "100")
   
   args  = parser.parse_args()
   
   rec = dumpToPcapngUtil(pathToTshark=args.tshark, interface=args.interface, destPath=args.destination, fileName=args.file)

   # rec = dumpToPcapngUtil(pathToTshark, interface='en0', destPath='/Users/francescopiscitelli/Desktop/reducedFile/', fileName='temp')

   # rec.dump('duration',2)
   
   # rec.dump('filesize',130)
   
   rec.dump(args.captureType,args.quantity)
