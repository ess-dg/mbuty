#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  8 08:19:54 2026

@author: francescopiscitelli
"""


import numpy as np

import matplotlib.pyplot as plt



# 1. Input Data & Axis

data = np.array([0,6.9, 7.1, 7.4, 9.8, 7.1, 10, 6.9, 4, 55, 8.1])

axis = np.arange(6, 10.5, 0.5)  # Your custom float intervals


vmin = np.min(axis)
vmax = np.max(axis)
n    = len(axis)


# valid_mask = (data >= vmin) & (data <= vmax)
# filtered_data = data[valid_mask]

# clipped_data = np.clip(data, vmin, vmax)


out_of_bounds = False

indexes1 = np.round((n - 1) * (data - vmin) / (vmax - vmin)).astype(np.int64)

# indexes2 = np.round((n - 1) * (filtered_data - vmin) / (vmax - vmin)).astype(np.int64)

# indexes3 = np.round((n - 1) * (clipped_data - vmin) / (vmax - vmin)).astype(np.int64)


oob = (indexes1 < 0) | (indexes1 > n - 1)

clipped_indexes = np.clip(indexes1, 0, n - 1)

# counts = np.bincount(indexes, minlength=len(axis) )


if out_of_bounds is False:

    if np.any(oob):

        print('{WARN}WARNING: 1D hist out of bounds values found.{RESET}')

    counts1 = np.bincount(indexes1[~oob], minlength=n).astype(np.float64)


counts2 = np.bincount(clipped_indexes, minlength=n).astype(np.float64)

# counts3 = np.bincount(indexes3, minlength=n).astype(np.float64) 

