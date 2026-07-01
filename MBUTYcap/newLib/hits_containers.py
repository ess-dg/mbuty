import numpy as np
import pandas as pd


class hits():
    """
    Abstract base class for all detector hits.
    Houses the single contiguous memory matrix block and global file metrics.

    Architectural contract:
    - ONE preallocated structured NumPy array (self.matrix) holds all rows.
      It is allocated to exactly readouts.fill_count — the full readout count
      before mapping — so there is never any slack to release.
    - absorb() is the single entry point for mappers to populate the container.
      It writes timing, writes all computed coordinate fields, then calls
      remove_invalid() to physically compact out unmapped rows.
    - remove_invalid() physically slices self.matrix to keep only rows where
      ID != -1, yielding a clean contiguous block ready for clustering or
      plotting. After absorb() returns, len(self.matrix) == fill_count always.
    - get_data_frame() exposes the active matrix as a labeled DataFrame for
      interactive inspection in Spyder or a terminal.
    - Mappers must NOT write to self.matrix directly, must NOT set fill_count,
      and must NOT call remove_invalid() themselves — absorb() owns that lifecycle.
    """

    def __init__(self, size: int, subclass_fields: list):
        # 1. Non-negotiable core base fields common to every mapped hit.
        #    ID carries the physical unit identifier looked up from config
        #    topology, replacing the legacy Cassette/Tube/Column fields.
        base_fields = [
            ('ID',        'int64'),   # Physical unit ID from config topology
            ('timeStamp', 'int64'),
            ('pulseT',    'int64'),
            ('prevPT',    'int64'),
        ]
        self.instrumentIDs = set()

        # 2. Combine base fields with subclass-specific mapped coordinates.
        full_schema = np.dtype(base_fields + subclass_fields)

        # 3. Preallocate ONE single contiguous memory matrix block.
        #    All fields default to -1 as an unmapped sentinel.
        self.matrix = np.full(size, -1, dtype=full_schema)

        # Zero-initialise timing fields, which are never sentinel-valued.
        for field in ('timeStamp', 'pulseT', 'prevPT'):
            if field in full_schema.names:
                self.matrix[field] = 0

        # Tracks the number of valid (post-remove_invalid) rows.
        # After absorb() returns, fill_count == len(self.matrix) always.
        self.fill_count: int = 0

        # Duration scalar carried forward from the readouts container.
        self.durations = np.zeros(0, dtype='int64')

    # ------------------------------------------------------------------
    # Primary mapper entry point
    # ------------------------------------------------------------------

    def absorb(self, computed_fields: dict, timing_src) -> None:
        """
        Single entry point for mappers to populate this container.

        Mappers prepare all coordinate arrays, then call this method once.
        absorb() validates incoming fields, writes timing from the readout
        source, writes all computed coordinate fields, sets fill_count, then
        calls remove_invalid() to physically compact the matrix.

        After this method returns:
          - self.matrix contains only valid (mapped) rows.
          - len(self.matrix) == self.fill_count.
          - No further slicing or cursor arithmetic is needed downstream.

        Parameters
        ----------
        computed_fields : dict
            Mapping of field_name -> np.ndarray for every subclass field
            the mapper has computed. Must include 'ID'.
            Timing fields (timeStamp, pulseT, prevPT) are written
            from timing_src and must NOT appear here.
        timing_src : np.ndarray
            The active slice of the readout matrix (readouts.matrix[:n]).
            Must contain timeStamp, pulseT, prevPT fields.

        Raises
        ------
        KeyError
            If 'ID' is missing from computed_fields.
        ValueError
            If computed_fields contains a timing field, an unknown field name,
            or any array whose length does not match the container size.
        """
        n = len(self.matrix)

        # --- Guard: ID is mandatory ------------------------------------------
        if 'ID' not in computed_fields:
            raise KeyError("absorb(): 'ID' must be present in computed_fields.")

        # --- Guard: timing fields belong to timing_src, not computed_fields ---
        timing_fields = {'timeStamp', 'pulseT', 'prevPT'}
        overlap = timing_fields & computed_fields.keys()
        if overlap:
            raise ValueError(
                f"absorb(): timing fields {overlap} must not appear in "
                f"computed_fields — they are sourced from timing_src."
            )

        # --- Guard: no unknown fields ----------------------------------------
        schema_names = set(self.matrix.dtype.names)
        unknown = set(computed_fields.keys()) - schema_names
        if unknown:
            raise ValueError(
                f"absorb(): computed_fields contains keys not in schema: {unknown}. "
                f"Schema fields are: {schema_names}."
            )

        # --- Guard: all arrays must match container size ----------------------
        for key, arr in computed_fields.items():
            if len(arr) != n:
                raise ValueError(
                    f"absorb(): array for '{key}' has length {len(arr)}, "
                    f"expected {n} (container size)."
                )

        # --- Write timing from readout source --------------------------------
        self.matrix['timeStamp'] = timing_src['timeStamp']
        self.matrix['pulseT']    = timing_src['pulseT']
        self.matrix['prevPT']    = timing_src['prevPT']

        # --- Write all computed coordinate fields ----------------------------
        for field_name, array in computed_fields.items():
            self.matrix[field_name] = array

        # --- Set cursor, then compact to valid rows only ---------------------
        self.fill_count = n
        self.remove_invalid()

    def remove_invalid(self) -> None:
        """
        Physically compact the matrix, keeping only rows where ID != -1.

        Rows with ID == -1 were never matched to any topology entry during
        mapping (equivalent to the legacy removeUnmappedData()). This method
        replaces self.matrix with a new contiguous array containing only the
        surviving rows, so that downstream consumers (clustering, plotting)
        can use self.matrix directly without cursor arithmetic.

        After this call: len(self.matrix) == self.fill_count.
        """
        valid_mask = self.matrix[:self.fill_count]['ID'] != -1  
        removed    = int(np.sum(~valid_mask))
        

        if removed > 0:
            self.matrix    = self.matrix[:self.fill_count][valid_mask].copy()
            self.fill_count = len(self.matrix)
            print(f'\t --> removing {removed} unmapped rows from hits ...')
        else:
            self.matrix    = self.matrix[:self.fill_count].copy()
            self.fill_count = len(self.matrix)
            print('\t --> no unmapped data in hits ...')
            
   
          

    # ------------------------------------------------------------------
    # Debug / inspection
    # ------------------------------------------------------------------

    def get_data_frame(self) -> pd.DataFrame:
        """
        Converts the active matrix into a labeled Pandas DataFrame for
        interactive inspection in Spyder or a terminal.
        """
        return pd.DataFrame(self.matrix)


# ----------------------------------------------------------------------
# Concrete hits subclasses — one per readout container type
# ----------------------------------------------------------------------

class hitsVMMnormal(hits):
    """
    Multi-Blade / Multi-Grid normal hits.
    Mapped from readoutsVMMnormal after unit ID lookup and
    channel-to-wire/strip coordinate transformation.

    Fields
    ------
    plane : int64
        Axis discriminator: 0 = wire plane (or wire-equivalent), 1 = strip plane.
        Replaces legacy WorS.
    index : int64
        Global mapped channel coordinate on that plane (wire number or strip
        number after cassette offset is applied).
        Replaces legacy WiresStrips / WiresStripsGlob.
    adc : int64
        Raw ADC value carried forward from the readout.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('plane', 'int64'),   # 0 = wire (or wire-equivalent), 1 = strip COMMENT or equivalent 
            ('index', 'int64'),   # Global coordinate on the plane
            ('adc',   'int64'),
        ]
        super().__init__(size, subclass_fields)

    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'plane',
            'index',
            'adc',
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df

class hitsVMMclustered(hits):
    """
    Multi-Blade clustered hits.
    Mapped from readoutsVMMclustered. Each row carries a simultaneous
    wire + strip pair with independent ADCs and per-plane multiplicities.

    Fields
    ------
    index0 : int64   Wire global coordinate.
    index1 : int64   Strip coordinate.
    adc0   : int64   ADC for the wire plane.
    adc1   : int64   ADC for the strip plane.
    mult0  : int64   Wire cluster multiplicity.
    mult1  : int64   Strip cluster multiplicity.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('index0', 'int64'),
            ('index1', 'int64'),
            ('adc0',   'int64'),
            ('adc1',   'int64'),
            ('mult0',  'int64'),
            ('mult1',  'int64'),
        ]
        super().__init__(size, subclass_fields)
        
    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'index0',
            'index1',
            'adc0',
            'adc1',
            'mult0',
            'mult1',
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df

class hitsR5560(hits):
    """
    Helium-3 continuous gas tube (CAEN R5560) hits.
    Mapped from readoutsR5560.

    index carries the physical tube number after ring/fen/tube lookup.
    counter1, ampA, ampB, counter2 are carried through unmodified.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            # ('index',    'int64'),   # Physical tube coordinate
            ('counter1', 'int64'),
            ('ampA',     'int64'),
            ('ampB',     'int64'),
            ('counter2', 'int64'),
        ]
        super().__init__(size, subclass_fields)
        
    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'ampA',
            'ampB',
            'counter1',
            'counter2',
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df

class hitsBM(hits):
    """
    Generic Beam Monitor diagnostic hits.
    Mapped from VMM readouts filtered on ring >= 11 when hardwareType == 'generic'.
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
        
    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'channel',
            'adc',
            'type',
            'posX',
            'posY',
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df

class hitsIBM(hits):
    """
    IBM variant Beam Monitor diagnostic hits.
    Mapped from VMM readouts filtered on ring >= 11 when hardwareType == 'ibm'.
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


    def get_data_frame(self) -> pd.DataFrame:
         """Convert active matrix block to labeled DataFrame for easy inspection."""
         
         columns_to_extract = [
            'pulseT',
            'prevPT',
            'timeStamp',
            'ID',
            'channel',
            'adc',
            'type',
            'debug',
            'mcaSum',
         ]

         df = pd.DataFrame(self.matrix[columns_to_extract])

         return df
     
        
# Note: wait to implement fully — structure TBD
class hitsSKADI(hits):
    """
    SKADI detector hits.
    Mapped from readoutsSKADI.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('IP',      'int64'),
            ('sysID',   'int64'),
            ('channel', 'int64'),
            ('column',  'int64'),
            ('row',     'int64'),
            ('adc',     'int64'),
            ('flag',    'int64'),
            ('opMode',  'int64'),
        ]
        super().__init__(size, subclass_fields)
        
    def get_data_frame(self) -> pd.DataFrame:
      """Convert active matrix block to labeled DataFrame for easy inspection."""
      
      
      # NOTE TO BE IMPLEMENTED
      
      # columns_to_extract = [
      #    'pulseT',
      #    'prevPT',
      #    'timeStamp',
      #    'ID',
      #    'channel',
      #    'adc',
      #    'type',
      #    'debug',
      #    'mcaSum',
      # ]

      df = pd.DataFrame(self.matrix[columns_to_extract])

      return df        