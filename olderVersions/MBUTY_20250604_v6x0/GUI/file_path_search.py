import tkinter as tk
import os
import tkinter.font as tkfont
from tkinter import messagebox
from .info_label import InfoLabel
from . import base_constants as const
from pathlib import Path
from .scroll_helpers import bind_listbox_scroll

class FilePathSearch:
    """
    A custom Tkinter widget that combines an entry field with a label and
    provides intelligent autocomplete functionality for local file system paths.
    It supports path validation, including checking for existence and offering
    to create new directories.

    Attributes:
        must_exist (bool): If True, the path entered must exist already. 
                           If False, the class will give the option to create it
        parent_widget (tk.Widget): The parent container for this widget.
        var (tk.StringVar): Tkinter variable holding the entry's text.
        entry_font (tkfont.Font): Font configuration for the entry widget.
        listbox_font (tkfont.Font): Font configuration for the autocomplete listbox.
        info_label (InfoLabel): A custom label displaying `label_text` and an optional tooltip.
        entry (tk.Entry): The main entry widget for path input.
        autocomplete_toplevel (tk.Toplevel): A top-level window for displaying autocomplete suggestions.
        autocomplete_listbox (tk.Listbox): The listbox within the toplevel for suggestions.
        current_autocomplete_base_path (str): The base directory for current suggestions.
        is_dropdown_open (bool): Flag indicating if the autocomplete dropdown is currently visible.
        _dropdown_fixed_width (int): Stores the calculated width for the autocomplete dropdown.
        root (tk.Tk | tk.Toplevel): The top-most Tkinter window.
        _configure_funcid (str): ID for the bind event on the root window's configure event.
        _after_id (str): ID for the `after` call used in dropdown positioning.
        _global_click_bind_id (str): ID for the global button-click bind.
        dummy_focus_holder (tk.Frame): A hidden frame used to manage focus behavior.
        canvas (tk.Canvas): Reference to an ancestor Tkinter Canvas widget, if found,
                            used for scroll-aware dropdown positioning.
        tooltip (tk.Toplevel): The toplevel window for the live tooltip.
        tooltip_label_font (tkfont.Font): Font for the tooltip label.
        tooltip_label (tk.Label): The label inside the tooltip.
        _tooltip_mouse_inside (bool): Flag indicating if the mouse is over the entry for tooltip.
        _tooltip_after_id (str): ID for the `after` call for tooltip delay.
    """

    def __init__(self, parent, row, label_text, default="", info_text=None, mustExist=True):
        """
        Initializes the FilePathSearch widget.

        Args:
            parent (tk.Widget): The parent container widget where this widget will be placed.
            row (int): The row index for positioning this widget within a grid layout.
            label_text (str): The text to display on the label next to the entry field.
            default (str, optional): The default path string to populate the entry field with.
                                     Defaults to an empty string.
            info_text (str, optional): A tooltip message that appears when hovering over the label.
                                       Defaults to None (no tooltip).
            mustExist (bool, optional): If True, the entered path must either already exist
                                        or be successfully creatable when validated. Defaults to True.
        """
        # Initialize instance variables to store configuration and state.
        self.must_exist = mustExist
        self.parent_widget = parent
        self.var = tk.StringVar(value=default)
        self.entry_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)
        self.listbox_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        # Create the information label and place it in the grid.
        self.info_label = InfoLabel(parent, label_text, info=info_text)
        self.info_label.grid(row=row, column=0, sticky="w")

        # Create the main entry widget and place it in the grid.
        self.entry = tk.Entry(parent, textvariable=self.var, font=self.entry_font)
        self.entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)

        # Initialize variables related to the autocomplete dropdown.
        self.autocomplete_toplevel = None
        self.autocomplete_listbox = None
        self.current_autocomplete_base_path = ""
        self.is_dropdown_open = False
        self._dropdown_fixed_width = 0

        # Get the root Tkinter window for global event binding and positioning.
        self.root = parent.winfo_toplevel()
        # Initialize IDs for managing scheduled events and bindings.
        self._configure_funcid = None
        self._after_id = None
        self._global_click_bind_id = None

        # Create a dummy frame to help manage focus behavior, especially when tabbing out.
        self.dummy_focus_holder = tk.Frame(parent, width=0, height=0)
        self.dummy_focus_holder.grid(row=row + 1, column=0)
        self.dummy_focus_holder.lower() # Ensure it's visually behind other widgets.

        # Bind keyboard and mouse events to the entry widget to trigger autocomplete and navigation.
        self.entry.bind("<KeyRelease>", self._handle_key_release)
        self.entry.bind("<Down>", self._navigate_list, add="+")
        self.entry.bind("<Up>", self._navigate_list, add="+")
        self.entry.bind("<Return>", self._select_item_on_enter, add="+")
        self.entry.bind("<Escape>", self._hide_autocomplete_and_return_focus, add="+")
        self.entry.bind("<Tab>", self._on_tab_key, add="+")

        # Bind focus-related events to control dropdown visibility and validation.
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Button-1>", self._on_entry_click, add="+")

        # Find a parent canvas, if any, to correctly position the dropdown when scrolled.
        self.canvas = self._find_canvas(parent)

        # Add a live tooltip that shows the full path if it overflows the entry.
        self._add_live_tooltip()
        # Perform an initial validation of the default path.
        self._validate_path()
        # Update fonts based on global settings.
        self.update_font()

        # Schedule the global click handler binding to occur after the GUI is fully rendered.
        self.root.after_idle(self._bind_global_click_handler)

    def _bind_global_click_handler(self):
        """Helper to bind a global click handler to the root window and store its ID.
        This handler is used to detect clicks outside the entry and dropdown,
        allowing the autocomplete dropdown to be hidden.
        """
        self._global_click_bind_id = self.root.bind_all("<Button-1>", self._handle_global_click, add="+")

    def _find_canvas(self, widget):
        """
        Recursively searches up the widget hierarchy to find an ancestor Tkinter Canvas widget.
        This is crucial for correctly positioning the autocomplete dropdown when the
        entry field itself is placed inside a scrollable canvas.

        Args:
            widget (tk.Widget): The starting widget to begin the search from.

        Returns:
            tk.Canvas or None: The found Canvas widget, or None if no Canvas ancestor is found.
        """
        # Traverse up the widget hierarchy until the master is None (root) or a Canvas is found.
        while widget:
            if isinstance(widget, tk.Canvas):
                return widget
            widget = widget.master
        return None

    def _setup_autocomplete_widgets(self):
        """
        Initializes or re-initializes the Tkinter Toplevel window and Listbox
        used for displaying autocomplete suggestions. It positions the dropdown
        immediately below the entry field to prevent flickering.
        """
        # Destroy any existing autocomplete toplevel to ensure a clean slate.
        if self.autocomplete_toplevel and self.autocomplete_toplevel.winfo_exists():
            self.autocomplete_toplevel.destroy()
        self.autocomplete_toplevel = None

        # Ensure the entry widget's geometry information is up-to-date.
        self.entry.update_idletasks()

        # Calculate the position and initial size for the toplevel window.
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self._dropdown_fixed_width = self.entry.winfo_width()
        # Provide a fallback width if the entry's width hasn't been determined yet.
        if self._dropdown_fixed_width == 0:
            self._dropdown_fixed_width = 200
        fixed_height = 100 # Define a fixed height for the dropdown.

        # Create the Toplevel window.
        self.autocomplete_toplevel = tk.Toplevel(self.parent_widget)
        # Configure the toplevel to be borderless and always on top, and initially transparent.
        self.autocomplete_toplevel.overrideredirect(True)
        self.autocomplete_toplevel.attributes("-topmost", True)
        self.autocomplete_toplevel.attributes("-alpha", 0.0) # Start transparent to avoid flash.

        self.autocomplete_toplevel.transient(self.root)

        # Set the initial geometry of the toplevel.
        self.autocomplete_toplevel.geometry(f"{self._dropdown_fixed_width}x{fixed_height}+{x}+{y}")

        # Bind to the <Expose> event to make the toplevel visible after it's fully mapped,
        # which helps prevent flickering.
        self.autocomplete_toplevel.bind("<Expose>", lambda e: self.autocomplete_toplevel.attributes("-alpha", 1.0))

        # Create the Listbox widget within the toplevel.
        self.autocomplete_listbox = tk.Listbox(
            self.autocomplete_toplevel,
            font=self.listbox_font,
            exportselection=False, # Prevents selection from interfering with other widgets.
            takefocus=0,           # Prevents listbox from taking focus during navigation.
            highlightthickness=0,  # No highlight border.
            relief="flat",         # Flat appearance.
            borderwidth=1,         # Small border for separation.
            selectmode="browse"    # Allows only single selection.
        )
        # Pack the listbox to fill the toplevel window.
        self.autocomplete_listbox.pack(fill="both", expand=True)
        # Bind events to the listbox for selection and navigation.
        self.autocomplete_listbox.bind("<<ListboxSelect>>", self._select_item)
        self.autocomplete_listbox.bind("<Button-1>", self._select_item, add="+")
        self.autocomplete_listbox.bind("<Return>", self._select_item_on_enter, add="+")
        self.autocomplete_listbox.bind("<Escape>", self._hide_autocomplete_and_return_focus, add="+")
        
        # Use a helper method to enable mouse wheel scrolling for the listbox.
        bind_listbox_scroll(self.autocomplete_listbox)

    def _on_focus_in(self, event=None):
        """
        Handles the event when the entry widget receives focus.
        If the dropdown is not already open and the entry has text, it shows
        the autocomplete dropdown and updates the suggestions.
        """
        if not self.is_dropdown_open and self.var.get().strip() != "":
            self._show_autocomplete()
            self._update_suggestions(self.var.get())

    def _on_entry_click(self, event):
        """
        Handles a mouse click event on the entry widget.
        Ensures the entry gains focus and toggles the autocomplete dropdown's visibility.
        If the dropdown is not open, it shows it and updates suggestions.
        """
        self.entry.focus_set()
        if not self.is_dropdown_open:
            self._show_autocomplete()
            self._update_suggestions(self.var.get())

    def _on_root_configure(self, event=None):
        """
        Callback function invoked when the root window is moved, resized, or configured.
        If the autocomplete dropdown is currently open, this triggers its repositioning
        to ensure it stays aligned with the entry widget.
        """
        if self.is_dropdown_open:
            self._update_dropdown_position()

    def _show_autocomplete(self):
        """
        Creates the autocomplete suggestions dropdown (Toplevel and Listbox) if it doesn't
        exist, then makes it visible. It also sets the `is_dropdown_open` flag to True
        and binds the root window's configure event to reposition the dropdown.
        """
        if self.is_dropdown_open:
            return

        # Setup or re-setup the autocomplete widgets.
        self._setup_autocomplete_widgets()
        # Make the toplevel window visible.
        self.autocomplete_toplevel.deiconify()
        self.autocomplete_toplevel.lift()
        self.is_dropdown_open = True

        # Bind the root window's <Configure> event to call _on_root_configure
        # for dynamic repositioning.
        self._configure_funcid = self.root.bind("<Configure>", self._on_root_configure, add="+")
        # Immediately update the dropdown's position.
        self._update_dropdown_position()

    def _update_dropdown_position(self):
        """
        Continuously repositions the autocomplete dropdown relative to its entry widget.
        This method handles scenarios where the main window is moved or resized,
        or when the entry is within a scrollable canvas. It uses `after` to
        periodically check and adjust the position.
        """
        # Cancel any previous scheduled position update to avoid multiple concurrent updates.
        if self._after_id:
            try:
                self.entry.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

        # If the toplevel or entry are no longer mapped or the dropdown is closed, hide it.
        if not self.autocomplete_toplevel or not self.autocomplete_toplevel.winfo_exists() or \
           not self.entry.winfo_ismapped() or not self.is_dropdown_open:
            self._hide_autocomplete()
            return

        try:
            # Get the root coordinates and dimensions of the entry widget.
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            fixed_height = 100 # Fixed height for the dropdown.

            # Update the geometry of the autocomplete toplevel.
            self.autocomplete_toplevel.geometry(f"{self._dropdown_fixed_width}x{fixed_height}+{x}+{y}")

            # If the entry is inside a Canvas, adjust position based on canvas scrolling.
            if self.canvas and self.canvas.winfo_ismapped():
                # Get the root Y coordinate of the entry and canvas.
                entry_root_y = self.entry.winfo_rooty()
                canvas_root_y = self.canvas.winfo_rooty()
                # Calculate the entry's Y position relative to the canvas's internal coordinates.
                entry_canvas_y = self.canvas.canvasy(entry_root_y - canvas_root_y)
                entry_height = self.entry.winfo_height()
                # Determine the top edge of the dropdown relative to the canvas's internal coordinates.
                dropdown_top_relative_to_canvas = entry_canvas_y + entry_height

                # Get the currently visible area of the canvas.
                visible_top_of_canvas = self.canvas.canvasy(0)
                visible_bottom_of_canvas = visible_top_of_canvas + self.canvas.winfo_height()

                # If the dropdown's top is outside the visible canvas area, hide the dropdown.
                if dropdown_top_relative_to_canvas < visible_top_of_canvas or \
                   dropdown_top_relative_to_canvas > visible_bottom_of_canvas:
                    self._hide_autocomplete()
                    return

        # Catch Tkinter TclError (e.g., if a widget is destroyed during update) or other exceptions.
        except tk.TclError:
            self._hide_autocomplete()
            return
        except Exception:
            self._hide_autocomplete()
            return

        # If the dropdown is still open, schedule the next position update.
        if self.is_dropdown_open:
            self._after_id = self.entry.after(50, self._update_dropdown_position)

    def _hide_autocomplete(self, event=None, return_focus_to_entry=False):
        """
        Hides the autocomplete suggestions dropdown and cleans up associated resources
        like scheduled `after` calls and root window bindings.

        Args:
            event (tk.Event, optional): The event object that triggered this method. Defaults to None.
            return_focus_to_entry (bool): If True, explicitly sets focus back to the entry widget
                                          after hiding the dropdown. Defaults to False.
        """
        # Cancel any pending _update_dropdown_position calls.
        if self._after_id:
            try:
                self.entry.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

        # Unbind the root window's configure event if it was bound.
        if self._configure_funcid and self.root.winfo_exists():
            try:
                self.root.unbind("<Configure>", self._configure_funcid)
            except tk.TclError:
                pass
            self._configure_funcid = None

        # Destroy the autocomplete toplevel window if it exists.
        if self.autocomplete_toplevel and self.autocomplete_toplevel.winfo_exists():
            self.autocomplete_toplevel.destroy()

        # Reset the toplevel and listbox references and the dropdown state flag.
        self.autocomplete_toplevel = None
        self.autocomplete_listbox = None
        self.is_dropdown_open = False

        # If requested, return focus to the entry widget.
        if return_focus_to_entry:
            if self.entry.winfo_exists(): # Check if entry still exists before setting focus.
                self.entry.focus_set()
    

    def _hide_autocomplete_and_return_focus(self, event=None):
        """
        A wrapper method that hides the autocomplete dropdown and explicitly
        ensures the focus is returned to the entry widget. Useful for handling
        keys like Escape.
        """
        self._hide_autocomplete(event, return_focus_to_entry=True)
        return "break" # Prevents the event from propagating further.

    def _handle_global_click(self, event):
        """
        Handles mouse clicks anywhere on the root window. This is used to
        determine if a click occurred outside the FilePathSearch widget's
        entry or its autocomplete dropdown. If so, it hides the dropdown.
        """
        clicked_widget = event.widget

        # Check if the click occurred within the autocomplete dropdown's area.
        is_click_in_dropdown_area = False
        if self.autocomplete_toplevel and self.autocomplete_toplevel.winfo_exists():
            is_click_in_dropdown_area = (clicked_widget is self.autocomplete_toplevel or
                                          str(clicked_widget).startswith(str(self.autocomplete_toplevel) + '.'))

        # Check if the click occurred directly on the entry widget.
        is_click_on_entry = (clicked_widget is self.entry)

        # If the click was inside the dropdown or on the entry, do not hide the dropdown.
        # Instead, ensure focus is on the entry if the dropdown is open.
        if is_click_in_dropdown_area or is_click_on_entry:
            if self.is_dropdown_open:
                self.entry.focus_set()
            return

        # If the click was outside both the entry and the dropdown, and the dropdown is open,
        # hide the dropdown and validate the path.
        if self.is_dropdown_open:
            self._hide_autocomplete(return_focus_to_entry=False)
            self._validate_path(show_pop_ups=True)


    def _on_focus_out(self, event):
        """
        Handles the event when focus leaves the entry widget.
        It checks if the focus moved to the autocomplete dropdown itself;
        otherwise, it hides the dropdown and triggers path validation.
        """
        # Determine the widget that currently has focus in the root window.
        focused_widget = self.root.focus_get()

        # If focus moved to the entry itself or any part of the autocomplete toplevel,
        # do nothing, as this is expected behavior within the widget's interaction.
        if focused_widget is self.entry or \
           (self.autocomplete_toplevel and self.autocomplete_toplevel.winfo_exists() and \
            str(focused_widget).startswith(str(self.autocomplete_toplevel))):
            return

        # If focus moved outside this widget's components and the dropdown is open,
        # hide the dropdown and perform path validation.
        if self.is_dropdown_open:
            self._hide_autocomplete(return_focus_to_entry=False)
            self._validate_path(show_pop_ups=True)
    

    def _handle_key_release(self, event):
        """
        Handles the KeyRelease event for the entry widget.
        It triggers autocomplete suggestions based on the current text in the entry,
        unless the key pressed is one of the navigation/action keys (Up, Down, Return, Escape, Tab).
        """
        current_text = self.var.get()
        # Ignore certain key presses that are handled by other specific binders.
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        
        # If the user has typed something, show the autocomplete dropdown and update suggestions.
        if current_text.strip():
            self._show_autocomplete()
            self._update_suggestions(current_text)
        else:
            # If the entry is empty, hide the autocomplete dropdown.
            self._hide_autocomplete()

        # Always validate the path after a key release to provide immediate feedback.
        self._validate_path()

    def _update_suggestions(self, current_input):
        """
        Updates the autocomplete listbox with relevant directory suggestions
        based on the user's current input. It handles different operating systems
        (Windows drive letters) and determines the base path and partial name for searching.
        """
        # If the entry is not mapped (e.g., window is hidden or destroyed), hide the dropdown.
        if not self.entry.winfo_ismapped():
            self._hide_autocomplete()
            return

        # If the input is empty, hide the dropdown.
        if current_input.strip() == "":
            self._hide_autocomplete()
            return

        base_path = ""
        partial_name = ""

        # Special handling for Windows drive letters (e.g., "C:" or "C").
        if os.name == 'nt' and (len(current_input) == 2 and current_input[1] == ':' or
                                (len(current_input) == 1 and current_input.isalpha())):
            base_path = "" # Base path is empty for drive root suggestions.
            partial_name = current_input.upper() # Partial name is the drive letter.
        else:
            # If input ends with a separator and is a directory, it's the base path.
            if current_input.endswith(os.sep) and os.path.isdir(current_input):
                base_path = current_input
                partial_name = ""
            else:
                # Otherwise, split into directory and filename parts.
                base_path = os.path.dirname(current_input)
                partial_name = os.path.basename(current_input)

            # If no base path, default to current directory.
            if not base_path:
                base_path = "."

        try:
            # Ensure the autocomplete widgets are set up before populating.
            if not self.autocomplete_toplevel or not self.autocomplete_toplevel.winfo_exists():
                self._setup_autocomplete_widgets()
            
            # Clear previous suggestions from the listbox.
            self.autocomplete_listbox.delete(0, tk.END)
            suggestions = []

            # Logic for generating suggestions based on the operating system.
            if os.name == 'nt' and not base_path: # On Windows, if no specific base path, list drives.
                for drive_letter_char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    drive_path = drive_letter_char + ":" + os.sep
                    # Check if drive exists and starts with the partial name.
                    if os.path.exists(drive_path) and os.path.isdir(drive_path) and \
                       drive_letter_char.lower().startswith(partial_name.lower().strip(':')):
                        suggestions.append(drive_path)
            elif os.path.exists(base_path) and os.path.isdir(base_path): # If base path is a valid directory.
                # List items in the base directory.
                for item in os.listdir(base_path):
                    full_path_item = os.path.join(base_path, item)
                    # If it's a directory and matches the partial name, add as a suggestion.
                    if os.path.isdir(full_path_item) and item.lower().startswith(partial_name.lower()):
                        suggestions.append(item)
            else:
                # If the base path doesn't exist or isn't a directory, hide the dropdown.
                self._hide_autocomplete()
                return

            self.filtered_options = suggestions

            # If suggestions are found, sort them and insert into the listbox.
            if suggestions:
                suggestions.sort(key=lambda s: s.lower()) # Sort suggestions alphabetically.
                for s in suggestions:
                    self.autocomplete_listbox.insert(tk.END, s)

                # Show the dropdown and store the base path for future selections.
                self._show_autocomplete()
                self.current_autocomplete_base_path = base_path
                self._update_dropdown_position() # Ensure dropdown is positioned correctly.
            else:
                # If no suggestions, hide the dropdown.
                self._hide_autocomplete()

        # Handle OS-related errors (e.g., permission denied) or other general exceptions.
        except OSError:
            self._hide_autocomplete()
        except Exception:
            self._hide_autocomplete()

    def _select_item(self, event=None):
        """
        Handles the selection of an item from the autocomplete listbox.
        It constructs the full path, normalizes it, appends a path separator
        if it's a directory, updates the entry field, and then updates
        the suggestions based on the newly selected path.
        """
        # If no listbox or no item is currently selected, do nothing.
        if not self.autocomplete_listbox or not self.autocomplete_listbox.curselection():
            return

        # Get the index and value of the selected item.
        selected_index = self.autocomplete_listbox.curselection()[0]
        selected_item = self.autocomplete_listbox.get(selected_index)

        # Determine the full path candidate. Special handling for Windows drive letters.
        if not self.current_autocomplete_base_path and os.name == 'nt' and ":" in selected_item:
            full_path_candidate = selected_item
        else:
            full_path_candidate = os.path.join(self.current_autocomplete_base_path, selected_item)

        # Normalize the path to handle ".." and other relative components.
        normalized_path = os.path.normpath(full_path_candidate)

        # Append a path separator if the selected item is a directory and doesn't already have one.
        final_path = normalized_path
        if os.path.isdir(normalized_path) and not normalized_path.endswith(os.sep):
            final_path += os.sep

        # Update the entry widget's text with the finalized path.
        self.var.set(final_path)
        # Place the text cursor at the end of the entry for continued typing.
        self.entry.icursor(tk.END)

        # Validate the updated path.
        self._validate_path()
        
        # Instead of hiding the dropdown, update the suggestions based on the newly entered path.
        # This allows for navigating into subdirectories via selection.
        self._update_suggestions(self.var.get())
        # Ensure that the entry widget retains focus so the user can continue typing or navigating.
        self.entry.focus_set()

    def _select_item_on_enter(self, event=None):
        """
        Handles the <Return> (Enter) key press event.
        If the autocomplete dropdown is open and an item is selected (or if it has items,
        selects the first one if none is explicitly selected), it calls `_select_item`.
        Otherwise, if the dropdown is open but empty, it hides it.
        If the dropdown is not open, it simply validates the current path in the entry.
        """
        if self.is_dropdown_open and self.autocomplete_listbox:
            selected_indices = self.autocomplete_listbox.curselection()
            if selected_indices:
                # If an item is selected, process the selection.
                self._select_item(event) # This will in turn call _update_suggestions.
            elif self.autocomplete_listbox.size() > 0:
                # If no item is selected but there are suggestions, select the first one.
                self.autocomplete_listbox.selection_clear(0, tk.END)
                self.autocomplete_listbox.selection_set(0)
                self.autocomplete_listbox.see(0) # Scroll to make the first item visible.
                self._select_item(event) # Process the newly selected first item.
            else:
                # If the dropdown is open but empty, hide it and validate the current entry.
                self._hide_autocomplete(return_focus_to_entry=True)
                self._validate_path()
            return "break" # Prevent default Tkinter behavior for <Return>.
        else:
            # If the dropdown is not open, simply validate the path and show pop-ups if needed.
            self._validate_path(show_pop_ups=True)
            return "break" # Prevent default Tkinter behavior for <Return>.

    def _navigate_list(self, event):
        """
        Handles Up and Down arrow key presses for navigating the autocomplete listbox.
        It updates the selection in the listbox and ensures the selected item is visible.
        """
        if self.is_dropdown_open and self.autocomplete_listbox:
            current_selection = self.autocomplete_listbox.curselection()
            list_size = self.autocomplete_listbox.size()

            # If the listbox is empty, do nothing.
            if not list_size:
                return "break"

            next_index = 0
            if event.keysym == "Down":
                # If no item is selected, select the first. Otherwise, move down one.
                if not current_selection:
                    next_index = 0
                else:
                    next_index = (current_selection[0] + 1) % list_size # Wrap around to the beginning.
            elif event.keysym == "Up":
                # If no item is selected, select the last. Otherwise, move up one.
                if not current_selection:
                    next_index = list_size - 1
                else:
                    next_index = (current_selection[0] - 1 + list_size) % list_size # Wrap around to the end.
            else:
                return # Should not happen given the bind definition, but as a safeguard.

            # Clear current selection, set new selection, and ensure it's visible.
            self.autocomplete_listbox.selection_clear(0, tk.END)
            self.autocomplete_listbox.selection_set(next_index)
            self.autocomplete_listbox.see(next_index)
            return "break" # Stop event propagation.

    def _on_tab_key(self, event=None):
        """
        Handles the Tab key press event. It hides the autocomplete dropdown,
        validates the current path, and then allows the default Tkinter Tab
        behavior (moving focus to the next widget) to proceed.
        """
        self._hide_autocomplete(return_focus_to_entry=False) # Hide dropdown without forcing focus back to entry.
        self._validate_path(show_pop_ups=True) # Validate the path, potentially showing pop-ups.
        return None # Return None to allow the default Tab behavior (focus traversal).

    def _validate_path(self, show_pop_ups=False):
        """
        Validates the path currently entered in the entry widget.
        It checks if the path is empty, if it exists and is a directory,
        or if it needs to be created (based on `self.must_exist`).
        The entry's background color is updated to indicate validity.
        Optionally displays message boxes for user feedback.

        Args:
            show_pop_ups (bool): If True, message boxes are displayed for invalid paths
                                 or to prompt for directory creation. Defaults to False.

        Returns:
            bool: True if the path is valid (exists as a directory or was successfully created),
                  False otherwise.
        """
        path = self.var.get().strip()

        # Handle empty path.
        if not path:
            # Change background color: orange if no pop-up, redder if pop-up intended.
            self.entry.config(bg="#FFCC99" if not show_pop_ups else "#ffdddd")
            if show_pop_ups:
                messagebox.showerror("Invalid Path", "Path cannot be empty.")
            return False

        try:
            path_obj = Path(path) # Use pathlib for robust path handling.

            # Check if the path exists and is a directory.
            if path_obj.is_dir():
                self.entry.config(bg="white") # Valid path, set background to white.
                return True

            # Check if the path exists but is not a directory (e.g., a file).
            if path_obj.exists():
                self.entry.config(bg="#FFCC99") # Indicate problem with orange background.
                if show_pop_ups:
                    messagebox.showerror(
                        "Path Type Mismatch",
                        f"The path '{path}' exists but is not a directory. Please choose a directory path."
                    )
                return False

            # If the path does not exist and `must_exist` is True, it's invalid.
            if self.must_exist:
                self.entry.config(bg="#ffdddd") # Red background for required non-existent path.
                # No pop-up here, as the user might be typing. Pop-ups handled by caller.
                return False

            # If `must_exist` is False and `show_pop_ups` is False, just indicate with orange.
            if not show_pop_ups:
                self.entry.config(bg="#FFCC99")
                return False

            # If `must_exist` is False and `show_pop_ups` is True, prompt to create the directory.
            response = messagebox.askyesno(
                "Create Directory?",
                f"The directory path '{path}' does not exist. Do you want to create it?"
            )

            if response:
                try:
                    # Attempt to create the directory, including any necessary parent directories.
                    path_obj.mkdir(parents=True, exist_ok=True)
                    messagebox.showinfo("Directory Created", f"Directory '{path}' has been created.")
                    self.entry.config(bg="white") # Set background to white upon successful creation.
                    return True
                except OSError as e:
                    # Handle OS-level errors during directory creation (e.g., permissions).
                    messagebox.showerror(
                        "Creation Error",
                        f"Failed to create directory '{path}':\n{e}\n\nPlease choose another path."
                    )
                    self.entry.config(bg="#ffdddd") # Red background for creation failure.
                except Exception as e:
                    # Catch any other unexpected errors during creation.
                    messagebox.showerror(
                        "Error",
                        f"An unexpected error occurred during directory creation:\n{e}"
                    )
                    self.entry.config(bg="#ffdddd") # Red background for unexpected failure.
            else:
                # If user declines to create the directory.
                messagebox.showinfo(
                    "Path Not Created",
                    "Please choose another directory path."
                )
                self.entry.config(bg="#ffdddd") # Red background for non-creation.

            return False # Path is not valid if creation failed or was declined.

        except Exception as e:
            # Catch any general exceptions during path manipulation/validation.
            self.entry.config(bg="#ffdddd") # Red background for any validation error.
            if show_pop_ups:
                messagebox.showerror(
                    "Invalid Path Syntax/Error",
                    f"An error occurred while validating path '{path}':\n{e}\n\nPlease choose another path."
                )
            return False

    def get(self):
        """
        Retrieves the current path from the entry widget and validates it.

        Returns:
            str: The normalized, validated path if it's valid; otherwise, an empty string.
        """
        value = self.var.get().strip()
        # Validate the path; if valid, return the normalized path.
        if self._validate_path():
            return os.path.normpath(value)
        return "" # Return empty string if path is invalid.

    def set(self, path):
        """
        Sets the value of the entry widget to the given path and triggers validation.

        Args:
            path (str): The path string to set in the entry widget.
        """
        self.var.set(path)
        self._validate_path()

    def _add_live_tooltip(self):
        """
        Configures and binds a dynamic tooltip to the entry widget.
        This tooltip appears when the mouse hovers over the entry and the
        entered text overflows its visible area, displaying the full path.
        """
        # Create a Toplevel window for the tooltip, initially hidden and undecorated.
        self.tooltip = tk.Toplevel(self.entry)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True) # Remove window decorations (title bar, borders).
        self.tooltip.configure(bg="lightyellow", padx=1, pady=1) # Set background and padding.

        # Define the font for the tooltip label.
        self.tooltip_label_font = tkfont.Font(family=const.gui_font, size=const.param_font_size)

        # Create the label inside the tooltip.
        self.tooltip_label = tk.Label(
            self.tooltip,
            text="",
            background="lightyellow",
            relief="solid",
            borderwidth=1,
            justify="left",
            wraplength=const.FIXED_INPUT_WIDTH, # Wrap text to the entry's fixed width.
            font=self.tooltip_label_font
        )
        self.tooltip_label.pack() # Pack the label to fill the tooltip window.

        # Initialize state variables for tooltip management.
        self._tooltip_mouse_inside = False
        self._tooltip_after_id = None

        def text_overflows():
            """Helper function to check if the text in the entry overflows its visible width."""
            text = self.var.get()
            self.entry.update_idletasks() # Ensure widget size is updated for accurate measurement.
            text_width = self.entry_font.measure(text)
            # Use max to avoid division by zero or issues with zero width, add buffer for padding.
            entry_width = max(self.entry.winfo_width(), 100)
            return text_width > (entry_width - 10) # 10 pixels for internal padding.

        def show_tooltip_delayed():
            """
            Displays the tooltip after a short delay if the mouse is still over the entry
            and the text overflows.
            """
            if not self._tooltip_mouse_inside:
                return # If mouse has left, do not show tooltip.
            self.entry.update_idletasks() # Update to get current entry dimensions.
            if not text_overflows():
                self.tooltip.withdraw() # Hide tooltip if text no longer overflows.
                return
            value = self.var.get().strip()
            self.tooltip_label.config(text=value) # Set tooltip text.

            # Position the tooltip just below the entry.
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            self.tooltip.geometry(f"+{x}+{y}")
            self.tooltip.deiconify() # Make the tooltip visible.

        def on_enter(event=None):
            """Event handler for when the mouse enters the entry widget."""
            self._tooltip_mouse_inside = True
            # Schedule the tooltip to show after a delay.
            self._tooltip_after_id = self.entry.after(150, show_tooltip_delayed)

        def on_leave(event=None):
            """Event handler for when the mouse leaves the entry widget."""
            self._tooltip_mouse_inside = False
            self.tooltip.withdraw() # Immediately hide the tooltip.
            # Cancel any pending tooltip display.
            if self._tooltip_after_id:
                self.entry.after_cancel(self._tooltip_after_id)
                self._tooltip_after_id = None

        # Bind mouse enter and leave events to the entry widget.
        self.entry.bind("<Enter>", on_enter)
        self.entry.bind("<Leave>", on_leave)

    def update_font(self):
        """
        Updates the font sizes of the entry widget, its associated InfoLabel,
        the autocomplete listbox, and the live tooltip label. This method is
        intended to be called when the global font size settings change in the GUI.
        """
        # Update the font of the InfoLabel if it exists and has an update_font method.
        if self.info_label and hasattr(self.info_label, 'update_font'):
            self.info_label.update_font()

        # Update the configuration of the entry and listbox fonts with the new size.
        self.entry_font.config(size=const.param_font_size)
        self.listbox_font.config(size=const.param_font_size)

        # If the autocomplete listbox exists and is mapped, update its font.
        if self.autocomplete_listbox and self.autocomplete_listbox.winfo_exists():
            self.autocomplete_listbox.config(font=self.listbox_font)

        # Update the tooltip label font if it exists.
        if hasattr(self, 'tooltip_label_font') and self.tooltip_label_font:
            self.tooltip_label_font.config(size=const.param_font_size)
            # Re-initialize the live tooltip to ensure its dimensions and text overflow
            # detection are correctly updated based on the new font size.
            self._add_live_tooltip()