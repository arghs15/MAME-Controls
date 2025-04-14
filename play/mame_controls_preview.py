import os
import random
import sys
import json
import traceback
from PyQt5.QtWidgets import (QAction, QGridLayout, QMainWindow, QMenu, QMessageBox, QSizePolicy, QSpinBox, QVBoxLayout, QHBoxLayout, QWidget, 
                            QLabel, QPushButton, QFrame, QApplication, QDesktopWidget,
                            QDialog, QGroupBox, QCheckBox, QSlider, QComboBox)
from PyQt5.QtGui import QFontInfo, QImage, QPixmap, QFont, QColor, QPainter, QPen, QFontMetrics
from PyQt5.QtCore import Qt, QPoint, QTimer, QRect, QEvent, QSize

class DraggableLabel(QLabel):
    """An enhanced draggable label with shadow, resizing and better visibility"""
    def __init__(self, text, parent=None, shadow_offset=2, settings=None, initialized_font=None):
        """Initialize the draggable label with enhanced resize behavior"""
        super().__init__(text, parent)
        self.shadow_offset = shadow_offset
        self.settings = settings or {}
        self.initialized_font = initialized_font
        
        # Apply font settings
        self.update_appearance()
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        self.dragging = False
        self.resizing = False
        self.was_resizing = False
        self.offset = QPoint()
        
        # Original position for reset
        self.original_pos = self.pos()
        
        # Original font size
        self.original_font_size = self.settings.get("font_size", 28)
        
        # Size for resize handle
        self.resize_handle_size = 15  # Larger handle area
        
        # Create context menu
        self.setup_context_menu()
        
        # Enable auto-resizing based on content
        self.setWordWrap(True)
        self.adjustSize()
        
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
        # If we have an initialized font, use it directly
        if self.initialized_font:
            self.setFont(self.initialized_font)
            print(f"DraggableLabel using initialized font: {self.initialized_font.family()}")
        else:
            # Standard font creation as fallback
            font_family = self.settings.get("font_family", "Arial")
            font_size = self.settings.get("font_size", 28)
            use_bold = self.settings.get("bold_strength", 2) > 0
            
            font = QFont(font_family, font_size)
            font.setBold(use_bold)
            self.setFont(font)
        
        # Only use stylesheet for color and background 
        self.setStyleSheet("color: white; background-color: transparent; border: none;")
        self.setCursor(Qt.OpenHandCursor)
        
    def update_text(self, text):
        """Update the displayed text, applying uppercase if needed"""
        if self.settings.get("use_uppercase", False):
            text = text.upper()
        self.setText(text)
        
    # Add this to mousePressEvent to store initial position for better resize calculations
    def mousePressEvent(self, event):
        """Handle mouse press events with better resize handling"""
        if event.button() == Qt.LeftButton:
            # Check if we're in the resize corner
            if self.is_in_resize_corner(event.pos()):
                self.resizing = True
                self.last_resize_pos = event.pos()  # Store initial position
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.dragging = True
                self.offset = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
        
    # Completely rewrite the mouseMoveEvent method to directly adjust text size
    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging and resizing with direct size adjustments"""
        # Update cursor when hovering over resize corner
        if not self.dragging and not self.resizing:
            if self.is_in_resize_corner(event.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
        
        # Handle dragging
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.offset)
            self.move(new_pos)
            
            # Notify the parent to update shadow label if it exists
            # Notify the parent to update shadow label if it exists
            if hasattr(self.parent(), "update_shadow_position"):
                self.parent().update_shadow_position(self)
        
        # Handle resizing with direct font size control
        elif self.resizing:
            self.was_resizing = True
            
            # Calculate the relative change based on mouse movement
            delta_x = event.x() - self.last_resize_pos.x() if hasattr(self, 'last_resize_pos') else 0
            delta_y = event.y() - self.last_resize_pos.y() if hasattr(self, 'last_resize_pos') else 0
            
            # Use the larger of horizontal or vertical movement
            delta = max(abs(delta_x), abs(delta_y))
            if (delta_x < 0 or delta_y < 0) and delta > 0:
                delta = -delta  # Make delta negative if shrinking
                
            # Store current position for next move
            self.last_resize_pos = event.pos()
            
            # Get current font and size
            current_font = self.font()
            current_size = current_font.pointSize()
            
            # Adjust size with appropriate sensitivity
            sensitivity = 0.5  # Higher = less sensitive
            new_size = current_size + (delta / sensitivity)
            
            # Enforce min/max limits
            new_size = max(8, min(120, new_size))
            
            # Only update if there's a meaningful change
            if abs(new_size - current_size) >= 0.5:
                # Apply new font size
                rounded_size = int(round(new_size))
                current_font.setPointSize(rounded_size)
                self.setFont(current_font)
                
                # Also resize the label to fit the text
                self.adjustSize()
                
                # Update settings
                if hasattr(self, 'settings'):
                    self.settings["font_size"] = rounded_size
                    print(f"Font size updated to: {rounded_size}")
                
                # Notify the parent to update shadow label if it exists
                if hasattr(self.parent(), "update_shadow_font"):
                    self.parent().update_shadow_font(self)
            
    # Fix the mouseReleaseEvent method in DraggableLabel to properly handle parent navigation
    def mouseReleaseEvent(self, event):
        """Handle mouse release without crashing on parent navigation"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            
            # Update local settings if it was resizing, but don't save to file
            if hasattr(self, 'was_resizing') and self.was_resizing:
                self.was_resizing = False
                current_size = self.font().pointSize()
                
                # Update settings object only
                if hasattr(self, 'settings'):
                    self.settings["font_size"] = current_size
                    
                    # Find the PreviewWindow to update its settings (but not save to file)
                    parent_widget = self.parent()
                    
                    # Check if parent has update_text_settings_no_save method
                    if parent_widget and hasattr(parent_widget, 'update_text_settings_no_save'):
                        parent_widget.update_text_settings_no_save(self.settings)
                        print(f"Font size {current_size} updated in memory (not saved to file)")
                    else:
                        # Try to find the PreviewWindow instance
                        # This is the safe way to navigate up the parent chain
                        preview_window = None
                        current = self.parent()
                        
                        # Safely navigate up the parent hierarchy
                        while current is not None:
                            if hasattr(current, 'update_text_settings_no_save'):
                                preview_window = current
                                break
                            try:
                                # Access the parent attribute, don't call it as a method
                                current = current.parent()
                            except Exception as e:
                                print(f"Error accessing parent: {e}")
                                break
                        
                        # Update settings in memory only if we found the PreviewWindow
                        if preview_window:
                            preview_window.update_text_settings_no_save(self.settings)
                            print(f"Font size {current_size} updated in memory via parent chain")
            
            # Update cursor based on position
            if self.is_in_resize_corner(event.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)
            
    # Add a method to PreviewWindow to update text settings without saving
    def update_text_settings_no_save(self, settings):
        """Update text settings in memory only without saving to file"""
        # Update local settings with merge
        self.text_settings.update(settings)
        
        # Apply to existing controls
        self.apply_text_settings()
        
        print(f"Text settings updated in memory (not saved): {self.text_settings}")
    
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
        
        # Store font file to family name mapping
        self.font_file_to_family = {}
        
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
        
        # Load custom fonts from preview/fonts directory
        if parent and hasattr(parent, 'mame_dir'):
            fonts_dir = os.path.join(parent.mame_dir, "preview", "fonts")
            if os.path.exists(fonts_dir):
                from PyQt5.QtGui import QFontDatabase
                
                print(f"Scanning for fonts in: {fonts_dir}")
                for filename in os.listdir(fonts_dir):
                    if filename.lower().endswith(('.ttf', '.otf')):
                        font_path = os.path.join(fonts_dir, filename)
                        
                        # Load font into QFontDatabase to get proper family name
                        font_id = QFontDatabase.addApplicationFont(font_path)
                        if font_id >= 0:
                            # Get the actual font family names
                            font_families = QFontDatabase.applicationFontFamilies(font_id)
                            if font_families:
                                actual_family = font_families[0]
                                print(f"Loaded font {filename}: family name = {actual_family}")
                                
                                # Add to our fonts list
                                fonts.append(actual_family)
                                
                                # Store mapping from filename to family name
                                base_name = os.path.splitext(filename)[0]
                                self.font_file_to_family[base_name] = actual_family
                            else:
                                print(f"Could not get family name for {filename}")
                        else:
                            print(f"Failed to load font: {filename}")

        self.font_combo.addItems(sorted(fonts))
        
        # Set current font - handle mapping from filename to family if needed
        current_font = self.settings.get("font_family", "Arial")
        if current_font in self.font_file_to_family:
            current_font = self.font_file_to_family[current_font]
            # Update the settings with the proper family name
            self.settings["font_family"] = current_font
        
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

class PreviewWindow(QMainWindow):
    """Window for displaying game controls preview"""
    def __init__(self, rom_name, game_data, mame_dir, parent=None, hide_buttons=False, clean_mode=False, font_registry=None):
        """Enhanced initialization with better logo handling"""
        # Keep the original __init__ code
        super().__init__(parent)

        # Store parameters
        self.rom_name = rom_name
        self.game_data = game_data
        self.mame_dir = mame_dir
        self.control_labels = {}
        self.shadow_labels = {}
        self.bg_label = None
        
        # Add clean preview mode parameters
        self.hide_buttons = hide_buttons
        self.clean_mode = clean_mode
        
        # Print debugging info
        print(f"Initializing PreviewWindow for ROM: {rom_name}")
        print(f"Clean mode: {clean_mode}, Hide buttons: {hide_buttons}")

        # Force window to be displayed in the correct place
        self.parent = parent
        
        try:
            # Load settings
            self.text_settings = self.load_text_settings()
            self.logo_settings = self.load_logo_settings()

            # CRITICAL: Force font loading BEFORE creating labels
            self.load_and_register_fonts()
            
            # NEW: Initialize fonts immediately at startup
            #self.init_fonts()

            # Initialize logo_visible from settings
            self.logo_visible = self.logo_settings.get("logo_visible", True)

            # Configure window
            self.setWindowTitle(f"Control Preview: {rom_name}")
            self.resize(1280, 720)
            
            # Set attributes for proper window handling
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            
            # Create central widget with black background
            self.central_widget = QWidget()
            self.central_widget.setStyleSheet("background-color: black;")
            self.setCentralWidget(self.central_widget)
            
            # Main layout - just holds the canvas, no buttons in this layout
            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create canvas area where the background image and controls will be displayed
            self.canvas = QWidget()
            self.canvas.setStyleSheet("background-color: black;")
            self.main_layout.addWidget(self.canvas, 1)  # 1 stretch factor for most space
            
            # Load the background image
            self.load_background_image_fullscreen()
            
            # Create control labels - WITH clean mode parameter
            self.create_control_labels(clean_mode=self.clean_mode)

            # Make sure the font is properly applied
            self.apply_text_settings()
            
            # Add logo if enabled
            if self.logo_visible:
                self.add_logo()
                
                # NEW: Add a small delay then force logo resize to ensure it applies correctly
                QTimer.singleShot(100, self.force_logo_resize)
            
            # Create button frame as a FLOATING OVERLAY
            if not self.hide_buttons and not self.clean_mode:
                self.create_floating_button_frame()
            
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
            self.layering_for_bezel()
            self.integrate_bezel_support()
            self.canvas.resizeEvent = self.on_canvas_resize_with_background
        
            # Add this line to initialize bezel state after a short delay
            QTimer.singleShot(500, self.ensure_bezel_state)
            
            print("PreviewWindow initialization complete")
            
            QTimer.singleShot(600, self.apply_joystick_visibility)
            QTimer.singleShot(200, self.load_and_register_fonts)
            
        except Exception as e:
            print(f"Error in PreviewWindow initialization: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error initializing preview: {e}")
            self.close()

    def load_and_register_fonts(self):
        """Load and register fonts from settings at startup"""
        from PyQt5.QtGui import QFontDatabase, QFont, QFontInfo
        
        print("\n=== LOADING FONTS ===")
        # Get requested font from settings
        font_family = self.text_settings.get("font_family", "Arial")
        font_size = self.text_settings.get("font_size", 28)
        bold_strength = self.text_settings.get("bold_strength", 2)
        
        print(f"Target font from settings: {font_family}")
        
        # 1. First try to load from custom fonts directory
        fonts_dir = os.path.join(self.mame_dir, "preview", "fonts")
        font_found = False
        exact_family_name = None
        
        if os.path.exists(fonts_dir):
            print(f"Scanning fonts directory: {fonts_dir}")
            for filename in os.listdir(fonts_dir):
                if filename.lower().endswith(('.ttf', '.otf')):
                    # Check if filename matches our target font
                    base_name = os.path.splitext(filename)[0].lower()
                    name_match = (
                        base_name == font_family.lower() or 
                        font_family.lower() in base_name or 
                        base_name in font_family.lower()
                    )
                    
                    if name_match:
                        font_path = os.path.join(fonts_dir, filename)
                        print(f"MATCH FOUND! Loading font: {font_path}")
                        
                        # Register the font
                        font_id = QFontDatabase.addApplicationFont(font_path)
                        if font_id >= 0:
                            families = QFontDatabase.applicationFontFamilies(font_id)
                            if families and len(families) > 0:
                                exact_family_name = families[0]
                                print(f"*** FONT LOADED SUCCESSFULLY: {exact_family_name} ***")
                                font_found = True
                                break
        
        # 2. If no custom font found, try system fonts
        if not font_found:
            # For system fonts, just use the family name directly
            exact_family_name = font_family
            print(f"Using system font: {exact_family_name}")
        
        # 3. Store the font information
        self.font_name = exact_family_name or font_family
        
        # 4. Create the actual font object
        self.current_font = QFont(self.font_name, font_size)
        self.current_font.setBold(bold_strength > 0)
        
        # 5. Force exact matching - this is critical (CORRECTED)
        self.current_font.setStyleStrategy(QFont.PreferMatch)
        
        # Print font diagnostic info
        info = QFontInfo(self.current_font)
        print(f"Created font object: {self.font_name}")
        print(f"Weight: {self.current_font.weight()}, Size: {self.current_font.pointSize()}")
        print(f"Actual family being used: {info.family()}")
        print("=== FONT LOADING COMPLETE ===\n")
        
        # Apply the font to existing controls if any
        self.apply_current_font_to_controls()
    
    def apply_current_font_to_controls(self):
        """Apply the current font to all control labels"""
        if not hasattr(self, 'current_font'):
            print("No current font to apply")
            return
            
        if not hasattr(self, 'control_labels'):
            print("No controls to apply font to")
            return
            
        print(f"Applying font {self.current_font.family()} to {len(self.control_labels)} controls")
        for control_name, control_data in self.control_labels.items():
            if 'label' in control_data and control_data['label']:
                label = control_data['label']
                label.setFont(self.current_font)
                
                # Also update shadow
                if control_name in self.shadow_labels:
                    shadow = self.shadow_labels[control_name]
                    shadow.setFont(self.current_font)
                    
        print("Font applied to all controls")
    
    def init_fonts(self):
        """Initialize and preload fonts at startup to ensure they're available throughout the session"""
        from PyQt5.QtGui import QFontDatabase, QFont
        
        print("\n--- INITIALIZING FONTS ---")
        # Get requested font from settings
        font_family = self.text_settings.get("font_family", "Arial")
        font_size = self.text_settings.get("font_size", 28)
        
        # 1. First try to load the exact font file if it's a known system font
        system_font_map = {
            "Times New Roman": "times.ttf",
            "Impact": "impact.ttf",
            "Courier New": "cour.ttf",
            "Comic Sans MS": "comic.ttf",
            "Georgia": "georgia.ttf",
            "Arial": "arial.ttf",
            "Verdana": "verdana.ttf",
            "Tahoma": "tahoma.ttf",
            "Calibri": "calibri.ttf"
        }
        
        # Store the actual font family name loaded
        self.initialized_font_family = None
        
        if font_family in system_font_map:
            font_file = system_font_map[font_family]
            font_path = os.path.join("C:\\Windows\\Fonts", font_file)
            
            if os.path.exists(font_path):
                print(f"Preloading system font: {font_path}")
                font_id = QFontDatabase.addApplicationFont(font_path)
                
                if font_id >= 0:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        self.initialized_font_family = families[0]
                        print(f"System font loaded and registered as: {self.initialized_font_family}")
        
        # 2. Check for custom fonts if we couldn't load a system font
        if not self.initialized_font_family:
            fonts_dir = os.path.join(self.mame_dir, "preview", "fonts")
            if os.path.exists(fonts_dir):
                # Try to find a matching font file
                for filename in os.listdir(fonts_dir):
                    if filename.lower().endswith(('.ttf', '.otf')):
                        base_name = os.path.splitext(filename)[0]
                        
                        # Check if this might be the font we're looking for
                        if (base_name.lower() == font_family.lower() or
                            font_family.lower() in base_name.lower()):
                            
                            font_path = os.path.join(fonts_dir, filename)
                            print(f"Trying to load custom font: {font_path}")
                            
                            font_id = QFontDatabase.addApplicationFont(font_path)
                            if font_id >= 0:
                                families = QFontDatabase.applicationFontFamilies(font_id)
                                if families:
                                    self.initialized_font_family = families[0]
                                    print(f"Custom font loaded and registered as: {self.initialized_font_family}")
                                    break
        
        # Create a proper QFont with the exact family name
        if self.initialized_font_family:
            # Store the font for future use
            self.initialized_font = QFont(self.initialized_font_family, font_size)
            self.initialized_font.setBold(self.text_settings.get("bold_strength", 2) > 0)
            self.initialized_font.setStyleStrategy(QFont.PreferMatch)
            
            print(f"Initialized font: {self.initialized_font_family} at size {font_size}")
        else:
            print(f"Could not initialize font: {font_family}. Will fallback to system handling.")
        
        print("--- FONT INITIALIZATION COMPLETE ---\n")

    def create_floating_button_frame(self):
        """Create clean, simple floating button frame with Tkinter-like styling"""
        # Create a floating button frame
        self.button_frame = QFrame(self)
        
        # Simple, clean styling with no border
        self.button_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 45, 200);
                border-radius: 8px;
                border: none;
            }
        """)
        
        # Adjust height for single row of buttons
        self.button_frame.setFixedHeight(50)
        
        # Add layout to button frame with better spacing
        self.button_layout = QHBoxLayout(self.button_frame)
        self.button_layout.setContentsMargins(10, 5, 10, 5)
        self.button_layout.setSpacing(8)
        
        # Clean, Tkinter-like button style
        button_style = """
            QPushButton {
                background-color: #404050;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #555565;
            }
            QPushButton:pressed {
                background-color: #303040;
            }
        """
        
        # Create a single row of essential buttons (minimize the number of buttons)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.close_button)
        
        '''self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_positions)
        self.reset_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.reset_button)'''
        
        self.save_button = QPushButton("Global Save")
        self.save_button.clicked.connect(lambda: self.save_positions(is_global=True))
        self.save_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.save_button)

        self.rom_button = QPushButton("ROM Save")
        self.rom_button.clicked.connect(lambda: self.save_positions(is_global=False))
        self.rom_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.rom_button)

        self.text_settings_button = QPushButton("Text Settings")
        self.text_settings_button.clicked.connect(self.show_text_settings)
        self.text_settings_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.text_settings_button)

        self.xinput_controls_button = QPushButton("Show All XInput")
        self.xinput_controls_button.clicked.connect(self.toggle_xinput_controls)
        self.xinput_controls_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.xinput_controls_button)
        
        self.toggle_texts_button = QPushButton("Hide Texts")
        self.toggle_texts_button.clicked.connect(self.toggle_texts)
        self.toggle_texts_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.toggle_texts_button)
        
        self.joystick_button = QPushButton("Joystick")
        self.joystick_button.clicked.connect(self.toggle_joystick_controls)
        self.joystick_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.joystick_button)
        
        # Logo toggle
        logo_text = "Hide Logo" if self.logo_visible else "Show Logo"
        self.logo_button = QPushButton(logo_text)
        self.logo_button.clicked.connect(self.toggle_logo)
        self.logo_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.logo_button)
        
        # Screen toggle with number indicator
        self.screen_button = QPushButton(f"Screen {getattr(self, 'current_screen', 1)}")
        self.screen_button.clicked.connect(self.toggle_screen)
        self.screen_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.screen_button)
        
        # Add save image button
        self.save_image_button = QPushButton("Save Image")
        self.save_image_button.clicked.connect(self.save_image)
        self.save_image_button.setStyleSheet(button_style)
        self.button_layout.addWidget(self.save_image_button)
        
        # Determine button frame position
        self.position_button_frame()
        
        # Show button frame
        self.button_frame.show()
        
        # Setup resize handler to reposition button frame
        self.resizeEvent = self.on_resize_with_buttons

    def position_button_frame(self):
        """Position the button frame at the bottom of the window"""
        if hasattr(self, 'button_frame'):
            # Calculate width and position - with int conversion
            frame_width = int(min(1000, self.width() * 0.9))  # 90% of window width, max 1000px
            x_pos = (self.width() - frame_width) // 2
            y_pos = self.height() - self.button_frame.height() - 20  # 20px from bottom
            
            # Set width and position
            self.button_frame.setFixedWidth(frame_width)
            self.button_frame.move(x_pos, y_pos)

    # 4. Override the resize event to reposition the button frame

    def on_resize_with_buttons(self, event):
        """Handle resize events and reposition the button frame"""
        # Let the normal resize event happen first
        super().resizeEvent(event)
        
        # Reposition the button frame
        self.position_button_frame()
        
        # Also handle bezel resizing if needed
        if hasattr(self, 'on_resize_with_bezel'):
            self.on_resize_with_bezel(event)
    
    # Add this to the PreviewWindow class
    def ensure_bezel_state(self):
        """Ensure bezel visibility state matches settings"""
        if not hasattr(self, 'has_bezel') or not self.has_bezel:
            return
            
        # Make sure bezel is shown if it should be based on settings
        if self.bezel_visible and (not hasattr(self, 'bezel_label') or not self.bezel_label or not self.bezel_label.isVisible()):
            self.show_bezel_with_background()
            print("Ensuring bezel is visible based on settings")
            
        # Update button text
        if hasattr(self, 'bezel_button'):
            self.bezel_button.setText("Hide Bezel" if self.bezel_visible else "Show Bezel")
    
    # Add this method to the PreviewWindow class in mame_controls_preview.py
    def ensure_consistent_text_positioning(self):
        """
        Ensure text positioning is consistent across all display methods.
        Call this after creating control labels.
        """
        # Apply standard positioning logic to all labels
        for control_name, control_data in self.control_labels.items():
            label = control_data['label']
            shadow = self.shadow_labels[control_name]
            
            # Ensure shadow is exactly 2px offset from main label
            shadow.move(label.pos().x() + 2, label.pos().y() + 2)
        
        print("Applied consistent text positioning to all controls")
    
    # Add bezel-related attributes and initial setup to __init__
    def add_bezel_support_to_init(self):
        """Initialize bezel-related attributes"""
        # Add bezel attributes
        self.bezel_visible = False
        self.bezel_label = None
        self.has_bezel = False
        
        # Add a button for toggling bezel visibility
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
        
        # Create bezel toggle button
        self.bezel_button = QPushButton("Show Bezel")
        self.bezel_button.clicked.connect(self.toggle_bezel_improved)
        self.bezel_button.setStyleSheet(button_style)
        
        # Add to the bottom row if it exists
        if hasattr(self, 'bottom_row'):
            self.bottom_row.addWidget(self.bezel_button)
        
        # Check if a bezel exists for this ROM
        bezel_path = self.find_bezel_path(self.rom_name)
        self.has_bezel = bezel_path is not None
        
        # Update button state
        self.bezel_button.setEnabled(self.has_bezel)
        if not self.has_bezel:
            self.bezel_button.setText("No Bezel")
            self.bezel_button.setToolTip(f"No bezel found for {self.rom_name}")
        else:
            self.bezel_button.setToolTip(f"Toggle bezel visibility: {bezel_path}")

    # Replace toggle_bezel_improved to always save global settings
    def toggle_bezel_improved(self):
        """Toggle bezel visibility and save the setting globally"""
        if not self.has_bezel:
            print("No bezel available to toggle")
            return
        
        # Toggle visibility flag
        self.bezel_visible = not self.bezel_visible
        
        # Update button text
        self.bezel_button.setText("Hide Bezel" if self.bezel_visible else "Show Bezel")
        
        # Show or hide bezel
        if self.bezel_visible:
            self.show_bezel_with_background()
            print(f"Bezel visibility is now: {self.bezel_visible}")
        else:
            if hasattr(self, 'bezel_label') and self.bezel_label:
                self.bezel_label.hide()
                print("Bezel hidden")
        
        # Always raise controls to top
        self.raise_controls_above_bezel()
        
        # ALWAYS save as global settings
        self.save_bezel_settings(is_global=True)
        print(f"Saved bezel visibility ({self.bezel_visible}) to GLOBAL settings")
    
    # Add method to find bezel path
    def find_bezel_path(self, rom_name):
        """Find bezel image path for a ROM name"""
        # Define possible locations for bezels
        possible_paths = [
            # Main artwork path with Bezel.png naming convention
            os.path.join(self.mame_dir, "artwork", rom_name, "Bezel.png"),
            
            # Alternative locations and naming conventions
            os.path.join(self.mame_dir, "artwork", rom_name, "bezel.png"),
            os.path.join(self.mame_dir, "artwork", rom_name, f"{rom_name}_bezel.png"),
            os.path.join(self.mame_dir, "bezels", f"{rom_name}.png"),
            os.path.join(self.mame_dir, "bezels", f"{rom_name}_bezel.png"),
            
            # Parent directory with artwork subfolder
            os.path.join(os.path.dirname(self.mame_dir), "artwork", rom_name, "Bezel.png"),
        ]
        
        # Check each possible path
        for path in possible_paths:
            if os.path.exists(path):
                print(f"Found bezel at: {path}")
                return path
        
        print(f"No bezel found for {rom_name}")
        return None

    # Replace the toggle_bezel_improved method to ensure the bezel is properly shown
    # Replace toggle_bezel_improved to save settings when toggled
    def add_global_bezel_button(self):
        """Add a button to save current bezel state as global default"""
        # Button style (reuse existing style)
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
        
        # Create button
        self.global_bezel_button = QPushButton("Global Bezel")
        self.global_bezel_button.clicked.connect(lambda: self.save_bezel_settings(is_global=True))
        self.global_bezel_button.setStyleSheet(button_style)
        self.global_bezel_button.setToolTip("Save current bezel visibility as global default")
        
        # Add to bottom row if it exists
        if hasattr(self, 'bottom_row'):
            self.bottom_row.addWidget(self.global_bezel_button)

    # Replace the show_bezel_with_background method for better bezel display
    def show_bezel_with_background(self):
        """Display bezel while preserving background with proper layering"""
        # Find bezel path
        bezel_path = self.find_bezel_path(self.rom_name)
        if not bezel_path:
            print("Cannot show bezel: no bezel image found")
            return
        
        try:
            print("\n--- Showing bezel with proper layering ---")
            
            # Create or recreate bezel label
            if hasattr(self, 'bezel_label') and self.bezel_label:
                self.bezel_label.deleteLater()
            
            # Create a fresh bezel label on the canvas
            self.bezel_label = QLabel(self.canvas)
            
            # Load bezel image
            self.original_bezel_pixmap = QPixmap(bezel_path)
            if self.original_bezel_pixmap.isNull():
                print(f"Error loading bezel image from {bezel_path}")
                self.bezel_visible = False
                return
            
            # Resize bezel to match window while preserving aspect ratio
            window_width = self.canvas.width()
            window_height = self.canvas.height()
            
            # Scale with high quality
            bezel_pixmap = self.original_bezel_pixmap.scaled(
                window_width,
                window_height,
                Qt.KeepAspectRatio,  # Keep aspect ratio
                Qt.SmoothTransformation  # High quality scaling
            )
            
            # Store this for saving to image later
            self.bezel_pixmap = bezel_pixmap
            
            # Set up the bezel label
            self.bezel_label.setPixmap(bezel_pixmap)
            
            # Position bezel in center
            x = (window_width - bezel_pixmap.width()) // 2
            y = (window_height - bezel_pixmap.height()) // 2
            self.bezel_label.setGeometry(x, y, bezel_pixmap.width(), bezel_pixmap.height())
            
            # CRITICAL: Make bezel transparent
            self.bezel_label.setStyleSheet("background-color: transparent;")
            
            # CRITICAL LAYERING FIX: First lower the bezel behind everything
            self.bezel_label.lower()
            
            # Then, if we have a background, make sure bezel is ABOVE background but BELOW other controls
            if hasattr(self, 'bg_label') and self.bg_label:
                # Print current widget stacking info
                print(f"Background exists: {self.bg_label.isVisible()}")
                
                # First lower background to bottom
                self.bg_label.lower()
                
                # Then raise bezel above background
                self.bezel_label.stackUnder(self.bg_label)
                self.bezel_label.raise_()
                
                print("Fixed layering: Background -> Bezel -> Other elements")
            
            # Make sure the bezel is visible
            self.bezel_label.show()
            self.bezel_visible = True
            
            # Now raise all controls above bezel
            self.raise_controls_above_bezel()
            
            print(f"Bezel displayed: {bezel_pixmap.width()}x{bezel_pixmap.height()} at ({x},{y})")
            print(f"Bezel visibility is set to: {self.bezel_visible}")
            
        except Exception as e:
            print(f"Error showing bezel: {e}")
            import traceback
            traceback.print_exc()
            self.bezel_visible = False
            
    # Improved method to raise controls above bezel
    def raise_controls_above_bezel(self):
        """Ensure all controls are above the bezel with proper debug info"""
        print("\n--- Applying proper stacking order ---")
        
        if not hasattr(self, 'bezel_label') or not self.bezel_label:
            print("No bezel label exists to stack controls above")
            return
        
        # First make sure background is at the bottom
        if hasattr(self, 'bg_label') and self.bg_label:
            self.bg_label.lower()
            print("Lowered background to bottom layer")
        
        # Then place bezel above background
        self.bezel_label.lower()  # First lower it all the way down
        if hasattr(self, 'bg_label') and self.bg_label:
            self.bezel_label.stackUnder(self.bg_label)  # Then stack under background
            self.bezel_label.raise_()  # Then raise above background
            print("Positioned bezel above background")
        
        # Raise all shadow labels above bezel but below real labels
        if hasattr(self, 'shadow_labels'):
            for shadow_label in self.shadow_labels.values():
                if shadow_label.isVisible():
                    shadow_label.raise_()
            print(f"Raised {len(self.shadow_labels)} shadow labels above bezel")
        
        # Raise all control labels to the top
        if hasattr(self, 'control_labels'):
            for control_data in self.control_labels.values():
                if 'label' in control_data and control_data['label'] and control_data['label'].isVisible():
                    control_data['label'].raise_()
            print(f"Raised {len(self.control_labels)} control labels to top")
        
        # Raise logo if it exists (should be on top of bezel but below controls)
        if hasattr(self, 'logo_label') and self.logo_label and self.logo_label.isVisible():
            self.logo_label.raise_()
            print("Raised logo above bezel")
        
        print("Final stack order: Background -> Bezel -> Shadows/Logo -> Controls")
    
    # Make sure the bezel is properly layered in window setup
    def layering_for_bezel(self):
        """Setup proper layering for bezel display"""
        # If we have a bezel, ensure proper layering at startup
        if hasattr(self, 'has_bezel') and self.has_bezel:
            # Make sure background label exists and is on top of bezel
            if hasattr(self, 'bg_label') and self.bg_label:
                self.bg_label.raise_()
            
            # Make sure logo is on top if it exists
            if hasattr(self, 'logo_label') and self.logo_label:
                self.logo_label.raise_()
            
            # Make sure all control labels are on top
            if hasattr(self, 'control_labels'):
                for control_data in self.control_labels.values():
                    if 'label' in control_data and control_data['label']:
                        control_data['label'].raise_()
                    if 'shadow' in control_data and control_data['shadow']:
                        control_data['shadow'].raise_()
            
            print("Layering setup for bezel display")
    
    # Replace integrate_bezel_support to load from settings
    # Update integrate_bezel_support to initialize joystick visibility
    def integrate_bezel_support(self):
        """Add bezel support with joystick visibility settings"""
        # Initialize with defaults
        self.bezel_label = None
        self.has_bezel = False
        
        # Load bezel and joystick settings
        bezel_settings = self.load_bezel_settings()
        self.bezel_visible = bezel_settings.get("bezel_visible", False)
        self.joystick_visible = bezel_settings.get("joystick_visible", True)  # Default to visible
        print(f"Loaded bezel visibility: {self.bezel_visible}, joystick visibility: {self.joystick_visible}")
        
        # [Rest of the original method]
        # Add button style (reuse existing style)
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
        
        # Create bezel toggle button
        self.bezel_button = QPushButton("Show Bezel")
        self.bezel_button.clicked.connect(self.toggle_bezel_improved)
        self.bezel_button.setStyleSheet(button_style)
        
        # Add to the bottom row
        if hasattr(self, 'bottom_row'):
            self.bottom_row.addWidget(self.bezel_button)
        elif hasattr(self, 'button_layout'):
            self.button_layout.addWidget(self.bezel_button)
        
        # Check if a bezel exists for this ROM
        bezel_path = self.find_bezel_path(self.rom_name)
        self.has_bezel = bezel_path is not None
        
        # Update button state
        self.bezel_button.setEnabled(self.has_bezel)
        
        if not self.has_bezel:
            self.bezel_button.setText("No Bezel")
            self.bezel_button.setToolTip(f"No bezel found for {self.rom_name}")
        else:
            # Set initial button text based on visibility setting
            self.bezel_button.setText("Hide Bezel" if self.bezel_visible else "Show Bezel")
            self.bezel_button.setToolTip(f"Toggle bezel visibility: {bezel_path}")
            print(f"Bezel available at: {bezel_path}")
            
            # If bezel should be visible based on settings, show it
            if self.bezel_visible:
                # Use a small delay to ensure the canvas is fully initialized
                QTimer.singleShot(100, self.show_bezel_with_background)
                print("Bezel initialized as visible based on settings")
    
    # Improved show_all_xinput_controls method that avoids duplicates
    def show_all_xinput_controls(self):
        """Show all possible P1 XInput controls for global positioning without duplicates"""
        # Standard XInput controls for positioning - P1 ONLY
        xinput_controls = {
            "P1_JOYSTICK_UP": "Left Stick Up",
            "P1_JOYSTICK_DOWN": "Left Stick Down",
            "P1_JOYSTICK_LEFT": "Left Stick Left",
            "P1_JOYSTICK_RIGHT": "Left Stick Right",
            "P1_JOYSTICK2_UP": "Right Stick Up",
            "P1_JOYSTICK2_DOWN": "Right Stick Down",
            "P1_JOYSTICK2_LEFT": "Right Stick Left",
            "P1_JOYSTICK2_RIGHT": "Right Stick Right",
            "P1_BUTTON1": "A Button",
            "P1_BUTTON2": "B Button",
            "P1_BUTTON3": "X Button",
            "P1_BUTTON4": "Y Button",
            "P1_BUTTON5": "Left Bumper",
            "P1_BUTTON6": "Right Bumper",
            "P1_BUTTON7": "Left Trigger",
            "P1_BUTTON8": "Right Trigger",
            "P1_BUTTON9": "Left Stick Button",
            "P1_BUTTON10": "Right Stick Button",
            "P1_START": "Start Button",
            "P1_SELECT": "Back Button",
            # All P2 controls removed
        }
        
        try:
            print("\n--- Showing all P1 XInput controls for positioning ---")
            
            # Save existing control positions
            if not hasattr(self, 'original_controls_backup'):
                self.original_controls_backup = {}
                for control_name, control_data in self.control_labels.items():
                    self.original_controls_backup[control_name] = {
                        'action': control_data['action'],
                        'position': control_data['label'].pos(),
                        'original_pos': control_data.get('original_pos', QPoint(0, 0))
                    }
                print(f"Backed up {len(self.original_controls_backup)} original controls")
            
            # Get canvas dimensions for positioning
            canvas_width = self.canvas.width()
            canvas_height = self.canvas.height()
            
            # Clear ALL existing controls first
            for control_name in list(self.control_labels.keys()):
                # Remove the control from the canvas
                if control_name in self.control_labels:
                    self.control_labels[control_name]['label'].deleteLater()
                    del self.control_labels[control_name]
                if control_name in self.shadow_labels:
                    self.shadow_labels[control_name].deleteLater()
                    del self.shadow_labels[control_name]
            
            # Clear collections
            self.control_labels = {}
            self.shadow_labels = {}
            print("Cleared all existing controls")
            
            # Default grid layout
            grid_x, grid_y = 0, 0
            
            # Apply text settings
            y_offset = self.text_settings.get("y_offset", -40)
            
            # Create all P1 XInput controls
            for control_name, action_text in xinput_controls.items():
                # Apply text settings - uppercase if enabled
                if self.text_settings.get("use_uppercase", False):
                    action_text = action_text.upper()
                
                # Check if we have a saved position for this control
                saved_position = None
                if control_name in self.original_controls_backup:
                    saved_position = self.original_controls_backup[control_name]['position']
                
                # Create a draggable label with current text settings
                label = DraggableLabel(action_text, self.canvas, settings=self.text_settings)
                
                # Create shadow effect for better visibility
                shadow_label = QLabel(action_text, self.canvas)
                shadow_label.setStyleSheet("color: black; background-color: transparent; border: none;")
                
                # Copy font settings from main label
                shadow_label.setFont(label.font())
                
                if saved_position:
                    # Use the saved position
                    x, y = saved_position.x(), saved_position.y()
                    # Use original position without offset for reset
                    original_pos = self.original_controls_backup[control_name]['original_pos']
                else:
                    # Use default grid position
                    x = 100 + (grid_x * 150)
                    y = 100 + (grid_y * 40)
                    
                    # Apply y-offset from text settings
                    y += y_offset
                    
                    # Store original position without offset
                    original_pos = QPoint(x, y - y_offset)
                    
                    # Update grid position
                    grid_x = (grid_x + 1) % 5
                    if grid_x == 0:
                        grid_y += 1
                
                # Position the labels - shadow goes behind
                shadow_label.move(x + 2, y + 2)  # Shadow offset
                label.move(x, y)
                
                # Make shadow label go behind the main label
                shadow_label.lower()
                
                # Store the labels
                self.control_labels[control_name] = {
                    'label': label,
                    'shadow': shadow_label,
                    'action': action_text,
                    'original_pos': original_pos  # Store without offset for reset
                }
                
                # Store shadow label separately for convenience
                self.shadow_labels[control_name] = shadow_label
                
                # Connect position update for shadow
                original_mouseMoveEvent = label.mouseMoveEvent
                label.mouseMoveEvent = lambda event, label=label, shadow=shadow_label, orig_func=original_mouseMoveEvent: self.on_label_move(event, label, shadow, orig_func)
                
                # Show control (respect joystick visibility)
                is_visible = True
                if "JOYSTICK" in control_name and hasattr(self, 'joystick_visible'):
                    is_visible = self.joystick_visible
                
                label.setVisible(is_visible)
                shadow_label.setVisible(is_visible)
            
            # Update button to allow going back to regular mode
            if hasattr(self, 'xinput_controls_button'):
                self.xinput_controls_button.setText("Normal Controls")
            
            # Set flag to indicate we're in XInput mode
            self.showing_all_xinput_controls = True
            
            print(f"Created and displayed {len(xinput_controls)} P1 XInput controls for positioning")
            return True
            
        except Exception as e:
            print(f"Error showing XInput controls: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Improved toggle_xinput_controls method that restores original controls properly
    def toggle_xinput_controls(self):
        """Toggle between normal game controls and all XInput controls"""
        # Check if already showing all XInput controls
        if hasattr(self, 'showing_all_xinput_controls') and self.showing_all_xinput_controls:
            # Switch back to normal game controls
            self.showing_all_xinput_controls = False
            
            # CRITICAL FIX: Clear all current controls
            for control_name in list(self.control_labels.keys()):
                # Remove the control from the canvas
                if control_name in self.control_labels:
                    self.control_labels[control_name]['label'].deleteLater()
                    del self.control_labels[control_name]
                if control_name in self.shadow_labels:
                    self.shadow_labels[control_name].deleteLater()
                    del self.shadow_labels[control_name]
            
            # Clear collections
            self.control_labels = {}
            self.shadow_labels = {}
            
            # Update button text
            if hasattr(self, 'xinput_controls_button'):
                self.xinput_controls_button.setText("Show All XInput")
            
            # Reload the current game controls from scratch
            self.create_control_labels()
            
            print("Switched back to normal game controls")
        else:
            # Switch to showing all XInput controls
            self.show_all_xinput_controls()

    # New method to force apply joystick visibility
    def apply_joystick_visibility(self):
        """Force apply joystick visibility settings to all controls"""
        controls_updated = 0
        
        for control_name, control_data in self.control_labels.items():
            if "JOYSTICK" in control_name:
                is_visible = self.texts_visible and self.joystick_visible
                
                # Only update if needed
                if control_data['label'].isVisible() != is_visible:
                    control_data['label'].setVisible(is_visible)
                    self.shadow_labels[control_name].setVisible(is_visible)
                    controls_updated += 1
        
        print(f"Applied joystick visibility ({self.joystick_visible}) to {controls_updated} controls")
        return controls_updated

    # Call this at the end of PreviewWindow.__init__
    def init_joystick_delayed(self):
        """Set up a delayed joystick visibility initialization"""
        # After UI is fully initialized, apply joystick visibility
        QTimer.singleShot(600, self.apply_joystick_visibility)
        print("Scheduled delayed joystick visibility application")
    
    # Add method to initialize joystick visibility during startup
    def initialize_joystick_visibility(self):
        """Apply joystick visibility setting to controls"""
        # Make sure joystick_visible is initialized
        if not hasattr(self, 'joystick_visible'):
            # Try to load from settings
            bezel_settings = self.load_bezel_settings()
            self.joystick_visible = bezel_settings.get("joystick_visible", True)
        
        # Update joystick button text if it exists
        if hasattr(self, 'joystick_button'):
            self.joystick_button.setText("Show Joystick" if not self.joystick_visible else "Hide Joystick")
        
        # Apply visibility to joystick controls
        for control_name, control_data in self.control_labels.items():
            if "JOYSTICK" in control_name:
                is_visible = self.texts_visible and self.joystick_visible
                control_data['label'].setVisible(is_visible)
                self.shadow_labels[control_name].setVisible(is_visible)
        
        print(f"Initialized joystick visibility to: {self.joystick_visible}")

    # Add this to the button_frame creation in __init__
    def add_xinput_controls_button(self):
        """Add a button to show all XInput controls"""
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
        
        # Create button for XInput controls toggle
        '''self.xinput_controls_button = QPushButton("Show All XInput")
        self.xinput_controls_button.clicked.connect(self.toggle_xinput_controls)
        self.xinput_controls_button.setStyleSheet(button_style)
        self.button_layout.setToolTip("Show all XInput controls for positioning")'''
        
        # Add to bottom row if it exists
        if hasattr(self, 'bottom_row'):
            self.bottom_row.addWidget(self.xinput_controls_button)
    
    # Add method to hide bezel
    def hide_bezel(self):
        """Hide the bezel image"""
        if self.bezel_label:
            self.bezel_label.hide()
            print("Bezel hidden")

    # Update resizeEvent to handle bezel resizing
    def on_resize_with_bezel(self, event):
        """Handle resize events with bezel support"""
        # Call the original resize handler first
        if hasattr(self, 'on_canvas_resize'):
            self.on_canvas_resize_original = self.on_canvas_resize
        self.canvas.resizeEvent = self.on_canvas_resize_with_background
        # Update bezel size if it exists and is visible
        if hasattr(self, 'bezel_visible') and self.bezel_visible and hasattr(self, 'bezel_label') and self.bezel_label:
            window_width = self.width()
            window_height = self.height()
            
            # Resize bezel to match window
            if hasattr(self.bezel_label, 'pixmap') and self.bezel_label.pixmap() and not self.bezel_label.pixmap().isNull():
                # Get the original pixmap
                original_pixmap = self.bezel_label.pixmap()
                
                # When scaling background or bezel images
                scaled_pixmap = original_pixmap.scaled(
                    self.canvas.width(),
                    self.canvas.height(),
                    Qt.IgnoreAspectRatio,  # This forces it to fill the entire space
                    Qt.SmoothTransformation
                )
                self.bezel_label.setPixmap(scaled_pixmap)
                self.bezel_label.setGeometry(0, 0, window_width, window_height)
                
                print(f"Bezel resized to {window_width}x{window_height}")
    
    # Add a force resize button to the UI
    def add_force_resize_button(self):
        """Add a button to force logo resize"""
        if hasattr(self, 'bottom_row'):
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
            
            self.resize_logo_button = QPushButton("Fix Logo")
            self.resize_logo_button.clicked.connect(self.force_logo_resize)
            self.resize_logo_button.setStyleSheet(button_style)
            self.resize_logo_button.setToolTip("Force logo to resize to stored settings")
            
            # Add to your bottom row layout
            self.bottom_row.addWidget(self.resize_logo_button)
    
    # Add helper method to explicitly save global text settings
    def save_global_text_settings(self):
        """Save current text settings as global defaults"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Save to global settings file
            global_settings_file = os.path.join(preview_dir, "global_text_settings.json")
            
            with open(global_settings_file, 'w') as f:
                json.dump(self.text_settings, f)
            print(f"Saved GLOBAL text settings to {global_settings_file}: {self.text_settings}")
            
            # Optional - show a confirmation message
            QMessageBox.information(self, "Settings Saved", 
                                "Text settings have been saved as global defaults.")
        except Exception as e:
            print(f"Error saving global text settings: {e}")
            import traceback
            traceback.print_exc()
    
    # Add a global button to save text settings
    def add_global_text_settings_button(self):
        """Add a button to save text settings as global defaults"""
        # Button style (reusing existing style)
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
        
        # Create button
        self.global_text_button = QPushButton("Global Text")
        self.global_text_button.clicked.connect(self.save_global_text_settings)
        self.global_text_button.setStyleSheet(button_style)
        
        # Add to bottom row if it exists
        if hasattr(self, 'bottom_row'):
            self.bottom_row.addWidget(self.global_text_button)
    
    # Add a new method to load bezel settings
    # Update load_bezel_settings to prioritize global settings
    # Update load_bezel_settings to include joystick visibility
    def load_bezel_settings(self):
        """Load bezel and joystick visibility settings from file"""
        settings = {
            "bezel_visible": False,  # Default to hidden
            "joystick_visible": True  # Default to visible
        }
        
        try:
            # Check for GLOBAL settings first
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            global_settings_file = os.path.join(preview_dir, "global_bezel.json")
            rom_settings_file = os.path.join(preview_dir, f"{self.rom_name}_bezel.json")
            
            # FIRST check for global settings (priority)
            if os.path.exists(global_settings_file):
                with open(global_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded global bezel/joystick settings: {settings}")
            
            # OPTIONALLY fall back to ROM-specific (if you want to keep this behavior)
            elif os.path.exists(rom_settings_file):
                with open(rom_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded ROM-specific bezel/joystick settings for {self.rom_name}: {settings}")
        except Exception as e:
            print(f"Error loading bezel/joystick settings: {e}")
        
        return settings

    # Add method to save bezel settings
    def save_bezel_settings(self, is_global=True):
        """Save bezel and joystick visibility settings to file"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Determine file path based on global flag
            if is_global:
                settings_file = os.path.join(preview_dir, "global_bezel.json")
            else:
                settings_file = os.path.join(preview_dir, f"{self.rom_name}_bezel.json")
            
            # Create settings object
            settings = {
                "bezel_visible": self.bezel_visible,
                "joystick_visible": getattr(self, 'joystick_visible', True)  # Default to True if not set
            }
            
            # Save settings
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
                
            # Show message if global
            if is_global:
                print(f"Saved GLOBAL bezel/joystick settings to {settings_file}: {settings}")
                QMessageBox.information(
                    self,
                    "Global Settings Saved",
                    f"Visibility settings saved as global default."
                )
            else:
                print(f"Saved ROM-specific bezel/joystick settings to {settings_file}: {settings}")
                
            return True
        except Exception as e:
            print(f"Error saving bezel/joystick settings: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Ensure the load_logo_settings method properly loads custom position
    def load_logo_settings(self):
        """Load logo settings from file"""
        settings = {
            "logo_visible": True,
            "custom_position": False,
            "x_position": 20,
            "y_position": 20,
            "width_percentage": 15,
            "height_percentage": 15,
            "maintain_aspect": True
        }
        
        try:
            # Check first for ROM-specific settings
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            rom_settings_file = os.path.join(preview_dir, f"{self.rom_name}_logo.json")
            global_settings_file = os.path.join(preview_dir, "global_logo.json")
            
            # First check for ROM-specific settings
            if os.path.exists(rom_settings_file):
                with open(rom_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded ROM-specific logo settings for {self.rom_name}: {settings}")
            # Then fall back to global settings
            elif os.path.exists(global_settings_file):
                with open(global_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded global logo settings: {settings}")
            else:
                # Backward compatibility with old location
                old_settings_file = os.path.join(self.mame_dir, "logo_settings.json")
                if os.path.exists(old_settings_file):
                    with open(old_settings_file, 'r') as f:
                        loaded_settings = json.load(f)
                        settings.update(loaded_settings)
                        print(f"Loaded legacy logo settings: {settings}")
                else:
                    print(f"No logo settings file found")
        except Exception as e:
            print(f"Error loading logo settings: {e}")
        
        return settings
    
    # Make sure the toggle_logo method properly handles visibility
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
        
        # Save setting immediately 
        self.save_positions(is_global=False)  # Save for current ROM by default
    
    def show_logo_position(self):
        """Show dialog to configure logo position"""
        self.show_logo_settings()
    
    # Method for properly saving logo settings
    def save_logo_settings(self, is_global=False):
        """Save logo settings to file with proper directory handling"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Determine file path
            if is_global:
                settings_file = os.path.join(preview_dir, "global_logo.json")
            else:
                settings_file = os.path.join(preview_dir, f"{self.rom_name}_logo.json")
            
            # Save settings
            with open(settings_file, 'w') as f:
                json.dump(self.logo_settings, f)
                
            print(f"Saved logo settings to {settings_file}: {self.logo_settings}")
            return True
        except Exception as e:
            print(f"Error saving logo settings: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Add a method to add_logo to store original pixmap
    # Improved add_logo method to handle sizes better
    def add_logo(self):
        """Add logo overlay to preview with better size handling"""
        # Find logo path
        logo_path = self.find_logo_path(self.rom_name)
        if not logo_path:
            print(f"No logo found for {self.rom_name}")
            return
            
        # Create logo label
        self.logo_label = QLabel(self.canvas)
        
        # Load and store original pixmap
        original_pixmap = QPixmap(logo_path)
        self.original_logo_pixmap = original_pixmap  # Store unmodified original
        
        if original_pixmap.isNull():
            print(f"Error loading logo image from {logo_path}")
            return
        
        # Set initial pixmap
        self.logo_label.setPixmap(original_pixmap)

        # Always remove border, especially important in clean mode
        self.logo_label.setStyleSheet("background-color: transparent; border: none;")

        # Only enable drag and resize in non-clean mode
        if not hasattr(self, 'clean_mode') or not self.clean_mode:
            # Set cursor for dragging
            self.logo_label.setCursor(Qt.OpenHandCursor)
            
            # Enable mouse tracking for logo
            self.logo_label.setMouseTracking(True)
            
            # Add drag and resize support
            self.logo_label.mousePressEvent = lambda event: self.logo_mouse_press(event)
            self.logo_label.mouseMoveEvent = lambda event: self.logo_mouse_move(event)
            self.logo_label.mouseReleaseEvent = lambda event: self.logo_mouse_release(event)
            
            # Add custom paint event for resize handle
            self.logo_label.paintEvent = lambda event: self.logo_paint_event(event)
        
        # Now update the logo display to apply settings
        # This will resize according to saved settings
        self.update_logo_display()
        
        # Show the logo
        self.logo_label.show()
        
        print(f"Logo added and sized: {self.logo_label.width()}x{self.logo_label.height()}")

    
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
    
    # Improve logo_mouse_press to store the original pixmap for proper resizing
    def logo_mouse_press(self, event):
        """Handle mouse press on logo for dragging and resizing with pixmap preservation"""
        if event.button() == Qt.LeftButton:
            # Check if we're in the resize corner
            if self.is_in_logo_resize_corner(event.pos()):
                # Start resizing
                self.logo_is_resizing = True
                self.logo_original_size = self.logo_label.size()
                self.logo_resize_start_pos = event.pos()
                
                # Make sure we have the original pixmap stored
                if not hasattr(self, 'original_logo_pixmap') or not self.original_logo_pixmap:
                    self.original_logo_pixmap = self.logo_label.pixmap()
                    
                self.logo_label.setCursor(Qt.SizeFDiagCursor)
                print("Logo resize started")
            else:
                # Start dragging
                self.logo_drag_start_pos = event.pos()
                self.logo_is_dragging = True
                
                # Change cursor to indicate dragging
                self.logo_label.setCursor(Qt.ClosedHandCursor)
                
                # Enable custom position mode
                self.logo_settings["custom_position"] = True

    # Add a method to check if we're in the logo resize corner
    def is_in_logo_resize_corner(self, pos):
        """Check if the position is in the logo resize corner"""
        if not hasattr(self, 'logo_label') or not self.logo_label:
            return False
            
        # Define resize handle size
        resize_handle_size = 15
        
        # Check if position is in bottom-right corner
        return (pos.x() > self.logo_label.width() - resize_handle_size and 
                pos.y() > self.logo_label.height() - resize_handle_size)
    
    # Modified logo_mouse_move method for more consistent pixmap handling
    def logo_mouse_move(self, event):
        """Handle mouse move on logo for dragging and resizing with reliable pixmap scaling"""
        # Handle resizing with direct pixmap manipulation
        if hasattr(self, 'logo_is_resizing') and self.logo_is_resizing:
            # Calculate size change
            delta_width = event.x() - self.logo_resize_start_pos.x()
            delta_height = event.y() - self.logo_resize_start_pos.y()
            
            # Calculate new size with minimum
            new_width = max(50, self.logo_original_size.width() + delta_width)
            new_height = max(30, self.logo_original_size.height() + delta_height)
            
            # Get the original pixmap
            if hasattr(self, 'original_logo_pixmap') and not self.original_logo_pixmap.isNull():
                original_pixmap = self.original_logo_pixmap
            else:
                # Fallback to the current pixmap if original not available
                original_pixmap = self.logo_label.pixmap()
                self.original_logo_pixmap = QPixmap(original_pixmap)  # Make a copy
            
            # Resize the pixmap with proper aspect ratio handling
            if self.logo_settings.get("maintain_aspect", True):
                scaled_pixmap = original_pixmap.scaled(
                    new_width, 
                    new_height, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
            else:
                scaled_pixmap = original_pixmap.scaled(
                    new_width, 
                    new_height, 
                    Qt.IgnoreAspectRatio, 
                    Qt.SmoothTransformation
                )
            
            # Apply the scaled pixmap
            self.logo_label.setPixmap(scaled_pixmap)
            
            # Actually resize the label to match the pixmap
            self.logo_label.resize(scaled_pixmap.width(), scaled_pixmap.height())
            
            # Update size percentages for settings
            canvas_width = self.canvas.width()
            canvas_height = self.canvas.height()
            
            width_percentage = (scaled_pixmap.width() / canvas_width) * 100
            height_percentage = (scaled_pixmap.height() / canvas_height) * 100
            
            # Update settings in memory
            self.logo_settings["width_percentage"] = width_percentage
            self.logo_settings["height_percentage"] = height_percentage
            
            # Debug output (occasionally)
            if random.random() < 0.05:
                print(f"Logo resized: {scaled_pixmap.width()}x{scaled_pixmap.height()} " +
                    f"({width_percentage:.1f}%, {height_percentage:.1f}%)")
        
        # Rest of the method for handling dragging and cursor updates...
        elif hasattr(self, 'logo_is_dragging') and self.logo_is_dragging:
            # Calculate new position
            delta = event.pos() - self.logo_drag_start_pos
            new_pos = self.logo_label.pos() + delta
            
            # Apply boundaries
            canvas_width = self.canvas.width()
            canvas_height = self.canvas.height()
            logo_width = self.logo_label.width()
            logo_height = self.logo_label.height()
            
            margin = 10
            new_pos.setX(max(margin, min(canvas_width - logo_width - margin, new_pos.x())))
            new_pos.setY(max(margin, min(canvas_height - logo_height - margin, new_pos.y())))
            
            # Move the logo
            self.logo_label.move(new_pos)
            
            # Update position in memory
            self.logo_settings["x_position"] = new_pos.x()
            self.logo_settings["y_position"] = new_pos.y()
        
        # Update cursor
        elif hasattr(self, 'logo_label') and self.logo_label:
            if self.is_in_logo_resize_corner(event.pos()):
                self.logo_label.setCursor(Qt.SizeFDiagCursor)
            else:
                self.logo_label.setCursor(Qt.OpenHandCursor)
                
    # Add a method that forces the logo to resize according to settings
    def force_logo_resize(self):
        """Force logo to resize according to current settings"""
        if not hasattr(self, 'logo_label') or not self.logo_label:
            print("No logo label to resize")
            return False
            
        if not hasattr(self, 'original_logo_pixmap') or self.original_logo_pixmap.isNull():
            # Try to load the logo image again
            logo_path = self.find_logo_path(self.rom_name)
            if not logo_path:
                print("Cannot force resize - no logo image found")
                return False
                
            self.original_logo_pixmap = QPixmap(logo_path)
            if self.original_logo_pixmap.isNull():
                print("Cannot force resize - failed to load logo image")
                return False
        
        # Get canvas and logo dimensions
        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        
        # Calculate target size
        width_percent = float(self.logo_settings.get("width_percentage", 15))
        height_percent = float(self.logo_settings.get("height_percentage", 15))
        
        target_width = int((width_percent / 100) * canvas_width)
        target_height = int((height_percent / 100) * canvas_height)
        
        print(f"Force-resizing logo to {target_width}x{target_height} pixels " +
            f"({width_percent:.1f}%, {height_percent:.1f}%)")
        
        # Scale the pixmap to the target size
        if self.logo_settings.get("maintain_aspect", True):
            scaled_pixmap = self.original_logo_pixmap.scaled(
                target_width, 
                target_height, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
        else:
            scaled_pixmap = self.original_logo_pixmap.scaled(
                target_width, 
                target_height, 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
        
        # Apply the scaled pixmap
        self.logo_label.setPixmap(scaled_pixmap)
        
        # Ensure label size matches pixmap size
        self.logo_label.resize(scaled_pixmap.width(), scaled_pixmap.height())
        
        # Position the logo
        if self.logo_settings.get("custom_position", False):
            self.logo_label.move(
                self.logo_settings.get("x_position", 20),
                self.logo_settings.get("y_position", 20)
            )
        
        print(f"Logo resized to {scaled_pixmap.width()}x{scaled_pixmap.height()} pixels")
        return True
    
    # Fix logo_mouse_release to NOT auto-save
    def logo_mouse_release(self, event):
        """Handle mouse release on logo to end dragging or resizing without auto-saving"""
        if event.button() == Qt.LeftButton:
            was_resizing = hasattr(self, 'logo_is_resizing') and self.logo_is_resizing
            was_dragging = hasattr(self, 'logo_is_dragging') and self.logo_is_dragging
            
            # End resizing/dragging states
            if hasattr(self, 'logo_is_resizing'):
                self.logo_is_resizing = False
            if hasattr(self, 'logo_is_dragging'):
                self.logo_is_dragging = False
            
            # Reset cursor
            if self.is_in_logo_resize_corner(event.pos()):
                self.logo_label.setCursor(Qt.SizeFDiagCursor)
            else:
                self.logo_label.setCursor(Qt.OpenHandCursor)
            
            # Update settings in memory only (don't save to file)
            if was_resizing or was_dragging:
                # Update position and size in settings
                if was_resizing:
                    pixmap = self.logo_label.pixmap()
                    canvas_width = self.canvas.width()
                    canvas_height = self.canvas.height()
                    
                    # Update size percentages
                    self.logo_settings["width_percentage"] = (pixmap.width() / canvas_width) * 100
                    self.logo_settings["height_percentage"] = (pixmap.height() / canvas_height) * 100
                
                if was_dragging:
                    pos = self.logo_label.pos()
                    self.logo_settings["x_position"] = pos.x()
                    self.logo_settings["y_position"] = pos.y()
                    self.logo_settings["custom_position"] = True
                
                # Only update in memory (don't save to file)
                action = "resized" if was_resizing else "moved"
                print(f"Logo {action} - settings updated in memory only")
    
    # Add logo resize handle display in paintEvent
    def logo_paint_event(self, event):
        """Paint event handler for logo label to draw resize handle"""
        # Call the original paint event first (we'll need to hook this up properly)
        QLabel.paintEvent(self.logo_label, event)
        
        # Draw a resize handle in the corner
        if hasattr(self, 'logo_label') and self.logo_label:
            painter = QPainter(self.logo_label)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            
            # Draw in bottom-right corner
            handle_size = 12
            width = self.logo_label.width()
            height = self.logo_label.height()
            
            # Draw diagonal lines for resize handle
            for i in range(1, 3):
                offset = i * 4
                painter.drawLine(
                    width - offset, height, 
                    width, height - offset
                )
            
            painter.end()
    
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
    
    # Completely rewrite the update_logo_display method to fix size loading 
    def update_logo_display(self):
        """Update the logo display based on current settings with fixed size loading"""
        if not hasattr(self, 'logo_label') or not self.logo_label:
            print("No logo label to update")
            return
        
        # Make sure we have the original pixmap
        if not hasattr(self, 'original_logo_pixmap') or not self.original_logo_pixmap or self.original_logo_pixmap.isNull():
            # If we don't have original, use current pixmap as original
            self.original_logo_pixmap = self.logo_label.pixmap()
            if not self.original_logo_pixmap or self.original_logo_pixmap.isNull():
                print("No logo pixmap available to resize")
                return
        
        # Get current canvas dimensions 
        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        
        # Get size percentages from settings
        width_percent = self.logo_settings.get("width_percentage", 15) / 100
        height_percent = self.logo_settings.get("height_percentage", 15) / 100
        
        # Calculate pixel dimensions based on percentages
        target_width = int(canvas_width * width_percent)
        target_height = int(canvas_height * height_percent)
        
        print(f"Logo target size: {target_width}x{target_height} pixels ({width_percent*100:.1f}%, {height_percent*100:.1f}%)")
        
        # Get original size for reference
        orig_width = self.original_logo_pixmap.width()
        orig_height = self.original_logo_pixmap.height()
        
        # Handle aspect ratio if needed
        if self.logo_settings.get("maintain_aspect", True):
            orig_ratio = orig_width / orig_height if orig_height > 0 else 1
            
            # Calculate dimensions preserving aspect ratio
            if (target_width / target_height) > orig_ratio:
                # Height is limiting factor
                final_height = target_height
                final_width = int(final_height * orig_ratio)
            else:
                # Width is limiting factor
                final_width = target_width
                final_height = int(final_width / orig_ratio)
        else:
            # Use target dimensions directly
            final_width = target_width
            final_height = target_height
        
        # Apply minimum size constraints
        final_width = max(30, final_width)
        final_height = max(20, final_height)
        
        # Scale the original pixmap to the calculated size
        scaled_pixmap = self.original_logo_pixmap.scaled(
            final_width, 
            final_height, 
            Qt.KeepAspectRatio if self.logo_settings.get("maintain_aspect", True) else Qt.IgnoreAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # Set the pixmap on the label
        self.logo_label.setPixmap(scaled_pixmap)
        
        # Resize the label to match pixmap
        self.logo_label.resize(scaled_pixmap.width(), scaled_pixmap.height())
        
        # Position the logo
        if self.logo_settings.get("custom_position", False) and "x_position" in self.logo_settings and "y_position" in self.logo_settings:
            x = self.logo_settings.get("x_position", 20)
            y = self.logo_settings.get("y_position", 20)
        else:
            # Default position
            x, y = 20, 20
        
        # Move to position
        self.logo_label.move(x, y)
        
        print(f"Logo display updated: {scaled_pixmap.width()}x{scaled_pixmap.height()} pixels")
        
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
    # Completely rewritten save_image method with explicit bezel handling
    # Add/update the save_image method in PreviewWindow in mame_controls_preview.py:
    def save_image(self):
        """Save current preview as an image with consistent text positioning"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Define the output path
            output_path = os.path.join(preview_dir, f"{self.rom_name}.png")
            
            # Check if file already exists
            if os.path.exists(output_path):
                # Ask for confirmation
                if QMessageBox.question(
                    self, 
                    "Confirm Overwrite", 
                    f"Image already exists for {self.rom_name}. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                ) != QMessageBox.Yes:
                    return False
            
            # Create a new image with the same size as the canvas
            image = QImage(
                self.canvas.width(),
                self.canvas.height(),
                QImage.Format_ARGB32
            )
            # Fill with black background
            image.fill(Qt.black)
            
            # Create painter for the image
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Draw the background image
            if hasattr(self, 'background_pixmap') and self.background_pixmap and not self.background_pixmap.isNull():
                bg_pixmap = self.background_pixmap
                
                # Calculate position to center the pixmap
                x = (self.canvas.width() - bg_pixmap.width()) // 2
                y = (self.canvas.height() - bg_pixmap.height()) // 2
                
                # Draw the pixmap
                painter.drawPixmap(x, y, bg_pixmap)
            
            # Draw the bezel if it's visible
            if hasattr(self, 'bezel_visible') and self.bezel_visible and hasattr(self, 'bezel_pixmap') and not self.bezel_pixmap.isNull():
                bezel_pixmap = self.bezel_pixmap
                # Position bezel in center
                x = (self.canvas.width() - bezel_pixmap.width()) // 2
                y = (self.canvas.height() - bezel_pixmap.height()) // 2
                painter.drawPixmap(x, y, bezel_pixmap)
            
            # Draw the logo if visible
            if hasattr(self, 'logo_label') and self.logo_label and self.logo_label.isVisible():
                logo_pixmap = self.logo_label.pixmap()
                if logo_pixmap and not logo_pixmap.isNull():
                    painter.drawPixmap(self.logo_label.pos(), logo_pixmap)
            
            # Draw control labels - CRITICAL CHANGE: Use the same relative positioning
            if hasattr(self, 'control_labels'):
                for control_name, control_data in self.control_labels.items():
                    label = control_data['label']
                    shadow = self.shadow_labels[control_name]
                    
                    # Skip if not visible
                    if not label.isVisible():
                        continue
                    
                    # IMPORTANT: Get the exact font from the label
                    font = label.font()
                    metrics = QFontMetrics(font)
                    
                    # CRITICAL FIX: Draw shadow first using EXACT same position logic as in the UI
                    # Draw shadow first with exact +2,+2 offset
                    shadow_pos = label.pos() + QPoint(2, 2)
                    painter.setFont(font)
                    painter.setPen(Qt.black)
                    painter.drawText(
                        shadow_pos.x(),
                        shadow_pos.y() + metrics.ascent(),  # This is the key fix - using ascent() 
                        label.text()
                    )
                    
                    # Then draw main text
                    painter.setPen(Qt.white)
                    painter.drawText(
                        label.pos().x(),
                        label.pos().y() + metrics.ascent(),  # This is the key fix - using ascent()
                        label.text()
                    )
            
            # End painting
            painter.end()
            
            # Save the image
            if image.save(output_path, "PNG"):
                print(f"Image saved successfully to {output_path}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Image saved to:\n{output_path}"
                )
                return True
            else:
                print(f"Failed to save image to {output_path}")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to save image. Could not write to file."
                )
                return False
                
        except Exception as e:
            print(f"Error saving image: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save image: {str(e)}"
            )
            return False

    # Add this method to properly force bezel rendering (useful when troubleshooting)
    def force_bezel_render(self):
        """Force bezel to render - useful for debugging"""
        if not hasattr(self, 'bezel_visible') or not self.bezel_visible:
            print("Bezel is not marked as visible, cannot force render")
            return False
        
        bezel_path = self.find_bezel_path(self.rom_name)
        if not bezel_path:
            print("No bezel path found for this ROM")
            return False
        
        try:
            # Load the bezel image directly
            bezel_pixmap = QPixmap(bezel_path)
            if bezel_pixmap.isNull():
                print(f"Failed to load bezel from {bezel_path}")
                return False
                
            # Scale with high quality
            window_width = self.canvas.width()
            window_height = self.canvas.height()
            
            # Scale with high quality
            scaled_bezel = bezel_pixmap.scaled(
                window_width,
                window_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Store for later use in saving
            self.bezel_pixmap = scaled_bezel
            
            # Update the bezel label if it exists
            if hasattr(self, 'bezel_label') and self.bezel_label:
                self.bezel_label.setPixmap(scaled_bezel)
                
                # Position centered
                x = (window_width - scaled_bezel.width()) // 2
                y = (window_height - scaled_bezel.height()) // 2
                self.bezel_label.move(x, y)
                
                # Make sure it's visible
                self.bezel_label.show()
                print(f"Forced bezel rendering: {scaled_bezel.width()}x{scaled_bezel.height()} at ({x},{y})")
                return True
            else:
                print("No bezel label exists to update")
                return False
        except Exception as e:
            print(f"Error in force_bezel_render: {e}")
            return False
        
    def handle_key_press(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.close()
            
    # Update the __init__ method to remove margins and borders
    def fix_borders_in_init(self):
        """Fix borders and margins in window setup"""
        # Set layout margins to zero
        if hasattr(self, 'main_layout'):
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
        
        # Set window margin/padding to zero
        self.setContentsMargins(0, 0, 0, 0)
        
        # Set central widget margins to zero
        if hasattr(self, 'central_widget'):
            self.central_widget.setContentsMargins(0, 0, 0, 0)
            
            # Add specific style for central widget
            self.central_widget.setStyleSheet("""
                QWidget {
                    background-color: black;
                    margin: 0px;
                    padding: 0px;
                    border: none;
                }
            """)
        
        # Set canvas margins to zero
        if hasattr(self, 'canvas'):
            self.canvas.setContentsMargins(0, 0, 0, 0)
            
            # Add specific style for canvas 
            self.canvas.setStyleSheet("""
                QWidget {
                    background-color: black;
                    margin: 0px;
                    padding: 0px;
                    border: none;
                }
            """)
        
        # Apply borderless style to the main window
        self.setStyleSheet("""
            QMainWindow {
                border: none;
                margin: 0px;
                padding: 0px;
            }
        """)
        
        print("Removed borders and margins from preview window")
    
    # Improve the button frame to avoid it creating border issues
    def fix_button_frame(self):
        """Fix button frame styling to avoid borders"""
        if hasattr(self, 'button_frame'):
            # Use a more transparent style
            self.button_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(20, 20, 20, 180);
                    border: none;
                    margin: 0px;
                    padding: 0px;
                }
            """)
            
            # Remove margins from button layout
            if hasattr(self, 'button_layout'):
                self.button_layout.setContentsMargins(10, 2, 10, 2)
                self.button_layout.setSpacing(2)
            
            # Update rows spacing too
            if hasattr(self, 'top_row'):
                self.top_row.setContentsMargins(0, 0, 0, 0)
                self.top_row.setSpacing(4)
            
            if hasattr(self, 'bottom_row'):
                self.bottom_row.setContentsMargins(0, 0, 0, 0)
                self.bottom_row.setSpacing(4)
                
            print("Fixed button frame styling")
    
    # Make sure the window is full screen without borders
    def set_fullscreen(self):
        """Make the window truly fullscreen without borders"""
        # Get screen geometry
        screen_rect = QApplication.desktop().screenGeometry(self.current_screen - 1)  # -1 for 0-based index
        
        # Set window to exactly screen size
        self.setGeometry(screen_rect)
        
        # Remove window frame
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        
        # Update window
        self.show()
        
        print(f"Set window to full screen: {screen_rect.width()}x{screen_rect.height()}")
    
    # Modify move_to_screen to ensure full screen
    def move_to_screen(self, screen_index):
        """Move window to specified screen with true fullscreen"""
        try:
            desktop = QDesktopWidget()
            screen_geometry = desktop.screenGeometry(screen_index - 1)  # Convert to 0-based index
            
            print(f"Screen geometry: {screen_geometry.width()}x{screen_geometry.height()}")
            
            # For debugging - log the window and central widget sizes
            print(f"Before fullscreen - Window: {self.width()}x{self.height()}, Canvas: {self.canvas.width()}x{self.canvas.height()}")
            
            # Ensure truly fullscreen with no borders
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.setGeometry(screen_geometry)
            
            # Store current screen
            self.current_screen = screen_index
            
            # Ensure the canvas fills the entire space
            self.canvas.setGeometry(0, 0, screen_geometry.width(), screen_geometry.height())
            
            # Show window to apply changes
            self.show()
            
            # Check actual sizes after showing
            QTimer.singleShot(100, self.check_dimensions)
            
            print(f"Window moved to screen {screen_index} in fullscreen mode")
        except Exception as e:
            print(f"Error moving to screen: {e}")
            import traceback
            traceback.print_exc()
            
    def check_dimensions(self):
        """Debug method to check actual dimensions after fullscreen is applied"""
        print(f"After fullscreen - Window: {self.width()}x{self.height()}, Canvas: {self.canvas.width()}x{self.canvas.height()}")
        print(f"Central widget: {self.central_widget.width()}x{self.central_widget.height()}")
        
        # If canvas isn't filling window, force its size
        if self.canvas.width() < self.width() or self.canvas.height() < self.height():
            print("Canvas smaller than window, forcing size match")
            self.canvas.setGeometry(0, 0, self.width(), self.height())
    
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
    
    # Add a method to force controls above the bezel
    def force_controls_above_bezel(self):
        """Force all control elements to be above the bezel"""
        if not hasattr(self, 'bezel_label') or not self.bezel_label:
            return
        
        # Raise all control labels
        if hasattr(self, 'control_labels'):
            for control_data in self.control_labels.values():
                if 'label' in control_data and control_data['label']:
                    control_data['label'].raise_()
                if 'shadow' in control_data and control_data['shadow']:
                    control_data['shadow'].raise_()
        
        # Raise logo if it exists
        if hasattr(self, 'logo_label') and self.logo_label:
            self.logo_label.raise_()
        
        print("All controls raised above bezel")
    
    # Revised background loading method
    # Replace the load_background_image_fullscreen method in mame_controls_preview.py
    def load_background_image_fullscreen(self):
        """Load the background image for the game with improved quality"""
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
                
                # Load the original pixmap without scaling yet
                original_pixmap = QPixmap(image_path)
                
                if original_pixmap.isNull():
                    print(f"Error: Could not load image from {image_path}")
                    self.bg_label.setText("Error loading background image")
                    self.bg_label.setStyleSheet("color: red; font-size: 18px;")
                    self.bg_label.setAlignment(Qt.AlignCenter)
                    return
                
                # Store the original pixmap for high-quality saving later
                self.original_background_pixmap = original_pixmap
                
                # Create a high-quality scaled version to display
                # Calculate aspect ratio preserving fit
                canvas_w = self.canvas.width()
                canvas_h = self.canvas.height()
                img_w = original_pixmap.width()
                img_h = original_pixmap.height()
                
                # Calculate the scaled size that fills the canvas while preserving aspect ratio
                scaled_pixmap = original_pixmap.scaled(
                    canvas_w, 
                    canvas_h, 
                    Qt.KeepAspectRatio,  # Preserve aspect ratio
                    Qt.SmoothTransformation  # High quality scaling
                )
                
                # Store the properly scaled pixmap
                self.background_pixmap = scaled_pixmap
                
                # Set it on the label
                self.bg_label.setPixmap(scaled_pixmap)
                
                # Position the background image in the center
                x = (canvas_w - scaled_pixmap.width()) // 2
                y = (canvas_h - scaled_pixmap.height()) // 2
                self.bg_label.setGeometry(x, y, scaled_pixmap.width(), scaled_pixmap.height())
                
                # Store the background position for control positioning
                self.bg_pos = (x, y)
                self.bg_size = (scaled_pixmap.width(), scaled_pixmap.height())
                
                # Make sure the background is below everything
                self.bg_label.lower()
                
                print(f"Background loaded: {scaled_pixmap.width()}x{scaled_pixmap.height()}, positioned at ({x},{y})")
                
                # Update when window resizes
                self.canvas.resizeEvent = self.on_canvas_resize_with_background
            else:
                # Handle no image found
                print("No preview image found")
                self.bg_label = QLabel("No preview image found", self.canvas)
                self.bg_label.setAlignment(Qt.AlignCenter)
                self.bg_label.setStyleSheet("color: white; font-size: 24px;")
                self.bg_label.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
        except Exception as e:
            print(f"Error loading background image: {e}")
            import traceback
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

    # Replace the on_canvas_resize_with_background method
    def on_canvas_resize_with_background(self, event):
        """Handle canvas resize while maintaining proper layer stacking"""
        try:
            print("\n--- Canvas resize with bezel handling ---")
            
            # Recalculate the background image position and scaling
            if hasattr(self, 'original_background_pixmap') and not self.original_background_pixmap.isNull():
                # Get the original unscaled pixmap
                original_pixmap = self.original_background_pixmap
                
                # Create a high-quality scaled version to fill the canvas
                canvas_w = self.canvas.width()
                canvas_h = self.canvas.height()
                
                # Scale with high quality while preserving aspect ratio
                scaled_pixmap = original_pixmap.scaled(
                    canvas_w, 
                    canvas_h, 
                    Qt.KeepAspectRatio,  # Preserve aspect ratio
                    Qt.SmoothTransformation  # High quality scaling
                )
                
                # Update the stored pixmap
                self.background_pixmap = scaled_pixmap
                
                # Update the bg_label with the newly scaled pixmap
                if hasattr(self, 'bg_label') and self.bg_label:
                    self.bg_label.setPixmap(scaled_pixmap)
                    
                    # Center the background
                    x = (canvas_w - scaled_pixmap.width()) // 2
                    y = (canvas_h - scaled_pixmap.height()) // 2
                    self.bg_label.setGeometry(x, y, scaled_pixmap.width(), scaled_pixmap.height())
                    
                    # Store the background position for control positioning
                    self.bg_pos = (x, y)
                    self.bg_size = (scaled_pixmap.width(), scaled_pixmap.height())
                    
                    # Make sure the background is below everything
                    self.bg_label.lower()
                    
                    print(f"Background resized: {scaled_pixmap.width()}x{scaled_pixmap.height()}, positioned at ({x},{y})")
            
            # Also update bezel if it's visible
            if hasattr(self, 'bezel_visible') and self.bezel_visible and hasattr(self, 'bezel_label') and self.bezel_label:
                # Resize the bezel to match the new canvas size
                if hasattr(self, 'original_bezel_pixmap') and not self.original_bezel_pixmap.isNull():
                    canvas_w = self.canvas.width()
                    canvas_h = self.canvas.height()
                    
                    bezel_pixmap = self.original_bezel_pixmap.scaled(
                        canvas_w,
                        canvas_h,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    
                    self.bezel_pixmap = bezel_pixmap
                    self.bezel_label.setPixmap(bezel_pixmap)
                    
                    # Position bezel in center
                    x = (canvas_w - bezel_pixmap.width()) // 2
                    y = (canvas_h - bezel_pixmap.height()) // 2
                    self.bezel_label.setGeometry(x, y, bezel_pixmap.width(), bezel_pixmap.height())
                    
                    print(f"Bezel resized: {bezel_pixmap.width()}x{bezel_pixmap.height()}, positioned at ({x},{y})")
                    
                    # Fix layering again after resize
                    self.raise_controls_above_bezel()
            
            # Call the original resize handler if it exists
            if hasattr(self, 'on_canvas_resize_original'):
                self.on_canvas_resize_original(event)
                
        except Exception as e:
            print(f"Error in canvas resize: {e}")
            import traceback
            traceback.print_exc()

    def check_layer_visibility(self):
        """Print diagnostic information about layer visibility"""
        print("\n----- LAYER VISIBILITY CHECK -----")
        
        # Check background
        if hasattr(self, 'bg_label') and self.bg_label:
            print(f"Background: {'VISIBLE' if self.bg_label.isVisible() else 'HIDDEN'}")
            if self.bg_label.pixmap():
                print(f"  Size: {self.bg_label.pixmap().width()}x{self.bg_label.pixmap().height()}")
            else:
                print("  No pixmap loaded")
        else:
            print("Background: NOT CREATED")
        
        # Check bezel
        if hasattr(self, 'bezel_label') and self.bezel_label:
            print(f"Bezel: {'VISIBLE' if self.bezel_label.isVisible() else 'HIDDEN'}")
            if self.bezel_label.pixmap():
                print(f"  Size: {self.bezel_label.pixmap().width()}x{self.bezel_label.pixmap().height()}")
            else:
                print("  No pixmap loaded")
        else:
            print("Bezel: NOT CREATED")
        
        # Check logo
        if hasattr(self, 'logo_label') and self.logo_label:
            print(f"Logo: {'VISIBLE' if self.logo_label.isVisible() else 'HIDDEN'}")
            if self.logo_label.pixmap():
                print(f"  Size: {self.logo_label.pixmap().width()}x{self.logo_label.pixmap().height()}")
            else:
                print("  No pixmap loaded")
        else:
            print("Logo: NOT CREATED")
        
        # Check controls (sample)
        if hasattr(self, 'control_labels') and self.control_labels:
            visible_controls = sum(1 for c in self.control_labels.values() 
                                if 'label' in c and c['label'] and c['label'].isVisible())
            print(f"Controls: {visible_controls} visible out of {len(self.control_labels)} total")
        else:
            print("Controls: NOT CREATED")
        
        print("--------------------------------")

    # Add this to toggle_bezel_improved
    # Add this call at the end of toggle_bezel_improved
        self.check_layer_visibility()
    
    # Force background to update on demand
    def force_background_fullscreen(self):
        """Force background to update to fullscreen"""
        if hasattr(self, 'bg_label') and self.bg_label and hasattr(self, 'canvas'):
            # Ensure the label fills the entire canvas
            self.bg_label.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
            self.bg_label.setScaledContents(True)
            self.bg_label.lower()
            self.bg_label.show()
            print(f"Force-updated background to fullscreen: {self.canvas.width()}x{self.canvas.height()}")
            return True
        return False
    
    def on_canvas_resize(self, event):
        """Handle canvas resize to update background image"""
        try:
            # Resize and center the background image
            if hasattr(self, 'bg_label'):
                # Get the original pixmap
                pixmap = self.bg_label.pixmap()
                if pixmap and not pixmap.isNull():
                    # Resize to fill the canvas, stretching it
                    new_pixmap = pixmap.scaled(
                        self.canvas.width(), 
                        self.canvas.height(), 
                        Qt.IgnoreAspectRatio,  # Stretch to fill the canvas without keeping aspect ratio
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
    
    # Update load_text_settings to check preview directory
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
            # First try global settings (prioritize global settings)
            preview_dir = os.path.join(self.mame_dir, "preview")
            global_settings_file = os.path.join(preview_dir, "global_text_settings.json")
            
            if os.path.exists(global_settings_file):
                with open(global_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded global text settings: {settings}")
                
                # Return immediately to prioritize global settings
                return settings
            
            # If no global settings, try ROM-specific settings
            rom_settings_file = os.path.join(preview_dir, f"{self.rom_name}_text_settings.json")
            if os.path.exists(rom_settings_file):
                with open(rom_settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    settings.update(loaded_settings)
                    print(f"Loaded ROM-specific text settings for {self.rom_name}")
            else:
                # Backward compatibility - check old location
                old_settings_file = os.path.join(self.mame_dir, "text_appearance_settings.json")
                if os.path.exists(old_settings_file):
                    with open(old_settings_file, 'r') as f:
                        loaded_settings = json.load(f)
                        settings.update(loaded_settings)
                        print(f"Loaded legacy text settings")
                else:
                    print("No text settings found, using defaults")
        except Exception as e:
            print(f"Error loading text appearance settings: {e}")
            import traceback
            traceback.print_exc()
        
        return settings
    
    # Update the save_text_settings method in PreviewWindow
    def save_text_settings(self, settings):
        """Save text appearance settings to file with better error handling"""
        try:
            # Update local settings
            self.text_settings.update(settings)
            
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Save to ROM-specific file
            rom_settings_file = os.path.join(preview_dir, f"{self.rom_name}_text_settings.json")
            
            with open(rom_settings_file, 'w') as f:
                json.dump(self.text_settings, f)
            print(f"Saved text settings to {rom_settings_file}: {self.text_settings}")
        except Exception as e:
            print(f"Error saving text settings: {e}")
            import traceback
            traceback.print_exc()

    # Improved create_control_labels method that respects joystick visibility
    def create_control_labels(self, clean_mode=False):
        """Create control labels with option for clean mode and joystick visibility support"""
        if not self.game_data or 'players' not in self.game_data:
            return
        
        # Load saved positions
        saved_positions = self.load_saved_positions()
        
        # Make sure joystick_visible is set before we start creating controls
        if not hasattr(self, 'joystick_visible'):
            # Load from settings if possible
            bezel_settings = self.load_bezel_settings() if hasattr(self, 'load_bezel_settings') else {}
            self.joystick_visible = bezel_settings.get("joystick_visible", True)
            print(f"Pre-initialized joystick visibility to: {self.joystick_visible}")
        
        # Process controls
        for player in self.game_data.get('players', []):
            if player['number'] != 1:  # Only show Player 1 controls
                continue
                    
            # Create a label for each control
            grid_x, grid_y = 0, 0
            for control in player.get('labels', []):
                control_name = control['name']
                action_text = control['value']
                
                # Determine visibility BEFORE creating the control
                is_visible = True
                if "JOYSTICK" in control_name:
                    is_visible = getattr(self, 'joystick_visible', True)
                
                # Apply text settings
                if self.text_settings.get("use_uppercase", False):
                    action_text = action_text.upper()
                
                # Get position - use saved position or default grid position
                if control_name in saved_positions:
                    # Get saved position
                    pos_x, pos_y = saved_positions[control_name]
                    
                    # Apply y-offset from text settings
                    y_offset = self.text_settings.get("y_offset", -40)
                    
                    # Use saved position
                    x, y = pos_x, pos_y + y_offset
                    original_pos = QPoint(pos_x, pos_y)  # Store without offset
                else:
                    # Default position based on a grid layout
                    x = 100 + (grid_x * 150)
                    y = 100 + (grid_y * 40)
                    
                    # Apply y-offset from text settings
                    y_offset = self.text_settings.get("y_offset", -40)
                    y += y_offset
                    
                    # Store original position without offset
                    original_pos = QPoint(x, y - y_offset)
                    
                    # Update grid position
                    grid_x = (grid_x + 1) % 5
                    if grid_x == 0:
                        grid_y += 1
                
                # When creating each label:
                if clean_mode:
                    # Simple label without drag features in clean mode
                    label = QLabel(action_text, self.canvas)
                    
                    # IMPORTANT: Use our loaded font
                    if hasattr(self, 'current_font'):
                        label.setFont(self.current_font)
                        print(f"Applied loaded font to {control_name}")
                    else:
                        # Fallback
                        font = QFont(self.text_settings.get("font_family", "Arial"), 
                                self.text_settings.get("font_size", 28))
                        font.setBold(self.text_settings.get("bold_strength", 2) > 0)
                        label.setFont(font)
                else:
                    # For DraggableLabel, pass the loaded font
                    if hasattr(self, 'current_font'):
                        label = DraggableLabel(action_text, self.canvas, 
                                            settings=self.text_settings,
                                            initialized_font=self.current_font)
                    else:
                        label = DraggableLabel(action_text, self.canvas, 
                                            settings=self.text_settings)
                
                # Make sure shadow also uses the same font
                shadow_label = QLabel(action_text, self.canvas)
                shadow_label.setStyleSheet("color: black; background-color: transparent; border: none;")
                
                # Copy font directly from main label to ensure consistency
                shadow_label.setFont(label.font())
                
                # Position the labels - IMPORTANT: shadow goes behind!
                shadow_label.move(x + 2, y + 2)  # Shadow offset
                label.move(x, y)
                
                # Make shadow label go behind the main label
                shadow_label.lower()
                
                # Apply visibility immediately
                label.setVisible(is_visible)
                shadow_label.setVisible(is_visible)
                
                # Store the labels
                if clean_mode:
                    self.control_labels[control_name] = {
                        'label': label,
                        'shadow': shadow_label,
                        'action': action_text
                    }
                else:
                    self.control_labels[control_name] = {
                        'label': label,
                        'shadow': shadow_label,
                        'action': action_text,
                        'original_pos': original_pos  # Store without offset for reset
                    }
                
                # Store shadow label separately for convenience
                self.shadow_labels[control_name] = shadow_label
                
                # Connect position update for shadow (only for draggable labels)
                if not clean_mode:
                    original_mouseMoveEvent = label.mouseMoveEvent
                    label.mouseMoveEvent = lambda event, label=label, shadow=shadow_label, orig_func=original_mouseMoveEvent: self.on_label_move(event, label, shadow, orig_func)
        
        # Update joystick button text if it exists
        if hasattr(self, 'joystick_button'):
            self.joystick_button.setText("Show Joystick" if not self.joystick_visible else "Hide Joystick")
        
        # At the end of the method, add a QTimer to ensure proper layout in clean mode
        if clean_mode:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, self.ensure_clean_layout)
        
        # At the very end of the method, add:
        # Ensure consistent text positioning
        self.ensure_consistent_text_positioning()
                
    def ensure_clean_layout(self):
        """Ensure all controls are properly laid out in clean mode"""
        # Force a redraw of the canvas
        self.canvas.update()
        
        # Make sure all shadow labels are properly positioned
        for control_name, control_data in self.control_labels.items():
            if 'shadow' in control_data and 'label' in control_data:
                shadow = control_data['shadow']
                label = control_data['label']
                pos = label.pos()
                shadow.move(pos.x() + 2, pos.y() + 2)
                
                # Make sure shadow is behind label
                shadow.lower()
                
        # If logo exists, make sure it has no border
        if hasattr(self, 'logo_label') and self.logo_label:
            self.logo_label.setStyleSheet("background-color: transparent; border: none;")
            
        print("Clean layout applied - shadows positioned correctly")
    
    # Add or update a method to load saved positions
    def load_saved_positions(self):
        """Load saved positions from ROM-specific or global config"""
        positions = {}
        
        try:
            # Check for ROM-specific positions first
            preview_dir = os.path.join(self.mame_dir, "preview")
            rom_positions_file = os.path.join(preview_dir, f"{self.rom_name}_positions.json")
            global_positions_file = os.path.join(preview_dir, "global_positions.json")
            
            # First try ROM-specific positions
            if os.path.exists(rom_positions_file):
                with open(rom_positions_file, 'r') as f:
                    positions = json.load(f)
                    print(f"Loaded ROM-specific positions for {self.rom_name} from {rom_positions_file}")
                    if positions:
                        # Check if we have any control positions (not just logo settings)
                        has_control_positions = any(key != "__logo_settings__" for key in positions.keys())
                        print(f"ROM-specific control positions found: {has_control_positions}")
            
            # If no ROM-specific positions or they're empty, try global positions
            if not positions:
                if os.path.exists(global_positions_file):
                    with open(global_positions_file, 'r') as f:
                        positions = json.load(f)
                        print(f"Loaded global positions from {global_positions_file}")
                else:
                    print(f"No position files found")
            
            # Handle special logo settings object if present
            if "__logo_settings__" in positions:
                # Don't include logo settings in the return value
                del positions["__logo_settings__"]
                
        except Exception as e:
            print(f"Error loading saved positions: {e}")
            import traceback
            traceback.print_exc()
        
        return positions
    
    def on_label_move(self, event, label, shadow, original_func):
        """Custom mouseMoveEvent to keep shadow with main label"""
        # Call the original mouseMoveEvent to handle dragging
        original_func(event)
        
        # CRITICAL CHANGE: Use exact 2px offset rather than calculating
        shadow.move(label.pos().x() + 2, label.pos().y() + 2)

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
    
    # Update toggle_joystick_controls to save settings
    def toggle_joystick_controls(self):
        """Toggle visibility of joystick controls and save setting"""
        self.joystick_visible = not self.joystick_visible
        
        # Update button text
        self.joystick_button.setText("Show Joystick" if not self.joystick_visible else "Hide Joystick")
        
        # Toggle visibility for joystick controls
        for control_name, control_data in self.control_labels.items():
            if "JOYSTICK" in control_name:
                is_visible = self.texts_visible and self.joystick_visible
                control_data['label'].setVisible(is_visible)
                self.shadow_labels[control_name].setVisible(is_visible)
        
        # Save the joystick visibility setting (globally)
        self.save_bezel_settings(is_global=True)
        print(f"Joystick visibility set to {self.joystick_visible} and saved to settings")
    
    # Update the reset_positions method to better handle saved positions
    def reset_positions(self):
        """Reset control labels to their original positions"""
        try:
            # Apply y-offset from text settings
            y_offset = self.text_settings.get("y_offset", -40)
            
            for control_name, control_data in self.control_labels.items():
                # Get the original position
                original_pos = control_data.get('original_pos', QPoint(100, 100))
                
                # Apply the current y-offset 
                new_pos = QPoint(original_pos.x(), original_pos.y() + y_offset)
                
                # Move the labels
                control_data['label'].move(new_pos)
                self.shadow_labels[control_name].move(new_pos.x() + 2, new_pos.y() + 2)
            
            print(f"Reset {len(self.control_labels)} control positions to original values")
            
            # Also reload saved positions to update self.control_labels with fresh saved positions 
            saved_positions = self.load_saved_positions()
            if saved_positions:
                # Update original positions in control_labels
                for control_name, position in saved_positions.items():
                    if control_name in self.control_labels:
                        pos_x, pos_y = position
                        self.control_labels[control_name]['original_pos'] = QPoint(pos_x, pos_y)
                
                print(f"Updated {len(saved_positions)} original positions from saved positions")
                
        except Exception as e:
            print(f"Error resetting positions: {e}")
            import traceback
            traceback.print_exc()
        
    # Now let's add a new method to handle saving both control positions and logo position
    # Update the save_positions method to include saving both text and logo settings
    # Enhanced save_positions method to properly save logo size
    def save_positions(self, is_global=False):
        """Save current control positions, text settings and logo settings"""
        # Create positions dictionary
        positions = {}
        
        # Save control positions (from original method)
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
            
            # Determine the file paths
            if is_global:
                positions_filepath = os.path.join(preview_dir, "global_positions.json")
                text_settings_filepath = os.path.join(preview_dir, "global_text_settings.json") 
                logo_settings_filepath = os.path.join(preview_dir, "global_logo.json")
            else:
                positions_filepath = os.path.join(preview_dir, f"{self.rom_name}_positions.json")
                text_settings_filepath = os.path.join(preview_dir, f"{self.rom_name}_text_settings.json")
                logo_settings_filepath = os.path.join(preview_dir, f"{self.rom_name}_logo.json")
            
            # Save positions to file
            with open(positions_filepath, 'w') as f:
                json.dump(positions, f)
            print(f"Saved {len(positions)} positions to: {positions_filepath}")
                    
            # Save text settings to file
            with open(text_settings_filepath, 'w') as f:
                json.dump(self.text_settings, f)
            print(f"Saved text settings to: {text_settings_filepath}")
            
            # Save logo settings to file if logo exists
            if hasattr(self, 'logo_label') and self.logo_label:
                # Update logo settings before saving
                if self.logo_label.isVisible():
                    # Update current logo position and size
                    self.logo_settings["logo_visible"] = True
                    self.logo_settings["custom_position"] = True
                    self.logo_settings["x_position"] = self.logo_label.pos().x()
                    self.logo_settings["y_position"] = self.logo_label.pos().y()
                    
                    # Update size percentages based on current pixmap
                    logo_pixmap = self.logo_label.pixmap()
                    if logo_pixmap and not logo_pixmap.isNull():
                        canvas_width = self.canvas.width()
                        canvas_height = self.canvas.height()
                        
                        width_percentage = (logo_pixmap.width() / canvas_width) * 100
                        height_percentage = (logo_pixmap.height() / canvas_height) * 100
                        
                        self.logo_settings["width_percentage"] = width_percentage
                        self.logo_settings["height_percentage"] = height_percentage
                        
                        print(f"Updating logo size in settings: {width_percentage:.1f}% x {height_percentage:.1f}%")
                
                # Save logo settings
                with open(logo_settings_filepath, 'w') as f:
                    json.dump(self.logo_settings, f)
                print(f"Saved logo settings to: {logo_settings_filepath}")
            
            # Print confirmation
            save_type = "global" if is_global else f"ROM-specific ({self.rom_name})"
            print(f"All settings saved as {save_type}")
            
            # Show confirmation message
            QMessageBox.information(
                self,
                "Settings Saved",
                f"Settings saved as {save_type}."
            )
            return True
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}"
            )
            return False
    
    # Update the show_text_settings method to include a global save option
    def show_text_settings(self):
        """Show dialog to configure text appearance with global saving"""
        dialog = TextSettingsDialog(self, self.text_settings)
        dialog.setWindowTitle("Text Appearance Settings")
        
        if dialog.exec_() == QDialog.Accepted:
            # Use the save_global_text_settings method instead
            self.save_global_text_settings()
            print("Text settings updated and saved globally")
    
    # Improved update_text_settings to ensure font size is applied to all controls
    def update_text_settings(self, settings):
        """Update text settings and properly apply to all controls with global saving"""
        # Update local settings with merge
        self.text_settings.update(settings)
        
        # Update font information
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        bold_strength = settings.get("bold_strength", 2)
        
        # Reload and register the font
        self.load_and_register_fonts()
        
        # Apply to existing controls
        self.apply_text_settings()
        
        # Save to file
        try:
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Save to global settings to ensure persistence
            settings_file = os.path.join(preview_dir, "global_text_settings.json")
            
            # Update the font_family with actual family name if available
            if hasattr(self, 'font_name') and self.font_name:
                self.text_settings["font_family"] = self.font_name
            
            with open(settings_file, 'w') as f:
                json.dump(self.text_settings, f)
            print(f"Saved text settings to {settings_file}: {self.text_settings}")
        except Exception as e:
            print(f"Error saving text settings: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"Text settings updated and applied: {self.text_settings}")
    
    def apply_specific_font(self, font_file_name, font_size, bold=False):
        """Load and apply a specific font from file"""
        from PyQt5.QtGui import QFont, QFontDatabase
        
        # Path to the font file - check in preview/fonts directory
        font_path = os.path.join(self.mame_dir, "preview", "fonts", font_file_name)
        
        # Check if file exists
        if not os.path.exists(font_path):
            print(f"Font file not found: {font_path}")
            return QFont("Arial", font_size, QFont.Bold if bold else QFont.Normal)
        
        # Load the font file
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id < 0:
            print(f"Error loading font file: {font_path}")
            return QFont("Arial", font_size, QFont.Bold if bold else QFont.Normal)
        
        # Get the font family name as recognized by Qt
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            print(f"No font families found in: {font_path}")
            return QFont("Arial", font_size, QFont.Bold if bold else QFont.Normal)
        
        # Use the first family name
        family_name = families[0]
        print(f"Successfully loaded font: {font_file_name} → {family_name}")
        
        # Create font with the exact family name
        font = QFont(family_name, font_size)
        font.setBold(bold)
        
        return font
    
    def apply_text_settings(self):
        """Apply current text settings to all controls with direct font application"""
        # Extract settings
        font_family = self.text_settings.get("font_family", "Arial")
        font_size = self.text_settings.get("font_size", 28)
        bold_strength = self.text_settings.get("bold_strength", 2)
        use_uppercase = self.text_settings.get("use_uppercase", False)
        y_offset = self.text_settings.get("y_offset", -40)
        
        # Debug font information if available
        if hasattr(self, 'debug_font_settings'):
            self.debug_font_settings()
        
        # DIRECT FONT LOADING - Create a completely new approach
        from PyQt5.QtGui import QFontDatabase, QFont, QFontInfo
        
        # Step 1: Create a font object with the requested family
        font = QFont(font_family, font_size)
        font.setBold(bold_strength > 0)
        
        # Step 2: Check if Qt is substituting the font
        font_info = QFontInfo(font)
        if font_info.family() != font_family:
            print(f"FONT SUBSTITUTION DETECTED: {font_family} → {font_info.family()}")
            
            # CRITICAL FIX: Ensure the font is available by loading the specific font file
            system_font_map = {
                "Times New Roman": "times.ttf",
                "Impact": "impact.ttf",
                "Courier New": "cour.ttf",
                "Comic Sans MS": "comic.ttf",
                "Georgia": "georgia.ttf"
            }
            
            font_loaded = False
            
            # Try loading system font if it's in our map
            if font_family in system_font_map and os.path.exists("C:\\Windows\\Fonts"):
                font_file = system_font_map[font_family]
                font_path = os.path.join("C:\\Windows\\Fonts", font_file)
                
                if os.path.exists(font_path):
                    print(f"Loading font directly from: {font_path}")
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    
                    if font_id >= 0:
                        families = QFontDatabase.applicationFontFamilies(font_id)
                        if families:
                            # IMPORTANT: Get the EXACT font family name from Qt
                            exact_family = families[0]
                            print(f"Font registered as: {exact_family}")
                            
                            # Replace the font object completely
                            font = QFont(exact_family, font_size)
                            font.setBold(bold_strength > 0)
                            
                            # Force exact match
                            font.setStyleStrategy(QFont.PreferMatch)
                            
                            # Double check it worked
                            new_info = QFontInfo(font)
                            print(f"New font family: {new_info.family()}")
                            font_loaded = True
            
            # If system font loading failed, try custom fonts
            if not font_loaded:
                fonts_dir = os.path.join(self.mame_dir, "preview", "fonts")
                if os.path.exists(fonts_dir):
                    # Try exact match
                    potential_files = [
                        f"{font_family}.ttf",
                        f"{font_family}.otf",
                        font_family.lower() + ".ttf",
                        font_family.lower() + ".otf"
                    ]
                    
                    for file_name in potential_files:
                        font_path = os.path.join(fonts_dir, file_name)
                        if os.path.exists(font_path):
                            print(f"Loading custom font: {font_path}")
                            font_id = QFontDatabase.addApplicationFont(font_path)
                            
                            if font_id >= 0:
                                families = QFontDatabase.applicationFontFamilies(font_id)
                                if families:
                                    exact_family = families[0]
                                    print(f"Custom font registered as: {exact_family}")
                                    
                                    font = QFont(exact_family, font_size)
                                    font.setBold(bold_strength > 0)
                                    font.setStyleStrategy(QFont.PreferMatch)
                                    
                                    font_loaded = True
                                    break
                    
                    # If no exact match, try all font files
                    if not font_loaded:
                        for filename in os.listdir(fonts_dir):
                            if filename.lower().endswith(('.ttf', '.otf')):
                                font_path = os.path.join(fonts_dir, filename)
                                print(f"Trying font: {font_path}")
                                
                                font_id = QFontDatabase.addApplicationFont(font_path)
                                if font_id >= 0:
                                    families = QFontDatabase.applicationFontFamilies(font_id)
                                    for family in families:
                                        # Check if this font family contains our requested name
                                        if (font_family.lower() in family.lower() or 
                                            family.lower() in font_family.lower()):
                                            print(f"Found matching font: {family}")
                                            
                                            font = QFont(family, font_size)
                                            font.setBold(bold_strength > 0)
                                            font.setStyleStrategy(QFont.PreferMatch)
                                            
                                            font_loaded = True
                                            break
                                
                                if font_loaded:
                                    break
        
        # Now apply the font to ALL controls with stricter checks
        from PyQt5.QtCore import QTimer
        
        for control_name, control_data in self.control_labels.items():
            if 'label' in control_data:
                label = control_data['label']
                
                # Get original action text
                action_text = control_data['action']
                
                # Apply uppercase if enabled
                display_text = action_text.upper() if use_uppercase else action_text
                
                # Update the text
                label.setText(display_text)
                
                # Apply the font - TWO ways for redundancy
                label.setFont(font)
                
                # FORCE SPECIFIC FONT NAME as fallback with stylesheet (as a second approach)
                label.setStyleSheet(f"color: white; background-color: transparent; border: none; font-family: '{font.family()}';")
                
                # CRITICALLY IMPORTANT: Update shadow
                shadow = self.shadow_labels[control_name]
                shadow.setText(display_text)
                shadow.setFont(font)
                shadow.setStyleSheet(f"color: black; background-color: transparent; border: none; font-family: '{font.family()}';")
                
                # Update positions
                original_pos = control_data.get('original_pos', QPoint(100, 100))
                label_x, label_y = original_pos.x(), original_pos.y() + y_offset
                
                # Move the labels
                label.move(label_x, label_y)
                shadow.move(label_x + 2, label_y + 2)
        
        # Force a repaint
        if hasattr(self, 'canvas'):
            self.canvas.update()
        
        # Verify font application
        if hasattr(self, 'verify_font_application'):
            # Use a short delay to allow Qt to properly apply fonts
            QTimer.singleShot(100, self.verify_font_application)

    def verify_font_application(self, control_name=None):
        """Verify that fonts are being correctly applied to labels"""
        print("\n--- FONT APPLICATION VERIFICATION ---")
        
        # Get the requested font family from settings
        requested_font = self.text_settings.get("font_family", "Arial")
        print(f"Requested font from settings: {requested_font}")
        
        # Check a specific control or all controls
        if control_name and control_name in self.control_labels:
            label = self.control_labels[control_name]['label']
            actual_font = label.font().family()
            actual_size = label.font().pointSize()
            print(f"Control '{control_name}': font={actual_font}, size={actual_size}")
        else:
            # Check a sample of controls
            sample_count = min(3, len(self.control_labels))
            count = 0
            for name, data in self.control_labels.items():
                if count >= sample_count:
                    break
                if 'label' in data:
                    label = data['label']
                    actual_font = label.font().family()
                    actual_size = label.font().pointSize()
                    print(f"Control '{name}': font={actual_font}, size={actual_size}")
                    count += 1
        
        print("----------------------------------")

    def ensure_font_loaded(self, font_family):
        """Ensure the specified font is loaded into the application"""
        from PyQt5.QtGui import QFontDatabase
        
        # Check if it's a system font
        system_fonts = ["Arial", "Verdana", "Tahoma", "Times New Roman", "Courier New", 
                    "Segoe UI", "Calibri", "Georgia", "Impact", "System"]
        
        if font_family in system_fonts:
            return True  # System font, no need to load
        
        # Check custom fonts directory
        fonts_dir = os.path.join(self.mame_dir, "preview", "fonts")
        if not os.path.exists(fonts_dir):
            print(f"Custom fonts directory not found: {fonts_dir}")
            return False
        
        # Look for font files with matching family name
        found = False
        for filename in os.listdir(fonts_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(fonts_dir, filename)
                
                # Load font into QFontDatabase to check family name
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id >= 0:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families and font_family in font_families:
                        found = True
                        print(f"Successfully loaded font {font_family} from {filename}")
                        break
        
        if not found:
            print(f"Warning: Could not find font file for '{font_family}' in {fonts_dir}")
            
        return found
    
    def debug_font_availability(self):
        """Debug helper to check font availability"""
        from PyQt5.QtGui import QFontDatabase
        
        # Get all available font families
        font_families = QFontDatabase().families()
        
        # Check if our target font is available
        current_font = self.text_settings.get("font_family", "Arial")
        
        print("\n--- Font Availability Debug ---")
        print(f"Current font from settings: {current_font}")
        print(f"Font exists in database: {current_font in font_families}")
        
        # Print some available custom fonts as examples
        custom_fonts = [f for f in font_families if f not in ["Arial", "Verdana", "Tahoma"]]
        print(f"Sample of available custom fonts: {custom_fonts[:5] if custom_fonts else 'None'}")
        
        # Check if any label is actually using the font
        if hasattr(self, 'control_labels') and self.control_labels:
            sample_label = next(iter(self.control_labels.values()))['label']
            if hasattr(sample_label, 'font'):
                current_label_font = sample_label.font().family()
                print(f"Font actually being used in label: {current_label_font}")
        
        print("----------------------------")
    
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
        if self.parent and hasattr(self.parent, 'update_text_settings'):
            self.parent.update_text_settings(settings)
            
            # Also force font reload and application
            if hasattr(self.parent, 'load_and_register_fonts'):
                QTimer.singleShot(100, self.parent.load_and_register_fonts)
    
    # Also update the TextSettingsDialog.accept_settings method to properly save settings
    def accept_settings(self):
        """Save settings and close dialog with more robust saving"""
        settings = self.get_current_settings()
        
        # Save locally
        self.settings = settings
        
        # If parent provided, update parent settings
        if self.parent and hasattr(self.parent, 'update_text_settings'):
            self.parent.update_text_settings(settings)
            print(f"Text settings saved via dialog: {settings}")
        
        # Close dialog
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
    # Replace the save_image method to properly include bezel
    def save_image(self):
        """Save current preview as an image with bezel support and better quality"""
        try:
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Define the output path
            output_path = os.path.join(preview_dir, f"{self.rom_name}.png")
            
            # Check if file already exists
            if os.path.exists(output_path):
                # Ask for confirmation
                if QMessageBox.question(
                    self, 
                    "Confirm Overwrite", 
                    f"Image already exists for {self.rom_name}. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                ) != QMessageBox.Yes:
                    return False
            
            # Create a new image with the same size as the canvas
            image = QImage(
                self.canvas.size(),
                QImage.Format_ARGB32
            )
            # Fill with black background
            image.fill(Qt.black)
            
            # Create painter for the image
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Draw the background image if available (using the saved high-quality pixmap)
            if hasattr(self, 'background_pixmap') and not self.background_pixmap.isNull():
                bg_pixmap = self.background_pixmap
                
                # Calculate position to center the pixmap
                x = (self.canvas.width() - bg_pixmap.width()) // 2
                y = (self.canvas.height() - bg_pixmap.height()) // 2
                
                # Draw the pixmap
                painter.drawPixmap(x, y, bg_pixmap)
                print(f"Background drawn at {x},{y}, size {bg_pixmap.width()}x{bg_pixmap.height()}")
            elif hasattr(self, 'bg_label') and self.bg_label and self.bg_label.pixmap():
                # Fallback to current bg_label pixmap if needed
                bg_pixmap = self.bg_label.pixmap()
                painter.drawPixmap(self.bg_label.pos(), bg_pixmap)
                print(f"Background drawn via bg_label at {self.bg_label.pos()}, size {bg_pixmap.width()}x{bg_pixmap.height()}")
            
            # Draw the bezel if it's visible
            if hasattr(self, 'bezel_visible') and self.bezel_visible and hasattr(self, 'bezel_label') and self.bezel_label:
                bezel_pixmap = self.bezel_label.pixmap()
                if bezel_pixmap and not bezel_pixmap.isNull():
                    # The bezel should typically cover the full canvas area
                    painter.drawPixmap(0, 0, bezel_pixmap)
                    print(f"Bezel drawn at 0,0, size {bezel_pixmap.width()}x{bezel_pixmap.height()}")
            
            # Draw the logo if visible
            if hasattr(self, 'logo_label') and self.logo_label and self.logo_label.isVisible():
                logo_pixmap = self.logo_label.pixmap()
                if logo_pixmap and not logo_pixmap.isNull():
                    painter.drawPixmap(self.logo_label.pos(), logo_pixmap)
                    print(f"Logo drawn at {self.logo_label.pos()}, size {logo_pixmap.width()}x{logo_pixmap.height()}")
            
            # Draw control labels
            if hasattr(self, 'control_labels'):
                for control_name, control_data in self.control_labels.items():
                    label = control_data['label']
                    
                    # Skip if label is not visible
                    if not label.isVisible():
                        continue
                    
                    # Draw shadow first if visible
                    shadow = self.shadow_labels.get(control_name)
                    if shadow and shadow.isVisible():
                        shadow_font = shadow.font()
                        painter.setFont(shadow_font)
                        painter.setPen(Qt.black)
                        painter.drawText(
                            shadow.pos().x(), 
                            shadow.pos().y() + QFontMetrics(shadow_font).height(), 
                            shadow.text()
                        )
                    
                    # Then draw the label text
                    font = label.font()
                    painter.setFont(font)
                    painter.setPen(Qt.white)
                    painter.drawText(
                        label.pos().x(), 
                        label.pos().y() + QFontMetrics(font).height(), 
                        label.text()
                    )
                    
                print(f"Drew {len(self.control_labels)} control labels")
            
            # End painting
            painter.end()
            
            # Save the image
            if image.save(output_path, "PNG"):
                print(f"Image saved successfully to {output_path}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Image saved to:\n{output_path}"
                )
                return True
            else:
                print(f"Failed to save image to {output_path}")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to save image. Could not write to file."
                )
                return False
                
        except Exception as e:
            print(f"Error saving image: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save image: {str(e)}"
            )
            return False

def show_preview(rom_name, game_data, mame_dir):
    """Show the preview window for a specific ROM"""
    # Create and show preview window
    preview = PreviewWindow(rom_name, game_data, mame_dir)
    preview.showFullScreen()  # For a fullscreen experience
    return preview