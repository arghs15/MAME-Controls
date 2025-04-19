"""
Updates to mame_controls_main.py to support the new directory structure
where the main app runs from the preview folder
"""

import os
import sys
import argparse


def get_application_path():
    """Get the base path for the application (handles PyInstaller bundling)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def get_mame_parent_dir(app_path=None):
    """
    Get the parent directory where MAME, ROMs, and artwork are located.
    If we're in the preview folder, the parent is the MAME directory.
    """
    if app_path is None:
        app_path = get_application_path()
    
    # If we're in the preview folder, the parent is the MAME directory
    if os.path.basename(app_path) == "preview":
        return os.path.dirname(app_path)
    else:
        # We're already in the MAME directory
        return app_path


def main():
    """Main entry point for the application with improved path handling"""
    print("Starting MAME Controls application...")
    
    # Get application path
    app_dir = get_application_path()
    mame_dir = get_mame_parent_dir(app_dir)
    
    print(f"App directory: {app_dir}")
    print(f"MAME directory: {mame_dir}")
    
    # Create argument parser
    parser = argparse.ArgumentParser(description='MAME Control Configuration')
    parser.add_argument('--preview-only', action='store_true', help='Show only the preview window')
    parser.add_argument('--clean-preview', action='store_true', help='Show preview without buttons and UI elements (like saved image)')
    parser.add_argument('--game', type=str, help='Specify the ROM name to preview')
    parser.add_argument('--screen', type=int, default=1, help='Screen number to display preview on (default: 1)')
    parser.add_argument('--auto-close', action='store_true', help='Automatically close preview when MAME exits')
    parser.add_argument('--no-buttons', action='store_true', help='Hide buttons in preview mode (overrides settings)')
    parser.add_argument('--tk', action='store_true', help='Use the Tkinter version of the main GUI (default: PyQt)')
    args = parser.parse_args()
    print("Arguments parsed.")
    
    # Make sure the path is properly set for module imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    
    # Also ensure parent directory is in path if we're in preview folder
    if os.path.basename(script_dir) == "preview":
        parent_dir = os.path.dirname(script_dir)
        sys.path.append(parent_dir)
    
    print(f"Script directory: {script_dir}")
    
    # Check for preview-only mode - always use PyQt
    if args.preview_only and args.game:
        print(f"Preview-only mode for ROM: {args.game}")
        try:
            # Initialize PyQt preview
            from PyQt5.QtWidgets import QApplication
            
            # Import module with proper path handling
            try:
                # Try direct import first
                from mame_controls_pyqt import MAMEControlConfig
            except ImportError:
                # If direct import fails, try using the module from the script directory
                sys.path.insert(0, script_dir)
                from mame_controls_pyqt import MAMEControlConfig
            
            # Create QApplication
            app = QApplication(sys.argv)
            app.setApplicationName("MAME Control Preview")

            # Apply dark theme
            set_dark_theme(app)
            
            # Create MAMEControlConfig in preview mode
            config = MAMEControlConfig(preview_only=True)
            
            # Force hide buttons in preview-only mode if requested
            if args.no_buttons:
                config.hide_preview_buttons = True
                print("Command line option forcing buttons to be hidden")
            
            # Show preview for specified game with clean mode if requested
            config.show_preview_standalone(args.game, args.auto_close, clean_mode=args.clean_preview)
            
            # Run app
            sys.exit(app.exec_())
        except ImportError:
            print("PyQt5 or necessary modules not found for preview mode.")
            sys.exit(1)
    
    # For the main application, check which UI to use - now defaulting to PyQt
    if not args.tk:  # Changed condition to check for --tk flag
        # Initialize PyQt application
        try:
            from PyQt5.QtWidgets import QApplication
            
            # Import module with proper path handling
            try:
                # Try direct import first
                from mame_controls_pyqt import MAMEControlConfig
            except ImportError:
                # If direct import fails, try using the module from the script directory
                sys.path.insert(0, script_dir)
                from mame_controls_pyqt import MAMEControlConfig
            
            # Create QApplication
            app = QApplication(sys.argv)
            app.setApplicationName("MAME Control Configuration (PyQt)")
            app.setApplicationVersion("1.0")

            # Apply dark theme
            set_dark_theme(app)

            # Create main window
            window = MAMEControlConfig()

            # First make window visible
            window.show()

            # Then maximize it - using multiple methods for redundancy
            from PyQt5.QtCore import QTimer, Qt
            window.setWindowState(Qt.WindowMaximized)
            QTimer.singleShot(100, window.showMaximized)

            # Run application
            sys.exit(app.exec_())
        except ImportError:
            print("PyQt5 not found, falling back to Tkinter version.")
            args.tk = True  # Fall back to Tkinter if PyQt fails
    
    # If using Tkinter (either by flag or PyQt failure)
    if args.tk:
        try:
            # Import the Tkinter version
            import customtkinter as ctk
            
            # Import module with proper path handling
            try:
                # Try direct import first
                from mame_controls_tkinter import MAMEControlConfig
            except ImportError:
                # If direct import fails, try using the module from the script directory
                sys.path.insert(0, script_dir)
                from mame_controls_tkinter import MAMEControlConfig
            
            # Set appearance mode and theme
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")
            
            # Create the Tkinter application
            app = MAMEControlConfig()
            
            # Auto maximize
            app.after(100, app.state, 'zoomed')
            
            # Run the application
            app.mainloop()
        except ImportError:
            print("CustomTkinter or required modules not found. Please install with:")
            print("pip install customtkinter")
            sys.exit(1)


def set_dark_theme(app):
    """Apply a dark theme to the PyQt application"""
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtCore import Qt
    
    # Create dark palette with better colors
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ToolTipText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Text, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Button, QColor(55, 55, 55))
    dark_palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 50, 50))
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    
    # Apply palette
    app.setPalette(dark_palette)
    
    # Set stylesheet for controls
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #2d2d2d;
        }
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QToolTip { 
            color: #f0f0f0; 
            background-color: #2a82da; 
            border: 1px solid #f0f0f0;
            border-radius: 4px;
            padding: 4px;
            font-size: 12px;
        }
        QPushButton { 
            background-color: #3d3d3d; 
            border: 1px solid #5a5a5a;
            padding: 6px 12px;
            border-radius: 4px;
            color: #f0f0f0;
            font-weight: bold;
            min-height: 25px;
        }
        QPushButton:hover { 
            background-color: #4a4a4a; 
            border: 1px solid #6a6a6a;
        }
        QPushButton:pressed { 
            background-color: #2a82da; 
            border: 1px solid #2472c4;
        }
        QScrollArea, QTextEdit, QLineEdit {
            background-color: #1e1e1e;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
        }
        QCheckBox { 
            spacing: 8px; 
            color: #f0f0f0;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        QCheckBox::indicator:unchecked {
            border: 1px solid #5A5A5A;
            background: #3d3d3d;
        }
        QCheckBox::indicator:checked {
            border: 1px solid #2a82da;
            background: #2a82da;
        }
        QLabel {
            color: #f0f0f0;
        }
        QFrame {
            border-radius: 4px;
            border: 1px solid #3d3d3d;
        }
        QScrollBar:vertical {
            border: none;
            background: #2d2d2d;
            width: 10px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #5a5a5a;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            border: none;
            background: #2d2d2d;
            height: 10px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #5a5a5a;
            min-width: 20px;
            border-radius: 5px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
    """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()