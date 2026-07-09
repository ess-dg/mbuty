#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module provides utility functions for handling scrolling and navigation
within Tkinter widgets, especially focusing on mousewheel events across
different operating systems and keyboard navigation for Listbox widgets.

Created on Wed Jul 2 09:52:03 2025

@author: sheilamonera
"""
import tkinter as tk
import platform

def on_mousewheel(scrollable_widget, event):
    """
    Handles mousewheel events for scrolling a Tkinter scrollable widget
    (e.g., Canvas, Text, Listbox). This function is designed for
    Windows and macOS platforms.

    Parameters:
        scrollable_widget: The Tkinter widget that supports `yview_scroll` (e.g., `tk.Canvas`, `tk.Text`, `tk.Listbox`).
        event (tk.Event): The event object containing mousewheel details.
                          `event.delta` provides the scroll amount.

    Returns:
        str: "break" to stop event propagation.
    """
    system = platform.system()
    if system == 'Darwin':
        # macOS uses event.delta directly for scroll units
        scrollable_widget.yview_scroll(int(-1 * event.delta), "units")
    elif system == 'Windows':
        # Windows often provides larger delta values, convert to units
        scrollable_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
    return "break"

def on_mousewheel_linux(scrollable_widget, event):
    """
    Handles Linux-specific mousewheel events using Button-4 (scroll up) and Button-5 (scroll down).

    Parameters:
        scrollable_widget: The Tkinter widget that supports `yview_scroll`.
        event (tk.Event): The event object. `event.num` indicates the button pressed (4 or 5).

    Returns:
        str: "break" to stop event propagation.
    """
    if event.num == 4:  # Mouse wheel up
        scrollable_widget.yview_scroll(-1, "units")
    elif event.num == 5:  # Mouse wheel down
        scrollable_widget.yview_scroll(1, "units")
    return "break"

def bind_mousewheel(root_widget, scrollable_widget):
    """
    Binds mousewheel events to a specific scrollable widget (e.g., Canvas, Text).
    This function sets up global mousewheel bindings that are active only when the mouse is
    positioned over the `scrollable_widget`, and deactivated when it leaves.

    Args:
        root_widget (tk.Tk or tk.Toplevel): The root Tkinter window or a Toplevel window.
        scrollable_widget (tk.Canvas or tk.Text): The widget to which scrolling behavior should be applied.
    """
    system = platform.system()

    def _on_enter(event):
        """
        Activates global mousewheel binding when the mouse cursor enters the `scrollable_widget` area.
        """
        if system in ('Windows', 'Darwin'):
            # Bind MouseWheel for Windows and macOS
            root_widget.bind_all("<MouseWheel>", lambda e: on_mousewheel(scrollable_widget, e))
        elif system == 'Linux':
            # Bind Button-4 and Button-5 for Linux
            root_widget.bind_all("<Button-4>", lambda e: on_mousewheel_linux(scrollable_widget, e))
            root_widget.bind_all("<Button-5>", lambda e: on_mousewheel_linux(scrollable_widget, e))

    def _on_leave(event):
        """
        Deactivates global mousewheel binding when the mouse cursor leaves the `scrollable_widget` area.
        This prevents unintended scrolling of other widgets.
        """
        # Unbind all global mousewheel events to clean up
        root_widget.unbind_all("<MouseWheel>")
        root_widget.unbind_all("<Button-4>")
        root_widget.unbind_all("<Button-5>")

    # Bind the enter/leave events to the specific scrollable_widget
    scrollable_widget.bind("<Enter>", _on_enter)
    scrollable_widget.bind("<Leave>", _on_leave)

def unbind_mousewheel(root_widget):
    """
    Unbinds all global mousewheel events from the root window.
    This function should be called during application shutdown to clean up global bindings
    and prevent memory leaks or unexpected behavior.

    Args:
        root_widget (tk.Tk or tk.Toplevel): The root Tkinter window or Toplevel window.
    """
    root_widget.unbind_all("<MouseWheel>")
    root_widget.unbind_all("<Button-4>")
    root_widget.unbind_all("<Button-5>")


def bind_listbox_scroll(listbox_widget):
    """
    Binds platform-specific mouse wheel events to a given Tkinter Listbox widget
    to enable scrolling. This binding uses the generalized `on_mousewheel`
    and `on_mousewheel_linux` handlers and prevents event propagation
    to parent widgets, ensuring only the Listbox scrolls.

    Args:
        listbox_widget (tk.Listbox): The `tk.Listbox` widget to bind scrolling to.
    """
    system_name = platform.system()
    if system_name == 'Windows' or system_name == 'Darwin': # macOS also uses <MouseWheel>
        listbox_widget.bind("<MouseWheel>", lambda e: on_mousewheel(listbox_widget, e))
    elif system_name == 'Linux':
        listbox_widget.bind("<Button-4>", lambda e: on_mousewheel_linux(listbox_widget, e))
        listbox_widget.bind("<Button-5>", lambda e: on_mousewheel_linux(listbox_widget, e))

def _handle_arrow_up(listbox_widget, event=None):
    """
    Helper function to handle the Up arrow key event for listbox navigation.
    Moves the selection up by one item and ensures the selected item is visible.

    Parameters:
        listbox_widget (tk.Listbox): The `tk.Listbox` widget to navigate.
        event (tk.Event, optional): The event object (ignored, but kept for consistency with bind callbacks).

    Returns:
        str or None: "break" to stop event propagation if an action was taken, else `None`.
    """
    # Check if the listbox widget exists before proceeding
    if not listbox_widget or not listbox_widget.winfo_exists():
        return None
    
    current_selection = listbox_widget.curselection()
    if current_selection:
        current_index = int(current_selection[0])
        if current_index > 0:
            new_index = current_index - 1
            listbox_widget.selection_clear(0, tk.END)  # Clear current selection
            listbox_widget.selection_set(new_index)    # Set new selection
            listbox_widget.activate(new_index)         # Activate (highlight) the new selection
            listbox_widget.see(new_index)              # Scroll to make the new selection visible
    else:
        # If no item is selected, select the last item if the list is not empty
        if listbox_widget.size() > 0:
            new_index = listbox_widget.size() - 1
            listbox_widget.selection_set(new_index)
            listbox_widget.activate(new_index)
            listbox_widget.see(new_index)
    return "break" # Indicate that the event has been handled

def _handle_arrow_down(listbox_widget, event=None):
    """
    Helper function to handle the Down arrow key event for listbox navigation.
    Moves the selection down by one item and ensures the selected item is visible.

    Parameters:
        listbox_widget (tk.Listbox): The `tk.Listbox` widget to navigate.
        event (tk.Event, optional): The event object (ignored, but kept for consistency with bind callbacks).

    Returns:
        str or None: "break" to stop event propagation if an action was taken, else `None`.
    """
    # Check if the listbox widget exists before proceeding
    if not listbox_widget or not listbox_widget.winfo_exists():
        return None
        
    current_selection = listbox_widget.curselection()
    if current_selection:
        current_index = int(current_selection[0])
        if current_index < listbox_widget.size() - 1:
            new_index = current_index + 1
            listbox_widget.selection_clear(0, tk.END)
            listbox_widget.selection_set(new_index)
            listbox_widget.activate(new_index)
            listbox_widget.see(new_index)
    else:
        # If no item is selected, select the first item if the list is not empty
        if listbox_widget.size() > 0:
            new_index = 0
            listbox_widget.selection_set(new_index)
            listbox_widget.activate(new_index)
            listbox_widget.see(new_index)
    return "break" # Indicate that the event has been handled

def bind_global_listbox_arrow_navigation(root_widget, listbox_getter_func):
    """
    Binds global Up/Down arrow key events to the root widget to control a listbox.
    This function uses a getter function to dynamically retrieve the currently active
    or relevant listbox widget, allowing for flexible navigation in applications
    with multiple or dynamically created listboxes.

    Args:
        root_widget (tk.Tk or tk.Toplevel): The root Tkinter window or Toplevel window.
        listbox_getter_func (callable): A function that, when called, returns the `tk.Listbox` widget
                                        that should currently be controlled by the arrow keys,
                                        or `None` if no listbox is active or focused.
    """
    def _on_global_arrow_up(event):
        """
        Callback for global Up arrow key presses.
        Retrieves the active listbox and calls the helper to handle navigation.
        """
        listbox = listbox_getter_func()
        if listbox and listbox.winfo_exists():
            return _handle_arrow_up(listbox, event)
        return None # Allow event propagation if no listbox is active

    def _on_global_arrow_down(event):
        """
        Callback for global Down arrow key presses.
        Retrieves the active listbox and calls the helper to handle navigation.
        """
        listbox = listbox_getter_func()
        if listbox and listbox.winfo_exists():
            return _handle_arrow_down(listbox, event)
        return None # Allow event propagation if no listbox is active

    # Bind the arrow key events globally to the root window.
    # The 'add="+'' ensures that these bindings are added to any existing bindings
    # without overwriting them.
    root_widget.bind("<Up>", _on_global_arrow_up, add="+")
    root_widget.bind("<Down>", _on_global_arrow_down, add="+")