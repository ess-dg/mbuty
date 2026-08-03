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
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.figure
import matplotlib.colors as colors

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
from lib.colors import WARN, RESET
from lib.histograms import Histogrammer
from lib.plotting_base import PlotGrid, BasePlotter, log_scale_norm, _safe_colorbar, fg_color

# ============================================================================
# Detector-agnostic base
# ============================================================================

class BaseEventsPlotter(BasePlotter):
    """
    Detector-agnostic events scaffolding: axis-set access, unit selection by
    mapped 'ID', and direct access onto this detector's flat configuration
    dictionary (needed for layout math and "not supported" messages).
    """
    PLOT_METHODS = {
        "XY":                   "plot_xy",
        "ToF vs XY":            "plot_tof_xy",
        "ToF":                  "plot_tof",
        "Wavelength":           "plot_lambda",
        "X vs Wavelength":      "plot_x_lambda",
        "Multiplicity":         "plot_multiplicity",
        "PHS":                  "plot_phs",
        "PHS Correlation":      "plot_phs_correlation",
        "Time Between Events":  "plot_time_between_events",
    }
    
    def select_unit(self, unit_id):
        """Boolean row mask for rows belonging to this unit ID (cassette/tube)."""
        return self.matrix['ID'] == unit_id

    # placeholder stubs - give warning if this function is not implemented in daughter class
    def plot_xy(self, *args, **kwargs): self._skip('plot_xy')
    def plot_tof_xy(self, *args, **kwargs): self._skip('plot_tof_xy')
    def plot_tof(self, *args, **kwargs): self._skip('plot_tof')
    def plot_lambda(self, *args, **kwargs): self._skip('plot_lambda') 
    def plot_x_lambda(self, *args, **kwargs): self._skip('plot_x_lambda')
    def plot_multiplicity(self, *args, **kwargs): self._skip('plot_multiplicity')
    def plot_phs(self, *args, **kwargs): self._skip('plot_phs')
    def plot_phs_correlation(self, *args, **kwargs): self._skip('plot_phs_correlation')
    def plot_time_between_events(self, *args, **kwargs): self._skip('plot_time_between_events')
    def plot_position_per_tube(self, *args, **kwargs): pass

# ============================================================================
# Shared VMM (ASIC-based) layer -- Multi-Blade + Multi-Grid
# ============================================================================

class VMMEventsPlotter(BaseEventsPlotter):
    """
    Shared structural logic and shared plots for VMM-based events
    (Multi-Blade, Multi-Grid, NMX): the global coincidence selection mask
    and every plot method (MB/MG/NMX each only override plot_xy/plot_tof_xy,
    which are genuinely different figures per detector).
    """
    SUPPORTS_ABS_UNITS = False
    ACCEPT_1D_X = True
    ACCEPT_1D_Y = False

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
        self.coincidence_ws_onoff = self.parameters.plotting.coincidenceWS_ONOFF

        requested_abs_units = self.parameters.plotting.plotABSunits
        if requested_abs_units and not self.SUPPORTS_ABS_UNITS:
            print(f'\n --> {WARN}WARNING: absUnits not supported for {type(self).__name__}, turning abs units off{RESET}')
        self.abs_units = requested_abs_units and self.SUPPORTS_ABS_UNITS

        if not self.is_empty:
            coord0_valid = (self.matrix['coordinate0'].astype(float) >= 0)
            coord1_valid = (self.matrix['coordinate1'].astype(float) >= 0)
            self.sel_full_coinc = coord0_valid & coord1_valid

            if self.coincidence_ws_onoff:
                print(f'\t building histograms ... coincidence {self.COINC_LABEL} ON for ToF and Lambda ...')
                self.selc = self.sel_full_coinc
            else:
                print(f'\t building histograms ... coincidence {self.COINC_LABEL} OFF for ToF and Lambda ...')
                self.selc = (self.ACCEPT_1D_X & coord0_valid) | (self.ACCEPT_1D_Y & coord1_valid)

    def _get_x_channel(self, global_x_coord: np.ndarray) -> np.ndarray:
        raise NotImplementedError("Subclasses must implement _get_x_channel().")

    def _get_y_channel(self, global_y_coord: np.ndarray) -> np.ndarray:
        return global_y_coord

    def _config_count(self, keys):
        """Return the first present config value among candidate keys (int)."""
        for key in keys:
            if key in self.config:
                return int(self.config[key])
        raise KeyError(f"None of {keys} found in detector config for {type(self).__name__}")

    def plot_tof(self, fig_num=333):
        """ToF distribution per unit: all events overlaid with 2D-coincidence-only events."""
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('ToF distr per unit')
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            unit_sel = self.select_unit(uid)
            valid = unit_sel & self.selc
            coinc = unit_sel & self.sel_full_coinc

            hist_tt  = self.hist.hist1d(ax_tof.centers, m['ToF'][coinc] / 1e9)
            hist_tt1 = self.hist.hist1d(ax_tof.centers, m['ToF'][valid] / 1e9)

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
        grid.fig.suptitle('Wavelength distr per unit')
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            unit_sel = self.select_unit(uid)
            valid = unit_sel & self.selc
            coinc = unit_sel & self.sel_full_coinc

            hist_wa  = self.hist.hist1d(ax_lambda.centers, m['wavelength'][coinc])
            hist_wa1 = self.hist.hist1d(ax_lambda.centers, m['wavelength'][valid])

            grid.ax[0][k].step(ax_lambda.centers, hist_wa1, 'r', where='mid', label='all')
            grid.ax[0][k].step(ax_lambda.centers, hist_wa, 'b', where='mid', label='2D')
            grid.ax[0][k].set_xlabel('wavelength (A)')
            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
            grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='large')
            
    def plot_time_between_events(self, fig_num=209):
        """Delta-time between consecutive events and internal cluster time spans, per unit."""
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 2, len(self.unit_ids), sharex=False)
        grid.fig.suptitle('Time between events and cluster time span')
        ax_rate = self.axis_set.ax_time_between_ev
        ax_span = self.axis_set.ax_time_span
        m = self.matrix
        forced_hist = Histogrammer(out_of_bounds=False)

        has_cluster_span = 'clusterTimeSpan' in m.dtype.names

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            valid_delta = sel & (m['timeBetweenEvents'] > 0)
            inter_cluster_times = m['timeBetweenEvents'][valid_delta] / 1e9

            hist_rate = forced_hist.hist1d(ax_rate.centers, inter_cluster_times)
            grid.ax[0][k].step(ax_rate.centers * 1e6, hist_rate, 'b', where='mid', label='time delta bet ev')
            
            hist_rate_zoomed = forced_hist.hist1d(ax_span.centers, inter_cluster_times)
            hist_span = None

            if has_cluster_span:
                cluster_spans = m['clusterTimeSpan'][sel] / 1e9
                hist_span = forced_hist.hist1d(ax_span.centers, cluster_spans)
                grid.ax[1][k].step(ax_span.centers * 1e6, hist_span, 'r', where='mid', label='cluster time span')
                grid.ax[1][k].step(ax_span.centers * 1e6, hist_rate_zoomed, 'b', where='mid', label='time delta bet ev')

            if hist_rate is not None and (hist_rate > 0).any():
                grid.ax[0][k].set_yscale('log')
            else:
                grid.ax[0][k].set_yscale('linear')

            has_positive_span = hist_span is not None and (hist_span > 0).any()
            has_positive_zoomed = hist_rate_zoomed is not None and (hist_rate_zoomed > 0).any()
            
            if has_positive_span or has_positive_zoomed:
                grid.ax[1][k].set_yscale('log')
            else:
                grid.ax[1][k].set_yscale('linear')    
                
            grid.ax[1][k].set_xscale('symlog', linthresh=1)

            grid.ax[0][k].set_xlabel('delta time (us)')
            grid.ax[1][k].set_xlabel('delta time / span (us)')
            
            grid.ax[0][k].set_title(f'ID {uid}')
            handles0, labels0 = grid.ax[0][k].get_legend_handles_labels()
            if labels0:
                grid.ax[0][k].legend(loc='upper right', shadow=False, fontsize='medium')
            
            handles1, labels1 = grid.ax[1][k].get_legend_handles_labels()
            if labels1:
                grid.ax[1][k].legend(loc='upper right', shadow=False, fontsize='medium')
            if k == 0:
                grid.ax[0][k].set_ylabel('num of events')

    def plot_multiplicity(self, fig_num=401):
        """Normalized per-axis multiplicity distributions and their 2D coincidence correlation, per unit."""
        if self.is_empty:
            return

        show_x = self.ACCEPT_1D_X
        show_y = self.ACCEPT_1D_Y
        symmetric = show_x and show_y
        width, extent = (0.15, 7) if symmetric else (0.2, 7)

        grid = PlotGrid(fig_num, 2, len(self.unit_ids))
        grid.fig.suptitle('Events - multiplicity')
        xx = self.axis_set.ax_mult.centers
        m = self.matrix
        n = len(xx)

        for k, uid in enumerate(self.unit_ids):
            unit_sel = self.select_unit(uid)
            valid = unit_sel & self.selc
            coinc = unit_sel & self.sel_full_coinc

            myx = self.hist.hist1d(xx, m['mult0'][valid])
            myy = self.hist.hist1d(xx, m['mult1'][valid])
            myxc = self.hist.hist1d(xx, m['mult0'][coinc]) if show_x else None
            myyc = self.hist.hist1d(xx, m['mult1'][coinc]) if show_y else None
            my2Dc, _, _ = self.hist.hist2d(xx, m['mult0'][coinc], xx, m['mult1'][coinc])

            if np.any(valid):
                sum_myx_slice = np.sum(myx[1:])
                sum_myy_slice = np.sum(myy[1:])
                sum_myx_all   = np.sum(myx)
                sum_myy_all   = np.sum(myy)
                sum_my2Dc_all = np.sum(my2Dc)

                myxnorm    = myx / sum_myx_slice if sum_myx_slice > 0 else np.zeros(n)
                myynorm    = myy / sum_myy_slice if sum_myy_slice > 0 else np.zeros(n)
                myxnormall = myx / sum_myx_all if sum_myx_all > 0 else np.zeros(n)
                myynormall = myy / sum_myy_all if sum_myy_all > 0 else np.zeros(n)
                my2Dcnorm  = my2Dc / sum_my2Dc_all if sum_my2Dc_all > 0 else np.zeros((n, n))
                if show_x:
                    sum_myxc_slice = np.sum(myxc[1:])
                    myxcnorm = myxc / sum_myxc_slice if sum_myxc_slice > 0 else np.zeros(n)
                if show_y:
                    sum_myyc_slice = np.sum(myyc[1:])
                    myycnorm = myyc / sum_myyc_slice if sum_myyc_slice > 0 else np.zeros(n)
            else:
                myxnorm = myynorm = myxnormall = myynormall = np.zeros(n)
                my2Dcnorm = np.zeros((n, n))
                myxcnorm = myycnorm = np.zeros(n)

            ax = grid.ax[0][k]
            if symmetric:
                ax.bar(xx[1:extent] - 1.5*width, myxnorm[1:extent],  width, color='m', label=self.X_LABEL)
                ax.bar(xx[1:extent] - 0.5*width, myynorm[1:extent],  width, color='b', label=self.Y_LABEL)
                ax.bar(xx[1:extent] + 0.5*width, myxcnorm[1:extent], width, color='r', label=f'{self.X_LABEL} (2D)')
                ax.bar(xx[1:extent] + 1.5*width, myycnorm[1:extent], width, color='orange', label=f'{self.Y_LABEL} (2D)')
                ax.bar(xx[0] - 0.5*width, myxnormall[0], width, color='c', label=f'no {self.X_LABEL}')
                ax.bar(xx[0] + 0.5*width, myynormall[0], width, color='y', label=f'no {self.Y_LABEL}')
            else:
                ax.bar(xx[:extent] - width, myxnorm[:extent], width, color='m', label=self.X_TAG)
                ax.bar(xx[1:extent] + width, myynorm[1:extent], width, color='b', label=self.Y_TAG)
                if show_x:
                    ax.bar(xx[0] + width, myynormall[0], width, color='c', label=f'no {self.Y_TAG}')
                    ax.bar(xx[:extent], myxcnorm[:extent], width, color='r', label=f'{self.X_TAG}/{self.Y_TAG}')
                elif show_y:
                    ax.bar(xx[0] - width, myxnormall[0], width, color='c', label=f'no {self.X_TAG}')
                    ax.bar(xx[:extent], myycnorm[:extent], width, color='r', label=f'{self.X_TAG}/{self.Y_TAG}')
            ax.set_xlabel('multiplicity')
            ax.set_title(f'ID {uid}')
            ax.legend(loc='upper right', shadow=False, fontsize='medium' if symmetric else 'large')
            if k == 0:
                ax.set_ylabel('probability')

            pos1 = grid.ax[1][k].imshow(
                my2Dcnorm[:extent, :extent], aspect='auto', norm=None, interpolation='none',
                extent=[xx[0] - 0.5, xx[extent] - 0.5, xx[0] - 0.5, xx[extent] - 0.5], origin='lower', cmap='jet',
            )
            grid.ax[1][k].set_xlabel(f'multiplicity {self.X_LABEL.lower()}')
            if k == 0:
                grid.ax[1][k].set_ylabel(f'multiplicity {self.Y_LABEL.lower()}')
            grid.fig.colorbar(pos1, ax=grid.ax[1][k])

    def plot_phs(self, fig_num=601):
        """X/Y pulse-height spectra per unit."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        grid = PlotGrid(fig_num, 4, len(self.unit_ids))
        grid.fig.suptitle('Pulse Heigth Spectra')

        ax_energy = self.axis_set.ax_energy
        num_x = self._config_count(self.X_COUNT_KEYS)
        num_y = self._config_count(self.Y_COUNT_KEYS)

        x_axis = np.linspace(0, num_x - 1, num_x)
        y_axis = np.linspace(0, num_y - 1, num_y)
        m = self.matrix

        x_ch = np.round(self._get_x_channel(m['coordinate0']))
        y_ch = np.round(self._get_y_channel(m['coordinate1']))

        for k, uid in enumerate(self.unit_ids):
            unit_sel = self.select_unit(uid)
            coinc = unit_sel & self.sel_full_coinc

            phs_x,  _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][unit_sel], x_axis, x_ch[unit_sel])
            phs_y,  _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight1'][coinc], y_axis, y_ch[coinc])
            phs_xc, _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][coinc], x_axis, x_ch[coinc])

            grid.ax[0][k].imshow(phs_x, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, x_axis[0], x_axis[-1]], origin='lower', cmap='jet')
            grid.ax[1][k].imshow(phs_y, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, y_axis[0], y_axis[-1]], origin='lower', cmap='jet')
            grid.ax[2][k].imshow(phs_xc, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, x_axis[0], x_axis[-1]], origin='lower', cmap='jet')

            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel(f'{self.X_LABEL} ch. no.')
                grid.ax[1][k].set_ylabel(f'{self.Y_LABEL} ch. no.')
                grid.ax[2][k].set_ylabel(f'{self.X_LABEL} coinc. ch. no.')

            phs_gx, phs_gy, phs_gxc = np.sum(phs_x, axis=0), np.sum(phs_y, axis=0), np.sum(phs_xc, axis=0)

            grid.ax[3][k].step(ax_energy.centers, phs_gx, 'r', where='mid', label=self.X_TAG)
            grid.ax[3][k].step(ax_energy.centers, phs_gy, 'b', where='mid', label=self.Y_TAG)
            grid.ax[3][k].step(ax_energy.centers, phs_gxc, fg_color(), where='mid', label=f'{self.X_TAG}/{self.Y_TAG}')
            grid.ax[3][k].set_xlabel('pulse height (a.u.)')
            grid.ax[3][k].legend(loc='upper right', shadow=False, fontsize='large')
            if k == 0:
                grid.ax[3][k].set_ylabel('counts')

    def plot_phs_correlation(self, fig_num=602):
        """X vs Y pulse-height correlation for 2D-coincidence events, per unit."""
        if self.is_empty:
            return

        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        grid = PlotGrid(fig_num, 1, len(self.unit_ids), fig_size=(12, 6))
        grid.fig.suptitle(f'Pulse Heigth Spectrum - Correlation {self.COINC_LABEL}')
        ax_energy = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            coinc = self.select_unit(uid) & self.sel_full_coinc

            phs_corr, _, _ = self.hist.hist2d(ax_energy.centers, m['pulseHeight0'][coinc],
                                            ax_energy.centers, m['pulseHeight1'][coinc])

            grid.ax[0][k].imshow(phs_corr, aspect='auto', norm=norm_colors, interpolation='none',
                                  extent=[ax_energy.start, ax_energy.stop, ax_energy.start, ax_energy.stop], origin='lower', cmap='jet')
            grid.ax[0][k].set_title(f'ID {uid}')
            grid.ax[0][k].set_xlabel(f'pulse height {self.X_LABEL.lower()} (a.u.)')
            if k == 0:
                grid.ax[0][k].set_ylabel(f'pulse height {self.Y_LABEL.lower()} (a.u.)')

    def plot_x_lambda(self, fig_num=103):
        """2D wavelength vs X-position image across all units combined."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.plotting.plotIMGlog)
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        if not self.abs_units:
            ax_x = self.axis_set.ax_x
            x_values, ylabel = m['coordinate0'], f'{self.X_LABEL} ch.'
        else:
            ax_x = self.axis_set.ax_x_mm
            x_values, ylabel = m['absCoordinate0'], f'{self.X_LABEL} coord. (mm)'

        h, _, _ = self.hist.hist2d(ax_lambda.centers, m['wavelength'][self.selc], ax_x.centers, x_values[self.selc])

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig = fig_num
            ax = fig.subplots(nrows=1, ncols=1)
        else:
            fig, ax = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)

        pos = ax.imshow(h, aspect='auto', norm=norm_colors, interpolation='nearest',
                         extent=[ax_lambda.start, ax_lambda.stop, ax_x.start, ax_x.stop], origin='lower', cmap='viridis')
        _safe_colorbar(fig, pos, ax, 'X vs Lambda')
        ax.set_ylabel(ylabel)
        ax.set_xlabel('wavelength (A)')
        fig.suptitle('DET wavelength')

# ============================================================================
# Multi-Blade
# ============================================================================

class MBEventsPlotter(VMMEventsPlotter):
    """Multi-Blade events: single-panel detector image (wire vs strip) and ToF-vs-wire image."""

    X_LABEL = 'Wire'
    Y_LABEL = 'Strip'
    X_TAG = 'w'
    Y_TAG = 's'
    COINC_LABEL = 'W/S'
    X_COUNT_KEYS = ('wires',)
    Y_COUNT_KEYS = ('strips',)
    SUPPORTS_ABS_UNITS = True

    def _get_x_channel(self, global_x_coord: np.ndarray) -> np.ndarray:
        num_wires = self.config['wires']
        return np.mod(global_x_coord, num_wires)

    def plot_xy(self, fig_num=101):
        if self.is_empty:
            return
        log_scale   = self.parameters.plotting.plotIMGlog
        orientation = self.config.get('orientation')
        
        norm_colors = log_scale_norm(log_scale)
        m = self.matrix

        if not self.abs_units:
            ax_wires, ax_strips = self.axis_set.ax_x, self.axis_set.ax_y
            wire_values, strip_values = m['coordinate0'], m['coordinate1']
            wire_label, strip_label = 'Wire ch.', 'Strip ch.'
        else:
            ax_wires, ax_strips = self.axis_set.ax_x_mm, self.axis_set.ax_y_mm
            wire_values, strip_values = m['absCoordinate0'], m['absCoordinate1']
            wire_label, strip_label = 'Wire coord. (mm)', 'Strip (mm)'

        h2d, _, _ = self.hist.hist_xyz(
            ax_wires.centers, wire_values[self.selc],
            ax_strips.centers, strip_values[self.selc],
            self.axis_set.ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )
        
        # RESTORED: Evaluate raw valid coordinate0 so all 1D wire counts render on the red curve
        h_proj_all = self.hist.hist1d(ax_wires.centers, wire_values[m['coordinate0'] >= 0])
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
        else:
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
        if self.is_empty:
            return
        log_scale   = self.parameters.plotting.plotIMGlog

        norm_colors = log_scale_norm(log_scale)
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        if not self.abs_units:
            ax_wires = self.axis_set.ax_x
            wire_values = m['coordinate0']
            wire_label = 'Wire ch.'
        else:
            ax_wires = self.axis_set.ax_x_mm
            wire_values = m['absCoordinate0']
            wire_label = 'Wire coord. (mm)'

        _, _, h_tof = self.hist.hist_xyz(
            ax_wires.centers, wire_values[self.selc],
            self.axis_set.ax_y.centers, m['coordinate1'][self.selc],
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
    """Multi-Grid events plotting class."""

    X_LABEL = 'Wire'
    Y_LABEL = 'Grid'
    X_TAG = 'w'
    Y_TAG = 'g'
    COINC_LABEL = 'W/G'
    X_COUNT_KEYS = ('wires',)
    Y_COUNT_KEYS = ('grids',)

    def _get_x_channel(self, global_x_coord: np.ndarray) -> np.ndarray:
        return global_x_coord

    def plot_xy(self, fig_num=101):
        if self.is_empty:
            return

        log_scale   = self.parameters.plotting.plotIMGlog
        orientation = self.config.get('orientation')

        norm_colors = log_scale_norm(log_scale)
        num_units = self.config['units']
        num_wires     = self.config['wires']
        num_strips    = self.config['grids']
        wires_per_row = self.config['wiresPerRow']
        ax_wires, ax_grids, ax_tof = self.axis_set.ax_x, self.axis_set.ax_y, self.axis_set.ax_tof
        m = self.matrix

        h2d, _, _ = self.hist.hist_xyz(
            ax_wires.centers, m['coordinate0'][self.selc],
            ax_grids.centers, m['coordinate1'][self.selc],
            ax_tof.centers, m['ToF'][self.selc] / 1e9,
        )
        
        # RESTORED: Evaluate raw valid coordinate0 so all 1D wire counts render on the red curve
        h_proj_all = self.hist.hist1d(ax_wires.centers, m['coordinate0'][m['coordinate0'] >= 0])
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
        else:
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
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        norm_colors = log_scale_norm(log_scale)

        ax_wires, ax_grids, ax_tof = self.axis_set.ax_x, self.axis_set.ax_y, self.axis_set.ax_tof
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
    """Event diagnostics for R5560 tubes."""
    PLOT_METHODS = {
        **BaseEventsPlotter.PLOT_METHODS,
        "Position per Tube": "plot_position_per_tube",
    }

    def plot_tof(self, fig_num=333):
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
            grid.ax[0][k].set_title(f'Tube ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')

    def plot_lambda(self, fig_num=339):
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

            grid.ax[0][k].step(ax_rate.centers * 1e6, hist_rate, fg_color(), where='mid', label='w')
            grid.ax[0][k].set_xlabel('delta time between events (us)')
            grid.ax[0][k].set_title(f'Tube ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('num of events')

    def plot_phs(self, fig_num=601):
        if self.is_empty:
            return

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
        else:
            pos1 = ax1.imshow(np.rot90(h2d, 1), aspect='auto', norm=norm_colors, interpolation='none',
                               extent=[ax_length.start - half_y_pixel, ax_length.stop + half_y_pixel, 
                                       ax_tubes.stop + half_x_pixel, ax_tubes.start - half_x_pixel], 
                               origin='upper', cmap='viridis')
            ax1.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%d'))
            ax1.set_yticks(ax_tubes.centers)
            ax1.set_yticklabels(ax_tubes.centers.astype(int))
            
            _safe_colorbar(grid_fig, pos1, ax1, 'XY', orientation='vertical', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_xlabel(pos0_label)
            ax1.set_ylabel(pos1_label)
            
        grid_fig.suptitle('DET image')

    def plot_position_per_tube(self, fig_num=104):
        if self.is_empty:
            return
        
        log_scale   = self.parameters.plotting.plotIMGlog
        abs_units   = self.parameters.plotting.plotABSunits
        m = self.matrix

        if not abs_units:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length, m['coordinate0'], 'Along tube position (a.u.)'
        else:
            ax_length, pos0_values, pos0_label = self.axis_set.ax_length_mm, m['absCoordinate0'], 'Along tube position (mm)'
           
        grid1d = PlotGrid(fig_num, 1, len(self.unit_ids))

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            h1d = self.hist.hist1d(ax_length.centers, pos0_values[sel])

            grid1d.ax[0][k].step(ax_length.centers, h1d, fg_color(), where='mid')
            grid1d.ax[0][k].set_xlabel(pos0_label)
            grid1d.ax[0][k].set_title(f'Tube ID {uid}')
            if log_scale:
                grid1d.ax[0][k].set_yscale('log')
            if k == 0:
                grid1d.ax[0][k].set_ylabel('counts')

    def plot_tof_xy(self, fig_num=102):
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
    PLOT_METHODS = {
        "ToF & PHS":  "plot_tof_phs_mon",
        "Wavelength": "plot_lambda_mon",
    }

    def plot_tof_phs_mon(self, fig_num=999):
        if self.is_empty:
            return
        m = self.matrix
        ax_tof, ax_energy_mon = self.axis_set.ax_tof, self.axis_set.ax_energy_mon

        hist_tof = self.hist.hist1d(ax_tof.centers, m['ToF'] / 1e9)
        hist_phs = self.hist.hist1d(ax_energy_mon.centers, m['pulseHeight0'])

        grid = PlotGrid(fig_num, n_rows=1, n_cols=2, fig_size=(9, 6), sharex=False, sharey=False)
        fig = grid.fig
        ax1, ax2 = grid.ax[0]
        fig.suptitle('MONITOR')

        ax1.step(ax_tof.centers * 1e3, hist_tof, fg_color(), where='mid', label='MON')
        ax1.set_xlabel('ToF (ms)')
        ax1.set_ylabel('counts')
        ax1.set_title('ToF')

        ax2.step(ax_energy_mon.centers, hist_phs, fg_color(), where='mid', label='MON')
        ax2.set_xlabel('Pulse Heigth (a.u.)')
        ax2.set_ylabel('counts')
        ax2.set_title('PHS')

    def plot_lambda_mon(self, fig_num=9998):
        if self.is_empty:
            return
        m = self.matrix
        ax_lambda = self.axis_set.ax_lambda
        hist_lambda = self.hist.hist1d(ax_lambda.centers, m['wavelength'])

        grid = PlotGrid(fig_num, n_rows=1, n_cols=1, fig_size=(6, 6), sharex=False, sharey=False)
        fig = grid.fig
        ax1 = grid.ax[0][0]
        fig.suptitle('MONITOR')

        ax1.step(ax_lambda.centers, hist_lambda, fg_color(), where='mid', label='MON')
        ax1.set_xlabel('wavelength (A)')
        ax1.set_ylabel('counts')
        ax1.set_title('WAVELENGTH')

# ============================================================================
# SKADI pixel detector
# ============================================================================

class SKADIEventsPlotter(BaseEventsPlotter):

    def plot_tof(self, fig_num=333):
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('ToF distr per tile')
        ax_tof = self.axis_set.ax_tof
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            hist_tt = self.hist.hist1d(ax_tof.centers, m['ToF'][sel] / 1e9)

            grid.ax[0][k].step(ax_tof.centers * 1e3, hist_tt, 'b', where='mid')
            grid.ax[0][k].set_xlabel('ToF (ms)')
            grid.ax[0][k].set_title(f'Tile ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')

    def plot_lambda(self, fig_num=339):
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Wavelength distr per tile')
        ax_lambda = self.axis_set.ax_lambda
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            hist_wa = self.hist.hist1d(ax_lambda.centers, m['wavelength'][sel])

            grid.ax[0][k].step(ax_lambda.centers, hist_wa, 'r', where='mid')
            grid.ax[0][k].set_xlabel('wavelength (A)')
            grid.ax[0][k].set_title(f'Tile ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')

    def plot_time_between_events(self, fig_num=209):
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

            grid.ax[0][k].step(ax_rate.centers * 1e6, hist_rate, fg_color(), where='mid')
            grid.ax[0][k].set_xlabel('delta time between events (us)')
            grid.ax[0][k].set_title(f'Tile ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('num of events')

    def plot_phs(self, fig_num=601):
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        pix = int(self.config['pix'])
        n_channels = pix * pix
        xbins = np.linspace(0, n_channels - 1, n_channels)

        grid = PlotGrid(fig_num, 1, len(self.unit_ids))
        grid.fig.suptitle('Pulse Heigth Spectra')
        ax_energy = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            histoch, _, _ = self.hist.hist2d(
                ax_energy.centers, m['pulseHeight0'][sel], xbins, m['channel'][sel]
            )

            grid.ax[0][k].imshow(
                histoch, aspect='auto', norm=norm_colors, interpolation='none',
                extent=[ax_energy.start, ax_energy.stop, xbins[0], xbins[-1]],
                origin='lower', cmap='jet',
            )
            grid.ax[0][k].set_xlabel('pulse height (a.u.)')
            grid.ax[0][k].set_title(f'Tile ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('ch no.')

    def plot_xy(self, fig_num=101):
        """3-row image per bank: X vs Y + X projection + Y projection, one column per bank."""
        if self.is_empty:
            return
        log_scale = self.parameters.plotting.plotIMGlog
        abs_units = self.parameters.plotting.plotABSunits
        norm_colors = log_scale_norm(log_scale)
        m = self.matrix

        if not abs_units:
            ax_x, ax_y = self.axis_set.ax_pix_x, self.axis_set.ax_pix_y
            x_values, y_values = m['coordinate0'], m['coordinate1']
            xlabel, ylabel = 'X pixel', 'Y pixel'
        else:
            ax_x, ax_y = self.axis_set.ax_pix_x_mm, self.axis_set.ax_pix_y_mm
            x_values, y_values = m['absCoordinate0'], m['absCoordinate1']
            xlabel, ylabel = 'X (mm)', 'Y (mm)'

        bank_ids = sorted(np.unique(m['bank']))
        n_banks = len(bank_ids)

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig = fig_num
        else:
            fig = plt.figure(num=fig_num)
        fig.suptitle('DET image')

        gs = fig.add_gridspec(
            3, n_banks, height_ratios=[4, 1, 1],
            hspace=0.30, wspace=0.22,
            left=0.04, right=0.97, top=0.95, bottom=0.06,
        )

        fig.canvas.draw()
        W, H = fig.get_size_inches()

        for k, bank in enumerate(bank_ids):
            sel_bank = m['bank'] == bank
            sel_valid = (m['coordinate0'] >= 0) & (m['coordinate1'] >= 0)
            sel = sel_bank & sel_valid

            sel_bank_x = sel_bank & (m['coordinate0'] >= 0)
            sel_bank_y = sel_bank & (m['coordinate1'] >= 0)

            ax_img = fig.add_subplot(gs[0, k])
            ax_px  = fig.add_subplot(gs[1, k])
            ax_py  = fig.add_subplot(gs[2, k])

            h2d, _, _ = self.hist.hist2d(ax_x.centers, x_values[sel], ax_y.centers, y_values[sel])
            h_proj_x_all = self.hist.hist1d(ax_x.centers, x_values[sel_bank_x])
            h_proj_x_2d = np.sum(h2d, axis=0)
            h_proj_y_all = self.hist.hist1d(ax_y.centers, y_values[sel_bank_y])
            h_proj_y_2d = np.sum(h2d, axis=1)

            if log_scale:
                max_val = np.max(h2d) if np.max(h2d) > 0 else 1
                norm_colors = colors.LogNorm(vmin=1, vmax=max_val)
            else:
                norm_colors = colors.Normalize()

            pos1 = ax_img.imshow(
                h2d, aspect='equal', norm=norm_colors, interpolation='none',
                extent=[ax_x.start, ax_x.stop, ax_y.start, ax_y.stop],
                origin='lower', cmap='viridis',
            )
            _safe_colorbar(fig, pos1, ax_img, f'Bank {bank}', orientation='vertical', fraction=0.046, pad=0.02)
            ax_img.set_title(f'Bank {bank}')
            ax_img.set_xlabel(xlabel)
            if k == 0:
                ax_img.set_ylabel(ylabel)

            ax_px.step(ax_x.centers, h_proj_x_all, 'r', where='mid', label='1D')
            ax_px.step(ax_x.centers, h_proj_x_2d, 'b', where='mid', label='2D')
            if log_scale:
                ax_px.set_yscale('log')
            ax_px.set_xlim(ax_x.start, ax_x.stop)
            ax_px.set_xlabel(xlabel)
            if k == 0:
                ax_px.set_ylabel('counts')
            ax_px.legend(loc='upper right', shadow=False, fontsize='medium')

            ax_py.step(ax_y.centers, h_proj_y_all, 'r', where='mid', label='1D')
            ax_py.step(ax_y.centers, h_proj_y_2d, 'b', where='mid', label='2D')
            if log_scale:
                ax_py.set_yscale('log')
            ax_py.set_xlim(ax_y.start, ax_y.stop)
            ax_py.set_xlabel(ylabel)
            if k == 0:
                ax_py.set_ylabel('counts')
            ax_py.legend(loc='upper right', shadow=False, fontsize='medium')

            # Let matplotlib enforce the true square box for the image (aspect='equal'
            # above already did this on draw). Just copy its resulting x0/width onto
            # the projection axes so they line up — don't override ax_img's own position.
            fig.canvas.draw()
            img_pos = ax_img.get_position()

            px_pos = ax_px.get_position()
            py_pos = ax_py.get_position()
            ax_px.set_position([img_pos.x0, px_pos.y0, img_pos.width, px_pos.height])
            ax_py.set_position([img_pos.x0, py_pos.y0, img_pos.width, py_pos.height])

# ============================================================================
# NMX (X/Y strip detector, no wire/strip asymmetry)
# ============================================================================

class NMXEventsPlotter(VMMEventsPlotter):
    """
    NMX events: X and Y are equally primary. Bank is derived from ID
    (ID // 10 = bank, remainder = quadrant).
    """

    X_LABEL = 'Strip X'
    Y_LABEL = 'Strip Y'
    X_TAG = 'x'
    Y_TAG = 'y'
    COINC_LABEL = 'X/Y'
    ACCEPT_1D_Y = True
    X_COUNT_KEYS = ('strips',)
    Y_COUNT_KEYS = ('strips',)

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
        self.bank_ids = sorted(np.unique(self.matrix['ID'] // 10)) if not self.is_empty else []

    def _get_x_channel(self, global_x_coord):
        num_strips = self._config_count(self.X_COUNT_KEYS)
        return np.mod(global_x_coord, num_strips)

    def _get_y_channel(self, global_y_coord):
        num_strips = self._config_count(self.Y_COUNT_KEYS)
        return np.mod(global_y_coord, num_strips)

    def plot_x_lambda(self, fig_num=103):
        """Wavelength vs position, one row per electrode (X, Y), one column per bank."""
        if self.is_empty:
            return

        norm_colors = log_scale_norm(self.parameters.plotting.plotIMGlog)
        ax_lambda = self.axis_set.ax_lambda
        ax_x, ax_y = self.axis_set.ax_x, self.axis_set.ax_y
        m = self.matrix

        grid = PlotGrid(fig_num, 2, len(self.bank_ids))
        grid.fig.suptitle('DET wavelength')

        for k, bank in enumerate(self.bank_ids):
            sel = ((m['ID'] // 10) == bank) & self.selc

            h_x, _, _ = self.hist.hist2d(ax_lambda.centers, m['wavelength'][sel], ax_x.centers, m['coordinate0'][sel])
            h_y, _, _ = self.hist.hist2d(ax_lambda.centers, m['wavelength'][sel], ax_y.centers, m['coordinate1'][sel])

            pos_x = grid.ax[0][k].imshow(h_x, aspect='auto', norm=norm_colors, interpolation='nearest',
                                          extent=[ax_lambda.start, ax_lambda.stop, ax_x.start, ax_x.stop], origin='lower', cmap='viridis')
            _safe_colorbar(grid.fig, pos_x, grid.ax[0][k], f'Bank {bank}')
            grid.ax[0][k].set_title(f'Bank {bank}')
            if k == 0:
                grid.ax[0][k].set_ylabel(f'{self.X_LABEL} ch.')

            pos_y = grid.ax[1][k].imshow(h_y, aspect='auto', norm=norm_colors, interpolation='nearest',
                                          extent=[ax_lambda.start, ax_lambda.stop, ax_y.start, ax_y.stop], origin='lower', cmap='viridis')
            _safe_colorbar(grid.fig, pos_y, grid.ax[1][k], f'Bank {bank}')
            grid.ax[1][k].set_xlabel('wavelength (A)')
            if k == 0:
                grid.ax[1][k].set_ylabel(f'{self.Y_LABEL} ch.')

    def plot_tof_xy(self, fig_num=102):
        """ToF vs position, one row per electrode (X, Y), one column per bank."""
        if self.is_empty:
            return

        norm_colors = log_scale_norm(self.parameters.plotting.plotIMGlog)
        ax_tof = self.axis_set.ax_tof
        ax_x, ax_y = self.axis_set.ax_x, self.axis_set.ax_y
        m = self.matrix

        grid = PlotGrid(fig_num, 2, len(self.bank_ids))
        grid.fig.suptitle('DET ToF')

        for k, bank in enumerate(self.bank_ids):
            sel = ((m['ID'] // 10) == bank) & self.selc

            h_x, _, _ = self.hist.hist2d(ax_tof.centers, m['ToF'][sel] / 1e9, ax_x.centers, m['coordinate0'][sel])
            h_y, _, _ = self.hist.hist2d(ax_tof.centers, m['ToF'][sel] / 1e9, ax_y.centers, m['coordinate1'][sel])

            pos_x = grid.ax[0][k].imshow(h_x, aspect='auto', norm=norm_colors, interpolation='nearest',
                                          extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_x.start, ax_x.stop], origin='lower', cmap='viridis')
            _safe_colorbar(grid.fig, pos_x, grid.ax[0][k], f'Bank {bank}')
            grid.ax[0][k].set_title(f'Bank {bank}')
            if k == 0:
                grid.ax[0][k].set_ylabel(f'{self.X_LABEL} ch.')

            pos_y = grid.ax[1][k].imshow(h_y, aspect='auto', norm=norm_colors, interpolation='nearest',
                                          extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_y.start, ax_y.stop], origin='lower', cmap='viridis')
            _safe_colorbar(grid.fig, pos_y, grid.ax[1][k], f'Bank {bank}')
            grid.ax[1][k].set_xlabel('ToF (ms)')
            if k == 0:
                grid.ax[1][k].set_ylabel(f'{self.Y_LABEL} ch.')

    def plot_xy(self, fig_num=101):
        """3-row image per bank: X vs Y + X projection + Y projection, one column per bank."""
        if self.is_empty:
            return
        log_scale = self.parameters.plotting.plotIMGlog
        norm_colors = log_scale_norm(log_scale)
        m = self.matrix

        ax_x, ax_y = self.axis_set.ax_x, self.axis_set.ax_y
        x_values, y_values = m['coordinate0'], m['coordinate1']
        xlabel, ylabel = 'X ch.', 'Y ch.'

        n_banks = len(self.bank_ids)

        if isinstance(fig_num, matplotlib.figure.Figure):
            fig = fig_num
        else:
            fig = plt.figure(num=fig_num)
        fig.suptitle('DET image')

        gs = fig.add_gridspec(
            3, n_banks, height_ratios=[4, 1, 1],
            hspace=0.30, wspace=0.22,
            left=0.04, right=0.97, top=0.95, bottom=0.06,
        )

        fig.canvas.draw()  
        W, H = fig.get_size_inches()

        for k, bank in enumerate(self.bank_ids):
            sel_bank = ((m['ID'] // 10) == bank) & self.selc
            sel_bank_x = ((m['ID'] // 10) == bank) & (m['coordinate0'] >= 0)
            sel_bank_y = ((m['ID'] // 10) == bank) & (m['coordinate1'] >= 0)

            ax_img = fig.add_subplot(gs[0, k])
            ax_px  = fig.add_subplot(gs[1, k])
            ax_py  = fig.add_subplot(gs[2, k])

            h2d, _, _ = self.hist.hist2d(ax_x.centers, x_values[sel_bank], ax_y.centers, y_values[sel_bank])
            h_proj_x_all = self.hist.hist1d(ax_x.centers, x_values[sel_bank_x])
            h_proj_x_2d = np.sum(h2d, axis=0)
            h_proj_y_all = self.hist.hist1d(ax_y.centers, y_values[sel_bank_y])
            h_proj_y_2d = np.sum(h2d, axis=1)

            pos1 = ax_img.imshow(h2d, aspect='auto', norm=norm_colors, interpolation='none',
                                extent=[ax_x.start, ax_x.stop, ax_y.start, ax_y.stop], origin='lower', cmap='viridis')
            _safe_colorbar(fig, pos1, ax_img, f'Bank {bank}', orientation='vertical', fraction=0.046, pad=0.02)
            ax_img.set_title(f'Bank {bank}')
            ax_img.set_xlabel(xlabel)
            if k == 0:
                ax_img.set_ylabel(ylabel)

            ax_px.step(ax_x.centers, h_proj_x_all, 'r', where='mid', label='1D')
            ax_px.step(ax_x.centers, h_proj_x_2d, 'b', where='mid', label='2D')
            if log_scale:
                ax_px.set_yscale('log')
            ax_px.set_xlim(ax_x.start, ax_x.stop)
            ax_px.set_xlabel(xlabel)
            if k == 0:
                ax_px.set_ylabel('counts')
            ax_px.legend(loc='upper right', shadow=False, fontsize='medium')

            ax_py.step(ax_y.centers, h_proj_y_all, 'r', where='mid', label='1D')
            ax_py.step(ax_y.centers, h_proj_y_2d, 'b', where='mid', label='2D')
            if log_scale:
                ax_py.set_yscale('log')
            ax_py.set_xlim(ax_y.start, ax_y.stop)
            ax_py.set_xlabel(ylabel)
            if k == 0:
                ax_py.set_ylabel('counts')
            ax_py.legend(loc='upper right', shadow=False, fontsize='medium')

            fig.canvas.draw()
            img_pos = ax_img.get_position()

            avail_w_in = img_pos.width * W
            avail_h_in = img_pos.height * H
            side_in = min(avail_w_in, avail_h_in)

            new_width = side_in / W
            new_height = side_in / H
            new_x0 = img_pos.x0 + (img_pos.width - new_width) / 2
            new_y0 = img_pos.y0 + (img_pos.height - new_height) / 2
            ax_img.set_position([new_x0, new_y0, new_width, new_height])

            px_pos = ax_px.get_position()
            py_pos = ax_py.get_position()
            ax_px.set_position([new_x0, px_pos.y0, new_width, px_pos.height])
            ax_py.set_position([new_x0, py_pos.y0, new_width, py_pos.height])