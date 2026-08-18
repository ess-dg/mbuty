# -*- coding: utf-8 -*-
"""
MBUTYconfigGen_GUI.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique

Qt-based GUI for generating and editing detector configuration files.
"""
import os
import json

from qtpy.QtCore import Qt
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
    QMessageBox,
    QSplitter,
    QScrollArea,
    QFrame,
    QSizePolicy,
)

from GUI import theme
from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options
from lib.config_generator import generateDefaultDetConfig

currentPath = os.path.abspath(os.path.dirname(__file__)) + os.sep

ui_config = {
    "edit_section": {
        "subtitle.edit_existing": {
            "type": "subheading",
            "label": "Edit Existing File"
        },
        "fileManagement.configFilePath": {
            "label": "Config Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, 'config'),
            "info": "The directory containing the configuration files."
        },
        "fileManagement.configFileName": {
            "label": "Select Config File",
            "type": "dropdown",
            "default": "",
            "optionsFromPath": "fileManagement.configFilePath",
            "fileTypeFilter": ".json",
            "info": "Select the JSON configuration file to edit."
        },
        "editFileButton": {
            "label": "Load & Edit File",
            "type": "button",
            "command": None
        },
    },
    "new_file_section": {
        "subtitle.make_new": {
            "type": "subheading",
            "label": "Make a New File"
        },
        "path": {
            "label": "Output Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, 'config'),
            "inputValidation": "localPath",
            "info": "The directory where the new configuration file will be saved."
        },
        "detectorName": {
            "label": "Detector Name",
            "type": "entry",
            "info": "Name of the detector. Output will be <detectorName>.json"
        },
        "detectorType": {
            "label": "Detector Type",
            "type": "bool",
            "options": ["MB", "MG", "He3", "SKADI", "NMX"],
            "default": "MB",
            "info": "Select detector type: MB, MG, He3, SKADI or NMX."
        },
        "instrumentName": {
            "label": "Instrument Name",
            "type": "dropdown",
            "options": ["TBL", "AMOR", "ESTIA", "FREIA", "TREX", "MIRACLES", "CSPEC", "BIFROST", "VESPA", "SKADI", "NMX"],
            "default": "ESTIA",
            "info": "Select the instrument according to the detector type."
        },
        "units": {
            "label": "Number of Units",
            "type": "entry",
            "default": "2",
            "inputValidation": "int",
            "info": "Number of units (must be an integer)."
        },
        "orientation": {
            "label": "Orientation",
            "type": "bool",
            "options": ["vertical", "horizontal"],
            "default": "vertical",
            "info": "Physical orientation of the detector."
        },
        "operationMode": {
            "label": "Operation Mode",
            "type": "bool",
            "options": ["normal", "clustered"],
            "default": "normal",
            "info": "Operational mode for the detector."
        },
        "createFileButton": {
            "label": "Create New File",
            "type": "button",
            "command": None
        },
    }
}


class ConfigCreatorWidget(QWidget):
    """Qt widget for creating, loading, and editing detector configuration JSON files."""

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.widgets = {}
        self.json_file_path = None
        self.after_widgets_created_tasks = []

        self._build_ui()
        self._set_single_panel_layout()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # --- Left Panel: Parameter Form ---
        self.params_container = QWidget()
        params_layout = QVBoxLayout(self.params_container)
        params_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.params_grid = QGridLayout(self.scroll_content)
        self.params_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.params_grid.setHorizontalSpacing(10)
        self.params_grid.setVerticalSpacing(theme.ROW_SPACING)

        # Header Title - bigger than the subheadings and centered over the form
        title_label = QLabel("Detector Configuration Management")
        title_label.setFont(theme.base_font(size=theme.FONT_SIZE_HEADER + 8, bold=True))
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.params_grid.addWidget(title_label, 0, 0, 1, 2, alignment=Qt.AlignHCenter)

        if self.theme_manager is not None:
            theme_btn = QToolButton()
            theme_btn.setText("\u263d")  # crescent moon
            theme_btn.setToolTip("Toggle light/dark mode")
            theme_btn.setStyleSheet("font-size: 20pt;")
            theme_btn.clicked.connect(self.theme_manager.toggle)
            self.params_grid.addWidget(theme_btn, 0, 2, alignment=Qt.AlignRight)

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
        self.params_grid.addWidget(font_row, 1, 0, 1, 3)

        self.params_grid.setRowMinimumHeight(1, 14)  # breathing room below the title

        current_row = 2

        # Build "Edit Existing File" section
        current_row = self._build_section(ui_config["edit_section"], start_row=current_row)
        if "editFileButton" in self.widgets:
            self.widgets["editFileButton"]["widget"].clicked.connect(self.edit_existing_config)

        # Divider between "Edit Existing File" and "Make a New File"
        current_row = self._add_divider(current_row)

        # Build "Make a New File" section
        current_row = self._build_section(ui_config["new_file_section"], start_row=current_row)
        if "createFileButton" in self.widgets:
            self.widgets["createFileButton"]["widget"].clicked.connect(self._create_new_config_file)

        scroll.setWidget(self.scroll_content)
        params_layout.addWidget(scroll)

        # --- Right Panel: JSON Editor ---
        self.json_editor_frame = QGroupBox("Edit Configuration File")
        json_layout = QVBoxLayout(self.json_editor_frame)

        self.json_text_widget = QPlainTextEdit()
        self.json_text_widget.setFont(theme.mono_font(size=theme.FONT_SIZE_CONSOLE))
        json_layout.addWidget(self.json_text_widget)

        self.save_json_button = QPushButton("Save Edits")
        self.save_json_button.setFont(theme.base_font(size=theme.FONT_SIZE_BASE, bold=True))
        self.save_json_button.clicked.connect(self._save_edited_json)
        json_layout.addWidget(self.save_json_button)

        self.splitter.addWidget(self.params_container)
        self.splitter.addWidget(self.json_editor_frame)

        # Resolve dynamic path options after all widgets exist
        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear()

    def _apply_font_size(self, new_size):
        theme.FONT_SIZE_BASE = new_size
        if self.theme_manager is not None:
            self.theme_manager.apply(self.theme_manager.mode)

    def _build_section(self, config_dict, start_row=0):
        current_row = start_row
        for key, item in config_dict.items():
            res = create_gui_widget(
                parent_frame=self.scroll_content,
                key=key,
                item=item,
                row=current_row
            )

            if not res:
                continue

            widget_instance = res[0]
            next_row = res[2]

            if widget_instance:
                self.widgets[key] = {"type": item["type"], "widget": widget_instance}

                if item["type"] == "dropdown":
                    dynamic_path_key = item.get("optionsFromPath")
                    file_filter = item.get("fileTypeFilter")
                    if dynamic_path_key and file_filter:
                        self.after_widgets_created_tasks.append(
                            lambda w=widget_instance, dpk=dynamic_path_key, ff=file_filter:
                                setup_dynamic_file_options(w, self.widgets.get(dpk)["widget"], ff)
                        )

            current_row = next_row

        return current_row

    def _add_divider(self, row):
        """Insert a full-width horizontal rule with breathing room above/below, return next row."""
        self.params_grid.setRowMinimumHeight(row, 18)  # space above the line

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.params_grid.addWidget(divider, row + 1, 0, 1, 2)

        self.params_grid.setRowMinimumHeight(row + 2, 18)  # space below the line

        return row + 3

    def _set_single_panel_layout(self):
        self.json_editor_frame.setVisible(False)
        self.splitter.setSizes([640, 0])
        # Shrink top-level window to fit the snug single-panel layout
        parent_window = self.window()
        if parent_window and parent_window != self:
            parent_window.resize(640, parent_window.height())
        else:
            self.resize(640, self.height())

    def _set_dual_panel_layout(self):
        self.json_editor_frame.setVisible(True)
        # Expand top-level window to comfortably show both panels side-by-side
        parent_window = self.window()
        if parent_window and parent_window != self:
            parent_window.resize(1220, parent_window.height())
        else:
            self.resize(1220, self.height())
        self.splitter.setSizes([620, 600])

    def _get_input_values_from_section(self, section_config):
        missing_fields = []
        data = {}

        for key, item in section_config.items():
            if item["type"] in ["subheading", "button"]:
                continue

            widget_info = self.widgets.get(key)
            if not widget_info or not hasattr(widget_info["widget"], "get"):
                continue

            val = widget_info["widget"].get()
            param_label = item.get('label', key)

            if val in ("", None, []):
                missing_fields.append(f"'{param_label}'")
            else:
                data[key] = val

        if missing_fields:
            QMessageBox.critical(
                self,
                "Missing Fields",
                "Please fill in or correct the following fields:\n- " + "\n- ".join(missing_fields)
            )
            return None
        return data

    def _load_config_for_editing(self, file_path):
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "File Not Found", f"The file '{file_path}' does not exist.")
            return

        self.json_file_path = file_path

        try:
            with open(self.json_file_path, 'r') as f:
                json_content = f.read()

            self.json_text_widget.clear()
            try:
                parsed_json = json.loads(json_content)
                pretty_json = json.dumps(parsed_json, indent=4)
                self.json_text_widget.setPlainText(pretty_json)
            except json.JSONDecodeError:
                self.json_text_widget.setPlainText(json_content)
                QMessageBox.warning(self, "Warning", "The selected file does not contain valid JSON. Displaying as plain text.")

            self.json_text_widget.setFocus()
            filename = os.path.basename(self.json_file_path)
            self.save_json_button.setText(f"Save Edits to {filename}")

            self._set_dual_panel_layout()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file for editing: {e}")

    def edit_existing_config(self):
        data = self._get_input_values_from_section(ui_config["edit_section"])
        if data is None:
            return

        selected_directory = data["fileManagement.configFilePath"]
        selected_file_name = data["fileManagement.configFileName"]

        full_file_path = os.path.join(selected_directory, selected_file_name)
        self._load_config_for_editing(full_file_path)
        QMessageBox.information(self, "Success", f"File '{selected_file_name}' loaded successfully for editing.")

    def _create_new_config_file(self):
        data = self._get_input_values_from_section(ui_config["new_file_section"])
        if data is None:
            return

        output_directory = data["path"]
        detector_name = data["detectorName"]
        file_name = f"{detector_name}.json"
        file_path = os.path.join(output_directory, file_name)

        overwrite = False
        if os.path.exists(file_path):
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"The file '{file_name}' already exists.\n\nDo you want to overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                QMessageBox.information(self, "Choose New Name", "Please choose a different detector name and try again.")
                return
            overwrite = True

        try:
            config_args = data.copy()
            config_args["overwrite"] = overwrite

            generated_file_path, flag = generateDefaultDetConfig(**config_args)

            if flag is False:
                QMessageBox.warning(
                    self,
                    "Configuration Alert",
                    "WARNING: Potential configuration mismatch! Instrument and detector type do not match!"
                )

            if generated_file_path is None:
                QMessageBox.critical(self, "Error", "Config file generation failed (check console for backend errors).")
                return

            self._load_config_for_editing(generated_file_path)
            QMessageBox.information(self, "Success", f"Configuration generated successfully in '{output_directory}'. You can now edit it in the panel.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create new config file: {e}")

    def _save_edited_json(self):
        if not self.json_file_path:
            QMessageBox.warning(self, "No File", "No JSON file has been generated or loaded yet to save.")
            return

        edited_content = self.json_text_widget.toPlainText().strip()

        try:
            parsed_json = json.loads(edited_content)
            with open(self.json_file_path, 'w') as f:
                json.dump(parsed_json, f, indent=4)
            QMessageBox.information(self, "Save Success", f"JSON configuration saved successfully to '{self.json_file_path}'!")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format. Please correct the syntax before saving:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving the JSON file: {e}")


if __name__ == "__main__":
    import sys as _sys
    from qtpy.QtWidgets import QApplication

    app = QApplication(_sys.argv)
    
    # Read theme mode from command-line arguments if provided
    mode = "dark"
    if len(_sys.argv) > 1:
        mode = _sys.argv[1]

    theme_manager = theme.ThemeManager(app, mode=mode)
    window = ConfigCreatorWidget(theme_manager=theme_manager)
    window.setWindowTitle("Detector Configuration Management")
    window.resize(640, 640)
    window.show()
    _sys.exit(app.exec_())