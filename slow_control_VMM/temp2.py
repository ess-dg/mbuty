

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 30/09/2026

@author: francescopiscitelli
"""

import sys
import os

from qtpy.QtCore import Qt, QObject, Signal
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QToolButton,
    QSlider,
    QPlainTextEdit,
    QSplitter,
    QScrollArea,
    QFrame,
    QSizePolicy,
)

# Project imports
from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options

try:
    from GUI import theme
except ImportError:
    class ThemeMock:
        ROW_SPACING = 10
        FONT_SIZE_HEADER = 14
        FONT_SIZE_BASE = 10
        FONT_SIZE_CONSOLE = 9

        def __init__(self, app, mode="dark"):
            self.app = app
            self.mode = mode

        def toggle(self):
            self.mode = "light" if self.mode == "dark" else "dark"
            self.apply(self.mode)

        def apply(self, mode):
            self.mode = mode

        @staticmethod
        def base_font(size=10, bold=False):
            from qtpy.QtGui import QFont
            f = QFont("Arial", size)
            f.setBold(bold)
            return f

        @staticmethod
        def mono_font(size=9):
            from qtpy.QtGui import QFont
            return QFont("Monospace", size)

    theme = ThemeMock

currentPath = os.path.abspath(os.path.dirname(__file__))

ui_config = {
    "section_1": {
        "subtitle.sec1": {"type": "subheading", "label": "1. Ring bring up cfg"},
        "rbu_path": {
            "label": "RBU cfg directory",
            "type": "filePath",
            "default": "/home/essdaq/detg_git/slow_control_driver/freia/",
            "info": "Directory for primary configurations."
        },
        "rbu_file": {
            "label": "RBU file",
            "type": "dropdown",
            "optionsFromPath": "rbu_path",
            "fileTypeFilter": ".json",
            "default": "cfg.json"
        },
    },
    "section_2": {
        "subtitle.sec2": {"type": "subheading", "label": "2. Address Map file"},
        "addr_path": {
            "label": "Address file directory",
            "type": "filePath",
            "default": os.path.join(currentPath, "calibration"),
            "info": "Directory for calibration parameters."
        },
        "addr_file": {
            "label": "Address map file",
            "type": "dropdown",
            "optionsFromPath": "addr_path",
            "fileTypeFilter": ".json",
            "options": ["calib_mg.json", "calib_mb.json"]
        },
    },
    "section_3": {
        "subtitle.sec3": {"type": "subheading", "label": "3. VMM config"},
        "cfg_path": {
            "label": "VMM cfg Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, "output"),
            "info": "Directory to write terminal exports/results."
        },
        "cfg_file": {
            "label": "VMM cfg",
            "type": "dropdown",
            "optionsFromPath": "cfg_path",
            "fileTypeFilter": ".json",
            "options": ["summary_template.json", "full_report.json"]
        },
    },
"section_4": {
        "subtitle.sec4": {"type": "subheading", "label": "4. Control Actions"},
        "btn_toggle_power": {
            "type": "bool",
            "label": "Acq ON/OFF",
            "options": ["OFF", "ON"],
            "default": "OFF"
        },
        "btn_warm_init": {
            "type": "button",
            "label": "Global Warm Init"
        },
        "btn_hard_reset": {
            "type": "button",
            "label": "Global Hard Reset"
        },
        "ring_warm_init": {
            "type": "entry",
            "label": "Warm Init - Ring",
            "default": "0",
            "inputValidation": "int"
        },
        "fen_warm_init": {
            "type": "entry",
            "label": "Warm Init - FEN",
            "default": "0",
            "inputValidation": "int"
        },
        "action_warm_init": {
            "type": "button",
            "label": "Warm Init"
        },
    }
}


class StreamOutput(QObject):
    messageWritten = Signal(str)

    def write(self, text):
        self.messageWritten.emit(str(text))

    def flush(self):
        pass


class ConfigCreatorWidget(QWidget):

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.widgets = {}
        self.after_widgets_created_tasks = []

        self._build_ui()
        self._setup_terminal_capture()
        self._apply_terminal_theme()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        self.params_container = QWidget()
        params_layout = QVBoxLayout(self.params_container)
        params_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.params_grid = QGridLayout(self.scroll_content)
        self.params_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.params_grid.setHorizontalSpacing(12)
        self.params_grid.setVerticalSpacing(getattr(theme, "ROW_SPACING", 10))

        self.params_grid.setColumnStretch(0, 0)
        self.params_grid.setColumnStretch(1, 3)
        self.params_grid.setColumnStretch(2, 3)
        self.params_grid.setColumnStretch(3, 1)

        title_label = QLabel("VMM slow control")
        title_label.setFont(theme.base_font(size=theme.FONT_SIZE_HEADER + 4, bold=True))
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.params_grid.addWidget(title_label, 0, 0, 1, 2, alignment=Qt.AlignHCenter)

        if self.theme_manager is not None:
            theme_btn = QToolButton()
            theme_btn.setText("\u263d")
            theme_btn.setToolTip("Toggle light/dark mode")
            theme_btn.setStyleSheet("font-size: 20pt;")
            theme_btn.clicked.connect(self._toggle_theme)
            self.params_grid.addWidget(theme_btn, 0, 2, alignment=Qt.AlignRight)

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
        self.params_grid.addWidget(font_row, 1, 0, 1, 3)

        current_row = 2

        current_row = self._build_section(ui_config["section_1"], start_row=current_row)
        current_row = self._add_divider(current_row)

        current_row = self._build_section(ui_config["section_2"], start_row=current_row)
        current_row = self._add_divider(current_row)

        current_row = self._build_section(ui_config["section_3"], start_row=current_row)
        current_row = self._add_divider(current_row)

        current_row = self._build_section(ui_config["section_4"], start_row=current_row)

        if "btn_toggle_power" in self.widgets:
            btn_toggle = self.widgets["btn_toggle_power"]
            if hasattr(btn_toggle, "toggled"):
                btn_toggle.toggled.connect(
                    lambda checked: print(f"[ACTION] Acq ON/OFF state changed to: {'ON' if checked else 'OFF'}\n")
                )

        if "btn_action_2" in self.widgets:
            self.widgets["btn_action_2"].clicked.connect(
                lambda: print("[ACTION] Executed Global Warm Init\n")
            )

        if "btn_action_3" in self.widgets:
            self.widgets["btn_action_3"].clicked.connect(self._on_warm_init_clicked)

        if "btn_action_4" in self.widgets:
            self.widgets["btn_action_4"].clicked.connect(
                lambda: print("[ACTION] Executed Global Hard Reset\n")
            )

        if "btn_action_5" in self.widgets:
            self.widgets["btn_action_5"].clicked.connect(self._on_hard_reset_clicked)

        scroll.setWidget(self.scroll_content)
        params_layout.addWidget(scroll)

        self.terminal_frame = QGroupBox("Terminal Output & Logs")
        terminal_layout = QVBoxLayout(self.terminal_frame)

        self.terminal_text_widget = QPlainTextEdit()
        self.terminal_text_widget.setReadOnly(True)
        self.terminal_text_widget.setFont(theme.mono_font(size=theme.FONT_SIZE_CONSOLE))
        terminal_layout.addWidget(self.terminal_text_widget)

        clear_btn = QPushButton("Clear Output")
        clear_btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        clear_btn.clicked.connect(self.terminal_text_widget.clear)
        terminal_layout.addWidget(clear_btn)

        self.splitter.addWidget(self.params_container)
        self.splitter.addWidget(self.terminal_frame)

        self.splitter.setSizes([500, 500])

        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear()

    def _build_section(self, config_dict, start_row=0):
        current_row = start_row
        for key, item in config_dict.items():
            res = create_gui_widget(
                parent_frame=self.scroll_content,
                key=key,
                item=item,
                row=current_row
            )

            if not res or res[0] is None:
                continue

            widget_instance = res[0]
            next_row = res[2]

            if widget_instance:
                if item.get("type") == "button_pair":
                    k1 = item.get("key1", "btn_action_2")
                    k2 = item.get("key2", "btn_action_4")
                    self.widgets[k1] = widget_instance[0]
                    self.widgets[k2] = widget_instance[1]
                elif item.get("type") == "action_with_fields":
                    btn_k = item.get("button_key")
                    fields_k = item.get("fields_key")
                    self.widgets[btn_k] = widget_instance[0]
                    self.widgets[fields_k] = widget_instance[1]
                else:
                    self.widgets[key] = widget_instance

                if item.get("type") == "dropdown" and "optionsFromPath" in item:
                    dynamic_path_key = item["optionsFromPath"]
                    file_filter = item.get("fileTypeFilter", "")

                    if dynamic_path_key in self.widgets:
                        path_widget = self.widgets[dynamic_path_key]
                        dropdown_widget = widget_instance

                        def _connect_dynamic_options(d_widget=dropdown_widget, p_widget=path_widget, ff=file_filter):
                            setup_dynamic_file_options(d_widget, p_widget, ff)

                        self.after_widgets_created_tasks.append(_connect_dynamic_options)

            current_row = next_row

        return current_row

    def _add_divider(self, row):
        self.params_grid.setRowMinimumHeight(row, 12)
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.params_grid.addWidget(divider, row + 1, 0, 1, 3)
        self.params_grid.setRowMinimumHeight(row + 2, 12)
        return row + 3

    def _apply_font_size(self, new_size):
        theme.FONT_SIZE_BASE = new_size
        if self.theme_manager is not None:
            self.theme_manager.apply(getattr(self.theme_manager, "mode", "dark"))

    def _toggle_theme(self):
        if self.theme_manager is not None:
            self.theme_manager.toggle()
            self._apply_terminal_theme()

    def _apply_terminal_theme(self):
        current_mode = getattr(self.theme_manager, "mode", "dark")
        if current_mode == "dark":
            self.terminal_text_widget.setStyleSheet(
                "background-color: #121212; color: #00ff66; border: 1px solid #333;"
            )
        else:
            self.terminal_text_widget.setStyleSheet(
                "background-color: #f5f5f5; color: #006600; border: 1px solid #ccc;"
            )

    def _setup_terminal_capture(self):
        self.stdout_stream = StreamOutput()
        self.stdout_stream.messageWritten.connect(self._append_terminal_message)
        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream

        print("[INFO] Terminal console successfully initialized.")

    def _append_terminal_message(self, text):
        self.terminal_text_widget.moveCursor(self.terminal_text_widget.textCursor().End)
        self.terminal_text_widget.insertPlainText(text)
        self.terminal_text_widget.moveCursor(self.terminal_text_widget.textCursor().End)

    def _on_warm_init_clicked(self):
        field_dict = self.widgets.get("fields_warm_init", {})
        ring_val = field_dict.get("ring").text() if isinstance(field_dict, dict) and "ring" in field_dict else "0"
        fen_val = field_dict.get("fen").text() if isinstance(field_dict, dict) and "fen" in field_dict else "0"
        print(f"[ACTION] Warm Init Executed -> Ring: {ring_val}, FEN: {fen_val}\n")

    def _on_hard_reset_clicked(self):
        field_dict = self.widgets.get("fields_hard_reset", {})
        ring_val = field_dict.get("ring").text() if isinstance(field_dict, dict) and "ring" in field_dict else "0"
        fen_val = field_dict.get("fen").text() if isinstance(field_dict, dict) and "fen" in field_dict else "0"
        hybrid_val = field_dict.get("hybrid").text() if isinstance(field_dict, dict) and "hybrid" in field_dict else "0"
        print(f"[ACTION] Hard Reset Executed -> Ring: {ring_val}, FEN: {fen_val}, Hybrid: {hybrid_val}\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    mode = "dark"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    theme_manager = theme.ThemeManager(app, mode=mode) if hasattr(theme, "ThemeManager") else theme(app, mode=mode)

    window = ConfigCreatorWidget(theme_manager=theme_manager)
    window.setWindowTitle("VMM slow control")

    window.resize(1600, 800)
    window.show()
    sys.exit(app.exec_())