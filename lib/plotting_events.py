"""
plotting_events.py

Event-level (post-clustering) physics plots for the MBUTY pipeline. Ports
the events plotting classes scattered across libPlotting.py (Multi-Blade +
generic base), libPlottingMG.py (Multi-Grid), and libPlottingR5560.py
(R5560 tubes) into a matrix-backed hierarchy built on top of
plotting_base.BasePlotter, reproducing the legacy plot logic, labels,
titles, and colors exactly.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
import sys, os
import matplotlib.figure

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
from lib.colors import WARN, RESET
from lib.histograms import Histogrammer
from lib.plotting_base import PlotGrid, BasePlotter, log_scale_norm, _safe_colorbar


# ============================================================================
# Detector-agnostic base
# ============================================================================

class BaseEventsPlotter(BasePlotter):
    """
    Detector-agnostic events scaffolding: axis-set access, unit selection by
    mapped 'ID', and direct access onto this detector's flat configuration
    dictionary (needed for layout math and "not supported" messages).
    """
    
    def select_unit(self, unit_id):
        """Boolean row mask for rows belonging to this unit ID (cassette/tube)."""
        return self.matrix['ID'] == unit_id

    # placholder stubs - give warning if this function is not implemented (overwritten) in daughter class
    def plot_xy(self, *args, **kwargs): self._skip('plot_xy')
    def plot_tof_xy(self, *args, **kwargs): self._skip('plot_tof_xy')
    def plot_tof(self, *args, **kwargs): self._skip('plot_tof')
    def plot_lambda(self, *args, **kwargs): self._skip('plot_lambda')
    def plot_x_lambda(self, *args, **kwargs): self._skip('plot_x_lambda')
    def plot_multiplicity(self, *args, **kwargs): self._skip('plot_multiplicity')
    def plot_phs(self, *args, **kwargs): self._skip('plot_phs')
    def plot_phs_correlation(self, *args, **kwargs): self._skip('plot_phs_correlation')
    def plot_time_between_events(self, *args, **kwargs): self._skip('plot_time_between_events')
    def plot_position_per_tube(self, *args, **kwargs): self._skip('plot_position_per_tube')

# ============================================================================
# Shared VMM (ASIC-based) layer -- Multi-Blade + Multi-Grid
# ============================================================================

class VMMEventsPlotter(BaseEventsPlotter):
    """
    Shared structural logic and shared plots for VMM-based events
    (Multi-Blade, Multi-Grid): the global coincidence selection mask and
    every plot method except plot_xy_tof (MB and MG each define their own;
    see module docstring).
    """

    def __init__(self, container, parameters, config, axis_set,unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
        self.coincidence_ws_onoff = self.parameters.plotting.coincidenceWS_ONOFF
        

        if not self.is_empty:
            if self.coincidence_ws_onoff:
                print('\t building histograms ... coincidence W/S ON for ToF and Lambda ...')
                coord1_valid = (self.matrix['coordinate1'].astype(float) >= 0)
                coord0_valid = (self.matrix['coordinate0'].astype(float) >= 0)
                self.selc = coord1_valid & coord0_valid

            else:
                print('\t building histograms ... coincidence W/S OFF for ToF and Lambda ...') 
                self.selc = (self.matrix['coordinate0'] >= 0)

    def _get_wire_channel(self, global_wire_coord: np.ndarray) -> np.ndarray:
        """
        Abstract hook: map a global wire coordinate onto the wire-channel
        value used for the PHS wire-channel axis. Detector-specific
        geometry (cassette wrapping, flat/linear passthrough, etc.) is
        supplied by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _get_wire_channel().")

    def plot_tof(self, fig_num=333):
        """ToF distribution per unit: all events overlaid with 2D-coincidence-only events."""
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('ToF distr per unit')
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            sel_2d = m['coordinate1'] >= 0

            hist_tt  = self.hist.hist1d(ax_tof.centers, m['ToF'][sel & sel_2d] / 1e9)
            hist_tt1 = self.hist.hist1d(ax_tof.centers, m['ToF'][sel] / 1e9)

            grid.ax[0][k].step(ax_tof.centers * 1e3, hist_tt1, 'r', where='mid', label='all')
            grid.ax[0][k].step(ax_tof.centers * 1e3, hist_tt, 'b', where='mid', label='2D')
            grid.ax[0][k].set_xlabel('ToF (ms)')
            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
            grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='large')

    def plot_lambda(self, fig_num=339):
        """Wavelength distribution per unit: all events overlaid with 2D-coincidence-only events."""
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Wavelength distr per cassette')
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            sel_2d = m['coordinate1'] >= 0

            hist_wa  = self.hist.hist1d(ax_lambda.centers, m['wavelength'][sel & sel_2d])
            hist_wa1 = self.hist.hist1d(ax_lambda.centers, m['wavelength'][sel])

            grid.ax[0][k].step(ax_lambda.centers, hist_wa1, 'r', where='mid', label='all')
            grid.ax[0][k].step(ax_lambda.centers, hist_wa, 'b', where='mid', label='2D')
            grid.ax[0][k].set_xlabel('wavelength (A)')
            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
            grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='large')

    def plot_time_between_events(self, fig_num=209):
        """
        Delta-time between consecutive events and internal cluster time spans, per unit.
        Always linear-binned: legacy hardcodes out_of_bounds=False here
        regardless of the instance's hist_out_of_bounds setting.
        """
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 2, len(self.unit_ids), sharex= False)
        grid.fig.suptitle('Time between events and cluster time span')
        ax_rate = self.axis_set.ax_time_between_ev
        ax_span = self.axis_set.ax_time_span
        m = self.matrix
        forced_hist = Histogrammer(out_of_bounds=False)

        # Determine if this container instance has VMM normal clustering analytics fields
        has_cluster_span = 'clusterTimeSpan' in m.dtype.names

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            
            # Use the precalculated field (stored in ns) instead of manually computing np.diff
            # Filtering for rows where delta is valid (> 0)
            valid_delta = sel & (m['timeBetweenEvents'] > 0)
            inter_cluster_times = m['timeBetweenEvents'][valid_delta] / 1e9 # convert ns to seconds for axis centers matching

            hist_rate = forced_hist.hist1d(ax_rate.centers, inter_cluster_times)
            grid.ax[0][k].step(ax_rate.centers * 1e6, hist_rate, 'b', where='mid', label='time delta bet ev')
            
            hist_rate_zoomed = forced_hist.hist1d(ax_span.centers, inter_cluster_times)

            # Overlay cluster time span if dealing with eventsVMMnormal
            if has_cluster_span:
                cluster_spans = m['clusterTimeSpan'][sel] / 1e9 # convert ns to seconds
                hist_span = forced_hist.hist1d(ax_span.centers, cluster_spans)
                grid.ax[1][k].step(ax_span.centers * 1e6, hist_span, 'r', where='mid', label='cluster time span')
                grid.ax[1][k].step(ax_span.centers * 1e6, hist_rate_zoomed, 'b', where='mid', label='time delta bet ev')
                
            # print(ax_rate.centers)
            
            grid.ax[0][k].set_yscale('log')
            grid.ax[1][k].set_yscale('log')
            
            # grid.ax[0][k].set_xscale('symlog', linthresh=1)
            grid.ax[1][k].set_xscale('symlog', linthresh=1)
            # grid.ax[0][k].set_xlim(ax_rate.start * 1e6, ax_rate.stop * 1e6)
            # grid.ax[1][k].set_xlim(ax_span.start * 1e6, ax_span.stop * 1e6)
            
            grid.ax[0][k].set_xlabel('delta time (us)')
            
            grid.ax[1][k].set_xlabel('delta time / span (us)')
            
            grid.ax[0][k].set_title(f'ID {uid}')
            # Check and apply legend for row 0
            handles0, labels0 = grid.ax[0][k].get_legend_handles_labels()
            if labels0:
                grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='medium')
            
            # Check and apply legend for row 1
            handles1, labels1 = grid.ax[1][k].get_legend_handles_labels()
            if labels1:
                grid.ax[1][k].legend(loc='upper right', shadow=False, fontsize='medium')
            if k == 0:
                grid.ax[0][k].set_ylabel('num of events')

    def plot_multiplicity(self, fig_num=401):
        """Normalized wire/strip multiplicity distributions and their 2D coincidence correlation, per unit."""
        if self.is_empty:
            return
        
        width, extent = 0.2, 7

        grid = PlotGrid(fig_num, 2, len(self.unit_ids))
        grid.fig.suptitle('Events - multiplicity')
        xx = self.axis_set.ax_mult.centers
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            sel_2d = m['coordinate1'] >= 0

            myw  = self.hist.hist1d(xx, m['mult0'][sel])            # wires all
            mys  = self.hist.hist1d(xx, m['mult1'][sel])            # strips all
            mywc = self.hist.hist1d(xx, m['mult0'][sel & sel_2d])   # wires coinc
            my2Dwc, _, _ = self.hist.hist2d(xx, m['mult0'][sel & sel_2d], xx, m['mult1'][sel & sel_2d])  # wires coinc with strips 2D

            if np.any(sel):
                # Calculate sums first to guard against 0
                sum_myw_slice   = np.sum(myw[1:])
                sum_mys_slice   = np.sum(mys[1:])
                sum_mys_all     = np.sum(mys)
                sum_mywc_slice  = np.sum(mywc[1:])
                sum_my2Dwc_all  = np.sum(my2Dwc)
                
                # Divide if sum > 0, otherwise fill with zeros
                mywnorm    = myw / sum_myw_slice if sum_myw_slice > 0 else np.zeros(len(xx))
                mysnorm    = mys / sum_mys_slice if sum_mys_slice > 0 else np.zeros(len(xx))
                mysnormall = mys / sum_mys_all if sum_mys_all > 0 else np.zeros(len(xx))
                mywcnorm   = mywc / sum_mywc_slice if sum_mywc_slice > 0 else np.zeros(len(xx))
                my2Dwcnorm = my2Dwc / sum_my2Dwc_all if sum_my2Dwc_all > 0 else np.zeros((len(xx), len(xx)))
            else:
                mywnorm    = np.zeros(len(xx))
                mysnorm    = np.zeros(len(xx))
                mysnormall = np.zeros(len(xx))
                mywcnorm   = np.zeros(len(xx))
                my2Dwcnorm = np.zeros((len(xx), len(xx)))

            grid.ax[0][k].bar(xx[:extent] - width, mywnorm[:extent], width, color='m', label='w')
            grid.ax[0][k].bar(xx[1:extent] + width, mysnorm[1:extent], width, color='b', label='s')
            grid.ax[0][k].bar(xx[0] + width, mysnormall[0], width, color='c', label='no s')
            grid.ax[0][k].bar(xx[:extent], mywcnorm[:extent], width, color='r', label='w/s')
            grid.ax[0][k].set_xlabel('multiplicity')
            grid.ax[0][k].set_title(f'ID {uid}')
            grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='large')
            if k == 0:
                grid.ax[0][k].set_ylabel('probability')

            pos1 = grid.ax[1][k].imshow(
                my2Dwcnorm[:extent, :extent], aspect='auto', norm=None, interpolation='none',
                extent=[xx[0] - 0.5, xx[extent] - 0.5, xx[0] - 0.5, xx[extent] - 0.5], origin='lower', cmap='jet',
            )
            grid.ax[1][k].set_xlabel('multiplicity wires')
            if k == 0:
                grid.ax[1][k].set_ylabel('multiplicity strips/grids')
            grid.fig.colorbar(pos1, ax=grid.ax[1][k])

    def plot_phs(self, fig_num=601):
        """Wire/strip pulse-height spectra per unit: raw wire, raw strip, wire-with-strip-coincidence, and the summed 1D comparison."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        grid = PlotGrid(fig_num, 4, len(self.unit_ids))
        grid.fig.suptitle('Pulse Heigth Spectra')

        ax_energy = self.axis_set.ax_energy
        num_wires     = self.config['wires']
        num_strips    = self.config.get('strips', self.config.get('grids', None))
            
        wire_axis  = np.linspace(0, num_wires - 1, num_wires)
        strip_axis = np.linspace(0, num_strips - 1, num_strips)
        m = self.matrix

        wire_ch  = np.round(self._get_wire_channel(m['coordinate0']))
        strip_ch = np.round(m['coordinate1'])

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            sel_2d = m['coordinate1'] >= 0

            phs_w,  _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][sel], wire_axis, wire_ch[sel])
            phs_s,  _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight1'][sel & sel_2d], strip_axis, strip_ch[sel & sel_2d])
            phs_wc, _ , _= self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][sel & sel_2d], wire_axis, wire_ch[sel & sel_2d])

            grid.ax[0][k].imshow(phs_w, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, wire_axis[0], wire_axis[-1]], origin='lower', cmap='jet')
            grid.ax[1][k].imshow(phs_s, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, strip_axis[0], strip_axis[-1]], origin='lower', cmap='jet')
            grid.ax[2][k].imshow(phs_wc, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, wire_axis[0], wire_axis[-1]], origin='lower', cmap='jet')

            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('wires ch. no.')
                grid.ax[1][k].set_ylabel('strips/grids ch. no.')
                grid.ax[2][k].set_ylabel('wires coinc. ch. no.')

            phs_gw, phs_gs, phs_gwc = np.sum(phs_w, axis=0), np.sum(phs_s, axis=0), np.sum(phs_wc, axis=0)

            grid.ax[3][k].step(ax_energy.centers, phs_gw, 'r', where='mid', label='w')
            grid.ax[3][k].step(ax_energy.centers, phs_gs, 'b', where='mid', label='s')
            grid.ax[3][k].step(ax_energy.centers, phs_gwc, 'k', where='mid', label='w/s or w/g')
            grid.ax[3][k].set_xlabel('pulse height (a.u.)')
            grid.ax[3][k].legend(loc='upper right', shadow=False, fontsize='large')
            if k == 0:
                grid.ax[3][k].set_ylabel('counts')

    def plot_phs_correlation(self, fig_num=602):
        """Wire vs strip/grids pulse-height correlation for 2D-coincidence events, per unit."""
        if self.is_empty:
            return

        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        grid = PlotGrid(fig_num, 1, len(self.unit_ids), fig_size=(12, 6))
        grid.fig.suptitle('Pulse Heigth Spectrum - Correlation W/S or W/G')
        ax_energy = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            sel_2d = m['coordinate1'] >= 0

            phs_corr, _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][sel & sel_2d],
                                            ax_energy.centers, m['pulseHeight1'][sel & sel_2d])

            grid.ax[0][k].imshow(phs_corr, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, ax_energy.start, ax_energy.stop], origin='lower', cmap='jet')
            grid.ax[0][k].set_title(f'ID {uid}')
            grid.ax[0][k].set_xlabel('pulse height wires (a.u.)')
            if k == 0:
                grid.ax[0][k].set_ylabel('pulse height strips/grids (a.u.)')

    def plot_x_lambda(self, fig_num=103):
        """2D wavelength vs wire-position image across all units combined, raw channel or absolute-mm coordinates. Respects the global coincidence mask."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.plotting.plotIMGlog)
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        if not self.parameters.plotting.plotABSunits:
            ax_wires, wire_values, ylabel = self.axis_set.ax_wires, m['coordinate0'], 'Wire ch.'
        else:
            ax_wires, wire_values, ylabel = self.axis_set.ax_wires_mm, m['absCoordinate0'], 'Wire coord. (mm)'

        h, _, _ = self.hist.hist2d(ax_lambda.centers, m['wavelength'][self.selc], ax_wires.centers, wire_values[self.selc])

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig = fig_num
            ax = fig.subplots(nrows=1, ncols=1)
        else:
            fig, ax = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)

        pos = ax.imshow(h, aspect='auto', norm=norm_colors, interpolation='nearest',
                         extent=[ax_lambda.start, ax_lambda.stop, ax_wires.start, ax_wires.stop], origin='lower', cmap='viridis')
        _safe_colorbar(fig, pos, ax, 'X vs Lambda')
        ax.set_ylabel(ylabel)
        ax.set_xlabel('wavelength (A)')
        fig.suptitle('DET wavelength')


# ============================================================================
# Multi-Blade
# ============================================================================

class MBEventsPlotter(VMMEventsPlotter):
    """Multi-Blade events: single-panel detector image (wire vs strip) and ToF-vs-wire image."""

    def _get_wire_channel(self, global_wire_coord: np.ndarray) -> np.ndarray:
        """Wrap a global wire coordinate into this cassette's local wire-channel range."""
        num_wires = self.config['wires'] 
        return np.mod(global_wire_coord, num_wires)

    def plot_xy(self, fig_num=101):
        """Generates the main detector image (wire vs strip) and its 1D projection panel."""
        if self.is_empty:
            return
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        orientation = self.config.get('orientation')
        
        norm_colors = log_scale_norm(log_scale)
        m = self.matrix

        if not abs_units:
            ax_wires, ax_strips = self.axis_set.ax_wires, self.axis_set.ax_strips
            wire_values, strip_values = m['coordinate0'], m['coordinate1']
            wire_label, strip_label = 'Wire ch.', 'Strip ch.'
        else:
            ax_wires, ax_strips = self.axis_set.ax_wires_mm, self.axis_set.ax_strips_mm
            wire_values, strip_values = m['absCoordinate0'], m['absCoordinate1']
            wire_label, strip_label = 'Wire coord. (mm)', 'Strip (mm)'

        h2d, _, _ = self.hist.hist_xyz(
            ax_wires.centers, wire_values[self.selc],
            ax_strips.centers, strip_values[self.selc],
            self.axis_set.ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )
        h_proj_all = self.hist.hist1d(ax_wires.centers, wire_values[m['coordinate0']>=0])   
        h_proj_2d  = np.sum(h2d, axis=0)
        
        if orientation == 'vertical':
            if isinstance(fig_num, matplotlib.figure.Figure):
                fig2d = fig_num
                (ax1, ax2) = fig2d.subplots(nrows=2, ncols=1)
            else:
                fig2d, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(6, 12), nrows=2, ncols=1)
            pos1 = ax1.imshow(h2d, aspect='auto', norm=norm_colors, interpolation='none',
                               extent=[ax_wires.start, ax_wires.stop, ax_strips.stop, ax_strips.start], origin='upper', cmap='viridis')
            _safe_colorbar(fig2d, pos1, ax1, 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_xlabel(wire_label)
            ax1.set_ylabel(strip_label)
        else:  # 'horizontal'
            if isinstance(fig_num, matplotlib.figure.Figure):
                fig2d = fig_num
                (ax1, ax2) = fig2d.subplots(nrows=1, ncols=2)
            else:
                fig2d, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(12, 6), nrows=1, ncols=2)
            pos1 = ax1.imshow(np.rot90(h2d, 1), aspect='auto', norm=norm_colors, interpolation='none',
                               extent=[ax_strips.start, ax_strips.stop, ax_wires.start, ax_wires.stop], origin='upper', cmap='viridis')
            _safe_colorbar(fig2d, pos1, ax1, 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_ylabel(wire_label)
            ax1.set_xlabel(strip_label)
        fig2d.suptitle('DET image')

        ax2.step(ax_wires.centers, h_proj_all, 'r', where='mid', label='1D')
        ax2.step(ax_wires.centers, h_proj_2d, 'b', where='mid', label='2D')
        if log_scale:
            ax2.set_yscale('log')
        ax2.set_xlabel(wire_label)
        ax2.set_ylabel('counts')
        ax2.set_xlim(ax_wires.start, ax_wires.stop)
        ax2.legend(loc='upper right', shadow=False, fontsize='large')

    def plot_tof_xy(self, fig_num=102):
        """Generates the dedicated Time of Flight vs Position layout."""
        if self.is_empty:
            return
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits

        norm_colors = log_scale_norm(log_scale)
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        if not abs_units:
            ax_wires = self.axis_set.ax_wires
            wire_values = m['coordinate0']
            wire_label = 'Wire ch.'
        else:
            ax_wires = self.axis_set.ax_wires_mm
            wire_values = m['absCoordinate0']
            wire_label = 'Wire coord. (mm)'

        _, _, h_tof = self.hist.hist_xyz(
            ax_wires.centers, wire_values[self.selc],
            self.axis_set.ax_strips.centers, m['coordinate1'][self.selc],
            ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )
    

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig_tof = fig_num
            ax_t = fig_tof.subplots(nrows=1, ncols=1)
        else:
            fig_tof, ax_t = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)
            
        pos_t = ax_t.imshow(h_tof, aspect='auto', norm=norm_colors, interpolation='nearest',
                             extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_wires.start, ax_wires.stop], origin='lower', cmap='viridis')
        _safe_colorbar(fig_tof, pos_t, ax_t, 'YToF')
        ax_t.set_ylabel(wire_label)
        ax_t.set_xlabel('ToF (ms)')
        fig_tof.suptitle('DET ToF')

# ============================================================================
# Multi-Grid
# ============================================================================

class MGEventsPlotter(VMMEventsPlotter):
    """
    Multi-Grid events: detector image (wire vs grid) with cassette/row
    separator lines and an extra row-projection panel pair, plus a
    ToF-vs-wire image. Only orientation='vertical' actually renders the
    top-left detector-image panel -- 'horizontal' prints a warning and
    leaves it blank while the rest of the figure still renders (a legacy
    bug preserved verbatim). absUnits is not supported at all (legacy never
    implemented it for MG).
    """

    def _get_wire_channel(self, global_wire_coord: np.ndarray) -> np.ndarray:
        """MG wire channels are already flat/linear across the full detector -- no per-cassette wrapping applied."""
        return global_wire_coord

    def plot_xy(self, fig_num=101):
        """Generates the 2x2 grid featuring multi-grid wire views and row-projected layouts."""
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        orientation = self.config.get('orientation')
        
        norm_colors = log_scale_norm(log_scale)
        if abs_units :
            print(f'\n --> {WARN}WARNING: absUnits is not supported for MG for now, change to False to get det image{RESET}', end='')
            return
        

        norm_colors = log_scale_norm(log_scale)
        num_units = self.config['units']
        num_wires     = self.config['wires']
        num_strips    = self.config['grids']
        wires_per_row = self.config['wiresPerRow']
        ax_wires, ax_grids, ax_tof = self.axis_set.ax_wires, self.axis_set.ax_grids, self.axis_set.ax_tof
        m = self.matrix

        h2d, _, _ = self.hist.hist_xyz(
            ax_wires.centers, m['coordinate0'][self.selc],
            ax_grids.centers, m['coordinate1'][self.selc],
            ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )
        h_proj_all = self.hist.hist1d(ax_wires.centers, m['coordinate0'][m['coordinate0']>=0])  
        h_proj_2d  = np.sum(h2d, axis=0)

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig2d = fig_num
            ax22 = fig2d.subplots(nrows=2, ncols=2)
        else:
            fig2d, ax22 = plt.subplots(num=fig_num, figsize=(9, 9), nrows=2, ncols=2)

        if orientation == 'vertical':
            pos1 = ax22[0][0].imshow(h2d, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_wires.start - 0.5, ax_wires.stop + 0.5, ax_grids.start - 0.5, ax_grids.stop + 0.5],
                                      origin='lower', cmap='viridis')
            _safe_colorbar(fig2d, pos1, ax22[0][0], 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
            ax22[0][0].set_xlabel('Wire ch.')
            ax22[0][0].set_ylabel('Grid ch.')

            for k in np.arange(0, num_units * num_wires, wires_per_row):
                ax22[0][0].plot([k - 0.5, k - 0.5], [-0.5, num_strips - 0.5], 'r', linewidth=1)
            for k in range(1, num_units):
                ax22[0][0].plot([k * num_wires - 0.5, k * num_wires - 0.5],
                                 [-0.5, num_strips - 1 + 0.5], color='m', linewidth=1)
            ax22[0][0].set_xlim(ax_wires.centers[0], ax_wires.centers[-1])
        else:  # 'horizontal'
            print(f'\n --> {WARN}WARNING: horizontal is not supported yet for MG for now, change in config file{RESET}', end='')

        fig2d.suptitle('DET image')

        ax22[1][0].step(ax_wires.centers, h_proj_all, 'r', where='mid', label='1D')
        ax22[1][0].step(ax_wires.centers, h_proj_2d, 'b', where='mid', label='2D')
        if log_scale:
            ax22[1][0].set_yscale('log')
        ax22[1][0].set_xlabel('Wire ch.')
        ax22[1][0].set_ylabel('counts')
        ax22[1][0].set_xlim(ax_wires.centers[0], ax_wires.centers[-1])
        ax22[1][0].legend(loc='upper right', shadow=False, fontsize='large')

        default_hist = Histogrammer(out_of_bounds=True)
        wire_ch_for_x = np.floor_divide(m['coordinate0'][self.selc], wires_per_row)

        if np.mod(num_wires, wires_per_row) != 0:
            print('Warning: num of Wires / Wires per row is not integer!')
            time.sleep(2)

        rows_per_col = int(num_wires / wires_per_row)
        steps = num_units * rows_per_col
        stop = steps - 1
        rows_axis = np.linspace(0, stop, steps)

        h2d_proj_win, _, _ = default_hist.hist_xyz(
            rows_axis, wire_ch_for_x,
            ax_grids.centers, m['coordinate1'][self.selc],
            ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )

        pos10 = ax22[0][1].imshow(h2d_proj_win, aspect='auto', norm=norm_colors, interpolation='none',
                                   extent=[-0.5, stop + 0.5, ax_grids.start - 0.5, ax_grids.stop + 0.5], origin='lower', cmap='viridis')
        _safe_colorbar(fig2d, pos10, ax22[0][1], 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
        ax22[0][1].set_xlabel('Row no.')
        ax22[0][1].set_ylabel('Grid ch.')
        ax22[0][1].set_xlim(ax_wires.centers[0] / wires_per_row - 0.5, ax_wires.centers[-1] / wires_per_row - 0.5)

        for k in range(1, num_units):
            ax22[0][1].plot([k * rows_per_col - 0.5, k * rows_per_col - 0.5],
                             [-0.5, num_strips - 1 + 0.5], color='m', linewidth=1)

        h_proj_all_2 = default_hist.hist1d(rows_axis, wire_ch_for_x)
        h_proj_2d_2  = np.sum(h2d_proj_win, axis=0)

        ax22[1][1].step(rows_axis, h_proj_all_2, 'r', where='mid', label='1D')
        ax22[1][1].step(rows_axis, h_proj_2d_2, 'b', where='mid', label='2D')
        if log_scale:
            ax22[1][1].set_yscale('log')
        ax22[1][1].set_xlabel('Row no.')
        ax22[1][1].set_ylabel('counts')
        ax22[1][1].set_xlim(ax_wires.centers[0] / wires_per_row - 0.5, ax_wires.centers[-1] / wires_per_row - 0.5)
        ax22[1][1].legend(loc='upper right', shadow=False, fontsize='large')

    def plot_tof_xy(self, fig_num=102):
        """Generates the dedicated multi-grid ToF panel."""
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        
        if abs_units:
            return
   
        norm_colors = log_scale_norm(log_scale)

        ax_wires, ax_grids, ax_tof = self.axis_set.ax_wires, self.axis_set.ax_grids, self.axis_set.ax_tof
        m = self.matrix

        _, _, h_tof = self.hist.hist_xyz(
            ax_wires.centers, m['coordinate0'][self.selc],
            ax_grids.centers, m['coordinate1'][self.selc],
            ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig_tof = fig_num
            ax_t = fig_tof.subplots(nrows=1, ncols=1)
        else:
            fig_tof, ax_t = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)
            
        pos_t = ax_t.imshow(h_tof, aspect='auto', norm=norm_colors, interpolation='nearest',
                             extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_wires.start, ax_wires.stop], origin='lower', cmap='viridis')
        _safe_colorbar(fig_tof, pos_t, ax_t, 'YToF')
        ax_t.set_ylabel('Wire ch.')
        ax_t.set_xlabel('ToF (ms)')
        fig_tof.suptitle('DET ToF')
# ============================================================================
# R5560 tubes
# ============================================================================

class R5560EventsPlotter(BaseEventsPlotter):
    """
    Event diagnostics for R5560 tubes. No wire/strip pair, so there's no
    coincidence concept (no self.selc), no multiplicity, and PHS correlation
    doesn't apply -- those simply print a "not supported" warning, matching
    legacy.
    """

    def plot_tof(self, fig_num=333):
        """ToF distribution per tube (single curve, no coincidence overlay)."""
        if self.is_empty:
            return

        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('ToF distr per tube')
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            hist_tt = self.hist.hist1d(ax_tof.centers, m['ToF'][sel] / 1e9)

            grid.ax[0][k].step(ax_tof.centers * 1e3, hist_tt, 'b', where='mid')
            grid.ax[0][k].set_xlabel('ToF (ms)')
            grid.ax[0][k].set_title(f'Tube ID {uid}')  # NOTE: "Tube D" typo preserved verbatim from legacy
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')

    def plot_lambda(self, fig_num=339):
        """Wavelength distribution per tube (single curve, no coincidence overlay)."""
        if self.is_empty:
            return
        
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Wavelength distr per tube')
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            hist_wa = self.hist.hist1d(ax_lambda.centers, m['wavelength'][sel])

            grid.ax[0][k].step(ax_lambda.centers, hist_wa, 'r', where='mid')
            grid.ax[0][k].set_xlabel('wavelength (A)')
            grid.ax[0][k].set_title(f'Tube ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')

    def plot_time_between_events(self, fig_num=209):
        """Delta-time between consecutive events, per tube. Always linear-binned (out_of_bounds forced off, matching legacy)."""
        if self.is_empty:
            return
    
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Time between events')
        ax_rate = self.axis_set.ax_time_between_ev
        m = self.matrix
        forced_hist = Histogrammer(out_of_bounds=False)

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            diff_time = np.diff(m['timeStamp'][sel])
            hist_rate = forced_hist.hist1d(ax_rate.centers, diff_time / 1e9)

            grid.ax[0][k].step(ax_rate.centers * 1e6, hist_rate, 'k', where='mid', label='w')
            grid.ax[0][k].set_xlabel('delta time between events (us)')
            grid.ax[0][k].set_title(f'Tube ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('num of events')

    def plot_phs(self, fig_num=601):
        if self.is_empty:
            return
        # log_scale   = self.parameters.plotting.plotIMGlog
        
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Pulse Heigth Spectra')
        ax_energy = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            phs_w = self.hist.hist1d(ax_energy.centers, m['pulseHeight0'][sel])

            grid.ax[0][k].step(ax_energy.centers, phs_w, 'b', where='mid')
            grid.ax[0][k].set_title(f'Tube ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
            grid.ax[0][k].set_xlabel('pulse height (a.u.)')

    def plot_multiplicity(self):
        """Not supported for R5560 (single coordinate, no wire/strip pair)."""
        if self.is_empty:
            return
        print(f"\n\t{WARN}WARNING: Multiplicity not supported for {self.config['detectorType']} -> SKIPPING PLOT.{RESET}")

    def plot_phs_correlation(self):
        """Not supported for R5560 -- use the raw hits ADC vs ADC correlation instead."""
        if self.is_empty:
            return
        print(f"\t{WARN}WARNING: PHS correlation not supported for {self.config['detectorType']} -> SKIPPING PLOT (use raw hits for ADC VS ADC).{RESET}")

    def plot_x_lambda(self):
        """Not supported for R5560."""
        if self.is_empty:
            return
        print(f"\t{WARN}WARNING: X VS Wavelength not supported for {self.config['detectorType']} -> SKIPPING PLOT.{RESET}")

    def plot_xy(self, fig_num=101):
        """Detector image (position vs tube ID)."""
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        orientation = self.config.get('orientation')

        norm_colors = log_scale_norm(log_scale)
        m = self.matrix
        ax_tof = self.axis_set.ax_tof

        if not abs_units:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length, m['coordinate0'], 'Along tube position (a.u.)'
            ax_tubes,  pos1_values, pos1_label = self.axis_set.ax_tubes, m['coordinate1'], 'Tube ID (a.u.)'
            
        else:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length_mm, m['absCoordinate0'], 'Along tube position (mm)'
            ax_tubes,  pos1_values, pos1_label = self.axis_set.ax_tubes_mm, m['absCoordinate1'], 'Tube Position (mm)'
           
        half_x_pixel = (ax_tubes.stop - ax_tubes.start)   / (2 * (len(ax_tubes.centers) - 1))
        half_y_pixel = (ax_length.stop - ax_length.start) / (2 * (len(ax_length.centers) - 1))
            
        h2d, _, _ = self.hist.hist_xyz(ax_tubes.centers, pos1_values, ax_length.centers, pos0_values, ax_tof.centers, m['ToF'] / 1e9)

        if isinstance(fig_num, matplotlib.figure.Figure):
            grid_fig = fig_num
            ax1 = grid_fig.subplots(nrows=1, ncols=1)
        else:
            grid_fig, ax1 = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)


        if orientation == 'vertical':
            pos1 = ax1.imshow(h2d, aspect='auto', norm=norm_colors, interpolation='none',
                               extent=[ax_tubes.start - half_x_pixel, ax_tubes.stop + half_x_pixel, 
                                       ax_length.stop + half_y_pixel, ax_length.start - half_y_pixel], 
                               origin='upper', cmap='viridis')
            ax1.set_xticks(ax_tubes.centers)
            ax1.set_xticklabels(ax_tubes.centers.astype(int))
            _safe_colorbar(grid_fig, pos1, ax1, 'XY', orientation='vertical', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_xlabel(pos1_label)
            ax1.set_ylabel(pos0_label)
        else:  # 'horizontal'
            pos1 = ax1.imshow(np.rot90(h2d, 1), aspect='auto', norm=norm_colors, interpolation='none',
                               extent=[ax_length.start - half_y_pixel, ax_length.stop + half_y_pixel, 
                                       ax_tubes.stop + half_x_pixel, ax_tubes.start - half_x_pixel], 
                               origin='upper', cmap='viridis')
            # Set the ticks on their newly oriented axes
            ax1.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%d'))
            
            # ax1.set_xticks(ax_length.centers)
            # ax1.set_xticklabels(ax_length.centers.astype(int))
            ax1.set_yticks(ax_tubes.centers)
            ax1.set_yticklabels(ax_tubes.centers.astype(int))
            
            _safe_colorbar(grid_fig, pos1, ax1, 'XY', orientation='vertical', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_xlabel(pos0_label)
            ax1.set_ylabel(pos1_label)
            
        grid_fig.suptitle('DET image')

    def plot_position_per_tube(self, fig_num=104):
        """Generates the multi-panel grid of 1D tube positions."""
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        
        m = self.matrix

        if not abs_units:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length, m['coordinate0'], 'Along tube position (a.u.)'
            # ax_tubes, pos1_values, pos1_label = self.axis_set.ax_tubes, m['coordinate1'], 'Tube ID (a.u.)'
            
        else:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length_mm, m['absCoordinate0'], 'Along tube position (mm)'
            # ax_tubes, pos1_values, pos1_label = self.axis_set.ax_tubes_mm, m['absCoordinate1'], 'Tube Position (mm)'
           
        grid1d = PlotGrid(fig_num, 1, len(self.unit_ids))

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            h1d = self.hist.hist1d(ax_length.centers, pos0_values[sel])

            grid1d.ax[0][k].step(ax_length.centers, h1d, 'k', where='mid')
            grid1d.ax[0][k].set_xlabel(pos0_label)
            grid1d.ax[0][k].set_title(f'Tube ID {uid}')
            if log_scale:
                grid1d.ax[0][k].set_yscale('log')
            if k == 0:
                grid1d.ax[0][k].set_ylabel('counts')

    def plot_tof_xy(self, fig_num=102):
        """Tube-ID-vs-ToF image distribution."""
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        norm_colors = log_scale_norm(log_scale)
        
        m = self.matrix
        ax_tof, ax_tubes, ax_length = self.axis_set.ax_tof, self.axis_set.ax_tubes, self.axis_set.ax_length

        _, _, h_tof = self.hist.hist_xyz(ax_tubes.centers, m['coordinate1'], ax_length.centers, m['coordinate0'], ax_tof.centers, m['ToF'] / 1e9)

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig_tof = fig_num
            ax2 = fig_tof.subplots(nrows=1, ncols=1)
        else:
            fig_tof, ax2 = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)

        ax2.imshow(h_tof, aspect='auto', norm=norm_colors, interpolation='nearest',
                   extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_tubes.start - 0.5, ax_tubes.stop + 0.5], origin='lower', cmap='viridis')
        ax2.set_yticks(ax_tubes.centers)
        ax2.set_yticklabels(ax_tubes.centers.astype(int))
        ax2.set_ylabel('Tube ID')
        ax2.set_xlabel('ToF (ms)')
        
        fig_tof.suptitle('DET ToF')
# ============================================================================
# Beam monitor
# ============================================================================

class MonitorEventsPlotter(BasePlotter):
    """
    Beam-monitor passthrough plots (eventsBM / eventsIBM / eventsSKADI): a
    single stream with no per-unit ID grouping at all, so this sits
    directly on BasePlotter rather than BaseEventsPlotter (no select_unit
    concept, no per-cassette loop).

    Two behavioural additions vs. legacy, both for consistency with the
    rest of this module rather than "new features": (1) the is_empty guard
    from BasePlotter, since legacy's plottingMON never checked for an
    empty stream at all; (2) the PHS panel reads the generic
    'pulseHeight0' field (matching legacy eventsMON.PHW) -- flag if your
    monitor pipeline actually wants the detector-specific 'adc' field
    instead.
    """


    def plot_tof_phs_mon(self, fig_num=999):
        """ToF and pulse-height spectra for the monitor stream, side by side."""
        if self.is_empty:
            return
        m = self.matrix
        ax_tof, ax_energy_mon = self.axis_set.ax_tof, self.axis_set.ax_energy_mon

        hist_tof = self.hist.hist1d(ax_tof.centers, m['ToF'] / 1e9)
        hist_phs = self.hist.hist1d(ax_energy_mon.centers, m['pulseHeight0'])

        fig, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(9, 6), nrows=1, ncols=2)
        fig.suptitle('MONITOR')

        ax1.step(ax_tof.centers * 1e3, hist_tof, 'k', where='mid', label='MON')
        ax1.set_xlabel('ToF (ms)')
        ax1.set_ylabel('counts')
        ax1.set_title('ToF')

        ax2.step(ax_energy_mon.centers, hist_phs, 'k', where='mid', label='MON')
        ax2.set_xlabel('Pulse Heigth (a.u.)')
        ax2.set_ylabel('counts')
        ax2.set_title('PHS')

    def plot_lambda_mon(self, fig_num=9998):
        """Wavelength spectrum for the monitor stream."""
        if self.is_empty:
            return
        m = self.matrix
        ax_lambda = self.axis_set.ax_lambda
        hist_lambda = self.hist.hist1d(ax_lambda.centers, m['wavelength'])

        fig, ax1 = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)
        fig.suptitle('MONITOR')

        ax1.step(ax_lambda.centers, hist_lambda, 'k', where='mid', label='MON')
        ax1.set_xlabel('wavelength (A)')
        ax1.set_ylabel('counts')
        ax1.set_title('WAVELENGTH')