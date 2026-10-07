#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 30/09/2026

@author: francescopiscitelli
"""
###############################################################################
###############################################################################
import sys
import os
import subprocess
import re
###############################################################################
###############################################################################

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

from lib.colors import WARN, RESET, ERR, INFO

# Compute project root directory once
current_dir  = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Ensure project root is at the top of sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Top-level imports
from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options
from GUI.expandable_section import ExpandableSection
from lib.IOC_manager_lib import manage_IOC_service

# Determine theme mode from command-line arguments (default to "dark")
theme_mode = sys.argv[1] if len(sys.argv) > 1 else "dark"

from lib_sc.VMM_configurator import VMMSlowCtrl
from lib_sc.R5560_configurator import R5560SlowCtrl

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
except ImportError as e:
    print(f"[ERROR] Failed to import GUI.theme: {e}")
    theme = None

###############################################################################
###############################################################################
###############################################################################
###############################################################################

ui_config = {
    # -------------------------------------------------------------------------
    # SECTION 1: Ring Bring Up & Address Map (Foldable / Collapsible)
    # -------------------------------------------------------------------------
    "section_1": {
        "subtitle.sec1": {
            "type": "subheading",
            "label": "Ring Bring Up and Address Map",
        },
        "rbu_path": {
            "label": "RBU cfg directory",
            "type": "filePath",
            "default": "/home/essdaq/detg_git/slow_control_driver/freia/",
            "info": "Directory for ring bring up cfg.",
        },
        "rbu_file": {
            "label": "RBU cfg file",
            "type": "dropdown",
            "optionsFromPath": "rbu_path",
            "fileTypeFilter": ".json",
            "default": "cfg.json",
        },
        "rbu_run_file": {
            "label": "RBU run file",
            "type": "dropdown",
            "optionsFromPath": "rbu_path",
            "fileTypeFilter": ".sh",
            "default": "run.sh",
        },  
        "sep_1": {
            "type": "spacer",
        },
        "addr_path": {
            "label": "Address map file directory",
            "type": "filePath",
            "default": os.path.join(current_dir, "sys_regs_map"),
            "info": "Directory address map file.",
        },
        "addr_file": {
            "label": "Address map file",
            "type": "dropdown",
            "optionsFromPath": "addr_path",
            "fileTypeFilter": ".txt",
            "default": "vmm_sys_regs_map_A0v1.txt",
            "info": "Address map file.",
        },
        "sep_2": {
            "type": "spacer",
        },
        "action_ring_bring_up": {
            "type": "button_pair",
            "label1": "ring bring up",
            "key1": "btn_ring_bring_up",
            "label2": "abort",
            "key2": "btn_rbu_abort",
        },
    },
    # -------------------------------------------------------------------------
    # SECTION 2: IOC Service (Foldable / Collapsible)
    # -------------------------------------------------------------------------
    "section_2": {
        "subtitle.sec2": {"type": "subheading", "label": "IOC service"},
        "ioc_service": {
            "label": "IOC service",
            "type": "entry",
            "default": "ioc-ESTIA-DtCmn_SC-IOC-002.service",
        },
        "sep_3": {
            "type": "spacer",
        },
        "ioc_actions": {
            "type": "button_row",
            "buttons": ["start", "stop", "status", "restart"],
            "key": "btn_ioc_row",
        },
    },
    # -------------------------------------------------------------------------
    # SECTION 3: VMM Config & Controls (Foldable / Collapsible)
    # -------------------------------------------------------------------------
    "section_3": {
        "subtitle.sec3": {"type": "subheading", "label": "VMM Config and Controls"},
        "cfg_VMM_path": {
            "label": "VMM cfg directory",
            "type": "filePath",
            "default": os.path.join(current_dir, "config_VMM"),
            "info": "VMM config files json.",
        },
        "cfg_VMM_file": {
            "label": "VMM cfg",
            "type": "dropdown",
            "optionsFromPath": "cfg_VMM_path",
            "fileTypeFilter": ".json",
            "default": "MB.FREIA.diagonalNoSymm.json",
        },
        "sep_4": {
            "type": "spacer",
        },
        "btn_toggle_power": {
            "label": "Acq ON/OFF",
            "type": "toggle_button",
            "default": False,
        },
        "sep_5": {
            "type": "spacer",
        },
        "btn_force_off": {
            "type": "button",
            "label": "Force Acq OFF",
        },
        "btn_global_actions": {
            "type": "button_pair",
            "label1": "global warm init",
            "key1": "btn_action_2",
            "label2": "global hard reset",
            "key2": "btn_action_4",
        },
        "action_warm_init": {
            "type": "action_with_fields",
            "button_key": "btn_action_3",
            "fields_key": "fields_warm_init",
            "label": "warm init",
            "button_width": 160,
            "fields": [
                {"key": "ring", "label": "ring", "default": "0", "width": 50},
                {"key": "fen", "label": "fen", "default": "0", "width": 50},
            ],
        },
        "action_hard_reset": {
            "type": "action_with_fields",
            "button_key": "btn_action_5",
            "fields_key": "fields_hard_reset",
            "label": "hard reset",
            "button_width": 160,
            "fields": [
                {"key": "ring", "label": "ring", "default": "0", "width": 50},
                {"key": "fen", "label": "fen", "default": "0", "width": 50},
                {"key": "hybrid", "label": "hybrid", "default": "0", "width": 50},
                ],
        },
    },
    # -------------------------------------------------------------------------
    # SECTION 4: R5560 Controls (Foldable / Collapsible)
    # -------------------------------------------------------------------------
    "section_4": {
        "subtitle.sec4": {"type": "subheading", "label": "R5560 Config and Controls"},
        
        "cfg_r5560_path": {
        "label": "R5560 cfg directory",
        "type": "filePath",
        "default": os.path.join(current_dir, "config_R5560"),
        "info": "R5560 config files json.",
    },
    "cfg_R5560_file": {
        "label": "R5560 cfg",
        "type": "dropdown",
        "optionsFromPath": "cfg_r5560_path",
        "fileTypeFilter": ".json",
        "default": "example5560cfg.json",
    },
        "sep_6": {
            "type": "spacer",
        },
    "btn_set_registers": {
        "type": "single_button",
        "label": "set all registers",
        "button_key": "btn_set_registers",
        "button_width": 160,
    },
    
    "action_set_threshold_glob": {
        "type": "action_with_fields",
        "button_key": "btn_action_6",
        "fields_key": "fields_set_threshold_glob",
        "label": "change threshold global",
        "button_width": 160,
        "fields": [
        {"key": "threshold", "label": "threshold", "default": "3000", "width":80},
        ],
    },
    
    "action_set_threshold_lcl": {
        "type": "action_with_fields",
        "button_key": "btn_action_7",
        "fields_key": "fields_set_threshold_lcl",
        "label": "change threshold lcl",
        "button_width": 160,
        "fields": [
                {"key": "threshold", "label": "threshold", "default": "3000", "width": 80},
                {"key": "ring", "label": "ring", "default": "0", "width": 50},
                {"key": "fen", "label": "fen", "default": "0", "width": 50},
                ],
    },
    
    },
}


###############################################################################
###############################################################################

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
    
      cfg_vmm_path = self.get_value_from_widget("cfg_VMM_path")
      cfg_vmm_file = self.get_value_from_widget("cfg_VMM_file")
    
      cfg_r5560_path = self.get_value_from_widget("cfg_r5560_path")
      cfg_r5560_file = self.get_value_from_widget("cfg_R5560_file")
    
      return (
          rbu_path,
          rbu_file,
          addr_path,
          addr_file,
          cfg_vmm_path,
          cfg_vmm_file,
          cfg_r5560_path,
          cfg_r5560_file,
      )

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Left Container: Parameters & Controls
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

        # Header Title
        title_label = QLabel("Slow Control")
        title_label.setFont(theme.base_font(size=theme.FONT_SIZE_HEADER + 4, bold=True))
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.params_grid.addWidget(title_label, 0, 0, 1, 2, alignment=Qt.AlignHCenter)

        # Dark/Light Theme Toggle Button
        if self.theme_manager is not None:
            theme_btn = QToolButton()
            theme_btn.setText("\u263d")
            theme_btn.setToolTip("Toggle light/dark mode")
            theme_btn.setStyleSheet("font-size: 20pt;")
            theme_btn.clicked.connect(self._toggle_theme)
            self.params_grid.addWidget(theme_btn, 0, 2, alignment=Qt.AlignRight)

        # Font Size Slider
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

        # Build Config Sections Dynamically
        current_row = 2
        sections = ["section_1", "section_2", "section_3", "section_4"]

        for idx, sec_key in enumerate(sections):
            if sec_key in ui_config:
                # _build_section handles ExpandableSection creation and grid placement internally
                current_row = self._build_section(ui_config[sec_key], start_row=current_row)

                if idx < len(sections) - 1:
                    current_row = self._add_divider(current_row)

        scroll.setWidget(self.scroll_content)
        params_layout.addWidget(scroll)

        # Right Container: Terminal Console Output
        self.terminal_frame = QGroupBox("Terminal Output Logs")
        terminal_layout = QVBoxLayout(self.terminal_frame)

        self.terminal_text_widget = QPlainTextEdit()
        self.terminal_text_widget.setReadOnly(True)
        self.terminal_text_widget.setFont(theme.mono_font(size=theme.FONT_SIZE_CONSOLE))
        self.terminal_text_widget.setStyleSheet(
            "background-color: #121212; color: #00ff66; border: 1px solid #333;"
        )
        terminal_layout.addWidget(self.terminal_text_widget)

        clear_btn = QPushButton("Clear Output")
        clear_btn.setFont(theme.base_font(size=theme.FONT_SIZE_BASE))
        clear_btn.clicked.connect(self.terminal_text_widget.clear)
        terminal_layout.addWidget(clear_btn)

        # Assemble Splitter
        self.splitter.addWidget(self.params_container)
        self.splitter.addWidget(self.terminal_frame)
        self.splitter.setSizes([600, 600])

        # Execute Post-Widget Creation Tasks
        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear()
 
    def _build_section(self, config_dict, start_row=0):
        # Extract collapsible settings from config_dict (defaulting to collapsible)
        is_collapsible = config_dict.get("collapsible", True)
        default_collapsed = config_dict.get("default_collapsed", True)

        # Extract section title from subheading item, or fallback to default
        section_title = "Section"
        for k, v in config_dict.items():
            if isinstance(v, dict) and v.get("type") == "subheading":
                section_title = v.get("label", section_title)
                break

        # 1. Check if section should be wrapped in ExpandableSection
        if is_collapsible:
            section_widget = ExpandableSection(
                parent=self.scroll_content,
                title_text=section_title,
                expanded=not default_collapsed,
            )
            content_parent = section_widget.get_content_frame()
        else:
            # Fallback to standard non-collapsible QGroupBox if collapsible is explicitly False
            section_widget = QGroupBox(section_title)
            content_parent = section_widget

        # 2. Reuse existing layout on content_parent if present, otherwise create a new one
        box_layout = content_parent.layout()
        if box_layout is None:
            box_layout = QVBoxLayout(content_parent)
            box_layout.setContentsMargins(4, 4, 4, 4)

        # Inner container for grid layout alignment
        content_widget = QWidget()
        content_grid = QGridLayout(content_widget)
        content_grid.setContentsMargins(0, 0, 0, 0)
        content_grid.setHorizontalSpacing(12)
        content_grid.setVerticalSpacing(getattr(theme, "ROW_SPACING", 8))

        # Match column stretch ratios of the main params_grid
        content_grid.setColumnStretch(0, 1)
        content_grid.setColumnStretch(1, 4)
        content_grid.setColumnStretch(2, 1)

        # Build section items inside content_grid
        current_row = 0
        for key, item in config_dict.items():
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            
            if item_type == "spacer":
                spacer_height = item.get("height", 14)
                spacer_widget = QWidget()
                spacer_widget.setFixedHeight(spacer_height)
                # Ensure transparent / no background or borders
                spacer_widget.setStyleSheet("background: transparent; border: none;")
                content_grid.addWidget(spacer_widget, current_row, 0, 1, 3)
                current_row += 1

            elif item_type == "toggle_button":
                current_row = self._create_toggle_button(
                    key, item, current_row, grid=content_grid
                )
            elif item_type in ("button", "single_button"):
                current_row = self._create_single_button(
                    key, item, current_row, grid=content_grid
                )
            elif item_type == "button_row":
                current_row = self._create_button_row(
                    key, item, current_row, grid=content_grid
                )
            elif item_type == "button_pair":
                current_row = self._create_button_pair(
                    key, item, current_row, grid=content_grid
                )
            elif item_type == "action_with_fields":
                current_row = self._create_action_with_fields(
                    key, item, current_row, grid=content_grid
                )
            elif item_type != "subheading":
                current_row = self._create_standard_widget(
                    key, item, current_row, grid=content_grid
                )

        box_layout.addWidget(content_widget)

        # Add the section into main params_grid spanning all 3 columns
        self.params_grid.addWidget(section_widget, start_row, 0, 1, 3)

        return start_row + 1
    
 
    # -------------------------------------------------------------------------
    # Helper Construction Methods for Custom Widget Types
    # -------------------------------------------------------------------------
    def _create_toggle_button(self, key, item, current_row, grid=None):
      target_grid = grid if grid is not None else self.params_grid
    
      label_text = item.get("label", "Toggle")
      btn = QPushButton(f"{label_text} (OFF)")
      btn.setCheckable(True)
      btn.setChecked(item.get("default", False))
      btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
      btn.toggled.connect(
          lambda checked, b=btn, l=label_text: b.setText(
              f"{l} (ON)" if checked else f"{l} (OFF)"
          )
      )
    
      target_grid.addWidget(btn, current_row, 0, 1, 3)
      self.widgets[key] = btn
      target_grid.setRowMinimumHeight(current_row + 1, 25)
      return current_row + 1
    
    
    def _create_single_button(self, key, item, current_row, grid=None):
      target_grid = grid if grid is not None else self.params_grid
    
      container = QWidget()
      h_layout = QHBoxLayout(container)
      h_layout.setContentsMargins(0, 0, 0, 0)
      h_layout.setSpacing(8)
    
      btn = QPushButton(item.get("label", "Action"))
      btn.setFixedWidth(item.get("button_width", 160))
      h_layout.addWidget(btn)
      h_layout.addStretch(1)
    
      target_grid.addWidget(container, current_row, 0, 1, 3)
      self.widgets[item.get("button_key", key)] = btn
      return current_row + 1
    
    
    def _create_button_row(self, key, item, current_row, grid=None):
      target_grid = grid if grid is not None else self.params_grid
    
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
    
      target_grid.addWidget(container, current_row, 0, 1, 3)
      self.widgets[item.get("key", key)] = buttons_dict
      return current_row + 1
    
    
    def _create_button_pair(self, key, item, current_row, grid=None):
      target_grid = grid if grid is not None else self.params_grid
    
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
        btn1.toggled.connect(
            lambda checked, b=btn1, l=label1: b.setText(
                f"{l} (ON)" if checked else f"{l} (OFF)"
            )
        )
      else:
        btn1 = QPushButton(label1)
    
      btn2 = QPushButton(label2)
      btn1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
      btn2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
      h_layout.addWidget(btn1)
      h_layout.addWidget(btn2)
    
      target_grid.addWidget(container, current_row, 0, 1, 3)
      self.widgets[item.get("key1", "btn_action_2")] = btn1
      self.widgets[item.get("key2", "btn_action_4")] = btn2
    
      target_grid.setRowMinimumHeight(current_row + 1, 25)
      return current_row + 1
    
    
    def _create_action_with_fields(self, key, item, current_row, grid=None):
        target_grid = grid if grid is not None else self.params_grid
    
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
            
            # Read custom field width if set; fallback to default (e.g., 50)
            field_w = field_info.get("width", 50)
            f_entry.setFixedWidth(field_w)
            
            h_layout.addWidget(f_label)
            h_layout.addWidget(f_entry)
            fields_dict[f_key] = f_entry
    
        h_layout.addStretch(1)
    
        target_grid.addWidget(container, current_row, 0, 1, 3)
        self.widgets[item.get("button_key")] = btn
        self.widgets[item.get("fields_key")] = fields_dict
        return current_row + 1
    
    
    def _create_standard_widget(self, key, item, current_row, grid=None):
      target_grid = grid if grid is not None else self.params_grid
      # Use parent container of target grid if available
      parent_container = (
          target_grid.parentWidget()
          if target_grid.parentWidget()
          else self.scroll_content
      )
    
      res = create_gui_widget(
          parent_frame=parent_container,
          key=key,
          item=item,
          row=current_row,
      )
    
      if not res or res[0] is None:
        return current_row + 1
    
      widget_instance, _, next_row = res
      self.widgets[key] = widget_instance
    
      if item.get("type") in ["entry", "filePath", "dropdown"]:
        target_grid.removeWidget(widget_instance)
        target_grid.addWidget(widget_instance, current_row, 1, 1, 2)
    
        if hasattr(widget_instance, "setSizePolicy"):
          widget_instance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
        for child in widget_instance.findChildren((QLineEdit, QComboBox)):
          child.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
      if item.get("type") == "dropdown" and "optionsFromPath" in item:
        dynamic_path_key = item["optionsFromPath"]
        file_filter = item.get("fileTypeFilter", "")
    
        if dynamic_path_key in self.widgets:
          path_widget = self.widgets[dynamic_path_key]
          self.after_widgets_created_tasks.append(
              lambda d=widget_instance, p=path_widget, ff=file_filter: (
                  setup_dynamic_file_options(d, p, ff)
              )
          )
    
      return next_row

    def _add_divider(self, row):
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.params_grid.setRowMinimumHeight(row, 1)
        self.params_grid.addWidget(divider, row + 1, 0, 1, 3)
        self.params_grid.setRowMinimumHeight(row + 2, 1)

        return row + 1
  

    def _apply_font_size(self, new_size):
        theme.FONT_SIZE_BASE = new_size
        if self.theme_manager is not None:
            self.theme_manager.apply(getattr(self.theme_manager, "mode", "dark"))

    def _toggle_theme(self):
        if self.theme_manager is not None:
            self.theme_manager.toggle()
            self._apply_terminal_theme()

    
    def _apply_terminal_theme(self):
        # Force dark background for terminal log widget
        self.terminal_text_widget.setStyleSheet(
            "background-color: #121212; color: #00ff66; border: 1px solid #333;"
        )

    def _setup_terminal_capture(self):
        self.stdout_stream = StreamOutput()
        self.stdout_stream.messageWritten.connect(self._append_terminal_message)
        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream

        print(f"Terminal console successfully initialized.")

    def _append_terminal_message(self, text):
        self.terminal_text_widget.moveCursor(self.terminal_text_widget.textCursor().End)
        self.terminal_text_widget.insertPlainText(text)
        self.terminal_text_widget.moveCursor(self.terminal_text_widget.textCursor().End)

###############################################################################
###############################################################################

class MainWindow(QMainWindow):
    def __init__(self, theme_manager=None):
        super().__init__()
        self.theme_manager = theme_manager

        self.config_widget = ConfigCreatorWidget(theme_manager=self.theme_manager)
        self.setCentralWidget(self.config_widget)

        self.slow_ctrl_VMM   = None
        self.slow_ctrl_R5560 = None
        
        self.init_slow_ctrl()

        self.is_acq_running = False

        self._connect_signals()
        
        self.setWindowTitle("MBUTY - Slow Control")

    def init_slow_ctrl(self):
        
        rbu_p, rbu_f, addr_p, addr_f, cfg_vmm_p, cfg_vmm_f, cfg_r5560_p, cfg_r5560_f = self.config_widget.get_config_paths()

        # print("\n----------------------------------------------------------------------")
        # print("Configuration Paths:")
        # print(f"  RBU Path:         {rbu_p}")
        # print(f"  RBU File:         {rbu_f}")
        # print(f"  Addr Path:        {addr_p}")
        # print(f"  Addr File:        {addr_f}")
        # print(f"  VMM Cfg Path:     {cfg_vmm_p}")
        # print(f"  VMM Cfg File:     {cfg_vmm_f}")
        # print(f"  R5560 Cfg Path:   {cfg_r5560_p}")
        # print(f"  R5560 Cfg File:   {cfg_r5560_f}")
        # print("----------------------------------------------------------------------\n")

        try:
            self.slow_ctrl_VMM = VMMSlowCtrl(
                rbu_path=rbu_p,
                rbu_file=rbu_f,
                addr_path=addr_p,
                addr_file=addr_f,
                cfg_path=cfg_vmm_p,
                cfg_file=cfg_vmm_f,
            )
        except Exception as e:
            print(f"[ERROR] Failed to initialize VMM Slow Ctrl: {e}")
            self.slow_ctrl_VMM = None
            
        try:
            self.slow_ctrl_R5560 = R5560SlowCtrl(
                rbu_path=rbu_p,
                rbu_file=rbu_f,
                addr_path=addr_p,
                addr_file=addr_f,
                cfg_path=cfg_r5560_p,
                cfg_file=cfg_r5560_f,
            )
                        
        except Exception as e:
            print(f"[ERROR] Failed to initialize R5560 Slow Ctrl: {e}")
            self.slow_ctrl_R5560 = None    

    def _connect_signals(self):
        widgets = self.config_widget.widgets

        # Power toggle
        self.btn_toggle_power = widgets.get("btn_toggle_power")
        if self.btn_toggle_power:
            self.btn_toggle_power.clicked.connect(self.handle_power_toggle)

        # IOC Service action row
        ioc_buttons = widgets.get("btn_ioc_row")
        if ioc_buttons:
            for action_name, btn in ioc_buttons.items():
                btn.clicked.connect(lambda checked, act=action_name: self.handle_ioc_action(act))

        # Action Button mappings: widget_key -> handler_function
        action_bindings = {
            "btn_ring_bring_up": self.handle_ring_bring_up,
            "btn_action_2": self.handle_global_warm_init,
            "btn_action_4": self.handle_global_hard_reset,
            "btn_action_3": self.handle_warm_init,
            "btn_action_5": self.handle_hard_reset,
            "btn_force_off": self.handle_force_acq_off,
            "btn_set_registers": self.handle_set_registers,
            "btn_action_6": self.handle_change_threshold_glob,
            "btn_action_7": self.handle_change_threshold_lcl,
        }

        for key, handler in action_bindings.items():
            btn = widgets.get(key)
            if btn:
                btn.clicked.connect(handler)

        # Abort Button (disabled initially)
        btn_rbu_abort = widgets.get("btn_rbu_abort")
        if btn_rbu_abort:
            btn_rbu_abort.clicked.connect(self.handle_rbu_abort)
            btn_rbu_abort.setEnabled(False)

    def handle_set_registers(self):
        """Handler for configuring the R5560 digitiser registers."""
        self.init_slow_ctrl()
        if not self.slow_ctrl_R5560:
            QMessageBox.critical(
                self,
                "Hardware Error",
                "R5560SlowCtrl backend could not be initialized.",
            )
            return

        try:
            self.slow_ctrl_R5560.configureR5560()
            print("[ACTION] R5560 registers configured successfully.\n")
        except Exception as e:
            print(f"[ERROR] Failed to configure R5560 registers: {e}")
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Failed to set R5560 registers:\n{e}",
            )  
            
            
    def handle_change_threshold_glob(self):
        """Handler for updating the threshold on R5560 digitisers."""
        self.init_slow_ctrl()
        if not self.slow_ctrl_R5560:
            QMessageBox.critical(
                self,
                "Hardware Error",
                "R5560SlowCtrl backend could not be initialized.",
            )
            return

        # Retrieve threshold value from the fields dictionary
        threshold_val = 3000  # Default fallback value
        fields_dict = self.config_widget.widgets.get("fields_set_threshold_glob")

        if isinstance(fields_dict, dict):
            # Extract values by calling .text() on QLineEdit widgets
            values = {k: widget.text() for k, widget in fields_dict.items()}
            threshold_str = values.get("threshold", "3000")
            try:
                threshold_val = int(threshold_str)
            except ValueError:
                print(
                    f"[WARN] Invalid threshold input '{threshold_str}'. Falling back to 3000."
                )
                threshold_val = 3000

        try:
            self.slow_ctrl_R5560.changeThreshold_glob(threshold=threshold_val)
            print(f"[ACTION] Threshold changed to {threshold_val} successfully.\n")
        except Exception as e:
            print(f"[ERROR] Failed to change R5560 threshold: {e}")
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Failed to change R5560 threshold:\n{e}",
            )
            
    def handle_change_threshold_lcl(self):
        """Handler for updating the threshold on specific ring and fen R5560 digitisers."""
        self.init_slow_ctrl()
        if not self.slow_ctrl_R5560:
            QMessageBox.critical(
                self,
                "Hardware Error",
                "R5560SlowCtrl backend could not be initialized.",
            )
            return

        # Retrieve inputs from the UI fields dictionary
        threshold_val = 3000
        ring          = 0
        fen           = 0

        fields_dict = self.config_widget.widgets.get("fields_set_threshold_lcl")

        if isinstance(fields_dict, dict):
            # Parse threshold
            try:
                threshold_val = int(fields_dict["threshold"].text())
            except (KeyError, ValueError):
                print("[WARN] Invalid or missing threshold input. Using default 3000.")

            # Parse ring
            try:
                ring = int(fields_dict["ring"].text())
            except (KeyError, ValueError):
                print("[WARN] Invalid or missing ring input. Using default 0.")

            # Parse fen
            try:
                fen = int(fields_dict["fen"].text())
            except (KeyError, ValueError):
                print("[WARN] Invalid or missing fen input. Using default 0.")

        try:
            self.slow_ctrl_R5560.changeThreshold_lcl(
                threshold=threshold_val, ring=ring, fen=fen
            )
            print(
                f"[ACTION] Local threshold changed to {threshold_val} for Ring {ring}, FEN {fen}.\n"
            )
        except Exception as e:
            print(f"[ERROR] Failed to change R5560 local threshold: {e}")
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Failed to change R5560 local threshold:\n{e}",
            )   

    def handle_force_acq_off(self):
        self.init_slow_ctrl()
        if self.slow_ctrl_VMM is None:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend could not be initialized.")
            return

        if self.btn_toggle_power:
            self.btn_toggle_power.setEnabled(False)

        target_state = False  # Hardcoded to turn acquisition OFF

        self.thread = QThread()
        self.worker = AcquisitionWorker(self.slow_ctrl_VMM, target_state)
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
        if self.slow_ctrl_VMM is None:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend could not be initialized.")
            return

        self.btn_toggle_power.setEnabled(False)
        target_state = not self.is_acq_running

        self.thread = QThread()
        self.worker = AcquisitionWorker(self.slow_ctrl_VMM, target_state)
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
            print(f"[ACTION] RBU script finished.\n")
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
        if self.slow_ctrl_VMM:
            self.slow_ctrl_VMM.warm_init_glob()

    def handle_global_hard_reset(self):
        self.init_slow_ctrl()
        if self.slow_ctrl_VMM:
            self.slow_ctrl_VMM.hard_reset_glob()

    def handle_warm_init(self):
        self.init_slow_ctrl()
        if not self.slow_ctrl_VMM:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend is not initialized.")
            return
        fields = self.config_widget.widgets.get("fields_warm_init", {})
        try:
            ring = int(fields.get("ring").text()) if "ring" in fields else 0
            fen  = int(fields.get("fen").text()) if "fen" in fields else 0
            self.slow_ctrl_VMM.warm_init(ring, fen)
        except ValueError:
            print("[ERROR] Ring and FEN must be integers.")

    def handle_hard_reset(self):
        self.init_slow_ctrl()
        if not self.slow_ctrl_VMM:
            QMessageBox.critical(self, "Hardware Error", "VMMSlowCtrl backend is not initialized.")
            return
        fields = self.config_widget.widgets.get("fields_hard_reset", {})
        try:
            ring = int(fields.get("ring").text()) if "ring" in fields else 0
            fen = int(fields.get("fen").text()) if "fen" in fields else 0
            hybrid = int(fields.get("hybrid").text()) if "hybrid" in fields else 0
            self.slow_ctrl_VMM.hard_reset(ring, fen, hybrid)
        except ValueError:
            print("[ERROR] Ring, FEN, and Hybrid must be integers.")
            
###############################################################################
###############################################################################

class StreamOutput(QObject):
    messageWritten = Signal(str)

    def write(self, text):
        self.messageWritten.emit(str(text))

    def flush(self):
        pass

class AcquisitionWorker(QObject):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, slow_ctrl_VMM, target_state):
        super().__init__()
        self.slow_ctrl_VMM = slow_ctrl_VMM
        self.target_state = target_state

    def run(self):
        try:
            if self.target_state:
                self.slow_ctrl_VMM.acq_on()
            else:
                self.slow_ctrl_VMM.acq_off()
            self.finished.emit(self.target_state)
        except Exception as e:
            self.error.emit(str(e))


###############################################################################
###############################################################################
    
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
            
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
###############################################################################
    
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
    
    