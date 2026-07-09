# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 09:02:44 2025

@author: sheilamonera
"""
import os
import tkinter as tk
import platform
import tkinter.font as tkfont

from .info_label import InfoLabel
from .base_constants import FIXED_INPUT_WIDTH
from . import base_constants as const
from GUI.scroll_helpers import bind_listbox_scroll, bind_global_listbox_arrow_navigation


class SearchableDropDown:
    """
    A dropdown widget that allows selecting a single item, with search capabilities.
    The selected item directly populates the entry field.

    Attributes:
        _initial_options (list[str]): The original list of options provided at initialization.
        _initial_default (str): The default value provided at initialization.
        options (list[str]): The currently available options for selection.
        selected_item (str | None): The currently selected item, or None if no item is selected.
        filtered_options (list[str]): Options filtered based on user input.
        parent (tk.Widget): The parent container for this widget.
        is_open (bool): True if the dropdown list is currently visible, False otherwise.
        dropdown_win (tk.Toplevel | None): The Toplevel window displaying the dropdown list.
        listbox (tk.Listbox | None): The Listbox widget within the dropdown_win.
        pathToOptions (dict | None): A dictionary containing path and filter for dynamic option loading.
        _key_release_job (str | None): Stores the ID of the scheduled `after` job for input throttling.
        entry_font (tkfont.Font): Font configuration for the entry widget.
        toggle_btn_font (tkfont.Font): Font configuration for the toggle button.
        listbox_font (tkfont.Font): Font configuration for the listbox.
        info_label (InfoLabel): The InfoLabel instance associated with this dropdown.
        wrapper (tk.Frame): The main frame containing the entry and toggle button.
        entry_var (tk.StringVar): The StringVar associated with the entry field.
        entry (tk.Entry): The entry widget for displaying and typing selection.
        toggle_btn (tk.Button): The button to open/close the dropdown.
        root (tk.Tk): The root Tkinter window.
        canvas (tk.Canvas | None): The parent canvas, if any, used for dropdown positioning.
    """

    def __init__(self, parent, row, label_text, options, default=None, info_text=None):
        """
        Initializes the SearchableDropDown widget.

        Args:
            parent (tk.Widget): The parent container.
            row (int): The grid row for widget placement.
            label_text (str): Label text shown to the left of the dropdown.
            options (list[str]): List of selectable options.
            default (str, optional): The initially selected item. Defaults to None.
            info_text (str, optional): Tooltip text for the label. Defaults to None.
        """
        self._initial_options = sorted(options,key=str.lower)
        self._initial_default = default

        self.options = []
        self.selected_item = None
        self.filtered_options = []
        self.parent = parent
        self.is_open = False
        self.dropdown_win = None
        self.listbox = None
        self.pathToOptions = None

        self._key_release_job = None

        self.entry_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)
        self.toggle_btn_font = tkfont.Font(family=const.gui_font, size=const.param_font_size, weight="bold")
        self.listbox_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        self.info_label = InfoLabel(parent, label_text, info=info_text)
        self.info_label.grid(row=row, column=0, sticky="nw", padx=5, pady=5)

        self.wrapper = tk.Frame(parent, bd=1, relief="solid", width=FIXED_INPUT_WIDTH)
        self.wrapper.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        parent.grid_columnconfigure(1, weight=1)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.wrapper, textvariable=self.entry_var, borderwidth=0, font=self.entry_font)
        self.entry.pack(side=tk.LEFT, fill="x", expand=True)

        self.toggle_btn = tk.Button(self.wrapper, text="V", width=2, command=self.toggle_dropdown, font=self.toggle_btn_font)
        self.toggle_btn.pack(side=tk.LEFT)

        # Bindings for entry widget
        self.entry.bind("<KeyRelease>", self.on_entry_key)
        self.entry.bind("<Button-1>", self.show_dropdown, add="+")
        self.entry.bind("<Return>", self.select_first_match)

        self.root = parent.winfo_toplevel()
        self.canvas = self._find_canvas(parent)
        self.root.bind_all("<Button-1>", self.handle_click_outside, add="+")

        # Bind global arrow navigation to the root window for listbox interaction
        bind_global_listbox_arrow_navigation(self.root, lambda: self.listbox if self.is_open else None)

        self.selected_item = None
        self.entry_var.set("")
        self.validate_selection()

        self.update_font()

        if self._initial_options:
            self.set_options(self._initial_options, self._initial_default)

    def _find_canvas(self, widget):
        """
        Recursively finds the nearest parent Canvas widget.

        Args:
            widget (tk.Widget): The widget to start the search from.

        Returns:
            tk.Canvas | None: The found Canvas widget, or None if no canvas is found.
        """
        while widget:
            if isinstance(widget, tk.Canvas):
                return widget
            widget = widget.master
        return None

    def toggle_dropdown(self):
        """Toggles the visibility of the dropdown list."""
        if self.is_open:
            self.hide_dropdown()
        else:
            self.show_dropdown()

    def show_dropdown(self, event=None):
        """
        Creates and displays the dropdown list below the entry field.
        If `pathToOptions` is set, it refreshes the options from the specified path.
        """
        if self.dropdown_win:
            return

        # Refresh options from path if configured
        if self.pathToOptions:
            try:
                path = self.pathToOptions.get('path')
                file_filter = self.pathToOptions.get('filter')

                if path and os.path.isdir(path):
                    updated_files = [f for f in os.listdir(path) if f.endswith(file_filter)]
                    self.options = sorted(updated_files, key=str.lower)
                else:
                    self.options = []
            except Exception:
                self.options = []

        # Calculate position for the dropdown window
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self.dropdown_win = tk.Toplevel(self.parent)
        self.dropdown_win.overrideredirect(True)
        self.dropdown_win.geometry(f"{self.wrapper.winfo_width()}x100+{x}+{y}")
        self.dropdown_win.attributes("-topmost", True)
        self.dropdown_win.transient(self.root)

        # Create and configure the Listbox
        self.listbox = tk.Listbox(self.dropdown_win, height=5, selectmode=tk.SINGLE, exportselection=False, takefocus=0, font=self.listbox_font)
        self.listbox.pack(fill="both", expand=True)

        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        self.listbox.bind("<Return>", self.select_first_match)

        # Bind mouse wheel for scrolling using the helper function
        bind_listbox_scroll(self.listbox)

        # Display all options initially when dropdown is shown
        self.filtered_options = self.options[:]
        self.update_listbox()
        self.is_open = True
        self._update_dropdown_position()

        # Ensure the entry widget receives focus after the Toplevel window is fully rendered.
        self.entry.after_idle(self.entry.focus_set)
        self.dropdown_win.lift()

    def _update_dropdown_position(self, attempts=0):
        """
        Continuously repositions the dropdown window relative to the entry widget,
        taking into account a scrollable canvas if present.

        Args:
            attempts (int): Current retry count for positioning in case of TclError.
        """
        if not self.dropdown_win or not self.entry.winfo_ismapped():
            self.hide_dropdown()
            return

        try:
            entry_x_on_screen = self.entry.winfo_rootx()
            entry_y_on_screen = self.entry.winfo_rooty()
            entry_height = self.entry.winfo_height()

            dropdown_target_x = entry_x_on_screen
            dropdown_target_y = entry_y_on_screen + entry_height

            # Calculate required width based on the longest filtered option
            max_width = self.wrapper.winfo_width()
            if self.listbox and self.filtered_options:
                longest_option_width = 0
                for option in self.filtered_options:
                    option_width = self.listbox_font.measure(option)
                    if option_width > longest_option_width:
                        longest_option_width = option_width
                max_width = max(max_width, longest_option_width + 20) # Add padding

            self.dropdown_win.geometry(f"{max_width}x200+{dropdown_target_x}+{dropdown_target_y}")

            # Check if the dropdown is within the visible part of the canvas
            if self.canvas and self.canvas.winfo_ismapped():
                canvas_visible_top_on_screen = self.canvas.winfo_rooty()
                canvas_visible_bottom_on_screen = canvas_visible_top_on_screen + self.canvas.winfo_height()

                dropdown_bottom_on_screen = dropdown_target_y + self.listbox.winfo_height()

                if (dropdown_bottom_on_screen < canvas_visible_top_on_screen or
                        dropdown_target_y > canvas_visible_bottom_on_screen):
                    self.hide_dropdown()
                    return

            if self.is_open:
                self.entry.after(50, self._update_dropdown_position)

        except tk.TclError as e:
            # Retry positioning if a TclError occurs, up to a maximum of 5 attempts
            if attempts < 5:
                self.entry.after(50, lambda: self._update_dropdown_position(attempts + 1))
            else:
                self.hide_dropdown()
        except Exception:
            # Continue scheduling updates even if general errors occur
            if self.is_open:
                self.entry.after(100, self._update_dropdown_position)

    def update_listbox(self):
        """
        Updates the contents of the dropdown listbox to reflect the `filtered_options`.
        Also highlights the currently selected item if it's present in the list.
        """
        if not self.listbox:
            return
        self.listbox.delete(0, tk.END)

        for i, option in enumerate(self.filtered_options):
            self.listbox.insert(tk.END, option)
            if option == self.selected_item:
                self.listbox.selection_set(i)
                self.listbox.see(i)

    def on_entry_key(self, event=None):
        """
        Filters options based on typed text in the entry field and updates the dropdown.
        Implements a throttling mechanism to prevent excessive updates during rapid typing.
        """
        # Ignore specific key presses that are handled elsewhere (e.g., navigation)
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        # Cancel any previously scheduled update job to debounce input
        if self._key_release_job:
            self.parent.after_cancel(self._key_release_job)

        # Schedule a new update job after a short delay
        self._key_release_job = self.parent.after(200, self._process_entry_input)

    def _process_entry_input(self):
        """
        Processes the entry input. This method is called after the throttling delay.
        It filters the options and updates the listbox.
        """
        typed = self.entry_var.get().strip().lower()
        if typed:
            self.filtered_options = [opt for opt in self.options if typed in opt.lower()]
        else:
            self.filtered_options = self.options[:]

        self.show_dropdown()
        self.update_listbox()

    def on_select(self, event=None):
        """
        Handles the selection of an item from the listbox.
        Sets the entry value, updates the selected item, and hides the dropdown.
        """
        if not self.listbox:
            return

        selected_indices = self.listbox.curselection()
        if selected_indices:
            index = selected_indices[0]
            selected_value = self.listbox.get(index)
            self.set(selected_value)
            self.hide_dropdown()
            self.entry.focus_set()

    def select_first_match(self, event=None):
        """
        Selects the currently highlighted item in the listbox. If no item is highlighted,
        it selects the first item from the `filtered_options`.
        Then, it sets the entry text and hides the dropdown.
        """
        if self.listbox and self.listbox.curselection():
            index = self.listbox.curselection()[0]
            selected_value = self.listbox.get(index)
            self.set(selected_value)
        elif self.filtered_options:
            self.set(self.filtered_options[0])
        else:
            self.set("")

        self.hide_dropdown()
        self.entry.focus_set()

    def hide_dropdown(self, trigger_focus_out=False):
        """
        Hides the dropdown window. Optionally triggers a selection validation.

        Args:
            trigger_focus_out (bool): If True, `validate_selection` is called.
        """
        if self.dropdown_win:
            self.dropdown_win.destroy()
            self.dropdown_win = None
        self.listbox = None
        self.is_open = False
        # Cancel any pending key release job when the dropdown is hidden
        if self._key_release_job:
            self.parent.after_cancel(self._key_release_job)
            self._key_release_job = None

        if trigger_focus_out:
            self.validate_selection()

    def handle_click_outside(self, event):
        """
        Closes the dropdown if a click event occurs outside the entry or toggle button.

        Args:
            event (tk.Event): The click event.
        """
        # Do not close if the click was inside the dropdown itself
        if self.dropdown_win and str(event.widget).startswith(str(self.dropdown_win)):
            return
        # Close if the click was not on the entry or toggle button
        if event.widget not in (self.entry, self.toggle_btn):
            self.hide_dropdown()

    def set_options(self, new_options, default_to_apply=None):
        """
        Sets a new list of selectable options for the dropdown.
        It clears the current selection if it's no longer present in the new options.
        An optional default value can be applied from the new set of options.

        Args:
            new_options (list[str]): The new options to set.
            default_to_apply (str, optional): An optional default value to apply.
                                               If None, it tries to use the `_initial_default`.
        """
        self.options = sorted(new_options,key=str.lower)

        final_default = default_to_apply if default_to_apply is not None else self._initial_default

        if final_default is not None and final_default in self.options:
            if self.selected_item != final_default:
                self.set(final_default)
        elif self.selected_item not in self.options:
            self.selected_item = None
            self.entry_var.set("")

        self.filtered_options = self.options[:]

        self.hide_dropdown()
        self.validate_selection()

        if self.listbox:
            self.update_listbox()

    def set_new_path_for_options(self, new_path_dict):
        """
        Sets a new `pathToOptions` dictionary, refreshes `self.options` by listing files
        from the specified path, and re-evaluates the default or current selection.

        Args:
            new_path_dict (dict): A dictionary containing 'path' (directory) and 'filter' (file extension).
        """
        self.pathToOptions = new_path_dict
        path = self.pathToOptions.get('path')
        file_filter = self.pathToOptions.get('filter')
        try:
            if path and os.path.isdir(path):
                self.options = [f for f in os.listdir(path) if f.endswith(file_filter)]
            else:
                self.options = []
        except Exception:
            self.options = []

        if self.selected_item is not None and self.selected_item in self.options:
            self.entry_var.set(self.selected_item)
        elif self._initial_default is not None and self._initial_default in self.options:
            self.set(self._initial_default)
        else:
            self.set("")

        if self.listbox and self.is_open:
            self.update_listbox()

    def validate_selection(self):
        """
        Sets the background color of the wrapper and entry based on whether
        an item is currently selected.
        """
        color = "#ffdddd" if self.selected_item is None else "white"
        self.wrapper.config(bg=color)
        self.entry.config(bg=color)

    def set(self, value):
        """
        Sets the selected item and updates the entry field.

        Args:
            value (str): The item to set as selected. Must be in `self.options` or an empty string.
                         An empty string "" will clear the selection.
        """
        if value == "" or value in self.options:
            self.selected_item = value if value != "" else None
            self.entry_var.set(value)
            self.validate_selection()
            if self.listbox:
                self.update_listbox()

    def get(self):
        """
        Returns the currently selected item.

        Returns:
            str | None: The selected option string, or None if no item is selected.
        """
        return self.selected_item

    def update_font(self):
        """
        Updates the font sizes for all relevant widgets within the dropdown.
        This method is designed to be called by a main GUI component when a global font size change occurs.
        """
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()

        self.entry_font.config(size=const.param_font_size)
        self.toggle_btn_font.config(size=const.param_font_size)
        self.listbox_font.config(size=const.param_font_size)

        if self.listbox:
            self.listbox.config(font=self.listbox_font)