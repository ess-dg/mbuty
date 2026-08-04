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
    def cluster(hits, config: dict, time_window_s: float) -> eventsVMMnormal:
        
        print(f'{INFO}\nClustering VMM normal events ... {RESET}',end='')
        
        m = hits.matrix[:hits.fill_count]
        n = len(m)

        if n == 0:
            return eventsVMMnormal(size=0)

        tw_recursive, tw_max = VMMNormalClusterer._derive_time_windows(time_window_s)
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
            'n_candidates':         n_clusters,
            'n_accepted':           n_accepted,
            'n_rejected':           n_clusters - n_accepted,
            'n_accepted_2d':        int(np.sum(accept_2d)),
            'n_accepted_1dw':        int(np.sum(accept_1dw)),
            'n_accepted_1ds':        int(np.sum(accept_1ds)),
            'n_rejected_overflow':  int(np.sum(~accept_window)),
            'n_rejected_neighbour': int(np.sum(accept_window & ~(accept_2d | accept_1dw | accept_1ds))),
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
# =============================================================================
# VMM Clustered Clusterer (Passthrough Engine)
# =============================================================================

class NMXClusterer:
    """
    Vectorized independent clustering logic for NMX detectors, following
    Dorothea's method:
      1. Independent plane-by-plane (Plane 0 / Plane 1) temporal & spatial
         clustering, using the same recursive time window as every other
         clusterer.
      2. Fast binary-search 2D coincidence matching across planes, using a
         matching window of 2x that same recursive window — no extra config
         parameter needed.
    """

    @staticmethod
    def _cluster_plane(plane_hits: np.ndarray, max_gap: int, max_span: int, tw_recursive: int, tw_span_cap: int) -> dict:
        """
        Form spatial/temporal clusters independently for a single NMX strip plane,
        following Dorothea's two-stage method:
          1. Split hits into time-clusters wherever the gap between consecutive
             readouts (sorted by time) exceeds tw_recursive, or the ID changes.
          2. Within each time-cluster, sort by strip index and SPLIT (never discard)
             wherever the spatial gap exceeds max_gap — one time-cluster can yield
             1 to r space clusters.
        """
        n = len(plane_hits)
        empty_res = {
            'count': 0, 'ts': np.array([]), 'pulseT': np.array([]), 'prevPT': np.array([]),
            'coord': np.array([]), 'adc': np.array([]), 'mult': np.array([]),
            'span': np.array([]), 'id': np.array([]), 'valid_mask': np.array([], dtype=bool)
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

        # Stage 2: within each time-cluster, sort by strip index and split again
        # wherever the spatial gap exceeds max_gap missing strips
        sort2 = np.lexsort((ch_idx, time_cluster_id))
        tc2, ch2, ts2, adc2, id2, pulseT2, prevPT2 = (
            time_cluster_id[sort2], ch_idx[sort2], ts[sort2], adc[sort2],
            ids[sort2], pulseT[sort2], prevPT[sort2],
        )

        break2 = np.empty(n, dtype=bool)
        break2[0]  = True
        break2[1:] = (tc2[1:] != tc2[:-1]) | ((ch2[1:] - ch2[:-1]) > (max_gap + 1))
        cluster_id  = np.cumsum(break2) - 1
        n_clusters  = int(cluster_id[-1]) + 1

        counts  = np.bincount(cluster_id, minlength=n_clusters).astype('int64')
        tot_adc = np.bincount(cluster_id, weights=adc2.astype('float64'), minlength=n_clusters)
        pos_num = np.bincount(cluster_id, weights=(ch2 * adc2).astype('float64'), minlength=n_clusters)

        c_min = np.full(n_clusters, 999999, dtype='int64')
        c_max = np.full(n_clusters, -1,     dtype='int64')
        np.minimum.at(c_min, cluster_id, ch2)
        np.maximum.at(c_max, cluster_id, ch2)
        spatial_span = c_max - c_min + 1

        ts_min = np.full(n_clusters, np.iinfo(np.int64).max, dtype='int64')
        ts_max = np.full(n_clusters, 0,                       dtype='int64')
        np.minimum.at(ts_min, cluster_id, ts2)
        np.maximum.at(ts_max, cluster_id, ts2)
        span = ts_max - ts_min

        # cluster_id is monotonically non-decreasing in this (tc2, ch2)-sorted order,
        # so the first row of each cluster is reachable via searchsorted
        first_idx = np.searchsorted(cluster_id, np.arange(n_clusters), side='left')
        id_out, pulseT_out, prevPT_out = id2[first_idx], pulseT2[first_idx], prevPT2[first_idx]

        valid_mask = (span <= tw_span_cap) & (spatial_span <= max_span) & (tot_adc > 0)

        with np.errstate(divide='ignore', invalid='ignore'):
            coords = np.where(tot_adc > 0, np.round(pos_num / tot_adc, 2), np.nan)
        valid_mask &= ~np.isnan(coords)

        return {
            'count': n_clusters, 'valid_mask': valid_mask,
            'ts': ts_min, 'pulseT': pulseT_out, 'prevPT': prevPT_out,
            'coord': coords, 'adc': tot_adc, 'mult': counts, 'span': span, 'id': id_out,
        }

    @staticmethod
    def cluster(hits, config: dict, time_window_s: float) -> eventsVMMnormal:
        print(f'{INFO}\nClustering NMX events ... {RESET}', end='')

        m = hits.matrix[:hits.fill_count]
        n = len(m)
        if n == 0:
            return eventsVMMnormal(size=0)

        required = ['maxSpanX', 'maxSpanY', 'maxGapX', 'maxGapY']
        missing  = [key for key in required if key not in config]
        if missing:
            print(f'\t [ERROR] NMX Config is missing key(s): {", ".join(missing)}. Check config file.')
            sys.exit(1)

        max_span_x, max_span_y = int(config['maxSpanX']), int(config['maxSpanY'])
        max_gap_x,  max_gap_y  = int(config['maxGapX']),  int(config['maxGapY'])

        # Single shared time window (same convention/derivation as every other
        # clusterer):
        #   tw_recursive   -> gap between consecutive readouts that splits a cluster
        #   tw_span_cap    -> total cluster duration (first hit -> last hit), 5x the
        #                      gap (mirrors Dorothea's 100 ns gap / 500 ns span cap)
        #   tw_coincidence -> cross-plane matching window, 2x the gap
        tw_recursive   = int(round(time_window_s * 1e9 * 1.01))
        tw_span_cap    = tw_recursive * 5
        tw_coincidence = tw_recursive * 2

        p0 = NMXClusterer._cluster_plane(m[m['plane'] == 0], max_gap_x, max_span_x, tw_recursive, tw_span_cap)
        p1 = NMXClusterer._cluster_plane(m[m['plane'] == 1], max_gap_y, max_span_y, tw_recursive, tw_span_cap)

        idx0, idx1 = np.where(p0['valid_mask'])[0], np.where(p1['valid_mask'])[0]
        ts0, ts1   = p0['ts'][idx0], p1['ts'][idx1]
        id0, id1   = p0['id'][idx0], p1['id'][idx1]

        p0_used = np.zeros(len(idx0), dtype=bool)
        p1_used = np.zeros(len(idx1), dtype=bool)
        matched_2d = []

        if len(idx0) and len(idx1):
            left  = np.searchsorted(ts1, ts0 - tw_coincidence, side='left')
            right = np.searchsorted(ts1, ts0 + tw_coincidence, side='right')

            for i, (l, r) in enumerate(zip(left, right)):
                if l >= r:
                    continue
                cand = np.where(~p1_used[l:r] & (id1[l:r] == id0[i]))[0] + l
                if len(cand):
                    best = cand[np.argmin(np.abs(ts1[cand].astype(np.int64) - ts0[i].astype(np.int64)))]
                    p0_used[i], p1_used[best] = True, True
                    matched_2d.append((idx0[i], idx1[best]))

        unmatched_p0 = idx0[~p0_used]
        unmatched_p1 = idx1[~p1_used]

        n2d, n1dx, n1dy = len(matched_2d), len(unmatched_p0), len(unmatched_p1)
        total = n2d + n1dx + n1dy

        out = eventsVMMnormal(size=total)
        out.durations, out.instrumentIDs = hits.durations.copy(), hits.instrumentIDs.copy()
        if total == 0:
            return out

        c_id     = np.empty(total, dtype='int64')
        c_coord0 = np.full(total, np.nan, dtype='float64')
        c_coord1 = np.full(total, np.nan, dtype='float64')
        c_ph0    = np.zeros(total, dtype='int64')
        c_ph1    = np.zeros(total, dtype='int64')
        c_mult0  = np.zeros(total, dtype='int64')
        c_mult1  = np.zeros(total, dtype='int64')
        c_span   = np.zeros(total, dtype='int64')
        ts_out, pulseT_out, prevPT_out = (np.zeros(total, dtype='int64') for _ in range(3))

        idx = 0
        for i0, i1 in matched_2d:
            c_id[idx], c_coord0[idx], c_coord1[idx] = p0['id'][i0], p0['coord'][i0], p1['coord'][i1]
            c_ph0[idx], c_ph1[idx]     = int(p0['adc'][i0]), int(p1['adc'][i1])
            c_mult0[idx], c_mult1[idx] = p0['mult'][i0], p1['mult'][i1]
            c_span[idx]                = max(p0['span'][i0], p1['span'][i1])
            ts_out[idx]                = min(p0['ts'][i0], p1['ts'][i1])
            pulseT_out[idx], prevPT_out[idx] = p0['pulseT'][i0], p0['prevPT'][i0]
            idx += 1

        for i0 in unmatched_p0:
            c_id[idx], c_coord0[idx] = p0['id'][i0], p0['coord'][i0]
            c_ph0[idx], c_mult0[idx], c_span[idx] = int(p0['adc'][i0]), p0['mult'][i0], p0['span'][i0]
            ts_out[idx], pulseT_out[idx], prevPT_out[idx] = p0['ts'][i0], p0['pulseT'][i0], p0['prevPT'][i0]
            idx += 1

        for i1 in unmatched_p1:
            c_id[idx], c_coord1[idx] = p1['id'][i1], p1['coord'][i1]
            c_ph1[idx], c_mult1[idx], c_span[idx] = int(p1['adc'][i1]), p1['mult'][i1], p1['span'][i1]
            ts_out[idx], pulseT_out[idx], prevPT_out[idx] = p1['ts'][i1], p1['pulseT'][i1], p1['prevPT'][i1]
            idx += 1

        timing_src = {'timeStamp': ts_out, 'pulseT': pulseT_out, 'prevPT': prevPT_out}
        computed = {
            'ID': c_id, 'coordinate0': c_coord0, 'coordinate1': c_coord1,
            'pulseHeight0': c_ph0, 'pulseHeight1': c_ph1,
            'mult0': c_mult0, 'mult1': c_mult1, 'clusterTimeSpan': c_span,
        }

        n_candidates = p0['count'] + p1['count']
        out.stats.update({
            'n_candidates': n_candidates, 'n_accepted': total, 'n_rejected': n_candidates - total,
            'n_accepted_2d': n2d, 'n_accepted_1dx': n1dx, 'n_accepted_1dy': n1dy,
            'n_rejected_overflow': 0, 'n_rejected_neighbour': n_candidates - total,
        })

        out.absorb(computed, timing_src)
        return out