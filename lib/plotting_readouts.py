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
from lib.colors import WARN, RESET
from lib.plotting_base import PlotGrid, BasePlotter, log_scale_norm, fg_color


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
    PLOT_METHODS = {
        "Raw Channels":   "plot_channels_raw",
        "Timestamps":     "plot_timestamps",
        "ADC vs Channel": "plot_adc_vs_channel",
        "Chopper Resets": "plot_chopper_resets",
    }
    
    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)

        topology         = config.get('topology', [])
        self._topo_by_id = self._index_topology_by_id(topology)

    @staticmethod
    def _index_topology_by_id(topology: list) -> dict:
        """dict: physical unit ID -> its config['topology'] entry."""
        return {entry['ID']: entry for entry in topology}

    def _topology_entry(self, unit_id) -> dict:
        return self._topo_by_id[unit_id]

    def plot_chopper_resets(self, fig_num=9999):
        if self.is_empty:
            return
        grid = PlotGrid(fig_num, 1, 2)
        grid.fig.suptitle('Chopper Resets - all channels')

        xax = np.arange(0, len(self.matrix['pulseT']))
        resets_time = (self.matrix['pulseT'] - self.matrix['pulseT'][0]) / 1e9

        grid.ax[0][0].scatter(xax, resets_time, 0.8, color=fg_color(), marker='+')
        grid.ax[0][0].set_xlabel('trigger no.')
        grid.ax[0][0].set_ylabel('time (s)')

        delta_time = np.concatenate((np.diff(resets_time), [0]), axis=0)

        grid.ax[0][1].scatter(xax, delta_time, 0.8, color=fg_color(), marker='+')
        grid.ax[0][1].set_xlabel('trigger no.')
        grid.ax[0][1].set_ylabel('delta time betweeen resets (s)')
        
    # placholder stubs - give warning if this function is not implemented (overwritten) in daughter class        
    def plot_channels_raw(self, *args, **kwargs): self._skip('plot_channels_raw')
    def plot_timestamps(self, *args, **kwargs): self._skip('plot_timestamps')
    def plot_adc_vs_channel(self, *args, **kwargs): self._skip('plot_adc_vs_channel')


# ============================================================================
# Multi-Blade
# ============================================================================

class MBReadoutsPlotter(BaseReadoutsPlotter):
    """Raw ASIC-level diagnostics for readoutsVMMnormal / readoutsVMMclustered (Multi-Blade)."""

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
   
        # number of channels in one VMM asic 
        self.n_channels = 64
        
        self.xbins = np.linspace(0, self.n_channels - 1, self.n_channels)
        self.is_clustered = self._has_field('channel0')

    def select_hybrid_from_unit_id(self, unit_id):
        """Boolean row mask for the hybrid belonging to this unit (mirrors legacy selectHybridFromCassetteID)."""
        entry = self._topology_entry(unit_id)
        m = self.matrix
        sel1 = m['ring']   == entry['ring']
        sel2 = m['fen']    == entry['fen']
        sel3 = m['hybrid'] == entry['hybrid']
        return sel1 & sel2 & sel3

    def plot_channels_raw(self, fig_num=1001):
        """Raw ASIC0/ASIC1 (or channel0/channel1 for clustered) channel occupancy per hybrid."""
        if self.is_empty:
            return

        ploth = PlotGrid(fig_num, 2, len(self.unit_ids))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
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

    def plot_timestamps(self,fig_num=1002):
        """Raw ASIC0/ASIC1 trigger timestamps per hybrid."""
        if self.is_empty:
            return
        
        plotht = PlotGrid(fig_num, 2, len(self.unit_ids))
        plotht.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
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

    def plot_adc_vs_channel(self, fig_num=1006):
        """ADC vs channel 2D occupancy per hybrid, ASIC0/ASIC1 (or ch0/ch1 for clustered)."""
        if self.is_empty:
            return
        
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)
 
        plothtch = PlotGrid(fig_num, 2, len(self.unit_ids))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                # readoutsVMMclustered has adc0/channel0, not bare 'adc'/'channel' fields.
                histoch0, _, _ = self.hist.hist2d(ax_e.centers, m['adc0'][sel], self.xbins, m['channel0'][sel])
                histoch1, _, _ = self.hist.hist2d(ax_e.centers, m['adc1'][sel], self.xbins, m['channel1'][sel])
            else:
                asic0 = m['asic'] == 0
                asic1 = m['asic'] == 1
                histoch0, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][sel & asic0], self.xbins, m['channel'][sel & asic0])
                histoch1, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][sel & asic1], self.xbins, m['channel'][sel & asic1])

            plothtch.ax[0][k].imshow(histoch0, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[1][k].imshow(histoch1, aspect='auto', norm=norm_colors, interpolation='none',
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

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)
   
        # number of channels in one VMM asic 
        self.n_channels = 64
        
        self.xbins = np.linspace(0, self.n_channels - 1, self.n_channels)
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

    def plot_channels_raw(self, fig_num=1001):
        """Raw WIRE/GRID ASIC0/ASIC1 channel occupancy per unit."""
        if self.is_empty:
            return
      
        ploth = PlotGrid(fig_num, 4, len(self.unit_ids))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
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

    def plot_timestamps(self, fig_num=1002):
        """Raw WIRE/GRID ASIC0/ASIC1 trigger timestamps per unit."""
        if self.is_empty:
            return
        plotht = PlotGrid(fig_num, 4, len(self.unit_ids))
        plotht.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
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

    def plot_adc_vs_channel(self, fig_num=1006):
        """ADC vs channel 2D occupancy per unit, WIRE/GRID x ASIC0/ASIC1."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)
        
        plothtch = PlotGrid(fig_num, 4, len(self.unit_ids))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            selW, selG = self.select_hybrid_from_unit_id(uid)

            if self.is_clustered:
                print(f'{WARN} --> other modes than normal is not supported for MG{RESET}')
                continue

            asic0 = m['asic'] == 0
            asic1 = m['asic'] == 1
            histoch0, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selW & asic0], self.xbins, m['channel'][selW & asic0])
            histoch1, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selW & asic1], self.xbins, m['channel'][selW & asic1])
            histoch2, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selG & asic0], self.xbins, m['channel'][selG & asic0])
            histoch3, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selG & asic1], self.xbins, m['channel'][selG & asic1])

            plothtch.ax[0][k].imshow(histoch0, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[1][k].imshow(histoch1, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[2][k].imshow(histoch2, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[3][k].imshow(histoch3, aspect='auto', norm=norm_colors, interpolation='none',
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

    def plot_channels_raw(self, fig_num=1001):
        """Bar chart of raw entry counts per tube, across every unit ID present in topology."""
        if self.is_empty:
            return
        
        ploth = PlotGrid(fig_num, 1, 1)
        ploth.fig.suptitle('Readouts - present tubes')

        size = len(self.unit_ids)
        xbins  = np.zeros(size, dtype='int64')
        histo0 = np.zeros(size, dtype='int64')

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_tube_from_unit_id(uid)
            xbins[k]  = uid
            histo0[k] = int(np.sum(sel))

        ploth.ax[0][0].bar(xbins, histo0, 0.8, color='r')
        ploth.ax[0][0].set_xlabel('Tubes')
        ploth.ax[0][0].set_ylabel('num of entries')
        ploth.ax[0][0].set_xticks(xbins)

    def plot_timestamps(self, fig_num=1002):
        """Raw trigger timestamps per tube."""
        if self.is_empty:
            return
        plotht = PlotGrid(fig_num, 1, len(self.unit_ids))
        plotht.fig.suptitle('Readouts - raw tubes time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_tube_from_unit_id(uid)
            timeStamp0 = m['timeStamp'][sel]
            xx0 = np.arange(0, len(timeStamp0), 1)

            plotht.ax[0][k].scatter(xx0, timeStamp0, 0.8, color='r', marker='+')
            plotht.ax[0][k].set_xlabel('trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'Tube ID.{uid}')
            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)

    def plot_adc_vs_channel(self, fig_num=None):
        """ADC vs channel is not supported for R5560 -- use raw hits for ADC vs ADC instead."""
        print(f'\n\t{WARN}WARNING: ADC vs Ch not supported for R5560 -> SKIPPING PLOT (use raw hits for ADC VS ADC).{RESET}')
        
        
# ============================================================================
# SKADI
# ============================================================================

class SKADIReadoutsPlotter(BaseReadoutsPlotter):
    """
    Raw pixel-channel diagnostics for SKADI readouts. Like R5560, SKADI has
    no VMM ASIC/plane structure to split subplots by -- one readout stream
    per tile ID -- so this mirrors R5560ReadoutsPlotter's shape (1 row of
    subplots, one column per unit_id) rather than MB/MG's 2-or-4-row ASIC
    split. Topology match is IP-only (mirrors the mapping stage), not
    ring/fen/hybrid or ring/fen/tube.
    """

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)

        # each tile is a pix x pix pixel grid -> pix**2 raw channels
        pix = int(config['pix'])
        self.n_channels = pix * pix
        self.xbins = np.linspace(0, self.n_channels - 1, self.n_channels)

    def select_tile_from_unit_id(self, unit_id):
        """Boolean row mask for the tile belonging to this unit ID (IP match)."""
        entry = self._topology_entry(unit_id)
        return self.matrix['IP'] == entry['IP']

    def plot_channels_raw(self, fig_num=1001):
        """Raw pixel-channel occupancy per tile: 1D histogram, one per unit ID."""
        if self.is_empty:
            return

        ploth = PlotGrid(fig_num, 1, len(self.unit_ids))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_tile_from_unit_id(uid)
            histo = self.hist.hist1d(self.xbins, m['channel'][sel])

            ploth.ax[0][k].bar(self.xbins, histo, 0.8, color='b')
            ploth.ax[0][k].set_xlabel('ch no.')
            ploth.ax[0][k].set_title(f'tile.{uid}')
            if k == 0:
                ploth.ax[0][k].set_ylabel('counts')

    def plot_timestamps(self, fig_num=1002):
        """Raw trigger timestamps per tile."""
        if self.is_empty:
            return
        plotht = PlotGrid(fig_num, 1, len(self.unit_ids))
        plotht.fig.suptitle('Readouts - raw tiles time stamps')
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_tile_from_unit_id(uid)
            timeStamp0 = m['timeStamp'][sel]
            xx0 = np.arange(0, len(timeStamp0), 1)

            plotht.ax[0][k].scatter(xx0, timeStamp0, 0.8, color='r', marker='+')
            plotht.ax[0][k].set_xlabel('trigger no.')
            plotht.ax[0][k].set_ylabel('time (ns)')
            plotht.ax[0][k].set_title(f'Tile ID.{uid}')
            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)

    def plot_adc_vs_channel(self, fig_num=1006):
        """ADC vs channel 2D occupancy per tile: 1 histogram, one per unit ID."""
        if self.is_empty:
            return
        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        plothtch = PlotGrid(fig_num, 1, len(self.unit_ids))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, uid in enumerate(self.unit_ids):
            sel = self.select_tile_from_unit_id(uid)
            histoch, _, _ = self.hist.hist2d(
                ax_e.centers, m['adc'][sel], self.xbins, m['channel'][sel]
            )

            plothtch.ax[0][k].imshow(
                histoch, aspect='auto', norm=norm_colors, interpolation='none',
                extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]],
                origin='lower', cmap='jet',
            )
            plothtch.ax[0][k].set_xlabel('ADC')
            plothtch.ax[0][k].set_title(f'tile.{uid}')

            if k == 0:
                plothtch.ax[0][k].set_ylabel('ch no.')
                
# ============================================================================
# NMX
# ============================================================================

class NMXReadoutsPlotter(BaseReadoutsPlotter):
    """
    Raw ASIC-level diagnostics for NMX readouts. Each unit ID ("panel") is a
    quadrant spanning two edges -- X and Y -- declared directly in its
    topology entry as ('fenX', 'hybridsX') / ('fenY', 'hybridsY'), each a
    list of 5 hybrid IDs (mirrors legacy config.cassMap panel/edge mapping).
    'hybrid' values are only unique *within* a fen, so selecting a plane
    requires matching fen + hybrid together, not hybrid alone (unlike MG's
    single hybridW/hybridG IDs).

    Every raw diagnostic here flattens (unit_id, hybrid_slot, asic) into one
    ordered column axis (built once in _build_columns so every plot method
    iterates identically): row 0 is the X edge, row 1 is the Y edge, and
    column k on both rows refers to the same hybrid slot within the same
    panel -- i.e. the two orthogonal coordinate readouts for one physical
    ASIC pair. With 12 unit IDs x 5 hybrids x 2 asics this is a wide
    (2 x 120) grid; that width is intentional per-column ASIC resolution,
    not an oversight -- tune fig_size at the call site if needed.
    """

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        super().__init__(container, parameters, config, axis_set, unit_ids)

        # number of channels in one VMM asic
        self.n_channels = 64
        self.xbins = np.linspace(0, self.n_channels - 1, self.n_channels)

        # Flattened (unit_id, hybrid_slot, asic) column list, built once so
        # every plot method (channels/timestamps/adc-vs-channel) walks the
        # exact same columns in the exact same order.
        self._columns = self._build_columns()

    def _build_columns(self):
        """
        One entry per physical ASIC column: (unit_id, hybrid_slot, asic).
        hybrid_slot is the *position* within hybridsX/hybridsY (0..4), not
        the raw hybrid ID -- row 0 (X) reads hybridsX[slot], row 1 (Y) reads
        hybridsY[slot] for that same slot, so a column always pairs the same
        physical hybrid position across both edges.
        """
        columns = []
        for uid in self.unit_ids:
            entry = self._topology_entry(uid)
            n_slots = len(entry['hybridsX'])
            for slot in range(n_slots):
                for asic in (0, 1):
                    columns.append((uid, slot, asic))
        return columns

    def select_asic_from_column(self, unit_id, slot, asic, plane):
        """Boolean row mask for one (unit_id, hybrid slot, asic) column on one plane ('X' or 'Y')."""
        entry = self._topology_entry(unit_id)
        m = self.matrix
        if plane == 'X':
            fen, hybrid_id = entry['fenX'], entry['hybridsX'][slot]
        else:
            fen, hybrid_id = entry['fenY'], entry['hybridsY'][slot]
        sel_ring   = m['ring']   == entry['ring']
        sel_fen    = m['fen']    == fen
        sel_hybrid = m['hybrid'] == hybrid_id
        sel_asic   = m['asic']   == asic
        return sel_ring & sel_fen & sel_hybrid & sel_asic

    def _column_label(self, unit_id, slot, asic, plane):
        entry = self._topology_entry(unit_id)
        hybrid_id = entry['hybridsX'][slot] if plane == 'X' else entry['hybridsY'][slot]
        return f'{unit_id}.{hybrid_id}.{asic}'

    def plot_channels_raw(self, fig_num=1001):
        """Raw channel occupancy per (unit_id, hybrid, asic) column; row 0 = X edge, row 1 = Y edge."""
        if self.is_empty:
            return

        ploth = PlotGrid(fig_num, 2, len(self._columns))
        ploth.fig.suptitle('Readouts - raw channels')
        m = self.matrix

        for k, (uid, slot, asic) in enumerate(self._columns):
            selX = self.select_asic_from_column(uid, slot, asic, 'X')
            selY = self.select_asic_from_column(uid, slot, asic, 'Y')

            histoX = self.hist.hist1d(self.xbins, m['channel'][selX])
            histoY = self.hist.hist1d(self.xbins, m['channel'][selY])

            ploth.ax[0][k].bar(self.xbins, histoX, 0.8, color='b')
            ploth.ax[1][k].bar(self.xbins, histoY, 0.8, color='r')

            ploth.ax[0][k].set_title(self._column_label(uid, slot, asic, 'X'), fontsize=6, rotation=90)
            ploth.ax[1][k].set_xlabel(self._column_label(uid, slot, asic, 'Y'), fontsize=6, rotation=90)

            if k == 0:
                ploth.ax[0][k].set_ylabel('X: counts')
                ploth.ax[1][k].set_ylabel('Y: counts')

    def plot_timestamps(self, fig_num=1002):
        """Raw trigger timestamps per (unit_id, hybrid, asic) column; row 0 = X edge, row 1 = Y edge."""
        if self.is_empty:
            return

        plotht = PlotGrid(fig_num, 2, len(self._columns))
        plotht.fig.suptitle('Readouts - raw channels time stamps')
        m = self.matrix

        for k, (uid, slot, asic) in enumerate(self._columns):
            selX = self.select_asic_from_column(uid, slot, asic, 'X')
            selY = self.select_asic_from_column(uid, slot, asic, 'Y')

            timeStampX = m['timeStamp'][selX]
            timeStampY = m['timeStamp'][selY]
            xxX = np.arange(0, len(timeStampX), 1)
            xxY = np.arange(0, len(timeStampY), 1)

            plotht.ax[0][k].scatter(xxX, timeStampX, 0.8, color='b', marker='+')
            plotht.ax[1][k].scatter(xxY, timeStampY, 0.8, color='r', marker='+')

            plotht.ax[0][k].set_title(self._column_label(uid, slot, asic, 'X'), fontsize=6, rotation=90)
            plotht.ax[1][k].set_xlabel(self._column_label(uid, slot, asic, 'Y'), fontsize=6, rotation=90)
            plotht.ax[0][k].grid(axis='x', alpha=0.75)
            plotht.ax[1][k].grid(axis='x', alpha=0.75)
            plotht.ax[0][k].grid(axis='y', alpha=0.75)
            plotht.ax[1][k].grid(axis='y', alpha=0.75)

            if k == 0:
                plotht.ax[0][k].set_ylabel('time (ns)')
                plotht.ax[1][k].set_ylabel('time (ns)')

    def plot_adc_vs_channel(self, fig_num=1006):
        """ADC vs channel 2D occupancy per (unit_id, hybrid, asic) column; row 0 = X edge, row 1 = Y edge."""
        if self.is_empty:
            return

        norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

        plothtch = PlotGrid(fig_num, 2, len(self._columns))
        plothtch.fig.suptitle('ADC vs CH')
        ax_e = self.axis_set.ax_energy
        m = self.matrix

        for k, (uid, slot, asic) in enumerate(self._columns):
            selX = self.select_asic_from_column(uid, slot, asic, 'X')
            selY = self.select_asic_from_column(uid, slot, asic, 'Y')

            histochX, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selX], self.xbins, m['channel'][selX])
            histochY, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][selY], self.xbins, m['channel'][selY])

            plothtch.ax[0][k].imshow(histochX, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
            plothtch.ax[1][k].imshow(histochY, aspect='auto', norm=norm_colors, interpolation='none',
                                      extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')

            plothtch.ax[0][k].set_xlabel('ADC')
            plothtch.ax[1][k].set_xlabel('ADC')
            plothtch.ax[0][k].set_title(self._column_label(uid, slot, asic, 'X'), fontsize=6, rotation=90)

            if k == 0:
                plothtch.ax[0][k].set_ylabel('X ch no.')
                plothtch.ax[1][k].set_ylabel('Y ch no.')
 