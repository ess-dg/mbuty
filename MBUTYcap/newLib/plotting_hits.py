"""
plotting_hits.py

Hit-level (post-mapping) diagnostic plots for the MBUTY pipeline. Ports the
hits plotting classes scattered across libPlotting.py (Multi-Blade),
libPlottingMG.py (Multi-Grid), and libPlottingR5560.py (R5560 tubes) into a
matrix-backed hierarchy built on top of plotting_base.BasePlotter,
reproducing the legacy plot logic, labels, titles, and colors exactly.
"""

import numpy as np
import sys, os
# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)
from newLib.colors import WARN, RESET
from newLib.plotting_base import PlotGrid, BasePlotter, log_scale_norm, toggled_by


# ============================================================================
# Detector-agnostic base
# ============================================================================

class BaseHitsPlotter(BasePlotter):
    """Detector-agnostic hits scaffolding: selection by mapped 'ID' field."""

    def select_unit(self, unit_id):
        """Boolean row mask for rows belonging to this mapped unit ID."""
        return self.matrix['ID'] == unit_id


# ============================================================================
# Shared VMM (ASIC-based) layer -- Multi-Blade + Multi-Grid
# ============================================================================

class VMMHitsPlotter(BaseHitsPlotter):
    """
    Shared structural logic and shared plots for VMM-based hits (Multi-Blade,
    Multi-Grid): clustered-mode detection, the wire global-to-local
    coordinate helper, and the timestamp plots, which are identical for both
    detector types (hitsVMMnormal is the same container class for both, and
    legacy pointer-wrapped these two methods into MG verbatim from MB).
    """

    def __init__(self, container, num_wires: int, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.num_wires = num_wires
        self.is_clustered = self._has_field('index0')

    def _local_wire_index(self, global_index: np.ndarray) -> np.ndarray:
        """Un-offset a global wire coordinate back to this unit's local 0..num_wires-1 range."""
        return np.mod(global_index, self.num_wires)

    @toggled_by("plotting.plotHitsTimeStamps")
    def plot_timestamps(self, unit_ids=None, fig_num=1004):
        """Wire and strip trigger timestamps per unit, overlaid."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        plotht = PlotGrid(fig_num, 1, len(unit_ids))
        plotht.fig.suptitle('Hits - W and S time stamps')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_unit(uid)

            if self.is_clustered:
                # Clustered modes have symmetric timelines
                ts_wire = m['timeStamp'][sel]
                ts_strip = m['timeStamp'][sel]
            else:
                is_wire  = m['plane'] == 0
                is_strip = m['plane'] == 1
                
                ts_wire  = m['timeStamp'][sel & is_wire]
                ts_strip = m['timeStamp'][sel & is_strip]

            xx0 = np.arange(0, len(ts_wire), 1)
            xx1 = np.arange(0, len(ts_strip), 1)

            if len(ts_wire) > 0:
                plotht.ax[0][k].scatter(xx0, ts_wire, 0.8, color='r', marker='+')
            if len(ts_strip) > 0:
                plotht.ax[0][k].scatter(xx1, ts_strip, 0.8, color='b', marker='+')
                
            plotht.ax[0][k].set_xlabel('trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'ID {uid}')
            plotht.ax[0][k].grid(axis='both', alpha=0.75)

    @toggled_by("plotting.plotHitsTimeStampsVSChannels")
    def plot_timestamps_vs_channel(self, unit_ids=None, fig_num=1005):
        """Wire and strip channel (after mapping) vs. trigger timestamp, overlaid."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        plothtvs = PlotGrid(fig_num, 1, len(unit_ids))
        plothtvs.fig.suptitle('Hits - W and S VS time stamps')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_unit(uid)

            if self.is_clustered:
                wire_local = self._local_wire_index(m['index0'][sel])
                WireCh = np.round(wire_local)
                StripCh = np.round(m['index1'][sel])
                ts_wire = m['timeStamp'][sel]
                ts_strip = m['timeStamp'][sel]
            else:
                is_wire  = m['plane'] == 0
                is_strip = m['plane'] == 1
                wire_local_full = self._local_wire_index(m['index'][sel & is_wire])
                WireCh = np.round(wire_local_full)
                StripCh = np.round(m['index'][sel & is_strip])
                
                ts_wire = m['timeStamp'][sel & is_wire]
                ts_strip = m['timeStamp'][sel & is_strip]

            # Re-apply the legacy visual padding shift (+10 wires, +20 strips) safely on filtered arrays
            WireCh_padded = WireCh + 10
            StripCh_padded = StripCh + 20

            # Shift back to correct spatial positions for overlaid mapping
            WireCh_final = WireCh_padded - 10
            StripCh_final = StripCh_padded - 20 + self.num_wires

            if len(ts_wire) > 0:
                plothtvs.ax[0][k].scatter(WireCh_final, ts_wire, 0.8, color='r', marker='+')
            if len(ts_strip) > 0:
                plothtvs.ax[0][k].scatter(StripCh_final, ts_strip, 0.8, color='b', marker='+')
                
            plothtvs.ax[0][k].set_ylabel('time (ns)')
            plothtvs.ax[0][k].set_xlabel('W or S channel (after mapping)')
            plothtvs.ax[0][k].set_title(f'ID {uid}')
            plothtvs.ax[0][k].grid(axis='both', alpha=0.75)


# ============================================================================
# Multi-Blade
# ============================================================================

class MBHitsPlotter(VMMHitsPlotter):
    """Mapped-channel occupancy for hitsVMMnormal / hitsVMMclustered (Multi-Blade)."""

    def __init__(self, container, num_wires: int, n_channels: int = 64, hist_out_of_bounds: bool = True):
        super().__init__(container, num_wires, hist_out_of_bounds)
        self.xbins = np.linspace(0, n_channels - 1, n_channels)

    @toggled_by("plotting.plotRawHits")
    def plot_channels_raw(self, unit_ids=None, fig_num=1003):
        """Mapped wire/strip channel occupancy per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        ploth = PlotGrid(fig_num, 2, len(unit_ids))
        ploth.fig.suptitle('Hits - mapped channels')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_unit(uid)

            if self.is_clustered:
                wire_idx  = self._local_wire_index(m['index0'][sel])
                strip_idx = m['index1'][sel]
            else:
                is_wire  = m['plane'] == 0
                is_strip = m['plane'] == 1
                wire_idx  = self._local_wire_index(m['index'][sel & is_wire])
                strip_idx = m['index'][sel & is_strip]

            histow = self.hist.hist1d(self.xbins, wire_idx)
            histos = self.hist.hist1d(self.xbins, strip_idx)

            ploth.ax[0][k].bar(self.xbins, histow, 0.8, color='r')
            ploth.ax[1][k].bar(self.xbins, histos, 0.8, color='b')
            ploth.ax[0][k].set_xlabel('hit wire ch no.')
            ploth.ax[1][k].set_xlabel('hit strip ch no.')
            ploth.ax[0][k].set_title(f'ID {uid}')


# ============================================================================
# Multi-Grid
# ============================================================================

class MGHitsPlotter(VMMHitsPlotter):
    """
    Mapped-channel occupancy for Multi-Grid hits. plot_timestamps and
    plot_timestamps_vs_channel now come straight from VMMHitsPlotter (they
    were never MB-specific to begin with -- legacy just happened to define
    them once, under MB, and pointer-wrap MG onto them). Only
    plot_channels_raw is defined here, since MG needs separate wire/grid bin
    counts instead of MB's single combined 64-bin axis. Clustered mode is
    not supported on MG hardware.
    """

    def __init__(self, container, num_wires: int, num_grids: int, hist_out_of_bounds: bool = True):
        super().__init__(container, num_wires, hist_out_of_bounds)
        self.num_grids = num_grids
        self.wbins = np.linspace(0, num_wires - 1, num_wires)
        self.gbins = np.linspace(0, num_grids - 1, num_grids)

    @toggled_by("plotting.plotRawHits")
    def plot_channels_raw(self, unit_ids=None, fig_num=1003):
        """Mapped wire/grid channel occupancy per unit."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        ploth = PlotGrid(fig_num, 2, len(unit_ids))
        ploth.fig.suptitle('Hits - mapped channels')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_unit(uid)

            if self.is_clustered:
                print(f'{WARN} --> other modes than normal is not supported for MG{RESET}')
                continue

            is_wire  = m['plane'] == 0
            is_grid  = m['plane'] == 1
            wire_idx = self._local_wire_index(m['index'][sel & is_wire])
            grid_idx = m['index'][sel & is_grid]

            histow = self.hist.hist1d(self.wbins, wire_idx)
            histos = self.hist.hist1d(self.gbins, grid_idx)

            ploth.ax[0][k].bar(self.wbins, histow, 0.8, color='r')
            ploth.ax[1][k].bar(self.gbins, histos, 0.8, color='b')
            ploth.ax[0][k].set_xlabel('hit wire ch no.')
            ploth.ax[1][k].set_xlabel('hit grid ch no.')
            ploth.ax[0][k].set_title(f'ID {uid}')


# ============================================================================
# R5560 tubes
# ============================================================================

class R5560HitsPlotter(BaseHitsPlotter):
    """
    Mapped-hit diagnostics for R5560 tubes. No channel/plane structure --
    'ID' is already the tube number, nothing further to resolve. Unlike
    MB/MG, plot_channels_raw here is a PHS correlation plot (ampA vs ampB),
    not a channel-occupancy plot -- kept under that name for API consistency
    even though the content is different, matching legacy's own naming.
    """

    def __init__(self, container, axis_set=None, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.axis_set = axis_set

    @toggled_by("plotting.plotRawHits")
    def plot_channels_raw(self, unit_ids=None, fig_num=1003):
        """Pulse-height correlation (ampA vs ampB) per tube. Always linear scale (matches legacy: logScale was never actually wired up here)."""
        if self.is_empty:
            return
        unit_ids = self.unit_ids() if unit_ids is None else unit_ids
        ax_e = self.axis_set.ax_energy
        plotPHScorr = PlotGrid(fig_num, 1, len(unit_ids), fig_size=(20, 20))
        plotPHScorr.fig.suptitle('Pulse Heigth Spectrum - Correlation A-B')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_unit(uid)

            PHScorr, _ = self.hist.hist2d(ax_e.centers, m['ampA'][sel], ax_e.centers, m['ampB'][sel])

            plotPHScorr.ax[0][k].imshow(PHScorr, aspect='auto', norm=None, interpolation='none',
                                         extent=[ax_e.start, ax_e.stop, ax_e.start, ax_e.stop], origin='lower', cmap='jet')
            plotPHScorr.ax[0][k].set_title(f'ID {uid}')
            plotPHScorr.ax[0][k].set_xlabel('pulse height A (a.u.)')
            plotPHScorr.ax[0][k].set_box_aspect(1)
            if k == 0:
                plotPHScorr.ax[0][k].set_ylabel('pulse height B (a.u.)')

    @toggled_by("plotting.plotHitsTimeStamps")
    def plot_timestamps(self, unit_ids=None, fig_num=1004):
        """Not supported for R5560 -- use the raw readouts timestamp plots instead."""
        if self.is_empty:
            return
        print(f'\n\t{WARN}WARNING: Hits time stamp not supported for R5560 -> SKIPPING PLOT (use raw readouts timestamp plots).{RESET}')

    @toggled_by("plotting.plotHitsTimeStampsVSChannels")
    def plot_timestamps_vs_channel(self, unit_ids=None, fig_num=1005):
        """Not supported for R5560 -- use the raw readouts timestamp plots instead."""
        if self.is_empty:
            return
        print(f'\n\t{WARN}WARNING: Hits time stamp VS Ch not supported for R5560 -> SKIPPING PLOT (use raw readouts timestamp plots).{RESET}')