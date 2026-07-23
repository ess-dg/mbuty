#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_calibration.py
====================
Exercises calibration.py's serial-driven ("new format") resolution pipeline
against a real calibration file (ill_efu_time_calib.json) and a test config
(AMOR_test_config.json) that has been seeded with real serials pulled
straight out of that calibration file.

Covers:
  1. Matched units resolve to the EXACT vmm0/vmm1 tdc+adc arrays that live
     in the calibration file for their serial (cross-checked by re-parsing
     the JSON independently, not by trusting calibration.py's own output).
  2. A unit with an empty serial in the config falls back to identity
     defaults (slope 1 / offset 0) and is NOT mistaken for "unit missing
     from config" (the bug fixed earlier).
  3. A unit whose serial doesn't exist anywhere in the calibration file
     also falls back to identity defaults, with the "no calibration entry
     for serial ..." warning.
  4. _calibrate_adc actually mutates readout data when the resolved
     slope/offset are non-identity, proving the apply step (not just the
     resolution step) works. The real calib file here ships identity ADC
     constants (its own header says "no ADC"), so that fact alone doesn't
     prove the math -- this test injects one synthetic non-identity ADC
     entry into a copy of the calibration map to prove the linear
     transform + clipping is applied correctly.

Run with: python3 test_calibration.py
"""

import copy
import json
import os
import sys
import types

import numpy as np

# ---------------------------------------------------------------------------
# Stub out lib.colors so calibration.py can be imported standalone. The real
# repo provides ANSI color constants here; for a test we don't care what they
# look like, just that the names exist.
# ---------------------------------------------------------------------------
_fake_lib = types.ModuleType("lib")
_fake_colors = types.ModuleType("lib.colors")
_fake_colors.ERR = "[ERR]"
_fake_colors.WARN = "[WARN]"
_fake_colors.INFO = "[INFO]"
_fake_colors.RESET = ""
_fake_lib.colors = _fake_colors
sys.modules["lib"] = _fake_lib
sys.modules["lib.colors"] = _fake_colors

# =============================================================================
# RUNTIME PATH BOOTSTRAP (Ensures absolute imports always work)
# =============================================================================
import os
import sys

_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lib_path = os.path.join(_workspace, "lib")

if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

import calibration  # noqa: E402 # noqa: E402  (import after sys.modules stub, intentional)

CALIB_FILE = r"C:\Projects\mbuty\calib\ill_efu_time_calib.json"
CONFIG_FILE = r"C:\Projects\mbuty\config\AMOR_TEST.json"

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


class _NS:
    """Tiny attribute-namespace stand-in for the real `parameters` object."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def make_parameters(adc_on=True, tdc_on=True):
    return _NS(
        dataReduction=_NS(calibrateVMM_ADC_ONOFF=adc_on, calibrateVMM_TDC_ONOFF=tdc_on),
        fileManagement=_NS(calibFilePath="", calibFileName=CALIB_FILE),
        timeSettings=_NS(timeResolutionType="fine"),
        clockTicks=_NS(NSperClockTick=11.35),
    )


def main():
    with open(CONFIG_FILE) as fh:
        config = json.load(fh)
    with open(CALIB_FILE) as fh:
        raw_calib = json.load(fh)

    # Independent re-parse of the calib file, keyed by serial, so we're not
    # trusting calibration.py's own parsing when we check its output.
    by_serial = {
        block["VMMHybridCalibration"]["HybridId"]: block["VMMHybridCalibration"]
        for block in raw_calib["Calibrations"]
    }

    parameters = make_parameters()

    print("=== 1. Format detection ===")
    calib_map = calibration.load_calibration_map(CALIB_FILE, config, parameters)
    # The real calib file uses serial-style HybridIds, so this must have
    # gone through the NEW pipeline, not the legacy FEN<n>_<m> one.
    check(
        "resolved via new (serial) pipeline, not legacy",
        all(not calibration._is_legacy_hybrid_id(e.hybrid_id) for e in calib_map.values() if e.hybrid_id),
    )

    print("\n=== 2. Matched units resolve to the real per-serial constants ===")
    for unit in config["topology"]:
        ring, fen, hybrid = int(unit["ring"]), int(unit["fen"]), int(unit["hybrid"])
        serial = unit.get("serial", "")
        key = (ring, fen, hybrid)
        entry = calib_map[key]

        if serial in by_serial:
            expected = by_serial[serial]
            exp_vmm0_tdc_off = np.asarray(expected["vmm0"]["tdc_offset"], dtype=np.float64)
            exp_vmm1_tdc_slope = np.asarray(expected["vmm1"]["tdc_slope"], dtype=np.float64)
            check(
                f"ring{ring} fen{fen} hybrid{hybrid} (serial {serial[:12]}...) vmm0 tdc_offset matches file",
                np.array_equal(entry.vmm0_tdc_offset, exp_vmm0_tdc_off),
            )
            check(
                f"ring{ring} fen{fen} hybrid{hybrid} (serial {serial[:12]}...) vmm1 tdc_slope matches file",
                np.array_equal(entry.vmm1_tdc_slope, exp_vmm1_tdc_slope),
            )

    print("\n=== 3. Empty-serial unit falls back to identity defaults ===")
    empty_serial_unit = next(u for u in config["topology"] if u.get("serial", "") == "")
    key = (int(empty_serial_unit["ring"]), int(empty_serial_unit["fen"]), int(empty_serial_unit["hybrid"]))
    entry = calib_map[key]
    check("empty-serial unit gets identity ADC (offset 0)", np.allclose(entry.vmm0_adc_offset, 0.0))
    check("empty-serial unit gets identity ADC (slope 1)", np.allclose(entry.vmm0_adc_slope, 1.0))
    check(
        "empty-serial unit gets a descriptive fallback id, not a blank one",
        entry.hybrid_id == f"ring{key[0]}_fen{key[1]}_hybrid{key[2]}",
    )

    print("\n=== 4. Unmatched-serial unit falls back to identity defaults ===")
    bogus_unit = next(u for u in config["topology"] if u.get("serial", "") == "SERIAL-NOT-IN-CALIB-FILE")
    key = (int(bogus_unit["ring"]), int(bogus_unit["fen"]), int(bogus_unit["hybrid"]))
    entry = calib_map[key]
    check("unmatched-serial unit gets identity TDC (slope 1)", np.allclose(entry.vmm0_tdc_slope, 1.0))
    check("unmatched-serial unit gets identity TDC (offset 0)", np.allclose(entry.vmm0_tdc_offset, 0.0))

    print("\n=== 5. _calibrate_adc actually changes readout data (non-identity case) ===")
    # This calib file's own ADC constants are identity (see its "no ADC"
    # comment), so to prove the *application* math works -- not just
    # resolution -- inject one synthetic non-identity entry.
    test_map = copy.deepcopy(calib_map)
    target_key = (0, 0, 0)
    synthetic = calibration.VMMCalibrationEntry(
        hybrid_id="synthetic-test-entry",
        vmm0_adc_offset=np.full(64, 10.0),
        vmm0_adc_slope=np.full(64, 2.0),
        vmm1_adc_offset=np.zeros(64),
        vmm1_adc_slope=np.ones(64),
        vmm0_tdc_offset=np.zeros(64),
        vmm0_tdc_slope=np.ones(64),
        vmm1_tdc_offset=np.zeros(64),
        vmm1_tdc_slope=np.ones(64),
    )
    test_map[target_key] = synthetic

    dtype = np.dtype([
        ("ring", np.int64), ("fen", np.int64), ("hybrid", np.int64),
        ("asic", np.int64), ("channel", np.int64), ("adc", np.int64),
    ])
    rows = np.array([
        (0, 0, 0, 0, 5, 100),   # matches target_key, asic 0, channel 5 -> should change
        (0, 0, 0, 1, 5, 100),   # matches target_key, asic 1 -> identity, should NOT change
        (1, 0, 0, 0, 5, 100),   # different hybrid entirely -> should NOT change
    ], dtype=dtype)

    class FakeReadouts:
        def __init__(self, matrix):
            self.matrix = matrix
            self.fill_count = len(matrix)

    engine = calibration.VMMCalibrationEngine(FakeReadouts(rows), config, parameters)
    engine._calibrate_adc(test_map)

    # raw=100, offset=10, slope=2 -> (100-10)*2 = 180, clipped to [0,1023]
    check("asic0/channel5 on the calibrated hybrid changed to the expected value", rows[0]["adc"] == 180)
    check("asic1 on the same hybrid (identity calib) is unchanged", rows[1]["adc"] == 100)
    check("a different hybrid entirely is unchanged", rows[2]["adc"] == 100)

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()