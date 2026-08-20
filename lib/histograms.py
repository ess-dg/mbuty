"""
histograms.py


@author: Sheila Monera Cabarique, francescopiscitelli
--------------------
Vectorized histogramming engine and axis-construction classes for the MBUTY
plotting stage. Replaces libHistograms.py.

Architectural notes
--------------------
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

from lib.colors import INFO, RESET, WARN, ERR, OK



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
                                                        
class LogAxis:
    """
    A single binned axis. `centers` holds the bin-center coordinates used
    both for histogram index calculation (Histogrammer) and for plot extents.
    """

    def __init__(self, start: float, stop: float, steps: int, lin_thresh: float = 1.0):
        self.start = start
        self.stop  = stop
        self.steps = steps
        self.lin_thresh = lin_thresh
        self.centers = self._calculate_symlog_centers()

    def _calculate_symlog_centers(self) -> np.ndarray:
        # Helper functions to convert to/from symlog space
        def forward_symlog(x, thresh):
            return np.sign(x) * np.log10(1.0 + np.abs(x) / thresh)

        def inverse_symlog(y, thresh):
            return np.sign(y) * thresh * (10.0**(np.abs(y)) - 1.0)

        # Force steps to be an odd number so 0.0 lands exactly on a central index
        half_steps = self.steps // 2
        
        # Calculate the log coordinate for the outer positive bound
        y_max = forward_symlog(self.stop, self.lin_thresh)
        
        # Linearly space the exponents from 0 to y_max
        y_pos = np.linspace(0, y_max, half_steps + 1)
        
        # Transform back to physical coordinates
        pos_side = inverse_symlog(y_pos, self.lin_thresh)
        
        # Mirror the positive side to create an exact symmetrical layout
        # pos_side[0] is exactly 0.0, so we skip it on the negative side to avoid duplicates
        neg_side = -pos_side[1:][::-1]
        
        # Concatenate them: [negative values, 0.0, positive values]
        centers = np.concatenate([neg_side, [0.0], pos_side[1:]])
        
        # Update self.steps to reflect the actual size (which will be 2 * half_steps + 1)
        self.steps = len(centers)
        
        return centers

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
    def _calculate_index(values: np.ndarray, centers: np.ndarray) -> np.ndarray:
        
        vmin = centers[0]
        vmax = centers[-1]
        n    = len(centers)
        
        # Prevent runtime warnings by substituting NaN elements with -1 prior to integer evaluation
        nan_mask    = np.isnan(values)
        safe_values = np.where(nan_mask, -1, values)
        
        indexes = np.round((n - 1) * (safe_values - vmin) / (vmax - vmin)).astype(np.int64)
        
        # Force rows containing NaNs out of bounds so the downstream histogrammer masks drop them cleanly
        if np.any(nan_mask):
            indexes[nan_mask] = -1
            
        return indexes

    def hist1d(self, axis_centers: np.ndarray, values: np.ndarray) -> np.ndarray:
        """
        1D histogram based on matching nearest bin centers.

        out_of_bounds == True  -> overflow/underflow events are folded into
                                   the first/last bin (clip-then-count).
        out_of_bounds == False -> overflow/underflow events are dropped and
                                   a warning is printed.
        """
        n_bins = len(axis_centers)
        
        indexes = self._calculate_index(values, axis_centers)
         
        if self.out_of_bounds is False:
            oob = (indexes < 0) | (indexes > (n_bins - 1))
            if np.any(oob):
                print(f'{WARN}WARNING: 1D hist out of bounds values found.{RESET}') 
            hist = np.bincount(indexes[~oob], minlength=n_bins).astype(np.int64)
       
        else:   
            clipped_indexes = np.clip(indexes, 0, n_bins - 1)
            hist = np.bincount(clipped_indexes, minlength=n_bins).astype(np.int64)
    
        return hist
        
        
        # alternative method 
        
        # n_bins = len(axis_centers)
        # Xmin   = np.min(axis_centers) 
        # Xmax   = np.max(axis_centers)
        
        # hist   = np.zeros(n_bins) 
        
        # # denom = Xmax - Xmin
        # # if denom == 0:
        # #     index = np.zeros(len(values), dtype=int)
        # # else:
        # #     index = np.int_(np.around(((n_bins - 1) * ((values - Xmin) / denom))))
            
        # # print(index)
        
        # index = np.int_(np.around(((n_bins-1)*((values-Xmin)/(Xmax-Xmin)))))
        
        # if self.out_of_bounds == False:
        #     if not(np.all(index >= 0) and np.all(index <= n_bins-1)):
        #         print(f'{WARN}WARNING: 1D hist out of bounds values found.{RESET}') 
        #         # return self.hist
        
        # for k in range(n_bins):    
        #     hist[k] = np.sum(index == k) 
        #     if self.out_of_bounds == True:
        #         # fill overflow last bin and first bin
        #         hist[0]  += np.sum(index<0)
        #         hist[-1] += np.sum(index>n_bins-1)
            
        # return hist

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
            return empty, empty, empty
        
        if weights is not None:
            if len(weights) != len(y_values) or len(weights) != len(x_values):
                print(f'\n\t{WARN}ABORTED: Weights is not same length of X or Y!{RESET}\n')
                empty = np.zeros((len(y_centers), len(x_centers)))
                return empty, empty, empty
        
        nx, ny = len(x_centers), len(y_centers)
        
        xi = self._calculate_index(x_values, x_centers)
        yi = self._calculate_index(y_values, y_centers)
        
        if self.out_of_bounds is False:
            oob_mask = (xi < 0) | (xi >= nx) | (yi < 0) | (yi >= ny)
            if np.any(oob_mask):
                print(f'{WARN}WARNING: 2D hist out of bounds values found.{RESET}')
                
            xi_final = xi[~oob_mask]
            yi_final = yi[~oob_mask]
            if weights is not None:
                weights = weights[~oob_mask]    
        
        else:
            xi_final = np.clip(xi, 0, nx - 1)
            yi_final = np.clip(yi, 0, ny - 1)
          
        # trick to use bincount in a flat 1d array 
        flat_indices = yi_final * nx + xi_final
        minlength = ny * nx  
        
        hist_flat = np.bincount(flat_indices, minlength=minlength).astype(np.int64)
        hist = hist_flat.reshape((ny, nx))
            
        # Calculate weighted histogram
        if weights is None:
            hist_weighted = hist.copy()
        else:
            hist_weighted_flat = np.bincount(flat_indices, weights=weights, minlength=minlength).astype(np.int64)
            hist_weighted = hist_weighted_flat.reshape((ny, nx))

        # 4. Calculate normalization
        total_counts = hist.sum()
        if total_counts > 0:
            # do this for nomr to total counts 
            hist_normalized = hist_weighted.astype(np.float64) / float(total_counts)
            #  do this for nomr bin by bin 
            # out_buffer = np.zeros((ny, nx), dtype=np.float64)
            # hist_normalized =  np.divide(hist_weighted, hist, out=out_buffer, where=hist > 0) 
              
        else:
            hist_normalized = np.zeros((ny, nx), dtype=np.float64)
            
        return hist, hist_normalized, hist_weighted
            
            
        # alternative method 
            
        # Xmin   = np.min(x_centers) 
        # Xmax   = np.max(x_centers) 
        
        # Ymin   = np.min(y_centers) 
        # Ymax   = np.max(y_centers) 
        
        # cont = 0
 
        # xi =  np.int_(np.around(((nx-1)*((x_values-Xmin)/(Xmax-Xmin)))))
        # yi =  np.int_(np.around(((ny-1)*((y_values-Ymin)/(Ymax-Ymin)))))
        
        # weig  = np.ones_like(xi) if weights is None else weights
        # # norma = np.zeros((ny,nx))
        # hist = np.zeros((ny,nx))
        # hist_weighted = np.zeros((ny,nx))

        # for k in range(len(x_values)):
         
        #     xx =  xi[k]
        #     yy =  yi[k]
        #     ww =  weig[k]
 
        #     if self.out_of_bounds == True:
                
        #        if ( (xx >= 0) and (xx <= nx-1) and (yy >= 0) and (yy <= ny-1) ):
        #            hist[yy,xx] += 1
        #            hist_weighted[yy,xx] += ww
        #        elif ( (xx >= 0) and (xx > nx-1) and (yy >= 0) and (yy <= ny-1) ):
        #            hist[yy,-1] += 1
        #            hist_weighted[yy,-1] += ww
        #        elif ( (xx < 0) and (xx <= nx-1) and (yy >= 0) and (yy <= ny-1) ):
        #             hist[yy,0] += 1
        #             hist_weighted[yy,0] += ww
        #        elif ( (xx >= 0) and (xx <= nx-1) and (yy < 0) and (yy <= ny-1) ):
        #            hist[0,xx]  += 1
        #            hist_weighted[0,xx]  += ww
        #        elif ( (xx >= 0) and (xx <= nx-1) and (yy >= 0) and (yy > ny-1) ):
        #            hist[-1,xx] += 1
        #            hist_weighted[-1,xx] += ww
                   
        #     elif self.out_of_bounds == False:
                 
        #        if ( (xx >= 0) and (xx <= nx-1) and (yy >= 0) and (yy <= ny-1) ):
        #           hist[yy,xx] += 1
        #           hist_weighted[yy,xx] += ww
        #        else:
        #            if cont == 0:
        #                print('\033[1;33mWARNING: 2D hist out of bounds values found.\033[1;37m') 
        #                cont = 1  
                       
  
        #     #  do this for nomr to total counts 
        #     hist_normalized  =  hist_weighted/(hist.sum())
        #     #  do this for nomr bin by bin 
        #     # self.hist_normalized  =  np.divide(self.hist_weighted, self.hist, out=np.zeros_like(self.hist_weighted), where=self.hist > 0) 
              
        # return hist, hist_normalized, hist_weighted


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
        
        xi = self._calculate_index(x_values, x_centers)
        yi = self._calculate_index(y_values, y_centers)
        zi = self._calculate_index(z_values, z_centers)
        
        oob_x = (xi < 0) | (xi >= nx - 1)
        oob_y = (yi < 0) | (yi >= ny - 1)
        oob_z = (zi < 0) | (zi >= nz - 1)
        
        valid_xy_proj =  ~oob_x
        valid_xy      =  ~oob_x & ~oob_y
        valid_xz      =  ~oob_x & ~oob_z
        
        if self.out_of_bounds is False:
            if np.any(oob_x):
                n_x_invalid = np.sum(oob_x)
                print(f'\n\t{WARN}WARNING: {n_x_invalid:d} out of 1D boundaries{RESET}\n')
            
            xi_final_1d = xi[valid_xy_proj]
            
            xi_final_xy = xi[valid_xy]
            yi_final    = yi[valid_xy] 
            
            xi_final_xz = xi[valid_xz]
            zi_final    = zi[valid_xz]
        
        else:
            xi_final_1d = np.clip(xi, 0, nx - 1)
            xi_final_xy = np.clip(xi, 0, nx - 1)
            yi_final    = np.clip(yi, 0, ny - 1)
            xi_final_xz = np.clip(xi, 0, nx - 1)
            zi_final    = np.clip(zi, 0, nz - 1)
            

        # XYproj: 1D projection on X 
        xy_proj = np.bincount(xi_final_1d, minlength=nx).astype(np.int64)

        # XY: requires both x and y in-bounds.
        flat_xy  = yi_final * nx + xi_final_xy
        xy       = np.bincount(flat_xy, minlength= nx * ny).astype(np.int64).reshape(ny, nx)

        # XZ: requires both x and z in-bounds.
        flat_xz  = xi_final_xz * nz + zi_final
        xz       = np.bincount(flat_xz, minlength= nx * nz).astype(np.int64).reshape(nx, nz)

        return xy, xy_proj, xz

        
        # alternative method 
        # Xmin   = np.min(x_centers) 
        # Xmax   = np.max(x_centers) 
        # Ymin   = np.min(y_centers) 
        # Ymax   = np.max(y_centers) 
        # Zmin   = np.min(z_centers) 
        # Zmax   = np.max(z_centers) 
        
        # xy, xy_proj, xz = np.zeros((ny,nx)) , np.zeros(nx), np.zeros((nx,nz))
        
        # count   = np.zeros((3,2)) #counter for rejected and good evetns
        
        # xi  =  np.int_(np.around(((nx-1)*((x_values-Xmin)/(Xmax-Xmin)))))
        # yi  =  np.int_(np.around(((ny-1)*((y_values-Ymin)/(Ymax-Ymin)))))
        # zi  =  np.int_(np.around(((nz-1)*((z_values-Zmin)/(Zmax-Zmin)))))
        
        
        # for k in range(0,len(x_values),1):
            
        #     xx , yy, zz = xi[k], yi[k], zi[k]
            
            # if ( (xx >= 0) and (xx <= nx-1) ):
                
            #     # 2D hist X-Y
            #     if ( (yy >= 0) and (yy <= ny-1) ):
            #         xy[yy,xx]  += 1
            #         count[0,0] += 1  # if 2D
            #     else:
            #         count[0,1] += 1  # if 1D
               
            #     # 1D hist X
            #     xy_proj[xx]  += 1
            #     count[1,0]   += 1   # if at least 1D
                
            #     if ( (zz >= 0) and (zz <= nz-1) ):
            #              xz[xx,zz]  += 1
            #              count[2,0] += 1
            #     else:
            #              count[2,1] += 1
                         
        #     else:
        #          count[1,1] += 1
                 
                 
        # if count[1,1] != 0 :
        #       print(f'\n \t {WARN}WARNING: {count[1,1]:.1f}% out of 1D boundaries{RESET}\n')
             
        # return xy, xy_proj, xz


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

    def __init__(self, parameters, config: dict):
        self.parameters = parameters
        self.config = config
        self._build_generic_axes()
        self.build_specific_axes()

    def _build_generic_axes(self) -> None:
        p = self.parameters
        self.ax_energy_mon = Axis(0, p.MONitor.maxEnerg, p.MONitor.energyBins)
        self.ax_energy     = Axis(0, p.pulseHeigthSpect.maxEnerg, p.pulseHeigthSpect.energyBins)
        # Calculate steps safely by dividing the total ToF range window by the individual bin width
        tof_steps = int(round(p.plotting.ToFrange / p.plotting.ToFbinning))
        self.ax_tof        = Axis(0, p.plotting.ToFrange, tof_steps)
        self.ax_lambda     = Axis(p.wavelength.lambdaRange[0], p.wavelength.lambdaRange[1], p.wavelength.lambdaBins)


        start = -p.plotting.ToFrange
        stop  =  p.plotting.ToFrange
        steps = round((stop - start) / p.plotting.timeBetwEvBin)
        self.ax_time_between_ev = Axis(start, stop, steps)
        
        # self.ax_time_span = LogAxis(-5e-6, 5e-6, 1024, lin_thresh = 1e-9)
        
        self.ax_time_span =  Axis(-10e-6, 10e-6, 2001)
        
    def build_specific_axes(self) -> None:
        """Override in subclasses to add detector-specific position axes."""
        pass

    def rebuild_all(self) -> None:
        self._build_generic_axes()
        self.build_specific_axes()

    def _resolve_position_bins(self, default_wires: int, default_strips: int) -> tuple[int, int]:
        """
        Dynamically calculates the total matrix grid bin resolution based on the 
        active positionReconstruction string parameter.
        """
        pos_recon = getattr(self.parameters.plotting, 'positionReconstruction', 'W.max-S.cog')
        
        if pos_recon == 'W.max-S.max':
            return default_wires, default_strips
        elif pos_recon == 'W.cog-S.cog':
            return default_wires * 2, default_strips * 2
        elif pos_recon == 'W.max-S.cog':
            return default_wires, default_strips * 2
        else:
            return default_wires, default_strips


class MBAxisSet(BaseAxisSet):
    """Position axes for Multi-Blade (VMM) wire/strip detectors."""

    def build_specific_axes(self) -> None:   

        num_strips  = int(self.config.get('strips', 64))
        num_wires   = int(self.config.get('wires', 32))
        blades_inclination = float(self.config.get('bladesInclination_deg', 5.1))
        wire_pitch  = float(self.config.get('wirePitch_mm', 4.0))
        strip_pitch = float(self.config.get('stripPitch_mm', 4.0))
        # n_cass      =  self.config.get('units', 0)
        topo        =  self.config.get('topology', [])
        offset_mm   =  self.config.get('offset1stWires_mm', 0)
        
        self.ax_mult = Axis(0, num_strips - 1, num_strips)
        
        sine   = np.sin(np.deg2rad(blades_inclination))
        
        # sine = 1 
      
        # offset_mm  = 110
        
        pos_w_bins, pos_s_bins = self._resolve_position_bins(num_wires, num_strips)
  
        min_id = min(d['ID'] for d in topo)    
        max_id = max(d['ID'] for d in topo)    
        
        start = min_id * num_wires
        stop  = (max_id+1) * num_wires
        self.ax_x  = Axis(start, stop-1, int((max_id + 1 - min_id)*pos_w_bins - int(pos_w_bins/num_wires - 1)))  # wire axis
  
        self.ax_y = Axis(0, num_strips-1, pos_s_bins - int(pos_s_bins/num_strips - 1))  # strip axis
  
        # start = min_id * (num_wires * wire_pitch * sine + offset_mm)
        # stop  = (max_id+1) * (num_wires * wire_pitch * sine)  +  (max_id * offset_mm)
        
        start = min_id * offset_mm
        stop  = (num_wires * wire_pitch * sine)  +  (max_id * offset_mm)
        
        self.ax_x_mm  = Axis(start, stop-1, self.ax_x.steps)  # wire axis, mm
  
        self.ax_y_mm = Axis(0, (num_strips - 1) * strip_pitch, self.ax_y.steps)  # strip axis, mm
          
 
class MGAxisSet(BaseAxisSet):
    """Position axes for Multi-Grid detector (VMM-like wire/strip geometry)."""

    def build_specific_axes(self, unit_offset: float = 0) -> None:        
        # Multi-Grid names the layout parameter 'grids' instead of 'strips'
        num_grids   = int(self.config.get('grids', 88))
        num_wires   = int(self.config.get('wires', 120))
        wirePitchX_mm  = float(self.config.get('wirePitchX_mm', 22))
        gridPitchY_mm = float(self.config.get('gridPitchY_mm', 25))
        # n_units    =  self.config.get('units', 0)
        topo       =  self.config.get('topology', [])
        offset_mm   =  self.config.get('linearOffset1stWires_mm', 0)
        

        self.ax_mult = Axis(0, num_grids - 1, num_grids)
        
        # Pass grids directly as the strips argument to the shared resolver
        pos_w_bins, pos_g_bins = self._resolve_position_bins(num_wires, num_grids)

        min_id = min(d['ID'] for d in topo)    
        max_id = max(d['ID'] for d in topo)    
        
        start = min_id * num_wires
        stop  = (max_id+1) * num_wires
        
        self.ax_x  = Axis(start, stop-1, int((max_id + 1 - min_id)*pos_w_bins - int(pos_w_bins/num_wires - 1)))  # wire axis

        self.ax_y = Axis(0, num_grids-1, pos_g_bins - int(pos_g_bins/num_grids - 1))  # grid axis

        # Physical coordinates TO BE FINISHED
        start = min_id * offset_mm
        stop  = num_wires * wirePitchX_mm + max_id * offset_mm
        
        self.ax_x_mm = Axis(start, stop, self.ax_x.steps)  # wire axis, mm
        self.ax_y_mm = Axis(0, (num_grids - 1) * gridPitchY_mm, self.ax_y.steps)  # grid axis, mm

        
        
class R5560AxisSet(BaseAxisSet):
    """Position axes for R5560 tube detector (1D position geometry)."""

    def build_specific_axes(self) -> None:
        # p   = self.parameters
        # n_units      =  self.config.get('units', 0)
        bins         = int(self.config.get('positionBins', 256))
        tube_length  = self.config.get('tubeLength', 256)
        tube_spacing = self.config.get('tubeSpacing', 10)
        topo         =  self.config.get('topology', [])
        
        self.ax_mult = Axis(0, 9, 10)  # Multiplicity 0-9

        # Normalized position (0-1 mapped to tube)
        self.ax_length = Axis(0, 1, bins)
        
        min_id = min(d['ID'] for d in topo)    
        max_id = max(d['ID'] for d in topo)  

        self.ax_tubes = Axis(min_id, max_id, max_id-min_id+1)

        # Physical position in mm along tube
        self.ax_length_mm  = Axis(0, tube_length, bins)

        self.ax_tubes_mm = Axis(min_id*tube_spacing, max_id*tube_spacing, (max_id-min_id+1))  


class SKADIAxisSet(BaseAxisSet):
    def build_specific_axes(self) -> None:
        pix           = int(self.config['pix'])
        tiles_per_row = int(self.config['tilesPerRow'])
        # Pull tilesPerCol from config if available; otherwise safely default to a balanced square configuration
        tiles_per_col = int(self.config.get('tilesPerCol', tiles_per_row))
        
        pix_size_mm   = float(self.config['pix_size_mm'])
        gap_x_mm      = float(self.config['gapX_mm'])
        gap_y_mm      = float(self.config['gapY_mm'])

        # 1. Pixel index boundaries (0-indexed global grid matrices)
        max_pix_x = (tiles_per_row * pix) - 1
        max_pix_y = (tiles_per_col * pix) - 1

        self.ax_pix_x = Axis(0, max_pix_x, tiles_per_row * pix)
        self.ax_pix_y = Axis(0, max_pix_y, tiles_per_col * pix)

        # 2. Absolute physical millimeter boundaries (including inter-tile gaps)
        stop_x_mm = (tiles_per_row * pix * pix_size_mm) + ((tiles_per_row - 1) * gap_x_mm)
        stop_y_mm = (tiles_per_col * pix * pix_size_mm) + ((tiles_per_col - 1) * gap_y_mm)

        # Calculate total gap bins collectively to prevent cumulative rounding drift
        total_gap_bins_x = int(round(((tiles_per_row - 1) * gap_x_mm) / pix_size_mm))
        total_gap_bins_y = int(round(((tiles_per_col - 1) * gap_y_mm) / pix_size_mm))

        # Sum the baseline pixel bins with the globally rounded gap bins
        steps_x_mm = (tiles_per_row * pix) + total_gap_bins_x
        steps_y_mm = (tiles_per_col * pix) + total_gap_bins_y

        # Define the clean, un-drifted physical axes
        self.ax_pix_x_mm = Axis(0, stop_x_mm, steps_x_mm)
        self.ax_pix_y_mm = Axis(0, stop_y_mm, steps_y_mm)
        
class NMXAxisSet(BaseAxisSet):
    """
    Axis set for NMX. 
    ax_x_mm/ax_y_mm (absolute-units variants) are deliberately omitted:
    no stripPitch_mm in the NMX config yet, and abs-units plotting isn't
    implemented for NMX regardless (see NMXEventsPlotter overrides).
    """

    def build_specific_axes(self) -> None:
        num_strips = int(self.config.get('strips', 640))  # per-edge channel count (5 hybrids * 2 asics * 64 ch)

        self.ax_mult = Axis(0, num_strips - 1, num_strips)

        full_width = 2 * num_strips  # tiled per-bank width, mirrors NMXEventsPlotter.FULL_WIDTH
        self.ax_x = Axis(0, full_width - 1, full_width)
        self.ax_y = Axis(0, full_width - 1, full_width)

        
###############################################################################
###############################################################################
###############################################################################
###############################################################################
if __name__ == '__main__':
    
    path = '/Users/francescopiscitelli/git_repos/mbuty/MBUTYcap/'
    
    # from lib.config_validator import validate_config, load_config

    # from lib import parameters as para


    # confPath    = path + 'config/'
    
    # confFileName  = "AMOR2.json"
    
    # # confFileName  = "MIRACLES3.json"
    
    # config = load_config(confPath+confFileName)
    # validate_config(config)
    
    
    # parameters  = para.parameters(confPath+confFileName)

    # aa = MBAxisSet(parameters, config)
    
    # # print(aa.ax_wires.centers)
    # # print(aa.ax_strips.centers)
    
    # bb = MGAxisSet(parameters, config)
    
    # cc = R5560AxisSet(parameters, config)
    
    # print(aa.ax_strips.centers)
    
    # coord = np.ones_like(aa.ax_strips.centers)
    
    # coord = np.array([10.5, 20.0, 5.0, 30.2])
    
    # coord[0] = 10
    
    # print(coord)
    
    # hist = np.bincount(coord)
    
    hg = Histogrammer(True)   
    
    # x_values  = np.array([0,6.9, 7.1, 7.4, 9.8, 7.1, 10, 6.9, 4, 55, 8.1])
    # x_centers = np.arange(6, 10.5, 0.5) 
    # hist1 = hg.hist1d(x_centers, x_values)
    
    
    
    x_centers = np.array([1, 2, 3, 4, 5, 6, 7])
    y_centers = np.array([13, 16, 19, 22])
    z_centers = np.array([55, 65, 75, 85])
    
    x_values = np.array([1.2, 5.9, 7, 6, 99])
    y_values = np.array([15, 21, 17, 20.9, 55])
    z_values = np.array([55, 66, -1, 32, 65])
    
  
    # weig = np.array([10, 20, 7, 3])
    

    # hist, hist_n, hits_w = hg.hist2d(x_centers, x_values, y_centers, y_values)
    
    xy, xy_proj, xz = hg.hist_xyz(x_centers, x_values, y_centers, y_values, z_centers, z_values)

    
    
    
    start =  -100e-3
    stop  =  100e-3
    # steps = round((stop - start) / p.plotting.timeBetwEvBin)
    
    steps = 1024

    
    ax_time_between_ev = LogAxis(start, stop, steps, lin_thresh=1e-10)
    
    cee = ax_time_between_ev.centers