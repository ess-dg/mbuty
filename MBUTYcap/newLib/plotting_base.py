"""
plotting_base.py

Shared plotting utilities and the common BasePlotter scaffolding used by
every concrete plotter module (plotting_readouts.py, plotting_hits.py,
plotting_events.py). Split out of plotting.py so those modules don't have
to import from each other.

Also home to the dashboard/headless-mode plot *selection* helpers
(resolve_active_plots, global_ui_kwargs_from_parameters) -- these used to
live in their own plot_selection.py, but they're thin, generic wrappers
directly on top of BasePlotter's own API (active_plot_methods()) with no
independent concerns of their own, so they live right next to what they
wrap instead of behind an extra import.
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
from newLib.histograms import Histogrammer
from newLib.colors import WARN, RESET


# ============================================================================
# Shared utilities
# ============================================================================

class PlotGrid:
    """Thin wrapper around plt.subplots producing a guaranteed-2D axis grid."""

    def __init__(self, fig_num, n_rows, n_cols=1, fig_size=(12, 12), sharex='col', sharey='row', **kwargs):
        import matplotlib.figure
        
        # If running inside a GUI context, populate the injected canvas figure directly
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

    def unshare_row(self, row_idx):
        """
        Detach every axis in `row_idx` from the shared y-axis group so it can
        carry its own independent y-scale (e.g. a taller PHS-sum panel below
        rows of channel-resolved 2D images that must stay locked together).
        """
        for ax in self.ax[row_idx]:
            try:
                ax.get_shared_y_axes().disconnect(ax)
            except AttributeError:
                # Fallback for older versions if needed
                if hasattr(ax, '_shared_axes') and 'y' in ax._shared_axes:
                    ax._shared_axes['y'].remove(ax)
            ax.yaxis.set_tick_params(labelleft=True)
            ax.autoscale(enable=True, axis='y')


def log_scale_norm(log_scale: bool):
    return LogNorm() if log_scale else None


def _safe_colorbar(fig, mappable, ax, warning_label: str, **kwargs):
    """imshow + LogNorm occasionally crashes when a panel is all-zero; degrade gracefully."""
    try:
        fig.colorbar(mappable, ax=ax, **kwargs)
    except Exception:
        print(f"\n --> {WARN}WARNING: Cannot plot {warning_label} in Log scale, changed to linear{RESET}", end='')


# ============================================================================
# Self-describing plot toggles
# ============================================================================
#
# Instead of a separate flags -> plot-method mapping table living off on its
# own (guaranteed to drift out of sync the moment a plot method is renamed,
# added, or removed), each plot_ method declares its own trigger flag(s)
# directly via @toggled_by, right next to the code it controls. Selection
# logic then just introspects whatever plot_ methods the concrete plotter
# actually has -- no table to maintain anywhere else.

def toggled_by(*flag_paths: str):
    """
    Decorator: marks a plot_ method as shown only when at least one of the
    given parameter flags is True. Each flag path is a dotted attribute
    path resolved against the live `parameters` object at selection time,
    e.g. "plotting.plotRawHits" or "wavelength.plotLambdaDistr".

    A plot_ method with NO @toggled_by at all is always active whenever its
    tab exists -- this is exactly legacy's behaviour for plot_xy_tof, which
    was never gated behind a flag.
    """
    def _decorate(func):
        func._toggle_flags = flag_paths
        return func
    return _decorate


def _resolve_flag(parameters, dotted_path: str) -> bool:
    obj = parameters
    for part in dotted_path.split('.'):
        obj = getattr(obj, part)
    return bool(obj)


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

    # ------------------------------------------------------------------
    # Generic plot-selection introspection -- see toggled_by() above.
    # ------------------------------------------------------------------

    def all_plot_methods(self) -> list:
        """Every plot_ method this concrete instance implements, regardless
        of whether it's currently toggled on. Used for tab-existence checks
        (empty means 'no plotter here at all') and the Comparison Matrix,
        which intentionally lists everything a plotter can produce."""
        return [name for name in dir(self) if name.startswith('plot_') and callable(getattr(self, name))]

    def active_plot_methods(self, parameters) -> list:
        """Subset of all_plot_methods() whose @toggled_by flag(s) currently
        resolve True against the live parameters object, plus every
        undecorated (always-on) plot_ method. This is what dashboard_config
        and headless mode iterate over -- the direct replacement for a
        hand-maintained flags-to-methods table."""
        active = []
        for name in self.all_plot_methods():
            flags = getattr(getattr(self, name), "_toggle_flags", None)
            if flags is None or any(_resolve_flag(parameters, f) for f in flags):
                active.append(name)
        return active


# ============================================================================
# Dashboard / headless-mode plot selection
# ============================================================================
#
# These build the {tab_key + '_active_plots': [...]} dict expected by
# MbutyDashboard's config, and also usable directly as an iteration order
# for headless mode. This replaces legacy MBUTY.py's plotting() if-chain,
# which called plot functions directly -- here we just produce a
# *selection*, and both the PySide6 dashboard (dashboard_config) and
# headless mode (direct calls) consume the same selection so there is
# exactly one place that decides "which plots does the user want".
#
# There used to be a hand-maintained table doing this job, mapping each
# parameters.plotting / .pulseHeigthSpect / .wavelength / .MONitor flag to
# a plot_* method name. That table lived off on its own, disconnected from
# the plot methods it described, and was guaranteed to drift the moment a
# method was renamed, added, or removed. It's gone now: resolve_active_plots()
# just asks each live plotter instance which of its own plot_ methods are
# currently active, via active_plot_methods() above -- no separate list to
# keep in sync, anywhere.

def resolve_active_plots(parameters, *, readout_plotter=None, hit_plotter=None,
                          event_plotter=None, bm_plotter=None) -> dict[str, list[str]]:
    """
    Parameters
    ----------
    parameters : the live `parameters` object, passed straight through to
        each plotter's active_plot_methods() to resolve @toggled_by flags.
    readout_plotter, hit_plotter, event_plotter, bm_plotter :
        the actual plotter instances for each tab (e.g.
        orchestrator.detector_pipeline.readout_plotter, ...
        orchestrator.bm_pipeline.event_plotter). Pass None for any tab
        whose pipeline wasn't built -- it resolves to an empty selection,
        same as legacy's "nothing to plot here" behaviour.

    Returns
    -------
    dict with keys: "readouts_active_plots", "hits_active_plots",
    "events_active_plots", "bm_active_plots" -- each a list of plot_*
    method names currently toggled on for that plotter.
    """
    def _active(plotter) -> list[str]:
        return plotter.active_plot_methods(parameters) if plotter is not None else []

    return {
        "readouts_active_plots": _active(readout_plotter),
        "hits_active_plots":     _active(hit_plotter),
        "events_active_plots":   _active(event_plotter),
        "bm_active_plots":       _active(bm_plotter),
    }


def global_ui_kwargs_from_parameters(parameters, config: dict, unit_ids=None, figure=None) -> dict:
    """
    Shared rendering kwargs every plot_* method may or may not accept
    (filtered downstream via inspect.signature). Single place both
    render_plot() and the headless driver pull these from, so the
    dashboard and the headless fallback can never drift apart.

    unit_ids: pass a "section" slice of unit IDs here to scope a plot
    call to one block of cassettes/tubes. Methods that don't accept
    unit_ids (plot_xy_tof, plot_x_lambda -- whole-detector composite
    images) simply ignore it via the same signature-filtering mechanism.
    """
    kwargs = {
        "log_scale":   getattr(parameters.plotting, "plotIMGlog", False),
        "abs_units":   getattr(parameters.plotting, "plotABSunits", False),
        "orientation": config.get("orientation", "vertical"),
    }
    if unit_ids is not None:
        kwargs["unit_ids"] = unit_ids
    if figure is not None:
        kwargs["fig_num"] = figure
    return kwargs