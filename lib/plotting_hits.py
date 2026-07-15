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
from lib.colors import WARN, RESET
from lib.plotting_base import PlotGrid, BasePlotter, log_scale_norm


# ============================================================================
# Detector-agnostic base
# ============================================================================
class BaseHitsPlotter(BasePlotter):
    """Detector-agnostic hits scaffolding: selection by mapped 'ID' field."""
    PLOT_METHODS = {
        "Raw Channels":          "plot_channels_raw",
        "Timestamps":            "plot_timestamps",
        "Timestamps vs Channel": "plot_timestamps_vs_channel",
    }
    
    def select_unit(self, unit_id):
        return self.matrix['ID'] == unit_id
    
    # placholder stubs - give warning if this function is not implemented (overwritten) in daughter class
    def plot_channels_raw(self, *args, **kwargs): self._skip('plot_channels_raw')
    def plot_timestamps(self, *args, **kwargs): self._skip('plot_timestamps')
    def plot_timestamps_vs_channel(self, *args, **kwargs): self._skip('plot_timestamps_vs_channel')


# ============================================================================
# Shared NORMAL-mode VMM layer -- Multi-Blade + Multi-Grid, operationMode == 'normal'
# ============================================================================

class VMMNormalHitsPlotter(BaseHitsPlotter):
    """
    Shared structural logic for NORMAL-mode VMM-based hits (hitsVMMnormal:
    'index'/'plane' fields, explicit wire-vs-strip split via plane==0/1).
    MB and MG both build on exactly this and nothing else. There is
    deliberately no clustered branching anywhere in this class -- clustered
    lives entirely in MBClusteredHitsPlotter below, which does NOT inherit
    from this class, since hardware-clustered hits share almost nothing
    structurally with normal-mode hits (different fields, no wire/strip
    split needed, no MG equivalent).
    """

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
        self.num_wires = self.config.get('wires')
        self.wbins = np.linspace(0, self.num_wires - 1, self.num_wires)
 
    def _local_wire_index(self, global_index: np.ndarray) -> np.ndarray:
        """Un-offset a global wire coordinate back to this unit's local 0..num_wires-1 range."""
        return np.mod(global_index, self.num_wires)

    def plot_timestamps(self, fig_num=1004):
        """Wire and strip trigger timestamps per unit, overlaid."""
        if self.is_empty:
            return
        
        plotht = PlotGrid(fig_num, 1, len(self.unit_ids))
        plotht.fig.suptitle('Hits - W and S/G time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            base_ts = m['timeStamp'][sel]
            is_wire  = m['plane'][sel] == 0
            is_strip = m['plane'][sel] == 1

            # Replicate legacy multiplication mask strategy
            ts_wire_raw  = base_ts * is_wire
            ts_strip_raw = base_ts * is_strip

            # Mask out zero placeholders to preserve coordinate sequence tracking
            ts_wire  = np.ma.masked_where(ts_wire_raw == 0, ts_wire_raw)
            ts_strip = np.ma.masked_where(ts_strip_raw == 0, ts_strip_raw)

            # Both X-axes now span the exact total length of events in this unit
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

    def plot_timestamps_vs_channel(self, fig_num=1005):
        """Wire and strip channel (after mapping) vs. trigger timestamp, overlaid."""
        if self.is_empty:
            return
        plothtvs = PlotGrid(fig_num, 1, len(self.unit_ids))
        plothtvs.fig.suptitle('Hits - W and S/G VS time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            is_wire  = m['plane'] == 0
            is_strip = m['plane'] == 1

            WireCh  = np.round(self._local_wire_index(m['index'][sel & is_wire]))
            StripCh = np.round(m['index'][sel & is_strip]) + self.num_wires

            ts_wire  = m['timeStamp'][sel & is_wire]
            ts_strip = m['timeStamp'][sel & is_strip]

            if len(ts_wire) > 0:
                plothtvs.ax[0][k].scatter(WireCh, ts_wire, 0.8, color='r', marker='+')
            if len(ts_strip) > 0:
                plothtvs.ax[0][k].scatter(StripCh, ts_strip, 0.8, color='b', marker='+')

            plothtvs.ax[0][k].set_ylabel('time (ns)')
            plothtvs.ax[0][k].set_xlabel('W or S/G channel (after mapping)')
            plothtvs.ax[0][k].set_title(f'ID {uid}')
            plothtvs.ax[0][k].grid(axis='both', alpha=0.75)


# ============================================================================
# Multi-Blade -- normal mode
# ============================================================================

class MBHitsPlotter(VMMNormalHitsPlotter):
    """Mapped-channel occupancy for hitsVMMnormal (Multi-Blade)."""

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)

        self.num_strips = self.config.get('strips')
        self.sbins = np.linspace(0, self.num_strips - 1, self.num_strips)


    def plot_channels_raw(self, fig_num=1003):
        """Mapped wire/strip channel occupancy per unit."""
        if self.is_empty:
            return
        ploth = PlotGrid(fig_num, 2, len(self.unit_ids))
        ploth.fig.suptitle('Hits - mapped channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            is_wire  = m['plane'] == 0
            is_strip = m['plane'] == 1
            wire_idx  = self._local_wire_index(m['index'][sel & is_wire])
            strip_idx = m['index'][sel & is_strip]

            histow = self.hist.hist1d(self.wbins, wire_idx)
            histos = self.hist.hist1d(self.sbins, strip_idx)

            ploth.ax[0][k].bar(self.wbins, histow, 0.8, color='r')
            ploth.ax[1][k].bar(self.sbins, histos, 0.8, color='b')
            ploth.ax[0][k].set_xlabel('hit wire ch no.')
            ploth.ax[1][k].set_xlabel('hit strip ch no.')
            ploth.ax[0][k].set_title(f'ID {uid}')


# ============================================================================
# Multi-Grid -- normal mode only (no clustered hardware track exists for MG)
# ============================================================================

class MGHitsPlotter(VMMNormalHitsPlotter):
    """Mapped-channel occupancy for Multi-Grid hits."""

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)

        self.num_grids = self.config.get('grids')
        self.gbins = np.linspace(0, self.num_grids - 1, self.num_grids)

    def plot_channels_raw(self, fig_num=1003):
        """Mapped wire/grid channel occupancy per unit."""
        if self.is_empty:
            return
       
        ploth = PlotGrid(fig_num, 2, len(self.unit_ids))
        ploth.fig.suptitle('Hits - mapped channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            is_wire = m['plane'] == 0
            is_grid = m['plane'] == 1
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
# Multi-Blade -- hardware-clustered mode (standalone, no shared parent
# beyond BaseHitsPlotter -- see VMMNormalHitsPlotter docstring for why)
# ============================================================================

class MBClusteredHitsPlotter(BaseHitsPlotter):
    """
    Mapped-channel occupancy and timestamps for hitsVMMclustered
    (hardware-clustered VMM3A, operationMode == 'clustered'). MB-only --
    there is no clustered hardware track for MG.

    Deliberately does not inherit VMMNormalHitsPlotter: the container has
    different fields ('index0'/'index1' instead of 'index'/'plane'), there's
    no wire/strip split to perform (the ASIC already merged them), and there
    is no second consumer (MG) to share code with. The one bit of literal
    duplication vs. VMMNormalHitsPlotter is _local_wire_index -- a one-line
    np.mod call -- which is a better trade than reaching for shared
    inheritance/mixins for a single call site.
    """
        
    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
        
        self.num_wires = self.config.get('wires')
        self.wbins = np.linspace(0, self.num_wires - 1, self.num_wires)
        self.num_strips = self.config.get('strips')
        self.sbins = np.linspace(0, self.num_strips - 1, self.num_strips)
        
        
    def _local_wire_index(self, global_index: np.ndarray) -> np.ndarray:
        return np.mod(global_index, self.num_wires)

    def plot_channels_raw(self, fig_num=1003):
        if self.is_empty:
            return
        
        ploth = PlotGrid(fig_num, 2, len(self.unit_ids))
        ploth.fig.suptitle('Hits - mapped channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            wire_idx  = self._local_wire_index(m['index0'][sel])
            strip_idx = m['index1'][sel]

            histow = self.hist.hist1d(self.wbins, wire_idx)
            histos = self.hist.hist1d(self.sbins, strip_idx)

            ploth.ax[0][k].bar(self.wbins, histow, 0.8, color='r')
            ploth.ax[1][k].bar(self.sbins, histos, 0.8, color='b')
            ploth.ax[0][k].set_xlabel('hit wire ch no.')
            ploth.ax[1][k].set_xlabel('hit strip ch no.')
            ploth.ax[0][k].set_title(f'ID {uid}')

    def plot_timestamps(self, fig_num=1004):
        if self.is_empty:
            return
       
        plotht = PlotGrid(fig_num, 1, len(self.unit_ids))
        plotht.fig.suptitle('Hits - W and S time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            ts_wire  = m['timeStamp'][sel]
            # ts_strip = m['timeStamp'][sel]

            xx0 = np.arange(0, len(ts_wire), 1)
            # xx1 = np.arange(0, len(ts_strip), 1)

            if len(ts_wire) > 0:
                plotht.ax[0][k].scatter(xx0, ts_wire, 0.8, color='r', marker='+')
            # if len(ts_strip) > 0:
            #     plotht.ax[0][k].scatter(xx1, ts_strip, 0.8, color='b', marker='+')

            plotht.ax[0][k].set_xlabel('trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'ID {uid}')
            plotht.ax[0][k].grid(axis='both', alpha=0.75)

    def plot_timestamps_vs_channel(self, fig_num=1005):
        if self.is_empty:
            return
       
        plothtvs = PlotGrid(fig_num, 1, len(self.unit_ids))
        plothtvs.fig.suptitle('Hits - W and S VS time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)
            WireCh  = np.round(self._local_wire_index(m['index0'][sel]))
            StripCh = np.round(m['index1'][sel]) + self.num_wires

            ts_wire  = m['timeStamp'][sel]
            ts_strip = m['timeStamp'][sel]

            if len(ts_wire) > 0:
                plothtvs.ax[0][k].scatter(WireCh, ts_wire, 0.8, color='r', marker='+')
            if len(ts_strip) > 0:
                plothtvs.ax[0][k].scatter(StripCh, ts_strip, 0.8, color='b', marker='+')

            plothtvs.ax[0][k].set_ylabel('time (ns)')
            plothtvs.ax[0][k].set_xlabel('W or S channel (after mapping)')
            plothtvs.ax[0][k].set_title(f'ID {uid}')
            plothtvs.ax[0][k].grid(axis='both', alpha=0.75)

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

    # def __init__(self, container, config, axis_set=None, hist_out_of_bounds: bool = True):
    #     super().__init__(container, config, axis_set, hist_out_of_bounds)
    #     self.axis_set = axis_set

    def plot_channels_raw(self,  fig_num=1003):
        """Pulse-height correlation (ampA vs ampB) per tube. Always linear scale (matches legacy: logScale was never actually wired up here)."""
        if self.is_empty:
            return
        
        ax_e = self.axis_set.ax_energy
        plotPHScorr = PlotGrid(fig_num, 1, len(self.unit_ids), fig_size=(20, 20))
        plotPHScorr.fig.suptitle('ADC correlation - A vs B')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_unit(uid)

            PHScorr, _, _ = self.hist.hist2d(ax_e.centers, m['ampA'][sel], ax_e.centers, m['ampB'][sel])

            plotPHScorr.ax[0][k].imshow(PHScorr, aspect='auto', norm=None, interpolation='none',
                                         extent=[ax_e.start, ax_e.stop, ax_e.start, ax_e.stop], origin='lower', cmap='jet')
            plotPHScorr.ax[0][k].set_title(f'ID {uid}')
            plotPHScorr.ax[0][k].set_xlabel('ADC A (a.u.)')
            plotPHScorr.ax[0][k].set_box_aspect(1)
            if k == 0:
                plotPHScorr.ax[0][k].set_ylabel('ADC B (a.u.)')

    def plot_timestamps(self,  fig_num=1004):
        """Not supported for R5560 -- use the raw readouts timestamp plots instead."""
        if self.is_empty:
            return
        print(f'\n\t{WARN}WARNING: Hits time stamp not supported for R5560 -> SKIPPING PLOT (use raw readouts timestamp plots).{RESET}')

    def plot_timestamps_vs_channel(self,  fig_num=1005):
        """Not supported for R5560 -- use the raw readouts timestamp plots instead."""
        if self.is_empty:
            return
        print(f'\n\t{WARN}WARNING: Hits time stamp VS Ch not supported for R5560 -> SKIPPING PLOT (use raw readouts timestamp plots).{RESET}')