import numpy as np
import pandas as pd
import sys
import os
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.colors import INFO, RESET, WARN, ERR, OK

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
              
            # Coordinates in terms of units - get directly from clustering stage
            ('coordinate0',  'float64'),     
            ('coordinate1',  'float64'),  
            ('pulseHeight0', 'int64'),   # Pulse height corresponding to coordinate0 (wires or tubes)
            
            # Coordinates in mm - calculated in absUnits and Lambda 
            ('absCoordinate0', 'float64'),   
            ('absCoordinate1', 'float64'),  
            ('ToF',            'int64'),   # Time-of-Flight (nanoseconds, populated by abs units)
            ('wavelength',     'float64'), # Neutron wavelength (Angstrom, populated by abs units) 
            
            ('timeBetweenEvents', 'int64'),
            
        ]
        
        self.instrumentIDs = set() 

        full_schema = np.dtype(base_fields + subclass_fields)

        # Preallocate core memory matrix with a -1 sentinel for unset/rejected rows
        self.matrix = np.full(size, -1, dtype=full_schema)

        # Zero-initialize timing and downstream units fields
        _zero_fields = (
            'timeStamp', 'pulseT', 'prevPT',
            'absCoordinate0', 'absCoordinate1',
            'ToF', 'wavelength', 
        )
        for field in _zero_fields:
            if field in full_schema.names:
                self.matrix[field] = 0

        self.fill_count: int = 0
        self.durations = np.zeros(0, dtype='int64')

    def absorb(self, computed_fields: dict, timing_src) -> None:
        """
        Single entry point to populate rows into this event container.

        Parameters
        ----------
        computed_fields : dict
            Mapping of field_name -> np.ndarray for every subclass field 
            the clustering engine has generated. Must include 'ID'.
        timing_src : np.ndarray or dict
            Source timing arrays providing 'timeStamp', 'pulseT', and 'prevPT'

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
        _timing_fields = {'timeStamp', 'pulseT', 'prevPT'}
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
        
        self.matrix['timeBetweenEvents'] = np.insert(np.diff(self.matrix['timeStamp']), 0, 0)

        # Map computed coordinates, charges, and multiplicities
        for field_name, array in computed_fields.items():
            self.matrix[field_name] = array

        self.fill_count = n
        self.remove_invalid()
        self.print_stats()

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
            
    def print_stats(self) -> None:
        """Override in subclasses to print detector-specific clustering diagnostics."""
        pass

    def get_data_frame(self) -> pd.DataFrame:
        """Convert active matrix block to labeled DataFrame for easy inspection."""
        return pd.DataFrame(self.matrix)

    
    def compute_and_filter_tof(self, remove_invalid: bool = False) -> None:
        """
        Calculates Time-of-Flight (timeStamp - pulseT) in-place for active rows.
        Attempts recovery via prevPT for negative values.
        """
        if self.fill_count == 0:
            return

        # Isolate the active preallocated memory chunk
        m = self.matrix[:self.fill_count]
        
        # Primary flight calculation
        tof = m['timeStamp'] - m['pulseT']
        
        # Detect invalid negative values and attempt recovery pass
        invalid1 = tof < 0
        n_invalid1 = int(np.sum(invalid1))
        
        if n_invalid1 > 0:
            print(f"\n {WARN}\t WARNING ---> {n_invalid1} ToFs (out of {self.fill_count}) are invalid, but corrected with Prev. Pulse Time {RESET}")
            tof[invalid1] = m['timeStamp'][invalid1] - m['prevPT'][invalid1]
            
            # Catch remaining uncorrected hard failures
            invalid2 = tof < 0
            n_invalid2 = int(np.sum(invalid2))
            if n_invalid2 > 0:
                print(f"\n {WARN}\t WARNING ---> {n_invalid1 - n_invalid2} corrected -> {n_invalid2} ToFs (out of {self.fill_count}) are still invalid after correction (with both PulseT and PrevPT), set to -1! {RESET}")
                tof[invalid2] = -1

        # Save calculations directly to the structural fields
        self.matrix['ToF'][:self.fill_count] = tof

        # If requested, slice out rows violating reality and perform memory compaction
        if remove_invalid:
            keep = self.matrix[:self.fill_count]['ToF'] > 0
            n_removed = int(np.sum(~keep))
            if n_removed > 0:
                self.matrix = self.matrix[:self.fill_count][keep].copy()
                self.fill_count = len(self.matrix)
                print(f"\t {WARN}\t {n_removed} events removed because of Invalid ToFs {RESET}")

    def trim_tof_range(self, tof_gate_range_s: list) -> None:
        """
        Gates and filters the active events matrix block based on a Time-of-Flight range.
        
        Parameters
        ----------
        tof_gate_range_s : list or tuple
            The [min_time, max_time] bounds given in seconds.
        """
        if self.fill_count == 0:
            return

        print(f"\t {INFO}Gating ToF between {tof_gate_range_s[0]*1e3:.2f}ms and {tof_gate_range_s[1]*1e3:.2f}ms ... {RESET}")

        # Guard: Ensure ToF array has been populated before attempting to filter
        m = self.matrix[:self.fill_count]
        if np.any(m['ToF'] != 0):
            # Convert input range from seconds to nanoseconds (int64 matching schema)
            min_ns = int(tof_gate_range_s[0] * 1e9)
            max_ns = int(tof_gate_range_s[1] * 1e9)

            keep = (m['ToF'] >= min_ns) & (m['ToF'] <= max_ns)
            removed = int(np.sum(~keep))

            if removed > 0:
                self.matrix = m[keep].copy()
                self.fill_count = len(self.matrix)
                print(f"\t {WARN}\t --> removing {removed} rows outside of ToF gate window ... {RESET}")
            else:
                print(f"\t {INFO}\t --> all events fall inside the defined gate window {RESET}")
        else:
            print(f"\n {WARN}\t WARNING ---> ToF gating not possible, calculate ToFs first. ToF array empty! {RESET}")





# =============================================================================
# Concrete Event Subclasses
# =============================================================================

###############################################################################            
class eventsVMMclustered(events):
    """Events for VMM hardware-pre-clustered readout (passthrough)."""
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('pulseHeight1',   'int64'),   # Pulse height corresponding to coordinate1 (strips or grids)
            ('mult0',          'int64'),   # Multiplicity for coordinate0 (wires)
            ('mult1',          'int64'),   # Multiplicity for coordinate1 (strips or grids)
            ('absCoordinate2', 'float64'), # Third physical mm axis (wire depth / posZmm)
        ]
        super().__init__(size, subclass_fields)
        
        self.matrix['absCoordinate2'] = 0.0

        self.stats = {
            'n_candidates': 0,
            'n_accepted':   0,
        }

    def print_stats(self) -> None:
        print(f'\t --- VMM Clustered passthrough stats ---')
        print(f'\t     accepted : {self.stats["n_accepted"]}')
        
        
    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'coordinate0',
            'coordinate1',
            'pulseHeight0',
            'pulseHeight1',
            'mult0',
            'mult1',
            'timeBetweenEvents',
            'absCoordinate0',
            'absCoordinate1',
            'absCoordinate2',
            'ToF',
            'wavelength'   
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df


###############################################################################
class eventsVMMnormal(events):
    """Events for VMM normal readout detectors (Multi-Blade, Multi-Grid)."""
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('pulseHeight1',   'int64'),
            ('mult0',          'int64'),
            ('mult1',          'int64'),
            ('absCoordinate2', 'float64'),
            ('clusterTimeSpan',    'int64'),
        ]
        super().__init__(size, subclass_fields)
        self.matrix['absCoordinate2'] = 0.0

        self.stats = {
            'n_candidates':         0,
            'n_accepted':           0,
            'n_rejected':           0,
            'n_accepted_2d':        0,
            'n_accepted_1dw':       0,
            'n_accepted_1ds':       0,
            'n_rejected_overflow':  0,
            'n_rejected_neighbour': 0,
        }

    def print_stats(self) -> None:
        s    = self.stats
        nc   = s['n_candidates']
        na   = s['n_accepted']
        n2d  = s['n_accepted_2d']
        n1dw = s['n_accepted_1dw']
        n1ds = s['n_accepted_1ds']

        if nc == 0:
            print('\t --- VMM Normal clustering stats --- (no candidates)')
            return

        pct = lambda x: 100.0 * x / nc

        if na > 0:
            print(f'\t N of candidates: {nc} -> not rejected events {na} ({pct(na):.1f}%) '
                f'(2D: {n2d} ({100.0 * n2d / na:.1f}%), 1D(w): {n1dw} ({100.0 * n1dw / na:.1f}%), 1D(s/g): {n1ds} ({100.0 * n1ds / na:.1f}%))')
        else:
            print(f'\t N of candidates: {nc} -> not rejected events {na}')

        print(f'\t not rej (2D) {pct(n2d):.1f}%, '
            f'not rej (1D w) {pct(n1dw):.1f}%, '
            f'not rej (1D s/g) {pct(n1ds):.1f}%, '
            f'rejected {pct(s["n_rejected"]):.1f}%, '
            f'rejected overflow (>32) {pct(s["n_rejected_overflow"]):.1f}%, '
            f'rejected no neighbour {pct(s["n_rejected_neighbour"]):.1f}%')

        
        n_1d_p0, n_1d_p1 = self._print_multiplicity_stats()
        

    def _print_multiplicity_stats(self) -> tuple:
        """Derive and print multiplicity distributions from the surviving event matrix."""
        if self.fill_count == 0:
            return 0, 0

        m = self.matrix[:self.fill_count]

        mask_2d  = (m['mult0'] > 0) & (m['mult1'] > 0)
        mask_1d_p0 = (m['mult0'] > 0) & (m['mult1'] == 0)
        mask_1d_p1 = (m['mult0'] == 0) & (m['mult1'] > 0)

        max_mult  = 5
        mult_bins = np.arange(1, max_mult + 2)

        wire_mult_2d,  _ = np.histogram(m['mult0'][mask_2d],    bins=mult_bins)
        plane1_mult_2d, _ = np.histogram(m['mult1'][mask_2d],   bins=mult_bins)
        wire_mult_1d,  _ = np.histogram(m['mult0'][mask_1d_p0], bins=mult_bins)
        plane1_mult_1d, _ = np.histogram(m['mult1'][mask_1d_p1], bins=mult_bins)

        def _fmt(counts):
            total = sum(counts)
            if total == 0:
                return '(none)'
            return ', '.join(f'{100.0 * c / total:.1f}% ({i+1})' for i, c in enumerate(counts))

        print('\n\t     multiplicity:')
        print(f'\t     2D: % wires        fired per event: {_fmt(wire_mult_2d)}')
        print(f'\t     2D: % strips/grids fired per event: {_fmt(plane1_mult_2d)}')
        print(f'\t     1D: % wires        fired per event (wire-only):         {_fmt(wire_mult_1d)}')
        print(f'\t     1D: % strips/grids fired per event (strips/grids-only): {_fmt(plane1_mult_1d)}')

        return int(np.sum(mask_1d_p0)), int(np.sum(mask_1d_p1))
    
    
    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'coordinate0',
            'coordinate1',
            'pulseHeight0',
            'pulseHeight1',
            'mult0',
            'mult1',
            'clusterTimeSpan',
            'timeBetweenEvents',
            'absCoordinate0',
            'absCoordinate1',
            'absCoordinate2',
            'ToF',
            'wavelength'   
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df

###############################################################################
class eventsR5560(events):
    """Events for He-3 continuous gas tube detectors (CAEN R5560)."""
    def __init__(self, size: int = 0):
        super().__init__(size, subclass_fields=[])

        self.stats = {
            'n_candidates':     0,
            'n_accepted':       0,
            'n_rejected':       0,
            'n_pileup_flagged': 0,
        }

    def print_stats(self) -> None:
        s  = self.stats
        nc = s['n_candidates']

        if nc == 0:
            print('\t --- R5560 clustering stats --- (no candidates)')
            return

        pct     = lambda x: 100.0 * x / nc
        n_other = s['n_rejected'] - s['n_pileup_flagged']

        print(f'\t N of candidates: {nc} -> not rejected events {s["n_accepted"]} ({pct(s["n_accepted"]):.1f}%), '
            f'rejected pile-up {s["n_pileup_flagged"]} ({pct(s["n_pileup_flagged"]):.1f}%), '
            f'rejected 0 ADC or NaN {n_other} ({pct(n_other):.1f}%)')

    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'coordinate0',
            'coordinate1',
            'pulseHeight0',
            'timeBetweenEvents',
            'absCoordinate0',
            'absCoordinate1',
            'ToF',
            'wavelength'   
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df
    
###############################################################################

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

###############################################################################
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

###############################################################################
class eventsSKADI(events):
    """SKADI detector event container placeholder stub."""
    def __init__(self, size: int = 0):
        subclass_fields: list = []
        super().__init__(size, subclass_fields)