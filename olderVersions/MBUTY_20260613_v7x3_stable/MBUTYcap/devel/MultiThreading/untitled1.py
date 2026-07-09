#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 12:20:15 2021

@author: francescopiscitelli
"""
import threading
import time
import sys
import signal


class ThreadingExample(object):
    """ Threading example class
    The run() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self, interval=1):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution
        # thread.join()

    def run(self):
        """ Method that runs forever """
        
        self.exit_event = threading.Event()
        
        while True:
            
            # try:
            # self.exit_event = threading.Event()
            # Do something
            print('Doing something important in the background')

            time.sleep(self.interval)
            
            # except KeyboardInterrupt():
            if self.exit_event.is_set():
                        print('\nexecution terminated by user')
                        sys.exit() 
            
    def signal_handler(self, signum, frame):
        self.exit_event.set()
        
        
        

example = ThreadingExample()
time.sleep(3)
print('Checkpoint')
time.sleep(2)
print('Bye')