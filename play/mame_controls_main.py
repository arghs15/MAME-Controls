#!/usr/bin/env python3

# If Python can't find PyQt5, install it via:
# pip install PyQt5
"""
MAME Control Configuration Tool - PyQt5 Version
A tool for viewing and configuring MAME controls.

This is the main entry point for the application.
Run this script to start the application:
    python mame_controls_main.py

Command line arguments:
    --preview-only: Show only the preview window
    --game: Specify the ROM name to preview
    --screen: Screen number to display preview on (default: 2)
    --auto-close: Automatically close preview when MAME exits
"""

import sys
import os
import argparse
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtCore import Qt, QTimer
except ImportError:
    print("PyQt5 is not installed. Please install it with: pip install PyQt5")
    sys.exit(1)

# Make sure the path is properly set for module imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)
print(f"Script directory: {script_dir}")

# Import the main application class
try:
    from mame_controls_pyqt import MAMEControlConfig
except ImportError as e:
    print(f"Error importing MAMEControlConfig: {e}")
    print("Make sure PyQt5 is installed: pip install PyQt5")
    sys.exit(1)

def main():
    """Main entry point for the application"""
    print("Starting MAME Controls application...")
    
    # Create argument parser
    parser = argparse.ArgumentParser(description='MAME Control Configuration')
    parser.add_argument('--preview-only', action='store_true', help='Show only the preview window')
    parser.add_argument('--game', type=str, help='Specify the ROM name to preview')
    parser.add_argument('--screen', type=int, default=2, help='Screen number to display preview on (default: 2)')
    parser.add_argument('--auto-close', action='store_true', help='Automatically close preview when MAME exits')
    args = parser.parse_args()
    print("Arguments parsed.")
    
    # Check for preview-only mode
    if args.preview_only and args.game:
        # Initialize QApplication for preview only
        app = QApplication(sys.argv)
        app.setApplicationName("MAME Control Preview")
        set_dark_theme(app)
        
        # Create MAMEControlConfig in preview mode
        config = MAMEControlConfig(preview_only=True)
        
        # Show preview for specified game
        config.show_preview_standalone(args.game, args.auto_close)
        
        # Run app
        sys.exit(app.exec_())
    
    # Initialize QApplication
    print("Creating QApplication...")
    app = QApplication(sys.argv)
    print("QApplication created.")
    
    # Set application metadata
    app.setApplicationName("MAME Control Configuration")
    app.setApplicationVersion("1.0")
    
    # Apply dark theme
    print("Applying dark theme...")
    set_dark_theme(app)
    print("Dark theme applied.")
    
    print("Creating main window...")
    try:
        window = MAMEControlConfig()

        # Get the screen geometry dynamically
        screen_geometry = QApplication.primaryScreen().geometry()
        window.setGeometry(screen_geometry)
        window.move(0, 0)
        window.show()
        print(f"Window set to {screen_geometry.width()}x{screen_geometry.height()}")

    except Exception as e:
        print(f"Error creating window: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Start the application main loop
    print("Starting application loop...")
    try:
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error running application: {e}")
        import traceback
        traceback.print_exc()

def set_dark_theme(app):
    """Apply an improved dark theme with rounded corners and better contrast"""
    app.setStyle("Fusion")
    
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