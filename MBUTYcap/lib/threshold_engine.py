import os
import numpy as np
import pandas as pd

from .colors import INFO, WARN, ERR, RESET

# =============================================================================
# Software (pulse-height) threshold engine.
#
# A threshold is a lower bound on pulse height: events whose pulse height
# does not exceed the bound for their channel are rejected. Thresholds are
# defined per physical unit (cassette / column / tube, i.e. matrix['ID'])
# and per local channel within that unit.
#
# 'ch0' refers to the channel selector derived from coordinate0 (wires),
# gating pulseHeight0.
# 'ch1' refers to the channel selector derived from coordinate1
# (strips/grids for MB/MG, tube ID for R5560).
# This mirrors the schema's own field naming (coordinate0/1, pulseHeight0/1)
# rather than introducing detector-specific vocabulary (wire/strip/grid/tube),
# so the same table/engine machinery works for every detector type.
# =============================================================================


# =============================================================================
# Threshold Table
# =============================================================================

# Legacy threshold files label planes by physical name rather than schema
# field name; map them onto the ch0/ch1 selectors used by the engines.
_PLANE_TO_CHANNEL_TYPE = {'wire': 'ch0', 'strip': 'ch1', 'grid': 'ch1', 'tube': 'ch1'}


class ThresholdTable:
    """
    Maps (unit_id, channel_type) -> 1D array of per-local-channel thresholds.
    channel_type is 'ch0' or 'ch1'. Missing (unit_id, channel_type) pairs
    mean "no threshold defined" -> that channel is never gated.
    """

    def __init__(self, table: dict):
        self._table = table  # {(unit_id, channel_type): np.ndarray}

    def get(self, unit_id: int, channel_type: str):
        """Return the threshold array for a unit/channel_type, or None if undefined."""
        return self._table.get((unit_id, channel_type))

    @classmethod
    def from_file(cls, filepath: str, unit_ids: list) -> 'ThresholdTable':
        """
        Load a threshold table (.xlsx or .csv) in the established MBUTY layout:
        first column is the plane label ('wire' / 'strip' / 'grid'), second
        column is the local channel index within that plane, and every
        remaining column is a unit ID (cassette/column) with per-channel
        threshold values down the rows, e.g.

            <blank>   Cassette ID   1      2      3    ...
            wire      0             5000   12380  ...
            wire      1             5000   16190  ...
            ...
            strip     0             0      0      ...

        Despite the header, the second column is a channel index, not a
        cassette ID — the actual unit IDs are the remaining column headers.
        """
        if not os.path.exists(filepath):
            print(f"\t {WARN}WARNING: threshold file '{filepath}' not found -> software thresholds switched OFF{RESET}")
            return cls({})

        print(f"\t {INFO}loading thresholds from file: {os.path.basename(filepath)} ...{RESET}")

        df = pd.read_csv(filepath) if filepath.lower().endswith('.csv') else pd.read_excel(filepath)

        if df.shape[1] < 3:
            print(f"\t {ERR}ERROR: threshold file needs a plane column, a channel column, "
                  f"and at least one unit ID column -> software thresholds switched OFF{RESET}")
            return cls({})

        plane_col, channel_col, *unit_cols = df.columns

        table = {}
        for plane_label, group in df.groupby(plane_col):
            channel_type = _PLANE_TO_CHANNEL_TYPE.get(str(plane_label).strip().lower())
            if channel_type is None:
                print(f"\t {WARN}WARNING: unrecognized plane label '{plane_label}' in threshold file -> skipped{RESET}")
                continue

            group      = group.sort_values(channel_col)
            channels   = group[channel_col].to_numpy(dtype='int64')
            n_channels = int(channels.max()) + 1

            for uid_col in unit_cols:
                try:
                    uid = int(uid_col)
                except (TypeError, ValueError):
                    print(f"\t {WARN}WARNING: threshold file column '{uid_col}' is not a valid unit ID -> skipped{RESET}")
                    continue

                arr = np.zeros(n_channels, dtype='float64')
                arr[channels] = group[uid_col].to_numpy(dtype='float64')
                table[(uid, channel_type)] = arr

        missing_units = set(unit_ids) - {uid for uid, _ in table}
        if missing_units:
            print(f"\t {WARN}WARNING: threshold file has no entries for unit IDs {sorted(missing_units)} "
                  f"-> software thresholds OFF for those units{RESET}")

        return cls(table)

    @classmethod
    def from_arrays(cls, arrays: dict) -> 'ThresholdTable':
        """
        Build directly from user-supplied arrays. Two equivalent shapes accepted:
            {(unit_id, 'ch0'): array, (unit_id, 'ch1'): array, ...}
            {unit_id: {'ch0': array, 'ch1': array}, ...}
        """
        table = {}
        for key, val in arrays.items():
            if isinstance(key, tuple):
                unit_id, channel_type = key
                table[(int(unit_id), str(channel_type))] = np.asarray(val, dtype='float64')
            else:
                for channel_type, arr in val.items():
                    table[(int(key), str(channel_type))] = np.asarray(arr, dtype='float64')
        return cls(table)
    
    @classmethod
    def from_constants(cls, values: tuple, unit_ids: list) -> 'ThresholdTable':
        """
        Build from a flat (ch0_value, ch1_value) pair, same bound for every
        unit_id. Pass None for a plane you don't want gated, e.g. (700, None)
        thresholds ch0 only, leaves ch1 ungated.
        """
        ch0_value, ch1_value = values
        table = {}
        for uid in unit_ids:
            if ch0_value is not None:
                table[(int(uid), 'ch0')] = np.array([float(ch0_value)])
            if ch1_value is not None:
                table[(int(uid), 'ch1')] = np.array([float(ch1_value)])
        return cls(table)

    @classmethod
    def empty(cls) -> 'ThresholdTable':
        return cls({})


# =============================================================================
# Base Threshold Engine
# =============================================================================

class BaseThresholdEngine:
    """
    Shared load/reject logic for all detector types. The pipeline picks
    which concrete engine to instantiate (WireStripThresholdEngine for
    MB/MG, TubeThresholdEngine for R5560) — there's no dispatcher here.
    Subclasses implement apply(), which knows which matrix fields and
    channel-decoding rules are relevant for that detector's geometry.

    Parameters
    ----------
    events     : events container (eventsVMMnormal, eventsR5560, ...)
    config     : flat dict loaded from JSON config file
    parameters : legacy parameters object (dot-notation access)
    """

    def __init__(self, events, config: dict, parameters):
        self.events     = events
        self.config     = config
        self.parameters = parameters
        self.unit_ids   = [entry['ID'] for entry in config['topology']]
        self.table      = ThresholdTable.empty()

    def load(self) -> None:
        """Populate self.table according to parameters.dataReduction.softThresholdType."""
        mode = self.parameters.dataReduction.softThresholdType

        if mode == 'fromFile':
            path = os.path.join(
                self.parameters.fileManagement.thresholdFilePath,
                self.parameters.fileManagement.thresholdFileName,
            )
            self.table = ThresholdTable.from_file(path, self.unit_ids)

        elif mode == 'userDefined':
            print(f"\t {INFO}loading user-defined thresholds ...{RESET}")
            self.table = ThresholdTable.from_arrays(self.parameters.dataReduction.softThArray)
            
        elif mode == 'constants':
            print(f"\t {INFO}loading constant thresholds ...{RESET}")
            self.table = ThresholdTable.from_constants(self.parameters.dataReduction.softThArray, self.unit_ids)

        else:
            print(f"\t {ERR}ERROR: unknown softThresholdType '{mode}' -> software thresholds switched OFF{RESET}")
            self.table = ThresholdTable.empty()
            self.parameters.dataReduction.softThresholdType = 'off'

    def apply(self) -> None:
        """Override in subclasses: build a keep_mask and reject the rest."""
        raise NotImplementedError(f'{self.__class__.__name__} must implement apply()')

    def process_pipeline(self) -> None:
        """Entry point: load thresholds (if enabled) then apply them."""
        if self.parameters.dataReduction.softThresholdType == 'off':
            print(f"\t software thresholds OFF ...")
            return

        self.load()

        if self.parameters.dataReduction.softThresholdType == 'off':
            # load() may itself have switched thresholds off on error
            return

        self.apply()


# =============================================================================
# Wire / Strip / Grid Threshold Engine (Multi-Blade, Multi-Grid)
# =============================================================================

class VMMThresholdEngine(BaseThresholdEngine):
    """
    Dual-plane threshold engine for MB and MG.

    ch0 gates pulseHeight0 (wires), decoded to a per-unit local channel via
    coordinate0 mod n_wires. This mod decode is equivalent to MB's wrap-around
    numbering and to MG's per-unit subtraction (coordinate0 - k*n_wires),
    since both schemes assign coordinate0 = k*n_wires + local_channel.

    ch1 gates pulseHeight1 (strips for MB, grids for MG). coordinate1 is
    already a local, unit-relative index in both cases (see
    MBAbsUnitsCalculator / MGAbsUnitsCalculator in abs_units_engine.py),
    so no decoding is needed there.

    An event is rejected only on a channel it actually has (per the
    coordinate >= 0 sentinel) — a missing plane never gates the event.
    """

    def apply(self) -> None:
        print(f"\t {INFO}applying wire/strip software thresholds ...{RESET}")

        n = self.events.fill_count
        if n == 0:
            return

        m       = self.events.matrix[:n]
        n_wires = int(self.config['wires'])

        has_ch0 = m['coordinate0'] >= 0
        has_ch1 = m['coordinate1'] >= 0

        safe_coord0 = np.nan_to_num(m['coordinate0'], nan=-1)
        ch0_local   = np.mod(safe_coord0.astype('int64'), n_wires)
        ch1_local   = np.nan_to_num(m['coordinate1'], nan=-1).astype('int64')

        keep_ch0 = np.ones(n, dtype=bool)
        keep_ch1 = np.ones(n, dtype=bool)

        for uid in self.unit_ids:
            sel_unit = m['ID'] == uid

            arr0 = self.table.get(uid, 'ch0')
            sel0 = sel_unit & has_ch0
            if arr0 is not None and np.any(sel0):
                idx = np.clip(ch0_local[sel0], 0, len(arr0) - 1)
                keep_ch0[sel0] = m['pulseHeight0'][sel0] > arr0[idx]

            arr1 = self.table.get(uid, 'ch1')
            sel1 = sel_unit & has_ch1
            if arr1 is not None and np.any(sel1):
                idx = np.clip(ch1_local[sel1], 0, len(arr1) - 1)
                keep_ch1[sel1] = m['pulseHeight1'][sel1] > arr1[idx]

        reject_mask = ~(keep_ch0 & keep_ch1)
        self.events.matrix['ID'][:self.events.fill_count][reject_mask] = -1
        self.events.remove_invalid()


# =============================================================================
# Tube Threshold Engine (R5560) — not present in the legacy pipeline
# =============================================================================

class TubeThresholdEngine(BaseThresholdEngine):
    """
    Single-plane threshold engine for the He-3 tube detector (CAEN R5560).

    R5560 has one pulse height per event (pulseHeight0) and no wire/strip
    split. coordinate1 holds the tube ID directly (see
    R5560AbsUnitsCalculator in abs_units_engine.py — no per-unit decode is
    needed, unlike the wire channel above), so 'ch1' selects the per-tube
    threshold that gates pulseHeight0.
    """

    def apply(self) -> None:
        print(f"\t {INFO}applying per-tube software thresholds ...{RESET}")

        n = self.events.fill_count
        if n == 0:
            return

        m         = self.events.matrix[:n]
        tube_local = np.nan_to_num(m['coordinate1'], nan=-1).astype('int64')
        has_tube   = m['coordinate1'] >= 0

        keep = np.ones(n, dtype=bool)

        for uid in self.unit_ids:
            sel_unit = m['ID'] == uid

            arr = self.table.get(uid, 'ch1')
            sel = sel_unit & has_tube
            if arr is not None and np.any(sel):
                idx = np.clip(tube_local[sel], 0, len(arr) - 1)
                keep[sel] = m['pulseHeight0'][sel] > arr[idx]

        self.events.matrix['ID'][:self.events.fill_count][~keep] = -1
        self.events.remove_invalid()
        
# =============================================================================
# Monitor threshold engine 
# ============================================================================= 
def apply_monitor_threshold(events, threshold: float) -> None:
    """
    Flat threshold for the beam monitor: pulseHeight0 <= threshold is
    rejected. No units, no channels, no ThresholdTable — mirrors the
    legacy `if MONThreshold > 0: belowTh = PHW <= MONThreshold` check,
    just using the reject/remove_invalid path instead of removeData().
    """
    if threshold <= 0:
        print(f"\t monitor threshold OFF ...")
        return

    print(f"\t {INFO}applying monitor software threshold ...{RESET}")

    n = events.fill_count
    if n == 0:
        return

    reject_mask = events.matrix['pulseHeight0'][:n] <= threshold
    events.matrix['ID'][:n][reject_mask] = -1
    events.remove_invalid()