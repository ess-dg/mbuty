#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 27 16:38:55 2021

@author: francescopiscitelli
"""

import os 
import sys
import time
from datetime import datetime
import subprocess
import signal



###############################################################################
############################################################################### 

def findPathApp(appName):
        IS_WINDOWS = sys.platform.startswith("win")
        comm = f'where {appName}' if IS_WINDOWS else f'which {appName}'
        
        app = subprocess.run(comm, shell=True, capture_output=True, encoding='utf-8')

        if app.returncode == 0:
            # found
            flag = True
            first_match = app.stdout.strip().splitlines()[0]
            temp = os.path.split(first_match)
            path = temp[0] + ('\\' if IS_WINDOWS else '/')
        else: 
            # not found
            flag = False
            path = ''
       
        return path, flag

############################################################################### 

def checkPathCreate(path):
    
        exist = os.path.exists(path)
        
        if exist is False:
            
            print('\n --> \033[1;33mWARNING: Folder: '+path+'does not exist.\033[1;37m')

            inp = input('     press (y) to create or (n or enter) to quit ')
            
            if inp == 'y':
                os.mkdir(path)
                print(' --> folder created.')
            else:    
                print(' --> exiting.')
                raise RuntimeError(f"Folder '{path}' does not exist and creation was cancelled.")
            

############################################################################### 
def syncData(sourcePath, destPath): # Removed 'verbose' parameter

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

    IS_WINDOWS = sys.platform.startswith("win")

    # Construct the rsync command as a list for subprocess
    # Always include --progress for detailed output
    # Using --info=progress2 is generally better for rsync 3.1+
    # If your rsync is older, you might need to revert to just '--progress'
    base_cmd = ["rsync", "-av", "--progress"] # Always print progress

    # Handle Windows/WSL specific command prefix
    if IS_WINDOWS:
        # Convert Windows path to WSL format if needed.
        # e.g., 'C:/Users/.../' -> '/mnt/c/Users/.../'
        destPath = destPath.replace("C:\\", "/mnt/c/").replace("C:/", "/mnt/c/").replace("\\", "/")
        cmd = ["wsl"] + base_cmd + [sourcePath, destPath]
    else:
        cmd = base_cmd + [sourcePath, destPath]

    # --- Print command before execution ---
    print("\n... syncing data ... ")
    #print(f"\n (Executing: {' '.join(cmd)})\n")
    process = None # Initialize process handle
    status = 1 # Default to non-zero (failure)

    # Shared kwargs for subprocess.Popen; preexec_fn is POSIX-only so it's added conditionally
    popen_kwargs = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if not IS_WINDOWS:
        popen_kwargs["preexec_fn"] = os.setsid # Isolate child process from parent's Ctrl+C

    try:
        # Use subprocess.Popen for control
        # stdout=subprocess.PIPE and stderr=subprocess.STDOUT to capture/stream all output
        # text=True for universal newlines and string output
        # bufsize=1 for line-buffered output
        process = subprocess.Popen(cmd, **popen_kwargs)

        # --- Critical: Set the global subprocess handle ---
        current_subprocess_handle = process

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
            if not IS_WINDOWS and status in (-signal.SIGTERM.value, -signal.SIGKILL.value):
                print(f"\n\033[1;31mERROR ... data sync interrupted (code: {status})\n\033[1;37m")
            elif current_subprocess_handle is None: # This indicates an external stop (e.g., from stop_back_end)
                print(f"\n\033[1;31mERROR ... data sync stopped by user (code: {status})\n\033[1;37m")
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
        print(f"\n\033[1;31mERROR ... An unexpected error occurred: {e}\n\033[1;37m")
        status = 1 # Indicate failure

    finally:
        # --- Critical: Clear the global subprocess handle ---
        if current_subprocess_handle is process:
            current_subprocess_handle = None

        print('\n-----') # Always print separator

    return status


    
###############################################################################   

def pcapConverter(pcapFile_PathAndFileName_IN,pathToTshark='/usr/sbin/'):

    pathToTshark = verifyTsharkInstallation(pathToTshark)

    if os.path.isfile(pcapFile_PathAndFileName_IN) is True:

        temp1 = os.path.split(pcapFile_PathAndFileName_IN)
        pcapFilePath    = temp1[0]+'/'
        pcapFileNameExt = temp1[1]

        temp2 = os.path.splitext(pcapFileNameExt)
        pcapFileName = temp2[0]
        pcapFileExt  = temp2[1]

        if pcapFileExt == '.pcap':

            print('pcap file selected')

            fileName_OUT = pcapFileName + '_convertedToPcapng.pcapng'

            # check if already converted 
            if os.path.isfile(pcapFilePath+fileName_OUT) is False:
                pcapngFile_PathAndFileName_OUT = pcapFilePath+fileName_OUT
                print(' -> converting pcap to pcapng ...')
                # Build the command as a list of independent arguments
                cmd = [pathToTshark + 'tshark', '-F', 'pcapng', '-r', pcapFile_PathAndFileName_IN, '-w', pcapngFile_PathAndFileName_OUT]
                # Run it safely without shell-parsing issues
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                status = result.returncode
                if status == 0: 
                    print(' conversion completed!')
                else:
                    print('\033[1;31mERROR ... \n\033[1;37m')
            else:
                print(' -> converted file already exists.')

        elif pcapFileExt == '.pcapng':

            pcapngFile_PathAndFileName_OUT = pcapFile_PathAndFileName_IN

    else:

        temp1 = os.path.split(pcapFile_PathAndFileName_IN)
        pcapFilePath    = temp1[0]+'/'
        pcapFileNameExt = temp1[1]

        print('\n \033[1;31m---> File: ' + pcapFileNameExt + ' DOES NOT EXIST \033[1;37m')
        print('\n ---> in folder: ' + pcapFilePath + ' \n')
        print('\n NOTE: file name must contain extension, e.g. *.pcapng\n')
        print(' ---> Exiting ... \n')
        print('------------------------------------------------------------- \n')
        raise FileNotFoundError(f"File {pcapFileNameExt} does not exist in folder {pcapFilePath}.")

    return pcapngFile_PathAndFileName_OUT
          
         
############################################################################### 

def verifyTsharkInstallation(initial_pathToTshark):
        IS_WINDOWS = sys.platform.startswith("win")
        binary_name = 'tshark.exe' if IS_WINDOWS else 'tshark'
        
        if os.path.isfile(os.path.join(initial_pathToTshark, binary_name)) is True:
            flag = True
            verified_pathToTshark = initial_pathToTshark
        else:
            flag = False
            
            # Try system lookup using appropriate shell command for OS
            cmd_app = 'tshark.exe' if IS_WINDOWS else 'tshark'
            verified_pathToTshark, flag = findPathApp(cmd_app)
            
            if flag is False:
                presetPaths = [
                    r'C:\Program Files\Wireshark\\',
                    r'C:\Program Files (x86)\Wireshark\\',
                    '/usr/sbin/',
                    '/usr/bin/',
                    '/Applications/Wireshark.app/Contents/MacOS/'
                ]

                for pat in presetPaths:
                    if os.path.isfile(os.path.join(pat, binary_name)) is True:
                        verified_pathToTshark = pat
                        flag = True
                        break
                    else:
                        flag = False

            if flag is False:  
                print('\n \033[1;31mFile Tshark not found in your system, either set right path to Tshark in parameters or install it.\033[1;37m\n')
                print('... exiting.')
                raise RuntimeError("Tshark binary not found in system paths.")

        return verified_pathToTshark
    
############################################################################### 
    
def dumpToPcapng(interface='en0', destPath='./', fileName='temp',typeOfCapture='packets',extraArgs=100,numOfFiles=1,delay=0,pathToTshark='/usr/sbin/',fileNameOnly=False,):
            
            pathToTshark= verifyTsharkInstallation(pathToTshark)
            
            checkPathCreate(destPath)
    
            # delay in seconds 
            delay = int(round(delay)) 
    
            # capture all packets 
            # command1 = self.pathToTshark+'tshark'+' -i '+str(self.interface)
            
            # capture only UDP packets 
            # command1 = 'sudo ' + os.path.join(self.pathToTshark,'tshark')+' -i '+str(self.interface) + ' -f "udp"'
            # command1 = os.path.join(pathToTshark,'tshark')+' -i '+str(interface) + ' -f "udp"'
    
            nowTime = datetime.now()
            current_date = nowTime.strftime("%Y%m%d")
            current_time = nowTime.strftime("%H%M%S")
    
            if delay > 0: 
                fileNameDetails1 = current_date+'_'+current_time+'_delay'+str(delay)+'s_'
            else:
                fileNameDetails1 = current_date+'_'+current_time+'_'
                
            fileExt  = '.pcapng'
            
            print('recording {} pcapng file(s) from interface {} ...'.format(numOfFiles,interface))
            
            if delay > 0:
                print('\ndelaying each file start of '+str(delay)+' s ...')
            
            status = []
    
            for currentAcq in range(numOfFiles):
                
                currentAcqStr = str(format(currentAcq,'05d'))
                
                print('... recording file no. '+currentAcqStr+' of '+str(format(numOfFiles-1,'05d')))
                
                ###############################
                # Build capture-specific arguments safely as elements of a list
                commandDetails = []

                if typeOfCapture == 'packets':
                    print('    by packets -> {} packets'.format(extraArgs))
                    numOfPackets = extraArgs
                    commandDetails = ['-c', str(numOfPackets)]
                    fileNameDetails2 = 'pkts' + str(numOfPackets)
        
                elif typeOfCapture == 'filesize':
                    print('    by file size -> {} kbytes'.format(extraArgs))
                    sizekbytes = extraArgs
                    commandDetails = ['-a', 'filesize:' + str(sizekbytes)]
                    fileNameDetails2 = 'size_kb_' + str(sizekbytes)
                    
                elif typeOfCapture == 'duration':
                    print('    by duration -> {} s'.format(extraArgs))
                    duration_s = extraArgs
                    commandDetails = ['-a', 'duration:' + str(duration_s)]
                    fileNameDetails2 = 'duration_s_' + str(duration_s)
                    
                else:
                    print(' \033[1;31mERROR ... \033[1;37m type of capture ' + typeOfCapture + ' not supported or typo! -> exiting!')
                    raise ValueError(f"Unsupported type of capture: {typeOfCapture}")
                
                temp = fileName.split('.', 1)
        
                if fileNameOnly is False:
                    if len(temp) > 1:
                        fileName = temp[0] 
                    fileFull = fileNameDetails1 + fileNameDetails2 + '_' + fileName + '_' + currentAcqStr + fileExt
                else:
                    if len(temp) == 1:
                        fileFull = fileName + fileExt
                    else:
                        fileFull = fileName
                        
                fileFullAndPath = os.path.join(destPath, fileFull) 
                
                # Construct full tshark token sequence safely 
                # The filter flag '-f' and its argument 'udp' are intentionally kept at the end
                tshark_bin = os.path.join(pathToTshark, 'tshark')
                cmd = [tshark_bin, '-i', str(interface)] + commandDetails + ['-w', fileFullAndPath, '-f', 'udp']
                
                # Run process via subprocess instead of os.system
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                temp_status = result.returncode
                
                if delay > 0:
                    print('\n...waiting ' + str(delay) + 's for the next acquisition ...')
                    time.sleep(delay)
                    
                status.append(temp_status)
                
                if temp_status != 0:
                    print(f"\033[1;31mERROR: interface does not exist or you do not have the rights to record -> exiting.\033[1;37m")
                    raise RuntimeError("pcap capture failed: interface does not exist or insufficient permissions.")
                    
            allStatus = sum(status)      
            if allStatus == 0: 
                print('recording completed!')
            else:
                print(' \033[1;31mERROR ... \n\033[1;37m')
                     
            return destPath, fileFull
         
                 
###############################################################################
###############################################################################
#  in case MBUTY AUTO we want to take it back from version 7.3 



# class acquisitionStatus():
#     def __init__(self, destPath):
        
#         self.pathFile = os.path.join(destPath,'acquisition.status')

#     def checkExist(self):   

#         if os.path.isfile(self.pathFile) is True:
#             # if the file already exists open it 
#             flag = True
#             # fo   = open(self.pathFile, "w+")
            
#         else:    
#             # open/create a new file and add the field names
#             flag = False
#             fo   = open(self.pathFile, "w")
#             fo.writelines('recording')
#             fo.close()
            
#         return flag   
    
#     def read(self):
        
#         flag = self.checkExist()
        
#         # print(flag)
        
#         fo = open(self.pathFile, "r")
#         lines = fo.readlines()
#         # print(lines) 
            
#         fo.close()
        
#         return lines
    
#     def set_RecStatus(self):
        
#         lines = self.read()
   
#         fo = open(self.pathFile, "w")
#         fo.writelines('recording')
#         fo.close()  
        
#     def set_FinStatus(self):
        
#         lines = self.read()
   
#         fo = open(self.pathFile, "w")
#         fo.writelines('finished')
#         fo.close() 
        
#     def flipStatus(self):
        
#         lines = self.read()
        
#         # print(lines) 
        
#         if lines[0] == 'recording':
#            flag = False
#            fo = open(self.pathFile, "w")
#            fo.writelines('finished')
#            fo.close()
#         elif lines[0] == 'finished' :
#            flag = True
#            fo = open(self.pathFile, "w")
#            fo.writelines('recording')
#            fo.close()   
           
#         return flag   
      
#     def checkStatus(self):
        
#         if os.path.isfile(self.pathFile) is True:
            
#             fo = open(self.pathFile, "r")
#             lines = fo.readlines()
#             # print(lines) 
#             fo.close()
            
#             if lines[0] == 'recording':
#                 acqIsOver = False
#             elif lines[0] == 'finished' :
#                 acqIsOver = True
                
#         else:
            
#             acqIsOver = None
#             print('status file does not exist')
#             time.sleep(2)
#             sys.exit()
    
            
#         return acqIsOver

        
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # IN = "/Users/francescopiscitelli/Desktop/untitled folder/file2_6pk.pcap" 
    
    # OUT, flag = pcapConverter(IN)
    
    
    sourcePath = 'essdaq@172.30.244.50:/home/essdaq/pcaps2/'
    
    destPath = "/Users/francescopiscitelli/Desktop/untitled folder/"
    
    # syncData(sourcePath, destPath)
    
    syncData(destPath, sourcePath)
    
    # dumpToPcapng(interface='en1', destPath=destPath, fileName='temp',typeOfCapture='packets',extraArgs=3,numOfFiles=1,delay=0,pathToTshark='/usr/sbin/',fileNameOnly=False )
    
    
   # transferData = transferDataUtil()
   # transferData.syncData('essdaq@172.30.244.50:~/pcapt/', '/Users/francescopiscitelli/Desktop/dataVMM/')   

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
