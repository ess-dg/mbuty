# -*- coding: utf-8 -*-
"""
multi_select_dropdown.py

qtpy replacement for the Tk MultiSelectDropDown.
"""
import os

from qtpy.QtCore import Qt, Signal, QEvent, QPoint
from qtpy.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QLabel,
    QToolButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
)

from .info_label import InfoLabel
from . import theme


class _TagChip(QFrame):
    """A single removable tag showing one selected value on its own line."""

    removed = Signal(str)

    def __init__(self, value, parent=None):
        super().__init__(parent)
        self.value = value
        self.setObjectName("TagChip")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        label = QLabel(value)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(label)

        close_btn = QToolButton()
        close_btn.setText("\u00d7")  # ×
        close_btn.setAutoRaise(True)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(14, 14)
        close_btn.clicked.connect(lambda: self.removed.emit(self.value))
        layout.addWidget(close_btn)


class _MultiSelectPopup(QWidget):
    """Floating checklist for picking items."""

    toggled = Signal(str, bool)

    def __init__(self, options, checked_values, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose)

        checked_values = set(checked_values or [])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter...")
        self._filter.textChanged.connect(self._apply_filter)
        outer.addWidget(self._filter)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        outer.addWidget(self._list)

        for opt in options:
            item = QListWidgetItem(opt)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if opt in checked_values else Qt.Unchecked)
            self._list.addItem(item)

        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemChanged.connect(self._on_item_changed)

        self._filter.setFocus()

    def _on_item_clicked(self, item):
        new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
        item.setCheckState(new_state)

    def _on_item_changed(self, item):
        self.toggled.emit(item.text(), item.checkState() == Qt.Checked)

    def _apply_filter(self, text):
        text = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(text not in item.text().lower())


class MultiSelectDropDown(QWidget):
    """A labeled multi-select dropdown widget displaying one item per line."""

    changed = Signal()

    def __init__(self, parent, label_text, options, default=None, info_text=None):
        super().__init__(parent)
        self._initial_default = default or []
        self.options = []
        self._checked = []
        self.pathToOptions = None
        self._popup = None
        self.reverse = True # make this True to sort filenames Z to A, instead False A -> Z

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

        self.field = QFrame()
        self.field.setObjectName("MultiSelectField")
        self.field.setFrameShape(QFrame.StyledPanel)
        self.field.setMinimumWidth(theme.INPUT_WIDTH)
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.field.setCursor(Qt.PointingHandCursor)
        self.field.installEventFilter(self)

        # Use QVBoxLayout to strictly enforce one tag chip per line
        self._vbox = QVBoxLayout(self.field)
        self._vbox.setContentsMargins(4, 4, 4, 4)
        self._vbox.setSpacing(4)

        self._add_placeholder()

        layout.addWidget(self.field, stretch=1)

        self.set_options(sorted(options, key=str.lower, reverse=self.reverse), default)

    def eventFilter(self, obj, event):
        if obj is self.field and event.type() == QEvent.MouseButtonRelease:
            self._open_popup()
            return True
        return super().eventFilter(obj, event)

    def _open_popup(self):
        if self.pathToOptions:
            self._refresh_from_path()

        self._popup = _MultiSelectPopup(self.options, self._checked, parent=self)
        self._popup.toggled.connect(self._on_item_toggled)
        self._popup.destroyed.connect(self._on_popup_destroyed)

        pos = self.field.mapToGlobal(QPoint(0, self.field.height()))
        self._popup.setMinimumWidth(self.field.width())
        self._popup.move(pos)
        self._popup.show()

    def _on_popup_destroyed(self):
        self._popup = None

    def _on_item_toggled(self, value, is_checked):
        if is_checked and value not in self._checked:
            self._checked.append(value)
        elif not is_checked and value in self._checked:
            self._checked.remove(value)
        self._rebuild_chips()
        self.changed.emit()

    def _add_placeholder(self):
        placeholder = QLabel("Select...")
        placeholder.setEnabled(False)
        self._vbox.addWidget(placeholder)

    def _rebuild_chips(self):
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not self._checked:
            self._add_placeholder()
            self.field.updateGeometry()
            return

        for value in self._checked:
            chip = _TagChip(value, parent=self.field)
            chip.removed.connect(self._remove_value)
            self._vbox.addWidget(chip)

        self.field.updateGeometry()

    def _remove_value(self, value):
        if value in self._checked:
            self._checked.remove(value)
        self._rebuild_chips()
        self.changed.emit()

    def _refresh_from_path(self):
        if not self.pathToOptions:
            return
        path = self.pathToOptions.get('path')
        file_filter = self.pathToOptions.get('filter')
        try:
            if path and os.path.isdir(path):
                new_options = sorted(
                    [f for f in os.listdir(path) if f.endswith(file_filter)], key=str.lower, reverse=self.reverse
                )
            else:
                new_options = []
        except Exception:
            new_options = []
        self._set_option_list(new_options)

    def _set_option_list(self, new_options):
        self.options = new_options
        
        # If we have initial defaults that haven't been applied yet, select them now
        if self._initial_default:
            valid_defaults = [v for v in self._initial_default if v in self.options]
            if valid_defaults:
                # Merge initial defaults into checked without losing user selections
                for v in valid_defaults:
                    if v not in self._checked:
                        self._checked.append(v)
                self._initial_default = []  # Clear after initial application
                
        # Keep checked values that are present in the updated options list
        self._checked = [v for v in self._checked if v in self.options]
        self._rebuild_chips()

    def set_options(self, new_options, default_to_apply=None):
        self._set_option_list(sorted(new_options, key=str.lower, reverse=self.reverse))

        final_default = default_to_apply if default_to_apply is not None else self._initial_default
        valid_default = [v for v in (final_default or []) if v in self.options]
        if valid_default:
            self.set(valid_default)

    def set_new_path_for_options(self, new_path_dict):
        self.pathToOptions = new_path_dict
        self._refresh_from_path()

    def set(self, values):
        values = set(values or [])
        self._checked = [v for v in self.options if v in values]
        self._rebuild_chips()
        self.changed.emit()

    def get(self):
        return list(self._checked)