import numpy as np
import pandas as pd

class events():
    """
    Abstract base class for all reconstructed physics events.
    Houses the single contiguous memory matrix block and diagnostic statistics.

    Architectural contract:
    - ONE preallocated structured NumPy array (self.matrix) holds all events.
    - absorb() is the single entry point for clustering/passthrough engines to 
      populate this container.
    - Supports downstream in-place enrichment stages (such as absolute units 
      and lambda calculators) by exposing pre-allocated coordinate matrices.
    - Tracks file-lifespan metadata (durations) and aggregate reconstruction 
      statistics (self.stats) out-of-band as separate properties.
    """

    def __init__(self, size: int, subclass_fields: list):
        # 1. Non-negotiable core base fields common to every physics event.
        base_fields = [
            ('ID',        'int64'),   # Physical unit ID (cassette, column, tube)
            ('timeStamp', 'int64'),   # Reconstructed event timestamp
            ('pulseT',    'int64'),   # Associated pulse heartbeat timeline
            ('prevPT',    'int64'),   # Associated previous pulse heartbeat timeline
            ('ToF',       'int64'),   # Time-of-Flight (nanoseconds, populated by abs units)
            ('wavelength','float64'), # Neutron wavelength (Angstrom, populated by abs units)
        ]

        # 2. Combine base fields with subclass-specific spatial/charge parameters.
        full_schema = np.dtype(base_fields + subclass_fields)

        # 3. Preallocate ONE single contiguous memory matrix block.
        #    Spatial coordinates default to -1 as unmapped/coincidence sentinels.
        self.matrix = np.full(size, -1, dtype=full_schema)

        # Zero-initialize non-sentinel metric fields.
        zero_fields = {'timeStamp', 'pulseT', 'prevPT', 'ToF', 'wavelength'}
        for field in zero_fields:
            if field in full_schema.names:
                if full_schema[field].kind in ('i', 'f'):
                    self.matrix[field] = 0

        # Tracks the number of valid reconstructed events populated.
        self.fill_count: int = 0

        # Cumulative metric arrays carried across from the readout/hit stages.
        self.durations = np.zeros(0, dtype='int64')

        # Centralized dict for tracking row-level filter and rejection diagnostics.
        self.stats = {
            'n_candidates': 0,
            'n_accepted_2d': 0,
            'n_accepted_1d': 0,
            'n_rejected_neighbour': 0,
            'n_rejected_overflow': 0,
            'n_rejected_other': 0
        }

    def absorb(self, computed_fields: dict, timing_src) -> None:
        """
        Single entry point to populate rows into this event container.

        Parameters
        ----------
        computed_fields : dict
            Mapping of field_name -> np.ndarray for every subclass field 
            the clustering engine has generated. Must include 'ID'.
        timing_src : np.ndarray or dict
            Source timing arrays providing 'timeStamp', 'pulseT', and 'prevPT'.
        """
        n = len(self.matrix)
        if n == 0:
            self.fill_count = 0
            return

        if 'ID' not in computed_fields:
            raise KeyError("absorb(): 'ID' must be present in computed_fields.")

        # Write core base timing parameters
        self.matrix['timeStamp'] = timing_src['timeStamp']
        self.matrix['pulseT']    = timing_src['pulseT']
        self.matrix['prevPT']    = timing_src['prevPT']
        self.matrix['ToF']       = 0
        self.matrix['wavelength']= 0.0

        # Write subclass-specific coordinates, pulse heights, and multiplicities
        for field_name, array in computed_fields.items():
            if field_name in self.matrix.dtype.names:
                self.matrix[field_name] = array

        self.fill_count = n

    def get_data_frame(self) -> pd.DataFrame:
        """Exposes the active matrix as a labeled Pandas DataFrame for quick inspection."""
        return pd.DataFrame(self.matrix[:self.fill_count])


# =============================================================================
# Concrete Event Subclasses
# =============================================================================

class eventsVMMnormal(events):
    """
    Multi-Blade (Normal/Clustered) and Multi-Grid physics events container.

    Accommodates 2D coordinates, 1D fallback cases (posS = -1), and allocates
    empty space for down-stream physical millimeter coordinate transformations.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('posW',    'float64'),  # Wire channel coordinate (CoM or Max)
            ('posS',    'float64'),  # Strip/Grid channel coordinate (-1 if 1D fallback)
            ('phW',     'int64'),    # Integrated Pulse Height for Wires
            ('phS',     'int64'),    # Integrated Pulse Height for Strips/Grids (0 if 1D)
            ('multW',   'int64'),    # Wire cluster hit multiplicity
            ('multS',   'int64'),    # Strip/Grid cluster hit multiplicity
            ('posWmm',  'float64'),  # Absolute wire position in mm (filled later)
            ('posSmm',  'float64'),  # Absolute strip position in mm (filled later)
            ('posZmm',  'float64'),  # Absolute depth coordinate in mm (filled later)
        ]
        super().__init__(size, subclass_fields)

        # Initialize millimeter positions to 0.0 default sentinels
        if size > 0:
            self.matrix['posWmm'] = 0.0
            self.matrix['posSmm'] = 0.0
            self.matrix['posZmm'] = 0.0


class eventsR5560(events):
    """
    Helium-3 continuous gas tube (CAEN R5560) physics events container.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('tubePos',   'float64'), # Normalised coordinate along the tube length (0.0 - 1.0)
            ('tubeID',    'int64'),   # Physical hardware tube number identifier
            ('ph',        'int64'),   # Integrated pulse height charge sum
            ('mult',      'int64'),   # Hit count multiplicity inside time window
            ('tubePosM',  'float64'), # Absolute spatial tube position in mm (filled later)
            ('tubeIDmm',  'float64'), # Absolute spatial pitch spacing in mm (filled later)
        ]
        super().__init__(size, subclass_fields)

        if size > 0:
            self.matrix['tubePosM'] = 0.0
            self.matrix['tubeIDmm'] = 0.0


class eventsBM(events):
    """
    Generic Beam Monitor passthrough event container. Bypasses clustering math.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('type',    'int64'),
            ('channel', 'int64'),
            ('adc',     'int64'),
            ('posX',    'int64'),
            ('posY',    'int64'),
        ]
        super().__init__(size, subclass_fields)


class eventsIBM(events):
    """
    IBM Variant Beam Monitor passthrough event container. Bypasses clustering math.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('type',    'int64'),
            ('channel', 'int64'),
            ('debug',   'int64'),
            ('adc',     'int64'),
            ('mcaSum',  'int64'),
        ]
        super().__init__(size, subclass_fields)