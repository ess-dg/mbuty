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

from lib.colors import WARN, ERR, INFO, OK, RESET
from lib.container_hits import (
    hitsVMMnormal,
    hitsVMMclustered,
    hitsR5560,
)

from lib.container_events import (
    eventsBM,
    eventsIBM,
    eventsSKADI,
)


# =============================================================================
# MG hardware iteration constant
# =============================================================================
# Selects which physical adapter PCB wiring scheme is in use for Multi-Grid.
# 0 = new penthouse PCB + new ebox PCB       (correct production configuration)
# 1 = old penthouse PCB + new interface PCB  (test vessel only, transitional)
# 2 = new penthouse PCB + new interface PCB  (test vessel only, transitional)
# Modes 1 and 2 will be removed once all hardware is on the production config.
MG_SWAP_IT = 3


# =============================================================================
# Module-level helpers — private, not part of public API
# =============================================================================

# def _derive_adapter_type(wire_asic: int) -> str:
#     """
#     MB adapter type is implicit in which ASIC carries the wires.
#     wireASIC == 1  →  'reverse'  (e.g. AMOR26)
#     wireASIC == 0  →  'straight'
#     """
#     return 'reverse' if wire_asic == 1 else 'straight'


def _report_unmapped_units(
    assigned_ids: np.ndarray,
    config_ids: np.ndarray,
    unit_label: str = 'unit',
) -> None:
    """Warn about topology entries that produced no mapped hits."""
    found_ids = np.unique(assigned_ids[assigned_ids != -1])
    missing   = np.setdiff1d(config_ids, found_ids)
    if len(missing) > 0:
        id_list_missing = ' '.join(str(x) for x in missing)
        msg = f'\t {WARN}WARNING: {unit_label} IDs: {id_list_missing} not found in data file. Mapping skipped for those.'
        
        # Only append the second line if we actually found some valid IDs
        if len(found_ids) > 0:
            id_list_found = ' '.join(str(x) for x in found_ids)
            msg += f'\n\t These readouts only contains IDs: {id_list_found}'
        else:
            msg += f'\n\t These {len(assigned_ids)} readouts do not match any ID in config.'
             
        print(f'{msg}{RESET}')


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
    
    @staticmethod
    def _map_channels(src, valid_mask):
        """Channel coordinate transformation."""
  
        n = len(src)
        asic, channel = src['asic'], src['channel']
        is_wire  = valid_mask & (asic == 1) & (channel >= 16) & (channel <= 47)
        is_strip = valid_mask & (asic == 0) & (channel >= 0) & (channel <= 63)

        local_index = np.full(n, -1, dtype='int64')
        plane = np.full(n, -1, dtype='int64')

        local_index[is_wire]  = channel[is_wire] - 16
        local_index[is_strip] = 63 - channel[is_strip]

        #     local_index[is_wire] = 31 - (channel[is_wire] - 16)
        #     local_index[is_strip] = channel[is_strip]
        
        plane[is_wire], plane[is_strip] = 0, 1
        return plane, local_index

    @staticmethod
    def _apply_global_offset(local_index, plane, mapping_idx, valid_mask, num_wires):
        """Wire plane global offset."""
        
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        
        # the cassette ID drives the position in the space, 0 is the bottom cassette or the most left 
        cassette_rank = np.where(valid_mask, mapping_idx, -1)
        wire_offset  = cassette_rank * num_wires
        global_index = local_index.copy()
        is_wire = valid_mask & (plane == 0)
        global_index[is_wire] = local_index[is_wire] + wire_offset[is_wire]
        return global_index

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMnormal:
        topology  = config['topology']
        num_wires = int(config['wires'])
 
        topo = DetectorMapper._build_topology_arrays(topology, ['ID', 'ring', 'fen', 'hybrid'])
        n    = readouts.fill_count
        src  = readouts.matrix[:n]

        # Stage 1: Topology ID lookup
        assigned_ids, topo_idx, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='hybrid'
        )

        # Stage 2: Channel mapping (coordinate transform)
        plane, local_index = MBMapper._map_channels(src, valid_mask)

        # assigned_ids = np.where(local_index==-1,-1,assigned_ids)

        # Stage 3: Global offset
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        global_index = MBMapper._apply_global_offset(local_index, plane, assigned_ids, valid_mask, num_wires)

        # Stage 4: Absorption
        h = hitsVMMnormal(size=n)
        h.durations = readouts.durations.copy()
        h.instrumentIDs = readouts.instrumentIDs.copy()
        h.absorb(
            computed_fields={'ID': assigned_ids, 'plane': plane, 'index': global_index, 'adc': src['adc'].astype('int64')},
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'cassette')
        return h
# =============================================================================
# MBClustMapper — Multi-Blade VMM clustered mode
# =============================================================================
class MBClustMapper(DetectorMapper):

    @staticmethod
    def _unpack_and_map_channels(src, valid_mask):
        """Unpack wire/strip from correct slots, apply coordinate formula."""

        wire_ch, wire_adc, wire_mult    = src['channel1'], src['adc1'], src['mult1']
        strip_ch, strip_adc, strip_mult = src['channel0'], src['adc0'], src['mult0']
        
        #     wire_ch, wire_adc, wire_mult = src['channel0'], src['adc0'], src['mult0']
        #     strip_ch, strip_adc, strip_mult = src['channel1'], src['adc1'], src['mult1']

        wire_in_range  = (wire_ch >= 16) & (wire_ch <= 47)
        strip_in_range = (strip_ch >= 0) & (strip_ch <= 63)

        local_wire  = np.where(valid_mask & wire_in_range, wire_ch - 16, -1)
        local_strip = np.where(valid_mask & strip_in_range, 63 - strip_ch, -1)

        #     local_wire = np.where(valid_mask & wire_in_range, 31 - (wire_ch - 16), -1)
        #     local_strip = np.where(valid_mask & strip_in_range, strip_ch, -1)

        return local_wire, local_strip, wire_adc, strip_adc, wire_mult, strip_mult

    @staticmethod
    def _apply_global_offset(local_wire, valid_mask, mapping_idx, num_wires):
        """Wire plane only."""
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        cassette_rank = np.where(valid_mask, mapping_idx, -1)
        wire_offset   = cassette_rank * num_wires
        return np.where(local_wire >= 0, local_wire + wire_offset, -1)

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMclustered:
        topology = config['topology']
        num_wires = int(config['wires'])

        topo = DetectorMapper._build_topology_arrays(topology, ['ID', 'ring', 'fen', 'hybrid'])
        n = readouts.fill_count
        src = readouts.matrix[:n]

        # Stage 1: Topology
        assigned_ids, topo_idx, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='hybrid'
        )
        
        # Stage 2: Channel mapping + unpacking
        local_w, local_s, adc0, adc1, mult0, mult1 = MBClustMapper._unpack_and_map_channels(
            src, valid_mask
        )

        # Stage 3: Global offset (wire plane only)
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        global_w = MBClustMapper._apply_global_offset(local_w, valid_mask, assigned_ids, num_wires)

        # Stage 4: Absorption
        h = hitsVMMclustered(size=n)
        h.durations = readouts.durations.copy()
        h.instrumentIDs = readouts.instrumentIDs.copy()
        h.absorb(
            computed_fields={
                'ID': assigned_ids, 'index0': global_w, 'index1': local_s,
                'adc0': adc0.astype('int64'), 'adc1': adc1.astype('int64'),
                'mult0': mult0.astype('int64'), 'mult1': mult1.astype('int64'),
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
        hybridGs = topo_arrays['hybridG']

        r = src['ring']    # (n,)
        f = src['fen']     # (n,)
        h = src['hybrid']  # (n,)

        # Broadcast: (n_readouts, n_topology)
        ring_match = r[:, None] == rings[None, :]    # (n, N)
        fen_match  = f[:, None] == fens[None, :]     # (n, N)
        hybW_match = h[:, None] == hybridWs[None, :] # (n, N)
        hybG_match = h[:, None] == hybridGs[None, :] # (n, N)

        col_match  = ring_match & fen_match & (hybW_match | hybG_match)  # (n, N)

        valid_mask   = col_match.any(axis=1)
        topo_idx     = np.where(valid_mask, col_match.argmax(axis=1), np.int64(-1))
        assigned_ids = np.where(valid_mask, ids[topo_idx], np.int64(-1))

        # Derive plane from which hybrid matched at the resolved column index.
        safe_idx = np.where(valid_mask, topo_idx, np.int64(0))

        is_wire  = valid_mask & (h == hybridWs[safe_idx])
        is_grid  = valid_mask & (h == hybridGs[safe_idx])

        plane = np.full(len(src), -1, dtype='int64')
        plane[is_wire]  = np.int64(0)
        plane[is_grid]  = np.int64(1)

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
        is_grid  = valid_mask & (plane == 1)

        if MG_SWAP_IT == 0:
            # -----------------------------------------------------------------
            # Production mapping: new penthouse PCB + new ebox PCB
            # -----------------------------------------------------------------

            # WIRES: index = 119 - (channel + 64 * asic)
            tempW = np.int64(119) - (channel[is_wire] + np.int64(64) * asic[is_wire])

            
            bad_w = ( (tempW >= np.int64(num_wires)) | (tempW < np.int64(0) ))
            if np.any(bad_w):
                print(f'Warning: found Wires above {num_wires - 1} in MG column — setting to -1')
            tempW[bad_w] = np.int64(-1)
            
            local_index[is_wire] = tempW
            
            # GRIDS: index = channel - 10 + 44 * asic
            tempS = channel[is_grid] - np.int64(10) + np.int64(44) * asic[is_grid]

            bad_s = ((tempS >= np.int64(num_grids)) | (tempS < np.int64(0)))
            if np.any(bad_s):
                print(f'Warning: found Grids above {num_grids - 1} in MG column — setting to -1')
            tempS[bad_s] = np.int64(-1)
            local_index[is_grid] = tempS

            
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

            ch_s   = channel[is_grid]
            asic_s = asic[is_grid]

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
            local_index[is_grid] = np.select(strip_conditions, strip_choices, default=-1)

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

            ch_s   = channel[is_grid]
            asic_s = asic[is_grid]

            strip_conditions = [
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 0),
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 1),
            ]
            strip_choices = [
                53 - ch_s,
                97 - ch_s,
            ]
            local_index[is_grid] = np.select(strip_conditions, strip_choices, default=-1)
            
        elif MG_SWAP_IT == 3:
            # -----------------------------------------------------------------
            # Transitional: new penthouse PCB + new interface PCB (test vessel)
            # Preserved verbatim from libMappingMG.mapDetector.mapp1cass
            # -----------------------------------------------------------------
            print(f'{WARN}----> WARNING: USING TEMPORARY INTERFACE PCB MAPPING (swapIT=3)!!!{RESET}')

            # ########################################## 
            # WIRES
            # ##########
            ch_w   = channel[is_wire]
            asic_w = asic[is_wire]

            wire_conditions = [
                (ch_w >= 16) & (ch_w <= 55) & (asic_w == 1),  # selection1
                (ch_w >= 40) & (ch_w <= 63) & (asic_w == 0),  # selection2
                (ch_w >= 0)  & (ch_w <= 16) & (asic_w == 1),  # selection3
                (ch_w >= 0)  & (ch_w <= 39) & (asic_w == 0)   # selection4
            ]
            
            wire_choices = [
                ch_w - 16,  # Map for selection1
                ch_w,       # Map for selection2
                ch_w + 64,  # Map for selection3
                ch_w + 80   # Map for selection4
            ]
            
            local_index[is_wire] = np.select(wire_conditions, wire_choices, default=-1)

            # ########################################## 
            # GRIDS / STRIPS
            # ##########
            ch_s   = channel[is_grid]
            asic_s = asic[is_grid]

            strip_conditions = [
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 0),  # selection1
                (ch_s >= 10) & (ch_s <= 53) & (asic_s == 1)   # selection2
            ]
            
            strip_choices = [
                53 - ch_s,   # Map for selection1
                97 - ch_s    # Map for selection2
            ]
            
            local_index[is_grid] = np.select(strip_conditions, strip_choices, default=-1)


        else:
            raise ValueError(
                f'MGMapper: MG_SWAP_IT={MG_SWAP_IT} is not a valid value. '
                f'Must be 0, 1, or 2.'
            )

        return local_index

    @staticmethod
    def _apply_global_offset(local_index, plane, mapping_idx, valid_mask, num_wires):
        """Wire plane offset."""
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        is_wire = valid_mask & (plane == 0)
        unit_rank = np.where(valid_mask, mapping_idx, -1)
        wire_offset  = unit_rank * num_wires
        global_index = local_index.copy()
        global_index[is_wire] = local_index[is_wire] + wire_offset[is_wire]
        
        return global_index

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMnormal:
        topology = config['topology']
        num_wires = int(config['wires'])
        num_grids = int(config['grids'])
        

        topo = DetectorMapper._build_topology_arrays(
            topology, ['ID', 'ring', 'fen', 'hybridW', 'hybridG']
        )
        n = readouts.fill_count
        src = readouts.matrix[:n]

        # Stage 1: Topology (MG override returns plane too)
        assigned_ids, topo_idx, valid_mask, plane = MGMapper._assign_ids_vectorized(src, topo)

        # Stage 2: Channel mapping
        local_index = MGMapper._map_channels(src, valid_mask, plane, num_wires, num_grids)

        assigned_ids = np.where(local_index==-1,-1,assigned_ids)
        
        # Stage 3: Global offset
        # Pass mapping_idx as topo_idx if you want to map as the units appear in the config file, 
        # or pass as assigned_IDs if you want to map as ID number 
        global_index = MGMapper._apply_global_offset(local_index, plane, assigned_ids, valid_mask, num_wires)

        # Stage 4: Absorption
        h = hitsVMMnormal(size=n)
        h.durations = readouts.durations.copy()
        h.instrumentIDs = readouts.instrumentIDs.copy()
        
        h.absorb(
            computed_fields={
                'ID': assigned_ids, 'plane': plane, 'index': global_index,
                'adc': src['adc'].astype('int64'),
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
        topo = DetectorMapper._build_topology_arrays(topology, ['ID', 'ring', 'fen', 'tube'])
        n = readouts.fill_count
        src = readouts.matrix[:n]

        # Stage 1: Topology only
        assigned_ids, _, valid_mask = DetectorMapper._assign_ids_vectorized(
            src, topo, src_third_field='tube'
        )

        # # No Stage 2 or 3 for He3 — index IS the tube number
        # index = np.where(valid_mask, src['tube'].astype('int64'), np.int64(-1))

        # Stage 4: Absorption
        h = hitsR5560(size=n)
        h.durations = readouts.durations.copy()
        h.instrumentIDs = readouts.instrumentIDs.copy()
        h.absorb(
            computed_fields={
                'ID': assigned_ids, 
                'counter1': src['counter1'].astype('int64'),
                'ampA': src['ampA'].astype('int64'),
                'ampB': src['ampB'].astype('int64'),
                'counter2': src['counter2'].astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'tube')
        return h
    
# =============================================================================
# SKADIMapper — SKADI pixel detector
# =============================================================================
# Standalone — does NOT inherit DetectorMapper. Topology matching here is a
# single-key match on IP (no ring/fen), and there's no clustering stage —
# readouts map straight into events. That's different enough that inheriting
# would mean overriding away most the base class 
# =============================================================================

class SKADIMapper:
    """
    Maps SKADI pixel-tile readouts directly to physical coordinates.
    No clustering stage: readouts -> eventsSKADI in one pass.

    Topology lookup is single-key on IP (not ring+fen+third like the
    VMM/He3 mappers). Each topology entry's ID encodes both the bank
    number and the tile's position within that bank's grid:

        bank     = ID // 1000
        local_id = ID % 1000
        x_tile   = local_id % tilesPerRow
        y_tile   = local_id // tilesPerRow

    Each tile is a pix x pix pixel grid. The readout's raw (row, column)
    address within the tile is rotated per the topology entry's `rotation`
    (0/1/2/3 = 0/90/180/270 degrees clockwise, driven by cabling) before
    being placed into the tile's local frame. Indices are 0..pix-1, so
    the "flip" terms use pix - 1 - x, not pix - x:

        rotation 0:  adj_row = row,           adj_col = col
        rotation 1:  adj_row = col,           adj_col = pix - 1 - row
        rotation 2:  adj_row = pix - 1 - row, adj_col = pix - 1 - col
        rotation 3:  adj_row = pix - 1 - col, adj_col = row

    Final absolute pixel coordinates:

        coordinate0 = x_tile * pix + adj_col
        coordinate1 = y_tile * pix + adj_row
    """

    @staticmethod
    def _assign_ids_by_ip(src: np.ndarray, topo_arrays: dict) -> tuple:
        """
        Map every readout row to a topology unit by matching IP alone.

        Returns
        -------
        assigned_ids : int64 array — topology ID, -1 where unmatched
        rotations    : int64 array — topology rotation, -1 where unmatched
        valid_mask   : bool  array
        """
        ids       = topo_arrays['ID']
        ips       = topo_arrays['IP']
        rotations = topo_arrays['rotation']

        src_ip = src['IP']

        # Broadcast: (n_readouts, n_topology)
        match = (src_ip[:, None] == ips[None, :])

        valid_mask   = match.any(axis=1)
        topo_idx     = np.where(valid_mask, match.argmax(axis=1), np.int64(-1))
        assigned_ids = np.where(valid_mask, ids[topo_idx], np.int64(-1))
        assigned_rot = np.where(valid_mask, rotations[topo_idx], np.int64(-1))

        return (
            assigned_ids.astype('int64'),
            assigned_rot.astype('int64'),
            valid_mask,
        )

    @staticmethod
    def _decode_bank_and_tile(
        assigned_ids: np.ndarray,
        valid_mask: np.ndarray,
        tiles_per_row: int,
    ) -> tuple:
        """
        Decode bank / tile grid position out of the topology ID.

        Unmatched rows are forced to -1 explicitly rather than run through
        // and % directly on -1: -1 // 1000 == -1 is fine, but
        -1 % 1000 == 999 would silently masquerade as a valid local_id.
        """
        n = len(assigned_ids)

        bank     = np.full(n, -1, dtype='int64')
        local_id = np.full(n, -1, dtype='int64')
        x_tile   = np.full(n, -1, dtype='int64')
        y_tile   = np.full(n, -1, dtype='int64')

        bank[valid_mask]     = assigned_ids[valid_mask] // 1000
        local_id[valid_mask] = assigned_ids[valid_mask] % 1000

        x_tile[valid_mask] = local_id[valid_mask] % tiles_per_row
        y_tile[valid_mask] = (tiles_per_row - 1) - (local_id[valid_mask] // tiles_per_row)

        return bank, x_tile, y_tile

    @staticmethod
    def _apply_rotation(
        row: np.ndarray,
        col: np.ndarray,
        rotation: np.ndarray,
        pix: int,
        valid_mask: np.ndarray,
    ) -> tuple:
        """
        Rotate each readout's raw (row, col) tile-local address per that
        unit's `rotation` (0/1/2/3 -> 0/90/180/270 clockwise). Uses
        pix - 1 - x for the flipped terms since row/col are 0-indexed
        (0..pix-1); pix - x alone would be off by one.
        """
        n = len(row)
        adj_row = np.full(n, -1, dtype='int64')
        adj_col = np.full(n, -1, dtype='int64')

        r0 = valid_mask & (rotation == 0)
        r1 = valid_mask & (rotation == 1)
        r2 = valid_mask & (rotation == 2)
        r3 = valid_mask & (rotation == 3)

        adj_row[r0], adj_col[r0] = row[r0],           col[r0]
        adj_row[r1], adj_col[r1] = col[r1],           pix - 1 - row[r1]
        adj_row[r2], adj_col[r2] = pix - 1 - row[r2], pix - 1 - col[r2]
        adj_row[r3], adj_col[r3] = pix - 1 - col[r3], row[r3]

        return adj_row, adj_col

    @staticmethod
    def map(readouts, config: dict) -> eventsSKADI:
        topology      = config['topology']
        tiles_per_row = int(config['tilesPerRow'])
        pix           = int(config['pix'])

        topo = DetectorMapper._build_topology_arrays(topology, ['ID', 'IP', 'rotation'])
        n    = readouts.fill_count
        src  = readouts.matrix[:n]

        # Stage 1: Topology lookup (IP -> ID + rotation)
        assigned_ids, rotations, valid_mask = SKADIMapper._assign_ids_by_ip(src, topo)

        # Stage 2: Decode bank / tile grid position from ID
        bank, x_tile, y_tile = SKADIMapper._decode_bank_and_tile(
            assigned_ids, valid_mask, tiles_per_row
        )

        # Stage 3: Rotate raw pixel (row, col) into tile-local frame
        adj_row, adj_col = SKADIMapper._apply_rotation(
            src['row'], src['column'], rotations, pix, valid_mask
        )

        # Stage 4: Absolute pixel coordinates
        coordinate0 = np.where(valid_mask, x_tile * pix + adj_col, -1).astype('float64')
        coordinate1 = np.where(valid_mask, y_tile * pix + adj_row, -1).astype('float64')

        # Stage 5: Absorption — timeStamp/pulseT/prevPT come from timing_src=src,
        # same as every other mapper; instrumentIDs/durations copied the same way too.
        e = eventsSKADI(size=n)
        e.durations = readouts.durations.copy()
        e.instrumentIDs = readouts.instrumentIDs.copy()
        e.absorb(
            computed_fields={
                'ID':          assigned_ids,
                'bank':        bank,
                'channel':     src['channel'].astype('int64'),
                'coordinate0': coordinate0,
                'coordinate1': coordinate1,
                'pulseHeight0': src['adc'].astype('int64'),
            },
            timing_src=src,
        )

        _report_unmapped_units(assigned_ids, topo['ID'], 'tile')
        return e

# ---------------------------------------------------------------------------
# Base Monitor Mother Class using Standard Absorb Lifecycle
# ---------------------------------------------------------------------------

class BaseMonitorMapper:
    """
    Abstract mother class for Beam Monitor mappers.
    Validates channels and utilizes standard hits.absorb() contract.
    This maps readoutsa directly into events 
    """
    @staticmethod
    def _prepare_base_fields(readouts, config: dict) -> tuple:
        n   = readouts.fill_count
        src = readouts.matrix[:n]
        
        mon_cfg     = config['monitor'][0]
        mon_id      = int(mon_cfg['ID'])
        mon_ring    = int(mon_cfg['ring'])
        mon_channel = int(mon_cfg['channel'])

        # Create target channel mask extraction
        target_mask = (src['channel'] == np.int64(mon_channel)) & (src['ring'] == np.int64(mon_ring))
        count = np.sum(target_mask)

        # Vectorized Warning Checks
        if n > 0:
            unique_pairs = np.unique(np.stack((src['channel'], src['ring']), axis=1), axis=0)
            num_unique = len(unique_pairs)
            
            # CASE 1: Multiple monitor channels/rings found
            if num_unique > 1:
                # Format pairs nicely for the print statement, e.g., [(ch1, r1), (ch2, r2)]
                pairs_list = [tuple(pair) for pair in unique_pairs]
                
                formatted_pairs = [(int(ch), int(rg)) for ch, rg in pairs_list]
                
                print(
                    f"\t {WARN}WARNING: Found {num_unique} monitors in data. "
                    f"MBUTY supports only one Monitor. Mapping channel {mon_channel} and ring {mon_ring} per config, "
                    f"but data contains pairs (channel, ring): {formatted_pairs}{RESET}"
)
            
            # CASE 2: Mismatch -> Data exists, but nothing matches the configured channel/ring
            if count == 0 and num_unique > 0:
                # Grab the first actual pair present in the data to show the user
                wrong_ch, wrong_ring = unique_pairs[0]
                
                print(f"\t {WARN}WARNING: mismatch → Candidates found, but it is NOT the selected one in config file ring {mon_ring} and channel {mon_channel}. "
                      f"Data contains Channel {wrong_ch} and Ring {wrong_ring}.{RESET}")
            
        else:
            print(f'\t {WARN}WARNING: No MONITOR data found in data file or not matching you config.{RESET}')
            
            
        # Assign real ID to configured rows; unconfigured rows stay at -1 to be cleanly dropped
        assigned_ids = np.where(target_mask, np.int64(mon_id), np.int64(-1))

        computed_base = {
            'ID':       assigned_ids,
            'type':     src['type'],        
            'pulseHeight0':      src['adc'],
        }
        
        return n, src, computed_base
    
    
    def _copy_duration_and_IDs(readouts, ev) -> tuple:
        
        ev.durations     = readouts.durations.copy()
        ev.instrumentIDs = readouts.instrumentIDs.copy()
         
# ---------------------------------------------------------------------------
# Derived Concrete Monitor Mappers
# ---------------------------------------------------------------------------

class BMMapper(BaseMonitorMapper):
    """Maps isolated readoutsBM into hitsBM using the standard absorb lifecycle."""
    @staticmethod
    def map(readouts, config: dict) -> eventsBM:
        
        print(f'{INFO}Mapping Beam Monitor readouts into events ... {RESET}')
        
        n, src, computed = BaseMonitorMapper._prepare_base_fields(readouts, config)

        computed['coordinate0'] = src['posX']
        computed['coordinate1'] = src['posY']

        ev = eventsBM(size=n)
        ev.absorb(computed, src)
        BaseMonitorMapper._copy_duration_and_IDs(readouts, ev)
        
        return ev


class IBMMonitorMapper(BaseMonitorMapper):
    """Maps isolated readoutsIBM into hitsIBM using the standard absorb lifecycle."""
    @staticmethod
    def map(readouts, config: dict) -> eventsIBM:
        
        print(f'{INFO}Mapping I-Beam Monitor readouts into events ... {RESET}')
        
        n, src, computed = BaseMonitorMapper._prepare_base_fields(readouts, config)
        
        # computed['debug']  = src['debug']
        # computed['mcaSum'] = src['mcaSum']

        ev = eventsIBM(size=n)
        ev.absorb(computed, src)
        BaseMonitorMapper._copy_duration_and_IDs(readouts, ev)
  
        
        return ev


# =============================================================================
# map_detector — top-level dispatcher - only used when testing mapping module 
# independently. Can theoretically be deleted after fully tested module 
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
    
    print(f"{INFO}Mapping detector {det_type} (units mapped according to IDs){RESET}")

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
    
    # ADD BM mapping and if it i found or mismatch 

    raise ValueError(
        f'map_detector: unsupported detectorType "{det_type}". '
        f'Call the appropriate mapper class directly for non-standard types.'
    )


###############################################################################
###############################################################################
###############################################################################
###############################################################################


if __name__ == '__main__':
    # =============================================================================
    # STANDALONE COMPONENT TEST HARNESS
    # =============================================================================
    import json

    class MockReadoutsNormal:
        def __init__(self):
            dtype = [
                ('timeStamp', 'int64'), ('pulseT', 'int64'), ('prevPT', 'int64'),
                ('ring', 'int64'), ('fen', 'int64'),
                ('hybrid', 'int64'), ('asic', 'int64'), ('channel', 'int64'),
                ('adc', 'int64'),
            ]
            # 4 events:
            #   0: cassette 100, wire asic (1), ch 20  → local wire index 4
            #   1: cassette 101, strip asic (0), ch 10 → local strip index 53
            #   2: cassette 102, wire asic (1), ch 16  → local wire index 0
            #   3: ring 5 — no match in topology → unmapped, will be removed
            self.matrix = np.array([
                (1000, 100, 50, 0, 0, 0, 1, 20, 250),
                (2000, 100, 50, 0, 0, 1, 0, 10, 300),
                (3000, 100, 50, 1, 0, 0, 1, 16, 180),
                (4000, 100, 50, 5, 9, 9, 1, 30, 999),
            ], dtype=dtype)
            self.fill_count = 4
            self.durations  = np.array([100], dtype='int64')

    # Minimal colors shim so the harness runs without the full lib install
    try:
        from lib.colors import WARN, ERR, INFO, OK, RESET
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
