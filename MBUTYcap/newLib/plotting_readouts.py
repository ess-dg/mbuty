"""
plotting_readouts.py

Readout-level diagnostic plots for the MBUTY pipeline. Ports the readout
plotting classes scattered across libPlotting.py (Multi-Blade), libPlottingMG.py
(Multi-Grid), and libPlottingR5560.py (R5560 tubes) into a single matrix-backed
hierarchy built on top of plotting_base.BasePlotter, reproducing the legacy
plot logic, labels, titles, and colors exactly.
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
from newLib.plotting_base import PlotGrid, BasePlotter, log_scale_norm


# ============================================================================
# Detector-agnostic base
# ============================================================================

class BaseReadoutsPlotter(BasePlotter):
    """
    Detector-agnostic readout-level diagnostic (chopper reset interval),
    plus the topology bookkeeping shared by every concrete subclass:
    index-by-unit-ID lookup, per-unit-ID topology entry access, and the
    declared-unit-ID listing. VMM-based and non-VMM (R5560) detectors both
    need exactly this and nothing more, so it lives here once instead of
    being duplicated in each branch.
    """

    def __init__(self, container, topology: list, hist_out_of_bounds: bool = True):
        super().__init__(container, hist_out_of_bounds)
        self.topology = topology
        self._topo_by_id = self._index_topology_by_id(topology)

    @staticmethod
    def _index_topology_by_id(topology: list) -> dict:
        """dict: physical unit ID -> its config['topology'] entry."""
        return {entry['ID']: entry for entry in topology}

    def topology_unit_ids(self) -> list:
        """All physical unit IDs declared in config['topology'] (not necessarily present in the data)."""
        return list(self._topo_by_id.keys())

    def _topology_entry(self, unit_id) -> dict:
        return self._topo_by_id[unit_id]

    def plot_chopper_resets(self, fig_num=9999):
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, 2)
        grid.fig.suptitle('Chopper Resets - all channels')

        xax = np.arange(0, len(self.matrix['pulseT']))
        resets_time = (self.matrix['pulseT'] - self.matrix['pulseT'][0]) / 1e9

        grid.ax[0][0].scatter(xax, resets_time, 0.8, color='k', marker='+')
        grid.ax[0][0].set_xlabel('trigger no.')
        grid.ax[0][0].set_ylabel('time (s)')

        delta_time = np.concatenate((np.diff(resets_time), [0]), axis=0)

        grid.ax[0][1].scatter(xax, delta_time, 0.8, color='k', marker='+')
        grid.ax[0][1].set_xlabel('trigger no.')
        grid.ax[0][1].set_ylabel('delta time betweeen resets (s)')


# ============================================================================
# Multi-Blade
# ============================================================================

class MBReadoutsPlotter(BaseReadoutsPlotter):
    """Raw ASIC-level diagnostics for readoutsVMMnormal / readoutsVMMclustered (Multi-Blade)."""

    def __init__(self, container, topology: list, axis_set=None, n_channels: int = 64, hist_out_of_bounds: bool = True):
        super().__init__(container, topology, hist_out_of_bounds)
        self.axis_set = axis_set
        self.n_channels = n_channels
        self.xbins = np.linspace(0, n_channels - 1, n_channels)
        self.is_clustered = self._has_field('channel0')

    def select_hybrid_from_unit_id(self, unit_id):
        """Boolean row mask for the hybrid belonging to this unit (mirrors legacy selectHybridFromCassetteID)."""
        entry = self._topology_entry(unit_id)
        m = self.matrix
        sel1 = m['ring']   == entry['ring']
        sel2 = m['fen']    == entry['fen']
        sel3 = m['hybrid'] == entry['hybrid']
        return sel1 & sel2 & sel3

    def plot_channels_raw(self, unit_ids=None, fig_num=1001):
        """Raw ASIC0/ASIC1 (or channel0/channel1 for clustered) channel occupancy per hybrid."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        ploth = PlotGrid(fig_num, 2, len(unit_ids))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                # readoutsVMMclustered has channel0/channel1, not a bare 'channel' field.
                histo0 = self.hist.hist1d(self.xbins, m['channel0'][sel])
                histo1 = self.hist.hist1d(self.xbins, m['channel1'][sel])
            else:
                asic0 = m['asic'] == 0
                asic1 = m['asic'] == 1
                histo0 = self.hist.hist1d(self.xbins, m['channel'][sel & asic0])
                histo1 = self.hist.hist1d(self.xbins, m['channel'][sel & asic1])

            ploth.ax[0][k].bar(self.xbins, histo0, 0.8, color='b')
            ploth.ax[1][k].bar(self.xbins, histo1, 0.8, color='r')
            ploth.ax[0][k].set_xlabel('ASIC 0 ch no.')
            ploth.ax[1][k].set_xlabel('ASIC 1 ch no.')
            ploth.ax[0][k].set_title(f'hyb.{uid}')
            if k == 0:
                ploth.ax[0][k].set_ylabel('counts')
                ploth.ax[1][k].set_ylabel('counts')

    def plot_timestamps(self, unit_ids=None, fig_num=1002):
        """Raw ASIC0/ASIC1 trigger timestamps per hybrid."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        plotht = PlotGrid(fig_num, 2, len(unit_ids))
        plotht.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                timeStamp0 = m['timeStamp'][sel]
                timeStamp1 = timeStamp0
            else:
                asic0 = m['asic'] == 0
                asic1 = m['asic'] == 1
                timeStamp0 = m['timeStamp'][sel & asic0]
                timeStamp1 = m['timeStamp'][sel & asic1]

            xx0 = np.arange(0, len(timeStamp0), 1)
            xx1 = np.arange(0, len(timeStamp1), 1)

            plotht.ax[0][k].scatter(xx0, timeStamp0, 0.8, color='b', marker='+')
            plotht.ax[1][k].scatter(xx1, timeStamp1, 0.8, color='r', marker='+')
            plotht.ax[0][k].set_xlabel('ASIC 0 trigger no.')
            plotht.ax[1][k].set_xlabel('ASIC 1 trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[1][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'hyb.{uid}')
            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[1][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)
            plotht.ax[1][k].grid(axis='y', alpha=0.75)

    def plot_adc_vs_channel(self, unit_ids=None, logScale: bool = False, fig_num=1006):
        """ADC vs channel 2D occupancy per hybrid, ASIC0/ASIC1 (or ch0/ch1 for clustered)."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        normColors = log_scale_norm(logScale)
        plothtch = PlotGrid(fig_num, 2, len(unit_ids))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                # readoutsVMMclustered has adc0/channel0, not bare 'adc'/'channel' fields.
                histoch0, _ = self.hist.hist2d(ax_e.centers, m['adc0'][sel], self.xbins, m['channel0'][sel])
                histoch1, _ = self.hist.hist2d(ax_e.centers, m['adc1'][sel], self.xbins, m['channel1'][sel])
            else:
                asic0 = m['asic'] == 0
                asic1 = m['asic'] == 1
                histoch0, _ = self.hist.hist2d(ax_e.centers, m['adc'][sel & asic0], self.xbins, m['channel'][sel & asic0])
                histoch1, _ = self.hist.hist2d(ax_e.centers, m['adc'][sel & asic1], self.xbins, m['channel'][sel & asic1])

            plothtch.ax[0][k].imshow(histoch0, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[1][k].imshow(histoch1, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')

            plothtch.ax[0][k].set_xlabel('ADC')
            plothtch.ax[1][k].set_xlabel('ADC')
            plothtch.ax[0][k].set_title(f'hyb.{uid}')

            if k == 0:
                plothtch.ax[0][k].set_ylabel('ASIC 0 ch no.')
                plothtch.ax[1][k].set_ylabel('ASIC 1 ch no.')


# ============================================================================
# Multi-Grid
# ============================================================================

class MGReadoutsPlotter(BaseReadoutsPlotter):
    """
    Raw ASIC-level diagnostics for Multi-Grid readouts. Each unit ID maps
    to a PAIR of hybrids -- 'hybridW' (wire) and 'hybridG' (grid) -- declared
    directly in its topology entry (mirrors legacy config.cassMap.hybridWID /
    hybridSID). Clustered mode is not supported on MG hardware.
    """

    def __init__(self, container, topology: list, axis_set=None, n_channels: int = 64, hist_out_of_bounds: bool = True):
        super().__init__(container, topology, hist_out_of_bounds)
        self.axis_set = axis_set
        self.n_channels = n_channels
        self.xbins = np.linspace(0, n_channels - 1, n_channels)
        self.is_clustered = self._has_field('channel0')

    def select_hybrid_from_unit_id(self, unit_id):
        """(selW, selG) boolean row masks for the wire/grid hybrids belonging to this unit."""
        entry = self._topology_entry(unit_id)
        m = self.matrix
        sel1 = m['ring']   == entry['ring']
        sel2 = m['fen']    == entry['fen']
        sel3 = m['hybrid'] == entry['hybridW']
        sel4 = m['hybrid'] == entry['hybridG']

        selW = sel1 & sel2 & sel3
        selG = sel1 & sel2 & sel4
        return selW, selG

    def plot_channels_raw(self, unit_ids=None, fig_num=1001):
        """Raw WIRE/GRID ASIC0/ASIC1 channel occupancy per unit."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        ploth = PlotGrid(fig_num, 4, len(unit_ids))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            selW, selG = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                print(f'{WARN} --> other modes than normal is not supported for MG{RESET}')
                continue

            asic0 = m['asic'] == 0
            asic1 = m['asic'] == 1
            histo0 = self.hist.hist1d(self.xbins, m['channel'][selW & asic0])
            histo1 = self.hist.hist1d(self.xbins, m['channel'][selW & asic1])
            histo2 = self.hist.hist1d(self.xbins, m['channel'][selG & asic0])
            histo3 = self.hist.hist1d(self.xbins, m['channel'][selG & asic1])

            ploth.ax[0][k].bar(self.xbins, histo0, 0.8, color='r')
            ploth.ax[1][k].bar(self.xbins, histo1, 0.8, color='m')
            ploth.ax[2][k].bar(self.xbins, histo2, 0.8, color='b')
            ploth.ax[3][k].bar(self.xbins, histo3, 0.8, color='c')

            ploth.ax[0][k].set_xlabel('WIRE H ASIC 0 ch no.')
            ploth.ax[1][k].set_xlabel('WIRE H ASIC 1 ch no.')
            ploth.ax[2][k].set_xlabel('GRID H ASIC 0 ch no.')
            ploth.ax[3][k].set_xlabel('GRID H ASIC 1 ch no.')

            ploth.ax[0][k].set_title(f'MG.{uid}')

    def plot_timestamps(self, unit_ids=None, fig_num=1002):
        """Raw WIRE/GRID ASIC0/ASIC1 trigger timestamps per unit."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        plotht = PlotGrid(fig_num, 4, len(unit_ids))
        plotht.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            selW, selG = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                print(f'{WARN} --> other modes than normal is not supported for MG{RESET}')
                continue

            asic0 = m['asic'] == 0
            asic1 = m['asic'] == 1
            timeStamp0 = m['timeStamp'][selW & asic0]
            timeStamp1 = m['timeStamp'][selW & asic1]
            timeStamp2 = m['timeStamp'][selG & asic0]
            timeStamp3 = m['timeStamp'][selG & asic1]

            xx0 = np.arange(0, len(timeStamp0), 1)
            xx1 = np.arange(0, len(timeStamp1), 1)
            xx2 = np.arange(0, len(timeStamp2), 1)
            xx3 = np.arange(0, len(timeStamp3), 1)

            plotht.ax[0][k].scatter(xx0, timeStamp0, 0.8, color='r', marker='+')
            plotht.ax[1][k].scatter(xx1, timeStamp1, 0.8, color='m', marker='+')
            plotht.ax[2][k].scatter(xx2, timeStamp2, 0.8, color='b', marker='+')
            plotht.ax[3][k].scatter(xx3, timeStamp3, 0.8, color='c', marker='+')

            plotht.ax[0][k].set_xlabel('WIRE H ASIC 0 trigger no.')
            plotht.ax[1][k].set_xlabel('WIRE H ASIC 1 trigger no.')
            plotht.ax[2][k].set_xlabel('GRID H ASIC 0 trigger no.')
            plotht.ax[3][k].set_xlabel('GRID H ASIC 1 trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[1][k].set_ylabel('time (ns)')
            plotht.ax[2][k].set_ylabel('time (ns)')
            plotht.ax[3][k].set_ylabel('time (ns)')

            plotht.ax[0][k].set_title(f'MG.{uid}')

            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[1][k].grid(axis='x', alpha=0.75)
            plotht.ax[2][k].grid(axis='x', alpha=0.75)
            plotht.ax[3][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)
            plotht.ax[1][k].grid(axis='y', alpha=0.75)
            plotht.ax[2][k].grid(axis='y', alpha=0.75)
            plotht.ax[3][k].grid(axis='y', alpha=0.75)

    def plot_adc_vs_channel(self, unit_ids=None, logScale: bool = False, fig_num=1006):
        """ADC vs channel 2D occupancy per unit, WIRE/GRID x ASIC0/ASIC1."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        normColors = log_scale_norm(logScale)
        plothtch = PlotGrid(fig_num, 4, len(unit_ids))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            selW, selG = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                print(f'{WARN} --> other modes than normal is not supported for MG{RESET}')
                continue

            asic0 = m['asic'] == 0
            asic1 = m['asic'] == 1
            histoch0, _ = self.hist.hist2d(ax_e.centers, m['adc'][selW & asic0], self.xbins, m['channel'][selW & asic0])
            histoch1, _ = self.hist.hist2d(ax_e.centers, m['adc'][selW & asic1], self.xbins, m['channel'][selW & asic1])
            histoch2, _ = self.hist.hist2d(ax_e.centers, m['adc'][selG & asic0], self.xbins, m['channel'][selG & asic0])
            histoch3, _ = self.hist.hist2d(ax_e.centers, m['adc'][selG & asic1], self.xbins, m['channel'][selG & asic1])

            plothtch.ax[0][k].imshow(histoch0, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[1][k].imshow(histoch1, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[2][k].imshow(histoch2, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[3][k].imshow(histoch3, aspect='auto', norm=normColors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')

            plothtch.ax[0][k].set_xlabel('ADC')
            plothtch.ax[1][k].set_xlabel('ADC')
            plothtch.ax[2][k].set_xlabel('ADC')
            plothtch.ax[3][k].set_xlabel('ADC')

            plothtch.ax[0][k].set_title(f'hyb.s of ID{uid}')

            if k == 0:
                plothtch.ax[0][k].set_ylabel('hyb 0 ASIC 0 ch no.')
                plothtch.ax[1][k].set_ylabel('hyb 0 ASIC 1 ch no.')
                plothtch.ax[2][k].set_ylabel('hyb 1 ASIC 0 ch no.')
                plothtch.ax[3][k].set_ylabel('hyb 1 ASIC 1 ch no.')


# ============================================================================
# R5560 tubes
# ============================================================================

class R5560ReadoutsPlotter(BaseReadoutsPlotter):
    """
    Raw tube-level diagnostics for R5560 readouts. R5560 tubes carry no VMM
    ASIC structure at all, so this inherits BaseReadoutsPlotter directly and
    looks up each unit ID's (ring, fen, tube) triple from topology (via the
    shared BaseReadoutsPlotter bookkeeping), mirroring legacy's
    config.get_cassID2RingFenHybrid() pattern.
    """

    def select_tube_from_unit_id(self, unit_id):
        """Boolean row mask for the tube belonging to this unit ID."""
        entry = self._topology_entry(unit_id)
        m = self.matrix
        sel1 = m['ring'] == entry['ring']
        sel2 = m['fen']  == entry['fen']
        sel3 = m['tube'] == entry['tube']
        return sel1 & sel2 & sel3

    def plot_channels_raw(self, unit_ids=None, fig_num=1001):
        """Bar chart of raw entry counts per tube, across every unit ID present in topology."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        ploth = PlotGrid(fig_num, 1, 1)
        ploth.fig.suptitle('Readouts - present tubes')

        size = len(unit_ids)
        xbins  = np.zeros(size, dtype='int64')
        histo0 = np.zeros(size, dtype='int64')

        for k, uid in enumerate(unit_ids):
            sel = self.select_tube_from_unit_id(uid)
            xbins[k]  = uid
            histo0[k] = int(np.sum(sel))

        ploth.ax[0][0].bar(xbins, histo0, 0.8, color='r')
        ploth.ax[0][0].set_xlabel('Tubes')
        ploth.ax[0][0].set_ylabel('num of entries')
        ploth.ax[0][0].set_xticks(xbins)

    def plot_timestamps(self, unit_ids=None, fig_num=1002):
        """Raw trigger timestamps per tube."""
        if self.is_empty:
            return
        unit_ids = self.topology_unit_ids() if unit_ids is None else unit_ids
        plotht = PlotGrid(fig_num, 1, len(unit_ids))
        plotht.fig.suptitle('Readouts - raw tubes time stamps')
        m = self.matrix

        for k, uid in enumerate(unit_ids):
            sel = self.select_tube_from_unit_id(uid)
            timeStamp0 = m['timeStamp'][sel]
            xx0 = np.arange(0, len(timeStamp0), 1)

            plotht.ax[0][k].scatter(xx0, timeStamp0, 0.8, color='r', marker='+')
            plotht.ax[0][k].set_xlabel('trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'Tube ID.{uid}')
            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)

    def plot_adc_vs_channel(self, unit_ids=None, logScale: bool = False, fig_num=None):
        """ADC vs channel is not supported for R5560 -- use raw hits for ADC vs ADC instead."""
        print(f'\n\t{WARN}WARNING: ADC vs Ch not supported for R5560 -> SKIPPING PLOT (use raw hits for ADC VS ADC).{RESET}')