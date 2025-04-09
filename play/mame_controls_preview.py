import os
import sys
import json
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
                            QLabel, QPushButton, QFrame, QApplication, QDesktopWidget,
                            QDialog, QGroupBox, QCheckBox, QSlider, QComboBox)
from PyQt5.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QFontMetrics
from PyQt5.QtCore import Qt, QPoint, QTimer, QRect, QEvent, QSize

class DraggableLabel(QLabel):
    """An enhanced draggable label with shadow and better visibility"""
    def __init__(self, text, parent=None, shadow_offset=2, settings=None):
        super().__init__(text, parent)
        self.shadow_offset = shadow_offset
        self.settings = settings or {}
        
        # Apply font settings
        self.update_appearance()
        
        # Enable mouse tracking for dragging
        self.dragging = False
        self.offset = QPoint()
        
        # Original position for reset
        self.original_pos = self.pos()
        
    def update_appearance(self):
        """Update appearance based on settings"""
        font_family = self.settings.get("font_family", "Arial")
        font_size = self.settings.get("font_size", 28)
        use_bold = self.settings.get("bold_strength", 2) > 0
        
        font = QFont(font_family, font_size)
        font.setBold(use_bold)
        self.setFont(font)
        
        self.setStyleSheet("color: white; background-color: transparent;")
        self.setCursor(Qt.OpenHandCursor)
        
    def update_text(self, text):
        """Update the displayed text, applying uppercase if needed"""
        if self.settings.get("use_uppercase", False):
            text = text.upper()
        self.setText(text)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.pos() - self.offset))
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor)
            
    def contextMenuEvent(self, event):
        """Placeholder for right-click menu"""
        # To be implemented later
        pass

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
        
        # Load settings
        self.text_settings = self.load_text_settings()
        self.logo_settings = self.load_logo_settings()
        
        # Configure window
        self.setWindowTitle(f"Control Preview: {rom_name}")
        self.resize(1280, 720)
        self.setWindowFlags(Qt.FramelessWindowHint)  # Frameless for fullscreen-like feel
        
        # Move to the second screen if available
        self.move_to_screen(2)  # Default to screen 2
        
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
        self.current_screen = 2
        
        # Bind ESC key to close
        self.keyPressEvent = self.handle_key_press
        
    def handle_key_press(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.close()
            
    def move_to_screen(self, screen_index):
        """Move window to specified screen"""
        desktop = QDesktopWidget()
        num_screens = desktop.screenCount()
        
        if screen_index < 1 or screen_index > num_screens:
            screen_index = 1  # Default to first screen if invalid
            
        # Get geometry of the selected screen (0-indexed)
        screen_geometry = desktop.screenGeometry(screen_index - 1)
        
        # Move window to that screen and maximize
        self.setGeometry(screen_geometry)
    
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
    
    def load_background_image(self):
        """Load the background image for the game"""
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
                break
                
        # If no ROM-specific image, try default image
        if not image_path:
            for ext in extensions:
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    break
        
        # Set background image if found
        if image_path:
            # Create background label with image
            self.bg_label = QLabel(self.canvas)
            pixmap = QPixmap(image_path)
            
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
            self.bg_label = QLabel("No preview image found", self.canvas)
            self.bg_label.setAlignment(Qt.AlignCenter)
            self.bg_label.setStyleSheet("color: white; font-size: 24px;")
            self.bg_label.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
    
    def on_canvas_resize(self, event):
        """Handle canvas resize to update background image"""
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
                
        # Call the original resize event
        super(self.canvas.__class__, self.canvas).resizeEvent(event)
    
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
                shadow_label.setStyleSheet("color: black; background-color: transparent;")
                
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
                
                # Position the labels
                label.move(x, y)
                shadow_label.move(x + 2, y + 2)  # Shadow offset
                
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
        if label.dragging:
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
        
        # Determine size based on percentage of canvas
        w_percent = self.logo_settings.get("width_percentage", 15) / 100
        h_percent = self.logo_settings.get("height_percentage", 15) / 100
        
        max_width = int(self.canvas.width() * w_percent)
        max_height = int(self.canvas.height() * h_percent)
        
        # Resize logo while maintaining aspect ratio
        if logo_pixmap.width() > 0 and logo_pixmap.height() > 0:
            scale = min(max_width / logo_pixmap.width(), max_height / logo_pixmap.height())
            new_width = int(logo_pixmap.width() * scale)
            new_height = int(logo_pixmap.height() * scale)
            
            # Scale the pixmap
            scaled_logo = logo_pixmap.scaled(
                new_width, 
                new_height, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            self.logo_label.setPixmap(scaled_logo)
            
            # Position logo based on logo_position setting
            position = self.logo_settings.get("logo_position", "top-left")
            self.position_logo(position)
            
            # Show the logo
            self.logo_label.show()
    
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
            
        # Save setting
        self.save_logo_settings()
    
    def show_logo_position(self):
        """Show dialog to configure logo position"""
        # Placeholder - to be implemented
        positions = ["top-left", "top-center", "top-right", 
                      "bottom-left", "bottom-center", "bottom-right"]
        
        # Simply cycle through positions for now
        current_pos = self.logo_settings.get("logo_position", "top-left")
        next_pos_index = (positions.index(current_pos) + 1) % len(positions)
        next_pos = positions[next_pos_index]
        
        # Update setting
        self.logo_settings["logo_position"] = next_pos
        
        # Reposition logo
        self.position_logo(next_pos)
        
        # Save settings
        self.save_logo_settings()
    
    def save_image(self):
        """Save current preview as an image"""
        # Placeholder - to be implemented
        print("Save image feature to be implemented")

def show_preview(rom_name, game_data, mame_dir):
    """Show the preview window for a specific ROM"""
    # Create and show preview window
    preview = PreviewWindow(rom_name, game_data, mame_dir)
    preview.showFullScreen()  # For a fullscreen experience
    return preview