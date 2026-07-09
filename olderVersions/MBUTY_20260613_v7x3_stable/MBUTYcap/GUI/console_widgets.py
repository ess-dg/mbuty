# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 14:55:22 2025

@author: sheilamonera
"""
import tkinter as tk
import sys
import re

class ANSIColorTextWidget(tk.Text):
    """
    A custom Tkinter Text widget designed to interpret and display text
    containing basic ANSI color escape codes. This widget is configured
    to be read-only for the user, acting primarily as a display console.
    """
    # Regular expression to find ANSI escape sequences (e.g., '\x1b[...m').
    # This pattern captures the numeric parameters within the escape code.
    ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[([0-9;]+)m')

    # A mapping from standard ANSI foreground color codes to Tkinter color names.
    # Includes both standard and bright (high-intensity) colors.
    COLOR_MAP = {
        '30': 'black',
        '31': 'red',
        '32': 'green',
        '33': 'yellow',
        '34': 'blue',
        '35': 'magenta',
        '36': 'cyan',
        '37': 'white',
        '90': 'gray',
        '91': 'lightcoral',
        '92': 'lightgreen',
        '93': 'lightyellow',
        '94': 'lightblue',
        '95': 'plum',
        '96': 'lightcyan',
        '97': 'white',
    }
    # A mapping from ANSI style codes to internal style names.
    # Currently supports 'bold' and 'reset' for styles.
    STYLE_MAP = {
        '1': 'bold',  # ANSI code for bold text
        '0': 'reset', # ANSI code for resetting all attributes
    }

    def __init__(self, master=None, initial_font_size=10, **kwargs):
        """
        Initializes the ANSIColorTextWidget.

        Args:
            master (tk.Widget, optional): The parent widget. Defaults to None.
            initial_font_size (int): The initial font size for the text. Defaults to 10.
            **kwargs: Arbitrary keyword arguments passed to the tk.Text constructor.
        """
        super().__init__(master, **kwargs)
        self.font_size = initial_font_size
        self._configure_tags()     # Set up Tkinter text tags based on color and style maps.
        self.insert_index = tk.END # Tracks where new text should be inserted (always at the end).
        self.config(state="disabled") # Make the widget read-only by default.

    def update_font_size(self, new_size):
        """
        Updates the font size of the text widget and reconfigures all tags
        to reflect the new size.

        Args:
            new_size (int): The new font size to apply.
        """
        self.font_size = new_size
        self._configure_tags()       # Reconfigure tags with the new font size.
        self.update_idletasks()      # Force an immediate update of the display.

    def _configure_tags(self):
        """
        Configures or reconfigures the Tkinter Text widget tags.
        This method creates tags for default text (reset), foreground colors,
        and text styles (e.g., bold) based on the `COLOR_MAP` and `STYLE_MAP`.
        """
        # Default tag for resetting text attributes (foreground color and font).
        self.tag_configure("reset", foreground="white", font=("Courier New", self.font_size))

        # Configure tags for each ANSI foreground color.
        for code, color_name in self.COLOR_MAP.items():
            self.tag_configure(f"fg_{code}", foreground=color_name)

        # Configure tags for text styles (e.g., bold font).
        self.tag_configure("bold", font=("Courier New", self.font_size, "bold"))

    def write(self, string):
        """
        Processes the incoming string, parsing ANSI escape codes to apply
        appropriate Tkinter tags for color and style, then inserts the
        formatted text into the widget. This method temporarily enables
        the widget for writing and then disables it again.

        Args:
            string (str): The string to be written, potentially containing ANSI escape codes.
        """
        self.config(state="normal") # Temporarily enable the widget for modification.

        # Split the input string by ANSI escape sequences. 
        parts = self.ANSI_ESCAPE_PATTERN.split(string)

        # Initialize variables to keep track of the currently active color and style tags.
        current_color_tag = None
        current_style_tag = None

        # Iterate through the parts of the split string.
        # Even-indexed parts are text segments; odd-indexed parts are ANSI code parameters.
        for i, part in enumerate(parts):
            if i % 2 == 0:  # This is a text segment.
                if part:    # Only insert if there's actual text content.
                    tags_to_apply = []
                    # Add the active color tag if one is set.
                    if current_color_tag:
                        tags_to_apply.append(current_color_tag)
                    # Add the active style tag if one is set.
                    if current_style_tag:
                        tags_to_apply.append(current_style_tag)

                    # If no specific color or style tags are active, apply the "reset" tag
                    # to ensure default formatting.
                    if not tags_to_apply:
                        tags_to_apply.append("reset")

                    # Insert the text part with the determined tags at the end of the widget.
                    self.insert(tk.END, part, tuple(tags_to_apply))
            else:  # This is an ANSI escape code parameter string (e.g., '1' or '32' or '1;32').
                # Split the parameters by semicolon to handle multiple codes in one sequence.
                codes = part.split(';')
                for code in codes:
                    if code == '0':  # ANSI code '0' signifies a reset of all attributes.
                        current_color_tag = None
                        current_style_tag = None
                    elif code in self.COLOR_MAP:
                        # If the code corresponds to a known color, set the current color tag.
                        current_color_tag = f"fg_{code}"
                    elif code in self.STYLE_MAP:
                        # If the code corresponds to a known style.
                        style_name = self.STYLE_MAP[code]
                        if style_name == 'bold':
                            current_style_tag = 'bold'
                        elif style_name == 'reset':
                            # Although '0' handles full reset, this ensures style-only reset too.
                            current_style_tag = None

        self.see(tk.END)           # Scroll the text widget to ensure the latest output is visible.
        self.update_idletasks()    # Force Tkinter to process all pending events, updating the display immediately.
        self.config(state="disabled") # Re-disable the widget to maintain its read-only nature.

    def clear_console(self):
        """
        Clears all text content from the Tkinter Text widget.
        Temporarily enables the widget for deletion and then disables it again.
        """
        self.config(state="normal")  # Temporarily enable the widget for modification.
        self.delete("1.0", tk.END)   # Delete all text from the first character ("1.0") to the end.
        self.config(state="disabled") # Re-disable the widget.

class ConsoleRedirector:
    """
    A utility class to redirect the standard output (sys.stdout) to a
    given Tkinter Text widget (specifically, an ANSIColorTextWidget).
    This allows console print statements to appear within the GUI.
    """
    def __init__(self, text_widget):
        """
        Initializes the ConsoleRedirector.

        Args:
            text_widget (ANSIColorTextWidget): The Tkinter Text widget to which
                                               stdout will be redirected.
        """
        self.text_widget = text_widget
        # Store a direct reference to Python's actual original stdout stream (`sys.__stdout__`)
        self.original_stdout_fallback = sys.__stdout__

    def write(self, string):
        """
        Writes the given string to the associated Tkinter Text widget.
        Includes error handling and a fallback to the original stdout
        if the widget is no longer valid or an error occurs during writing.

        Args:
            string (str): The string to write.
        """
        try:
            # Check if the text_widget still exists and is mapped (visible) before writing.
            # `winfo_exists()` is critical here to prevent errors if the widget
            # has been destroyed (e.g., when the GUI window is closed).
            if self.text_widget and self.text_widget.winfo_exists():
                self.text_widget.write(string)
            else:
                # If the widget is gone (e.g., window closed), print to the actual
                # console stdout as a fallback to prevent loss of output.
                self.original_stdout_fallback.write(string)
        except Exception as e:
            # Catch any other potential errors during writing to the widget
            # and fall back to the original stdout, also printing the error.
            self.original_stdout_fallback.write(f"GUI Console Error: {e} - Original string: {string}")
            self.original_stdout_fallback.flush() # Ensure error message is immediately visible.

    def flush(self):
        """
        Required for stdout redirection. This method ensures that any buffered
        output is immediately written to the text widget. It forces Tkinter
        to update its display. If the widget is gone, it flushes the original stdout.
        """
        if self.text_widget and self.text_widget.winfo_exists():
            self.text_widget.update_idletasks() # Force update of the Tkinter display.
        else:
            self.original_stdout_fallback.flush() # Flush the original stdout if the widget is gone.