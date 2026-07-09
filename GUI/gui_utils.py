#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module provides helper functions for creating and managing GUI widgets
based on a configuration. It supports dynamic updates of widget options
and visibility based on other widget states.

Created on Thu Jul 3 15:30:02 2025

@author: sheilamonera
"""
import tkinter as tk
from GUI import (
    SearchableDropDown,
    ValidatedEntry,
    MultiSelectDropDown,
    RangeEntryWidgets,
    RadioEntry,
    BooleanSelect,
    FilePathSearch,
)
import GUI.base_constants as const
import tkinter.font as tkfont

def create_gui_widget(parent_frame, key, item, row, existing_widgets_for_dynamic_paths=None):
    """
    Creates and places a single input widget based on configuration metadata.
    This function contains the common logic for widget instantiation and basic layout.

    Parameters:
        parent_frame (tk.Frame): The parent frame where the input row should be placed.
        key (str): The full configuration key representing the parameter.
        item (dict): Metadata describing the parameter (type, label, default, etc.).
        row (int): Current row number in the layout grid.
        existing_widgets_for_dynamic_paths (dict, optional): A dictionary of already created widgets.
                                                              This is passed from the caller for `setup_dynamic_file_options`
                                                              and similar dynamic option setups.
    Returns:
        tuple: (widget_instance, row_frame_or_widget_itself, updated_row, widget_info_for_font_list)
                - widget_instance: The created custom widget or Tkinter widget (Label, Button).
                - row_frame_or_widget_itself: The `tk.Frame` that contains the label and the widget.
                                              For 'subheading' and 'button' (if directly gridded), this will be the `widget_instance` itself.
                - updated_row: The new row index (row + 1).
                - widget_info_for_font_list: A dictionary containing information needed to add to the font-dynamic list
                                             (widget, type, font_offset, style). Returns `None` for regular custom widgets
                                             that handle their own font updates internally.
    """
    input_type = item["type"]
    label = item.get("label", key)

    row_frame = tk.Frame(parent_frame)
    
    # Configure grid for standard input types
    if input_type not in ["subheading", "button"]:
        row_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        row_frame.grid_columnconfigure(0, minsize=const.label_width)
        row_frame.grid_columnconfigure(1, minsize=const.FIXED_INPUT_WIDTH, weight=0)
    
    # Common keyword arguments for widget initialization
    kwargs = {
        "parent": row_frame,
        "row": 0,
        "label_text": label,
        "info_text": item.get("info", None),
    }
    if "default" in item:
        kwargs["default"] = item["default"]
    
    widget_instance = None
    widget_info_for_font_list = None

    # Widget creation based on input type
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
            kwargs["mustExist"] = must_exist
        widget_instance = FilePathSearch(**kwargs)
        
    elif input_type == "subheading":
        subheading_label = tk.Label(
            parent_frame,
            text=label,
            font=(const.gui_font, const.param_font_size + 1, "bold", "underline"),
            anchor="w",
            pady=5,
        )
        subheading_label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 5))
        widget_instance = subheading_label
        row_frame = subheading_label  # Subheading itself acts as the row frame for layout purposes
        widget_info_for_font_list = {
            "widget": subheading_label,
            "type": "label",
            "font_offset": 1,
            "style": ("bold", "underline")
        }
        
    elif input_type == "button":
        def on_button_click():
            """
            Handles button click events, prioritizing a custom command handler if provided.
            """
            command = item.get("command")
            if callable(command):
                command()

        # Place the row_frame itself in the parent_frame, spanning two columns
        row_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        
        # Configure columns within the row_frame for the button.
        # Column 0 for the "label" space, with its fixed minimum width.
        row_frame.grid_columnconfigure(0, minsize=const.label_width)
        # Column 1 for the "input" space, where the button will reside. Make it expandable.
        row_frame.grid_columnconfigure(1, weight=1)

        btn = tk.Button(
            row_frame, # Parent is the correctly gridded row_frame
            text=label,
            command=on_button_click,
            relief="raised",
            bg=const.light_blue,
            font=(const.gui_font, const.param_font_size, "bold"),
            padx=10, pady=3
        )
        # Place the button in column 1 of the row_frame and make it stick to east-west
        # to fill the entire width of column 1.
        btn.grid(row=0, column=1, sticky="ew", pady=5)
        
        widget_instance = btn
        widget_info_for_font_list = {
            "widget": btn,
            "type": "button",
            "font_offset": 0,
            "style": ("bold",)
        }
    else:
        print(f"Unknown input type: {input_type} for key {key}")
        return None, None, row + 1, None

    # For custom composite widgets, indicate that they handle their own font updates
    if widget_instance and hasattr(widget_instance, 'update_font') and input_type not in ["subheading", "button"]:
        widget_info_for_font_list = {
            "widget": widget_instance,
            "type": "custom_composite",
            "font_offset": 0,
            "style": ()
        }

    return widget_instance, row_frame, row + 1, widget_info_for_font_list


def setup_dynamic_file_options(widget, file_path_widget, file_filter):
    """
    Dynamically updates `widget` options based on the folder path from `file_path_widget`.

    On initialization, preserves the widget's current selection.
    On path change, sets the `pathToOptions` for the widget to refresh on display.

    Parameters:
        widget: The widget whose options will be updated (e.g., a `SearchableDropDown`).
        file_path_widget: The `FilePathSearch` widget that provides the folder path.
        file_filter (str): The file extension filter to apply (e.g., "*.txt").
    """

    def update_path_for_dropdown(*_):
        """
        Callback function to update the dropdown options when the file path changes.
        """
        if file_path_widget:
            folder = file_path_widget.get()
            widget.set_new_path_for_options({'path': folder, 'filter': file_filter})
        else: # Clear path options if widget is gone
            widget.set_new_path_for_options(None)

    # Assign the update function to the widget for external triggering (if needed)
    widget._update_file_list = update_path_for_dropdown
    # Initial update to populate options
    update_path_for_dropdown()

    # Trace changes in the file path widget's variable to trigger updates
    if hasattr(file_path_widget, "var"):
        file_path_widget.var.trace_add("write", update_path_for_dropdown)

def setup_dynamic_option_resolver(widget, resolver_func, widgets_dict, watch_keys):
    """
    Dynamically updates `widget` options based on a resolver function
    and a list of dependency keys to watch for changes.

    Args:
        widget: The widget whose options will be updated (must support `set_options` or `set_new_path_for_options`).
        resolver_func: Callable that takes `widgets_dict` and returns either:
                       - A list of options (for direct setting).
                       - A tuple (path, file_extension) (for setting options from a path).
        widgets_dict (dict): A dictionary of all widget instances, keyed by their configuration keys.
        watch_keys (list): List of configuration keys whose changes should trigger the update.
    """
    def update_options(*_):
        """
        Callback function to resolve and update widget options when dependencies change.
        """
        try:
            resolved_data = resolver_func(widgets_dict)
            if isinstance(resolved_data, tuple) and len(resolved_data) == 2:
                path, file_extension = resolved_data
                if hasattr(widget, 'set_new_path_for_options'):
                    widget.set_new_path_for_options({'path': path, 'filter': file_extension})
                elif hasattr(widget, 'set_options_from_path'):
                    widget.set_options_from_path(path, file_extension)
                else:
                    print(f"Warning: Widget {widget.__class__.__name__} does not support dynamic path-based options. Falling back to 'set_options' with empty list.")
                    if hasattr(widget, 'set_options'):
                        widget.set_options([])
            else:
                new_options = resolved_data
                if hasattr(widget, 'set_options'):
                    widget.set_options(new_options)
                else:
                    print(f"Warning: Widget {widget.__class__.__name__} does not support 'set_options'.")
        except Exception as e:
            print(f"Error resolving dynamic options for {widget.__class__.__name__}: {e}")
            if hasattr(widget, 'set_options'):
                widget.set_options([])

    # Assign the update function to the widget for external triggering (if needed)
    widget._update_file_list = update_options
    # Initial update to populate options
    update_options()

    # Trace changes in dependency widgets to trigger updates
    for key in watch_keys:
        dep_widget = widgets_dict.get(key)
        if dep_widget and hasattr(dep_widget, "var"):
            dep_widget.var.trace_add("write", update_options)


def should_show(depends_on, widgets_dict):
    """
    Evaluates whether a widget should be visible, based on `dependsOn` logic
    defined in the configuration.

    Parameters:
        depends_on (dict or tuple): The dependency logic. Can be a tuple (key, required_value)
                                    or a dictionary with "and" or "or" keys containing sub-conditions.
        widgets_dict (dict): A dictionary of all widget instances, keyed by their configuration keys.

    Returns:
        bool: True if the widget should be shown, False otherwise.
    """
    if not depends_on:
        return True

    def evaluate(condition):
        """
        Recursively evaluates a single dependency condition.
        """
        if isinstance(condition, tuple) and len(condition) == 2:
            key, required = condition
            widget = widgets_dict.get(key)
            if widget is None:
                return False  # Dependency widget not found
            val = widget.get() if hasattr(widget, "get") else None
            # Check if the current value matches the required value or is in a list of required values
            return val == required or (isinstance(required, (list, tuple)) and val in required)

        if isinstance(condition, dict):
            if "and" in condition:
                return all(evaluate(sub) for sub in condition["and"])
            if "or" in condition:
                return any(evaluate(sub) for sub in condition["or"])

        return False  # Invalid condition format

    return evaluate(depends_on)


def extract_dependency_keys(depends_on):
    """
    Recursively extracts all widget keys involved in the dependency logic.

    Parameters:
        depends_on (dict or tuple): The dependency logic, as defined in the configuration.

    Returns:
        set: A set of unique widget keys that are part of the dependency.
    """
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

def update_widget_fonts(widgets_to_update, base_font_size, gui_font_family):
    """
    Updates the font size and style for a list of dynamically sized widgets.

    Args:
        widgets_to_update (list): A list of dictionaries, where each dict contains:
                                  - "widget": The Tkinter widget instance.
                                  - "type": A string indicating the widget type (e.g., "label", "button", "custom_composite").
                                  - "font_offset" (optional): An integer offset from the base_font_size.
                                  - "style" (optional): A tuple of font styles (e.g., "bold", "underline").
        base_font_size (int): The current base font size to apply.
        gui_font_family (str): The font family to use (e.g., "Arial").
    """
    for widget_info in widgets_to_update:
        widget = widget_info["widget"]
        font_offset = widget_info.get("font_offset", 0)
        current_style = widget_info.get("style", ())
        widget_type = widget_info["type"]

        # Handle custom composite widgets that manage their own font updates
        if widget_type == "custom_composite":
            if hasattr(widget, 'update_font'):
                widget.update_font()
        # Handle standard Tkinter widgets
        elif isinstance(widget, tk.Widget) and widget.winfo_exists():
            target_font = tkfont.Font(family=gui_font_family, size=base_font_size + font_offset)

            # Apply font styles
            if current_style:
                if "bold" in current_style:
                    target_font.config(weight="bold")
                if "underline" in current_style:
                    target_font.config(underline=True)

            try:
                widget.config(font=target_font)
            except tk.TclError:
                # Catch TclError if the widget has been destroyed
                pass