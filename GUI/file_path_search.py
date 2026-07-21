# -*- coding: utf-8 -*-
"""
file_path_search.py

qtpy replacement for the Tk FilePathSearch (path entry with directory
autocomplete, existence validation, and an offer to create missing
directories).
"""
import os
from pathlib import Path

from qtpy.QtCore import QDir, Signal
from qtpy.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QToolButton, QCompleter,
    QFileSystemModel, QFileDialog, QMessageBox,
)

from .info_label import InfoLabel
from . import theme


class FilePathSearch(QWidget):
    """
    A labeled path entry with directory autocomplete, a browse button, and
    existence validation.
    """

    pathChanged = Signal()
    changed = Signal()  # uniform alias gui_utils' dependency watching relies on; emitted alongside pathChanged

    def __init__(self, parent, label_text, default="", info_text=None, must_exist=True):
        super().__init__(parent)
        self.must_exist = must_exist
        self._last_emitted_path = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

        self.entry = QLineEdit(default)
        self.entry.setMinimumWidth(theme.INPUT_WIDTH - 30)
        layout.addWidget(self.entry, stretch=1)

        self._fs_model = QFileSystemModel()
        self._fs_model.setRootPath("")
        self._fs_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self._completer = QCompleter(self._fs_model)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.entry.setCompleter(self._completer)

        self.entry.textEdited.connect(self._prime_completer_directory)

        self.browse_btn = QToolButton()
        self.browse_btn.setText("...")
        self.browse_btn.clicked.connect(self._browse)
        layout.addWidget(self.browse_btn)

        # Validate visual state on text change, but don't emit changed signal until editing is finished
        self.entry.textChanged.connect(lambda _: self.validate_path(show_pop_ups=False, emit_signal=False))
        self.entry.editingFinished.connect(lambda: self.validate_path(show_pop_ups=False, emit_signal=True))
        self.pathChanged.connect(self.changed.emit)

        self.validate_path(show_pop_ups=False, emit_signal=False)

    def _prime_completer_directory(self, text):
        clean_text = text.strip()
        parent_dir = clean_text if clean_text.endswith(os.sep) else os.path.dirname(clean_text)
        if parent_dir and os.path.exists(parent_dir):
            self._fs_model.index(parent_dir)

    def _browse(self):
        start_dir = self.entry.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select folder", start_dir)
        if chosen:
            normalized = os.path.normpath(chosen)
            self.entry.setText(normalized)
            self.validate_path(show_pop_ups=False, emit_signal=True)

    def validate_path(self, show_pop_ups=False, emit_signal=True):
        """
        Validate the current entry text.
        """
        raw_path = self.entry.text().strip()

        if not raw_path:
            theme.set_widget_state(self.entry, "invalid" if show_pop_ups else "warning")
            if show_pop_ups:
                QMessageBox.critical(self, "Invalid Path", "Path cannot be empty.")
            return False

        try:
            norm_path = os.path.normpath(raw_path)
            path_obj = Path(norm_path)

            if path_obj.is_dir():
                theme.set_widget_state(self.entry, "")
                if emit_signal and self._last_emitted_path != norm_path:
                    self._last_emitted_path = norm_path
                    self.pathChanged.emit()
                return True

            if path_obj.exists():
                theme.set_widget_state(self.entry, "warning")
                if show_pop_ups:
                    QMessageBox.critical(
                        self, "Path Type Mismatch",
                        f"The path '{raw_path}' exists but is not a directory. "
                        "Please choose a directory path.",
                    )
                return False

            if self.must_exist:
                theme.set_widget_state(self.entry, "invalid")
                return False

            if not show_pop_ups:
                theme.set_widget_state(self.entry, "")
                return True

            response = QMessageBox.question(
                self, "Create Directory?",
                f"The directory path '{raw_path}' does not exist. Do you want to create it?",
            )
            if response == QMessageBox.Yes:
                try:
                    path_obj.mkdir(parents=True, exist_ok=True)
                    QMessageBox.information(self, "Directory Created", f"Directory '{raw_path}' has been created.")
                    theme.set_widget_state(self.entry, "")
                    if emit_signal and self._last_emitted_path != norm_path:
                        self._last_emitted_path = norm_path
                        self.pathChanged.emit()
                    return True
                except OSError as e:
                    QMessageBox.critical(self, "Creation Error", f"Failed to create directory '{raw_path}':\n{e}")
                    theme.set_widget_state(self.entry, "invalid")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An unexpected error occurred:\n{e}")
                    theme.set_widget_state(self.entry, "invalid")
            else:
                QMessageBox.information(self, "Path Not Created", "Please choose another directory path.")
                theme.set_widget_state(self.entry, "invalid")
            return False

        except Exception as e:
            theme.set_widget_state(self.entry, "invalid")
            if show_pop_ups:
                QMessageBox.critical(self, "Invalid Path Syntax/Error", f"'{raw_path}':\n{e}")
            return False

    def get(self):
        """Return the normalized path if valid, else ''."""
        value = self.entry.text().strip()
        if value:
            norm_value = os.path.normpath(value)
            if os.path.isdir(norm_value):
                return norm_value
            if not self.must_exist:
                return norm_value
        return ""

    def set(self, path):
        normalized = os.path.normpath(path) if path else ""
        self.entry.setText(normalized)
        self.validate_path(show_pop_ups=False, emit_signal=True)