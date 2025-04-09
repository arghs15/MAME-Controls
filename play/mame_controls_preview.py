import os
import sys
import json
import traceback
from PyQt5.QtWidgets import (QAction, QGridLayout, QMainWindow, QMenu, QMessageBox, QSpinBox, QVBoxLayout, QHBoxLayout, QWidget, 
                            QLabel, QPushButton, QFrame, QApplication, QDesktopWidget,
                            QDialog, QGroupBox, QCheckBox, QSlider, QComboBox)
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QFontMetrics
from PyQt5.QtCore import Qt, QPoint, QTimer, QRect, QEvent, QSize

class DraggableLabel(QLabel):
    """An enhanced draggable label with shadow, resizing and better visibility"""
    def __init__(self, text, parent=None, shadow_offset=2, settings=None):
        super().__init__(text, parent)
        self.shadow_offset = shadow_offset
        self.settings = settings or {}
        
        # Apply font settings
        self.update_appearance()
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        self.dragging = False
        self.resizing = False
        self.offset = QPoint()
        
        # Original position for reset
        self.original_pos = self.pos()
        
        # Original font size
        self.original_font_size = self.settings.get("font_size", 28)
        
        # Size for resize handle
        self.resize_handle_size = 10
        
        # Create context menu
        self.setup_context_menu()
        
    def setup_context_menu(self):
        """Setup right-click context menu"""
        self.menu = QMenu(self)
        
        # Font size options
        font_menu = QMenu("Font Size", self.menu)
        
        # Add size options
        for size in [16, 20, 24, 28, 32, 36, 40]:
            action = QAction(f"{size}px", self)
            action.triggered.connect(lambda checked, s=size: self.change_font_size(s))
            font_menu.addAction(action)
        
        self.menu.addMenu(font_menu)
        
        # Color options
        color_menu = QMenu("Text Color", self.menu)
        
        # Add color options
        colors = {
            "White": Qt.white,
            "Yellow": Qt.yellow,
            "Red": Qt.red,
            "Green": QColor(50, 255, 50),
            "Blue": QColor(80, 160, 255),
            "Pink": QColor(255, 100, 255)
        }
        
        for name, color in colors.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked, c=color: self.change_text_color(c))
            color_menu.addAction(action)
        
        self.menu.addMenu(color_menu)
        
        # Add reset option
        reset_action = QAction("Reset Size", self)
        reset_action.triggered.connect(self.reset_font_size)
        self.menu.addAction(reset_action)
        
        # Add duplicate option
        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(self.duplicate_label)
        self.menu.addAction(duplicate_action)
        
    def update_appearance(self):
        """Update appearance based on settings"""
        font_family = self.settings.get("font_family", "Arial")
        font_size = self.settings.get("font_size", 28)
        use_bold = self.settings.get("bold_strength", 2) > 0
        
        font = QFont(font_family, font_size)
        font.setBold(use_bold)
        self.setFont(font)
        
        # Remove all borders and make background transparent
        self.setStyleSheet("color: white; background-color: transparent; border: none;")
        self.setCursor(Qt.OpenHandCursor)
        
    def update_text(self, text):
        """Update the displayed text, applying uppercase if needed"""
        if self.settings.get("use_uppercase", False):
            text = text.upper()
        self.setText(text)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if we're in the resize corner
            if self.is_in_resize_corner(event.pos()):
                self.resizing = True
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.dragging = True
                self.offset = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
        
    def mouseMoveEvent(self, event):
        # Update cursor when hovering over the resize corner
        if not self.dragging and not self.resizing:
            if self.is_in_resize_corner(event.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
        
        # Handle dragging
        if self.dragging:
            self.move(self.mapToParent(event.pos() - self.offset))
            
            # Notify the parent to update shadow label if it exists
            if hasattr(self.parent(), "update_shadow_position"):
                self.parent().update_shadow_position(self)
        
        # Handle resizing
        elif self.resizing:
            # Calculate the relative change based on the movement
            width_delta = event.x() - self.width()
            height_delta = event.y() - self.height()
            
            # Use the larger change to determine how much to scale the font
            delta = max(width_delta, height_delta)
            
            # Scale font size based on movement
            current_font = self.font()
            current_size = current_font.pointSize()
            
            # Adjust font size, with a minimum size
            new_size = max(8, current_size + delta // 10)
            
            # Apply new font size
            current_font.setPointSize(new_size)
            self.setFont(current_font)
            
            # Update settings
            if self.settings:
                self.settings["font_size"] = new_size
            
            # Notify the parent to update shadow label if it exists
            if hasattr(self.parent(), "update_shadow_font"):
                self.parent().update_shadow_font(self)
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            
            # Update cursor based on position
            if self.is_in_resize_corner(event.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
            
    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        self.menu.exec_(event.globalPos())
    
    def is_in_resize_corner(self, pos):
        """Check if the position is in the resize corner"""
        return (pos.x() > self.width() - self.resize_handle_size and 
                pos.y() > self.height() - self.resize_handle_size)
    
    def paintEvent(self, event):
        """Override paint event to draw resize handle"""
        super().paintEvent(event)
        
        # Draw resize handle in the bottom-right corner
        painter = QPainter(self)
        painter.setPen(Qt.white)
        
        # Draw simple diagonal lines for resize handle
        x = self.width() - self.resize_handle_size
        y = self.height() - self.resize_handle_size
        for i in range(1, 4):
            painter.drawLine(
                x + i * 2, y + self.resize_handle_size - 2,
                x + self.resize_handle_size - 2, y + i * 2
            )
    
    def change_font_size(self, size):
        """Change font size through context menu"""
        current_font = self.font()
        current_font.setPointSize(size)
        self.setFont(current_font)
        
        # Update settings
        if self.settings:
            self.settings["font_size"] = size
        
        # Notify the parent to update shadow label if it exists
        if hasattr(self.parent(), "update_shadow_font"):
            self.parent().update_shadow_font(self)
    
    def reset_font_size(self):
        """Reset font size to original"""
        self.change_font_size(self.original_font_size)
    
    def change_text_color(self, color):
        """Change text color"""
        self.setStyleSheet(f"color: {color.name()}; background-color: transparent; border: none;")
        
        # Find and update the shadow label if possible
        if hasattr(self.parent(), "update_shadow_for_label"):
            self.parent().update_shadow_for_label(self)
    
    # Add this method to PreviewWindow class
    def update_shadow_for_label(self, label):
        """Find and update the shadow for a label"""
        for control_name, control_data in self.control_labels.items():
            if control_data['label'] == label:
                # Just update the shadow position to ensure it's behind
                shadow = self.shadow_labels[control_name]
                shadow.lower()  # Make sure shadow stays behind
                shadow.move(label.pos().x() + 2, label.pos().y() + 2)
                break
    
    def toggle_shadow(self):
        """Toggle visibility of shadow text"""
        for shadow in self.shadow_labels.values():
            shadow.setVisible(not shadow.isVisible())

    def update_shadow_color(self, color=QColor(0, 0, 0)):
        """Update shadow color for all labels"""
        for shadow in self.shadow_labels.values():
            shadow.setStyleSheet(f"color: {color.name()}; background-color: transparent; border: none;")

    # Add this method to update the duplicate_control_label function to better handle shadows
    def duplicate_control_label(self, label):
        """Duplicate a control label"""
        # Find which control this label belongs to
        for control_name, control_data in self.control_labels.items():
            if control_data['label'] == label:
                # Create a new unique control name
                new_control_name = f"{control_name}_copy"
                counter = 1
                
                # Make sure the name is unique
                while new_control_name in self.control_labels:
                    new_control_name = f"{control_name}_copy{counter}"
                    counter += 1
                
                # Create a new label with the same text
                action_text = control_data['action']
                
                # Create a new draggable label
                new_label = DraggableLabel(action_text, self.canvas, settings=self.text_settings)
                
                # Copy font and other properties
                new_label.setFont(label.font())
                new_label.setStyleSheet(label.styleSheet())
                
                # Create shadow effect for better visibility
                shadow_label = QLabel(action_text, self.canvas)
                shadow_label.setStyleSheet("color: black; background-color: transparent; border: none;")
                shadow_label.setFont(new_label.font())
                
                # Position slightly offset from original
                new_pos = QPoint(label.pos().x() + 20, label.pos().y() + 20)
                
                # Position shadow behind the label
                shadow_label.move(new_pos.x() + 2, new_pos.y() + 2)
                new_label.move(new_pos)
                
                # Make sure shadow is behind
                shadow_label.lower()
                
                # Store the new labels
                self.control_labels[new_control_name] = {
                    'label': new_label,
                    'shadow': shadow_label,
                    'action': action_text,
                    'original_pos': new_pos
                }
                
                # Store shadow label separately for convenience
                self.shadow_labels[new_control_name] = shadow_label
                
                # Connect position update for shadow
                original_mouseMoveEvent = new_label.mouseMoveEvent
                new_label.mouseMoveEvent = lambda event, label=new_label, shadow=shadow_label, orig_func=original_mouseMoveEvent: self.on_label_move(event, label, shadow, orig_func)
                
                # Show the new labels
                shadow_label.show()
                new_label.show()
                
                break
    
    def duplicate_label(self):
        """Duplicate this label"""
        if hasattr(self.parent(), "duplicate_control_label"):
            self.parent().duplicate_control_label(self)

class TextSettingsDialog(QDialog):
    """Dialog for configuring text appearance in preview"""
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Text Appearance Settings")
        self.resize(400, 500)
        
        # Store parent reference for settings access
        self.parent = parent
        
        # Use provided settings or load defaults
        self.settings = settings or {
            "font_family": "Arial",
            "font_size": 28,
            "bold_strength": 2,
            "use_uppercase": False,
            "y_offset": -40
        }
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Font section
        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout(font_group)
        
        # Font family selection
        font_row = QHBoxLayout()
        font_label = QLabel("Font Family:")
        
        self.font_combo = QComboBox()
        # Add common fonts
        fonts = ["Arial", "Verdana", "Tahoma", "Times New Roman", "Courier New", "Segoe UI", 
                 "Calibri", "Georgia", "Impact", "System"]
        self.font_combo.addItems(fonts)
        
        # Set current font
        current_font = self.settings.get("font_family", "Arial")
        index = self.font_combo.findText(current_font)
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
            
        font_row.addWidget(font_label)
        font_row.addWidget(self.font_combo)
        font_layout.addLayout(font_row)
        
        # Font size slider
        size_row = QHBoxLayout()
        size_label = QLabel("Font Size:")
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setMinimum(12)
        self.size_slider.setMaximum(48)
        self.size_slider.setValue(self.settings.get("font_size", 28))
        
        self.size_value = QLabel(str(self.size_slider.value()))
        self.size_slider.valueChanged.connect(lambda v: self.size_value.setText(str(v)))
        
        size_row.addWidget(size_label)
        size_row.addWidget(self.size_slider)
        size_row.addWidget(self.size_value)
        font_layout.addLayout(size_row)
        
        # Bold strength
        bold_row = QHBoxLayout()
        bold_label = QLabel("Bold Strength:")
        
        self.bold_slider = QSlider(Qt.Horizontal)
        self.bold_slider.setMinimum(0)
        self.bold_slider.setMaximum(5)
        self.bold_slider.setValue(self.settings.get("bold_strength", 2))
        
        self.bold_labels = ["None", "Light", "Medium", "Strong", "Very Strong", "Maximum"]
        self.bold_value = QLabel(self.bold_labels[self.bold_slider.value()])
        
        self.bold_slider.valueChanged.connect(
            lambda v: self.bold_value.setText(self.bold_labels[v])
        )
        
        bold_row.addWidget(bold_label)
        bold_row.addWidget(self.bold_slider)
        bold_row.addWidget(self.bold_value)
        font_layout.addLayout(bold_row)
        
        layout.addWidget(font_group)
        
        # Text options
        options_group = QGroupBox("Text Options")
        options_layout = QVBoxLayout(options_group)
        
        # Uppercase option
        self.uppercase_check = QCheckBox("Use UPPERCASE for all text")
        self.uppercase_check.setChecked(self.settings.get("use_uppercase", False))
        options_layout.addWidget(self.uppercase_check)
        
        # Y-offset slider for vertical positioning
        offset_row = QHBoxLayout()
        offset_label = QLabel("Y-Offset:")
        
        self.offset_slider = QSlider(Qt.Horizontal)
        self.offset_slider.setMinimum(-80)
        self.offset_slider.setMaximum(0)
        self.offset_slider.setValue(self.settings.get("y_offset", -40))
        
        self.offset_value = QLabel(str(self.offset_slider.value()))
        self.offset_slider.valueChanged.connect(lambda v: self.offset_value.setText(str(v)))
        
        offset_row.addWidget(offset_label)
        offset_row.addWidget(self.offset_slider)
        offset_row.addWidget(self.offset_value)
        options_layout.addLayout(offset_row)
        
        layout.addWidget(options_group)
        
        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Preview Text")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group)
        
        # Update preview when settings change
        self.font_combo.currentTextChanged.connect(self.update_preview)
        self.size_slider.valueChanged.connect(self.update_preview)
        self.bold_slider.valueChanged.connect(self.update_preview)
        self.uppercase_check.stateChanged.connect(self.update_preview)
        
        # Initial preview update
        self.update_preview()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept_settings)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.apply_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def update_preview(self):
        """Update the preview label with current settings"""
        # Get current settings
        font_family = self.font_combo.currentText()
        font_size = self.size_slider.value()
        bold_strength = self.bold_slider.value()
        use_uppercase = self.uppercase_check.isChecked()
        
        # Create font
        font = QFont(font_family, font_size)
        font.setBold(bold_strength > 0)
        font.setWeight(QFont.Bold if bold_strength > 0 else QFont.Normal)
        
        # Apply to preview
        self.preview_label.setFont(font)
        
        # Apply uppercase if enabled
        preview_text = "Preview Text"
        if use_uppercase:
            preview_text = preview_text.upper()
        
        self.preview_label.setText(preview_text)
        
        # Apply shadow effect based on bold strength
        if bold_strength == 0:
            self.preview_label.setStyleSheet("background-color: black; color: white;")
        else:
            # Advanced shadow effect needs to be implemented in actual rendering
            self.preview_label.setStyleSheet(
                f"background-color: black; color: white; text-shadow: {bold_strength}px {bold_strength}px black;"
            )
    
    def get_current_settings(self):
        """Get the current settings from dialog controls"""
        return {
            "font_family": self.font_combo.currentText(),
            "font_size": self.size_slider.value(),
            "bold_strength": self.bold_slider.value(),
            "use_uppercase": self.uppercase_check.isChecked(),
            "y_offset": self.offset_slider.value()
        }
    
    def apply_settings(self):
        """Apply the current settings without closing dialog"""
        settings = self.get_current_settings()
        
        # Update settings locally
        self.settings = settings
        
        # If parent provided and has the method, update parent settings
        if self.parent and hasattr(self.parent, 'update_text_settings'):
            self.parent.update_text_settings(settings)
    
    def accept_settings(self):
        """Save settings and close dialog"""
        self.apply_settings()
        self.accept()

"""
Modifications to the PreviewWindow class in mame_controls_preview.py
"""

# Replace or modify the PreviewWindow class initialization
class PreviewWindow(QMainWindow):
    """Window for displaying game controls preview"""
    def __init__(self, rom_name, game_data, mame_dir, parent=None):
        super().__init__(parent)
        
        # Store parameters
        self.rom_name = rom_name
        self.game_data = game_data
        self.mame_dir = mame_dir
        self.control_labels = {}
        self.shadow_labels = {}
        self.bg_label = None
        self.background_pixmap = None  # For saving image
        
        # Force window to be displayed in the correct place
        self.parent = parent
        
        # Print debugging info
        print(f"Initializing PreviewWindow for ROM: {rom_name}")
        print(f"MAME directory: {mame_dir}")
        
        try:
            # Load settings
            self.text_settings = self.load_text_settings()
            self.logo_settings = self.load_logo_settings()
            
            # Configure window
            self.setWindowTitle(f"Control Preview: {rom_name}")
            self.resize(1280, 720)
            
            # Keep frame for now to make window more visible
            # self.setWindowFlags(Qt.FramelessWindowHint)
            
            # Set attributes for proper window handling
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            
            # Create central widget with black background
            self.central_widget = QWidget()
            self.central_widget.setStyleSheet("background-color: black;")
            self.setCentralWidget(self.central_widget)
            
            # Main layout
            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create canvas area where the background image and controls will be displayed
            self.canvas = QWidget()
            self.canvas.setStyleSheet("background-color: black;")
            self.main_layout.addWidget(self.canvas, 1)  # 1 stretch factor for most space
            
            # Button row at the bottom
            self.button_frame = QFrame()
            self.button_frame.setStyleSheet("background-color: rgba(30, 30, 30, 180);")  # Semi-transparent
            self.button_frame.setFixedHeight(80)
            self.button_layout = QVBoxLayout(self.button_frame)
            self.button_layout.setContentsMargins(10, 5, 10, 5)
            
            # Create two rows for buttons
            self.top_row = QHBoxLayout()
            self.bottom_row = QHBoxLayout()
            
            # Button style
            button_style = """
                QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: 1px solid #5a5a5a;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    min-width: 90px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """
            
            # Top row buttons
            self.close_button = QPushButton("Close")
            self.close_button.clicked.connect(self.close)
            self.close_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.close_button)
            
            self.reset_button = QPushButton("Reset")
            self.reset_button.clicked.connect(self.reset_positions)
            self.reset_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.reset_button)
            
            self.global_button = QPushButton("Global")
            self.global_button.clicked.connect(lambda: self.save_positions(is_global=True))
            self.global_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.global_button)
            
            self.rom_button = QPushButton("ROM")
            self.rom_button.clicked.connect(lambda: self.save_positions(is_global=False))
            self.rom_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.rom_button)
            
            self.text_settings_button = QPushButton("Text Settings")
            self.text_settings_button.clicked.connect(self.show_text_settings)
            self.text_settings_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.text_settings_button)
            
            self.save_image_button = QPushButton("Save Image")
            self.save_image_button.clicked.connect(self.save_image)
            self.save_image_button.setStyleSheet(button_style)
            self.top_row.addWidget(self.save_image_button)
            
            # Bottom row buttons
            self.joystick_button = QPushButton("Joystick")
            self.joystick_button.clicked.connect(self.toggle_joystick_controls)
            self.joystick_button.setStyleSheet(button_style)
            self.bottom_row.addWidget(self.joystick_button)
            
            self.toggle_texts_button = QPushButton("Hide Texts")
            self.toggle_texts_button.clicked.connect(self.toggle_texts)
            self.toggle_texts_button.setStyleSheet(button_style)
            self.bottom_row.addWidget(self.toggle_texts_button)
            
            # Add logo controls
            self.logo_visible = self.logo_settings.get("logo_visible", True)
            logo_text = "Hide Logo" if self.logo_visible else "Show Logo"
            self.logo_button = QPushButton(logo_text)
            self.logo_button.clicked.connect(self.toggle_logo)
            self.logo_button.setStyleSheet(button_style)
            self.bottom_row.addWidget(self.logo_button)
            
            self.logo_pos_button = QPushButton("Logo Pos")
            self.logo_pos_button.clicked.connect(self.show_logo_position)
            self.logo_pos_button.setStyleSheet(button_style)
            self.bottom_row.addWidget(self.logo_pos_button)
            
            # Add screen toggle button
            self.screen_button = QPushButton("Screen 2")
            self.screen_button.clicked.connect(self.toggle_screen)
            self.screen_button.setStyleSheet(button_style)
            self.bottom_row.addWidget(self.screen_button)
            
            # Add rows to button layout
            self.button_layout.addLayout(self.top_row)
            self.button_layout.addLayout(self.bottom_row)
            
            # Add button frame to main layout
            self.main_layout.addWidget(self.button_frame)
            
            # Load the background image
            self.load_background_image()
            
            # Create control labels
            self.create_control_labels()
            
            # Add logo if enabled
            if self.logo_visible:
                self.add_logo()
            
            # Track whether texts are visible
            self.texts_visible = True
            
            # Joystick controls visibility
            self.joystick_visible = True
            
            # Track current screen
            self.current_screen = 1  # Start with primary screen
            
            # Bind ESC key to close
            self.keyPressEvent = self.handle_key_press
            
            # Move to primary screen first
            self.move_to_screen(1)  # Start with primary screen
            
            print("PreviewWindow initialization complete")
            
        except Exception as e:
            print(f"Error in PreviewWindow initialization: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error initializing preview: {e}")
            self.close()
        
        
    def load_logo_settings(self):
        """Load logo settings from file"""
        settings = {
            "logo_visible": True,
            "logo_position": "top-left"
        }
        
        try:
            settings_file = os.path.join(self.mame_dir, "logo_settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
        except Exception as e:
            print(f"Error loading logo settings: {e}")
        
        return settings
    
        # Update this method in the PreviewWindow class
    def toggle_logo(self):
        """Toggle logo visibility"""
        self.logo_visible = not self.logo_visible
        
        # Update button text
        self.logo_button.setText("Hide Logo" if self.logo_visible else "Show Logo")
        
        # Toggle logo visibility
        if hasattr(self, 'logo_label'):
            self.logo_label.setVisible(self.logo_visible)
        elif self.logo_visible:
            # Create logo if it doesn't exist yet
            self.add_logo()
        
        # Update settings
        self.logo_settings["logo_visible"] = self.logo_visible
        
        # Save setting
        self.save_logo_settings()
    
    def show_logo_position(self):
        """Show dialog to configure logo position"""
        self.show_logo_settings()
    
    def save_logo_settings(self):
        """Save logo settings to file"""
        try:
            settings = {
                "logo_visible": self.logo_visible,
                "logo_position": self.logo_settings.get("logo_position", "top-left")
            }
            
            settings_file = os.path.join(self.mame_dir, "logo_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
            print(f"Saved logo settings: {settings}")
        except Exception as e:
            print(f"Error saving logo settings: {e}")
    
    def add_logo(self):
        """Add logo overlay to preview"""
        # Find logo path
        logo_path = self.find_logo_path(self.rom_name)
        if not logo_path:
            print(f"No logo found for {self.rom_name}")
            return
            
        # Create logo label
        self.logo_label = QLabel(self.canvas)
        logo_pixmap = QPixmap(logo_path)
        
        if logo_pixmap.isNull():
            print(f"Error loading logo image from {logo_path}")
            return
        
        # Store original pixmap
        self.logo_label.setPixmap(logo_pixmap)
        
        # Update the logo display
        self.update_logo_display()
        
        # Enable mouse tracking for logo
        self.logo_label.setMouseTracking(True)
        
        # Add context menu for logo
        self.logo_label.setContextMenuEnabled = True
        self.logo_label.contextMenuEvent = lambda event: self.logo_context_menu(event)
        
        # Add drag support
        self.logo_label.mousePressEvent = lambda event: self.logo_mouse_press(event)
        self.logo_label.mouseMoveEvent = lambda event: self.logo_mouse_move(event)
        self.logo_label.mouseReleaseEvent = lambda event: self.logo_mouse_release(event)
        
        # Show the logo
        self.logo_label.show()
    
    def logo_context_menu(self, event):
        """Show context menu for logo"""
        menu = QMenu(self)
        
        # Add options
        settings_action = QAction("Logo Settings...", self)
        settings_action.triggered.connect(self.show_logo_settings)
        menu.addAction(settings_action)
        
        # Add position presets submenu
        position_menu = QMenu("Position", menu)
        
        positions = [
            ("Top Left", "top-left"),
            ("Top Center", "top-center"),
            ("Top Right", "top-right"),
            ("Center Left", "center-left"),
            ("Center", "center"),
            ("Center Right", "center-right"),
            ("Bottom Left", "bottom-left"),
            ("Bottom Center", "bottom-center"),
            ("Bottom Right", "bottom-right")
        ]
        
        for label, pos_id in positions:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, p=pos_id: self.set_logo_position(p))
            position_menu.addAction(action)
        
        menu.addMenu(position_menu)
        
        # Add toggle visibility option
        visibility_action = QAction("Hide Logo" if self.logo_visible else "Show Logo", self)
        visibility_action.triggered.connect(self.toggle_logo)
        menu.addAction(visibility_action)
        
        # Show menu
        menu.exec_(event.globalPos())
    
    def set_logo_position(self, position):
        """Set logo position to a preset"""
        self.logo_settings["logo_position"] = position
        self.logo_settings["custom_position"] = False
        self.update_logo_display()
        self.save_logo_settings()
    
    def logo_mouse_press(self, event):
        """Handle mouse press on logo for dragging"""
        if event.button() == Qt.LeftButton:
            # Store drag start position
            self.logo_drag_start_pos = event.pos()
            self.logo_is_dragging = True
            
            # Change cursor to indicate dragging
            self.logo_label.setCursor(Qt.ClosedHandCursor)
            
            # Enable custom position mode
            self.logo_settings["custom_position"] = True

    def logo_mouse_move(self, event):
        """Handle mouse move on logo for dragging"""
        if hasattr(self, 'logo_is_dragging') and self.logo_is_dragging:
            # Calculate new position
            delta = event.pos() - self.logo_drag_start_pos
            new_pos = self.logo_label.pos() + delta
            
            # Move the logo
            self.logo_label.move(new_pos)
            
            # Update settings with new position
            self.logo_settings["x_position"] = new_pos.x()
            self.logo_settings["y_position"] = new_pos.y()

    def logo_mouse_release(self, event):
        """Handle mouse release on logo to end dragging"""
        if event.button() == Qt.LeftButton and hasattr(self, 'logo_is_dragging'):
            self.logo_is_dragging = False
            
            # Reset cursor
            self.logo_label.setCursor(Qt.OpenHandCursor)
            
            # Save the new position
            self.save_logo_settings()
    
    def find_logo_path(self, rom_name):
        """Find logo path for a ROM name"""
        # Define logo directory path - modify this to your setup
        logo_dir = os.path.join(self.mame_dir, "..", "..", "collections", "Arcades", "medium_artwork", "logo")
        
        # Try to find logo with ROM name
        for ext in ['.png', '.jpg', '.jpeg']:
            logo_path = os.path.join(logo_dir, f"{rom_name}{ext}")
            if os.path.exists(logo_path):
                return logo_path
        
        # If not found by exact name, try case-insensitive search
        if os.path.exists(logo_dir):
            for filename in os.listdir(logo_dir):
                file_base, file_ext = os.path.splitext(filename.lower())
                if file_base == rom_name.lower() and file_ext.lower() in ['.png', '.jpg', '.jpeg']:
                    return os.path.join(logo_dir, filename)
        
        # Fallback - not found
        return None
    
    def update_logo_display(self):
        """Update the logo display based on current settings"""
        if not hasattr(self, 'logo_label') or not self.logo_label:
            return
        
        # Get logo size from pixmap
        logo_pixmap = self.logo_label.pixmap()
        if not logo_pixmap or logo_pixmap.isNull():
            return
        
        # Calculate size based on percentage of canvas and maintain aspect ratio
        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        
        width_percent = self.logo_settings.get("width_percentage", 15) / 100
        height_percent = self.logo_settings.get("height_percentage", 15) / 100
        
        # Calculate new dimensions
        new_width = int(canvas_width * width_percent)
        new_height = int(canvas_height * height_percent)
        
        # Resize logo while maintaining aspect ratio if specified
        if self.logo_settings.get("maintain_aspect", True):
            orig_ratio = logo_pixmap.width() / logo_pixmap.height() if logo_pixmap.height() != 0 else 1
            
            # Calculate the width based on height
            calc_width = int(new_height * orig_ratio)
            
            # Calculate the height based on width
            calc_height = int(new_width / orig_ratio)
            
            # Use the smaller of the two dimensions to maintain aspect ratio
            if calc_width <= new_width:
                new_width = calc_width
            else:
                new_height = calc_height
        
        # Scale the pixmap
        scaled_logo = logo_pixmap.scaled(
            new_width, 
            new_height, 
            Qt.KeepAspectRatio if self.logo_settings.get("maintain_aspect", True) else Qt.IgnoreAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # Update the label with new pixmap
        self.logo_label.setPixmap(scaled_logo)
        
        # Position the logo based on settings
        if self.logo_settings.get("custom_position", False):
            # Use custom X,Y position
            x = self.logo_settings.get("x_position", 20)
            y = self.logo_settings.get("y_position", 20)
        else:
            # Use predefined position
            position = self.logo_settings.get("logo_position", "top-left")
            
            # Padding from edges
            padding = 20
            
            # Calculate position
            if "top" in position and "left" in position:
                x, y = padding, padding
            elif "top" in position and "center" in position and "center-left" not in position and "center-right" not in position:
                x = (canvas_width - new_width) // 2
                y = padding
            elif "top" in position and "right" in position:
                x = canvas_width - new_width - padding
                y = padding
            elif "center" in position and "left" in position:
                x = padding
                y = (canvas_height - new_height) // 2
            elif position == "center":
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
            elif "center" in position and "right" in position:
                x = canvas_width - new_width - padding
                y = (canvas_height - new_height) // 2
            elif "bottom" in position and "left" in position:
                x = padding
                y = canvas_height - new_height - padding
            elif "bottom" in position and "center" in position and "center-left" not in position and "center-right" not in position:
                x = (canvas_width - new_width) // 2
                y = canvas_height - new_height - padding
            elif "bottom" in position and "right" in position:
                x = canvas_width - new_width - padding
                y = canvas_height - new_height - padding
            else:
                # Default to top-left
                x, y = padding, padding
        
        # Move logo to position
        self.logo_label.resize(new_width, new_height)
        self.logo_label.move(x, y)
    
    def position_logo(self, position):
        """Position the logo based on position setting"""
        if not hasattr(self, 'logo_label'):
            return
            
        # Get logo size
        logo_width = self.logo_label.pixmap().width()
        logo_height = self.logo_label.pixmap().height()
        
        # Padding from edges
        padding = 20
        
        # Calculate position
        if position == "top-left":
            x, y = padding, padding
        elif position == "top-center":
            x = (self.canvas.width() - logo_width) // 2
            y = padding
        elif position == "top-right":
            x = self.canvas.width() - logo_width - padding
            y = padding
        elif position == "bottom-left":
            x = padding
            y = self.canvas.height() - logo_height - padding
        elif position == "bottom-center":
            x = (self.canvas.width() - logo_width) // 2
            y = self.canvas.height() - logo_height - padding
        elif position == "bottom-right":
            x = self.canvas.width() - logo_width - padding
            y = self.canvas.height() - logo_height - padding
        else:
            # Default to top-left
            x, y = padding, padding
            
        # Move logo to position
        self.logo_label.move(x, y)
    
    # Add these methods to your PreviewWindow class to support the enhanced draggable labels
    def update_shadow_position(self, label):
        """Update the shadow position when the main label moves"""
        # Find which control this label belongs to
        for control_name, control_data in self.control_labels.items():
            if control_data['label'] == label:
                # Update shadow position
                shadow = self.shadow_labels[control_name]
                shadow.move(label.pos().x() + 2, label.pos().y() + 2)
                break

    def update_shadow_font(self, label):
        """Update the shadow font when the main label font changes"""
        # Find which control this label belongs to
        for control_name, control_data in self.control_labels.items():
            if control_data['label'] == label:
                # Update shadow font
                shadow = self.shadow_labels[control_name]
                shadow.setFont(label.font())
                break

    def duplicate_control_label(self, label):
        """Duplicate a control label"""
        # Find which control this label belongs to
        for control_name, control_data in self.control_labels.items():
            if control_data['label'] == label:
                # Create a new unique control name
                new_control_name = f"{control_name}_copy"
                counter = 1
                
                # Make sure the name is unique
                while new_control_name in self.control_labels:
                    new_control_name = f"{control_name}_copy{counter}"
                    counter += 1
                
                # Create a new label with the same text
                action_text = control_data['action']
                
                # Create a new draggable label
                new_label = DraggableLabel(action_text, self.canvas, settings=self.text_settings)
                
                # Copy font and other properties
                new_label.setFont(label.font())
                new_label.setStyleSheet(label.styleSheet())
                
                # Create shadow effect for better visibility
                shadow_label = QLabel(action_text, self.canvas)
                shadow_label.setStyleSheet("color: black; background-color: transparent; border: none;")
                shadow_label.setFont(new_label.font())
                
                # Position slightly offset from original
                new_pos = QPoint(label.pos().x() + 20, label.pos().y() + 20)
                new_label.move(new_pos)
                shadow_label.move(new_pos.x() + 2, new_pos.y() + 2)
                
                # Store the new labels
                self.control_labels[new_control_name] = {
                    'label': new_label,
                    'shadow': shadow_label,
                    'action': action_text,
                    'original_pos': new_pos
                }
                
                # Store shadow label separately for convenience
                self.shadow_labels[new_control_name] = shadow_label
                
                # Connect position update for shadow
                original_mouseMoveEvent = new_label.mouseMoveEvent
                new_label.mouseMoveEvent = lambda event, label=new_label, shadow=shadow_label, orig_func=original_mouseMoveEvent: self.on_label_move(event, label, shadow, orig_func)
                
                # Show the new labels
                new_label.show()
                shadow_label.show()
                
                break
    
    def create_button_rows(self):
        """Create the button rows for the preview window"""
        # Create two rows for buttons
        self.top_row = QHBoxLayout()
        self.bottom_row = QHBoxLayout()
        
        # Button style
        button_style = """
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #5a5a5a;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        
        # Top row buttons
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.close_button)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_positions)
        self.reset_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.reset_button)
        
        self.global_button = QPushButton("Global")
        self.global_button.clicked.connect(lambda: self.save_positions(is_global=True))
        self.global_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.global_button)
        
        self.rom_button = QPushButton("ROM")
        self.rom_button.clicked.connect(lambda: self.save_positions(is_global=False))
        self.rom_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.rom_button)
        
        self.text_settings_button = QPushButton("Text Settings")
        self.text_settings_button.clicked.connect(self.show_text_settings)
        self.text_settings_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.text_settings_button)
        
        self.save_image_button = QPushButton("Save Image")
        self.save_image_button.clicked.connect(self.save_image)
        self.save_image_button.setStyleSheet(button_style)
        self.top_row.addWidget(self.save_image_button)
        
        # Bottom row buttons
        self.joystick_button = QPushButton("Joystick")
        self.joystick_button.clicked.connect(self.toggle_joystick_controls)
        self.joystick_button.setStyleSheet(button_style)
        self.bottom_row.addWidget(self.joystick_button)
        
        self.toggle_texts_button = QPushButton("Hide Texts")
        self.toggle_texts_button.clicked.connect(self.toggle_texts)
        self.toggle_texts_button.setStyleSheet(button_style)
        self.bottom_row.addWidget(self.toggle_texts_button)
        
        # Add logo controls
        self.logo_visible = self.logo_settings.get("logo_visible", True)
        logo_text = "Hide Logo" if self.logo_visible else "Show Logo"
        self.logo_button = QPushButton(logo_text)
        self.logo_button.clicked.connect(self.toggle_logo)
        self.logo_button.setStyleSheet(button_style)
        self.bottom_row.addWidget(self.logo_button)
        
        self.logo_pos_button = QPushButton("Logo Pos")
        self.logo_pos_button.clicked.connect(self.show_logo_position)
        self.logo_pos_button.setStyleSheet(button_style)
        self.bottom_row.addWidget(self.logo_pos_button)
        
        # Add screen toggle button
        self.screen_button = QPushButton("Screen 2")
        self.screen_button.clicked.connect(self.toggle_screen)
        self.screen_button.setStyleSheet(button_style)
        self.bottom_row.addWidget(self.screen_button)
        
        # Add rows to button layout
        self.button_layout.addLayout(self.top_row)
        self.button_layout.addLayout(self.bottom_row)
        
    # Add a shadow toggle button to the setup UI
    # Add this to the method that creates your button rows
    def add_shadow_toggle_button(self):
        """Add a shadow toggle button to the UI"""
        # Add to bottom row
        button_style = """
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #5a5a5a;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        
        self.shadow_button = QPushButton("Hide Shadow")
        self.shadow_button.clicked.connect(self.toggle_shadow)
        self.shadow_button.setStyleSheet(button_style)
        
        # Add to your bottom row layout
        self.bottom_row.addWidget(self.shadow_button)
    
    # Fix for the save_image method
    def save_image(self):
        """Save current preview as an image"""
        try:
            from mame_controls_save import SaveUtility
            result = SaveUtility.save_preview_image(self.canvas, self.rom_name, self.mame_dir)
            if result:
                print(f"Successfully saved image for {self.rom_name}")
            else:
                print("Image save was cancelled or failed")
        except ImportError:
            print("SaveUtility module not found")
            QMessageBox.warning(self, "Not Implemented", 
                            "Save image feature requires mame_controls_save.py module.")
        except Exception as e:
            print(f"Error saving image: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save image: {str(e)}")
        
    def handle_key_press(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.close()
            
    # Replace the move_to_screen method with this enhanced version
    def move_to_screen(self, screen_index):
        """Move window to specified screen"""
        try:
            desktop = QDesktopWidget()
            num_screens = desktop.screenCount()
            
            print(f"Moving to screen {screen_index} (found {num_screens} screens)")
            
            if screen_index < 1 or screen_index > num_screens:
                screen_index = 1  # Default to first screen if invalid
                print(f"Invalid screen index, defaulting to 1")
            
            # Get geometry of the selected screen (0-indexed)
            screen_geometry = desktop.screenGeometry(screen_index - 1)
            print(f"Screen {screen_index} geometry: {screen_geometry.x()},{screen_geometry.y()} {screen_geometry.width()}x{screen_geometry.height()}")
            
            # Move window to that screen and maximize
            self.setGeometry(screen_geometry)
            print(f"Window moved to screen {screen_index}")
            
            # Update screen button text
            if hasattr(self, 'screen_button'):
                self.screen_button.setText(f"Screen {screen_index}")
        except Exception as e:
            print(f"Error moving to screen: {e}")
            traceback.print_exc()
    
    def toggle_screen(self):
        """Toggle between screens"""
        desktop = QDesktopWidget()
        num_screens = desktop.screenCount()
        
        # Cycle to next screen
        self.current_screen = (self.current_screen % num_screens) + 1
        
        # Update button text
        self.screen_button.setText(f"Screen {self.current_screen}")
        
        # Move to the new screen
        self.move_to_screen(self.current_screen)
    
    # Replace the load_background_image method with this enhanced version
    def load_background_image(self):
        """Load the background image for the game"""
        try:
            # Check for game-specific image
            preview_dir = os.path.join(self.mame_dir, "preview")
            
            # Try to find an image file
            image_path = None
            extensions = ['.png', '.jpg', '.jpeg']
            
            # Look for ROM-specific image
            for ext in extensions:
                test_path = os.path.join(preview_dir, f"{self.rom_name}{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    print(f"Found ROM-specific image: {image_path}")
                    break
                    
            # If no ROM-specific image, try default image
            if not image_path:
                for ext in extensions:
                    test_path = os.path.join(preview_dir, f"default{ext}")
                    if os.path.exists(test_path):
                        image_path = test_path
                        print(f"Using default image: {image_path}")
                        break
            
            # Set background image if found
            if image_path:
                # Create background label with image
                self.bg_label = QLabel(self.canvas)
                pixmap = QPixmap(image_path)
                
                if pixmap.isNull():
                    print(f"Error: Could not load image from {image_path}")
                    self.bg_label.setText("Error loading background image")
                    self.bg_label.setStyleSheet("color: red; font-size: 18px;")
                    self.bg_label.setAlignment(Qt.AlignCenter)
                    return
                    
                # Store pixmap for saving later
                self.background_pixmap = pixmap
                
                # Resize pixmap to fit the canvas while maintaining aspect ratio
                self.bg_label.setPixmap(pixmap.scaled(
                    self.canvas.width(), 
                    self.canvas.height(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                ))
                
                # Center the background image
                self.center_background()
                
                # Update when window resizes
                self.canvas.resizeEvent = self.on_canvas_resize
            else:
                # Create a black background with text
                print("No preview image found")
                self.bg_label = QLabel("No preview image found", self.canvas)
                self.bg_label.setAlignment(Qt.AlignCenter)
                self.bg_label.setStyleSheet("color: white; font-size: 24px;")
                self.bg_label.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
        except Exception as e:
            print(f"Error loading background image: {e}")
            traceback.print_exc()
            # Handle error by showing message on canvas
            if hasattr(self, 'bg_label') and self.bg_label:
                self.bg_label.setText(f"Error loading image: {str(e)}")
                self.bg_label.setStyleSheet("color: red; font-size: 18px;")
                self.bg_label.setAlignment(Qt.AlignCenter)
            else:
                self.bg_label = QLabel(f"Error: {str(e)}", self.canvas)
                self.bg_label.setStyleSheet("color: red; font-size: 18px;")
                self.bg_label.setAlignment(Qt.AlignCenter)
                self.bg_label.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
    
    # Replace the on_canvas_resize method in mame_controls_preview.py with this fixed version

    def on_canvas_resize(self, event):
        """Handle canvas resize to update background image"""
        try:
            # Resize and center the background image
            if hasattr(self, 'bg_label'):
                # Get the original pixmap
                pixmap = self.bg_label.pixmap()
                if pixmap and not pixmap.isNull():
                    # Resize to fit the canvas
                    new_pixmap = pixmap.scaled(
                        self.canvas.width(), 
                        self.canvas.height(), 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    self.bg_label.setPixmap(new_pixmap)
                    
                    # Center the background
                    self.center_background()
            
            # Also update control positions
            self.update_control_positions()
                    
            # Call the original QWidget resize event directly instead of using super()
            QWidget.resizeEvent(self.canvas, event)
            
        except Exception as e:
            print(f"Error in on_canvas_resize: {e}")
            import traceback
            traceback.print_exc()
    
    def center_background(self):
        """Center the background image in the canvas"""
        if hasattr(self, 'bg_label') and self.bg_label.pixmap():
            pixmap = self.bg_label.pixmap()
            # Calculate position to center the pixmap
            x = (self.canvas.width() - pixmap.width()) // 2
            y = (self.canvas.height() - pixmap.height()) // 2
            self.bg_label.setGeometry(x, y, pixmap.width(), pixmap.height())
            
            # Store the background position for control positioning
            self.bg_pos = (x, y)
            self.bg_size = (pixmap.width(), pixmap.height())
    
    def load_text_settings(self):
        """Load text appearance settings from file"""
        settings = {
            "font_family": "Arial",
            "font_size": 28,
            "bold_strength": 2,
            "use_uppercase": False,
            "y_offset": -40
        }
        
        try:
            settings_file = os.path.join(self.mame_dir, "text_appearance_settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
        except Exception as e:
            print(f"Error loading text appearance settings: {e}")
        
        return settings
    
    def save_text_settings(self, settings):
        """Save text appearance settings to file"""
        try:
            settings_file = os.path.join(self.mame_dir, "text_appearance_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
            print(f"Saved text appearance settings: {settings}")
        except Exception as e:
            print(f"Error saving text appearance settings: {e}")
    
    def create_control_labels(self):
        """Create draggable labels for each control"""
        if not self.game_data or 'players' not in self.game_data:
            return
                
        # Get Player 1 controls
        for player in self.game_data.get('players', []):
            if player['number'] != 1:  # Only show Player 1 controls for now
                continue
                    
            # Create a label for each control
            grid_x, grid_y = 0, 0
            for control in player.get('labels', []):
                control_name = control['name']
                action_text = control['value']
                
                # Apply text settings - uppercase if enabled
                if self.text_settings.get("use_uppercase", False):
                    action_text = action_text.upper()
                
                # Create a draggable label with current text settings
                label = DraggableLabel(action_text, self.canvas, settings=self.text_settings)
                
                # Create shadow effect for better visibility
                shadow_label = QLabel(action_text, self.canvas)
                shadow_label.setStyleSheet("color: black; background-color: transparent; border: none;")
                
                # Copy font settings from main label
                shadow_label.setFont(label.font())
                
                # Default position based on a grid layout
                x = 100 + (grid_x * 150)
                y = 100 + (grid_y * 40)
                
                # Apply y-offset from text settings
                y_offset = self.text_settings.get("y_offset", -40)
                y += y_offset
                
                # Update grid position
                grid_x = (grid_x + 1) % 5
                if grid_x == 0:
                    grid_y += 1
                
                # Position the labels - IMPORTANT: shadow goes behind!
                shadow_label.move(x + 2, y + 2)  # Shadow offset
                label.move(x, y)
                
                # Make shadow label go behind the main label
                shadow_label.lower()
                
                # Store the labels
                self.control_labels[control_name] = {
                    'label': label,
                    'shadow': shadow_label,
                    'action': action_text,
                    'original_pos': QPoint(x, y - y_offset)  # Store without offset for reset
                }
                
                # Store shadow label separately for convenience
                self.shadow_labels[control_name] = shadow_label
                
                # Connect position update for shadow
                original_mouseMoveEvent = label.mouseMoveEvent
                label.mouseMoveEvent = lambda event, label=label, shadow=shadow_label, orig_func=original_mouseMoveEvent: self.on_label_move(event, label, shadow, orig_func)

    def on_label_move(self, event, label, shadow, original_func):
        """Custom mouseMoveEvent to keep shadow with main label"""
        # Call the original mouseMoveEvent to handle dragging
        original_func(event)
        
        # Now update the shadow position
        if hasattr(label, 'dragging') and label.dragging:
            shadow.move(label.pos().x() + 2, label.pos().y() + 2)
        # If resizing, update the shadow font too
        elif hasattr(label, 'resizing') and label.resizing:
            shadow.setFont(label.font())
            shadow.move(label.pos().x() + 2, label.pos().y() + 2)
    
    def update_control_positions(self):
        """Update control positions when canvas resizes"""
        # This would be used to maintain relative positions on resize
        # Placeholder for now - requires position management system
        pass
    
    def toggle_texts(self):
        """Toggle visibility of control labels"""
        self.texts_visible = not self.texts_visible
        
        # Update button text
        self.toggle_texts_button.setText("Show Texts" if not self.texts_visible else "Hide Texts")
        
        # Toggle visibility for each control
        for control_name, control_data in self.control_labels.items():
            control_data['label'].setVisible(self.texts_visible)
            self.shadow_labels[control_name].setVisible(self.texts_visible)
    
    def toggle_joystick_controls(self):
        """Toggle visibility of joystick controls"""
        self.joystick_visible = not self.joystick_visible
        
        # Toggle visibility for joystick controls
        for control_name, control_data in self.control_labels.items():
            if "JOYSTICK" in control_name:
                is_visible = self.texts_visible and self.joystick_visible
                control_data['label'].setVisible(is_visible)
                self.shadow_labels[control_name].setVisible(is_visible)
    
    def reset_positions(self):
        """Reset control labels to default positions"""
        y_offset = self.text_settings.get("y_offset", -40)
        
        for control_name, control_data in self.control_labels.items():
            # Get the original position
            original_pos = control_data.get('original_pos', QPoint(100, 100))
            
            # Apply the current y-offset
            new_pos = QPoint(original_pos.x(), original_pos.y() + y_offset)
            
            # Move the labels
            control_data['label'].move(new_pos)
            self.shadow_labels[control_name].move(new_pos.x() + 2, new_pos.y() + 2)
    
    def save_positions(self, is_global=False):
        """Save current control positions"""
        # Create positions dictionary
        positions = {}
        
        # Remove y-offset from positions for storage
        y_offset = self.text_settings.get("y_offset", -40)
        
        for control_name, control_data in self.control_labels.items():
            label_pos = control_data['label'].pos()
            
            # Store normalized position (without y-offset)
            positions[control_name] = [label_pos.x(), label_pos.y() - y_offset]
        
        # Save to file
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Determine the file path
            if is_global:
                filepath = os.path.join(preview_dir, "global_positions.json")
            else:
                filepath = os.path.join(preview_dir, f"{self.rom_name}_positions.json")
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(positions, f)
                
            print(f"Saved {len(positions)} positions to: {filepath}")
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def show_text_settings(self):
        """Show dialog to configure text appearance"""
        dialog = TextSettingsDialog(self, self.text_settings)
        if dialog.exec_() == QDialog.Accepted:
            print("Text settings updated")
    
    def update_text_settings(self, settings):
        """Update text settings and apply to controls"""
        # Update local settings
        self.text_settings = settings
        
        # Save to file
        self.save_text_settings(settings)
        
        # Apply to existing controls
        self.apply_text_settings()
    
    def apply_text_settings(self):
        """Apply current text settings to all controls"""
        # Extract settings
        font_family = self.text_settings.get("font_family", "Arial")
        font_size = self.text_settings.get("font_size", 28)
        bold_strength = self.text_settings.get("bold_strength", 2)
        use_uppercase = self.text_settings.get("use_uppercase", False)
        y_offset = self.text_settings.get("y_offset", -40)
        
        # Create font
        font = QFont(font_family, font_size)
        font.setBold(bold_strength > 0)
        font.setWeight(QFont.Bold if bold_strength > 0 else QFont.Normal)
        
        for control_name, control_data in self.control_labels.items():
            # Get original action text
            action_text = control_data['action']
            
            # Apply uppercase if enabled
            display_text = action_text.upper() if use_uppercase else action_text
            
            # Update label text and font
            control_data['label'].setText(display_text)
            control_data['label'].setFont(font)
            control_data['label'].update_appearance()
            
            # Update shadow text and font
            shadow = self.shadow_labels[control_name]
            shadow.setText(display_text)
            shadow.setFont(font)
            
            # Update positions to apply new y-offset
            original_pos = control_data.get('original_pos', QPoint(100, 100))
            label_x, label_y = original_pos.x(), original_pos.y() + y_offset
            
            # Move the labels
            control_data['label'].move(label_x, label_y)
            shadow.move(label_x + 2, label_y + 2)  # Shadow offset
    
class LogoSettingsDialog(QDialog):
    """Dialog for configuring logo appearance and position"""
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Logo Settings")
        self.resize(400, 350)
        
        # Store parent reference for settings access
        self.parent = parent
        
        # Use provided settings or load defaults
        self.settings = settings or {
            "logo_visible": True,
            "logo_position": "top-left",
            "width_percentage": 15,
            "height_percentage": 15,
            "custom_position": False,
            "x_position": 20,
            "y_position": 20
        }
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Position selection group
        position_group = QGroupBox("Logo Position")
        position_layout = QVBoxLayout(position_group)
        
        # Position buttons grid
        pos_grid = QGridLayout()
        
        # Create position buttons
        self.position_buttons = {}
        positions = [
            ("top-left", 0, 0, "Top Left"),
            ("top-center", 0, 1, "Top Center"),
            ("top-right", 0, 2, "Top Right"),
            ("center-left", 1, 0, "Center Left"),
            ("center", 1, 1, "Center"),
            ("center-right", 1, 2, "Center Right"),
            ("bottom-left", 2, 0, "Bottom Left"),
            ("bottom-center", 2, 1, "Bottom Center"),
            ("bottom-right", 2, 2, "Bottom Right")
        ]
        
        for pos_id, row, col, label in positions:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked, p=pos_id: self.set_position(p))
            
            # Check if this is the current position
            if pos_id == self.settings.get("logo_position", "top-left"):
                btn.setChecked(True)
            
            pos_grid.addWidget(btn, row, col)
            self.position_buttons[pos_id] = btn
        
        position_layout.addLayout(pos_grid)
        
        # Custom position checkbox
        self.custom_position_check = QCheckBox("Use Custom Position (X, Y)")
        self.custom_position_check.setChecked(self.settings.get("custom_position", False))
        self.custom_position_check.toggled.connect(self.toggle_custom_position)
        position_layout.addWidget(self.custom_position_check)
        
        # Custom position controls
        custom_pos_layout = QHBoxLayout()
        
        self.x_spin = QSpinBox()
        self.x_spin.setMinimum(0)
        self.x_spin.setMaximum(1000)
        self.x_spin.setValue(self.settings.get("x_position", 20))
        self.x_spin.setEnabled(self.settings.get("custom_position", False))
        
        self.y_spin = QSpinBox()
        self.y_spin.setMinimum(0)
        self.y_spin.setMaximum(1000)
        self.y_spin.setValue(self.settings.get("y_position", 20))
        self.y_spin.setEnabled(self.settings.get("custom_position", False))
        
        custom_pos_layout.addWidget(QLabel("X:"))
        custom_pos_layout.addWidget(self.x_spin)
        custom_pos_layout.addWidget(QLabel("Y:"))
        custom_pos_layout.addWidget(self.y_spin)
        
        position_layout.addLayout(custom_pos_layout)
        
        layout.addWidget(position_group)
        
        # Size settings group
        size_group = QGroupBox("Logo Size")
        size_layout = QVBoxLayout(size_group)
        
        # Width percentage slider
        width_row = QHBoxLayout()
        width_label = QLabel("Width %:")
        
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setMinimum(5)
        self.width_slider.setMaximum(50)
        self.width_slider.setValue(self.settings.get("width_percentage", 15))
        
        self.width_value = QLabel(f"{self.width_slider.value()}%")
        self.width_slider.valueChanged.connect(
            lambda v: self.width_value.setText(f"{v}%")
        )
        
        width_row.addWidget(width_label)
        width_row.addWidget(self.width_slider)
        width_row.addWidget(self.width_value)
        size_layout.addLayout(width_row)
        
        # Height percentage slider
        height_row = QHBoxLayout()
        height_label = QLabel("Height %:")
        
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setMinimum(5)
        self.height_slider.setMaximum(50)
        self.height_slider.setValue(self.settings.get("height_percentage", 15))
        
        self.height_value = QLabel(f"{self.height_slider.value()}%")
        self.height_slider.valueChanged.connect(
            lambda v: self.height_value.setText(f"{v}%")
        )
        
        height_row.addWidget(height_label)
        height_row.addWidget(self.height_slider)
        height_row.addWidget(self.height_value)
        size_layout.addLayout(height_row)
        
        # Add maintain aspect ratio checkbox
        self.aspect_check = QCheckBox("Maintain Aspect Ratio")
        self.aspect_check.setChecked(self.settings.get("maintain_aspect", True))
        size_layout.addWidget(self.aspect_check)
        
        layout.addWidget(size_group)
        
        # Preview section (placeholder)
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Logo Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept_settings)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.apply_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Initialize UI based on settings
        self.toggle_custom_position(self.settings.get("custom_position", False))
    
    def set_position(self, position):
        """Set the logo position"""
        for pos_id, button in self.position_buttons.items():
            button.setChecked(pos_id == position)
            
    def toggle_custom_position(self, enabled):
        """Toggle custom position controls"""
        self.x_spin.setEnabled(enabled)
        self.y_spin.setEnabled(enabled)
        
        # Update button states - disable position buttons if custom is enabled
        for button in self.position_buttons.values():
            button.setEnabled(not enabled)
    
    def get_current_settings(self):
        """Get the current settings from dialog controls"""
        # Determine which position is selected
        selected_position = "top-left"
        for pos_id, button in self.position_buttons.items():
            if button.isChecked():
                selected_position = pos_id
                break
        
        return {
            "logo_position": selected_position,
            "custom_position": self.custom_position_check.isChecked(),
            "x_position": self.x_spin.value(),
            "y_position": self.y_spin.value(),
            "width_percentage": self.width_slider.value(),
            "height_percentage": self.height_slider.value(),
            "maintain_aspect": self.aspect_check.isChecked(),
            "logo_visible": self.settings.get("logo_visible", True)  # Preserve visibility
        }
    
    def apply_settings(self):
        """Apply the current settings without closing dialog"""
        settings = self.get_current_settings()
        
        # Update settings locally
        self.settings = settings
        
        # If parent provided and has the method, update parent settings
        if self.parent and hasattr(self.parent, 'update_logo_settings'):
            self.parent.update_logo_settings(settings)
    
    def accept_settings(self):
        """Save settings and close dialog"""
        self.apply_settings()
        self.accept()

    def show_logo_settings(self):
        """Show dialog to configure logo settings"""
        dialog = LogoSettingsDialog(self, self.logo_settings)
        if dialog.exec_() == QDialog.Accepted:
            print("Logo settings updated and saved")
        
        def update_logo_settings(self, settings):
            """Update logo settings and apply to the logo"""
            # Update local settings
            self.logo_settings = settings
            
            # Update logo visibility
            if hasattr(self, 'logo_label'):
                self.logo_visible = settings.get("logo_visible", True)
                self.logo_label.setVisible(self.logo_visible)
                
                # Update logo position and size
                self.update_logo_display()
            
            # Save settings to file
            self.save_logo_settings()
    
    # Add this simple save_image implementation if you don't have the SaveUtility
    def save_image(self):
        """Save current preview as an image"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            if not os.path.exists(preview_dir):
                os.makedirs(preview_dir)
                
            # Define the output path
            output_path = os.path.join(preview_dir, f"{self.rom_name}_controls.png")
            
            # Check if file already exists
            if os.path.exists(output_path):
                # Ask for confirmation
                if QMessageBox.question(
                    self, 
                    "Confirm Overwrite", 
                    f"Image already exists for {self.rom_name}. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                ) != QMessageBox.Yes:
                    return
            
            # Create a new image with the same size as the canvas
            image = QImage(
                self.canvas.size(),
                QImage.Format_ARGB32
            )
            image.fill(Qt.black)
            
            # Create painter for the image
            painter = QPainter(image)
            
            # Render the canvas to the image
            self.canvas.render(painter)
            
            # End painting
            painter.end()
            
            # Save the image
            if image.save(output_path, "PNG"):
                QMessageBox.information(
                    self,
                    "Success",
                    f"Image saved to:\n{output_path}"
                )
                print(f"Image saved successfully to {output_path}")
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to save image to {output_path}"
                )
                
        except Exception as e:
            print(f"Error saving image: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save image: {str(e)}"
            )

def show_preview(rom_name, game_data, mame_dir):
    """Show the preview window for a specific ROM"""
    # Create and show preview window
    preview = PreviewWindow(rom_name, game_data, mame_dir)
    preview.showFullScreen()  # For a fullscreen experience
    return preview