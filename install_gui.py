#!/usr/bin/env python3
import os
import stat
import platform
import subprocess

# --- Configuration ---
APP_NAME    = "MBUTY GUI"
SCRIPT_NAME = "MBUTY_GUI.py"

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, SCRIPT_NAME)
SYSTEM      = platform.system()

# For best results on Windows, use a .ico file if available
ICON_PATH1 = os.path.join(BASE_DIR, "GUI", "logos", "MBUTYlogo.ico")
ICON_PATH2 = os.path.join(BASE_DIR, "GUI", "logos", "MBUTYlogo.png")
ICON_PATH3 = os.path.join(BASE_DIR, "GUI", "logos", "MBUTYlogo.icns")

def make_executable(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

def create_windows_shortcut():
    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    shortcut_path = os.path.join(desktop, f"{APP_NAME}.lnk")
    
    # Use 'pythonw.exe' instead of 'python.exe' to suppress the console window
    vbs_script = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{shortcut_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "pythonw.exe"
    oLink.Arguments = "{SCRIPT_PATH}"
    oLink.WorkingDirectory = "{BASE_DIR}"
    oLink.IconLocation = "{ICON_PATH1}"
    oLink.Save
    """
    vbs_path = os.path.join(BASE_DIR, "temp_shortcut.vbs")
    with open(vbs_path, "w") as f: f.write(vbs_script)
    subprocess.run(["cscript", "//NoLogo", vbs_path], check=True)
    os.remove(vbs_path)
    print(f"Windows: Shortcut created using 'pythonw' (No Terminal).")


def get_linux_desktop():
    try:
        # Queries the system for the actual Desktop path
        return subprocess.check_output(["xdg-user-dir", "DESKTOP"]).decode().strip()
    except Exception:
        # Fallback to the standard path if xdg-user-dir isn't installed
        return os.path.expanduser("~/Desktop")

def create_linux_shortcut():
    desktop_dir = get_linux_desktop()
    # Check if the directory actually exists
    if not os.path.exists(desktop_dir):
        print(f"Error: Could not find desktop directory at {desktop_dir}")
        return

    # IF YOU WANT TO INSTALL IN APPLICATIONS INSTEAD OF DESKTOP 
    # desktop_path = os.path.expanduser("~/.local/share/applications/mbuty.desktop")
    
    desktop_path = os.path.join(desktop_dir, "mbuty.desktop")
    python_exe = subprocess.check_output(["which", "python3"]).decode().strip()  
    # Setting Terminal=false prevents the terminal window from opening
    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={APP_NAME}
Exec={python_exe} {SCRIPT_PATH}
Path={BASE_DIR}
Icon={ICON_PATH2}
Terminal=false
Categories=Application;Development;
"""
    with open(desktop_path, "w") as f: f.write(content)
    make_executable(desktop_path)
    print(f"Linux: Shortcut created with Terminal=false.")
    print(f"FINAL STEP: You MUST right-click the file on the Desktop and select 'Allow Launching'.")

def create_macos_shortcut():
    app_path = os.path.expanduser(f"~/Desktop/{APP_NAME}.app")
    
    # 1. Get the absolute path to the current python3 executable
    try:
        python_path = subprocess.check_output(["which", "python3"]).decode().strip()
    except:
        python_path = "python3" # Fallback

    # 2. Build the AppleScript. 
    # We 'cd' into the directory so your script's relative paths work.
    applescript = (
        f'do shell script "cd \'{BASE_DIR}\' && '
        f'{python_path} \'{SCRIPT_PATH}\' > /dev/null 2>&1 &"'
    )
    
    try:
        # Clear old version if it exists
        if os.path.exists(app_path):
            subprocess.run(["rm", "-rf", app_path])
            
        # Create the .app bundle
        subprocess.run(["osacompile", "-o", app_path, "-e", applescript], check=True)
        
        # 3. Apply the Icon (Using the AppKit bridge)
        if os.path.exists(ICON_PATH3):
            icon_cmd = f'''
try:
    from AppKit import NSWorkspace, NSImage
    ws = NSWorkspace.sharedWorkspace()
    img = NSImage.alloc().initByReferencingFile_("{ICON_PATH3}")
    ws.setIcon_forFile_options_(img, "{app_path}", 0)
except Exception as e:
    print(e)
'''

            subprocess.run(["python3", "-c", icon_cmd], check=False)
            # Force Finder to refresh the icon
            subprocess.run(["touch", app_path])

        print(f"macOS: Created silent .app bundle at {app_path}")
        
    except Exception as e:
        print(f"macOS Error: {e}")



def main():
    if SYSTEM == "Windows":
        create_windows_shortcut()
    elif SYSTEM == "Linux":
        create_linux_shortcut()
    elif SYSTEM == "Darwin":
        create_macos_shortcut()
    else:
        print(f"Unsupported OS: {SYSTEM}")

###############################################################################
###############################################################################

if __name__ == "__main__":
    main()