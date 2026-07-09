# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:30:32 2025

@author: sheilamonera
"""
import tkinter as tk
import tkinter.font as tkfont 
from . import base_constants as const 

class ExpandableSection(tk.Frame): # Inherits from tk.Frame
    """
    A collapsible/expandable section frame with a toggleable header.

    Parameters:
        parent (tk.Widget): Parent container widget.
        title_text (str): Title text displayed on the section header.
        *args, **kwargs: Standard tk.Frame arguments.
    """

    def __init__(self, parent, title_text, *args, **kwargs):
        # Call the constructor of the parent class (tk.Frame)
        super().__init__(parent, *args, **kwargs)

        self.title_text = title_text
        self.is_expanded = False # Initial state: collapsed

        # Create a tkinter.font.Font object for dynamic font updates
        self.header_font = tkfont.Font(
            family=const.gui_font,
            size=const.param_font_size + 2, # Initial size, slightly larger than param_font_size
            weight="bold"
        )

        # Header button with arrow indicator (using tk.Button as requested)
        self.toggle_button = tk.Button(
            self, # Parent is self (the ExpandableSection frame itself)
            text="> " + self.title_text, # Initial text (collapsed arrow)
            command=self.toggle,
            font=self.header_font, # Apply the font directly to tk.Button
            anchor="w", # Align text to the left
            relief="raised", # Set relief to "raised" for a pop-out effect
            borderwidth=1, # Add a thin border to the button
            padx=5, # Add some internal padding to the button
            pady=2
        )
        self.toggle_button.pack(fill="x", expand=True)

        # Content area (initially hidden)
        self.content_frame = tk.Frame(self) # Use self as parent
        # content_frame is initially packed, but then forgotten to hide it
        self.content_frame.pack(fill="x", expand=True)
        self.content_frame.pack_forget() # Initially hidden

        # Call update_font once at initialization to set the correct initial size
        self.update_font()

    def toggle(self):
        """
        Toggle the section between expanded and collapsed states.
        """
        if self.is_expanded:
            self.content_frame.pack_forget() # Use pack_forget to hide
            self.toggle_button.config(text="> " + self.title_text) # Collapsed arrow
        else:
            self.content_frame.pack(fill="x", expand=True) # Use pack to show
            self.toggle_button.config(text="V " + self.title_text) # Expanded arrow
        self.is_expanded = not self.is_expanded

    def get_content_frame(self):
        """
        Return the internal content frame where widgets should be placed.
        Returns:
            tk.Frame: The content frame for placing widgets.
        """
        return self.content_frame

    def update_font(self):
        """
        Update the font size of the expandable section's title (header button).
        This method will be called by the main GUI when the global font size changes.
        """
        # Update the size of the tkfont.Font object.
        # The toggle_button (which uses this font) will update automatically.
        self.header_font.config(size=const.param_font_size + 2) # Maintain +2 offset

