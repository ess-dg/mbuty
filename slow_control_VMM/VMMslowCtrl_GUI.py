#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 30/09/2026

@author: francescopiscitelli
"""

import sys
import os
import subprocess

# Compute project root directory once
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Ensure project root is at the top of sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Top-level imports
from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options
from lib.IOC_manager_lib import manage_IOC_service

# Determine theme mode from command-line arguments (default to "dark")
theme_mode = sys.argv[1] if len(sys.argv) > 1 else "dark"

try:
    from libVMM.VMM_configurator import VMMSlowCtrl
except ImportError:
    class VMMSlowCtrl:
        def __init__(self, rbu_path, rbu_file, addr_path, addr_file, cfg_path, cfg_file):
            self.rbu_path = rbu_path
            self.rbu_file = rbu_file
            self.addr_path = addr_path
            self.addr_file = addr_file
            self.cfg_path = cfg_path
            self.cfg_file = cfg_file
            print(f"------- BACKEND MOCKUP -------\n"
                  f"[BACKEND MOCK] Initialized VMMSlowCtrl with:\n"
                  f"  RBU:  {os.path.join(rbu_path, rbu_file)}\n"
                  f"  ADDR: {os.path.join(addr_path, addr_file)}\n"
                  f"  CFG:  {os.path.join(cfg_path, cfg_file)}")

        def acq_on(self):
            print("[BACKEND MOCK] Acquisition ON")

        def acq_off(self):
            print("[BACKEND MOCK] Acquisition OFF")

        def warm_init(self, ring, fen):
            print(f"[BACKEND MOCK] Warm init on Ring {ring}, FEN {fen}")

        def warm_init_glob(self):
            print("[BACKEND MOCK] Global warm init executed")

        def hard_reset(self, ring, fen, hybrid):
            print(f"[BACKEND MOCK] Hard reset on Ring {ring}, FEN {fen}, Hybrid {hybrid}")

        def hard_reset_glob(self):
            print("[BACKEND MOCK] Global hard reset executed")

        def toggle_ioc(self, state):
            print(f"[BACKEND MOCK] IOC service toggled: {'ON' if state else 'OFF'}")


from qtpy.QtCore import Qt, QObject, Signal, QThread
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
    QMainWindow,
    QMessageBox,
)

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


ui_config = {
    "section_1": {
        "subtitle.sec1": {"type": "subheading", "label": "Ring bring up cfg"},
        "rbu_path": {
            "label": "RBU cfg directory",
            "type": "filePath",
            "default": "/home/essdaq/detg_git/slow_control_driver/freia/",
            "info": "Directory for ring bring up cfg."
        },
        "rbu_file": {
            "label": "RBU cfg file",
            "type": "dropdown",
            "optionsFromPath": "rbu_path",
            "fileTypeFilter": ".json",
            "default": "cfg.json"
        },
        "rbu_run_file": {
            "label": "RBU run file",
            "type": "dropdown",
            "optionsFromPath": "rbu_path",
            "fileTypeFilter": ".sh",
            "default": "run.sh"
        },
    },
    "section_2": {
        "subtitle.sec2": {"type": "subheading", "label": "Address Map file"},
        "addr_path": {
            "label": "Address map file directory",
            "type": "filePath",
            "default": os.path.join(current_dir, "sys_regs_map"),
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
        "subtitle.sec3": {"type": "subheading", "label": "VMM config"},
        "cfg_path": {
            "label": "VMM cfg directory",
            "type": "filePath",
            "default": os.path.join(current_dir, "config_VMM"),
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
        "subtitle.sec4": {"type": "subheading", "label": "IOC service"},
        "ioc_service": {
            "label": "IOC service",
            "type": "entry",
            "default": "ioc-ESTIA-DtCmn_SC-IOC-002.service",
        },
        "ioc_actions": {
            "type": "button_row",
            "buttons": ["start", "stop", "status", "restart"],
            "key": "btn_ioc_row"
        },
    },
    "section_5": {
        "subtitle.sec5": {"type": "subheading", "label": "Ring Bring Up"},
        "action_ring_bring_up": {
            "type": "button_pair",
            "label1": "ring bring up",
            "key1": "btn_ring_bring_up",
            "label2": "abort",
            "key2": "btn_rbu_abort"
        },
    },
    "section_6": {
        "subtitle.sec6": {"type": "subheading", "label": "VMM Controls"},
        "btn_toggle_power": {
            "label": "Acq ON/OFF",
            "type": "toggle_button",
            "default": False
        },
        "btn_force_off": {
            "type": "button",
            "label": "Force Acq OFF",
            } , 
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


class AcquisitionWorker(QObject):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, slow_ctrl, target_state):
        super().__init__()
        self.slow_ctrl = slow_ctrl
        self.target_state = target_state

    def run(self):
        try:
            if self.target_state:
                self.slow_ctrl.acq_on()
            else:
                self.slow_ctrl.acq_off()
            self.finished.emit(self.target_state)
        except Exception as e:
            self.error.emit(str(e))


class ConfigCreatorWidget(QWidget):

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.widgets = {}
        self.after_widgets_created_tasks = []

        self._build_ui()
        self._setup_terminal_capture()
        self._apply_terminal_theme()

    def get_value_from_widget(self, key):
        widget = self.widgets.get(key)
        if widget is None:
            return ""

        if isinstance(widget, QLineEdit):
            return widget.text()
        line_edit = widget.findChild(QLineEdit)
        if line_edit:
            return line_edit.text()

        if isinstance(widget, QComboBox):
            return widget.currentText()
        combo = widget.findChild(QComboBox)
        if combo:
            return combo.currentText()

        return ""

    def get_config_paths(self):
        rbu_path = self.get_value_from_widget("rbu_path")
        rbu_file = self.get_value_from_widget("rbu_file")
        addr_path = self.get_value_from_widget("addr_path")
        addr_file = self.get_value_from_widget("addr_file")
        cfg_path = self.get_value_from_widget("cfg_path")
        cfg_file = self.get_value_from_widget("cfg_file")

        return rbu_path, rbu_file, addr_path, addr_file, cfg_path, cfg_file

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

        self.params_grid.setColumnStretch(0, 1)
        self.params_grid.setColumnStretch(1, 4)
        self.params_grid.setColumnStretch(2, 1)

        title_label = QLabel("Slow Control")
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
        current_row = self._add_divider(current_row)

        current_row = self._build_section(ui_config["section_5"], start_row=current_row)
        current_row = self._add_divider(current_row)

        current_row = self._build_section(ui_config["section_6"], start_row=current_row)

        scroll.setWidget(self.scroll_content)
        params_layout.addWidget(scroll)

        self.terminal_frame = QGroupBox("Terminal Output Logs")
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

        self.splitter.setSizes([600, 600])

        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear()


    def _build_section(self, config_dict, start_row=0):
        current_row = start_row
        for key, item in config_dict.items():
            item_type = item.get("type")

            # Handle custom widget types natively to avoid create_gui_widget warnings
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

                self.params_grid.setRowMinimumHeight(current_row + 1, 25)
                current_row += 2
                continue

            elif item_type == "button":
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(8)

                btn = QPushButton(item.get("label", "Action"))
                btn.setFixedWidth(item.get("button_width", 160))
                h_layout.addWidget(btn)
                h_layout.addStretch(1)

                self.params_grid.addWidget(container, current_row, 0, 1, 3)
                self.widgets[item.get("button_key", key)] = btn
                current_row += 1
                continue

            elif item_type == "button_row":
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(8)

                buttons_dict = {}
                for label in item.get("buttons", []):
                    b = QPushButton(label)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    h_layout.addWidget(b)
                    buttons_dict[label] = b

                self.params_grid.addWidget(container, current_row, 0, 1, 3)
                self.widgets[item.get("key", key)] = buttons_dict

                current_row += 1
                continue

            elif item_type == "button_pair":
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(8)

                label1 = item.get("label1", "Button 1")
                label2 = item.get("label2", "Button 2")

                if item.get("is_toggle_1", False):
                    btn1 = QPushButton(f"{label1} (OFF)")
                    btn1.setCheckable(True)
                    btn1.setChecked(item.get("default_1", False))
                    def _on_toggle_1(checked, b=btn1, l=label1):
                        b.setText(f"{l} (ON)" if checked else f"{l} (OFF)")
                    btn1.toggled.connect(_on_toggle_1)
                else:
                    btn1 = QPushButton(label1)

                btn2 = QPushButton(label2)
                btn1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                h_layout.addWidget(btn1)
                h_layout.addWidget(btn2)

                self.params_grid.addWidget(container, current_row, 0, 1, 3)
                self.widgets[item.get("key1", "btn_action_2")] = btn1
                self.widgets[item.get("key2", "btn_action_4")] = btn2

                self.params_grid.setRowMinimumHeight(current_row + 1, 25)
                current_row += 2
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

            # Fall back to create_gui_widget for standard types (entry, filePath, dropdown, subheadings)
            res = create_gui_widget(
                parent_frame=self.scroll_content,
                key=key,
                item=item,
                row=current_row
            )

            if not res or res[0] is None:
                current_row += 1
                continue

            widget_instance = res[0]
            next_row = res[2]
            self.widgets[key] = widget_instance

            if item.get("type") in ["entry", "filePath", "dropdown"]:
                self.params_grid.removeWidget(widget_instance)
                self.params_grid.addWidget(widget_instance, current_row, 1, 1, 2)

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


class MainWindow(QMainWindow):
    def __init__(self, theme_manager=None):
        super().__init__()
        self.theme_manager = theme_manager

        self.config_widget = ConfigCreatorWidget(theme_manager=self.theme_manager)
        self.setCentralWidget(self.config_widget)

        self.slow_ctrl = None
        self.init_slow_ctrl()

        self.is_acq_running = False

        self._connect_signals()

    def init_slow_ctrl(self):
        rbu_p, rbu_f, addr_p, addr_f, cfg_p, cfg_f = self.config_widget.get_config_paths()

        try:
            self.slow_ctrl = VMMSlowCtrl(
                rbu_path=rbu_p,
                rbu_file=rbu_f,
                addr_path=addr_p,
                addr_file=addr_f,
                cfg_path=cfg_p,
                cfg_file=cfg_f,
            )
        except Exception as e:
            print(f"[ERROR] Failed to initialize VMMSlowCtrl: {e}")
            self.slow_ctrl = None

    def _connect_signals(self):
        self.btn_toggle_power = self.config_widget.widgets.get("btn_toggle_power")
        if self.btn_toggle_power:
            self.btn_toggle_power.clicked.connect(self.handle_power_toggle)

        ioc_buttons = self.config_widget.widgets.get("btn_ioc_row")
        if ioc_buttons:
            for action_name, btn in ioc_buttons.items():
                btn.clicked.connect(lambda checked, act=action_name: self.handle_ioc_action(act))

        btn_rbu = self.config_widget.widgets.get("btn_ring_bring_up")
        if btn_rbu:
            btn_rbu.clicked.connect(self.handle_ring_bring_up)
            
        btn_rbu_abort = self.config_widget.widgets.get("btn_rbu_abort")
        if btn_rbu_abort:
            btn_rbu_abort.clicked.connect(self.handle_rbu_abort)
            btn_rbu_abort.setEnabled(False)  # Disabled by default until RBU starts    

        btn_g_warm = self.config_widget.widgets.get("btn_action_2")
        if btn_g_warm:
            btn_g_warm.clicked.connect(self.handle_global_warm_init)

        btn_g_hard = self.config_widget.widgets.get("btn_action_4")
        if btn_g_hard:
            btn_g_hard.clicked.connect(self.handle_global_hard_reset)

        btn_warm = self.config_widget.widgets.get("btn_action_3")
        if btn_warm:
            btn_warm.clicked.connect(self.handle_warm_init)

        btn_hard = self.config_widget.widgets.get("btn_action_5")
        if btn_hard:
            btn_hard.clicked.connect(self.handle_hard_reset)
            
        btn_off = self.config_widget.widgets.get("btn_force_off")
        if btn_hard:
            btn_off.clicked.connect(self.handle_force_acq_off)

    def handle_force_acq_off(self):
        self.init_slow_ctrl()
        if self.slow_ctrl is None:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend could not be initialized.")
            return

        # Disable the button (or specific control) while forcing off
        self.btn_toggle_power.setEnabled(False)
        target_state = False  # Hardcoded to turn acquisition OFF

        self.thread = QThread()
        self.worker = AcquisitionWorker(self.slow_ctrl, target_state)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_acq_toggle_finished)
        self.worker.error.connect(self.on_acq_toggle_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
        


    def handle_power_toggle(self):
        self.init_slow_ctrl()
        if self.slow_ctrl is None:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend could not be initialized.")
            return

        self.btn_toggle_power.setEnabled(False)
        target_state = not self.is_acq_running

        self.thread = QThread()
        self.worker = AcquisitionWorker(self.slow_ctrl, target_state)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_acq_toggle_finished)
        self.worker.error.connect(self.on_acq_toggle_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_acq_toggle_finished(self, state_is_on):
        self.is_acq_running = state_is_on
        self.btn_toggle_power.setEnabled(True)

        if state_is_on:
            self.btn_toggle_power.setText("Stop Acquisition (ON)")
            self.btn_toggle_power.setStyleSheet("background-color: darkred; color: white; font-weight: bold;")
            print("[ACTION] Acquisition started successfully.\n")
        else:
            self.btn_toggle_power.setText("Start Acquisition (OFF)")
            self.btn_toggle_power.setStyleSheet("background-color: darkgreen; color: white; font-weight: bold;")
            print("[ACTION] Acquisition stopped successfully.\n")

    def on_acq_toggle_error(self, err_msg):
        self.btn_toggle_power.setEnabled(True)
        QMessageBox.critical(self, "Acquisition Error", f"Failed to toggle acquisition:\n{err_msg}")

    def handle_ioc_action(self, action):
        service_name = self.config_widget.get_value_from_widget("ioc_service")
        if not service_name:
            QMessageBox.warning(self, "Missing Service", "Please specify a valid IOC service name.")
            return

        print(f"[ACTION] Executing IOC action '{action}' on service '{service_name}'...")
        try:
            manage_IOC_service(action, service_name)
        except Exception as e:
            print(f"[ERROR] Failed to execute IOC action {action}: {e}")

    def handle_ring_bring_up(self):
        rbu_path     = self.config_widget.get_value_from_widget("rbu_path")
        rbu_run_file = self.config_widget.get_value_from_widget("rbu_run_file")

        if not rbu_path or not rbu_run_file:
            QMessageBox.warning(self, "Missing Configuration", "Please specify a valid RBU path and run file.")
            return

        script_path = os.path.join(rbu_path, rbu_run_file)
        if not os.path.isfile(script_path):
            QMessageBox.critical(self, "File Not Found", f"The RBU run script does not exist:\n{script_path}")
            return

        # Toggle buttons state
        btn_rbu = self.config_widget.widgets.get("btn_ring_bring_up")
        btn_abort = self.config_widget.widgets.get("btn_rbu_abort")
        if btn_rbu: btn_rbu.setEnabled(False)
        if btn_abort: btn_abort.setEnabled(True)

        self.rbu_thread = QThread()
        self.rbu_worker = RBUWorker(script_path)
        self.rbu_worker.moveToThread(self.rbu_thread)

        self.rbu_thread.started.connect(self.rbu_worker.run)
        self.rbu_worker.finished.connect(self.on_rbu_finished)
        self.rbu_worker.error.connect(self.on_rbu_error)

        self.rbu_worker.finished.connect(self.rbu_thread.quit)
        self.rbu_worker.finished.connect(self.rbu_worker.deleteLater)
        self.rbu_thread.finished.connect(self.rbu_thread.deleteLater)

        self.rbu_thread.start()

    def handle_rbu_abort(self):
        if hasattr(self, 'rbu_worker') and self.rbu_worker:
            self.rbu_worker.abort()

    def on_rbu_finished(self, returncode):
        btn_rbu = self.config_widget.widgets.get("btn_ring_bring_up")
        btn_abort = self.config_widget.widgets.get("btn_rbu_abort")
        if btn_rbu: btn_rbu.setEnabled(True)
        if btn_abort: btn_abort.setEnabled(False)

        if returncode == 0:
            print(f"[ACTION] RBU script finished successfully.\n")
        elif returncode == -999:
            print(f"[ACTION] RBU script execution aborted by user.\n")
        else:
            print(f"[ERROR] RBU script exited with return code {returncode}.\n")

    def on_rbu_error(self, err_msg):
        btn_rbu = self.config_widget.widgets.get("btn_ring_bring_up")
        btn_abort = self.config_widget.widgets.get("btn_rbu_abort")
        if btn_rbu: btn_rbu.setEnabled(True)
        if btn_abort: btn_abort.setEnabled(False)
        QMessageBox.critical(self, "Execution Error", f"Failed to execute RBU script:\n{err_msg}")

    def handle_global_warm_init(self):
        self.init_slow_ctrl()
        if self.slow_ctrl:
            self.slow_ctrl.warm_init_glob()

    def handle_global_hard_reset(self):
        self.init_slow_ctrl()
        if self.slow_ctrl:
            self.slow_ctrl.hard_reset_glob()

    def handle_warm_init(self):
        self.init_slow_ctrl()
        if not self.slow_ctrl:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend is not initialized.")
            return
        fields = self.config_widget.widgets.get("fields_warm_init", {})
        try:
            ring = int(fields.get("ring").text()) if "ring" in fields else 0
            fen = int(fields.get("fen").text()) if "fen" in fields else 0
            self.slow_ctrl.warm_init(ring, fen)
        except ValueError:
            print("[ERROR] Ring and FEN must be integers.")

    def handle_hard_reset(self):
        self.init_slow_ctrl()
        if not self.slow_ctrl:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend is not initialized.")
            return
        fields = self.config_widget.widgets.get("fields_hard_reset", {})
        try:
            ring = int(fields.get("ring").text()) if "ring" in fields else 0
            fen = int(fields.get("fen").text()) if "fen" in fields else 0
            hybrid = int(fields.get("hybrid").text()) if "hybrid" in fields else 0
            self.slow_ctrl.hard_reset(ring, fen, hybrid)
        except ValueError:
            print("[ERROR] Ring, FEN, and Hybrid must be integers.")
            
            
class RBUWorker(QObject):
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path
        self.process = None
        self._is_aborted = False

    def run(self):
        try:
            print(f"[ACTION] Executing RBU script: {self.script_path}")
            script_dir = os.path.dirname(self.script_path)
            
            self.process = subprocess.Popen(
                ["bash", self.script_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=script_dir
            )
            
            while True:
                if self._is_aborted:
                    break
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    print(line, end="")

            if self._is_aborted:
                returncode = -999  # Custom code for aborted tasks
            else:
                returncode = self.process.wait()
                
            self.finished.emit(returncode)
        except Exception as e:
            if not self._is_aborted:
                self.error.emit(str(e))

    def abort(self):
        self._is_aborted = True
        if self.process and self.process.poll() is None:
            print("[ACTION] Aborting RBU script process...")
            try:
                # Terminate process group or process tree if needed, or simple terminate
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            

    
if __name__ == "__main__":
    import sys as _sys
    from qtpy.QtWidgets import QApplication
    
    app = QApplication(_sys.argv)
    
    # Read theme mode from command-line arguments if provided
    # theme_mode = "dark"
    if len(_sys.argv) > 1:
        theme_mode = _sys.argv[1]
    else:
        theme_mode = 'dark'
        
    # print(f"DEBUG sys.argv received: {_sys.argv}")    

    # Initialize theme manager safely
    try:
        from GUI import theme
        if hasattr(theme, "ThemeManager"):
            theme_manager = theme.ThemeManager(app, mode=theme_mode)
        else:
            theme_manager = theme.ThemeMock(app, mode=theme_mode)
    except ImportError:
        # Fallback if the GUI module isn't found locally
        theme_manager = None # Or instantiate your fallback mock class here

    main_win = MainWindow(theme_manager=theme_manager)
    main_win.resize(1200, 800)
    main_win.show()
    
    # Use _sys instead of sys to match your import alias
    _sys.exit(app.exec_())