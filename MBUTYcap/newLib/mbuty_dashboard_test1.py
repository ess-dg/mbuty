"""
mbuty_results_dashboard.py
===========================
Clean PySide6 results dashboard: tabbed plots + comparison mode.

Architecture:
- Pure plot functions: plot_xxx(ax, data) → draw on ax
- PLOT_REGISTRY: register plots by data type (events, hits, readouts)
- Tabbed view: one tab per plot
- Comparison grid: select 2-4 plots, view side-by-side
- No patching, no complexity

Run with:
    pip install PySide6 matplotlib numpy pandas
    python mbuty_results_dashboard.py
"""

import sys
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableView, QLabel, QCheckBox, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt, QAbstractTableModel


# ============================================================================
# Fake data generators (swap for your real pipeline output)
# ============================================================================

RNG = np.random.default_rng(42)

def make_fake_events(n=20_000):
    """Events container (clustered, with physics coordinates)."""
    n1, n2 = int(n * 0.6), int(n * 0.4)
    return pd.DataFrame({
        'ID': RNG.choice([0, 1, 2], n),
        'wire_ch': np.concatenate([RNG.integers(0, 32, n1), RNG.integers(0, 32, n2)]),
        'strip_ch': np.concatenate([RNG.normal(30, 10, n1), RNG.normal(20, 8, n2)]),
        'posW_mm': np.concatenate([RNG.normal(-15, 8, n1), RNG.normal(20, 5, n2)]),
        'posS_mm': np.concatenate([RNG.normal(10, 12, n1), RNG.normal(-8, 6, n2)]),
        'energy': np.concatenate([RNG.normal(1200, 200, n1), RNG.normal(800, 150, n2)]),
        'tof': np.concatenate([RNG.normal(12_000, 1_500, n1), RNG.normal(18_000, 1_000, n2)]),
        'wavelength': np.concatenate([RNG.normal(1.8, 0.3, n1), RNG.normal(2.8, 0.4, n2)]),
    })

def make_fake_hits(n=5_000):
    """Hits container (mapped channels, pre-clustering)."""
    return pd.DataFrame({
        'ring': RNG.choice([0, 1, 2], n),
        'fen': RNG.choice([0, 1, 2], n),
        'hybrid': RNG.choice([0, 1], n),
        'wire_ch': RNG.integers(0, 32, n),
        'strip_ch': RNG.integers(0, 64, n),
        'adc0': np.abs(RNG.normal(512, 80, n)).astype(int),
        'adc1': np.abs(RNG.normal(512, 80, n)).astype(int),
        'tdc': RNG.integers(0, 4096, n),
    })

def make_fake_readouts(n=10_000):
    """Readouts container (raw ASIC output)."""
    return pd.DataFrame({
        'ring': RNG.choice([0, 1], n),
        'fen': RNG.choice([0, 1, 2], n),
        'hybrid': RNG.choice([0, 1], n),
        'asic': RNG.choice([0, 1], n),
        'channel': RNG.integers(0, 64, n),
        'adc': np.abs(RNG.normal(512, 100, n)).astype(int),
        'timestamp': RNG.integers(0, 1_000_000, n),
    })


# ============================================================================
# Plot functions (pure: (ax, data) → draws on ax)
# ============================================================================

def plot_detector_image(ax, events):
    """2D wire vs strip detector image."""
    h = ax.hist2d(events['posW_mm'], events['posS_mm'], bins=64, cmap='Blues')
    ax.set_xlabel('Wire position (mm)')
    ax.set_ylabel('Strip position (mm)')
    ax.set_title('Detector image')
    ax.figure.colorbar(h[3], ax=ax, label='Counts')

def plot_energy_spectrum(ax, events):
    """Pulse height spectrum."""
    ax.hist(events['energy'], bins=200, color='#2563eb', alpha=0.85)
    ax.set_xlabel('Energy (a.u.)')
    ax.set_ylabel('Counts')
    ax.set_title('Energy spectrum')

def plot_tof_spectrum(ax, events):
    """Time-of-flight spectrum."""
    ax.hist(events['tof'], bins=200, color='#2563eb', alpha=0.85)
    ax.set_xlabel('Time-of-flight (µs)')
    ax.set_ylabel('Counts')
    ax.set_title('ToF spectrum')

def plot_wavelength(ax, events):
    """Wavelength distribution."""
    ax.hist(events['wavelength'], bins=150, color='#7c3aed', alpha=0.85)
    ax.set_xlabel('Wavelength (Å)')
    ax.set_ylabel('Counts')
    ax.set_title('Wavelength distribution')

def plot_energy_vs_tof(ax, events):
    """2D energy vs ToF."""
    h = ax.hist2d(events['energy'], events['tof'], bins=100, cmap='viridis')
    ax.set_xlabel('Energy (a.u.)')
    ax.set_ylabel('ToF (µs)')
    ax.set_title('Energy vs ToF')
    ax.figure.colorbar(h[3], ax=ax, label='Counts')

def plot_wire_channel_spectrum(ax, events):
    """Wire channel occupancy."""
    ax.hist(events['wire_ch'], bins=32, color='#2563eb', alpha=0.85, edgecolor='black')
    ax.set_xlabel('Wire channel')
    ax.set_ylabel('Counts')
    ax.set_title('Wire channel occupancy')

def plot_strip_channel_spectrum(ax, events):
    """Strip channel occupancy."""
    ax.hist(events['strip_ch'], bins=64, color='#2563eb', alpha=0.85, edgecolor='black')
    ax.set_xlabel('Strip channel')
    ax.set_ylabel('Counts')
    ax.set_title('Strip channel occupancy')

def plot_multiplicity(ax, events):
    """Event multiplicity per unit."""
    mult = events.groupby('ID').size()
    ax.bar(mult.index, mult.values, color='#2563eb', alpha=0.85, edgecolor='black')
    ax.set_xlabel('Unit ID')
    ax.set_ylabel('Event count')
    ax.set_title('Multiplicity by unit')

# Hits-level plots
def plot_adc_distribution(ax, hits):
    """ADC value distribution (both ASICs)."""
    ax.hist(hits['adc0'], bins=100, alpha=0.6, color='#2563eb', label='ASIC 0')
    ax.hist(hits['adc1'], bins=100, alpha=0.6, color='#dc2626', label='ASIC 1')
    ax.set_xlabel('ADC value')
    ax.set_ylabel('Counts')
    ax.set_title('ADC distribution')
    ax.legend()

def plot_tdc_spectrum(ax, hits):
    """TDC (fine timing) spectrum."""
    ax.hist(hits['tdc'], bins=256, color='#7c3aed', alpha=0.85, edgecolor='black')
    ax.set_xlabel('TDC value')
    ax.set_ylabel('Counts')
    ax.set_title('TDC spectrum')

def plot_hits_per_hybrid(ax, hits):
    """Hits occupancy per hybrid."""
    hybrid_counts = hits.groupby(['ring', 'fen', 'hybrid']).size()
    labels = [f"R{r}F{f}H{h}" for r, f, h in hybrid_counts.index]
    ax.bar(range(len(labels)), hybrid_counts.values, color='#2563eb', alpha=0.85)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Hit count')
    ax.set_title('Hits per hybrid')

# Readouts-level plots
def plot_asic_channel_heatmap(ax, readouts):
    """Channel occupancy per ASIC."""
    asic0 = readouts[readouts['asic'] == 0].groupby('channel').size()
    asic1 = readouts[readouts['asic'] == 1].groupby('channel').size()
    
    x = np.arange(64)
    width = 0.35
    ax.bar(x - width/2, [asic0.get(i, 0) for i in x], width, label='ASIC 0', alpha=0.8)
    ax.bar(x + width/2, [asic1.get(i, 0) for i in x], width, label='ASIC 1', alpha=0.8)
    ax.set_xlabel('Channel')
    ax.set_ylabel('Readout count')
    ax.set_title('ASIC channel occupancy')
    ax.legend()
    ax.set_xticks(x[::8])

def plot_timestamp_distribution(ax, readouts):
    """Timestamp distribution (trigger times)."""
    ax.hist(readouts['timestamp'], bins=200, color='#2563eb', alpha=0.85)
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Counts')
    ax.set_title('Timestamp distribution')

def plot_readouts_per_hybrid(ax, readouts):
    """Readout count per hybrid."""
    hybrid_counts = readouts.groupby(['ring', 'fen', 'hybrid']).size()
    labels = [f"R{r}F{f}H{h}" for r, f, h in hybrid_counts.index]
    ax.bar(range(len(labels)), hybrid_counts.values, color='#2563eb', alpha=0.85)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('Readout count')
    ax.set_title('Readouts per hybrid')


# ============================================================================
# Plot registry: one entry per plot
# ============================================================================

PLOT_REGISTRY = {
    'events': [
        {'name': 'Detector image', 'fn': plot_detector_image},
        {'name': 'Energy spectrum', 'fn': plot_energy_spectrum},
        {'name': 'ToF spectrum', 'fn': plot_tof_spectrum},
        {'name': 'Wavelength', 'fn': plot_wavelength},
        {'name': 'Energy vs ToF', 'fn': plot_energy_vs_tof},
        {'name': 'Wire channels', 'fn': plot_wire_channel_spectrum},
        {'name': 'Strip channels', 'fn': plot_strip_channel_spectrum},
        {'name': 'Multiplicity', 'fn': plot_multiplicity},
    ],
    'hits': [
        {'name': 'ADC distribution', 'fn': plot_adc_distribution},
        {'name': 'TDC spectrum', 'fn': plot_tdc_spectrum},
        {'name': 'Hits per hybrid', 'fn': plot_hits_per_hybrid},
    ],
    'readouts': [
        {'name': 'ASIC channels', 'fn': plot_asic_channel_heatmap},
        {'name': 'Timestamp distribution', 'fn': plot_timestamp_distribution},
        {'name': 'Readouts per hybrid', 'fn': plot_readouts_per_hybrid},
    ],
}


# ============================================================================
# Plot canvas — single figure, toolbar, no complexity
# ============================================================================

class PlotCanvas(QWidget):
    """Embedded matplotlib canvas + toolbar."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(6, 4.5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.figure.add_subplot(111)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def draw_plot(self, plot_fn, data):
        """Clear and redraw with given function and data."""
        self.ax.clear()
        try:
            plot_fn(self.ax, data)
            self.figure.tight_layout()
        except Exception as e:
            self.ax.text(0.5, 0.5, f'Error: {str(e)}', ha='center', va='center')
        self.canvas.draw()


# ============================================================================
# Data table — raw DataFrame view for debugging
# ============================================================================

class DataFrameModel(QAbstractTableModel):
    def __init__(self, df=None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        value = self._df.iat[index.row(), index.column()]
        if isinstance(value, (float, np.floating)):
            return f'{value:.3f}'
        return str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section)


# ============================================================================
# Main dashboard window
# ============================================================================

class ResultsDashboard(QMainWindow):
    """
    Main window: organize results by data type.
    - Left: stack of tabs (plots for current data type)
    - Right: comparison panel (select 2-4 plots to view side-by-side)
    """

    def __init__(self, events=None, hits=None, readouts=None):
        super().__init__()
        self.setWindowTitle('MBUTY Results')
        self.resize(1600, 900)

        self.events = events or make_fake_events()
        self.hits = hits or make_fake_hits()
        self.readouts = readouts or make_fake_readouts()

        self.data_by_type = {
            'events': self.events,
            'hits': self.hits,
            'readouts': self.readouts,
        }

        # Current active data type
        self.current_type = 'events'
        self.comparison_plots = []  # Selected plot keys for comparison

        self.setup_ui()

    def setup_ui(self):
        """Main layout: tabs (left) + comparison controls (right)."""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # ===== LEFT: Data type tabs =====
        self.data_tabs = QTabWidget()
        for dtype in ['events', 'hits', 'readouts']:
            self.build_data_tab(dtype)
        self.data_tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.data_tabs, stretch=2)

        # ===== RIGHT: Comparison panel =====
        comparison_panel = self.build_comparison_panel()
        main_layout.addWidget(comparison_panel, stretch=1)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def build_data_tab(self, dtype):
        """Build a tab for one data type (events, hits, readouts)."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Top: data type title + info label
        info = QLabel(f'{dtype.title()} ({len(self.data_by_type[dtype]):,} rows)')
        info.setStyleSheet('color: #64748b; padding: 8px; font-size: 12px;')
        layout.addWidget(info)

        # Tabs for each plot in this data type
        plot_tabs = QTabWidget()
        for entry in PLOT_REGISTRY[dtype]:
            plot_key = f'{dtype}_{entry["name"].lower().replace(" ", "_")}'
            canvas = PlotCanvas()
            plot_tabs.addTab(canvas, entry['name'])
            
            # Store canvas for later reference
            setattr(canvas, 'plot_key', plot_key)
            setattr(canvas, 'plot_fn', entry['fn'])
            setattr(canvas, 'data_type', dtype)
            
            # Draw initial plot
            canvas.draw_plot(entry['fn'], self.data_by_type[dtype])

        layout.addWidget(plot_tabs, stretch=2)

        # Bottom: data table
        table_label = QLabel('Raw data (first 1000 rows)')
        table_label.setStyleSheet('color: #64748b; padding: 4px; font-size: 11px;')
        layout.addWidget(table_label)

        table_model = DataFrameModel(self.data_by_type[dtype].head(1000))
        table = QTableView()
        table.setModel(table_model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.NoEditTriggers)
        layout.addWidget(table, stretch=1)

        self.data_tabs.addTab(container, dtype.title())

    def build_comparison_panel(self):
        """Right-side panel: select plots to compare side-by-side."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel('Comparison')
        title.setStyleSheet('font-weight: 600; font-size: 13px; color: #0f172a; padding: 8px 0;')
        layout.addWidget(title)

        # Checkboxes for each plot
        self.plot_checkboxes = {}
        all_plots = []
        for dtype in ['events', 'hits', 'readouts']:
            for entry in PLOT_REGISTRY[dtype]:
                key = f'{dtype}_{entry["name"].lower().replace(" ", "_")}'
                all_plots.append((key, dtype, entry['name']))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        checkbox_container = QWidget()
        checkbox_layout = QVBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(4)

        for key, dtype, name in all_plots:
            cb = QCheckBox(f'{name} ({dtype})')
            cb.setStyleSheet('font-size: 11px; color: #334155;')
            cb.stateChanged.connect(self.on_comparison_selection_changed)
            self.plot_checkboxes[key] = (cb, dtype)
            checkbox_layout.addWidget(cb)

        checkbox_layout.addStretch()
        scroll.setWidget(checkbox_container)
        layout.addWidget(scroll, stretch=1)

        # Buttons
        layout.addSpacing(12)
        show_btn = QPushButton('Show Comparison')
        show_btn.setStyleSheet('padding: 6px; font-size: 12px; background: #2563eb; color: white; border: none; border-radius: 4px;')
        show_btn.clicked.connect(self.show_comparison_grid)
        layout.addWidget(show_btn)

        return panel

    def on_tab_changed(self, index):
        """Track which data type tab is active."""
        self.current_type = list(self.data_by_type.keys())[index]

    def on_comparison_selection_changed(self):
        """Update list of selected plots."""
        self.comparison_plots = [key for key, (cb, _) in self.plot_checkboxes.items() if cb.isChecked()]
        # Limit to 4
        if len(self.comparison_plots) > 4:
            self.comparison_plots = self.comparison_plots[:4]

    def show_comparison_grid(self):
        """Show selected plots in a side-by-side grid window."""
        if not self.comparison_plots:
            return

        # Create new window
        comp_window = QWidget()
        comp_window.setWindowTitle('Comparison')
        comp_window.resize(1400, 800)

        layout = QVBoxLayout(comp_window)

        # Calculate grid layout (1, 2, 2x2, or 2x2)
        n = len(self.comparison_plots[:4])
        if n == 1:
            grid_layout = QVBoxLayout()
        elif n == 2:
            grid_layout = QHBoxLayout()
        elif n == 3:
            grid_layout = QHBoxLayout()
        else:  # n >= 4
            grid_layout = QVBoxLayout()
            
        # Add plot canvases
        row_layout = QHBoxLayout()
        col_count = 0
        max_cols = 2 if n > 2 else n

        for i, plot_key in enumerate(self.comparison_plots[:4]):
            # Determine data type and plot function
            dtype = plot_key.split('_')[0]
            plot_name = plot_key.replace(f'{dtype}_', '').replace('_', ' ').title()
            
            # Find the plot function
            plot_fn = None
            for entry in PLOT_REGISTRY[dtype]:
                if entry['name'].lower() == plot_name.lower():
                    plot_fn = entry['fn']
                    break
            
            if plot_fn is None:
                continue

            # Create canvas and draw
            canvas = PlotCanvas()
            canvas.draw_plot(plot_fn, self.data_by_type[dtype])
            row_layout.addWidget(canvas)
            col_count += 1

            # Wrap to next row if needed
            if col_count >= max_cols or i == len(self.comparison_plots[:4]) - 1:
                grid_layout.addLayout(row_layout)
                row_layout = QHBoxLayout()
                col_count = 0

        layout.addLayout(grid_layout)
        comp_window.setLayout(layout)
        comp_window.show()

        # Keep reference to avoid garbage collection
        self._comparison_windows = getattr(self, '_comparison_windows', [])
        self._comparison_windows.append(comp_window)


# ============================================================================
# Entry point
# ============================================================================

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = ResultsDashboard()
    dashboard.show()
    sys.exit(app.exec())