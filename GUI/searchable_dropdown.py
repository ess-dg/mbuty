# -*- coding: utf-8 -*-
"""
searchable_dropdown.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique

A single-select dropdown with type-to-filter search, built on
QComboBox(editable=True) + QCompleter:

- typing filters the popup list                  -> QCompleter(filterMode=...)
- click outside / Escape closes the popup         -> built into the popup
- arrow keys navigate the popup list               -> built in
- the popup follows the widget on scroll/resize    -> built in

This file wires options in/out on top of that and adds the
get()/set()/set_options()/set_new_path_for_options() API and
"selection must come from the option list" validation behavior the rest
of the app relies on.
"""
import os

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QWidget, QHBoxLayout, QComboBox, QCompleter

from .info_label import InfoLabel
from . import theme


class _RefreshingComboBox(QComboBox):
    """A QComboBox that refreshes its item list from a folder right
    before the popup opens. Ignores wheel events to prevent scroll hijacking."""

    def __init__(self, refresh_callback, parent=None):
        super().__init__(parent)
        self._refresh_callback = refresh_callback
        self.setFocusPolicy(Qt.ClickFocus)
        self.setEditable(True)
        
        line_edit = self.lineEdit()
        line_edit.setFocusPolicy(Qt.ClickFocus)
        # Install event filter on line edit to capture clicks and show popup
        line_edit.installEventFilter(self)
        
        # Block wheel events on the internal view
        if self.view():
            self.view().installEventFilter(self)

    def showPopup(self):
        if self._refresh_callback:
            self._refresh_callback()
        super().showPopup()
        # Re-install event filter on the view after popup shows
        if self.view():
            self.view().installEventFilter(self)

    def wheelEvent(self, event):
        """Ignore wheel events to allow parent page scrolling."""
        event.ignore()

    def eventFilter(self, obj, event):
        """Block wheel events on the popup view, show popup on line edit click."""
        from qtpy.QtCore import QEvent
        
        # Show popup when clicking the line edit (if not already visible)
        if obj == self.lineEdit() and event.type() == QEvent.MouseButtonPress:
            if not self.view() or not self.view().isVisible():
                self.showPopup()
            return False  # Allow normal processing to continue
        
        # Block wheel events on the popup view
        if event.type() == QEvent.Wheel:
            return True  # Consume the event, don't pass it on
        
        return super().eventFilter(obj, event)


class SearchableDropDown(QWidget):
    """
    A single-select dropdown with type-to-filter search. Only values
    present in `options` (or "") count as a valid selection — typing
    something that doesn't match anything leaves get() returning None
    and the field styled invalid, same as the Tk version.

    Parameters:
        parent: parent widget
        label_text (str): label text
        options (list[str]): selectable options
        default (str, optional): initially selected option
        info_text (str, optional): tooltip text for the label
    """

    changed = Signal()  # uniform signal name gui_utils' dependency watching relies on

    def __init__(self, parent, label_text, options, default=None, info_text=None):
        super().__init__(parent)
        self._initial_default = default
        self.options = []
        self.selected_item = None
        self.pathToOptions = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

        self.combo = _RefreshingComboBox(self._refresh_from_path)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setMinimumWidth(theme.INPUT_WIDTH)

        self._completer = QCompleter()
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.combo.setCompleter(self._completer)

        layout.addWidget(self.combo, stretch=1)

        self.combo.activated.connect(self._on_activated)
        self.combo.lineEdit().editingFinished.connect(self.validate_selection)
        self.combo.lineEdit().textEdited.connect(self._on_text_edited)

        self.set_options(sorted(options, key=str.lower), default)

    # ------------------------------------------------------------------
    def _on_activated(self, index):
        """Fired when the user picks an item from the popup list."""
        self.set(self.combo.itemText(index))

    def _on_text_edited(self, text):
        """Live-validate as the user types, same red/white feedback as Tk."""
        if text == "" or text in self.options:
            self.selected_item = text if text != "" else None
        else:
            self.selected_item = None
        self.validate_selection()

    def _refresh_from_path(self):
        if not self.pathToOptions:
            return
        path = self.pathToOptions.get('path')
        file_filter = self.pathToOptions.get('filter')
        try:
            if path and os.path.isdir(path):
                new_options = sorted(
                    [f for f in os.listdir(path) if f.endswith(file_filter)], key=str.lower
                )
            else:
                new_options = []
        except Exception:
            new_options = []
        self._set_option_list(new_options)

    def _set_option_list(self, new_options):
        self.options = new_options
        current_text = self.combo.currentText()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(self.options)
        self.combo.setEditText(current_text)
        self.combo.blockSignals(False)
        self._completer.setModel(self.combo.model())

    # ------------------------------------------------------------------
    # public API 
    # ------------------------------------------------------------------
    def set_options(self, new_options, default_to_apply=None):
        self._set_option_list(sorted(new_options, key=str.lower))

        final_default = default_to_apply if default_to_apply is not None else self._initial_default
        if final_default is not None and final_default in self.options:
            self.set(final_default)
        elif self.selected_item not in self.options:
            self.selected_item = None
            self.combo.setEditText("")

        self.validate_selection()

    def set_new_path_for_options(self, new_path_dict):
        self.pathToOptions = new_path_dict
        self._refresh_from_path()

        if self.selected_item is not None and self.selected_item in self.options:
            self.combo.setEditText(self.selected_item)
        elif self._initial_default is not None and self._initial_default in self.options:
            self.set(self._initial_default)
        else:
            self.set("")

    def validate_selection(self):
        valid = self.selected_item is not None
        theme.set_widget_state(self.combo, "" if valid else "invalid")
        self.changed.emit()

    def set(self, value):
        if value == "" or value in self.options:
            self.selected_item = value if value != "" else None
            self.combo.setEditText(value)
            self.validate_selection()

    def get(self):
        return self.selected_item