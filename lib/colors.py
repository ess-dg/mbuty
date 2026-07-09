#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
colors.py
=========
Stateless ANSI escape sequences for unified terminal color output.
"""

# Text Formatting Constants
WARN  = "\033[1;33m"  # Bold Yellow (Warnings)
ERR   = "\033[1;31m"  # Bold Red (Crashes / Errors)
INFO  = "\033[1;36m"  # Bold Cyan (Ingestion Metrics)
OK    = "\033[1;32m"  # Bold Green (Success Checkpoints)
RESET = "\033[1;37m"  # Standard White Terminal Reset

if __name__ == '__main__':
    print('{WARN}This is a warning{RESET}')