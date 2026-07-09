## -*- coding: utf-8 -*-
"""
This module provides a Tkinter-based GUI for managing detector configuration files.
It allows users to either create new configuration files from a form or load and edit
existing JSON configuration files in a dedicated text editor. The GUI supports
dynamic widget creation based on a configuration dictionary, real-time font size
adjustment, and dynamic options for dropdowns based on file paths.

Created on Mon Jun 23 13:56:56 2025

@author: sheilamonera
"""
# --- GENERIC IMPORTS ---
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
import os
import json

# --- IMPORTS FOR CUSTOM CLASSES ---
from GUI import LineNumberedText
from GUI.gui_utils import create_gui_widget, update_widget_fonts, setup_dynamic_file_options
from GUI import base_constants as const
from lib.libConfigGenerator import generateDefaultDetConfig

# --- Configuration for the Config Creator GUI ---
# Determine the current script's directory for default paths
currentPath = os.path.abspath(os.path.dirname(__file__)) + os.sep

# This dictionary defines all the UI elements and their properties.
# It is used to dynamically build the GUI sections for both editing and creating configurations.
ui_config = {
    "edit_section": {
        "subtitle.edit_existing": {
            "type": "subheading",
            "label": "Edit Existing File"
        },
        "fileManagement.configFilePath": {
            "label": "Config Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, 'config'), # Default directory for config files
            "info": "The directory containing the configuration files."
        },
        "fileManagement.configFileName": {
            "label": "Select Config File",
            "type": "dropdown",
            "default": "", # No default selected file, will be populated dynamically from the directory
            "optionsFromPath": "fileManagement.configFilePath", # Key of the FilePathSearch widget to get the directory from
            "fileTypeFilter": ".json", # Filter for JSON files in the selected directory
            "info": "Select the JSON configuration file to edit."
        },
        "editFileButton": {
            "label": "Load & Edit File",
            "type": "button",
            "command": None # Command will be set programmatically in _build_ui
        },
    },
    "new_file_section": {
        "subtitle.make_new": {
            "type": "subheading",
            "label": "Make a New File"
        },
        "path": { # This is the same as output directory for new files
            "label": "Output Directory",
            "type": "filePath",
            "default": os.path.join(currentPath, 'config'),
            "inputValidation": "localPath",
            "info": "The directory where the new configuration file will be saved. Must be an existing local path."
        },
        "Detector": {
            "label": "Detector Name",
            "type": "entry",
            "info": "Select the name of the detector, the configuration file will be this name + .json"
        },
        "cassettes": {
            "label": "Number of Cassettes",
            "type": "entry",
            "default": "14",
            "inputValidation": "int",
            "info": "Number of cassettes, must be an integer"
        },
        "orientation": {
            "label": "Orientation",
            "type": "bool",
            "options": ["vertical", "horizontal"],
            "default": "vertical",
            "info": "Physical orientation of the detector."
        },
        "operationMode": {
            "label": "Operation Mode",
            "type": "bool",
            "options": ["normal", "clustered"],
            "default": "normal",
            "info": "Operational mode for the detector."
        },
        "createFileButton": {
            "label": "Create New File",
            "type": "button",
            "command": None # Command will be set programmatically in _build_ui
        },
    }
}

class ConfigCreatorFrame(tk.Frame):
    """
    A Tkinter Frame containing the UI elements for both creating and editing
    detector configuration files. This frame manages input widgets,
    a JSON text editor, and the logic for loading, creating, and saving configurations.
    It can be embedded into a `tk.Tk` (root) or `tk.Toplevel` (dialog) window.
    """
    def __init__(self, master_container):
        """
        Initializes the ConfigCreatorFrame.

        Args:
            master_container (tk.Tk or tk.Toplevel): The parent Tkinter window
                                                      that this frame will be packed into.
        """
        super().__init__(master_container)

        self.widgets = {} # Dictionary to store all created widget instances, keyed by their unique identifier.
        self.all_font_dynamic_widgets = [] # List to track widgets whose fonts need dynamic updating based on a slider.

        # Define initial fonts based on base_constants for static elements and base sizes
        self.main_label_font = tkfont.Font(family=const.gui_font, size=const.param_font_size + 4, weight="bold")
        self.section_title_font = tkfont.Font(family=const.gui_font, size=const.param_font_size + 1, weight="bold")
        self.button_font = tkfont.Font(family=const.gui_font, size=const.param_font_size + 2, weight="bold")
        
        self.current_font_size_label = None # Reference to the label displaying the current font size.
        self.font_size_var = tk.IntVar(value=const.param_font_size) # Tkinter variable for the font size slider.

        self.json_file_path = None # Stores the file path of the currently loaded or newly created JSON file.

        # List to hold tasks (functions/lambdas) that need to be run AFTER all widgets are created.
        # This is crucial for setting up dependencies, e.g., dropdowns whose options depend on
        # the value of a FilePathSearch widget created later in the build process.
        self.after_widgets_created_tasks = []

        self._build_ui() # Construct the graphical user interface.
        self.update_font() # Apply initial font settings to all dynamic widgets.
        
        # Set initial layout to show only the parameter forms for editing/creating,
        # hiding the JSON editor until a file is loaded/created.
        self._set_single_panel_layout() 

    def _build_ui(self):
        """
        Constructs the main user interface, including parameter input sections,
        font size control, and the JSON editor.
        """
        # Main container frame for the entire UI (parameter forms on the left, JSON editor on the right).
        self.main_container_frame = tk.Frame(self, padx=15, pady=15)
        self.main_container_frame.pack(fill="both", expand=True)

        # Initial grid configuration for main_container_frame.
        # Row 0 will hold the two main panels.
        self.main_container_frame.grid_rowconfigure(0, weight=1)

        # Frame to hold the parameter input forms (left side of the main container).
        self.params_frame = tk.Frame(self.main_container_frame, padx=15, pady=15, relief="groove", bd=2)
        # Configure columns within params_frame for label and input widgets.
        self.params_frame.grid_columnconfigure(0, minsize=const.label_width, weight=0) # Fixed width for labels
        self.params_frame.grid_columnconfigure(1, minsize=const.FIXED_INPUT_WIDTH, weight=0) # Fixed width for input widgets

        # Main title label for the entire parameter section.
        title_label = tk.Label(self.params_frame, text="Detector Configuration Management", font=self.main_label_font)
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="n")
        # Add this label to the list of widgets whose fonts need dynamic updating.
        self.all_font_dynamic_widgets.append({"widget": title_label, "type": "label", "font_offset": 4, "style": ("bold",)})

        current_row = 1 # Start grid layout from row 1 (after the main title)

        # Font control slider and its associated labels.
        font_control_frame = tk.Frame(self.params_frame, pady=5)
        font_control_frame.grid(row=current_row, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        font_control_frame.grid_columnconfigure(1, weight=1) # The slider column expands.

        font_label = tk.Label(font_control_frame, text="Form Font Size:", font=(const.gui_font, const.param_font_size))
        font_label.grid(row=0, column=0, sticky="w")
        self.all_font_dynamic_widgets.append({"widget": font_label, "type": "label", "font_offset": 0})

        self.current_font_size_label = tk.Label(font_control_frame, text=f"{const.param_font_size}pt", font=(const.gui_font, const.param_font_size))
        self.current_font_size_label.grid(row=0, column=2, sticky="e", padx=(5,0))
        self.all_font_dynamic_widgets.append({"widget": self.current_font_size_label, "type": "label", "font_offset": 0})

        self.font_size_slider = ttk.Scale(
            font_control_frame,
            from_=8, to=24, orient="horizontal",
            variable=self.font_size_var,
            # Update the label text immediately as the slider is dragged
            command=lambda val: self.current_font_size_label.config(text=f"{int(float(val))} pt", font=(const.gui_font, int(float(val))))
        )
        self.font_size_slider.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.font_size_slider.set(const.param_font_size) # Set initial slider position
        # Bind the release event to trigger a full font update for all widgets
        self.font_size_slider.bind("<ButtonRelease-1>", self.update_font)

        current_row += 1 # Increment row for the next UI elements

        # --- Build "Edit Existing File" section based on ui_config ---
        # _create_widgets_from_config_dict will recursively populate self.widgets
        # and self.all_font_dynamic_widgets.
        current_row = self._create_widgets_from_config_dict(self.params_frame, ui_config["edit_section"], start_row=current_row)

        # Set the command for the "Load & Edit File" button.
        # We access the actual `tk.Button` object from the stored `self.widgets` dictionary.
        self.widgets["editFileButton"]["widget"].config(command=self.edit_existing_config)
        
        # --- Build "Make a New File" section based on ui_config ---
        current_row = self._create_widgets_from_config_dict(self.params_frame, ui_config["new_file_section"], start_row=current_row)
        
        # Set the command for the "Create New File" button.
        self.widgets["createFileButton"]["widget"].config(command=self._create_new_config_file)


        # --- JSON Editor Frame Setup (right side of the main container) ---
        self.json_editor_frame = tk.Frame(self.main_container_frame, padx=15, pady=15, relief="groove", bd=2)
        # Configure columns for json_editor_frame: column 0 for title and text area.
        self.json_editor_frame.grid_columnconfigure(0, weight=1) # The main content column expands.
        self.json_editor_frame.grid_rowconfigure(1, weight=1) # The row where the text editor will go expands.

        json_title_label = tk.Label(self.json_editor_frame, text="Edit Configuration File", font=self.main_label_font)
        json_title_label.grid(row=0, column=0, pady=(0, 10), sticky="n")
        self.all_font_dynamic_widgets.append({"widget": json_title_label, "type": "label", "font_offset": 4, "style": ("bold",)})

        # Create the LineNumberedText widget for JSON editing.
        self.json_editor_widget = LineNumberedText(self.json_editor_frame,
                                                 font=(const.gui_font, const.param_font_size))
        self.json_editor_widget.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Get the internal Tkinter Text widget from LineNumberedText for font updates.
        self.json_text_widget = self.json_editor_widget.get_text_widget() 
        self.all_font_dynamic_widgets.append({"widget": self.json_text_widget, "type": "text", "font_offset": 0})

        self.save_json_button = tk.Button(
            self.json_editor_frame,
            text="Save Edits", # Default text, will be updated with actual filename when a file is loaded
            command=self._save_edited_json,
            font=self.button_font,
            bg=const.green,
            padx=10, pady=5
        )
        self.save_json_button.grid(row=2, column=0, pady=(10, 0))
        self.all_font_dynamic_widgets.append({"widget": self.save_json_button, "type": "button", "font_offset": 2, "style": ("bold",)})
        
        # Execute tasks that depend on all widgets being created (e.g., dynamic dropdown options).
        # This loop ensures that dependencies between widgets are correctly set up after the UI is fully built.
        for task in self.after_widgets_created_tasks:
            task()
        self.after_widgets_created_tasks.clear() # Clear the list after execution to free up memory.

    def _create_widgets_from_config_dict(self, parent_frame, config_dict, start_row=0):
        """
        Helper method to iterate through a configuration dictionary and create
        corresponding GUI widgets directly within this function.
        Each widget's properties (type, label, default, etc.) are defined in the `config_dict`.
    
        Args:
            parent_frame (tk.Frame): The Tkinter frame where the widgets will be placed.
            config_dict (dict): A dictionary defining the widgets to create, where keys
                                are widget identifiers and values are dictionaries
                                of widget properties.
            start_row (int): The initial grid row number from which to start placing widgets.
    
        Returns:
            int: The next available grid row number after creating all widgets in the `config_dict`.
        """
        current_row = start_row
        for key, item in config_dict.items():
            # Call the external helper function to create the widget instance and its associated info.
            # 'row_frame_or_widget' is returned by create_gui_widget but not used here
            # since there is no dynamic hiding/showing logic.
            widget_instance, row_frame_or_widget, next_row, widget_font_info = create_gui_widget(
                parent_frame=parent_frame, # Use parent_frame directly here
                key=key,
                item=item,
                row=current_row, # Use current_row for the current item
                existing_widgets_for_dynamic_paths=self.widgets,
            )
            
            # If widget creation failed (e.g., unsupported type), create_gui_widget returns None.
            # In that case, just update the row and continue.
            if widget_instance is None:
                current_row = next_row # Ensure current_row is updated even if widget wasn't created
                continue # Move to the next item in the config_dict
    
            if widget_font_info:
                self.all_font_dynamic_widgets.append(widget_font_info)
            
            self.widgets[key] = {"type": item["type"], "widget": widget_instance}
            
            # Handle dynamic dropdown options that depend on other FilePathSearch widgets.
            if item["type"] == "dropdown":
                dynamic_path_key = item.get("optionsFromPath")
                file_filter = item.get("fileTypeFilter")
                if dynamic_path_key and file_filter:
                    self.after_widgets_created_tasks.append(
                        # lambda to defer execution until all widgets are created
                        # This ensures self.widgets.get(dpk)["widget"] is available
                        lambda w=widget_instance, dpk=dynamic_path_key, ff=file_filter:
                            setup_dynamic_file_options(w, self.widgets.get(dpk)["widget"], ff)
                    )
            
            current_row = next_row # Update current_row for the next iteration
    
        return current_row

    def _set_single_panel_layout(self):
        """
        Configures the `main_container_frame` to display only the `params_frame`
        (the left-hand side form), hiding the JSON editor. This is the initial view 
        of the application.
        """
        self.json_editor_frame.grid_remove() # Hide the JSON editor frame.

        # Configure column weights for `main_container_frame`:
        # Column 0 (for params_frame) gets all horizontal space, Column 1 (where json_editor was) gets no weight.
        self.main_container_frame.grid_columnconfigure(0, weight=1)
        self.main_container_frame.grid_columnconfigure(1, weight=0)

        # Place the `params_frame` in column 0, stretching vertically.
        self.params_frame.grid(row=0, column=0, sticky="ns", padx=(0,0)) 

        # Force Tkinter to update its geometry calculations immediately.
        self.update_idletasks()
        # Allow the master window to resize itself to fit the new single-panel layout.
        self.master.geometry("") 

    def _set_dual_panel_layout(self):
        """
        Configures the `main_container_frame` to display both the `params_frame`
        (left-hand side form) and the `json_editor_frame` (right-hand side editor).
        This view is activated when a file is loaded for editing or created.
        """
        # Adjust column weights: `params_frame`'s column (0) has fixed width,
        # `json_editor_frame`'s column (1) expands to fill available space.
        self.main_container_frame.grid_columnconfigure(0, weight=0)
        self.main_container_frame.grid_columnconfigure(1, weight=1)

        # Place the `params_frame` in column 0.
        self.params_frame.grid(row=0, column=0, sticky="ns", padx=(0,10)) 
        
        # Place the `json_editor_frame` in column 1, stretching to fill its cell.
        self.json_editor_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 0)) 

        # Force Tkinter to update its geometry calculations.
        self.update_idletasks()
        # Allow the master window to resize itself to fit the new dual-panel layout.
        self.master.geometry("") 

    def update_font(self, event=None):
        """
        Updates the font size and style for all dynamically sized widgets in the GUI.
        It reconfigures fonts for specific UI elements and then iterates through
        the `self.all_font_dynamic_widgets` list to update other widgets.
        """
        new_size = int(self.font_size_var.get())
        if const.param_font_size == new_size:
            return
        
        const.param_font_size = new_size # Update the global constant
        # Update fonts for main title, section titles, and buttons based on new base size.
        self.main_label_font.config(size=const.param_font_size + 4)
        self.section_title_font.config(size=const.param_font_size + 1)
        self.button_font.config(size=const.param_font_size + 2)
    
        # Update the font size label in real-time.
        if self.current_font_size_label and self.current_font_size_label.winfo_exists():
            self.current_font_size_label.config(text=f"{const.param_font_size}pt",
                                                 font=(const.gui_font, const.param_font_size))
    
        # Call the external helper function to update fonts for all registered dynamic widgets.
        update_widget_fonts(self.all_font_dynamic_widgets, const.param_font_size, const.gui_font)
    
        # Call update_idletasks() only once, after ALL font updates are done for this GUI,
        # to ensure efficient rendering.
        self.master.update_idletasks()
        self.master.geometry("") # Recalculate window size if widget sizes have changed.
        
    

    def _get_input_values_from_section(self, section_config):
        """
        Helper method to gather input values from widgets defined within a
        specific section of the UI configuration. This method relies on the
        individual widgets to perform their own internal validation and return
        an empty string, None, or an empty list if the input is invalid or missing.
        
        If missing/invalid fields are found, a Tkinter messagebox with a standard
        title ("Missing Fields") is displayed. The function then returns `None`
        to signal that the data collection failed and processing should stop.
    
        Parameters:
            section_config (dict): A dictionary representing a section of the `ui_config`,
                                   containing keys and properties of input widgets.
    
        Returns:
            dict or None: A dictionary where keys are widget identifiers
                          and values are the gathered input values, if all fields
                          are valid and present. Validated values are expected
                          directly from the widget's `get()` method.
                          Returns `None` if a messagebox was displayed due to
                          missing/invalid fields, indicating that processing should stop.
        """
        missing_fields_labels = [] # Renamed to clarify it's for display
        data = {}
    
        for key, item in section_config.items():
            if item["type"] in ["subheading", "button"]:
                continue
    
            widget_info = self.widgets.get(key)
            if not widget_info or not hasattr(widget_info["widget"], "get"):
                continue
    
            widget_instance = widget_info["widget"]
            value = widget_instance.get()
            param_label = item['label']
    
            if value in ("", None, []):
                missing_fields_labels.append(f"'{param_label}'")
            else:
                data[key] = value
    
        if missing_fields_labels:
            messagebox.showerror(
                "Missing Fields",
                "Please fill in or correct the following fields:\n- " + "\n- ".join(missing_fields_labels)
            )
            return None # Signal failure by returning None
        else:
            return data # Return the collected data if successful

    def _load_config_for_editing(self, file_path):
        """
        Loads the specified JSON configuration file into the JSON text editor.
        It handles file existence, reads content, attempts to pretty-print JSON,
        and updates the save button's text.

        Parameters:
            file_path (str): The complete file path of the JSON configuration file to load.
        """
        # Ensure the file exists before attempting to load.
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The file '{file_path}' does not exist.")
            return

        self.json_file_path = file_path # Store the path of the currently loaded file.

        try:
            with open(self.json_file_path, 'r') as f:
                json_content = f.read()

            self.json_text_widget.delete("1.0", tk.END) # Clear any existing content in the editor.
            try:
                # Attempt to parse the content as JSON and then pretty-print it.
                parsed_json = json.loads(json_content)
                pretty_json = json.dumps(parsed_json, indent=4)
                self.json_text_widget.insert("1.0", pretty_json)
                self.json_text_widget.config(state=tk.NORMAL) # Ensure the editor is editable.
            except json.JSONDecodeError:
                # If the file content is not valid JSON, insert it as plain text and show a warning.
                self.json_text_widget.insert("1.0", json_content)
                self.json_text_widget.config(state=tk.NORMAL) # Ensure the editor is editable.
                messagebox.showwarning("Warning", "The selected file does not contain valid JSON. Displaying as plain text.")
            
            # Set focus to the text editor and place the cursor at the beginning.
            self.json_text_widget.focus_set()
            self.json_text_widget.mark_set(tk.INSERT, "1.0")

            # Update the text of the Save button to reflect the loaded filename.
            filename = os.path.basename(self.json_file_path)
            self.save_json_button.config(text=f"Save Edits to {filename}")

            # Switch the layout to show both the form and the JSON editor.
            self._set_dual_panel_layout() 

        except Exception as e:
            # Catch any other exceptions during file loading and display an error message.
            messagebox.showerror("Error", f"Failed to load file for editing: {e}")

    def edit_existing_config(self):
        """
        Gathers the required input values (config directory and file name)
        from the "Edit Existing File" section of the form and
        then calls `_load_config_for_editing` to display the selected file.
        This function is typically bound to the "Load & Edit File" button.
        """
        # Get data from the "edit_section" as defined in ui_config.
        edit_section_data = self._get_input_values_from_section(ui_config["edit_section"])
        
        # Check if the data collection was aborted (due to missing values popup in _get_input_values_from_section)
        if edit_section_data is None:
            return

        # Extract the selected directory and file name.
        selected_directory = edit_section_data["fileManagement.configFilePath"]
        selected_file_name = edit_section_data["fileManagement.configFileName"]

        # Construct the full file path and load the config.
        full_file_path = os.path.join(selected_directory, selected_file_name)
        self._load_config_for_editing(full_file_path)
        # Show a success message to the user.
        messagebox.showinfo("Success", f"File '{selected_file_name}' loaded successfully for editing.")

    def _create_new_config_file(self):
        """
        Generates a new JSON configuration file based on the inputs provided
        in the "Make a New File" section of the form. It handles input validation,
        file existence checks (with overwrite prompt), and calls the backend
        `generateDefaultDetConfig` function.
        """
        # Get values from the "new_file_section" as defined in ui_config.
        new_file_data = self._get_input_values_from_section(ui_config["new_file_section"])

        # Check if the data collection was aborted (due to missing values popup in _get_input_values_from_section)
        if new_file_data is None:
            return
        
        # Extract necessary data for opening file and updating the button and popups with correct paths and file names
        output_directory = new_file_data["path"]
        detector_name = new_file_data["Detector"]
        file_name = f"{detector_name}.json"
        file_path = os.path.join(output_directory, file_name)

        # --- Check if file exists and ask user for overwrite confirmation ---
        overwrite = False
        if os.path.exists(file_path):
            result = messagebox.askquestion(
                "File Exists",
                f"The file '{file_name}' already exists.\n\nDo you want to overwrite it?",
                icon='warning'
            )
            if result == 'no':
                messagebox.showinfo("Choose New Name", "Please choose a different detector name and try again.")
                return
            overwrite = True # Set overwrite flag if user confirms

        try:
            # Create a copy of `new_file_data` to pass to the backend function.
            config_args_for_backend = new_file_data.copy()
            # Add the 'overwrite' flag which is determined by the user's choice.
            config_args_for_backend["overwrite"] = overwrite
            # Call the backend function to generate the configuration file.
            generated_file_path = generateDefaultDetConfig(**config_args_for_backend)
            
            if generated_file_path is None:
                # If the backend function returns None, it indicates a failure.
                messagebox.showerror("Error", "Config file generation failed (check console for backend errors).")
                return
            
            # Load the newly created file into the JSON editor for immediate viewing/editing.
            self._load_config_for_editing(generated_file_path)
            
            messagebox.showinfo("Success", f"Configuration generated successfully in '{output_directory}'. You can now edit it in the panel.")
            
        except Exception as e:
            # Catch any exceptions during file creation and display an error message.
            messagebox.showerror("Error", f"Failed to create new config file: {e}")

    def _save_edited_json(self):
        """
        Saves the content currently in the JSON text editor back to the
        `json_file_path` that was previously loaded or generated.
        It validates the content as JSON before saving.
        """
        if not self.json_file_path:
            # If no file is currently associated with the editor, warn the user.
            messagebox.showwarning("No File", "No JSON file has been generated or loaded yet to save.")
            return

        # Get the current content from the text editor.
        edited_content = self.json_text_widget.get("1.0", tk.END).strip()

        try:
            # Attempt to parse the content as JSON to validate its format.
            parsed_json = json.loads(edited_content)
            with open(self.json_file_path, 'w') as f:
                # Save the parsed (and implicitly validated) JSON content, pretty-printed.
                json.dump(parsed_json, f, indent=4)
            messagebox.showinfo("Save Success", f"JSON configuration saved successfully to '{self.json_file_path}'!")
        except json.JSONDecodeError as e:
            # If JSON is invalid, show an error with details.
            messagebox.showerror("JSON Error", f"Invalid JSON format. Please correct the syntax before saving:\n{e}")
        except Exception as e:
            # Catch any other file I/O or saving errors.
            messagebox.showerror("Save Error", f"An error occurred while saving the JSON file: {e}")
    

if __name__ == "__main__":
    try:
        # Create the main Tkinter root window.
        root = tk.Tk()
        root.title("Main Application Window (Config Creator)") 
        
        # Set the initial size and position of the main window to be centered on the screen.
        window_width = 1200
        window_height = 650
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        root.resizable(True, True) # Allow the window to be resized by the user.

        # Create an instance of the ConfigCreatorFrame and pack it to fill the root window.
        config_frame_instance = ConfigCreatorFrame(root)
        config_frame_instance.pack(fill="both", expand=True) 

        # Set a protocol handler for when the window is closed (e.g., clicking the 'X' button).
        # This ensures proper cleanup by destroying the root window.
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        
        # Start the Tkinter event loop. This keeps the application running and
        # responsive to user interactions.
        root.mainloop()

    except Exception as e:
        # Catch and print any unhandled exceptions that occur during application startup
        # or within the main event loop, providing a traceback for debugging.
        print(f"\n!!! An unhandled error occurred during application startup: {e}")
        import traceback
        traceback.print_exc()