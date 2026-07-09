# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 11:51:22 2025

@author: sheilamonera
"""
"""
GUI Configuration File for MBUTY Detector Interface
---------------------------------------------------

This module defines a centralized configuration dictionary `config` that specifies all user-configurable parameters
exposed via the GUI. These parameters are grouped by section (e.g. 'static', 'file_management', 'analysis', etc.),
and each parameter entry follows a structured schema:

Each parameter item (within a section) supports the following fields:

- `label` (str): The user-visible label for the GUI widget.

- `type` (str): The type of widget. Must be one of:
    - 'entry'         : text box entry that can be validated by one of the inputValidation types below.
    - 'dropdown'      : dropdown selection menu
    - 'multiSelect'   : multi-select dropdown
    - 'radio'         : vertical radio button group
    - 'bool'          : horizontal toggle between two options (True/False or custom)
    - 'filePath'      : an entry with file path autocomplete features
    - 'range'         : validated numeric range input (e.g., [min, max]). 
                        Can be combined with inputValidation of 'int' or 'float'. If no inputValidation type specified, defaults to 'float'
    - 'subheading'    : only other parameter acceptable with 'type'='subheading' is 'label' which is the subheading text to be displayed
    - 'button'        : basic button needs a 'label' and 'command' to be executed

- `options` (list, optional): Static list of selectable values. Required for 'radio', and 'bool'. Can be used in 'dropdown' or 'multiselect'
    - If dynamic loading is used (see `oplotionsFromPath`), this can be set to an empty list or omitted.

- `default` (any, optional): Default value used to initialize the widget.
    - Type should match the expected input type: str for dropdowns, list[str] for multiSelect, int/float for entries, etc.

- `info` (str, optional): Description text shown in a tooltip for that setting.

- `inputValidation` (str, optional): Validation rule (used only for 'entry' and 'range' widgets).
  Must be one of:

    - 'int'         : Accepts integer numbers (e.g., 42, -5)
    - 'float'       : Accepts decimal numbers (e.g., 3.14, -0.01)
    - 'scientific'  : Accepts scientific notation (e.g., 1e-3, -2.5E+4). Matches regex:
                      r'[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)([eE][-+]?\\d+)?'
    - 'remotepath'   : Validates remote-style SSH paths (e.g., user@192.168.1.1:/path/to/data)
                       Matches regex:
                       r'^[\\w.-]+@[\\d.]+:.*'
    - 'host:port'    : Validates a hostname and port pair (e.g., localhost:8080)
                       - Host must match r'^[\\w\\.-]+$'
                       - Port must be an integer between 1 and 65535
    - 'fileNumbers'  : Accepts file number patterns (e.g., "1-5", "1,3,7", "1-10,12,15")
                       Parsed via custom logic that supports:
                         - comma-separated values
                         - numeric ranges like "5-10"
                         - mixed formats ("1-3,5,7-9")
                       Invalid formats or malformed ranges are rejected
    
    Notes:
        - If omitted, validation defaults to 'any' (no strict checking).
        - Custom validation can be extended in the widget logic if needed.
        

- `range` (tuple[int|float, int|float], optional): Applicable only to 'entry' widgets with numeric inputValidation.

- `dependsOn` (optional): Conditionally show this widget only when certain conditions are met.
    - This field defines a **logic tree** for conditional visibility using key-value checks combined with `and` / `or` logic.
        
    This field supports both simple and complex conditional logic, such as:
        
        1. **Simple condition**  
           Show this widget only if another widget has a specific value, tuple of the form:
           ("other_parameter_key", "required_value")
           ("other_parameter_key", ["allowed_value1", "allowed_value2", ...])
        
        2. **Logic tree (nested and / or structure)** :
            Define more complicated dependecies using an and or tree logic,
            Example (show if acqMode is "off" OR "pcap-local" OR (acqMode is "pcap-sync" AND selectDifferentDataPath is True)):
                
           {
                "or": [
                    ("parameters.acqMode", ["off", "pcap-local"]),
                    {
                        "and": [
                            ("parameters.acqMode", "pcap-sync"),
                            ("selectDifferentDataPath", True)
                        ]
                    }
                ]
            }



- `optionsFromPath` (str, optional): For 'dropdown' and 'multiSelect' widgets only.
    Indicates that this widget's options should be dynamically loaded from the folder path given by another widget.
    The value should be the config key of the controlling path entry (e.g., "parameters.fileManagement.filePath").

- `dynamicOptions` (callable, optional): For 'dropdown' and 'multiSelect' widgets only.
    A function that takes the `widgets` dictionary as an argument and returns the correct path to generate the options.
    This allows for more complex dynamic generation of options based on multiple other widget states.

- `watchKeys` (list[str], optional): Used in conjunction with `dynamicOptions`.
    A list of other configuration keys. When the value of any of these watched keys changes in the GUI,
    the `dynamicOptions` function for *this* widget will be re-evaluated to update its options.

- `mustExist` (bool, optional): Only relevant for 'type'= 'filePath'. If set to `True`, it will only accept existing paths.
    If set to `False`, it will check if the path exists and if not, it will prompt the user if they want to create it.
    If not set, the default will be `True`.

- `fileTypeFilter` (str, optional): Used with `optionsFromPath` or `dynamicOptions` to filter files by extension (e.g., ".json", ".pcapng").
    Must be used together with `optionsFromPath` or `dynamicOptions`.

- `set` (callable): A lambda function that takes the selected value and sets it in the underlying `parameters` object.

- 'command' : only aplicable to the 'type'='button' widgets - can be in form of a lamda function or can call another function 
    
Notes:
- Providing extra keys not used by a widget type is harmless and simply ignored.
- Omitting required fields (like `options` for static dropdowns) will result in incomplete widgets (e.g. empty list).
- If `optionsFromPath` or 'dynamicOptions' is provided, the `options` field is ignored after initialization and dynamically populated at runtime.
- By default all of the fields are required to have some input before the back end can run, if there is a field which is optional,
    control this using a radio button and 'dependsOn' logic to turn this field on/off or set a default value
"""

import os
import sys
import subprocess
from tkinter import messagebox

# Fix import path to allow access to lib from GUI folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lib import libParameters as para
# Set current path
currentPath = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) 
parameters = para.parameters(currentPath)

def dataFileOptions(widgets):
    try:
        acq_mode = widgets.get("parameters.acqMode").get()
        use_alt = widgets.get("selectDifferentDataPath").get()
        file_path = widgets.get("parameters.fileManagement.filePath").get()
        dest_path = widgets.get("parameters.fileManagement.destPath").get()
        folder = dest_path if acq_mode == "pcap-sync" and not use_alt else file_path
        return (folder, ".pcapng")
    except Exception:
        return []


def set_ThW(val):
    parameters.dataReduction.softThArray.ThW[:, :] = val

def set_ThS(val):
    parameters.dataReduction.softThArray.ThS[:, :] = val
    
def open_config_creator_standalone():
    """
    Launches configGenGUI.py as a completely separate, standalone Python process.
    This will create a new, independent window for the Config Creator.
    """
    python_executable = sys.executable
    config_gui_path = os.path.join(currentPath, 'MBUTYconfigGen_GUI.py')

    # Verify that the script exists before trying to run it
    if not os.path.exists(config_gui_path):
        messagebox.showerror("Error", f"Config Creator script not found at: {config_gui_path}")
        return

    try:
        subprocess.Popen([python_executable, config_gui_path])#,
                         # stdout=subprocess.DEVNULL, # Suppress stdout
                         # stderr=subprocess.DEVNULL) # Suppress stderr

    except FileNotFoundError:
        messagebox.showerror("Error", "Python executable not found. Make sure Python is installed and in your system's PATH.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Config Creator:\n{e}")
        
# Define configuration structure
config = {
    "static": {
        "subtitle.acqMode": {
            "type": "subheading",
            "label": "Acquisition mode settings"
        },
        "parameters.acqMode": {
            "label": "Acquisition Mode",
            "type": "radio",
            "options": ["off", "pcap-sync", "pcap-local", "pcap-local-overwrite", "kafka"],
            "default": "off",
            "set": lambda val: setattr(parameters, 'acqMode', val)

        },
        "parameters.dumpSettings.interface": {
            "label": "Network Interface",
            "type": "entry",
            "default": "ens2np0",
            "dependsOn": ("parameters.acqMode", ["pcap-local", "pcap-local-overwrite"]),
            "info": "Used for acqMode = pcap-local, pcap-local-overwrite, or kafka",
            "set": lambda val: setattr(parameters.dumpSettings, 'interface', val)
        },
        "parameters.dumpSettings.typeOfCapture": {
            "label": "Type of Capture",
            "type": "radio",
            "options": ["packets", "duration", "filesize"],
            "default": "packets",
            "dependsOn": ("parameters.acqMode", ["pcap-local", "pcap-local-overwrite"]),
            "info": "Choose whether to capture by number of packets, duration (in seconds) or filesize (in kbytes)",
            "set": lambda val: setattr(parameters.dumpSettings, 'typeOfCapture', val)
        },
        "parameters.dumpSettings.quantity": {
            "label": "Quantity",
            "type": "entry",
            "inputValidation": "int",
            "default": 100,
            "dependsOn": ("parameters.acqMode", ["pcap-local", "pcap-local-overwrite"]),
            "info": "Number of packets, seconds (duration) or kbytes (filesize) to capture based on 'typeOfCapture'",
            "set": lambda val: setattr(parameters.dumpSettings, 'quantity', val)
        },
        "parameters.fileManagement.fileNameSave": {
            "label": "Save File Name",
            "type": "entry",
            "default": "test",
            "dependsOn": ("parameters.acqMode", "pcap-local"),
            "info": "Name of the file to save captured data",
            "set": lambda val: setattr(parameters.fileManagement, 'fileNameSave', val)
        },
        "parameters.kafkaSettings.broker": {
            "label": "Kafka Broker",
            "type": "entry",
            "inputValidation": "host:port",
            "default": "127.0.0.1:9092",
            "dependsOn": ("parameters.acqMode", "kafka"),
            "info": "Broker address in the format host:port. Relevant for acqMode = kafka",
            "set": lambda val: setattr(parameters.kafkaSettings, 'broker', val)
        },
        "parameters.kafkaSettings.topic": {
            "label": "Kafka Topic",
            "type": "entry",
            "default": "freia_debug",
            "dependsOn": ("parameters.acqMode", "kafka"),
            "set": lambda val: setattr(parameters.kafkaSettings, 'topic', val)
        },
        "parameters.kafkaSettings.numOfPackets": {
            "label": "Number of Packets",
            "type": "entry",
            "inputValidation": "int",
            "default": 100,
            "info": "Total number of packets to dump (used with acqMode = kafka)",
            "dependsOn": ("parameters.acqMode", "kafka"),
            "set": lambda val: setattr(parameters.kafkaSettings, 'numOfPackets', val)
        },
        "parameters.fileManagement.sourcePath": { 
            "label": "Source Path",
            "type": "entry",
            "inputValidation": "remotePath",
            "default": "essdaq@172.30.244.50:~/pcaps/",
            "info": "Remote source path to rsync from. Relevant for acqMode = pcap-sync",
            "dependsOn": ("parameters.acqMode", "pcap-sync"),
            "set": lambda val: setattr(parameters.fileManagement, 'sourcePath', val)
        },
        "parameters.fileManagement.destPath": {
            "label": "Destination Path",
            "type": "filePath",
            # "default": os.path.join(currentPath, 'data'),
            "default": '',
            "mustExist": False,
            "info": "Local destination path to rsync to. Relevant for acqMode = pcap-sync",
            "dependsOn": ("parameters.acqMode", "pcap-sync"),
            "set": lambda val: (
                setattr(parameters.fileManagement, 'destPath', val),
                # We also set filePath here, if the user toggles the selectDifferentDataPath button,
                # the filePath widget will become visible and this path will be overwritten below with the new filePath
                setattr(parameters.fileManagement, 'filePath', val)
            )
        },
        "selectDifferentDataPath": {
            "label": "Select Different Data Path",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "By default the data path = the destination path for pcap-sync if you want to get data from a different path select 'True' and enter path",
            "dependsOn": ("parameters.acqMode", "pcap-sync"),
        },
        "parameters.fileManagement.filePath": { ######### does not create folder
            "label": "Data Folder Path",
            "type": "filePath",
            "mustExist": True,
            "default": os.path.join(currentPath, 'data'),
            # "default": '/opt/mb_tools/pcaps/',
            "info": "Path to the folder containing data files. Relevant for acqMode = off, pcap-sync, and pcap-local",
            "dependsOn": {
                "or": [
                    ("parameters.acqMode", "off"),
                    {
                        "and": [
                            ("parameters.acqMode", "pcap-sync"),
                            ("selectDifferentDataPath", True)
                        ]
                    }
                ]
            },
            "set": lambda val: setattr(parameters.fileManagement, 'filePath', val)
        },
        "parameters.fileManagement.filePath2": { #creates folder if does not exist
            "label": "Data Folder Path",
            "type": "filePath",
            "mustExist": False,
            # "default": os.path.join(currentPath, 'data'),
            "default": '/opt/mb_tools/pcaps/',
            "info": "Path to the folder containing data files. Relevant for acqMode = off, pcap-sync, and pcap-local",
            "dependsOn": ("parameters.acqMode","pcap-local"),
            "set": lambda val: setattr(parameters.fileManagement, 'filePath', val)
        },
        "syncDataButton": {
            "label": "Sync Data",
            "type": "button",
            "dependsOn": ("parameters.acqMode", "pcap-sync"),
            "command": None  # Will be injected after widgets are created
        },
        "parameters.fileManagement.openMode": {
            "label": "File Open Mode",
            "type": "radio",
            "options": ["fileName", "latest", "secondLast", "wholeFolder", "sequence"],
            "default": "fileName",
            "dependsOn": ("parameters.acqMode", ["off", "pcap-sync"]),
            "info": "Choose how files should be selected and loaded: 'window' opens file browser, 'fileName' uses preset file, 'latest' and 'secondLast' load most recent files, 'wholeFolder' analyzes all files, 'sequence' uses fileSerials.",
            "set": lambda val: setattr(parameters.fileManagement, 'openMode', val)
        },
        "parameters.fileManagement.fileName": {
            "label": "Data File Name(s)",
            "type": "multiSelect",
            "default": ["ESSmask2023.pcapng"], 
            "dynamicOptions": dataFileOptions,
            "watchKeys": [
                "parameters.acqMode",
                "selectDifferentDataPath",
                "parameters.fileManagement.filePath",
                "parameters.fileManagement.destPath"
            ],
            "info": "List of file(s) to load from the resolved folder.",
            "dependsOn":  {
                "and": [("parameters.acqMode", ["off", "pcap-sync"]),
                        ("parameters.fileManagement.openMode", ["fileName", "sequence"])
                        ]
                },
            "set": lambda val: setattr(parameters.fileManagement, 'fileName', val)
        },
        "parameters.fileManagement.fileSerials": { 
            "label": "File Serials",
            "type": "entry",
            "default": "0,1,2,65,68-73",
            "inputValidation": "fileNumbers",
            "info": "Used when openMode is 'sequence' to indicate file serial numbers of files to be opened. Accepts comma separated lists and ranges e.g 5-10,15,17 ",  
            "dependsOn": ("parameters.fileManagement.openMode", "sequence"),
            "set": lambda val: setattr(parameters.fileManagement, 'fileSerials', val)
        },
        "parameters.fileManagement.pathToTshark": {
            "label": "Path to Tshark",
            "type": "filePath",
            "default": "/usr/sbin/",
            "dependsOn": ("parameters.acqMode", ["pcap-local", "pcap-local-overwrite"]),
            "info": "Filesystem path to the Tshark binary. Used to convert PCAP to PCAPNG if needed.",
            "set": lambda val: setattr(parameters.fileManagement, 'pathToTshark', val)
        },
        "parameters.fileManagement.pcapLoadingMethod": {
            "label": "PCAP Loading Method",
            "type": "bool",
            "options": ["allocate", "quick"],
            "default": "allocate",
            "dependsOn": ("parameters.acqMode", ["off", "pcap-sync", "pcap-local", "pcap-local-overwrite"]),
            "info": "Controls how memory is allocated when loading PCAP files. 'allocate' is more rigorous, \n'quick' estimates the memory and is faster.",
            "set": lambda val: setattr(parameters.fileManagement, 'pcapLoadingMethod', val)
        },
        "parameters.VMMsettings.sortReadoutsByTimeStampsONOFF": {
            "label": "Sort Readouts by Time Stamps",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "Sorting readouts by time stamp, if OFF they are as in RMM stream",
            "set": lambda val: setattr(parameters.VMMsettings, 'sortReadoutsByTimeStampsONOFF', val)
        },
        "parameters.VMMsettings.timeResolutionType": {
            "label": "Time Resolution Type",
            "type": "bool",
            "options": ["fine", "coarse"],
            "default": "fine",
            "info": "Time stamp is time HI + time LO or if fine corrected with TDC ",
            "set": lambda val: setattr(parameters.VMMsettings, 'timeResolutionType', val)
        },
        "subtitle.bareReadouts": {
            "type": "subheading",
            "label": "Readouts"
        },
        "parameters.plotting.bareReadoutsCalculation": {
            "label": "Stop at readouts",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "Disables clustering and mapping for speed. Stops analysis at raw readouts.",
            "set": lambda val: setattr(parameters.plotting, 'bareReadoutsCalculation', val)
        },
        "subtitle.config": {
            "type": "subheading",
            "label": "Detector config"
        },
        
        "makeConfigFileButton": {
            "label": "Create or modify config file",
            "type": "button",
            "command": open_config_creator_standalone
        },
        "parameters.fileManagement.configFilePath": {
            "label": "Enter path to config file",
            "type": "filePath",
            "default": os.path.join(currentPath, 'config'),
            "set": lambda val: setattr(parameters.fileManagement,'configFilePath', val)
        },
        "parameters.fileManagement.configFileName": {
            "label": "Select Config File",
            "type": "dropdown",
            "default": "AMOR.json",
            "optionsFromPath": "parameters.fileManagement.configFilePath",
            "fileTypeFilter": ".json",
            "info": "Must select config file",
            "set": lambda val: setattr(parameters.fileManagement,'configFileName', val)

        }
    },
    "clustering": {
        "parameters.dataReduction.timeWindow": {
            "label": "Time Window for clustering (s)",
            "type": "entry",
            "inputValidation": "scientific",
            "default": "0.5e-6",
            "info": "Time window to search for clusters.\nThis is the maximum time allowed between events in a cluster.\nHalf the value is used as the recursive threshold between adjacent hits.",
            "set": lambda val: setattr(parameters.dataReduction, 'timeWindow', val)
        },
        "parameters.plotting.positionReconstruction": {
            "label": "Position Reconstruction Method",
            "type": "radio",
            "options": ["W.max-S.max", "W.cog-S.cog", "W.max-S.cog"],
            "default": "W.max-S.cog",
            "info": "'W.max-S.max' is max max,  'W.cog-S.cog' is CoG CoG, 'W.max-S.cog' is wires max and strips CoG ",
            "set": lambda val: setattr(parameters.plotting, 'positionReconstruction', val)
        },
    },
    "threshold": {
        "parameters.dataReduction.softThresholdType": {
            "label": "Soft Threshold Type",
            "type": "radio",
            "options": ["off", "fromFile", "userDefined"],
            "default": "off",
            "info": "Select how to define soft thresholds: off, from file, or user-defined.",
            "set": lambda val: (
                    setattr(parameters.dataReduction, 'softThresholdType', val),
                    parameters.dataReduction.createThArrays(parameters)
                    if val == "userDefined" else None
                )[-1]
        },
        "parameters.fileManagement.thresholdFilePath": {
            "label": "Threshold File Path",
            "type": "filePath",
            "default": os.path.join(parameters.fileManagement.currentPath, 'config'),
            "dependsOn": ("parameters.dataReduction.softThresholdType","fromFile"),
            "info": "Path to the threshold file folder.",
            "set": lambda val: setattr(parameters.fileManagement, 'thresholdFilePath', val)
        },
        "parameters.fileManagement.thresholdFileName": {
            "label": "Threshold File Name",
            "type": "dropdown",
            "optionsFromPath": "parameters.fileManagement.thresholdFilePath",
            "fileTypeFilter": ".xlsx",
            "default": "MB300L_thresholds.xlsx", 
            "dependsOn": ("parameters.dataReduction.softThresholdType","fromFile"),
            "info": "Name of the Excel threshold file.",
            "set": lambda val: setattr(parameters.fileManagement, 'thresholdFileName', val)
        },
        "parameters.dataReduction.softThArray.ThW[:,:]": {
            "label": "Soft Threshold W",
            "type": "entry",
            "inputValidation": "float",
            "default": 200,
            "dependsOn": ("parameters.dataReduction.softThresholdType", "userDefined"),
            "set": set_ThW
        },
        "parameters.dataReduction.softThArray.ThS[:,:]": {
            "label": "Soft Threshold S",
            "type": "entry",
            "inputValidation": "float",
            "default": 100,
            "dependsOn": ("parameters.dataReduction.softThresholdType", "userDefined"),
            "set": set_ThS
        }
    }, 
    "calibration": {
        "parameters.dataReduction.calibrateVMM_ADC_ONOFF": {
            "label": "Calibrate VMM ADC",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "Calibration VMM ADC",
            "set": lambda val: setattr(parameters.dataReduction, 'calibrateVMM_ADC_ONOFF', val)
        },
        "parameters.fileManagement.calibFilePath": {
            "label": "Calibration File Path",
            "type": "filePath",
            "default": os.path.join(parameters.fileManagement.currentPath,'calib'),
            "dependsOn": ("parameters.dataReduction.calibrateVMM_ADC_ONOFF", True),
            "info": "Path to the calibration file folder.",
            "set": lambda val: setattr(parameters.fileManagement, 'calibFilePath', val)
        },
        "parameters.fileManagement.calibFileName": {
            "label": "Calibration File Name",
            "type": "dropdown",
            "optionsFromPath": "parameters.fileManagement.calibFilePath",
            "fileTypeFilter": ".json",
            "default": "AMOR_calib_20231111002842.json",
            "dependsOn": ("parameters.dataReduction.calibrateVMM_ADC_ONOFF", True),
            "info": "Name of the calibration file.",
            "set": lambda val: setattr(parameters.fileManagement, 'calibFileName', val)
        }
    },
    "pulse_height": {
        "parameters.pulseHeigthSpect.plotPHS": {
            "label": "Plot PHS",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "info": "Enable or disable pulse height spectra per channel and globally.",
            "set": lambda val: setattr(parameters.pulseHeigthSpect, 'plotPHS', val)
        },
  
        "parameters.pulseHeigthSpect.plotPHScorrelation": {
            "label": "Plot PHS Correlation (Wires vs Strips)",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.pulseHeigthSpect, 'plotPHScorrelation', val)
        },
        
        "parameters.pulseHeigthSpect.plotPHSlog": {
            "label": "PHS Log Scale",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "dependsOn":  {
                    "or": [
                    ("parameters.pulseHeigthSpect.plotPHS", True),
                    ("parameters.pulseHeigthSpect.plotPHScorrelation", True)
                    ]},
            "info": "If True, plot pulse height spectra using a logarithmic scale.",
            "set": lambda val: setattr(parameters.pulseHeigthSpect, 'plotPHSlog', val)
        },
        "parameters.pulseHeigthSpect.energyBins": {
            "label": "Energy Bins",
            "type": "entry",
            "default": 128,
            "inputValidation": "int",
            "dependsOn":  {
                    "or": [
                    ("parameters.pulseHeigthSpect.plotPHS", True),
                    ("parameters.pulseHeigthSpect.plotPHScorrelation", True)
                    ]},
            "info": "Number of bins to use in the pulse height histogram.",
            "set": lambda val: setattr(parameters.pulseHeigthSpect, 'energyBins', val)
        },
        "parameters.pulseHeigthSpect.maxEnerg": {
            "label": "Max Energy",
            "type": "entry",
            "default": 1700,
            "inputValidation": "int",
            "dependsOn":  {
                    "or": [
                    ("parameters.pulseHeigthSpect.plotPHS", True),
                    ("parameters.pulseHeigthSpect.plotPHScorrelation", True)
                    ]},
            "info": "Maximum energy value considered in pulse height analysis.",
            "set": lambda val: setattr(parameters.pulseHeigthSpect, 'maxEnerg', val)
         }
    },
    "wavelength": {
        "parameters.wavelength.calculateLambda": {
            "label": "Calculate Lambda",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.wavelength, 'calculateLambda', val)
        },
        "parameters.wavelength.distance": {
            "label": "Distance (mm)",
            "type": "entry",
            "default": 8000,
            "inputValidation": "int",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "Distance in mm from chopper and wires 0 of detector",
            "set": lambda val: setattr(parameters.wavelength, 'distance', val)
        },
    
        "parameters.wavelength.plotXLambda": {
            "label": "Plot X vs Lambda",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "2D plot of X vs Lambda",
            "set": lambda val: setattr(parameters.wavelength, 'plotXLambda', val)
        },
        "parameters.wavelength.plotLambdaDistr": {
            "label": "Plot Lambda Distribution",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "ON/OFF integrated over single cassettes",
            "set": lambda val: setattr(parameters.wavelength, 'plotLambdaDistr', val)
        },
        "parameters.wavelength.lambdaBins": {
            "label": "Lambda Bins",
            "type": "entry",
            "default": 128,
            "inputValidation": "int",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "Number of bins for the lambda histogram",
            "set": lambda val: setattr(parameters.wavelength, 'lambdaBins', val)
        },
        "parameters.wavelength.lambdaRange": {
            "label": "Lambda Range [min, max] (Å)",
            "type": "range",
            "default": [1, 16],
            "inputValidation": "float",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "Range of lambda values (in Å) as [min, max]",
            "set": lambda val: setattr(parameters.wavelength, 'lambdaRange', val)
        },
        "parameters.wavelength.chopperPeriod": {
            "label": "Chopper Period (s)",
            "type": "entry",
            "default": 0.12,
            "inputValidation": "float",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "Chopper period in seconds (relevant if multipleFramesPerRest > 1)",
            "set": lambda val: setattr(parameters.wavelength, 'chopperPeriod', val)
        },
        "parameters.wavelength.multipleFramePerReset": {
            "label": "Multiple Frames per Reset",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "dependsOn": ("parameters.wavelength.calculateLambda", True),
            "info": "ON/OFF toggle for if chopper has two openings or more per reset of ToF \n(This only affects the lambda calculation)",
            "set": lambda val: setattr(parameters.wavelength, 'multipleFramePerReset', val)
        },
        "parameters.wavelength.numOfBunchesPerPulse": {
            "label": "Bunches per Pulse",
            "type": "entry",
            "default": 2,
            "inputValidation": "int",
            "dependsOn": {
                "and": [ 
                    ("parameters.wavelength.calculateLambda", True),
                    ("parameters.wavelength.multipleFramePerReset", True)
                    ]
                },
            "info": "Number of neutron bunches per pulse",
            "set": lambda val: setattr(parameters.wavelength, 'numOfBunchesPerPulse', val)
        },
        "parameters.wavelength.lambdaMIN": {
            "label": "Minimum Lambda (Å)",
            "type": "entry",
            "default": 2.5,
            "inputValidation": "float",
            "dependsOn": {
                "and": [ 
                    ("parameters.wavelength.calculateLambda", True),
                    ("parameters.wavelength.multipleFramePerReset", True)
                    ]
                },
            "set": lambda val: setattr(parameters.wavelength, 'lambdaMIN', val)
        },
        "parameters.wavelength.chopperPickUpDelay": {
            "label": "Chopper PickUp Delay (s)",
            "type": "entry",
            "default": 0.00225,
            "inputValidation": "float",
            "dependsOn": {
                "and": [ 
                    ("parameters.wavelength.calculateLambda", True),
                    ("parameters.wavelength.multipleFramePerReset", True)
                    ]
                },
            "set": lambda val: setattr(parameters.wavelength, 'chopperPickUpDelay', val)
        }
    },
    "plotting": {
        "parameters.plottingInSections": {
            "label": "Plot in Sections",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "If True, plots are split into blocks for easier visualization.",
            "set": lambda val: setattr(parameters, 'plottingInSections', val)
        },
        "parameters.plottingInSectionsBlocks": {
            "label": "Sections Per Block",
            "type": "entry",
            "default": 5,
            "inputValidation": "int",
            "dependsOn": ("parameters.plottingInSections", True),
            "info": "Number of cassettes per plotting section.",
            "set": lambda val: setattr(parameters, 'plottingInSectionsBlocks', val)
        },
        "parameters.plotting.showStat": {
            "label": "Statistics Display",
            "type": "radio",
            "options": ["globalStat", "individualStat"],
            "default": "globalStat",
            "info": "Choose how to display statistical summaries.",
            "set": lambda val: setattr(parameters.plotting, 'showStat', val)
        },
        # Raw plotting options
        "parameters.plotting.plotRawReadouts": {
            "label": "Plot Raw Readouts",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "set": lambda val: setattr(parameters.plotting, 'plotRawReadouts', val)
        },
        "parameters.plotting.plotReadoutsTimeStamps": {
            "label": "Plot Readouts Time Stamps",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotReadoutsTimeStamps', val)
        },
        "parameters.plotting.plotADCvsCh": {
            "label": "Plot ADC vs Channel",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotADCvsCh', val)
        },
        "parameters.plotting.plotADCvsChlog": {
            "label": "Plot ADC vs Channel (Log Scale)",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "dependsOn": ("parameters.plotting.plotADCvsCh", True),
            "set": lambda val: setattr(parameters.plotting, 'plotADCvsChlog', val)
        },
        "parameters.plotting.plotChopperResets": {
            "label": "Plot Chopper Resets",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotChopperResets', val)
        },
        # Hit-level plotting
        "parameters.plotting.plotRawHits": {
            "label": "Plot Raw Hits",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotRawHits', val)
        },
        "parameters.plotting.plotHitsTimeStamps": {
            "label": "Plot Hits Time Stamps",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotHitsTimeStamps', val)
        },
        "parameters.plotting.plotHitsTimeStampsVSChannels": {
            "label": "Plot Hits Timestamps vs Channels",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotHitsTimeStampsVSChannels', val)
        },
        # Instantaneous Rate
        "parameters.plotting.plotInstRate": {
            "label": "Plot Instantaneous Rate",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotInstRate', val)
        },
        "parameters.plotting.instRateBin": {
            "label": "Rate Bin Width (s)",
            "type": "entry",
            "default": "100e-6",
            "inputValidation": "scientific",
            "dependsOn": ("parameters.plotting.plotInstRate", True),
            "set": lambda val: setattr(parameters.plotting, 'instRateBin', val)
        },
        # ToF (Time of Flight) plotting
        "parameters.plotting.plotToFDistr": {
            "label": "Plot ToF Distribution",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotToFDistr', val)
        },
        "parameters.plotting.ToFrange": {
            "label": "ToF Range (s)",
            "type": "entry",
            "default": 0.15,
            "inputValidation": "float",
            "set": lambda val: setattr(parameters.plotting, 'ToFrange', val)
        },
        "parameters.plotting.ToFbinning": {
            "label": "ToF Binning (s)",
            "type": "entry",
            "default": "100e-6",
            "inputValidation": "scientific",
            "set": lambda val: setattr(parameters.plotting, 'ToFbinning', val)
        },
        "parameters.plotting.ToFGate": {
            "label": "Enable ToF Gating",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'ToFGate', val)
        },
        "parameters.plotting.ToFGateRange": {
            "label": "ToF Gate Range [s]",
            "type": "range",
            "default": [0.02, 0.025],
            "inputValidation": "float",
            "dependsOn": ("parameters.plotting.ToFGate", True),
            "set": lambda val: setattr(parameters.plotting, 'ToFGateRange', val)
        },
        "parameters.plotting.plotMultiplicity": {
            "label": "Plot Multiplicity",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "set": lambda val: setattr(parameters.plotting, 'plotMultiplicity', val)
        },
        "parameters.plotting.plotABSunits": {
            "label": "Use Absolute Units",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "if True plot XY and XtoF plot in absolute unit (mm), if False plot in wire and strip ch no.",
            "set": lambda val: setattr(parameters.plotting, 'plotABSunits', val)
        },
        "parameters.plotting.plotIMGlog": {
            "label": "Log Scale for Images",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "plot XY and XToF in log scale",
            "set": lambda val: setattr(parameters.plotting, 'plotIMGlog', val)
        },
        "parameters.plotting.coincidenceWS_ONOFF": {
            "label": "Require Strip Coincidence",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "info": "ON/OFF, if  Tof  and Lambdaplot needs to include only events with strip present (2D) is True otherwise all events also without strip set to False",
            "set": lambda val: setattr(parameters.plotting, 'coincidenceWS_ONOFF', val)
        },
        "parameters.plotting.removeInvalidToFs": {
            "label": "Remove Invalid ToFs",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "info": "ON/OFF, if  invalid ToFs Tofare included in the plots or removed from events",
            "set": lambda val: setattr(parameters.plotting, 'removeInvalidToFs', val)
        },
        "parameters.plotting.histogOutBounds": {
            "label": "Histogram Out-of-Bounds",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "info": "histogram outBounds param set as True as default (Events out of bounds stored in first and last bin)",
            "set": lambda val: setattr(parameters.plotting, 'histogOutBounds', val)
        }
    },
    "monitor": {
        "parameters.MONitor.MONOnOff": {
            "label": "Enable Monitor",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "ON/OFF switch for including the monitor in the analysis.",
            "set": lambda val: setattr(parameters.MONitor, 'MONOnOff', val)
        },
        "parameters.MONitor.MONThreshold": {
            "label": "Monitor Threshold",
            "type": "entry",
            "default": 0,
            "inputValidation": "float",
            "dependsOn": ("parameters.MONitor.MONOnOff", True),
            "info": "Threshold on monitor events. 0 disables threshold; any other value enables it.",
            "set": lambda val: setattr(parameters.MONitor, 'MONThreshold', val)
        },
        "parameters.MONitor.plotMONtofPHS": {
            "label": "Plot Monitor ToF & PHS",
            "type": "bool",
            "options": ["True", "False"],
            "default": "True",
            "dependsOn": ("parameters.MONitor.MONOnOff", True),
            "info": "ON/OFF plotting for Monitor Time-of-Flight and Pulse Height spectra.",
            "set": lambda val: setattr(parameters.MONitor, 'plotMONtofPHS', val)
        },
        "parameters.MONitor.MONDistance": {
            "label": "Monitor Distance (mm)",
            "type": "entry",
            "default": 6000,
            "inputValidation": "int",
            "info": "Distance in mm from chopper to monitor (needed for lambda calculation of ToF).", 
            "dependsOn": ("parameters.MONitor.MONOnOff", True),
            "set": lambda val: setattr(parameters.MONitor, 'MONDistance', val)
        }
    },
    "reduced_file": {#####################################################################################################################
        "parameters.fileManagement.saveReducedFileONOFF": {
            "label": "Save Reduced File",
            "type": "bool",
            "options": ["True", "False"],
            "default": "False",
            "info": "Enable or disable saving a reduced HDF file with clusters.",
            "set": lambda val: setattr(parameters.fileManagement, 'saveReducedFileONOFF', val)
        },
        "parameters.fileManagement.saveReducedPath": {
            "label": "Reduced File Path",
            "type": "filePath",
            "mustExist": False,
            "dependsOn": ("parameters.fileManagement.saveReducedFileONOFF", True),
            "info": "Destination path for saving reduced HDF files.",
            "set": lambda val: setattr(parameters.fileManagement, 'saveReducedPath', val)
        },
        "parameters.fileManagement.reducedNameMainFolder": { # don't know if there are more options - if no more options remove from GUI and set fixed value
            "label": "Main Folder in HDF",
            "type": "entry",
            "default": "entry1",
            "dependsOn": ("parameters.fileManagement.saveReducedFileONOFF", True),
            "set": lambda val: setattr(parameters.fileManagement, 'reducedNameMainFolder', val)
        },
        "parameters.fileManagement.reducedCompressionHDFT": {
            "label": "HDF Compression Type",
            "type": "radio",
            "options": ["gzip"],
            "default": "gzip",
            "dependsOn": ("parameters.fileManagement.saveReducedFileONOFF", True),
            "info": "Compression method used for saving HDF files.",
            "set": lambda val: setattr(parameters.fileManagement, 'reducedCompressionHDFT', val)
        },
        "parameters.fileManagement.reducedCompressionHDFL": {
            "label": "HDF Compression Level",
            "type": "entry",
            "inputValidation": "int",
            "range": (0,9),
            "default": 9,
            "dependsOn": ("parameters.fileManagement.saveReducedFileONOFF", True),
            "info": "Compression level (0-9) used with HDF file saving.",
            "set": lambda val: setattr(parameters.fileManagement, 'reducedCompressionHDFL', val)
        }
    }
}



# Export
__all__ = ["config", "parameters"]