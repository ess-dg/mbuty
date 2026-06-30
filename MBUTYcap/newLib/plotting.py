"""
plotting.py

Clean, class-hierarchy plotting layer for the MBUTY pipeline. Replaces
libPlotting.py. Operates directly on the new matrix-based readouts / hits /
events containers (physical unit ID based -- no Cassette/hybrid name
overloading).

Layout
------
PlotGrid                      thin wrapper around plt.subplots, replaces preparePlotMatrix.
log_scale_norm()              small helper, replaces logScaleMap.

BasePlotter                   shared empty-container guard + matrix slicing, used by
                               every concrete plotter below.

BaseEventsPlotter              detector-agnostic event-level physics plots (ToF,
                               wavelength, instantaneous rate, multiplicity, global
                               PHS) -- works for ANY events subclass exposing the
                               relevant base/optional fields.
  VMMEventsPlotter             Multi-Blade / Multi-Grid specific plots: 2D detector
                               image (wire vs strip), X-vs-Lambda, channel-resolved PHS.

BaseHitsPlotter                detector-agnostic hit-level diagnostics (per-unit ID
                               timestamp scatter).
  VMMHitsPlotter                wire/strip raw mapped-channel histograms + timestamps.

BaseReadoutsPlotter             detector-agnostic readout-level diagnostics (chopper
                               reset interval).
  VMMReadoutsPlotter             per-hybrid raw ASIC channel histograms, ADC-vs-channel.

MonitorPlotter                 beam monitor ToF / PHS / wavelength (standalone, not
                               part of the events hierarchy -- monitor events use a
                               distinct container).
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import sys, os
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
from newLib.histograms import Histogrammer
from newLib.colors import WARN, RESET


# ============================================================================
# Shared utilities
# ============================================================================

class PlotGrid:
    """Thin wrapper around plt.subplots producing a guaranteed-2D axis grid."""

    def __init__(self, fig_num, n_rows, n_cols=1, fig_size=(12, 12), sharex='col', sharey='row'):
        self.fig, axes = plt.subplots(
            num=fig_num, figsize=fig_size, nrows=n_rows, ncols=n_cols,
            sharex=sharex, sharey=sharey,
        )
        self.ax = np.atleast_2d(axes).reshape(n_rows, n_cols)


def log_scale_norm(log_scale: bool):
    return LogNorm() if log_scale else None


def _safe_colorbar(fig, mappable, ax, warning_label: str, **kwargs):
    """imshow + LogNorm occasionally crashes when a panel is all-zero; degrade gracefully."""
    try:
        fig.colorbar(mappable, ax=ax, **kwargs)
    except Exception:
        print(f"\n --> {WARN}WARNING: Cannot plot {warning_label} in Log scale, changed to linear{RESET}", end='')


# ============================================================================
# Base plotter
# ============================================================================

class BasePlotter:
    """
    Common scaffolding for every plotter in this module.

    Wraps a single container (readouts / hits / events instance) and exposes
    `self.matrix` as the active (already-trimmed) data block, plus an
    `is_empty` flag so every plot method can guard with a one-liner instead
    of the legacy checkXxxClass() pattern.
    """

    def __init__(self, container, hist_out_of_bounds: bool = True):
        self.container = container
        self.hist = Histogrammer(hist_out_of_bounds)
        self.is_empty = container.fill_count == 0

        if self.is_empty:
            print(f'\t{WARN}WARNING: {type(container).__name__} is empty -> skipping plots{RESET}')

    @property
    def matrix(self):
        return self.container.matrix[:self.container.fill_count]

    def _has_field(self, name: str) -> bool:
        return name in self.container.matrix.dtype.names

    def unit_ids(self) -> np.ndarray:
        """Sorted unique physical unit IDs present in this container (hits/events only)."""
        return np.unique(self.matrix['ID'])


# ============================================================================
# Events plotters
# ============================================================================

class BaseEventsPlotter(BasePlotter):
    """
    Detector-agnostic physics plots built from the common `events` base
    schema (ID, coordinate0/1, pulseHeight0, ToF, wavelength). Optional
    fields (pulseHeight1, mult0, mult1) are detected via the matrix dtype
    and silently skipped if a concrete events subclass doesn't carry them.

    `coincidence_2d` selects the convention for "this event has a valid
    second coordinate" (2D-reconstructed), defaulting to coordinate1 >= 0.
    """

    def __init__(self, container, axis_set, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.axis_set = axis_set

    def _coincidence_mask(self, sub_matrix) -> np.ndarray:
        return sub_matrix['coordinate1'] >= 0

    def plot_tof(self, unit_ids=None, fig_num=333):
        """ToF distribution per physical unit: all events vs 2D-coincident events."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('ToF distribution per unit')
        ax_tof = self.axis_set.ax_tof

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            sel_2d = sel & self._coincidence_mask(self.matrix)

            h_all = self.hist.hist1d(ax_tof.centers, self.matrix['ToF'][sel] / 1e9)
            h_2d  = self.hist.hist1d(ax_tof.centers, self.matrix['ToF'][sel_2d] / 1e9)

            ax = grid.ax[0][k]
            ax.step(ax_tof.centers * 1e3, h_all, 'r', where='mid', label='all')
            ax.step(ax_tof.centers * 1e3, h_2d,  'b', where='mid', label='2D')
            ax.set_xlabel('ToF (ms)')
            ax.set_title(f'ID {uid}')
            if k == 0:
                ax.set_ylabel('counts')
            ax.legend(loc='upper right', fontsize='large')

    def plot_wavelength(self, unit_ids=None, fig_num=339):
        """Wavelength distribution per physical unit: all events vs 2D-coincident events."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('Wavelength distribution per unit')
        ax_lambda = self.axis_set.ax_lambda

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            sel_2d = sel & self._coincidence_mask(self.matrix)

            h_all = self.hist.hist1d(ax_lambda.centers, self.matrix['wavelength'][sel])
            h_2d  = self.hist.hist1d(ax_lambda.centers, self.matrix['wavelength'][sel_2d])

            ax = grid.ax[0][k]
            ax.step(ax_lambda.centers, h_all, 'r', where='mid', label='all')
            ax.step(ax_lambda.centers, h_2d,  'b', where='mid', label='2D')
            ax.set_xlabel('wavelength (A)')
            ax.set_title(f'ID {uid}')
            if k == 0:
                ax.set_ylabel('counts')
            ax.legend(loc='upper right', fontsize='large')

    def plot_instantaneous_rate(self, unit_ids=None, fig_num=209):
        """Histogram of delta-time between consecutive 2D-coincident events, per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('Instantaneous Rate')
        ax_rate = self.axis_set.ax_inst_rate
        hist_no_oob = Histogrammer(out_of_bounds=False)

        for k, uid in enumerate(unit_ids):
            sel = (self.matrix['ID'] == uid) & self._coincidence_mask(self.matrix)
            dt = np.diff(self.matrix['timeStamp'][sel])
            h_rate = hist_no_oob.hist1d(ax_rate.centers, dt / 1e9)

            ax = grid.ax[0][k]
            ax.step(ax_rate.centers * 1e6, h_rate, 'k', where='mid', label='w')
            ax.set_xlabel('delta time between events (us)')
            ax.set_title(f'ID {uid}')
            if k == 0:
                ax.set_ylabel('num of events')

    def plot_multiplicity(self, unit_ids=None, fig_num=401, extent: int = 7):
        """
        Normalized 1D multiplicity distributions (mult0, mult1, mult0 coincident)
        plus a 2D mult0-vs-mult1 heatmap, per unit. No-op if mult0/mult1 fields
        are not present on this events subclass (e.g. R5560).
        """
        if self.is_empty:
            return
        if not (self._has_field('mult0') and self._has_field('mult1')):
            return

        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 2, len(unit_ids))
        grid.fig.suptitle('Events - multiplicity')
        ax_mult = self.axis_set.ax_mult
        xx = ax_mult.centers
        width = 0.2

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            sel_2d = sel & self._coincidence_mask(self.matrix)

            mult0 = self.hist.hist1d(xx, self.matrix['mult0'][sel])
            mult1 = self.hist.hist1d(xx, self.matrix['mult1'][sel])
            mult0_coinc = self.hist.hist1d(xx, self.matrix['mult0'][sel_2d])
            mult2d = self.hist.hist2d(xx, self.matrix['mult0'][sel_2d], xx, self.matrix['mult1'][sel_2d])[0]

            if np.any(sel):
                mult0_n = mult0 / np.sum(mult0[1:])
                mult1_n = mult1 / np.sum(mult1[1:])
                mult1_n_all = mult1 / np.sum(mult1)
                mult0_coinc_n = mult0_coinc / np.sum(mult0_coinc[1:])
                mult2d_n = mult2d / np.sum(mult2d)
            else:
                mult0_n = mult1_n = mult1_n_all = mult0_coinc_n = np.zeros(len(xx))
                mult2d_n = np.zeros((len(xx), len(xx)))

            ax0 = grid.ax[0][k]
            ax0.bar(xx[:extent] - width, mult0_n[:extent], width, color='m', label='coord0')
            ax0.bar(xx[1:extent] + width, mult1_n[1:extent], width, color='b', label='coord1')
            ax0.bar(xx[0] + width, mult1_n_all[0], width, color='c', label='no coord1')
            ax0.bar(xx[:extent], mult0_coinc_n[:extent], width, color='r', label='coord0/1')
            ax0.set_xlabel('multiplicity')
            ax0.set_title(f'ID {uid}')
            ax0.legend(loc='upper right', fontsize='large')
            if k == 0:
                ax0.set_ylabel('probability')

            pos = grid.ax[1][k].imshow(
                mult2d_n[:extent, :extent], aspect='auto', interpolation='none',
                extent=[xx[0] - 0.5, xx[extent] - 0.5, xx[0] - 0.5, xx[extent] - 0.5],
                origin='lower', cmap='jet',
            )
            grid.ax[1][k].set_xlabel('multiplicity coord0')
            if k == 0:
                grid.ax[1][k].set_ylabel('multiplicity coord1')
            plt.colorbar(pos, ax=grid.ax[1][k])

    def plot_phs_global(self, unit_ids=None, fig_num=601, logScale: bool = False):
        """Global (channel-unresolved) pulse height spectra: coord0, coord1, coincident, per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('Pulse Height Spectra (global)')
        ax_e = self.axis_set.ax_energy
        has_ph1 = self._has_field('pulseHeight1')

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            sel_2d = sel & self._coincidence_mask(self.matrix)

            h0 = self.hist.hist1d(ax_e.centers, self.matrix['pulseHeight0'][sel])

            ax = grid.ax[0][k]
            ax.step(ax_e.centers, h0, 'r', where='mid', label='coord0')

            if has_ph1:
                h1 = self.hist.hist1d(ax_e.centers, self.matrix['pulseHeight1'][sel_2d])
                h0c = self.hist.hist1d(ax_e.centers, self.matrix['pulseHeight0'][sel_2d])
                ax.step(ax_e.centers, h1, 'b', where='mid', label='coord1')
                ax.step(ax_e.centers, h0c, 'k', where='mid', label='coord0/1')

            if logScale:
                ax.set_yscale('log')
            ax.set_xlabel('pulse height (a.u.)')
            ax.set_title(f'ID {uid}')
            ax.legend(loc='upper right', fontsize='large')
            if k == 0:
                ax.set_ylabel('counts')


class VMMEventsPlotter(BaseEventsPlotter):
    """
    Multi-Blade / Multi-Grid (VMM) specific event plots: the 2D detector
    image (wire vs strip), the wire-vs-wavelength image, and the
    channel-resolved pulse height spectra / correlation.
    """

    def plot_detector_image(self, logScale: bool = False, absUnits: bool = False, orientation: str = 'vertical', fig_num=101):
        """2D wire/strip detector image + 1D wire projection + wire-vs-ToF image."""
        if self.is_empty:
            return
        normColors = log_scale_norm(logScale)
        m = self.matrix
        sel_2d = self._coincidence_mask(m)

        if absUnits:
            ax_w, ax_s = self.axis_set.ax_wires_mm, self.axis_set.ax_strips_mm
            coord0, coord1 = m['absCoordinate0'], m['absCoordinate1']
            xlabel, ylabel = 'Wire coord. (mm)', 'Strip (mm)'
        else:
            ax_w, ax_s = self.axis_set.ax_wires, self.axis_set.ax_strips
            coord0, coord1 = m['coordinate0'], m['coordinate1']
            xlabel, ylabel = 'Wire ch.', 'Strip ch.'

        ax_tof = self.axis_set.ax_tof

        h2d, proj1d, h_tof = self.hist.hist_xyz(
            ax_w.centers, coord0[sel_2d], ax_s.centers, coord1[sel_2d], ax_tof.centers, m['ToF'][sel_2d] / 1e9,
        )
        proj_all = self.hist.hist1d(ax_w.centers, coord0)
        proj_2d = np.sum(h2d, axis=0)

        if orientation == 'vertical':
            fig2d, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(6, 12), nrows=2, ncols=1)
            pos1 = ax1.imshow(h2d, aspect='auto', norm=normColors, interpolation='none',
                               extent=[ax_w.start, ax_w.stop, ax_s.stop, ax_s.start], origin='upper', cmap='viridis')
            _safe_colorbar(fig2d, pos1, ax1, 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_xlabel(xlabel)
            ax1.set_ylabel(ylabel)
        else:
            fig2d, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(12, 6), nrows=1, ncols=2)
            pos1 = ax1.imshow(np.rot90(h2d, 1), aspect='auto', norm=normColors, interpolation='none',
                               extent=[ax_s.start, ax_s.stop, ax_w.start, ax_w.stop], origin='upper', cmap='viridis')
            _safe_colorbar(fig2d, pos1, ax1, 'XY', orientation='horizontal', fraction=0.07, anchor=(1.0, 0.0))
            ax1.set_ylabel(xlabel)
            ax1.set_xlabel(ylabel)

        fig2d.suptitle('DET image')

        ax2.step(ax_w.centers, proj_all, 'r', where='mid', label='1D')
        ax2.step(ax_w.centers, proj_2d, 'b', where='mid', label='2D')
        if logScale:
            ax2.set_yscale('log')
        ax2.set_xlabel(xlabel)
        ax2.set_ylabel('counts')
        ax2.set_xlim(ax_w.start, ax_w.stop)
        ax2.legend(loc='upper right', fontsize='large')

        fig_tof, ax_t = plt.subplots(num=fig_num + 1, figsize=(6, 6), nrows=1, ncols=1)
        pos_t = ax_t.imshow(h_tof, aspect='auto', norm=normColors, interpolation='nearest',
                             extent=[ax_tof.start * 1e3, ax_tof.stop * 1e3, ax_w.start, ax_w.stop],
                             origin='lower', cmap='viridis')
        _safe_colorbar(fig_tof, pos_t, ax_t, 'YToF')
        ax_t.set_ylabel(xlabel)
        ax_t.set_xlabel('ToF (ms)')
        fig_tof.suptitle('DET ToF')

    def plot_wire_vs_lambda(self, logScale: bool = False, absUnits: bool = False, fig_num=103):
        """2D image of wire channel (or mm) vs wavelength."""
        if self.is_empty:
            return
        normColors = log_scale_norm(logScale)
        m = self.matrix
        sel_2d = self._coincidence_mask(m)
        ax_lambda = self.axis_set.ax_lambda

        if absUnits:
            ax_w = self.axis_set.ax_wires_mm
            coord0 = m['absCoordinate0']
            ylabel = 'Wire coord. (mm)'
        else:
            ax_w = self.axis_set.ax_wires
            coord0 = m['coordinate0']
            ylabel = 'Wire ch.'

        h, _ = self.hist.hist2d(ax_lambda.centers, m['wavelength'][sel_2d], ax_w.centers, coord0[sel_2d])

        fig, ax = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)
        pos = ax.imshow(h, aspect='auto', norm=normColors, interpolation='nearest',
                         extent=[ax_lambda.start, ax_lambda.stop, ax_w.start, ax_w.stop],
                         origin='lower', cmap='viridis')
        _safe_colorbar(fig, pos, ax, 'XY')
        ax.set_ylabel(ylabel)
        ax.set_xlabel('wavelength (A)')
        fig.suptitle('DET wavelength')

    def plot_phs(self, unit_ids=None, logScale: bool = False, fig_num=601):
        """Channel-resolved pulse height spectra: wire, strip, wire-coincident, + global sum, per unit."""
        if self.is_empty:
            return
        if not self._has_field('pulseHeight1'):
            return

        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 4, len(unit_ids))
        grid.fig.suptitle('Pulse Height Spectra (channel-resolved)')
        normColors = log_scale_norm(logScale)
        ax_e = self.axis_set.ax_energy
        wire_axis = self.axis_set.ax_wires.centers
        strip_axis = self.axis_set.ax_strips.centers

        m = self.matrix
        wire_ch = np.round(np.mod(m['coordinate0'], len(wire_axis)))
        strip_ch = np.round(m['coordinate1'])

        for k, uid in enumerate(unit_ids):
            sel = m['ID'] == uid
            sel_2d = sel & self._coincidence_mask(m)

            phs_w, _ = self.hist.hist2d(ax_e.centers, m['pulseHeight0'][sel], wire_axis, wire_ch[sel])
            phs_s, _ = self.hist.hist2d(ax_e.centers, m['pulseHeight1'][sel_2d], strip_axis, strip_ch[sel_2d])
            phs_wc, _ = self.hist.hist2d(ax_e.centers, m['pulseHeight0'][sel_2d], wire_axis, wire_ch[sel_2d])

            grid.ax[0][k].imshow(phs_w, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, wire_axis[0], wire_axis[-1]], origin='lower', cmap='jet')
            grid.ax[1][k].imshow(phs_s, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, strip_axis[0], strip_axis[-1]], origin='lower', cmap='jet')
            grid.ax[2][k].imshow(phs_wc, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, wire_axis[0], wire_axis[-1]], origin='lower', cmap='jet')
            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('wire ch. no.')
                grid.ax[1][k].set_ylabel('strip ch. no.')
                grid.ax[2][k].set_ylabel('wire coinc. ch. no.')

            phs_w_g, phs_s_g, phs_wc_g = np.sum(phs_w, axis=0), np.sum(phs_s, axis=0), np.sum(phs_wc, axis=0)
            grid.ax[3][k].step(ax_e.centers, phs_w_g, 'r', where='mid', label='w')
            grid.ax[3][k].step(ax_e.centers, phs_s_g, 'b', where='mid', label='s')
            grid.ax[3][k].step(ax_e.centers, phs_wc_g, 'k', where='mid', label='w/s')
            grid.ax[3][k].set_xlabel('pulse height (a.u.)')
            grid.ax[3][k].legend(loc='upper right', fontsize='large')
            if k == 0:
                grid.ax[3][k].set_ylabel('counts')

    def plot_phs_correlation(self, unit_ids=None, logScale: bool = False, fig_num=602):
        """Wire-pulse-height vs strip-pulse-height 2D correlation, per unit."""
        if self.is_empty:
            return
        if not self._has_field('pulseHeight1'):
            return

        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids), fig_size=(12, 6))
        grid.fig.suptitle('Pulse Height Spectrum - Correlation coord0/coord1')
        normColors = log_scale_norm(logScale)
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel_2d = (m['ID'] == uid) & self._coincidence_mask(m)
            corr, _ = self.hist.hist2d(ax_e.centers, m['pulseHeight0'][sel_2d], ax_e.centers, m['pulseHeight1'][sel_2d])

            grid.ax[0][k].imshow(corr, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, ax_e.start, ax_e.stop], origin='lower', cmap='jet')
            grid.ax[0][k].set_title(f'ID {uid}')
            grid.ax[0][k].set_xlabel('pulse height wires (a.u.)')
            if k == 0:
                grid.ax[0][k].set_ylabel('pulse height strips (a.u.)')


# ============================================================================
# Hits plotters
# ============================================================================

class BaseHitsPlotter(BasePlotter):
    """Detector-agnostic hit-level diagnostic: per-unit timestamp scatter."""

    def plot_timestamps(self, unit_ids=None, fig_num=1004):
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('Hits - time stamps')

        for k, uid in enumerate(unit_ids):
            ts = self.matrix['timeStamp'][self.matrix['ID'] == uid]
            xx = np.arange(len(ts))
            ax = grid.ax[0][k]
            ax.scatter(xx, ts, 0.8, color='k', marker='+')
            ax.set_xlabel('hit no.')
            ax.set_ylabel('time (ns)')
            ax.set_title(f'ID {uid}')
            ax.grid(axis='both', alpha=0.75)


class VMMHitsPlotter(BaseHitsPlotter):
    """
    Wire/strip raw mapped-channel diagnostics for hitsVMMnormal (plane/index
    fields) and hitsVMMclustered (index0/index1 fields).
    """

    def __init__(self, container, n_channels: int = 64, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.n_channels = n_channels
        self.xbins = np.linspace(0, n_channels - 1, n_channels)
        self.is_clustered = self._has_field('index0')

    def _wire_strip_indices(self, sel: np.ndarray):
        if self.is_clustered:
            return self.matrix['index0'][sel], self.matrix['index1'][sel]
        wires = sel & (self.matrix['plane'] == 0)
        strips = sel & (self.matrix['plane'] == 1)
        return self.matrix['index'][wires], self.matrix['index'][strips]

    def plot_channels_raw(self, unit_ids=None, fig_num=1003):
        """Mapped wire/strip channel occupancy per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 2, len(unit_ids))
        grid.fig.suptitle('Hits - mapped channels')

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            wire_idx, strip_idx = self._wire_strip_indices(sel)
            wire_ch = np.mod(wire_idx, self.n_channels)

            h_wire = self.hist.hist1d(self.xbins, wire_ch)
            h_strip = self.hist.hist1d(self.xbins, strip_idx)

            grid.ax[0][k].bar(self.xbins, h_wire, 0.8, color='r')
            grid.ax[1][k].bar(self.xbins, h_strip, 0.8, color='b')
            grid.ax[0][k].set_xlabel('hit wire ch no.')
            grid.ax[1][k].set_xlabel('hit strip ch no.')
            grid.ax[0][k].set_title(f'ID {uid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
                grid.ax[1][k].set_ylabel('counts')

    def plot_timestamps_vs_channel(self, unit_ids=None, fig_num=1005):
        """Wire/strip channel vs hit timestamp, per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        grid = PlotGrid(fig_num, 1, len(unit_ids))
        grid.fig.suptitle('Hits - W/S channel VS time stamps')

        for k, uid in enumerate(unit_ids):
            sel = self.matrix['ID'] == uid
            if self.is_clustered:
                ts_wire = self.matrix['timeStamp'][sel]
                ts_strip = ts_wire
                wire_idx, strip_idx = self._wire_strip_indices(sel)
            else:
                wires = sel & (self.matrix['plane'] == 0)
                strips = sel & (self.matrix['plane'] == 1)
                ts_wire = self.matrix['timeStamp'][wires]
                ts_strip = self.matrix['timeStamp'][strips]
                wire_idx = self.matrix['index'][wires]
                strip_idx = self.matrix['index'][strips]

            ax = grid.ax[0][k]
            ax.scatter(np.mod(wire_idx, self.n_channels), ts_wire, 0.8, color='r', marker='+')
            ax.scatter(strip_idx, ts_strip, 0.8, color='b', marker='+')
            ax.set_ylabel('time (ns)')
            ax.set_xlabel('W or S channel (after mapping)')
            ax.set_title(f'ID {uid}')
            ax.grid(axis='both', alpha=0.75)


# ============================================================================
# Readouts plotters
# ============================================================================

class BaseReadoutsPlotter(BasePlotter):
    """Detector-agnostic readout-level diagnostic: chopper reset interval."""

    def plot_chopper_resets(self, fig_num=9999):
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, 2)
        grid.fig.suptitle('Chopper Resets - all channels')

        xax = np.arange(len(self.matrix['pulseT']))
        resets_time = (self.matrix['pulseT'] - self.matrix['pulseT'][0]) / 1e9

        grid.ax[0][0].scatter(xax, resets_time, 0.8, color='k', marker='+')
        grid.ax[0][0].set_xlabel('trigger no.')
        grid.ax[0][0].set_ylabel('time (s)')

        delta_time = np.concatenate((np.diff(resets_time), [0]))
        grid.ax[0][1].scatter(xax, delta_time, 0.8, color='k', marker='+')
        grid.ax[0][1].set_xlabel('trigger no.')
        grid.ax[0][1].set_ylabel('delta time between resets (s)')


class VMMReadoutsPlotter(BaseReadoutsPlotter):
    """
    Raw ASIC-level diagnostics for readoutsVMMnormal / readoutsVMMclustered.
    Grouping is done directly by the (ring, fen, hybrid) triplets present in
    the data via container.get_ring_fen_hybrid_table(), replacing the legacy
    cassette-ID-to-config lookup.
    """

    def __init__(self, container, axis_set=None, n_channels: int = 64, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.axis_set = axis_set
        self.n_channels = n_channels
        self.xbins = np.linspace(0, n_channels - 1, n_channels)
        self.is_clustered = self._has_field('channel0')

    def hybrid_table(self):
        return [] if self.is_empty else self.container.get_ring_fen_hybrid_table()

    def _select_hybrid(self, ring, fen, hybrid):
        m = self.matrix
        return (m['ring'] == ring) & (m['fen'] == fen) & (m['hybrid'] == hybrid)

    def plot_channels_raw(self, hybrids=None, fig_num=1001):
        """Raw ASIC0/ASIC1 (or channel0/channel1 for clustered) channel occupancy per hybrid."""
        if self.is_empty:
            return
        hybrids = self.hybrid_table() if hybrids is None else hybrids
        grid = PlotGrid(fig_num, 2, len(hybrids))
        grid.fig.suptitle('Readouts - raw channels')

        for k, (ring, fen, hybrid) in enumerate(hybrids):
            sel = self._select_hybrid(ring, fen, hybrid)
            m = self.matrix

            if self.is_clustered:
                ch0, ch1 = m['channel0'][sel], m['channel1'][sel]
            else:
                asic0, asic1 = sel & (m['asic'] == 0), sel & (m['asic'] == 1)
                ch0, ch1 = m['channel'][asic0], m['channel'][asic1]

            h0 = self.hist.hist1d(self.xbins, ch0)
            h1 = self.hist.hist1d(self.xbins, ch1)

            grid.ax[0][k].bar(self.xbins, h0, 0.8, color='b')
            grid.ax[1][k].bar(self.xbins, h1, 0.8, color='r')
            grid.ax[0][k].set_xlabel('ASIC 0 ch no.')
            grid.ax[1][k].set_xlabel('ASIC 1 ch no.')
            grid.ax[0][k].set_title(f'hyb.{hybrid} (r{ring}/f{fen})')
            if k == 0:
                grid.ax[0][k].set_ylabel('counts')
                grid.ax[1][k].set_ylabel('counts')

    def plot_adc_vs_channel(self, hybrids=None, logScale: bool = False, fig_num=1006):
        """ADC vs channel 2D occupancy per hybrid, ASIC0/ASIC1 (or ch0/ch1 for clustered)."""
        if self.is_empty:
            return
        if self.axis_set is None:
            print(f'{WARN}WARNING: plot_adc_vs_channel requires an axis_set (ax_energy) -- skipping.{RESET}')
            return

        hybrids = self.hybrid_table() if hybrids is None else hybrids
        grid = PlotGrid(fig_num, 2, len(hybrids))
        grid.fig.suptitle('ADC vs CH')
        normColors = log_scale_norm(logScale)
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, (ring, fen, hybrid) in enumerate(hybrids):
            sel = self._select_hybrid(ring, fen, hybrid)

            if self.is_clustered:
                h0, _ = self.hist.hist2d(ax_e.centers, m['adc0'][sel], self.xbins, m['channel0'][sel])
                h1, _ = self.hist.hist2d(ax_e.centers, m['adc1'][sel], self.xbins, m['channel1'][sel])
            else:
                asic0, asic1 = sel & (m['asic'] == 0), sel & (m['asic'] == 1)
                h0, _ = self.hist.hist2d(ax_e.centers, m['adc'][asic0], self.xbins, m['channel'][asic0])
                h1, _ = self.hist.hist2d(ax_e.centers, m['adc'][asic1], self.xbins, m['channel'][asic1])

            grid.ax[0][k].imshow(h0, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            grid.ax[1][k].imshow(h1, aspect='auto', norm=normColors, interpolation='none',
                                  extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            grid.ax[0][k].set_xlabel('ADC')
            grid.ax[1][k].set_xlabel('ADC')
            grid.ax[0][k].set_title(f'hyb.{hybrid}')
            if k == 0:
                grid.ax[0][k].set_ylabel('ASIC 0 ch no.')
                grid.ax[1][k].set_ylabel('ASIC 1 ch no.')

    def plot_timestamps(self, hybrids=None, fig_num=1002):
        """Raw ASIC0/ASIC1 trigger timestamps per hybrid."""
        if self.is_empty:
            return
        hybrids = self.hybrid_table() if hybrids is None else hybrids
        grid = PlotGrid(fig_num, 2, len(hybrids))
        grid.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, (ring, fen, hybrid) in enumerate(hybrids):
            sel = self._select_hybrid(ring, fen, hybrid)

            if self.is_clustered:
                ts0 = m['timeStamp'][sel]
                ts1 = ts0
            else:
                asic0, asic1 = sel & (m['asic'] == 0), sel & (m['asic'] == 1)
                ts0, ts1 = m['timeStamp'][asic0], m['timeStamp'][asic1]

            grid.ax[0][k].scatter(np.arange(len(ts0)), ts0, 0.8, color='b', marker='+')
            grid.ax[1][k].scatter(np.arange(len(ts1)), ts1, 0.8, color='r', marker='+')
            grid.ax[0][k].set_xlabel('ASIC 0 trigger no.')
            grid.ax[1][k].set_xlabel('ASIC 1 trigger no.')
            grid.ax[0][k].set_ylabel('time (ns)')
            grid.ax[1][k].set_ylabel('time (ns)')
            grid.ax[0][k].set_title(f'hyb.{hybrid}')
            grid.ax[0][k].grid(axis='both', alpha=0.75)
            grid.ax[1][k].grid(axis='both', alpha=0.75)


# ============================================================================
# Monitor plotter
# ============================================================================

class MonitorPlotter:
    """Beam monitor ToF / PHS / wavelength plots. Standalone (monitor events use a distinct container)."""

    def __init__(self, monitor_events, axis_set, hist_out_of_bounds: bool = True):
        self.events = monitor_events
        self.axis_set = axis_set
        self.hist = Histogrammer(hist_out_of_bounds)

    def plot_tof_and_phs(self, fig_num=999):
        h_tof = self.hist.hist1d(self.axis_set.ax_tof.centers, self.events.ToF / 1e9)
        h_phs = self.hist.hist1d(self.axis_set.ax_energy_mon.centers, self.events.PHW)

        fig, (ax1, ax2) = plt.subplots(num=fig_num, figsize=(9, 6), nrows=1, ncols=2)
        fig.suptitle('MONITOR')

        ax1.step(self.axis_set.ax_tof.centers * 1e3, h_tof, 'k', where='mid', label='MON')
        ax1.set_xlabel('ToF (ms)')
        ax1.set_ylabel('counts')
        ax1.set_title('ToF')

        ax2.step(self.axis_set.ax_energy_mon.centers, h_phs, 'k', where='mid', label='MON')
        ax2.set_xlabel('Pulse Heigth (a.u.)')
        ax2.set_ylabel('counts')
        ax2.set_title('PHS')

    def plot_wavelength(self, fig_num=998):
        h_lambda = self.hist.hist1d(self.axis_set.ax_lambda.centers, self.events.wavelength)

        fig, ax = plt.subplots(num=fig_num, figsize=(6, 6), nrows=1, ncols=1)
        fig.suptitle('MONITOR')
        ax.step(self.axis_set.ax_lambda.centers, h_lambda, 'k', where='mid', label='MON')
        ax.set_xlabel('wavelength (A)')
        ax.set_ylabel('counts')
        ax.set_title('WAVELENGTH')