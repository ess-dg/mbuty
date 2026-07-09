# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:25:39 2025

@author: sheilamonera
"""
import tkinter as tk
import tkinter.font as tkfont 
from .info_label import InfoLabel
from . import base_constants as const 


class BooleanSelect:
    """
    A horizontal group of radio buttons for selecting between boolean-style options
    like True/False or Yes/No, with a label and optional tooltip.

    Parameters:
        parent (tk.Widget): Parent container widget.
        row (int): Row index for grid layout.
        label_text (str): Text for the label to the left of the radio buttons.
        options (list[str]): List of options (e.g., ['True', 'False'] or ['Yes', 'No']).
        default (str, optional): Default selected option.
        info_text (str, optional): Tooltip text for the label.
    """

    def __init__(self, parent, row, label_text, options, default=None, info_text=None):
        self.var = tk.StringVar(value=default if default is not None else options[0])
        self.radio_buttons = [] # List to store references to individual radio buttons

        self.radio_button_font = tkfont.Font(
            family=const.gui_font,
            size=const.param_font_size # Initial size based on global constant
        )

        # Store a reference to the InfoLabel instance
        self.info_label = InfoLabel(parent, label_text, info=info_text)
        self.info_label.grid(row=row, column=0)

        # Frame to hold horizontal radio buttons
        self.radio_frame = tk.Frame(parent) # Store reference to the frame
        self.radio_frame.grid(row=row, column=1, sticky="w", padx=5)

        for i, opt in enumerate(options):
            radio_btn = tk.Radiobutton(
                self.radio_frame,
                text=opt,
                variable=self.var,
                value=opt,
                font=self.radio_button_font # Apply the dynamic font
            )
            radio_btn.pack(side=tk.LEFT, padx=(0 if i == 0 else 10, 0))
            self.radio_buttons.append(radio_btn) # Store the radio button

        # Call update_font once at initialization to set initial fonts
        self.update_font()

    def get(self):
        """
        Return the selected value, automatically converting 'True'/'False' strings
        to Python booleans if possible.

        Returns:
            bool | str: Boolean value if the string matches 'True' or 'False',
                        otherwise returns the raw string.
        """
        val = self.var.get()
        if val == "True":
            return True
        elif val == "False":
            return False
        return val

    
    def update_font(self):
        """
        Update the font size of the radio buttons and the associated InfoLabel.
        This method will be called by the main GUI when the global font size changes.
        """
        # Update the size of the tk.Font object for radio buttons.
        # All radio buttons linked to this font will automatically update.
        self.radio_button_font.config(size=const.param_font_size)

        # Call the update_font method of the associated InfoLabel
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()
