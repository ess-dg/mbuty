#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 19:48:21 2021

@author: francescopiscitelli
"""
import time
import random
from threading import Thread
import signal 

class C1:
   def __init__(self):
      signal.signal(signal.SIGINT,self.signal_handler)
      self.keepgoing = True
      self.list = list()

   def infinite_loop(self):
      while self.keepgoing:
         self.list.append(random.randint(1,10))
         time.sleep(2)
         print(self.list)

   def signal_handler(self, sig, frame):
       print('You pressed Ctrl+C!')
       self.keepgoing = False

class C2:
   def __init__(self):
      print('inside C2 init')
      self.c1 = C1()

   def main(self):
      self.bg_th = Thread(target=self.c1.infinite_loop)
      self.bg_th.start()

   def disp(self):
      print(self.c1.list)



c2 = C2()
c2.main()
time.sleep(2)
c2.disp()
c2.bg_th.join()