# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:32:14 2025

@author: sheilamonera
"""
import sys
import os
import tkinter as tk

# Fixed pixel width for input fields and dropdowns to maintain UI consistency.
FIXED_INPUT_WIDTH = 350

# Label column width for alignment consistency across various widgets in the GUI.
label_width = 200

# Base font sizes for different text elements. These will be scaled based on system DPI.
param_font_size = 9
font_size = 10

# Define a set of colors and a font family to be used consistently throughout the GUI.
light_blue = "#cceeff"
light_green = "#90ee90"
light_red = "#ff6961"
green = "#90EE90"
field_bg_color = "white"
gui_font = "arial"

def get_scaled_font_size(base_size=10):
    """
    Calculates a scaled font size based on the operating system and display DPI
    to ensure consistent font rendering across different environments.

    The function first checks for an environment variable 'CONSOLE_FONT_SIZE'
    to allow manual override of the font size. If not present, it attempts
    to determine the system's DPI (dots per inch) using Tkinter.
    The scaling logic differs for Windows, macOS, and Linux to account for
    their respective font rendering behaviors.

    Args:
        base_size (int): The base font size to be scaled. Defaults to 10.

    Returns:
        int: The calculated and scaled font size.
    """
    # Allow overriding the font size via an environment variable.
    override = os.getenv("CONSOLE_FONT_SIZE")
    if override:
        try:
            return int(override)
        except ValueError:
            # If the override value is not a valid integer, it is ignored,
            # and the DPI-based scaling proceeds.
            pass

    # Create a dummy Tkinter root window to get display information.
    root = tk.Tk()
    root.withdraw()  # Hide the root window as it's only used for information.

    try:
        # Attempt to get the number of pixels per inch (DPI) from Tkinter.
        dpi = root.winfo_fpixels('1i')
    except Exception:
        # Fallback DPI if `winfo_fpixels` fails for any reason.
        dpi = 96

    root.destroy()  # Destroy the dummy root window to free resources.

    # Apply platform-specific scaling logic.
    if sys.platform.startswith("win"):
        # Windows typically handles scaling automatically, so return base size.
        return base_size
    elif sys.platform == "darwin":
        # macOS often requires a larger font size for similar visual appearance.
        return int(base_size * 2)
    else:  # Linux
        # For Linux, scale the font size based on the calculated DPI.
        # Ensure the scaled size is not smaller than the base size.
        scale = dpi / 96
        return max(int(base_size * scale), base_size)

# Set the default and parameter font sizes by calling the scaling function.
# This ensures that the GUI elements adapt to the user's display settings.
font_size = get_scaled_font_size(10)
param_font_size = get_scaled_font_size(9)