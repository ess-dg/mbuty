#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 13 09:02:22 2025

@author: francescopiscitelli
"""

import numpy as np
import os
import h5py
import sys
import matplotlib.pyplot as plt

###############################################################################
###############################################################################

# NOTE: for orginal file look into devel/NEXUS/plot_mb for more info 

###############################################################################
###############################################################################
plt.close("all")
###############################################################################
###############################################################################

filePath = '/Users/francescopiscitelli/Documents/DOC/DATA/202504_MBTBLsite/'

fileName = 'NEXUS_tbl_mb1_Diagonal.hdf'

fileName = 'NEXUS_tbl_f_file_MUONS.hdf'


###############################################################################
###############################################################################

pathAndFileName = filePath+fileName

if os.path.exists(pathAndFileName) is False:
        print(' \033[1;31m---> File: '+fileName+' DOES NOT EXIST \033[1;37m')
        print(' ---> in folder: '+filePath)
        # print('  ---> in folder: '+self.filePath+' -> ... it will be skipped!')
        print(' ---> Exiting ... \n')
         # print('------------------------------------------------------------- \n')
        sys.exit()
else:
           
   try:
            
      fid    = h5py.File(pathAndFileName, "r")
                
   except:
        
      print('Unable to opne h5 file')
      sys.exit()
                 
    # def __del__(self):
    #     try:
    #         self.fid.close()
    #     except:
    #         pass
                 
    # def dprint(self, tabs, msg):
    #     if self.showTree:
    #         print(tabs+"{}".format(msg))   
    
    
    
# for key_main in fid.keys():
    
#         print('1-',key_main) 
       
#         # entry
#         main = fid[key_main] 
        
#         for key_gr in main.keys():
            
#             print('2-\t',key_gr)
           
#             # detector, monitor, parameters
#             group = main[key_gr]
   
with h5py.File(pathAndFileName, 'r') as fid:      
       event_id = fid[f'entry/instrument/multiblade_detector/data/event_id'][:] # pixel IDs, length M
       event_index = fid[f'entry/instrument/multiblade_detector/data/event_index'][:] # slice indicies per pulse, length N
       event_time_offset = fid[f'entry/instrument/multiblade_detector/data/event_time_offset'][:] # rToA, length M
       event_time_zero = fid[f'entry/instrument/multiblade_detector/data/event_time_zero'][:] # Pulse times, length N

       # detector_number is the pixel_id list, and each index has the corresponding x, y, z positions 
       detector_number = fid[f'entry/instrument/multiblade_detector/detector_number'][:]
       x_pixel_offset = fid[f'entry/instrument/multiblade_detector/x_pixel_offset'][:]
       y_pixel_offset = fid[f'entry/instrument/multiblade_detector/y_pixel_offset'][:]
       z_pixel_offset = fid[f'entry/instrument/multiblade_detector/z_pixel_offset'][:]     
       
#     geometries[detector]['detector_number'] = detector_number
#     geometries[detector]['x_pixel_offset'] = x_pixel_offset
#     geometries[detector]['y_pixel_offset'] = y_pixel_offset
#     geometries[detector]['z_pixel_offset'] = z_pixel_offset
#
#
# # correct the sans detector number
# geometries['sans']['detector_number'] = geometries['sans']['detector_number'] - 1122304 + 720896
#
#
# full_detector_number = np.concatenate([geometries[detector]['detector_number'] for detector in detectors])
# full_x_pixel_offset = np.concatenate([geometries[detector]['x_pixel_offset'] for detector in detectors])
# full_y_pixel_offset = np.concatenate([geometries[detector]['y_pixel_offset'] for detector in detectors])
# full_z_pixel_offset = np.concatenate([geometries[detector]['z_pixel_offset'] for detector in detectors])
#
#
# # bin the data. For each detector_number, set the count to the number of events with that index in event_id
#
#
#
# detector_to_plot = 'high_resolution'
#
# detector_number = geometries[detector_to_plot]['detector_number']
# x_pixel_offset = geometries[detector_to_plot]['x_pixel_offset']
# y_pixel_offset = geometries[detector_to_plot]['y_pixel_offset']
# z_pixel_offset = geometries[detector_to_plot]['z_pixel_offset']       
       
# Use np.unique to count occurrences of each detector number in event_id
unique_event_ids, counts = np.unique(event_id, return_counts=True)

# Create a dictionary to map detector numbers to their positions in the detector_number array
detector_number_to_index = {detector_num: index for index, detector_num in enumerate(detector_number)}

# Use np.isin to filter event IDs that are in detector_number
mask = np.isin(unique_event_ids, detector_number)
filtered_event_ids = unique_event_ids[mask]
filtered_counts    = counts[mask]

# Create an array for count data
count_data = np.zeros_like(detector_number)

# Use np.searchsorted to find indices of filtered_event_ids in detector_number
indices = np.searchsorted(detector_number, filtered_event_ids)

# Populate count_data with the corresponding counts
np.add.at(count_data, indices, filtered_counts)

###############################################################################
###############################################################################

# rescale from m to mm
# x_pixel_offset = x_pixel_offset * 1000
# y_pixel_offset = - y_pixel_offset * 1000
# z_pixel_offset = z_pixel_offset * 1000

Nstrips = 64 
Nwires  = 32*14

fig2D, ax1 = plt.subplots(num=101,figsize=(10,6), nrows=1, ncols=1)  

ax1.imshow(count_data.reshape(Nwires, Nstrips), cmap='viridis', interpolation='none', aspect="auto")
ax1.set_ylabel('Wire ch.')
ax1.set_xlabel('Strip ch.')
fig2D.suptitle('DET image')

###############################################################################
###############################################################################
plt.show()       

#
# print(x_pixel_offset)
#
# marker_data = go.Scatter3d(
#     x=x_pixel_offset,
#     y=y_pixel_offset,
#     z=z_pixel_offset,
#     # marker=go.scatter3d.Marker(size=0.5),
#     marker=dict(
#         size=2,
#         color=count_data,  # set color to an array/list of desired values
#         colorscale='Viridis',   # choose a colorscale
#         opacity=0.8
#     ),
#     # opacity=0.8,
#     mode='markers'
# )
#
#
# # set the max and min of the colorbar
# marker_data.marker.cmin = 0
# marker_data.marker.cmax = 100
#
# fig = go.Figure(data=marker_data)
# # fig.update_layout(
# #     scene=dict(
# #         xaxis=dict(nticks=4, range=[-3000, 3000], ),
# #         yaxis=dict(nticks=4, range=[-3000, 3000], ),
# #         zaxis=dict(nticks=4, range=[-3000, 3000], ), ),
# #     margin=dict(r=20, l=10, b=10, t=10))
# fig.show()
#
