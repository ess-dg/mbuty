#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 27 16:38:55 2021

@author: francescopiscitelli
"""

import os 
# from lib import libParameters as para
import sys
import time
from datetime import datetime
import subprocess
import signal
# import numpy as np

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

class checkPathCreate():
    
    def __init__(self,path):
        
        exist = os.path.exists(path)
        
        if exist is False:
            
            print('\n --> \033[1;33mWARNING: Folder: '+path+'does not exist.\033[1;37m')

            inp = input('     press (y) to create or (n or enter) to quit ')
            
            if inp == 'y':
                os.mkdir(path)
                print(' --> folder created.')
            else:    
                print(' --> exiting.')
                sys.exit()
            

############################################################################### 
class transferDataUtil:
    def __init__(self):
        self.IS_WINDOWS = sys.platform.startswith("win")
        self.IS_MAC = sys.platform == "darwin"
        self.IS_LINUX = sys.platform.startswith("linux")
        self.current_subprocess = None

    def convert_path(self, win_path):
        """Convert Windows path to WSL format if needed."""
        if not self.IS_WINDOWS:
            return win_path
        # e.g., 'C:/Users/.../' -> '/mnt/c/Users/.../'
        return win_path.replace("C:\\", "/mnt/c/").replace("C:/", "/mnt/c/").replace("\\", "/")

    def syncData(self, sourcePath, destPath): # Removed 'verbose' parameter
        """
        Synchronizes data using rsync via subprocess.Popen.
        Always prints all rsync output.
        Supports:
        - Running independently of GUI (prints to console/redirector)
        - KeyboardInterrupt (Ctrl+C) handling for graceful termination
        - Integration with a global `current_subprocess_handle` for GUI stop button.

        Returns:
            int: 0 for success, non-zero for failure/interruption.
        """
        global current_subprocess_handle # Declare intent to modify the global handle

        # Construct the rsync command as a list for subprocess
        # Always include --progress for detailed output
        # Using --info=progress2 is generally better for rsync 3.1+
        # If your rsync is older, you might need to revert to just '--progress'
        base_cmd = ["rsync", "-av", "--progress"] # Always print progress

        # Handle Windows/WSL specific command prefix
        if self.IS_WINDOWS:
            destPath = self.convert_path(destPath)
            cmd = ["wsl"] + base_cmd + [sourcePath, destPath]
        else:
            cmd = base_cmd + [sourcePath, destPath]

        # --- Print command before execution ---
        print("\n... syncing data ... ")
        #print(f"\n (Executing: {' '.join(cmd)})\n")
        process = None # Initialize process handle
        status = 1 # Default to non-zero (failure)

        try:
            # Use subprocess.Popen for control
            # stdout=subprocess.PIPE and stderr=subprocess.STDOUT to capture/stream all output
            # text=True for universal newlines and string output
            # bufsize=1 for line-buffered output
            if not self.IS_WINDOWS:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid # Isolate child process from parent's Ctrl+C
                )
            else:
                 process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

            # --- Critical: Set the global subprocess handle ---
            current_subprocess_handle = process
            self._current_subprocess = process # Also set internal reference

            # Stream all output line by line
            for line in iter(process.stdout.readline, ''):
                # Check if the process was terminated externally while reading
                if process.poll() is not None:
                    print("Process terminated externally while reading output.\n")
                    break # Exit the loop if process is no longer running
                print(line, end='') # This relies on sys.stdout redirection

            # Wait for the process to complete and get its return code
            return_code = process.wait()
            status = return_code # Assign the actual return code to status

            if status == 0:
                print('\nData sync completed')
            else:
                # Check for termination signals (negative return codes on Unix-like)
                # or if the process was directly stopped by the GUI (current_subprocess_handle becomes None)
                if not self.IS_WINDOWS and status in (-signal.SIGTERM.value, -signal.SIGKILL.value):
                     print(f'\n\033[1;31mERROR ... data sync interrupted (code: {status})\n\033[1;37m')
                elif current_subprocess_handle is None: # This indicates an external stop (e.g., from stop_back_end)
                     print(f'\n\033[1;31mERROR ... data sync stopped by user (code: {status})\n\033[1;37m')
                else:
                    print('\n \033[1;31mERROR ... connection refused or other sync error! \n\033[1;37m')

        except KeyboardInterrupt:
            # This handles Ctrl+C when `syncData` is called directly (not in a GUI thread),
            # or if `raise_keyboard_interrupt` successfully injects one.
            print('\n\033[1;31mKeyboardInterrupt detected! Terminating rsync process...\033[1;37m\n')
            if process and process.poll() is None: # If the subprocess is still running
                try:
                    process.terminate() # Send SIGTERM (polite)
                    process.wait(timeout=5) # Give it time to exit
                except subprocess.TimeoutExpired:
                    process.kill() # Send SIGKILL (forceful)
                    process.wait()
            status = 1 # Indicate failure due to interruption (or specific exit code from subprocess)
            print('\n\033[1;31mData sync interrupted.\033[1;37m')

        except Exception as e:
            # Catch any other unexpected errors during subprocess execution
            print(f'\n\033[1;31mERROR ... An unexpected error occurred: {e}\n\033[1;37m')
            status = 1 # Indicate failure

        finally:
            # --- Critical: Clear the global subprocess handle ---
            if current_subprocess_handle == process:
                current_subprocess_handle = None
            # Also clear internal reference if this instance was responsible for it
            if self._current_subprocess == process:
                self._current_subprocess = None

            print('\n-----') # Always print separator

        return status


    
###############################################################################   

class pcapConverter():
    def __init__(self, parameters):
        
        self.parameters = parameters   
        
        self.flag  = None
        
        self.fileName_OUT = ''
     
    def convertPcap2Pcapng(self,pcapFile_PathAndFileName_IN,pcapngFile_PathAndFileName_OUT):
        
        pathToTshark = self.parameters.fileManagement.pathToTshark
        
        pathToTshark, flag = verifyTsharkInstallation().verify(pathToTshark)
        
        if flag is True:

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
              print('\n NOTE: file name must contain extension, e.g. *.pcapng\n')
              print(' ---> Exiting ... \n')
              print('------------------------------------------------------------- \n')
              sys.exit()

############################################################################### 

class verifyTsharkInstallation():
    def verify(self, initial_pathToTshark):
        
        if os.path.isfile(os.path.join(initial_pathToTshark,'tshark')) is True:
            
            flag = True
            verified_pathToTshark = initial_pathToTshark
            
        else:
            
            flag = False
            
            # print('1 not found in'+initial_pathToTshark)
  
            # try first to find the path 
            verified_pathToTshark, flag = findPathApp().check('wireshark')
            
            if flag is False:
                
                # print('2 not found in'+pathToTshark)
                
                verified_pathToTshark, flag = findPathApp().check('tshark')
                
                if flag is False:
                
                    # print('2 not found in'+pathToTshark)
                    
                    # print('go for the loop ... ')
                
                    presetPaths = [ '/usr/sbin/', '/usr/bin/','/Applications/Wireshark.app/Contents/MacOS/']
                    
                    # presetPaths = [ '/usr/sbin/', '/Applications/Wireshark.app/Contents/MacOS/', '/usr/bin/','ff']


                    # cont = 3
                    
                    for pat in presetPaths:
                    
        
                        if os.path.isfile(os.path.join(pat,'tshark')) is True:
                            verified_pathToTshark = pat
                            flag = True
                            # print(str(cont)+' ---> found in'+pathToTshark)
                            break
                        else:
                            flag = False
                            # print(str(cont)+' not found in'+pat)
                            
                        # cont = cont + 1 
  
            if flag is False:  
                
                flag = False
                print('\n \033[1;31mFile Tshark not found in your system, either set right path to Thark in parameters or install it.\033[1;37m\n')
                print('... exiting.')
                sys.exit()
 
        return verified_pathToTshark, flag 
    
############################################################################### 
    
class dumpToPcapngUtil():
    def __init__(self, pathToTshark, interface='en0', destPath='./', fileName='temp'):
        
        self.pathToTshark = pathToTshark
        self.interface    = interface
        self.destPath     = destPath
        self.fileName     = fileName 
        
        pathToTshark, flag = verifyTsharkInstallation().verify(self.pathToTshark)
        
        if flag is True:
            # checks if path exist if not asks for creation
            checkPathCreate(self.destPath)
            self.pathToTshark = pathToTshark
 
    def dump(self,typeOfCapture='packets',extraArgs=100,numOfFiles=1,delay=0,fileNameOnly=False):
        
        # delay in seconds 
        delay = int(round(delay)) 
        
        # capture all packets 
        # command1 = self.pathToTshark+'tshark'+' -i '+str(self.interface)
        
        # capture only UDP packets 
        # command1 = 'sudo ' + os.path.join(self.pathToTshark,'tshark')+' -i '+str(self.interface) + ' -f "udp"'
        command1 = os.path.join(self.pathToTshark,'tshark')+' -i '+str(self.interface) + ' -f "udp"'

        nowTime = datetime.now()
        current_date = nowTime.strftime("%Y%m%d")
        current_time = nowTime.strftime("%H%M%S")

        if delay > 0: 
            fileNameDetails1 = current_date+'_'+current_time+'_delay'+str(delay)+'s_'
        else:
            fileNameDetails1 = current_date+'_'+current_time+'_'
            
        fileExt  = '.pcapng'
        
        print('\nrecording '+str(numOfFiles)+' pcapng files ...')
        
        if delay > 0:
            print('\ndelaying each file start of '+str(delay)+' s ...')
        
        status = []

        for currentAcq in range(numOfFiles):
            
            currentAcqStr = str(format(currentAcq,'05d'))
            
            print('\n... recording file no. '+currentAcqStr+' of '+str(format(numOfFiles-1,'05d')))
            
            ###############################
            if typeOfCapture == 'packets':
                
                print('by packets -> {} packets'.format(extraArgs))
                
                numOfPackets   = extraArgs
                commandDetails = ' -c '+str(numOfPackets)
                
                fileNameDetails2    = 'pkts'+str(numOfPackets)
  
            elif typeOfCapture == 'filesize':
                
                print('by file size -> {} kbytes'.format(extraArgs))
                
                sizekbytes     = extraArgs
                commandDetails = ' -a filesize:'+str(sizekbytes)
                
                fileNameDetails2    = 'size_kb_'+str(sizekbytes)
                
                
            elif typeOfCapture == 'duration':
                
                print('by duration -> {} s'.format(extraArgs))
                
                duration_s     = extraArgs
                commandDetails = ' -a duration:'+str(duration_s)
                
                fileNameDetails2    = 'duration_s_'+str(duration_s)
                
            else:
                print(' \033[1;31mERROR ... \033[1;37m type of capture '+typeOfCapture+' not supported or typo! -> exiting!')
                sys.exit()
                
            ###############################   
            
            temp = self.fileName.split('.',1)

            if fileNameOnly is False:
                if len(temp) > 1:
                    self.fileName = temp[0] 
                fileFull =  fileNameDetails1+fileNameDetails2+'_'+self.fileName+'_'+currentAcqStr+fileExt
            else:
                if len(temp) == 1:
                    fileFull = self.fileName+fileExt
                else:
                    fileFull = self.fileName
                    
            fileFullAndPath = os.path.join(self.destPath,fileFull) 
            
            temp = os.system(command1+commandDetails+' -w '+fileFullAndPath)
            
            if delay > 0:
                print('\n...waiting '+str(delay)+'s for the next acquisition ...')
                time.sleep(delay)
                
            
            status.append(temp)
            
            if temp != 0:
                # print(' \033[1;31mERROR ... \n\033[1;37m')
                print(' ERROR ... EXIT!\n')
                sys.exit()
                
        allStatus = sum(status)      
        if allStatus == 0: 
               print('\nrecording completed!')
        else:
               print(' \033[1;31mERROR ... \n\033[1;37m')
                  
        return allStatus ,  fileFullAndPath
              
 
                 
###############################################################################
###############################################################################

class acquisitionStatus():
    def __init__(self, destPath):
        
        self.pathFile = os.path.join(destPath,'acquisition.status')

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
    
    
   transferData = transferDataUtil()
   transferData.syncData('essdaq@172.30.244.50:~/pcapt/', '/Users/francescopiscitelli/Desktop/dataVMM/')   

   ########
    # path, flag = findPathApp().check('wireshark')
   
   ########
    # destPath  = '/Users/francescopiscitelli/Desktop/dataPcapUtgard/'

    # st = acquisitionStatus(destPath)   

    # st.checkExist()  
    
    # st.read()
    
    # flag = st.flipStatus()
   
    # print(flag)
    
    # acqOver = st.checkStatus()
    
    # print(acqOver)
    
    
   # path, flag = findPathApp().check('tshark')
   
   
   ########
    # pathToTshark = '/Applications/Wireshark.app/Contents/MacOS/'
    
    # ret_pathToTshark, flag= verifyTsharkInstallation().verify(pathToTshark)
    
    # print('------')
    # print(ret_pathToTshark)
    # print(flag)

    # rec = dumpToPcapngUtil(pathToTshark, interface='en0', destPath='/Users/francescopiscitelli/Desktop/reducedFile/', fileName='temp')
    # status=rec.dump('duration',2,3)
   
    # rec.dump('filesize',3,2)
   
   # status=rec.dump('packets',9,numOfFiles=2)
   
   #
