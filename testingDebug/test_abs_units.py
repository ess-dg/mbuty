#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import pytest
import sys 
import os
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

# Import refactored containers and engines
from newLib.events_containers import eventsVMMnormal, eventsR5560, eventsBM
from newLib.abs_units_engine import (
    MBAbsUnitsCalculator,
    MGAbsUnitsCalculator,
    R5560AbsUnitsCalculator,
    calculate_monitor_wavelength
)

# Dummy parameters class mimicking the dot-notation architecture
class DummyWavelengthParams:
    def __init__(self):
        self.distance = 8038.0             # mm (chopper to first wire)
        self.multipleFramePerReset = True
        self.lambdaMIN = 2.7               # Angstrom
        self.chopperPeriod = 0.06          # seconds
        self.numOfBunchesPerPulse = 2
        self.chopperPickUpDelay = 0.0005   # seconds

class DummyMonitorParams:
    def __init__(self):
        self.MONDistance = 4000.0          # mm

class DummyParameters:
    def __init__(self):
        self.wavelength = DummyWavelengthParams()
        self.MONitor = DummyMonitorParams()


# =============================================================================
# MULTI-BLADE PIPELINE TEST
# =============================================================================
def test_multi_blade_pipeline():
    print("\n--- Testing Multi-Blade Pipeline Pass ---")
    
    # 1. Setup Mock Configuration
    config = {
        'wires': 32,
        'wirePitch_mm': 2.5,
        'stripPitch_mm': 4.0,
        'bladesInclination_deg': 5.0,
        'offset1stWires_mm': 10.0,
        'topology': [{'ID': 1}, {'ID': 2}]
    }
    params = DummyParameters()
    
    # 2. Preallocate Container (Size 4 for mixed cases)
    ev = eventsVMMnormal(size=4)
    
    # Simulate clustering output payloads
    computed = {
        'ID':          np.array([1, 2, 1, 1], dtype='int64'),
        'coordinate0': np.array([0, 31, -1, 5], dtype='float64'),  # Row 2 is Strip-only (1D)
        'coordinate1': np.array([10, -1, 15, 2], dtype='float64'), # Row 1 is Wire-only (1D)
        'pulseHeight1': np.zeros(4, dtype='int64'),
        'mult0':        np.array([1, 1, 0, 1], dtype='int64'),
        'mult1':        np.array([1, 0, 1, 1], dtype='int64'),
        'clusterSpan':  np.zeros(4, dtype='int64')
    }
    
    # Timing timeline with recovery states
    timing = {
        'timeStamp': np.array([1000000, 2000000, 3000000, 4000000], dtype='int64'),
        'pulseT':    np.array([900000,  2500000, 2800000, 3800000], dtype='int64'), # Changed index 2 to 2800000
        'prevPT':    np.array([800000,  1800000, 2000000, 3000000], dtype='int64')
        }
    
    ev.absorb(computed, timing)
    
    # 3. Instantiate Engine and execute full pipeline process loop
    calc = MBAbsUnitsCalculator(ev, config, params)
    calc.process_pipeline(remove_invalid_tofs=False)
    
    m = ev.matrix[:ev.fill_count]
    
    # Assertions: Timing and Recovery Validation
    assert m['ToF'][0] == 100000  # 1000000 - 900000
    assert m['ToF'][1] == 200000  # Negative recovered: 2000000 - 1800000 (prevPT)
    
    # Assertions: 1D vs 2D Coordinate Sentinel Guards using np.isnan()
    assert np.isnan(m['absCoordinate1'][1])  # Wire-only event drops strip pitch
    assert np.isnan(m['absCoordinate0'][2])  # Strip-only event drops wire tracking
    assert np.isnan(m['absCoordinate2'][2])  # Strip-only event drops wire depth
    
    # 4. Test ToF Range Gating
    ev.trim_tof_range(tof_gate_range_s=[0.00015, 0.005]) # 150,000ns to 5,000,000ns
    assert ev.fill_count == 3  # Row 0 (100,000ns) should be dropped


# =============================================================================
# MULTI-GRID PIPELINE TEST
# =============================================================================
def test_multi_grid_pipeline():
    print("\n--- Testing Multi-Grid Pipeline Pass ---")
    
    config = {
        'wires': 40,
        'wiresPerRow': 20,
        'wirePitchX_mm': 22.0,
        'wirePitchZ_mm': 10.0,
        'gridPitchY_mm': 25.0,
        'topology': [{'ID': 10}, {'ID': 11}]
    }
    params = DummyParameters()
    
    ev = eventsVMMnormal(size=3)
    
    computed = {
        'ID':          np.array([10, 11, 10], dtype='int64'),
        'coordinate0': np.array([5, 45, -1], dtype='float64'),  # Row 1 is local wire 5 on Cass 11 (45 - 40)
        'coordinate1': np.array([2, -1, 4], dtype='float64'),   # Row 2 is Strip-only (1D)
        'pulseHeight1': np.zeros(3, dtype='int64'),
        'mult0':        np.array([1, 1, 0], dtype='int64'),
        'mult1':        np.array([1, 0, 1], dtype='int64'),
        'clusterSpan':  np.zeros(3, dtype='int64')
    }
    
    timing = {
        'timeStamp': np.array([5000000, 6000000, 7000000], dtype='int64'),
        'pulseT':    np.array([4800000, 5700000, 6600000], dtype='int64'),
        'prevPT':    np.array([4000000, 5000000, 6000000], dtype='int64')
    }
    
    ev.absorb(computed, timing)
    
    calc = MGAbsUnitsCalculator(ev, config, params)
    calc.process_pipeline(remove_invalid_tofs=False)
    
    m = ev.matrix[:ev.fill_count]
    
    # Assertions: Local wire channel mapping row/depth checks
    assert m['absCoordinate0'][0] == 0.0
    assert m['absCoordinate2'][0] == 50.0  # 5 * 10.0mm depth pitch
    
    # Row 1: Cass 11 -> wire local = 45 - 40 = 5 -> row 0, depth 5
    assert m['absCoordinate0'][1] == 0.0
    assert np.isnan(m['absCoordinate1'][1])  # Wire-only event
    
    # Row 2: Grid-only event -> all wire attributes mapped to nan sentinels
    assert np.isnan(m['absCoordinate0'][2])
    assert np.isnan(m['absCoordinate2'][2])


# =============================================================================
# CAEN R5560 HELIUM-3 BOX TUBE TEST
# =============================================================================
def test_r5560_pipeline():
    print("\n--- Testing R5560 Gas Tube Pipeline Pass ---")
    
    config = {
        'tubeLength': 2000.0,
        'tubeSpacing': 25.4
    }
    params = DummyParameters()
    
    ev = eventsR5560(size=2)
    
    computed = {
        'ID':          np.array([1, 1], dtype='int64'),
        'coordinate0': np.array([0.25, 0.75], dtype='float64'), # Fractional positions
        'coordinate1': np.array([0, 4], dtype='float64')         # Tube IDs
    }
    
    timing = {
        'timeStamp': np.array([1000, 2000], dtype='int64'),
        'pulseT':    np.array([500,  1200], dtype='int64'),
        'prevPT':    np.array([0,    1000], dtype='int64')
    }
    
    ev.absorb(computed, timing)
    
    calc = R5560AbsUnitsCalculator(ev, config, params)
    calc.process_pipeline(remove_invalid_tofs=False)
    
    m = ev.matrix[:ev.fill_count]
    
    # Assertions: Continuous positions mapping along length
    assert m['absCoordinate0'][0] == 500.0   # 0.25 * 2000mm
    assert m['absCoordinate1'][1] == 101.6   # 4 * 25.4mm spacing


# =============================================================================
# STANDALONE MONITOR WORKFLOW TEST
# =============================================================================
def test_beam_monitor_wavelength():
    print("\n--- Testing Standalone Beam Monitor Pass ---")
    
    params = DummyParameters()
    mon_ev = eventsBM(size=2)
    
    # Set mock payload coordinates directly
    mon_ev.matrix['ID'][:2] = np.array([1, 1], dtype='int64')
    mon_ev.matrix['ToF'][:2] = np.array([2000000, 4000000], dtype='int64') # 2ms and 4ms ToF
    mon_ev.fill_count = 2
    
    # Execute the decoupled standalone function
    calculate_monitor_wavelength(mon_ev, params)
    
    m = mon_ev.matrix[:mon_ev.fill_count]
    
    # Verify wavelength populated successfully
    assert not np.isnan(m['wavelength'][0])
    assert m['wavelength'][0] > 0.0


if __name__ == '__main__':
    pytest.main([__file__, "-v", "-s"])