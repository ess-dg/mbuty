#!/usr/bin/env python3
"""
VMM Slow-Control ADC Parser v2 (Fixed & Optimized)
Enhanced parser that tracks VMM configuration to determine measurement types.
Parses both WRITE packets (configuration) and READ replies (ADC data) 
using robust python-pcapng block scanning.
"""

import struct
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple
from collections import defaultdict
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
import pcapng as pg  # python-pcapng
import numpy as np

@dataclass
class VMMConfig:
    """Tracks VMM configuration state for measurement interpretation."""
    sm5_sm0: int = 0          # Monitoring output select (0-63)
    scmx: int = 0             # Channel mux control
    sdt: int = 0              # Threshold DAC setting (combined, scaled)
    sdt_lo4: int = 0          # sdt low nibble, from sp1 bits[28:31] (less significant half)
    sdt_hi4: int = 0          # sdt high nibble, from sp2 bits[0:3] (more significant half)
    sdp10: int = 0            # Pulser DAC setting
    polarity_sp: int = 0      # Polarity bit
    timestamp: float = 0.0    # Last update time


class ADCReading(NamedTuple):
    """Represents a single ADC measurement with measurement context."""
    ring: int
    fen: int
    vmm: int
    measurement_type: str     # 'threshold', 'pedestal', 'pulser_dac', 'temperature'
    channel: Optional[int]    # For per-channel measurements (threshold/pedestal)
    dac_setting: Optional[int]  # Requested DAC code for chip-wide sweeps (pulser_dac/threshold_dac)
    adc_mv: float
    raw_data: int
    address: int
    packet_index: int         # Sequence in PCAP
    # --- Decoded register decomposition (sp1XX / sp2XX / vmm_chNNXX), as
    # they stood at the moment this reading was taken. Included so each
    # reading is traceable back to the settings that produced it. ---
    scmx: int = 0              # sp2: channel mux control (0=chip-wide, 1=per-channel)
    sm5_sm0: int = 0           # sp2: monitoring select / active channel (0-63)
    sdt: int = 0               # sp1+sp2 combined: threshold DAC setting
    sdp10: int = 0             # sp1: pulser DAC setting
    polarity_sp: int = 0       # sp2 bit 31: polarity
    smx: Optional[int] = None  # channel register bit 18: 0=pedestal, 1=threshold (None if unresolved)


class VMMSlowControlParserV2:
    """Enhanced parser tracking VMM configuration state."""
    
    # Slow-control packet headers
    READ_REQUEST = 0xE55C0001  
    READ_REPLY = 0xE55C0002    
    WRITE_REQUEST = 0xE55C0003
    WRITE_REPLY = 0xE55C0004 
    
    # Register offsets
    VMM_ADC_OFFSET_MIN = 0x1A0
    VMM_ADC_OFFSET_MAX = 0x1CC
    VMM_CH_OFFSET_MIN = 0x260
    VMM_CH_OFFSET_MAX = 0xE5F
    
    def __init__(self):
        self.adc_readings: List[ADCReading] = []
        self.vmm_configs: Dict[Tuple[int, int, int], VMMConfig] = defaultdict(VMMConfig)
        self.channel_smx: Dict[Tuple[int, int, int, int], int] = {}
        self.packet_index = 0
    
    def parse_pcap(self, pcap_file: str) -> List[ADCReading]:
        """
        Parse PCAP file using python-pcapng FileScanner in a single pass,
        processing packets in file order. Config state (VMMConfig) is updated
        as WRITE packets are encountered, and READ replies are decoded using
        whatever config is current AT THAT POINT in the stream.
        """
        self.adc_readings.clear()
        self.packet_index = 0

        print(f"Reading {pcap_file}...")
        
        with open(pcap_file, 'rb') as f:
            scanner = pg.FileScanner(f)
            for block in scanner:
                try:
                    packet_data = block.packet_data
                except AttributeError:
                    continue

                idx = packet_data.find(b'\xe5\x5c')
                if idx == -1 or (len(packet_data) - idx) < 4:
                    continue

                header = int.from_bytes(packet_data[idx:idx+4], byteorder='big')
                payload = packet_data[idx+4:]

                if header == self.WRITE_REQUEST:
                    # 8 bytes per entry: u32 addr, u32 data
                    for i in range(0, len(payload) - 7, 8):
                        addr, value = struct.unpack('>II', payload[i:i+8])
                        self._process_config_write(addr, value)
                elif header == self.WRITE_REPLY:
                    # 12 bytes per entry: u32 addr, u32 data, u32 status
                    for i in range(0, len(payload) - 11, 12):
                        addr, value, status = struct.unpack('>III', payload[i:i+12])
                        self._process_config_write(addr, value)
                elif header == self.READ_REPLY:
                    # 12 bytes per entry: u32 addr, u32 data, u32 status
                    for i in range(0, len(payload) - 11, 12):
                        addr, value, status = struct.unpack('>III', payload[i:i+12])
                        if status == 0:
                            addr_offset = addr & 0xFFF
                            if self.VMM_ADC_OFFSET_MIN <= addr_offset <= self.VMM_ADC_OFFSET_MAX:
                                reading = self._decode_adc_reading(addr, value)
                                if reading:
                                    self.adc_readings.append(reading)
                                    self.packet_index += 1

        return self.adc_readings
    
    def _process_config_write(self, addr: int, value: int):
        """Process a configuration register write to update VMM state using correct register block strides."""
        ring = (addr >> 28) & 0xF
        fen = (addr >> 23) & 0x1F
        offset = addr & 0xFFF
        
        # Channel register block (0x260-0xE5F): 12 VMMs x 64 channels, one
        # 4-byte register per channel. Layout is CHANNEL-major / VMM-minor
        # (register naming is vmm_ch<channel><vmm>, e.g. vmm_ch0000 = channel
        # 0 vmm 0, vmm_ch0001 = channel 0 vmm 1, ..., vmm_ch0100 = channel 1 vmm 0
        # Bit 18 (SMX) of the written value selects whether that channel's 
        # register is being used for a pedestal (SMX=0) or threshold (SMX=1)
        # measurement
        if self.VMM_CH_OFFSET_MIN <= offset <= self.VMM_CH_OFFSET_MAX:
            reg_index = (offset - self.VMM_CH_OFFSET_MIN) // 4
            channel = reg_index // 12
            ch_vmm = reg_index % 12
            if 0 <= ch_vmm <= 11:
                smx = (value >> 18) & 1
                self.channel_smx[(ring, fen, ch_vmm, channel)] = smx
            return

        vmm = None
        sp_num = None
        
        if 0xe60 <= offset <= 0xe8c:
            vmm = (offset - 0xe60) // 4
            sp_num = 0                   # "sp0" block
        elif 0xe90 <= offset <= 0xebc:
            vmm = (offset - 0xe90) // 4
            sp_num = 1                   # "sp1" block  -> vmm_global_bank1_sp1XX
        elif 0xec0 <= offset <= 0xeec:
            vmm = (offset - 0xec0) // 4
            sp_num = 2                   # "sp2" block  -> vmm_global_bank1_sp2XX
            
        if vmm is not None and 0 <= vmm <= 11:
            key = (ring, fen, vmm)
            cfg = self.vmm_configs[key]
            
            if sp_num == 0:
                # sp0 block (0xe60-0xe8c) - contents not yet decoded/needed.
                pass
            elif sp_num == 1:
                # sp1 (0xe90 block): bits [16:25] are the pulser DAC setting (sdp10).
                cfg.sdp10 = (value >> 16) & 0x3FF

                # sdt (threshold DAC) is split across sp1 and sp2:
                #   sp1 bits [28:31] -> low nibble
                #   sp2 bits [0:3]   -> high nibble
                #   sdt = ((high << 4) | low) * 4
                cfg.sdt_lo4 = (value >> 28) & 0xF
                cfg.sdt = ((cfg.sdt_hi4 << 4) | cfg.sdt_lo4) * 4
            elif sp_num == 2:
                # sp2 (0xec0 block): bit 18 is scmx (0=chip-wide, 1=per-channel
                # mode), bits [19:24] are sm5_sm0 (monitoring select / active
                # channel 0-63).
                cfg.scmx = (value >> 18) & 1
                cfg.sm5_sm0 = (value >> 19) & 0x3F

                # sdt high nibble - see sp_num==1 branch above
                cfg.sdt_hi4 = value & 0xF
                cfg.sdt = ((cfg.sdt_hi4 << 4) | cfg.sdt_lo4) * 4

                # polarity_sp: bit 31. If positive polarity, threshold mV
                # readings are corrected as 1200 - adc_result.
                cfg.polarity_sp = (value >> 31) & 1
    
    def _decode_adc_reading(self, addr: int, raw_data: int) -> Optional[ADCReading]:
        """Decode an ADC reading using current configuration state."""
        ring = (addr >> 28) & 0xF
        fen = (addr >> 23) & 0x1F
        offset = addr & 0xFFF
        
        vmm = (offset - self.VMM_ADC_OFFSET_MIN) // 4
        if vmm > 11:
            return None
        
        # Get VMM config state
        key = (ring, fen, vmm)
        cfg = self.vmm_configs[key]
        
        # Convert raw ADC to mV: (value & 0xFFFF) >> 4
        adc_mv = float((raw_data & 0xFFFF) >> 4)  
        
        # Determine measurement type from configuration
        measurement_type = 'unknown'
        channel = None
        dac_setting = None
        smx = None
        
        if cfg.scmx == 0:
            if cfg.sm5_sm0 == 1:
                measurement_type = 'pulser_dac'
                dac_setting = cfg.sdp10
            elif cfg.sm5_sm0 == 2:
                measurement_type = 'threshold_dac'
                dac_setting = cfg.sdt
            elif cfg.sm5_sm0 == 3:
                measurement_type = 'bandgap_reference'
            elif cfg.sm5_sm0 == 4:
                measurement_type = 'temperature'
        else:
            channel = cfg.sm5_sm0
            smx = self.channel_smx.get((ring, fen, vmm, channel))
            if smx == 0:
                measurement_type = 'pedestal'
            elif smx == 1:
                measurement_type = 'threshold'
            else:
                # No channel-register write observed yet for this
                # (vmm, channel) - can't tell pedestal from threshold.
                measurement_type = 'channel_measurement'

        # Apply polarity correction for threshold measurements (both the
        # chip-wide threshold_dac sweep and the per-channel threshold
        # reading
        if measurement_type in ('threshold_dac', 'threshold') and cfg.polarity_sp == 1:
            adc_mv = 1200.0 - adc_mv
        
        # Temperature conversion
        if measurement_type == 'temperature':
            adc_mv = (725.0 - adc_mv) / 1.85 
        
        return ADCReading(
            ring=ring,
            fen=fen,
            vmm=vmm,
            measurement_type=measurement_type,
            channel=channel,
            dac_setting=dac_setting,
            adc_mv=adc_mv,
            raw_data=raw_data,
            address=addr,
            packet_index=self.packet_index,
            scmx=cfg.scmx,
            sm5_sm0=cfg.sm5_sm0,
            sdt=cfg.sdt,
            sdp10=cfg.sdp10,
            polarity_sp=cfg.polarity_sp,
            smx=smx
        )
    
    def group_by_vmm(self) -> Dict[Tuple[int,int,int], List[ADCReading]]:
        """Group all readings by (ring, fen, vmm)."""
        grouped = defaultdict(list)
        for reading in self.adc_readings:
            key = (reading.ring, reading.fen, reading.vmm)
            grouped[key].append(reading)
        return dict(grouped)
    
    def group_by_measurement_type(self) -> Dict[str, List[ADCReading]]:
        """Group all readings by measurement type."""
        grouped = defaultdict(list)
        for reading in self.adc_readings:
            grouped[reading.measurement_type].append(reading)
        return dict(grouped)
    
    def export_json(self, output_file: str):
        """Export readings to JSON."""
        by_type = self.group_by_measurement_type()
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_readings': len(self.adc_readings),
            'readings_by_type': {}
        }
        
        for mtype, readings in by_type.items():
            output['readings_by_type'][mtype] = {
                'count': len(readings),
                'readings': [
                    {
                        'ring': r.ring,
                        'fen': r.fen,
                        'vmm': r.vmm,
                        'channel': r.channel,
                        'dac_setting': r.dac_setting,
                        'adc_mv': round(r.adc_mv, 2),
                        'address': f'0x{r.address:08x}',
                        # Register decomposition (sp1XX / sp2XX / vmm_chNNXX)
                        # as it stood when this reading was taken.
                        'registers': {
                            'scmx': r.scmx,
                            'sm5_sm0': r.sm5_sm0,
                            'sdt': r.sdt,
                            'sdp10': r.sdp10,
                            'polarity_sp': r.polarity_sp,
                            'smx': r.smx
                        }
                    }
                    for r in readings
                ]
            }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\nExported to {output_file}")
    
    def print_summary(self):
        """Print summary of parsed data."""
        grouped_vmm = self.group_by_vmm()
        grouped_type = self.group_by_measurement_type()
        
        print(f"\n{'='*60}")
        print(f"VMM Slow-Control ADC Measurements Summary")
        print(f"{'='*60}")
        print(f"Total readings: {len(self.adc_readings)}")
        print(f"Unique VMMs: {len(grouped_vmm)}")
        print(f"\nReadings by measurement type:")
        
        for mtype in sorted(grouped_type.keys()):
            readings = grouped_type[mtype]
            print(f"  {mtype:20s}: {len(readings):4d} readings")
        
        print(f"\n{'Ring':<6} {'FEN':<6} {'VMM':<6} {'Readings':<12} {'Avg mV':<12}")
        print(f"{'-'*54}")
        
        for (ring, fen, vmm) in sorted(grouped_vmm.keys()):
            readings = grouped_vmm[(ring, fen, vmm)]
            avg_mv = sum(r.adc_mv for r in readings) / len(readings)
            print(f"{ring:<6} {fen:<6} {vmm:<6} {len(readings):<12} {avg_mv:<12.2f}")


    def plot_results(self):
        """
        Display calibration plots from the parsed readings in interactive
        pop-up windows (no files saved):
          - pedestal / threshold (per-channel, scmx==1, resolved via the SMX
            bit in the channel register): one line per (ring, fen, vmm),
            channel (0-63) on x, ADC mV on y. 'channel_measurement' is also
            plotted the same way as a fallback, for scmx==1 readings whose
            channel register write (and therefore SMX/pedestal-vs-threshold
            label) wasn't observed in the capture.
          - pulser_dac / threshold_dac (chip-wide DAC sweeps): one line per
            (ring, fen, vmm), requested DAC setting on x, measured ADC mV on y.
        """
        import matplotlib.pyplot as plt

        grouped_type = self.group_by_measurement_type()
        any_plots = False

        # --- Per-channel measurements (pedestal / threshold) ---
        for mtype in ('pedestal', 'threshold', 'channel_measurement'):
            if mtype not in grouped_type:
                continue
            by_vmm = defaultdict(list)
            for r in grouped_type[mtype]:
                if r.channel is not None:
                    by_vmm[(r.ring, r.fen, r.vmm)].append(r)

            if by_vmm:
                fig, ax = plt.subplots(figsize=(10, 6))
                for (ring, fen, vmm), readings in sorted(by_vmm.items()):
                    readings_sorted = sorted(readings, key=lambda r: r.channel)
                    ax.plot(
                        [r.channel for r in readings_sorted],
                        [r.adc_mv for r in readings_sorted],
                        marker='o', markersize=4,
                        label=f"Ring{ring} FEN{fen} VMM{vmm}"
                    )
                ax.set_xlabel("Channel")
                ax.set_ylabel("ADC reading (mV)")
                ax.set_title(f"Per-channel {mtype}")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
                any_plots = True

        # --- Chip-wide DAC sweeps (pulser_dac / threshold_dac) ---
        for mtype in ('pulser_dac', 'threshold_dac'):
            if mtype not in grouped_type:
                continue
            by_vmm = defaultdict(list)
            for r in grouped_type[mtype]:
                if r.dac_setting is not None:
                    by_vmm[(r.ring, r.fen, r.vmm)].append(r)

            if not by_vmm:
                continue

            fig, ax = plt.subplots(figsize=(10, 6))
            for (ring, fen, vmm), readings in sorted(by_vmm.items()):
                readings_sorted = sorted(readings, key=lambda r: r.dac_setting)
                
                x = np.array([r.dac_setting for r in readings_sorted])
                y = np.array([r.adc_mv for r in readings_sorted])
                
                # Linear regression (degree 1 polyfit: y = slope * x + offset).
                # Needs at least 2 distinct x values - with a single point (or
                # multiple points all at the same x) numpy can't fit a line
                # and prints a RankWarning straight to the console. Guard for
                # that instead of letting the warning leak out.
                label = f"Ring{ring} FEN{fen} VMM{vmm}"
                if len(x) >= 2 and len(set(x.tolist())) >= 2:
                    slope, offset = np.polyfit(x, y, 1)
                    label += f" | slope: {slope:.3f}, offset: {offset:.2f}"
                ax.plot(
                    x, y,
                    marker='o', markersize=4,
                    label=label
                )
            ax.set_xlabel("Requested DAC setting")
            ax.set_ylabel("Measured ADC (mV)")
            ax.set_title(f"{mtype} calibration")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            any_plots = True

        if any_plots:
            plt.show()
        else:
            print("\nNo plottable data found (no pedestal/threshold/channel_measurement/pulser_dac/threshold_dac readings).")


def main():
    # -------------------------------------------------------------------
    # Set the pcap file to process here - no more command-line arguments.
    # -------------------------------------------------------------------
    file_name = r"C:\Users\sheil\Downloads\threshold_measurement.pcapng"

    output_json = r"C:\Projects\mbuty\slow_control\data\vmm_adc_data.json"

    if not Path(file_name).exists():
        print(f"Error: {file_name} not found")
        return

    parser = VMMSlowControlParserV2()
    parser.parse_pcap(file_name)

    parser.print_summary()
    parser.plot_results()
    
    answer = input("\nSave results to JSON? (y/n): ").strip().lower()
    if answer == 'y':
        parser.export_json(output_json)
    else:
        print("Skipping JSON export.")


if __name__ == '__main__':
    main()
