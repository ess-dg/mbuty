import numpy as np
import sys
import os

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib.colors import INFO, WARN, RESET

# =============================================================================
# Shared Physics Utility
# =============================================================================

class _Tof2LambdaConverter:
    """Converts between neutron time-of-flight and wavelength."""

    _ht    = 1.054e-34  # J*s (reduced Planck)
    _mn    = 1.67e-27   # kg  (neutron mass)
    _const = ((_ht**2) * 4 * (np.pi**2) / (2 * _mn)) * 1e20 * 6.24e18  # A^2 * eV

    @classmethod
    def tof_to_lambda(cls, distance_m: np.ndarray, tof_s: np.ndarray) -> np.ndarray:
        """Convert ToF (s) and distance (m) to wavelength (Angstrom)."""
        velocity = np.divide(distance_m, tof_s,
                             out=np.zeros_like(tof_s), where=tof_s != 0)
        energy   = 0.5 * (cls._mn / 1.6e-19) * velocity**2
        lamb     = np.where(energy > 0,
                            np.sqrt(cls._const / np.where(energy > 0, energy, 1.0)),
                            np.nan)
        return lamb

    @classmethod
    def lambda_to_tof(cls, distance_m, wavelength_a: float) -> float:
        """Convert wavelength (Angstrom) and distance (m) to ToF (s)."""
        energy   = cls._const / wavelength_a**2
        velocity = np.sqrt(2 * energy / (cls._mn / 1.6e-19))
        return distance_m / velocity


# =============================================================================
# Base Abs Units Calculator
# =============================================================================

class BaseAbsUnitsCalculator:
    """
    Shared wavelength configuration and pipeline orchestration for all detectors.
    Subclasses implement calculate_positions() for detector-specific geometry.
    All methods write directly into the event container matrix fields.

    Parameters
    ----------
    events     : events container (eventsVMMnormal, eventsR5560, etc.)
    config     : flat dict loaded from JSON config file
    parameters : legacy parameters object (dot-notation access)
    """

    def __init__(self, events, config: dict, parameters):
        self.events     = events
        self.config     = config
        self.parameters = parameters

    def calculate_positions(self) -> None:
        """Override in subclasses to implement detector-specific geometry."""
        raise NotImplementedError(
            f'{self.__class__.__name__} must implement calculate_positions()'
        )

    def calculate_wavelength(self) -> None:
        """
        Compute neutron wavelength from ToF and chopper parameters.
        Uses absCoordinate2 (detector depth in mm) if present in schema,
        otherwise uses distance alone.
        Writes result into matrix['wavelength'].
        """
        print(f"{INFO}Calculating neutron wavelength ... {RESET}", end='')

        m     = self.events.matrix[:self.events.fill_count]
        tof_s = m['ToF'].astype('float64') / 1e9  # ns -> s

        # Depth correction: VMM detectors have absCoordinate2 (wire depth in mm)
        if 'absCoordinate2' in m.dtype.names:
            distance_mm = m['absCoordinate2'] + self.parameters.wavelength.distance
        else:
            distance_mm = np.full(len(m), float(self.parameters.wavelength.distance),
                                  dtype='float64')

        distance_m = distance_mm * 1e-3

        if self.parameters.wavelength.multipleFramePerReset:
            tof_start        = _Tof2LambdaConverter.lambda_to_tof(
                                   distance_m,
                                   self.parameters.wavelength.lambdaMIN)
            period_per_bunch = (self.parameters.wavelength.chopperPeriod /
                                self.parameters.wavelength.numOfBunchesPerPulse)
            tof_s = ((tof_s
                      - tof_start
                      - self.parameters.wavelength.chopperPickUpDelay)
                     % period_per_bunch) + tof_start

        wavelength = _Tof2LambdaConverter.tof_to_lambda(distance_m, tof_s)
        self.events.matrix['wavelength'][:self.events.fill_count] = np.round(wavelength, 2)
        # print('done')

    def process_pipeline(self, remove_invalid_tofs: bool = False) -> None:
        """Convenience execution loop: triggers timing alignment, positions, then wavelength."""
        # 1. Delegate core timeline matching directly to the container method
        self.events.compute_and_filter_tof(remove_invalid=remove_invalid_tofs)
        
        if self.parameters.plotting.ToFGate:
            self.events.trim_tof_range(self.parameters.plotting.ToFGateRange)
        
        # 2. Run geometric spatial conversions
        self.calculate_positions()
        
        # 3. Process spectroscopic mapping
        if self.parameters.wavelength.calculateLambda is True:
            self.calculate_wavelength()


# =============================================================================
# Multi-Blade Abs Units Calculator
# =============================================================================

class MBAbsUnitsCalculator(BaseAbsUnitsCalculator):
    """
    Position conversion for Multi-Blade detector.

    coordinate0 (wire global) -> absCoordinate0 (X along blade, mm)
                               -> absCoordinate2 (Z depth across wires, mm)
    coordinate1 (strip)       -> absCoordinate1 (strip position, mm)
    """

    def calculate_positions(self) -> None:
        print(f"{INFO}Calculating MB absolute coordinates ... {RESET}")

        m           = self.events.matrix[:self.events.fill_count]
        n_wires     = int(self.config['wires'])
        wire_pitch  = float(self.config['wirePitch_mm'])
        strip_pitch = float(self.config['stripPitch_mm'])
        inclination = float(self.config['bladesInclination_deg'])
        offset_1st  = float(self.config['offset1stWires_mm'])
        unit_ids    = [entry['ID'] for entry in self.config['topology']]

        sine = np.sin(np.deg2rad(inclination))
        cosi = np.cos(np.deg2rad(inclination))
        
        # sine = 1 
        # offset_1st = 110

        # note coordiate when not present is nan
        has_wire   = m['coordinate0'] >= 0
        has_strip  = m['coordinate1'] >= 0

        # Only perform modulo mapping on rows containing a valid wire coordinate
        
        # wire_local = np.where(has_wire, np.mod(m['coordinate0'].astype('int64'), n_wires), 0)
        
        # Replace NaN with a dummy value (e.g., -1) so the int64 cast doesn't complain
        safe_coord = np.nan_to_num(m['coordinate0'], nan=-1)
        wire_local = np.where(has_wire, (np.round(np.mod(safe_coord,n_wires))), -1)

        # absCoordinate0: X along blade (mm)
        x_mm = np.full(len(m), np.nan, dtype='float64')
        for uid in unit_ids:
 
            sel = (m['ID'] == uid) & has_wire  # Only assign if the row has a wire
    
            x_mm[sel] = np.round(
                wire_local[sel] * wire_pitch * sine + offset_1st * uid, 2
            )
        # Strip-only events (no wire) get a nan sentinel
        x_mm[~has_wire] = np.nan

        # absCoordinate1: strip position (mm), nan for 1D wire-only events
        strip_mm  = np.where(has_strip,
                             np.round(m['coordinate1'] * strip_pitch, 2),
                             np.nan)

        # absCoordinate2: Z depth across wires (mm), nan for 1D strip-only events
        z_mm = np.where(has_wire,
                        np.round(wire_local * wire_pitch * cosi, 2),
                        np.nan)

        self.events.matrix['absCoordinate0'][:self.events.fill_count] = x_mm
        self.events.matrix['absCoordinate1'][:self.events.fill_count] = strip_mm
        self.events.matrix['absCoordinate2'][:self.events.fill_count] = z_mm
        # print('done')


# =============================================================================
# Multi-Grid Abs Units Calculator
# =============================================================================

class MGAbsUnitsCalculator(BaseAbsUnitsCalculator):
    """
    Position conversion for Multi-Grid detector.

    coordinate0 (wire global) -> absCoordinate0 (X row position, mm)
                               -> absCoordinate2 (Z depth, mm)
    coordinate1 (grid)        -> absCoordinate1 (Y grid position, mm)
    """

    def calculate_positions(self) -> None:
        print(f"{INFO}Calculating MG absolute coordinates  ... {RESET}")

        m             = self.events.matrix[:self.events.fill_count]
        n_wires       = int(self.config['wires'])
        wires_per_row = int(self.config['wiresPerRow'])
        pitch_x       = float(self.config['wirePitchX_mm'])
        pitch_z       = float(self.config['wirePitchZ_mm'])
        pitch_y       = float(self.config['gridPitchY_mm'])
        unit_ids      = [entry['ID'] for entry in self.config['topology']]
        
        # Track valid coordinate masks for 1D event alignment safety
        has_wire  = m['coordinate0'] >= 0
        has_grid  = m['coordinate1'] >= 0

        # Bring global wire coordinate back to local within each column safely
        wire_local = np.zeros(len(m), dtype='int64')
        for k, uid in enumerate(unit_ids):
            sel = (m['ID'] == uid) & has_wire
            wire_local[sel] = m['coordinate0'][sel].astype('int64') - uid * n_wires

        # Row along X and depth along Z within each row
        wire_row = np.floor_divide(wire_local, wires_per_row)
        wire_z   = np.mod(wire_local, wires_per_row)

        # absCoordinate0: X row position (mm), nan for grid-only events
        x_mm = np.where(has_wire, np.round(wire_row * pitch_x, 2), np.nan)

        # absCoordinate1: Y grid position (mm), nan for wire-only events
        y_mm = np.where(has_grid, np.round(m['coordinate1'] * pitch_y, 2), np.nan)

        # absCoordinate2: Z depth (mm), nan for grid-only events
        z_mm = np.where(has_wire, np.round(wire_z * pitch_z, 2), np.nan)

        # ---------------------------------------------------------------------
        # NOTE: Column relative position / trigonometry loop is left 
        # unfinished. Because column angular offsets are omitted, the calculated X 
        # coordinates (wire channels) will be overlapping/mapped on top of each other.
        #
        # for k, cass in enumerate(self.parameters.config.DETparameters.cassInConfig):
        #      selectCass = self.events.Cassette == cass
        #      # here do trigonometry ... 
        # ---------------------------------------------------------------------

        # Write results directly into preallocated matrix block
        self.events.matrix['absCoordinate0'][:self.events.fill_count] = x_mm
        self.events.matrix['absCoordinate1'][:self.events.fill_count] = y_mm
        self.events.matrix['absCoordinate2'][:self.events.fill_count] = z_mm
        # print('done')

# =============================================================================
# R5560 Abs Units Calculator
# =============================================================================

class R5560AbsUnitsCalculator(BaseAbsUnitsCalculator):
    """
    Position conversion for He-3 continuous gas tube detector (CAEN R5560).

    coordinate0 (fractional position along tube) -> absCoordinate0 (mm)
    coordinate1 (tube ID)                        -> absCoordinate1 (mm)
    """

    def calculate_positions(self) -> None:
        print(f"{INFO}Calculating absolute coordinates  ... {RESET}")

        m            = self.events.matrix[:self.events.fill_count]
        tube_length  = float(self.config['tubeLength'])   # mm
        tube_spacing = float(self.config['tubeSpacing'])  # mm

        pos_mm  = np.round(m['coordinate0'] * tube_length,  3)
        tube_mm = np.round(m['coordinate1'] * tube_spacing, 3)

        self.events.matrix['absCoordinate0'][:self.events.fill_count] = pos_mm
        self.events.matrix['absCoordinate1'][:self.events.fill_count] = tube_mm
        # print('done')
# =============================================================================
# SKADI Abs Units Calculator
# =============================================================================

class SKADIAbsUnitsCalculator(BaseAbsUnitsCalculator):
    """
    Position conversion for SKADI pixel detector.

    coordinate0 = x_tile * pix + adj_col  (absolute pixel column within this
                                           bank's tile grid, from mapping stage)
    coordinate1 = y_tile * pix + adj_row  (absolute pixel row, same grid)

    Physical mm position isn't a flat coordinate * pix_size_mm scaling
    because there's a gap between tiles. Each tile occupies
    (pix * pix_size_mm + gap_mm) of physical space, which expands to:

        absCoordinate0 = coordinate0 * pix_size_mm + x_tile * gapX_mm

    where x_tile = coordinate0 // pix (recovered with the same divmod
    relationship the mapping stage used to build coordinate0 in the first
    place). Same logic for absCoordinate1 with gapY_mm and y_tile.
    """

    def calculate_positions(self) -> None:
        print(f"{INFO}Calculating SKADI absolute coordinates ... {RESET}")

        m           = self.events.matrix[:self.events.fill_count]
        pix         = int(self.config['pix'])
        pix_size_mm = float(self.config['pix_size_mm'])
        gap_x_mm    = float(self.config['gapX_mm'])
        gap_y_mm    = float(self.config['gapY_mm'])

        x_tile = np.floor_divide(m['coordinate0'].astype('int64'), pix)
        y_tile = np.floor_divide(m['coordinate1'].astype('int64'), pix)

        x_mm = np.round(m['coordinate0'] * pix_size_mm + x_tile * gap_x_mm, 2)
        y_mm = np.round(m['coordinate1'] * pix_size_mm + y_tile * gap_y_mm, 2)

        self.events.matrix['absCoordinate0'][:self.events.fill_count] = x_mm
        self.events.matrix['absCoordinate1'][:self.events.fill_count] = y_mm
      
  
# =============================================================================
# Standalone Monitor Function
# =============================================================================

def calculate_monitor_wavelength(monitor_events, parameters) -> None:
    """Wavelength for monitor events — fixed distance, no depth correction."""
    print(f"{INFO}Calculating monitor wavelength ... {RESET}", end='')

    m          = monitor_events.matrix[:monitor_events.fill_count]
    tof_s      = m['ToF'].astype('float64') / 1e9
    distance_m = parameters.MONitor.MONDistance * 1e-3

    wavelength = _Tof2LambdaConverter.tof_to_lambda(distance_m, tof_s)
    monitor_events.matrix['wavelength'][:monitor_events.fill_count] = np.round(wavelength, 2)
    # print('done')