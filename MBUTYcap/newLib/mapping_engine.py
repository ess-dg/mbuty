#!/usr/bin/env python3
"""
mapping_engine.py — Stateless, vectorized ESS neutron detector geometry mapper.

Pipeline position: readouts → [mapping_engine] → hits

Contract
--------
Each public mapper class takes a fully populated (and trimmed) readouts
container plus the raw JSON config dict, and returns a populated hits
container of the matching type.  No element-by-element loops, no sequential
appends.  Every coordinate assignment is a single vectorized NumPy pass.

Supported detector types
------------------------
MBMapper      — Multi-Blade VMM normal mode   (readoutsVMMnormal  → hitsVMMnormal)
MBClustMapper — Multi-Blade VMM clustered     (readoutsVMMclustered → hitsVMMclustered)
He3Mapper     — Helium-3 CAEN R5560 tubes     (readoutsR5560       → hitsR5560)
MonitorMapper — Beam Monitor (generic or IBM)  (readoutsVMMnormal   → hitsBM | hitsIBM)

Usage
-----
    config = json.load(open('AMOR26.json'))
    hits   = MBMapper.map(readouts_vmm_normal, config)
    mon    = MonitorMapper.map(readouts_vmm_normal, config)
"""

import numpy as np
import os 
import sys

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
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


# ---------------------------------------------------------------------------
# Internal helpers — not part of the public API
# ---------------------------------------------------------------------------

def _build_topology_arrays(topology: list) -> tuple:
    """
    Convert the config topology list into four parallel NumPy int64 arrays
    for fully vectorized lookup.

    Returns
    -------
    ids, rings, fens, hybrids : np.ndarray, shape (N,), dtype int64
        Parallel arrays; row k describes topology entry k.
    """
    ids     = np.array([e['ID']     for e in topology], dtype='int64')
    rings   = np.array([e['ring']   for e in topology], dtype='int64')
    fens    = np.array([e['fen']    for e in topology], dtype='int64')
    hybrids = np.array([e['hybrid'] for e in topology], dtype='int64')
    return ids, rings, fens, hybrids


def _assign_ids_vectorized(
    readout_matrix,
    ids: np.ndarray,
    rings: np.ndarray,
    fens: np.ndarray,
    hybrids: np.ndarray,
) -> tuple:
    """
    Map every readout row to a cassette/tube/unit ID by matching its
    (ring, fen, hybrid) triple against the topology lookup arrays.

    Strategy: build a (n_readouts, n_topology) boolean match matrix in one
    broadcast pass, then argmax along axis=1 to get the topology index for
    each row.  Rows that match nothing stay at ID = -1 (already the default
    from np.full in hits.__init__).

    Returns
    -------
    assigned_ids  : int64 array, shape (n_readouts,)
        Physical ID for each readout row; -1 where no match.
    topo_idx      : int64 array, shape (n_readouts,)
        Index into the topology array for each row (drives cassette offset);
        -1 where no match.
    valid_mask    : bool array, shape (n_readouts,)
        True where a topology match was found.
    """
    r = readout_matrix['ring']    # (n,)
    f = readout_matrix['fen']     # (n,)
    h = readout_matrix['hybrid']  # (n,)

    # Broadcast: compare each readout against every topology entry
    # match shape: (n_readouts, n_topology)
    match = (
        (r[:, None] == rings[None, :]) &
        (f[:, None] == fens[None, :])  &
        (h[:, None] == hybrids[None, :])
    )

    valid_mask = match.any(axis=1)           # (n,) bool
    topo_idx   = np.where(valid_mask, match.argmax(axis=1), -1)  # (n,) int

    assigned_ids = np.where(valid_mask, ids[topo_idx], np.int64(-1))

    return assigned_ids.astype('int64'), topo_idx.astype('int64'), valid_mask


def _derive_adapter_type(wire_asic: int) -> str:
    """
    Adapter type is implicit in which ASIC carries the wires.
    WireASIC == 1, StripASIC == 0  →  'reverse'  (the AMOR26 case)
    WireASIC == 0, StripASIC == 1  →  'straight'
    """
    return 'reverse' if wire_asic == 1 else 'straight'


def _copy_timing(src_matrix, dst_matrix, row_slice=slice(None)) -> None:
    """Copy timing base fields from readout rows into hits rows."""
    dst_matrix['timeStamp'] = src_matrix['timeStamp'][row_slice]
    dst_matrix['pulseT']    = src_matrix['pulseT'][row_slice]
    dst_matrix['prevPT']    = src_matrix['prevPT'][row_slice]
    dst_matrix['instrID']   = src_matrix['instrID'][row_slice]


# ---------------------------------------------------------------------------
# MBMapper — Multi-Blade VMM normal mode
# ---------------------------------------------------------------------------

class MBMapper:
    """
    Maps readoutsVMMnormal → hitsVMMnormal for Multi-Blade detectors.

    Channel coordinate rules (from legacy libMapping.mapChannels):

    Adapter 'reverse'  (WireASIC == 1):
        Wires  : ASIC == wireASIC,  channel in [16, 47]  →  index = channel - 16
        Strips : ASIC == stripASIC, channel in [0,  63]  →  index = 63 - channel

    Adapter 'straight' (WireASIC == 0):
        Wires  : ASIC == wireASIC,  channel in [16, 47]  →  index = 31 - (channel - 16)
        Strips : ASIC == stripASIC, channel in [0,  63]  →  index = channel

    Global wire offset (from legacy mapChannelsGlob):
        index_global = index_local + cassette_position_in_config * num_wires
        where cassette_position_in_config is the 0-based rank of the cassette
        in the topology list (not the ID value itself).
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMnormal:
        """
        Parameters
        ----------
        readouts : readoutsVMMnormal
            Fully populated and trimmed VMM normal readout container.
        config : dict
            Raw JSON config dict (output of json.load).

        Returns
        -------
        hitsVMMnormal
            Populated, trimmed hits container. ID == -1 rows have been removed.
        """
        topology    = config['topology']
        wire_asic   = int(config['channelMapping'][0]['wireASIC'])
        strip_asic  = int(config['channelMapping'][0]['stripASIC'])
        num_wires   = int(config['wires'])
        adapter     = _derive_adapter_type(wire_asic)

        if wire_asic == strip_asic:
            raise ValueError(
                'CONFIG ERROR: wireASIC and stripASIC are the same — '
                'wires and strips cannot share an ASIC.'
            )

        ids, rings, fens, hybrids = _build_topology_arrays(topology)

        n = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: topology lookup — assign cassette IDs and position index ---
        assigned_ids, topo_idx, valid_mask = _assign_ids_vectorized(
            src, ids, rings, fens, hybrids
        )

        # --- Step 2: channel coordinate masks ---
        asic    = src['asic']
        channel = src['channel']

        wire_asic_mask  = asic == np.int64(wire_asic)
        strip_asic_mask = asic == np.int64(strip_asic)
        wire_ch_mask    = (channel >= 16) & (channel <= 47)
        strip_ch_mask   = (channel >= 0)  & (channel <= 63)

        is_wire  = valid_mask & wire_asic_mask  & wire_ch_mask
        is_strip = valid_mask & strip_asic_mask & strip_ch_mask

        # --- Step 3: compute local channel coordinate ---
        # Allocate a single working array for index; -1 for anything unresolved.
        local_index = np.full(n, -1, dtype='int64')
        plane       = np.full(n, -1, dtype='int64')

        if adapter == 'reverse':
            local_index[is_wire]  = channel[is_wire] - 16
            local_index[is_strip] = np.int64(63) - channel[is_strip]
        else:  # straight
            local_index[is_wire]  = np.int64(31) - (channel[is_wire] - 16)
            local_index[is_strip] = channel[is_strip]

        plane[is_wire]  = np.int64(0)
        plane[is_strip] = np.int64(1)

        # --- Step 4: apply global wire offset ---
        # cassette_rank = position of this row's cassette in the topology list.
        # Only wire-plane rows get the offset; strip coordinates are cassette-local.
        cassette_rank = np.where(valid_mask, topo_idx, np.int64(0))
        wire_offset   = (cassette_rank * np.int64(num_wires)).astype('int64')

        global_index = local_index.copy()
        global_index[is_wire] = local_index[is_wire] + wire_offset[is_wire]

        # --- Step 5: pack into hits container ---
        h = hitsVMMnormal(size=n)
        h.fill_count = n

        _copy_timing(src, h.matrix)
        h.matrix['ID']    = assigned_ids
        h.matrix['plane'] = plane
        h.matrix['index'] = global_index
        h.matrix['adc']   = src['adc']

        h.durations = readouts.durations.copy()

        # --- Step 6: discard rows with no topology match ---
        h.remove_invalid()
        h.trim()

        _report_unmapped_cassettes(assigned_ids, ids, 'cassette')

        return h


# ---------------------------------------------------------------------------
# MBClustMapper — Multi-Blade VMM clustered mode
# ---------------------------------------------------------------------------

class MBClustMapper:
    """
    Maps readoutsVMMclustered → hitsVMMclustered for Multi-Blade detectors.

    In clustered mode each readout row already contains a pre-paired
    wire+strip event: channel0/adc0/mult0 and channel1/adc1/mult1.
    Which slot carries wires vs strips is determined by wireASIC:

    WireASIC == 1  ('reverse'):
        Wire   slot → channel1, adc1, mult1  →  index0 = channel1 - 16
        Strip  slot → channel0, adc0, mult0  →  index1 = 63 - channel0

    WireASIC == 0  ('straight'):
        Wire   slot → channel0, adc0, mult0  →  index0 = 31 - (channel0 - 16)
        Strip  slot → channel1, adc1, mult1  →  index1 = channel1

    Global wire offset applied to index0 exactly as in normal mode.
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsVMMclustered:
        topology   = config['topology']
        wire_asic  = int(config['channelMapping'][0]['wireASIC'])
        num_wires  = int(config['wires'])
        adapter    = _derive_adapter_type(wire_asic)

        ids, rings, fens, hybrids = _build_topology_arrays(topology)

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        # --- Step 1: topology lookup ---
        assigned_ids, topo_idx, valid_mask = _assign_ids_vectorized(
            src, ids, rings, fens, hybrids
        )

        # --- Step 2: unpack wire and strip raw channels from the correct slots ---
        if adapter == 'reverse':
            # WireASIC == 1 → wires are in slot 1 (channel1, adc1, mult1)
            wire_ch   = src['channel1']
            wire_adc  = src['adc1']
            wire_mult = src['mult1']
            # strips in slot 0
            strip_ch   = src['channel0']
            strip_adc  = src['adc0']
            strip_mult = src['mult0']
        else:
            # WireASIC == 0 → wires are in slot 0 (channel0, adc0, mult0)
            wire_ch   = src['channel0']
            wire_adc  = src['adc0']
            wire_mult = src['mult0']
            # strips in slot 1
            strip_ch   = src['channel1']
            strip_adc  = src['adc1']
            strip_mult = src['mult1']

        # --- Step 3: channel-to-coordinate transform ---
        wire_in_range  = (wire_ch  >= 16) & (wire_ch  <= 47)
        strip_in_range = (strip_ch >= 0)  & (strip_ch <= 63)

        if adapter == 'reverse':
            local_wire_index = np.where(
                valid_mask & wire_in_range,
                wire_ch - np.int64(16),
                np.int64(-1)
            )
            local_strip_index = np.where(
                valid_mask & strip_in_range,
                np.int64(63) - strip_ch,
                np.int64(-1)
            )
        else:
            local_wire_index = np.where(
                valid_mask & wire_in_range,
                np.int64(31) - (wire_ch - np.int64(16)),
                np.int64(-1)
            )
            local_strip_index = np.where(
                valid_mask & strip_in_range,
                strip_ch,
                np.int64(-1)
            )

        # --- Step 4: global wire offset ---
        cassette_rank = np.where(valid_mask, topo_idx, np.int64(0))
        wire_offset   = (cassette_rank * np.int64(num_wires)).astype('int64')

        global_wire_index = np.where(
            local_wire_index >= 0,
            local_wire_index + wire_offset,
            np.int64(-1)
        )

        # --- Step 5: pack into hits container ---
        h = hitsVMMclustered(size=n)
        h.fill_count = n

        _copy_timing(src, h.matrix)
        h.matrix['ID']     = assigned_ids
        h.matrix['index0'] = global_wire_index
        h.matrix['index1'] = local_strip_index
        h.matrix['adc0']   = wire_adc
        h.matrix['adc1']   = strip_adc
        h.matrix['mult0']  = wire_mult
        h.matrix['mult1']  = strip_mult

        h.durations = readouts.durations.copy()

        h.remove_invalid()
        h.trim()

        _report_unmapped_cassettes(assigned_ids, ids, 'cassette')

        return h


# ---------------------------------------------------------------------------
# He3Mapper — Helium-3 CAEN R5560 tubes
# ---------------------------------------------------------------------------

class He3Mapper:
    """
    Maps readoutsR5560 → hitsR5560.

    Topology lookup maps (ring, fen, tube) to a physical tube ID.
    The R5560 readout uses 'tube' in place of 'hybrid' — both are stored in
    the same structured field name, so the generic _assign_ids_vectorized
    helper works without modification because we use the 'hybrid' column name
    that readoutsR5560 maps its tube field into at read time.

    counter1, ampA, ampB, counter2 are carried through unmodified.
    index carries the physical tube ID (same as the topology ID lookup result).
    """

    @staticmethod
    def map(readouts, config: dict) -> hitsR5560:
        topology = config['topology']
        ids, rings, fens, hybrids = _build_topology_arrays(topology)

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        assigned_ids, _topo_idx, valid_mask = _assign_ids_vectorized(
            src, ids, rings, fens, hybrids
        )

        h = hitsR5560(size=n)
        h.fill_count = n

        _copy_timing(src, h.matrix)
        h.matrix['ID']       = assigned_ids
        # For He3 the physical position IS the tube ID from topology
        h.matrix['index']    = np.where(valid_mask, assigned_ids, np.int64(-1))
        h.matrix['counter1'] = src['counter1']
        h.matrix['ampA']     = src['ampA']
        h.matrix['ampB']     = src['ampB']
        h.matrix['counter2'] = src['counter2']

        h.durations = readouts.durations.copy()

        h.remove_invalid()
        h.trim()

        _report_unmapped_cassettes(assigned_ids, ids, 'tube')

        return h


# ---------------------------------------------------------------------------
# MonitorMapper — Beam Monitor (generic or IBM)
# ---------------------------------------------------------------------------

class MonitorMapper:
    """
    Maps the monitor stream out of a VMM normal readout container into
    hitsBM (hardwareType == 'generic') or hitsIBM (hardwareType == 'ibm').

    The monitor occupies Ring >= 11 in the readout stream.  The specific
    (ring, channel) pair to accept is declared in config['monitor'][0].

    Detection logic (mirrors legacy mapMonitor):
    1. Build a mask for the exact (ring, channel) pair from config.
    2. Scan Ring >= 11 rows for any (ring, channel) pairs actually present.
    3. If the configured pair is found → map those rows.
    4. If a different single pair is found → warn, flag not found.
    5. If nothing at all in Ring >= 11 → warn, flag not found.

    Returns
    -------
    (hits_container, found_flag) : tuple
        hits_container is hitsBM or hitsIBM depending on hardwareType.
        found_flag is True if monitor data was successfully mapped.
    """

    @staticmethod
    def map(readouts, config: dict) -> tuple:
        mon_cfg          = config['monitor'][0]
        mon_id           = int(mon_cfg['ID'])
        hardware_type    = str(mon_cfg['hardwareType']).lower()
        mon_ring         = int(mon_cfg['ring'])
        mon_channel      = int(mon_cfg['channel'])

        n   = readouts.fill_count
        src = readouts.matrix[:n]

        ring_col    = src['ring']
        channel_col = src['channel']

        # Exact selection from config
        target_mask = (ring_col == np.int64(mon_ring)) & \
                      (channel_col == np.int64(mon_channel))

        # All potential monitor rows (Ring >= 11)
        mon_band_mask = ring_col >= np.int64(11)

        # Unique (ring, channel) pairs found in the monitor band
        if np.any(mon_band_mask):
            mon_pairs = np.unique(
                np.column_stack([
                    ring_col[mon_band_mask],
                    channel_col[mon_band_mask]
                ]),
                axis=0
            )
        else:
            mon_pairs = np.empty((0, 2), dtype='int64')

        found_flag  = False
        hits_out    = MonitorMapper._make_empty_container(hardware_type)

        if np.any(target_mask):
            if len(mon_pairs) > 1:
                print(
                    f'\t \033[1;33mWARNING: Found {len(mon_pairs)} monitor '
                    f'sources in data. MBUTY supports only one Monitor. '
                    f'Mapping according to config, but data contains '
                    f'(Ring, Channel): {mon_pairs.tolist()}\033[1;37m'
                )

            hits_out  = MonitorMapper._fill(src, target_mask, hardware_type, mon_id)
            found_flag = True
            print('\033[1;36mMapping Monitor ... \033[1;37m')

        elif len(mon_pairs) == 1:
            wrong_ring, wrong_ch = mon_pairs[0]
            print(
                f'\t \033[1;33mWARNING: mismatch → one monitor candidate found '
                f'but it is NOT the one selected in config file. '
                f'Data contains Ring {wrong_ring} and Channel {wrong_ch}.\033[1;37m'
            )

        else:
            print('\t \033[1;33mNo MONITOR data found in data file\033[1;37m')

        hits_out.durations = readouts.durations.copy()
        return hits_out, found_flag

    @staticmethod
    def _make_empty_container(hardware_type: str):
        if hardware_type == 'ibm':
            return hitsIBM(size=0)
        return hitsBM(size=0)

    @staticmethod
    def _fill(src, mask, hardware_type: str, mon_id: int):
        """
        Pack selected rows into the correct monitor hits container.

        hitsBM  fields: ID, timeStamp, pulseT, prevPT, instrID, type, channel, adc, posX, posY
        hitsIBM fields: ID, timeStamp, pulseT, prevPT, instrID, type, channel, debug, adc, mcaSum

        The VMM normal readout carries adc directly.  The remaining
        monitor-specific fields (posX, posY for BM; debug, mcaSum for IBM)
        have no equivalent in a VMM readout stream, so they are left at the
        -1 sentinel established by hits.__init__.  This is correct behaviour:
        the monitor is a diagnostic stream and those fields are only populated
        when the readout hardware itself provides them.
        """
        count = int(np.sum(mask))
        rows  = src[mask]

        if hardware_type == 'ibm':
            h = hitsIBM(size=count)
        else:
            h = hitsBM(size=count)

        h.fill_count = count

        h.matrix['ID']        = np.int64(mon_id)
        h.matrix['timeStamp'] = rows['timeStamp']
        h.matrix['pulseT']    = rows['pulseT']
        h.matrix['prevPT']    = rows['prevPT']
        h.matrix['instrID']   = rows['instrID']
        h.matrix['adc']       = rows['adc']

        # channel is available from the VMM readout
        h.matrix['channel']   = rows['channel']

        h.trim()
        return h


# ---------------------------------------------------------------------------
# Convenience dispatcher
# ---------------------------------------------------------------------------

def map_detector(readouts, config: dict):
    """
    Top-level convenience function.  Inspects config['detectorType'] and
    config['operationMode'] to select and invoke the correct mapper.

    Returns the populated hits container.  For monitor extraction, call
    MonitorMapper.map() separately — it consumes the same readouts object.
    """
    det_type = config.get('detectorType', '')
    op_mode  = config.get('operationMode', 'normal')

    if det_type in ('MB', 'MG'):
        if op_mode == 'clustered':
            return MBClustMapper.map(readouts, config)
        return MBMapper.map(readouts, config)

    if det_type == 'He3':
        return He3Mapper.map(readouts, config)

    raise ValueError(
        f'map_detector: unsupported detectorType "{det_type}". '
        f'Call the appropriate mapper class directly for non-standard types.'
    )


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------

def _report_unmapped_cassettes(
    assigned_ids: np.ndarray,
    config_ids: np.ndarray,
    unit_label: str = 'cassette',
) -> None:
    found_ids = np.unique(assigned_ids[assigned_ids != -1])
    missing   = np.setdiff1d(config_ids, found_ids)

    if len(missing) > 0:
        id_list = ' '.join(str(x) for x in missing)
        print(f"\t {WARN}WARNING: {unit_label} IDs: {id_list} not found in data file. Mapping skipped for those.{RESET}")
        
        
        
        
if __name__ == '__main__':
    # =============================================================================
    # STANDALONE COMPONENT TEST HARNESS
    # =============================================================================
    import json

    # Quick inline mock for readouts structure to avoid tracking files for a dry run
    class MockReadoutsNormal:
        def __init__(self):
            # Create a mock structured array matching readoutsVMMnormal specifications
            dtype = [
                ('timeStamp', 'int64'), ('pulseT', 'int64'), ('prevPT', 'int64'),
                ('instrID', 'int64'), ('ring', 'int64'), ('fen', 'int64'),
                ('hybrid', 'int64'), ('asic', 'int64'), ('channel', 'int64'),
                ('adc', 'int64')
            ]
            # Mock 4 events: 
            # 1. Valid Cassette 0, Wire ASIC 1, Channel 20 (Local Wire index 4)
            # 2. Valid Cassette 1, Strip ASIC 0, Channel 10 (Local Strip index 53)
            # 3. Valid Cassette 2, Wire ASIC 1, Channel 16 (Local Wire index 0)
            # 4. Invalid hardware coordinate (Ring 5 doesn't exist in config)
            self.matrix = np.array([
                (1000, 100, 50, 1, 0, 0, 0, 1, 20, 250),
                (2000, 100, 50, 1, 0, 0, 1, 0, 10, 300),
                (3000, 100, 50, 1, 1, 0, 0, 1, 16, 180),
                (4000, 100, 50, 1, 5, 9, 9, 1, 30, 999) 
            ], dtype=dtype)
            self.fill_count = 4
            self.durations = np.array([100], dtype='int64')

    print(f"{INFO}--- Starting Standalone Mapping Engine Verification Harness ---{RESET}")

    # Dummy configuration block matching AMOR26 reverse adapter specifications
    mock_config = {
        "detectorType": "MB",
        "operationMode": "normal",
        "wires": 32,
        "strips": 64,
        "channelMapping": [{"wireASIC": 1, "stripASIC": 0}],
        "topology": [
            {"ID": 100, "ring": 0, "fen": 0, "hybrid": 0},
            {"ID": 101, "ring": 0, "fen": 0, "hybrid": 1},
            {"ID": 102, "ring": 1, "fen": 0, "hybrid": 0}
        ],
        "monitor": [
            {"ID": 99, "hardwareType": "generic", "connectionType": "ring", "ring": 11, "channel": 0}
        ]
    }

    readouts = MockReadoutsNormal()
    
    print(f"{INFO}Piping mock readouts through vectorized mapping dispatcher...{RESET}\n")
    try:
        hits_out = map_detector(readouts, mock_config)
        
        print("-------------------------------------------------------------")
        print(f"{OK}Mapping successful! Structured Output Matrix rows:{RESET}")
        for idx, row in enumerate(hits_out.matrix[:hits_out.fill_count]):
            print(f" Hit {idx} -> ID: {row['ID']}, Plane: {row['plane']}, Index: {row['index']}, ADC: {row['adc']}")
        print("-------------------------------------------------------------")
        
        # Verify that row 4 was stripped due to invalid configuration coordinates
        if hits_out.fill_count == 3:
            print(f"{OK}Success: Vector filter dropped unmapped dataset rows automatically.{RESET}")
        else:
            print(f"{WARN}Warning: Expected 3 valid rows post-trim, found {hits_out.fill_count}{RESET}")

    except Exception as e:
        print(f"{ERR}Execution Failure: {e}{RESET}")
        sys.exit(1)