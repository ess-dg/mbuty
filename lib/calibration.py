#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibration.py
==============
Self-contained VMM3A ADC/TDC calibration engine for MB/MG detector readouts.

Calibration file formats supported
----------------------------------
LEGACY  : HybridId directly encodes logical position, e.g. "FEN0_3".
          Ring/fen/hybrid are parsed straight out of the string.
NEW     : HybridId is the physical hybrid board's serial number. Every
          entry also carries a 'HybridIndex' field, which is what we use
          to detect this format. The serial is resolved against this
          run's topology (config['topology'][i]['serial']) to find which
          (ring, fen, hybrid) slot that physical board is plugged into.

Once the legacy format is fully retired, delete everything marked
"OLD CALIB FORMAT" below (the branch in _resolve_hybrid_key and the
_parse_hybrid_id_legacy helper) and this file collapses to serial-only
resolution.
"""

from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field
import numpy as np

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib.colors import ERR, WARN, INFO, RESET

# =============================================================================
# 1. CALIBRATION DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class VMMCalibrationEntry:
    """Immutable calibration constants for one VMM hybrid (two ASICs)."""
    hybrid_id: str            # e.g., "FEN0_3" (legacy) or a serial number (new)
    vmm0_adc_offset: np.ndarray = field(repr=False)  # ASIC 0: Per-channel ADC offsets, shape (64,)
    vmm0_adc_slope: np.ndarray  = field(repr=False)  # ASIC 0: Per-channel ADC gains,   shape (64,)
    vmm1_adc_offset: np.ndarray = field(repr=False)  # ASIC 1: Per-channel ADC offsets, shape (64,)
    vmm1_adc_slope: np.ndarray  = field(repr=False)  # ASIC 1: Per-channel ADC gains,   shape (64,)
    vmm0_tdc_offset: np.ndarray = field(repr=False)  # ASIC 0: Per-channel TDC offsets, shape (64,)
    vmm0_tdc_slope: np.ndarray  = field(repr=False)  # ASIC 0: Per-channel TDC slopes,  shape (64,)
    vmm1_tdc_offset: np.ndarray = field(repr=False)  # ASIC 1: Per-channel TDC offsets, shape (64,)
    vmm1_tdc_slope: np.ndarray  = field(repr=False)  # ASIC 1: Per-channel TDC slopes,  shape (64,)


def _default_entry(hybrid_id: str) -> VMMCalibrationEntry:
    """Return an identity-calibration entry (slope 1, offset 0) for a hybrid."""
    return VMMCalibrationEntry(
        hybrid_id       = hybrid_id,
        vmm0_adc_offset     = np.zeros(64, dtype=np.float64),
        vmm0_adc_slope      = np.ones(64,  dtype=np.float64),
        vmm1_adc_offset     = np.zeros(64, dtype=np.float64),
        vmm1_adc_slope      = np.ones(64,  dtype=np.float64),
        vmm0_tdc_offset     = np.zeros(64, dtype=np.float64),
        vmm0_tdc_slope      = np.ones(64,  dtype=np.float64),
        vmm1_tdc_offset     = np.zeros(64, dtype=np.float64),
        vmm1_tdc_slope      = np.ones(64,  dtype=np.float64),
    )


# =============================================================================
# 2. HYBRID KEY RESOLUTION — legacy FEN format vs new serial format
# =============================================================================

def _parse_hybrid_id_legacy(hybrid_id_text: str) -> tuple[int, int, int]:
    """
    --- OLD CALIB FORMAT — delete this function once new format fully in use ---
    Parse format 'FEN{ring}_{hybrid}' into integer coordinates. Fen is always 0.
    """
    try:
        left, right = hybrid_id_text.split('_', 1)
        ring   = int(left.split('FEN')[1])
        fen    = 0
        hybrid = int(right)
        return ring, fen, hybrid
    except (IndexError, ValueError) as exc:
        raise ValueError(
            f"Cannot parse HybridId '{hybrid_id_text}': expected format 'FEN<n>_<m>'."
        ) from exc


def _build_serial_lookup(config: dict) -> dict[str, tuple[int, int, int]]:
    """Map each configured hybrid's serial -> (ring, fen, hybrid) for this run's topology."""
    lookup: dict[str, tuple[int, int, int]] = {}
    for unit in config['topology']:
        serial = unit.get('serial', '')
        if serial:
            lookup[serial] = (int(unit['ring']), int(unit['fen']), int(unit['hybrid']))
    return lookup


def _resolve_hybrid_key(hybrid_id_text: str, block: dict, serial_lookup: dict) -> tuple[int, int, int] | None:
    """
    Resolve one calibration entry's HybridId to a (ring, fen, hybrid) key.
    Returns None if the entry cannot be resolved (caller skips it and the
    hybrid falls back to identity calibration further down the pipeline).

    Format is detected by the presence of 'HybridIndex', which only the
    new (serial-based) format carries.
    """
    if 'HybridIndex' not in block:
        # --- OLD CALIB FORMAT — delete this branch once new format fully in use ---
        try:
            return _parse_hybrid_id_legacy(hybrid_id_text)
        except ValueError as exc:
            print(f'\t {WARN}WARNING: Skipping unparseable entry — {exc}{RESET}')
            return None

    # --- NEW CALIB FORMAT: HybridId is the physical hybrid board's serial number ---
    key = serial_lookup.get(hybrid_id_text)
    if key is None:
        hybrid_index = block.get('HybridIndex', '?')
        print(
            f'\t {WARN}WARNING: calibration for serial {hybrid_id_text!r} not found in config file, '
            f'ID {hybrid_index} falling back to default/identity calibration{RESET}'
        )
        return None
    return key


# =============================================================================
# 3. JSON FILE INGESTION LAYER
# =============================================================================

def load_calibration_map(calib_file_path: str, config: dict, parameters) -> dict[tuple[int, int, int], VMMCalibrationEntry]:
    """
    Load VMM3A ADC/TDC calibrations from a JSON file into a (ring, fen, hybrid)
    lookup map. Handles both legacy FEN-labeled entries and new serial-labeled
    entries transparently (see _resolve_hybrid_key). Missing entries fall back
    to identity defaults (slope 1, offset 0).
    """
    # -------------------------------------------------------------------------
    # Guard Pass: Only MB / MG detectors feature VMM ADC calibration arrays
    # -------------------------------------------------------------------------
    det_type = config['detectorType']
    if det_type not in ('MB', 'MG'):
        print(f'\t {ERR}WARNING: calibrations for detector type {det_type!r} are not supported → switch OFF calibration!{RESET}')
        sys.exit(1)

    calib_filename = os.path.basename(calib_file_path)

    # -------------------------------------------------------------------------
    # Disk Read Pass: Ingest raw configuration JSON tree safely
    # -------------------------------------------------------------------------
    try:
        with open(calib_file_path, 'r') as fh:
            raw = json.load(fh)
        file_valid = True
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f'\n {WARN}---> WARNING: Calibration file {calib_filename!r} issues ({exc}) → fallback defaults applied.{RESET}')
        raw = {}
        file_valid = False

    if file_valid:
        print(f'{INFO}\nLoading VMM calibration file: {calib_filename}{RESET}')

    calibrations_raw = raw.get('Calibrations', [])
    serial_lookup     = _build_serial_lookup(config)
    json_lookup: dict[tuple[int, int, int], VMMCalibrationEntry] = {}

    # -------------------------------------------------------------------------
    # Mapping Loop: Parse existing file constants into the temporary lookup
    # -------------------------------------------------------------------------
    for item in calibrations_raw:
        block = item.get('VMMHybridCalibration', {})
        hybrid_id_text = block.get('HybridId', '')

        key = _resolve_hybrid_key(hybrid_id_text, block, serial_lookup)
        if key is None:
            continue

        vmm0 = block.get('vmm0', {})
        vmm1 = block.get('vmm1', {})

        json_lookup[key] = VMMCalibrationEntry(
            hybrid_id       = hybrid_id_text,
            vmm0_adc_offset     = np.asarray(vmm0.get('adc_offset', np.zeros(64)), dtype=np.float64),
            vmm0_adc_slope      = np.asarray(vmm0.get('adc_slope',  np.ones(64)),  dtype=np.float64),
            vmm1_adc_offset     = np.asarray(vmm1.get('adc_offset', np.zeros(64)), dtype=np.float64),
            vmm1_adc_slope      = np.asarray(vmm1.get('adc_slope',  np.ones(64)),  dtype=np.float64),
            vmm0_tdc_offset     = np.asarray(vmm0.get('tdc_offset', np.zeros(64)), dtype=np.float64),
            vmm0_tdc_slope      = np.asarray(vmm0.get('tdc_slope', np.zeros(64)), dtype=np.float64),
            vmm1_tdc_offset     = np.asarray(vmm1.get('tdc_offset', np.zeros(64)), dtype=np.float64),
            vmm1_tdc_slope      = np.asarray(vmm1.get('tdc_slope', np.zeros(64)), dtype=np.float64),
        )

    # -------------------------------------------------------------------------
    # Final Orchestration Map: Align strictly with configured cassettes
    # -------------------------------------------------------------------------
    final_map: dict[tuple[int, int, int], VMMCalibrationEntry] = {}
    units = config['topology']

    for unit in units:
        ring   = int(unit['ring'])
        fen    = int(unit['fen'])
        hybrid = int(unit['hybrid'])
        key    = (ring, fen, hybrid)

        if key in json_lookup:
            final_map[key] = json_lookup[key]
        else:
            # Replicates legacy constructor fallback array mapping precisely
            print(f'\t {WARN}No calib found in calib file for Ring {ring}, Fen {fen}, Hybrid {hybrid} → using defaults: slope 1, offset 0{RESET}')
            final_map[key] = _default_entry(f"FEN{ring}_{hybrid}")

    # Post-check for all-zero calibrations
    for (ring, fen, hybrid), entry in final_map.items():

        if parameters.dataReduction.calibrateVMM_ADC_ONOFF:
            if np.allclose(entry.vmm0_adc_offset, 0.0) and np.allclose(entry.vmm1_adc_offset, 0.0):
                print(f'\t {WARN}WARNING: ADC calibration all zeros for Ring {ring}, Fen {fen}, Hybrid {hybrid}{RESET}')

        if parameters.dataReduction.calibrateVMM_TDC_ONOFF:
            if np.allclose(entry.vmm0_tdc_offset, 0.0) and np.allclose(entry.vmm1_tdc_offset, 0.0):
                print(f'\t {WARN}WARNING: TDC calibration all zeros for Ring {ring}, Fen {fen}, Hybrid {hybrid}{RESET}')

    return final_map


# =============================================================================
# 4. CALIBRATION ENGINE — applies loaded constants to a readouts container
# =============================================================================

class VMMCalibrationEngine:
    """
    Self-contained VMM3A ADC/TDC calibration engine for MB/MG readouts.

    Mirrors the BaseAbsUnitsCalculator / VMMThresholdEngine convention:
    instantiate with (readouts, config, parameters) and call
    process_pipeline(). On/off flags and the informational print are
    handled internally, so pipelines.py can call this unconditionally —
    same as the other per-stage engines.
    """

    def __init__(self, readouts, config: dict, parameters):
        self.readouts   = readouts
        self.config     = config
        self.parameters = parameters

    def process_pipeline(self) -> None:
        if self.readouts.fill_count == 0:
            return

        adc_calib_on = getattr(getattr(self.parameters, 'dataReduction', None), 'calibrateVMM_ADC_ONOFF', False)
        tdc_calib_on = getattr(getattr(self.parameters, 'dataReduction', None), 'calibrateVMM_TDC_ONOFF', False)

        if not adc_calib_on and not tdc_calib_on:
            print(f'\t {INFO}VMM calibration OFF (ADC and TDC both disabled){RESET}')
            return

        calib_path = getattr(getattr(self.parameters, 'fileManagement', None), 'calibFilePath', '')
        calib_name = getattr(getattr(self.parameters, 'fileManagement', None), 'calibFileName', '')
        calib_map  = load_calibration_map(calib_path + calib_name, self.config, self.parameters)

        if adc_calib_on:
            self._calibrate_adc(calib_map)
        if tdc_calib_on:
            self._calibrate_tdc(calib_map)

    def _calibrate_adc(self, calib_map: dict) -> None:
        """Applies per-channel linear ADC calibrations to the readouts matrix."""
        if not calib_map:
            return
        print(f'{INFO}Calibrating ADC ...{RESET}')

        matrix     = self.readouts.matrix
        ring_col   = matrix['ring']
        fen_col    = matrix['fen']
        hybrid_col = matrix['hybrid']
        asic_col   = matrix['asic']
        chan_col   = matrix['channel']
        adc_col    = matrix['adc']

        for (ring, fen, hybrid), entry in calib_map.items():
            mask = (ring_col == ring) & (fen_col == fen) & (hybrid_col == hybrid)
            if not np.any(mask):
                continue

            for asic_idx, offset_arr, slope_arr in (
                (0, entry.vmm0_adc_offset, entry.vmm0_adc_slope),
                (1, entry.vmm1_adc_offset, entry.vmm1_adc_slope),
            ):
                asic_mask = mask & (asic_col == asic_idx)
                if not np.any(asic_mask):
                    continue

                adc_float   = adc_col[asic_mask].astype(np.float64, copy=True)
                channel_idx = chan_col[asic_mask].astype(np.intp)
                calibrated  = np.around((adc_float - offset_arr[channel_idx]) * slope_arr[channel_idx])
                matrix['adc'][asic_mask] = np.clip(calibrated, 0, 1023).astype(np.int64)

    def _calibrate_tdc(self, calib_map: dict) -> None:
        """Applies per-channel TDC fine-time calibration across the readouts matrix."""
        time_res_type     = getattr(getattr(self.parameters, 'timeSettings', None), 'timeResolutionType', 'coarse')
        ns_per_clock_tick = float(getattr(getattr(self.parameters, 'clockTicks', None), 'NSperClockTick', 11.35))

        if time_res_type != 'fine':
            print(f'\t {WARN}WARNING: calibrateVMM_TDC_ONOFF is True but timeResolutionType is coarse → TDC calibration skipped.{RESET}')
            return

        if not calib_map:
            return

        print(f'{INFO}Calibrating TDC and recalculating time stamp ...{RESET}')

        matrix     = self.readouts.matrix
        ring_col   = matrix['ring']
        fen_col    = matrix['fen']
        hybrid_col = matrix['hybrid']
        asic_col   = matrix['asic']

        for (ring, fen, hybrid), entry in calib_map.items():
            mask = (ring_col == ring) & (fen_col == fen) & (hybrid_col == hybrid)
            if not np.any(mask):
                continue

            for asic_idx, offset_arr, slope_arr in (
                (0, entry.vmm0_tdc_offset, entry.vmm0_tdc_slope),
                (1, entry.vmm1_tdc_offset, entry.vmm1_tdc_slope),
            ):
                asic_mask = mask & (asic_col == asic_idx)
                if not np.any(asic_mask):
                    continue

                # Fine-timestamp math itself stays on the readouts container
                # (it's shared with the uncalibrated pass in clean_and_sort);
                # the engine just supplies the calibrated offset/slope arrays.
                self.readouts._calculate_fine_timestamp(
                    ns_per_clock_tick,
                    mask=asic_mask,
                    tdc_offset_array=offset_arr,
                    tdc_slope_array=slope_arr,
                ) 