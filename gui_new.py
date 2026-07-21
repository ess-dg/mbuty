# -*- coding: utf-8 -*-
"""
main_window.py
"""
import os
import sys
import ctypes
import threading

import matplotlib.pyplot as plt

from qtpy.QtCore import Qt, QObject, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QToolButton, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QScrollArea,
    QSlider, QSplitter, QMessageBox, QSizePolicy,
)

from gui_qt.expandable_section import ExpandableSection
from gui_qt.console_widgets import ANSIConsole, ConsoleWriter
from gui_qt import theme
from gui_qt import gui_utils
from gui_qt.gui_config import config, parameters
from MBUTY import MBUTYOrchestrator
from lib import terminal as ta


class _MainThreadDispatcher(QObject):
    """
    Thread-safe replacement for the Tk main_thread_queue + after(100)
    polling loop. Any worker thread can call `dispatcher.post(fn)`; `fn`
    always runs on the GUI thread, because the connection below is a
    Qt.QueuedConnection - Qt itself marshals the call across threads via
    its event loop. No queue object, no polling interval to tune.
    """
    _run_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self._run_requested.connect(self._run, Qt.QueuedConnection)

    def post(self, fn):
        self._run_requested.emit(fn)

    @staticmethod
    def _run(fn):
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()


class MBUTYMainWindow(QMainWindow):
    """Main application window for the MBUTY GUI."""

    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager

        self.analysis_running = False
        self.backend_thread = None
        self.widgets = {}
        self.current_subprocess_handle = None
        self.original_stdout = sys.stdout
        self.dispatcher = _MainThreadDispatcher()
        self.after_widgets_created_tasks = []

        self.console = None
        self.console_writer = None
        self.output_panel = None
        self.stop_button = None
        self.next_section_button = None
        self.exit_plotting_button = None
        self.run_button = None
        self.buttons_row = None

        # Section flow state -- drives both the dashboard and loose-plot
        # "plot in sections" paths through one shared controller. See
        # _start_section_flow / _show_current_section below.
        self._section_blocks = []
        self._section_idx = 0
        self._section_mode = None       # 'dashboard' or 'loose'
        self._section_backend = None
        self._current_dashboard = None
        self._advancing = False         # guards the reentrant case where
                                         # closing the dashboard ourselves
                                         # (Next Section / Exit Plotting)
                                         # would otherwise re-trigger
                                         # _on_section_window_closed

        self.setWindowTitle("MBUTY GUI")
        self.resize(680, 720)  # Snug default fit for parameter panel on startup

        self._build_ui()

    # ------------------------------------------------------------------
    # Top-level layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        outer.addWidget(self._build_header())

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        outer.addWidget(divider)

        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        
        param_panel = self._build_parameter_panel()
        self.content_splitter.addWidget(param_panel)
        
        self.output_panel = self._build_output_panel()
        self.output_panel.setVisible(False)
        self.content_splitter.addWidget(self.output_panel)
        
        # Allow interactive resizing of both panels
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([580, 600])
        
        outer.addWidget(self.content_splitter, stretch=1)

        outer.addWidget(self._build_run_controls())

        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear()

        info_btn = QToolButton(self)
        info_btn.setText("info")
        info_btn.clicked.connect(self.show_about_dialog)
        self.statusBar().addPermanentWidget(info_btn)

    def _build_header(self):
        header = QWidget()
        layout = QGridLayout(header)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 1)

        current_path = os.path.abspath(os.path.dirname(__file__))

        left_logo_path = os.path.join(current_path, "gui_qt", "logos", "DetGlogo.png")
        left_logo = QLabel()
        pix = QPixmap(left_logo_path)
        if not pix.isNull():
            left_logo.setPixmap(pix.scaled(120, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            print(f"Left logo not found: {left_logo_path}")
        layout.addWidget(left_logo, 0, 0, Qt.AlignLeft)

        user_name = os.environ.get("USER", os.environ.get("USERNAME", "User"))
        title = QLabel(f"Ciao {user_name}! Welcome to MBUTY 8.0")
        title.setProperty("role", "header")
        title.setStyleSheet("color: #228B22;")  # forest green, matches the Tk version's fg
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, 0, 1, Qt.AlignCenter)

        right_logo_path = os.path.join(current_path, "gui_qt", "logos", "MBUTYlogo.png")
        right_logo = QLabel()
        pix2 = QPixmap(right_logo_path)
        if not pix2.isNull():
            right_logo.setPixmap(pix2.scaled(120, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            print(f"Right logo not found: {right_logo_path}")
        layout.addWidget(right_logo, 0, 2, Qt.AlignRight)

        # Theme toggle - new, since ThemeManager existed but nothing in the UI drove it yet
        theme_btn = QToolButton()
        theme_btn.setText("\u263d")  # crescent moon
        theme_btn.setToolTip("Toggle light/dark mode")
        theme_btn.clicked.connect(self.theme_manager.toggle)
        layout.addWidget(theme_btn, 1, 2, Qt.AlignRight)

        return header

    # ------------------------------------------------------------------
    # Parameter panel (left)
    # ------------------------------------------------------------------
    def _build_parameter_panel(self):
        group = QGroupBox("Parameters")
        # Allow expanding beyond 580px, but keep 580px as the snug minimum
        group.setMinimumWidth(580)
        group_layout = QVBoxLayout(group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        group_layout.addWidget(scroll)

        # Font-size control row
        font_row = QWidget()
        font_row_layout = QHBoxLayout(font_row)
        font_row_layout.setContentsMargins(0, 0, 0, 8)
        font_row_layout.addWidget(QLabel("Font Size:"))
        font_slider = QSlider(Qt.Horizontal)
        font_slider.setMinimum(8)
        font_slider.setMaximum(18)
        font_slider.setValue(theme.FONT_SIZE_BASE)
        font_size_label = QLabel(f"{theme.FONT_SIZE_BASE} pt")
        font_slider.valueChanged.connect(lambda v: font_size_label.setText(f"{v} pt"))
        font_slider.sliderReleased.connect(lambda: self._apply_font_size(font_slider.value()))
        font_row_layout.addWidget(font_slider)
        font_row_layout.addWidget(font_size_label)
        font_row_layout.addStretch(1)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(6, 6, 6, 6)
        inner_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        inner_layout.addWidget(font_row)

        static_section = QWidget()
        static_layout = QGridLayout(static_section)
        static_layout.setContentsMargins(0, 0, 0, 0)
        static_layout.setHorizontalSpacing(10)
        static_layout.setColumnStretch(0, 0)
        static_layout.setColumnStretch(1, 1)

        row = 0
        for key, item in config["static"].items():
            row = self._display_param(static_section, key, item, row)
        inner_layout.addWidget(static_section)

        # Wire custom sync-data button
        config["static"]["syncDataButton"]["command"] = self.custom_sync_data

        for section_name, section_items in config.items():
            if section_name == "static":
                continue
            section = ExpandableSection(inner, section_name.replace("_", " ").title() + " Parameters")
            section_body = QWidget()
            section_layout = QGridLayout(section_body)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setHorizontalSpacing(10)
            section_layout.setColumnStretch(0, 0)
            section_layout.setColumnStretch(1, 1)
            section.content_layout.addWidget(section_body)

            row = 0
            for key, item in section_items.items():
                row = self._display_param(section_body, key, item, row)
            inner_layout.addWidget(section)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        return group

    def _display_param(self, frame, key, item, row):
        """Create one widget from config, wire dependsOn visibility and
        dynamic options, and register it in self.widgets."""
        input_type = item["type"]
        depends_on = item.get("dependsOn")

        widget_instance, row_widget, updated_row = gui_utils.create_gui_widget(frame, key, item, row)
        if widget_instance is None:
            return updated_row

        self.widgets[key] = widget_instance

        if depends_on:
            widget_instance.should_show = lambda: gui_utils.should_show(depends_on, self.widgets)
            gui_utils.setup_visibility_resolver(row_widget, depends_on, self.widgets)

        if input_type in ("dropdown", "multiSelect"):
            dynamic_path_key = item.get("optionsFromPath")
            file_filter = item.get("fileTypeFilter")
            if dynamic_path_key and file_filter:
                self.after_widgets_created_tasks.append(
                    lambda w=widget_instance, dpk=dynamic_path_key, ff=file_filter:
                        gui_utils.setup_dynamic_file_options(w, self.widgets.get(dpk), ff)
                )
            elif "dynamicOptions" in item and "watchKeys" in item:
                self.after_widgets_created_tasks.append(
                    lambda w=widget_instance, dyn_opt=item["dynamicOptions"], wk=item["watchKeys"]:
                        gui_utils.setup_dynamic_option_resolver(w, dyn_opt, self.widgets, wk)
                )

        return updated_row

    def _apply_font_size(self, new_size):
        theme.FONT_SIZE_BASE = new_size
        self.theme_manager.apply(self.theme_manager.mode)

    # ------------------------------------------------------------------
    # Output panel (right) - hidden until an analysis/sync starts
    # ------------------------------------------------------------------
    def _build_output_panel(self):
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        zoom_row = QWidget()
        zoom_layout = QHBoxLayout(zoom_row)
        zoom_layout.setContentsMargins(0, 0, 0, 4)
        zoom_layout.addWidget(QLabel("Zoom:"))
        zoom_slider = QSlider(Qt.Horizontal)
        zoom_slider.setMinimum(8)
        zoom_slider.setMaximum(20)
        zoom_slider.setValue(theme.FONT_SIZE_CONSOLE)
        zoom_layout.addWidget(zoom_slider, stretch=1)
        layout.addWidget(zoom_row)

        console_label = QLabel("Console Output")
        console_label.setProperty("role", "header")
        layout.addWidget(console_label)

        self.console = ANSIConsole(theme_manager=self.theme_manager)
        zoom_slider.valueChanged.connect(
            lambda v: self.console.setFont(theme.mono_font(v))
        )
        layout.addWidget(self.console, stretch=1)

        self.console_writer = ConsoleWriter(original_stdout=self.original_stdout)
        self.console_writer.text_written.connect(self.console.write, Qt.QueuedConnection)

        return group

    def _setup_output_console(self, clear_content=True):
        if not self.output_panel.isVisible():
            self.output_panel.setVisible(True)
            # Expand main window dynamically to accommodate output console side-by-side
            if self.width() < 1100:
                self.resize(1200, self.height())
            self.content_splitter.setSizes([580, 600])

        if clear_content:
            self.console.clear_console()
        sys.stdout = self.console_writer

    # ------------------------------------------------------------------
    # Run / Stop / Close-plots controls
    # ------------------------------------------------------------------
    def _build_run_controls(self):
        row = QWidget()
        layout = QHBoxLayout(row)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_analysis)
        layout.addWidget(self.run_button)

        self.buttons_row = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_row)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_back_end)
        self.stop_button.setVisible(False)
        buttons_layout.addWidget(self.stop_button)

        self.next_section_button = QPushButton("Next Section")
        self.next_section_button.clicked.connect(self._next_section)
        self.next_section_button.setVisible(False)
        buttons_layout.addWidget(self.next_section_button)

        self.exit_plotting_button = QPushButton("Exit Plotting")
        self.exit_plotting_button.clicked.connect(self._exit_plotting)
        self.exit_plotting_button.setVisible(False)
        buttons_layout.addWidget(self.exit_plotting_button)

        layout.addWidget(self.buttons_row)
        layout.addStretch(1)
        return row

    # ------------------------------------------------------------------
    # Stop handling (unchanged from the Tk version - this is a plain
    # threading.Thread issue, not a Tk-vs-Qt one, so the ctypes-based
    # async KeyboardInterrupt injection still applies as-is)
    # ------------------------------------------------------------------
    def _raise_keyboard_interrupt(self, thread):
        if not thread or not thread.is_alive():
            return
        tid = ctypes.c_long(thread.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(KeyboardInterrupt))
        if res == 0:
            raise ValueError("Invalid thread ID")
        elif res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_back_end(self):
        print("\n\nStop operation requested by user.")

        if self.backend_thread and self.backend_thread.is_alive():
            try:
                self._raise_keyboard_interrupt(self.backend_thread)
                print("Stop signal sent to backend thread.")
            except Exception as e:
                print(f"Failed to stop backend thread: {e}")

        if self.current_subprocess_handle and self.current_subprocess_handle.poll() is None:
            print("Terminating active external process...")
            try:
                self.current_subprocess_handle.terminate()
                self.current_subprocess_handle.wait(timeout=5)
                if self.current_subprocess_handle.poll() is None:
                    print("Process did not terminate gracefully, sending SIGKILL.")
                    self.current_subprocess_handle.kill()
            except Exception as e:
                print(f"Error while trying to terminate process: {e}")
            finally:
                self.current_subprocess_handle = None

        self.analysis_running = False

    # ------------------------------------------------------------------
    # Data sync
    # ------------------------------------------------------------------
    def custom_sync_data(self):
        source_path = self.widgets.get("parameters.fileManagement.sourcePath").get()
        dest_path = self.widgets.get("parameters.fileManagement.destPath").get()

        if not source_path or not dest_path:
            QMessageBox.critical(self, "Error", "Please enter both source and destination paths before syncing.")
            return

        if self.analysis_running:
            QMessageBox.critical(
                self, "Please Wait",
                "An analysis or sync operation is already running.\nPlease wait for it to finish before starting another.",
            )
            return

        self.analysis_running = True
        self.buttons_row.setVisible(True)
        self.stop_button.setVisible(True)

        self._setup_output_console(clear_content=False)
        print("\nStarting data synchronization...\n")

        def sync_work():
            try:
                transfer_data = ta.transferDataUtil()
                status = transfer_data.syncData(source_path, dest_path)

                if status == 0:
                    self.dispatcher.post(
                        lambda: QMessageBox.information(self, "Sync Complete", "Data synced successfully.")
                    )
                    if self.stop_button.isVisible():
                        self.dispatcher.post(lambda: self.stop_button.setVisible(False))
                else:
                    self.dispatcher.post(
                        lambda: QMessageBox.critical(
                            self, "Sync Failed",
                            "Data synchronization failed or was interrupted. Check console output.",
                        )
                    )

                dropdown_widget = self.widgets.get("parameters.fileManagement.fileName")
                if dropdown_widget and hasattr(dropdown_widget, "_update_file_list"):
                    self.dispatcher.post(dropdown_widget._update_file_list)

            except Exception as e:
                print(f" Error during data synchronization (in sync_work): {e}")
                self.dispatcher.post(
                    lambda exc=e: QMessageBox.critical(self, "Sync Error", f"An error occurred during sync: {exc}")
                )
            finally:
                self.analysis_running = False

        self.backend_thread = threading.Thread(target=sync_work, daemon=True)
        self.backend_thread.start()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def run_analysis(self):
        if self.analysis_running:
            QMessageBox.warning(
                self, "Please Wait",
                "An analysis is already running.\nPlease wait for it to finish before starting another.",
            )
            return
        self.analysis_running = True

        missing = []
        selected = {}
        for key, widget in self.widgets.items():
            if hasattr(widget, "should_show") and not widget.should_show():
                continue
            if not hasattr(widget, "get"):
                continue
            value = widget.get()
            if value in ("", None, []):
                label = key
                for section in config.values():
                    if key in section:
                        label = section[key].get("label", key)
                        break
                missing.append(label)
            else:
                selected[key] = value

        if missing:
            QMessageBox.critical(self, "Missing Fields", "Please fill in or correct:\n- " + "\n- ".join(missing))
            self.analysis_running = False
            return

        for key, value in selected.items():
            for section_dict in config.values():
                if key in section_dict:
                    setter = section_dict[key].get("set")
                    if setter:
                        setter(value)
                    break

        self.buttons_row.setVisible(True)
        self.stop_button.setVisible(True)
        self._setup_output_console(clear_content=True)
        plt.close("all")

        backend = MBUTYOrchestrator(parameters, plottingOnOff="gui", main_thread_queue=self.dispatcher)

        def backend_work():
            try:
                print("\nRunning Master Ingestion Pipeline...\n")
                backend.run_pipeline()
                print("\nAnalysis complete. Dispatching plots to main thread...")

                self.dispatcher.post(lambda: self._start_section_flow(backend))

                if self.stop_button.isVisible():
                    self.dispatcher.post(lambda: self.stop_button.setVisible(False))
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    print("\nAnalysis was interrupted by user.")
                else:
                    print(f" Error during analysis: {e}")
            finally:
                self.analysis_running = False

        self.backend_thread = threading.Thread(target=backend_work, daemon=True)
        self.backend_thread.start()

    # ------------------------------------------------------------------
    # Section flow: one controller for both dashboard and loose-plot
    # modes. Next Section / Exit Plotting drive everything from here;
    # closing the dashboard's own window (the X button) is treated
    # identically to clicking Next Section -- see
    # _on_section_window_closed. There is no blocking loop anywhere in
    # this path, unlike the old modal QMessageBox / nested QEventLoop
    # approaches, so the plot windows stay fully interactive between
    # sections.
    # ------------------------------------------------------------------
    def _start_section_flow(self, backend):
        # apply_mpl_theme() sets the matplotlib rcParams every Figure picks
        # up (background/text colors) and patches the Qt toolbar class so
        # icons get tinted to match -- previously this only ran inside
        # launch_dashboard(), which this controller bypasses (it calls
        # build_dashboard_section directly), so theming silently stopped
        # applying to both the dashboard and the loose-plot path. Must
        # happen before any Figure/canvas/toolbar is built below.
        theme.apply_mpl_theme(self.theme_manager.mode)

        self._section_backend = backend
        self._section_mode = "dashboard" if parameters.plotting.useDashboard else "loose"
        self._current_dashboard = None
        self._section_idx = 0

        if backend.detector_pipeline:
            self._section_blocks = backend.detector_pipeline.get_unit_id_blocks()
        else:
            self._section_blocks = []

        bm_active = bool(backend.bm_pipeline) and parameters.MONitor.MONOnOff
        if self._section_mode == "dashboard" and bm_active:
            backend.bm_pipeline.build_plotter()  # construction only; BM isn't sectioned

        has_anything = bool(self._section_blocks) or bm_active
        self.next_section_button.setVisible(len(self._section_blocks) > 1)
        self.exit_plotting_button.setVisible(has_anything)
        self._show_current_section()

    def _show_current_section(self):
        blocks = self._section_blocks
        backend = self._section_backend

        if self._section_idx >= len(blocks):
            self._finish_sections()
            return

        block = blocks[self._section_idx]
        if len(blocks) > 1:
            print(f"\n\tSection {self._section_idx + 1}/{len(blocks)} "
                  f"-- unit IDs {block[0]} to {block[-1]}.")

        if self._section_mode == "dashboard":
            try:
                from lib.mbuty_dashboard import build_dashboard_section
                bm_active = bool(backend.bm_pipeline) and parameters.MONitor.MONOnOff
                dashboard = build_dashboard_section(
                    backend.detector_pipeline, backend.bm_pipeline, parameters, block, bm_active
                )
                dashboard.closing.connect(self._on_section_window_closed)
                self._current_dashboard = dashboard
                dashboard.show()
                dashboard.raise_()
                dashboard.activateWindow()
                return
            except Exception as e:
                print(f" Dashboard failed ({e}) -- falling back to standard plotting.")
                self._section_mode = "loose"
                # fall through to the loose-plot branch below for this section

        backend.detector_pipeline.plot_section(block)
        plt.draw()
        try:
            fig = plt.gcf()
            if fig and fig.canvas:
                fig.canvas.draw_idle()
                if fig.canvas.manager:
                    fig.canvas.manager.window.raise_()
                    fig.canvas.manager.window.activateWindow()
        except Exception:
            pass
        plt.show(block=False)

        if self._section_idx == 0 and backend.bm_pipeline and parameters.MONitor.MONOnOff:
            backend.bm_pipeline.plot()

    def _on_section_window_closed(self):
        """The dashboard's own close (X button) is treated identically to
        clicking Next Section. _advancing guards the reentrant case: if
        Next Section (or Exit Plotting) triggered this close() itself,
        skip -- otherwise a single button click would advance twice."""
        if self._advancing:
            return
        self._next_section()

    def _next_section(self):
        self._advancing = True
        try:
            if self._current_dashboard is not None:
                self._current_dashboard.close()
                self._current_dashboard = None
            else:
                plt.close("all")
            self._section_idx += 1
        finally:
            self._advancing = False
        self._show_current_section()

    def _exit_plotting(self):
        self._advancing = True
        try:
            if self._current_dashboard is not None:
                self._current_dashboard.close()
                self._current_dashboard = None
            plt.close("all")
        finally:
            self._advancing = False
        self._finish_sections()

    def _finish_sections(self):
        self.next_section_button.setVisible(False)
        self.exit_plotting_button.setVisible(False)
        self._section_blocks = []
        self._section_idx = 0
        self._section_backend = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def show_about_dialog(self):
        version = "8.0 (July 14, 2026)"
        author = "Francesco Piscitelli, Sheila Monera Cabarique"
        about_text = (
            f"MBUTY GUI Analysis Suite\n"
            f"--------------------------\n"
            f"Version: {version}\n"
            f"Authors: {author}\n"
            f"mail: francesco.piscitelli@ess.eu\n\n"
            f"Created: June 13, 2021\n"
            f"Description: Utility Tool for Analysis. Supports readers for all data formats: "
            f"VMM, BM, R5560 and SKADI. Supports detectors MB (TBL, ESTIA, FREIA), MG (TREX), "
            f"He3 tubes (TBL, CSPEC, BIFROST, MIRACLES and VESPA)."
        )
        QMessageBox.information(self, "About MBUTY", about_text)

    def closeEvent(self, event):
        self.stop_back_end()
        if self._current_dashboard is not None:
            self._current_dashboard.close()
            self._current_dashboard = None
        plt.close("all")
        sys.stdout = self.original_stdout
        super().closeEvent(event)


def main():
    import sys as _sys
    from qtpy.QtWidgets import QApplication

    app = QApplication(_sys.argv)
    theme_manager = theme.ThemeManager(app, mode="dark")
    window = MBUTYMainWindow(theme_manager)
    window.show()
    _sys.exit(app.exec())


if __name__ == "__main__":
    main()