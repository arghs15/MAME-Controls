import sys
import os
import json
import re
import subprocess
from typing import Dict, Optional, Set, List, Tuple
import xml.etree.ElementTree as ET
import customtkinter as ctk
from tkinter import messagebox, StringVar, scrolledtext, Frame, Label, PhotoImage, TclError

import tkinter as tk
from tkinter import ttk, messagebox


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

        # Generate configs button
        self.analyze_button = ctk.CTkButton(
            self.stats_frame,
            text="Analyze Controls",
            command=self.analyze_controls,
            width=150
        )
        self.analyze_button.grid(row=0, column=4, padx=5, pady=5, sticky="e")

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

        # Controls display
        self.control_frame = ctk.CTkScrollableFrame(self.right_panel)
        self.control_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    
    #######################################################################
    #CONFIF TO CREATE INFO FILES FOR RETROFE
    #- INFO FOLDER ENEDS TO BE IN PREVIEW\SETTINGS\INFO WITH A DEFAULT TEMPLATE
    ##########################################################################
    
    
    def create_info_directory(self):
        """Create info directory if it doesn't exist"""
        # Use application_path instead of __file__ for PyInstaller compatibility
        app_path = get_application_path()
        info_dir = os.path.join(app_path, "preview", "settings", "info")
        if not os.path.exists(info_dir):
            os.makedirs(info_dir)
        return info_dir
    
    def generate_all_configs(self):
        """Generate config files for all available ROMs from gamedata.json"""
        info_dir = self.create_info_directory()
        print(f"Created/Found info directory at: {info_dir}")
        
        # First verify we have the template
        template = self.load_default_template()
        if not template:
            messagebox.showerror("Error", "Could not find default.conf template in info directory!")
            return
        print("Successfully loaded template")
        
        count = 0
        errors = []
        skipped = 0
        
        # Process all ROMs with control data
        roms_to_process = list(self.available_roms)
        
        total_roms = len(roms_to_process)
        print(f"Found {total_roms} ROMs to process")
        
        # Process each ROM
        for rom_name in roms_to_process:
            try:
                # Get game data
                game_data = self.get_game_data(rom_name)
                
                if game_data:
                    config_content = self.generate_game_config(game_data)
                    if config_content:
                        config_path = os.path.join(info_dir, f"{rom_name}.conf")
                        with open(config_path, 'w', encoding='utf-8') as f:
                            f.write(config_content)
                        count += 1
                        if count % 50 == 0:  # Progress update every 50 files
                            print(f"Generated {count}/{total_roms} config files...")
                    else:
                        print(f"Skipping {rom_name}: No config content generated")
                        skipped += 1
                else:
                    print(f"Skipping {rom_name}: No control data found")
                    skipped += 1
            except Exception as e:
                error_msg = f"Error with {rom_name}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        # Final report
        report = f"Generated {count} config files in {info_dir}\n"
        report += f"Skipped {skipped} ROMs\n"
        if errors:
            report += f"\nEncountered {len(errors)} errors:\n"
            report += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                report += f"\n...and {len(errors) - 5} more errors"
        
        print(report)
        messagebox.showinfo("Config Generation Report", report)
    
    def load_default_template(self):
        """Load the default.conf template with improved path handling for PyInstaller"""
        # Use application_path instead of __file__ for PyInstaller compatibility
        app_path = get_application_path()
        template_path = os.path.join(app_path, "preview", "settings", "info", "default.conf")
        
        # Debug output to help diagnose path issues
        print(f"\nLooking for default template at: {template_path}")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                print(f"Successfully loaded template ({len(template_content)} characters)")
                return template_content
        except Exception as e:
            print(f"Error loading template: {e}")
            
            # Try an alternate path for backwards compatibility
            alt_path = os.path.join(app_path, "preview", "info", "default.conf")
            print(f"Trying alternate path: {alt_path}")
            
            try:
                with open(alt_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                    print(f"Successfully loaded template from alternate path ({len(template_content)} characters)")
                    return template_content
            except Exception as alt_e:
                print(f"Error loading from alternate path: {alt_e}")
                
                # Last resort: create a default template on the fly
                print("Creating default template content")
                default_content = """# MAME Controls Info File
    # Auto-generated default template

    controller A t = A Button
    controller B t = B Button
    controller X t = X Button
    controller Y t = Y Button
    controller LB t = Left Bumper
    controller RB t = Right Bumper
    controller LT t = Left Trigger
    controller RT t = Right Trigger
    controller LSB t = Left Stick Button
    controller RSB t = Right Stick Button
    controller L-stick t = Left Stick
    controller R-stick t = Right Stick
    controller D-pad t = D-Pad
    """
                # Try to save this for future use
                try:
                    os.makedirs(os.path.dirname(template_path), exist_ok=True)
                    with open(template_path, 'w', encoding='utf-8') as f:
                        f.write(default_content)
                    print(f"Created new default template at: {template_path}")
                except Exception as save_e:
                    print(f"Could not save default template: {save_e}")
                    
                return default_content
    
    def generate_game_config(self, game_data: dict) -> str:
        """Generate config file content for a specific game"""
        template = self.load_default_template()
        if not template:
            return None
            
        # Split template into lines while preserving exact spacing
        template_lines = template.splitlines()
        output_lines = []
        
        # Get the position of the = sign from the template to maintain alignment
        equals_positions = []
        for line in template_lines:
            if '=' in line:
                pos = line.find('=')
                equals_positions.append(pos)
        
        # Get the maximum position to align all equals signs
        max_equals_pos = max(equals_positions) if equals_positions else 0
        
        # Process each line
        for line in template_lines:
            if '=' in line:
                # Split at equals but preserve original spacing
                field_part = line[:line.find('=')].rstrip()
                default_value = line[line.find('=')+1:].strip()
                
                # If it's a tooltip field (ends with 't')
                if field_part.strip().endswith('t'):
                    action_found = False
                    
                    # Look through game controls for a matching action
                    for player in game_data.get('players', []):
                        for label in player.get('labels', []):
                            control_name = label['name']
                            action = label['value']
                            
                            # Map control to config field
                            config_field, _ = self.map_control_to_xinput_config(control_name)
                            
                            if config_field == field_part.strip():
                                # Add the line with proper alignment and the action
                                padding = ' ' * (max_equals_pos - len(field_part))
                                output_lines.append(f"{field_part}{padding}= {action}")
                                action_found = True
                                break
                                
                    if not action_found:
                        # Keep original line with exact spacing
                        output_lines.append(line)
                else:
                    # For non-tooltip fields, keep the original line exactly
                    output_lines.append(line)
            else:
                # For lines without '=', keep them exactly as is
                output_lines.append(line)
        
        return '\n'.join(output_lines)
    
    def map_control_to_xinput_config(self, control_name: str) -> Tuple[str, str]:
        """Map MAME control to Xbox controller config field"""
        mapping_dict = {
            'P1_BUTTON1': ('controller A t', 'A Button'),      # A
            'P1_BUTTON2': ('controller B t', 'B Button'),      # B
            'P1_BUTTON3': ('controller X t', 'X Button'),      # X
            'P1_BUTTON4': ('controller Y t', 'Y Button'),      # Y
            'P1_BUTTON5': ('controller LB t', 'Left Bumper'),  # LB
            'P1_BUTTON6': ('controller RB t', 'Right Bumper'), # RB
            'P1_BUTTON7': ('controller LT t', 'Left Trigger'), # LT
            'P1_BUTTON8': ('controller RT t', 'Right Trigger'),# RT
            'P1_BUTTON9': ('controller LSB t', 'L3'),          # Left Stick Button
            'P1_BUTTON10': ('controller RSB t', 'R3'),         # Right Stick Button
            'P1_JOYSTICK_UP': ('controller L-stick t', 'Left Stick Up'),
            'P1_JOYSTICK_DOWN': ('controller L-stick t', 'Left Stick Down'),
            'P1_JOYSTICK_LEFT': ('controller L-stick t', 'Left Stick Left'),
            'P1_JOYSTICK_RIGHT': ('controller L-stick t', 'Left Stick Right'),
        }
        return mapping_dict.get(control_name, (None, None))
    
    '''#######################################################################
    CONFIF EDIT GAMES IN GAMEDATA.JSON
    - GAMEDATA JSON NEEDS OT BE IN MAME ROOT FODLER
    ##########################################################################
    '''
    
    def analyze_controls(self):
        """Comprehensive analysis of ROM controls with editing capabilities"""
        # Get data from both methods
        generic_games, missing_games = self.identify_generic_controls()
        matched_roms = set()
        for rom in self.available_roms:
            if self.get_game_data(rom):
                matched_roms.add(rom)
        unmatched_roms = self.available_roms - matched_roms
        
        # Identify default controls (games with real control data but not customized)
        default_games = []
        already_categorized = set([g[0] for g in generic_games]) | set(missing_games)
        for rom_name in sorted(matched_roms):
            if rom_name not in already_categorized:
                game_data = self.get_game_data(rom_name)
                if game_data and 'gamename' in game_data:
                    default_games.append((rom_name, game_data.get('gamename', rom_name)))
        
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("ROM Control Analysis")
        #dialog.geometry("800x600")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog on the screen
        dialog_width = 800
        dialog_height = 600

        # Get screen width and height
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        # Calculate position x, y
        x = int((screen_width / 2) - (dialog_width / 2))
        y = int((screen_height / 2) - (dialog_height / 2))

        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Create tabs
        tabview = ctk.CTkTabview(dialog)
        tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Summary tab
        summary_tab = tabview.add("Summary")
        stats_text = (
            f"Total ROMs: {len(self.available_roms)}\n"
            f"ROMs with control data: {len(matched_roms)}\n"
            f"ROMs without control data: {len(unmatched_roms)}\n\n"
            f"Control data breakdown:\n"
            f"- ROMs with generic controls: {len(generic_games)}\n"
            f"- ROMs with custom controls: {len(default_games)}\n"
            f"- ROMs with missing controls: {len(missing_games)}\n\n"
            f"Control data coverage: {(len(matched_roms) / max(len(self.available_roms), 1) * 100):.1f}%"
        )
        stats_label = ctk.CTkLabel(
            summary_tab,
            text=stats_text,
            font=("Arial", 14),
            justify="left"
        )
        stats_label.pack(padx=20, pady=20, anchor="w")
        
        # Create each tab with the better list UI from unmatched_roms
        self.create_game_list_with_edit(tabview.add("Generic Controls"), 
                                    generic_games, "ROMs with Generic Controls")
        self.create_game_list_with_edit(tabview.add("Missing Controls"), 
                                    [(rom, rom) for rom in missing_games], "ROMs with Missing Controls")
        self.create_game_list_with_edit(tabview.add("Custom Controls"), 
                                    default_games, "ROMs with Custom Controls")
        
        # Add export button
        def export_analysis():
            try:
                file_path = os.path.join(self.mame_dir, "controls_analysis.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("MAME Controls Analysis\n")
                    f.write("====================\n\n")
                    f.write(stats_text + "\n\n")
                    
                    f.write("Games with Generic Controls:\n")
                    f.write("==========================\n")
                    for rom, game_name in generic_games:
                        f.write(f"{rom} - {game_name}\n")
                    f.write("\n")
                    
                    f.write("Games with Missing Controls:\n")
                    f.write("==========================\n")
                    for rom in sorted(missing_games):
                        f.write(f"{rom}\n")
                    f.write("\n")
                    
                    f.write("Games with Custom Controls:\n")
                    f.write("==========================\n")
                    for rom, game_name in default_games:
                        f.write(f"{rom} - {game_name}\n")
                        
                messagebox.showinfo("Export Complete", 
                            f"Analysis exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
        
        # Export button
        export_button = ctk.CTkButton(
            dialog,
            text="Export Analysis",
            command=export_analysis
        )
        export_button.pack(pady=10)
        
        # Close button
        close_button = ctk.CTkButton(
            dialog,
            text="Close",
            command=dialog.destroy
        )
        close_button.pack(pady=10)
        
        # Select Summary tab by default
        tabview.set("Summary")
    
    def show_control_editor(self, rom_name, game_name=None):
        """Show editor for a game's controls with direct gamedata.json editing and standard button layout"""
        game_data = self.get_game_data(rom_name) or {}
        game_name = game_name or game_data.get('gamename', rom_name)
        
        # Check if this is an existing game or a new one
        is_new_game = not bool(game_data)
        
        # Create dialog
        editor = ctk.CTkToplevel(self)
        editor.title(f"{'Add New Game' if is_new_game else 'Edit Controls'} - {game_name}")
        editor.geometry("900x750")  # Made taller to accommodate all controls
        editor.transient(self)
        editor.grab_set()
        
        # Header
        header_frame = ctk.CTkFrame(editor)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            header_frame,
            text=f"{'Add New Game' if is_new_game else 'Edit Controls for'} {game_name}",
            font=("Arial", 16, "bold")
        ).pack(side=tk.LEFT, padx=10)
        
        # Game properties section (shown prominently for new games)
        properties_frame = ctk.CTkFrame(editor)
        properties_frame.pack(fill="x", padx=10, pady=10)
        
        # Add a label for the properties section
        ctk.CTkLabel(
            properties_frame,
            text="Game Properties",
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # Create grid for properties
        properties_grid = ctk.CTkFrame(properties_frame)
        properties_grid.pack(fill="x", padx=10, pady=5)
        
        # Get current values
        current_description = game_data.get('gamename', game_name) or rom_name
        current_playercount = game_data.get('numPlayers', 2)
        if isinstance(current_playercount, str):
            current_playercount = int(current_playercount)
        
        # For buttons and sticks, try to extract from miscDetails if available
        current_buttons = "6"  # Default
        current_sticks = "1"  # Default
        
        if 'miscDetails' in game_data:
            # Try to parse from miscDetails (format: "Buttons: X, Sticks: Y")
            details = game_data.get('miscDetails', '')
            buttons_match = re.search(r'Buttons: (\d+)', details)
            sticks_match = re.search(r'Sticks: (\d+)', details)
            
            if buttons_match:
                current_buttons = buttons_match.group(1)
            if sticks_match:
                current_sticks = sticks_match.group(1)
        
        # Row 0: Game Description (Name)
        ctk.CTkLabel(properties_grid, text="Game Name:", width=100).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        description_var = ctk.StringVar(value=current_description)
        description_entry = ctk.CTkEntry(properties_grid, width=300, textvariable=description_var)
        description_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Row 1: Player Count
        ctk.CTkLabel(properties_grid, text="Players:", width=100).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        playercount_var = ctk.StringVar(value=str(current_playercount))
        playercount_combo = ctk.CTkComboBox(properties_grid, width=100, values=["1", "2", "3", "4"], variable=playercount_var)
        playercount_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Set up players alternating option
        alternating_var = ctk.BooleanVar(value=game_data.get('alternating', False))
        alternating_check = ctk.CTkCheckBox(properties_grid, text="Alternating Play", variable=alternating_var)
        alternating_check.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        
        # Row 2: Buttons and Sticks
        ctk.CTkLabel(properties_grid, text="Buttons:", width=100).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        buttons_var = ctk.StringVar(value=current_buttons)
        buttons_combo = ctk.CTkComboBox(properties_grid, width=100, values=["1", "2", "3", "4", "5", "6", "8"], variable=buttons_var)
        buttons_combo.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(properties_grid, text="Sticks:", width=100).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        sticks_var = ctk.StringVar(value=current_sticks)
        sticks_combo = ctk.CTkComboBox(properties_grid, width=100, values=["0", "1", "2"], variable=sticks_var)
        sticks_combo.grid(row=2, column=3, padx=5, pady=5, sticky="w")
        
        # Set column weights
        properties_grid.columnconfigure(1, weight=1)
        properties_grid.columnconfigure(3, weight=1)
        
        # Main content frame with scrolling
        content_frame = ctk.CTkScrollableFrame(editor)
        content_frame.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Define standard controller buttons from the mapping dictionary
        standard_controls = [
            ('P1_BUTTON1', 'A Button'),
            ('P1_BUTTON2', 'B Button'),
            ('P1_BUTTON3', 'X Button'),
            ('P1_BUTTON4', 'Y Button'),
            ('P1_BUTTON5', 'Left Bumper (LB)'),
            ('P1_BUTTON6', 'Right Bumper (RB)'),
            ('P1_BUTTON7', 'Left Trigger (LT)'),
            ('P1_BUTTON8', 'Right Trigger (RT)'),
            ('P1_BUTTON9', 'Left Stick Button (L3)'),
            ('P1_BUTTON10', 'Right Stick Button (R3)'),
            ('P1_JOYSTICK_UP', 'Left Stick Up'),
            ('P1_JOYSTICK_DOWN', 'Left Stick Down'),
            ('P1_JOYSTICK_LEFT', 'Left Stick Left'),
            ('P1_JOYSTICK_RIGHT', 'Left Stick Right')
        ]
        
        # Create a dictionary to store all the entry fields
        control_entries = {}
        
        # Helper function to get existing action for a control
        def get_existing_action(control_name):
            for player in game_data.get('players', []):
                for label in player.get('labels', []):
                    if label.get('name') == control_name:
                        return label.get('value', '')
            return ''
        
        # Header for the controls
        header_frame = ctk.CTkFrame(content_frame)
        header_frame.pack(fill="x", pady=5)
        
        control_label = ctk.CTkLabel(header_frame, text="Control", width=200, font=("Arial", 14, "bold"))
        control_label.pack(side=tk.LEFT, padx=5)
        
        action_label = ctk.CTkLabel(header_frame, text="Action/Function (leave empty to skip)", width=300, font=("Arial", 14, "bold"))
        action_label.pack(side=tk.LEFT, padx=5)
        
        # Create entry fields for each standard control
        for control_name, display_name in standard_controls:
            # Create a frame for each control
            control_frame = ctk.CTkFrame(content_frame)
            control_frame.pack(fill="x", pady=5)
            
            # Button/control name display
            ctk.CTkLabel(control_frame, text=display_name, width=200).pack(side=tk.LEFT, padx=5)
            
            # Get existing action if available
            existing_action = get_existing_action(control_name)
            
            # Create entry for action
            action_entry = ctk.CTkEntry(control_frame, width=400)
            action_entry.insert(0, existing_action)
            action_entry.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
            
            # Store the entry widget in our dictionary
            control_entries[control_name] = action_entry
        
        # Add a section for custom controls
        custom_frame = ctk.CTkFrame(content_frame)
        custom_frame.pack(fill="x", pady=(20, 5))
        
        ctk.CTkLabel(
            custom_frame, 
            text="Add Custom Controls (Optional)", 
            font=("Arial", 14, "bold")
        ).pack(pady=5)
        
        # Frame to hold custom control entries
        custom_controls_frame = ctk.CTkFrame(content_frame)
        custom_controls_frame.pack(fill="x", pady=5)
        
        # List to track custom controls
        custom_control_rows = []
        
        # Function to add a new custom control row
        def add_custom_control_row():
            row_frame = ctk.CTkFrame(custom_controls_frame)
            row_frame.pack(fill="x", pady=2)
            
            # Control name entry
            control_entry = ctk.CTkEntry(row_frame, width=200, placeholder_text="Custom Control (e.g., P1_BUTTON11)")
            control_entry.pack(side=tk.LEFT, padx=5)
            
            # Action entry
            action_entry = ctk.CTkEntry(row_frame, width=400, placeholder_text="Action/Function")
            action_entry.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
            
            # Remove button
            def remove_row():
                row_frame.pack_forget()
                row_frame.destroy()
                if row_data in custom_control_rows:
                    custom_control_rows.remove(row_data)
            
            remove_button = ctk.CTkButton(
                row_frame,
                text="❌",
                width=30,
                command=remove_row
            )
            remove_button.pack(side=tk.LEFT, padx=5)
            
            # Store row data
            row_data = {'frame': row_frame, 'control': control_entry, 'action': action_entry}
            custom_control_rows.append(row_data)
            
            return row_data
        
        # Add first custom row
        add_custom_control_row()
        
        # Add button for additional rows
        add_custom_button = ctk.CTkButton(
            custom_controls_frame,
            text="+ Add Another Custom Control",
            command=add_custom_control_row
        )
        add_custom_button.pack(pady=10)
        
        # Instructions
        instructions_frame = ctk.CTkFrame(editor)
        instructions_frame.pack(fill="x", padx=10, pady=10)
        
        instructions_text = """
        Instructions:
        1. Enter the action/function for each standard control you want to include
        2. Leave fields empty for controls you don't want to add
        3. Use the custom section to add any non-standard controls
        4. Click Save to update the game's controls in the database
        """
        
        ctk.CTkLabel(
            instructions_frame,
            text=instructions_text,
            justify="left"
        ).pack(padx=10, pady=10, anchor="w")
        
        # Buttons frame
        button_frame = ctk.CTkFrame(editor)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        def save_controls():
            """Save controls directly to gamedata.json with support for adding missing games"""
            try:
                # Collect game properties
                game_description = description_var.get().strip() or game_name or rom_name
                game_playercount = playercount_var.get()
                game_buttons = buttons_var.get()
                game_sticks = sticks_var.get()
                game_alternating = alternating_var.get()
                
                # Load the gamedata.json file using centralized path
                gamedata_path = self.get_gamedata_path()
                with open(gamedata_path, 'r', encoding='utf-8') as f:
                    gamedata = json.load(f)
                
                # Find where to save the controls (main entry or clone)
                target_found = False
                
                # Process control entries - only include non-empty fields
                control_updates = {}
                
                # Add standard controls with non-empty values
                for control_name, entry in control_entries.items():
                    action_value = entry.get().strip()
                    
                    # Only add if action is not empty
                    if action_value:
                        control_updates[control_name] = action_value
                
                # Add custom controls with non-empty values
                for row_data in custom_control_rows:
                    control_name = row_data['control'].get().strip()
                    action_value = row_data['action'].get().strip()
                    
                    # Only add if both fields are filled
                    if control_name and action_value:
                        control_updates[control_name] = action_value
                
                print(f"Control updates to save: {len(control_updates)} controls")
                
                # Helper function to update controls in a gamedata structure
                def update_controls_in_data(data):
                    if 'controls' not in data:
                        data['controls'] = {}
                    
                    # First, check if we need to explicitly remove any controls
                    # This is for controls that existed in the original data but aren't in our updates
                    if 'controls' in data:
                        existing_controls = set(data['controls'].keys())
                        updated_controls = set(control_updates.keys())
                        
                        # Find controls that were in the original data but aren't in our updates
                        # These are ones that were explicitly removed or left blank
                        for removed_control in existing_controls - updated_controls:
                            # Remove from the data structure
                            if removed_control in data['controls']:
                                print(f"Removing control: {removed_control}")
                                del data['controls'][removed_control]
                    
                    # Update or add name attributes to controls
                    for control_name, action in control_updates.items():
                        if control_name in data['controls']:
                            # Update existing control
                            data['controls'][control_name]['name'] = action
                        else:
                            # Create new control with placeholder values
                            data['controls'][control_name] = {
                                'name': action,
                                'tag': '',
                                'mask': '0'
                            }
                            
                    return True
                
                # First check if the ROM has its own controls section
                if rom_name in gamedata and 'controls' in gamedata[rom_name]:
                    # Update the game properties too
                    gamedata[rom_name]['description'] = game_description
                    gamedata[rom_name]['playercount'] = game_playercount
                    gamedata[rom_name]['buttons'] = game_buttons
                    gamedata[rom_name]['sticks'] = game_sticks
                    gamedata[rom_name]['alternating'] = game_alternating
                    
                    update_controls_in_data(gamedata[rom_name])
                    target_found = True
                    
                # If not, check clones
                elif rom_name in gamedata and 'clones' in gamedata[rom_name]:
                    # Update the game properties too
                    gamedata[rom_name]['description'] = game_description
                    gamedata[rom_name]['playercount'] = game_playercount
                    gamedata[rom_name]['buttons'] = game_buttons
                    gamedata[rom_name]['sticks'] = game_sticks
                    gamedata[rom_name]['alternating'] = game_alternating
                    
                    # If ROM has no controls but has clones with controls, update the last clone
                    clone_with_controls = None
                    
                    for clone_name in gamedata[rom_name]['clones']:
                        if isinstance(gamedata[rom_name]['clones'], dict) and clone_name in gamedata[rom_name]['clones']:
                            clone_data = gamedata[rom_name]['clones'][clone_name]
                            if 'controls' in clone_data:
                                clone_with_controls = clone_name
                        
                    if clone_with_controls:
                        update_controls_in_data(gamedata[rom_name]['clones'][clone_with_controls])
                        target_found = True
                    else:
                        # No clone has controls either, add controls to the main ROM
                        update_controls_in_data(gamedata[rom_name])
                        target_found = True
                
                # If ROM is a clone, try to find it in its parent's clone list
                else:
                    clone_parent_found = False
                    for parent_name, parent_data in gamedata.items():
                        if 'clones' in parent_data and isinstance(parent_data['clones'], dict) and rom_name in parent_data['clones']:
                            # Update the clone's properties if supported
                            if isinstance(parent_data['clones'][rom_name], dict):
                                parent_data['clones'][rom_name]['description'] = game_description
                                parent_data['clones'][rom_name]['playercount'] = game_playercount
                                parent_data['clones'][rom_name]['buttons'] = game_buttons
                                parent_data['clones'][rom_name]['sticks'] = game_sticks
                                parent_data['clones'][rom_name]['alternating'] = game_alternating
                            
                            update_controls_in_data(parent_data['clones'][rom_name])
                            target_found = True
                            clone_parent_found = True
                            break
                    
                    # If it's not in any parent's clone list, it's a new game
                    if not clone_parent_found:
                        target_found = False
                
                # If no existing control structure was found anywhere, create a new entry
                if not target_found:
                    print(f"Game {rom_name} not found in gamedata.json - creating new entry")
                    # Create a new entry for this ROM
                    gamedata[rom_name] = {
                        "description": game_description,
                        "playercount": game_playercount,
                        "buttons": game_buttons,
                        "sticks": game_sticks,
                        "alternating": game_alternating,
                        "clones": {},
                        "controls": {}
                    }
                    
                    # Add all the controls to the new entry
                    update_controls_in_data(gamedata[rom_name])
                    target_found = True  # Now we have a target
                    
                    messagebox.showinfo(
                        "New Game Added", 
                        f"Added new game entry for {rom_name} to gamedata.json"
                    )
                
                # Save the updated gamedata back to the file
                with open(gamedata_path, 'w', encoding='utf-8') as f:
                    json.dump(gamedata, f, indent=2)
                    
                messagebox.showinfo("Success", f"Controls for {game_description} saved to gamedata.json!")
                
                # Force a reload of gamedata.json
                if hasattr(self, 'gamedata_json'):
                    del self.gamedata_json
                    self.load_gamedata_json()
                
                # Clear the in-memory cache to force reloading data
                if hasattr(self, 'rom_data_cache'):
                    self.rom_data_cache = {}
                    print("Cleared ROM data cache to force refresh")
                
                # Rebuild SQLite database if it's being used
                if hasattr(self, 'db_path') and self.db_path:
                    print("Rebuilding SQLite database to reflect control changes...")
                    self.build_gamedata_db()
                    print("Database rebuild complete")
                
                # Refresh any currently displayed data
                if self.current_game == rom_name and hasattr(self, 'on_game_select'):
                    print(f"Refreshing display for current game: {rom_name}")
                    # Create a mock event to trigger refresh
                    class MockEvent:
                        def __init__(self):
                            self.x = 10
                            self.y = 10
                    self.on_game_select(MockEvent())
                
                # Close the editor
                editor.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save controls: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Remove Game button (with confirmation)
        def remove_game():
            """Remove this game entirely from the database"""
            # Confirm with user
            if not messagebox.askyesno(
                "Confirm Removal", 
                f"Are you sure you want to completely remove {rom_name} from the database?\n\nThis action cannot be undone!",
                icon="warning"
            ):
                return
                
            try:
                # Load the gamedata.json file
                gamedata_path = self.get_gamedata_path()
                with open(gamedata_path, 'r', encoding='utf-8') as f:
                    gamedata = json.load(f)
                
                removed = False
                
                # Check if it's a direct entry
                if rom_name in gamedata:
                    # Direct removal
                    del gamedata[rom_name]
                    removed = True
                    print(f"Removed game: {rom_name}")
                else:
                    # Check if it's a clone in any parent's clone list
                    for parent_name, parent_data in gamedata.items():
                        if 'clones' in parent_data and isinstance(parent_data['clones'], dict):
                            if rom_name in parent_data['clones']:
                                # Remove from clone list
                                del parent_data['clones'][rom_name]
                                removed = True
                                print(f"Removed clone game: {rom_name} from parent: {parent_name}")
                                break
                
                if not removed:
                    messagebox.showerror("Error", f"Could not find {rom_name} in the database.")
                    return
                
                # Save the updated gamedata back to the file
                with open(gamedata_path, 'w', encoding='utf-8') as f:
                    json.dump(gamedata, f, indent=2)
                    
                # Force a reload of gamedata.json
                if hasattr(self, 'gamedata_json'):
                    del self.gamedata_json
                    self.load_gamedata_json()
                
                # Clear the in-memory cache to force reloading data
                if hasattr(self, 'rom_data_cache'):
                    self.rom_data_cache = {}
                    print("Cleared ROM data cache to force refresh")
                
                # Rebuild SQLite database if it's being used
                if hasattr(self, 'db_path') and self.db_path:
                    print("Rebuilding SQLite database to reflect game removal...")
                    self.build_gamedata_db()
                    print("Database rebuild complete")
                
                messagebox.showinfo("Success", f"{rom_name} has been removed from the database.")
                
                # Close the editor
                editor.destroy()
                
                # Refresh any currently displayed data
                # Since we removed the current game, we need to select a different game
                if self.current_game == rom_name:
                    self.current_game = None
                    self.game_title.configure(text="Select a game")
                    # Clear the control frame
                    for widget in self.control_frame.winfo_children():
                        widget.destroy()
                    # Update the game list
                    self.update_game_list()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove game: {str(e)}")
                import traceback
                traceback.print_exc()

        # Add a distinctive red "Remove Game" button
        remove_button = ctk.CTkButton(
            button_frame,
            text="Remove Game",
            command=remove_game,
            font=("Arial", 14),
            fg_color="#B22222",  # Firebrick red
            hover_color="#8B0000"  # Darker red on hover
        )
        remove_button.pack(side="left", padx=10, pady=5)

        
        # Save button
        save_button = ctk.CTkButton(
            button_frame,
            text="Save Controls",
            command=save_controls,
            font=("Arial", 14)
        )
        save_button.pack(side="left", padx=10, pady=5)
        
        # Close button
        close_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=editor.destroy,
            font=("Arial", 14)
        )
        close_button.pack(side="right", padx=10, pady=5)
    
    # Updated get_gamedata_path method to work when exe is in preview folder
    def get_gamedata_path(self):
        """Get the path to the gamedata.json file without checking legacy paths"""
        import os
        
        # Determine if we're in preview folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        in_preview_folder = os.path.basename(current_dir) == "preview"
        
        if in_preview_folder:
            # If we're in preview folder, settings are in preview/settings
            settings_path = os.path.join(self.mame_dir, "gamedata.json")
        else:
            # Normal path relative to mame_dir
            settings_path = os.path.join(self.mame_dir, "gamedata.json")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        return settings_path
    
    def create_game_list_with_edit(self, parent_frame, game_list, title_text):
        """Helper function to create a consistent list with edit button for games"""
        # Frame for the list
        list_frame = ctk.CTkFrame(parent_frame)
        list_frame.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Title
        ctk.CTkLabel(
            list_frame,
            text=title_text,
            font=("Arial", 14, "bold")
        ).pack(pady=(5, 10))
        
        # Create frame for list and scrollbar
        list_container = ctk.CTkFrame(list_frame)
        list_container.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Create listbox
        game_listbox = tk.Listbox(list_container, font=("Arial", 12))
        game_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=game_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        game_listbox.config(yscrollcommand=scrollbar.set)
        
        # Populate listbox
        for rom, game_name in game_list:
            if rom == game_name:
                game_listbox.insert(tk.END, rom)
            else:
                game_listbox.insert(tk.END, f"{rom} - {game_name}")
        
        # Store the rom names for lookup when editing
        rom_map = [rom for rom, _ in game_list]
        
        # Button frame
        button_frame = ctk.CTkFrame(list_frame)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        def edit_selected_game():
            selection = game_listbox.curselection()
            if not selection:
                messagebox.showinfo("Selection Required", "Please select a game to edit")
                return
                
            idx = selection[0]
            if idx < len(rom_map):
                rom = rom_map[idx]
                game_name = game_list[idx][1] if game_list[idx][0] != game_list[idx][1] else None
                self.show_control_editor(rom, game_name)
        
        edit_button = ctk.CTkButton(
            button_frame,
            text="Edit Selected Game",
            command=edit_selected_game
        )
        edit_button.pack(side=tk.LEFT, padx=5)
        
        return list_frame
    
    def identify_generic_controls(self):
        """Identify games that only have generic control names"""
        generic_control_games = []
        missing_control_games = []
        
        # Generic action names that indicate default mappings
        generic_actions = [
            "A Button", "B Button", "X Button", "Y Button", 
            "LB Button", "RB Button", "LT Button", "RT Button",
            "Up", "Down", "Left", "Right"
        ]
        
        for rom_name in sorted(self.available_roms):
            # First check if game data exists at all
            game_data = self.get_game_data(rom_name)
            if not game_data:
                missing_control_games.append(rom_name)
                continue
                
            # Check if controls are just generic
            has_custom_controls = False
            for player in game_data.get('players', []):
                for label in player.get('labels', []):
                    action = label['value']
                    # If we find any non-generic action, mark this game as having custom controls
                    if action not in generic_actions:
                        has_custom_controls = True
                        break
                if has_custom_controls:
                    break
                    
            # If no custom controls found, add to list
            if not has_custom_controls and game_data.get('players'):
                generic_control_games.append((rom_name, game_data.get('gamename', rom_name)))
        
        return generic_control_games, missing_control_games
    
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
        
        settings_path = os.path.join(self.mame_dir, "preview", "control_config_settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        """Load settings from JSON file if it exists"""
        settings_path = os.path.join(self.mame_dir, "preview", "control_config_settings.json")
        # Set sensible defaults
        self.preferred_preview_screen = 1  # Default to second screen
        self.visible_control_types = ["BUTTON"]  # Default to just buttons
        self.hide_preview_buttons = False
        self.show_button_names = False
        
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
                    # Important: Properly handle empty or invalid lists
                    if isinstance(settings['visible_control_types'], list):
                        self.visible_control_types = settings['visible_control_types']
                        print(f"Loaded visible control types: {self.visible_control_types}")
                    else:
                        print(f"Warning: Invalid visible_control_types format in settings: {settings['visible_control_types']}")
                    
                    # Make sure BUTTON is always included for proper display
                    if "BUTTON" not in self.visible_control_types:
                        self.visible_control_types.append("BUTTON")
                        print("Added BUTTON to visible control types for complete display")
                        # Update the saved settings
                        settings['visible_control_types'] = self.visible_control_types
                        with open(settings_path, 'w') as f:
                            json.dump(settings, f)
                else:
                    # Default to showing just buttons
                    self.visible_control_types = ["BUTTON"]
                    settings['visible_control_types'] = self.visible_control_types
                    with open(settings_path, 'w') as f:
                        json.dump(settings, f)

                # Load hide preview buttons setting
                if 'hide_preview_buttons' in settings:
                    # Handle both boolean and integer (0/1) formats
                    if isinstance(settings['hide_preview_buttons'], bool):
                        self.hide_preview_buttons = settings['hide_preview_buttons']
                    elif isinstance(settings['hide_preview_buttons'], int):
                        self.hide_preview_buttons = bool(settings['hide_preview_buttons'])
                    print(f"Loaded hide_preview_buttons: {self.hide_preview_buttons}")
                    
                    # Update toggle if it exists
                    if hasattr(self, 'hide_buttons_toggle'):
                        if self.hide_preview_buttons:
                            self.hide_buttons_toggle.select()
                        else:
                            self.hide_buttons_toggle.deselect()
                else:
                    self.hide_preview_buttons = False
                    
                # Load show button names setting
                if 'show_button_names' in settings:
                    # Handle both boolean and integer (0/1) formats
                    if isinstance(settings['show_button_names'], bool):
                        self.show_button_names = settings['show_button_names']
                    elif isinstance(settings['show_button_names'], int):
                        self.show_button_names = bool(settings['show_button_names'])
                    print(f"Loaded show_button_names: {self.show_button_names}")
                else:
                    # Default to showing button names for backward compatibility
                    self.show_button_names = True
                    settings['show_button_names'] = True
                    with open(settings_path, 'w') as f:
                        json.dump(settings, f)
                        
            except Exception as e:
                print(f"Error loading settings: {e}")
                import traceback
                traceback.print_exc()
                self.hide_preview_buttons = False
                self.visible_control_types = ["BUTTON"]  # Default to just buttons
                self.show_button_names = True  # Default to showing button names
        else:
            # Default settings
            self.hide_preview_buttons = False
            self.visible_control_types = ["BUTTON"]  # Default to just buttons
            self.show_button_names = True  # Default to showing button names
            
            # Create settings file with defaults
            settings = {
                'preferred_preview_screen': self.preferred_preview_screen,
                'visible_control_types': self.visible_control_types,
                'hide_preview_buttons': self.hide_preview_buttons,
                'show_button_names': self.show_button_names
            }
            try:
                with open(settings_path, 'w') as f:
                    json.dump(settings, f)
                print("Created default settings file")
            except Exception as e:
                print(f"Error creating settings file: {e}")
        
        # Debug output of final settings
        print(f"\nFinal settings:")
        print(f"  - visible_control_types: {self.visible_control_types}")
        print(f"  - hide_preview_buttons: {self.hide_preview_buttons}")
        print(f"  - show_button_names: {self.show_button_names}")
        print(f"  - preferred_preview_screen: {self.preferred_preview_screen}\n")

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
