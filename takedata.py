#!/usr/bin/python
import os
import subprocess
import re
import sys

try:
        args = ['./MBUTYdump.py', '-i', 'en0', '-f', 'test.pcapng', '-n', '1', '-e', '/Users/francescopiscitelli/programming/dg_MultiBlade_MBUTY/MBUTYcap/', '-t', '/usr/local/bin/tshark', '-s','10']
        subprocess.call(args)

#(base) pingunix:MBUTYcap dpfeiffe$ ./MBUTY_DUMP.py -h
#usage: MBUTY_DUMP.py [-h] [-i INTERFACE] [-t TSHARK] [-e DESTINATION] [-f FILE] [-n NUMOFFILES] [-r DELAY]
#                     [-d DURATION | -p PACKETS | -s SIZE]
#
#optional arguments:
#  -h, --help            show this help message and exit
#  -i INTERFACE, --interface INTERFACE
#                        interface from which capture packets
#  -t TSHARK, --tshark TSHARK
#                        path where tshark is located
#  -e DESTINATION, --destination DESTINATION
#                        path where to save recorded pcapng files
#  -f FILE, --file FILE  pcapng filename
#  -n NUMOFFILES, --numoffiles NUMOFFILES
#                        num of files to record in sequence
#  -r DELAY, --delay DELAY
#                        sleep (s) between consecutive files
#  -d DURATION, --duration DURATION
#                        duration (seconds)
#  -p PACKETS, --packets PACKETS
#                        num of packets (int)
#  -s SIZE, --size SIZE  file size (kbytes)
except OSError:
	pass
