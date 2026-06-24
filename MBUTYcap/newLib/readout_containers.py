import numpy as np
import time
from .calibration import load_calibration_map
from .colors import WARN, RESET, INFO
import pandas as pd 

class readouts():
    """
    Abstract base class for all detector readouts.
    Houses the single contiguous memory matrix block and global file metrics.
    """
    def __init__(self, size: int, subclass_fields: list):
        # 1. Non-negotiable core base fields common to every network data frame
        base_fields = [
            # Common fields for all readout types
            ('ring',      'int64'),
            ('fen',       'int64'),
            ('length',    'int64'),
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

    def trim(self) -> bool:
        """
        Slice matrix down to fill_count. Containers with no data become zero-length.
        Returns True if unused rows were present (caller can use this to decide
        whether to print a trimming message).
        """
        had_slack = self.fill_count < len(self.matrix)
        self.matrix = self.matrix[:self.fill_count]
        return had_slack
    
    def get_data_frame(self) -> pd.DataFrame:
        """
        Slices out the actively populated data rows and converts the structured 
        NumPy matrix into a cleanly labeled Pandas DataFrame.
        
        Designed for instant, interactive spreadsheet visualization inside 
        Spyder's Variable Explorer or terminal debugging sessions.
        """
        # Explicit Change: Slice exactly up to fill_count to avoid viewing trailing unpopulated rows
        active_data = self.matrix[:self.fill_count]
        return pd.DataFrame(active_data)

    def clean_and_sort(self, parameters=None) -> None:
        """
        Sort matrix by timeStamp if enabled by configuration, and calculate duration.
        Subclasses that need to filter rows (e.g. VMM) override this method,
        perform their filtering first, then call super().clean_and_sort().
        The super call must come LAST so sort and duration run on the final
        filtered data, not on rows that are about to be removed.
        Guard at top means this is safe to call on empty containers.
        """
        if self.fill_count == 0:
            return

        sort_enabled = getattr(getattr(parameters, 'VMMsettings', None), 'sortReadoutsByTimeStampsONOFF', False)
        if sort_enabled:
            print("Readouts are sorted by timestamp")
            idx = self.matrix['timeStamp'].argsort(kind='quicksort')
            self.matrix = self.matrix[idx]
        else:
            print("Readouts are NOT sorted by timestamp")

        # Calculate durations
        try:
            t_start = self.matrix['timeStamp'][0]
            t_stop  = self.matrix['timeStamp'][-1]
        except IndexError:
            t_start = 0
            t_stop  = 0
            print(f'\t {WARN}WARNING: Not able to calculate duration! (Container might be empty){RESET}')

        self.durations = np.array([t_stop - t_start], dtype='int64')
        
    def calibrate(self, parameters, config: dict) -> None:
        """No-op. Non-VMM containers have no calibration."""
        pass
    
    def check_invalid_tofs(self) -> tuple[int, int, int]:
        """
        Evaluates readouts relative to Pulse Time and falls back to Previous Pulse Time 
        to recover late arrivals. Returns a tuple of (num_readouts, counter_1, counter_2).
        """
        # Calculate and return raw counts to the reader for unified printing
        num_readouts = self.fill_count
        if num_readouts == 0:
            return 0, 0, 0

        active_matrix = self.matrix[:self.fill_count]

        # Stage 1: Check baseline ToF relative to current Pulse Time
        temp_tof     = active_matrix['timeStamp'] - active_matrix['pulseT']
        invalid_mask = temp_tof < 0
        counter_1    = int(np.sum(invalid_mask))
        counter_2    = 0

        # Stage 2: Attempt fallback correction against Previous Pulse Time
        if counter_1 > 0:
            temp_tof_2         = active_matrix['timeStamp'][invalid_mask] - active_matrix['prevPT'][invalid_mask]
            invalid_mask_again = temp_tof_2 < 0
            counter_2          = int(np.sum(invalid_mask_again))

        return num_readouts, counter_1, counter_2
    
    @classmethod
    def merge(cls, container_list: list) -> 'readouts':
        """
        Combine a list of same-type containers into one pre-allocated master
        instance using a single memory allocation and block-copy pass.

        This replaces the legacy field-by-field np.concatenate loop in MBUTY,
        reducing O(N²) copy overhead to O(N).

        Parameters
        ----------
        container_list : list
            List of instances of the calling class. All must share the same
            matrix dtype (guaranteed if they are the same concrete subclass).

        Returns
        -------
        Instance of cls with all active rows merged and fill_count set exactly.
        """
        if not container_list:
            return cls(size=0)

        total_size = sum(c.fill_count for c in container_list)

        master = cls(size=total_size)

        write_ptr = 0
        for source in container_list:
            n = source.fill_count
            if n == 0:
                continue
            master.matrix[write_ptr : write_ptr + n] = source.matrix[:n]
            write_ptr += n

        master.fill_count = total_size

        duration_arrays = [c.durations for c in container_list if len(c.durations) > 0]
        master.durations = np.concatenate(duration_arrays) if duration_arrays else np.zeros(0, dtype='int64')

        return master
    

class readoutsVMM(readouts):
    """
    Intermediate base class for all VMM-based detector readouts.

    Houses the fields common to all VMM formats and shared filtering
    utilities used by both normal and clustered containers.
    """

    def __init__(self, size: int, subclass_fields: list):

        common_vmm_fields = [
            ('hybrid', 'int64'),
            ('geo',    'int64'),
            ('g0',     'int64')
        ]

        super().__init__(size, common_vmm_fields + subclass_fields)

    def remove_g0_rows(self, g0_value: int, mode_name: str) -> None:
        """
        Remove all rows matching a particular g0 mode.
        """

        mask = (self.matrix['g0'] == np.int64(g0_value))

        if not np.any(mask):
            return

        qty = int(np.sum(mask))

        print(
            f'\n\t{WARN}WARNING: {qty} {mode_name} data found in '
            f'READOUTS {self.fill_count}.{RESET}',
            end=''
        )

        time.sleep(1)

        print(f'--> removing {mode_name} data from readouts ...')

        # Boolean fancy indexing produces a new array (a filtered copy of the
        # preallocated block, not a view). The original contiguous allocation is
        # released here. This is intentional — after g0 filtering the matrix is
        # smaller than prealloc_length and a copy is the only correct option.
        # fill_count is updated to match so downstream write-pointer logic stays valid.
        self.matrix = self.matrix[~mask]
        self.fill_count = len(self.matrix)

        print(
            f'removed {qty} {mode_name} readouts --> '
            f'readouts left {self.fill_count}'
        )
        
    def get_ring_fen_hybrid_table(self) -> list[tuple]:
        """Returns sorted list of (ring, fen, hybrid) tuples present in matrix."""
        if self.fill_count == 0:
            return []
        unique = np.unique(self.matrix[['ring', 'fen', 'hybrid']])
        return [(int(r['ring']), int(r['fen']), int(r['hybrid'])) for r in unique]


class readoutsVMMnormal(readoutsVMM):
    """Multi-Blade / Multi-Grid normal readouts parameterized data profile."""

    def __init__(self, size: int = 0):
        # Define fields unique to VMM electronics inside the class constructor
        hardware_fields = [
            ('vmm',     'int64'),
            ('asic',    'int64'),
            ('channel', 'int64'),
            ('adc',     'int64'),
            ('bc',      'int64'),
            ('oth',     'int64'),
            ('tdc',     'int64'),
            ('timeCoarse', 'int64')
        ]

        super().__init__(size, hardware_fields)

    def clean_and_sort(self, parameters=None) -> None:
        """
        Remove calibration rows (g0 == 1) and clustered rows (g0 == 2),
        initialize fine time if selected, then delegate to base class for sort.
        """
        if self.fill_count == 0:
            return

        # Stage 1 — calibration rows (g0 == 1), always removed from both VMM containers
        self.remove_g0_rows(1, 'calibration latency mode')

        # Stage 2 — clustered rows (g0 == 2) do not belong in the normal container
        self.remove_g0_rows(2, 'clustered mode')

        # Conditional timestamp assignment based on selected time resolution type
        time_resolution    = getattr(getattr(parameters, 'VMMsettings', None), 'timeResolutionType', 'coarse')
        ns_per_clock_tick  = float(getattr(getattr(parameters, 'clockTicks', None), 'NSperClockTick', 11.35))

        if time_resolution == 'fine':
            self._calculate_fine_timestamp(ns_per_clock_tick)
        else:
            self.matrix['timeStamp'] = self.matrix['timeCoarse']

        super().clean_and_sort(parameters)
        
    def calibrate(self, parameters, config: dict) -> None:
        if self.fill_count == 0:
            return

        adc_calib_on = getattr(getattr(parameters, 'dataReduction', None), 'calibrateVMM_ADC_ONOFF', False)
        tdc_calib_on = getattr(getattr(parameters, 'dataReduction', None), 'calibrateVMM_TDC_ONOFF', False)

        if not adc_calib_on and not tdc_calib_on:
            return

        calib_path = getattr(getattr(parameters, 'fileManagement', None), 'calibFilePath', '')
        calib_name = getattr(getattr(parameters, 'fileManagement', None), 'calibFileName', '')
        calib_map  = load_calibration_map(calib_path + calib_name, config)

        if adc_calib_on:
            self._calibrate_adc(calib_map)
        if tdc_calib_on:
            self._calibrate_tdc(calib_map, parameters)
            
        
    def _calibrate_adc(self, calib_map: dict) -> None:
        """Applies per-channel linear ADC calibrations to the matrix."""
        if not calib_map:
            return
        print(f'{INFO}Calibrating ADC ...{RESET}')
        
        ring_col   = self.matrix['ring']
        fen_col    = self.matrix['fen']
        hybrid_col = self.matrix['hybrid']
        asic_col   = self.matrix['asic']
        chan_col   = self.matrix['channel']
        adc_col    = self.matrix['adc']

        for (ring, fen, hybrid), entry in calib_map.items():
            mask = (ring_col == ring) & (fen_col == fen) & (hybrid_col == hybrid)
            if not np.any(mask):
                continue

            for asic_idx, offset_arr, slope_arr in (
                (0, entry.vmm0_adc_offset, entry.vmm0_adc_slope),
                (1, entry.vmm1_adc_offset, entry.vmm1_adc_slope),
            ):
                asic_mask = mask & (asic_col == asic_idx)
                if not np.any(asic_mask):
                    continue

                adc_float   = adc_col[asic_mask].astype(np.float64, copy=True)
                channel_idx = chan_col[asic_mask].astype(np.intp)
                calibrated  = np.around((adc_float - offset_arr[channel_idx]) * slope_arr[channel_idx])
                self.matrix['adc'][asic_mask] = np.clip(calibrated, 0, 1023).astype(np.int64)

    def _calibrate_tdc(self, calib_map: dict, parameters) -> None:
        """Applies per-channel TDC fine-time calibration across the full matrix."""
        time_res_type     = getattr(getattr(parameters, 'VMMsettings', None), 'timeResolutionType', 'coarse')
        ns_per_clock_tick = float(getattr(getattr(parameters, 'clockTicks', None), 'NSperClockTick', 11.35))

        if time_res_type != 'fine':
            print(f'\t {WARN}WARNING: calibrateVMM_TDC_ONOFF is True but timeResolutionType is coarse → TDC calibration skipped.{RESET}')
            return

        if not calib_map:
            return
        
        print(f'{INFO}Calibrating TDC and recalculating time stamp ...{RESET}')
        
        ring_col   = self.matrix['ring']
        fen_col    = self.matrix['fen']
        hybrid_col = self.matrix['hybrid']
        asic_col   = self.matrix['asic']
        chan_col   = self.matrix['channel']

        for (ring, fen, hybrid), entry in calib_map.items():
            mask = (ring_col == ring) & (fen_col == fen) & (hybrid_col == hybrid)
            if not np.any(mask):
                continue

            for asic_idx, offset_arr, slope_arr in (
                (0, entry.vmm0_tdc_offset, entry.vmm0_tdc_slope),
                (1, entry.vmm1_tdc_offset, entry.vmm1_tdc_slope),
            ):
                asic_mask = mask & (asic_col == asic_idx)
                if not np.any(asic_mask):
                    continue

                self._calculate_fine_timestamp(
                    ns_per_clock_tick,
                    mask=asic_mask,
                    tdc_offset_array=offset_arr,
                    tdc_slope_array=slope_arr,
                )


    def _calculate_fine_timestamp(
        self,
        ns_per_clock_tick: float,
        mask=None,
        tdc_offset_array: np.ndarray = None,
        tdc_slope_array: np.ndarray = None,
    ) -> None:
        """Apply TDC→ns conversion to timeStamp. Operates in-place on self.matrix."""
        m = mask if mask is not None else slice(self.fill_count)
        
        tdc_raw = self.matrix['tdc'][m].astype(np.float64)
        chan = self.matrix['channel'][m].astype(np.intp)
        
        if tdc_offset_array is not None and tdc_slope_array is not None:
            tdc_calib = (tdc_raw - tdc_offset_array[chan]) * tdc_slope_array[chan]
        else:
            tdc_calib = tdc_raw
        
        tdc_clip = np.clip(tdc_calib, 0, 255).astype(np.float64)
        tdc_ns = np.round((ns_per_clock_tick * 3.0) - (tdc_clip * 60.0 / 255.0) ).astype(np.int64)
        
        self.matrix['timeStamp'][m] = self.matrix['timeCoarse'][m] + tdc_ns


class readoutsVMMclustered(readoutsVMM):
    """Multi-Blade clustered readouts parameterized data profile."""

    def __init__(self, size: int = 0):
        hardware_fields = [
            ('channel0', 'int64'),
            ('adc0',     'int64'),
            ('mult0',    'int64'),
            ('channel1', 'int64'),
            ('adc1',     'int64'),
            ('mult1',    'int64')
        ]

        super().__init__(size, hardware_fields)

    def clean_and_sort(self, parameters=None) -> None:
        """
        Remove calibration rows (g0 == 1) and normal-hit rows (g0 == 0),
        then delegate to base class for sort and duration.
        This container holds clustered readouts (g0 == 2) only.
        """
        if self.fill_count == 0:
            return

        # Stage 1 — calibration rows (g0 == 1), always removed from both VMM containers
        self.remove_g0_rows(1, 'calibration latency mode')

        # Stage 2 — normal-hit rows (g0 == 0) do not belong in the clustered container
        self.remove_g0_rows(0, 'normal hit mode')

        super().clean_and_sort(parameters)


class readoutsR5560(readouts):
    """Helium-3 continuous gas tube (CAEN) parameterized data profile."""

    def __init__(self, size: int = 0):
        hardware_fields = [
            ('tube',     'int64'),
            ('counter1', 'int64'),
            ('ampA',     'int64'),
            ('ampB',     'int64'),
            ('counter2', 'int64')
        ]

        super().__init__(size, hardware_fields)

class readoutsBM(readouts):
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


class readoutsIBM(readouts):
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


class readoutsSKADI(readouts):
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