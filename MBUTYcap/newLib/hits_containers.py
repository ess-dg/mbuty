import numpy as np
import pandas as pd


class hits():
    """
    Abstract base class for all detector hits.
    Houses the single contiguous memory matrix block and global file metrics.

    Architectural contract (mirrors readout_containers.py):
    - ONE preallocated structured NumPy array (self.matrix) holds all rows.
    - self.fill_count tracks how many rows have been written during the mapping pass.
    - trim() slices matrix[:fill_count] once mapping is complete, releasing slack.
    - get_data_frame() exposes the active rows as a labeled DataFrame for debugging.
    - remove_invalid() discards rows whose ID field was never assigned (stayed -1),
      i.e. readout rows that matched no topology entry in the config.
    """

    def __init__(self, size: int, subclass_fields: list):
        # 1. Non-negotiable core base fields common to every mapped hit.
        #    ID replaces the legacy Cassette/Tube/Column field and carries
        #    the physical unit identifier looked up from config topology.
        base_fields = [
            ('ID',        'int64'),   # Physical unit ID from config topology
            ('timeStamp', 'int64'),
            ('pulseT',    'int64'),
            ('prevPT',    'int64'),
            ('instrID',   'int64'),
        ]

        # 2. Combine base fields with subclass unique mapped coordinates.
        full_schema = np.dtype(base_fields + subclass_fields)

        # 3. Preallocate ONE single contiguous memory matrix block.
        #    ID and all index/plane fields default to -1 to mark unmapped rows.
        self.matrix = np.full(size, -1, dtype=full_schema)

        # Zero-initialise the timing fields which are never sentinel-valued.
        for field in ('timeStamp', 'pulseT', 'prevPT', 'instrID'):
            if field in full_schema.names:
                self.matrix[field] = 0

        # Tracks how many rows have been written during the mapping pass.
        # remove_invalid() and trim() both operate relative to this cursor.
        self.fill_count: int = 0

        # Per-file duration scalars accumulated by the mapping engine.
        self.durations = np.zeros(0, dtype='int64')

    # ------------------------------------------------------------------
    # Memory lifecycle
    # ------------------------------------------------------------------

    def trim(self) -> bool:
        """
        Slice matrix down to fill_count, releasing pre-allocated slack.
        Returns True if unused rows were present (caller may log this).
        Must be called AFTER remove_invalid() so the cursor is already exact.
        """
        had_slack = self.fill_count < len(self.matrix)
        self.matrix     = self.matrix[:self.fill_count]
        return had_slack

    def remove_invalid(self) -> None:
        """
        Remove rows whose ID field was never assigned during mapping (ID == -1).
        These correspond to readout rows that matched no topology entry in the
        config, i.e. the mapping equivalent of the legacy removeUnmappedData().

        Uses a single boolean mask pass — no loops, no per-field concatenation.
        fill_count is updated to match the surviving row count.
        """
        active = self.matrix[:self.fill_count]
        valid_mask = active['ID'] != -1

        removed = int(np.sum(~valid_mask))
        if removed > 0:
            self.matrix[:np.sum(valid_mask)] = active[valid_mask]
            self.fill_count = int(np.sum(valid_mask))
            print(f'\t --> removing {removed} unmapped rows from hits ...')
        else:
            print('\t --> no unmapped data in hits ...')

    # ------------------------------------------------------------------
    # Debug / inspection
    # ------------------------------------------------------------------

    def get_data_frame(self) -> pd.DataFrame:
        """
        Converts the active portion of the structured matrix into a labeled
        Pandas DataFrame for interactive inspection in Spyder or a terminal.
        """
        return pd.DataFrame(self.matrix[:self.fill_count])


# ----------------------------------------------------------------------
# Concrete hits subclasses — one per readout container type
# ----------------------------------------------------------------------

class hitsVMMnormal(hits):
    """
    Multi-Blade / Multi-Grid normal hits.
    Mapped from readoutsVMMnormal after cassette ID lookup and
    channel-to-wire/strip coordinate transformation.

    Fields
    ------
    plane : int64
        Axis discriminator: 0 = wire plane, 1 = strip plane.
        Replaces legacy WorS.
    index : int64
        Global mapped channel coordinate on that plane (wire number or
        strip number after cassette offset is applied).
        Replaces legacy WiresStrips / WiresStripsGlob.
    adc : int64
        Raw ADC value carried forward from the readout.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('plane', 'int64'),   # 0 = wire, 1 = strip
            ('index', 'int64'),   # Global coordinate on the plane
            ('adc',   'int64'),
        ]
        super().__init__(size, subclass_fields)


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


class hitsR5560(hits):
    """
    Helium-3 continuous gas tube (CAEN R5560) hits.
    Mapped from readoutsR5560.

    index carries the physical tube number after ring/fen/tube lookup.
    counter1, ampA, ampB, counter2 are carried through unmodified.
    """
    def __init__(self, size: int = 0):
        subclass_fields = [
            ('index',    'int64'),   # Physical tube coordinate
            ('counter1', 'int64'),
            ('ampA',     'int64'),
            ('ampB',     'int64'),
            ('counter2', 'int64'),
        ]
        super().__init__(size, subclass_fields)


class hitsBM(hits):
    """
    Generic Beam Monitor diagnostic hits.
    Mapped from readoutsBM or from VMM readouts filtered on Ring >= 11
    when hardwareType == 'generic'.
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


class hitsIBM(hits):
    """
    IBM variant Beam Monitor diagnostic hits.
    Mapped from readoutsIBM or from VMM readouts filtered on Ring >= 11
    when hardwareType == 'ibm'.
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

# Note wait to implement fully - need structure
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