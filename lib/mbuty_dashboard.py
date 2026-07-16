"""
mbuty_dashboard.py — Phase 1 Consolidated PySide6 UI Dashboard Shell

Architectural contract:
  * This module does NOT import or touch any vectorized core engine, reader,
    or calibration file. All pipeline access goes through DashboardDataSource,
    an interface the real pipeline implements elsewhere.
  * Sorting is assumed already done upstream (kind='stable'). Column-header
    sort in the UI is a view-only QSortFilterProxyModel reorder — it never
    mutates or re-sorts the underlying structured array.
  * Canvas / table widgets are single-source-of-truth dicts keyed by
    (tab_key, item_name); no parallel/disconnected metadata lists.
  * Per-instrument-tab plots are fixed at construction time from config
    (whatever the user selected before running). No add/remove/toggle at
    runtime, no checkboxes on Readouts / Mapped Hits / Coincidence Events /
    Beam Monitor. Only the Comparison Matrix tab is interactive.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Sequence

import numpy as np
import os
# os.environ["QT_API"] = "pyside6"

# CHANGED: Replaced PySide6 imports with qtpy equivalents for clean cross-IDE & cross-platform portability
from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QTimer
from qtpy.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QCheckBox,
    QLabel,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QFrame,
)

# RESTORED: Standard Matplotlib Agg backend that automatically resolves Qt5 vs Qt6
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure


# --------------------------------------------------------------------------
# Data source interface — implemented by the real pipeline, not by this file
# --------------------------------------------------------------------------

class DashboardDataSource:
    """Contract the dashboard shell relies on. No implementation here touches
    engine internals; the real pipeline subclasses this."""

    def beam_monitor_present(self) -> bool:
        raise NotImplementedError

    def get_dataframe_array(self, tab_key: str) -> tuple[np.ndarray, int]:
        """Return (structured_array, fill_count) for the given tab."""
        raise NotImplementedError

    def get_available_plots(self, tab_key: str) -> Sequence[str]:
        """All plots the pipeline can produce for this tab. InstrumentView
        only ever renders the config-selected subset; ComparisonMatrixView
        lists all of them, per tab section."""
        raise NotImplementedError

    def render_plot(self, tab_key: str, plot_name: str, figure: Figure) -> None:
        """Draw directly onto the given matplotlib Figure."""
        raise NotImplementedError


class OrchestratorDataSource(DashboardDataSource):
    def __init__(self, detector_pipeline, bm_pipeline):
        self._plotters = {
            "readouts":           detector_pipeline.readout_plotter,
            "mapped_hits":        detector_pipeline.hit_plotter,
            "coincidence_events": detector_pipeline.event_plotter,
            "beam_monitor":       bm_pipeline.event_plotter if bm_pipeline else None,
        }
        # Same keys as _plotters -- the container backing each tab's
        # dataframe pane. bm_pipeline is already None-checked by the
        # caller (MBUTYOrchestrator._launch_dashboard), same as above.
        self._containers = {
            "readouts":              detector_pipeline.readouts_container,
            "mapped_hits":           detector_pipeline.hits_container,
            "coincidence_events":    detector_pipeline.events_container,
            "beam_monitor":          bm_pipeline.events_container if bm_pipeline else None,
            "beam_monitor_readouts": bm_pipeline.readouts_container if bm_pipeline else None,
        }

    def beam_monitor_present(self) -> bool:
        return self._plotters.get("beam_monitor") is not None

    def get_available_plots(self, tab_key):
        p = self._plotters.get(tab_key)
        return p.available_plot_names() if p else []

    def get_dataframe_array(self, tab_key):
        container = self._containers.get(tab_key)
        if container is None:
            return np.empty(0, dtype=[("_", "i4")]), 0
        return container.matrix, container.fill_count

    def render_plot(self, tab_key, plot_name, figure):
        p = self._plotters.get(tab_key)
        if p:
            p.render(plot_name, figure)


# --------------------------------------------------------------------------
# Orchestration entry point -- everything MBUTY.py needs is this one call
# --------------------------------------------------------------------------

def _selected_plot_names_by_tab(parameters) -> dict:
    """Mirrors -- flag for flag -- the exact checklist BasePipeline.make_plots()
    and BeamMonitorPipeline.plot() read to decide what a CLI run would have
    drawn. The dashboard is a viewing layer, not a second source of truth,
    so "what's selected" must come from the same parameters.plotting /
    .wavelength / .pulseHeigthSpect / .MONitor flags, not be reinvented here.

    A few plots aren't gated by any flag at all -- plot_xy/plot_tof_xy
    (BasePipeline.plot_always, run unconditionally) and plot_position_per_tube
    (R5560Pipeline.plot_always override, same deal) -- those are included
    unconditionally rather than left out.

    Returns display-name sets keyed by dashboard tab_key; launch_dashboard()
    intersects each set against get_available_plots() so a flag being on
    never surfaces a plot this pipeline can't actually produce.
    """
    p, w, phs, mon = parameters.plotting, parameters.wavelength, parameters.pulseHeigthSpect, parameters.MONitor

    readouts = {name for name, on in {
        "Raw Channels":   p.plotRawReadouts,
        "Timestamps":     p.plotReadoutsTimeStamps,
        "ADC vs Channel": p.plotADCvsCh,
        "Chopper Resets": p.plotChopperResets,
    }.items() if on}

    hits = {name for name, on in {
        "Raw Channels":          p.plotRawHits,
        "Timestamps":            p.plotHitsTimeStamps,
        "Timestamps vs Channel": p.plotHitsTimeStampsVSChannels,
    }.items() if on}

    events = {"XY", "ToF vs XY", "Position per Tube"}  # always drawn, no flag
    events |= {name for name, on in {
        "ToF":                 p.plotToFDistr,
        "Wavelength":          w.plotLambdaDistr,
        "X vs Wavelength":     w.plotXLambda,
        "Multiplicity":        p.plotMultiplicity,
        "PHS":                 phs.plotPHS,
        "PHS Correlation":     phs.plotPHScorrelation,
        "Time Between Events": p.plotTimeBetwEv,
    }.items() if on}

    # BeamMonitorPipeline.plot(): plot_lambda_mon is nested inside the
    # plotMONtofPHS check, not an independent flag -- reproduce that nesting.
    beam_monitor = set()
    if mon.plotMONtofPHS:
        beam_monitor.add("ToF & PHS")
        if w.plotLambdaDistr:
            beam_monitor.add("Wavelength")

    return {
        "readouts":           readouts,
        "mapped_hits":        hits,
        "coincidence_events": events,
        "beam_monitor":       beam_monitor,
    }


def launch_dashboard(detector_pipeline, bm_pipeline, parameters):
    """The one call MBUTY.py needs to make. Builds the plotters
    (construction only -- no eager drawing, see BasePipeline.build_plotters /
    BeamMonitorPipeline.build_plotter), wraps them in OrchestratorDataSource,
    works out which plots the user's parameters actually select, and shows
    the Qt window(s).

    Mirrors BasePipeline.plot()'s plottingInSections behaviour: when it's
    on, topology unit_ids are chunked into blocks (same _chunk helper CLI
    mode uses) and one dashboard is shown per block -- closing it advances
    to the next section's dashboard, same "close one, next pops up" flow
    the CLI gives via its per-section input() prompt, just windows instead
    of a console step-through. Beam Monitor has no per-unit concept at all,
    so its plotter is built once and reused unchanged across every section.

    Deliberately does none of its own error handling: MBUTY.py wraps the
    call in a try/except that falls back to standard plotting on any
    failure here (missing PySide6, no display/Qt platform plugin, etc.),
    so this stays a plain "build it and show it" path.

    Returns the last MbutyDashboard instance shown, so the caller can hold
    a reference (Qt won't keep a window alive if it's garbage-collected).
    """
    import sys
    from lib.pipelines import _chunk

    bm_active = bool(bm_pipeline) and parameters.MONitor.MONOnOff
    if bm_active:
        bm_pipeline.build_plotter()  # construction only, doesn't draw; BM isn't sectioned

    app = QApplication.instance() or QApplication(sys.argv)
    selected = _selected_plot_names_by_tab(parameters)

    def _show_section(unit_ids) -> MbutyDashboard:
        detector_pipeline.build_plotters(unit_ids=unit_ids)
        # Fresh data source every section -- build_plotters() just replaced
        # detector_pipeline.readout_plotter/hit_plotter/event_plotter with
        # new instances scoped to this block, and OrchestratorDataSource
        # snapshots those references at construction time.
        data_source = OrchestratorDataSource(detector_pipeline, bm_pipeline if bm_active else None)
        config = {
            "readouts_active_plots": [n for n in data_source.get_available_plots("readouts")
                                       if n in selected["readouts"]],
            "hits_active_plots":     [n for n in data_source.get_available_plots("mapped_hits")
                                       if n in selected["mapped_hits"]],
            "events_active_plots":   [n for n in data_source.get_available_plots("coincidence_events")
                                       if n in selected["coincidence_events"]],
            "bm_active_plots":       [n for n in data_source.get_available_plots("beam_monitor")
                                       if n in selected["beam_monitor"]],
        }
        dashboard = MbutyDashboard(data_source, config=config)
        dashboard.resize(1300, 800)
        dashboard.show()
        app.exec()  # blocks until this section's window is closed
        return dashboard

    topology = detector_pipeline.config.get('topology', [])
    unit_ids = np.sort([entry['ID'] for entry in topology])

    if not parameters.plotting.plottingInSections:
        return _show_section(unit_ids)

    blocks = _chunk(list(unit_ids), parameters.plotting.plottingInSectionsBlocks)
    print(f'\nDashboard: plotting in {len(blocks)} section(s) of '
          f'{parameters.plotting.plottingInSectionsBlocks} unit(s) each.')

    dashboard = None
    for i, block in enumerate(blocks):
        print(f'\n\tSection {i + 1}/{len(blocks)} -- unit IDs {block[0]} to {block[-1]}'
              f' -- close this window to continue.')
        dashboard = _show_section(block)
    return dashboard


# --------------------------------------------------------------------------
# Table model: structured numpy array -> QTableView, with the validity gate
# --------------------------------------------------------------------------

class StructuredArrayTableModel(QAbstractTableModel):
    """Read-only view over array[:fill_count], filtered by sentinel masks."""

    def __init__(self, index_fields: Iterable[str] = (), parent=None):
        super().__init__(parent)
        self._array: np.ndarray = np.empty(0, dtype=[("_", "i4")])
        self._fill_count: int = 0
        self._index_fields = tuple(index_fields)
        self._valid_rows: np.ndarray = np.empty(0, dtype=np.int64)

    def set_data(self, array: np.ndarray, fill_count: int) -> None:
        self.beginResetModel()
        self._array = array
        self._fill_count = max(0, min(fill_count, len(array)))
        self._valid_rows = self._compute_valid_rows()
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        """
        Bypasses Qt loops by using C-optimized NumPy vector sorting on the underlying array data.
        """
        if self._fill_count == 0 or self._array.dtype.names is None or len(self._valid_rows) == 0:
            return

        self.layoutAboutToBeChanged.emit()
        
        # Get the name of the column field clicked
        field_name = self._array.dtype.names[column]
        
        # Extract only the active valid rows for this column to sort on
        sort_values = self._array[field_name][self._valid_rows]
        
        # Perform highly optimized vector argsort
        sorted_indices = np.argsort(sort_values)
        
        if order == Qt.DescendingOrder:
            sorted_indices = sorted_indices[::-1]
            
        # Re-order our valid rows index map instantly
        self._valid_rows = self._valid_rows[sorted_indices]
        
        self.layoutChanged.emit()

    def _compute_valid_rows(self) -> np.ndarray:
        if self._fill_count == 0 or self._array.dtype.names is None:
            return np.empty(0, dtype=np.int64)
        view = self._array[: self._fill_count]
        mask = np.ones(self._fill_count, dtype=bool)
        
        float_fields = [name for name in view.dtype.names if np.issubdtype(view.dtype[name], np.floating)]
        idx_fields = [name for name in self._index_fields if name in view.dtype.names]
        
        for name in float_fields:
            mask &= ~np.isnan(view[name])
        for name in idx_fields:
            mask &= view[name] >= 0
            
        return np.nonzero(mask)[0]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._valid_rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._array.dtype.names is None:
            return 0
        return len(self._array.dtype.names)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._valid_rows):
            return None
        row = self._valid_rows[index.row()]
        field = self._array.dtype.names[index.column()]
        value = self._array[field][row]
        if role == Qt.DisplayRole:
            if isinstance(value, np.floating):
                return f"{value:.6g}"
            return str(value)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._array.dtype.names[section]
        return str(section)


def _build_dataframe_pane(index_fields: Iterable[str]) -> tuple[QWidget, StructuredArrayTableModel, QTableView]:
    """Single reusable factory for a sortable, read-only dataframe view."""
    model = StructuredArrayTableModel(index_fields=index_fields)
    
    view = QTableView()
    # Direct binding: bypasses the proxy model bottleneck entirely
    view.setModel(model)
    view.setEditTriggers(QTableView.NoEditTriggers)
    view.setSelectionBehavior(QTableView.SelectRows)
    view.setAlternatingRowColors(True)
    view.setSortingEnabled(True)  # Still enabled, but handled via vector sorting now

    # Bump the font a notch -- the default point size reads cramped/tiny,
    # especially on Readouts with its wider column count.
    font = view.font()
    font.setPointSize(font.pointSize() + 2)
    view.setFont(font)
    view.horizontalHeader().setFont(font)

    # Fixed row height: without this Qt can fall back to measuring every
    # row's sizeHint (O(rows)) on layout changes instead of O(visible).
    # Cheap, unconditional win once row counts get into the 10^4-10^6 range.
    # Sized up to match the larger font above.
    vheader = view.verticalHeader()
    vheader.setSectionResizeMode(vheader.ResizeMode.Fixed)
    vheader.setDefaultSectionSize(28)

    return view, model, view


def _build_plot_pane(tab_key: str, plot_name: str, data_source: DashboardDataSource) -> tuple[QWidget, FigureCanvasQTAgg]:
    canvas = FigureCanvasQTAgg(Figure(figsize=(5, 4)))
    canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    canvas.setMinimumSize(50, 50)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(NavigationToolbar2QT(canvas, page))
    page_layout.addWidget(canvas)
    data_source.render_plot(tab_key, plot_name, canvas.figure)
    canvas.draw_idle()
    return page, canvas


# --------------------------------------------------------------------------
# TabSpec: single source of truth for tab key / title / filter fields /
# which plots that tab shows, consumed by both InstrumentView and
# ComparisonMatrixView.
# --------------------------------------------------------------------------

class TabSpec(NamedTuple):
    key: str
    title: str
    index_fields: tuple[str, ...]
    active_plots: tuple[str, ...]  # fixed set chosen in config, pre-run
    # (sub-tab title, data-source key for get_dataframe_array). A data
    # key of None means "use this tab's own key" -- true for every
    # instrument tab except Beam Monitor, which shows two containers
    # (raw BM readouts + mapped BM events) side by side as two sub-tabs.
    dataframe_tabs: tuple[tuple[str, str | None], ...] = (("Dataframe View", None),)


# --------------------------------------------------------------------------
# One instrument tab: flat sub-tabs — Dataframe View + one per active plot.
# No checkboxes, no runtime add/remove. Set once from config at construction.
# --------------------------------------------------------------------------

class InstrumentView(QWidget):
    """
    Sub-tabs are ordered plots-first, "Dataframe View" last -- the plots are
    what a physicist actually watches during a run; the dataframe is a
    debugging tool, more useful side-by-side in the Comparison Matrix than
    as this tab's default landing page.

    Only the sub-tab shown first is built synchronously. Once it's up, the
    rest fill in one at a time on the Qt event loop's idle turns (a 0ms
    QTimer chain), so by the time the user has looked around, everything's
    already built with no perceptible per-tab click lag. If the user clicks
    an unbuilt tab before the queue gets to it, that click jumps the queue.
    """

    def __init__(self, spec: TabSpec, data_source: DashboardDataSource, parent=None):
        super().__init__(parent)
        self._tab_key = spec.key
        self._spec = spec
        self._data_source = data_source

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        self.table_models: dict[str, StructuredArrayTableModel] = {}
        self.table_views: dict[str, QTableView] = {}
        self._plot_canvases: dict[str, FigureCanvasQTAgg] = {}

        # sub-tab title -> data-source key (None resolves to this tab's own key)
        self._dataframe_keys: dict[str, str] = {
            title: (data_key if data_key is not None else spec.key)
            for title, data_key in spec.dataframe_tabs
        }

        self._built: set[str] = set()
        for plot_name in spec.active_plots:
            self.sub_tabs.addTab(QWidget(), plot_name)
        for title in self._dataframe_keys:
            self.sub_tabs.addTab(QWidget(), title)

        self._fill_queue: list[str] = [self.sub_tabs.tabText(i) for i in range(self.sub_tabs.count())]

        self.sub_tabs.currentChanged.connect(self._ensure_built)
        self._ensure_built(0)  # the sub-tab shown by default needs content now
        QTimer.singleShot(0, self._process_background_queue)

    def _process_background_queue(self) -> None:
        while self._fill_queue and self._fill_queue[0] in self._built:
            self._fill_queue.pop(0)
        if not self._fill_queue:
            return
        title = self._fill_queue.pop(0)
        index = self._index_of(title)
        if index is not None:
            self._ensure_built(index)
        # Yield back to the event loop between builds so clicks stay
        # responsive and can jump ahead of the queue.
        QTimer.singleShot(0, self._process_background_queue)

    def _index_of(self, title: str) -> int | None:
        for i in range(self.sub_tabs.count()):
            if self.sub_tabs.tabText(i) == title:
                return i
        return None

    def _ensure_built(self, index: int) -> None:
        if index < 0:
            return  # removeTab() below can transiently emit currentChanged(-1)
        title = self.sub_tabs.tabText(index)
        if not title or title in self._built:
            return
        self._built.add(title)

        if title in self._dataframe_keys:
            page, model, view = _build_dataframe_pane(self._spec.index_fields)
            self.table_models[title] = model
            self.table_views[title] = view
            array, fill_count = self._data_source.get_dataframe_array(self._dataframe_keys[title])
            model.set_data(array, fill_count)
        else:
            page, canvas = _build_plot_pane(self._tab_key, title, self._data_source)
            self._plot_canvases[title] = canvas

        # removeTab()/insertTab() shift the current tab and re-emit
        # currentChanged reentrantly (into this same slot) while we're mid-
        # swap. Block signals for the swap itself, then restore selection
        # afterwards -- but ONLY force focus onto the rebuilt tab if it's
        # the one the user was already looking at. A background fill of
        # some other tab must not yank the view out from under them; Qt
        # already keeps the currently-viewed widget selected automatically
        # since we insert back at the exact index we removed from.
        was_current_index = self.sub_tabs.currentIndex()
        was_current_title = self.sub_tabs.tabText(was_current_index) if was_current_index >= 0 else None

        old = self.sub_tabs.widget(index)
        self.sub_tabs.blockSignals(True)
        try:
            self.sub_tabs.removeTab(index)
            self.sub_tabs.insertTab(index, page, title)
        finally:
            self.sub_tabs.blockSignals(False)

        if index == was_current_index or title == was_current_title:
            self.sub_tabs.setCurrentIndex(index)
        if old is not None:
            old.deleteLater()

    def refresh_dataframe(self) -> None:
        for title, model in self.table_models.items():
            array, fill_count = self._data_source.get_dataframe_array(self._dataframe_keys[title])
            model.set_data(array, fill_count)


# --------------------------------------------------------------------------
# Comparison Matrix tab: sectioned checkbox panel (dataframe + plots per
# tab) + dynamic grid, 2-4 items, that never lets one cell dominate.
# This is the one interactive/runtime-configurable tab.
# --------------------------------------------------------------------------

class ComparisonMatrixView(QWidget):
    MIN_ACTIVE = 2
    MAX_ACTIVE = 4
    DATAFRAME_ITEM = "Dataframe View"

    def __init__(self, data_source: DashboardDataSource, tab_specs: Sequence[TabSpec], parent=None):
        super().__init__(parent)
        self._data_source = data_source
        self._index_fields_by_tab = {spec.key: spec.index_fields for spec in tab_specs}

        # item_key = (tab_key, item_name) -> checkbox
        self._checkboxes: dict[tuple[str, str], QCheckBox] = {}
        # item_key -> live widget (FigureCanvasQTAgg or QTableView), single source
        self._cells: dict[tuple[str, str], QWidget] = {}

        root = QHBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(240)
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel(f"Select {self.MIN_ACTIVE}-{self.MAX_ACTIVE} items to compare:"))

        for spec in tab_specs:
            header = QLabel(spec.title)
            header.setStyleSheet("font-weight: bold; margin-top: 8px;")
            panel_layout.addWidget(header)
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            panel_layout.addWidget(line)

            # Comparison Matrix lists every plot the pipeline supports for
            # this tab, not just the config-selected subset shown in the
            # instrument tab itself. Plots first, Dataframe View last --
            # it's the debugging tool, most useful here specifically for
            # side-by-side comparison (e.g. hits vs. events to verify
            # clustering), not as the thing someone reaches for first.
            for plot_name in data_source.get_available_plots(spec.key):
                item_key = (spec.key, plot_name)
                cb = QCheckBox(plot_name)
                cb.toggled.connect(self._on_toggle)
                panel_layout.addWidget(cb)
                self._checkboxes[item_key] = cb

            df_key = (spec.key, self.DATAFRAME_ITEM)
            df_cb = QCheckBox(self.DATAFRAME_ITEM)
            df_cb.toggled.connect(self._on_toggle)
            panel_layout.addWidget(df_cb)
            self._checkboxes[df_key] = df_cb

        panel_layout.addStretch()
        scroll.setWidget(panel)
        root.addWidget(scroll)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        root.addWidget(self.grid_container, stretch=1)

        self._status_label = QLabel(f"Select at least {self.MIN_ACTIVE} items to compare.")
        self._status_label.setAlignment(Qt.AlignCenter)
        self.grid_layout.addWidget(self._status_label, 0, 0)

    def _active_keys(self) -> list[tuple[str, str]]:
        return [key for key, cb in self._checkboxes.items() if cb.isChecked()]

    def _on_toggle(self, checked: bool) -> None:
        if checked and len(self._active_keys()) > self.MAX_ACTIVE:
            sender = self.sender()
            sender.blockSignals(True)
            sender.setChecked(False)
            sender.blockSignals(False)
            return
        self._rebuild_grid()

    def _clear_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        # Reset stretch/minimums so a previous 1- or 2-item layout can't
        # keep dominating space when the item count changes.
        for r in range(2):
            self.grid_layout.setRowStretch(r, 0)
            self.grid_layout.setRowMinimumHeight(r, 0)
        for c in range(2):
            self.grid_layout.setColumnStretch(c, 0)
            self.grid_layout.setColumnMinimumWidth(c, 0)

    def _rebuild_grid(self) -> None:
        active = self._active_keys()
        self._clear_grid()

        # Drop cells for items that were unchecked.
        for key in list(self._cells.keys()):
            if key not in active:
                widget = self._cells.pop(key)
                widget.setParent(None)
                widget.deleteLater()

        if len(active) < self.MIN_ACTIVE:
            self._status_label = QLabel(
                f"Select at least {self.MIN_ACTIVE} items to compare "
                f"({len(active)} selected)."
            )
            self._status_label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(self._status_label, 0, 0, 1, 1)
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setColumnStretch(0, 1)
            return

        positions = self._positions_for(len(active))
        rows_used = {p[0] for p in positions}
        cols_used = {p[1] for p in positions}
        for r in rows_used:
            self.grid_layout.setRowStretch(r, 1)
        for c in cols_used:
            self.grid_layout.setColumnStretch(c, 1)

        for key, pos in zip(active, positions):
            tab_key, item_name = key
            widget = self._cells.get(key)
            if widget is None:
                widget = self._build_cell(tab_key, item_name)
                self._cells[key] = widget
            row, col, rspan, cspan = pos
            self.grid_layout.addWidget(widget, row, col, rspan, cspan)

    def _build_cell(self, tab_key: str, item_name: str) -> QWidget:
        if item_name == self.DATAFRAME_ITEM:
            index_fields = self._index_fields_by_tab.get(tab_key, ())
            df_pane, model, _view = _build_dataframe_pane(index_fields)
            array, fill_count = self._data_source.get_dataframe_array(tab_key)
            model.set_data(array, fill_count)
            df_pane.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            df_pane.setMinimumSize(50, 50)
            return df_pane

        canvas = FigureCanvasQTAgg(Figure(figsize=(5, 4)))
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas.setMinimumSize(50, 50)
        self._data_source.render_plot(tab_key, item_name, canvas.figure)
        canvas.draw_idle()
        return canvas

    @staticmethod
    def _positions_for(n: int) -> list[tuple[int, int, int, int]]:
        if n <= 1:
            return [(0, 0, 1, 1)]
        if n == 2:
            return [(0, 0, 1, 1), (0, 1, 1, 1)]
        return [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)][:n]


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------

class MbutyDashboard(QMainWindow):
    def __init__(self, data_source: DashboardDataSource, config: dict, parent=None):
        super().__init__(parent)
        self._data_source = data_source
        self._config = config
        self.setWindowTitle("MBUTY Dashboard")

        self.main_tabs = QTabWidget()
        self.setCentralWidget(self.main_tabs)

        # Single source of truth for which tabs exist, their field config,
        # and which plots each instrument tab shows (config-selected,
        # pre-run — fixed for the lifetime of this window).
        # Reverse-pipeline order: Events is what a physicist watches during
        # a run (and has the most plots), so it's shown -- and built --
        # first. Readouts/Hits are further back in the pipeline and mostly
        # matter for debugging, so they load later / on demand.
        #
        # Generic availability rule: a tab is only added if the pipeline
        # actually has something behind it. get_available_plots() already
        # returns [] whenever the backing plotter is None (see
        # OrchestratorDataSource) -- e.g. bareReadoutsCalculation stopped
        # the pipeline after the readouts stage, or a given pipeline
        # deliberately suppresses a plotter (VMMClusteredPipeline currently
        # sets hit_plotter to None even though hits are still computed
        # internally -- see pipelines.py). One rule covers every such case
        # without the dashboard needing to know *why* a tab is missing.
        def _maybe_tab(key: str, title: str, index_cfg_key: str, active_cfg_key: str) -> TabSpec | None:
            available = data_source.get_available_plots(key)
            if not available:
                return None
            return TabSpec(
                key, title,
                tuple(config.get(index_cfg_key, ())),
                tuple(config.get(active_cfg_key, available)),
            )

        tab_specs: list[TabSpec] = []
        for spec in (
            _maybe_tab("coincidence_events", "Coincidence Events", "events_index_fields", "events_active_plots"),
            _maybe_tab("mapped_hits", "Mapped Hits", "hits_index_fields", "hits_active_plots"),
            _maybe_tab("readouts", "Readouts", "readouts_index_fields", "readouts_active_plots"),
        ):
            if spec is not None:
                tab_specs.append(spec)

        # Beam Monitor stays on its own explicit condition rather than the
        # generic None-check above: it's an independent pipeline (possibly
        # of a different hardware type than the main detector), not a stage
        # of the same pipeline, so "is a BM stream present at all" is a
        # different question than "did this stage of the detector pipeline
        # produce data".
        if data_source.beam_monitor_present():
            tab_specs.append(TabSpec(
                "beam_monitor", "Beam Monitor",
                tuple(config.get("bm_index_fields", ())),
                tuple(config.get("bm_active_plots", data_source.get_available_plots("beam_monitor"))),
                dataframe_tabs=(
                    ("BM Readouts", "beam_monitor_readouts"),
                    ("BM Events",   "beam_monitor"),
                ),
            ))

        # Main tabs are lazy too: each InstrumentView is only constructed
        # (and its default sub-tab built) when the user actually clicks it,
        # not for all 4 instruments before the window has even painted.
        self._tab_specs = tab_specs
        self._data_source = data_source
        self.views: dict[str, InstrumentView] = {}
        self._built_main: set[int] = set()

        for spec in tab_specs:
            self.main_tabs.addTab(QWidget(), spec.title)

        self.comparison_view = ComparisonMatrixView(data_source, tab_specs)
        self.main_tabs.addTab(self.comparison_view, "Comparison Matrix")

        self.main_tabs.currentChanged.connect(self._ensure_main_built)
        self._ensure_main_built(0)  # whichever tab is shown first needs content now

    def _ensure_main_built(self, index: int) -> None:
        if index < 0 or index in self._built_main:
            return  # removeTab() below can transiently emit currentChanged(-1)
        title = self.main_tabs.tabText(index)
        spec = next((s for s in self._tab_specs if s.title == title), None)
        if spec is None:
            return  # Comparison Matrix -- already fully built up front
        self._built_main.add(index)

        view = InstrumentView(spec, self._data_source)
        self.views[spec.key] = view

        old = self.main_tabs.widget(index)
        self.main_tabs.blockSignals(True)
        try:
            self.main_tabs.removeTab(index)
            self.main_tabs.insertTab(index, view, title)
        finally:
            self.main_tabs.blockSignals(False)
        self.main_tabs.setCurrentIndex(index)
        if old is not None:
            old.deleteLater()

    def refresh_all_dataframes(self) -> None:
        """Refresh dataframes only for tabs that have actually been opened."""
        for view in self.views.values():
            view.refresh_dataframe()


# --------------------------------------------------------------------------
# Demo data source — for manual smoke-testing this shell only.
# Delete / replace with the real pipeline's DashboardDataSource subclass.
# --------------------------------------------------------------------------

class _DemoDataSource(DashboardDataSource):
    _DTYPE = np.dtype([("ts", "f8"), ("wire", "i4"), ("strip", "i4"), ("adc", "f8")])

    def beam_monitor_present(self) -> bool:
        return True

    def get_dataframe_array(self, tab_key: str):
        n = 50
        arr = np.zeros(n, dtype=self._DTYPE)
        arr["ts"] = np.arange(n, dtype="f8")
        arr["wire"] = np.arange(n) % 16
        arr["strip"] = np.arange(n) % 32
        arr["adc"] = np.random.rand(n) * 1000
        arr["wire"][3] = -1        # uninitialized sentinel row -> filtered
        arr["adc"][7] = np.nan     # math-noise sentinel row -> filtered
        return arr, n

    def get_available_plots(self, tab_key: str):
        return ["ADC Spectrum", "Wire vs Strip", "Time Profile", "Rate vs Time"]

    def render_plot(self, tab_key: str, plot_name: str, figure: Figure) -> None:
        figure.clear()
        ax = figure.add_subplot(111)
        ax.plot(np.random.rand(50))
        ax.set_title(f"{tab_key} :: {plot_name}")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    # Demo config: each instrument tab shows only the plots selected
    # "before running" — a fixed subset of what the pipeline can produce.
    demo_config = {
        "readouts_active_plots": ["ADC Spectrum", "Time Profile"],
        "hits_active_plots": ["Wire vs Strip"],
        "events_active_plots": ["ADC Spectrum", "Wire vs Strip", "Rate vs Time"],
        "bm_active_plots": ["Rate vs Time"],
    }
    window = MbutyDashboard(_DemoDataSource(), config=demo_config)
    window.resize(1300, 800)
    window.show()
    sys.exit(app.exec())