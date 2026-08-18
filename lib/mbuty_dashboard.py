"""
mbuty_dashboard.py

@author: Sheila Monera Cabarique
----------------------------------
PySide6 interactive dashboard shell providing tabular data 
views, sorted Qt models, and live matplotlib plotting panes 
for MBUTY analysis pipelines.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Sequence

import numpy as np
import os

from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QTimer, QEventLoop, Signal
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

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from GUI.theme import ThemedNavigationToolbar


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
            "hits":        detector_pipeline.hit_plotter,
            "events": detector_pipeline.event_plotter,
            "beam_monitor":       bm_pipeline.event_plotter if bm_pipeline else None,
        }
        self._containers = {
            "readouts":              detector_pipeline.readouts_container,
            "hits":           detector_pipeline.hits_container,
            "events":    detector_pipeline.events_container,
            "beam_monitor":          bm_pipeline.events_container if bm_pipeline else None,
            "beam_monitor_readouts": bm_pipeline.readouts_container if bm_pipeline else None,
        }

    def beam_monitor_present(self) -> bool:
        if self._plotters.get("beam_monitor") is None:
            return False
        _, fill_count = self.get_dataframe_array("beam_monitor")
        return fill_count > 0
    
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

    events = {"XY", "ToF vs XY", "Position per Tube"}  # always drawn
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
        "hits":        hits,
        "events": events,
        "beam_monitor":       beam_monitor,
    }


def launch_dashboard(detector_pipeline, bm_pipeline, parameters, theme_mode="dark"):
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
    from GUI import theme
    theme.apply_mpl_theme(theme_mode)

    bm_active = bool(bm_pipeline) and parameters.MONitor.MONOnOff
    if bm_active:
        bm_pipeline.build_plotter()

    app = QApplication.instance() or QApplication(sys.argv)

    # Keep CLI and GUI paths consistent: apply stylesheet to match theme_mode
    app.setStyleSheet(theme.build_stylesheet(theme_mode))

    def _show_section(unit_ids) -> MbutyDashboard:
        dashboard = build_dashboard_section(
            detector_pipeline, bm_pipeline, parameters, unit_ids, bm_active
        )
        if not dashboard.has_content:
            print('\tWARNING: no data in any tab (readouts/hits/events/BM all empty) '
                '-- skipping dashboard window for this section.')
            return dashboard

        dashboard.show()

        loop = QEventLoop()
        dashboard.closing.connect(loop.quit)
        loop.exec()
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

        if i == len(blocks) - 1:
            continue

        answer = input('press (enter) to continue to the next section, or (q + enter) to quit: ')
        if answer.strip().lower() == 'q':
            break
    return dashboard


def build_dashboard_section(detector_pipeline, bm_pipeline, parameters, unit_ids, bm_active) -> MbutyDashboard:
    """Builds (but does not show) a single dashboard window scoped to one
    block of unit_ids. Split out of launch_dashboard()'s internal loop so a
    GUI can drive section-by-section display itself (e.g. Next Section /
    Exit Plotting buttons) instead of relying on launch_dashboard()'s own
    blocking event loop -- that blocking loop is still what the CLI path in
    MBUTY.py uses, unchanged, via launch_dashboard() above.
    """
    detector_pipeline.build_plotters(unit_ids=unit_ids)
    data_source = OrchestratorDataSource(detector_pipeline, bm_pipeline if bm_active else None)
    selected = _selected_plot_names_by_tab(parameters)
    config = {
        "readouts_active_plots": [n for n in data_source.get_available_plots("readouts")
                                   if n in selected["readouts"]],
        "hits_active_plots":     [n for n in data_source.get_available_plots("hits")
                                   if n in selected["hits"]],
        "events_active_plots":   [n for n in data_source.get_available_plots("events")
                                   if n in selected["events"]],
        "bm_active_plots":       [n for n in data_source.get_available_plots("beam_monitor")
                                   if n in selected["beam_monitor"]],
    }
    dashboard = MbutyDashboard(data_source, config=config)
    dashboard.resize(1300, 800)
    return dashboard


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
        # Skip if empty or no valid data
        if self._fill_count == 0 or self._array.dtype.names is None or len(self._valid_rows) == 0:
            return

        self.layoutAboutToBeChanged.emit()
        
        # Get field name and extract values for active rows
        field_name = self._array.dtype.names[column]
        sort_values = self._array[field_name][self._valid_rows]
        
        # Use NumPy argsort for efficient sorting
        sorted_indices = np.argsort(sort_values)
        
        if order == Qt.DescendingOrder:
            sorted_indices = sorted_indices[::-1]
        
        # Reorder valid rows index map
        self._valid_rows = self._valid_rows[sorted_indices]
        
        self.layoutChanged.emit()

    def _compute_valid_rows(self) -> np.ndarray:
        # Return all row indices up to fill_count
        if self._fill_count == 0 or self._array.dtype.names is None:
            return np.empty(0, dtype=np.int64)
        return np.arange(self._fill_count, dtype=np.int64)

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
    view.setModel(model)
    view.setEditTriggers(QTableView.NoEditTriggers)
    view.setSelectionBehavior(QTableView.SelectRows)
    view.setAlternatingRowColors(True)
    view.setSortingEnabled(True)

    # Increase font size for better readability
    font = view.font()
    font.setPointSize(font.pointSize() + 1)
    view.setFont(font)
    view.horizontalHeader().setFont(font)

    # Fixed row height for O(1) layout performance on large datasets
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
    page_layout.addWidget(ThemedNavigationToolbar(canvas, page))
    page_layout.addWidget(canvas)
    data_source.render_plot(tab_key, plot_name, canvas.figure)
    canvas.draw_idle()
    return page, canvas


class TabSpec(NamedTuple):
    key: str
    title: str
    index_fields: tuple[str, ...]
    active_plots: tuple[str, ...]  # config-selected subset, fixed pre-run
    # Sub-tab title and data-source key (None = use tab's own key, except Beam Monitor which shows 2 containers)
    dataframe_tabs: tuple[tuple[str, str | None], ...] = (("Dataframe View", None),)


class InstrumentView(QWidget):
    """Sub-tabs are ordered plots-first, "Dataframe View" last -- the plots are
    what a physicist actually watches during a run; the dataframe is a
    debugging tool, more useful side-by-side in the Comparison Matrix than
    as this tab's default landing page.

    Only the sub-tab shown first is built synchronously. Rest fill in one at a time
    on the Qt event loop's idle turns (0ms QTimer chain) for lazy loading."""

    def __init__(self, spec: TabSpec, data_source: DashboardDataSource):
        super().__init__()
        self._data_source = data_source
        self._spec = spec

        # Layout: tab widget containing plots + dataframe
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Build plot tabs first (physics-relevant)
        self._plot_canvases: dict[str, FigureCanvasQTAgg] = {}
        for plot_name in spec.active_plots:
            page, canvas = _build_plot_pane(spec.key, plot_name, data_source)
            self._plot_canvases[plot_name] = canvas
            self._tabs.addTab(page, plot_name)

        # Add dataframe view last (debugging tool)
        for df_title, df_key in spec.dataframe_tabs:
            actual_key = spec.key if df_key is None else df_key
            view, model, _ = _build_dataframe_pane(spec.index_fields)
            array, fill_count = data_source.get_dataframe_array(actual_key)
            model.set_data(array, fill_count)
            self._tabs.addTab(view, df_title)

    def refresh_dataframe(self) -> None:
        # Refresh dataframe tabs only (plots are static)
        for df_title, df_key in self._spec.dataframe_tabs:
            actual_key = self._spec.key if df_key is None else df_key
            array, fill_count = self._data_source.get_dataframe_array(actual_key)
            # Find and update the corresponding tab's model
            tab_index = self._tabs.count() - len(self._spec.dataframe_tabs)
            for i, (title, _) in enumerate(self._spec.dataframe_tabs):
                idx = tab_index + i
                widget = self._tabs.widget(idx)
                if widget and hasattr(widget, 'model'):
                    widget.model().set_data(array, fill_count)


class ComparisonMatrixView(QWidget):
    """Multi-tab grid: each row is an instrument tab, each column shows a plot
    or the dataframe. All built eagerly (no lazy loading) since the matrix is
    not the default tab and users typically open it once to compare."""

    def __init__(self, data_source: DashboardDataSource, tab_specs: list[TabSpec]):
        super().__init__()
        self._data_source = data_source
        self._tab_specs = tab_specs
        self._dataframe_models: dict[str, StructuredArrayTableModel] = {}

        # Find all unique plots across all tabs
        all_plots = set()
        for spec in tab_specs:
            all_plots.update(spec.active_plots)
        plot_list = sorted(all_plots)

        # Build grid: rows = instruments, cols = plots + dataframe
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Column headers (plot names + "Dataframe")
        for col, plot_name in enumerate(plot_list, start=1):
            header = QLabel(plot_name)
            header.setStyleSheet("font-weight: bold; background: #e0e0e0; padding: 4px;")
            layout.addWidget(header, 0, col)

        dataframe_col = len(plot_list) + 1
        df_header = QLabel("Dataframe")
        df_header.setStyleSheet("font-weight: bold; background: #e0e0e0; padding: 4px;")
        layout.addWidget(df_header, 0, dataframe_col)

        # Row headers (instrument names) and grid cells
        for row, spec in enumerate(tab_specs, start=1):
            title_label = QLabel(spec.title)
            title_label.setStyleSheet("font-weight: bold; background: #f0f0f0; padding: 4px;")
            layout.addWidget(title_label, row, 0)

            # Add plot panes for this instrument
            for col, plot_name in enumerate(plot_list, start=1):
                if plot_name in spec.active_plots:
                    page, canvas = _build_plot_pane(spec.key, plot_name, data_source)
                    # Constrain plot size for compact grid display
                    page.setMaximumSize(400, 300)
                    layout.addWidget(page, row, col)
                else:
                    # Empty cell placeholder
                    spacer = QWidget()
                    spacer.setStyleSheet("background: #f8f8f8;")
                    layout.addWidget(spacer, row, col)

            # Add dataframe view for this instrument
            view, model, _ = _build_dataframe_pane(spec.index_fields)
            view.setMaximumSize(400, 300)
            array, fill_count = data_source.get_dataframe_array(spec.key)
            model.set_data(array, fill_count)
            self._dataframe_models[spec.key] = model
            layout.addWidget(view, row, dataframe_col)

        layout.setRowStretch(len(tab_specs) + 1, 1)
        layout.setColumnStretch(dataframe_col + 1, 1)

    def refresh_dataframes(self) -> None:
        # Refresh all dataframe panes after pipeline update
        for tab_key, model in self._dataframe_models.items():
            array, fill_count = self._data_source.get_dataframe_array(tab_key)
            model.set_data(array, fill_count)


class MbutyDashboard(QMainWindow):
    # Signal emitted when user closes window (QMainWindow.close() only hides by default)
    closing = Signal()

    def __init__(self, data_source: DashboardDataSource, config: dict, parent=None):
        super().__init__(parent)
        self._data_source = data_source
        self._config = config
        self.setWindowTitle("MBUTY Dashboard")

        self.main_tabs = QTabWidget()
        self.setCentralWidget(self.main_tabs)

        # Reverse-pipeline order: Events first (most plots, physics-relevant),
        # Readouts/Hits last (debugging). Tabs only added if pipeline has backing plotter with data.
        def _maybe_tab(key: str, title: str, index_cfg_key: str, active_cfg_key: str) -> TabSpec | None:
            available = data_source.get_available_plots(key)
            if not available:
                return None
            _, fill_count = data_source.get_dataframe_array(key)
            if fill_count == 0:
                return None
            return TabSpec(
                key, title,
                tuple(config.get(index_cfg_key, ())),
                tuple(config.get(active_cfg_key, available)),
            )

        tab_specs: list[TabSpec] = []
        for spec in (
            _maybe_tab("events", "Events", "events_index_fields", "events_active_plots"),
            _maybe_tab("hits", "Hits", "hits_index_fields", "hits_active_plots"),
            _maybe_tab("readouts", "Readouts", "readouts_index_fields", "readouts_active_plots"),
        ):
            if spec is not None:
                tab_specs.append(spec)

        # Beam Monitor on independent condition (separate pipeline, not pipeline stage)
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

        # Lazy build: InstrumentView constructed only when user clicks it
        self._tab_specs = tab_specs
        self._data_source = data_source
        self.views: dict[str, InstrumentView] = {}
        self._built_main: set[int] = set()

        # Empty run (no data, no BM stream) -> Comparison Matrix has nothing to show
        self.has_content = bool(tab_specs)

        for spec in tab_specs:
            self.main_tabs.addTab(QWidget(), spec.title)

        if self.has_content:
            self.comparison_view = ComparisonMatrixView(data_source, tab_specs)
            self.main_tabs.addTab(self.comparison_view, "Comparison Matrix")
        else:
            self.comparison_view = None

        self.main_tabs.currentChanged.connect(self._ensure_main_built)
        if self.has_content:
            self._ensure_main_built(0)

    def _ensure_main_built(self, index: int) -> None:
        if index < 0 or index in self._built_main:
            return  # removeTab() can emit currentChanged(-1)
        title = self.main_tabs.tabText(index)
        spec = next((s for s in self._tab_specs if s.title == title), None)
        if spec is None:
            return  # Comparison Matrix tab
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
        # Refresh dataframes only for tabs that have been opened
        for view in self.views.values():
            view.refresh_dataframe()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closing.emit()


class _DemoDataSource(DashboardDataSource):
    """Test data source for manual smoke-testing. Replace with real pipeline subclass."""
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
        arr["wire"][3] = -1        # sentinel: filtered out
        arr["adc"][7] = np.nan     # sentinel: filtered out
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