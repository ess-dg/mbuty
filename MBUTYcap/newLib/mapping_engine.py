#!/usr/bin/env python3
"""
mapping_engine.py — Vectorized ESS neutron detector geometry mapper.

Pipeline position: readouts → [mapping_engine] → hits

Contract
--------
Each public mapper class accepts a fully populated readouts container
plus the raw JSON config dict, and returns a populated hits container
of the matching type. No element-by-element loops. Every coordinate
assignment is a single vectorized NumPy pass.

The hits container owns its own memory lifecycle. Mappers prepare computed
coordinate arrays and hand them to hits.absorb(), which writes timing,
writes all fields, and calls remove_invalid() to physically compact the
matrix. Mappers never write to hits.matrix directly and never call
remove_invalid() themselves.

Class hierarchy
---------------
DetectorMapper              Abstract base.
                              _build_topology_arrays() — generic topology extractor.
                              _assign_ids_vectorized() — generic single third-key match.
  MBMapper                  Multi-Blade normal    (readoutsVMMnormal   → hitsVMMnormal)
  MBClustMapper             Multi-Blade clustered (readoutsVMMclustered → hitsVMMclustered)
  MGMapper                  Multi-Grid normal     (readoutsVMMnormal   → hitsVMMnormal)
                              Overrides _assign_ids_vectorized for two-hybrid OR match.
  He3Mapper                 Helium-3 R5560        (readoutsR5560       → hitsR5560)
  MonitorMapper             Beam Monitor          (readoutsVMMnormal   → hitsBM | hitsIBM)
                              Completely standalone — no topology lookup.

Dispatcher
----------
    config = json.load(open('AMOR26.json'))
    hits   = map_detector(readouts_vmm_normal, config)
    mon, found = MonitorMapper.map(readouts_vmm_normal, config)
"""

import numpy as np
import os
import sys

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.colors import WARN, ERR, INFO, OK, RESET
from newLib.hits_containers import (
    hitsVMMnormal,
    hitsVMMclustered,
    hitsR5560,
    hitsBM,
    hitsIBM,
)


# =============================================================================
# MG hardware iteration constant
# =============================================================================
# Selects which physical adapter PCB wiring scheme is in use for Multi-Grid.
# 0 = new penthouse PCB + new ebox PCB       (correct production configuration)
# 1 = old penthouse PCB + new interface PCB  (test vessel only, transitional)
# 2 = new penthouse PCB + new interface PCB  (test vessel only, transitional)
# Modes 1 and 2 will be removed once all hardware is on the production config.
MG_SWAP_IT = 0


# =============================================================================
# Module-level helpers — private, not part of public API
# =============================================================================

def _derive_adapter_type(wire_asic: int) -> str:
    """
    MB adapter type is implicit in which ASIC carries the wires.
    wireASIC == 1  →  'reverse'  (e.g. AMOR26)
    wireASIC == 0  →  'straight'
    """
    return 'reverse' if wire_asic == 1 else 'straight'


def _report_unmapped_units(
    assigned_ids: np.ndarray,
    config_ids: np.ndarray,
    unit_label: str = 'unit',
) -> None:
    """Warn about topology entries that produced no mapped hits."""
    found_ids = np.unique(assigned_ids[assigned_ids != -1])
    missing   = np.setdiff1d(config_ids, found_ids)
    if len(missing) > 0:
        id_list = ' '.join(str(x) for x in missing)
        print(
            f'\t {WARN}WARNING: {unit_label} IDs: {id_list} '
            f'not found in data file. Mapping skipped for those.{RESET}'
        )


# =============================================================================
# DetectorMapper — abstract base
# =============================================================================

class DetectorMapper:
    """
    Abstract base for all detector mappers.

    Provides two shared utilities used by every concrete mapper:

    _build_topology_arrays(topology, keys)
        Converts the config topology list into a dict of parallel int64
        NumPy arrays, one per requested key. Generic across all detector
        types — the caller declares which keys it needs.

    _assign_ids_vectorized(src, topo_arrays, src_third_field)
        Broadcasts a (n_readouts × n_topology) boolean match matrix over
        (ring, fen, <third_field>) and returns per-row ID assignments.
        This is the default single third-key match. MGMapper overrides it
        with a two-hybrid OR match.

    Subclasses must implement map() as a @staticmethod.
    """

    @staticmethod
    def _build_topology_arrays(topology: list, keys: list) -> dict:
        """
        Extract named fields from the config topology list into parallel
        int64 NumPy arrays.

        Parameters
        ----------
        topology : list of dicts
            config['topology'] — one dict per physical unit.
        keys : list of str
            Field names to extract. Every key must be present in each entry.

        Returns
        -------
        dict mapping key -> np.ndarray of shape (N,), dtype int64.
        """
        return {
            k: np.array([e[k] for e in topology], dtype='int64')
            for k in keys
        }

    @staticmethod
    def _assign_ids_vectorized(
        src: np.ndarray,
        topo_arrays: dict,
        src_third_field: str,
    ) -> tuple:
        """
        Map every readout row to a topology unit ID by matching its
        (ring, fen, <src_third_field>) triple against the topology arrays.

        Strategy: broadcast a (n_readouts × n_topology) boolean match matrix
        in one pass, then argmax along axis=1 to resolve the topology index
        for each row. Rows that match nothing stay at ID = -1.

        Parameters
        ----------
        src : np.ndarray
            Active slice of the readout matrix (readouts.matrix[:n]).
        topo_arrays : dict
            Must contain 'ID', 'ring', 'fen', and the key named by
            src_third_field. Built by _build_topology_arrays().
        src_third_field : str
            Field name in src to use as the third match key.
            'hybrid' for MB; 'tube' for He3.

        Returns
        -------
        assigned_ids : int64 array, shape (n_readouts,)  — -1 where no match
        topo_idx     : int64 array, shape (n_readouts,)  — index into topology
        valid_mask   : bool  array, shape (n_readouts,)
        """
        ids   = topo_arrays['ID']
        rings = topo_arrays['ring']
        fens  = topo_arrays['fen']
        third = topo_arrays[src_third_field]

        r = src['ring']
        f = src['fen']
        h = src[src_third_field]

        # Broadcast: (n_readouts, n_topology)
        match = (
            (r[:, None] == rings[None, :]) &
            (f[:, None] == fens[None, :])  &
            (h[:, None] == third[None, :])
        )

        valid_mask   = match.any(axis=1)
        topo_idx     = np.where(valid_mask, match.argmax(axis=1), np.int64(-1))
        assigned_ids = np.where(valid_mask, ids[topo_idx], np.int64(-1))

        return assigned_ids.astype('int64'), topo_idx.astype('int64'), valid_mask

    @staticmethod
    def map(readouts, config: dict):
        raise NotImplementedError(
            "DetectorMapper subclasses must implement map(readouts, config)."
        )


# =============================================================================
# MBMapper — Multi-Blade VMM normal mode
# =============================================================================

class MBMapper(DetectorMapper):
    """
    Maps readoutsVMMnormal → hitsVMMnormal for Multi-Blade detectors.

    Topology key: single 'hybrid' per cassette entry.

    Channel coordinate rules (from legacy libMapping.mapChannels):

    Adapter 'reverse'  (wireASIC == 1):
        Wires  : asic == wireASIC,  channel in [16, 47]  →  index = channel - 16
        Strips : asic == stripASIC, channel in [0,  63]  →  index = 63 - channel

    Adapter 'straight' (wireASIC == 0):
        Wires  : asic == wireASIC,  channel in [16, 47]  →  index = 31 - (channel - 16)
        Strips : asic == stripASIC, channel in [0,  63]  →  index = channel

    Global wire offset (from legacy mapChannelsGlob):
        index_global = index_local + cassette_rank * num_wires
        where cassette_rank is the 0-based position of the cassette in the
        topology list (not the ID value itself).
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMnormal:
        """
        Parameters
        ----------
        readouts : readoutsVMMnormal
        config   : dict  (raw JSON config)

        Returns
        -------
        hitsVMMnormal — populated, physically compacted, invalid rows removed.
        """
        topology   = config['topology']
        wire_asic  = int(config['channelMapping'][0]['wireASIC'])
        strip_asic = int(config['channelMapping'][0]['stripASIC'])
        num_wires  = int(config['wires'])
        adapter    = _derive_adapter_type(wire_asic)

        if wire_asic == strip_asic:
            raise ValueError(
                'CONFIG ERROR: wireASIC and stripASIC are identical — '
                'wires and strips cannot share an ASIC.'
            )

        topo = DetectorMapper._build_topology_arrays(
            topology, ['ID', 'ring', 'fen', 'hybrid']
        )

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: topology ID lookup --------------------------------------
        assigned_ids, topo_idx, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='hybrid'
        )

        # --- Step 2: channel coordinate masks --------------------------------
        asic    = src['asic']
        channel = src['channel']

        is_wire  = valid_mask & (asic == np.int64(wire_asic))  & (channel >= 16) & (channel <= 47)
        is_strip = valid_mask & (asic == np.int64(strip_asic)) & (channel >= 0)  & (channel <= 63)

        # --- Step 3: local channel coordinate --------------------------------
        local_index = np.full(n, -1, dtype='int64')
        plane       = np.full(n, -1, dtype='int64')

        if adapter == 'reverse':
            local_index[is_wire]  = channel[is_wire] - np.int64(16)
            local_index[is_strip] = np.int64(63) - channel[is_strip]
        else:  # straight
            local_index[is_wire]  = np.int64(31) - (channel[is_wire] - np.int64(16))
            local_index[is_strip] = channel[is_strip]

        plane[is_wire]  = np.int64(0)
        plane[is_strip] = np.int64(1)

        # --- Step 4: global wire offset (wire plane only) --------------------
        cassette_rank = np.where(valid_mask, topo_idx, np.int64(0))
        wire_offset   = (cassette_rank * np.int64(num_wires)).astype('int64')

        global_index = local_index.copy()
        global_index[is_wire] = local_index[is_wire] + wire_offset[is_wire]

        # --- Step 5: hand off to hits container ------------------------------
        h = hitsVMMnormal(size=n)
        h.durations = readouts.durations.copy()
        h.absorb(
            computed_fields={
                'ID':    assigned_ids,
                'plane': plane,
                'index': global_index,
                'adc':   src['adc'].astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'cassette')
        return h


# =============================================================================
# MBClustMapper — Multi-Blade VMM clustered mode
# =============================================================================

class MBClustMapper(DetectorMapper):
    """
    Maps readoutsVMMclustered → hitsVMMclustered for Multi-Blade detectors.

    Topology key: single 'hybrid' per cassette (same as MBMapper).

    Each readout row already contains a pre-paired wire+strip event:
    channel0/adc0/mult0 and channel1/adc1/mult1. Which slot carries wires
    vs strips is determined by wireASIC:

    wireASIC == 1  ('reverse'):
        Wire  slot → channel1, adc1, mult1  →  index0 = channel1 - 16
        Strip slot → channel0, adc0, mult0  →  index1 = 63 - channel0

    wireASIC == 0  ('straight'):
        Wire  slot → channel0, adc0, mult0  →  index0 = 31 - (channel0 - 16)
        Strip slot → channel1, adc1, mult1  →  index1 = channel1

    Global wire offset applied to index0 exactly as in MBMapper.
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMclustered:
        topology  = config['topology']
        wire_asic = int(config['channelMapping'][0]['wireASIC'])
        num_wires = int(config['wires'])
        adapter   = _derive_adapter_type(wire_asic)

        topo = DetectorMapper._build_topology_arrays(
            topology, ['ID', 'ring', 'fen', 'hybrid']
        )

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: topology ID lookup --------------------------------------
        assigned_ids, topo_idx, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='hybrid'
        )

        # --- Step 2: unpack wire and strip raw channels from correct slots ---
        if adapter == 'reverse':
            # wireASIC == 1 → wires in slot 1
            wire_ch    = src['channel1']
            wire_adc   = src['adc1']
            wire_mult  = src['mult1']
            strip_ch   = src['channel0']
            strip_adc  = src['adc0']
            strip_mult = src['mult0']
        else:
            # wireASIC == 0 → wires in slot 0
            wire_ch    = src['channel0']
            wire_adc   = src['adc0']
            wire_mult  = src['mult0']
            strip_ch   = src['channel1']
            strip_adc  = src['adc1']
            strip_mult = src['mult1']

        # --- Step 3: channel-to-coordinate transform -------------------------
        wire_in_range  = (wire_ch  >= 16) & (wire_ch  <= 47)
        strip_in_range = (strip_ch >= 0)  & (strip_ch <= 63)

        if adapter == 'reverse':
            local_wire_index = np.where(
                valid_mask & wire_in_range,
                wire_ch - np.int64(16),
                np.int64(-1),
            )
            local_strip_index = np.where(
                valid_mask & strip_in_range,
                np.int64(63) - strip_ch,
                np.int64(-1),
            )
        else:
            local_wire_index = np.where(
                valid_mask & wire_in_range,
                np.int64(31) - (wire_ch - np.int64(16)),
                np.int64(-1),
            )
            local_strip_index = np.where(
                valid_mask & strip_in_range,
                strip_ch,
                np.int64(-1),
            )

        # --- Step 4: global wire offset --------------------------------------
        cassette_rank     = np.where(valid_mask, topo_idx, np.int64(0))
        wire_offset       = (cassette_rank * np.int64(num_wires)).astype('int64')
        global_wire_index = np.where(
            local_wire_index >= 0,
            local_wire_index + wire_offset,
            np.int64(-1),
        )

        # --- Step 5: hand off to hits container ------------------------------
        h = hitsVMMclustered(size=n)
        h.durations = readouts.durations.copy()
        h.absorb(
            computed_fields={
                'ID':     assigned_ids,
                'index0': global_wire_index,
                'index1': local_strip_index,
                'adc0':   wire_adc.astype('int64'),
                'adc1':   strip_adc.astype('int64'),
                'mult0':  wire_mult.astype('int64'),
                'mult1':  strip_mult.astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'cassette')
        return h


# =============================================================================
# MGMapper — Multi-Grid VMM normal mode
# =============================================================================

class MGMapper(DetectorMapper):
    """
    Maps readoutsVMMnormal → hitsVMMnormal for Multi-Grid detectors.

    Topology key: TWO hybrids per column — 'hybridW' (wires) and 'hybridS'
    (grids/strips). The readout field 'hybrid' may match either one; which it
    matched determines the plane assignment.

    Overrides _assign_ids_vectorized with _assign_ids_mg, which uses OR logic
    across both hybrid fields and derives plane from which one matched.

    Channel formulas (controlled by module-level MG_SWAP_IT constant):

    MG_SWAP_IT == 0  (production: new penthouse PCB + new ebox PCB):
        Wires  : index = 119 - (channel + 64 * asic)
        Grids  : index = channel - 10 + 44 * asic

    MG_SWAP_IT == 1  (transitional: old penthouse + new interface PCB):
        Wires  : np.select over 4 conditions (preserved verbatim from legacy)
        Grids  : np.select over 3 conditions (preserved verbatim from legacy)

    MG_SWAP_IT == 2  (transitional: new penthouse + new interface PCB):
        Wires  : np.select over 7 conditions (preserved verbatim from legacy)
        Grids  : np.select over 2 conditions (preserved verbatim from legacy)

    Global wire offset:
        index_global = index_local + column_rank * num_wires
        where column_rank is the 0-based position of the column in the
        topology list (identical math to MBMapper).
    """

    @staticmethod
    def _assign_ids_vectorized(
        src: np.ndarray,
        topo_arrays: dict,
        src_third_field: str = 'hybrid',  # unused for MG, kept for interface consistency
    ) -> tuple:
        """
        MG-specific topology lookup. Overrides DetectorMapper._assign_ids_vectorized.

        A readout row belongs to a column if:
            ring == rings[k]  AND  fen == fens[k]
            AND (hybrid == hybridW[k]  OR  hybrid == hybridS[k])

        Plane assignment falls out of which hybrid matched:
            hybrid == hybridW[k]  →  plane = 0 (wire)
            hybrid == hybridS[k]  →  plane = 1 (grid/strip)

        Returns
        -------
        assigned_ids : int64 (n,)   — -1 where no match
        topo_idx     : int64 (n,)   — column index in topology arrays
        valid_mask   : bool  (n,)
        plane        : int64 (n,)   — 0=wire, 1=grid, -1=unmatched

        Note: returns a 4-tuple (not 3) to carry the plane array.
        MGMapper.map() unpacks accordingly.
        """
        ids      = topo_arrays['ID']
        rings    = topo_arrays['ring']
        fens     = topo_arrays['fen']
        hybridWs = topo_arrays['hybridW']
        hybridSs = topo_arrays['hybridS']

        r = src['ring']    # (n,)
        f = src['fen']     # (n,)
        h = src['hybrid']  # (n,)

        # Broadcast: (n_readouts, n_topology)
        ring_match = r[:, None] == rings[None, :]    # (n, N)
        fen_match  = f[:, None] == fens[None, :]     # (n, N)
        hybW_match = h[:, None] == hybridWs[None, :] # (n, N)
        hybS_match = h[:, None] == hybridSs[None, :] # (n, N)

        col_match  = ring_match & fen_match & (hybW_match | hybS_match)  # (n, N)

        valid_mask   = col_match.any(axis=1)
        topo_idx     = np.where(valid_mask, col_match.argmax(axis=1), np.int64(-1))
        assigned_ids = np.where(valid_mask, ids[topo_idx], np.int64(-1))

        # Derive plane from which hybrid matched at the resolved column index.
        safe_idx = np.where(valid_mask, topo_idx, np.int64(0))

        is_wire  = valid_mask & (h == hybridWs[safe_idx])
        is_strip = valid_mask & (h == hybridSs[safe_idx])

        plane = np.full(len(src), -1, dtype='int64')
        plane[is_wire]  = np.int64(0)
        plane[is_strip] = np.int64(1)

        return (
            assigned_ids.astype('int64'),
            topo_idx.astype('int64'),
            valid_mask,
            plane,
        )

    @staticmethod
    def _map_channels(
        src: np.ndarray,
        valid_mask: np.ndarray,
        plane: np.ndarray,
        num_wires: int,
        num_grids: int,
    ) -> np.ndarray:
        """
        Apply MG channel-to-coordinate formulas, controlled by MG_SWAP_IT.

        Returns
        -------
        local_index : int64 array, shape (n,)
            Local wire or grid coordinate; -1 for out-of-range or unmatched rows.
        """
        n = len(src)
        channel = src['channel']
        asic    = src['asic']

        local_index = np.full(n, -1, dtype='int64')

        is_wire  = valid_mask & (plane == 0)
        is_strip = valid_mask & (plane == 1)

        if MG_SWAP_IT == 0:
            # -----------------------------------------------------------------
            # Production mapping: new penthouse PCB + new ebox PCB
            # -----------------------------------------------------------------

            # WIRES: index = 119 - (channel + 64 * asic)
            tempW = np.int64(119) - (channel[is_wire] + np.int64(64) * asic[is_wire])
            bad_w = tempW >= np.int64(num_wires)
            if np.any(bad_w):
                print(f'Warning: found Wires above {num_wires - 1} in MG column — setting to -1')
            tempW[bad_w] = np.int64(-1)
            local_index[is_wire] = tempW

            # GRIDS: index = channel - 10 + 44 * asic
            tempS = channel[is_strip] - np.int64(10) + np.int64(44) * asic[is_strip]
            bad_s = tempS >= np.int64(num_grids)
            if np.any(bad_s):
                print(f'Warning: found Grids above {num_grids - 1} in MG column — setting to -1')
            tempS[bad_s] = np.int64(-1)
            local_index[is_strip] = tempS

        elif MG_SWAP_IT == 1:
            # -----------------------------------------------------------------
            # Transitional: old penthouse PCB + new interface PCB (test vessel)
            # Preserved verbatim from libMappingMG.mapDetector.mapp1cass
            # -----------------------------------------------------------------
            print(f'{WARN}----> WARNING: USING TEMPORARY INTERFACE PCB MAPPING (swapIT=1)!!!{RESET}')

            ch_w   = channel[is_wire]
            asic_w = asic[is_wire]

            wire_conditions = [
                (ch_w >= 16) & (ch_w <= 55) & (asic_w == 1),
                (ch_w >= 40) & (ch_w <= 63) & (asic_w == 0),
                (ch_w >= 0)  & (ch_w <= 16) & (asic_w == 1),
                (ch_w >= 0)  & (ch_w <= 39) & (asic_w == 0),
            ]
            wire_choices = [
                ch_w - 16,
                ch_w,
                ch_w + 64,
                ch_w + 80,
            ]
            local_index[is_wire] = np.select(wire_conditions, wire_choices, default=-1)

            ch_s   = channel[is_strip]
            asic_s = asic[is_strip]

            strip_conditions = [
                (ch_s >= 0)  & (ch_s <= 43) & (asic_s == 0),
                (ch_s >= 0)  & (ch_s <= 23) & (asic_s == 1),
                (ch_s >= 44) & (ch_s <= 63) & (asic_s == 0),
            ]
            strip_choices = [
                43 - ch_s,
                67 - ch_s,
                131 - ch_s,
            ]
            local_index[is_strip] = np.select(strip_conditions, strip_choices, default=-1)

        elif MG_SWAP_IT == 2:
            # -----------------------------------------------------------------
            # Transitional: new penthouse PCB + new interface PCB (test vessel)
            # Preserved verbatim from libMappingMG.mapDetector.mapp1cass
            # -----------------------------------------------------------------
            print(f'{WARN}----> WARNING: USING TEMPORARY INTERFACE PCB MAPPING (swapIT=2)!!!{RESET}')

            ch_w   = channel[is_wire]
            asic_w = asic[is_wire]

            wire_conditions = [
                (ch_w >= 20) & (ch_w <= 39) & (asic_w == 0),
                (ch_w >= 0)  & (ch_w <= 19) & (asic_w == 0),
                (ch_w >= 60) & (ch_w <= 63) & (asic_w == 0),
                (ch_w >= 0)  & (ch_w <= 15) & (asic_w == 1),
                (ch_w >= 40) & (ch_w <= 59) & (asic_w == 0),
                (ch_w >= 36) & (ch_w <= 55) & (asic_w == 1),
                (ch_w >= 16) & (ch_w <= 35) & (asic_w == 1),
            ]
            wire_choices = [
                ch_w - 20,
                ch_w + 20,
                ch_w - 20,
                ch_w + 44,
                ch_w + 20,
                ch_w + 44,
                ch_w + 84,
            ]
            local_index[is_wire] = np.select(wire_conditions, wire_choices, default=-1)

            ch_s   = channel[is_strip]
            asic_s = asic[is_strip]

            strip_conditions = [
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 0),
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 1),
            ]
            strip_choices = [
                53 - ch_s,
                97 - ch_s,
            ]
            local_index[is_strip] = np.select(strip_conditions, strip_choices, default=-1)

        else:
            raise ValueError(
                f'MGMapper: MG_SWAP_IT={MG_SWAP_IT} is not a valid value. '
                f'Must be 0, 1, or 2.'
            )

        return local_index

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMnormal:
        """
        Parameters
        ----------
        readouts : readoutsVMMnormal
        config   : dict  (raw JSON config)

        Returns
        -------
        hitsVMMnormal — populated, physically compacted, invalid rows removed.
        """
        topology  = config['topology']
        num_wires = int(config['wires'])
        num_grids = int(config['strips'])

        topo = DetectorMapper._build_topology_arrays(
            topology, ['ID', 'ring', 'fen', 'hybridW', 'hybridS']
        )

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: MG topology lookup (two-hybrid match + plane derivation) --
        assigned_ids, topo_idx, valid_mask, plane = MGMapper._assign_ids_vectorized(src, topo)

        # --- Step 2: channel-to-coordinate formulas --------------------------
        local_index = MGMapper._map_channels(src, valid_mask, plane, num_wires, num_grids)

        # --- Step 3: global wire offset (wire plane only) --------------------
        is_wire       = valid_mask & (plane == 0)
        cassette_rank = np.where(valid_mask, topo_idx, np.int64(0))
        wire_offset   = (cassette_rank * np.int64(num_wires)).astype('int64')

        global_index = local_index.copy()
        global_index[is_wire] = local_index[is_wire] + wire_offset[is_wire]

        # --- Step 4: hand off to hits container ------------------------------
        h = hitsVMMnormal(size=n)
        h.durations = readouts.durations.copy()
        h.absorb(
            computed_fields={
                'ID':    assigned_ids,
                'plane': plane,
                'index': global_index,
                'adc':   src['adc'].astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'column')
        return h


# =============================================================================
# He3Mapper — Helium-3 CAEN R5560
# =============================================================================

class He3Mapper(DetectorMapper):
    """
    Maps readoutsR5560 → hitsR5560.

    Topology key: 'tube'. The readout field is also 'tube'.
    Uses the base _assign_ids_vectorized with src_third_field='tube'.

    No channel formula, no plane, no adapter, no global offset.
    index = the topology ID (physical tube number).
    counter1, ampA, ampB, counter2 are carried through unmodified.
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsR5560:
        """
        Parameters
        ----------
        readouts : readoutsR5560
        config   : dict  (raw JSON config)

        Returns
        -------
        hitsR5560 — populated, physically compacted, invalid rows removed.
        """
        topology = config['topology']

        topo = DetectorMapper._build_topology_arrays(
            topology, ['ID', 'ring', 'fen', 'tube']
        )

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: topology ID lookup --------------------------------------
        assigned_ids, _, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='tube'
        )

        # For He3 the physical position IS the topology ID — no further formula.
        index = np.where(valid_mask, assigned_ids, np.int64(-1))

        # --- Step 2: hand off to hits container ------------------------------
        h = hitsR5560(size=n)
        h.durations = readouts.durations.copy()
        h.absorb(
            computed_fields={
                'ID':       assigned_ids,
                'index':    index,
                'counter1': src['counter1'].astype('int64'),
                'ampA':     src['ampA'].astype('int64'),
                'ampB':     src['ampB'].astype('int64'),
                'counter2': src['counter2'].astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'tube')
        return h


# =============================================================================
# MonitorMapper — Beam Monitor (generic or IBM)
# =============================================================================

class MonitorMapper:
    """
    Maps the monitor stream out of a VMM normal readout container into
    hitsBM (hardwareType == 'generic') or hitsIBM (hardwareType == 'ibm').

    Completely standalone — no topology lookup, does not inherit from
    DetectorMapper.

    The monitor occupies ring >= 11 in the readout stream. The specific
    (ring, channel) pair to accept is declared in config['monitor'][0].

    Detection logic (mirrors legacy mapMonitor):
    1. Build a mask for the exact (ring, channel) pair from config.
    2. Scan ring >= 11 rows for any (ring, channel) pairs actually present.
    3. If the configured pair is found → map those rows.
    4. If a different single pair is found → warn, return empty container.
    5. If nothing at all in ring >= 11 → warn, return empty container.

    Returns
    -------
    (hits_container, found_flag) : tuple
        hits_container is hitsBM or hitsIBM depending on hardwareType.
        found_flag is True if monitor data was successfully mapped.

    NOTE: supports only ONE monitor entry (legacy behaviour preserved).
    """

    @staticmethod
    def map(readouts, config: dict) -> tuple:
        mon_cfg       = config['monitor'][0]
        mon_id        = int(mon_cfg['ID'])
        hardware_type = str(mon_cfg['hardwareType']).lower()
        mon_ring      = int(mon_cfg['ring'])
        mon_channel   = int(mon_cfg['channel'])

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        ring_col    = src['ring']
        channel_col = src['channel']

        target_mask   = (ring_col == np.int64(mon_ring)) & \
                        (channel_col == np.int64(mon_channel))
        mon_band_mask = ring_col >= np.int64(11)

        if np.any(mon_band_mask):
            mon_pairs = np.unique(
                np.column_stack([
                    ring_col[mon_band_mask],
                    channel_col[mon_band_mask],
                ]),
                axis=0,
            )
        else:
            mon_pairs = np.empty((0, 2), dtype='int64')

        found_flag = False
        hits_out   = MonitorMapper._make_empty_container(hardware_type)

        if np.any(target_mask):
            if len(mon_pairs) > 1:
                print(
                    f'\t {WARN}WARNING: Found {len(mon_pairs)} monitor sources in data. '
                    f'MBUTY supports only one Monitor. Mapping according to config, '
                    f'but data contains (ring, channel): {mon_pairs.tolist()}{RESET}'
                )
            hits_out   = MonitorMapper._fill(src, target_mask, hardware_type, mon_id)
            found_flag = True
            print(f'{INFO}Mapping Monitor ...{RESET}')

        elif len(mon_pairs) == 1:
            wrong_ring, wrong_ch = mon_pairs[0]
            print(
                f'\t {WARN}WARNING: mismatch → one monitor candidate found but it is '
                f'NOT the one selected in config. '
                f'Data contains ring {wrong_ring} and channel {wrong_ch}.{RESET}'
            )

        else:
            print(f'\t {WARN}No MONITOR data found in data file{RESET}')

        hits_out.durations = readouts.durations.copy()
        return hits_out, found_flag

    @staticmethod
    def _make_empty_container(hardware_type: str):
        if hardware_type == 'ibm':
            return hitsIBM(size=0)
        return hitsBM(size=0)

    @staticmethod
    def _fill(src: np.ndarray, mask: np.ndarray, hardware_type: str, mon_id: int):
        """
        Pack selected rows into the correct monitor hits container.

        hitsBM  fields: ID, timeStamp, pulseT, prevPT, instrID, type, channel, adc, posX, posY
        hitsIBM fields: ID, timeStamp, pulseT, prevPT, instrID, type, channel, debug, adc, mcaSum

        The VMM normal readout carries adc and channel directly. The remaining
        monitor-specific fields (posX, posY for BM; debug, mcaSum for IBM) have
        no equivalent in a VMM readout stream and are left at the -1 sentinel
        established by hits.__init__. This is correct — those fields are only
        populated when the hardware itself provides them.
        """
        count = int(np.sum(mask))
        rows  = src[mask]

        h = hitsIBM(size=count) if hardware_type == 'ibm' else hitsBM(size=count)

        h.absorb(
            computed_fields={
                'ID':      np.full(count, np.int64(mon_id), dtype='int64'),
                'channel': rows['channel'].astype('int64'),
                'adc':     rows['adc'].astype('int64'),
            },
            timing_src=rows,
        )
        return h


# =============================================================================
# map_detector — top-level dispatcher
# =============================================================================

def map_detector(readouts, config: dict):
    """
    Top-level convenience dispatcher. Inspects config['detectorType'] and
    config['operationMode'] to select and invoke the correct mapper class.

    Returns the populated hits container for the detector stream.
    For monitor extraction call MonitorMapper.map() separately — it consumes
    the same readouts object.

    Raises
    ------
    ValueError
        On unsupported detectorType / operationMode combinations.
    """
    det_type = config.get('detectorType', '')
    op_mode  = config.get('operationMode', 'normal')

    if det_type == 'MB':
        if op_mode == 'clustered':
            return MBClustMapper.map(readouts, config)
        if op_mode == 'normal':
            return MBMapper.map(readouts, config)
        raise ValueError(f'map_detector: unsupported operationMode "{op_mode}" for MB.')

    if det_type == 'MG':
        if op_mode == 'clustered':
            raise ValueError(
                'map_detector: clustered mode is not supported for MG detectors.'
            )
        if op_mode == 'normal':
            return MGMapper.map(readouts, config)
        raise ValueError(f'map_detector: unsupported operationMode "{op_mode}" for MG.')

    if det_type == 'He3':
        if op_mode != 'normal':
            raise ValueError(
                f'map_detector: He3 detectors only support normal mode '
                f'(got "{op_mode}").'
            ) 
        return He3Mapper.map(readouts, config)

    raise ValueError(
        f'map_detector: unsupported detectorType "{det_type}". '
        f'Call the appropriate mapper class directly for non-standard types.'
    )


if __name__ == '__main__':
    # =============================================================================
    # STANDALONE COMPONENT TEST HARNESS
    # =============================================================================
    import json

    class MockReadoutsNormal:
        def __init__(self):
            dtype = [
                ('timeStamp', 'int64'), ('pulseT', 'int64'), ('prevPT', 'int64'),
                ('instrID', 'int64'), ('ring', 'int64'), ('fen', 'int64'),
                ('hybrid', 'int64'), ('asic', 'int64'), ('channel', 'int64'),
                ('adc', 'int64'),
            ]
            # 4 events:
            #   0: cassette 100, wire asic (1), ch 20  → local wire index 4
            #   1: cassette 101, strip asic (0), ch 10 → local strip index 53
            #   2: cassette 102, wire asic (1), ch 16  → local wire index 0
            #   3: ring 5 — no match in topology → unmapped, will be removed
            self.matrix = np.array([
                (1000, 100, 50, 1, 0, 0, 0, 1, 20, 250),
                (2000, 100, 50, 1, 0, 0, 1, 0, 10, 300),
                (3000, 100, 50, 1, 1, 0, 0, 1, 16, 180),
                (4000, 100, 50, 1, 5, 9, 9, 1, 30, 999),
            ], dtype=dtype)
            self.fill_count = 4
            self.durations  = np.array([100], dtype='int64')

    # Minimal colors shim so the harness runs without the full newLib install
    try:
        from newLib.colors import WARN, ERR, INFO, OK, RESET
    except ImportError:
        WARN = ERR = INFO = OK = '\033[0m'
        RESET = '\033[0m'

    print(f"{INFO}--- Starting Standalone Mapping Engine Verification Harness ---{RESET}")

    mock_config = {
        "detectorType": "MB",
        "operationMode": "normal",
        "wires": 32,
        "strips": 64,
        "channelMapping": [{"wireASIC": 1, "stripASIC": 0}],
        "topology": [
            {"ID": 100, "ring": 0, "fen": 0, "hybrid": 0},
            {"ID": 101, "ring": 0, "fen": 0, "hybrid": 1},
            {"ID": 102, "ring": 1, "fen": 0, "hybrid": 0},
        ],
        "monitor": [
            {"ID": 99, "hardwareType": "generic", "connectionType": "ring",
             "ring": 11, "channel": 0}
        ],
    }

    readouts = MockReadoutsNormal()

    print(f"{INFO}Piping mock readouts through vectorized mapping dispatcher...{RESET}\n")
    try:
        hits_out = map_detector(readouts, mock_config)

        print("-------------------------------------------------------------")
        print(f"{OK}Mapping successful! Output matrix ({hits_out.fill_count} rows):{RESET}")
        for idx, row in enumerate(hits_out.matrix):
            print(
                f"  Hit {idx} → ID: {row['ID']}, "
                f"Plane: {row['plane']}, "
                f"Index: {row['index']}, "
                f"ADC: {row['adc']}"
            )
        print("-------------------------------------------------------------")

        if hits_out.fill_count == 3:
            print(f"{OK}Success: unmapped row correctly removed. "
                  f"len(matrix) == fill_count == 3.{RESET}")
        else:
            print(f"{WARN}Expected 3 valid rows, found {hits_out.fill_count}{RESET}")

    except Exception as e:
        import traceback
        print(f"{ERR}Execution failure: {e}{RESET}")
        traceback.print_exc()
        sys.exit(1)
