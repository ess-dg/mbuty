# -*- coding: utf-8 -*-
"""
gui_utils.py

qtpy port of the Tk gui_utils.py.
"""
from qtpy.QtWidgets import QLabel, QPushButton, QSizePolicy
from qtpy.QtCore import Qt
from .validated_entry import ValidatedEntry
from .range_entry import RangeEntryWidgets
from .boolean_select import BooleanSelect
from .radio_entry import RadioEntry
from .searchable_dropdown import SearchableDropDown
from .multi_select_dropdown import MultiSelectDropDown
from .file_path_search import FilePathSearch


def create_gui_widget(parent_frame, key, item, row):
    input_type = item["type"]
    label = item.get("label", key)
    layout = parent_frame.layout()

    kwargs = {
        "parent": parent_frame,
        "label_text": label,
        "info_text": item.get("info", None),
    }
    if "default" in item:
        kwargs["default"] = item["default"]

    widget_instance = None

    if input_type == "entry":
        kwargs.update({
            "validation_type": item.get("inputValidation", "any"),
            "value_range": item.get("range"),
        })
        widget_instance = ValidatedEntry(**kwargs)

    elif input_type == "range":
        kwargs["input_validation"] = item.get("inputValidation", "float")
        widget_instance = RangeEntryWidgets(**kwargs)

    elif input_type == "bool":
        kwargs["options"] = item["options"]
        widget_instance = BooleanSelect(**kwargs)

    elif input_type == "radio":
        kwargs["options"] = item["options"]
        widget_instance = RadioEntry(**kwargs)

    elif input_type == "dropdown":
        kwargs["options"] = item.get("options", [])
        widget_instance = SearchableDropDown(**kwargs)

    elif input_type == "multiSelect":
        kwargs["options"] = item.get("options", [])
        widget_instance = MultiSelectDropDown(**kwargs)

    elif input_type == "filePath":
        must_exist = item.get("mustExist")
        if must_exist is not None:
            kwargs["must_exist"] = must_exist
        widget_instance = FilePathSearch(**kwargs)

    elif input_type == "subheading":
        widget_instance = QLabel(label)
        widget_instance.setProperty("role", "header")
        widget_instance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    elif input_type == "button":
        widget_instance = QPushButton(label)

        def on_button_click():
            command = item.get("command")
            if callable(command):
                command()

        widget_instance.clicked.connect(on_button_click)

    else:
        print(f"Unknown input type: {input_type} for key {key}")
        return None, None, row + 1

    layout.addWidget(widget_instance, row, 0, 1, 2, Qt.AlignLeft)
    return widget_instance, widget_instance, row + 1


def setup_dynamic_file_options(widget, file_path_widget, file_filter):
    """
    Dynamically updates `widget` options based on the folder path from
    `file_path_widget`.
    """
    def update_path_for_dropdown():
        if file_path_widget:
            folder = file_path_widget.get()
            widget.set_new_path_for_options({'path': folder, 'filter': file_filter})
        else:
            widget.set_new_path_for_options(None)

    widget._update_file_list = update_path_for_dropdown
    update_path_for_dropdown()

    if file_path_widget is not None and hasattr(file_path_widget, "changed"):
        file_path_widget.changed.connect(update_path_for_dropdown)


def setup_dynamic_option_resolver(widget, resolver_func, widgets_dict, watch_keys):
    """
    Dynamically updates `widget` options based on a resolver function and a
    list of dependency keys to watch for changes.
    """
    def update_options():
        try:
            resolved_data = resolver_func(widgets_dict)
            if isinstance(resolved_data, tuple) and len(resolved_data) == 2:
                path, file_extension = resolved_data
                if hasattr(widget, 'set_new_path_for_options'):
                    widget.set_new_path_for_options({'path': path, 'filter': file_extension})
                elif hasattr(widget, 'set_options_from_path'):
                    widget.set_options_from_path(path, file_extension)
                else:
                    if hasattr(widget, 'set_options'):
                        widget.set_options([])
            else:
                new_options = resolved_data
                if hasattr(widget, 'set_options'):
                    widget.set_options(new_options)
        except Exception as e:
            print(f"Error resolving dynamic options for {widget.__class__.__name__}: {e}")
            if hasattr(widget, 'set_options'):
                widget.set_options([])

    widget._update_file_list = update_options
    update_options()

    for key in watch_keys:
        dep_widget = widgets_dict.get(key)
        if dep_widget is not None and hasattr(dep_widget, "changed"):
            dep_widget.changed.connect(update_options)


def setup_dynamic_must_exist(widget, resolver_func, widgets_dict, watch_keys):
    """
    Dynamically updates `widget.must_exist` based on a resolver function and a
    list of dependency keys to watch for changes. Mirrors
    setup_dynamic_option_resolver's wiring pattern, but for the mustExist flag
    on filePath widgets instead of options.
    """
    def update_must_exist():
        try:
            result = resolver_func(widgets_dict)
        except Exception as e:
            print(f"Error resolving dynamic mustExist for {widget.__class__.__name__}: {e}")
            return
        if hasattr(widget, "set_must_exist"):
            widget.set_must_exist(result)

    update_must_exist()

    for key in watch_keys:
        dep_widget = widgets_dict.get(key)
        if dep_widget is not None and hasattr(dep_widget, "changed"):
            dep_widget.changed.connect(update_must_exist)


def should_show(depends_on, widgets_dict):
    if not depends_on:
        return True

    def evaluate(condition):
        if isinstance(condition, tuple) and len(condition) == 2:
            key, required = condition
            widget = widgets_dict.get(key)
            if widget is None:
                return False
            val = widget.get() if hasattr(widget, "get") else None
            return val == required or (isinstance(required, (list, tuple)) and val in required)

        if isinstance(condition, dict):
            if "and" in condition:
                return all(evaluate(sub) for sub in condition["and"])
            if "or" in condition:
                return any(evaluate(sub) for sub in condition["or"])

        return False

    return evaluate(depends_on)


def extract_dependency_keys(depends_on):
    keys = set()
    if not depends_on:
        return keys
    if isinstance(depends_on, tuple) and len(depends_on) == 2:
        keys.add(depends_on[0])
    elif isinstance(depends_on, dict):
        logic_key = "and" if "and" in depends_on else "or"
        for sub in depends_on.get(logic_key, []):
            keys.update(extract_dependency_keys(sub))
    elif isinstance(depends_on, list):
        for sub in depends_on:
            keys.update(extract_dependency_keys(sub))
    return keys


def setup_visibility_resolver(widget, depends_on, widgets_dict):
    if not depends_on:
        return

    def update_visibility():
        widget.setVisible(should_show(depends_on, widgets_dict))

    update_visibility()

    for key in extract_dependency_keys(depends_on):
        dep_widget = widgets_dict.get(key)
        if dep_widget is not None and hasattr(dep_widget, "changed"):
            dep_widget.changed.connect(update_visibility)