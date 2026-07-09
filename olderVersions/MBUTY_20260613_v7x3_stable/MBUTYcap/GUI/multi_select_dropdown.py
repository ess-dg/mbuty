import os
import tkinter as tk
import tkinter.font as tkfont
from GUI.info_label import InfoLabel
from GUI.base_constants import FIXED_INPUT_WIDTH
from . import base_constants as const
from GUI.scroll_helpers import bind_listbox_scroll, bind_global_listbox_arrow_navigation


class MultiSelectDropDown:
    """
    A dropdown widget that allows selecting multiple items, which are then displayed as clickable tags.
    It provides search capabilities to filter the available options.

    Attributes:
        options (list[str]): The complete sorted list of all available options.
        selected (set[str]): A set of currently selected items.
        filtered_options (list[str]): The list of options currently displayed in the dropdown,
                                       filtered based on user input.
        parent (tk.Widget): The parent Tkinter widget.
        is_open (bool): A flag indicating whether the dropdown list is currently visible.
        dropdown_win (tk.Toplevel | None): The Toplevel window that holds the listbox. None if closed.
        listbox (tk.Listbox | None): The Listbox widget inside the dropdown_win. None if closed.
        pathToOptions (dict | None): A dictionary containing 'path' and 'filter' to dynamically
                                     load options from a directory.
        _initial_default (list[str] | None): The list of default selections provided at initialization.
        _key_release_job (str | None): The ID of the `after` job used for throttling key release events.
        entry_font (tkfont.Font): Font configuration for the entry widget.
        toggle_btn_font (tkfont.Font): Font configuration for the dropdown toggle button.
        listbox_font (tkfont.Font): Font configuration for the listbox items.
        tag_label_font (tkfont.Font): Font configuration for the text within selected tags.
        tag_button_font (tkfont.Font): Font configuration for the 'X' button on selected tags.
        info_label (InfoLabel): The InfoLabel instance for the dropdown's main label.
        wrapper (tk.Frame): The main container frame for the entry, tags, and toggle button.
        tags_frame (tk.Frame): A frame within `wrapper` that holds the visual tags of selected items.
        entry_wrapper (tk.Frame): A frame containing the entry field and the toggle button.
        entry_var (tk.StringVar): The StringVar linked to the entry widget.
        entry (tk.Entry): The entry widget for typing and filtering options.
        toggle_btn (tk.Button): The button to open/close the dropdown.
        root (tk.Tk): The root Tkinter window of the application.
        canvas (tk.Canvas | None): A reference to a parent Canvas widget, used for correct
                                   dropdown positioning in scrollable areas.
    """

    def __init__(self, parent, row, label_text, options, default=None, info_text=None):
        """
        Initializes the MultiSelectDropDown widget.

        Args:
            parent (tk.Widget): The parent container.
            row (int): The grid row for placement.
            label_text (str): Label text shown to the left of the dropdown.
            options (list[str]): List of selectable options.
            default (list[str], optional): List of initially selected items. Defaults to None.
            info_text (str, optional): Tooltip text for the label. Defaults to None.
        """
        ###################
        # make this True to sort filenames Z to A, instead False A -> Z 
        self.rev = True    # Z -> A 
        # self.rev = False # A -> Z 
        #################### 
        
        
        self.options = sorted(options, key=str.lower, reverse=self.rev)
        self.selected = set(default) if default else set()
        self.filtered_options = self.options[:]
        self.parent = parent
        self.is_open = False
        self.dropdown_win = None
        self.listbox = None
        self.pathToOptions = None
        self._initial_default = default

        self._key_release_job = None

        self.entry_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)
        self.toggle_btn_font = tkfont.Font(family=const.gui_font, size=const.param_font_size, weight="bold")
        self.listbox_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)
        self.tag_label_font = tkfont.Font(family=const.gui_font, size=const.param_font_size - 1)
        self.tag_button_font = tkfont.Font(family=const.gui_font, size=const.param_font_size - 2, weight="bold")

        self.info_label = InfoLabel(parent, label_text, info=info_text)
        self.info_label.grid(row=row, column=0, sticky="nw", padx=5, pady=5)

        self.wrapper = tk.Frame(parent, bd=1, relief="solid", width=FIXED_INPUT_WIDTH)
        self.wrapper.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        parent.grid_columnconfigure(1, weight=1)

        self.tags_frame = tk.Frame(self.wrapper)

        self.entry_wrapper = tk.Frame(self.wrapper)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.entry_wrapper, textvariable=self.entry_var, borderwidth=0, font=self.entry_font)
        self.entry.pack(side=tk.LEFT, fill="x", expand=True)

        self.toggle_btn = tk.Button(self.entry_wrapper, text="V", width=2, command=self.toggle_dropdown, font=self.toggle_btn_font)
        self.toggle_btn.pack(side=tk.LEFT)

        self.entry.bind("<KeyRelease>", self.on_entry_key)
        self.entry.bind("<Button-1>", self.show_dropdown, add="+")
        self.entry.bind("<Return>", self.add_first_match)

        self.root = parent.winfo_toplevel()
        self.canvas = self._find_canvas(parent)
        self.root.bind_all("<Button-1>", self.handle_click_outside, add="+")

        bind_global_listbox_arrow_navigation(self.root, lambda: self.listbox if self.is_open else None)

        self.entry_wrapper.pack(side=tk.BOTTOM, fill="x")
        self.refresh_tags()

        self.validate_selection()

        self.update_font()

    def _find_canvas(self, widget):
        """
        Recursively finds the nearest parent Tkinter Canvas widget.

        This is used for positioning the dropdown correctly relative to a
        scrollable area, ensuring it stays visible.

        Args:
            widget (tk.Widget): The starting widget from which to search up the parent hierarchy.

        Returns:
            tk.Canvas or None: The parent Canvas widget if found, otherwise None.
        """
        while widget:
            if isinstance(widget, tk.Canvas):
                return widget
            widget = widget.master
        return None

    def toggle_dropdown(self):
        """Toggles the visibility of the dropdown: opens it if closed, closes it if open."""
        if self.is_open:
            self.hide_dropdown()
        else:
            self.show_dropdown()

    def show_dropdown(self, event=None):
        """
        Creates and displays the dropdown list below the entry field.
        If the dropdown is already open, it does nothing.
        Dynamically loads options from `pathToOptions` if set.
        """
        if self.dropdown_win:
            return

        if self.pathToOptions:
            try:
                path = self.pathToOptions.get('path')
                file_filter = self.pathToOptions.get('filter')

                if path and os.path.isdir(path):
                    updated_files = [f for f in os.listdir(path) if f.endswith(file_filter)]
                    self.options = sorted(updated_files, key=str.lower, reverse=self.rev)
                    self.filtered_options = self.options
                else:
                    self.options = []
            except Exception:
                self.options = []

        # Calculate dropdown position
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self.dropdown_win = tk.Toplevel(self.parent)
        self.dropdown_win.overrideredirect(True)
        self.dropdown_win.geometry(f"{self.wrapper.winfo_width()}x100+{x}+{y}")
        self.dropdown_win.attributes("-topmost", True)

        self.dropdown_win.transient(self.root)

        # Create Listbox
        self.listbox = tk.Listbox(self.dropdown_win, height=5, selectmode="multiple", exportselection=False, takefocus=0, font=self.listbox_font)
        self.listbox.pack(fill="both", expand=True)

        self.listbox.bind("<ButtonRelease-1>", self.on_select)
        self.listbox.bind("<Return>", self.add_selected_from_listbox)

        bind_listbox_scroll(self.listbox)

        self.update_listbox()
        self.is_open = True
        self._update_dropdown_position()

        self.entry.after_idle(self.entry.focus_set)
        self.dropdown_win.lift()

    def _update_dropdown_position(self, attempts=0):
        """
        Continuously repositions the dropdown relative to the entry field
        and checks if it remains within the visible area of a parent canvas.
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

            max_width = self.wrapper.winfo_width()
            if self.listbox and self.filtered_options:
                longest_option_width = 0
                for option in self.filtered_options:
                    option_width = self.listbox_font.measure(option)
                    if option_width > longest_option_width:
                        longest_option_width = option_width
                max_width = max(max_width, longest_option_width + 20)

            self.dropdown_win.geometry(f"{max_width}x200+{dropdown_target_x}+{dropdown_target_y}")

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

        except tk.TclError:
            if attempts < 5:
                self.entry.after(50, lambda: self._update_dropdown_position(attempts + 1))
            else:
                self.hide_dropdown()
        except Exception as e:
            print(f"Dropdown positioning error: {e}")
            if self.is_open:
                self.entry.after(100, self._update_dropdown_position)

    def update_listbox(self):
        """
        Updates the dropdown listbox contents to match `filtered_options`,
        applying a light blue background highlight for selected items.
        """
        if not self.listbox:
            return
        self.listbox.delete(0, tk.END)

        for i, option in enumerate(self.filtered_options):
            self.listbox.insert(tk.END, option)
            if option in self.selected:
                self.listbox.itemconfigure(i, background='#ADD8E6')
            else:
                self.listbox.itemconfigure(i, background='white')

        if self.is_open:
            pass

    def set_new_path_for_options(self, new_path_dict):
        """
        Sets a new dictionary containing a path and file filter,
        then refreshes the `options` by listing files in that path.
        This method is intended to be called by external code.

        Args:
            new_path_dict (dict): A dictionary with 'path' and 'filter' keys,
                                  e.g., `{'path': '/home/user/data', 'filter': '.txt'}`.
        """
        self.pathToOptions = new_path_dict
        path = self.pathToOptions.get('path')
        file_filter = self.pathToOptions.get('filter')
        try:
            if path and os.path.isdir(path):
                updated_files = [f for f in os.listdir(path) if f.endswith(file_filter)]
                self.set_options(updated_files)
            else:
                self.set_options([])
        except Exception:
            self.options = []

    def on_entry_key(self, event=None):
        """
        Handles key release events on the entry widget.
        Filters options based on typed text and updates the dropdown.
        Includes a throttling mechanism to prevent excessive updates on rapid typing.
        """
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return

        if self._key_release_job:
            self.parent.after_cancel(self._key_release_job)

        self._key_release_job = self.parent.after(200, self._process_entry_input)

    def _process_entry_input(self):
        """
        Processes the entry input. This method is called after the throttle delay.
        It filters options and updates the listbox.
        """
        typed = self.entry_var.get().strip().lower()
        self.filtered_options = [opt for opt in self.options if typed in opt.lower()]
        self.show_dropdown()
        self.update_listbox()

    def on_select(self, event=None):
        """
        Handles selection/deselection of items from the listbox via mouse click.
        Toggles selection status and updates the UI (tags, listbox highlights)
        without hiding the dropdown.
        """
        if not self.listbox:
            return

        try:
            clicked_index = self.listbox.nearest(event.y)
            clicked_item = self.listbox.get(clicked_index)
        except ValueError:
            return

        if clicked_item in self.selected:
            self.selected.discard(clicked_item)
        else:
            self.selected.add(clicked_item)

        self.refresh_tags()
        self.update_listbox()
        self.validate_selection()
        self.entry.focus_set()

    def add_selected_from_listbox(self, event=None):
        """
        Handles adding selected items from the listbox when the Enter key is pressed.
        Adds the currently highlighted item to selection, clears the entry, and hides the dropdown.
        """
        if self.listbox and self.listbox.curselection():
            selected_idx = self.listbox.curselection()[0]
            selected_item = self.listbox.get(selected_idx)
            if selected_item not in self.selected:
                self.selected.add(selected_item)

        self.entry_var.set("")
        self.refresh_tags()
        self.hide_dropdown()
        self.validate_selection()

    def add_first_match(self, event=None):
        """
        Adds the currently highlighted item in the listbox to the selection,
        or the first matching filtered item if no item is highlighted.
        Clears the entry, refreshes tags, and hides the dropdown.
        """
        item_to_add = None

        if self.listbox and self.listbox.curselection():
            index = self.listbox.curselection()[0]
            item_to_add = self.listbox.get(index)
        elif self.filtered_options:
            item_to_add = self.filtered_options[0]

        if item_to_add:
            if item_to_add not in self.selected:
                self.selected.add(item_to_add)

            self.entry_var.set("")
            self.refresh_tags()
            self.hide_dropdown()
            self.validate_selection()

    def refresh_tags(self):
        """
        Re-renders the visual tags for selected items.
        Manages the packing of `self.tags_frame` to ensure it collapses when empty
        and is visible when items are selected.
        """
        for widget in self.tags_frame.winfo_children():
            widget.destroy()

        if not self.selected:
            self.tags_frame.pack_forget()
        else:
            try:
                self.tags_frame.pack(side=tk.TOP, anchor="w", fill="x")
            except tk.TclError:
                pass

            for item in sorted(list(self.selected),key=str.lower, reverse=self.rev):
                tag = tk.Frame(self.tags_frame, bd=1, relief="ridge", padx=2, pady=1)
                tk.Label(tag, text=item, font=self.tag_label_font,
                         wraplength=FIXED_INPUT_WIDTH - 40, justify="left").pack(side=tk.LEFT)
                tk.Button(tag, text="X", command=lambda i=item: self.remove_tag(i),
                          padx=1, pady=0, font=self.tag_button_font,
                          width=2).pack(side=tk.LEFT)
                tag.pack(fill="x", pady=2, padx=2, anchor="w")

        self.tags_frame.update_idletasks()
        self.wrapper.update_idletasks()

    def remove_tag(self, item):
        """
        Removes a specific item from the selection.

        Args:
            item (str): The item to remove from the selected set.
        """
        self.selected.discard(item)
        self.refresh_tags()
        self.validate_selection()

        if self.listbox:
            self.update_listbox()

    def hide_dropdown(self, trigger_focus_out=False):
        """
        Hides the dropdown window and resets its state.
        Optionally triggers selection validation.

        Args:
            trigger_focus_out (bool, optional): If True, forces a selection
                                               validation. Defaults to False.
        """
        if self.dropdown_win:
            self.dropdown_win.destroy()
            self.dropdown_win = None
        self.listbox = None
        self.is_open = False

        if self._key_release_job:
            self.parent.after_cancel(self._key_release_job)
            self._key_release_job = None

        if trigger_focus_out:
            self.validate_selection()

    def handle_click_outside(self, event):
        """
        A global click handler that closes the dropdown if a click occurs
        outside the entry widget, the toggle button, or the dropdown window itself.
        """
        if self.dropdown_win and str(event.widget).startswith(str(self.dropdown_win)):
            return
        if event.widget not in (self.entry, self.toggle_btn):
            self.hide_dropdown()

    def set_options(self, new_options):
        """
        Sets a new list of selectable options for the dropdown.
        Preserves any currently selected items that are still valid in the new options.

        Args:
            new_options (list[str]): The new list of options to set.
        """
        self.options = sorted(new_options, key=str.lower, reverse=self.rev)
        self.selected = {item for item in self.selected if item in new_options}

        typed_text = self.entry_var.get().strip().lower()
        if typed_text:
            self.filtered_options = [opt for opt in self.options if typed_text in opt.lower()]
        else:
            self.filtered_options = self.options[:]

        self.entry_var.set("")
        self.refresh_tags()
        self.hide_dropdown()

        if self.listbox:
            self.update_listbox()

        self.validate_selection()

    def validate_selection(self):
        """
        Updates the background color of the wrapper, tags frame, and entry
        based on whether any items are currently selected.
        Highlights red if no items are selected.
        """
        color = "#ffdddd" if not self.selected else "white"
        self.wrapper.config(bg=color)
        self.tags_frame.config(bg=color)
        self.entry.config(bg=color)

    def get(self):
        """
        Returns a list of currently selected items.

        Returns:
            list[str]: A list of selected option strings.
        """
        return list(self.selected)

    def update_font(self):
        """
        Updates the font sizes of all relevant widgets within MultiSelectDropDown.
        This method should be called by the main GUI when the global font size changes.
        """
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()

        self.entry_font.config(size=const.param_font_size)
        self.toggle_btn_font.config(size=const.param_font_size)
        self.listbox_font.config(size=const.param_font_size)
        self.tag_label_font.config(size=const.param_font_size - 1)
        self.tag_button_font.config(size=const.param_font_size - 2)

        self.refresh_tags()

        if self.listbox:
            self.listbox.config(font=self.listbox_font)