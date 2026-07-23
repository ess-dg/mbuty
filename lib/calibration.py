#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibration.py
==============
Self-contained VMM3A ADC/TDC calibration engine for MB/MG detector readouts.

Mirrors the abs_units_engine / threshold_engine convention used elsewhere
in the pipeline: instantiate with (readouts, config, parameters) and call
process_pipeline(). The engine reads its own on/off flags internally, so
callers in pipelines.py invoke it unconditionally, same as the other
per-stage engines.

Calibration file formats supported
----------------------------------
LEGACY  : HybridId directly encodes logical position, e.g. "FEN0_3".
          Ring/fen/hybrid are parsed straight out of the string.
NEW     : HybridId is the physical hybrid board's serial number, resolved
          against this run's topology (config['topology'][i]['serial']) to
          find which (ring, fen, hybrid) slot that physical board is
          plugged into.

Format is detected ONCE per file (_detect_calib_file_format), by whether
the first entry's HybridId matches the legacy 'FEN<n>_<m>' pattern — a real
file is always one format or the other, never a mix. Whichever it is, the
WHOLE file is then resolved through exactly one of two fully independent
pipelines (_resolve_legacy_pipeline / _resolve_new_pipeline); neither one
ever falls back to or consults the other.

Once the legacy format is fully retired, delete everything marked
"OLD CALIB FORMAT" below (_resolve_legacy_pipeline, _build_fen_lookup_from_file,
_parse_hybrid_id_legacy, and the 'legacy' branch in _detect_calib_file_format)
and this file collapses to serial-only resolution.
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
# 2. HYBRID KEY RESOLUTION — the CONFIG topology is the source of truth.
#    For each configured hybrid we ask the calibration file "do you have
#    an entry for this?" — never the other way around. Otherwise a
#    calibration file covering more hybrids than this instrument's
#    topology (very likely — one shared lab-wide file, many instruments)
#    would spam warnings about hybrids that aren't this run's business.
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


def _build_fen_lookup_from_file(calibrations_raw: list) -> dict[tuple[int, int, int], dict]:
    """
    --- OLD CALIB FORMAT — delete this function once new format fully in use ---
    Index calibration file entries by (ring, fen, hybrid), parsed straight out
    of the legacy 'FEN<n>_<m>' HybridId. Entries using the new serial-style
    HybridId simply fail to parse this way and are skipped here — they're
    indexed by _build_serial_lookup_from_file instead.
    """
    lookup: dict[tuple[int, int, int], dict] = {}
    for item in calibrations_raw:
        block = item.get('VMMHybridCalibration', {})
        try:
            key = _parse_hybrid_id_legacy(block.get('HybridId', ''))
        except ValueError:
            continue
        lookup[key] = block
    return lookup


def _build_serial_lookup_from_file(calibrations_raw: list) -> dict[str, dict]:
    """Index calibration file entries by their own HybridId (the physical serial), verbatim."""
    lookup: dict[str, dict] = {}
    for item in calibrations_raw:
        block = item.get('VMMHybridCalibration', {})
        hybrid_id_text = block.get('HybridId', '')
        if hybrid_id_text:
            lookup[hybrid_id_text] = block
    return lookup


def _is_legacy_hybrid_id(hybrid_id_text: str) -> bool:
    """True if this HybridId matches the legacy 'FEN<n>_<m>' position-encoded pattern."""
    try:
        _parse_hybrid_id_legacy(hybrid_id_text)
        return True
    except ValueError:
        return False


def _detect_calib_file_format(calibrations_raw: list) -> str:
    """
    Decide ONCE, for the whole file, whether this is the OLD (legacy
    'FEN<n>_<m>' position-encoded HybridId) format or the NEW (physical
    serial number HybridId) format. A real calibration file is one or the
    other, never a mix, so checking the first entry's HybridId is enough.
    Returns 'legacy' or 'new'.
    """
    if not calibrations_raw:
        return 'new'  # nothing to resolve either way; new is the going-forward default
    first_block = calibrations_raw[0].get('VMMHybridCalibration', {})
    first_hybrid_id = first_block.get('HybridId', '')
    return 'legacy' if _is_legacy_hybrid_id(first_hybrid_id) else 'new'


def _resolve_legacy_pipeline(calibrations_raw: list, config: dict, parameters) -> dict[tuple[int, int, int], "VMMCalibrationEntry"]:
    """
    --- OLD CALIB FORMAT PIPELINE — delete this whole function once every
    calibration file in use is the new serial-based format ---
    The whole file is legacy: every entry's HybridId is parsed as
    'FEN<n>_<m>' and matched purely by (ring, fen, hybrid) position.
    Config's 'serial' field is never consulted here — this pipeline doesn't
    know serials exist.
    """
    fen_lookup = _build_fen_lookup_from_file(calibrations_raw)
    final_map: dict[tuple[int, int, int], VMMCalibrationEntry] = {}

    for unit in config['topology']:
        ring   = int(unit['ring'])
        fen    = int(unit['fen'])
        hybrid = int(unit['hybrid'])
        key    = (ring, fen, hybrid)

        if key in fen_lookup:
            entry = _entry_from_block(f"FEN{ring}_{hybrid}", fen_lookup[key])
            final_map[key] = entry
            _check_resolved_entry_integrity(ring, fen, hybrid, entry, parameters)
        else:
            print(
                f'\t {WARN}Warning: ring {ring} fen {fen} hybrid {hybrid} not found in config file '
                f'using defaults: slope 1, offset 0{RESET}'
            )
            final_map[key] = _default_entry(f"FEN{ring}_{hybrid}")

    return final_map


def _resolve_new_pipeline(calibrations_raw: list, config: dict, parameters) -> dict[tuple[int, int, int], "VMMCalibrationEntry"]:
    """
    NEW CALIB FORMAT PIPELINE — serial-driven, this is the one true path
    once the transition is complete. The whole file is new format: every
    entry's HybridId is the physical hybrid board's serial number, matched
    purely against config's own recorded 'serial' field. Legacy
    ring/fen/hybrid position is never consulted here — this pipeline
    doesn't know the legacy encoding exists.
    """
    serial_lookup = _build_serial_lookup_from_file(calibrations_raw)
    final_map: dict[tuple[int, int, int], VMMCalibrationEntry] = {}

    for unit in config['topology']:
        ring        = int(unit['ring'])
        fen         = int(unit['fen'])
        hybrid      = int(unit['hybrid'])
        key         = (ring, fen, hybrid)
        unit_serial = unit.get('serial', '')

        if unit_serial in serial_lookup:
            entry = _entry_from_block(unit_serial, serial_lookup[unit_serial])
            final_map[key] = entry
            _check_resolved_entry_integrity(ring, fen, hybrid, entry, parameters)
        else:
            print(
                f'\t {WARN}Warning: No calibration entry for serial no {unit_serial!r} in calibration file. '
                f'Ring {ring} Fen {fen} Hybrid {hybrid} using defaults: slope 1, offset 0.{RESET}'
            )
            final_map[key] = _default_entry(f"ring{ring}_fen{fen}_hybrid{hybrid}")

    return final_map


def _entry_from_block(hybrid_id_text: str, block: dict) -> VMMCalibrationEntry:
    """Build a VMMCalibrationEntry from one calibration file entry's vmm0/vmm1 blocks."""
    vmm0 = block.get('vmm0', {})
    vmm1 = block.get('vmm1', {})
    return VMMCalibrationEntry(
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


def _check_resolved_entry_integrity(ring: int, fen: int, hybrid: int, entry: VMMCalibrationEntry, parameters) -> None:
    """
    Sanity check run AFTER resolution, only on hybrids this config actually
    uses — never on the rest of the file. A calibration file (especially a
    shared lab-wide one) can carry many more hybrids than this instrument's
    topology; there's no reason to warn about ones we never touch. Flags
    all-zero/identity ADC or TDC per asic, which usually means a dummy or
    placeholder entry made it into the calibration file for a hybrid this
    run does depend on.

    Only checks ADC when calibrateVMM_ADC_ONOFF is on, and TDC when
    calibrateVMM_TDC_ONOFF is on — no point flagging a channel that isn't
    going to be used anyway. Not called for defaulted (unmatched) units —
    those already got their own "not found" / "no calibration entry"
    warning at resolution time.
    """
    adc_calib_on = getattr(getattr(parameters, 'dataReduction', None), 'calibrateVMM_ADC_ONOFF', False)
    tdc_calib_on = getattr(getattr(parameters, 'dataReduction', None), 'calibrateVMM_TDC_ONOFF', False)

    if not adc_calib_on and not tdc_calib_on:
        return

    if adc_calib_on and np.allclose(entry.vmm0_adc_offset, 0.0) and np.allclose(entry.vmm1_adc_offset, 0.0):
        print(f'\t {WARN}Warning: Ring {ring} Fen {fen} Hybrid {hybrid} has all zeros for ADC on both asics. Check calibration file {RESET}')

    if tdc_calib_on and np.allclose(entry.vmm0_tdc_offset, 0.0) and np.allclose(entry.vmm1_tdc_offset, 0.0):
        print(f'\t {WARN}Warning: Ring {ring} Fen {fen} Hybrid {hybrid} has all zeros for TDC on both asics. Check calibration file {RESET}')

# =============================================================================
# 3. JSON FILE INGESTION LAYER
# =============================================================================

def load_calibration_map(calib_file_path: str, config: dict, parameters) -> dict[tuple[int, int, int], VMMCalibrationEntry]:
    """
    Load VMM3A ADC/TDC calibrations from a JSON file into a (ring, fen, hybrid)
    lookup map.

    The calibration file's FORMAT is decided once, for the whole file (see
    _detect_calib_file_format) — never per unit or per entry, since a real
    file is one format or the other, never a mix. Whichever format it is,
    all of config['topology'] is resolved through that single pipeline:
      - legacy file  -> _resolve_legacy_pipeline: ring/fen/hybrid position
        match only; config's 'serial' field is never consulted.
      - new file     -> _resolve_new_pipeline: serial match only; legacy
        ring/fen/hybrid position is never consulted.
    These two pipelines are fully independent. The legacy one is dead code
    the moment every calibration file in use is the new serial-based
    format, and can be deleted wholesale at that point.

    Each pipeline also runs an all-zero/identity ADC-TDC integrity check
    (_check_resolved_entry_integrity) right after each successful match —
    so it only ever fires for hybrids this config actually depends on, not
    for every entry sitting in the file (which may cover more hybrids than
    this instrument's topology, e.g. a shared lab-wide calibration file).
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

    # -------------------------------------------------------------------------
    # The calibration file's FORMAT is decided ONCE, for the whole file (see
    # _detect_calib_file_format) — never per unit, never per entry, since a
    # real file is one format or the other, never a mix. Whichever format it
    # is, ALL of config['topology'] is resolved through that single pipeline.
    # OLD and NEW are fully independent pipelines: the OLD one is dead code
    # the moment every calibration file in use is the new serial-based
    # format, and can be deleted wholesale.
    #
    # Each pipeline runs the all-zero/identity ADC-TDC integrity check
    # (_check_resolved_entry_integrity) itself, right after a successful
    # match — so it only ever fires for hybrids this config actually uses,
    # never for unrelated entries elsewhere in the file, and never for units
    # that already fell back to identity defaults (those get their own
    # "not found" warning instead).
    # -------------------------------------------------------------------------
    calib_format = _detect_calib_file_format(calibrations_raw)

    if calib_format == 'legacy':
        # --- OLD CALIB FORMAT — delete this branch once new format fully in use ---
        return _resolve_legacy_pipeline(calibrations_raw, config, parameters)
    else:
        return _resolve_new_pipeline(calibrations_raw, config, parameters)


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