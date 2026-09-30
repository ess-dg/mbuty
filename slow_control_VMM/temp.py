#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 10:27:18 2026

@author: francescopiscitelli
"""

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
    QLineEdit,
    QComboBox,
    QFileDialog,
    QSplitter,
    QScrollArea,
    QFrame,
    QSizePolicy,
)

# Project imports or fallback mocks
try:
    from GUI import theme
    from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options
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

    def setup_dynamic_file_options(dropdown_widget, path_widget, file_filter):
        pass


def create_gui_widget(parent_frame, key, item, row):
    """Widget creation helper supporting toggle_button, filePath, dropdown, button_pair, and action_with_fields."""
    item_type = item.get("type")

    # 1. Subheading
    if item_type == "subheading":
        lbl = QLabel(item.get("label", ""))
        lbl.setFont(theme.base_font(size=12, bold=True))
        parent_frame.layout().addWidget(lbl, row, 0, 1, 3)
        return None, None, row + 1

    # 2. Toggle Button
    if item_type == "toggle_button":
        btn = QPushButton(f"{item.get('label', 'Toggle')} (OFF)")
        btn.setCheckable(True)
        btn.setChecked(item.get("default", False))
        btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE, bold=True))
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        def _on_toggle(checked):
            base_text = item.get('label', 'Toggle')
            if checked:
                btn.setText(f"{base_text} (ON)")
                btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
            else:
                btn.setText(f"{base_text} (OFF)")
                btn.setStyleSheet("")

        btn.toggled.connect(_on_toggle)
        btn.get = btn.isChecked
        parent_frame.layout().addWidget(btn, row, 0, 1, 3)
        return btn, None, row + 1

    # 3. Standard Action Button
    if item_type == "button":
        btn = QPushButton(item.get("label", "Click"))
        btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        parent_frame.layout().addWidget(btn, row, 0, 1, 3)
        return btn, None, row + 1

    # 4. Paired Buttons Side-by-Side
    if item_type == "button_pair":
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        btn1 = QPushButton(item.get("label1", "Button 1"))
        btn1.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        btn1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn2 = QPushButton(item.get("label2", "Button 2"))
        btn2.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        btn2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        h_layout.addWidget(btn1)
        h_layout.addWidget(btn2)

        parent_frame.layout().addWidget(container, row, 0, 1, 3)
        return (btn1, btn2), None, row + 1

    # 5. Action Button with Inline Fields
    if item_type == "action_with_fields":
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        btn = QPushButton(item.get("label", "Action"))
        btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        btn.setFixedWidth(item.get("button_width", 160))
        h_layout.addWidget(btn)

        fields_dict = {}
        for field_info in item.get("fields", []):
            f_key = field_info["key"]
            f_label = QLabel(field_info.get("label", f_key) + ":")
            f_label.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))

            f_entry = QLineEdit(field_info.get("default", "0"))
            f_entry.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
            f_entry.setFixedWidth(50)

            h_layout.addWidget(f_label)
            h_layout.addWidget(f_entry)
            fields_dict[f_key] = f_entry

        h_layout.addStretch(1)

        parent_frame.layout().addWidget(container, row, 0, 1, 3)
        return (btn, fields_dict), None, row + 1

    # 6. Standalone Text Input Field
    if item_type == "textInput":
        label_widget = QLabel(item.get("label", key))
        label_widget.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        parent_frame.layout().addWidget(label_widget, row, 0)

        entry = QLineEdit(item.get("default", ""))
        entry.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        entry.get = entry.text
        parent_frame.layout().addWidget(entry, row, 1, 1, 2)
        return entry, None, row + 1

    # 7. File Path Search
    if item_type == "filePath":
        label_widget = QLabel(item.get("label", key))
        label_widget.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        parent_frame.layout().addWidget(label_widget, row, 0)

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)

        entry = QLineEdit(item.get("default", ""))
        entry.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn = QPushButton("...")
        btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE, bold=True))
        btn.setFixedWidth(35)

        def _browse():
            start_dir = entry.text() if os.path.exists(entry.text()) else ""
            d = QFileDialog.getExistingDirectory(parent_frame, "Select Directory", start_dir)
            if d:
                entry.setText(d)

        btn.clicked.connect(_browse)
        h_layout.addWidget(entry)
        h_layout.addWidget(btn)

        container.get = entry.text
        container.line_edit = entry

        parent_frame.layout().addWidget(container, row, 1, 1, 2)
        return container, None, row + 1

    # 8. Dropdown with Browse capability
    if item_type == "dropdown":
        label_widget = QLabel(item.get("label", key))
        label_widget.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        parent_frame.layout().addWidget(label_widget, row, 0)

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)

        cb = QComboBox()
        cb.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cb.setEnabled(True)
        cb.setFocusPolicy(Qt.StrongFocus)

        btn_browse = QPushButton("...")
        btn_browse.setFont(theme.base_font(size=theme.FONT_SIZE_BASE, bold=True))
        btn_browse.setFixedWidth(35)

        container.line_edit_ref = None

        def populate_from_folder(folder_path, file_filter=""):
            cb.blockSignals(True)
            try:
                cb.clear()
                options_to_add = []

                if folder_path and os.path.isdir(folder_path):
                    try:
                        files = [
                            f for f in sorted(os.listdir(folder_path))
                            if not file_filter or f.endswith(file_filter)
                        ]
                        if files:
                            options_to_add = files
                    except Exception as e:
                        print(f"[WARN] Could not read directory '{folder_path}': {e}")

                if not options_to_add and "options" in item:
                    options_to_add = item.get("options", [])

                if options_to_add:
                    cb.addItems(options_to_add)
                    default_item = item.get("default")
                    if default_item:
                        idx = cb.findText(default_item)
                        if idx >= 0:
                            cb.setCurrentIndex(idx)
                else:
                    cb.addItem("No files found")
            finally:
                cb.blockSignals(False)

        def _browse_file():
            start_dir = ""
            if container.line_edit_ref and os.path.exists(container.line_edit_ref.text()):
                start_dir = container.line_edit_ref.text()

            ff_ext = item.get("fileTypeFilter", "")
            filter_str = f"Files (*{ff_ext})" if ff_ext else "All Files (*)"

            file_path, _ = QFileDialog.getOpenFileName(
                parent_frame, "Select File", start_dir, filter_str
            )

            if file_path:
                filename = os.path.basename(file_path)
                idx = cb.findText(filename)
                if idx < 0:
                    cb.addItem(filename)
                    idx = cb.findText(filename)
                cb.setCurrentIndex(idx)

        btn_browse.clicked.connect(_browse_file)

        h_layout.addWidget(cb)
        h_layout.addWidget(btn_browse)

        container.populate_from_folder = populate_from_folder
        container.cb = cb
        container.get = cb.currentText

        parent_frame.layout().addWidget(container, row, 1, 1, 2)
        return container, None, row + 1


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
            self.widgets["btn_toggle_power"]["widget"].toggled.connect(
                lambda checked: print(f"[ACTION] Acq ON/OFF state changed to: {'ON' if checked else 'OFF'}\n")
            )

        if "btn_action_2" in self.widgets:
            self.widgets["btn_action_2"]["widget"].clicked.connect(
                lambda: print("[ACTION] Executed Global Warm Init\n")
            )

        if "btn_action_3" in self.widgets:
            self.widgets["btn_action_3"]["widget"].clicked.connect(self._on_warm_init_clicked)

        if "btn_action_4" in self.widgets:
            self.widgets["btn_action_4"]["widget"].clicked.connect(
                lambda: print("[ACTION] Executed Global Hard Reset\n")
            )

        if "btn_action_5" in self.widgets:
            self.widgets["btn_action_5"]["widget"].clicked.connect(self._on_hard_reset_clicked)

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

            if not res or (res[0] is None and res[2] is None):
                continue

            widget_instance = res[0]
            next_row = res[2]

            if widget_instance:
                if item["type"] == "button_pair":
                    k1 = item.get("key1", "btn_action_2")
                    k2 = item.get("key2", "btn_action_4")
                    self.widgets[k1] = {"type": "button", "widget": widget_instance[0]}
                    self.widgets[k2] = {"type": "button", "widget": widget_instance[1]}
                elif item["type"] == "action_with_fields":
                    btn_k = item.get("button_key")
                    fields_k = item.get("fields_key")
                    self.widgets[btn_k] = {"type": "button", "widget": widget_instance[0]}
                    self.widgets[fields_k] = {"type": "fieldGroup", "widget": widget_instance[1]}
                else:
                    self.widgets[key] = {"type": item["type"], "widget": widget_instance}

                if item["type"] == "dropdown":
                    dynamic_path_key = item.get("optionsFromPath")
                    file_filter = item.get("fileTypeFilter", "")

                    if dynamic_path_key and dynamic_path_key in self.widgets:
                        path_container = self.widgets[dynamic_path_key]["widget"]
                        line_edit = getattr(path_container, "line_edit", path_container)
                        dropdown_container = widget_instance

                        # Save line_edit reference into the container for browse dialog
                        dropdown_container.line_edit_ref = line_edit

                        def _update_dropdown(le=line_edit, container=dropdown_container, ff=file_filter):
                            folder = le.text()
                            container.populate_from_folder(folder, ff)

                        self.after_widgets_created_tasks.append(_update_dropdown)

                        line_edit.textChanged.connect(
                            lambda text, container=dropdown_container, ff=file_filter: container.populate_from_folder(text, ff)
                        )

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
        field_dict = self.widgets.get("fields_warm_init", {}).get("widget", {})
        ring_val = field_dict.get("ring").text() if "ring" in field_dict else "0"
        fen_val = field_dict.get("fen").text() if "fen" in field_dict else "0"
        print(f"[ACTION] Warm Init Executed -> Ring: {ring_val}, FEN: {fen_val}\n")

    def _on_hard_reset_clicked(self):
        field_dict = self.widgets.get("fields_hard_reset", {}).get("widget", {})
        ring_val = field_dict.get("ring").text() if "ring" in field_dict else "0"
        fen_val = field_dict.get("fen").text() if "fen" in field_dict else "0"
        hybrid_val = field_dict.get("hybrid").text() if "hybrid" in field_dict else "0"
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