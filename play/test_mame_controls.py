#!/usr/bin/env python3
"""
Test script for MAME Controls PyQt implementation.
This script will try to run the main application and diagnose any issues.
"""

import sys
import os
import traceback

def run_test():
    """Run a test of the MAME Controls application"""
    print("=== MAME Controls PyQt Test ===")
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    
    # Check for required modules
    required_modules = ["PyQt5", "json", "xml.etree.ElementTree"]
    for module_name in required_modules:
        try:
            __import__(module_name)
            print(f"Module {module_name} found.")
        except ImportError as e:
            print(f"ERROR: Module {module_name} not found: {e}")
            print(f"Please install it using: pip install {module_name.split('.')[0]}")
            return False
    
    # Check for main application files
    required_files = ["mame_controls_main.py", "mame_controls_pyqt.py"]
    for filename in required_files:
        if not os.path.exists(filename):
            print(f"ERROR: Required file '{filename}' not found.")
            return False
        else:
            print(f"File {filename} found.")
    
    # Try importing the main class
    try:
        from mame_controls_pyqt import MAMEControlConfig
        print("Successfully imported MAMEControlConfig class.")
    except Exception as e:
        print(f"ERROR importing MAMEControlConfig: {e}")
        traceback.print_exc()
        return False
    
    # Try creating the application
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        print("Successfully created QApplication.")
    except Exception as e:
        print(f"ERROR creating QApplication: {e}")
        traceback.print_exc()
        return False
    
    # Try creating the main window (without showing it)
    try:
        window = MAMEControlConfig()
        print("Successfully created MAMEControlConfig instance.")
        
        # Check if the window has basic attributes
        checks = [
            ("game_list", hasattr(window, "game_list")),
            ("control_layout", hasattr(window, "control_layout")),
            ("mame_dir", hasattr(window, "mame_dir") and window.mame_dir is not None)
        ]
        
        for name, result in checks:
            status = "OK" if result else "MISSING"
            print(f"  - {name}: {status}")
        
        return all(result for _, result in checks)
    except Exception as e:
        print(f"ERROR creating main window: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n✅ All tests passed! The application should work.")
        print("Run the application with: python mame_controls_main.py")
    else:
        print("\n❌ Some tests failed. See error messages above.")