import numpy as np
import sys 
import os
# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
    
from newLib.events_containers import eventsVMMnormal, eventsVMMclustered, eventsR5560

# =============================================================================
# Wires and Strips Normal Clusterer (Multi-Blade & Multi-Grid)
# =============================================================================

class VMMNormalClusterer:
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
        m = hits.matrix[:hits.fill_count]
        n = len(m)

        if n == 0:
            return eventsVMMnormal(size=0)

        tw_recursive, tw_max = VMMNormalClusterer._derive_time_windows(time_window_s)
        # Get the wire and strip/grid configuration from config for clustering (error and exit if not found)
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

        cluster_ids, sort_order, n_clusters = VMMNormalClusterer._partition_hits(m['ID'], m['timeStamp'], tw_recursive)
        
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
        accept_1d = ((accept_window & has_wire_hit & ~has_strip_hit & wire_contiguous & wire_in_limits)
                    | (accept_window & has_strip_hit & ~has_wire_hit & strip_contiguous & strip_in_limits))

        with np.errstate(divide='ignore', invalid='ignore'):
            coord0 = np.where(wire_adc  > 0, np.round(wire_pos_num  / wire_adc,  2), np.nan)
            coord1 = np.where(strip_adc > 0, np.round(strip_pos_num / strip_adc, 2), np.nan)

        accept_2d &= ~(np.isnan(coord0) | np.isnan(coord1))
        accept_1d &= ~np.isnan(coord0)  | ~np.isnan(coord1)

        assigned_ids = np.where(accept_2d | accept_1d, ms['ID'][first_hit], np.int64(-1))
        n_accepted   = int(np.sum(accept_2d | accept_1d))

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
            'clusterSpan':  span.astype('int64'),
        }

        # Populate stats BEFORE absorb() so print_stats() sees the correct values
        out.stats.update({
            'n_candidates':         n_clusters,
            'n_accepted':           n_accepted,
            'n_rejected':           n_clusters - n_accepted,
            'n_accepted_2d':        int(np.sum(accept_2d)),
            'n_accepted_1d':        int(np.sum(accept_1d)),
            'n_rejected_overflow':  int(np.sum(~accept_window)),
            'n_rejected_neighbour': int(np.sum(accept_window & ~(accept_2d | accept_1d))),
        })

        out.absorb(computed, timing_src)
        return out


# =============================================================================
# VMM Clustered Clusterer (Passthrough Engine)
# =============================================================================

class VMMClusteredClusterer:
    """Passthrough engine for hardware-firmware pre-clustered readout matrices."""
    @staticmethod
    def cluster(hits, config: dict, time_window_s: float = 0.0) -> eventsVMMclustered:
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