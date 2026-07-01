"""
histograms.py

Vectorized histogramming engine and axis-construction classes for the MBUTY
plotting stage. Replaces libHistograms.py.

Architectural notes
--------------------
- No physics/math was changed versus the legacy implementation, EXCEPT one
  bug fix (see Histogrammer.hist1d docstring) and the removal of per-event
  Python loops in favour of vectorized np.bincount binning.
- Axis stores bin *centers* (np.linspace(start, stop, steps)), matching the
  legacy convention where index = round((nbins-1) * (x - xmin) / (xmax - xmin)).
- BaseAxisSet builds axes common to every detector (energy, ToF, wavelength,
  instantaneous rate). Detector-specific position axes (wire/strip/tube
  coordinates) are supplied by build_specific_axes() overrides in concrete
  subclasses (e.g. VMMAxisSet).
"""

import numpy as np
import sys
import os
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from newLib.colors import INFO, RESET, WARN, ERR, OK


# ============================================================================
# Axis
# ============================================================================

class Axis:
    """
    A single binned axis. `centers` holds the bin-center coordinates used
    both for histogram index calculation (Histogrammer) and for plot extents.
    """

    def __init__(self, start: float, stop: float, steps: int):
        self.start = start
        self.stop  = stop
        self.steps = steps
        self.centers = np.linspace(start, stop, steps)

    def rebuild(self, start=None, stop=None, steps=None) -> 'Axis':
        """Regenerate centers in place after manually editing start/stop/steps."""
        self.start = self.start if start is None else start
        self.stop  = self.stop  if stop  is None else stop
        self.steps = self.steps if steps is None else steps
        self.centers = np.linspace(self.start, self.stop, self.steps)
        return self


# ============================================================================
# Histogramming engine (fully vectorized)
# ============================================================================

class Histogrammer:
    """
    Builds 1D / 2D / coupled XYZ histograms against pre-built Axis bin
    centers. All binning is vectorized via np.bincount; there are no
    per-event Python loops, unlike the legacy `histog` class this replaces.
    """

    def __init__(self, out_of_bounds: bool = True):
        self.out_of_bounds = out_of_bounds

    @staticmethod
    def _bin_index(values: np.ndarray, centers: np.ndarray) -> np.ndarray:
        n = len(centers)
        vmin, vmax = centers[0], centers[-1]
        return np.rint((n - 1) * (values - vmin) / (vmax - vmin)).astype(np.int64)

    def hist1d(self, axis_centers: np.ndarray, values: np.ndarray) -> np.ndarray:
        """
        1D histogram.

        out_of_bounds == True  -> overflow/underflow events are folded into
                                   the first/last bin (clip-then-count).
        out_of_bounds == False -> overflow/underflow events are dropped and
                                   a warning is printed.

        Bug fix vs legacy hist1D: the original accumulated the out-of-bounds
        overflow into bin 0 / bin -1 *inside* the per-bin loop, so it added
        the overflow count `nbins` times instead of once. Here it is folded
        in exactly once via clip-then-bincount.
        """
        n_bins = len(axis_centers)
        idx = self._bin_index(values, axis_centers)
        oob = (idx < 0) | (idx > n_bins - 1)

        if self.out_of_bounds is False:
            if np.any(oob):
                print(f'{WARN}WARNING: 1D hist out of bounds values found.{RESET}')
            return np.bincount(idx[~oob], minlength=n_bins).astype(np.float64)

        idx_clipped = np.clip(idx, 0, n_bins - 1)
        return np.bincount(idx_clipped, minlength=n_bins).astype(np.float64)

    def hist2d(self, x_centers, x_values, y_centers, y_values, weights=None):
        """
        2D histogram. Returns (hist, hist_normalized).

        If `weights` is given, `hist` holds the summed weight per bin and
        `hist_normalized` holds the per-bin mean (hist / counts); otherwise
        `hist_normalized` is identical to `hist` (plain counts).
        """
        if len(x_values) != len(y_values):
            print(f'\n\t{WARN}ABORTED: X and Y not same length!{RESET}\n')
            empty = np.zeros((len(y_centers), len(x_centers)))
            return empty, empty

        nx, ny = len(x_centers), len(y_centers)
        xi = self._bin_index(x_values, x_centers)
        yi = self._bin_index(y_values, y_centers)

        in_bounds = (xi >= 0) & (xi <= nx - 1) & (yi >= 0) & (yi <= ny - 1)

        if self.out_of_bounds is False:
            if not np.all(in_bounds):
                print(f'{WARN}WARNING: 2D hist out of bounds values found.{RESET}')
            xi, yi = xi[in_bounds], yi[in_bounds]
            w = weights[in_bounds] if weights is not None else None
        else:
            xi = np.clip(xi, 0, nx - 1)
            yi = np.clip(yi, 0, ny - 1)
            w = weights

        flat_idx = yi * nx + xi
        counts = np.bincount(flat_idx, minlength=nx * ny).astype(np.float64).reshape(ny, nx)

        if w is None:
            return counts, counts

        sums = np.bincount(flat_idx, weights=w, minlength=nx * ny).astype(np.float64).reshape(ny, nx)
        with np.errstate(divide='ignore', invalid='ignore'):
            means = np.where(counts > 0, sums / counts, 0.0)
        return sums, means

    def hist_xyz(self, x_centers, x_values, y_centers, y_values, z_centers, z_values):
        """
        Builds three histograms in one pass over (x, y, z) triplets, mirroring
        the legacy histXYZ used for detector-image + ToF plots:
          - xy      : 2D histogram of x vs y (both must be in-bounds)
          - xy_proj : 1D projection of x (only x needs to be in-bounds)
          - xz      : 2D histogram of x vs z (only x and z need to be in-bounds)
        """
        if not (len(x_values) == len(y_values) == len(z_values)):
            print(f'\n\t{WARN}ABORT: X and/or Y and/or Z not same length!{RESET}\n')
            empty_xy   = np.zeros((len(y_centers), len(x_centers)))
            empty_proj = np.zeros(len(x_centers))
            empty_xz   = np.zeros((len(x_centers), len(z_centers)))
            return empty_xy, empty_proj, empty_xz

        nx, ny, nz = len(x_centers), len(y_centers), len(z_centers)
        xi = self._bin_index(x_values, x_centers)
        yi = self._bin_index(y_values, y_centers)
        zi = self._bin_index(z_values, z_centers)

        x_valid = (xi >= 0) & (xi <= nx - 1)
        n_x_invalid = int(np.sum(~x_valid))
        if n_x_invalid != 0 and len(x_values) > 0:
            pct = 100.0 * n_x_invalid / len(x_values)
            print(f'\n\t{WARN}WARNING: {pct:.1f}% out of 1D boundaries{RESET}\n')

        xi_v, yi_v, zi_v = xi[x_valid], yi[x_valid], zi[x_valid]

        # XYproj: 1D projection on X -- only requires x to be in-bounds.
        xy_proj = np.bincount(xi_v, minlength=nx).astype(np.float64)

        # XY: requires both x and y in-bounds.
        xy_mask  = (yi_v >= 0) & (yi_v <= ny - 1)
        flat_xy  = yi_v[xy_mask] * nx + xi_v[xy_mask]
        xy = np.bincount(flat_xy, minlength=nx * ny).astype(np.float64).reshape(ny, nx)

        # XZ: requires both x and z in-bounds.
        xz_mask  = (zi_v >= 0) & (zi_v <= nz - 1)
        flat_xz  = xi_v[xz_mask] * nz + zi_v[xz_mask]
        xz = np.bincount(flat_xz, minlength=nx * nz).astype(np.float64).reshape(nx, nz)

        return xy, xy_proj, xz


# ============================================================================
# Axis sets
# ============================================================================

class BaseAxisSet:
    """
    Axes common to every detector type: energy spectra (PHS + monitor),
    ToF, wavelength, and instantaneous rate. Detector-specific position
    axes (wire/strip/tube coordinates) are built by build_specific_axes(),
    which concrete subclasses must implement.
    """

    def __init__(self, parameters, offset: float = 0):
        self.parameters = parameters
        self._build_generic_axes()
        self.build_specific_axes(offset)

    def _build_generic_axes(self) -> None:
        p = self.parameters
        self.ax_energy_mon = Axis(0, p.MONitor.maxEnerg, p.MONitor.energyBins)
        self.ax_energy     = Axis(0, p.pulseHeigthSpect.maxEnerg, p.pulseHeigthSpect.energyBins)
        self.ax_tof        = Axis(0, p.plotting.ToFrange, p.plotting.ToFbins)
        self.ax_lambda     = Axis(p.wavelength.lambdaRange[0], p.wavelength.lambdaRange[1], p.wavelength.lambdaBins)

        start = -p.plotting.ToFrange
        stop  =  p.plotting.ToFrange
        steps = round((stop - start) / p.plotting.instRateBin)
        self.ax_inst_rate = Axis(start, stop, steps)

    def build_specific_axes(self, offset: float = 0) -> None:
        """Override in subclasses to add detector-specific position axes."""
        raise NotImplementedError

    def rebuild_all(self, offset: float = 0) -> None:
        self._build_generic_axes()
        self.build_specific_axes(offset)


class VMMAxisSet(BaseAxisSet):
    """Position axes for Multi-Blade / Multi-Grid (VMM) wire/strip detectors."""

    def build_specific_axes(self, cass_offset: float = 0) -> None:
        p   = self.parameters
        det = p.config.DETparameters

        self.ax_mult = Axis(0, det.numOfStrips - 1, det.numOfStrips)

        sine   = np.sin(np.deg2rad(det.bladesInclination))
        n_cass = len(det.cassInConfig)

        offset = cass_offset * det.numOfWires
        self.ax_wires = Axis(
            offset,
            n_cass * det.numOfWires - 1 + offset,
            n_cass * p.plotting.posWbins - int(p.plotting.posWbins / det.numOfWires - 1),
        )

        self.ax_strips = Axis(
            0,
            det.numOfStrips - 1,
            p.plotting.posSbins - int(p.plotting.posSbins / det.numOfStrips - 1),
        )

        offset_mm = cass_offset * det.numOfWires * det.wirePitch * sine
        self.ax_wires_mm = Axis(
            offset_mm,
            (n_cass * det.numOfWires - 1) * det.wirePitch * sine + offset_mm,
            self.ax_wires.steps,
        )

        self.ax_strips_mm = Axis(
            0,
            (det.numOfStrips - 1) * det.stripPitch,
            self.ax_strips.steps,
        )
        
class R5560AxisSet(BaseAxisSet):
    """Position axes for R5560 tube detector (1D position geometry)."""

    def build_specific_axes(self, cass_offset: float = 0) -> None:
        p   = self.parameters
        det = p.config.DETparameters

        self.ax_mult = Axis(0, 9, 10)  # Multiplicity 0-9

        # Normalized position (0-1 mapped to tube)
        self.ax_wires = Axis(0, 1, p.config.DETparameters.positionBins)

        # Cassette ID axis (discrete; min-max of configured cassettes)
        cf = np.array(det.cassInConfig)
        mincf, maxcf = np.min(cf), np.max(cf)
        self.ax_strips = Axis(mincf, maxcf, maxcf - mincf + 1)

        # Physical position in mm
        self.ax_wires_mm = Axis(0, det.tubeLength, p.config.DETparameters.positionBins)

        # Cassette physical spacing
        self.ax_strips_mm = Axis(0, 0, 1)  # Placeholder; overridden below
        self.ax_strips_mm.centers = np.array(det.cassInConfig) * det.tubeSpacing


class MGAxisSet(BaseAxisSet):
    """Position axes for Multi-Grid detector (VMM-like wire/strip geometry)."""

    def build_specific_axes(self, cass_offset: float = 0) -> None:
        p   = self.parameters
        det = p.config.DETparameters

        self.ax_mult = Axis(0, det.numOfStrips - 1, det.numOfStrips)

        n_cass = len(det.cassInConfig)
        offset = cass_offset * det.numOfWires

        self.ax_wires = Axis(
            offset,
            n_cass * det.numOfWires - 1 + offset,
            n_cass * p.plotting.posWbins - int(p.plotting.posWbins / det.numOfWires - 1),
        )

        self.ax_strips = Axis(
            0,
            det.numOfStrips - 1,
            p.plotting.posSbins - int(p.plotting.posSbins / det.numOfStrips - 1),
        )

        # Physical coordinates (4 mm pitch for MG)
        self.ax_wires_mm = Axis(
            0,
            (n_cass * det.numOfWires - 1) * 4,
            self.ax_wires.steps,
        )

        self.ax_strips_mm = Axis(
            0,
            (det.numOfStrips - 1) * 4,
            self.ax_strips.steps,
        )