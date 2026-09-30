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
    QLineEdit,
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
    QComboBox,
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
            "info": "Directory for ring bring up cfg."
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
            "label": "Address map file directory",
            "type": "filePath",
            "default": os.path.join(currentPath, "sys_regs_map"),
            "info": "Directory address map file."
        },
        "addr_file": {
            "label": "Address map file",
            "type": "dropdown",
            "optionsFromPath": "addr_path",
            "fileTypeFilter": ".txt",
            "default": "vmm_sys_regs_map_A0v1.txt",
            "info": "Address map file."
        },
    },
    "section_3": {
        "subtitle.sec3": {"type": "subheading", "label": "3. VMM config"},
        "cfg_path": {
            "label": "VMM cfg Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, "config_VMM"),
            "info": "VMM config files json."
        },
        "cfg_file": {
            "label": "VMM cfg",
            "type": "dropdown",
            "optionsFromPath": "cfg_path",
            "fileTypeFilter": ".json",
            "default": "MB.FREIA.diagonalNoSymm.json",
        },
    },
    "section_4": {
        "subtitle.sec4": {"type": "subheading", "label": "4. Control Actions"},
        "btn_toggle_power": {
            "label": "Acq ON/OFF",
            "type": "toggle_button",
            "default": False
        },
        "btn_global_actions": {
            "type": "button_pair",
            "label1": "global warm init",
            "key1": "btn_action_2",
            "label2": "global hard reset",
            "key2": "btn_action_4"
        },
        "action_warm_init": {
            "type": "action_with_fields",
            "button_key": "btn_action_3",
            "fields_key": "fields_warm_init",
            "label": "warm init",
            "button_width": 160,
            "fields": [
                {"key": "ring", "label": "ring", "default": "0"},
                {"key": "fen", "label": "fen", "default": "0"}
            ]
        },
        "action_hard_reset": {
            "type": "action_with_fields",
            "button_key": "btn_action_5",
            "fields_key": "fields_hard_reset",
            "label": "hard reset",
            "button_width": 160,
            "fields": [
                {"key": "ring", "label": "ring", "default": "0"},
                {"key": "fen", "label": "fen", "default": "0"},
                {"key": "hybrid", "label": "hybrid", "default": "0"}
            ]
        }
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

        self.params_grid.setColumnStretch(0, 1)  # Label column
        self.params_grid.setColumnStretch(1, 4)  # Widget column / Control inputs
        self.params_grid.setColumnStretch(2, 1)  # Action / Extra column

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

            # --- Custom handling for widget types not in GUI.gui_utils ---
            if not res or res[0] is None:
                item_type = item.get("type")
                
                if item_type == "toggle_button":
                    btn = QPushButton(f"{item.get('label', 'Toggle')} (OFF)")
                    btn.setCheckable(True)
                    btn.setChecked(item.get("default", False))
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    
                    def _on_toggle(checked, b=btn, l=item.get('label', 'Toggle')):
                        b.setText(f"{l} (ON)" if checked else f"{l} (OFF)")
                        
                    btn.toggled.connect(_on_toggle)
                    self.params_grid.addWidget(btn, current_row, 0, 1, 3)
                    self.widgets[key] = btn
                    
                    # --- ADD VERTICAL SPACE BELOW TOGGLE BUTTON ---
                    self.params_grid.setRowMinimumHeight(current_row + 1, 25)
                    current_row += 2
                    continue

                elif item_type == "button_pair":
                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(8)

                    btn1 = QPushButton(item.get("label1", "Button 1"))
                    btn2 = QPushButton(item.get("label2", "Button 2"))
                    btn1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    btn2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    
                    h_layout.addWidget(btn1)
                    h_layout.addWidget(btn2)

                    self.params_grid.addWidget(container, current_row, 0, 1, 3)
                    self.widgets[item.get("key1", "btn_action_2")] = btn1
                    self.widgets[item.get("key2", "btn_action_4")] = btn2
                    current_row += 1
                    continue

                elif item_type == "action_with_fields":
                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(8)

                    btn = QPushButton(item.get("label", "Action"))
                    btn.setFixedWidth(item.get("button_width", 160))
                    h_layout.addWidget(btn)

                    fields_dict = {}
                    for field_info in item.get("fields", []):
                        f_key = field_info["key"]
                        f_label = QLabel(field_info.get("label", f_key) + ":")
                        f_entry = QLineEdit(field_info.get("default", "0"))
                        f_entry.setFixedWidth(50)
                        h_layout.addWidget(f_label)
                        h_layout.addWidget(f_entry)
                        fields_dict[f_key] = f_entry

                    h_layout.addStretch(1)

                    self.params_grid.addWidget(container, current_row, 0, 1, 3)
                    self.widgets[item.get("button_key")] = btn
                    self.widgets[item.get("fields_key")] = fields_dict
                    current_row += 1
                    continue

                else:
                    current_row += 1
                    continue

            # --- Standard GUI.gui_utils widget processing ---
            widget_instance = res[0]
            next_row = res[2]
            self.widgets[key] = widget_instance

            # Ensure filePath and dropdown widgets expand horizontally across the grid space
            if item.get("type") in ["filePath", "dropdown"]:
                # Re-bind grid placement so the control area spans columns 1 to 2 fully (columns 1..3)
                self.params_grid.removeWidget(widget_instance)
                self.params_grid.addWidget(widget_instance, current_row, 1, 1, 2)

                # Set expansion policies on the parent widget and internal components (QLineEdit / QComboBox)
                if hasattr(widget_instance, "setSizePolicy"):
                    widget_instance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                
                for child in widget_instance.findChildren((QLineEdit, QComboBox)):
                    child.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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