# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:23:46 2025

@author: sheilamonera
"""
import tkinter as tk
import tkinter.font as tkfont
from .info_label import InfoLabel
from .base_constants import FIXED_INPUT_WIDTH
from . import base_constants as const


class RangeEntryWidgets:
    """
    A custom Tkinter widget that provides a pair of linked entry fields for defining
    a numeric range (minimum and maximum values).

    It supports validation for either integer or float inputs, visually indicating
    invalid ranges (e.g., non-numeric input or min > max) by changing the background
    color of the entry fields. The widget also supports dynamic font size updates.

    Attributes:
        var_min (tk.StringVar): Tkinter variable holding the string value for the minimum entry.
        var_max (tk.StringVar): Tkinter variable holding the string value for the maximum entry.
        input_validation (str): Specifies the type of validation ('int' or 'float').
        entry_font (tkfont.Font): A Tkinter font object for the entry fields, allowing
                                 dynamic size updates.
        to_label_font (tkfont.Font): A Tkinter font object for the "to" label, allowing
                                    dynamic size updates.
        info_label (InfoLabel): An instance of the custom InfoLabel widget for the
                               main label and its associated tooltip.
        wrapper (tk.Frame): A Tkinter Frame that serves as a container for the
                            min entry, "to" label, and max entry. It has a fixed
                            width to ensure consistent layout.
        entry_min (tk.Entry): The Tkinter Entry widget for the minimum value.
        to_label (tk.Label): The Tkinter Label widget displaying "to" between the entries.
        entry_max (tk.Entry): The Tkinter Entry widget for the maximum value.
        dummy_focus_holder (tk.Frame): An invisible frame used to shift focus away from
                                       the entry fields after validation.
    """

    def __init__(self, parent, row, label_text, default=(0, 1), info_text=None, input_validation="float"):
        """
        Initializes the RangeEntryWidgets widget.

        Args:
            parent (tk.Widget): The parent container widget.
            row (int): The grid row index within the parent's grid where this widget
                       (label and entry fields) will be placed.
            label_text (str): The text to display as the main label for this range input.
            default (tuple): A tuple (min_value, max_value) representing the initial
                             values for the range. Values can be strings or numbers.
                             Defaults to (0, 1).
            info_text (str, optional): The text to display in a tooltip when hovering over
                                       the info icon next to the label. Defaults to None.
            input_validation (str, optional): The type of validation to apply to the inputs.
                                              Can be 'int' for integer validation or 'float'
                                              for floating-point validation. Defaults to 'float'.
        """
        self.var_min = tk.StringVar(value=str(default[0]))
        self.var_max = tk.StringVar(value=str(default[1]))
        self.input_validation = input_validation

        # Create tkfont.Font objects for dynamic font updates for entries and the "to" label
        self.entry_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)
        self.to_label_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        # Create the InfoLabel for the main label and its tooltip
        self.info_label = InfoLabel(parent, label_text, info=info_text)
        self.info_label.grid(row=row, column=0, padx=(5, 0), pady=5, sticky="nw")

        # Calculate initial height for the wrapper frame based on font metrics
        # This ensures the wrapper's height scales with the font size.
        initial_height = self.entry_font.metrics('linespace') + 6  # linespace includes leading
        self.wrapper = tk.Frame(parent, width=FIXED_INPUT_WIDTH, height=initial_height)
        # Prevent the wrapper from growing beyond its specified width/height
        self.wrapper.grid_propagate(False)
        self.wrapper.grid(row=row, column=1, padx=5, pady=5, sticky="ew")

        # Configure column weights within the wrapper to allow entries to expand proportionally
        self.wrapper.grid_columnconfigure(0, weight=1)  # Column for min entry
        self.wrapper.grid_columnconfigure(1, minsize=30)  # Column for "to" label (fixed minimum width)
        self.wrapper.grid_columnconfigure(2, weight=1)  # Column for max entry

        # Create the minimum value entry field
        # The 'width' here acts as a minimum preferred size; the entry will stretch
        # within its weighted column due to sticky="ew" and wrapper.grid_propagate(False).
        self.entry_min = tk.Entry(self.wrapper, textvariable=self.var_min, font=self.entry_font, width=4)
        self.entry_min.grid(row=0, column=0, sticky="ew")

        # Create the "to" label
        self.to_label = tk.Label(self.wrapper, text="to", font=self.to_label_font)
        self.to_label.grid(row=0, column=1, sticky="n", padx=4)

        # Create the maximum value entry field
        self.entry_max = tk.Entry(self.wrapper, textvariable=self.var_max, font=self.entry_font, width=4)
        self.entry_max.grid(row=0, column=2, sticky="ew")

        # Create a dummy focus holder to remove focus from entries when clicking outside
        self.dummy_focus_holder = tk.Frame(parent)
        self.dummy_focus_holder.grid(row=row + 1, column=0)
        self.dummy_focus_holder.lower() # Place it behind other widgets

        # Bind validation triggers
        for entry in [self.entry_min, self.entry_max]:
            # Set focus to the entry after a small delay on click, for consistent behavior
            entry.bind("<Button-1>", lambda e, ent=entry: ent.after(10, ent.focus_set))
            entry.bind("<Return>", self.on_trigger)  # Validate on Enter key press
            entry.bind("<Tab>", self.on_trigger)     # Validate on Tab key press

        # Bind a global click handler to validate when clicking outside of entries
        root = parent.winfo_toplevel() # Get the top-level window
        root.bind_all("<Button-1>", self.handle_click_outside, add="+")

        # Perform initial validation and font update
        self.validate()
        self.update_font()

    def on_trigger(self, *_):
        """
        Callback method triggered when the user presses Enter or Tab within
        either of the entry fields. It initiates validation and shifts focus.
        """
        self.validate()
        self.dummy_focus_holder.focus_set() # Shift focus away from the entries

    def handle_click_outside(self, event):
        """
        Event handler for clicks anywhere in the root window. If the click
        is not on an entry widget, it triggers validation.
        """
        if isinstance(event.widget, tk.Entry):
            return  # Do nothing if the click was on an entry widget
        self.entry_min.after(1, self.validate) # Validate after a short delay

    def validate(self, *_):
        """
        Validates the current input in both entry fields.
        If the range is valid (numeric and min <= max), the background color
        is set to 'white'; otherwise, it's set to a light red to indicate an error.
        """
        color = "white" if self._is_valid() else "#ffdddd"  # Light red for invalid
        self.entry_min.config(bg=color)
        self.entry_max.config(bg=color)

    def get(self):
        """
        Retrieves the validated numeric range.

        Returns:
            list[int | float]: A list containing [min_value, max_value] if the
                               inputs are valid; otherwise, an empty list `[]`.
        """
        if self._is_valid():
            return [self._convert(self.var_min.get()), self._convert(self.var_max.get())]
        return []

    def _convert(self, val):
        """
        Helper method to convert a string value from an entry field to
        either an integer or a float, based on `self.input_validation`.

        Args:
            val (str): The string value to convert.

        Returns:
            int | float: The converted numeric value.
        """
        val = val.strip()
        return int(val) if self.input_validation == "int" else float(val)

    def _is_valid(self):
        """
        Helper method to check the validity of the range.
        It verifies that both inputs are convertible to numbers and that
        the minimum value is less than or equal to the maximum value.

        Returns:
            bool: True if the range is valid, False otherwise.
        """
        try:
            # Check if min <= max after conversion
            return self._convert(self.var_min.get()) <= self._convert(self.var_max.get())
        except ValueError:
            # Conversion failed (e.g., non-numeric input)
            return False

    def update_font(self):
        """
        Updates the font sizes of all relevant widgets within RangeEntryWidgets
        (entries, "to" label, and the InfoLabel). This method should be called
        when the global font size constant `const.param_font_size` changes.
        It also recalculates and updates the height of the wrapper frame.
        """
        # Update InfoLabel's font
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()

        # Update dynamic font objects' sizes
        self.entry_font.config(size=const.param_font_size)
        self.to_label_font.config(size=const.param_font_size)

        # Dynamically update the height of the wrapper frame to match the new font size
        new_height = self.entry_font.metrics('linespace') + 6
        self.wrapper.config(height=new_height)

        # Re-apply validation, as font changes might sometimes affect layout/rendering
        # which could implicitly influence perceived validity or prompt a redraw.
        self.validate()