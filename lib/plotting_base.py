"""
plotting_base.py

Shared plotting utilities and the common BasePlotter scaffolding used by
every concrete plotter module (plotting_readouts.py, plotting_hits.py,
plotting_events.py). Split out of plotting.py so those modules don't have
to import from each other.
"""

from __future__ import annotations

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
from lib.histograms import Histogrammer
from lib.colors import WARN, RESET


# ============================================================================
# Shared utilities
# ============================================================================

class PlotGrid:
    """Thin wrapper around plt.subplots producing a guaranteed-2D axis grid."""

    def __init__(self, fig_num, n_rows, n_cols=1, fig_size=(12, 12), sharex='col', sharey='row', **kwargs):
        import matplotlib.figure

        # # If running inside a GUI context, populate the injected canvas figure directly
        if isinstance(fig_num, matplotlib.figure.Figure):
            self.fig = fig_num
            axes = self.fig.subplots(
                nrows=n_rows, ncols=n_cols,
                sharex=sharex, sharey=sharey, **kwargs
            )
        # Fallback to standard PyPlot state manager if running a standalone script track
        else:
            self.fig, axes = plt.subplots(
                    num=fig_num, figsize=fig_size, nrows=n_rows, ncols=n_cols,
                    sharex=sharex, sharey=sharey, **kwargs,
            )

        self.ax = np.atleast_2d(axes).reshape(n_rows, n_cols)

    # def unshare_row(self, row_idx):
    #     """
    #     Detach every axis in `row_idx` from the shared y-axis group so it can
    #     carry its own independent y-scale (e.g. a taller PHS-sum panel below
    #     rows of channel-resolved 2D images that must stay locked together).
    #     """
    #     for ax in self.ax[row_idx]:
    #         try:
    #             ax.get_shared_y_axes().disconnect(ax)
    #         except AttributeError:
    #             # Fallback for older versions if needed
    #             if hasattr(ax, '_shared_axes') and 'y' in ax._shared_axes:
    #                 ax._shared_axes['y'].remove(ax)
    #         ax.yaxis.set_tick_params(labelleft=True)
    #         ax.autoscale(enable=True, axis='y')


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

    # Dashboard menu: display name -> method name. Empty on the base class;
    # each concrete plotter (or its detector-agnostic base, when every
    # subclass shares the same method names) sets this to declare what it
    # can show. See available_plot_names()/render() below.
    PLOT_METHODS: dict[str, str] = {}

    def __init__(self, container, parameters, config, axis_set, unit_ids):
        self.container  = container
        self.config     = config
        self.parameters = parameters
        self.axis_set   = axis_set
        self.hist       = Histogrammer(parameters.plotting.histogOutBounds)
        self.is_empty   = container.fill_count == 0
        self.unit_ids   = unit_ids
 
        if self.is_empty:
            print(f'\t{WARN}WARNING: {type(container).__name__} is empty -> skipping plots{RESET}')

    @property
    def matrix(self):
        return self.container.matrix[:self.container.fill_count]

    def _has_field(self, name: str) -> bool:
        return name in self.container.matrix.dtype.names

    ################ For dashboard #######################################
    def available_plot_names(self) -> list[str]:
        """Menu names the dashboard can show for this plotter -- everything
        in PLOT_METHODS whose target method actually exists. Stage-base
        stubs (e.g. plot_adc_vs_channel on R5560ReadoutsPlotter) still count
        as "available": they exist, and calling them just prints a
        not-supported notice via _skip -- same graceful-degrade behaviour
        CLI plotting already relies on."""
        return [name for name, m in self.PLOT_METHODS.items() if hasattr(self, m)]

    def render(self, plot_name: str, figure) -> None:
        """The one seam the dashboard draws through. CLI plotting never
        touches this -- it keeps calling plot_channels_raw() etc. directly.
        `figure` is a real matplotlib Figure (a Qt canvas's canvas.figure);
        passing it straight through as fig_num relies on PlotGrid's
        isinstance(fig_num, Figure) branch to draw onto it in place instead
        of opening a pyplot-managed window."""
        method = getattr(self, self.PLOT_METHODS.get(plot_name, ''), None)
        if method is None:
            self._skip(plot_name)
            return
        method(fig_num=figure)
    #######################################################################

    def _skip(self, name: str, *args, **kwargs) -> None:
        """Shared no-op body for stage-base stub methods (see
        BaseReadoutsPlotter/BaseHitsPlotter/BaseEventsPlotter). A concrete
        plotter that doesn't implement a given plot_* method inherits the
        stub, which just prints and returns -- so BasePipeline.plot() can
        call any plot_* method on any plotter unconditionally, safely."""
        print(f"\t{WARN}'{name}' is not supported for {type(self).__name__} -- skipping.{RESET}")