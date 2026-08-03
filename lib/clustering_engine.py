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
    def _max_electrode_counts(config: dict) -> tuple:
        """
        Resolve (max_span_x, max_span_y) from config, keyed off detectorType --
        electrode_x/electrode_y is plane-0/plane-1 (mirrors hits.plane: 0=X, 1=Y), NOT any
        particular electrode technology. Which config key backs each side differs per detector:

            MB:  electrode_x <- config['wires']   electrode_y <- config['strips']
            MG:  electrode_x <- config['wires']   electrode_y <- config['grids']
            NMX: electrode_x <- config['strips']  electrode_y <- config['strips']  (same value, both edges are strips)
        """
        det_type = config.get('detectorType', '')

        if det_type == 'NMX':
            required = ['strips', 'maxSpanX', 'maxSpanY', 'maxGapX', 'maxGapY']
            missing = [key for key in required if key not in config]

            if missing:
                print(f'\t [ERROR] Config is missing the following key(s): {", ".join(missing)}. Check your config file.')
                sys.exit(1)

            max_span_x = int(config['maxSpanX'])
            max_span_y = int(config['maxSpanY'])
            max_gap_x = int(config['maxGapX'])
            max_gap_y = int(config['maxGapY'])
            return max_span_x, max_span_y, max_gap_x, max_gap_y

        # MB / MG share the electrode_x <- wires 
        if 'wires' not in config:
            print('\t [ERROR] Config is missing "wires" — cannot cluster. Check your config file.')
            sys.exit(1)
        max_span_x = int(config['wires'])

        if 'strips' in config:
            max_span_y = int(config['strips']) # MB 
        elif 'grids' in config:
            max_span_y = int(config['grids']) # MG
        else:
            print('\t [ERROR] Config is missing both "strips" and "grids" — cannot cluster. Check your config file.')
            sys.exit(1)

        return max_span_x, max_span_y, 0, 0

    @staticmethod
    def cluster(hits, config: dict, time_window_s: float) -> eventsVMMnormal:

        print(f'{INFO}\nClustering VMM normal events ... {RESET}', end='')

        m = hits.matrix[:hits.fill_count]
        n = len(m)

        if n == 0:
            return eventsVMMnormal(size=0)

        tw_recursive, tw_max = VMMNormalClusterer._derive_time_windows(time_window_s)

        max_span_x, max_span_y, max_gap_x, max_gap_y = VMMNormalClusterer._max_electrode_counts(config)

        cluster_ids, sort_order, n_clusters = VMMNormalClusterer._partition_hits(m['ID'], m['timeStamp'], tw_recursive)

        out = eventsVMMnormal(size=n_clusters)
        out.durations     = hits.durations.copy()
        out.instrumentIDs = hits.instrumentIDs.copy()

        ms            = m[sort_order]
        ts            = ms['timeStamp']
        is_electrode_x = ms['plane'] == 0
        is_electrode_y = ms['plane'] == 1
        ch_idx        = ms['index']
        adc           = ms['adc']

        first_hit = np.searchsorted(cluster_ids, np.arange(n_clusters), side='left')
        last_hit  = np.searchsorted(cluster_ids, np.arange(n_clusters), side='right') - 1
        span      = ts[last_hit] - ts[first_hit]

        x_count = np.bincount(cluster_ids, weights=is_electrode_x.astype('int64'), minlength=n_clusters).astype('int64')
        y_count = np.bincount(cluster_ids, weights=is_electrode_y.astype('int64'), minlength=n_clusters).astype('int64')

        x_adc = np.bincount(cluster_ids, weights=(adc * is_electrode_x).astype('float64'), minlength=n_clusters)
        y_adc = np.bincount(cluster_ids, weights=(adc * is_electrode_y).astype('float64'), minlength=n_clusters)

        x_pos_num = np.bincount(cluster_ids, weights=(ch_idx * adc * is_electrode_x).astype('float64'), minlength=n_clusters)
        y_pos_num = np.bincount(cluster_ids, weights=(ch_idx * adc * is_electrode_y).astype('float64'), minlength=n_clusters)

        x_min = np.full(n_clusters, 999999, dtype='int64')
        x_max = np.full(n_clusters, -1,     dtype='int64')
        np.minimum.at(x_min, cluster_ids[is_electrode_x], ch_idx[is_electrode_x])
        np.maximum.at(x_max, cluster_ids[is_electrode_x], ch_idx[is_electrode_x])

        y_min = np.full(n_clusters, 999999, dtype='int64')
        y_max = np.full(n_clusters, -1,     dtype='int64')
        np.minimum.at(y_min, cluster_ids[is_electrode_y], ch_idx[is_electrode_y])
        np.maximum.at(y_max, cluster_ids[is_electrode_y], ch_idx[is_electrode_y])

        accept_window   = span <= tw_max
        x_contiguous = np.where(x_count > 0, ((x_max - x_min + 1) - x_count) <= max_gap_x, False)
        y_contiguous = np.where(y_count > 0, ((y_max - y_min + 1) - y_count) <= max_gap_y, False)
        x_in_limits  = np.where(x_count > 0, (x_max - x_min + 1) <= max_span_x, True)
        y_in_limits  = np.where(y_count > 0, (y_max - y_min + 1) <= max_span_y, True)
        has_x_hit        = x_count >= 1
        has_y_hit        = y_count >= 1

        accept_2d  = (accept_window & has_x_hit & has_y_hit & x_contiguous & y_contiguous & x_in_limits & y_in_limits)
        accept_1dx = (accept_window & has_x_hit  & ~has_y_hit & x_contiguous & x_in_limits)
        accept_1dy = (accept_window & has_y_hit  & ~has_x_hit & y_contiguous & y_in_limits)

        with np.errstate(divide='ignore', invalid='ignore'):
            coord0 = np.where(x_adc > 0, np.round(x_pos_num / x_adc, 2), np.nan)
            coord1 = np.where(y_adc > 0, np.round(y_pos_num / y_adc, 2), np.nan)

        accept_2d  &= ~(np.isnan(coord0) | np.isnan(coord1))
        accept_1dx &= ~np.isnan(coord0)  & np.isnan(coord1)
        accept_1dy &= np.isnan(coord0)   & ~np.isnan(coord1)

        assigned_ids = np.where(accept_2d | accept_1dx | accept_1dy, ms['ID'][first_hit], np.int64(-1))
        n_accepted   = int(np.sum(accept_2d | accept_1dx | accept_1dy))

        timing_src = {
            'timeStamp': ts[first_hit],
            'pulseT':    ms['pulseT'][first_hit],
            'prevPT':    ms['prevPT'][first_hit],
        }

        computed = {
            'ID':           assigned_ids,
            'coordinate0':  coord0,
            'coordinate1':  coord1,
            'pulseHeight0': x_adc.astype('int64'),
            'pulseHeight1': y_adc.astype('int64'),
            'mult0':        x_count,
            'mult1':        y_count,
            'clusterTimeSpan': span.astype('int64'),
        }

        # Populate stats BEFORE absorb() so print_stats() sees the correct values
        out.stats.update({
            'n_candidates':         n_clusters,
            'n_accepted':           n_accepted,
            'n_rejected':           n_clusters - n_accepted,
            'n_accepted_2d':        int(np.sum(accept_2d)),
            'n_accepted_1dx':       int(np.sum(accept_1dx)),
            'n_accepted_1dy':       int(np.sum(accept_1dy)),
            'n_rejected_overflow':  int(np.sum(~accept_window)),
            'n_rejected_neighbour': int(np.sum(accept_window & ~(accept_2d | accept_1dx | accept_1dy))),
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