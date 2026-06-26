import numpy as np
import pandas as pd

class events():
    """Base class for all events.
        R5560 uses the base class
    """

    def __init__(self, size: int, subclass_fields: list):
        
        # Core base fields common to every physics event.
        base_fields = [
            ('ID',           'int64'),   # Physical unit ID (cassette, column, tube)
            ('timeStamp',    'int64'),   # Reconstructed event timestamp
            ('pulseT',       'int64'),   # Associated pulse heartbeat timeline
            ('prevPT',       'int64'),   # Associated previous pulse heartbeat timeline
            ('instrID',      'int64'),   # Instrument identifier matching readout source
              
            # Coordinates in terms of units - get directly from clustering stage
            ('coordinate0',  'float64'),     
            ('coordinate1',  'float64'),  
            ('pulseHeight0', 'int64'),   # Pulse height corresponding to coordinate0 (wires or tubes)
            
            # Coordinates in mm - calculated in absUnits and Lambda 
            ('absCoordinate0', 'float64'),   
            ('absCoordinate1', 'float64'),  
            ('ToF',            'int64'),   # Time-of-Flight (nanoseconds, populated by abs units)
            ('wavelength',     'float64'), # Neutron wavelength (Angstrom, populated by abs units)  
        ]

        full_schema = np.dtype(base_fields + subclass_fields)

        # Preallocate core memory matrix with a -1 sentinel for unset/rejected rows
        self.matrix = np.full(size, -1, dtype=full_schema)

        # Zero-initialize timing and downstream units fields
        _zero_fields = (
            'timeStamp', 'pulseT', 'prevPT', 'instrID',
            'absCoordinate0', 'absCoordinate1',
            'ToF', 'wavelength',
        )
        for field in _zero_fields:
            if field in full_schema.names:
                self.matrix[field] = 0

        self.fill_count: int = 0
        self.durations = np.zeros(0, dtype='int64')

        # Aggregate reconstruction diagnostics written by the clustering engine
        self.stats: dict = {
            'n_candidates':         0,  # Raw hit groups offered to clustering
            'n_accepted_2d':        0,  # Events with both coordinate axes valid
            'n_accepted_1d':        0,  # Events with coordinate1 absent (VMM only)
            'n_rejected_neighbour': 0,  # Rejected by neighbour / time-window check
            'n_rejected_overflow':  0,  # Rejected because cluster spanned > TimeWindowMax
            'n_rejected_other':     0,  # NaN, zero-ADC, or other pathological rows
        }
        
        # Pile up stats ???? 

    def absorb(self, computed_fields: dict, timing_src) -> None:
        """
        Single entry point to populate rows into this event container.

        Parameters
        ----------
        computed_fields : dict
            Mapping of field_name -> np.ndarray for every subclass field 
            the clustering engine has generated. Must include 'ID'.
        timing_src : np.ndarray or dict
            Source timing arrays providing 'timeStamp', 'pulseT', 'prevPT', and 'instrID'.

        Raises
        ------
        KeyError
            If 'ID' is missing from computed_fields.
        ValueError
            If timing fields overlap or if array lengths mismatch the container size.
        """
        n = len(self.matrix)
        if n == 0:
            self.fill_count = 0
            return

        # --- Guard: ID is mandatory ---
        if 'ID' not in computed_fields:
            raise KeyError("absorb(): 'ID' must be present in computed_fields.")

        # --- Guard: timing fields belong to timing_src, not computed_fields ---
        _timing_fields = {'timeStamp', 'pulseT', 'prevPT', 'instrID'}
        overlap = _timing_fields & computed_fields.keys()
        if overlap:
            raise ValueError(f"absorb(): timing fields {overlap} must come from timing_src.")

        # --- Guard: no unknown fields ---
        schema_names = set(self.matrix.dtype.names)
        unknown = set(computed_fields.keys()) - schema_names
        if unknown:
            raise ValueError(f"absorb(): computed_fields contains keys not in schema: {unknown}.")

        # --- Guard: all arrays must match container size ---
        for key, arr in computed_fields.items():
            if len(arr) != n:
                raise ValueError(f"absorb(): field '{key}' length {len(arr)} mismatch, expected {n}.")

        # Write base timing properties from clustering output
        self.matrix['timeStamp'] = timing_src['timeStamp']
        self.matrix['pulseT']    = timing_src['pulseT']
        self.matrix['prevPT']    = timing_src['prevPT']
        self.matrix['instrID']   = timing_src['instrID']

        # Map computed coordinates, charges, and multiplicities
        for field_name, array in computed_fields.items():
            self.matrix[field_name] = array

        self.fill_count = n
        self.remove_invalid()

    def remove_invalid(self) -> None:
        """Physically slice and compact the matrix, keeping only rows where ID != -1."""
        valid_mask = self.matrix[:self.fill_count]['ID'] != -1
        removed    = int(np.sum(~valid_mask))

        if removed > 0:
            self.matrix     = self.matrix[:self.fill_count][valid_mask].copy()
            self.fill_count = len(self.matrix)
            print(f'\t --> removing {removed} rejected rows from events ...')
        else:
            self.matrix     = self.matrix[:self.fill_count].copy()
            self.fill_count = len(self.matrix)
            print('\t --> no rejected events ...')

    def get_data_frame(self) -> pd.DataFrame:
        """Convert active matrix block to labeled DataFrame for easy inspection."""
        return pd.DataFrame(self.matrix)


# =============================================================================
# Concrete Event Subclasses
# =============================================================================

class eventsVMM(events):
    """Events for all VMM-based detectors (Multi-Blade and Multi-Grid)."""
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('pulseHeight1',   'int64'),   # Pulse height corresponding to coordinate1 (strips or grids)
            ('mult0',          'int64'),   # Multiplicity for coordinate0 (wires)
            ('mult1',          'int64'),   # Multiplicity for coordinate1 (strips or grids)
            ('absCoordinate2', 'float64'), # Third physical mm axis (wire depth / posZmm)
        ]
        super().__init__(size, subclass_fields)

        if size > 0:
            self.matrix['absCoordinate2'] = 0.0


class eventsBM(events):
    """Generic Beam Monitor passthrough event container."""
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
    """IBM-variant Beam Monitor passthrough event container."""
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('type',    'int64'),
            ('channel', 'int64'),
            ('debug',   'int64'),
            ('adc',     'int64'),
            ('mcaSum',  'int64'),
        ]
        super().__init__(size, subclass_fields)


class eventsSKADI(events):
    """SKADI detector event container placeholder stub."""
    def __init__(self, size: int = 0):
        subclass_fields: list = []
        super().__init__(size, subclass_fields)