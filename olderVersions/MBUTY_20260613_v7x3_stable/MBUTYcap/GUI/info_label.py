# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 08:46:51 2025

@author: sheilamonera
"""
import tkinter as tk
import tkinter.font as tkfont
from . import base_constants as const


class Tooltip:
    """
    A class to create a tooltip window that appears when hovering over a widget.

    Attributes:
        widget (tk.Widget): The Tkinter widget to which the tooltip is attached.
        text (str): The text content to be displayed within the tooltip.
        tip_window (tk.Toplevel | None): The Toplevel window instance for the tooltip.
                                         It is None when the tooltip is not active.
    """

    def __init__(self, widget, text):
        """
        Initializes the Tooltip with the target widget and text.

        Args:
            widget (tk.Widget): The Tkinter widget to attach the tooltip to.
            text (str): The string content for the tooltip.
        """
        self.widget = widget
        self.text = text
        self.tip_window = None

        # Bind events to show and hide the tooltip
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        """
        Displays the tooltip window.
        The tooltip is positioned near the widget and adjusted to stay on screen.
        It uses the global `const.param_font_size` for its text.
        """
        if self.tip_window or not self.text:
            return

        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        # Calculate initial desired position for the tooltip
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        # Create the tooltip Toplevel window
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)  # Remove window decorations
        self.tip_window.geometry("+10000+10000")  # Temporarily move off-screen to measure

        # Create and pack the Label for the tooltip text
        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            background="#ffffe0",  # Light yellow background
            relief="solid",
            borderwidth=1,
            font=(const.gui_font, const.param_font_size),  # Use dynamic font size
            wraplength=500  # Wrap text after 500 pixels
        )
        label.pack(ipadx=5, ipady=2)

        # Update IDLE tasks to ensure the label's size is calculated before measuring
        self.tip_window.update_idletasks()
        tooltip_width = self.tip_window.winfo_width()
        tooltip_height = self.tip_window.winfo_height()

        # Adjust position if the tooltip would extend beyond screen boundaries
        if x + tooltip_width > screen_width:
            x = screen_width - tooltip_width - 10
        if y + tooltip_height > screen_height:
            y = self.widget.winfo_rooty() - tooltip_height - 10

        # Set the final position of the tooltip window
        self.tip_window.geometry(f"+{x}+{y}")

    def hide(self, event=None):
        """
        Hides and destroys the tooltip window.
        """
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class InfoLabel(tk.Frame):
    """
    A custom Tkinter Frame that displays a main text label and an optional
    info button with a tooltip. It's designed to have a fixed width and
    dynamically update its font based on global settings.

    Attributes:
        main_label (tk.Label): The main text label displaying `text`.
        info_btn (tk.Button | None): The ' (i) ' button that shows a tooltip on hover.
                                     None if no `info` text is provided.
        main_label_font (tkfont.Font): Font object for the main label, dynamically sized.
        info_btn_font (tkfont.Font): Font object for the info button, dynamically sized and bold.
    """

    def __init__(self, parent, text, info=None, total_width=const.label_width, **kwargs):
        """
        Initializes the InfoLabel widget.

        Args:
            parent (tk.Widget): The parent widget.
            text (str): The main label text to display.
            info (str, optional): The tooltip text to show when hovering over the info button.
                                  If None, no info button is created. Defaults to None.
            total_width (int, optional): The fixed width of the entire InfoLabel frame.
                                         Defaults to `const.label_width`.
            **kwargs: Additional keyword arguments passed to the `tk.Frame` constructor.
        """
        super().__init__(parent, **kwargs)

        # Enforce fixed width on the parent’s grid column where this InfoLabel is placed
        parent.grid_columnconfigure(0, minsize=total_width)

        # Configure this frame to have a fixed width and prevent it from propagating its size
        self.config(width=total_width)
        self.grid_propagate(False)

        # Internal wrapper to allow the main label to dynamically adjust its height based on text wrapping
        wrapper = tk.Frame(self, width=total_width)
        wrapper.pack(fill="both", expand=True)

        # Define dynamic font objects for the main label and info button
        self.main_label_font = tkfont.Font(
            family=const.gui_font,
            size=const.param_font_size
        )
        self.info_btn_font = tkfont.Font(
            family=const.gui_font,
            size=const.param_font_size,
            weight="bold"
        )

        # Create the main label
        self.main_label = tk.Label(
            wrapper,
            text=text,
            justify="left",
            anchor="w",
            wraplength=total_width - 40,  # Allocate space for the info button
            font=self.main_label_font  # Apply dynamic font
        )
        self.main_label.pack(side="left", fill="x", expand=True)

        # Create the optional info button if info text is provided
        if info:
            self.info_btn = tk.Button(
                wrapper,
                text="(i)",
                padx=0,
                pady=0,
                fg="#0066cc",  # Blue foreground for the info button
                font=self.info_btn_font,  # Apply dynamic font
                relief=tk.FLAT,
                borderwidth=0,
                width=2  # Fixed width for the button
            )
            self.info_btn.pack(side="left", padx=(4, 0))
            Tooltip(self.info_btn, info)  # Attach the tooltip
        else:
            self.info_btn = None

        # Apply initial font settings
        self.update_font()

    def update_font(self):
        """
        Updates the font sizes for the main label and the info button
        based on the current value of `const.param_font_size`.
        This method should be called when the global font size setting changes.
        """
        self.main_label_font.config(size=const.param_font_size)
        if self.info_btn:
            self.info_btn_font.config(size=const.param_font_size)

    def grid(self, **kwargs):
        """
        Overrides the default `grid` method to ensure consistent default padding
        and sticky behavior for the InfoLabel when placed in a grid layout.
        """
        kwargs.setdefault("sticky", "nw")  # Default to top-left alignment
        kwargs.setdefault("padx", (5, 0))  # Default horizontal padding (left only)
        kwargs.setdefault("pady", 5)  # Default vertical padding
        super().grid(**kwargs)