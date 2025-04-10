#!/usr/bin/env python3
"""
MAME Control Configuration Tool - PyQt5 Version
A tool for viewing and configuring MAME controls.
"""

import sys
import os
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mame_controls_pyqt import MAMEControlConfig

def set_dark_theme(app):
    """Apply dark theme to application"""
    app.setStyle("Fusion")
    
    # Create dark palette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    
    # Apply dark palette
    app.setPalette(dark_palette)
    
    # Set stylesheet for additional styling
    app.setStyleSheet("""
        QToolTip { 
            color: #ffffff; 
            background-color: #2a82da; 
            border: 1px solid white; 
        }
        QPushButton { 
            background-color: #2d2d2d; 
            border: 1px solid #555555;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover { 
            background-color: #3d3d3d; 
        }
        QPushButton:pressed { 
            background-color: #1a1a1a; 
        }
        QCheckBox { 
            spacing: 5px; 
        }
        QCheckBox::indicator {
            width: 13px;
            height: 13px;
        }
        QCheckBox::indicator:unchecked {
            border: 1px solid #5A5A5A;
            background: #2d2d2d;
        }
        QCheckBox::indicator:checked {
            border: 1px solid #5A5A5A;
            background: #2a82da;
        }
    """)

def main():
    """Main entry point for the application"""
    # Create argument parser
    parser = argparse.ArgumentParser(description='MAME Control Configuration')
    parser.add_argument('--preview-only', action='store_true', help='Show only the preview window')
    parser.add_argument('--game', type=str, help='Specify the ROM name to preview')
    parser.add_argument('--screen', type=int, default=2, help='Screen number to display preview on (default: 2)')
    parser.add_argument('--auto-close', action='store_true', help='Automatically close preview when MAME exits')
    args = parser.parse_args()
    
    # Initialize QApplication
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("MAME Control Configuration")
    app.setApplicationVersion("1.0")
    
    # Apply dark theme
    set_dark_theme(app)
    
    if args.preview_only and args.game:
        # Preview-only mode: just show the preview for the specified game
        window = MAMEControlConfig(preview_only=True)
        
        # Set screen preference from command line
        window.preferred_preview_screen = args.screen
        print(f"Using screen {args.screen} from command line")
        
        # Hide buttons in preview-only mode
        window.hide_preview_buttons = True
        
        # Show the standalone preview
        window.show_preview_standalone(args.game, args.auto_close)
    else:
        # Normal mode: start the full application
        window = MAMEControlConfig()
        window.show()
    
    # Start the application main loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()