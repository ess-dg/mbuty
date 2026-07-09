# -*- coding: utf-8 -*-
"""
Created on Tue Jun 24 09:57:48 2025

@author: sheilamonera
"""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from . import base_constants as const


class LineNumberedText(tk.Frame):
    """
    A custom Tkinter widget that combines a Text widget with a Canvas
    to display line numbers alongside the text content. It supports dynamic
    font updates and automatic adjustment of line number column width.

    Attributes:
        line_numbers (tk.Canvas): The canvas widget responsible for drawing line numbers.
        text (tk.Text): The main text entry widget where content is displayed and edited.
        scrollbar (ttk.Scrollbar): The vertical scrollbar for the text widget.
    """

    def __init__(self, parent, font=("Courier", 10)):
        """
        Initializes the LineNumberedText widget.

        Args:
            parent (tk.Widget): The parent Tkinter widget.
            font (tuple, optional): A tuple specifying the font family and size
                                    for the text content. Defaults to ("Courier", 10).
        """
        super().__init__(parent)

        # Configure grid layout: line numbers column (0) and text column (1)
        self.grid_columnconfigure(1, weight=1)  # Text widget column expands
        self.grid_rowconfigure(0, weight=1)     # Row for all widgets expands vertically

        # Canvas for displaying line numbers
        self.line_numbers = tk.Canvas(self, width=20, bg="lightgrey")
        self.line_numbers.grid(row=0, column=0, sticky="ns")

        # Main Text Widget for content
        self.text = tk.Text(self, wrap="word", undo=True, font=font,
                            bg="white", bd=2, relief="solid")
        self.text.grid(row=0, column=1, sticky="nsew")

        # Vertical Scrollbar for the text widget
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_scrollbar)
        self.scrollbar.grid(row=0, column=2, sticky="ns")
        self.text.config(yscrollcommand=self._on_text_scroll)

        # Bind events to trigger line number updates
        self.text.bind("<KeyRelease>", self._update_line_numbers)
        self.text.bind("<MouseWheel>", self._update_line_numbers)
        self.text.bind("<Button-1>", self._update_line_numbers)
        self.text.bind("<Configure>", self._update_line_numbers)
        self.text.bind("<FocusIn>", self._update_line_numbers)
        self.text.bind("<<Modified>>", self._on_text_modified)

        self._update_line_numbers()  # Initial drawing of line numbers

    def _on_scrollbar(self, *args):
        """
        Callback for scrollbar movement. Scrolls the text and updates line numbers.
        """
        self.text.yview(*args)
        self._update_line_numbers()

    def _on_text_scroll(self, *args):
        """
        Callback for text widget scrolling. Updates the scrollbar and line numbers.
        """
        self.scrollbar.set(*args)
        self._update_line_numbers()

    def _on_text_modified(self, event):
        """
        Callback for text modification event. Resets the modified flag and updates line numbers.
        """
        self.text.edit_modified(False)  # Reset modified flag to allow future <<Modified>> events
        self._update_line_numbers()

    def _update_line_numbers(self, event=None):
        """
        Redraws the line numbers on the canvas.
        Calculates and adjusts the width of the line number canvas based on the maximum line number.
        """
        self.line_numbers.delete("all")  # Clear existing line numbers

        try:
            # Get the indices of the first and last visible lines
            first_visible_line = self.text.index("@0,0")
            last_visible_line = self.text.index(f"@0,{self.text.winfo_height()}")
        except tk.TclError:
            # This can happen if the widget is not yet fully rendered or destroyed
            return

        i = first_visible_line
        max_linenum = 1  # Track the maximum line number for width calculation
        current_font = self.text.cget("font") # Get the current font of the text widget

        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break # No more visible lines

            y = dline[1] + dline[4] // 2  # Calculate vertical center for the line number
            linenum = str(i).split(".")[0] # Extract the line number part (e.g., "1.0" -> "1")
            max_linenum = max(max_linenum, int(linenum)) # Update max line number

            x = int(self.line_numbers.cget("width")) - 2 # Position text near the right edge of the canvas
            self.line_numbers.create_text(x, y, anchor="e", text=linenum, font=current_font)

            # Move to the next line
            next_i = self.text.index(f"{i} lineend+1c")
            if self.text.compare(next_i, ">", last_visible_line):
                break # Stop if beyond the last visible line
            if next_i == i and self.text.index("end-1c") != i:
                # Handle cases where lineend+1c doesn't move the index (e.g., last character of file)
                try:
                    next_i = self.text.index(f"{i}+1c")
                except tk.TclError:
                    break
            i = next_i

        # Synchronize scroll position of line numbers canvas with text widget
        self.line_numbers.yview_moveto(self.text.yview()[0])

        # Dynamically calculate and set the width of the line number canvas
        num_digits = len(str(max_linenum))
        font_obj = tkfont.Font(font=current_font)
        char_width = font_obj.measure("0")  # Measure width of a single digit
        padding = 6 # Small padding for aesthetics
        desired_width = padding + char_width * num_digits
        self.line_numbers.config(width=desired_width)

    def get_text_widget(self):
        """
        Returns the internal `tk.Text` widget.

        Returns:
            tk.Text: The text widget instance.
        """
        return self.text

    def update_font(self):
        """
        Updates the font of the internal `tk.Text` widget and triggers
        a redraw of the line numbers to reflect the new font size.
        This method uses `const.param_font_size` for the text size.
        """
        text_font_size = const.param_font_size
        new_font_tuple = (const.gui_font, text_font_size)

        self.text.config(font=new_font_tuple)
        self._update_line_numbers()