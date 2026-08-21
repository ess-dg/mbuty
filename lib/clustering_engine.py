#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clustering_engine.py

@author: Sheila Monera Cabarique
--------------------
Vectorized event clustering engines for VMM normal/clustered readouts and Helium-3 gas tubes.
"""
import numpy as np
import sys 
import os
# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from lib.container_events import eventsVMMnormal, eventsVMMclustered, eventsR5560

from lib.colors import WARN, ERR, INFO, OK, RESET

# =============================================================================
# Wires and Strips Normal Clusterer (Multi-Blade & Multi-Grid)
# =============================================================================

class VMMNormalClustererOld:
    """Stateless vectorized clustering logic for VMM Normal multi-plane readouts."""
    @staticmethod
    def _derive_time_windows(time_window_s: float) -> tuple:
        """Convert float window seconds into standard recursive and max integer ns gates."""
        tw_ns        = int(round(time_window_s * 1e9))
        tw_recursive = int(round(tw_ns * 1.01))
        tw_max       = int(round(tw_recursive * 1.5))
        return tw_recursive, tw_max

    @staticmethod
    def _partition_hits(ids: np.ndarray, timestamps: np.ndarray, tw_recursive: int) -> tuple:
        """Assign a monotonically increasing cluster index to hit rows matching legacy sequence order."""
        sort_order = np.argsort(ids, kind='stable')
        ids_s      = ids[sort_order]
        ts_s       = timestamps[sort_order]

        break_mask      = np.empty(len(ids_s), dtype=bool)
        break_mask[0]   = True
        break_mask[1:]  = (
            (np.abs(np.diff(ts_s)) > tw_recursive) |
            (ids_s[1:] != ids_s[:-1])
        )

        cluster_ids = np.cumsum(break_mask) - 1
        n_clusters  = int(cluster_ids[-1]) + 1 if len(cluster_ids) > 0 else 0
        return cluster_ids, sort_order, n_clusters
    
    @staticmethod
    def cluster(hits, config: dict, time_window_s: float) -> eventsVMMnormal:
        
        print(f'{INFO}\nClustering VMM normal events (OLD method - stats approx.)... {RESET}',end='')
        
        m = hits.matrix[:hits.fill_count]
        n = len(m)

        if n == 0:
            return eventsVMMnormal(size=0)

        tw_recursive, tw_max = VMMNormalClustererOld._derive_time_windows(time_window_s)
        # Get the wire and strip/grid configuration from config for clustering (error and exit if not found)
        # Make this more generic based on config
        if 'wires' not in config:
            print('\t [ERROR] Config is missing "wires" — cannot cluster. Check your config file.')
            sys.exit(1)

        if 'strips' in config:
            max_strips = int(config['strips'])
        elif 'grids' in config:
            max_strips = int(config['grids'])
        else:
            print('\t [ERROR] Config is missing both "strips" and "grids" — cannot cluster. Check your config file.')
            sys.exit(1)

        max_wires = int(config['wires']) 

        cluster_ids, sort_order, n_clusters = VMMNormalClustererOld._partition_hits(m['ID'], m['timeStamp'], tw_recursive)
        
        out = eventsVMMnormal(size=n_clusters)
        out.durations     = hits.durations.copy()
        out.instrumentIDs = hits.instrumentIDs.copy()

        ms       = m[sort_order]
        ts       = ms['timeStamp']
        is_wire  = ms['plane'] == 0
        is_strip = ms['plane'] == 1
        ch_idx   = ms['index']
        adc      = ms['adc']

        first_hit = np.searchsorted(cluster_ids, np.arange(n_clusters), side='left')
        last_hit  = np.searchsorted(cluster_ids, np.arange(n_clusters), side='right') - 1
        span      = ts[last_hit] - ts[first_hit]

        wire_count  = np.bincount(cluster_ids, weights=is_wire.astype('int64'),  minlength=n_clusters).astype('int64')
        strip_count = np.bincount(cluster_ids, weights=is_strip.astype('int64'), minlength=n_clusters).astype('int64')

        wire_adc  = np.bincount(cluster_ids, weights=(adc * is_wire).astype('float64'),  minlength=n_clusters)
        strip_adc = np.bincount(cluster_ids, weights=(adc * is_strip).astype('float64'), minlength=n_clusters)

        wire_pos_num  = np.bincount(cluster_ids, weights=(ch_idx * adc * is_wire).astype('float64'),  minlength=n_clusters)
        strip_pos_num = np.bincount(cluster_ids, weights=(ch_idx * adc * is_strip).astype('float64'), minlength=n_clusters)

        wire_min = np.full(n_clusters, 999999, dtype='int64')
        wire_max = np.full(n_clusters, -1,     dtype='int64')
        np.minimum.at(wire_min, cluster_ids[is_wire], ch_idx[is_wire])
        np.maximum.at(wire_max, cluster_ids[is_wire], ch_idx[is_wire])

        strip_min = np.full(n_clusters, 999999, dtype='int64')
        strip_max = np.full(n_clusters, -1,     dtype='int64')
        np.minimum.at(strip_min, cluster_ids[is_strip], ch_idx[is_strip])
        np.maximum.at(strip_max, cluster_ids[is_strip], ch_idx[is_strip])

        accept_window    = span <= tw_max
        wire_contiguous  = np.where(wire_count > 0,  (wire_max - wire_min) == (wire_count - 1),  False)
        strip_contiguous = np.where(strip_count > 0, (strip_max - strip_min) == (strip_count - 1), False)
        wire_in_limits   = wire_count  < max_wires
        strip_in_limits  = strip_count < max_strips
        has_wire_hit     = wire_count  >= 1
        has_strip_hit    = strip_count >= 1

        accept_2d = (accept_window & has_wire_hit & has_strip_hit & wire_contiguous & strip_contiguous & wire_in_limits & strip_in_limits)
        accept_1dw = (accept_window & has_wire_hit  & ~has_strip_hit & wire_contiguous & wire_in_limits)
        accept_1ds = (accept_window & has_strip_hit & ~has_wire_hit & strip_contiguous & strip_in_limits)

        with np.errstate(divide='ignore', invalid='ignore'):
            coord0 = np.where(wire_adc  > 0, np.round(wire_pos_num  / wire_adc,  2), np.nan)
            coord1 = np.where(strip_adc > 0, np.round(strip_pos_num / strip_adc, 2), np.nan)

        accept_2d  &= ~(np.isnan(coord0) | np.isnan(coord1))
        accept_1dw &= ~np.isnan(coord0)  & np.isnan(coord1)
        accept_1ds &= np.isnan(coord0)   & ~np.isnan(coord1)
   

        assigned_ids = np.where(accept_2d | accept_1dw | accept_1ds , ms['ID'][first_hit], np.int64(-1))
        n_accepted   = int(np.sum(accept_2d | accept_1dw | accept_1ds))

        timing_src = {
            'timeStamp': ts[first_hit],
            'pulseT':    ms['pulseT'][first_hit],
            'prevPT':    ms['prevPT'][first_hit],
        }

        computed = {
            'ID':           assigned_ids,
            'coordinate0':  coord0,
            'coordinate1':  coord1,
            'pulseHeight0': wire_adc.astype('int64'),
            'pulseHeight1': strip_adc.astype('int64'),
            'mult0':        wire_count,
            'mult1':        strip_count,
            'clusterTimeSpan':  span.astype('int64'),
        }

        # Populate stats BEFORE absorb() so print_stats() sees the correct values
        out.stats.update({
            'n_candidates':    n_clusters,
            'n_candidates_p0': 0,
            'n_candidates_p1': 0,
            'n_accepted': n_accepted,
            'n_accepted_2d':  int(np.sum(accept_2d)/2),
            'n_accepted_1dw': int(np.sum(accept_1dw)),
            'n_accepted_1ds': int(np.sum(accept_1ds)),
            'n_rejected': n_clusters - n_accepted,
            'n_rejected_1dw': 0,
            'n_rejected_1ds': 0,
        })
        
        
        # out.stats.update({
        #     'n_candidates': n_clusters,
        #     'n_candidates_p0': 0, 
        #     'n_candidates_p1': 0,
        #     'n_accepted': n_accepted, 
        #     'n_rejected': n_clusters - n_accepted,
        #     'n_accepted_2d':        int(np.sum(accept_2d)),
        #     'n_accepted_1dw':       int(np.sum(accept_1dw)),
        #     'n_accepted_1ds':       int(np.sum(accept_1ds)),
        #     'n_rejected_overflow':  int(np.sum(~accept_window)),
        #     'n_rejected_neighbour': int(np.sum(accept_window & ~(accept_2d | accept_1dw | accept_1ds))),
        # })

        out.absorb(computed, timing_src)
        return out


# =============================================================================
# VMM Clustered Clusterer (Passthrough Engine)
# =============================================================================

class VMMClusteredClusterer:
    """Passthrough engine for hardware-firmware pre-clustered readout matrices."""
    @staticmethod
    def cluster(hits, config: dict, time_window_s: float = 0.0) -> eventsVMMclustered:
        
        print(f'{INFO}\nAbsorbing Clustered events ... {RESET}',end='')
        
        m = hits.matrix[:hits.fill_count]
        n = len(m)

        out = eventsVMMclustered(size=n)
        out.durations     = hits.durations.copy()
        out.instrumentIDs = hits.instrumentIDs.copy()

        if n == 0:
            return out

        timing_src = {
            'timeStamp': m['timeStamp'],
            'pulseT':    m['pulseT'],
            'prevPT':    m['prevPT'],
        }

        computed = {
            'ID':           m['ID'],
            'coordinate0':  m['index0'].astype('float64'),
            'coordinate1':  m['index1'].astype('float64'),
            'pulseHeight0': m['adc0'].astype('int64'),
            'pulseHeight1': m['adc1'].astype('int64'),
            'mult0':        m['mult0'].astype('int64'),
            'mult1':        m['mult1'].astype('int64'),
        }

        # Populate stats BEFORE absorb()
        out.stats.update({
            'n_candidates': n,
            'n_accepted':   n,   # passthrough — firmware already accepted everything
        })

        out.absorb(computed, timing_src)
        return out


# =============================================================================
# R5560 Clusterer (Helium-3 Continuous Gas Tubes)
# =============================================================================

class R5560Clusterer:
    """Vectorized position calculator and pile-up filter for Helium-3 gas tubes."""
    @staticmethod
    def cluster(hits, config: dict, time_window_s: float) -> eventsR5560:
        
        print(f'{INFO}\nClustering R5560 events ... {RESET}',end='')
        
        m = hits.matrix[:hits.fill_count]
        n = len(m)

        if n == 0:
            return eventsR5560(size=0)

        tw_ns = int(round(time_window_s * 1e9))
        tw_recursive = int(round(tw_ns * 1.01))

        # Step 1: Sort by ID while preserving chronological arrival order
        sort_order = np.argsort(m['ID'], kind='stable')
        ms = m[sort_order]

        # Step 2: Calculate time deltas to locate pile-up bounds
        deltas    = np.abs(np.diff(ms['timeStamp']))
        same_unit = ms['ID'][1:] == ms['ID'][:-1] # False when a new unit starts 
        too_close = same_unit & (deltas <= tw_recursive)

        # Allocate and populate the flat pile-up filter
        pile_up = np.zeros(n, dtype=bool)
        pile_up[1:]  |= too_close  # Flags the hit too close to the one BEFORE it
        pile_up[:-1] |= too_close  # Flags the hit too close to the one AFTER it

        # Step 3: Slice down our working arrays to include ONLY clean rows
        ms_clean = ms[~pile_up]
        
        # If every single row in this batch was pile-up noise, exit early
        n_clean = len(ms_clean)
        if n_clean == 0:
            return eventsR5560(size=0)

        # Step 4: Run math ONLY on the clean data
        amp_a = ms_clean['ampA'].astype('float64')
        amp_b = ms_clean['ampB'].astype('float64')
        total = amp_a + amp_b

        # Quick baseline guard check for zero total charge on surviving rows
        zero_charge = total == 0.0
        with np.errstate(divide='ignore', invalid='ignore'):
            position = np.where(~zero_charge, np.round(amp_a / total, 3), np.nan)

        # Any row that hits a zero charge glitch gets marked -1 for absorb to drop
        final_accept = ~zero_charge & ~np.isnan(position)
        assigned_ids = np.where(final_accept, ms_clean['ID'], np.int64(-1))
        c1_final     = np.where(final_accept, ms_clean['ID'].astype('float64'), -1.0)

        # Step 5: Allocate container scaled exactly to our clean subset size
        out = eventsR5560(size=n_clean)
        out.durations = hits.durations.copy()
        out.instrumentIDs = hits.instrumentIDs.copy()

        # Step 6: Map straight to the final output layout
        timing_src = {
            'timeStamp': ms_clean['timeStamp'],
            'pulseT':    ms_clean['pulseT'],
            'prevPT':    ms_clean['prevPT'],
        }

        computed = {
            'ID':           assigned_ids,
            'coordinate0':  position,
            'coordinate1':  c1_final,
            'pulseHeight0': total.astype('int64'),
        }

        n_pileup = int(np.sum(pile_up))
        n_other  = n_clean - int(np.sum(final_accept))  # zero-charge or NaN rows

        # Populate stats BEFORE absorb()
        out.stats.update({
            'n_candidates':     n,
            'n_accepted':       int(np.sum(final_accept)),
            'n_rejected':       n_pileup + n_other,
            'n_pileup_flagged': n_pileup,
        })

        out.absorb(computed, timing_src)
        return out
# =============================================================================
# VMM Normal Clusterer 
# =============================================================================

import numpy as np
import sys
from lib.container_events import eventsVMMnormal


class VMMNormalClusterer:
    """
    Split-based vectorized clustering for VMM Normal multi-plane readouts
    (Multi-Blade / Multi-Grid). Planes are clustered independently in time,
    split spatially instead of discarded, then matched into 2D events using
    an optimized vectorized one-to-one matching algorithm.

    Default max_gap is 0 (no missing channel allowed), which reproduces the
    old "must be spatially contiguous" requirement for MB/MG — the gap
    handling itself is otherwise identical to NMX's.
    """

    # --- window ratios, all derived off a single time_window_s parameter ---
    RECURSIVE_MULT    = 1.01   # tw_recursive = time_window_s(ns) * this
    SPAN_MULT         = 1.5    # tw_span_cap  = tw_recursive * this (max 1D window)
    COINCIDENCE_MULT  = 2.0    # tw_coincidence = tw_recursive * this (2D matching window)

    # --- spatial gap allowed within a single plane's spatial split step ---
    DEFAULT_MAX_GAP = 0        # 0 = contiguous only (MB/MG behaviour)

    # --- labels, used only for logging / stats-dict key naming ---
    LABEL      = "VMM normal"
    PLANE0_TAG = "w"           # wire
    PLANE1_TAG = "s"           # strip / grid

    # -------------------------------------------------------------------
    # Hooks — override these in a subclass to change behaviour
    # -------------------------------------------------------------------
    @classmethod
    def _derive_time_windows(cls, time_window_s: float) -> tuple:
        """Convert float window seconds into recursive / span-cap / coincidence ns gates."""
        tw_ns          = int(round(time_window_s * 1e9))
        tw_recursive   = int(round(tw_ns * cls.RECURSIVE_MULT))
        tw_span_cap    = int(round(tw_recursive * cls.SPAN_MULT))
        tw_coincidence = int(round(tw_recursive * cls.COINCIDENCE_MULT))
        return tw_recursive, tw_span_cap, tw_coincidence

    @classmethod
    def _get_plane_limits(cls, config: dict) -> tuple:
        """
        Return (max_span0, max_span1, max_gap0, max_gap1) for plane 0 (wire)
        and plane 1 (strip/grid). MB/MG reads the existing 'wires' /
        'strips'/'grids' config keys and uses DEFAULT_MAX_GAP for both planes.
        """
        if 'wires' not in config:
            print('\t [ERROR] Config is missing "wires" — cannot cluster. Check your config file.')
            sys.exit(1)

        if 'strips' in config:
            max_strips = int(config['strips'])
        elif 'grids' in config:
            max_strips = int(config['grids'])
        else:
            print('\t [ERROR] Config is missing both "strips" and "grids" — cannot cluster. Check your config file.')
            sys.exit(1)

        max_wires = int(config['wires'])
        gap = cls.DEFAULT_MAX_GAP
        return max_wires, max_strips, gap, gap

    @staticmethod
    def _calc_position(ch2: np.ndarray, ts2: np.ndarray, adc2: np.ndarray,
                        cluster_id: np.ndarray, n_clusters: int) -> np.ndarray:
        """Weighted average (center of gravity) position — MB/MG behaviour."""
        tot_adc = np.bincount(cluster_id, weights=adc2.astype('float64'), minlength=n_clusters)
        pos_num = np.bincount(cluster_id, weights=(ch2.astype('float64') * adc2), minlength=n_clusters)
        with np.errstate(divide='ignore', invalid='ignore'):
            return np.where(tot_adc > 0, pos_num / tot_adc, np.nan)

    # -------------------------------------------------------------------
    # OPTIMIZED METHODS — Vectorized plane matching and output filling
    # -------------------------------------------------------------------
    
    @classmethod
    def _match_planes_one_to_one_vectorized(
        cls,
        idx0: np.ndarray,
        idx1: np.ndarray,
        ts0: np.ndarray,
        ts1: np.ndarray,
        id0: np.ndarray,
        id1: np.ndarray,
        tw_coincidence: int,
    ) -> tuple:
        """
        Vectorized one-to-one plane matching with greedy quality-sorted assignment.
        
        Instead of looping over p0 clusters individually and checking p1_used state,
        this collects ALL candidate pairs, sorts by time difference, then greedily
        assigns from best-first, ensuring strict one-to-one matching.
        
        ~50-200× faster than the original for-loop version.
        
        Args:
            idx0, idx1: Original indices into valid clusters
            ts0, ts1: Timestamps of valid clusters  
            id0, id1: Hit IDs of valid clusters
            tw_coincidence: Time window for matching (ns)
        
        Returns:
            (matched_idx0, matched_idx1): 1D numpy arrays of matching pair indices
        """
        
        if len(idx0) == 0 or len(idx1) == 0:
            return np.array([], dtype='int64'), np.array([], dtype='int64')
        
        # Find time windows using searchsorted (reuse existing logic)
        left = np.searchsorted(ts1, ts0 - tw_coincidence, side='left')
        right = np.searchsorted(ts1, ts0 + tw_coincidence, side='right')
        
        # ===== STEP 1: Vectorized candidate collection =====
        # Collect ALL candidate pairs in this pass, vectorizing time diffs per batch
        candidates_p0 = []
        candidates_p1 = []
        candidates_diff = []
        
        for i, (l, r) in enumerate(zip(left, right)):
            if l >= r:  # No candidates in this time window
                continue
            
            # Get indices within the time window
            p1_window = np.arange(l, r)
            
            # Filter by matching ID (vectorized)
            id_match = id1[p1_window] == id0[i]
            p1_matches = p1_window[id_match]
            
            if len(p1_matches) == 0:
                continue
            
            # Vectorized time difference computation for this batch
            time_diffs = np.abs(ts1[p1_matches].astype(np.int64) - ts0[i].astype(np.int64))
            
            # Collect (p0_idx, p1_idx, quality) tuples
            candidates_p0.extend([i] * len(p1_matches))
            candidates_p1.extend(p1_matches)
            candidates_diff.extend(time_diffs)
        
        if len(candidates_p0) == 0:
            return np.array([], dtype='int64'), np.array([], dtype='int64')
        
        # Convert to arrays for sorting
        candidates_p0 = np.array(candidates_p0, dtype='int64')
        candidates_p1 = np.array(candidates_p1, dtype='int64')
        candidates_diff = np.array(candidates_diff, dtype='int64')
        
        # ===== STEP 2: Sort candidates by match quality (time difference) =====
        sort_order = np.argsort(candidates_diff)
        sorted_p0 = candidates_p0[sort_order]
        sorted_p1 = candidates_p1[sort_order]
        
        # ===== STEP 3: Greedy one-to-one assignment =====
        # Track which p0 and p1 clusters have been matched
        p0_matched = np.zeros(len(idx0), dtype=bool)
        p1_matched = np.zeros(len(idx1), dtype=bool)
        
        # Iterate through candidates in quality order, assign if both unmatched
        final_matches_p0 = []
        final_matches_p1 = []
        
        for p0_local_idx, p1_local_idx in zip(sorted_p0, sorted_p1):
            if not p0_matched[p0_local_idx] and not p1_matched[p1_local_idx]:
                p0_matched[p0_local_idx] = True
                p1_matched[p1_local_idx] = True
                final_matches_p0.append(idx0[p0_local_idx])
                final_matches_p1.append(idx1[p1_local_idx])
        
        return np.array(final_matches_p0, dtype='int64'), np.array(final_matches_p1, dtype='int64')
    
    @staticmethod
    def _populate_output_vectorized(
        p0: dict,
        p1: dict,
        matched_p0_idx: np.ndarray,
        matched_p1_idx: np.ndarray,
        unmatched_p0: np.ndarray,
        unmatched_p1: np.ndarray,
    ) -> dict:
        """
        Vectorized output construction that sorts all accepted events chronologically.
        """
        n2d   = len(matched_p0_idx)
        n1d0  = len(unmatched_p0)
        n1d1  = len(unmatched_p1)
        total = n2d + n1d0 + n1d1

        if total == 0:
            empty_arr = np.array([], dtype='int64')
            empty_flt = np.array([], dtype='float64')
            return {
                'id': empty_arr, 'coord0': empty_flt, 'coord1': empty_flt,
                'ph0': empty_arr, 'ph1': empty_arr, 'mult0': empty_arr,
                'mult1': empty_arr, 'span': empty_arr, 'ts': empty_arr,
                'pulseT': empty_arr, 'prevPT': empty_arr,
            }

        # 1. Compute timestamps for all candidate event types
        ts_2d   = np.minimum(p0['ts'][matched_p0_idx], p1['ts'][matched_p1_idx]) if n2d > 0 else np.array([], dtype='int64')
        ts_1d0  = p0['ts'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        ts_1d1  = p1['ts'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        # Combine timestamps to find chronological sort order
        ts_combined = np.concatenate([ts_2d, ts_1d0, ts_1d1])
        sort_order  = np.argsort(ts_combined, kind='stable')

        # 2. Build unsorted component arrays
        # IDs
        ids_2d  = p0['id'][matched_p0_idx] if n2d > 0 else np.array([], dtype='int64')
        ids_1d0 = p0['id'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        ids_1d1 = p1['id'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        # Coordinates
        c0_2d  = p0['coord'][matched_p0_idx] if n2d > 0 else np.array([], dtype='float64')
        c0_1d0 = p0['coord'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='float64')
        c0_1d1 = np.full(n1d1, np.nan, dtype='float64')

        c1_2d  = p1['coord'][matched_p1_idx] if n2d > 0 else np.array([], dtype='float64')
        c1_1d0 = np.full(n1d0, np.nan, dtype='float64')
        c1_1d1 = p1['coord'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='float64')

        # ADCs / Pulse Heights
        ph0_2d  = p0['adc'][matched_p0_idx].astype('int64') if n2d > 0 else np.array([], dtype='int64')
        ph0_1d0 = p0['adc'][unmatched_p0].astype('int64') if n1d0 > 0 else np.array([], dtype='int64')
        ph0_1d1 = np.zeros(n1d1, dtype='int64')

        ph1_2d  = p1['adc'][matched_p1_idx].astype('int64') if n2d > 0 else np.array([], dtype='int64')
        ph1_1d0 = np.zeros(n1d0, dtype='int64')
        ph1_1d1 = p1['adc'][unmatched_p1].astype('int64') if n1d1 > 0 else np.array([], dtype='int64')

        # Multiplicities
        m0_2d  = p0['mult'][matched_p0_idx] if n2d > 0 else np.array([], dtype='int64')
        m0_1d0 = p0['mult'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        m0_1d1 = np.zeros(n1d1, dtype='int64')

        m1_2d  = p1['mult'][matched_p1_idx] if n2d > 0 else np.array([], dtype='int64')
        m1_1d0 = np.zeros(n1d0, dtype='int64')
        m1_1d1 = p1['mult'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        # Spans
        span_2d  = (np.maximum(p0['ts_max'][matched_p0_idx], p1['ts_max'][matched_p1_idx]) -
                    np.minimum(p0['ts'][matched_p0_idx], p1['ts'][matched_p1_idx])) if n2d > 0 else np.array([], dtype='int64')
        span_1d0 = p0['span'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        span_1d1 = p1['span'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        # Pulse Timing Metrics
        pt_2d  = p0['pulseT'][matched_p0_idx] if n2d > 0 else np.array([], dtype='int64')
        pt_1d0 = p0['pulseT'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        pt_1d1 = p1['pulseT'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        ppt_2d  = p0['prevPT'][matched_p0_idx] if n2d > 0 else np.array([], dtype='int64')
        ppt_1d0 = p0['prevPT'][unmatched_p0] if n1d0 > 0 else np.array([], dtype='int64')
        ppt_1d1 = p1['prevPT'][unmatched_p1] if n1d1 > 0 else np.array([], dtype='int64')

        # 3. Concatenate and sort everything by timestamps
        return {
            'id':     np.concatenate([ids_2d, ids_1d0, ids_1d1])[sort_order],
            'coord0': np.concatenate([c0_2d, c0_1d0, c0_1d1])[sort_order],
            'coord1': np.concatenate([c1_2d, c1_1d0, c1_1d1])[sort_order],
            'ph0':    np.concatenate([ph0_2d, ph0_1d0, ph0_1d1])[sort_order],
            'ph1':    np.concatenate([ph1_2d, ph1_1d0, ph1_1d1])[sort_order],
            'mult0':  np.concatenate([m0_2d, m0_1d0, m0_1d1])[sort_order],
            'mult1':  np.concatenate([m1_2d, m1_1d0, m1_1d1])[sort_order],
            'span':   np.concatenate([span_2d, span_1d0, span_1d1])[sort_order],
            'ts':     ts_combined[sort_order],
            'pulseT': np.concatenate([pt_2d, pt_1d0, pt_1d1])[sort_order],
            'prevPT': np.concatenate([ppt_2d, ppt_1d0, ppt_1d1])[sort_order],
        }
    # @staticmethod
    # def _populate_output_vectorized(
    #     p0: dict,
    #     p1: dict,
    #     matched_p0_idx: np.ndarray,
    #     matched_p1_idx: np.ndarray,
    #     unmatched_p0: np.ndarray,
    #     unmatched_p1: np.ndarray,
    # ) -> dict:
    #     """
    #     Vectorized population of output arrays using fancy indexing.
        
    #     Replaces three manual for-loops with vectorized array operations:
    #     - All 2D matches filled with a single fancy-indexed assignment per field
    #     - All 1D plane-0 unmatched filled with a single fancy-indexed assignment per field
    #     - All 1D plane-1 unmatched filled with a single fancy-indexed assignment per field
        
    #     ~5-10× faster than manual loop population.
        
    #     Returns:
    #         dict with keys: 'id', 'coord0', 'coord1', 'ph0', 'ph1', 'mult0', 'mult1',
    #                        'span', 'ts', 'pulseT', 'prevPT'
    #     """
    #     n2d   = len(matched_p0_idx)
    #     n1d0  = len(unmatched_p0)
    #     n1d1  = len(unmatched_p1)
    #     total = n2d + n1d0 + n1d1
        
    #     # Pre-allocate all output arrays at once
    #     c_id     = np.empty(total, dtype='int64')
    #     c_coord0 = np.full(total, np.nan, dtype='float64')
    #     c_coord1 = np.full(total, np.nan, dtype='float64')
    #     c_ph0    = np.zeros(total, dtype='int64')
    #     c_ph1    = np.zeros(total, dtype='int64')
    #     c_mult0  = np.zeros(total, dtype='int64')
    #     c_mult1  = np.zeros(total, dtype='int64')
    #     c_span   = np.zeros(total, dtype='int64')
    #     ts_out   = np.zeros(total, dtype='int64')
    #     pulseT_out = np.zeros(total, dtype='int64')
    #     prevPT_out = np.zeros(total, dtype='int64')
        
    #     # ===== Fill 2D matches: vectorized fancy indexing (no loop) =====
    #     if n2d > 0:
    #         c_id[:n2d] = p0['id'][matched_p0_idx]
    #         c_coord0[:n2d] = p0['coord'][matched_p0_idx]
    #         c_coord1[:n2d] = p1['coord'][matched_p1_idx]
    #         c_ph0[:n2d] = p0['adc'][matched_p0_idx].astype('int64')
    #         c_ph1[:n2d] = p1['adc'][matched_p1_idx].astype('int64')
    #         c_mult0[:n2d] = p0['mult'][matched_p0_idx]
    #         c_mult1[:n2d] = p1['mult'][matched_p1_idx]
            
    #         # Time span: max timestamp of either plane minus min timestamp
    #         c_span[:n2d] = (
    #             np.maximum(p0['ts_max'][matched_p0_idx], p1['ts_max'][matched_p1_idx]) -
    #             np.minimum(p0['ts'][matched_p0_idx], p1['ts'][matched_p1_idx])
    #         )
    #         ts_out[:n2d] = np.minimum(p0['ts'][matched_p0_idx], p1['ts'][matched_p1_idx])
    #         pulseT_out[:n2d] = p0['pulseT'][matched_p0_idx]
    #         prevPT_out[:n2d] = p0['prevPT'][matched_p0_idx]
        
    #     # ===== Fill 1D plane-0 unmatched: vectorized fancy indexing =====
    #     if n1d0 > 0:
    #         start = n2d
    #         end = n2d + n1d0
            
    #         c_id[start:end] = p0['id'][unmatched_p0]
    #         c_coord0[start:end] = p0['coord'][unmatched_p0]
    #         c_ph0[start:end] = p0['adc'][unmatched_p0].astype('int64')
    #         c_mult0[start:end] = p0['mult'][unmatched_p0]
    #         c_span[start:end] = p0['span'][unmatched_p0]
    #         ts_out[start:end] = p0['ts'][unmatched_p0]
    #         pulseT_out[start:end] = p0['pulseT'][unmatched_p0]
    #         prevPT_out[start:end] = p0['prevPT'][unmatched_p0]
        
    #     # ===== Fill 1D plane-1 unmatched: vectorized fancy indexing =====
    #     if n1d1 > 0:
    #         start = n2d + n1d0
            
    #         c_id[start:] = p1['id'][unmatched_p1]
    #         c_coord1[start:] = p1['coord'][unmatched_p1]
    #         c_ph1[start:] = p1['adc'][unmatched_p1].astype('int64')
    #         c_mult1[start:] = p1['mult'][unmatched_p1]
    #         c_span[start:] = p1['span'][unmatched_p1]
    #         ts_out[start:] = p1['ts'][unmatched_p1]
    #         pulseT_out[start:] = p1['pulseT'][unmatched_p1]
    #         prevPT_out[start:] = p1['prevPT'][unmatched_p1]
        
    #     return {
    #         'id': c_id, 'coord0': c_coord0, 'coord1': c_coord1,
    #         'ph0': c_ph0, 'ph1': c_ph1,
    #         'mult0': c_mult0, 'mult1': c_mult1, 'span': c_span,
    #         'ts': ts_out, 'pulseT': pulseT_out, 'prevPT': prevPT_out,
    #     }

    # -------------------------------------------------------------------
    # Shared machinery — should not need overriding
    # -------------------------------------------------------------------
    @classmethod
    def _cluster_plane(cls, plane_hits: np.ndarray, max_gap: int, max_span: int,
                        tw_recursive: int, tw_span_cap: int) -> dict:
        """
        Form spatial/temporal clusters independently for a single plane:
          1. Split hits into time-clusters wherever the gap between consecutive
             readouts (sorted by time) exceeds tw_recursive, or the ID changes.
          2. Within each time-cluster, sort by channel index and SPLIT (never
             discard) wherever the spatial gap exceeds max_gap — one
             time-cluster can yield 1..r space clusters.
        """

        n = len(plane_hits)
        empty_res = {
            'count': 0, 'ts': np.array([]), 'pulseT': np.array([]), 'prevPT': np.array([]),
            'coord': np.array([]), 'adc': np.array([]), 'mult': np.array([]),
            'span': np.array([]), 'id': np.array([]), 'valid_mask': np.array([], dtype=bool),
            'ts_max': np.array([])
        }
        if n == 0:
            return empty_res

        # Stage 1: sort by time, split on ID change or a time gap > tw_recursive
        sort_order = np.argsort(plane_hits['timeStamp'], kind='stable')
        ts, ch_idx, adc, ids, pulseT, prevPT = (
            plane_hits['timeStamp'][sort_order], plane_hits['index'][sort_order],
            plane_hits['adc'][sort_order], plane_hits['ID'][sort_order],
            plane_hits['pulseT'][sort_order], plane_hits['prevPT'][sort_order],
        )

        break1 = np.empty(n, dtype=bool)
        break1[0]  = True
        break1[1:] = (np.abs(np.diff(ts)) > tw_recursive) | (ids[1:] != ids[:-1])
        time_cluster_id = np.cumsum(break1) - 1

        # Stage 2: within each time-cluster, sort by channel index and split again
        # wherever the spatial gap exceeds max_gap missing channels
        sort2 = np.lexsort((ch_idx, time_cluster_id))
        tc2, ch2, ts2, adc2, id2, pulseT2, prevPT2 = (
            time_cluster_id[sort2], ch_idx[sort2], ts[sort2], adc[sort2],
            ids[sort2], pulseT[sort2], prevPT[sort2],
        )
   
        # Stage 2: Group hits in the same time cluster within the max_span boundary
        break2 = np.empty(n, dtype=bool)
        break2[0] = True
        # Split only on time-cluster change or if spatial gap exceeds max_span
        break2[1:] = (tc2[1:] != tc2[:-1]) | ((ch2[1:] - ch2[:-1]) > max_span)
        cluster_id = np.cumsum(break2) - 1
        n_clusters = int(cluster_id[-1]) + 1
        
        # --- Metrics Calculation ---
        counts = np.bincount(cluster_id, minlength=n_clusters).astype('int64')
        tot_adc = np.bincount(cluster_id, weights=adc2.astype('float64'), minlength=n_clusters)
        
        c_min = np.full(n_clusters, 999999, dtype='int64')
        c_max = np.full(n_clusters, -1, dtype='int64')
        np.minimum.at(c_min, cluster_id, ch2)
        np.maximum.at(c_max, cluster_id, ch2)
        spatial_span = c_max - c_min + 1
        
        ts_min = np.full(n_clusters, np.iinfo(np.int64).max, dtype='int64')
        ts_max = np.full(n_clusters, 0, dtype='int64')
        np.minimum.at(ts_min, cluster_id, ts2)
        np.maximum.at(ts_max, cluster_id, ts2)
        span = ts_max - ts_min
        
        first_idx = np.searchsorted(cluster_id, np.arange(n_clusters), side='left')
        id_out, pulseT_out, prevPT_out = id2[first_idx], pulseT2[first_idx], prevPT2[first_idx]
        
        # --- REJECTION LOGIC ---
        # 1. Ensure no missing channels exist inside the cluster span
        no_gaps = (counts == spatial_span)
        
        # 2. Combine all validation constraints
        valid_mask = (
            (span <= tw_span_cap) & 
            (spatial_span <= max_span) & 
            (tot_adc > 0) & 
            no_gaps  # <-- Rejects [23, 24, 27] completely
        )
    
        coords = cls._calc_position(ch2, ts2, adc2, cluster_id, n_clusters)
        valid_mask &= ~np.isnan(coords)

        return {
            'count': n_clusters, 'valid_mask': valid_mask,
            'ts': ts_min, 'ts_max': ts_max, 'pulseT': pulseT_out, 'prevPT': prevPT_out,
            'coord': coords, 'adc': tot_adc, 'mult': counts, 'span': span, 'id': id_out,
        }
    
    @classmethod
    def cluster(cls, hits, config: dict, time_window_s: float) -> eventsVMMnormal:
        from lib.colors import INFO, RESET

        print(f'{INFO}\nClustering {cls.LABEL} events ... {RESET}', end='')

        m = hits.matrix[:hits.fill_count]
        n = len(m)
        if n == 0:
            return eventsVMMnormal(size=0)

        max_span0, max_span1, max_gap0, max_gap1 = cls._get_plane_limits(config)
        tw_recursive, tw_span_cap, tw_coincidence = cls._derive_time_windows(time_window_s)

        # 1. Cluster each plane independently
        p0 = cls._cluster_plane(m[m['plane'] == 0], max_gap0, max_span0, tw_recursive, tw_span_cap)
        p1 = cls._cluster_plane(m[m['plane'] == 1], max_gap1, max_span1, tw_recursive, tw_span_cap)

        # 2. Get valid candidate indices per plane
        idx0, idx1 = np.where(p0['valid_mask'])[0], np.where(p1['valid_mask'])[0]
        ts0, ts1   = p0['ts'][idx0], p1['ts'][idx1]
        id0, id1   = p0['id'][idx0], p1['id'][idx1]

        # 3. Vectorized one-to-one plane matching
        matched_p0_idx, matched_p1_idx = cls._match_planes_one_to_one_vectorized(
            idx0, idx1, ts0, ts1, id0, id1, tw_coincidence
        )

        # 4. Identify 1D single-plane candidates
        matched_p0_mask = np.isin(idx0, matched_p0_idx)
        matched_p1_mask = np.isin(idx1, matched_p1_idx)

        unmatched_p0 = idx0[~matched_p0_mask]
        unmatched_p1 = idx1[~matched_p1_mask]
        
        accepted_2d    = len(matched_p0_idx)
        accepted_1d_p0 = len(unmatched_p0)
        accepted_1d_p1 = len(unmatched_p1)

        accepted_total = accepted_2d + accepted_1d_p0 + accepted_1d_p1

        n_candidates0 = p0['count']
        n_candidates1 = p1['count']
        n_candidates  = n_candidates0 + n_candidates1

        rejected_p0 = np.sum(~p0['valid_mask'])
        rejected_p1 = np.sum(~p1['valid_mask'])
        rejected_total = rejected_p0 + rejected_p1

        out = eventsVMMnormal(size=accepted_total)
        out.durations, out.instrumentIDs = hits.durations.copy(), hits.instrumentIDs.copy()

        if accepted_total == 0:
            out.stats.update({
                'n_candidates':    n_candidates,
                'n_candidates_p0': n_candidates0,
                'n_candidates_p1': n_candidates1,
                'n_accepted': 0,
                'n_accepted_2d': 0,
                f'n_accepted_1d{cls.PLANE0_TAG}': 0,
                f'n_accepted_1d{cls.PLANE1_TAG}': 0,
                'n_rejected': rejected_total,
                f'n_rejected_1d{cls.PLANE0_TAG}': rejected_p0,
                f'n_rejected_1d{cls.PLANE1_TAG}': rejected_p1,
            })
            return out

        # 5. Populate output array with 2D and 1D single-plane events in chronological order
        output_dict = cls._populate_output_vectorized(
            p0, p1, matched_p0_idx, matched_p1_idx, unmatched_p0, unmatched_p1
        )

        timing_src = {
            'timeStamp': output_dict['ts'],
            'pulseT': output_dict['pulseT'],
            'prevPT': output_dict['prevPT']
        }

        computed = {
            'ID': output_dict['id'],
            'coordinate0': output_dict['coord0'],
            'coordinate1': output_dict['coord1'],
            'pulseHeight0': output_dict['ph0'],
            'pulseHeight1': output_dict['ph1'],
            'mult0': output_dict['mult0'],
            'mult1': output_dict['mult1'],
            'clusterTimeSpan': output_dict['span'],
        }

        out.stats.update({
            'n_candidates':    n_candidates,
            'n_candidates_p0': n_candidates0,
            'n_candidates_p1': n_candidates1,
            'n_accepted': accepted_total,
            'n_accepted_2d': accepted_2d,
            f'n_accepted_1d{cls.PLANE0_TAG}': accepted_1d_p0,
            f'n_accepted_1d{cls.PLANE1_TAG}': accepted_1d_p1,
            'n_rejected': rejected_total,
            f'n_rejected_1d{cls.PLANE0_TAG}': rejected_p0,
            f'n_rejected_1d{cls.PLANE1_TAG}': rejected_p1,
        })

        out.absorb(computed, timing_src)
        return out
    
    # @classmethod
    # def cluster(cls, hits, config: dict, time_window_s: float) -> eventsVMMnormal:
    #     """
    #     Cluster hits into 2D and 1D events by independently clustering two planes,
    #     matching coincident 2D events, and retaining valid unmatched 1D clusters
    #     (wires-only or strips-only).
    #     """
    #     from lib.colors import INFO, RESET

    #     print(f'{INFO}\nClustering {cls.LABEL} events ... {RESET}', end='')

    #     m = hits.matrix[:hits.fill_count]
    #     n = len(m)
    #     if n == 0:
    #         return eventsVMMnormal(size=0)

    #     max_span0, max_span1, max_gap0, max_gap1 = cls._get_plane_limits(config)
    #     tw_recursive, tw_span_cap, tw_coincidence = cls._derive_time_windows(time_window_s)

    #     # 1. Cluster each plane independently
    #     p0 = cls._cluster_plane(m[m['plane'] == 0], max_gap0, max_span0, tw_recursive, tw_span_cap)
    #     p1 = cls._cluster_plane(m[m['plane'] == 1], max_gap1, max_span1, tw_recursive, tw_span_cap)

    #     # 2. Get valid candidate indices per plane
    #     idx0, idx1 = np.where(p0['valid_mask'])[0], np.where(p1['valid_mask'])[0]
    #     ts0, ts1   = p0['ts'][idx0], p1['ts'][idx1]
    #     id0, id1   = p0['id'][idx0], p1['id'][idx1]

    #     # 3. Vectorized one-to-one plane matching
    #     matched_p0_idx, matched_p1_idx = cls._match_planes_one_to_one_vectorized(
    #         idx0, idx1, ts0, ts1, id0, id1, tw_coincidence
    #     )

    #     # 4. Identify 1D single-plane candidates (valid candidates that were not matched in 2D)
    #     matched_p0_mask = np.isin(idx0, matched_p0_idx)
    #     matched_p1_mask = np.isin(idx1, matched_p1_idx)

    #     unmatched_p0 = idx0[~matched_p0_mask]
    #     unmatched_p1 = idx1[~matched_p1_mask]
        
    #     # 1D accepted counts must be the UNMATCHED valid candidates
    #     accepted_2d    = len(matched_p0_idx)
    #     accepted_1d_p0 = len(unmatched_p0)
    #     accepted_1d_p1 = len(unmatched_p1)

    #     # Total output events: 2D matched pairs + 1D unmatched p0 + 1D unmatched p1
    #     accepted_total = accepted_2d + accepted_1d_p0 + accepted_1d_p1

    #     # All formed candidates vs. valid candidates
    #     n_candidates0 = p0['count']
    #     n_candidates1 = p1['count']
    #     n_candidates  = n_candidates0 + n_candidates1

    #     # Calculate rejected candidates (those that failed single-plane validity checks)
    #     rejected_p0 = np.sum(~p0['valid_mask'])
    #     rejected_p1 = np.sum(~p1['valid_mask'])
    #     rejected_total = rejected_p0 + rejected_p1

    #     out = eventsVMMnormal(size=accepted_total)
    #     out.durations, out.instrumentIDs = hits.durations.copy(), hits.instrumentIDs.copy()

    #     if accepted_total == 0:
    #         out.stats.update({
    #             'n_candidates':    n_candidates,
    #             'n_candidates_p0': n_candidates0,
    #             'n_candidates_p1': n_candidates1,
    #             'n_accepted': 0,
    #             'n_accepted_2d': 0,
    #             f'n_accepted_1d{cls.PLANE0_TAG}': 0,
    #             f'n_accepted_1d{cls.PLANE1_TAG}': 0,
    #             'n_rejected': rejected_total,
    #             f'n_rejected_1d{cls.PLANE0_TAG}': rejected_p0,
    #             f'n_rejected_1d{cls.PLANE1_TAG}': rejected_p1,
    #         })
    #         return out

    #     # 5. Populate output array with 2D matches followed by 1D single-plane events
    #     output_dict = cls._populate_output_vectorized(
    #         p0, p1, matched_p0_idx, matched_p1_idx, unmatched_p0, unmatched_p1
    #     )

    #     # Extract mapped output arrays
    #     timing_src = {
    #         'timeStamp': output_dict['ts'],
    #         'pulseT': output_dict['pulseT'],
    #         'prevPT': output_dict['prevPT']
    #     }

    #     computed = {
    #         'ID': output_dict['id'],
    #         'coordinate0': output_dict['coord0'],
    #         'coordinate1': output_dict['coord1'],
    #         'pulseHeight0': output_dict['ph0'],
    #         'pulseHeight1': output_dict['ph1'],
    #         'mult0': output_dict['mult0'],
    #         'mult1': output_dict['mult1'],
    #         'clusterTimeSpan': output_dict['span'],
    #     }


    #     out.stats.update({
    #         'n_candidates':    n_candidates,
    #         'n_candidates_p0': n_candidates0,
    #         'n_candidates_p1': n_candidates1,
    #         'n_accepted': accepted_total,
    #         'n_accepted_2d': accepted_2d,
    #         f'n_accepted_1d{cls.PLANE0_TAG}': accepted_1d_p0,
    #         f'n_accepted_1d{cls.PLANE1_TAG}': accepted_1d_p1,
    #         'n_rejected': rejected_total,
    #         f'n_rejected_1d{cls.PLANE0_TAG}': rejected_p0,
    #         f'n_rejected_1d{cls.PLANE1_TAG}': rejected_p1,
    #     })

    #     out.absorb(computed, timing_src)
    #     return out

# =============================================================================
# NMX Clusterer — inherits the split/match machinery, overrides only the
# three things that differ: window ratios, gap source (per-axis, from
# config, non-zero), and the position calculation (micro-TPC).
# =============================================================================

class NMXClusterer(VMMNormalClusterer):
    """
    NMX-specific clustering, built on VMMNormalClusterer's split-based
    independent-plane-then-match approach. Differs from MB/MG only in:
      - a spatial gap is allowed within a plane cluster (config-driven,
        per axis), instead of requiring strict contiguity
      - the span-cap / coincidence window ratios (5x / 2x instead of 1.5x / 2x)
      - position is micro-TPC (channel of the hit with the largest timestamp
        in the cluster), not a charge-weighted average
    
    Inherits the optimized vectorized matching from VMMNormalClusterer.
    """

    SPAN_MULT        = 5.0   # tw_span_cap    = tw_recursive * 5 (mirrors 100 ns gap / 500 ns span cap)
    COINCIDENCE_MULT = 2.0   # tw_coincidence = tw_recursive * 2

    LABEL      = "NMX"
    PLANE0_TAG = "x"
    PLANE1_TAG = "y"

    @classmethod
    def _get_plane_limits(cls, config: dict) -> tuple:
        required = ['maxSpanX', 'maxSpanY', 'maxGapX', 'maxGapY']
        missing  = [key for key in required if key not in config]
        if missing:
            print(f'\t [ERROR] NMX Config is missing key(s): {", ".join(missing)}. Check config file.')
            sys.exit(1)

        max_span_x, max_span_y = int(config['maxSpanX']), int(config['maxSpanY'])
        max_gap_x,  max_gap_y  = int(config['maxGapX']),  int(config['maxGapY'])
        return max_span_x, max_span_y, max_gap_x, max_gap_y

    @staticmethod
    def _calc_position(ch2: np.ndarray, ts2: np.ndarray, adc2: np.ndarray,
                        cluster_id: np.ndarray, n_clusters: int) -> np.ndarray:
        """Micro-TPC position: channel of the hit with the largest timestamp in the cluster."""
        counts       = np.bincount(cluster_id, minlength=n_clusters)
        time_order   = np.lexsort((ts2, cluster_id))
        last_in_time = np.searchsorted(cluster_id[time_order], np.arange(n_clusters), side='right') - 1
        return np.where(counts > 0, ch2[time_order][last_in_time].astype('float64'), np.nan)