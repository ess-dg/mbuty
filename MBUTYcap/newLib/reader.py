import os
import sys
import time
import ipaddress
 
import numpy as np
import pcapng as pg  # python-pcapng

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.colors import WARN, ERR, INFO, OK, RESET

from newLib.instrument_registry import (
    get_readout_spec,
    check_valid_data_stream,
    print_info_data_stream,
    match_data_stream_with_config,
)
from newLib.readout_containers import (
    readoutsVMMnormal,
    readoutsVMMclustered,
    readoutsR5560,
    readoutsBM,
    readoutsIBM,
    readoutsSKADI,
)

from newLib.hardware_decoders import (
    VMMNormalDecoder,
    VMMClusteredDecoder,
    R5560Decoder,
    SkadiDecoder,
    BMDecoder,
    IBMMonitorDecoder,
    
)

class BaseReader:
    """
    Abstract base class for all ESS detector data ingestion sources.

    Owns all shared state, the full packet processing pipeline, and every
    post-read diagnostic. Subclasses must implement these methods:

        run()                       — prepends source-specific allocation before
                                        calling super().run()
        _fetch_packets()            — generator that yields (packet_data, packet_length)
                                        for each iteration; all ESS parsing from cookie
                                        location onward is handled here in _read_packets().
        _run_warnings_and_checks()  — calls other functions to run the appropriate post 
                                        checks in the right order

    Containers
    ----------
    All six typed readout containers (VMM normal, VMM clustered, R5560, BM,
    IBM, SKADI) are allocated once by _allocate_all_containers(), trimmed to
    actual fill counts after reading, and exposed as public attributes:

        self.readouts_vmm_normal, self.readouts_vmm_clustered,
        self.readouts_r5560, self.readouts_bm,
        self.readouts_ibm, self.readouts_skadi

    Empty containers (no data routed to them) remain as zero-length arrays.
    """
    def __init__(
        self,
        parameters,
        config: dict,
    ):
        self._parameters = parameters

        # ---- physics / timing -----------------------------------------------
        self.ns_per_clock_tick    = float(parameters.clockTicks.NSperClockTick)
        self.time_resolution_type = parameters.VMMsettings.timeResolutionType
        self.operation_mode       = config.get('operationMode', 'normal')
        self.instrument_name      = config.get('instrumentName')
        self.detector_type        = config.get('detectorType')

        # ---- beam-monitor routing — extracted from config -------------------
        _mon          = config.get('Monitor', [{}])[0]
        self.mon_hw   = _mon.get('hardwareType', 'generic')
        self.mon_conn = _mon.get('connectionType', 'ring')
        self.mon_ring = int(_mon.get('Ring', 11))

        # ---- ESS header geometry (resolved during scan, not hardcoded) ------
        # Populated by extract_common_ess_header() on the first valid packet.
        # Consumed by _read_packets().
        self._ess_header_size:  int = None  # 30 (v0) or 32 (v>=1)
        self._main_header_size: int = None  # 42 for pcap file, 0 for kafka
        self._full_header_size: int = None  # _main_header_size + _ess_header_size

        # ---- per-packet record geometry -------------------------------------
        # singleReadoutSize is confirmed per packet via instrID lookup.
        # Default used only for the quick preallocation estimate.
        self._single_readout_size: int = 20
        self._roe_type: str = None  # 'VMM' | 'R5560' | 'SKADI' | 'BM'

        # ---- packet-level diagnostic counters (preserved exactly) -----------
        self._counter_packets            = 0
        self._counter_candidate_packets  = 0
        self._counter_valid_ess_packets  = 0
        self._counter_non_ess_packets    = 0
        self._counter_empty_ess_packets  = 0
        self._total_readout_count        = 0
        self._prealloc_length            = 0

        # ---- instrument IDs seen during scan pass ---------------------------
        self.instr_ids_found:  set = set()
        self.unknown_instr_ids: set = set()

        # ---- per-file accumulator lists (consumed by _run_warnings_and_checks) ----
        self._fw_versions_raw = []
        self._ip_tuples_raw   = []

        # ---- one-shot warning flags -----------------------------------------
        self._warned_bm = False  # BM data found in ring < 11

        # ---- debug toggle ---------------------------------------------------
        self.debug = False

        # ---- internal option: strip mode-mismatched / calib readouts --------
        self._remove_other_data_types = True
        # ---- loading method (pcapng only; None for all other sources) -------
        self.pcap_loading_method = None
        
        # ---- readout containers ---------------------------------------------
        # Intentionally not constructed here. _allocate_all_containers() builds
        # them exactly once after the scan pass resolves _prealloc_length.
        # Accessing a container before run() will raise AttributeError by design.
        self.readouts_vmm_normal    = None
        self.readouts_vmm_clustered = None
        self.readouts_r5560         = None
        self.readouts_bm            = None
        self.readouts_ibm           = None
        self.readouts_skadi         = None

        # ---- dual heartbeat timelines ---------------------------------------
        # heartbeats_all  : pulse_t from every valid ESS header (incl. empty packets)
        # heartbeats_data : pulse_t only from packets that carried decoded physics data
        # Both are None until run() completes.
        self.heartbeats_all:  np.ndarray = None
        self.heartbeats_data: np.ndarray = None
        
        
    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
 
    def run(self) -> None:
        """
        Full execution pipeline:
          1. Allocate all containers to prealloc_length
          2. Read all packets — ingest data and accumulate diagnostic metadata
            - Once filled, trim containers to actual fill counts
          3. Warnings and checks phase (FW, IP, time source, stream validation) 
            — all general diagnostics run here, after reading is complete
          4. Sorting and cleaning the containers
          5. Report instrument IDs found
        """
        self._allocate_all_containers(self._prealloc_length)
        self._read_packets()
        self._report_instrument_ids()
        self._check_time_settings()
        self._run_warnings_and_checks()
        for c in self._all_containers():
            c.clean_and_sort(self._parameters)
        
    # ------------------------------------------------------------------
    # Private: container allocation
    # ------------------------------------------------------------------
 
    def _allocate_all_containers(self, size: int) -> None:
        """
        Build all six typed containers to the given preallocated row count.
        Called exactly once from run() after _scan_and_allocate() resolves
        _prealloc_length. Containers are never rebuilt after this point.
        """
        self.readouts_vmm_normal    = readoutsVMMnormal(size=size)
        self.readouts_vmm_clustered = readoutsVMMclustered(size=size)
        self.readouts_r5560         = readoutsR5560(size=size)
        self.readouts_bm            = readoutsBM(size=size)
        self.readouts_ibm           = readoutsIBM(size=size)
        self.readouts_skadi         = readoutsSKADI(size=size)
 
    def _all_containers(self):
        """Convenience iterator over all six typed containers."""
        return (
            self.readouts_vmm_normal,
            self.readouts_vmm_clustered,
            self.readouts_r5560,
            self.readouts_bm,
            self.readouts_ibm,
            self.readouts_skadi,
        )


    # ------------------------------------------------------------------
    # Private: main read loop and post-read helpers
    # ------------------------------------------------------------------
        
    def _process_network_layer(self, packet_data: bytes, index_ess: int, ip_accumulator: list) -> None:
        pass

    def _read_packets(self) -> None:
        """
        Main packet ingestion loop — shared across all ingestion sources.
        Raw bytes for each iteration are provided by _fetch_next_packet(),
        which subclasses implement. Everything from ESS cookie location onward
        is identical regardless of source (pcapng file or Kafka stream).

          1.  Locates ESS cookie; skips non-ESS blocks.
          2.  Checks cookie position and ICMP flag.
          3.  Parses common ESS header via extract_common_ess_header().
          4.  Looks up (single_readout_size, hw) from the instrument registry.
          5.  Accumulates fw_version, ip_tuple, time_source_byte, instr_id into
              per-packet arrays — these are consumed by _run_warnings_and_checks().
          6.  Skips empty packets (payload == 0 bytes); records heartbeat only.
          7.  For non-empty packets: validates byte alignment, computes n_readouts,
              applies BM routing conditions, selects destination container and decoder.
          8.  Slices the container write window and calls decoder.decode().
          9.  Advances container.fill_count by n_readouts.
         10.  Records heartbeat (pulse_t) for this packet.
         11.  Emits progress ticker at _steps_for_progress intervals.
        """
        print('\n', end='')

        out_of_position_counter = np.int64(0)
        icmp_counter            = np.int64(0)
        other_counter           = np.int64(0)

        _heartbeats_all_list  = []
        _heartbeats_data_list = []

        vmm_normal_decoder    = VMMNormalDecoder(self.ns_per_clock_tick, self)
        vmm_clustered_decoder = VMMClusteredDecoder(self.ns_per_clock_tick, self)
        r5560_decoder         = R5560Decoder(self.ns_per_clock_tick, self)
        skadi_decoder         = SkadiDecoder(self.ns_per_clock_tick, self)
        bm_decoder            = BMDecoder(self.ns_per_clock_tick, self)
        ibm_decoder           = IBMMonitorDecoder(self.ns_per_clock_tick, self)

        self._steps_for_progress = max(1, int(self._counter_candidate_packets / 5) + 1)

        for packet_data, packet_length in self._fetch_packets():

            # ------------------------------------------------------------------
            # 1. ESS cookie location
            # ------------------------------------------------------------------
            index_ess = self.locate_ess_cookie(packet_data)
            if index_ess == -1:
                self._counter_non_ess_packets += 1
                continue

            self._counter_valid_ess_packets += 1
            if self._counter_valid_ess_packets == 1:
                print('loading ... [0%]', end=' ')

            # ------------------------------------------------------------------
            # 2. Cookie position check + ICMP gate
            # ------------------------------------------------------------------
            data_start_idx  = np.int64(self._ess_header_size + (index_ess - 2))
            icmp_byte_extra = np.int64(28)
            icmp_flag       = False

            if data_start_idx != self._full_header_size:
                out_of_position_counter += np.int64(1)
                if data_start_idx == self._full_header_size + icmp_byte_extra:
                    icmp_counter += np.int64(1)
                    icmp_flag = True
                else:
                    other_counter += np.int64(1)

            if icmp_flag:
                continue

            # ------------------------------------------------------------------
            # 3. Common ESS header decode
            # ------------------------------------------------------------------
            hdr = self.extract_common_ess_header(packet_data, index_ess)

            # Accumulate telemetry parameters dynamically on every valid packet step during decoding
            self._fw_versions_raw.append(np.int64(hdr['fw_version']))
            # For kafka this is just a simple pass - nothing happens
            self._process_network_layer(packet_data, index_ess, self._ip_tuples_raw)

            instr_id       = np.int64(hdr['instr_id'])
            pulse_t        = np.int64(hdr['pulse_time'])
            prev_pt        = np.int64(hdr['prev_pulse_time'])
            ess_length     = np.int64(hdr['ess_length'])
            data_start_idx = np.int64(hdr['data_start_idx'])

            # ------------------------------------------------------------------
            # 4. Instrument registry lookup
            # ------------------------------------------------------------------
            single_readout_size, hw = get_readout_spec(int(instr_id))
            single_readout_size = np.int64(single_readout_size)

            # Track known vs unknown IDs for post-read check_valid_data_stream.
            if hw is not None:
                self.instr_ids_found.add(int(instr_id))
            else:
                self.unknown_instr_ids.add(int(instr_id))

            # ------------------------------------------------------------------
            # 6. Empty-packet gate — heartbeat only
            # ------------------------------------------------------------------
            payload_bytes = np.int64(packet_length - data_start_idx)

            if payload_bytes == 0:
                self._counter_empty_ess_packets += 1
                self._dprint(f'empty packet No. {self._counter_empty_ess_packets}')
                _heartbeats_all_list.append(pulse_t)   # valid ESS header; record for all-HB
                # Not appended to _heartbeats_data_list — no physics data in this packet.
                if self._counter_valid_ess_packets % self._steps_for_progress == 0:
                    percents = int(round(
                        100.0 * self._counter_valid_ess_packets
                        / float(max(1, self._counter_candidate_packets)), 1
                    ))
                    print('[' + format(percents, '01d') + '%]', end=' ')
                continue

            # ------------------------------------------------------------------
            # 7. Byte alignment validation
            # ------------------------------------------------------------------
            if payload_bytes % single_readout_size != 0:
                print(f'\n{ERR}WARNING ---> something wrong with data bytes dimensions {RESET}')
                time.sleep(1)
                _heartbeats_all_list.append(pulse_t)   # valid ESS header; record for all-HB
                # Not appended to _heartbeats_data_list — malformed payload, no data written.
                continue

            n_readouts = int(payload_bytes // single_readout_size)
            self._total_readout_count += n_readouts

            self._dprint(
                f'ESS packet length {ess_length} bytes, packetLength {packet_length} bytes, '
                f'readouts in packet {n_readouts}'
            )

            # ------------------------------------------------------------------
            # 8. Ring extraction for BM routing (first readout byte, all packets
            #    from one device share the same ring so first byte is sufficient)
            # ------------------------------------------------------------------
            physical_ring = np.int64(
                int.from_bytes(packet_data[data_start_idx:data_start_idx + 1], byteorder='little')
            )
            ring = np.int64(physical_ring // 2)

            # ------------------------------------------------------------------
            # 9. BM routing conditions 
            # ------------------------------------------------------------------
            is_lemo_mode = (self.mon_conn == 'lemo' and ring >= 11)
            is_ring_mode = (self.mon_conn == 'ring'  and ring == self.mon_ring)
            is_bm_packet = is_lemo_mode or is_ring_mode

            # ------------------------------------------------------------------
            # 10. Select destination container and decoder
            # ------------------------------------------------------------------
            if is_bm_packet:
                if self.mon_hw == 'generic':
                    dest_container = self.readouts_bm
                    active_decoder = bm_decoder
                elif self.mon_hw == 'ibm':
                    dest_container = self.readouts_ibm
                    active_decoder = ibm_decoder
                else:
                    print(f'\n\t{ERR}ERROR: BM Data format not supported ---> Exiting ... \n{RESET}', end='')
                    time.sleep(2)
                    sys.exit()

            elif hw == 'VMM':
                if self.operation_mode == 'normal':
                    dest_container = self.readouts_vmm_normal
                    active_decoder = vmm_normal_decoder
                elif self.operation_mode == 'clustered':
                    dest_container = self.readouts_vmm_clustered
                    active_decoder = vmm_clustered_decoder
                else:
                    print(
                        f'\n\t{ERR}ERROR: Operation mode ({self.operation_mode} found) is not one of these: '
                        f'normal or clustered mode! --> Exiting!{RESET}',
                        end=''
                    )
                    time.sleep(2)
                    sys.exit()
                

            elif hw == 'BM':
                # instrID == BM but ring < 11 — treat as detector with one-shot warning.
                if not self._warned_bm:
                    print(f'\n {WARN}WARNING ---> BM data found in ring < 11, treated as a detector and HW generic (not IBM)! {RESET}')
                    self._warned_bm = True
                dest_container = self.readouts_bm
                active_decoder = bm_decoder

            elif hw == 'R5560':
                dest_container = self.readouts_r5560
                active_decoder = r5560_decoder

            elif hw == 'SKADI':
                dest_container = self.readouts_skadi
                active_decoder = skadi_decoder

            elif hw is None:
                # Unknown instrID — already added to unknown_instr_ids above.
                # Skip payload; no container write.
                _heartbeats_all_list.append(pulse_t)   # valid ESS header; record for all-HB
                # Not appended to _heartbeats_data_list — no data decoded.
                if self._counter_valid_ess_packets % self._steps_for_progress == 0:
                    percents = int(round(
                        100.0 * self._counter_valid_ess_packets
                        / float(max(1, self._counter_candidate_packets)), 1
                    ))
                    print('[' + format(percents, '01d') + '%]', end=' ')
                continue

            else:
                # hw value present but not handled — unsupported type (e.g. CPIX).
                print(f'\n\t{ERR}ERROR: Data format not supported ---> Exiting ... \n{RESET}', end='')
                time.sleep(2)
                sys.exit()

            # ------------------------------------------------------------------
            # 11. Slice the destination container write window
            # ------------------------------------------------------------------
            start      = np.int64(dest_container.fill_count)
            stop       = np.int64(start + n_readouts)
            dest_block = dest_container.matrix[start:stop]

            # ------------------------------------------------------------------
            # 12a. Broadcast packet-level fields onto the write window.
            #      These are identical for every readout in a packet and are
            #      set here so decode() does not need them as parameters.
            # ------------------------------------------------------------------
            dest_block['pulseT']  = pulse_t
            dest_block['prevPT']  = prev_pt
            dest_block['instrID'] = instr_id

            # ------------------------------------------------------------------
            # 12b. Decode readout-level fields into the write window.
            # ------------------------------------------------------------------
            active_decoder.decode(
                packet_data    = packet_data,
                data_start_idx = data_start_idx,
                n_readouts     = n_readouts,
                dest_block     = dest_block,
            )

            # ------------------------------------------------------------------
            # 13. Advance the container write pointer
            # ------------------------------------------------------------------
            dest_container.fill_count = int(stop)

            # ------------------------------------------------------------------
            # 14. Record heartbeat
            # ------------------------------------------------------------------
            _heartbeats_all_list.append(pulse_t)    # all valid ESS headers
            _heartbeats_data_list.append(pulse_t)   # data-carrying packets only
            
            # ------------------------------------------------------------------
            # 15. Progress ticker 
            # ------------------------------------------------------------------
            if self._counter_valid_ess_packets % self._steps_for_progress == 0:
                percents = int(round(
                    100.0 * self._counter_valid_ess_packets
                    / float(max(1, self._counter_candidate_packets)), 1
                ))
                print('[' + format(percents, '01d') + '%]', end=' ')

        # ---- end of scanner loop ------------------------------------------------

        print('[100%]')
        
        self._print_data_warnings(out_of_position_counter, icmp_counter, other_counter)
        
        self._dprint(
            f'\n All Packets {self._counter_packets}, '
            f'Candidates for Data {self._counter_candidate_packets} --> '
            f'Valid ESS {self._counter_valid_ess_packets} '
            f'(empty {self._counter_empty_ess_packets}), '
            f'NonESS {self._counter_non_ess_packets}'
        )

        # trim containers
        for c in self._all_containers():
            c.trim()

        if self.pcap_loading_method == 'quick':
            self._counter_candidate_packets = (
                self._counter_valid_ess_packets + self._counter_non_ess_packets
            )
            self._counter_packets = self._counter_candidate_packets

        print(
            f'\ndata loaded - found {self._total_readout_count} readouts - '
            f'Packets: all {self._counter_candidate_packets} --> '
            f'valid ESS {self._counter_valid_ess_packets} '
            f'(of which empty {self._counter_empty_ess_packets}), '
            f'nonESS {self._counter_non_ess_packets}'
        )

        self.heartbeats_all  = np.array(_heartbeats_all_list,  dtype='int64')
        self.heartbeats_data = np.array(_heartbeats_data_list, dtype='int64')


    def _print_data_warnings(self, out_of_position_counter, icmp_counter, other_counter) -> None:
        """
        Print end-of-read warnings for misaligned cookie positions and ICMP packets.
        """
        if out_of_position_counter != 0:
            print(
                f"\n{WARN}WARNING ---> ESS cookie was found {out_of_position_counter} times "
                f"not in position! Data does not start at byte 72 or 74 or 42 or 44! ... {RESET}"
            )
            if icmp_counter == out_of_position_counter:
                print(
                    f" {WARN}    ... ---> but it was an ICMP packet {icmp_counter} times "
                    f"-> skipping those packets. {RESET}"
                )
            else:
                print(
                    f" {ERR}    ... ---> found {icmp_counter} ICMP packets that can be skipped "
                    f"and {other_counter} times not an ICMP packet, BUT DATA MIGHT BE CORRUPTED. "
                    f"{RESET}"
                )

    def _run_warnings_and_checks(self) -> None:
        pass
        
    # ------------------------------------------------------------------    
    # Step 2 — Layer 1: ESS cookie location
    # ------------------------------------------------------------------
 
    def locate_ess_cookie(self, packet_data: bytes) -> int:
        """
        Scan the raw packet buffer for the 3-byte ESS cookie (0x45 0x53 0x53).
        Returns the byte index at which the cookie begins, or -1 if absent (not an ESS packet).
        """
        return packet_data.find(b'ESS')
 
    # ------------------------------------------------------------------
    # Step 2 — Layer 2b: ESS common header decode
    # ------------------------------------------------------------------
 
    def extract_common_ess_header(
        self,
        packet_data: bytes,
        index_ess:   int,
    ) -> dict:
        """
        Decode the ESS common header fields that flank the cookie, using
        only relative offsets from index_ess.
 
        ESS common header layout relative to index_ess
        -----------------------------------------------
        index_ess - 1          : firmware version byte (1 byte, little-endian)
        index_ess + 0..2       : cookie 'ESS' (already confirmed by caller)
        index_ess + 3          : instrument ID (1 byte, little-endian)
        index_ess + 4..5       : ESS payload length (2 bytes, little-endian)
        index_ess + 6          : padding / reserved (not extracted here)
        index_ess + 7          : time-source flags byte (1 byte, interpreted below)
        index_ess + 8..11      : pulse time HIGH word, seconds (4 bytes, LE)
        index_ess + 12..15     : pulse time LOW word, clock ticks (4 bytes, LE)
        index_ess + 16..19     : prev-pulse time HIGH word, seconds (4 bytes, LE)
        index_ess + 20..23     : prev-pulse time LOW word, clock ticks (4 bytes, LE)
 
        Firmware version → ESS header size
        -----------------------------------
        _ess_header_size and _full_header_size are updated on every call. This means
        the values always reflect the most recently seen packet, which is
        correct because the header size is a function of FW version and the
        FW version should be consistent across a file (a mismatch is warned
        by _check_fw_version_consistency in the scan pass).
 
            version == 0  →  _ess_header_size = 30
            version >= 1  →  _ess_header_size = 32
 
        Returns
        -------
        dict with keys:
            'fw_version'      : int  — firmware version byte
            'instr_id'        : int  — instrument identifier byte
            'ess_length'      : int  — ESS payload length in bytes
            'pulse_time'      : int  — current pulse timestamp (ns, int64)
            'prev_pulse_time' : int  — previous pulse timestamp (ns, int64)
            'data_start_idx'  : int  — byte index at which readout payload begins
        """
        # ---- firmware version → header size (updated on every packet) -------
        fw_version = int.from_bytes(
            packet_data[index_ess - 1 : index_ess], byteorder='little'
        )
 
        # Always overwrite 
        if fw_version == 0:
            self._ess_header_size = 30
        else:  # version >= 1
            self._ess_header_size = 32
 
        self._full_header_size = self._main_header_size + self._ess_header_size
 
        # ---- instrument ID --------------------------------------------------
        instr_id = np.int64(
            int.from_bytes(packet_data[index_ess + 3 : index_ess + 4], byteorder='little')
        )
 
        # ---- ESS payload length ---------------------------------------------
        ess_length = np.int64(
            int.from_bytes(packet_data[index_ess + 4 : index_ess + 6], byteorder='little')
        )
 
        # ---- pulse timestamps using high-precision integer arithmetic -------
        # HIGH words are in whole seconds -> convert straight to integer nanoseconds (x 1_000_000_000)
        pulse_hi_sec = int.from_bytes(packet_data[index_ess + 8 : index_ess + 12], byteorder='little')
        pulse_hi     = np.int64(pulse_hi_sec * 1_000_000_000)
 
        prev_hi_sec  = int.from_bytes(packet_data[index_ess + 16 : index_ess + 20], byteorder='little')
        prev_hi      = np.int64(prev_hi_sec * 1_000_000_000)
 
        # LOW words are in clock ticks -> multiply by float scalar and round to integer immediately
        pulse_lo_ticks = int.from_bytes(packet_data[index_ess + 12 : index_ess + 16], byteorder='little')
        pulse_lo       = np.int64(round(pulse_lo_ticks * self.ns_per_clock_tick))
 
        prev_lo_ticks  = int.from_bytes(packet_data[index_ess + 20 : index_ess + 24], byteorder='little')
        prev_lo        = np.int64(round(prev_lo_ticks * self.ns_per_clock_tick))
 
        # Combine components cleanly using pure integer addition
        pulse_time      = pulse_hi + pulse_lo
        prev_pulse_time = prev_hi + prev_lo
 
        # ---- data payload start index ---------------------------------------
        data_start_idx = np.int64(self._ess_header_size + (index_ess - 2))
 
        return {
            'fw_version'      : int(fw_version),
            'instr_id'        : instr_id,
            'ess_length'      : ess_length,
            'pulse_time'      : pulse_time,
            'prev_pulse_time' : prev_pulse_time,
            'data_start_idx'  : data_start_idx,
        }
 
    def _check_time_src(self, time_source_byte: int) -> None:
        """
        Decode and print the time-source status flags from the ESS header.
        Called once from _scan_and_allocate() after the scan loop, on the
        last valid ESS packet seen
 
        Bit layout (lower nibble only; upper 4 bits unused per ESS spec):
            bit 0 : timestamp source  (0 = MRF,      1 = local)
            bit 1 : sync source       (0 = MRF sync,  1 = local sync)
            bit 2 : sync method       (0 = internal,  1 = external TTL)
            bit 3 : status            (0 = OK,        1 = Error)
 
        """
        b = int(time_source_byte)
 
        src    = 'local timestamp' if (b & 0x1)       else 'MRF timestamp'
        iss    = 'local sync'      if (b & 0x2) >> 1  else 'MRF sync'
        sm     = 'external (TTL)'  if (b & 0x4) >> 2  else 'internal'
        status = 'Error'           if (b & 0x8) >> 3  else 'OK'
 
        print(
            f"checking time source --> source: {src}, "
            f"internal sync source: {iss}, "
            f"sync method: {sm}, "
            f"status: {status}"
        )
 
    def _check_fw_version_consistency(self, fw_versions: np.ndarray) -> None:
        """
        Warn if multiple firmware versions are found across the scan packets.
        Mirrors the original checkFWversionSetHeaders warning block exactly.
        Called by _scan_and_allocate() after the scan loop.
 
        Note: in 'quick' mode only one packet is scanned so only one version
        is ever seen; the mismatch branch will never fire in that mode.
        """
        print('checking RMM firmware version ', end='')
        try:
            if np.any(fw_versions != fw_versions[0]):
                print(
                    f'\n {ERR}WARNING ---> found different Firmware Versions in packets, '
                    f'use version 0 as default, data might be corrupted for other versions'
                    f'{RESET}'
                )
                time.sleep(1)
            else:
                print(f'--> version: {fw_versions[0]}')
        except Exception:
            print('--> unable to verify version.')
 
    # ------------------------------------------------------------------
    # Step 2 — post-read validation and time-resolution application
    # ------------------------------------------------------------------
 
    def _check_time_settings(self) -> None:
        """
        Validate operation_mode and time_resolution_type after reading.
        Exits immediately with the original error messages on invalid values.
        """
        if self.operation_mode not in ('normal', 'clustered'):
            print(
                f'\n\t{ERR}ERROR: Operation mode (found {self.operation_mode}) not set either to normal '
                f'or clustered ---> Exiting ... \n{RESET}',
                end=''
            )
            time.sleep(2)
            sys.exit()
 
        if self.time_resolution_type not in ('fine', 'coarse'):
            print(
                f'\n\t{ERR}ERROR: Time resolution (found {self.time_resolution_type}) not set either to fine '
                f'or coarse ---> Exiting ... \n{RESET}',
                end=''
            )
            time.sleep(2)
            sys.exit()
 
    def _report_instrument_ids(self) -> None:
        """
        Print one line per unique instrument ID seen during reading.
        prints "found X data stream - Y" for known IDs, nothing for unknown.
        Unknown IDs are reported separately.
        """
        for iid in sorted(self.instr_ids_found):
            print('\n---> ', end='')
            print_info_data_stream(int(iid))

        for iid in sorted(self.unknown_instr_ids):
            print(f'\n---> unknown instrument ID {iid} (0x{iid:02x})', end='')

        print('\n')
        
        
    def _analyse_heartbeats(self) -> None:
        """
        Internal metrics engine. Evaluates pulse timing deltas across both 
        heartbeats_all (all packets) and heartbeats_data (non-empty data packets) timelines.
        """
        try:
            # ---- Pass 1: Timing from all packets (including empty) -----------------------
            try:
                heartbeats_unique = np.unique(self.heartbeats_all)

                delta_time_all    = np.diff(heartbeats_unique - heartbeats_unique[0])
                idx_nonzero_all   = np.argwhere(delta_time_all > 0)
                delta_nonzero_all = delta_time_all[idx_nonzero_all]
                
                if len(delta_nonzero_all) == 0:
                    mean_delta_all     = np.nan
                    variance_delta_all = np.nan
                    mean_freq_all      = np.nan
                else:
                    mean_delta_all     = np.mean(delta_nonzero_all) / 1e9
                    variance_delta_all = np.var(delta_nonzero_all) / 1e9
                    mean_freq_all      = 1 / mean_delta_all

                if np.isnan(mean_delta_all) or mean_delta_all == 0:
                    print('\nNo Chopper found or all data is in one single Pulse Time')
                else:
                    print(
                        '\nHeartbeats Period     (all unique packets: %d)       '
                        'is %.6f s (variance %.6f s) --> frequency %.3f Hz'
                        % (len(delta_nonzero_all) + 1, mean_delta_all, variance_delta_all, mean_freq_all)
                    )
            except Exception:
                print(f'\t {WARN}WARNING: Unable to calculate timing/chopper frequency from all packets!{RESET}')
                time.sleep(2)

            # ---- Pass 2: Timing from data-carrying (non-empty) packets only --------------
            try:
                if len(self.heartbeats_data) == 0:
                    print(f'\t {WARN}WARNING: Packets might be all empty! Data timeline is empty. {RESET}')
                else:
                    delta_time_data    = np.diff(self.heartbeats_data - self.heartbeats_data[0])
                    idx_nonzero_data   = np.argwhere(delta_time_data > 0)
                    delta_nonzero_data = delta_time_data[idx_nonzero_data]
                    
                    if len(delta_nonzero_data) == 0:
                        mean_delta_data     = np.nan
                        variance_delta_data = np.nan
                        mean_freq_data      = np.nan
                    else:
                        mean_delta_data     = np.mean(delta_nonzero_data) / 1e9
                        variance_delta_data = np.var(delta_nonzero_data) / 1e9
                        mean_freq_data      = 1 / mean_delta_data
                    
                    if np.isnan(mean_delta_data) or mean_delta_data == 0:
                        print('\nNo Chopper found or all data is in one single Pulse Time')
                    else:
                        print(
                            f'Timing/Chopper Period (not empty unique packets: {len(delta_nonzero_data)+1:d}) '
                            f'is {mean_delta_data:.6f} s (variance {variance_delta_data:.6f} s) --> frequency {mean_freq_data:.3f} Hz'
                        )
            except Exception:
                print(f'\t {WARN}WARNING: Unable to calculate timing/chopper frequency from non-empty packets!{RESET}')
                time.sleep(2)

        except Exception:
            print(f'\t {WARN}WARNING: Unable to calculate timing/chopper frequency!{RESET}')
            time.sleep(2)
            
            
    def _check_invalid_tofs(self) -> None:
        """
         Accumulates Time-of-Flight validation metrics from all active hardware
         containers and prints a single unified status summary.
        """
        # Explicit Change: Extracted out of the main orchestrator block for modular cleanliness
        total_num_readouts = 0
        total_counter_1    = 0
        total_counter_2    = 0

        for c in self._all_containers():
            n_readouts, c1, c2 = c.check_invalid_tofs()
            total_num_readouts += n_readouts
            total_counter_1    += c1
            total_counter_2    += c2

        if total_num_readouts > 0:
            valid_tofs   = total_num_readouts - total_counter_2
            valid_valid  = total_num_readouts - total_counter_1
            valid_prev_p = total_counter_1 - total_counter_2
            
            print(
                f'\n {WARN}\t Readouts {total_num_readouts}: {valid_tofs} ToFs valid '
                f'({valid_valid} valid, {valid_prev_p} PrevPulse corrected) - invalid {total_counter_2} {RESET}'
            )
    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------
 
    def _dprint(self, msg: str) -> None:
        """Conditional debug print"""
        if self.debug:
            print(f"{msg}")
            
            
            
            

class PcapngFileReader(BaseReader):
    """
    Concrete reader for ESS pcapng network capture files.

    Extends BaseReader with pcapng-specific concerns: file validation, two
    preallocation strategies, Ethernet/IP/UDP header stripping, and IP
    network layer reporting.

    Loading methods (set via parameters.fileManagement.pcapLoadingMethod):
        'allocate' — full scan pass; counts readouts exactly from packet sizes.
                     Slower but exact; preferred for testing and analysis.
        'quick'    — single-packet scan; estimates from file_size / readout_size.
                     Slight overestimate, trimmed after reading. Faster for
                     routine data reduction.

    Public interface
    ----------------
    reader = PcapngFileReader(file_path, parameters, config)
    reader.run()
    """
    def __init__(
        self,
        file_path:  str,
        parameters,
        config:     dict,
    ):
        super().__init__(parameters, config)

        # ---- pcapng loading strategy ----------------------------------------
        self.pcap_loading_method = parameters.fileManagement.pcapLoadingMethod
        # Valid values: 'allocate' (exact, full scan) and 'quick' (estimated, single-packet scan).

        # ---- file path and size ---------------------------------------------
        self.file_path  = file_path
        self._file_size = os.path.getsize(self.file_path)
        self._validate_file()
        _filename = os.path.basename(self.file_path)
        print(f"{_filename} is {self._file_size / 1_000_000:.4f} Mbytes")

        # ---- pcapng-specific header geometry --------------------------------
        self._main_header_size = 42  # Ethernet/IP/UDP overhead
    
    
    def run(self) -> None:
        "Allocates memory then runs the main loop"
        self._scan_and_allocate()
        super().run()
    # ------------------------------------------------------------------
    # Private: validation helpers
    # ------------------------------------------------------------------
 
    def _validate_file(self) -> None:
        """Checks if file exists and prints error if not"""
        if not os.path.isfile(self.file_path):
            print(
                f"\n{ERR}ERROR: File not found: {self.file_path} "
                f"---> Exiting.{RESET}"
            )
            sys.exit()
   
    def _resolve_fw_version_and_header(self, packet_data: bytes, index_ess: int) -> None:
        """
        Read the firmware version byte from the first valid ESS packet and set
        _ess_header_size and _full_header_size accordingly. Silent — no print output.

        Version mapping:
            version == 0  →  _ess_header_size = 30
            version >= 1  →  _ess_header_size = 32

        Parameters
        ----------
        packet_data : bytes — raw bytes of the first valid ESS packet
        index_ess   : int   — byte index of the ESS cookie in packet_data
        """
        fw_version = int.from_bytes(
            packet_data[index_ess - 1 : index_ess], byteorder='little'
        )
        if fw_version == 0:
            self._ess_header_size = 30
        else:
            self._ess_header_size = 32

        self._full_header_size = self._main_header_size + self._ess_header_size
    
    # ------------------------------------------------------------------
    # Private: scan pass
    # ------------------------------------------------------------------
 
    def _scan_and_allocate(self) -> None:
        """
        Pre-scan pass: resolves _prealloc_length only.

        This method has one job: return a row count large enough to hold all
        readouts in the file. 

        The only diagnostic side-effect is resolving _ess_header_size, which
        requires peeking at the FW version byte of the first valid ESS packet.
        This is done silently via _resolve_fw_version_and_header() with no print
        output.

        'allocate' mode
        ---------------
        Iterates all blocks. For each ESS packet, computes exact readout count:
            n = (packet_size - _full_header_size) / _single_readout_size
        Sums these across all packets for an exact prealloc_length.

        'quick' mode
        ------------
        Reads only the first valid ESS packet to resolve header sizes, then
        estimates from file size:
            prealloc_length = file_size / _single_readout_size
        This overestimates; unused rows are trimmed after reading
        _counter_candidate_packets is also set to this estimate so the progress
        ticker in _read_packets() has a valid denominator; corrected post-read.
        """
        if self.pcap_loading_method not in ('allocate', 'quick'):
            print(
                f'{WARN}WARNING: Wrong data loading option: select either quick or allocate '
                f'--> setting it to allocate method!{RESET}'
            )
            self.pcap_loading_method = 'allocate'

        elif self.pcap_loading_method == 'allocate':
            print('pcap loading method: allocate')
        else:
            print('pcap loading method: quick')

        print('allocating memory...', end='')

        ff      = open(self.file_path, 'rb')
        scanner = pg.FileScanner(ff)

        packet_sizes        = []
        header_resolved     = False
        max_ess_for_quick   = 1
        ess_packets_scanned = np.int64(0)

        # Track the fallback packet marker for time source checking
        self._scan_last_packet_data = None
        self._scan_last_index_ess   = None

        try:
            for block in scanner:

                self._counter_packets += 1
                if self._counter_packets == 4 or self._counter_packets % 5000 == 0:
                    print('.', end='')

                try:
                    packet_size = block.packet_len
                    packet_data = block.packet_data
                except Exception:
                    self._dprint(
                        f'--> other packet found No. '
                        f'{self._counter_packets - self._counter_candidate_packets}'
                    )
                    continue
                
                self._counter_candidate_packets += 1
                index_ess = self.locate_ess_cookie(packet_data)
                if index_ess == -1:
                    continue

                ess_packets_scanned += np.int64(1)

                # Resolve FW version and header size from the first ESS packet only.
                if not header_resolved:
                    self._resolve_fw_version_and_header(packet_data, index_ess)
                    header_resolved = True

                # Track the last packet seen for checkTimeSrc
                self._scan_last_packet_data = packet_data
                self._scan_last_index_ess   = index_ess

                if self.pcap_loading_method == 'allocate':
                    packet_sizes.append(np.int64(packet_size))

                if self.pcap_loading_method == 'quick' and ess_packets_scanned >= max_ess_for_quick:
                    break

        except Exception as e:
            print(
                f"\n{ERR}ERROR: {e} ---> probably data is being created and "
                f"file not closed -> exiting.{RESET}"
            )
            time.sleep(2)
            sys.exit()

        ff.close()

        if self.pcap_loading_method == 'allocate':
            sizes_arr      = np.array(packet_sizes, dtype='int64')
            readout_counts = (sizes_arr - self._full_header_size) / self._single_readout_size
            total_readouts = np.sum(readout_counts[readout_counts >= 0])
            self._prealloc_length = int(round(total_readouts))

        else:  # 'quick'
            self._prealloc_length           = int(round(self._file_size / self._single_readout_size))
            self._counter_candidate_packets = self._prealloc_length
            self._counter_packets           = self._prealloc_length

        self._dprint(f'prealloc_length {self._prealloc_length}')

    # ------------------------------------------------------------------
    # Network layer extraction and ICMP gate
    # ------------------------------------------------------------------
 
    def _process_network_layer(
        self,
        packet_data: bytes,
        index_ess:   int,
        ip_accumulator: list,
    ) -> None:
        """
        Extract connection metadata using relative backward offsets from the
        ESS cookie index. All slices are expressed as (index_ess - N) so that
        variable network padding (e.g. VLAN tags) never shifts the extraction
        window — only index_ess itself absorbs any such variation.
 
        Relative offset map (all measured backwards from index_ess):
        ---------------------------------------------------------------
        The packet layout arriving at index_ess looks like this in memory,
        reading left-to-right toward index_ess:
 
          [ Ethernet (14) | IP header (20) | UDP header (8) | 2-byte pad | ESS... ]
                                                                          ^
                                                                      index_ess
 
        Working back from index_ess:
          index_ess - 2        : start of 2-byte pad before cookie (not used)
          index_ess - 2 - 8    : start of UDP header (8 bytes)
          index_ess - 2 - 8 - 20 : start of IP header (20 bytes)
 
        Within the IP header (20 bytes starting at index_ess - 30):
          Protocol byte  : offset +9  inside IP header
                         → absolute: index_ess - 30 + 9 = index_ess - 21
          Src IP         : offset +12 → bytes [index_ess-18 : index_ess-14]
          Dst IP         : offset +16 → bytes [index_ess-14 : index_ess-10]
 
        Within the UDP header (8 bytes starting at index_ess - 10):
          Src port       : bytes [index_ess-10 : index_ess-8]
          Dst port       : bytes [index_ess-8  : index_ess-6]
 
        ICMP check:
          IP protocol byte == 1 means ICMP. The RMM firmware occasionally sends
          ping packets that embed ESS data but must be discarded. We detect this
          here so the caller can skip payload extraction cleanly.
 
        Parameters
        ----------
        packet_data     : raw bytes of the current pcapng block
        index_ess       : byte index returned by locate_ess_cookie()
        ip_accumulator  : list to which (src_ip, src_port, dst_ip, dst_port)
                          tuples are appended during the scan pass; consumed
                          by _print_ip_report() after the scan loop.
        """
        try:
            # ---- IPv4 source and destination ------------------------------------
            src_ip = str(ipaddress.IPv4Address(packet_data[index_ess - 18 : index_ess - 14]))
            dst_ip = str(ipaddress.IPv4Address(packet_data[index_ess - 14 : index_ess - 10]))
    
            # ---- UDP ports ------------------------------------------------------
            src_port = np.int64(int.from_bytes(packet_data[index_ess - 10 : index_ess - 8], byteorder='big'))
            dst_port = np.int64(int.from_bytes(packet_data[index_ess - 8  : index_ess - 6], byteorder='big'))
    
            # ---- accumulate for post-scan unique-connection report --------------
            ip_accumulator.append((src_ip, int(src_port), dst_ip, int(dst_port)))
        except Exception:
            pass
 
 
    def _print_ip_report(self, ip_accumulator: list) -> None:
        """
        Deduplicate the connection tuples gathered during the scan pass and
        print the unique-connection map in the original diagnostic format.
 
        Called once by _scan_and_allocate() after the scan loop completes.
        In 'allocate' mode, all candidate packets contribute.
        In 'quick' mode, only the first valid ESS packet contributes.
        """
        print("checking IPs:ports ...")
 
        arr = np.array(
            [(s_ip, s_p, d_ip, d_p) for s_ip, s_p, d_ip, d_p in ip_accumulator],
            dtype=[('src_ip', 'U40'), ('src_port', 'i8'),
                   ('dst_ip', 'U40'), ('dst_port', 'i8')],
        )
        unique_rows, counts = np.unique(arr, return_counts=True)
 
        for kk, (conn, num) in enumerate(zip(unique_rows, counts)):
            print(
                f"\tConnection {kk} found ({num} pkts) --> "
                f"Source: {conn['src_ip']}:{conn['src_port']} | "
                f"Dest: {conn['dst_ip']}:{conn['dst_port']}"
            )
        print()
    
    
    def _fetch_packets(self):
        """
        Generator: opens the pcapng file and yields (packet_data, packet_length)
        for every block. Handles network layer IP extraction as a side effect.
        Consumed by BaseReader._read_packets().
        """
        ff      = open(self.file_path, 'rb')
        scanner = pg.FileScanner(ff)

        try:
            for block in scanner:
                try:
                    packet_length = np.int64(block.packet_len)
                    packet_data   = block.packet_data
                except Exception:
                    self._dprint('--> other packet found')
                    continue
                
                yield packet_data, packet_length
        finally:
            ff.close()

    def _run_warnings_and_checks(self) -> None:
        """
        Dedicated post-read stream validation phase.
        Aggregates all network, firmware, timing, and instrument stream 
        diagnostics to run once all file data is completely loaded.
        """
        # 1. Firmware version consistency check across the full file run
        fw_versions_arr = np.array(self._fw_versions_raw, dtype='int64')
        if len(fw_versions_arr) > 0:
            self._check_fw_version_consistency(fw_versions_arr)

        # 2. Hardware time source flag decoding
        if self._scan_last_packet_data is not None:
            ts_byte = int(self._scan_last_packet_data[self._scan_last_index_ess + 7])
            self._check_time_src(ts_byte)

        # 3. Deduplicated IP and Port network map report
        if self._ip_tuples_raw:
            self._print_ip_report(self._ip_tuples_raw)

        # 4. Valid instrument stream verification lookup
        check_valid_data_stream(self.instr_ids_found, self.unknown_instr_ids)
        
        # 5. Match config parameters with actual data 
        match_data_stream_with_config(self.instrument_name, self.detector_type, self.instr_ids_found)
        
        # 6. Heartbeat timing analysis print out
        self._analyse_heartbeats()
        
        # 7. Global Time-of-Flight validation summary pass
        self._check_invalid_tofs()
        
        # Flush internal telemetry accumulation collections to free memory overhead after validation finishes
        self._fw_versions_raw.clear()
        self._ip_tuples_raw.clear()
           
# =============================================================================
# Module-level diagnostic utility functions
# =============================================================================

def check_which_ring_fen_hybrid_in_file(file_path: str, parameters, config: dict) -> None:
    """
    Debug utility: read a pcapng file and print all unique (Ring, Fen, Hybrid)
    hardware coordinate tables detected across both normal and clustered streams.
    """
    reader = PcapngFileReader(file_path, parameters, config)
    reader.run()
    filename = os.path.basename(file_path)
    
    print(f"\nRings, Fens and Hybrids in file: {filename}")
    counter = 0
    
    for container in (reader.readouts_vmm_normal, reader.readouts_vmm_clustered):
        if container.fill_count == 0:
            continue
        
        unique_table = container.get_ring_fen_hybrid_table()
        for (ring, fen, hybrid) in unique_table:
            counter += 1
            print(f"\tNo. {counter}:     Ring {int(ring)}, Fen {int(fen)}, Hybrid {int(hybrid)}")         
            
            
if __name__ == '__main__':
    print(f'{WARN}TEST WARNING COLOR{RESET}')
    import time
    from types import SimpleNamespace
    import json 
    t_start = time.time()

    # ------------------------------------------------------------------ #
    # Configuration — edit these for your environment
    # ------------------------------------------------------------------ #
    file_path = r"C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap\data\20260611_083055_pkts100_Test-full_00000.pcapng"

    with open(r"C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap\config\AMOR26.json") as json_file:
        config = json.load(json_file)
    
    # Minimal stub — mirrors only the attributes PcapngFileReader reads
    parameters = SimpleNamespace(
        acqMode       = 'pcap',
        clockTicks    = SimpleNamespace(NSperClockTick = 11.356860963629653),
        VMMsettings   = SimpleNamespace(timeResolutionType = 'coarse'),
        fileManagement= SimpleNamespace(pcapLoadingMethod  = 'allocate'),
    )

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    reader = PcapngFileReader(
        file_path  = file_path,
        parameters = parameters,
        config     = config,
    )

    reader.run()

    # ------------------------------------------------------------------ #
    # Grab containers
    # ------------------------------------------------------------------ #
    vmm_normal    = reader.readouts_vmm_normal
    vmm_clustered = reader.readouts_vmm_clustered
    r5560         = reader.readouts_r5560
    bm            = reader.readouts_bm
    ibm           = reader.readouts_ibm
    skadi         = reader.readouts_skadi

    # ------------------------------------------------------------------ #
    # Quick sanity print
    # ------------------------------------------------------------------ #
    print(f'\nVMM normal    : {vmm_normal.fill_count} readouts')
    print(f'VMM clustered : {vmm_clustered.fill_count} readouts')
    print(f'R5560         : {r5560.fill_count} readouts')
    print(f'BM            : {bm.fill_count} readouts')
    print(f'IBM           : {ibm.fill_count} readouts')
    print(f'SKADI         : {skadi.fill_count} readouts')

    if vmm_normal.fill_count > 0:
        print('\nFirst VMM normal readout:')
        print(vmm_normal.matrix[0])

    print(f'\n Data Loading Completed in {time.time() - t_start:.2f} s')