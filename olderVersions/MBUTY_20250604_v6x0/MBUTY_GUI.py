# -*- coding: utf-8 -*-
"""
Created on Wed May 21 16:43:15 2025

@author: sheilamonera
"""
###############################################################################
"""
Issues that need resolving:
    - Font resizing of params does not work properly on macOS (non-critical)
    
Things to add/improve:
    - Add a reset defaults button
    - Add an option to save selected params in json
    - Add option to load default params from json
    - Add styling/ make it look nicer
"""
###############################################################################
import os
import sys
import queue
import threading
import ctypes
import tkinter as tk
import matplotlib.pyplot as plt
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

import GUI.base_constants as const
from GUI.expandable_section import ExpandableSection
from GUI.gui_config import config, parameters
from GUI.gui_utils import create_gui_widget, setup_dynamic_file_options, setup_dynamic_option_resolver, should_show, extract_dependency_keys, update_widget_fonts
from GUI.console_widgets import ANSIColorTextWidget, ConsoleRedirector
from MBUTY import MBUTYmain
from lib import libTerminal as ta
from GUI.scroll_helpers import bind_mousewheel, unbind_mousewheel

class MBUTY_GUI_App:
    """
    Main application class for the MBUTY GUI.

    This class manages the Tkinter window, builds the user interface for
    parameter input, handles analysis execution, and displays output.
    It integrates various GUI components and backend logic for the MBUTY analysis.
    """
    def __init__(self):
        """
        Initializes the MBUTY_GUI_App, setting up instance variables
        and building the main window structure.
        """
        # Initialize instance variables to manage application state and widgets
        self.analysis_running = False
        self.backend_thread = None
        self.widgets = {} # Stores references to all created input widgets
        self.stop_button = None
        self.console_text_widget = None
        self.current_subprocess_handle = None # For tracking external processes like rsync
        self.all_font_dynamic_widgets = [] # List to track widgets whose fonts need dynamic updates
        self.main_app_title_label = None
        self.run_button = None
        self.close_plots_button = None
        self.buttons_frame = None
        self.win = None # The main Tkinter window
        self.main_thread_queue = queue.Queue() # Queue for thread-safe GUI updates
        self.scrollbar = None # Scrollbar for the parameter canvas
        self.canvas = None # Canvas for scrollable parameter section
        self.frame = None # Frame inside the canvas that holds parameter widgets
        self.output_frame = None # Frame for displaying console output
        self.current_param_font_size_label = None # Label showing current font size
        self.console_redirector = None # Object to redirect stdout to the console widget
        self.main_frame = None # Main content frame of the window
        self.original_stdout = sys.stdout # Store original stdout early to restore it later
        # Initialize a list for tasks that need to be executed after all widgets are created
        self.after_widgets_created_tasks = []

        self._build_window_structure() # Construct the GUI
        self.win.protocol("WM_DELETE_WINDOW", self._on_closing) # Set custom close handler
        self.check_queue() # Start periodic check for main thread tasks

    # === Scrollable Canvas Behavior ===
    def _resize_canvas(self, event=None):
        """
        Resizes the canvas width to match its parent frame during layout updates.

        Args:
            event (tk.Event, optional): The event object (e.g., from a <Configure> bind).
                                        Defaults to None.
        """
        if self.canvas: # Ensure the canvas widget exists
            # Update the width of the inner frame within the canvas to match canvas width
            self.canvas.itemconfig("inner_frame", width=self.canvas.winfo_width())

    def _update_param_scrollregion(self, event=None):
        """
        Updates the scroll region of the parameter canvas based on the content's bounding box.
        This ensures the scrollbar accurately reflects the scrollable area.

        Args:
            event (tk.Event, optional): The event object (e.g., from a <Configure> bind).
                                        Defaults to None.
        """
        # Return if canvas does not exist or is not visible
        if self.canvas is None or not self.canvas.winfo_exists():
            return

        # Get the bounding box of all items within the canvas
        bbox = self.canvas.bbox("all")
        if bbox is None:
            # If no items, set scroll region to empty
            self.canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        # Configure the canvas scroll region based on the content's bounding box
        self.canvas.configure(scrollregion=bbox)

    # === Consolidated Function for updating all fonts ===
    def update_fonts(self, value=None):
        """
        Updates the font size for all relevant GUI elements, including dynamic widgets
        and main window specific elements. This function is typically called
        by the font size slider.

        Args:
            value (str, optional): The new font size value from a slider (as a string).
                                   If None, it uses the current `const.param_font_size`.
        """
        if value is not None:
            new_size = int(float(value))
            # Only update if the size has actually changed to avoid unnecessary reconfigurations
            if const.param_font_size != new_size:
                const.param_font_size = new_size # Update the global constant

        # 1. Update the font size label specific to the parameter panel's slider
        if self.current_param_font_size_label and self.current_param_font_size_label.winfo_exists():
             self.current_param_font_size_label.config(text=f"{const.param_font_size} pt",
                                                       font=(const.gui_font, const.param_font_size))

        # 2. Update all registered dynamic widgets using the utility helper function
        update_widget_fonts(self.all_font_dynamic_widgets, const.param_font_size, const.gui_font)

        # 3. Update main window specific fonts directly
        # Update Main Title label font
        if self.main_app_title_label and self.main_app_title_label.winfo_exists():
            self.main_app_title_label.config(font=(const.gui_font, const.param_font_size + 8, "bold"))

        # Update Run Button font
        if self.run_button and self.run_button.winfo_exists():
            self.run_button.config(font=(const.gui_font, const.param_font_size + 3, "bold"))

        # Update Stop Button font
        if self.stop_button and self.stop_button.winfo_exists():
            self.stop_button.config(font=(const.gui_font, const.param_font_size + 3, "bold"))

        # Update Close Plots Button font
        if self.close_plots_button and self.close_plots_button.winfo_exists():
            self.close_plots_button.config(font=(const.gui_font, const.param_font_size + 3, "bold"))

        # 4. Force a redraw and recalculate window size after all font updates are complete
        if self.win and self.win.winfo_exists():
            self.win.update_idletasks() # Processes all pending geometry and redraw events

    # === Build Parameter UI ===
    def _build_parameter_ui(self, parent_frame):
        """
        Builds the entire parameter input interface within a scrollable canvas.

        This function sets up:
        - A left-hand scrollable "Parameters" panel (`canvas` and `frame`).
        - A right-hand "Output" panel (`output_frame`) which initially remains hidden.
        - Populates the `widgets` dictionary with references to all created UI widgets.
        - Iterates through the `config` dictionary to create and display
          static and expandable parameter sections using `_display_param()`.

        Args:
            parent_frame (tk.Frame): The container frame where both the parameter
                                     section (left) and output section (right) are placed.
        """
        # === LEFT: Scrollable Parameters Panel ===
        # Create a LabelFrame to group parameter inputs
        wrapper = tk.LabelFrame(parent_frame, text="Parameters", width=600)
        wrapper.grid(row=0, column=0, sticky="ns", padx=(0, 5), pady=5)
        wrapper.grid_rowconfigure(0, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        # Create a Canvas widget within the wrapper for scrollability
        self.canvas = tk.Canvas(wrapper, width=600)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        # Create a vertical scrollbar and link it to the canvas
        self.scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create a Frame inside the canvas to hold the actual parameter widgets
        self.frame = tk.Frame(self.canvas)
        # Create a window on the canvas, embedding the frame. "inner_frame" tag is for resizing.
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw", tags="inner_frame")

        # Bind canvas resizing to adjust the inner frame's width
        self.canvas.bind("<Configure>", self._resize_canvas)
        # Bind inner frame's configure event to update the canvas scroll region
        self.frame.bind("<Configure>", lambda e: self.canvas.after(50, self._update_param_scrollregion))

        # Bind mouse wheel for scrolling on the canvas
        bind_mousewheel(self.win, self.canvas)

        # Font Size Slider for Parameter Panel - placed at the very top of `self.frame`
        font_control_frame = tk.Frame(self.frame, pady=5)
        font_control_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Create and add Font Size label to the list of dynamic widgets for font updates
        font_label = tk.Label(font_control_frame, text="Font Size:", font=(const.gui_font, const.param_font_size))
        font_label.pack(side="left")
        self.all_font_dynamic_widgets.append({"widget": font_label, "type": "label", "font_offset": 0})

        # Create and add current font size label to the list of dynamic widgets
        self.current_param_font_size_label = tk.Label(font_control_frame, text=f"{const.param_font_size} pt", font=(const.gui_font, const.param_font_size))
        self.current_param_font_size_label.pack(side="right", padx=(5,0))
        self.all_font_dynamic_widgets.append({"widget": self.current_param_font_size_label, "type": "label", "font_offset": 0})

        # Create the font size slider
        font_size_slider = ttk.Scale(
            font_control_frame,
            from_=8,
            to=18, # Defines the range of font sizes
            orient="horizontal",
            # Update the label text immediately as slider is moved
            command=lambda val: self.current_param_font_size_label.config(text=f"{int(float(val))} pt", font=(const.gui_font, int(float(val))))
            )
        # When the mouse button is released (slider movement finishes), update all fonts
        font_size_slider.bind("<ButtonRelease-1>", lambda event: self.update_fonts(font_size_slider.get()))
        font_size_slider.set(const.param_font_size) # Set the initial position of the slider
        font_size_slider.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # === RIGHT: Scrollable Output Panel (initially hidden) ===
        # Create a LabelFrame for the output section
        self.output_frame = tk.LabelFrame(parent_frame, text="Output", width=600)
        # Do NOT grid the output frame yet; it will be displayed when analysis starts
        self.output_frame.grid_rowconfigure(0, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=1)

        # === Parameters inside the LEFT panel ===
        # Frame for static parameters (always visible, not in an expandable section)
        static_section = tk.Frame(self.frame)
        static_section.pack(fill="x", pady=5)
        # Configure columns for consistent widget alignment
        static_section.grid_columnconfigure(0, minsize=const.label_width)
        static_section.grid_columnconfigure(1, minsize=const.FIXED_INPUT_WIDTH, weight=0)

        row = 0
        # Iterate through static parameters defined in the config and display them
        for key, item in config["static"].items():
            row = self._display_param(static_section, key, item, row, self.widgets, config)

        # Assign the custom synchronization function to the syncDataButton command
        config["static"]["syncDataButton"]["command"] = self.custom_sync_data

        # Loop through other sections (non-static) and create ExpandableSection widgets
        for section_name, section_items in config.items():
            if section_name == "static": # Skip the static section as it's handled above
                continue
            # Create an ExpandableSection with a formatted title
            section = ExpandableSection(self.frame, section_name.replace("_", " ").title() + " Parameters")
            section.pack(fill="x", padx=10, pady=10)

            # Add the ExpandableSection instance to the list of dynamic font widgets.
            # It's marked as 'custom_composite' because it manages its own internal widget fonts.
            self.all_font_dynamic_widgets.append({
                "widget": section,
                "type": "custom_composite", # Custom type indicating it has an update_font method
                "font_offset": 0, # Offset handled internally by ExpandableSection
                "style": () # Style handled internally
            })
            # Get the content frame of the expandable section to place parameters inside
            section_frame = section.get_content_frame()
            # Configure columns for consistent widget alignment within the section
            section_frame.grid_columnconfigure(0, minsize=const.label_width)
            section_frame.grid_columnconfigure(1, minsize=const.FIXED_INPUT_WIDTH, weight=0)

            row = 0 # Reset row counter for content within each new expandable section
            # Iterate through parameters in the current section and display them
            for key, item in section_items.items():
                row = self._display_param(section_frame, key, item, row, self.widgets, config)

    # === Display a Single Input Widget ===
    def _display_param(self, frame, key, item, row, widgets, config):
        """
        Creates and places a dynamic parameter input widget within the GUI based
        on its configuration metadata. Handles dependencies and dynamic options.

        Args:
            frame (tk.Frame): The parent frame where the widget will be placed.
            key (str): The unique identifier key for the parameter.
            item (dict): The dictionary containing configuration details for the parameter.
            row (int): The current grid row number for placement.
            widgets (dict): A dictionary to store references to all created widgets.
            config (dict): The global configuration dictionary containing all parameters.

        Returns:
            int: The updated row number after placing the widget.
        """
        input_type = item["type"]
        depends_on = item.get("dependsOn")

        # Call the utility helper function to create the widget and its row frame
        widget_instance, actual_row_frame_for_visibility, updated_row, widget_info_for_font_list = \
            create_gui_widget(frame, key, item, row, existing_widgets_for_dynamic_paths=widgets)

        # If widget creation failed, return the original row
        if widget_instance is None:
            return updated_row

        # Add the widget's font information to the list for dynamic font updates
        if widget_info_for_font_list:
            self.all_font_dynamic_widgets.append(widget_info_for_font_list)

        # Store the created widget instance in the widgets dictionary for later access
        widgets[key] = widget_instance

        # === Apply dependency logic if 'dependsOn' is specified for this item ===
        if depends_on:
            # Assign the row frame to the widget instance for visibility control
            widget_instance._row_frame = actual_row_frame_for_visibility
            # Assign a lambda function to determine widget visibility based on dependencies
            widget_instance.should_show = lambda: should_show(depends_on, widgets) # Pass widgets to should_show

            # Extract and iterate through controlling keys from the 'dependsOn' condition
            for controller_key in extract_dependency_keys(depends_on):
                controller = widgets.get(controller_key)
                # If the controller widget exists and has a Tkinter variable (e.g., StringVar, IntVar)
                if controller and hasattr(controller, "var"):
                    # Trace changes to the controller's variable to update visibility
                    controller.var.trace_add("write", lambda *args, w=widget_instance:
                                             w._row_frame.grid() if w.should_show() else w._row_frame.grid_remove())

            # Perform an initial check to set the correct visibility upon creation
            if not should_show(depends_on, widgets):
                actual_row_frame_for_visibility.grid_remove() # Hide if dependencies are not met

        # === Handle dynamic options for dropdowns/multiSelects ===
        if input_type in ["dropdown", "multiSelect"]:
            dynamic_path_key = item.get("optionsFromPath")
            file_filter = item.get("fileTypeFilter")
            # If options are to be populated from files in a dynamic path
            if dynamic_path_key and file_filter:
                # Defer the setup of dynamic file options until all widgets are created
                self.after_widgets_created_tasks.append(
                    lambda w=widget_instance, dpk=dynamic_path_key, ff=file_filter:
                        setup_dynamic_file_options(w, widgets.get(dpk), ff)
                )
            # If options are dynamically resolved based on other watch keys
            elif "dynamicOptions" in item and "watchKeys" in item:
                # Defer the setup of dynamic option resolution until all widgets are created
                self.after_widgets_created_tasks.append(
                    lambda w=widget_instance, dyn_opt=item["dynamicOptions"], wk=item["watchKeys"]:
                        setup_dynamic_option_resolver(w, dyn_opt, widgets, wk)
                )

        return updated_row # Return the updated row number for the next widget placement

    def _raise_keyboard_interrupt(self, thread):
        """
        Forcefully raises a KeyboardInterrupt in a specified thread.
        This is used to attempt to stop long-running Python backend operations.

        Args:
            thread (threading.Thread): The target thread in which to raise the interrupt.

        Raises:
            ValueError: If the thread ID is invalid.
            SystemError: If PyThreadState_SetAsyncExc fails unexpectedly.
        """
        # Return if the thread is not valid or not alive
        if not thread or not thread.is_alive():
            return
        tid = ctypes.c_long(thread.ident) # Get the thread ID
        # Use Python C API to asynchronously raise an exception in the target thread
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(KeyboardInterrupt))
        if res == 0:
            raise ValueError("Invalid thread ID")
        elif res > 1:
            # If res > 1, it means multiple exceptions were set; reset and raise an error
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0) # Clear pending exceptions
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_back_end(self):
        """
        Requests the stopping of any running backend analysis or data synchronization process.
        It attempts to gracefully interrupt the Python backend thread and terminate any
        external subprocesses being tracked.
        """
        print("\n\nStop operation requested by user.")

        # A. Attempt to interrupt the Python backend thread (e.g., for MBUTYmain's analysis)
        if self.backend_thread and self.backend_thread.is_alive():
            try:
                self._raise_keyboard_interrupt(self.backend_thread)
                print("Stop signal sent to backend thread.")
            except Exception as e:
                print(f"Failed to stop backend thread: {e}")

        # B. Terminate any actively tracked *external* subprocess (e.g., rsync)
        if self.current_subprocess_handle and self.current_subprocess_handle.poll() is None:
            print("Terminating active external process...")
            try:
                self.current_subprocess_handle.terminate() # Send SIGTERM (graceful termination)
                self.current_subprocess_handle.wait(timeout=5) # Wait for process to exit
                if self.current_subprocess_handle.poll() is None: # Check if still running
                    print("Process did not terminate gracefully, sending SIGKILL.")
                    self.current_subprocess_handle.kill() # Force kill (SIGKILL)
            except Exception as e:
                print(f"Error while trying to terminate process: {e}")
            finally:
                self.current_subprocess_handle = None # Clear the handle regardless of success

        self.analysis_running = False # Reset the flag indicating no analysis is running

    # === Function to set up and display the output console ===
    def _setup_output_console(self, clear_content=True):
        """
        Configures and displays the output panel, including the console text widget
        and its associated zoom slider. Optionally clears previous console content.

        Args:
            clear_content (bool, optional): If True, clears the console text widget content.
                                            Defaults to True.
        """
        # Ensure the output panel is visible and occupies its grid space
        if self.output_frame and not self.output_frame.winfo_ismapped():
            self.output_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)

        # Adjust the grid column weights of the main frame:
        # Shrink the parameter panel (column 0) and expand the output panel (column 1)
        self.main_frame.grid_columnconfigure(0, weight=0)
        self.main_frame.grid_columnconfigure(1, weight=1)

        # If the console text widget already exists, clear its content if requested
        if self.console_text_widget and self.console_text_widget.winfo_exists():
            if clear_content:
                self.console_text_widget.clear_console()
        else: # If console_text_widget does not exist, create it and its related widgets
            # Clear any existing widgets in the output_frame before creating new ones
            if self.output_frame:
                for widget in self.output_frame.winfo_children():
                    widget.destroy()

            # === Zoom bar frame ===
            zoom_frame = tk.Frame(self.output_frame)
            zoom_frame.pack(fill="x", padx=10, pady=(10, 5))

            # Create and add Zoom label to the list of dynamic font widgets
            zoom_label = tk.Label(zoom_frame, text="Zoom:", font=(const.gui_font, const.param_font_size+1))
            zoom_label.pack(side="left")
            self.all_font_dynamic_widgets.append({"widget": zoom_label, "type": "label", "font_offset": 1})

            # Create the zoom slider for the console font size
            zoom_slider = ttk.Scale(
                zoom_frame,
                from_=8, to=20, # Define the zoom range
                orient="horizontal",
                # Update the console's font size as the slider is moved
                command=lambda val: (
                    self.console_text_widget.update_font_size(int(float(val))) if self.console_text_widget else None
                )
            )
            zoom_slider.set(const.font_size) # Set initial slider position to default font size
            zoom_slider.pack(side="left", fill="x", expand=True, padx=(5, 0))

            # === Console Output Label ===
            console_output_label = tk.Label(self.output_frame, text="Console Output", font=(const.gui_font, const.param_font_size+1, "bold"), anchor="w")
            console_output_label.pack(fill="x", padx=10, pady=(0, 0))
            # Add to dynamic font widgets list
            self.all_font_dynamic_widgets.append({
                "widget": console_output_label,
                "type": "label",
                "font_offset": 1,
                "style": ("bold",)
            })

            # === Console Text Widget and Scrollbar ===
            console_scrollbar = ttk.Scrollbar(self.output_frame)
            console_scrollbar.pack(side="right", fill="y")

            # Create the custom ANSIColorTextWidget for console output
            self.console_text_widget = ANSIColorTextWidget(
                self.output_frame,
                wrap="word", # Wrap text at word boundaries
                bg="black", # Background color
                fg="white", # Foreground color
                insertbackground="white", # Cursor color
                font=("Courier New", const.font_size), # Initial font
                yscrollcommand=console_scrollbar.set, # Link scrollbar to widget
                initial_font_size=const.font_size # Pass initial font size
            )
            self.console_text_widget.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=(0, 10))
            console_scrollbar.config(command=self.console_text_widget.yview) # Link widget to scrollbar

            # Bind mouse wheel for scrolling on the console
            bind_mousewheel(self.win, self.console_text_widget)

        # Redirect standard output (sys.stdout) to the custom console text widget
        self.console_redirector = ConsoleRedirector(self.console_text_widget)
        sys.stdout = self.console_redirector

    # === Custom sync_data function ===
    def custom_sync_data(self):
        """
        Initiates a data synchronization process between a source and destination path
        using `libTerminal.transferDataUtil`. Displays progress and results in the console.
        Prevents multiple sync operations from running concurrently.
        """
        # Retrieve source and destination paths from their respective widgets
        source_path = self.widgets.get("parameters.fileManagement.sourcePath").get()
        dest_path = self.widgets.get("parameters.fileManagement.destPath").get()

        # Validate that both paths are provided
        if not source_path or not dest_path:
            messagebox.showerror("Error", "Please enter both source and destination paths before syncing.")
            return

        # Prevent concurrent operations
        if self.analysis_running:
            messagebox.showerror("Please Wait", "An analysis or sync operation is already running.\nPlease wait for it to finish before starting another.")
            return

        self.analysis_running = True # Set flag to indicate an operation is running
        # Display buttons frame and stop button if they exist
        if self.buttons_frame:
            self.buttons_frame.grid()
        if self.stop_button:
            self.stop_button.grid()
            self.stop_button.config(command=self.stop_back_end) # Link stop button to stop function

        # Set up the output console to display sync messages
        self._setup_output_console(clear_content=False) # Do not clear content on sync, append instead
        print("\nStarting data synchronization...\n")

        def sync_work():
            """
            Worker function executed in a separate thread for data synchronization.
            Handles the actual data transfer and updates the GUI upon completion or error.
            """
            try:
                transferData = ta.transferDataUtil()
                # Perform the data synchronization
                status = transferData.syncData(source_path, dest_path)

                if status == 0:
                    # Show success message box on the main thread
                    if self.output_frame:
                        self.output_frame.after(0, lambda: messagebox.showinfo("Sync Complete", "Data synced successfully."))
                    # Hide the stop button upon successful completion
                    if self.stop_button and self.stop_button.winfo_ismapped():
                        self.stop_button.grid_remove()
                else:
                    # Show error message box on the main thread
                    if self.output_frame:
                        self.output_frame.after(0, lambda: messagebox.showerror("Sync Failed", "Data synchronization failed or was interrupted. Check console output."))

                # Update the file list in the relevant dropdown widget if it exists
                dropdown_key = "parameters.fileManagement.fileName"
                dropdown_widget = self.widgets.get(dropdown_key)
                if dropdown_widget and hasattr(dropdown_widget, "_update_file_list"):
                    if self.output_frame:
                        self.output_frame.after(0, dropdown_widget._update_file_list)

            except Exception as e:
                # Print error to console and show error message box on main thread
                print(f" Error during data synchronization (in sync_work): {e}")
                if self.output_frame:
                    self.output_frame.after(0, lambda exc=e: messagebox.showerror("Sync Error", f"An error occurred during sync: {exc}"))
            finally:
                self.analysis_running = False # Reset the running flag in finally block

        # Start the synchronization work in a new thread to keep the GUI responsive
        self.backend_thread = threading.Thread(target=sync_work)
        self.backend_thread.start()

    # === Trigger Analysis ===
    def run_analysis(self):
        """
        Triggers the backend analysis process.
        This function performs input validation, applies selected parameters,
        runs the MBUTY analysis in a separate thread, and manages GUI updates
        for output display and plot handling.
        """
        # Prevent starting a new analysis if one is already running
        if self.analysis_running:
            messagebox.showwarning("Please Wait", "An analysis is already running.\nPlease wait for it to finish before starting another.")
            return
        self.analysis_running = True # Set flag to indicate analysis is running

        # === Validate and gather input values ===
        missing = [] # List to store labels of missing required fields
        selected = {} # Dictionary to store selected parameter values

        # Iterate through all widgets to collect values and check for missing inputs
        for key, widget in self.widgets.items():
            # Skip widgets that are currently hidden due to dependencies
            if hasattr(widget, "should_show") and not widget.should_show():
                continue
            # Skip widgets that do not have a 'get' method (e.g., labels, buttons)
            if not hasattr(widget, "get"):
                continue
            value = widget.get()

            # Check if the value is empty or an empty list
            if value in ("", None, []):
                label = key # Default label if not found in config
                # Find the user-friendly label from the config dictionary
                for section in config.values():
                    if key in section:
                        label = section[key].get("label", key)
                        break
                missing.append(label) # Add to missing list
            else:
                selected[key] = value # Store the selected value

        # If any required fields are missing, display an error message and stop
        if missing:
            messagebox.showerror("Missing Fields", "Please fill in or correct:\n- " + "\n- ".join(missing))
            self.analysis_running = False # Reset running flag
            return

        # === Apply input values to parameters ===
        # Iterate through the selected values and apply them using setter functions
        for key, value in selected.items():
            for section_dict in config.values():
                if key in section_dict:
                    setter = section_dict[key].get("set")
                    if setter:
                        setter(value) # Execute the setter function to update parameter
                    break

        # === Prepare layout and clear output ===
        # Display the buttons frame and the stop button
        if self.buttons_frame:
            self.buttons_frame.grid()
        if self.stop_button:
            self.stop_button.grid()

        # Call the modular function to set up and clear the output console
        self._setup_output_console(clear_content=True)

        # Close any open matplotlib plots from previous runs and clear plot folders (implicitly by MBUTYmain)
        plt.close("All")

        # Initialize the MBUTY backend with current parameters and the main thread queue
        MBUTY_backEnd = MBUTYmain(parameters, runFromGui=True, main_thread_queue = self.main_thread_queue)

        # === Backend work in a separate thread ===
        def backend_work():
            """
            Worker function executed in a separate thread for the MBUTY analysis.
            Handles the execution of the backend analysis and reports status.
            """
            try:
                print("\nRunning analysis with selected parameters...\n")
                MBUTY_backEnd.analysis() # Execute the main analysis function
                print("\n Analysis complete.\n")
                # Display the "Close Plots" button after analysis completion
                if self.close_plots_button:
                    self.close_plots_button.grid()
                # Hide the "Stop" button after analysis completion
                if self.stop_button and self.stop_button.winfo_ismapped():
                    self.stop_button.grid_remove()
            except Exception as e:
                # Check if the exception was a KeyboardInterrupt raised by the stop button
                if isinstance(e, KeyboardInterrupt):
                    print("\nAnalysis was interrupted by user.")
                else:
                    print(f" Error during analysis: {e}")
            finally:
                self.analysis_running = False # Reset the running flag in finally block

        # Start the backend work in a new thread to prevent GUI freezing
        self.backend_thread = threading.Thread(target=backend_work)
        self.backend_thread.start()

    def check_queue(self):
        """
        Periodically checks the `main_thread_queue` for functions that need
        to be executed on the main Tkinter thread. This ensures thread-safe
        updates to the GUI.
        """
        # IMPORTANT: Check if the Tkinter window still exists BEFORE scheduling another 'after' call
        # and before trying to interact with it.
        if not self.win.winfo_exists():
            print("[Main Thread] Tkinter window destroyed. Stopping check_queue.")
            return # Stop scheduling if the window is gone

        try:
            # Try to get a function from the queue without blocking
            callback_function = self.main_thread_queue.get_nowait()
            callback_function() # Execute the function on the main thread
        except queue.Empty:
            pass # No function in the queue yet, simply do nothing
        except Exception as e:
            print(f"[Main Thread] Error processing queue item: {e}")
            # Only show messagebox if the window still exists to prevent errors during shutdown
            if self.win.winfo_exists():
                messagebox.showerror("Error", f"An error occurred: {e}")
        finally:
            # Schedule this method to run again after 100 milliseconds.
            # This ensures continuous checking of the queue as long as the window exists.
            self.win.after(100, self.check_queue)

    def _on_closing(self):
        """
        Handles the graceful closing of the application window.
        It stops any running backend processes, closes all matplotlib plots,
        unbinds mouse wheel events, restores stdout, and destroys the Tkinter window.
        """
        self.stop_back_end() # Stop any active analysis or sync
        plt.close("All") # Close all Matplotlib plots
        unbind_mousewheel(self.win) # Unbind mouse wheel events to prevent resource leaks
        sys.stdout = self.original_stdout # Restore the original stdout
        self.win.destroy() # Destroy the main Tkinter window
        plt.close("all") # Ensure all plots are closed (redundant but safe)

    # === Main GUI Build Method ===
    def _build_window_structure(self):
        """
        Initializes and constructs the entire Tkinter GUI window layout.
        This includes setting up the main window, header with logos and title,
        a divider line, the main content frame (for parameters and output),
        and control buttons (Run, Stop, Close Plots).
        """
        # Create the main Tkinter window
        self.win = tk.Tk()
        self.win.title("MBUTY GUI")
        self.win.geometry("1200x700") # Set initial window size
        # Configure grid weights for the main window to allow expansion
        self.win.grid_rowconfigure(2, weight=1) # Row 2 (main content) expands vertically
        self.win.grid_columnconfigure(0, weight=1) # Column 0 (main content) expands horizontally

        # === Header Frame ===
        header = tk.Frame(self.win)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        # Configure header columns for logo and title placement
        header.grid_columnconfigure(0, weight=1) # Left logo column
        header.grid_columnconfigure(1, weight=2) # Center title column (takes more space)
        header.grid_columnconfigure(2, weight=1) # Right logo column

        # === Left Logo ===
        currentPath = os.path.abspath(os.path.dirname(__file__))
        left_logo_path = os.path.join(currentPath,"GUI", "logos", "DetGlogo.png")
        if os.path.isfile(left_logo_path):
            try:
                img = Image.open(left_logo_path)
                img_resized = img.resize((120, 60)) # Resize image
                left_img = ImageTk.PhotoImage(img_resized, master=header)
                left_logo = tk.Label(header, image=left_img)
                left_logo.image = left_img # Keep a reference to prevent garbage collection
                left_logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=10)
            except Exception as e:
                print(f"Error loading left logo: {e}")
        else:
            print(f"Left logo not found: {left_logo_path}")

        # === Center Title ===
        user_name = os.environ.get('USER', os.environ.get('USERNAME', 'User'))
        self.main_app_title_label = tk.Label(
            header,
            text=f"Ciao {user_name}! Welcome to MBUTY 6.0",
            font=(const.gui_font, const.param_font_size+8, "bold"), # Initial font
            fg="#228B22", # Foreground color (Forest Green)
        )
        self.main_app_title_label.grid(row=0, column=1, sticky="n", pady=(10, 0))
        # Add the main title label to the list of widgets whose font can be dynamically updated
        self.all_font_dynamic_widgets.append({
            "widget": self.main_app_title_label,
            "type": "label",
            "font_offset": 8, # Font size offset relative to base parameter font size
            "style": ("bold",) # Font style
        })
        # === Right Logo ===
        right_logo_path = os.path.join(currentPath,"GUI", "logos", "MBlogo.png")
        if os.path.isfile(right_logo_path):
            try:
                img = Image.open(right_logo_path)
                img_resized = img.resize((120, 60))
                right_img = ImageTk.PhotoImage(img_resized, master=header)
                right_logo = tk.Label(header, image=right_img)
                right_logo.image = right_img
                right_logo.grid(row=0, column=2, rowspan=2, sticky="e", padx=10)
            except Exception as e:
                print(f"Error loading right logo: {e}")
        else:
            print(f"Right logo not found: {right_logo_path}")

        # === Divider Line ===
        divider = ttk.Separator(self.win, orient="horizontal")
        divider.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))

        # Main content container frame (holds parameter UI and output console)
        self.main_frame = tk.Frame(self.win)
        self.main_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        # Configure columns for parameter panel (0) and output panel (1)
        self.main_frame.grid_columnconfigure(0, weight=1) # Parameter panel expands
        self.main_frame.grid_columnconfigure(1, weight=0) # Output panel starts non-expanding
        self.main_frame.grid_rowconfigure(0, weight=1) # Main row expands vertically

        # Run Analysis button
        self.run_button = tk.Button(
            self.main_frame,
            text="Run",
            command=self.run_analysis, # Link to run_analysis method
            font=(const.gui_font, const.param_font_size+3, "bold"),
            bg = const.light_green, # Background color
            width=12 # Minimum visual width
        )
        # Place the run button at the bottom of the first column
        self.run_button.grid(row=3, column=0, pady=[10, 50], sticky="n")
        # Add to dynamic font widgets list
        self.all_font_dynamic_widgets.append({
            "widget": self.run_button,
            "type": "button",
            "font_offset": 3,
            "style": ("bold",)
        })

        # Frame to hold both the Stop and Close Plots buttons
        self.buttons_frame = tk.Frame(self.main_frame)
        self.buttons_frame.grid(row=3, column=1, sticky="nesw")
        self.buttons_frame.grid_remove() # Hidden initially
        self.buttons_frame.grid_columnconfigure(0, weight=1) # Makes column 0 expandable
        self.buttons_frame.grid_columnconfigure(1, weight=1) # Makes column 1 expandable

        # Stop Analysis button (initially hidden, appears to the right of Run button)
        self.stop_button = tk.Button(
            self.buttons_frame,
            text="Stop",
            command=self.stop_back_end, # Link to stop_back_end method
            font=(const.gui_font, const.param_font_size+3, "bold"),
            bg= const.light_red, # Background color
            width=12 # Minimum visual width
        )
        self.stop_button.grid(row=0, column=0, pady=[10, 50], sticky="n")
        self.stop_button.grid_remove() # Hidden initially
        # Add to dynamic font widgets list
        self.all_font_dynamic_widgets.append({
            "widget": self.stop_button,
            "type": "button",
            "font_offset": 3,
            "style": ("bold",)
        })

        # Close Plots button (initially hidden)
        self.close_plots_button = tk.Button(
            self.buttons_frame,
            text="Close Plots",
            # Lambda function to close all plots and then hide the button itself
            command= lambda: (plt.close("all"), self.close_plots_button.grid_remove()),
            font=(const.gui_font, const.param_font_size+3, "bold"),
            bg= "lightBlue", # Background color
            width=12 # Minimum visual width
        )
        self.close_plots_button.grid(row=0, column=1, pady=[10, 50], sticky="n")
        self.close_plots_button.grid_remove() # Hidden initially
        # Add to dynamic font widgets list
        self.all_font_dynamic_widgets.append({
            "widget": self.close_plots_button,
            "type": "button",
            "font_offset": 3,
            "style": ("bold",)
        })

        # Build the actual parameter input UI within the main frame
        self._build_parameter_ui(self.main_frame)

        # Execute all deferred tasks. These tasks typically involve setting up
        # dynamic options or dependencies that require all widgets to be initialized first.
        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear() # Clear the list after execution

    def run(self):
        """Starts the Tkinter event loop, making the GUI interactive."""
        self.win.mainloop()

# === Entry Point ===
if __name__ == "__main__":
    app = MBUTY_GUI_App()
    app.run()