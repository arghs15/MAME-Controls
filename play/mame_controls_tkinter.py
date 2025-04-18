import sys
import os
import json
import re
import subprocess
from typing import Dict, Optional, Set, List, Tuple
import xml.etree.ElementTree as ET
import customtkinter as ctk
from tkinter import messagebox, StringVar, scrolledtext, Frame, Label, PhotoImage, TclError


def get_application_path():
    """Get the base path for the application (handles PyInstaller bundling)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


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
            settings = self.parent.load_text_appearance_settings()  # Use direct method call
            y_offset = settings.get("y_offset", -40)
        
        # Remove y-offset
        normalized_y = y - y_offset
        return x, normalized_y
    
    def apply_offset(self, x, normalized_y, y_offset=None):
        """Apply y-offset to a normalized position for display"""
        if y_offset is None:
            # Get from settings if not provided
            settings = self.parent.load_text_appearance_settings()  # Use direct method call
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


class MAMEControlConfig(ctk.CTk):
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

        # Configure the window
        self.title("MAME Control Configuration Checker")
        self.geometry("1024x768")
        self.fullscreen = True  # Track fullscreen state
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        # Bind F11 key for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        
        self.selected_line = None
        self.highlight_tag = "highlight"
        
        # Set initial fullscreen state
        self.after(100, self.state, 'zoomed')  # Use zoomed for Windows
        
        # Find necessary directories
        self.mame_dir = self.find_mame_directory()
        if not self.mame_dir:
            messagebox.showerror("Error", "Please place this script in the MAME directory!")
            self.quit()
            return

        # Create the interface
        self.create_layout()
        
        # Load all data
        self.load_all_data()
    
    def get_game_data(self, romname):
        """Get control data for a ROM from gamedata.json with improved clone handling"""
        if not hasattr(self, 'gamedata_json'):
            self.load_gamedata_json()
            
        # Debug output
        #print(f"\nLooking up game data for: {romname}")
        
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
            
            # Check if this is a clone and needs to inherit controls from parent
            needs_parent_controls = False
            
            # Find controls (direct or in a clone)
            controls = None
            if 'controls' in game_data:
                controls = game_data['controls']
                #print(f"Found direct controls for {romname}")
            else:
                needs_parent_controls = True
                #print(f"No direct controls for {romname}, needs parent controls")
                
            # If no controls and this is a clone, try to use parent controls
            if needs_parent_controls:
                parent_rom = None
                
                # Check explicit parent field (should be there from load_gamedata_json)
                if 'parent' in game_data:
                    parent_rom = game_data['parent']
                    #print(f"Found parent {parent_rom} via direct reference")
                
                # Also check parent lookup table for redundancy
                elif hasattr(self, 'parent_lookup') and romname in self.parent_lookup:
                    parent_rom = self.parent_lookup[romname]
                    #print(f"Found parent {parent_rom} via lookup table")
                
                # If we found a parent, try to get its controls
                if parent_rom and parent_rom in self.gamedata_json:
                    parent_data = self.gamedata_json[parent_rom]
                    if 'controls' in parent_data:
                        controls = parent_data['controls']
                        #print(f"Using controls from parent {parent_rom} for clone {romname}")
            
            # Now process the controls (either direct or inherited from parent)
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
    
    def parse_cfg_controls(self, cfg_content: str) -> Dict[str, str]:
        """Parse MAME cfg file to extract control mappings"""
        controls = {}
        try:
            import xml.etree.ElementTree as ET
            from io import StringIO
            
            # Parse the XML content
            parser = ET.XMLParser(encoding='utf-8')
            tree = ET.parse(StringIO(cfg_content), parser=parser)
            root = tree.getroot()
            
            # Find all port elements under input
            input_elem = root.find('.//input')
            if input_elem is not None:
                print("Found input element")
                for port in input_elem.findall('port'):
                    control_type = port.get('type')
                    if control_type and control_type.startswith('P') and ('BUTTON' in control_type or 'JOYSTICK' in control_type):
                        # Find the newseq element for the mapping
                        newseq = port.find('.//newseq')
                        if newseq is not None and newseq.text:
                            mapping = newseq.text.strip()
                            controls[control_type] = mapping
                            print(f"Found mapping: {control_type} -> {mapping}")
            else:
                print("No input element found in XML")
                
        except ET.ParseError as e:
            print(f"XML parsing failed with error: {str(e)}")
            print("First 100 chars of content:", repr(cfg_content[:100]))
        except Exception as e:
            print(f"Unexpected error parsing cfg: {str(e)}")
            
        print(f"Found {len(controls)} control mappings")
        if controls:
            print("Sample mappings:")
            for k, v in list(controls.items())[:3]:
                print(f"  {k}: {v}")
                
        return controls
    
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
    
    def generate_all_configs(self):
        """Generate config files for all available ROMs from gamedata.json"""
        messagebox.showinfo("Coming Soon", "This feature will be implemented in a future update.")

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen state"""
        self.fullscreen = not self.fullscreen
        self.attributes('-fullscreen', self.fullscreen)
        
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.fullscreen = False
        self.attributes('-fullscreen', False)

    def find_mame_directory(self) -> Optional[str]:
        """Find the MAME directory containing necessary files"""
        # First check in the application directory
        app_dir = get_application_path()
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

    def toggle_xinput(self):
        """Handle toggling between JOYCODE and XInput mappings"""
        self.use_xinput = self.xinput_toggle.get()
        print(f"XInput toggle set to: {self.use_xinput}")
        
        # Refresh the current game display if one is selected
        if self.current_game and self.selected_line is not None:
            # Store the current scroll position
            scroll_pos = self.control_frame._scrollbar.get()
            
            # Create a mock event with coordinates for the selected line
            class MockEvent:
                def __init__(self_mock, line_num):
                    # Calculate position to hit the middle of the line
                    bbox = self.game_list.bbox(f"{line_num}.0")
                    if bbox:
                        self_mock.x = bbox[0] + 5  # A bit to the right of line start
                        self_mock.y = bbox[1] + 5  # A bit below line top
                    else:
                        self_mock.x = 5
                        self_mock.y = line_num * 20  # Approximate line height
            
            # Create the mock event targeting our current line
            mock_event = MockEvent(self.selected_line)
            
            # Force a full refresh of the display
            self.on_game_select(mock_event)
            
            # Restore scroll position
            self.control_frame._scrollbar.set(*scroll_pos)

    def toggle_ingame_mode(self):
        """Toggle between normal and in-game display modes"""
        if self.ingame_toggle.get():
            self.switch_to_ingame_mode()
        else:
            # Create mock event to reuse existing game select logic
            class MockEvent:
                def __init__(self):
                    self.x = 0
                    self.y = 5
            self.on_game_select(MockEvent())

    def switch_to_ingame_mode(self):
        """Switch to a simplified, large-format display for in-game reference"""
        if not self.current_game:
            return
            
        # Clear existing display
        for widget in self.control_frame.winfo_children():
            widget.destroy()
            
        # Get the current game's controls
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            return
            
        # Get custom controls
        cfg_controls = {}
        if self.current_game in self.custom_configs:
            cfg_controls = self.parse_cfg_controls(self.custom_configs[self.current_game])
            if self.use_xinput:
                cfg_controls = {
                    control: self.convert_mapping(mapping, True)
                    for control, mapping in cfg_controls.items()
                }

        # Configure single column layout
        self.control_frame.grid_columnconfigure(0, weight=1)

        # Create controls display with large font
        controls_frame = ctk.CTkFrame(self.control_frame)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        row = 0
        for player in game_data.get('players', []):
            # Player header
            player_label = ctk.CTkLabel(
                controls_frame,
                text=f"Player {player['number']}",
                font=("Arial", 24, "bold")
            )
            player_label.grid(row=row, column=0, padx=10, pady=(20,10), sticky="w")
            row += 1
            
            # Player controls
            for label in player.get('labels', []):
                control_name = label['name']
                default_action = label['value']
                current_mapping = cfg_controls.get(control_name, "Default")
                
                display_control = self.format_control_name(control_name)
                display_mapping = self.format_mapping_display(current_mapping)
                
                # Create a frame for each control to better organize the information
                control_frame = ctk.CTkFrame(controls_frame)
                control_frame.grid(row=row, column=0, padx=20, pady=5, sticky="ew")
                control_frame.grid_columnconfigure(1, weight=1)  # Make action column expandable
                
                # Control name
                ctk.CTkLabel(
                    control_frame,
                    text=display_control,
                    font=("Arial", 20, "bold"),
                    anchor="w"
                ).grid(row=0, column=0, padx=5, pady=2, sticky="w")

                # Default action
                default_label = ctk.CTkLabel(
                    control_frame,
                    text=f"Action: {default_action}",
                    font=("Arial", 18),
                    text_color="gray75",
                    anchor="w"
                )
                default_label.grid(row=1, column=0, columnspan=2, padx=20, pady=2, sticky="w")
                
                # Current mapping (if different from default)
                if current_mapping != "Default":
                    mapping_label = ctk.CTkLabel(
                        control_frame,
                        text=f"Mapped to: {display_mapping}",
                        font=("Arial", 18),
                        text_color="yellow",
                        anchor="w"
                    )
                    mapping_label.grid(row=2, column=0, columnspan=2, padx=20, pady=2, sticky="w")
                
                row += 1

    def create_layout(self):
        """Create the main application layout"""
        # Configure grid
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # Create left panel (game list)
        self.left_panel = ctk.CTkFrame(self)
        self.left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(2, weight=1)

        # Create stats frame at the top of left panel
        self.stats_frame = ctk.CTkFrame(self.left_panel)
        self.stats_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.stats_frame.grid_columnconfigure(1, weight=1)
        self.stats_frame.grid_columnconfigure(3, weight=0)

        # Stats label
        self.stats_label = ctk.CTkLabel(self.stats_frame, text="Loading...", 
                                    font=("Arial", 12))
        self.stats_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Unmatched ROMs button
        self.unmatched_button = ctk.CTkButton(
            self.stats_frame,
            text="Show Unmatched ROMs",
            command=self.show_unmatched_roms,
            width=150
        )
        self.unmatched_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # Generate configs button
        self.generate_configs_button = ctk.CTkButton(
            self.stats_frame,
            text="Generate Info Files",
            command=self.generate_all_configs,
            width=150
        )
        self.generate_configs_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        # Search box
        self.search_var = StringVar()
        self.search_var.trace("w", self.filter_games)
        self.search_entry = ctk.CTkEntry(self.left_panel, 
                                    placeholder_text="Search games...",
                                    textvariable=self.search_var)
        self.search_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Game list with improved styling
        self.game_list = ctk.CTkTextbox(self.left_panel, font=("Arial", 13))
        self.game_list.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        self.game_list._textbox.tag_configure(self.highlight_tag, background="#1a5fb4", foreground="white")
        self.game_list.configure(padx=5, pady=5)
        self.game_list.bind("<Button-1>", self.on_game_select)

        # Create right panel (control display)
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(2, weight=1)

        # Game title
        self.game_title = ctk.CTkLabel(self.right_panel, 
                                    text="Select a game",
                                    font=("Arial", 20, "bold"))
        self.game_title.grid(row=0, column=0, padx=5, pady=5)

        # Add Preview button next to the game title
        self.preview_button = ctk.CTkButton(
            self.right_panel,
            text="Preview Controls",
            command=self.show_preview,
            width=150
        )
        self.preview_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.hide_buttons_toggle = ctk.CTkSwitch(
            self.right_panel,
            text="Hide Preview Buttons",
            command=self.toggle_hide_preview_buttons
        )
        self.hide_buttons_toggle.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        # Add XInput toggle switch
        self.xinput_toggle = ctk.CTkSwitch(
            self.right_panel,
            text="Use XInput Mappings",
            command=self.toggle_xinput
        )
        self.xinput_toggle.select()  # Set it on by default
        self.xinput_toggle.grid(row=1, column=0, padx=5, pady=5)

        # Add In-Game Mode toggle
        self.ingame_toggle = ctk.CTkSwitch(
            self.right_panel,
            text="In-Game Mode",
            command=self.toggle_ingame_mode
        )
        self.ingame_toggle.grid(row=1, column=1, padx=5, pady=5, sticky="e")

        # Controls display
        self.control_frame = ctk.CTkScrollableFrame(self.right_panel)
        self.control_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

    '''def show_preview(self):
        """Launch the PyQt preview window as a separate process"""
        if not self.current_game:
            messagebox.showinfo("No Game Selected", "Please select a game first")
            return
            
        # Get game data
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            messagebox.showinfo("No Control Data", f"No control data found for {self.current_game}")
            return
        
        # Launch preview as a separate process
        try:
            script_path = os.path.join(get_application_path(), "mame_controls_main.py")
            subprocess.Popen([
                sys.executable,
                script_path,
                "--preview-only",
                "--game", self.current_game
            ])
            print(f"Launched preview process for {self.current_game}")
        except Exception as e:
            print(f"Error launching preview: {e}")
            messagebox.showerror("Error", f"Failed to launch preview: {str(e)}")'''
    
    def show_preview(self):
        """Launch the PyQt preview window as a separate process"""
        if not self.current_game:
            messagebox.showinfo("No Game Selected", "Please select a game first")
            return
            
        # Get game data
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            messagebox.showinfo("No Control Data", f"No control data found for {self.current_game}")
            return
        
        # Launch preview as a separate process
        try:
            script_path = os.path.join(get_application_path(), "mame_controls_main.py")
            
            # Build command with appropriate flags
            command = [
                sys.executable,
                script_path,
                "--preview-only",
                "--game", self.current_game
            ]
            
            # Add hide buttons flag if enabled
            if hasattr(self, 'hide_preview_buttons') and self.hide_preview_buttons:
                command.append("--no-buttons")
                
            # Launch the process
            subprocess.Popen(command)
            print(f"Launched preview process for {self.current_game} with command: {command}")
        except Exception as e:
            print(f"Error launching preview: {e}")
            messagebox.showerror("Error", f"Failed to launch preview: {str(e)}")

    def toggle_hide_preview_buttons(self):
        """Toggle whether preview buttons should be hidden"""
        self.hide_preview_buttons = self.hide_buttons_toggle.get()
        
        # Save setting to config file
        self.save_settings()
        
    def save_settings(self):
        """Save current settings to a JSON file"""
        settings = {
            "preferred_preview_screen": getattr(self, 'preferred_preview_screen', 2),
            "visible_control_types": self.visible_control_types,
            "hide_preview_buttons": getattr(self, 'hide_preview_buttons', False)
        }
        
        settings_path = os.path.join(self.mame_dir, "control_config_settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

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
                        if self.hide_preview_buttons:
                            self.hide_buttons_toggle.select()
                        else:
                            self.hide_buttons_toggle.deselect()
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
            elif "RYAXIS_POS" in mapping:  # Right stick Y-axis positive
                return "Joy Right Stick Down"
            elif "RXAXIS_NEG" in mapping:  # Right stick X-axis negative
                return "Joy Right Stick Left"
            elif "RXAXIS_POS" in mapping:  # Right stick X-axis positive
                return "Joy Right Stick Right"
            
            # Standard button format for other joystick controls
            parts = mapping.split('_')
            if len(parts) >= 4:
                joy_num = parts[1]
                control_type = parts[2].capitalize()
                
                # Extract button number for BUTTON types
                if control_type == "Button" and len(parts) >= 4:
                    button_num = parts[3]
                    return f"Joy {joy_num} {control_type} {button_num}"
                else:
                    # Generic format for other controls
                    remainder = '_'.join(parts[3:])
                    return f"Joy {joy_num} {control_type} {remainder}"
                    
        return mapping
        
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
            
            # Check if the game list has content
            list_content = self.game_list.get("1.0", "end-1c")
            if not list_content.strip():
                print("Game list appears to be empty")
                return
            
            # Find the line with our ROM
            lines = list_content.split('\n')
            target_line = None
            
            for i, line in enumerate(lines):
                if first_rom in line:
                    target_line = i + 1  # Lines are 1-indexed in Tkinter
                    print(f"Found ROM on line {target_line}: '{line}'")
                    break
                    
            if target_line is None:
                print(f"Could not find '{first_rom}' in game list")
                return
            
            # Highlight the selected line
            self.highlight_selected_game(target_line)
            self.current_game = first_rom
            
            # Get game data
            game_data = self.get_game_data(first_rom)
            if game_data:
                # Update game title
                self.game_title.configure(text=game_data['gamename'])
                
                # Clear existing display
                for widget in self.control_frame.winfo_children():
                    widget.destroy()
                
                # Force display update by simulating a game selection
                # Create a mock event targeting the line
                class MockEvent:
                    def __init__(self):
                        self.x = 10
                        self.y = target_line * 20
                
                self.on_game_select(MockEvent())
                
                print(f"Auto-selected ROM: {first_rom}")
            else:
                print(f"No game data available for {first_rom}")
                
        except Exception as e:
            print(f"Error in auto-selection: {e}")
            import traceback
            traceback.print_exc()
            
    def highlight_selected_game(self, line_index):
        """Highlight the selected game in the list"""
        # Clear previous highlight if any
        if self.selected_line is not None:
            self.game_list._textbox.tag_remove(self.highlight_tag, f"{self.selected_line}.0", f"{self.selected_line + 1}.0")
        
        # Apply new highlight
        self.selected_line = line_index
        self.game_list._textbox.tag_add(self.highlight_tag, f"{line_index}.0", f"{line_index + 1}.0")
        
        # Ensure the selected item is visible
        self.game_list.see(f"{line_index}.0")
        
    def on_game_select(self, event):
        """Handle game selection and display controls"""
        try:
            # Get the selected game name
            index = self.game_list.index(f"@{event.x},{event.y}")
            
            # Get the line number (starting from 1)
            line_num = int(index.split('.')[0])
            
            # Get the text from this line
            line = self.game_list.get(f"{line_num}.0", f"{line_num}.0 lineend")
            
            # Highlight the selected line
            self.highlight_selected_game(line_num)
            
            # Remove prefix indicators
            if line.startswith("* "):
                line = line[2:]
            if line.startswith("+ ") or line.startswith("- "):
                line = line[2:]
                
            romname = line.split(" - ")[0]
            self.current_game = romname

            # Get game data including variants
            game_data = self.get_game_data(romname)
            
            # Clear existing display
            for widget in self.control_frame.winfo_children():
                widget.destroy()

            if not game_data:
                # Clear display for ROMs without control data
                self.game_title.configure(text=f"No control data: {romname}")
                return

            # Update game title
            self.game_title.configure(text=game_data['gamename'])

            # Configure columns for the controls table
            self.control_frame.grid_columnconfigure(0, weight=2)  # Control name
            self.control_frame.grid_columnconfigure(1, weight=2)  # Default action
            self.control_frame.grid_columnconfigure(2, weight=3)  # Current mapping

            row = 0

            # Basic game info - using a frame for better organization
            info_frame = ctk.CTkFrame(self.control_frame)
            info_frame.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
            info_frame.grid_columnconfigure(0, weight=1)

            # Game info with larger font and better spacing
            info_text = (
                f"ROM: {game_data['romname']}\n\n"
                f"Players: {game_data['numPlayers']}\n"
                f"Alternating: {game_data['alternating']}\n"
                f"Mirrored: {game_data['mirrored']}"
            )
            if game_data.get('miscDetails'):
                info_text += f"\n\nDetails: {game_data['miscDetails']}"

            info_label = ctk.CTkLabel(
                info_frame, 
                text=info_text,
                font=("Arial", 14),
                justify="left",
                anchor="w",
                wraplength=800
            )
            info_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
            row += 1

            # Get custom controls if they exist
            cfg_controls = {}
            if romname in self.custom_configs:
                cfg_controls = self.parse_cfg_controls(self.custom_configs[romname])
                
                # Convert mappings if XInput is enabled
                if self.use_xinput:
                    cfg_controls = {
                        control: self.convert_mapping(mapping, True)
                        for control, mapping in cfg_controls.items()
                    }

            # Column headers with consistent styling
            headers = ["Control", "Default Action", "Current Mapping"]
            header_frame = ctk.CTkFrame(self.control_frame)
            header_frame.grid(row=row, column=0, columnspan=3, padx=5, pady=(20,5), sticky="ew")
            
            for col, header in enumerate(headers):
                header_frame.grid_columnconfigure(col, weight=[2,2,3][col])
                header_label = ctk.CTkLabel(
                    header_frame,
                    text=header,
                    font=("Arial", 14, "bold")
                )
                header_label.grid(row=0, column=col, padx=5, pady=5, sticky="ew")
            row += 1

            # Create a frame for the controls list
            controls_frame = ctk.CTkFrame(self.control_frame)
            controls_frame.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
            for col in range(3):
                controls_frame.grid_columnconfigure(col, weight=[2,2,3][col])
            
            # Display control comparisons
            comparisons = self.compare_controls(game_data, cfg_controls)
            control_row = 0
            for control_name, default_label, current_mapping, is_different in comparisons:
                # Control name - now with formatting
                display_control = self.format_control_name(control_name)
                name_label = ctk.CTkLabel(
                    controls_frame,
                    text=display_control,
                    font=("Arial", 12)
                )
                name_label.grid(row=control_row, column=0, padx=5, pady=2, sticky="w")
                
                # Default action
                default_label = ctk.CTkLabel(
                    controls_frame,
                    text=default_label,
                    font=("Arial", 12)
                )
                default_label.grid(row=control_row, column=1, padx=5, pady=2, sticky="w")
                
                # Current mapping
                display_mapping = self.format_mapping_display(current_mapping)
                
                mapping_label = ctk.CTkLabel(
                    controls_frame,
                    text=display_mapping,
                    text_color="yellow" if is_different else None,
                    font=("Arial", 12)
                )
                mapping_label.grid(row=control_row, column=2, padx=5, pady=2, sticky="w")
                
                control_row += 1
            row += 1

            # Display raw custom config if it exists
            if romname in self.custom_configs:
                custom_header = ctk.CTkLabel(
                    self.control_frame,
                    text="RAW CONFIGURATION FILE",
                    font=("Arial", 16, "bold")
                )
                custom_header.grid(row=row, column=0, columnspan=3,
                                padx=5, pady=(20,5), sticky="w")
                row += 1

                custom_text = ctk.CTkTextbox(
                    self.control_frame,
                    height=200,
                    width=200  # The frame will expand this
                )
                custom_text.grid(row=row, column=0, columnspan=3,
                            padx=20, pady=5, sticky="ew")
                custom_text.insert("1.0", self.custom_configs[romname])
                custom_text.configure(state="disabled")

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
        
    def update_stats_label(self):
        """Update the statistics label"""
        unmatched = len(self.find_unmatched_roms())
        matched = len(self.available_roms) - unmatched
        stats = (
            f"Available ROMs: {len(self.available_roms)} ({matched} with controls, {unmatched} without)\n"
            f"Custom configs: {len(self.custom_configs)}"
        )
        self.stats_label.configure(text=stats)
    
    def find_unmatched_roms(self) -> Set[str]:
        """Find ROMs that don't have matching control data"""
        matched_roms = set()
        for rom in self.available_roms:
            if self.get_game_data(rom):
                matched_roms.add(rom)
        return self.available_roms - matched_roms
    
    def show_unmatched_roms(self):
        """Display ROMs that don't have matching control data"""
        # Categorize ROMs
        matched_roms = []
        unmatched_roms = []

        for rom in sorted(self.available_roms):
            game_data = self.get_game_data(rom)
            if game_data:
                game_name = game_data['gamename']
                matched_roms.append((rom, game_name))
            else:
                unmatched_roms.append(rom)

        # Create new window
        self.unmatched_dialog = ctk.CTkToplevel(self)
        self.unmatched_dialog.title("ROM Control Data Analysis")
        self.unmatched_dialog.geometry("800x600")
        
        # Make it modal
        self.unmatched_dialog.transient(self)
        self.unmatched_dialog.grab_set()
        
        # Create tabs
        tabview = ctk.CTkTabview(self.unmatched_dialog)
        tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Summary tab
        summary_tab = tabview.add("Summary")
        stats_text = (
            f"Total ROMs: {len(self.available_roms)}\n"
            f"Matched ROMs: {len(matched_roms)}\n"
            f"Unmatched ROMs: {len(unmatched_roms)}\n\n"
            f"Control data coverage: {(len(matched_roms) / max(len(self.available_roms), 1) * 100):.1f}%"
        )
        stats_label = ctk.CTkLabel(
            summary_tab,
            text=stats_text,
            font=("Arial", 14),
            justify="left"
        )
        stats_label.pack(padx=20, pady=20, anchor="w")
        
        # Unmatched ROMs tab
        unmatched_tab = tabview.add("Unmatched ROMs")
        if unmatched_roms:
            unmatched_text = ctk.CTkTextbox(unmatched_tab)
            unmatched_text.pack(expand=True, fill="both", padx=10, pady=10)
            
            for rom in sorted(unmatched_roms):
                unmatched_text.insert("end", f"{rom}\n")
                    
            unmatched_text.configure(state="disabled")
        else:
            ctk.CTkLabel(
                unmatched_tab,
                text="No unmatched ROMs found!",
                font=("Arial", 14)
            ).pack(expand=True)
        
        # Matched ROMs tab 
        matched_tab = tabview.add("Matched ROMs")
        if matched_roms:
            matched_text = ctk.CTkTextbox(matched_tab)
            matched_text.pack(expand=True, fill="both", padx=10, pady=10)
            
            for rom, game_name in sorted(matched_roms):
                matched_text.insert("end", f"{rom} - {game_name}\n")
                
            matched_text.configure(state="disabled")
        else:
            ctk.CTkLabel(
                matched_tab,
                text="No matched ROMs found!",
                font=("Arial", 14)
            ).pack(expand=True)
        
        # Select Summary tab by default
        tabview.set("Summary")
        
        # Add export button with embedded export function
        def export_analysis():
            try:
                file_path = os.path.join(self.mame_dir, "control_analysis.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("MAME Control Data Analysis\n")
                    f.write("=========================\n\n")
                    f.write(stats_text + "\n\n")
                    
                    f.write("Matched ROMs:\n")
                    f.write("============\n")
                    for rom, game_name in sorted(matched_roms):
                        f.write(f"{rom} - {game_name}\n")
                    f.write("\n")
                    
                    f.write("Unmatched ROMs:\n")
                    f.write("==============\n")
                    for rom in sorted(unmatched_roms):
                        f.write(f"{rom}\n")
                        
                messagebox.showinfo("Export Complete", 
                                f"Analysis exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
        
        # Export button using the locally defined function
        export_button = ctk.CTkButton(
            self.unmatched_dialog,
            text="Export Analysis",
            command=export_analysis
        )
        export_button.pack(pady=10)
        
        # Add close button
        close_button = ctk.CTkButton(
            self.unmatched_dialog,
            text="Close",
            command=self.unmatched_dialog.destroy
        )
        close_button.pack(pady=10)
        
    def update_game_list(self):
        """Update the game list to show all available ROMs with visual enhancements"""
        self.game_list.delete("1.0", "end")
        
        # Sort available ROMs
        available_roms = sorted(self.available_roms)
        
        # Add alternating row backgrounds for better readability
        row_count = 0
        
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
            line_start = self.game_list.index("end-1c")
            self.game_list.insert("end", f"{prefix}{display_name}\n")
            
            # Apply alternate row background for better readability
            row_count += 1
            
        print(f"\nGame List Update:")
        print(f"Total ROMs: {len(available_roms)}")
        print(f"ROMs with control data: {sum(1 for rom in available_roms if self.get_game_data(rom))}")
        print(f"ROMs with configs: {len(self.custom_configs)}")

    def filter_games(self, *args):
        """Filter the game list based on search text"""
        search_text = self.search_var.get().lower()
        self.game_list.delete("1.0", "end")
        
        # Sort available ROMs
        available_roms = sorted(self.available_roms)
        
        # Reset the selected line when filtering
        self.selected_line = None
        
        # Add alternating row backgrounds for better readability
        row_count = 0
        
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
                line_start = self.game_list.index("end-1c")
                self.game_list.insert("end", f"{prefix}{display_name}\n")
                
                # Apply alternate row background for better readability
                row_count += 1
    
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
    
    def load_gamedata_json(self):
        """Load and parse the gamedata.json file for control data with improved clone handling"""
        if hasattr(self, 'gamedata_json') and self.gamedata_json:
            # Already loaded
            return self.gamedata_json
                
        self.gamedata_json = {}
        self.parent_lookup = {}  # Add a dedicated parent lookup table
            
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
                    
                # Index clones with more explicit parent relationship
                if 'clones' in game_data:
                    for clone_name, clone_data in game_data['clones'].items():
                        # Store explicit parent reference
                        clone_data['parent'] = rom_name
                        # Also store in the parent lookup table
                        self.parent_lookup[clone_name] = rom_name
                        self.gamedata_json[clone_name] = clone_data
                        #print(f"Indexed clone {clone_name} with parent {rom_name}")
                
            #print(f"Loaded {len(self.gamedata_json)} games from gamedata.json")
            #print(f"Indexed {len(self.parent_lookup)} parent-clone relationships")
            return self.gamedata_json
                
        except Exception as e:
            print(f"Error loading gamedata.json: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
        
    # Add these remaining methods to the MAMEControlConfig class in mame_controls_tk.py:
    def ensure_preview_folder(self):
        """Create preview directory if it doesn't exist"""
        preview_dir = os.path.join(self.mame_dir, "preview")  # Keep as "preview" here
        if not os.path.exists(preview_dir):
            print(f"Creating preview directory: {preview_dir}")
            os.makedirs(preview_dir)
            
            # Copy any bundled preview images if running as executable
            if getattr(sys, 'frozen', False):
                bundled_preview = os.path.join(get_application_path(), "preview2")  # Use "preview2" here
                if os.path.exists(bundled_preview):
                    import shutil
                    for item in os.listdir(bundled_preview):
                        source = os.path.join(bundled_preview, item)
                        dest = os.path.join(preview_dir, item)
                        if os.path.isfile(source):
                            shutil.copy2(source, dest)
                            print(f"Copied: {item} to preview folder")
        return preview_dir

    def create_default_image(self, output_dir=None):
        """Create a default image if none exists"""
        if output_dir is None:
            output_dir = os.path.join(self.mame_dir, "preview")  # Default to preview directory
        
        # Check if default image already exists
        default_png_path = os.path.join(output_dir, "default.png")
        default_jpg_path = os.path.join(output_dir, "default.jpg")
        
        if os.path.exists(default_png_path):
            print("Default PNG image already exists")
            return default_png_path
        elif os.path.exists(default_jpg_path):
            print("Default JPG image already exists")
            return default_jpg_path
        
        # No default image found, create one
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a new black image
            img = Image.new('RGB', (1280, 720), color='black')
            
            # Get a drawing context
            draw = ImageDraw.Draw(img)
            
            # Draw some text
            try:
                font = ImageFont.truetype("arial.ttf", 32)
            except:
                font = ImageFont.load_default()
            
            draw.text((640, 300), "MAME Controls Preview", fill="white", anchor="mm", font=font)
            draw.text((640, 360), "Place game screenshots in preview folder", fill="gray", anchor="mm", font=font)
            draw.text((640, 420), "with rom name (e.g., pacman.png)", fill="gray", anchor="mm", font=font)
            
            # Save the image
            created_path = os.path.join(output_dir, "default.png")
            img.save(created_path)
            print(f"Created default image at: {created_path}")
            
            return created_path
        except ImportError:
            print("PIL not installed, cannot create default image")
            return None
        except Exception as e:
            print(f"Error creating default image: {e}")
            return None

    def is_control_visible(self, control_name):
        """Check if a control type should be visible based on current settings"""
        if "JOYSTICK" in control_name:
            return "JOYSTICK" in self.visible_control_types
        elif "BUTTON" in control_name:
            return "BUTTON" in self.visible_control_types
        return True

    def create_text_with_shadow(self, canvas, x, y, text, font):
        """Create text with shadow effect for better visibility"""
        # Create shadow text
        shadow = canvas.create_text(
            x + 2, y + 2,
            text=text,
            font=font,
            fill="black",
            anchor="sw"
        )
        
        # Create main text
        text_item = canvas.create_text(
            x, y,
            text=text,
            font=font,
            fill="white",
            anchor="sw"
        )
        
        return text_item, shadow

    def get_display_text(self, action, settings=None):
        """Get the display text with proper case according to settings"""
        if settings is None:
            settings = self.load_text_appearance_settings()
            
        use_uppercase = settings.get("use_uppercase", False)
        if use_uppercase:
            return action.upper()
        return action

    def get_tkfont(self, settings=None):
        """Create a TkFont object based on settings"""
        import tkinter.font as tkfont
        
        if settings is None:
            settings = self.load_text_appearance_settings()
            
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        
        # Apply scaling factor
        adjusted_font_size = self.apply_font_scaling(font_family, font_size)
        
        # Create font object
        font = tkfont.Font(family=font_family, size=adjusted_font_size, weight="bold")
        return font

    def apply_font_scaling(self, font_family, font_size):
        """Apply scaling factor for certain fonts that appear small"""
        # Scaling factors for various fonts
        scaling_factors = {
            "Times New Roman": 1.5,
            "Times": 1.5,
            "Georgia": 1.4,
            "Garamond": 1.7,
            "Baskerville": 1.6,
            "Palatino": 1.5,
            "Courier New": 1.3,
            "Courier": 1.3,
            "Consolas": 1.2,
            "Cambria": 1.4
        }
        
        # Apply scaling if font needs it
        scale = scaling_factors.get(font_family, 1.0)
        adjusted_font_size = int(font_size * scale)
        
        print(f"Font size adjustment: {font_family} - original: {font_size}, adjusted: {adjusted_font_size} (scale: {scale})")
        return adjusted_font_size
