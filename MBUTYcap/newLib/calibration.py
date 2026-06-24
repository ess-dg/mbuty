#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
libVMMcalibration.py
====================
Stateless calibration engine for VMM3A-based ESS detector readouts.
"""

from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field
import numpy as np
from .colors import ERR, WARN, INFO, RESET

# =============================================================================
# 1. CALIBRATION DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class VMMCalibrationEntry:
    """Immutable calibration constants for one VMM hybrid (two ASICs)."""
    hybrid_id: str            # e.g., "FEN0_3"
    vmm0_adc_offset: np.ndarray = field(repr=False)  # ASIC 0: Per-channel ADC offsets, shape (64,)
    vmm0_adc_slope: np.ndarray  = field(repr=False)  # ASIC 0: Per-channel ADC gains,   shape (64,)
    vmm1_adc_offset: np.ndarray = field(repr=False)  # ASIC 1: Per-channel ADC offsets, shape (64,)
    vmm1_adc_slope: np.ndarray  = field(repr=False)  # ASIC 1: Per-channel ADC gains,   shape (64,)
    vmm0_tdc_offset: np.ndarray = field(repr=False)  # ASIC 0: Per-channel TDC offsets, shape (64,)
    vmm0_tdc_slope: np.ndarray  = field(repr=False)  # ASIC 0: Per-channel TDC slopes,  shape (64,)
    vmm1_tdc_offset: np.ndarray = field(repr=False)  # ASIC 1: Per-channel TDC offsets, shape (64,)
    vmm1_tdc_slope: np.ndarray  = field(repr=False)  # ASIC 1: Per-channel TDC slopes,  shape (64,)

# =============================================================================
# 2. CALIBRATION FALLBACK & PARSING HELPERS
# =============================================================================

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


def _parse_hybrid_id(hybrid_id_text: str) -> tuple[int, int, int]:
    """Parse format 'FEN{ring}_{hybrid}' into integer coordinates. Fen is always 0."""
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


# =============================================================================
# 3. JSON FILE INGESTION LAYER
# =============================================================================

def load_calibration_map(calib_file_path: str, config: dict) -> dict[tuple[int, int, int], VMMCalibrationEntry]:
    """
    Load VMM3A ADC calibrations from a JSON file into a (ring, fen, hybrid) lookup map.
    Missing entries fallback to identity defaults (slope 1, offset 0) via helper.
    """
    # -------------------------------------------------------------------------
    # Guard Pass: Only MB / MG detectors feature VMM ADC calibration arrays
    # -------------------------------------------------------------------------
    det_type = config['detectorType']
    if det_type not in ('MB', 'MG'):
        print(f'\t {ERR}WARNING: calibrations for detector type {det_type!r} are not supported → switch OFF calibration!{RESET}')
        sys.exit(1)

    calib_filename = os.path.basename(calib_file_path)
    calib_dir      = os.path.dirname(calib_file_path)

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
    json_lookup: dict[tuple[int, int, int], VMMCalibrationEntry] = {}

    # -------------------------------------------------------------------------
    # Mapping Loop: Parse existing file constants into the temporary lookup
    # -------------------------------------------------------------------------
    for item in calibrations_raw:
        block = item.get('VMMHybridCalibration', {})
        hybrid_id_text = block.get('HybridId', '')

        try:
            key = _parse_hybrid_id(hybrid_id_text)
        except ValueError as exc:
            print(f'\t {WARN}WARNING: Skipping unparseable entry — {exc}{RESET}')
            continue

        vmm0 = block.get('vmm0', {})
        vmm1 = block.get('vmm1', {})

        # TODO: replace tdc_offset/tdc_slope key names once calibration file schema is confirmed
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

    return final_map





