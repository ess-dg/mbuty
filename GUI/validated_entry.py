# -*- coding: utf-8 -*-
"""
validated_entry.py

qtpy replacement for the Tk ValidatedEntry. All validation_type semantics
(int, float, scientific, localPath, remotepath, host:port, fileNumbers, any)
and get() return types are ported 1:1 — same regexes, same "invalid returns
'' or [] " behavior — so gui_config.py's schema doesn't need to change.

What's simpler here than the Tk version:
- No dummy_focus_holder / root.bind_all("<Button-1>", ...) "click outside"
  hack. QLineEdit.editingFinished already fires exactly when focus leaves
  the field, and we additionally validate on every keystroke for live
  feedback — Qt handles the focus tracking natively either way.
- No hand-built Toplevel tooltip with manual position math and an `after`
  timer to detect overflow. Qt's setToolTip() + native hover timing
  replaces all of `_add_live_tooltip()`; we just decide *when* to attach
  a tooltip (text overflows the field) using fontMetrics() instead of
  winfo_width()/font.measure().
"""
import re
import os

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget, QHBoxLayout, QLineEdit

from .info_label import InfoLabel
from . import theme


class ValidatedEntry(QWidget):
    """
    A labeled entry field with type-specific validation and invalid-state
    styling.

    Parameters:
        parent: parent widget
        label_text (str): label text
        validation_type (str): one of 'int', 'float', 'scientific',
            'localPath', 'remotepath', 'host:port', 'fileNumbers', 'any'
        default (str): initial text
        info_text (str, optional): tooltip text for the label
        value_range (tuple, optional): (min, max) for 'int'/'float' types
    """

    valueChanged = Signal()  # emitted whenever the field is confirmed valid
    changed = Signal()  # uniform alias gui_utils' dependency watching relies on; emitted alongside valueChanged

    def __init__(self, parent, label_text, validation_type="any", default="",
                 info_text=None, value_range=None):
        super().__init__(parent)
        self.validation_type = validation_type
        self.value_range = value_range

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

        self.entry = QLineEdit(str(default))
        self.entry.setMinimumWidth(theme.INPUT_WIDTH)
        layout.addWidget(self.entry, stretch=1)

        self.entry.textChanged.connect(self._on_text_changed)
        self.valueChanged.connect(self.changed.emit)
        self.validate()

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    def _on_text_changed(self, _text):
        self._update_overflow_tooltip()
        self.validate()

    def validate(self):
        value = self.entry.text().strip()
        valid = self._is_valid(value) if value else (self.validation_type == "fileNumbers")
        theme.set_widget_state(self.entry, "" if valid else "invalid")
        if valid:
            self.valueChanged.emit()
        return valid

    def _update_overflow_tooltip(self):
        """Only show a tooltip (the full text) when it doesn't fit in the field —
        mirrors the Tk version's "live tooltip on overflow" without the manual
        Toplevel/positioning code; Qt's own hover-tooltip timing takes it from here."""
        text = self.entry.text()
        text_width = self.entry.fontMetrics().horizontalAdvance(text)
        if text_width > self.entry.width() - 10:
            self.entry.setToolTip(text)
        else:
            self.entry.setToolTip("")

    def _is_in_range(self, numeric_value):
        if self.value_range is None:
            return True
        return self.value_range[0] <= numeric_value <= self.value_range[1]

    @staticmethod
    def _parse_file_input(input_string):
        """Parse '1-50, 60, 65-70' style strings into a sorted list of ints."""
        file_numbers = set()
        if not input_string.strip():
            return []
        for part in input_string.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start, end = int(start_str), int(end_str)
                    if start <= end:
                        file_numbers.update(range(start, end + 1))
                    else:
                        return []
                except ValueError:
                    return []
            else:
                try:
                    file_numbers.add(int(part))
                except ValueError:
                    return []
        return sorted(file_numbers)

    def _is_valid_file_numbers(self, value_string):
        if not value_string.strip():
            return True
        parsed = self._parse_file_input(value_string)
        if not parsed and value_string.strip():
            return False
        return True

    def _is_valid(self, value):
        try:
            if self.validation_type == "int":
                return self._is_in_range(int(value))
            elif self.validation_type == "float":
                return self._is_in_range(float(value))
            elif self.validation_type == "scientific":
                return bool(re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)([eE][-+]?\d+)?', value))
            elif self.validation_type == "localPath":
                return os.path.exists(value)
            elif self.validation_type == "remotepath":
                return bool(re.match(r"^[\w.-]+@[\d.]+:.*", value))
            elif self.validation_type == "host:port":
                parts = value.strip().split(":")
                if len(parts) != 2:
                    return False
                host, port = parts
                if not re.match(r"^[\w\.-]+$", host):
                    return False
                return 1 <= int(port) <= 65535
            elif self.validation_type == "fileNumbers":
                return self._is_valid_file_numbers(value)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # value access
    # ------------------------------------------------------------------
    def get(self):
        """Same return semantics as the Tk version: parsed value if valid,
        '' (or [] for fileNumbers) if not."""
        value = self.entry.text().strip()
        if not self.validate():
            return [] if self.validation_type == "fileNumbers" else ""

        if self.validation_type == "int":
            return int(value)
        elif self.validation_type in ("float", "scientific"):
            return float(value)
        elif self.validation_type == "fileNumbers":
            return self._parse_file_input(value)
        else:
            return value

    def set(self, value):
        self.entry.setText(str(value))