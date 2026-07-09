#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 12:20:15 2021

@author: francescopiscitelli
"""
import threading
import time
from lib import libTerminal as ta
import sys
import signal

############################################################################### 
###############################################################################


class background(object):
 
    def __init__(self,sourcePath,destPath):
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        b = threading.Thread(name='background', target=self.checkAcq(sourcePath,destPath))
        b.daemon = True
        b.start()
        
    def __init__(self, interval=1):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution

    def run(self):
        """ Method that runs forever """
        while True:
            # Do something
            print('Doing something important in the background')

            time.sleep(self.interval)

example = ThreadingExample()
time.sleep(3)
print('Checkpoint')
time.sleep(2)
print('Bye')