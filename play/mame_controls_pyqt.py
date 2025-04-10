def save_current_preview(self):
    """Save the current preview as an image"""
    if not hasattr(self, 'preview_window') or not self.current_game:
        QMessageBox.warning(self, "Warning", "No preview is currently open to save.")
        return
    
    # Import the save utility
    # Use the actual filename (without .py extension):
    from mame_controls_save import SaveUtility
    
    # Save the preview
    SaveUtility.save_preview_image(
        self.preview_window.preview_canvas,
        self.current_game,
        self.mame_dir
    )

def export_current_controls(self):
    """Export control data for the current game"""
    if not self.current_game:
        QMessageBox.warning(self, "Warning", "No game is currently selected.")
        return
    
    # Get game data
    game_data = self.get_game_data(self.current_game)
    if not game_data:
        QMessageBox.warning(self, "Warning", "No control data available for this game.")
        return
    
    # Import the save utility
    # Use the actual filename (without .py extension):
    from mame_controls_save import SaveUtility  
    
    # Export the control data
    if SaveUtility.export_control_data(game_data, self.mame_dir):
        QMessageBox.information(
            self,
            "Success",
            f"Control data exported to exports/{self.current_game}_controls.txt"
        )    
        
def setup_preview_controls(self, preview_window, game_data):
    """Set up control display on the preview window"""
    # Clear any existing controls
    preview_window.preview_canvas.clear_all_text_items()
    
    # Get text appearance settings
    settings = self.load_text_appearance_settings()
    use_uppercase = settings.get("use_uppercase", False)
    
    # Add player controls
    for player in game_data.get('players', []):
        # Only show Player 1 controls for now
        if player['number'] != 1:
            continue
            
        for label in player.get('labels', []):
            control_name = label['name']
            action = label['value']
            
            # Format text (apply uppercase if needed)
            display_text = action.upper() if use_uppercase else action
            
            # Check if control should be visible
            is_visible = self.is_control_visible(control_name)
            
            # Get position from position manager if available
            if hasattr(self, 'position_manager'):
                x, y = self.position_manager.get_display(control_name)
            else:
                # Default positioning in a grid
                col = len(preview_window.preview_canvas.text_items) % 3
                row = len(preview_window.preview_canvas.text_items) // 3
                x, y = 100 + col * 200, 100 + row * 80
            
            # Add control to canvas
            preview_window.preview_canvas.add_control_text(
                control_name, 
                display_text, 
                x, y, 
                visible=is_visible
            )
            import sys
import os
import json
import re
import sys
from typing import Dict, Optional, Set, List, Tuple
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QSplitter, QLabel, QLineEdit, QTextEdit, QFrame, QPushButton, 
                            QCheckBox, QScrollArea, QGridLayout, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QColor, QPalette, QIcon

class PositionManager:
    """Handles storage, normalization, and application of text positions"""
    def __init__(self, parent):
        """Initialize the position manager"""
        self.parent = parent  # Reference to the main app
        self.positions = {}   # Store for in-memory positions
    
    def normalize(self, x, y, y_offset=None):
        """Convert a display position to a normalized position (without y-offset)"""
        if y_offset is None:
            # Get from settings if not provided
            settings = self.parent.load_text_appearance_settings()
            y_offset = settings.get("y_offset", -40)
        
        # Remove y-offset
        normalized_y = y - y_offset
        return x, normalized_y
    
    def apply_offset(self, x, normalized_y, y_offset=None):
        """Apply y-offset to a normalized position for display"""
        if y_offset is None:
            # Get from settings if not provided
            settings = self.parent.load_text_appearance_settings()
            y_offset = settings.get("y_offset", -40)
        
        # Add y-offset
        display_y = normalized_y + y_offset
        return x, display_y
    
    def store(self, control_name, x, y, is_normalized=False):
        """Store a position for a control (normalizing if needed)"""
        if not is_normalized:
            # Normalize if the position includes y-offset
            x, normalized_y = self.normalize(x, y)
        else:
            # Already normalized
            normalized_y = y
        
        # Store the normalized position
        self.positions[control_name] = (x, normalized_y)
        return x, normalized_y
    
    def get_display(self, control_name, default_x=0, default_y=0):
        """Get the display position (with y-offset applied) for a control"""
        # Get normalized position (or use defaults)
        x, normalized_y = self.get_normalized(control_name, default_x, default_y)
        
        # Apply offset for display
        return self.apply_offset(x, normalized_y)
    
    def get_normalized(self, control_name, default_x=0, default_y=0):
        """Get the normalized position (without y-offset) for a control"""
        if control_name in self.positions:
            return self.positions[control_name]
        else:
            # Return defaults if not found
            return default_x, default_y
    
    def update_from_dragging(self, control_name, new_x, new_y):
        """Update a position from dragging (storing normalized values)"""
        x, normalized_y = self.normalize(new_x, new_y)
        self.positions[control_name] = (x, normalized_y)
        return x, normalized_y
    
    def load_from_file(self, game_name):
        """Load positions from file for a specific game"""
        # Reset the positions
        self.positions = {}
        
        try:
            # Use the parent's file loading method to get positions with proper priority
            loaded_positions = self.parent.load_text_positions(game_name)
            
            # Store the loaded positions (they should already be normalized)
            for name, pos in loaded_positions.items():
                if isinstance(pos, list) and len(pos) == 2:
                    x, normalized_y = pos
                    self.positions[name] = (x, normalized_y)
                    
            return len(self.positions) > 0
        except Exception as e:
            print(f"Error loading positions: {e}")
            return False
    
    def save_to_file(self, game_name=None, is_global=False):
        """Save positions to file (globally or for a specific game)"""
        if not self.positions:
            print("No positions to save")
            return False
            
        try:
            # Convert to format expected by file saving function
            positions_to_save = {}
            for name, (x, normalized_y) in self.positions.items():
                positions_to_save[name] = [x, normalized_y]
            
            # Create preview directory if it doesn't exist
            preview_dir = os.path.join(self.parent.mame_dir, "preview")
            os.makedirs(preview_dir, exist_ok=True)
            
            # Determine the file path
            if is_global:
                filepath = os.path.join(preview_dir, "global_positions.json")
            else:
                filepath = os.path.join(preview_dir, f"{game_name}_positions.json")
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(positions_to_save, f)
                
            print(f"Saved {len(positions_to_save)} positions to: {filepath}")
            return True
                
        except Exception as e:
            print(f"Error saving positions: {e}")
            return False
    
    def update_from_text_items(self, text_items):
        """Update positions from text items dictionary"""
        for name, data in text_items.items():
            if 'x' in data and 'y' in data:
                x, y = data['x'], data['y']
                # If base_y is available, use it directly (already normalized)
                if 'base_y' in data:
                    normalized_y = data['base_y']
                    self.positions[name] = (x, normalized_y)
                else:
                    # Otherwise normalize the position
                    x, normalized_y = self.normalize(x, y)
                    self.positions[name] = (x, normalized_y)
    
    def update_text_items(self, text_items):
        """Update text_items dictionary with current positions (with offset applied)"""
        for name, (x, normalized_y) in self.positions.items():
            if name in text_items:
                # Apply offset to get display coordinates
                display_x, display_y = self.apply_offset(x, normalized_y)
                
                # Update the data
                text_items[name]['x'] = display_x
                text_items[name]['y'] = display_y
                text_items[name]['base_y'] = normalized_y  # Also store the normalized base_y
                
        return text_items


class GameListWidget(QTextEdit):
    """Custom widget for the game list with highlighting support"""
    gameSelected = pyqtSignal(str, int)  # Signal for game selection (game_name, line_number)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Arial", 13))
        self.setCursor(Qt.PointingHandCursor)
        self.selected_line = None
        
        # Setup document for text formatting
        self.document().setDefaultStyleSheet("a { text-decoration: none; color: white; }")
        
        # Setup event handling
        self.mousePressEvent = self.on_game_select
    
    def on_game_select(self, event):
        """Handle mouse click event to select a game"""
        cursor = self.cursorForPosition(event.pos())
        block_number = cursor.blockNumber() + 1  # Lines start at 1
        
        # Get text content of the line
        cursor.select(QTextCursor.LineUnderCursor)
        line = cursor.selectedText()
        
        # Remove prefix indicators
        if line.startswith("* "):
            line = line[2:]
        if line.startswith("+ ") or line.startswith("- "):
            line = line[2:]
        
        # Extract ROM name
        rom_name = line.split(" - ")[0] if " - " in line else line
        
        # Highlight the selected line
        self.highlight_line(block_number)
        
        # Emit signal with ROM name and line number
        self.gameSelected.emit(rom_name, block_number)
    
    def highlight_line(self, line_number):
        """Highlight the selected line and remove highlight from previously selected line"""
        # Create background color for highlighting
        highlight_color = QColor(26, 95, 180)  # Similar to #1a5fb4
        
        # Create a cursor for the document
        cursor = QTextCursor(self.document())
        
        # Clear previous highlighting if any
        if self.selected_line is not None:
            cursor.setPosition(0)
            for _ in range(self.selected_line - 1):
                cursor.movePosition(QTextCursor.NextBlock)
            
            # Select the previously highlighted line
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            
            # Remove formatting
            fmt = cursor.charFormat()
            fmt.setBackground(Qt.transparent)
            cursor.setCharFormat(fmt)
        
        # Apply new highlighting
        cursor.setPosition(0)
        for _ in range(line_number - 1):
            cursor.movePosition(QTextCursor.NextBlock)
        
        # Select the line to highlight
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        
        # Apply highlighting
        fmt = cursor.charFormat()
        fmt.setBackground(highlight_color)
        fmt.setForeground(Qt.white)
        cursor.setCharFormat(fmt)
        
        # Store the selected line
        self.selected_line = line_number
        
        # Ensure the selected line is visible
        self.ensureCursorVisible()


class MAMEControlConfig(QMainWindow):
    def __init__(self, preview_only=False):
        super().__init__()
        
        # Initialize core attributes needed for both modes
        self.visible_control_types = ["BUTTON", "JOYSTICK"]
        self.default_controls = {}
        self.gamedata_json = {}
        self.available_roms = set()
        self.custom_configs = {}
        self.current_game = None
        self.use_xinput = True
        
        # Logo size settings (as percentages)
        self.logo_width_percentage = 15
        self.logo_height_percentage = 15
        
        # Initialize the position manager
        self.position_manager = PositionManager(self)
        
        # Skip main window setup if in preview-only mode
        if not preview_only:
            # Configure the window
            self.setWindowTitle("MAME Control Configuration Checker")
            self.resize(1024, 768)
            self.fullscreen = True  # Track fullscreen state
            
            # Find necessary directories
            self.mame_dir = self.find_mame_directory()
            if not self.mame_dir:
                QMessageBox.critical(self, "Error", "Please place this script in the MAME directory!")
                sys.exit(1)
                
            # Create the interface
            self.create_layout()
            
            # Load all data
            self.load_all_data()
            
            # Add generate images button
            self.add_generate_images_button()
            
            # Add appearance settings button
            self.add_appearance_settings_button()
        else:
            # For preview-only mode, just initialize minimal attributes
            self.fullscreen = True
            self.preferred_preview_screen = 2  # Default to second screen
            
            # Hide the main window completely
            self.hide()
    
    def get_application_path(self):
        """Get the base path for the application (handles PyInstaller bundling)"""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            return os.path.dirname(sys.executable)
        else:
            # Running as script
            return os.path.dirname(os.path.abspath(__file__))
            
    def find_mame_directory(self) -> Optional[str]:
        """Find the MAME directory containing necessary files"""
        # First check in the application directory
        app_dir = self.get_application_path()
        app_gamedata = os.path.join(app_dir, "gamedata.json")
        
        if os.path.exists(app_gamedata):
            print(f"Using bundled gamedata.json: {app_dir}")
            return app_dir
            
        # Then check in the current directory
        current_dir = os.path.abspath(os.path.dirname(__file__))
        current_gamedata = os.path.join(current_dir, "gamedata.json")
        
        if os.path.exists(current_gamedata):
            print(f"Found MAME directory: {current_dir}")
            return current_dir
            
        # Then check common MAME paths
        common_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "MAME"),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), "MAME"),
            "C:\\MAME",
            "D:\\MAME"
        ]
        
        for path in common_paths:
            gamedata_path = os.path.join(path, "gamedata.json")
            if os.path.exists(gamedata_path):
                print(f"Found MAME directory: {path}")
                return path
                
        print("Error: gamedata.json not found in known locations")
        return None
    
    def create_layout(self):
        """Create the main application layout"""
        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout with splitter
        main_layout = QHBoxLayout(central_widget)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel (game list)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # Stats frame
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_layout = QHBoxLayout(stats_frame)
        
        # Stats label
        self.stats_label = QLabel("Loading...")
        # If you're still getting an error, try:
        #self.stats_label.setFont(QFont("Arial", 12, QFont.Normal))
        stats_layout.addWidget(self.stats_label)
        
        # Unmatched ROMs button
        self.unmatched_button = QPushButton("Show Unmatched ROMs")
        self.unmatched_button.setFixedWidth(150)
        self.unmatched_button.clicked.connect(self.find_unmatched_roms)
        stats_layout.addWidget(self.unmatched_button)
        
        # Generate configs button
        self.generate_configs_button = QPushButton("Generate Info Files")
        self.generate_configs_button.setFixedWidth(150)
        self.generate_configs_button.clicked.connect(self.generate_all_configs)
        stats_layout.addWidget(self.generate_configs_button)
        
        # Generate images button (added later)
        self.generate_images_button = QPushButton("Generate Images")
        self.generate_images_button.setFixedWidth(150)
        self.generate_images_button.clicked.connect(self.show_generate_images_dialog)
        stats_layout.addWidget(self.generate_images_button)
        
        # Text settings button
        self.appearance_button = QPushButton("Text Settings")
        self.appearance_button.setFixedWidth(150)
        self.appearance_button.clicked.connect(self.show_text_appearance_settings)
        stats_layout.addWidget(self.appearance_button)
        
        left_layout.addWidget(stats_frame)
        
        # Search box
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search games...")
        self.search_entry.textChanged.connect(self.filter_games)
        left_layout.addWidget(self.search_entry)
        
        # Game list widget
        self.game_list = GameListWidget()
        self.game_list.gameSelected.connect(self.on_game_selected)
        left_layout.addWidget(self.game_list)
        
        # Right panel (control display)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        # Game title and preview button row
        title_row = QHBoxLayout()
        
        # Game title
        self.game_title = QLabel("Select a game")
        from PyQt5.QtGui import QFont
        self.game_title.setFont(QFont("Arial", 20, QFont.Bold)) 
        title_row.addWidget(self.game_title)
        
        # Preview button
        self.preview_button = QPushButton("Preview Controls")
        self.preview_button.setFixedWidth(150)
        self.preview_button.clicked.connect(self.show_preview)
        title_row.addWidget(self.preview_button)
        
        # Hide preview buttons toggle
        self.hide_buttons_toggle = QCheckBox("Hide Preview Buttons")
        self.hide_buttons_toggle.toggled.connect(self.toggle_hide_preview_buttons)
        title_row.addWidget(self.hide_buttons_toggle)
        
        right_layout.addLayout(title_row)
        
        # Toggle switches row
        toggle_row = QHBoxLayout()
        
        # XInput toggle
        self.xinput_toggle = QCheckBox("Use XInput Mappings")
        self.xinput_toggle.setChecked(True)
        self.xinput_toggle.toggled.connect(self.toggle_xinput)
        toggle_row.addWidget(self.xinput_toggle)
        
        # In-Game Mode toggle
        self.ingame_toggle = QCheckBox("In-Game Mode")
        self.ingame_toggle.toggled.connect(self.toggle_ingame_mode)
        toggle_row.addWidget(self.ingame_toggle)
        
        toggle_row.addStretch()
        right_layout.addLayout(toggle_row)
        
        # Controls display (scrollable)
        self.control_scroll = QScrollArea()
        self.control_scroll.setWidgetResizable(True)
        self.control_frame = QWidget()
        self.control_layout = QVBoxLayout(self.control_frame)
        self.control_scroll.setWidget(self.control_frame)
        right_layout.addWidget(self.control_scroll)
        
        # Add panels to splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        
        # Set initial splitter sizes
        main_splitter.setSizes([300, 700])
        
        # Set layout on central widget
        self.centralWidget().setLayout(main_layout)
    
    def add_generate_images_button(self):
        """Add button to generate preview images for ROMs"""
        # Button already added in create_layout
        pass
    
    def add_appearance_settings_button(self):
        """Add a button to configure text appearance settings"""
        # Button already added in create_layout
        pass
    
    def load_all_data(self):
        """Load all necessary data sources"""
        # Load settings from file
        self.load_settings()
        
        # Scan ROMs directory
        self.scan_roms_directory()
        
        # Load default controls
        self.load_default_config()
        
        # Load gamedata.json
        self.load_gamedata_json()
        
        # Always load custom configs
        self.load_custom_configs()
        
        # Update UI
        self.update_stats_label()
        self.update_game_list()
        
        # Auto-select first ROM
        self.select_first_rom()
    
    def scan_roms_directory(self):
        """Scan the roms directory for available games"""
        roms_dir = os.path.join(self.mame_dir, "roms")
        print(f"\nScanning ROMs directory: {roms_dir}")
        
        if not os.path.exists(roms_dir):
            print(f"ERROR: ROMs directory not found: {roms_dir}")
            return

        self.available_roms = set()  # Reset the set
        rom_count = 0

        for filename in os.listdir(roms_dir):
            # Strip common ROM extensions
            base_name = os.path.splitext(filename)[0]
            self.available_roms.add(base_name)
            rom_count += 1
            if rom_count <= 5:  # Print first 5 ROMs as sample
                print(f"Found ROM: {base_name}")
        
        print(f"Total ROMs found: {len(self.available_roms)}")
        if len(self.available_roms) > 0:
            print("Sample of available ROMs:", list(self.available_roms)[:5])
        else:
            print("WARNING: No ROMs were found!")
    
    def load_gamedata_json(self):
        """Load and parse the gamedata.json file for control data"""
        if hasattr(self, 'gamedata_json') and self.gamedata_json:
            # Already loaded
            return self.gamedata_json
            
        self.gamedata_json = {}
        
        # Look for gamedata.json in common locations
        json_paths = [
            os.path.join(self.mame_dir, "gamedata.json"),
            os.path.join(self.mame_dir, "metadata", "gamedata.json"),
            os.path.join(self.mame_dir, "data", "gamedata.json")
        ]
        
        json_path = None
        for path in json_paths:
            if os.path.exists(path):
                json_path = path
                break
        
        if not json_path:
            print("gamedata.json not found")
            return {}
            
        try:
            print(f"Loading gamedata.json from: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Process the data to find both main games and clones
            for rom_name, game_data in data.items():
                self.gamedata_json[rom_name] = game_data
                
                # Also index clones for easier lookup
                if 'clones' in game_data:
                    for clone_name, clone_data in game_data['clones'].items():
                        # Store clone with reference to parent
                        clone_data['parent'] = rom_name
                        self.gamedata_json[clone_name] = clone_data
            
            print(f"Loaded {len(self.gamedata_json)} games from gamedata.json")
            return self.gamedata_json
            
        except Exception as e:
            print(f"Error loading gamedata.json: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
    
    def load_custom_configs(self):
        """Load custom configurations from cfg directory"""
        cfg_dir = os.path.join(self.mame_dir, "cfg")
        if not os.path.exists(cfg_dir):
            print(f"Config directory not found: {cfg_dir}")
            return

        for filename in os.listdir(cfg_dir):
            if filename.endswith(".cfg"):
                game_name = filename[:-4]
                full_path = os.path.join(cfg_dir, filename)
                try:
                    # Read as binary first to handle BOM
                    with open(full_path, "rb") as f:
                        content = f.read()
                    # Decode with UTF-8-SIG to handle BOM
                    self.custom_configs[game_name] = content.decode('utf-8-sig')
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

        print(f"Loaded {len(self.custom_configs)} custom configurations")
    
    def load_default_config(self):
        """Load the default MAME control configuration"""
        # Look in the cfg directory
        cfg_dir = os.path.join(self.mame_dir, "cfg")
        default_cfg_path = os.path.join(cfg_dir, "default.cfg")
        
        print(f"Looking for default.cfg at: {default_cfg_path}")
        if os.path.exists(default_cfg_path):
            try:
                print(f"Loading default config from: {default_cfg_path}")
                # Read file content
                with open(default_cfg_path, "rb") as f:
                    content = f.read()
                
                # Parse the default mappings
                self.default_controls = self.parse_default_cfg(content.decode('utf-8-sig'))
                
                # Debug output
                print(f"Loaded {len(self.default_controls)} default control mappings")
                for i, (k, v) in enumerate(list(self.default_controls.items())[:5]):
                    print(f"  Sample {i+1}: {k} -> {v}")
                    
                return True
            except Exception as e:
                print(f"Error loading default config: {e}")
                import traceback
                traceback.print_exc()
                self.default_controls = {}
                return False
        else:
            print("No default.cfg found in cfg directory")
            self.default_controls = {}
            return False
    
    def parse_default_cfg(self, cfg_content):
        """Special parser just for default.cfg - extract ONLY joystick mappings"""
        controls = {}
        try:
            import xml.etree.ElementTree as ET
            from io import StringIO
            import re
            
            # Parse the XML content
            parser = ET.XMLParser(encoding='utf-8')
            tree = ET.parse(StringIO(cfg_content), parser)
            root = tree.getroot()
            
            # Find the input section
            input_elem = root.find('.//input')
            if input_elem is not None:
                print("Found input element in default.cfg")
                joycode_count = 0
                for port in input_elem.findall('port'):
                    control_type = port.get('type')
                    if control_type:
                        # Find the standard sequence
                        newseq = port.find('./newseq[@type="standard"]')
                        if newseq is not None and newseq.text:
                            full_mapping = newseq.text.strip()
                            
                            # Extract only JOYCODE parts using regex
                            joycode_match = re.search(r'(JOYCODE_\d+_[A-Z0-9_]+)', full_mapping)
                            if joycode_match:
                                joycode = joycode_match.group(1)
                                controls[control_type] = joycode
                                joycode_count += 1
            
            print(f"Parsed {len(controls)} joystick controls from default.cfg (found {joycode_count} JOYCODE entries)")
        except Exception as e:
            print(f"Error parsing default.cfg: {e}")
            import traceback
            traceback.print_exc()
        
        return controls
    
    def load_settings(self):
        """Load settings from JSON file if it exists"""
        settings_path = os.path.join(self.mame_dir, "control_config_settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    
                # Load screen preference
                if 'preferred_preview_screen' in settings:
                    self.preferred_preview_screen = settings['preferred_preview_screen']
                    print(f"Loaded preferred screen from settings: {self.preferred_preview_screen}")
                
                # Load visibility settings
                if 'visible_control_types' in settings:
                    self.visible_control_types = settings['visible_control_types']
                    print(f"Loaded visible control types: {self.visible_control_types}")

                # Load hide preview buttons setting
                if 'hide_preview_buttons' in settings:
                    self.hide_preview_buttons = settings['hide_preview_buttons']
                    # Update toggle if it exists
                    if hasattr(self, 'hide_buttons_toggle'):
                        self.hide_buttons_toggle.setChecked(self.hide_preview_buttons)
                else:
                    self.hide_preview_buttons = False
                    
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.hide_preview_buttons = False
        else:
            # Default setting
            self.hide_preview_buttons = False
        
        # Ensure the visible_control_types is initialized even if no settings file exists
        if not hasattr(self, 'visible_control_types') or self.visible_control_types is None:
            self.visible_control_types = ["BUTTON", "JOYSTICK"]
    
    def update_stats_label(self):
        """Update the statistics label"""
        unmatched = len(self.find_unmatched_roms())
        matched = len(self.available_roms) - unmatched
        stats = (
            f"Available ROMs: {len(self.available_roms)} ({matched} with controls, {unmatched} without)\n"
            f"Custom configs: {len(self.custom_configs)}"
        )
        self.stats_label.setText(stats)
    
    def find_unmatched_roms(self) -> Set[str]:
        """Find ROMs that don't have matching control data"""
        matched_roms = set()
        for rom in self.available_roms:
            if self.get_game_data(rom):
                matched_roms.add(rom)
        return self.available_roms - matched_roms
    
    def load_text_positions(self, rom_name):
        """Load text positions, with more reliable file path handling"""
        positions = {}
        
        # Create preview directory if it doesn't exist
        preview_dir = os.path.join(self.mame_dir, "preview")
        if not os.path.exists(preview_dir):
            os.makedirs(preview_dir)
            return positions  # Return empty positions if directory was just created
        
        # First try ROM-specific positions - with explicit path
        rom_positions_file = os.path.join(preview_dir, f"{rom_name}_positions.json")
        if os.path.exists(rom_positions_file):
            try:
                with open(rom_positions_file, 'r') as f:
                    positions = json.load(f)
                print(f"Loaded {len(positions)} ROM-specific positions from: {rom_positions_file}")
                return positions
            except Exception as e:
                print(f"Error loading ROM-specific positions: {e}")
        
        # Fall back to global positions - with explicit path
        global_positions_file = os.path.join(preview_dir, "global_positions.json")
        if os.path.exists(global_positions_file):
            try:
                with open(global_positions_file, 'r') as f:
                    positions = json.load(f)
                print(f"Loaded {len(positions)} positions from global file: {global_positions_file}")
            except Exception as e:
                print(f"Error loading global positions: {e}")
        
        return positions
    
    def load_text_appearance_settings(self):
        """Load text appearance settings from file"""
        settings = {
            "font_family": "Arial",
            "font_size": 28,
            "title_font_size": 36,
            "bold_strength": 2,
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
    
    def save_text_appearance_settings(self, settings):
        """Save text appearance settings to file"""
        try:
            settings_file = os.path.join(self.mame_dir, "text_appearance_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
            print(f"Saved text appearance settings: {settings}")
        except Exception as e:
            print(f"Error saving text appearance settings: {e}")
    
    def show_text_appearance_settings(self, update_preview=False):
        """Show dialog to configure text appearance for images"""
        # To be implemented with PyQt dialog
        print("Text appearance settings dialog to be implemented")
        
    def update_game_list(self):
        """Update the game list to show all available ROMs with visual enhancements"""
        self.game_list.clear()
        
        # Sort available ROMs
        available_roms = sorted(self.available_roms)
        
        for romname in available_roms:
            # Get game data
            game_data = self.get_game_data(romname)
            has_config = romname in self.custom_configs
            
            # Build the prefix
            prefix = "* " if has_config else "  "
            if game_data:
                prefix += "+ "
                display_name = f"{romname} - {game_data['gamename']}"
            else:
                prefix += "- "
                display_name = romname
            
            # Insert the line
            self.game_list.append(f"{prefix}{display_name}")
        
        print(f"\nGame List Update:")
        print(f"Total ROMs: {len(available_roms)}")
        print(f"ROMs with control data: {sum(1 for rom in available_roms if self.get_game_data(rom))}")
        print(f"ROMs with configs: {len(self.custom_configs)}")
    
    def filter_games(self, search_text):
        """Filter the game list based on search text"""
        search_text = search_text.lower()
        self.game_list.clear()
        
        # Sort available ROMs
        available_roms = sorted(self.available_roms)
        
        # Reset selection
        self.game_list.selected_line = None
        
        for romname in available_roms:
            # Get game data including variants
            game_data = self.get_game_data(romname)
            
            # Check if ROM matches search
            if (search_text in romname.lower() or 
                (game_data and search_text in game_data['gamename'].lower())):
                
                has_config = romname in self.custom_configs
                
                # Build the prefix
                prefix = "* " if has_config else "  "
                if game_data:
                    prefix += "+ "
                    display_name = f"{romname} - {game_data['gamename']}"
                else:
                    prefix += "- "
                    display_name = romname
                
                # Insert the line
                self.game_list.append(f"{prefix}{display_name}")
    
    def get_game_data(self, romname):
        """Get control data for a ROM from gamedata.json"""
        if not hasattr(self, 'gamedata_json'):
            self.load_gamedata_json()
            
        if romname in self.gamedata_json:
            game_data = self.gamedata_json[romname]
            
            # Simple name defaults
            default_actions = {
                'P1_JOYSTICK_UP': 'Up',
                'P1_JOYSTICK_DOWN': 'Down',
                'P1_JOYSTICK_LEFT': 'Left',
                'P1_JOYSTICK_RIGHT': 'Right',
                'P2_JOYSTICK_UP': 'Up',
                'P2_JOYSTICK_DOWN': 'Down',
                'P2_JOYSTICK_LEFT': 'Left',
                'P2_JOYSTICK_RIGHT': 'Right',
                'P1_BUTTON1': 'A Button',
                'P1_BUTTON2': 'B Button',
                'P1_BUTTON3': 'X Button',
                'P1_BUTTON4': 'Y Button',
                'P1_BUTTON5': 'LB Button',
                'P1_BUTTON6': 'RB Button',
                # Mirror P1 button names for P2
                'P2_BUTTON1': 'A Button',
                'P2_BUTTON2': 'B Button',
                'P2_BUTTON3': 'X Button',
                'P2_BUTTON4': 'Y Button',
                'P2_BUTTON5': 'LB Button',
                'P2_BUTTON6': 'RB Button',
            }
            
            # Basic structure conversion
            converted_data = {
                'romname': romname,
                'gamename': game_data.get('description', romname),
                'numPlayers': int(game_data.get('playercount', 1)),
                'alternating': game_data.get('alternating', False),
                'mirrored': False,
                'miscDetails': f"Buttons: {game_data.get('buttons', '?')}, Sticks: {game_data.get('sticks', '?')}",
                'players': []
            }
            
            # Find controls (direct or in a clone)
            controls = None
            if 'controls' in game_data:
                controls = game_data['controls']
            elif 'clones' in game_data:
                for clone in game_data['clones'].values():
                    if 'controls' in clone:
                        controls = clone['controls']
                        break
            
            if controls:
                # First pass - collect P1 button names to mirror to P2
                p1_button_names = {}
                for control_name, control_data in controls.items():
                    if control_name.startswith('P1_BUTTON') and 'name' in control_data:
                        button_num = control_name.replace('P1_BUTTON', '')
                        p1_button_names[f'P2_BUTTON{button_num}'] = control_data['name']
                        
                # Process player controls
                p1_controls = []
                p2_controls = []
                
                for control_name, control_data in controls.items():
                    # Add P1 controls
                    if control_name.startswith('P1_'):
                        # Skip non-joystick/button controls
                        if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                            # Get the friendly name
                            friendly_name = None
                            
                            # First check for explicit name
                            if 'name' in control_data:
                                friendly_name = control_data['name']
                            # Then check for default actions
                            elif control_name in default_actions:
                                friendly_name = default_actions[control_name]
                            # Fallback to control name
                            else:
                                parts = control_name.split('_')
                                if len(parts) > 1:
                                    friendly_name = parts[-1]
                                
                            if friendly_name:
                                p1_controls.append({
                                    'name': control_name,
                                    'value': friendly_name
                                })
                    
                    # Add P2 controls - prioritize matching P1 button names
                    elif control_name.startswith('P2_'):
                        if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                            friendly_name = None
                            
                            # First check for explicit name
                            if 'name' in control_data:
                                friendly_name = control_data['name']
                            # Then check if we have a matching P1 button name
                            elif control_name in p1_button_names:
                                friendly_name = p1_button_names[control_name]
                            # Then check defaults
                            elif control_name in default_actions:
                                friendly_name = default_actions[control_name]
                            # Fallback to control name
                            else:
                                parts = control_name.split('_')
                                if len(parts) > 1:
                                    friendly_name = parts[-1]
                                
                            if friendly_name:
                                p2_controls.append({
                                    'name': control_name,
                                    'value': friendly_name
                                })
                
                # Also check for special direction mappings (P1_UP, etc.)
                for control_name, control_data in controls.items():
                    if control_name == 'P1_UP' and 'name' in control_data:
                        # Update the joystick control if it exists
                        for control in p1_controls:
                            if control['name'] == 'P1_JOYSTICK_UP':
                                control['value'] = control_data['name']
                    elif control_name == 'P1_DOWN' and 'name' in control_data:
                        for control in p1_controls:
                            if control['name'] == 'P1_JOYSTICK_DOWN':
                                control['value'] = control_data['name']
                    elif control_name == 'P1_LEFT' and 'name' in control_data:
                        for control in p1_controls:
                            if control['name'] == 'P1_JOYSTICK_LEFT':
                                control['value'] = control_data['name']
                    elif control_name == 'P1_RIGHT' and 'name' in control_data:
                        for control in p1_controls:
                            if control['name'] == 'P1_JOYSTICK_RIGHT':
                                control['value'] = control_data['name']
                    # Also handle P2 directional controls the same way
                    elif control_name == 'P2_UP' and 'name' in control_data:
                        for control in p2_controls:
                            if control['name'] == 'P2_JOYSTICK_UP':
                                control['value'] = control_data['name']
                    elif control_name == 'P2_DOWN' and 'name' in control_data:
                        for control in p2_controls:
                            if control['name'] == 'P2_JOYSTICK_DOWN':
                                control['value'] = control_data['name']
                    elif control_name == 'P2_LEFT' and 'name' in control_data:
                        for control in p2_controls:
                            if control['name'] == 'P2_JOYSTICK_LEFT':
                                control['value'] = control_data['name']
                    elif control_name == 'P2_RIGHT' and 'name' in control_data:
                        for control in p2_controls:
                            if control['name'] == 'P2_JOYSTICK_RIGHT':
                                control['value'] = control_data['name']
                
                # Sort controls by name to ensure consistent order (Button 1 before Button 2)
                p1_controls.sort(key=lambda x: x['name'])
                p2_controls.sort(key=lambda x: x['name'])
                            
                # Add player 1 if we have controls
                if p1_controls:
                    converted_data['players'].append({
                        'number': 1,
                        'numButtons': int(game_data.get('buttons', 1)),
                        'labels': p1_controls
                    })

                # Add player 2 if we have controls
                if p2_controls:
                    converted_data['players'].append({
                        'number': 2,
                        'numButtons': int(game_data.get('buttons', 1)),
                        'labels': p2_controls
                    })
                
            # Mark as gamedata source
            converted_data['source'] = 'gamedata.json'
            return converted_data
            
        # Try parent lookup if direct lookup failed
        if romname in self.gamedata_json and 'parent' in self.gamedata_json[romname]:
            parent_rom = self.gamedata_json[romname]['parent']
            if parent_rom:
                # Recursive call to get parent data
                parent_data = self.get_game_data(parent_rom)
                if parent_data:
                    # Update with this ROM's info
                    parent_data['romname'] = romname
                    parent_data['gamename'] = self.gamedata_json[romname].get('description', f"{romname} (Clone)")
                    return parent_data
        
        # Not found
        return None
        
    def select_first_rom(self):
        """Select and display the first available ROM"""
        print("\n=== Auto-selecting first ROM ===")
        
        try:
            # Get the first available ROM that has game data
            available_games = sorted([rom for rom in self.available_roms if self.get_game_data(rom)])
            
            if not available_games:
                print("No ROMs with game data found")
                return
                
            first_rom = available_games[0]
            print(f"Selected first ROM: {first_rom}")
            
            # Find the corresponding line in the game list
            line_number = None
            for i in range(self.game_list.document().blockCount()):
                line = self.game_list.document().findBlockByNumber(i).text()
                if first_rom in line:
                    line_number = i + 1  # Lines are 1-indexed
                    break
            
            if line_number is None:
                print(f"Could not find '{first_rom}' in game list")
                return
            
            # Highlight the selected line
            self.game_list.highlight_line(line_number)
            
            # Update game data display
            self.on_game_selected(first_rom, line_number)
                
        except Exception as e:
            print(f"Error in auto-selection: {e}")
            import traceback
            traceback.print_exc()
    
    def on_game_selected(self, rom_name, line_number):
        """Handle game selection and display controls"""
        try:
            # Store current game
            self.current_game = rom_name
            
            # Get game data
            game_data = self.get_game_data(rom_name)
            
            # Clear existing control display
            for i in reversed(range(self.control_layout.count())):
                item = self.control_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
                
            if not game_data:
                # Clear display for ROMs without control data
                self.game_title.setText(f"No control data: {rom_name}")
                return
                
            # Update game title
            self.game_title.setText(game_data['gamename'])
            
            # Get custom controls if they exist
            cfg_controls = {}
            if rom_name in self.custom_configs:
                cfg_controls = self.parse_cfg_controls(self.custom_configs[rom_name])
                
                # Convert mappings if XInput is enabled
                if self.use_xinput:
                    cfg_controls = {
                        control: self.convert_mapping(mapping, True)
                        for control, mapping in cfg_controls.items()
                    }
            
            # Create basic game info section
            info_frame = QFrame()
            info_frame.setFrameShape(QFrame.StyledPanel)
            info_layout = QVBoxLayout(info_frame)
            
            # Game info with larger font and better spacing
            info_text = (
                f"ROM: {game_data['romname']}\n\n"
                f"Players: {game_data['numPlayers']}\n"
                f"Alternating: {game_data['alternating']}\n"
                f"Mirrored: {game_data['mirrored']}"
            )
            if game_data.get('miscDetails'):
                info_text += f"\n\nDetails: {game_data['miscDetails']}"
                
            info_label = QLabel(info_text)
            info_label.setFont(QFont("Arial", 14))
            info_label.setWordWrap(True)
            info_layout.addWidget(info_label)
            
            self.control_layout.addWidget(info_frame)
            
            # Create column headers
            header_frame = QFrame()
            header_frame.setFrameShape(QFrame.StyledPanel)
            header_layout = QHBoxLayout(header_frame)
            
            headers = ["Control", "Default Action", "Current Mapping"]
            header_weights = [2, 2, 3]
            
            for header, weight in zip(headers, header_weights):
                header_label = QLabel(header)
                header_label.setFont(QFont("Arial", 14, QFont.Bold))
                header_layout.addWidget(header_label, weight)
                
            self.control_layout.addWidget(header_frame)
            
            # Create controls list frame
            controls_frame = QFrame()
            controls_frame.setFrameShape(QFrame.StyledPanel)
            controls_layout = QGridLayout(controls_frame)
            
            # Display control comparisons
            comparisons = self.compare_controls(game_data, cfg_controls)
            for row, (control_name, default_label, current_mapping, is_different) in enumerate(comparisons):
                # Control name
                display_control = self.format_control_name(control_name)
                name_label = QLabel(display_control)
                name_label.setFont(QFont("Arial", 12))
                controls_layout.addWidget(name_label, row, 0)
                
                # Default action
                default_action_label = QLabel(default_label)
                default_action_label.setFont(QFont("Arial", 12))
                controls_layout.addWidget(default_action_label, row, 1)
                
                # Current mapping
                display_mapping = self.format_mapping_display(current_mapping)
                mapping_label = QLabel(display_mapping)
                mapping_label.setFont(QFont("Arial", 12))
                if is_different:
                    mapping_label.setStyleSheet("color: yellow;")
                controls_layout.addWidget(mapping_label, row, 2)
            
            self.control_layout.addWidget(controls_frame)
            
            # Display raw custom config if it exists
            if rom_name in self.custom_configs:
                custom_header = QLabel("RAW CONFIGURATION FILE")
                custom_header.setFont(QFont("Arial", 16, QFont.Bold))
                self.control_layout.addWidget(custom_header)
                
                custom_text = QTextEdit()
                custom_text.setReadOnly(True)
                custom_text.setFont(QFont("Courier New", 10))
                custom_text.setMinimumHeight(200)
                custom_text.setText(self.custom_configs[rom_name])
                self.control_layout.addWidget(custom_text)
                
            # Add spacer at the bottom
            self.control_layout.addStretch()
                
        except Exception as e:
            print(f"Error displaying game: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def compare_controls(self, game_data: Dict, cfg_controls: Dict) -> List[Tuple[str, str, str, bool]]:
        """Compare controls with game-specific and default mappings"""
        comparisons = []
        
        # Debug output
        has_defaults = hasattr(self, 'default_controls') and self.default_controls
        print(f"Compare controls: ROM={game_data['romname']}, " 
            f"Custom CFG={len(cfg_controls)}, "
            f"Default Controls Available={has_defaults and len(self.default_controls)}, "
            f"XInput={self.use_xinput}")
        
        # Convert default controls to XInput if needed
        default_controls = {}
        if has_defaults:
            for control, mapping in self.default_controls.items():
                if self.use_xinput:
                    default_controls[control] = self.convert_mapping(mapping, True)
                else:
                    default_controls[control] = mapping
        
        # Get default controls from game data
        for player in game_data.get('players', []):
            player_num = player['number']
            for label in player.get('labels', []):
                control_name = label['name']
                default_label = label['value']
                
                # Game-specific cfg has highest priority
                if control_name in cfg_controls:
                    current_mapping = cfg_controls[control_name]
                    is_different = True  # Custom mapping
                # Default.cfg has second priority - already converted to XInput if needed
                elif control_name in default_controls:
                    current_mapping = default_controls[control_name]
                    is_different = False  # Default mapping from default.cfg
                else:
                    current_mapping = "Not mapped"
                    is_different = False
                    
                comparisons.append((control_name, default_label, current_mapping, is_different))
        
        # Debug - print a few samples
        if comparisons:
            print(f"Generated {len(comparisons)} control comparisons. Samples:")
            for i, (name, label, mapping, diff) in enumerate(comparisons[:3]):
                src = "Custom" if diff else ("Default" if mapping != "Not mapped" else "None")
                print(f"  {name}: {label} -> {mapping} ({src})")
        
        return comparisons
    
    def convert_mapping(self, mapping: str, to_xinput: bool) -> str:
        """Convert between JOYCODE and XInput mappings"""
        xinput_mappings = {
            'JOYCODE_1_BUTTON1': 'XINPUT_1_A',           # A Button
            'JOYCODE_1_BUTTON2': 'XINPUT_1_B',           # B Button
            'JOYCODE_1_BUTTON3': 'XINPUT_1_X',           # X Button
            'JOYCODE_1_BUTTON4': 'XINPUT_1_Y',           # Y Button
            'JOYCODE_1_BUTTON5': 'XINPUT_1_SHOULDER_L',  # Left Bumper
            'JOYCODE_1_BUTTON6': 'XINPUT_1_SHOULDER_R',  # Right Bumper
            'JOYCODE_1_BUTTON7': 'XINPUT_1_TRIGGER_L',   # Left Trigger
            'JOYCODE_1_BUTTON8': 'XINPUT_1_TRIGGER_R',   # Right Trigger
            'JOYCODE_1_BUTTON9': 'XINPUT_1_THUMB_L',     # Left Stick Button
            'JOYCODE_1_BUTTON10': 'XINPUT_1_THUMB_R',    # Right Stick Button
            'JOYCODE_1_HATUP': 'XINPUT_1_DPAD_UP',       # D-Pad Up
            'JOYCODE_1_HATDOWN': 'XINPUT_1_DPAD_DOWN',   # D-Pad Down
            'JOYCODE_1_HATLEFT': 'XINPUT_1_DPAD_LEFT',   # D-Pad Left
            'JOYCODE_1_HATRIGHT': 'XINPUT_1_DPAD_RIGHT', # D-Pad Right
            'JOYCODE_2_BUTTON1': 'XINPUT_2_A',           # A Button
            'JOYCODE_2_BUTTON2': 'XINPUT_2_B',           # B Button
            'JOYCODE_2_BUTTON3': 'XINPUT_2_X',           # X Button
            'JOYCODE_2_BUTTON4': 'XINPUT_2_Y',           # Y Button
            'JOYCODE_2_BUTTON5': 'XINPUT_2_SHOULDER_L',  # Left Bumper
            'JOYCODE_2_BUTTON6': 'XINPUT_2_SHOULDER_R',  # Right Bumper
            'JOYCODE_2_BUTTON7': 'XINPUT_2_TRIGGER_L',   # Left Trigger
            'JOYCODE_2_BUTTON8': 'XINPUT_2_TRIGGER_R',   # Right Trigger
            'JOYCODE_2_BUTTON9': 'XINPUT_2_THUMB_L',     # Left Stick Button
            'JOYCODE_2_BUTTON10': 'XINPUT_2_THUMB_R',    # Right Stick Button
            'JOYCODE_2_HATUP': 'XINPUT_2_DPAD_UP',       # D-Pad Up
            'JOYCODE_2_HATDOWN': 'XINPUT_2_DPAD_DOWN',   # D-Pad Down
            'JOYCODE_2_HATLEFT': 'XINPUT_2_DPAD_LEFT',   # D-Pad Left
            'JOYCODE_2_HATRIGHT': 'XINPUT_2_DPAD_RIGHT', # D-Pad Right
        }
        joycode_mappings = {v: k for k, v in xinput_mappings.items()}
        
        if to_xinput:
            return xinput_mappings.get(mapping, mapping)
        else:
            return joycode_mappings.get(mapping, mapping)
    
    def format_control_name(self, control_name: str) -> str:
        """Convert MAME control names to friendly names based on input type"""
        if not self.use_xinput:
            return control_name
            
        # Split control name into parts (e.g., 'P1_BUTTON1' -> ['P1', 'BUTTON1'])
        parts = control_name.split('_')
        if len(parts) < 2:
            return control_name
            
        player_num = parts[0]  # e.g., 'P1'
        control_type = '_'.join(parts[1:])  # Join rest in case of JOYSTICK_UP etc.
        
        # Mapping dictionary for controls based on official XInput mapping
        control_mappings = {
            'BUTTON1': 'A Button',
            'BUTTON2': 'B Button',
            'BUTTON3': 'X Button',
            'BUTTON4': 'Y Button',
            'BUTTON5': 'LB Button',
            'BUTTON6': 'RB Button',
            'BUTTON7': 'LT Button',      # Left Trigger (axis)
            'BUTTON8': 'RT Button',      # Right Trigger (axis)
            'BUTTON9': 'LSB Button',     # Left Stick Button
            'BUTTON10': 'RSB Button',    # Right Stick Button
            'JOYSTICK_UP': 'Left Stick (Up)',
            'JOYSTICK_DOWN': 'Left Stick (Down)',
            'JOYSTICK_LEFT': 'Left Stick (Left)',
            'JOYSTICK_RIGHT': 'Left Stick (Right)',
            'JOYSTICK2_UP': 'Right Stick (Up)',
            'JOYSTICK2_DOWN': 'Right Stick (Down)',
            'JOYSTICK2_LEFT': 'Right Stick (Left)',
            'JOYSTICK2_RIGHT': 'Right Stick (Right)',
        }
        
        # Check if we have a mapping for this control
        if control_type in control_mappings:
            return f"{player_num} {control_mappings[control_type]}"
        
        return control_name
    
    def format_mapping_display(self, mapping: str) -> str:
        """Format the mapping string for display"""
        # Handle XInput mappings
        if "XINPUT" in mapping:
            # Convert XINPUT_1_A to "XInput A"
            parts = mapping.split('_')
            if len(parts) >= 3:
                button_part = ' '.join(parts[2:])
                return f"XInput {button_part}"
                
        # Handle JOYCODE mappings
        elif "JOYCODE" in mapping:
            # Special handling for axis/stick controls
            if "YAXIS_UP" in mapping or "DPADUP" in mapping:
                return "Joy Stick Up"
            elif "YAXIS_DOWN" in mapping or "DPADDOWN" in mapping:
                return "Joy Stick Down"
            elif "XAXIS_LEFT" in mapping or "DPADLEFT" in mapping:
                return "Joy Stick Left"
            elif "XAXIS_RIGHT" in mapping or "DPADRIGHT" in mapping:
                return "Joy Stick Right"
            elif "RYAXIS_NEG" in mapping:  # Right stick Y-axis negative
                return "Joy Right Stick Up"
    
    def generate_all_configs(self):
        """Generate config files for all available ROMs"""
        # Implementation will be added later
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Not Implemented", "This feature will be implemented in a future version.")
    
    def generate_all_configs(self):
        """Generate config files for all available ROMs"""
        # Implementation will be added later
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Not Implemented", "This feature will be implemented in a future version.")

    def show_generate_images_dialog(self):
        """Show dialog to configure image generation"""
        # Implementation will be added later
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Not Implemented", "This feature will be implemented in a future version.")

    def show_text_appearance_settings(self, update_preview=False):
        """Show dialog to configure text appearance for images"""
        # Implementation will be added later
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Not Implemented", "Text appearance settings will be implemented in a future version.")

    def show_unmatched_roms(self):
        """Display ROMs that don't have matching control data"""
        # Implementation will be added later
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Not Implemented", "Unmatched ROMs dialog will be implemented in a future version.")

    def show_preview_standalone(self, rom_name, auto_close=False):
        """Show the preview for a specific ROM in standalone mode"""
        # Set the current game
        self.current_game = rom_name
        
        # Show the preview
        self.show_preview()