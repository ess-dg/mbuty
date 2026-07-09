#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 19:48:21 2021

@author: francescopiscitelli
"""
import time
import random
import threading 
import signal 
import sys
from lib import libTerminal as ta

############################################################################### 
###############################################################################

class background:
    
   def __init__(self,sourcePath,destPath):
       
      self.sourcePath = sourcePath
      self.destPath   = destPath
      
      signal.signal(signal.SIGINT,self.signal_handler)
      self.keepGoing = True
      
      self.status       = ta.acquisitionStatus(self.destPath)
      self.acqIsOver    = self.status.checkStatus()
      self.transferData = ta.transferDataUtil()

   def checkInfiniteLoop(self):
       
      self.interval = 3
       
      while self.keepGoing:
        
          print('transferring data ...',end='')
          self.transferData.syncData(self.sourcePath, self.destPath, verbose=False)
          print(' -> completed.')
          self.acqIsOver = self.status.checkStatus()
          
          if  self.acqIsOver is False:
            
                # print('\033[1;33m\nRECORDING ... elapsed time '+str('%.0f' % timeElaps)+' s \033[1;37m',end=' ')
                
                print('\033[1;33m\nRECORDING ... \033[1;37m',end=' ')
                
                for tt in range(self.interval):
                    print('%',end=' ')
                    time.sleep(1)     
            
          elif self.acqIsOver is True:   
                
                print('\033[1;36mNOT RECORDING ... \033[1;37m')
                time.sleep(self.interval)

   def signal_handler(self, sig, frame):
       
       print('\nexecution terminated by user')        
       self.keepGoing = False
        # sys.exit()

#########################################

class foreground:
   def __init__(self,sourcePath,destPath):
      print('inside C2 init')
      self.background = background(sourcePath,destPath)

   def main(self):
      self.bg_th = threading.Thread(target=self.background.checkInfiniteLoop)
      self.bg_th.start()
      
      self.acqIsOver = self.background.acqIsOver
          
      print(self.acqIsOver)

   # def disp(self):
   #    print(self.background.list)

############################################################################### 
###############################################################################

    
if __name__ == '__main__':
    
    sourcePath = 'essdaq@172.30.244.233:~/pcaps/'
    destPath   = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
    
    status = ta.acquisitionStatus(destPath)  

    status.set_FinStatus()
    # status.set_RecStatus()
    
    
    foreground = foreground(sourcePath,destPath)
    foreground.main()
    time.sleep(2)
    # foreground.disp()
    # foreground.bg_th.join()