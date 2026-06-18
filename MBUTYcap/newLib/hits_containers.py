import numpy as np
import time
from calibration import load_calibration_map, calibrate_adc_channels
from colors import WARN, RESET
import pandas as pd 

class hits():
    """
    Abstract base class for all detector hits.
    Houses the single contiguous memory matrix block and global file metrics.
    """
    def __init__(self, size: int, subclass_fields: list):
        # 1. Non-negotiable core base fields common to every network data frame
        base_fields = [
            # Common fields for all readout types
            ('ID',      'int64'),
            ('timeStamp', 'int64'),
            # Ess header
            ('pulseT',    'int64'),
            ('prevPT',    'int64'),
            ('instrID',   'int64')
        ]

        # 2. Combine base fields with subclass unique hardware parameters
        full_schema = np.dtype(base_fields + subclass_fields)

        # 3. Preallocate ONE single contiguous memory matrix block
        self.matrix = np.zeros(size, dtype=full_schema)

        # Tracks how many rows have been written during the read pass.
        # _trim_all_containers() slices matrix[:fill_count] after reading.
        self.fill_count: int = 0

        # Per number of files (Independent scalar metrics tracking file lifespan)
        self.durations = np.zeros((0), dtype='int64')


# fen rin hybrid becomes id
class hitsVMMnormal(hits):
    """Multi-Blade / Multi-Grid normal hits parameterized data profile."""

    def __init__(self, size: int = 0):
        # Define fields unique to VMM electronics inside the class constructor
        hardware_fields = [
            ('index', 'int64'),
            ('plane', 'int64')
            ('adc',     'int64'),
        ]
        super().__init__(size, hardware_fields)

class hitsVMMclustered(hits):
    """Multi-Blade clustered hits parameterized data profile."""

    def __init__(self, size: int = 0):
        hardware_fields = [
            ('index0', 'int64'),
            ('index1',     'int64'),
            ('mult0',    'int64'),
            ('mult1', 'int64'),
            ('adc0',     'int64'),
            ('adc1',    'int64')
        ]

        super().__init__(size, hardware_fields)
        
# ring fen tube becomes id everything else stays same
class hitsR5560(hits):
    """Helium-3 continuous gas tube (CAEN) parameterized data profile."""

    def __init__(self, size: int = 0):
        hardware_fields = [
            ('counter1', 'int64'),
            ('ampA',     'int64'),
            ('ampB',     'int64'),
            ('counter2', 'int64')
        ]

        super().__init__(size, hardware_fields)
        
# BM hits are exact same as event 
class hitsBM(hits):
    """Generic Beam Monitor diagnostic parameterized data profile."""
    def __init__(self, size: int = 0):
        hardware_fields = [
            ('type',    'int64'),
            ('channel', 'int64'),
            ('adc',     'int64'),
            ('posX',    'int64'),
            ('posY',    'int64')
        ]
        super().__init__(size, hardware_fields)


class hitsIBM(hits):
    """IBM variant Beam Monitor diagnostic parameterized data profile."""
    def __init__(self, size: int = 0):
        hardware_fields = [
            ('type',     'int64'),
            ('channel',  'int64'),
            ('debug',    'int64'),
            ('adc',      'int64'),
            ('mcaSum',   'int64')
        ]
        super().__init__(size, hardware_fields)

# On hold - need to clarify structure
class hitsSKADI(hits):
    """SKADI detector parameterized data profile."""
    def __init__(self, size: int = 0):
        hardware_fields = [
            ('IP',       'int64'),
            ('sysID',    'int64'),
            ('channel',  'int64'),
            ('column',   'int64'),
            ('row',      'int64'),
            ('adc',      'int64'),
            ('flag',     'int64'),
            ('opMode',   'int64')
        ]
        super().__init__(size, hardware_fields)