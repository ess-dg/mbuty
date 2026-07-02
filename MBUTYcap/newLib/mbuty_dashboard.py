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

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import (
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


# --------------------------------------------------------------------------
# Table model: structured numpy array -> QTableView, with the validity gate
# --------------------------------------------------------------------------

class StructuredArrayTableModel(QAbstractTableModel):
    """Read-only view over array[:fill_count], filtered by:
       - NaN on any floating-point field (math noise sentinel)
       - < 0 on any field listed in index_fields (uninitialized -1 sentinel)
    Never re-sorts; upstream stable-sort order is preserved in the source
    model. Header-click sorting is applied on top via QSortFilterProxyModel
    in _build_dataframe_pane(), so it never touches this array or order.
    """

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

    def _compute_valid_rows(self) -> np.ndarray:
        if self._fill_count == 0 or self._array.dtype.names is None:
            return np.empty(0, dtype=np.int64)
        view = self._array[: self._fill_count]
        mask = np.ones(self._fill_count, dtype=bool)
        for name in view.dtype.names:
            col = view[name]
            if np.issubdtype(col.dtype, np.floating):
                mask &= ~np.isnan(col)
            if name in self._index_fields:
                mask &= col >= 0
        return np.nonzero(mask)[0]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._valid_rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._array.dtype.names is None:
            return 0
        return len(self._array.dtype.names)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._valid_rows[index.row()]
        field = self._array.dtype.names[index.column()]
        value = self._array[field][row]
        if role == Qt.DisplayRole:
            if isinstance(value, np.floating):
                return f"{value:.6g}"
            return str(value)
        if role == Qt.EditRole:
            # Raw typed value, used as the sort key by the proxy model.
            return value.item() if hasattr(value, "item") else value
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._array.dtype.names[section]
        return str(section)


def _build_dataframe_pane(index_fields: Iterable[str]) -> tuple[QWidget, StructuredArrayTableModel, QTableView]:
    """Single reusable factory for a sortable, read-only dataframe view.
    Used both by each instrument tab's 'Dataframe View' sub-tab and by the
    Comparison Matrix when a 'Dataframe View' item is selected.
    """
    model = StructuredArrayTableModel(index_fields=index_fields)
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.setSortRole(Qt.EditRole)

    view = QTableView()
    view.setModel(proxy)
    view.setEditTriggers(QTableView.NoEditTriggers)
    view.setSelectionBehavior(QTableView.SelectRows)
    view.setAlternatingRowColors(True)
    view.setSortingEnabled(True)  # click header to sort; source array/order untouched

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


# --------------------------------------------------------------------------
# One instrument tab: flat sub-tabs — Dataframe View + one per active plot.
# No checkboxes, no runtime add/remove. Set once from config at construction.
# --------------------------------------------------------------------------

class InstrumentView(QWidget):
    def __init__(self, spec: TabSpec, data_source: DashboardDataSource, parent=None):
        super().__init__(parent)
        self._tab_key = spec.key
        self._data_source = data_source

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        df_pane, self.table_model, self.table_view = _build_dataframe_pane(spec.index_fields)
        self.sub_tabs.addTab(df_pane, "Dataframe View")

        self._plot_canvases: dict[str, FigureCanvasQTAgg] = {}
        for plot_name in spec.active_plots:
            page, canvas = _build_plot_pane(self._tab_key, plot_name, data_source)
            self._plot_canvases[plot_name] = canvas
            self.sub_tabs.addTab(page, plot_name)

    def refresh_dataframe(self) -> None:
        array, fill_count = self._data_source.get_dataframe_array(self._tab_key)
        self.table_model.set_data(array, fill_count)


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

            df_key = (spec.key, self.DATAFRAME_ITEM)
            df_cb = QCheckBox(self.DATAFRAME_ITEM)
            df_cb.toggled.connect(self._on_toggle)
            panel_layout.addWidget(df_cb)
            self._checkboxes[df_key] = df_cb

            # Comparison Matrix lists every plot the pipeline supports for
            # this tab, not just the config-selected subset shown in the
            # instrument tab itself.
            for plot_name in data_source.get_available_plots(spec.key):
                item_key = (spec.key, plot_name)
                cb = QCheckBox(plot_name)
                cb.toggled.connect(self._on_toggle)
                panel_layout.addWidget(cb)
                self._checkboxes[item_key] = cb

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
        tab_specs: list[TabSpec] = [
            TabSpec(
                "readouts", "Readouts",
                tuple(config.get("readouts_index_fields", ())),
                tuple(config.get("readouts_active_plots", data_source.get_available_plots("readouts"))),
            ),
            TabSpec(
                "mapped_hits", "Mapped Hits",
                tuple(config.get("hits_index_fields", ())),
                tuple(config.get("hits_active_plots", data_source.get_available_plots("mapped_hits"))),
            ),
            TabSpec(
                "coincidence_events", "Coincidence Events",
                tuple(config.get("events_index_fields", ())),
                tuple(config.get("events_active_plots", data_source.get_available_plots("coincidence_events"))),
            ),
        ]
        if data_source.beam_monitor_present():
            tab_specs.append(TabSpec(
                "beam_monitor", "Beam Monitor",
                tuple(config.get("bm_index_fields", ())),
                tuple(config.get("bm_active_plots", data_source.get_available_plots("beam_monitor"))),
            ))

        self.views: dict[str, InstrumentView] = {}
        for spec in tab_specs:
            view = InstrumentView(spec, data_source)
            self.views[spec.key] = view
            self.main_tabs.addTab(view, spec.title)

        self.comparison_view = ComparisonMatrixView(data_source, tab_specs)
        self.main_tabs.addTab(self.comparison_view, "Comparison Matrix")

        self.refresh_all_dataframes()

    def refresh_all_dataframes(self) -> None:
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