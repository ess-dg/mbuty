# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:05:15 2025

@author: sheilamonera
"""
import tkinter as tk
import re
import os
import tkinter.font as tkfont
from .info_label import InfoLabel
from . import base_constants as const


class ValidatedEntry:
    """
    A custom Tkinter widget providing a labeled entry field with robust input validation,
    dynamic background coloring to indicate validity, and support for various input types.
    It also includes a live tooltip that displays the full text of the entry if it overflows
    its visible width, and dynamic font sizing.

    Attributes:
        parent (tk.Widget): The parent container widget.
        var (tk.StringVar): Tkinter variable holding the current text input of the entry.
        validation_type (str): The type of validation to apply (e.g., 'int', 'float',
                               'scientific', 'localPath', 'remotepath', 'host:port', 'fileNumbers', 'any').
        value_range (tuple | None): A tuple (min, max) for numeric validation, or None if no range is applied.
        entry_font (tkfont.Font): A Tkinter font object for the entry field, allowing
                                 dynamic size updates.
        container_frame (tk.Frame): A container frame holding the label and entry widget
                                    for better layout management and destruction.
        info_label (InfoLabel): An instance of the custom InfoLabel widget for the main label
                                and its associated tooltip.
        entry (tk.Entry): The Tkinter Entry widget where the user inputs text.
        dummy_focus_holder (tk.Frame): An invisible frame used to shift focus away from the
                                       entry fields after validation.
        root (tk.Tk | tk.Toplevel): A reference to the top-level (root) window.
        _tooltip_after_id (str | None): ID for the Tkinter `after` call used to delay tooltip display,
                                        enabling cancellation.
        tooltip (tk.Toplevel): The top-level window used to display the live tooltip.
        tooltip_label_font (tkfont.Font): A Tkinter font object for the tooltip label.
        tooltip_label (tk.Label): The Tkinter Label widget displaying the tooltip text.
        _tooltip_mouse_inside (bool): Flag to track if the mouse cursor is currently over the entry.
    """

    def __init__(self, parent, row, label_text,
                 validation_type="any", default="",
                 info_text=None, value_range=None):
        """
        Initializes the ValidatedEntry widget.

        Args:
            parent (tk.Widget): The parent container widget where this ValidatedEntry will be placed.
            row (int): The grid row index within the parent's grid where this widget will be placed.
            label_text (str): The text to display as the main label for this entry.
            validation_type (str, optional): The type of validation to apply. Supported types
                                             include 'int', 'float', 'scientific', 'localPath',
                                             'remotepath', 'host:port', 'fileNumbers', and 'any'.
                                             Defaults to 'any'.
            default (str, optional): The initial text value for the entry field. Defaults to an empty string.
            info_text (str, optional): The text to display in a tooltip when hovering over the
                                       info icon next to the label. Defaults to None.
            value_range (tuple, optional): A tuple (min_value, max_value) for numeric validation types.
                                           If provided, the input must fall within this range. Defaults to None.
        """
        self.parent = parent
        self.var = tk.StringVar(value=default)
        self.validation_type = validation_type
        self.value_range = value_range

        # Create a tkfont.Font object for the main entry field, allowing dynamic size updates
        self.entry_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        # Create a container frame for the label and entry for organized layout
        self.container_frame = tk.Frame(parent)
        self.container_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        # Configure internal columns of the container_frame
        self.container_frame.grid_columnconfigure(0, minsize=const.label_width) # Fixed width for the label column
        self.container_frame.grid_columnconfigure(1, weight=1) # Entry column expands to fill available space

        # Create the InfoLabel for the main label and its tooltip
        self.info_label = InfoLabel(self.container_frame, label_text, info=info_text)
        self.info_label.grid(row=0, column=0) # Place InfoLabel within its container_frame

        # Create the Entry widget
        self.entry = tk.Entry(self.container_frame, textvariable=self.var, font=self.entry_font)
        self.entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5) # Place Entry within its container_frame

        # Dummy focus holder to enable clearing focus from the entry fields manually
        self.dummy_focus_holder = tk.Frame(self.container_frame)
        self.dummy_focus_holder.grid(row=1, column=0) # Placed in a separate row within container_frame
        self.dummy_focus_holder.lower() # Send it to the bottom of the stacking order

        # Bind validation triggers to keyboard events
        self.entry.bind("<Return>", self.on_trigger) # Validate on Enter key press
        self.entry.bind("<Tab>", self.on_trigger)   # Validate on Tab key press

        # Manual delay for click-based focus to ensure consistency with global bindings
        self.entry.bind("<Button-1>", lambda e: self.entry.after(10, self.entry.focus_set))

        # Get a reference to the top-level window
        self.root = self.entry.winfo_toplevel()

        # Bind a global click handler to trigger validation when the user clicks outside the entry
        self.root.bind_all("<Button-1>", self.handle_click_outside, add="+")

        # Initialize tooltip's `after` ID for cancellation
        self._tooltip_after_id = None

        # Add the live tooltip functionality for text overflow
        self._add_live_tooltip()

        # Perform initial validation and font update
        self.validate()
        self.update_font()

    def destroy(self):
        """
        Cleans up resources and unbinds events associated with this ValidatedEntry
        instance to prevent errors when the widget or its parent is destroyed.
        """
        # Cancel any pending 'after' calls related to the tooltip mechanism
        if self._tooltip_after_id:
            try:
                self.entry.after_cancel(self._tooltip_after_id)
            except tk.TclError:
                pass # The widget might already be destroyed, implicitly cancelling `after`

        # Destroy the tooltip Toplevel window if it exists and is still active
        if hasattr(self, 'tooltip') and self.tooltip.winfo_exists():
            self.tooltip.destroy()

        # Destroy the main container frame for this ValidatedEntry instance,
        # which in turn destroys all its child widgets (label, entry, dummy_focus_holder).
        if hasattr(self, 'container_frame') and self.container_frame.winfo_exists():
            self.container_frame.destroy()

    @staticmethod
    def _parse_file_input(input_string):
        """
        Parses a string representing file numbers (e.g., "1-50", "1,2,5,8", "1-30,35,50")
        and returns a sorted list of unique integers.

        Args:
            input_string (str): The string to parse.

        Returns:
            list[int]: A sorted list of unique integers. Returns an empty list if
                       parsing fails or if the input is empty/invalid.
        """
        file_numbers = set()
        if not input_string.strip():
            return []

        parts = input_string.split(',')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start = int(start_str)
                    end = int(end_str)
                    if start <= end:
                        file_numbers.update(range(start, end + 1))
                    else:
                        return [] # Invalid range (start > end)
                except ValueError:
                    return [] # Non-integer in range
            else:
                try:
                    file_numbers.add(int(part))
                except ValueError:
                    return [] # Non-integer single value

        return sorted(list(file_numbers))

    def on_trigger(self, event):
        """
        Callback method triggered when the user presses Enter or Tab within
        the entry field. It initiates validation and shifts focus away from the entry.
        """
        # Defensive check: Ensure the entry widget still exists before acting
        if not self.entry.winfo_exists():
            return
        self.validate()
        self.dummy_focus_holder.focus_set() # Shift focus to the dummy holder

    def handle_click_outside(self, event):
        """
        Event handler for global clicks in the root window. If the click occurs
        outside this entry field (and its immediate container/tooltip), it triggers validation.
        """
        # Defensive check: Ensure the entry widget still exists before acting
        if not self.entry.winfo_exists():
            return

        # Check if the clicked widget is this entry, a child of its container frame,
        # or part of its tooltip. If so, do not validate.
        if event.widget == self.entry or \
           (hasattr(self, 'container_frame') and self.container_frame.winfo_exists() and \
            event.widget in self.container_frame.winfo_children()) or \
           (hasattr(self, 'tooltip') and self.tooltip.winfo_exists() and event.widget == self.tooltip_label):
            return

        # If click is outside, schedule a delayed validation
        self.entry.after(1, self._delayed_validate, event.widget)

    def _delayed_validate(self, clicked_widget):
        """
        Performs validation after a slight delay, typically used when focus is lost
        due to a click elsewhere. Ensures the click wasn't on the entry itself.
        """
        # Defensive check: Ensure the entry widget still exists before acting
        if not self.entry.winfo_exists():
            return
        if clicked_widget != self.entry:
            self.validate()

    def validate(self):
        """
        Validates the current content of the entry field based on its `validation_type`
        and `value_range`. The entry's background color is updated to 'white' for
        valid input or '#ffdddd' (light red) for invalid input.
        """
        # Defensive check: Ensure the entry widget still exists before configuring it
        if not self.entry.winfo_exists():
            return

        value = self.var.get().strip()
        # Handle empty string validation based on type
        if not value:
            # Empty string is invalid for most types unless explicitly handled (like fileNumbers below)
            if self.validation_type != 'fileNumbers':
                self.entry.config(bg="#ffdddd")
                return
            elif self.validation_type == 'fileNumbers':
                # For 'fileNumbers', an empty string is considered a valid (empty) input
                self.entry.config(bg="white")
                return

        if self._is_valid(value):
            self.entry.config(bg="white")
        else:
            self.entry.config(bg="#ffdddd")

    def _is_in_range(self, numeric_value):
        """
        Checks if a given numeric value falls within the specified `value_range`.

        Args:
            numeric_value (int | float): The number to check.

        Returns:
            bool: True if the value is within the range or if no range is specified, False otherwise.
        """
        if self.value_range is None:
            return True
        return self.value_range[0] <= numeric_value <= self.value_range[1]

    def _is_valid_file_numbers(self, value_string):
        """
        Validates if the input string can be correctly parsed into a list of file numbers
        using the `_parse_file_input` static method.

        Args:
            value_string (str): The input string to validate.

        Returns:
            bool: True if the string is a valid format for file numbers (including empty), False otherwise.
        """
        # An empty input is valid for 'fileNumbers'
        if not value_string.strip():
            return True

        parsed_list = self._parse_file_input(value_string)
        # If parsing results in an empty list AND the original string was not empty,
        # it indicates a parsing error (invalid format).
        if not parsed_list and value_string.strip():
            return False
        return True

    def _is_valid(self, value):
        """
        Performs type-specific validation on the input string based on `self.validation_type`.

        Args:
            value (str): The string value from the entry field.

        Returns:
            bool: True if the value is valid according to its type and range, False otherwise.
        """
        try:
            if self.validation_type == "int":
                return self._is_in_range(int(value))
            elif self.validation_type == "float":
                return self._is_in_range(float(value))
            elif self.validation_type == "scientific":
                # Matches standard or scientific notation floats
                return bool(re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)([eE][-+]?\d+)?', value))
            elif self.validation_type == "localPath":
                # Checks if the path exists on the local filesystem
                return os.path.exists(value)
            elif self.validation_type == "remotepath":
                # Validates a simple remote path format (e.g., user@host:/path/to/file)
                return bool(re.match(r"^[\w.-]+@[\d.]+:.*", value))
            elif self.validation_type == "host:port":
                # Validates a host:port format
                parts = value.strip().split(":")
                if len(parts) != 2:
                    return False
                host, port = parts
                # Basic host validation (letters, numbers, hyphen, dot)
                if not re.match(r"^[\w\.-]+$", host):
                    return False
                # Port range validation
                return 1 <= int(port) <= 65535
            elif self.validation_type == "fileNumbers":
                # Validates a string of file numbers (e.g., "1-50, 60, 65-70")
                return self._is_valid_file_numbers(value)
            # Default for "any" or unknown types: consider all non-empty values valid
            return True
        except Exception:
            # Catch any conversion or parsing errors and treat as invalid
            return False

    def get(self):
        """
        Retrieves the validated and parsed value from the entry field.

        Returns:
            str | int | float | list[int]: The parsed value based on `validation_type`.
                                           Returns an empty string or empty list (`[]` for fileNumbers)
                                           if the current input is invalid.
        """
        value = self.var.get().strip()
        if not self._is_valid(value):
            if self.validation_type == "fileNumbers":
                return []
            return "" # Return empty string for invalid input of other types

        if self.validation_type == "int":
            return int(value)
        elif self.validation_type == "float" or self.validation_type == "scientific":
            return float(value)
        elif self.validation_type == "fileNumbers":
            return self._parse_file_input(value)
        else:
            return value # Return raw string for "any", "localPath", "remotepath", "host:port"

    def _add_live_tooltip(self):
        """
        Initializes or re-initializes the live tooltip functionality.
        The tooltip appears when the mouse hovers over the entry field and
        the entry's text content overflows its visible width. It displays the full text.
        """
        # Clean up any existing tooltip to prevent duplicates
        if hasattr(self, 'tooltip') and self.tooltip.winfo_exists():
            self.tooltip.destroy()
            self._tooltip_after_id = None

        # Create the Toplevel window for the tooltip
        self.tooltip = tk.Toplevel(self.entry)
        self.tooltip.withdraw()          # Hide initially
        self.tooltip.overrideredirect(True) # Remove window decorations (border, title bar)
        self.tooltip.configure(bg="lightyellow", padx=1, pady=1)

        # Create a font object for the tooltip label, linked to the global param_font_size
        self.tooltip_label_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        # Create the Label within the tooltip Toplevel
        self.tooltip_label = tk.Label(
            self.tooltip,
            text="",
            background="lightyellow",
            relief="solid",
            borderwidth=1,
            justify="left",
            wraplength=const.FIXED_INPUT_WIDTH, # Wrap tooltip text at the fixed input width
            font=self.tooltip_label_font
        )
        self.tooltip_label.pack()

        self._tooltip_mouse_inside = False

        def text_overflows():
            """Checks if the text in the entry field exceeds its visible width."""
            if not self.entry.winfo_exists():
                return False
            text = self.var.get()
            text_width = self.entry_font.measure(text)
            entry_width = max(self.entry.winfo_width(), 100) # Use a minimum width to avoid division by zero or tiny widths
            return text_width > entry_width

        def show_tooltip_delayed():
            """Displays the tooltip after a short delay if text overflows and mouse is still inside."""
            # Defensive checks: Ensure widgets exist before interacting
            if not self.entry.winfo_exists() or not self.tooltip.winfo_exists():
                return
            if not self._tooltip_mouse_inside:
                return # Only show if mouse is still over the entry

            self.entry.update_idletasks() # Ensure layout information is up-to-date
            if not text_overflows():
                self.tooltip.withdraw() # Hide if text no longer overflows
                return

            value = self.var.get().strip()
            self.tooltip_label.config(text=value)

            # Position tooltip directly below the entry field
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            self.tooltip.geometry(f"+{x}+{y}")
            self.tooltip.deiconify() # Make the tooltip visible

        def on_enter(event=None):
            """Event handler for mouse entering the entry field."""
            if not self.entry.winfo_exists():
                return
            self._tooltip_mouse_inside = True
            # Schedule the tooltip to show after a short delay
            self._tooltip_after_id = self.entry.after(150, show_tooltip_delayed)

        def on_leave(event=None):
            """Event handler for mouse leaving the entry field."""
            if not self.entry.winfo_exists():
                return
            self._tooltip_mouse_inside = False
            self.tooltip.withdraw() # Hide tooltip immediately
            if self._tooltip_after_id:
                try:
                    self.entry.after_cancel(self._tooltip_after_id) # Cancel any pending `show_tooltip_delayed`
                except tk.TclError:
                    pass # The `after` call might have already been executed or widget destroyed
                self._tooltip_after_id = None

        # Bind mouse events to the entry field for tooltip control
        self.entry.bind("<Enter>", on_enter)
        self.entry.bind("<Leave>", on_leave)

    def update_font(self):
        """
        Updates the font sizes of the entry field, its live tooltip, and the
        associated InfoLabel. This method should be called when the global
        font size constant `const.param_font_size` changes.
        """
        # Defensive check: Ensure the entry widget still exists before updating
        if not self.entry.winfo_exists():
            return

        # Update the InfoLabel's font
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()

        # Update the font size for the main entry field
        self.entry_font.config(size=const.param_font_size)

        # Update the font size for the tooltip label if it exists
        if hasattr(self, 'tooltip_label_font') and self.tooltip_label_font:
            self.tooltip_label_font.config(size=const.param_font_size)
            # If the tooltip is currently visible, re-create it to reflect the new font size
            if hasattr(self, 'tooltip') and self.tooltip.winfo_exists() and self.tooltip.winfo_ismapped():
                self._add_live_tooltip() # Rebuilds tooltip with new font and size