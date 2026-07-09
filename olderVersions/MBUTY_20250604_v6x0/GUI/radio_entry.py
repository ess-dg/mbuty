# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:24:56 2025

@author: sheilamonera
"""
import tkinter as tk
import tkinter.font as tkfont
from .info_label import InfoLabel
from . import base_constants as const


class RadioEntry:
    """
    A custom Tkinter widget that displays a group of vertically stacked radio buttons
    with an associated label and an optional tooltip. It dynamically updates its font
    based on a global constant.

    Attributes:
        parent (tk.Widget): The parent container widget.
        var (tk.StringVar): The Tkinter variable that holds the currently selected
                            value of the radio buttons.
        radio_buttons (list[tk.Radiobutton]): A list of the created radio button instances.
        radio_button_font (tkfont.Font): A Tkinter font object used for all radio buttons,
                                        allowing dynamic size updates.
        info_label (InfoLabel): An instance of the custom InfoLabel widget for the main label
                                and its associated tooltip.
        radio_frame (tk.Frame): A Tkinter Frame that serves as a container for the radio buttons.
    """

    def __init__(self, parent, row, label_text, options, default=None, info_text=None):
        """
        Initializes the RadioEntry widget.

        Args:
            parent (tk.Widget): The parent container widget where this RadioEntry will be placed.
            row (int): The grid row index within the parent's grid where this widget's
                       label and radio buttons will be placed.
            label_text (str): The text to display as the main label for this group of radio buttons.
            options (list[str]): A list of strings, where each string represents an option
                                 and will become the text for a radio button.
            default (str, optional): The initial value to be selected. If None, the first
                                     option in `options` will be selected by default.
            info_text (str, optional): The text to display in a tooltip when hovering over
                                       the info icon next to the label. Defaults to None.
        """
        self.parent = parent
        # Initialize StringVar with default value; if default is None, use the first option
        self.var = tk.StringVar(value=default or options[0])
        self.radio_buttons = []

        # Create a tk.Font object to manage the font for all radio buttons
        self.radio_button_font = tkfont.Font(
            family=const.gui_font,
            size=const.param_font_size  # Initial font size based on the global constant
        )

        # Create the InfoLabel for the main label and its tooltip
        self.info_label = InfoLabel(parent, label_text, info=info_text)
        # Grid the InfoLabel in the parent's grid, column 0, sticking to the west
        self.info_label.grid(row=row, column=0, sticky="w")

        # Create a Frame to contain the individual radio buttons
        self.radio_frame = tk.Frame(parent)
        # Grid the radio_frame in the parent's grid, column 1, allowing it to expand
        # horizontally to fill its column.
        self.radio_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)

        # Configure the internal grid of radio_frame: make its first column expandable.
        # This ensures that if the font size increases, the radio button text has space
        # to grow without being clipped, as all radio buttons are placed in this column.
        self.radio_frame.grid_columnconfigure(0, weight=1)

        # Create and place each radio button
        for i, opt in enumerate(options):
            radio_btn = tk.Radiobutton(
                self.radio_frame,
                text=opt,
                variable=self.var,
                value=opt,
                font=self.radio_button_font  # Apply the dynamically managed font
            )
            # Place each radio button in a new row within the radio_frame's internal grid,
            # sticking to the west to align them.
            radio_btn.grid(row=i, column=0, sticky="w")
            self.radio_buttons.append(radio_btn)  # Store reference to the button

        # Apply initial font settings for all components
        self.update_font()

    def get(self):
        """
        Retrieves the value of the currently selected radio button.

        Returns:
            str: The value associated with the selected radio button option.
        """
        return self.var.get()

    def update_font(self):
        """
        Updates the font size for all radio buttons within this widget and
        triggers the font update for the associated InfoLabel. This method should
        be called when the global font size constant `const.param_font_size` changes.
        """
        # Update the size of the tk.Font object. This automatically applies the change
        # to all tk.Radiobutton widgets that use this font object.
        self.radio_button_font.config(size=const.param_font_size)

        # If an InfoLabel exists and has an `update_font` method, call it
        # to ensure its font also updates.
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()