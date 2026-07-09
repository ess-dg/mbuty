#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct  7 09:19:40 2021

@author: francescopiscitelli
"""
import argparse

parser = argparse.ArgumentParser()
     
#  ARGS for FRAPIS LAPTOP
parser.add_argument("-i", "--interface", help = "interface from which capture packets", type = str, default = "en0")
parser.add_argument("-t", "--tshark", help = "path where tshark is located", type = str, default = "/Applications/Wireshark.app/Contents/MacOS/")
parser.add_argument("-e", "--destination", help = "path where to save recorded pcapng files", type = str, default = "/Users/francescopiscitelli/Desktop/reducedFile/")


#  ARGS for ESSDAQ
# parser.add_argument("-i", "--interface", help = "interface from which capture packets", type = str, default = "p4p1")
# parser.add_argument("-s", "--tshark", help = "path where tshark is located", type = str, default = "/usr/sbin/")
# parser.add_argument("-e", "--destination", help = "path where to save recorded pcapng files", type = str, default = "/home/essdaq/pcaps/")


# common
parser.add_argument("-f", "--file", help = "pcapng filename", type = str, default = "temp")
parser.add_argument("-n", "--numoffiles", help = "num of files to record in sequence", type = int, default = 1)
# 
# parser.add_argument("-m", "--mode", help = "capture mode: packets, filesize (kb) or duration (s)", type = str, default = "packets")
# parser.add_argument("-q", "--quantity", help = "quantity: num of packets, or kb filesize

command_group = parser.add_mutually_exclusive_group(required=False)
command_group.add_argument("-d", "--duration", help = "duration (seconds)", type=int)
command_group.add_argument("-p", "--packets", help = "num of packets (int)", type=int)
command_group.add_argument("-s", "--size", help = "file size (kbytes)", type=int)

# parser.add_argument("-d", "--duration", help = "duration (s)", type = int, default = 3)
# parser.add_argument("-q", "--quantity", help = "quantity: num of packets, or kb filesize, or s for duration", type = str, default = "100")

args  = parser.parse_args()

# args.duration = 4

if args.duration is None and args.packets is None and args.size is None:
    #  default:
        args.packets = 100

if args.packets is not None:
            print('dsdqdqwdwqdwq')

print(args.interface)
print(args.tshark)
print(args.duration)
print(args.packets)
print(args.size)