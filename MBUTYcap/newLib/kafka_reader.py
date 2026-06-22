#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kafka_reader.py
===============
Kafka stream ingestion for ESS detector data.

Mirrors the public interface of PcapngFileReader — same BaseReader inheritance,
same container layout, same run() entry point. The only difference is how raw
ESS packet bytes are obtained: polled from a Kafka broker (or the bytesGen
testing simulator) rather than read from a pcapng file.
"""

import sys
import time
import numpy as np
import os
from confluent_kafka import Consumer, TopicPartition

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.reader import BaseReader
from newLib.libKafkaRawReadoutMessage import RawReadoutMessage
import newLib.libKafkaRX as krx
from newLib.colors import WARN, ERR, RESET

from newLib.instrument_registry import (
    check_valid_data_stream,
    match_data_stream_with_config,
)

# =============================================================================
# Testing simulator
# =============================================================================
def load_test_packet() -> bytes:
    """Load a single saved ESS packet for Kafka pipeline testing."""
    _here = os.path.dirname(os.path.abspath(__file__))
    for path in (
        os.path.join(_here, 'data'),
        os.path.join(_here, '..', 'data'),
    ):
        candidate = os.path.join(path, 'outputBinary1pkt')
        try:
            with open(candidate, 'rb') as f:
                return f.read()[42:]
        except OSError:
            continue
    raise FileNotFoundError("Cannot find 'outputBinary1pkt' in ./data/ or ../data/")

# =============================================================================
# KafkaReader
# =============================================================================

class KafkaReader(BaseReader):
    """
    Concrete reader for live ESS Kafka streams.

    Extends BaseReader with Kafka-specific concerns: broker connection, topic
    validation, partition assignment, FlatBuffers unpacking, and a fixed-count
    polling loop. A local testing mode (testing=True) replaces the broker poll
    with the bytesGen file simulator so the full pipeline can be exercised
    without a live cluster.

    Pre-allocation
    --------------
    Memory is estimated upfront as:
        n_packets * readouts_per_packet
    where readouts_per_packet is derived from a single-readout-size constant
    (20 bytes) and the ESS header size (32 bytes, v1 upper bound). This is a
    slight overestimate; containers are trimmed to actual fill counts after
    reading, identical to the pcapng 'quick' path.

    Public interface
    ----------------
    reader = KafkaReader(parameters, config, broker, topic, n_packets)
    reader.run()
    """

    # ESS header size used for pre-allocation estimate — v1 upper bound (32 bytes)
    # guarantees we never under-allocate regardless of actual firmware version.
    _ESS_HEADER_ESTIMATE: int = 32
    _SINGLE_READOUT_SIZE: int = 20
    _READOUTS_PER_PACKET: int = 447  # matches original estimate

    def __init__(
        self,
        parameters,
        config:     dict,
        testing:    bool = False,
    ):
        super().__init__(parameters, config)

        # ---- Kafka connection parameters ------------------------------------
        self._broker    = getattr(getattr(parameters, 'kafkaSettings', None), 'broker',    '127.0.0.1:9092')
        self._topic     = getattr(getattr(parameters, 'kafkaSettings', None), 'topic',     'freia_debug')
        self._n_packets = getattr(getattr(parameters, 'kafkaSettings', None), 'numOfPackets', 1)
        self._testing   = testing

        # ---- Kafka has no network layer — ESS bytes start at offset 0 ------
        self._main_header_size = 0
        self._kafka_ts_byte = None  # resolved from first packet in _fetch_packets

        # ---- pre-allocation estimate (mirrors original formula) -------------
        estimated_bytes = (
            self._n_packets
            * (self._SINGLE_READOUT_SIZE * self._READOUTS_PER_PACKET
               + self._ESS_HEADER_ESTIMATE)
        )

        if testing:
            print(f'{WARN}WARNING ---> Not streaming but testing locally enabled!{RESET}')
            print(
                f'Simulating streaming {self._n_packets} packets '
                f'({estimated_bytes / 1000:.1f} kbytes) from kafka'
            )
        else:
            print(
                f'Streaming {self._n_packets} packets '
                f'({estimated_bytes / 1000:.1f} kbytes) from kafka'
            )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Allocates containers from n_packets estimate then delegates to
        BaseReader.run() for the shared read → validate → sort pipeline.
        """
        self._prealloc_length            = self._n_packets * self._READOUTS_PER_PACKET
        self._counter_candidate_packets  = self._n_packets
        self._counter_packets            = self._n_packets
        self._steps_for_progress         = max(1, int(self._n_packets / 20) + 1)

        print('allocating memory ... ', end='')
        super().run()

    # ------------------------------------------------------------------
    # Packet source — Kafka poll or local simulator
    # ------------------------------------------------------------------

    def _fetch_packets(self):
        """
        Generator: yields (packet_data: bytes, packet_length: int) for each
        of the n_packets iterations. Connects to the Kafka broker (or the
        bytesGen simulator in testing mode) and polls one message at a time.

        On connection failure or unknown topic the method prints a clear error
        and exits — matching original behaviour.
        """
        if not self._testing:
            consumer = self._connect()
        else:
            consumer = None

        t_start = time.time()

        try:
            for n in range(self._n_packets):
                try:
                    if not self._testing:
                        # Poll until a message arrives, printing a wait notice
                        # after 3 s of silence (matches original behaviour).
                        while (msg := consumer.poll(timeout=0.5)) is None:
                            time.sleep(0.2)
                            if time.time() - t_start > 3:
                                print(
                                    f'\nWaiting for next consumer poll on '
                                    f'topic {self._topic}'
                                )
                                t_start = time.time()

                        ar52        = RawReadoutMessage.GetRootAs(msg.value(), 0)
                        packet_data = ar52.RawDataAsNumpy().tobytes()

                    else:
                        packet_data = load_test_packet()

                    packet_length = len(packet_data)

                except Exception:
                    self._dprint('--> other packet found')
                    print(f'{ERR}ERROR ---> streaming failed ... exiting ...{RESET}')
                    time.sleep(2)
                    sys.exit()

                # Resolve ESS header size from first packet — Kafka has no
                # scan pass so _ess_header_size is None until here.
                # Supports both v0 (30 bytes) and v1 (32 bytes) firmware.
                if n == 0:
                    index_ess = self.locate_ess_cookie(packet_data)
                    if index_ess != -1:
                        fw_version             = int.from_bytes(packet_data[index_ess - 1 : index_ess], byteorder='little')
                        self._ess_header_size  = 30 if fw_version == 0 else 32
                        self._full_header_size = self._main_header_size + self._ess_header_size
                        self._kafka_ts_byte    = int(packet_data[index_ess + 7])

                self._dprint(f'\npacket {n + 1} of {self._n_packets} received')
                yield packet_data, packet_length

        finally:
            if consumer is not None:
                consumer.close()

    def _run_warnings_and_checks(self) -> None:
        """
        Post-read validation for Kafka streams. Runs only the checks that are
        meaningful for a live stream — no IP report, no TOF validation, no
        cross-packet FW consistency (FW version resolved from first packet only).
        """
        # 1. Firmware version consistency 
        fw_versions_arr = np.array(self._fw_versions_raw, dtype='int64')
        if len(fw_versions_arr) > 0:
            self._check_fw_version_consistency(fw_versions_arr)

        # 2. Time source — resolved from first packet in _fetch_packets()
        #    Store ts_byte there and use it here
        if self._kafka_ts_byte is not None:
            self._check_time_src(self._kafka_ts_byte)

        # 3. Valid instrument stream verification
        check_valid_data_stream(self.instr_ids_found, self.unknown_instr_ids)

        # 4. Match config parameters with actual data
        match_data_stream_with_config(self.instrument_name, self.detector_type, self.instr_ids_found)
        
        # 5. Heartbeat timing analysis print out
        self._analyse_heartbeats()
        
        # 6. Global Time-of-Flight validation summary pass
        self._check_invalid_tofs()
        
        # Flush accumulators
        self._fw_versions_raw.clear()
        self._ip_tuples_raw.clear()

    # ------------------------------------------------------------------
    # Private: broker connection helper
    # ------------------------------------------------------------------

    def _connect(self) -> Consumer:
        """
        Connects to the Kafka broker, blocks until metadata is available,
        validates the requested topic exists, and assigns all its partitions.
        Returns a ready Consumer.
        """
        kafka_config = krx.generate_config(self._broker, staging=True)
        consumer     = Consumer(kafka_config)

        metadata = krx.get_metadata_blocking(consumer)
        print('---> connection to kafka successful!')

        if self._topic not in metadata.topics:
            print(
                f'{ERR}ERROR ---> Topic "{self._topic}" does not exist.{RESET}\n'
                f'Available topics:'
            )
            for t in metadata.topics:
                print(f'  - {t}')
            print('\nExiting ...')
            time.sleep(2)
            sys.exit()

        topic_partitions = [
            TopicPartition(self._topic, p)
            for p in metadata.topics[self._topic].partitions
        ]
        consumer.assign(topic_partitions)

        return consumer
    
if __name__ == '__main__':
    import time
    import json
    from types import SimpleNamespace
    
    t_start = time.time()

    # ------------------------------------------------------------------ #
    # Configuration — mirrors the pcapng test block in reader.py
    # ------------------------------------------------------------------ #
    with open(r"C:\Projects\dg_MultiBlade_MBUTY_original\MBUTYcap\config\AMOR26.json") as json_file:
        config = json.load(json_file)

    # Minimal stub — only attributes KafkaReader / BaseReader reads
    parameters = SimpleNamespace(
        clockTicks     = SimpleNamespace(NSperClockTick      = 11.356860963629653),
        VMMsettings    = SimpleNamespace(timeResolutionType  = 'coarse'),
        sortByTimeStampsONOFF = False,
    )

    # ------------------------------------------------------------------ #
    # Run — testing=True uses bytesGen simulator, no broker needed
    # ------------------------------------------------------------------ #
    reader = KafkaReader(
        parameters = parameters,
        config     = config,
        testing    = True,
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

    print(f'\nKafka stream completed in {time.time() - t_start:.2f} s')