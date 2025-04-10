from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QFrame, QMenu, QAction)
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QMouseEvent, QContextMenuEvent
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QPoint, QSize
import os

class DraggableLabel(QLabel):
    """A QLabel that can be dragged around a canvas"""
    positionChanged = pyqtSignal(str, int, int)  # control_name, x, y
    rightClicked = pyqtSignal(str, QPoint)  # control_name, global_pos
    
    def __init__(self, control_name, text, parent=None):
        super().__init__(parent)
        self.control_name = control_name
        self.setText(text)
        self.setStyleSheet("color: white; background-color: transparent;")
        self.setFont(QFont("Arial", 18, QFont.Bold))
        self.setCursor(Qt.OpenHandCursor)
        self.setAlignment(Qt.AlignLeft)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Shadow effect
        self.shadow_enabled = True
        self.shadow_offset = 2
        self.shadow_color = QColor(0, 0, 0, 255)
        
        # Use QLabel with HTML formatting for shadow
        self.setTextFormat(Qt.RichText)
        self.updateText(text)
        
        # Drag tracking
        self.dragging = False
        self.drag_start_pos = None
        
    def updateText(self, text):
        """Update the text including shadow effect using HTML"""
        if self.shadow_enabled:
            # Create HTML with shadow using span with text-shadow style
            html = f'<span style="text-shadow: {self.shadow_offset}px {self.shadow_offset}px {self.shadow_color.name()}">{text}</span>'
            self.setText(html)
        else:
            self.setText(text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.dragging and self.drag_start_pos is not None:
            # Calculate movement
            delta = event.pos() - self.drag_start_pos
            new_pos = self.pos() + delta
            
            # Move the label
            self.move(new_pos)
            
            # Emit the position change signal
            self.positionChanged.emit(self.control_name, new_pos.x(), new_pos.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click for context menu"""
        self.rightClicked.emit(self.control_name, event.globalPos())
        event.accept()


class PreviewCanvas(QWidget):
    """Canvas widget for the preview display"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_pixmap = None
        self.text_items = {}  # Dictionary of control_name -> DraggableLabel
        self.position_manager = None
        
        # Set widget properties
        self.setMouseTracking(True)
        self.setMinimumSize(800, 600)
        
        # Alignment guides
        self.show_alignment_guides = False
        self.h_guide_pos = -1
        self.v_guide_pos = -1
        self.alignment_threshold = 10  # Pixels
        
        # Snap points from other controls
        self.snap_points = {}
        
        # Default background color
        self.setStyleSheet("background-color: black;")
        
        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def setBackgroundImage(self, image_path):
        """Set the background image from a file"""
        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.background_pixmap = pixmap
                self.update()
                return True
        
        return False
    
    def resizeEvent(self, event):
        """Handle resize event to scale background image"""
        super().resizeEvent(event)
        if self.background_pixmap:
            self.update()
    
    def paintEvent(self, event):
        """Paint the canvas background and alignment guides"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw background color
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        # Draw background image if available
        if self.background_pixmap and not self.background_pixmap.isNull():
            # Scale pixmap to fit widget while maintaining aspect ratio
            scaled_pixmap = self.background_pixmap.scaled(
                self.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # Calculate position to center the pixmap
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            
            # Draw the pixmap
            painter.drawPixmap(x, y, scaled_pixmap)
        
        # Draw alignment guides if enabled
        if self.show_alignment_guides:
            # Set up pen for guidelines
            painter.setPen(QColor(255, 255, 0, 128))  # Semi-transparent yellow
            
            # Draw horizontal guide if active
            if self.h_guide_pos >= 0:
                painter.drawLine(0, self.h_guide_pos, self.width(), self.h_guide_pos)
            
            # Draw vertical guide if active
            if self.v_guide_pos >= 0:
                painter.drawLine(self.v_guide_pos, 0, self.v_guide_pos, self.height())
    
    def add_control_text(self, control_name, text, x, y, visible=True):
        """Add a control text item to the canvas"""
        # Remove existing item if it exists
        if control_name in self.text_items:
            self.text_items[control_name].deleteLater()
        
        # Create a new draggable label
        label = DraggableLabel(control_name, text, self)
        label.move(x, y)
        label.positionChanged.connect(self.on_text_position_changed)
        label.rightClicked.connect(self.on_text_right_clicked)
        
        # Set visibility
        label.setVisible(visible)
        
        # Store the label
        self.text_items[control_name] = label
        
        # Update snap points
        self.snap_points[control_name] = (x, y)
        
        return label
    
    def on_text_position_changed(self, control_name, x, y):
        """Handle position changes for text items"""
        # Check for snapping if alignment guides are enabled
        if self.show_alignment_guides:
            new_x, new_y = x, y
            snapped = False
            
            # Check for snapping to other controls
            for name, (point_x, point_y) in self.snap_points.items():
                if name == control_name:
                    continue
                
                # Check horizontal alignment
                if abs(y - point_y) < self.alignment_threshold:
                    new_y = point_y
                    self.h_guide_pos = point_y
                    snapped = True
                
                # Check vertical alignment
                if abs(x - point_x) < self.alignment_threshold:
                    new_x = point_x
                    self.v_guide_pos = point_x
                    snapped = True
            
            # If snapped, update position
            if snapped:
                label = self.text_items[control_name]
                label.move(new_x, new_y)
                
                # Update snap point
                self.snap_points[control_name] = (new_x, new_y)
                
                # Update the display
                self.update()
            else:
                # Update guides to follow the control
                self.h_guide_pos = y
                self.v_guide_pos = x
                
                # Update snap point
                self.snap_points[control_name] = (x, y)
                
                # Update the display
                self.update()
        else:
            # Just update snap point
            self.snap_points[control_name] = (x, y)
        
        # Send to position manager if available
        if self.position_manager:
            self.position_manager.update_from_dragging(control_name, x, y)
    
    def on_text_right_clicked(self, control_name, global_pos):
        """Handle right-click on text items"""
        # Create context menu
        menu = QMenu(self)
        
        # Add actions
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(lambda: self.hide_text_item(control_name))
        
        reset_action = QAction("Reset Position", self)
        reset_action.triggered.connect(lambda: self.reset_text_position(control_name))
        
        # Add actions to menu
        menu.addAction(hide_action)
        menu.addAction(reset_action)
        
        # Show menu at click position
        menu.exec_(global_pos)
    
    def show_context_menu(self, pos):
        """Show context menu for the canvas"""
        global_pos = self.mapToGlobal(pos)
        
        # Create context menu
        menu = QMenu(self)
        
        # Add actions
        toggle_alignment = QAction(
            "Disable Alignment" if self.show_alignment_guides else "Enable Alignment", 
            self
        )
        toggle_alignment.triggered.connect(self.toggle_alignment_guides)
        
        show_all_action = QAction("Show All Controls", self)
        show_all_action.triggered.connect(self.show_all_text_items)
        
        # Add actions to menu
        menu.addAction(toggle_alignment)
        menu.addAction(show_all_action)
        
        # Show menu at click position
        menu.exec_(global_pos)
    
    def toggle_alignment_guides(self):
        """Toggle alignment guides on/off"""
        self.show_alignment_guides = not self.show_alignment_guides
        
        if not self.show_alignment_guides:
            # Reset guide positions
            self.h_guide_pos = -1
            self.v_guide_pos = -1
            self.update()
    
    def hide_text_item(self, control_name):
        """Hide a text item"""
        if control_name in self.text_items:
            self.text_items[control_name].setVisible(False)
    
    def show_all_text_items(self):
        """Show all text items"""
        for label in self.text_items.values():
            label.setVisible(True)
    
    def reset_text_position(self, control_name):
        """Reset a text item to its default position"""
        if control_name in self.text_items:
            # This would need to know the default positions
            # In a real implementation, you'd get this from your position manager
            pass
    
    def clear_all_text_items(self):
        """Remove all text items from the canvas"""
        for label in self.text_items.values():
            label.deleteLater()
        
        self.text_items.clear()
        self.snap_points.clear()


class PreviewWindow(QMainWindow):
    """Main preview window for displaying control layouts"""
    
    def __init__(self, parent=None, rom_name=None, mame_dir=None, position_manager=None):
        super().__init__(parent)
        
        # Store passed parameters
        self.rom_name = rom_name
        self.mame_dir = mame_dir
        self.position_manager = position_manager
        
        # Set window properties
        self.setWindowTitle(f"Control Preview: {rom_name}")
        self.resize(1280, 720)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create preview canvas
        self.preview_canvas = PreviewCanvas()
        if position_manager:
            self.preview_canvas.position_manager = position_manager
        main_layout.addWidget(self.preview_canvas)
        
        # Create button panels
        self.create_button_panels()
        
        # Add button panel to layout
        main_layout.addWidget(self.button_frame)
        
        # Initialize attributes for settings
        self.logo_visible = True
        self.show_texts = True
        
        # Load image if ROM name is provided
        if rom_name and mame_dir:
            self.load_preview_image(rom_name)
            self.load_control_data(rom_name)
    
    def create_button_panels(self):
        """Create button panels for the preview window"""
        # Create main button frame
        self.button_frame = QFrame()
        self.button_frame.setStyleSheet("background-color: #2d2d2d;")
        self.button_frame.setMaximumHeight(80)
        
        # Create layout for button frame
        button_layout = QVBoxLayout(self.button_frame)
        
        # Create two rows of buttons
        top_row = QHBoxLayout()
        bottom_row = QHBoxLayout()
        
        # Top row buttons
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        top_row.addWidget(close_button)
        
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.reset_text_positions)
        top_row.addWidget(reset_button)
        
        global_button = QPushButton("Global")
        global_button.clicked.connect(self.save_global_positions)
        top_row.addWidget(global_button)
        
        rom_button = QPushButton("ROM")
        rom_button.clicked.connect(self.save_rom_positions)
        top_row.addWidget(rom_button)
        
        # Add spacer to push buttons to left
        top_row.addStretch()
        
        # Bottom row buttons
        joystick_button = QPushButton("Joystick")
        joystick_button.clicked.connect(self.toggle_joystick_controls)
        bottom_row.addWidget(joystick_button)
        
        self.text_toggle_button = QPushButton("Hide Texts")
        self.text_toggle_button.clicked.connect(self.toggle_texts_visibility)
        bottom_row.addWidget(self.text_toggle_button)
        
        # Add spacer to push buttons to left
        bottom_row.addStretch()
        
        # Add rows to button layout
        button_layout.addLayout(top_row)
        button_layout.addLayout(bottom_row)
    
    def load_preview_image(self, rom_name):
        """Load the preview image for the specified ROM"""
        if not self.mame_dir:
            return False
            
        # Look for ROM-specific image
        preview_dir = os.path.join(self.mame_dir, "preview")
        if not os.path.exists(preview_dir):
            os.makedirs(preview_dir)
        
        # Try to find an image for this ROM
        image_path = None
        for ext in ['.png', '.jpg', '.jpeg']:
            test_path = os.path.join(preview_dir, f"{rom_name}{ext}")
            if os.path.exists(test_path):
                image_path = test_path
                break
        
        # If no ROM-specific image, try the default image
        if not image_path:
            for ext in ['.png', '.jpg', '.jpeg']:
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    break
        
        # Set the image if found
        if image_path:
            return self.preview_canvas.setBackgroundImage(image_path)
        
        return False
    
    def load_control_data(self, rom_name):
        """Load control data for the specified ROM"""
        # This would typically call back to the main application to get control data
        # For now, we'll just create some dummy data
        dummy_controls = {
            'P1_BUTTON1': 'Jump',
            'P1_BUTTON2': 'Attack',
            'P1_JOYSTICK_UP': 'Move Up',
            'P1_JOYSTICK_DOWN': 'Move Down',
            'P1_JOYSTICK_LEFT': 'Move Left',
            'P1_JOYSTICK_RIGHT': 'Move Right'
        }
        
        # Position controls on canvas
        positions = {}
        if self.position_manager:
            self.position_manager.load_from_file(rom_name)
            
        # Add texts to canvas
        for i, (control_name, text) in enumerate(dummy_controls.items()):
            # Get position from position manager if available
            x, y = 100 + (i % 3) * 200, 100 + (i // 3) * 100  # Default positions
            
            if self.position_manager and control_name in self.position_manager.positions:
                x, y = self.position_manager.get_display(control_name, x, y)
            
            # Add to canvas
            self.preview_canvas.add_control_text(control_name, text, x, y)
    
    def reset_text_positions(self):
        """Reset all text positions to default"""
        # In a real implementation, this would use default positions
        # For now, just rearrange in a grid
        for i, (control_name, label) in enumerate(self.preview_canvas.text_items.items()):
            x = 100 + (i % 3) * 200
            y = 100 + (i // 3) * 100
            label.move(x, y)
            self.preview_canvas.snap_points[control_name] = (x, y)
            
            # Update position manager
            if self.position_manager:
                self.position_manager.store(control_name, x, y)
    
    def save_global_positions(self):
        """Save current positions as global positions"""
        if self.position_manager:
            self.position_manager.save_to_file(is_global=True)
    
    def save_rom_positions(self):
        """Save current positions for this ROM"""
        if self.position_manager and self.rom_name:
            self.position_manager.save_to_file(game_name=self.rom_name, is_global=False)
    
    def toggle_joystick_controls(self):
        """Toggle visibility of joystick controls"""
        # In a real implementation, this would filter by control type
        for control_name, label in self.preview_canvas.text_items.items():
            if 'JOYSTICK' in control_name:
                label.setVisible(not label.isVisible())
    
    def toggle_texts_visibility(self):
        """Toggle visibility of all text items"""
        self.show_texts = not self.show_texts
        
        # Update button text
        self.text_toggle_button.setText("Show Texts" if not self.show_texts else "Hide Texts")
        
        # Update visibility of all labels
        for label in self.preview_canvas.text_items.values():
            label.setVisible(self.show_texts)


# For testing the preview window standalone
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create preview window
    window = PreviewWindow(rom_name="pacman", mame_dir="C:\\MAME")
    window.show()
    
    sys.exit(app.exec_())