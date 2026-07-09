#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 14 14:03:57 2023

@author: francescopiscitelli
"""

import time
import configargparse as argparse

import matplotlib.pyplot as plt
import numpy as np
from confluent_kafka import Consumer, TopicPartition
import RawReadoutMessage as rawmsg
import kafkarx as krx 


###############################################################################
###############################################################################
###############################################################################
###############################################################################


broker = ''

topic = ''


kafka_config = krx.generate_config(broker, True)

krx.main(kafka_config, topic)
    
    

