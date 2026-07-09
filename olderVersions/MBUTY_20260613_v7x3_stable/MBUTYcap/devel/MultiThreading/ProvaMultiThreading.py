#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct  4 15:20:39 2021

@author: francescopiscitelli
"""
import threading
import time
from lib import libTerminal as ta
import sys
import signal

############################################################################### 
###############################################################################


class background():
    
    def __init__(self,sourcePath,destPath):
        
        self.destPath   = destPath
        self.sourcePath = sourcePath
        
        self.ta = ta
    
        self.status = self.ta.acquisitionStatus(destPath)

        self.transferData = self.ta.transferDataUtil()

        # self.status.set_FinStatus()
        # self.status.set_RecStatus()

        # self.startTime = time.time()

        # self.acqOverPlot = True
        
        self.exit_event = threading.Event()

    def checkAcq(self):

        # while True:
            
        for  k in range(10):
            time.sleep(1)
       
            # self.transferData.syncData(self.sourcePath, self.destPath, verbose=False)
            self.acqIsOver = self.status.checkStatus()
            
            # print(self.acqOver)
        
            # timeElaps =  time.time() - self.startTime 
            
            if  self.acqIsOver is False:
            
                # print('\033[1;33m\nRECORDING ... elapsed time '+str('%.0f' % timeElaps)+' s \033[1;37m',end=' ')
                
                print('\033[1;33m\nRECORDING ... \033[1;37m',end=' ')
                
                for tt in range(5):
                    print('%',end=' ')
                    time.sleep(1)
        
                    if self.exit_event.is_set():
                        print('\nexecution terminated by user')
                        sys.exit() 
            
            elif self.acqIsOver is True:   
                
                print('NOT RECORDING ... ',end=' ')
    
                if self.exit_event.is_set():
                   print('\nexecution terminated by user')
                   sys.exit() 
                    
            return self.acqIsOver       

    def signal_handler(self, signum, frame):
        self.exit_event.set()

################################
 
# class foreground():
    
#     def run(self,acqOver):
           
#             print(acqOver)
#             time.sleep(2)
        
    
    
   
############################################################################### 
###############################################################################  
    
if __name__ == '__main__':
    
    sourcePath = 'essdaq@172.30.244.233:~/pcaps/'
    destPath   = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'
    
    status = ta.acquisitionStatus(destPath)  

    # transferData = ta.transferDataUtil()
    
    status.set_FinStatus()
    status.set_RecStatus()

    # startTime = time.time()
    
    bg = background(sourcePath,destPath)
    # fg = foreground()

    signal.signal(signal.SIGINT, bg.signal_handler)
    
    b = threading.Thread(name='background', target=bg.checkAcq())
    # f = threading.Thread(name='foreground', target=fg.run(bg.checkAcq()))
   
    
    b.start()
    # f.start()
    
    b.join()
    
