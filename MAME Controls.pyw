import sys
from PIL import ImageFont
import customtkinter as ctk
import json
import os
import re
from tkinter import Image, messagebox, ttk
from typing import Dict, Optional, Set, List, Tuple
import xml.etree.ElementTree as ET
import subprocess
import threading
import time
from PIL import Image, ImageTk
# Make sure to add this import at the top of your file
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

def get_application_path():
    """Get the base path for the application (handles PyInstaller bundling)"""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))
        
# ======================================================
# POSITION MANAGEMENT SYSTEM
# ======================================================

class PositionManager:
    """Handles storage, normalization, and application of text positions"""
    
    def __init__(self, parent):
        """Initialize the position manager"""
        self.parent = parent  # Reference to the main app
        self.positions = {}   # Store for in-memory positions
    
    def normalize(self, x, y):
        """Convert a display position to a normalized position (without y-offset)"""
        # Get settings directly from the app for consistency
        settings = self.parent.get_text_settings()
        y_offset = settings.get("y_offset", -40)
        
        # Remove y-offset to get normalized position
        normalized_y = y - y_offset
        return x, normalized_y
    
    def apply_offset(self, x, normalized_y, y_offset=None):
        """Apply y-offset to a normalized position for display"""
        # Get settings directly from the app for consistency
        settings = self.parent.get_text_settings()
        
        # Use provided y_offset if specified, otherwise get from settings
        if y_offset is None:
            y_offset = settings.get("y_offset", -40)
        
        # Add y-offset for display
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
        # Get settings for consistent y-offset calculation
        settings = self.parent.get_text_settings()
        y_offset = settings.get('y_offset', -40)
        
        # Calculate normalized y-coordinate (the true position without offset)
        normalized_y = new_y - y_offset
        
        # Store the position with coordinates properly normalized
        self.positions[control_name] = (new_x, normalized_y)
        
        print(f"Position updated from drag - {control_name}: display=({new_x}, {new_y}), normalized=({new_x}, {normalized_y})")
        
        return new_x, normalized_y
    
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
        """Save positions to file (globally or for a specific game) using centralized paths"""
        if not self.positions:
            print("No positions to save")
            return False
                
        try:
            # Convert to format expected by file saving function
            positions_to_save = {}
            for name, (x, normalized_y) in self.positions.items():
                positions_to_save[name] = [x, normalized_y]
            
            # Check if we should use the no-names variant of positions file
            show_button_names = getattr(self.parent, 'show_button_names', True)
            suffix = "" if show_button_names else "_no_names"
            
            # Determine the file path using centralized function
            if is_global:
                filepath = self.parent.get_settings_path(f"positions{suffix}")
            else:
                filepath = self.parent.get_settings_path(f"positions{suffix}", game_name)
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(positions_to_save, f)
                
            print(f"Saved {len(positions_to_save)} positions to: {filepath} (button names: {show_button_names})")
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

class MAMEControlConfig(ctk.CTk):
    def __init__(self, preview_only=False):
        super().__init__()
        # At the beginning of the class initialization:
        self._debug_data_source = False  # Set to True for detailed data source logging     
        # Initialize core attributes needed for both modes
        self.visible_control_types = ["BUTTON", "JOYSTICK"]
        self.default_controls = {}
        self.gamedata_json = {}
        self.available_roms = set()
        self.custom_configs = {}
        self.current_game = None
        self.use_xinput = True
        self.show_rom_info = False

        # Button visibility settings
        # Image Buttons
        self.show_generate_buttons = True  # Default to showing generate images button
        self.show_exact_preview_button = True  # Default to showing exact preview button
        self.show_save_button = True  # Default to showing save button
        
        self.show_analyze_button = True    # Default to showing analyze button
        self.show_generate_info_buttons = True  # Default to showing generate images button

        # Logo size settings (as percentages)
        self.logo_width_percentage = 15
        self.logo_height_percentage = 15
        
        # IMPORTANT: Bind the method only after initializing attributes
        self.get_game_data_with_ijson = self.get_game_data_with_ijson.__get__(self, type(self))
        
        # Set current directory as default MAME directory before finding the actual one
        # This ensures mame_dir is never None
        self.mame_dir = os.path.abspath(os.path.dirname(__file__))
        print(f"Set default MAME directory to current directory: {self.mame_dir}")
        
        # Now try to find the real MAME directory
        try:
            mame_dir = self.find_mame_directory()
            if mame_dir:
                self.mame_dir = mame_dir
                print(f"Updated MAME directory to: {self.mame_dir}")
        except Exception as e:
            print(f"Error finding MAME directory: {e}")
            # Keep using the default directory set above
        
        # Create preview folder if needed and check for gamedata.json
        self.ensure_preview_folder_improved()  # Use the improved function that also creates default.png
        
        # Check for gamedata.json - this will now run even if the file is not found initially
        have_gamedata = self.check_and_prompt_for_gamedata()
        
        # IMPORTANT: Handle case when user cancels gamedata selection or import fails
        if not have_gamedata and not preview_only:
            # Show a warning but continue anyway to allow them to import later
            messagebox.showwarning(
                "Limited Functionality", 
                "Running without gamedata.json - some features may be limited.\n\n" +
                "You can import this file later using the 'Import Gamedata' button."
            )
        
        # Initialize the position manager
        self.position_manager = PositionManager(self)

        # Migrate settings files to new structure if needed
        self.migrate_settings_files()

        # Skip main window setup if in preview-only mode
        if not preview_only:
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

            # Now we can load settings that depend on mame_dir
            self.load_logo_settings()
            self.load_bezel_settings()
            self.load_layer_settings()  # Add this line to load layer settings

            self.ensure_font_available()

            # Create the interface
            self.create_layout()
            
            # IMPORTANT: Now add the import button AFTER create_layout has run
            self.add_import_gamedata_button()  # Add gamedata import button
            
            # Load all data
            self.load_all_data()  # Use your existing method to load ROMs and other data

            # Add generate images button
            self.add_generate_images_button()  

            # Add this line here:
            self.add_appearance_settings_button()
        
            # Add the text appearance settings button
            analyze_button = self.create_button(
                self.stats_frame,
                text="Analyze Controls",
                command=self.analyze_controls,
                button_id="analyze_controls_button",
                show=getattr(self, 'show_analyze_button', True)
            )
            if analyze_button:
                analyze_button.grid(row=0, column=5, padx=5, pady=5, sticky="e")
            
            # Apply the preview update hook to update preview text with settings
            self.apply_preview_update_hook()
        
        else:
            # For preview-only mode, just initialize minimal attributes
            self.fullscreen = True
            self.preferred_preview_screen = 2  # Default to second screen
            
            # We should still load layer settings even in preview-only mode
            if hasattr(self, 'mame_dir') and self.mame_dir:
                self.load_layer_settings()
            
            # Hide the main window completely
            self.withdraw()
    
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
    
    def get_gamedata_path(self):
        """Get the path to the gamedata.json file without checking legacy paths"""
        # Primary location in settings directory
        settings_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.json")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        return settings_path
    
    def build_gamedata_db(self):
        """Build a SQLite database from gamedata.json with improved handling of game removals"""
        # Find the gamedata.json file
        gamedata_path = self.get_gamedata_path()
        if not os.path.exists(gamedata_path):
            print("Error: gamedata.json not found")
            return False
        
        # Set up database path
        db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        print(f"Building SQLite database from {gamedata_path}...")
        start_time = time.time()
        
        try:
            # Connect to the database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Drop existing tables to ensure a clean rebuild
            cursor.execute('DROP TABLE IF EXISTS games')
            cursor.execute('DROP TABLE IF EXISTS clones')
            
            # Create the games table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                romname TEXT PRIMARY KEY,
                gamename TEXT,
                players INTEGER,
                alternating INTEGER,
                buttons TEXT,
                sticks TEXT,
                data TEXT
            )
            ''')
            
            # Create the clones table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS clones (
                clone TEXT PRIMARY KEY,
                parent TEXT
            )
            ''')
            
            # Begin a transaction for faster inserts
            conn.execute('BEGIN TRANSACTION')
            
            # Load the file in chunks to avoid memory issues
            game_count = 0
            clone_count = 0
            
            # Read the file and parse JSON
            with open(gamedata_path, 'r', encoding='utf-8') as f:
                # This loads the entire file, but we'll keep this simple
                # For extremely large files, you'd use a streaming approach
                game_data = json.load(f)
                
                # Process each game
                for romname, data in game_data.items():
                    # Extract basic game info
                    gamename = data.get('description', romname)
                    players = int(data.get('playercount', 1))
                    alternating = 1 if data.get('alternating', False) else 0
                    buttons = data.get('buttons', '')
                    sticks = data.get('sticks', '')
                    
                    # Store the game data
                    cursor.execute(
                        'INSERT OR REPLACE INTO games VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (romname, gamename, players, alternating, buttons, sticks, json.dumps(data))
                    )
                    game_count += 1
                    
                    # Process clones if available
                    if 'clones' in data and isinstance(data['clones'], dict):
                        for clone_name in data['clones']:
                            cursor.execute(
                                'INSERT OR REPLACE INTO clones VALUES (?, ?)',
                                (clone_name, romname)
                            )
                            clone_count += 1
                    
                    # Commit every 1000 games to avoid transaction getting too big
                    if game_count % 1000 == 0:
                        conn.commit()
                        conn.execute('BEGIN TRANSACTION')
                        print(f"Processed {game_count} games...")
            
            # Final commit
            conn.commit()
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_gamename ON games (gamename)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_clones_parent ON clones (parent)')
            
            # Close the connection
            conn.close()
            
            # Store the database path
            self.db_path = db_path
            
            # Report performance
            duration = time.time() - start_time
            print(f"SQLite database built in {duration:.2f} seconds")
            print(f"Indexed {game_count} games and {clone_count} clones")
            
            return True
        
        except Exception as e:
            print(f"Error building database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def is_database_update_needed(self):
        """Check if the database needs to be rebuilt by comparing timestamps"""
        # Get paths
        db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
        json_path = self.get_gamedata_path()
        
        print(f"\n=== Checking if database needs updating ===")
        print(f"Database path: {db_path}")
        print(f"JSON path: {json_path}")
        
        # If database doesn't exist, it definitely needs to be built
        if not os.path.exists(db_path):
            print("Database doesn't exist, rebuild needed")
            return True
            
        # If gamedata.json doesn't exist, we can't build the database
        if not os.path.exists(json_path):
            print("gamedata.json doesn't exist, can't build database")
            return False
            
        # Compare modification times
        db_mtime = os.path.getmtime(db_path)
        json_mtime = os.path.getmtime(json_path)
        
        db_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(db_mtime))
        json_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(json_mtime))
        
        print(f"Database timestamp: {db_time_str}")
        print(f"JSON file timestamp: {json_time_str}")
        
        # If JSON file is newer than database, we need to rebuild
        if json_mtime > db_mtime:
            print(f"gamedata.json is newer than database, rebuild needed")
            return True
            
        print("Database is up to date, no rebuild needed")
        print("=== Database check complete ===\n")
        return False
    
    def get_game_data_from_db(self, romname):
        """Get game data from SQLite database with optimized query"""
        # Make sure we have a database connection
        if not hasattr(self, 'db_conn'):
            try:
                import sqlite3
                self.db_conn = sqlite3.connect(self.db_path)
                self.db_conn.row_factory = sqlite3.Row  # This allows accessing columns by name
                print("Created persistent database connection")
            except Exception as e:
                print(f"Error creating database connection: {e}")
                return None
        
        try:
            cursor = self.db_conn.cursor()
            
            # First try direct lookup with a single query that also checks clone status
            cursor.execute('''
            SELECT data, NULL as parent FROM games WHERE romname = ?
            UNION ALL
            SELECT g.data, c.parent FROM games g 
            JOIN clones c ON g.romname = c.parent 
            WHERE c.clone = ? LIMIT 1
            ''', (romname, romname))
            
            row = cursor.fetchone()
            
            if row and row[0]:
                # Game found directly or as clone parent
                game_data = json.loads(row[0])
                result = self.convert_db_game_data(romname, game_data)
                return result
            
            # Not found
            return None
            
        except Exception as e:
            print(f"Error getting game data from database: {e}")
            return None
    
    def convert_db_game_data(self, romname, game_data):
        """Convert game data from database format to application format"""
        # Default action names for standard controls
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
            'P2_BUTTON1': 'A Button',
            'P2_BUTTON2': 'B Button',
            'P2_BUTTON3': 'X Button',
            'P2_BUTTON4': 'Y Button',
            'P2_BUTTON5': 'LB Button',
            'P2_BUTTON6': 'RB Button',
        }
        
        # Basic structure for output
        converted_data = {
            'romname': romname,
            'gamename': game_data.get('description', romname),
            'numPlayers': int(game_data.get('playercount', 1)),
            'alternating': game_data.get('alternating', False),
            'mirrored': False,
            'miscDetails': f"Buttons: {game_data.get('buttons', '?')}, Sticks: {game_data.get('sticks', '?')}",
            'players': [],
            'source': 'database'
        }
        
        # Process controls if available
        controls = None
        if 'controls' in game_data:
            controls = game_data['controls']
        
        if controls:
            # First collect P1 button names to mirror to P2
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
                    if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                        friendly_name = None
                        if 'name' in control_data:
                            friendly_name = control_data['name']
                        elif control_name in default_actions:
                            friendly_name = default_actions[control_name]
                        else:
                            parts = control_name.split('_')
                            if len(parts) > 1:
                                friendly_name = parts[-1]
                        
                        if friendly_name:
                            p1_controls.append({
                                'name': control_name,
                                'value': friendly_name
                            })
                
                # Add P2 controls
                elif control_name.startswith('P2_'):
                    if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                        friendly_name = None
                        if 'name' in control_data:
                            friendly_name = control_data['name']
                        elif control_name in p1_button_names:
                            friendly_name = p1_button_names[control_name]
                        elif control_name in default_actions:
                            friendly_name = default_actions[control_name]
                        else:
                            parts = control_name.split('_')
                            if len(parts) > 1:
                                friendly_name = parts[-1]
                        
                        if friendly_name:
                            p2_controls.append({
                                'name': control_name,
                                'value': friendly_name
                            })
            
            # Special handling for direction mappings
            special_mappings = {
                'P1_UP': 'P1_JOYSTICK_UP',
                'P1_DOWN': 'P1_JOYSTICK_DOWN',
                'P1_LEFT': 'P1_JOYSTICK_LEFT',
                'P1_RIGHT': 'P1_JOYSTICK_RIGHT',
                'P2_UP': 'P2_JOYSTICK_UP',
                'P2_DOWN': 'P2_JOYSTICK_DOWN',
                'P2_LEFT': 'P2_JOYSTICK_LEFT',
                'P2_RIGHT': 'P2_JOYSTICK_RIGHT'
            }
            
            for special, joystick in special_mappings.items():
                if special in controls and 'name' in controls[special]:
                    # Find the matching joystick control
                    if joystick.startswith('P1_'):
                        for control in p1_controls:
                            if control['name'] == joystick:
                                control['value'] = controls[special]['name']
                    elif joystick.startswith('P2_'):
                        for control in p2_controls:
                            if control['name'] == joystick:
                                control['value'] = controls[special]['name']
            
            # Sort controls by name
            p1_controls.sort(key=lambda x: x['name'])
            p2_controls.sort(key=lambda x: x['name'])
            
            # Add player 1 controls if available
            if p1_controls:
                converted_data['players'].append({
                    'number': 1,
                    'numButtons': int(game_data.get('buttons', 1)),
                    'labels': p1_controls
                })
            
            # Add player 2 controls if available
            if p2_controls:
                converted_data['players'].append({
                    'number': 2,
                    'numButtons': int(game_data.get('buttons', 1)),
                    'labels': p2_controls
                })
        
        return converted_data

    def initialize_database(self):
        """Initialize SQLite database and patch methods"""
        print("\n=== Database Initialization ===")
        
        # Save original method if needed
        if not hasattr(self, 'orig_get_game_data'):
            self.orig_get_game_data = self.get_game_data
            print("Original get_game_data method stored")
        
        # Check if database exists and set path
        db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
        self.db_path = db_path
        print(f"Database path set to: {db_path}")
        
        # Only rebuild the database if needed
        if self.is_database_update_needed():
            print("Building database because it needs updating")
            success = self.build_gamedata_db()
            if success:
                print("Database built successfully")
            else:
                print("Database build failed")
        else:
            print("Using existing database - no rebuild needed")
        
        # Initialize debug counters as a dictionary property
        # Store them in a normal attribute that won't conflict with tkinter
        self.debug_source_counters = {
            'cache': 0,
            'custom': 0,
            'database': 0,
            'json': 0,
            'not_found': 0
        }
        
        print("=== Database Initialization Complete ===\n")
    
    def create_button(self, parent, text, command, button_id, show=True, width=150, **kwargs):
        """
        Create a button with standardized properties and visibility control.
        
        Parameters:
        - parent: Parent widget
        - text: Button text
        - command: Function to call when button is clicked
        - button_id: Unique ID for this button to store reference
        - show: Whether to show this button (defaults to True)
        - width: Button width (defaults to 150)
        - **kwargs: Additional parameters to pass to CTkButton
        
        Returns:
        - Button widget if created, None if not shown
        """
        # Check if button should be shown
        if not show:
            # Store None for this button ID
            setattr(self, button_id, None)
            print(f"Button '{button_id}' is hidden by configuration")
            return None
        
        # Create the button with standard properties
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            **kwargs
        )
        
        # Store reference to the button
        setattr(self, button_id, button)
        print(f"Created button '{button_id}': {text}")
        
        return button
    
    def check_and_prompt_for_gamedata(self):
        """
        Check if gamedata.json exists in the preview/settings folder.
        If not, prompt the user to locate it and copy it to the correct location.
        Returns True if gamedata.json exists or was successfully imported, False otherwise.
        """
        import os
        import shutil
        from tkinter import filedialog, messagebox
        import sys
        import subprocess

        # Get the path where gamedata.json should be
        settings_dir = os.path.join(self.mame_dir, "preview", "settings")
        gamedata_path = os.path.join(settings_dir, "gamedata.json")
        
        # Create settings directory if it doesn't exist
        if not os.path.exists(settings_dir):
            try:
                os.makedirs(settings_dir, exist_ok=True)
                print(f"Created settings directory: {settings_dir}")
            except Exception as e:
                print(f"Error creating settings directory: {e}")
                # Continue anyway to check for existing file
        
        # Check if gamedata.json already exists in settings directory
        if os.path.exists(gamedata_path):
            print("gamedata.json found at: {gamedata_path}")
            return True
        
        # Check for legacy location (directly in MAME directory)
        legacy_path = os.path.join(self.mame_dir, "gamedata.json")
        if os.path.exists(legacy_path):
            try:
                # Copy from legacy location to new location
                shutil.copy2(legacy_path, gamedata_path)
                print(f"Copied gamedata.json from legacy location: {legacy_path} to {gamedata_path}")
                return True
            except Exception as e:
                print(f"Error copying from legacy location: {e}")
                # Continue to prompt
        
        # If running in preview-only mode, don't show prompt (will be handled by main app)
        if not hasattr(self, 'game_list'):
            print("Running in preview-only mode, skipping gamedata prompt")
            return False
        
        # If not found in any location, show prompt asking if the user wants to locate it
        response = messagebox.askyesno(
            "Gamedata File Missing",
            "gamedata.json not found in the expected location.\n\n"
            "This file is required for game control information.\n"
            "Would you like to locate and import a gamedata.json file now?",
            icon="question"
        )
        
        if not response:
            # User chose not to import, inform them of the limitations
            messagebox.showinfo(
                "Limited Functionality",
                "Without gamedata.json, game control information will be limited.\n"
                "You can import the file later from the main application."
            )
            return False
        
        # Open file selection dialog
        filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        selected_file = filedialog.askopenfilename(
            title="Select gamedata.json file",
            filetypes=filetypes,
            initialdir=self.mame_dir  # Start in MAME directory
        )
        
        if not selected_file:
            # User cancelled the selection
            print("User cancelled gamedata.json selection")
            return False
        
        try:
            # Validate the selected file (basic check that it's a valid JSON file)
            import json
            with open(selected_file, 'r', encoding='utf-8') as f:
                try:
                    # Just try to load it to verify it's valid JSON
                    data = json.load(f)
                    # Check if it at least has some expected structure
                    if not isinstance(data, dict) or len(data) < 10:  # Arbitrary check for a reasonable number of entries
                        raise ValueError("File doesn't appear to be a valid gamedata.json (too few game entries)")
                except json.JSONDecodeError:
                    raise ValueError("Selected file is not valid JSON")
            
            # Copy the file to the correct location
            shutil.copy2(selected_file, gamedata_path)
            
            # Show success message
            restart_response = messagebox.askyesno(
                "Import Successful",
                f"Successfully imported gamedata.json.\n\n"
                f"File copied to: {gamedata_path}\n\n"
                "The application needs to restart to use the new gamedata file. "
                "Would you like to restart now?",
                icon="question"
            )
            
            print(f"Imported gamedata.json from: {selected_file} to: {gamedata_path}")
            
            if restart_response:
                # User chose to restart - use the app's restart method if available
                print("Restarting application...")
                if hasattr(self, 'restart_application') and callable(getattr(self, 'restart_application')):
                    self.restart_application()
                else:
                    # Fallback restart method
                    self.restart_app_fallback()
                
                return True  # Return here even though the app is restarting
                
            return True
            
        except Exception as e:
            # Show error message if import fails
            messagebox.showerror(
                "Import Failed",
                f"Failed to import gamedata.json: {str(e)}\n\n"
                "Please make sure you selected a valid gamedata.json file."
            )
            print(f"Error importing gamedata.json: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def restart_app_fallback(self):
        """
        Fallback method to restart the application if restart_application doesn't exist.
        This uses a different approach to restart the app.
        """
        import sys
        import os
        import subprocess

        try:
            print("Using fallback restart method")
            
            # Get current script path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                app_path = sys.executable
                print(f"Restarting executable: {app_path}")
            else:
                # Running as script
                app_path = os.path.abspath(__file__)
                print(f"Restarting script: {app_path}")
            
            # Start a new instance of the application
            if sys.platform.startswith('win'):
                # On Windows, use pythonw.exe for .pyw files to avoid console
                if app_path.lower().endswith('.pyw') and not getattr(sys, 'frozen', False):
                    python_exe = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                    subprocess.Popen([python_exe, app_path])
                else:
                    subprocess.Popen([app_path])
            else:
                # On other platforms
                if getattr(sys, 'frozen', False):
                    subprocess.Popen([app_path])
                else:
                    subprocess.Popen([sys.executable, app_path])
            
            # Exit the current instance
            print("Exiting current instance")
            self.quit()
            
            # Force exit if quit() doesn't work
            sys.exit(0)
            
        except Exception as e:
            print(f"Error during restart: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error message
            from tkinter import messagebox
            messagebox.showerror(
                "Restart Failed",
                f"Unable to restart the application: {str(e)}\n\n"
                "Please close and reopen the app manually."
            )
    
    # Function to add an "Import Gamedata" button to the UI
    def add_import_gamedata_button(self):
        """
        Add a button to import gamedata.json from the main interface.
        Skips button creation if gamedata.json already exists in the expected folder.
        """
        # Build the full expected path to gamedata.json
        gamedata_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.json")

        # Skip adding the button if gamedata.json already exists
        if os.path.exists(gamedata_path):
            print(f"gamedata.json already exists at: {gamedata_path}. Skipping Import button.")
            return False

        # Check if stats_frame exists
        if not hasattr(self, 'stats_frame'):
            print("Warning: stats_frame not found, can't add Import Gamedata button yet")
            return False

        # Check if stats_frame is a valid widget
        try:
            self.stats_frame.winfo_exists()
        except Exception:
            print("Warning: stats_frame is not a valid widget, can't add Import Gamedata button")
            return False

        # Create the button
        import_button = self.create_button(
            self.stats_frame,
            text="Import Gamedata",
            command=self.check_and_prompt_for_gamedata,
            button_id="import_gamedata_button"
        )

        if import_button:
            import_button.grid(row=0, column=20, padx=5, pady=5, sticky="e")
            print("Added Import Gamedata button at fixed position (column 20)")
            return True

        return False

        
    def add_appearance_settings_button(self):
        """Add a button to configure text appearance settings (using the centralized button system)"""
        # Add to stats frame next to the generate images button
        appearance_button = self.create_button(
            self.stats_frame,
            text="Text Settings",
            command=self.show_text_appearance_settings,
            button_id="appearance_button"
        )
        if appearance_button:
            appearance_button.grid(row=0, column=4, padx=5, pady=5, sticky="e")

        # Also add to preview window button row if it exists
        if hasattr(self, 'show_preview'):
            # Store the original method
            original_show_preview = self.show_preview
            
            # Define a wrapper method that adds our button
            def show_preview_with_settings_button(*args, **kwargs):
                # Call the original method
                result = original_show_preview(*args, **kwargs)
                
                # Add appearance settings button if button_row1 exists
                if hasattr(self, 'button_row1') and self.button_row1.winfo_exists():
                    settings_button = self.create_button(
                        self.button_row1,
                        text="Text Settings",
                        command=self.show_text_appearance_settings,
                        button_id="appearance_button",
                        width=90  # Match other buttons
                    )
                    if settings_button:
                        settings_button.pack(side="left", padx=3)
                
                return result
            
            # Replace the original method with our wrapper
            self.show_preview = show_preview_with_settings_button
    
    def find_mame_directory(self) -> str:
        """Find the MAME directory containing necessary files - with improved handling when gamedata.json not found"""
        # First check in the application directory
        app_dir = get_application_path()
        print(f"\n=== DEBUG: find_mame_directory ===")
        print(f"Application directory: {app_dir}")
        
        # Look for the settings directory path
        settings_gamedata = os.path.join(app_dir, "preview", "settings", "gamedata.json")
        print(f"Checking for gamedata.json at: {settings_gamedata}")
        if os.path.exists(settings_gamedata):
            print(f"FOUND: gamedata.json in settings folder at: {app_dir}")
            return app_dir
        
        # Also check current directory with new path structure
        current_dir = os.path.abspath(os.path.dirname(__file__))
        print(f"Current directory: {current_dir}")
        current_settings_gamedata = os.path.join(current_dir, "preview", "settings", "gamedata.json")
        print(f"Checking for gamedata.json at: {current_settings_gamedata}")
        
        if os.path.exists(current_settings_gamedata):
            print(f"FOUND: gamedata.json in current directory at: {current_dir}")
            return current_dir
        
        # Check common MAME paths with new structure
        common_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "MAME"),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), "MAME"),
            "C:\\MAME",
            "D:\\MAME"
        ]
        
        for path in common_paths:
            settings_gamedata_path = os.path.join(path, "preview", "settings", "gamedata.json")
            print(f"Checking common path: {settings_gamedata_path}")
            if os.path.exists(settings_gamedata_path):
                print(f"FOUND: gamedata.json in common path at: {path}")
                return path
        
        # *** IMPORTANT CHANGE: If no gamedata.json found, return current directory instead of None ***
        # This allows the application to start without gamedata.json and then prompt the user to select it
        print("WARNING: gamedata.json not found in any known location - will use current directory")
        return current_dir  # Use current directory as MAME directory instead of returning None
    
    def create_transparent_default_image(self, output_dir=None):
        """
        Create a default transparent PNG image if none exists.
        
        Args:
            output_dir: Directory to save the image to (defaults to preview dir)
            
        Returns:
            Path to the created image, or None if creation failed
        """
        if output_dir is None:
            output_dir = os.path.join(self.mame_dir, "preview")
            
        # Check if default image already exists
        default_png_path = os.path.join(output_dir, "default.png")
        
        if os.path.exists(default_png_path):
            print(f"Default PNG image already exists at: {default_png_path}")
            return default_png_path
        
        # No default image found, create one
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a new transparent image
            # RGBA mode - A is alpha/transparency channel
            img = Image.new('RGBA', (1280, 720), color=(0, 0, 0, 0))
            
            # Get a drawing context
            draw = ImageDraw.Draw(img)
            
            # Create semi-transparent background rectangle for better text visibility
            # Define rectangle coordinates (left, top, right, bottom)
            rect_left = 320
            rect_top = 260
            rect_right = 960
            rect_bottom = 460
            # Draw with semi-transparent dark background
            draw.rectangle([rect_left, rect_top, rect_right, rect_bottom], 
                        fill=(0, 0, 0, 180))  # RGBA with alpha=180 (semi-transparent)
            
            # Try to use a font
            try:
                font = ImageFont.truetype("arial.ttf", 32)
                small_font = ImageFont.truetype("arial.ttf", 24)
            except:
                # Fall back to default if no font available
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Draw text on the semi-transparent background
            # Main title
            draw.text((640, 300), "MAME Controls Preview", 
                    fill=(255, 255, 255, 255), anchor="mm", font=font)
            
            # Instructions
            draw.text((640, 360), "Place game screenshots in preview folder", 
                    fill=(200, 200, 200, 255), anchor="mm", font=small_font)
            draw.text((640, 400), "with ROM name (e.g., pacman.png)", 
                    fill=(200, 200, 200, 255), anchor="mm", font=small_font)
            
            # Save the image
            created_path = os.path.join(output_dir, "default.png")
            img.save(created_path)
            print(f"Created transparent default image at: {created_path}")
            
            return created_path
        except ImportError:
            print("PIL not installed, cannot create default image")
            return None
        except Exception as e:
            print(f"Error creating transparent default image: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Improved version of ensure_preview_folder_improved() to create transparent default image
    def ensure_preview_folder_improved(self):
        """Create preview directory if it doesn't exist and ensure default image exists"""
        import os
        import sys
        
        # Make sure mame_dir exists and is a string
        if not hasattr(self, 'mame_dir') or self.mame_dir is None:
            # Fallback to current directory if mame_dir is not set
            self.mame_dir = os.path.abspath(os.path.dirname(__file__))
            print(f"Warning: mame_dir not set, using current directory: {self.mame_dir}")
        
        preview_dir = os.path.join(self.mame_dir, "preview")
        print(f"Ensuring preview folder at: {preview_dir}")
        
        # Create directory if it doesn't exist
        if not os.path.exists(preview_dir):
            try:
                print(f"Creating preview directory: {preview_dir}")
                os.makedirs(preview_dir, exist_ok=True)
                
                # Copy any bundled preview images if running as executable
                if getattr(sys, 'frozen', False):
                    bundled_preview = os.path.join(get_application_path(), "preview2")
                    if os.path.exists(bundled_preview):
                        import shutil
                        for item in os.listdir(bundled_preview):
                            source = os.path.join(bundled_preview, item)
                            dest = os.path.join(preview_dir, item)
                            if os.path.isfile(source):
                                shutil.copy2(source, dest)
                                print(f"Copied: {item} to preview folder")
            except Exception as e:
                print(f"Error creating preview directory: {e}")
                # Create a fallback directory in the current location
                try:
                    current_dir = os.path.abspath(os.path.dirname(__file__))
                    preview_dir = os.path.join(current_dir, "preview")
                    os.makedirs(preview_dir, exist_ok=True)
                    print(f"Created fallback preview directory: {preview_dir}")
                except Exception as e2:
                    print(f"Error creating fallback preview directory: {e2}")
                    # Last resort - use temp directory
                    import tempfile
                    preview_dir = os.path.join(tempfile.gettempdir(), "mame_preview")
                    os.makedirs(preview_dir, exist_ok=True)
                    print(f"Created last-resort preview directory: {preview_dir}")
        
        # Ensure settings directory exists
        settings_dir = os.path.join(preview_dir, "settings")
        if not os.path.exists(settings_dir):
            try:
                os.makedirs(settings_dir, exist_ok=True)
                print(f"Created settings directory: {settings_dir}")
            except Exception as e:
                print(f"Error creating settings directory: {e}")
        
        # Ensure default image exists
        default_img_path = os.path.join(preview_dir, "default.png")
        if not os.path.exists(default_img_path):
            # Create transparent default image
            try:
                self.create_transparent_default_image(preview_dir)
                print(f"Created transparent default image at: {default_img_path}")
            except Exception as e:
                print(f"Error creating transparent default image: {e}")
                # Attempt simplified default image creation as fallback
                try:
                    self.create_simple_default_image(preview_dir)
                    print(f"Created simple default image at: {default_img_path}")
                except Exception as e2:
                    print(f"Error creating simple default image: {e2}")
        
        return preview_dir
    
    def create_simple_default_image(self, output_dir):
        """Create a simple default image (fallback if PIL fails)"""
        import os
        
        default_png_path = os.path.join(output_dir, "default.png")
        
        # Create a minimal 1x1 PNG file with raw bytes
        # This is a valid 1x1 black PNG file in raw bytes
        png_data = bytearray([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
            0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
            0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        with open(default_png_path, 'wb') as f:
            f.write(png_data)
        
        return default_png_path
    
    def create_default_image(output_dir=None):
        """Create a default image if none exists"""
        if output_dir is None:
            output_dir = os.getcwd()  # Default to current directory
        
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
    
    def save_settings(self):
        """Save current settings to a JSON file using the centralized file path"""
        settings = {
            "preferred_preview_screen": getattr(self, 'preferred_preview_screen', 2),
            "visible_control_types": self.visible_control_types,
            "hide_preview_buttons": getattr(self, 'hide_preview_buttons', False),
            "show_button_names": getattr(self, 'show_button_names', True)
        }
        
        # Use centralized path function
        settings_path = self.get_settings_path("general")
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
            print(f"Saved general settings to: {settings_path}")
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def load_settings(self):
        """Load settings from JSON file with improved defaults using the centralized file path"""
        settings_path = self.get_settings_path("general")
        
        # Set sensible defaults
        self.preferred_preview_screen = 2  # Default to second screen
        self.visible_control_types = ["BUTTON"]  # Default to just buttons
        self.hide_preview_buttons = False
        self.show_button_names = True
        
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
    
     # Show/hide methods for preview buttons
    def show_button_frame(self):
        """Show the button frame"""
        if hasattr(self, 'frame_bg'):
            self.frame_bg.place(
                relx=0.5, 
                rely=0.95, 
                anchor="center", 
                width=min(1000, self.preview_window.winfo_width()-20), 
                height=80
            )

    def hide_button_frame(self):
        """Hide the button frame"""
        if hasattr(self, 'frame_bg'):
            self.frame_bg.place_forget()
    
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
    
    def show_generic_controls_dialog(self):
        """Show dialog with games that have only generic controls or missing controls"""
        generic_games, missing_games = self.identify_generic_controls()
        
        # Also identify games with default controls 
        default_games = []
        already_categorized = set([g[0] for g in generic_games]) | set(missing_games)
        
        for rom_name in sorted(self.available_roms):
            if rom_name not in already_categorized:
                game_data = self.get_game_data(rom_name)
                if game_data and 'gamename' in game_data:
                    default_games.append((rom_name, game_data.get('gamename', rom_name)))
        
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Game Controls Editor")
        dialog.geometry("800x600")
        dialog.transient(self)
        dialog.grab_set()
        
        # Create tabs
        tabview = ctk.CTkTabview(dialog)
        tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Summary tab
        summary_tab = tabview.add("Summary")
        stats_text = (
            f"Total ROMs: {len(self.available_roms)}\n"
            f"ROMs with generic controls: {len(generic_games)}\n"
            f"ROMs with missing controls: {len(missing_games)}\n"
            f"ROMs with default controls: {len(default_games)}\n\n"
            f"Games needing real control data: {len(generic_games) + len(missing_games)}"
        )
        stats_label = ctk.CTkLabel(
            summary_tab,
            text=stats_text,
            font=("Arial", 14),
            justify="left"
        )
        stats_label.pack(padx=20, pady=20, anchor="w")
        
        # Generic Controls tab
        generic_tab = tabview.add("Generic Controls")
        
        if generic_games:
            # Frame for list and buttons
            list_frame = ctk.CTkFrame(generic_tab)
            list_frame.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Create listbox
            generic_listbox = tk.Listbox(list_frame, font=("Arial", 12))
            generic_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=generic_listbox.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            generic_listbox.config(yscrollcommand=scrollbar.set)
            
            # Populate listbox
            for rom, game_name in generic_games:
                generic_listbox.insert(tk.END, f"{rom} - {game_name}")
            
            # Store the rom names for lookup when editing
            generic_rom_map = [rom for rom, _ in generic_games]
            
            # Button frame
            button_frame = ctk.CTkFrame(generic_tab)
            button_frame.pack(fill="x", padx=10, pady=10)
            
            def edit_selected_generic():
                selection = generic_listbox.curselection()
                if not selection:
                    messagebox.showinfo("Selection Required", "Please select a game to edit")
                    return
                    
                idx = selection[0]
                if idx < len(generic_rom_map):
                    rom = generic_rom_map[idx]
                    game_name = generic_games[idx][1]
                    self.show_control_editor(rom, game_name)
            
            edit_button = ctk.CTkButton(
                button_frame,
                text="Edit Selected Game",
                command=edit_selected_generic
            )
            edit_button.pack(side=tk.LEFT, padx=5)
        else:
            ctk.CTkLabel(
                generic_tab,
                text="No games with generic controls found!",
                font=("Arial", 14)
            ).pack(expand=True)
        
        # Missing Controls tab
        missing_tab = tabview.add("Missing Controls")
        
        if missing_games:
            # Frame for list and buttons
            missing_list_frame = ctk.CTkFrame(missing_tab)
            missing_list_frame.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Create listbox
            missing_listbox = tk.Listbox(missing_list_frame, font=("Arial", 12))
            missing_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
            
            # Add scrollbar
            missing_scrollbar = ttk.Scrollbar(missing_list_frame, orient="vertical", command=missing_listbox.yview)
            missing_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            missing_listbox.config(yscrollcommand=missing_scrollbar.set)
            
            # Populate listbox
            missing_rom_list = sorted(missing_games)
            for rom in missing_rom_list:
                missing_listbox.insert(tk.END, rom)
            
            # Button frame
            missing_button_frame = ctk.CTkFrame(missing_tab)
            missing_button_frame.pack(fill="x", padx=10, pady=10)
            
            def edit_selected_missing():
                selection = missing_listbox.curselection()
                if not selection:
                    messagebox.showinfo("Selection Required", "Please select a game to edit")
                    return
                    
                idx = selection[0]
                if idx < len(missing_rom_list):
                    rom = missing_rom_list[idx]
                    self.show_control_editor(rom)
            
            edit_missing_button = ctk.CTkButton(
                missing_button_frame,
                text="Edit Selected Game",
                command=edit_selected_missing
            )
            edit_missing_button.pack(side=tk.LEFT, padx=5)
        else:
            ctk.CTkLabel(
                missing_tab,
                text="No games with missing controls found!",
                font=("Arial", 14)
            ).pack(expand=True)
        
        # Default Controls tab (new)
        default_tab = tabview.add("Default Controls")
        
        if default_games:
            # Frame for list and buttons
            default_list_frame = ctk.CTkFrame(default_tab)
            default_list_frame.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Create listbox
            default_listbox = tk.Listbox(default_list_frame, font=("Arial", 12))
            default_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
            
            # Add scrollbar
            default_scrollbar = ttk.Scrollbar(default_list_frame, orient="vertical", command=default_listbox.yview)
            default_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            default_listbox.config(yscrollcommand=default_scrollbar.set)
            
            # Populate listbox
            default_rom_list = [rom for rom, _ in default_games]
            for rom, game_name in default_games:
                default_listbox.insert(tk.END, f"{rom} - {game_name}")
            
            # Button frame
            default_button_frame = ctk.CTkFrame(default_tab)
            default_button_frame.pack(fill="x", padx=10, pady=10)
            
            def edit_selected_default():
                selection = default_listbox.curselection()
                if not selection:
                    messagebox.showinfo("Selection Required", "Please select a game to edit")
                    return
                    
                idx = selection[0]
                if idx < len(default_rom_list):
                    rom = default_rom_list[idx]
                    game_name = default_games[idx][1]
                    self.show_control_editor(rom, game_name)
            
            edit_default_button = ctk.CTkButton(
                default_button_frame,
                text="Edit Selected Game",
                command=edit_selected_default
            )
            edit_default_button.pack(side=tk.LEFT, padx=5)
        else:
            ctk.CTkLabel(
                default_tab,
                text="No games with default controls found!",
                font=("Arial", 14)
            ).pack(expand=True)
        
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
                    
                    f.write("Games with Default Controls:\n")
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
        
        # Check for gamedata.json in application directory
        app_gamedata = os.path.join(app_dir, "gamedata.json")
        if os.path.exists(app_gamedata):
            print(f"Using bundled gamedata.json: {app_dir}")
            return app_dir
        
        # Check for gamedata.json in settings directory within app dir
        settings_gamedata = os.path.join(app_dir, "preview", "settings", "gamedata.json")
        if os.path.exists(settings_gamedata):
            print(f"Using gamedata.json in settings folder: {app_dir}")
            return app_dir
            
        # Then check in the current directory
        current_dir = os.path.abspath(os.path.dirname(__file__))
        
        # Look for gamedata.json in various locations
        gamedata_paths = [
            os.path.join(current_dir, "gamedata.json"),
            os.path.join(current_dir, "preview", "settings", "gamedata.json"),  # Added settings path
            os.path.join(current_dir, "metadata", "gamedata.json"),
            os.path.join(current_dir, "data", "gamedata.json")
        ]
        
        for path in gamedata_paths:
            if os.path.exists(path):
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
            # Check both direct and settings paths
            if os.path.exists(os.path.join(path, "gamedata.json")) or \
            os.path.exists(os.path.join(path, "preview", "settings", "gamedata.json")):
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
        """Create the main application layout with configurable buttons"""
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
        self.stats_frame.grid_columnconfigure(3, weight=0)  # Add column for Generate Images button

        # Stats label
        self.stats_label = ctk.CTkLabel(self.stats_frame, text="Loading...", 
                                    font=("Arial", 12))
        self.stats_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Unmatched ROMs button. REPLACED/COMBINED WITH ANALYUZE CONTROLS BUTTON
        #self.unmatched_button = ctk.CTkButton(
        #    self.stats_frame,
        #    text="Show Unmatched ROMs",
        #    command=self.show_unmatched_roms,
        #    width=150
        #)
        #self.unmatched_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # Generate configs button
        generate_configs_button = self.create_button(
            self.stats_frame,
            text="Generate Info Files",
            command=self.generate_all_configs,
            button_id="generate_configs_button",
            show=getattr(self, 'show_generate_info_buttons', True)
        )
        if generate_configs_button:
            generate_configs_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        # REPLACED/COMBINED WITH ANALYUZE CONTROLS BUTTON
        #self.generic_controls_button = ctk.CTkButton(
        #    self.stats_frame,
        #    text="Find Missing Controls",
        #    command=self.show_generic_controls_dialog,
        #    width=150
        #)
        #self.generic_controls_button.grid(row=0, column=5, padx=5, pady=5, sticky="e")

        # Search box
        self.search_var = ctk.StringVar()
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
        preview_button = self.create_button(
            self.right_panel,
            text="Preview Controls",
            command=self.show_preview,
            button_id="preview_button",
            show=getattr(self, 'preview_button', True)
        )
        if preview_button:
            preview_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

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

    def show_preview(self):
        """Show a preview of the control layout for the current game on the second screen"""
        # First close any existing preview windows to prevent accumulation
        self.close_all_previews()
        
        if not self.current_game:
            messagebox.showinfo("No Game Selected", "Please select a game first")
            return
            
        # Create preview directory and handle bundled images if needed
        preview_dir = self.ensure_preview_folder_improved()

        # Check for a ROM-specific image (PNG or JPG)
        image_extensions = [".png", ".jpg", ".jpeg"]
        image_path = None

        for ext in image_extensions:
            test_path = os.path.join(preview_dir, f"{self.current_game}{ext}")
            if os.path.exists(test_path):
                image_path = test_path
                break

        # Fall back to default image (PNG or JPG)
        if not image_path:
            for ext in image_extensions:
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    break

        # If no image found, show a message
        if not image_path:
            messagebox.showinfo(
                "Image Not Found",
                f"No preview image found for {self.current_game}\n"
                f"Place PNG or JPG images in {preview_dir} folder"
            )
            return

        # Get game control data
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            messagebox.showinfo("No Control Data", f"No control data found for {self.current_game}")
            return
        
        # Check for screen preference in settings
        preferred_screen = getattr(self, 'preferred_preview_screen', 2)  # Default to second screen
        
        # We'll use tkinter directly for the window but CustomTkinter for buttons
        import tkinter as tk
        from PIL import Image, ImageTk
        
        # Create our preview window directly
        self.preview_window = tk.Toplevel()
        self.preview_window.title(f"Control Preview: {self.current_game}")
        
        # Hide window initially and prevent flashing
        self.preview_window.withdraw()
        
        # Configure the window to properly exit when closed
        self.preview_window.protocol("WM_DELETE_WINDOW", self.close_preview)
        
        # Bind ESC to the force_quit function
        self.preview_window.bind("<Escape>", lambda event: self.close_preview())
        
        # Get information about monitors through direct Windows API if possible
        monitors = []
        try:
            # Try to use Windows API
            import ctypes
            from ctypes import windll
            
            # Define structs needed to get monitor info
            class RECT(ctypes.Structure):
                _fields_ = [
                    ('left', ctypes.c_long),
                    ('top', ctypes.c_long),
                    ('right', ctypes.c_long),
                    ('bottom', ctypes.c_long)
                ]
                
            # Get monitor info
            def callback(monitor, dc, rect, data):
                rect = ctypes.cast(rect, ctypes.POINTER(RECT)).contents
                monitors.append({
                    'left': rect.left,
                    'top': rect.top,
                    'right': rect.right,
                    'bottom': rect.bottom,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top,
                    'index': len(monitors)  # Add index for selection
                })
                return 1
                
            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(RECT),
                ctypes.c_double
            )
            
            # Enumerate monitors
            windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
            
            print(f"Found {len(monitors)} monitors")
            for i, mon in enumerate(monitors):
                print(f"Monitor {i+1}: {mon['width']}x{mon['height']} at position {mon['left']},{mon['top']}")
                
        except Exception as e:
            print(f"Error using Windows API for monitor detection: {e}")
            # Create a minimal monitor list with defaults
            monitors = [{'left': 0, 'top': 0, 'width': 1920, 'height': 1080, 'index': 0}]
            
            # Try to detect second monitor using simple method
            full_width = self.winfo_screenwidth()
            if full_width > 2000:  # Assume wide screen means multiple monitors
                monitors.append({
                    'left': 1920, 'top': 0, 
                    'width': full_width - 1920, 'height': self.winfo_screenheight(),
                    'index': 1
                })
                print(f"Detected probable second monitor at x=1920 (simple method)")
        
        # Force at least two monitors for button functionality
        if len(monitors) < 2:
            monitors.append({
                'left': monitors[0]['width'], 
                'top': 0, 
                'width': monitors[0]['width'], 
                'height': monitors[0]['height'],
                'index': 1
            })
            print(f"Added virtual second monitor for button functionality")
        
        # Use selected monitor or fall back to primary
        target_monitor = None
        if 0 <= preferred_screen - 1 < len(monitors):
            target_monitor = monitors[preferred_screen - 1]
            print(f"Using preferred screen {preferred_screen}: {target_monitor}")
        else:
            # Default to first monitor if preferred screen doesn't exist
            target_monitor = monitors[0]
            print(f"Preferred screen {preferred_screen} not available, using monitor 1")
            
        # Position window on selected monitor
        window_x = target_monitor['left']
        window_y = target_monitor['top']
        window_width = target_monitor['width']
        window_height = target_monitor['height']
        
        print(f"Setting window dimensions: {window_width}x{window_height}+{window_x}+{window_y}")
        
        # Configure the preview window
        self.preview_window.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
        
        # Make it fullscreen without window decorations
        self.preview_window.overrideredirect(True)
        
        # Update tasks to allow window to process
        self.preview_window.update_idletasks()
        
        # Make the window visible
        self.preview_window.deiconify()
        
        # Ensure it stays on top
        self.preview_window.attributes('-topmost', True)

        # Load and display the image
        try:
            # Load the image
            img = Image.open(image_path)
            print(f"Loaded image: {image_path}, size={img.size}")
            
            # Get window dimensions (use the values we set earlier)
            win_width = window_width
            win_height = window_height
            
            # Resize image to fit window while maintaining aspect ratio
            img_width, img_height = img.size
            
            # Ensure dimensions are positive
            if win_width <= 0:
                win_width = 1024
            if win_height <= 0:
                win_height = 768
            
            # Handle zero-size image
            if img_width <= 0 or img_height <= 0:
                print("Image has invalid dimensions, creating blank image")
                img = Image.new('RGB', (win_width, win_height), color='black')
                img_width, img_height = img.size
            
            # Calculate resize ratio
            ratio = min(win_width/max(img_width, 1), win_height/max(img_height, 1))
            new_width = max(int(img_width * ratio), 1)  # Ensure at least 1 pixel
            new_height = max(int(img_height * ratio), 1)  # Ensure at least 1 pixel
            
            print(f"Resizing image to: {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Create canvas with black background
            canvas = tk.Canvas(self.preview_window, 
                            width=win_width, 
                            height=win_height,
                            bg="black",
                            highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            
            # Center the image
            x = max((win_width - new_width) // 2, 0)
            y = max((win_height - new_height) // 2, 0)
            # After creating the background image
            canvas.create_image(x, y, image=photo, anchor="nw", tags="background_image")
            canvas.image = photo  # Keep a reference to prevent garbage collection

            # Apply proper layering
            self.apply_layering()
            
            # Initialize logo display
            self.preview_logo_item = None
            self.preview_logo_photo = None

            # Load logo settings
            if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
                self.load_logo_settings()
                print(f"Loaded logo settings: visible={self.logo_visible}, position={self.logo_position}")

            # Add logo immediately if it should be visible
            if self.logo_visible:
                try:
                    self.add_logo_to_preview_canvas()
                    print("Added logo during preview initialization")
                except Exception as e:
                    print(f"Error adding logo during initialization: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Store canvas and image info for text placement
            self.preview_canvas = canvas
            self.image_x = x
            self.image_y = y
            
            # Reset text items dictionary
            self.text_items = {}
            
            # Load the position manager with saved positions
            self.position_manager.load_from_file(self.current_game)
            print(f"Loaded {len(self.position_manager.positions)} positions from position manager")
            
            # Load text appearance settings
            settings = self.get_text_settings()
            use_uppercase = settings.get("use_uppercase", False)
            font_family = settings.get("font_family", "Arial")
            font_size = settings.get("font_size", 28)
            bold_strength = settings.get("bold_strength", 2)
            y_offset = settings.get('y_offset', -40)
            
            print(f"Loaded text settings: uppercase={use_uppercase}, font={font_family}, size={font_size}, y_offset={y_offset}")
            
            # Apply scaling factor for fonts
            adjusted_font_size = self.apply_font_scaling(font_family, font_size)
            
            # Create font with correct size and family
            try:
                import tkinter.font as tkfont
                text_font = tkfont.Font(family=font_family, size=adjusted_font_size, weight="bold")
            except Exception as e:
                print(f"Error creating font: {e}")
                text_font = (font_family, adjusted_font_size, "bold")
            
            # Add player controls as text overlays
            control_count = 0
            
            # Process only Player 1 controls
            for player in game_data.get('players', []):
                if player['number'] != 1:
                    continue
                    
                for label in player.get('labels', []):
                    control_name = label['name']
                    action = label['value']
                    
                    # Only include P1 controls
                    if not control_name.startswith('P1_'):
                        continue
                    
                    # Apply uppercase if enabled
                    display_text = self.get_display_text(action, settings)
                    
                    print(f"Adding control: {control_name} = {display_text}")
                    
                    # Get position from position manager or use default
                    if control_name in self.position_manager.positions:
                        # Get normalized position
                        normalized_x, normalized_y = self.position_manager.get_normalized(control_name)
                        
                        # Apply current offset for display
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y, y_offset)
                        
                        print(f"Using saved position for {control_name}: normalized=({normalized_x}, {normalized_y}), display=({text_x}, {text_y})")
                    else:
                        # Default position calculation (arranged in a grid)
                        grid_x = x + 100 + (control_count % 5) * 150
                        grid_y = y + 50 + (control_count // 5) * 40
                        
                        # Apply offset to default position
                        text_x, text_y = grid_x, grid_y + y_offset
                        
                        # Store normalized position
                        normalized_x, normalized_y = grid_x, grid_y
                        
                        print(f"Using default position for {control_name}: ({text_x}, {text_y})")
                    
                    # Check visibility based on control type
                    is_visible = self.is_control_visible(control_name)
                    
                    # Create text with appropriate shadow effect
                    text_item, shadow_item = self.create_text_with_shadow(
                        canvas, 
                        text_x, 
                        text_y, 
                        display_text, 
                        text_font
                    )
                    
                    # Set visibility state
                    if not is_visible:
                        canvas.itemconfigure(text_item, state="hidden")
                        if shadow_item is not None:
                            canvas.itemconfigure(shadow_item, state="hidden")
                    
                    # Store the text items
                    self.text_items[control_name] = {
                        'text': text_item,
                        'shadow': shadow_item,
                        'action': action,           # Store original action for reuse
                        'display_text': display_text, # Store display text that may be uppercase
                        'x': text_x, 
                        'y': text_y,
                        'base_y': normalized_y      # Store the normalized base_y
                    }
                    
                    # Store in position manager (if not already there)
                    if control_name not in self.position_manager.positions:
                        self.position_manager.store(control_name, normalized_x, normalized_y, is_normalized=True)
                    
                    # Make the text draggable
                    self.make_draggable(canvas, text_item, shadow_item, control_name)
                    control_count += 1
            
            # Add right-click menu for text removal
            self.create_context_menu(canvas)

            self.frame_bg = tk.Frame(self.preview_window, bg="black")  # Changed to self.frame_bg

            # Only show if setting allows
            if not hasattr(self, 'hide_preview_buttons') or not self.hide_preview_buttons:
                self.frame_bg.place(relx=0.5, rely=0.95, anchor="center", width=min(1000, window_width-20), height=80)

            # Create ctk frame with default color
            button_frame = ctk.CTkFrame(self.frame_bg)  # Changed from frame_bg to self.frame_bg
            button_frame.pack(expand=True, fill="both")
            self.button_frame = button_frame  # Store reference to button frame

            # Create two rows of buttons using frames
            top_row = ctk.CTkFrame(button_frame)
            top_row.pack(side="top", fill="x", expand=True, pady=2)

            bottom_row = ctk.CTkFrame(button_frame)
            bottom_row.pack(side="bottom", fill="x", expand=True, pady=2)

            # Store row references for the feature buttons
            self.button_row1 = top_row
            self.button_row2 = bottom_row

            # Calculate button width to fit all buttons
            button_width = 90  # Slightly smaller width
            button_padx = 3    # Smaller padding
            
            # Top row buttons (4 buttons)
            # Close button - use the force_quit function to ensure proper termination
            close_button = self.create_button(
                top_row,
                text="Close",
                command=self.close_preview,
                button_id="preview_close_button",
                width=button_width
            )
            if close_button:
                close_button.pack(side="left", padx=button_padx)

            # Reset positions button
            reset_button = self.create_button(
                top_row,
                text="Reset",
                command=self.reset_text_positions,
                button_id="preview_reset_button",
                width=button_width
            )
            if reset_button:
                reset_button.pack(side="left", padx=button_padx)

            # Add save buttons
            global_button = self.create_button(
                top_row,
                text="Global",
                command=self.save_global_positions,
                button_id="preview_global_button",
                width=button_width
            )
            if global_button:
                global_button.pack(side="left", padx=button_padx)

            # ROM button
            rom_button = self.create_button(
                top_row,
                text="ROM",
                command=self.save_rom_positions,
                button_id="preview_rom_button",
                width=button_width
            )
            if rom_button:
                rom_button.pack(side="left", padx=button_padx)

            # Bottom row buttons
            # Set initial state for toggle buttons
            self.show_texts = True

            # Add toggle joystick button
            joystick_button = ctk.CTkButton(
                bottom_row,
                text="Joystick",
                command=self.toggle_joystick_controls,
                width=button_width
            )
            joystick_button.pack(side="left", padx=button_padx)

            # Add toggle texts button to bottom row
            def toggle_texts():
                self.toggle_texts_visibility()
                texts_button.configure(text="Hide Texts" if self.show_texts else "Show Texts")
                
            texts_button = ctk.CTkButton(
                bottom_row,
                text="Hide Texts",
                command=toggle_texts,
                width=button_width
            )
            texts_button.pack(side="left", padx=button_padx)

            # Initialize logo settings
            if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
                self.load_logo_settings()
                print(f"Loaded logo settings: visible={self.logo_visible}, position={self.logo_position}")
            
            # Schedule the logo to be added after the window has fully rendered (300ms delay)
            if self.logo_visible:
                self.preview_window.after(300, self.add_logo_to_preview_canvas)
                print("Scheduled logo to be added after window initialization")
            
            # Add logo visibility toggle button to bottom row
            logo_toggle_text = "Hide Logo" if self.logo_visible else "Show Logo"
            logo_toggle_button = ctk.CTkButton(
                bottom_row,
                text=logo_toggle_text,
                command=self.toggle_logo_visibility,
                width=button_width
            )
            logo_toggle_button.pack(side="left", padx=button_padx)
            self.logo_toggle_button = logo_toggle_button  # Save reference
            
            # Add logo position button to bottom row
            logo_position_button = ctk.CTkButton(
                bottom_row,
                text="Logo Pos",
                command=self.show_logo_position_dialog,
                width=button_width
            )
            logo_position_button.pack(side="left", padx=button_padx)
            self.logo_position_button = logo_position_button  # Save reference
            
            # Now add the logo to the preview canvas if visibility is on
            if self.logo_visible:
                self.add_logo_to_preview_canvas()
            
            # Add text settings button to the top row
            text_settings_button = ctk.CTkButton(
                top_row,
                text="Text Settings",
                command=lambda: self.show_text_appearance_settings(update_preview=True),
                width=button_width
            )
            text_settings_button.pack(side="left", padx=button_padx)
            
            # Add the "Save Image" button
            save_button = ctk.CTkButton(
                top_row,
                text="Save Image",
                command=self.save_current_preview,
                width=button_width
            )
            save_button.pack(side="left", padx=button_padx)

             # Add a repeated check to ensure logo appears
            def ping_logo_visibility(attempt=1, max_attempts=5):
                """Try multiple times to ensure logo is visible"""
                if not hasattr(self, 'preview_window') or not self.preview_window.winfo_exists():
                    return  # Window closed, stop trying
                    
                if self.logo_visible and (not hasattr(self, 'preview_logo_item') or not self.preview_logo_item):
                    print(f"Logo visibility check attempt {attempt} - adding logo now")
                    success = self.add_logo_to_preview_canvas()
                    
                    # If unsuccessful and we haven't reached max attempts, try again
                    if not success and attempt < max_attempts:
                        self.preview_window.after(250, lambda: ping_logo_visibility(attempt + 1, max_attempts))
                    elif success:
                        print(f"Logo successfully added on attempt {attempt}")
                    else:
                        print(f"Failed to add logo after {attempt} attempts")
                elif hasattr(self, 'preview_logo_item') and self.preview_logo_item:
                    print(f"Logo already visible on attempt {attempt}")
            
            # Schedule the first check after 200ms
            self.preview_window.after(200, ping_logo_visibility)
            
            # Add toggle screen button to bottom row
            def toggle_screen():
                # Cycle to the next available monitor
                current_screen = getattr(self, 'preferred_preview_screen', 2)
                next_screen = (current_screen % len(monitors)) + 1
                
                # Set the preference and print
                self.preferred_preview_screen = next_screen
                print(f"Switching to screen {next_screen}")
                
                # Close and reopen the preview window
                self.preview_window.destroy()
                self.show_preview()
                
            screen_button = ctk.CTkButton(
                bottom_row,
                text=f"Screen {preferred_screen}",
                command=toggle_screen,
                width=button_width
            )
            screen_button.pack(side="left", padx=button_padx)

            # Add the feature functions
            self.add_alignment_guides()
            self.add_show_all_buttons_feature()
        
        except ImportError:
            messagebox.showinfo("Missing Package", "Please install Pillow: pip install pillow")
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying image: {str(e)}")
            import traceback
            traceback.print_exc()

    def get_tkfont(self, settings=None):
        """Get a tkinter font object based on settings"""
        import tkinter.font as tkfont
        
        if settings is None:
            settings = self.get_text_settings()
        
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        
        # Apply scaling factor for certain fonts
        scale = self.apply_font_scaling(font_family, font_size)
        adjusted_size = int(scale)
        
        # Create and return the font object
        try:
            return tkfont.Font(family=font_family, size=adjusted_size, weight="bold")
        except Exception as e:
            print(f"Error creating font: {e}")
            return tkfont.Font(family="Arial", size=28, weight="bold")  # Fallback font
    
    def apply_font_scaling(self, font_family, font_size):
        """Apply scaling factor for certain fonts that appear smaller than expected"""
        # Define scaling factors for fonts that tend to appear small
        scaling_factors = {
            "Times New Roman": 1.5,
            "Press Start 2P": 0.8,
            "Times": 1.5,
            "Georgia": 1.4,
            "Garamond": 1.7,
            "Baskerville": 1.6,
            "Palatino": 1.5,
            "Courier New": 1.3,
            "Courier": 1.3,
            "Consolas": 1.2,
            "Cambria": 1.4,
            # Add more here if you find other fonts need adjustment
        }
        
        # Apply scaling if the font needs it, otherwise return original size
        scale = scaling_factors.get(font_family, 1.0)
        adjusted_size = int(font_size * scale)
        
        print(f"Font scaling: {font_family} size {font_size} → {adjusted_size} (scale factor: {scale})")
        return adjusted_size
    
    # 2. Add the toggle handler method
    def toggle_hide_preview_buttons(self):
        """Toggle whether preview buttons should be hidden"""
        self.hide_preview_buttons = self.hide_buttons_toggle.get()
        
        # Save setting to config file
        self.save_preview_button_setting()
        
        # Update any open preview windows
        if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
            if self.hide_preview_buttons:
                self.hide_button_frame()
            else:
                self.show_button_frame()

    # 3. Add methods to save and load the setting
    def save_preview_button_setting(self):
        """Save the preview buttons visibility setting using centralized path"""
        try:
            # Use centralized settings path function
            settings_path = self.get_settings_path("general")
            
            # Load existing settings if available
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            
            # Add hide buttons setting
            settings['hide_preview_buttons'] = self.hide_preview_buttons
            
            # Save back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
                
            print(f"Saved hide_preview_buttons setting: {self.hide_preview_buttons} to {settings_path}")
        except Exception as e:
            print(f"Error saving setting: {e}")
    
    def save_visibility_settings(self):
        """Save joystick visibility and other display settings using the centralized path"""
        try:
            # Get settings path using the centralized function
            settings_path = self.get_settings_path("general")
            
            # Load existing settings if available
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            
            # Update with current visibility settings
            settings['visible_control_types'] = self.visible_control_types
            
            # Save back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
                
            print(f"Saved visibility settings to: {settings_path}")
            print(f"Visibility settings: {self.visible_control_types}")
            return True
        except Exception as e:
            print(f"Error saving visibility settings: {e}")
            return False

    def toggle_joystick_controls(self):
        """Toggle joystick controls visibility and save the setting using centralized path"""
        # Check if joystick is currently visible
        joystick_visible = "JOYSTICK" in self.visible_control_types
        
        # Store joystick positions before hiding them
        if joystick_visible:
            # We're about to hide joysticks, store their positions
            self.temp_joystick_positions = {}
            joystick_buttons = ["UP", "DOWN", "LEFT", "RIGHT"]
            
            for button_name in joystick_buttons:
                if button_name in self.text_items:
                    data = self.text_items[button_name]
                    if 'x' in data and 'base_y' in data:
                        # Store normalized position
                        self.temp_joystick_positions[button_name] = (data['x'], data['base_y'])
                        print(f"Stored joystick position before hiding: {button_name} = ({data['x']}, {data['base_y']})")
        
        if joystick_visible:
            # Remove JOYSTICK from visible types
            self.visible_control_types.remove("JOYSTICK")
        else:
            # Add JOYSTICK to visible types
            self.visible_control_types.append("JOYSTICK")
        
        # Update existing controls
        joystick_visible = not joystick_visible  # New state
        state = "" if joystick_visible else "hidden"
        
        # List of XInput button names that correspond to joystick directions
        joystick_buttons = ["UP", "DOWN", "LEFT", "RIGHT"]
        
        # Update visibility of current controls based on XInput button names
        for button_name, data in self.text_items.items():
            # Check if this is a joystick direction button
            if button_name in joystick_buttons:
                if 'text' in data:
                    self.preview_canvas.itemconfigure(data['text'], state=state)
                if 'shadow' in data and data['shadow']:
                    self.preview_canvas.itemconfigure(data['shadow'], state=state)
        
        # Save the visibility setting using centralized path function
        success = self.save_visibility_settings()
        
        print(f"Toggled joystick visibility to: {joystick_visible} (Save success: {success})")
    
    def save_global_positions(self):
        """Save all positions to global file, including hidden controls"""
        try:
            # Reset the positions storage to start fresh
            self.position_manager = PositionManager(self)
            
            # Log current text positions before processing
            print("\n=== SAVING GLOBAL POSITIONS ===")
            print(f"Found {len(self.text_items)} text items to save")
            
            # Track the hidden status of joystick controls
            joystick_hidden = "JOYSTICK" not in self.visible_control_types
            joystick_controls = ["UP", "DOWN", "LEFT", "RIGHT"]
            
            # Process each text item and store its position properly
            for button_name, data in self.text_items.items():
                if 'x' not in data or 'y' not in data:
                    print(f"  Warning: Missing x/y for {button_name}")
                    continue
                    
                # Get raw display coordinates from the text item
                display_x = data['x']
                display_y = data['y']
                
                # Get text settings for proper y-offset handling
                settings = self.get_text_settings()
                y_offset = settings.get('y_offset', -40)
                
                # Calculate normalized y-coordinate (remove the y-offset effect)
                normalized_y = display_y - y_offset
                
                # Store normalized coordinates in position manager using XInput button as key
                self.position_manager.store(button_name, display_x, normalized_y, is_normalized=True)
                
                is_joystick = button_name in joystick_controls
                print(f"  Stored position for {button_name}: display=({display_x}, {display_y}), normalized=({display_x}, {normalized_y}), joystick={is_joystick}")
            
            # Get positions from any hidden joystick controls from the "Show All" view
            if joystick_hidden and self.showing_all_controls:
                # We're in "Show All" mode with joystick hidden
                # Need to retrieve joystick positions from temp storage
                # This ensures we don't lose joystick positions when they're hidden
                for button_name in joystick_controls:
                    if button_name not in self.text_items and hasattr(self, 'temp_joystick_positions'):
                        if button_name in self.temp_joystick_positions:
                            x, normalized_y = self.temp_joystick_positions[button_name]
                            self.position_manager.store(button_name, x, normalized_y, is_normalized=True)
                            print(f"  Recovered hidden joystick position for {button_name}: ({x}, {normalized_y})")
            
            # Save the positions to file
            result = self.position_manager.save_to_file(is_global=True)
            
            # Print positions that were actually saved
            print("\nPositions saved to global file:")
            for name, (x, y) in self.position_manager.positions.items():
                print(f"  {name}: [{x}, {y}]")
            
            if result:
                count = len(self.position_manager.positions)
                print(f"\nSaved {count} global positions")
                messagebox.showinfo("Success", f"Global positions saved ({count} items)")
                return True
            else:
                messagebox.showerror("Error", "Could not save positions")
                return False
                
        except Exception as e:
            print(f"Error saving global positions: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not save positions: {e}")
            return False

    def save_rom_positions(self):
        """Save positions for current ROM using the position manager"""
        if not self.current_game:
            messagebox.showinfo("Error", "No game selected")
            return False
            
        try:
            # Make sure we have a position manager
            if not hasattr(self, 'position_manager'):
                self.position_manager = PositionManager(self)
            
            # Update the position manager with current text item positions
            if hasattr(self, 'text_items'):
                self.position_manager.update_from_text_items(self.text_items)
            
            # Save positions for the current game
            result = self.position_manager.save_to_file(game_name=self.current_game, is_global=False)
            
            if result:
                count = len(self.position_manager.positions)
                print(f"Saved {count} positions for {self.current_game}")
                messagebox.showinfo("Success", f"Positions saved for {self.current_game}")
                return True
            else:
                messagebox.showerror("Error", "Could not save positions")
                return False
                
        except Exception as e:
            print(f"Error saving ROM positions: {e}")
            messagebox.showerror("Error", f"Could not save positions: {e}")
            return False
    
    def make_draggable(self, canvas, text_item, shadow_item, control_name):
        """Make text draggable on the canvas with position manager integration"""
        def on_drag_start(event):
            # Save initial position
            canvas.drag_data = {
                'text': text_item,
                'shadow': shadow_item,
                'control': control_name,
                'x': canvas.canvasx(event.x),
                'y': canvas.canvasy(event.y)
            }
        
        def on_drag_motion(event):
            if hasattr(canvas, 'drag_data'):
                try:
                    control_name = canvas.drag_data['control']
                    
                    # Calculate movement
                    dx = canvas.canvasx(event.x) - canvas.drag_data['x']
                    dy = canvas.canvasy(event.y) - canvas.drag_data['y']
                    
                    # Move the text and shadow
                    canvas.move(canvas.drag_data['text'], dx, dy)
                    if canvas.drag_data['shadow'] is not None:
                        canvas.move(canvas.drag_data['shadow'], dx, dy)
                    
                    # Update saved coordinates
                    canvas.drag_data['x'] = canvas.canvasx(event.x)
                    canvas.drag_data['y'] = canvas.canvasy(event.y)
                    
                    # Update stored position with explicit values
                    old_x = self.text_items[control_name]['x']
                    old_y = self.text_items[control_name]['y']
                    new_x = old_x + dx
                    new_y = old_y + dy
                    
                    # Update with position manager
                    x, normalized_y = self.position_manager.update_from_dragging(control_name, new_x, new_y)
                    
                    # Update the text item dictionary
                    self.text_items[control_name]['x'] = new_x
                    self.text_items[control_name]['y'] = new_y
                    self.text_items[control_name]['base_y'] = normalized_y  # Store the normalized base_y
                    
                    # Print debugging info
                    if "BUTTON" in control_name:
                        print(f"Dragging {control_name}: ({old_x},{old_y}) -> ({new_x},{new_y}), base_y={normalized_y}")
                        
                except Exception as e:
                    print(f"Error in drag motion: {e}")
                    import traceback
                    traceback.print_exc()
        
        def on_drag_end(event):
            # Clean up
            if hasattr(canvas, 'drag_data'):
                try:
                    # Print final position for debugging
                    control_name = canvas.drag_data['control']
                    x, y = self.text_items[control_name]['x'], self.text_items[control_name]['y']
                    base_y = self.text_items[control_name].get('base_y', y)
                    print(f"Final position for {control_name}: x={x}, y={y}, base_y={base_y}")
                except Exception as e:
                    print(f"Error in drag end: {e}")
                finally:
                    delattr(canvas, 'drag_data')
        
        # Bind mouse events to the text
        canvas.tag_bind(text_item, "<ButtonPress-1>", on_drag_start)
        canvas.tag_bind(text_item, "<B1-Motion>", on_drag_motion)
        canvas.tag_bind(text_item, "<ButtonRelease-1>", on_drag_end)

    def create_context_menu(self, canvas):
        """Create right-click menu for text items"""
        from tkinter import Menu
        
        def show_context_menu(event):
            # Find text item under cursor
            items = canvas.find_closest(canvas.canvasx(event.x), canvas.canvasy(event.y))
            if items:
                for control_name, data in self.text_items.items():
                    if data['text'] == items[0] or data['shadow'] == items[0]:
                        self.selected_text = control_name
                        context_menu.post(event.x_root, event.y_root)
                        break
        
        def remove_text():
            if hasattr(self, 'selected_text'):
                control_name = self.selected_text
                if control_name in self.text_items:
                    # Remove text from canvas
                    canvas.delete(self.text_items[control_name]['text'])
                    canvas.delete(self.text_items[control_name]['shadow'])
                    del self.text_items[control_name]
        
        def reset_text():
            if hasattr(self, 'selected_text'):
                self.reset_single_text_position(self.selected_text)
        
        # Create menu
        context_menu = Menu(canvas, tearoff=0)
        context_menu.add_command(label="Remove Text", command=remove_text)
        context_menu.add_command(label="Reset Position", command=reset_text)
        
        # Bind right-click
        canvas.bind("<Button-3>", show_context_menu)

    def save_text_positions_global(self):
        """Save positions globally for all games"""
        if not self.current_game:
            messagebox.showinfo("No Game", "No game is selected")
            return
            
        # Define the global file path
        preview_dir = os.path.join(self.mame_dir, "preview")
        global_file = os.path.join(preview_dir, "global_positions.json")
        
        # Save to this file
        if self.save_positions_to_file(global_file):
            messagebox.showinfo("Success", "Positions saved globally for all games")
    
    def load_text_positions(self, rom_name):
        """Load text positions, with default positions as fallback using centralized paths"""
        positions = {}
        
        # Check if we should use the no-names variant of positions file
        show_button_names = getattr(self, 'show_button_names', True)
        suffix = "" if show_button_names else "_no_names"
        
        # First try ROM-specific positions
        rom_positions_file = self.get_settings_path(f"positions{suffix}", rom_name)
        if os.path.exists(rom_positions_file):
            try:
                with open(rom_positions_file, 'r') as f:
                    positions = json.load(f)
                print(f"Loaded {len(positions)} ROM-specific positions from: {rom_positions_file}")
                return positions
            except Exception as e:
                print(f"Error loading ROM-specific positions: {e}")
        
        # Fall back to global positions
        global_positions_file = self.get_settings_path(f"positions{suffix}")
        if os.path.exists(global_positions_file):
            try:
                with open(global_positions_file, 'r') as f:
                    positions = json.load(f)
                print(f"Loaded {len(positions)} positions from global file: {global_positions_file}")
            except Exception as e:
                print(f"Error loading global positions: {e}")
        
        # If no positions found with current suffix, try the other variant as fallback
        if not positions:
            alt_suffix = "_no_names" if show_button_names else ""
            alt_global_file = self.get_settings_path(f"positions{alt_suffix}")
            if os.path.exists(alt_global_file):
                try:
                    with open(alt_global_file, 'r') as f:
                        positions = json.load(f)
                    print(f"Loaded {len(positions)} positions from alternate global file: {alt_global_file}")
                except Exception as e:
                    print(f"Error loading alternate global positions: {e}")
        
        # If no positions found or file doesn't exist, use default positions
        if not positions:
            # Default XInput button positions
            default_positions = {
                "A": [739.3333333333334, 322.0], 
                "B": [739.3333333333334, 401.0], 
                "X": [739.3333333333334, 478.0], 
                "Y": [739.3333333333334, 548.0], 
                "LB": [739.3333333333334, 782.0], 
                "RB": [739.3333333333334, 626.0], 
                "LT": [739.3333333333334, 856.0], 
                "RT": [739.3333333333334, 701.0], 
                "LS": [739.3333333333334, 941.0], 
                "RS": [739.3333333333334, 999.0], 
                "UP": [669.3333333333334, 367.0], 
                "DOWN": [668.3333333333334, 322.0], 
                "LEFT": [667.3333333333334, 456.0], 
                "RIGHT": [667.3333333333334, 412.0]
            }
            
            positions = default_positions
            print(f"No saved positions found, using {len(positions)} default positions")
            
            # Create the global positions file with defaults
            try:
                with open(global_positions_file, 'w') as f:
                    json.dump(default_positions, f)
                print(f"Created global positions file with defaults: {global_positions_file}")
            except Exception as e:
                print(f"Error creating default global positions file: {e}")
        
        return positions
    
    def reset_text_positions(self):
        """Reset all text positions to default"""
        text_y = self.image_y + 50
        i = 0
        
        for control_name in list(self.text_items.keys()):
            self.reset_single_text_position(control_name, index=i)
            i += 1

    def reset_single_text_position(self, control_name, index=None):
        """Reset a single text to default position"""
        if index is None:
            index = list(self.text_items.keys()).index(control_name)
        
        # Calculate default position (5 items per row)
        text_x = self.image_x + 100 + (index % 5) * 150
        text_y = self.image_y + 50 + (index // 5) * 40
        
        # Move text and shadow
        data = self.text_items[control_name]
        self.preview_canvas.coords(data['text'], text_x, text_y)
        self.preview_canvas.coords(data['shadow'], text_x+2, text_y+2)
        
        # Update stored position
        self.text_items[control_name]['x'] = text_x
        self.text_items[control_name]['y'] = text_y

    def toggle_texts_visibility(self):
        """Toggle visibility of all text items"""
        import tkinter as tk  # Add the import here
        
        self.show_texts = not self.show_texts
        
        # Set visibility state for vanilla tkinter
        state = tk.NORMAL if self.show_texts else tk.HIDDEN
        for data in self.text_items.values():
            self.preview_canvas.itemconfig(data['text'], state=state)
            self.preview_canvas.itemconfig(data['shadow'], state=state)
    
    def load_all_data(self):
        """Modified load_all_data to use improved folder checks"""
        # Display loading status
        if hasattr(self, 'stats_label'):
            self.stats_label.configure(text="Loading settings and ROMs...")
        
        # Load settings first (small and fast)
        self.load_settings()
        
        # Ensure preview folder and default image exist
        self.ensure_preview_folder_improved()
        
        # Initialize database only if needed
        db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
        if not os.path.exists(db_path) or self.is_database_update_needed():
            # Start a thread to build the database in the background
            import threading
            build_thread = threading.Thread(target=self.build_gamedata_db)
            build_thread.daemon = True
            build_thread.start()
            
            # If database building is still running, show status
            if build_thread.is_alive():
                if hasattr(self, 'stats_label'):
                    self.stats_label.configure(text="Building SQLite index (this may take a moment)...")
                
                # Wait for the database to be built (UI will freeze temporarily)
                build_thread.join()
        else:
            # Database is up to date, just set the path
            self.db_path = db_path
            print(f"Using existing database: {db_path}")
        
        # Scan ROMs directory (with caching for speed)
        self.scan_roms_directory()
        
        # Load default config (usually quick)
        self.load_default_config()
        
        # Load custom configs (can be slow for many files)
        self.load_custom_configs()
        
        # Update UI after all data is loaded
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
            
    def switch_to_ingame_mode(self):
        """Switch to a simplified, large-format display for in-game reference"""
        if not self.current_game:
            return
            
        # Clear existing display
        for widget in self.control_frame.winfo_children():
            widget.destroy()
            
        # Get the current game's controls
        game_data = next((game for game in self.controls_data if game['romname'] == self.current_game), None)
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

    def load_gamedata_json(self):
        """Load and parse the gamedata.json file for control data with improved performance"""
        if hasattr(self, 'gamedata_json') and self.gamedata_json:
            # Already loaded
            return self.gamedata_json
                
        self.gamedata_json = {}
        
        # Look for gamedata.json in common locations
        json_path = self.get_gamedata_path()
        if not os.path.exists(json_path):
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
    
    def get_game_data_with_ijson(self, romname):
        """Get game data for a specific ROM using ijson for better performance"""
        # Initialize cache if it doesn't exist
        if not hasattr(self, 'rom_data_cache'):
            self.rom_data_cache = {}
                
        # Return cached data if available
        if romname in self.rom_data_cache:
            print(f"Using cached data for {romname}")
            return self.rom_data_cache[romname]
        
        # First check for custom edits
        custom_path = os.path.join(self.mame_dir, "custom_controls", f"{romname}.json")
        if os.path.exists(custom_path):
            try:
                with open(custom_path, 'r', encoding='utf-8') as f:
                    custom_data = json.load(f)
                    # Make sure essential fields are set
                    custom_data['romname'] = romname
                    custom_data['source'] = 'custom'
                    print(f"Using custom controls for {romname}")
                    # Cache the result before returning
                    self.rom_data_cache[romname] = custom_data
                    return custom_data
            except Exception as e:
                print(f"Error loading custom controls for {romname}: {e}")
        
        try:
            print(f"Attempting to load data for ROM {romname} using ijson")
            
            json_path = self.get_gamedata_path()
            if not json_path or not os.path.exists(json_path):
                print("gamedata.json not found in any expected location")
                return None
            
            # Try importing ijson
            try:
                import ijson
                print("Successfully imported ijson")
            except ImportError:
                print("ijson not installed, falling back to regular JSON parsing")
                return self.get_game_data(romname)
            
            # Data structures we'll build
            found_data = None
            parent_rom = None
            controls = None
            
            # First attempt: try to find ROM as direct entry
            with open(json_path, 'rb') as f:
                print(f"Searching for {romname} as direct entry")
                parser = ijson.parse(f)
                
                # First pass to find if this ROM exists directly
                for prefix, event, value in parser:
                    if event == 'map_key' and value == romname:
                        print(f"Found {romname} as direct entry")
                        found_data = {}
                        found_data['romname'] = romname
                        break
                
            # If ROM found as direct entry, get its data
            if found_data is not None:
                print(f"Extracting data for direct entry {romname}")
                with open(json_path, 'rb') as f:
                    for prefix, event, value in ijson.parse(f):
                        if prefix == f"{romname}.description" and event == 'string':
                            found_data['description'] = value
                            print(f"Found description for {romname}: {value}")
                        elif prefix == f"{romname}.buttons" and (event == 'string' or event == 'number'):
                            found_data['buttons'] = value
                        elif prefix == f"{romname}.sticks" and (event == 'string' or event == 'number'):
                            found_data['sticks'] = value
                        elif prefix == f"{romname}.playercount" and (event == 'string' or event == 'number'):
                            found_data['playercount'] = value
                        elif prefix == f"{romname}.alternating" and (event == 'string' or event == 'boolean'):
                            found_data['alternating'] = value
                        elif prefix == f"{romname}.controls":
                            if event == 'map_key':
                                # ROM has controls - will collect them in a separate pass
                                if controls is None:
                                    controls = {}
                                    print(f"ROM {romname} has controls section")
            
            # If we found the ROM but need to extract controls
            if found_data is not None and controls is not None:
                print(f"Extracting controls for {romname}")
                with open(json_path, 'rb') as f:
                    current_control = None
                    control_name = None
                    
                    for prefix, event, value in ijson.parse(f):
                        # Look for controls section and populate it
                        if prefix.startswith(f"{romname}.controls."):
                            parts = prefix.split('.')
                            if len(parts) == 3 and event == 'map_key':
                                # This is a control name (e.g., "P1_BUTTON1")
                                control_name = value
                                controls[control_name] = {}
                                current_control = controls[control_name]
                                print(f"Found control: {control_name}")
                            elif len(parts) == 4 and current_control is not None:
                                # This is a control property
                                attr_name = parts[3]
                                if event in ('string', 'number', 'boolean'):
                                    current_control[attr_name] = value
                                    if attr_name == 'name':
                                        print(f"  - {control_name} name: {value}")
            
            # If we didn't find it as a direct entry, look for it as a clone
            if found_data is None:
                print(f"ROM {romname} not found as direct entry, checking for clone")
                with open(json_path, 'rb') as f:
                    for prefix, event, value in ijson.parse(f):
                        parts = prefix.split('.')
                        # Look for entries like "somegame.clones"
                        if len(parts) == 2 and parts[1] == 'clones' and event == 'map_key':
                            potential_parent = parts[0]
                            # Then check if our ROM is a clone of this game
                            clone_check_prefix = f"{potential_parent}.clones.{romname}"
                            
                            # Look ahead to see if this clone exists
                            for p2, e2, v2 in ijson.parse(f):
                                if p2.startswith(clone_check_prefix):
                                    # Found our ROM as a clone
                                    print(f"Found {romname} as clone of {potential_parent}")
                                    parent_rom = potential_parent
                                    found_data = {'romname': romname, 'parent': parent_rom}
                                    break
                            
                            if parent_rom:
                                break
            
            # If we found it as a clone, extract its data
            if parent_rom and found_data:
                print(f"Extracting data for clone {romname} of parent {parent_rom}")
                with open(json_path, 'rb') as f:
                    clone_prefix = f"{parent_rom}.clones.{romname}"
                    for prefix, event, value in ijson.parse(f):
                        if prefix == f"{clone_prefix}.description" and event == 'string':
                            found_data['description'] = value
                            print(f"Found description for clone {romname}: {value}")
                        elif prefix == f"{clone_prefix}.buttons" and (event == 'string' or event == 'number'):
                            found_data['buttons'] = value
                        elif prefix == f"{clone_prefix}.sticks" and (event == 'string' or event == 'number'):
                            found_data['sticks'] = value
                        elif prefix == f"{clone_prefix}.playercount" and (event == 'string' or event == 'number'):
                            found_data['playercount'] = value
                        elif prefix == f"{clone_prefix}.alternating" and (event == 'string' or event == 'boolean'):
                            found_data['alternating'] = value
                
                # If clone doesn't have controls, try to get controls from parent
                if controls is None:
                    print(f"Checking if parent {parent_rom} has controls")
                    with open(json_path, 'rb') as f:
                        # First check if parent has controls section
                        has_controls = False
                        for prefix, event, value in ijson.parse(f):
                            if prefix == f"{parent_rom}.controls" and event == 'map_key':
                                has_controls = True
                                controls = {}
                                print(f"Parent {parent_rom} has controls section")
                                break
                        
                        # If parent has controls, extract them
                        if has_controls:
                            print(f"Extracting controls from parent {parent_rom}")
                            current_control = None
                            control_name = None
                            
                            with open(json_path, 'rb') as f2:
                                for prefix, event, value in ijson.parse(f2):
                                    # Look for controls section and populate it
                                    if prefix.startswith(f"{parent_rom}.controls."):
                                        parts = prefix.split('.')
                                        if len(parts) == 3 and event == 'map_key':
                                            # This is a control name (e.g., "P1_BUTTON1")
                                            control_name = value
                                            controls[control_name] = {}
                                            current_control = controls[control_name]
                                            print(f"Found control from parent: {control_name}")
                                        elif len(parts) == 4 and current_control is not None:
                                            # This is a control property
                                            attr_name = parts[3]
                                            if event in ('string', 'number', 'boolean'):
                                                current_control[attr_name] = value
                                                if attr_name == 'name':
                                                    print(f"  - {control_name} name: {value}")
            
            # If we couldn't find the ROM at all
            if found_data is None:
                print(f"ROM {romname} not found in gamedata.json")
                return None
                
            # If we found ROM data but don't have description
            if 'description' not in found_data:
                print(f"Missing description for {romname}")
                found_data['description'] = romname  # Use ROM name as fallback
            
            # Convert to expected format
            print(f"Converting data for {romname} to expected format")
            
            # Default action names
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
                'P2_BUTTON1': 'A Button',
                'P2_BUTTON2': 'B Button',
                'P2_BUTTON3': 'X Button',
                'P2_BUTTON4': 'Y Button',
                'P2_BUTTON5': 'LB Button',
                'P2_BUTTON6': 'RB Button',
            }
            
            # Basic structure for output
            converted_data = {
                'romname': romname,
                'gamename': found_data.get('description', romname),
                'numPlayers': int(found_data.get('playercount', 1)),
                'alternating': found_data.get('alternating', False),
                'mirrored': False,
                'miscDetails': f"Buttons: {found_data.get('buttons', '?')}, Sticks: {found_data.get('sticks', '?')}",
                'players': [],
                'source': 'ijson'
            }
            
            # Process controls if we have any
            if controls:
                # First collect P1 button names to mirror to P2
                p1_button_names = {}
                for control_name, control_data in controls.items():
                    if control_name.startswith('P1_BUTTON') and 'name' in control_data:
                        button_num = control_name.replace('P1_BUTTON', '')
                        p1_button_names[f'P2_BUTTON{button_num}'] = control_data['name']
                
                # Organize controls by player
                p1_controls = []
                p2_controls = []
                
                for control_name, control_data in controls.items():
                    if control_name.startswith('P1_'):
                        if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                            # Get friendly name for this control
                            friendly_name = None
                            if 'name' in control_data:
                                friendly_name = control_data['name']
                            elif control_name in default_actions:
                                friendly_name = default_actions[control_name]
                            else:
                                parts = control_name.split('_')
                                if len(parts) > 1:
                                    friendly_name = parts[-1]
                            
                            if friendly_name:
                                p1_controls.append({
                                    'name': control_name,
                                    'value': friendly_name
                                })
                    
                    elif control_name.startswith('P2_'):
                        if 'JOYSTICK' in control_name or 'BUTTON' in control_name:
                            friendly_name = None
                            if 'name' in control_data:
                                friendly_name = control_data['name']
                            elif control_name in p1_button_names:
                                friendly_name = p1_button_names[control_name]
                            elif control_name in default_actions:
                                friendly_name = default_actions[control_name]
                            else:
                                parts = control_name.split('_')
                                if len(parts) > 1:
                                    friendly_name = parts[-1]
                            
                            if friendly_name:
                                p2_controls.append({
                                    'name': control_name,
                                    'value': friendly_name
                                })
                
                # Handle special direction mappings
                direction_mappings = {
                    'P1_UP': 'P1_JOYSTICK_UP',
                    'P1_DOWN': 'P1_JOYSTICK_DOWN',
                    'P1_LEFT': 'P1_JOYSTICK_LEFT',
                    'P1_RIGHT': 'P1_JOYSTICK_RIGHT',
                    'P2_UP': 'P2_JOYSTICK_UP',
                    'P2_DOWN': 'P2_JOYSTICK_DOWN',
                    'P2_LEFT': 'P2_JOYSTICK_LEFT',
                    'P2_RIGHT': 'P2_JOYSTICK_RIGHT'
                }
                
                for dir_control, joy_control in direction_mappings.items():
                    if dir_control in controls and 'name' in controls[dir_control]:
                        # Find the corresponding joystick control and update its name
                        if dir_control.startswith('P1_'):
                            for control in p1_controls:
                                if control['name'] == joy_control:
                                    control['value'] = controls[dir_control]['name']
                        elif dir_control.startswith('P2_'):
                            for control in p2_controls:
                                if control['name'] == joy_control:
                                    control['value'] = controls[dir_control]['name']
                
                # Sort controls by name
                p1_controls.sort(key=lambda x: x['name'])
                p2_controls.sort(key=lambda x: x['name'])
                
                # Add controls to players if we have any
                if p1_controls:
                    converted_data['players'].append({
                        'number': 1,
                        'numButtons': int(found_data.get('buttons', 1)),
                        'labels': p1_controls
                    })
                
                if p2_controls:
                    converted_data['players'].append({
                        'number': 2,
                        'numButtons': int(found_data.get('buttons', 1)),
                        'labels': p2_controls
                    })
            
            # Add default controls if needed
            if not converted_data['players']:
                print(f"No controls found, creating default controls for {romname}")
                # If we have no controls at all, create some defaults
                p1_controls = []
                
                # Add basic joystick controls
                for direction in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                    control_name = f'P1_JOYSTICK_{direction}'
                    p1_controls.append({
                        'name': control_name,
                        'value': default_actions[control_name]
                    })
                
                # Add some default buttons
                for button_num in range(1, 7):  # Buttons 1-6
                    control_name = f'P1_BUTTON{button_num}'
                    p1_controls.append({
                        'name': control_name,
                        'value': default_actions.get(control_name, f'Button {button_num}')
                    })
                
                # Add the default player 1 controls
                converted_data['players'].append({
                    'number': 1,
                    'numButtons': int(found_data.get('buttons', 1)) or 6,
                    'labels': p1_controls
                })
            
            # Cache the result
            self.rom_data_cache[romname] = converted_data
            print(f"Successfully created game data for {romname} using ijson")
            
            # Return the converted data
            return converted_data
            
        except Exception as e:
            print(f"Error in ijson parsing for {romname}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fall back to regular method
            print(f"Falling back to regular get_game_data method for {romname}")
            return self.get_game_data(romname)

    def get_game_data(self, romname):
        """Get game data using SQLite database with optimized caching"""
        # Prevent recursion
        if hasattr(self, '_in_get_game_data') and self._in_get_game_data:
            return None
        
        # Set recursion guard
        self._in_get_game_data = True
        
        # Initialize debug counters if not already done
        if not hasattr(self, 'debug_source_counters'):
            self.debug_source_counters = {
                'cache': 0,
                'custom': 0,
                'database': 0,
                'json': 0,
                'not_found': 0
            }
        
        try:
            # Check cache first for fastest response
            if hasattr(self, 'rom_data_cache') and romname in self.rom_data_cache:
                self._in_get_game_data = False
                
                # Only print debug for the first 5 cache hits
                if self.debug_source_counters['cache'] < 5:
                    print(f"Data for {romname} from memory cache")
                    self.debug_source_counters['cache'] += 1
                elif self.debug_source_counters['cache'] == 5:
                    print("Further memory cache lookups will not be logged...")
                    self.debug_source_counters['cache'] += 1
                    
                return self.rom_data_cache[romname]
            
            # Check for custom controls first
            custom_path = os.path.join(self.mame_dir, "custom_controls", f"{romname}.json")
            if os.path.exists(custom_path):
                try:
                    with open(custom_path, 'r', encoding='utf-8') as f:
                        custom_data = json.load(f)
                        custom_data['romname'] = romname
                        custom_data['source'] = 'custom'
                        
                        # Cache the result
                        if not hasattr(self, 'rom_data_cache'):
                            self.rom_data_cache = {}
                        self.rom_data_cache[romname] = custom_data
                        self._in_get_game_data = False
                        
                        # Only print debug for the first 5 custom files
                        if self.debug_source_counters['custom'] < 5:
                            print(f"Data for {romname} from custom controls file")
                            self.debug_source_counters['custom'] += 1
                        elif self.debug_source_counters['custom'] == 5:
                            print("Further custom control lookups will not be logged...")
                            self.debug_source_counters['custom'] += 1
                            
                        return custom_data
                except Exception as e:
                    print(f"Error loading custom controls: {e}")
            
            # Initialize the database path if it's not set yet
            if not hasattr(self, 'db_path') or not self.db_path:
                db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
                if os.path.exists(db_path):
                    self.db_path = db_path
                else:
                    # Database doesn't exist, try to build it
                    self.initialize_database()
            
            # Try getting data from the database if it's available
            if hasattr(self, 'db_path') and self.db_path and os.path.exists(self.db_path):
                try:
                    result = self.get_game_data_from_db(romname)
                    if result:
                        # Cache the result
                        if not hasattr(self, 'rom_data_cache'):
                            self.rom_data_cache = {}
                        self.rom_data_cache[romname] = result
                        self._in_get_game_data = False
                        
                        # Only print debug for the first 5 database hits
                        if self.debug_source_counters['database'] < 5:
                            print(f"Data for {romname} from database")
                            self.debug_source_counters['database'] += 1
                        elif self.debug_source_counters['database'] == 5:
                            print("Further database lookups will not be logged...")
                            self.debug_source_counters['database'] += 1
                            
                        return result
                except Exception as e:
                    print(f"Error getting data from database: {e}")
            
            # Fall back to JSON method if database fails or doesn't exist
            if hasattr(self, 'gamedata_json') and self.gamedata_json:
                # Use the original method as fallback
                result = self.orig_get_game_data(romname)
                
                # Cache if found
                if result:
                    if not hasattr(self, 'rom_data_cache'):
                        self.rom_data_cache = {}
                    self.rom_data_cache[romname] = result
                    
                    # Only print debug for the first 5 JSON lookups
                    if self.debug_source_counters['json'] < 5:
                        print(f"Data for {romname} from JSON fallback")
                        self.debug_source_counters['json'] += 1
                    elif self.debug_source_counters['json'] == 5:
                        print("Further JSON lookups will not be logged...")
                        self.debug_source_counters['json'] += 1
                
                self._in_get_game_data = False
                return result
            
            # Not found by any method
            if self.debug_source_counters['not_found'] < 5:
                print(f"No data found for {romname}")
                self.debug_source_counters['not_found'] += 1
            elif self.debug_source_counters['not_found'] == 5:
                print("Further 'not found' messages will not be logged...")
                self.debug_source_counters['not_found'] += 1
                
            self._in_get_game_data = False
            return None
        except Exception as e:
            print(f"Error in get_game_data: {e}")
            self._in_get_game_data = False
            return None

    def scan_roms_directory(self):
        """Scan the roms directory for available games"""
        roms_dir = os.path.join(self.mame_dir, "roms")
        print(f"\n=== DEBUG: scan_roms_directory ===")
        print(f"Scanning ROMs directory: {roms_dir}")
        print(f"Directory exists: {os.path.exists(roms_dir)}")
        
        if not os.path.exists(roms_dir):
            print(f"ERROR: ROMs directory not found: {roms_dir}")
            return

        self.available_roms = set()  # Reset the set
        rom_count = 0

        try:
            rom_files = os.listdir(roms_dir)
            print(f"Found {len(rom_files)} files in ROMs directory")
            
            for filename in rom_files:
                # Strip common ROM extensions
                base_name = os.path.splitext(filename)[0]
                self.available_roms.add(base_name)
                rom_count += 1
                if rom_count <= 5:  # Print first 5 ROMs as sample
                    print(f"Found ROM: {base_name}")
        except Exception as e:
            print(f"Error scanning ROMs directory: {e}")
        
        print(f"Total ROMs found: {len(self.available_roms)}")
        if len(self.available_roms) > 0:
            print("Sample of available ROMs:", list(self.available_roms)[:5])
        else:
            print("WARNING: No ROMs were found!")

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

    def on_game_select(self, event):
        """Handle game selection and display controls"""
        try:
            # First, close any existing preview windows
            self.close_all_previews()
            
            # Get the selected game name
            index = self.game_list.index(f"@{event.x},{event.y}")
            
            # Get the line number (starting from 1)
            line_num = int(index.split('.')[0])
            
            # Get the text from this line
            line = self.game_list.get(f"{line_num}.0", f"{line_num}.0 lineend")
            
            # Highlight the selected line
            self.highlight_selected_game(line_num)
            
            # IMPROVED PREFIX HANDLING: Strip all leading spaces first
            line = line.strip()
            
            # Then remove specific prefixes
            if line.startswith("*"):
                line = line[1:].strip()
            if line.startswith("+") or line.startswith("-"):
                line = line[1:].strip()
                    
            romname = line.split(" - ")[0].strip()
            self.current_game = romname

            # Get game data including variants
            game_data = self.get_game_data(romname)
            
            # Rest of the method...
            print(f"Game data found: {game_data is not None}")
            
            # ... rest of the method
            
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
        
    def close_all_previews(self):
        """Close all preview windows to prevent accumulation"""
        # Close main preview window
        if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
            try:
                # Clean up canvas items first
                if hasattr(self, 'preview_canvas'):
                    self.preview_canvas.delete("all")
                
                # Destroy window
                self.preview_window.destroy()
                print("Closed main preview window during ROM switch")
            except Exception as e:
                print(f"Error closing main preview: {e}")
        
        # Close exact preview window
        if hasattr(self, 'exact_preview_window') and self.exact_preview_window.winfo_exists():
            try:
                self.exact_preview_window.destroy()
                print("Closed exact preview window during ROM switch")
            except Exception as e:
                print(f"Error closing exact preview: {e}")
        
        # Reset text items
        if hasattr(self, 'text_items'):
            self.text_items = {}
            
        # Reset original positions
        if hasattr(self, 'original_positions'):
            self.original_positions = {}
    
    def create_info_directory(self):
        """Create info directory if it doesn't exist"""
        # Use application_path instead of __file__ for PyInstaller compatibility
        app_path = get_application_path()
        info_dir = os.path.join(app_path, "preview", "settings", "info")
        if not os.path.exists(info_dir):
            os.makedirs(info_dir)
        return info_dir

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

    def save_game_config(self, romname: str):
        """Save config file for a specific game"""
        # Get game data
        game_data = next((game for game in self.controls_data if game['romname'] == romname), None)
        if not game_data:
            return
            
        # Generate config content
        config_content = self.generate_game_config(game_data)
        if not config_content:
            return
            
        # Save to file
        info_dir = self.create_info_directory()
        config_path = os.path.join(info_dir, f"{romname}.conf")
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            print(f"Saved config for {romname}")
        except Exception as e:
            print(f"Error saving config for {romname}: {e}")

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

    def add_alignment_guides(self):
        """Add horizontal and vertical alignment guides to the canvas"""
        # Create guide lines (initially hidden)
        self.h_guide = self.preview_canvas.create_line(0, 0, 0, 0, fill="yellow", width=1, dash=(4, 4), state="hidden")
        self.v_guide = self.preview_canvas.create_line(0, 0, 0, 0, fill="yellow", width=1, dash=(4, 4), state="hidden")
        
        # Create snap points for each text item (invisible - just for snapping)
        self.snap_points = {}
        for control_name, data in self.text_items.items():
            text_x, text_y = data['x'], data['y']
            self.snap_points[control_name] = (text_x, text_y)
        
        # Track which item is being dragged
        self.dragged_item = None
        
        # Update draggable method to use guides
        self.update_draggable_for_alignment()
        
        # Add a button to toggle alignment guides (using the bottom row)
        self.alignment_button = ctk.CTkButton(
            self.button_row2,  # Use bottom row frame
            text="Alignment",
            command=self.toggle_alignment_mode,
            width=90  # Match other buttons
        )
        self.alignment_button.pack(side="left", padx=3)
        
        # Set initial alignment mode
        self.alignment_mode = False
        
        print("Alignment guides added")

    def update_draggable_for_alignment(self):
        """Update the drag handlers to use alignment guides"""
        # Import tkinter for error handling
        import tkinter as tk
        
        # Store original drag motion method
        self.original_drag_motion = self.preview_canvas.tag_bind

        # Unbind existing motion handlers for all text items
        for control_name, data in self.text_items.items():
            try:
                # Check if the text item still exists before trying to unbind
                if 'text' in data and self.preview_canvas.winfo_exists():
                    # Try to get info about the item to check if it exists
                    try:
                        self.preview_canvas.itemcget(data['text'], 'text')  # Test if item exists
                        self.preview_canvas.tag_unbind(data['text'], "<B1-Motion>")
                    except (tk.TclError, Exception):
                        # Item doesn't exist, skip it
                        continue
            except Exception as e:
                print(f"Error unbinding from {control_name}: {e}")
                continue
            
            # Rebind with alignment-aware version
            try:
                if 'text' in data:
                    self.preview_canvas.tag_bind(data['text'], "<B1-Motion>", 
                                        lambda e, name=control_name: self.on_drag_with_alignment(e, name))
                    
                    # Add binding to start drag
                    self.preview_canvas.tag_bind(data['text'], "<ButtonPress-1>", 
                                        lambda e, name=control_name: self.on_drag_start_with_alignment(e, name))
                    
                    # Add binding to end drag
                    self.preview_canvas.tag_bind(data['text'], "<ButtonRelease-1>", 
                                        lambda e, name=control_name: self.on_drag_end_with_alignment(e, name))
            except Exception as e:
                print(f"Error binding new handlers for {control_name}: {e}")
                continue

    def on_drag_start_with_alignment(self, event, control_name):
        """Start dragging with alignment guides"""
        # Store which item is being dragged
        self.dragged_item = control_name
        
        # Store initial position
        self.drag_start_x = self.preview_canvas.canvasx(event.x)
        self.drag_start_y = self.preview_canvas.canvasy(event.y)
        
        # If alignment mode is on, show guides
        if self.alignment_mode:
            # Position guides at current item position
            text_x, text_y = self.text_items[control_name]['x'], self.text_items[control_name]['y']
            
            # Set guide lines to span the canvas
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            self.preview_canvas.coords(self.h_guide, 0, text_y, canvas_width, text_y)
            self.preview_canvas.coords(self.v_guide, text_x, 0, text_x, canvas_height)
            
            # Show guides
            self.preview_canvas.itemconfigure(self.h_guide, state="normal")
            self.preview_canvas.itemconfigure(self.v_guide, state="normal")

    def on_drag_with_alignment(self, event, control_name):
        """Handle dragging with alignment guides"""
        if not control_name == self.dragged_item:
            return
        
        # Calculate movement
        new_x = self.preview_canvas.canvasx(event.x)
        new_y = self.preview_canvas.canvasy(event.y)
        
        dx = new_x - self.drag_start_x
        dy = new_y - self.drag_start_y
        
        # Update start position
        self.drag_start_x = new_x
        self.drag_start_y = new_y
        
        # Get current position
        data = self.text_items[control_name]
        old_x, old_y = data['x'], data['y']
        new_x, new_y = old_x + dx, old_y + dy
        
        # Check for snapping if alignment mode is on
        if self.alignment_mode:
            # Snap threshold in pixels
            threshold = 10
            
            # Check for snapping to other items
            snap_x, snap_y = None, None
            for name, (x, y) in self.snap_points.items():
                if name == control_name:
                    continue
                    
                # Check horizontal alignment
                if abs(new_y - y) < threshold:
                    snap_y = y
                    
                # Check vertical alignment
                if abs(new_x - x) < threshold:
                    snap_x = x
            
            # Apply snapping
            if snap_y is not None:
                new_y = snap_y
                # Update horizontal guide
                canvas_width = self.preview_canvas.winfo_width()
                self.preview_canvas.coords(self.h_guide, 0, snap_y, canvas_width, snap_y)
                
            if snap_x is not None:
                new_x = snap_x
                # Update vertical guide
                canvas_height = self.preview_canvas.winfo_height()
                self.preview_canvas.coords(self.v_guide, snap_x, 0, snap_x, canvas_height)
        
        # Move the text and shadow
        self.preview_canvas.move(data['text'], new_x - old_x, new_y - old_y)
        self.preview_canvas.move(data['shadow'], new_x - old_x, new_y - old_y)
        
        # Update stored coordinates
        data['x'] = new_x
        data['y'] = new_y
        
        # Update snap points
        self.snap_points[control_name] = (new_x, new_y)
        
        # Update guides
        if self.alignment_mode:
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            self.preview_canvas.coords(self.h_guide, 0, new_y, canvas_width, new_y)
            self.preview_canvas.coords(self.v_guide, new_x, 0, new_x, canvas_height)

    def on_drag_end_with_alignment(self, event, control_name):
        """End dragging with alignment guides"""
        if not control_name == self.dragged_item:
            return
            
        # Hide guides
        self.preview_canvas.itemconfigure(self.h_guide, state="hidden")
        self.preview_canvas.itemconfigure(self.v_guide, state="hidden")
        
        # Clear dragged item
        self.dragged_item = None

    def toggle_alignment_mode(self):
        """Toggle alignment mode on/off"""
        self.alignment_mode = not self.alignment_mode
        if self.alignment_mode:
            self.alignment_button.configure(text="Alignment ON")
        else:
            self.alignment_button.configure(text="Alignment OFF")
            # Hide guides
            self.preview_canvas.itemconfigure(self.h_guide, state="hidden")
            self.preview_canvas.itemconfigure(self.v_guide, state="hidden")
    
    # Add these methods to implement the "Show All Buttons" feature

    def add_show_all_buttons_feature(self):
        """Add button and functionality to show all possible controls"""
        # Add button to the button frame (using the bottom row)
        self.show_all_button = ctk.CTkButton(
            self.button_row2,  # Use bottom row
            text="Show All",
            command=self.toggle_show_all_controls,
            width=90  # Match other buttons
        )
        self.show_all_button.pack(side="left", padx=3)
        
        # Initialize flag
        self.showing_all_controls = False
        
        # Store original controls when showing all
        self.original_text_items = None
        
        print("Show All Buttons feature added")

    def toggle_show_all_controls(self):
        """Toggle between showing all possible controls and just the game controls"""
        if not self.showing_all_controls:
            # Switch to showing all controls
            self.show_all_possible_controls()
            self.show_all_button.configure(text="Game Only")
            self.showing_all_controls = True
        else:
            # Switch back to game-specific controls
            self.restore_game_controls()
            self.show_all_button.configure(text="Show All")
            self.showing_all_controls = False
    
    # 1. Fix for show_all_possible_controls()
    def show_all_possible_controls(self):
        """Show all possible XInput controls for positioning"""
        # Store current controls to restore later
        self.original_text_items = self.text_items.copy()
        
        # Clear existing controls
        for button_name, data in self.text_items.items():
            self.preview_canvas.delete(data['text'])
            if data['shadow'] is not None:
                self.preview_canvas.delete(data['shadow'])
        
        # Define all standard XInput controls with placeholder actions
        standard_controls = {
            # Main buttons
            "A": "A Button Action",
            "B": "B Button Action",
            "X": "X Button Action",
            "Y": "Y Button Action",
            
            # Bumpers and triggers
            "LB": "Left Bumper Action",
            "RB": "Right Bumper Action",
            "LT": "Left Trigger Action",
            "RT": "Right Trigger Action",
            
            # Stick buttons
            "LS": "Left Stick Button Action",
            "RS": "Right Stick Button Action",
            
            # D-pad directions
            "UP": "D-Pad Up Action",
            "DOWN": "D-Pad Down Action",
            "LEFT": "D-Pad Left Action",
            "RIGHT": "D-Pad Right Action"
        }
        
        # Create new text items dictionary
        self.text_items = {}
        
        # Get image dimensions for positioning
        image_x = self.image_x
        image_y = self.image_y
        
        # Load saved positions from global positions file
        self.position_manager = PositionManager(self)
        self.position_manager.load_from_file("global")
        print(f"Loaded {len(self.position_manager.positions)} positions from global file")
        
        # Also load any stored joystick positions
        if hasattr(self, 'temp_joystick_positions'):
            for button_name, (x, y) in self.temp_joystick_positions.items():
                if button_name not in self.position_manager.positions:
                    self.position_manager.store(button_name, x, y, is_normalized=True)
                    print(f"Loaded stored joystick position: {button_name} = ({x}, {y})")
        
        # Load text appearance settings
        settings = self.get_text_settings(refresh=True)
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        bold_strength = settings.get("bold_strength", 2)
        y_offset = settings.get('y_offset', -40)
        
        print(f"Using text settings for 'Show All': font={font_family}, size={font_size}, bold={bold_strength}, y_offset={y_offset}")
        
        # Create font with correct size and family
        try:
            import tkinter.font as tkfont
            text_font = tkfont.Font(family=font_family, size=self.apply_font_scaling(font_family, font_size), weight="bold")
        except Exception as e:
            print(f"Error creating font: {e}")
            text_font = (font_family, self.apply_font_scaling(font_family, font_size), "bold")
        
        # Add all XInput controls as text
        control_count = 0
        joystick_visible = "JOYSTICK" in self.visible_control_types
        
        for button_name, action in standard_controls.items():
            # Skip joystick controls if they're hidden
            is_joystick = button_name in ["UP", "DOWN", "LEFT", "RIGHT"]
            if is_joystick and not joystick_visible:
                # Still create and position them but make them hidden
                print(f"Joystick control {button_name} will be created but hidden")
                
            # Apply uppercase if enabled
            use_uppercase = settings.get("use_uppercase", False)
            display_text = f"{button_name}: {action.upper() if use_uppercase else action}"
            
            # Position text - use position manager if available, otherwise use a grid layout
            if button_name in self.position_manager.positions:
                # Get normalized position
                normalized_x, normalized_y = self.position_manager.get_normalized(button_name)
                
                # Apply offset for display
                text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y, y_offset)
                
                print(f"Using saved position for {button_name}: normalized=({normalized_x}, {normalized_y}), display=({text_x}, {text_y})")
            else:
                # Default grid layout - arrange buttons in rows and columns
                grid_cols = 4  # Number of columns in the grid
                grid_row = control_count // grid_cols
                grid_col = control_count % grid_cols
                
                # Calculate position - spread evenly across the screen
                margin_x = 100
                margin_y = 100
                spacing_x = (self.preview_canvas.winfo_width() - 2 * margin_x) / (grid_cols - 1)
                spacing_y = 80  # Vertical spacing between rows
                
                normalized_x = image_x + margin_x + (grid_col * spacing_x)
                normalized_y = image_y + margin_y + (grid_row * spacing_y)
                
                # Apply offset for display
                text_x, text_y = normalized_x, normalized_y + y_offset
                
                # Store in position manager
                self.position_manager.store(button_name, normalized_x, normalized_y, is_normalized=True)
                print(f"Using default position for {button_name}: ({text_x}, {text_y})")
            
            # Create text with proper shadow effect
            text_item, shadow_item = self.create_text_with_shadow(
                self.preview_canvas, 
                text_x, 
                text_y, 
                display_text, 
                text_font
            )
            
            # Set joystick controls visibility
            if is_joystick and not joystick_visible:
                self.preview_canvas.itemconfigure(text_item, state="hidden")
                if shadow_item is not None:
                    self.preview_canvas.itemconfigure(shadow_item, state="hidden")
            
            # Store the text items
            self.text_items[button_name] = {
                'text': text_item,
                'shadow': shadow_item,
                'action': action,
                'display_text': display_text,
                'x': text_x, 
                'y': text_y,
                'base_y': normalized_y,
                'is_joystick': is_joystick
            }
            
            # Make the text draggable
            self.make_draggable(self.preview_canvas, text_item, shadow_item, button_name)
            control_count += 1
        
        # Update snap points for alignment
        if hasattr(self, 'snap_points'):
            self.snap_points = {}
            for button_name, data in self.text_items.items():
                self.snap_points[button_name] = (data['x'], data['y'])
        
        # Apply alignment if available
        if hasattr(self, 'update_draggable_for_alignment'):
            self.update_draggable_for_alignment()
        
        print(f"Showing all {len(self.text_items)} XInput controls with current text settings")

    # 2. Fix for restore_game_controls()
    def restore_game_controls(self):
        """Restore the game-specific controls after showing all possible controls"""
        if not self.original_text_items:
            print("No original controls to restore")
            return
            
        # Remove all current controls
        for button_name, data in self.text_items.items():
            self.preview_canvas.delete(data['text'])
            if data['shadow'] is not None:
                self.preview_canvas.delete(data['shadow'])
        
        # Get game data again
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            print(f"No game data available for {self.current_game}")
            return
        
        # Get custom controls if they exist
        cfg_controls = {}
        if self.current_game in self.custom_configs:
            cfg_controls = self.parse_cfg_controls(self.custom_configs[self.current_game])
            # Convert mappings if XInput is enabled
            if self.use_xinput:
                cfg_controls = {
                    control: self.convert_mapping(mapping, True)
                    for control, mapping in cfg_controls.items()
                }
        
        # Load text appearance settings
        settings = self.get_text_settings()
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        bold_strength = settings.get("bold_strength", 2)
        y_offset = settings.get('y_offset', -40)
        
        # Create font with correct size and family
        try:
            import tkinter.font as tkfont
            text_font = tkfont.Font(family=font_family, size=self.apply_font_scaling(font_family, font_size), weight="bold")
        except Exception as e:
            print(f"Error creating font: {e}")
            text_font = (font_family, self.apply_font_scaling(font_family, font_size), "bold")
        
        # Reset text items dictionary
        self.text_items = {}
        
        # Process all player controls
        control_count = 0
        for player in game_data.get('players', []):
            if player['number'] != 1:
                continue
                
            for label in player.get('labels', []):
                control_name = label['name']
                action = label['value']
                
                # Only include P1 controls
                if not control_name.startswith('P1_'):
                    continue
                
                # Get custom mapping if available
                custom_mapping = None
                if control_name in cfg_controls:
                    custom_mapping = cfg_controls[control_name]
                
                # Get XInput button for this control
                xinput_button = self.get_xinput_button_from_control(control_name, custom_mapping)
                
                # Skip controls that don't map to XInput
                if not xinput_button:
                    continue
                
                # Get display text for this control
                display_text = self.get_display_text(action, settings, control_name, custom_mapping)
                
                # Skip if no display text
                if not display_text:
                    continue
                
                # Get position from position manager
                normalized_x, normalized_y = self.position_manager.get_normalized(xinput_button)
                text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y, y_offset)
                
                # Create text with shadow
                text_item, shadow_item = self.create_text_with_shadow(
                    self.preview_canvas, 
                    text_x, 
                    text_y, 
                    display_text, 
                    text_font
                )
                
                # Check visibility based on control type
                is_visible = self.is_control_visible(control_name)
                
                # Set visibility state
                if not is_visible:
                    self.preview_canvas.itemconfigure(text_item, state="hidden")
                    if shadow_item is not None:
                        self.preview_canvas.itemconfigure(shadow_item, state="hidden")
                
                # Store the text items
                self.text_items[xinput_button] = {
                    'text': text_item,
                    'shadow': shadow_item,
                    'action': action,
                    'display_text': display_text,
                    'control_name': control_name,
                    'x': text_x, 
                    'y': text_y,
                    'base_y': normalized_y,
                    'custom_mapping': custom_mapping
                }
                
                # Make the text draggable
                self.make_draggable(self.preview_canvas, text_item, shadow_item, xinput_button)
                control_count += 1
        
        # Update snap points for alignment
        if hasattr(self, 'snap_points'):
            self.snap_points = {}
            for button_name, data in self.text_items.items():
                self.snap_points[button_name] = (data['x'], data['y'])
        
        # Re-apply the alignment drag handlers
        if hasattr(self, 'update_draggable_for_alignment'):
            self.update_draggable_for_alignment()
        
        # Clear the original reference
        self.original_text_items = None
        
        print(f"Restored {len(self.text_items)} game-specific controls using current text settings")

    def get_display_text(self, action, settings=None, control_name=None, custom_mapping=None):
        """
        Generate display text for controls based on settings
        """
        if settings is None:
            settings = self.get_text_settings()
                
        # Apply uppercase if enabled
        use_uppercase = settings.get("use_uppercase", False)
        action_text = action.upper() if use_uppercase else action
        
        # Check if we should show button names
        show_button_names = getattr(self, 'show_button_names', True)
        
        # If we're not showing button names, just return the action text
        if not show_button_names:
            return action_text
        
        # Initialize button text
        button_text = ""
        
        # Check for custom mapping first
        if custom_mapping and custom_mapping != "Default" and custom_mapping != "Not mapped":
            # Only process XInput and joystick mappings
            if "XINPUT" in custom_mapping:
                # XInput buttons
                if "_A" in custom_mapping:
                    button_text = "A"
                elif "_B" in custom_mapping:
                    button_text = "B"
                elif "_X" in custom_mapping:
                    button_text = "X"
                elif "_Y" in custom_mapping:
                    button_text = "Y"
                # Bumpers and triggers
                elif "SHOULDER_L" in custom_mapping:
                    button_text = "LB"
                elif "SHOULDER_R" in custom_mapping:
                    button_text = "RB"
                elif "TRIGGER_L" in custom_mapping:
                    button_text = "LT"
                elif "TRIGGER_R" in custom_mapping:
                    button_text = "RT"
                # Stick buttons
                elif "THUMB_L" in custom_mapping:
                    button_text = "LS"
                elif "THUMB_R" in custom_mapping:
                    button_text = "RS"
                # D-pad directions
                elif "DPAD_UP" in custom_mapping:
                    button_text = "UP"
                elif "DPAD_DOWN" in custom_mapping:
                    button_text = "DOWN"
                elif "DPAD_LEFT" in custom_mapping:
                    button_text = "LEFT"
                elif "DPAD_RIGHT" in custom_mapping:
                    button_text = "RIGHT"
            # Handle joystick directions specifically
            elif "JOYCODE" in custom_mapping and ("HAT" in custom_mapping or "AXIS" in custom_mapping):
                if "UP" in custom_mapping or "YAXIS_UP" in custom_mapping:
                    button_text = "UP"
                elif "DOWN" in custom_mapping or "YAXIS_DOWN" in custom_mapping:
                    button_text = "DOWN"
                elif "LEFT" in custom_mapping or "XAXIS_LEFT" in custom_mapping:
                    button_text = "LEFT"
                elif "RIGHT" in custom_mapping or "XAXIS_RIGHT" in custom_mapping:
                    button_text = "RIGHT"
        else:
            # For default mappings, only show XInput buttons and joystick directions
            if control_name:
                if "JOYSTICK_UP" in control_name:
                    button_text = "UP"
                elif "JOYSTICK_DOWN" in control_name:
                    button_text = "DOWN"
                elif "JOYSTICK_LEFT" in control_name:
                    button_text = "LEFT"
                elif "JOYSTICK_RIGHT" in control_name:
                    button_text = "RIGHT"
                elif "BUTTON" in control_name:
                    # Extract button number and map to XInput
                    button_match = re.search(r'BUTTON(\d+)', control_name)
                    if button_match:
                        button_num = button_match.group(1)
                        # Map to XInput buttons
                        xinput_buttons = {
                            "1": "A",
                            "2": "B",
                            "3": "X",
                            "4": "Y",
                            "5": "LB",
                            "6": "RB",
                            "7": "LT",
                            "8": "RT",
                            "9": "LS",
                            "10": "RS"
                        }
                        button_text = xinput_buttons.get(button_num, "")
        
        # Only create compound display text if we have a recognized button and we're showing button names
        if button_text:
            display_text = f"{button_text}: {action_text}"
        else:
            # If no button mapping available, just show action text
            display_text = action_text
        
        return display_text
    
    def get_xinput_button_from_control(self, control_name, custom_mapping=None):
        """
        Get the XInput button name that corresponds to this control
        Used for mapping controls to positions based on XInput buttons
        """
        # If there's a custom mapping, use that to determine the XInput button
        if custom_mapping and custom_mapping != "Default" and custom_mapping != "Not mapped":
            if "XINPUT" in custom_mapping:
                if "_A" in custom_mapping:
                    return "A"
                elif "_B" in custom_mapping:
                    return "B"
                elif "_X" in custom_mapping:
                    return "X"
                elif "_Y" in custom_mapping:
                    return "Y"
                elif "SHOULDER_L" in custom_mapping:
                    return "LB"
                elif "SHOULDER_R" in custom_mapping:
                    return "RB"
                elif "TRIGGER_L" in custom_mapping:
                    return "LT"
                elif "TRIGGER_R" in custom_mapping:
                    return "RT"
                elif "THUMB_L" in custom_mapping:
                    return "LS"
                elif "THUMB_R" in custom_mapping:
                    return "RS"
                elif "DPAD_UP" in custom_mapping:
                    return "UP"
                elif "DPAD_DOWN" in custom_mapping:
                    return "DOWN"
                elif "DPAD_LEFT" in custom_mapping:
                    return "LEFT"
                elif "DPAD_RIGHT" in custom_mapping:
                    return "RIGHT"
            # Handle joystick directions
            elif "JOYCODE" in custom_mapping:
                if "HATUP" in custom_mapping or "YAXIS_UP" in custom_mapping:
                    return "UP"
                elif "HATDOWN" in custom_mapping or "YAXIS_DOWN" in custom_mapping:
                    return "DOWN"
                elif "HATLEFT" in custom_mapping or "XAXIS_LEFT" in custom_mapping:
                    return "LEFT"
                elif "HATRIGHT" in custom_mapping or "XAXIS_RIGHT" in custom_mapping:
                    return "RIGHT"
                
        # If no custom mapping, map based on the control name
        if control_name:
            if "JOYSTICK_UP" in control_name:
                return "UP"
            elif "JOYSTICK_DOWN" in control_name:
                return "DOWN"
            elif "JOYSTICK_LEFT" in control_name:
                return "LEFT"
            elif "JOYSTICK_RIGHT" in control_name:
                return "RIGHT"
            elif "BUTTON" in control_name:
                # Extract button number and map to XInput
                import re
                button_match = re.search(r'BUTTON(\d+)', control_name)
                if button_match:
                    button_num = button_match.group(1)
                    # Map to XInput buttons
                    xinput_buttons = {
                        "1": "A",
                        "2": "B",
                        "3": "X",
                        "4": "Y",
                        "5": "LB",
                        "6": "RB",
                        "7": "LT",
                        "8": "RT",
                        "9": "LS",
                        "10": "RS"
                    }
                    return xinput_buttons.get(button_num, "")
        
        # If nothing matches
        return ""
    
    def save_all_controls_positions(self):
        """Save positions for all XInput controls to the global positions file"""
        try:
            # Use the position manager to store all current positions properly
            if not hasattr(self, 'position_manager'):
                self.position_manager = PositionManager(self)
            
            # Update position manager from current text items
            for button_name, data in self.text_items.items():
                if 'x' not in data or 'y' not in data:
                    print(f"  Warning: Missing x/y for {button_name}")
                    continue
                    
                x = data['x']
                # Use base_y (normalized y) if available, otherwise calculate it
                if 'base_y' in data:
                    normalized_y = data['base_y']
                else:
                    # Need to subtract y_offset to get normalized position
                    settings = self.get_text_settings()
                    y_offset = settings.get('y_offset', -40)
                    normalized_y = data['y'] - y_offset
                    
                # Store in position manager with normalized coordinates
                self.position_manager.store(button_name, x, normalized_y, is_normalized=True)
                print(f"Stored position for {button_name}: ({x}, {normalized_y})")
                
            # Now save all positions to global file
            result = self.position_manager.save_to_file(is_global=True)
            
            if result:
                count = len(self.position_manager.positions)
                print(f"Saved {count} positions to global positions file")
                messagebox.showinfo("Success", f"All controls positions saved to global file ({count} items)")
                return True
            else:
                print("Failed to save positions")
                messagebox.showerror("Error", "Could not save positions")
                return False
                
        except Exception as e:
            print(f"Error saving all controls positions: {e}")
            messagebox.showerror("Error", f"Could not save positions: {e}")
            return False

    def check_rom_relationship(self, rom_name):
        """Check if ROM is a parent or clone and print relationship info"""
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if it's a parent with clones
            cursor.execute('SELECT clone FROM clones WHERE parent = ?', (rom_name,))
            clones = cursor.fetchall()
            
            # Check if it's a clone
            cursor.execute('SELECT parent FROM clones WHERE clone = ?', (rom_name,))
            parent_row = cursor.fetchone()
            
            # Print results
            print(f"\nROM RELATIONSHIP CHECK FOR: {rom_name}")
            if clones:
                clone_list = [c[0] for c in clones]
                print(f"This is a PARENT ROM with {len(clones)} clones: {', '.join(clone_list)}")
            
            if parent_row:
                parent = parent_row[0]
                print(f"This is a CLONE ROM. Parent is: {parent}")
                
            if not clones and not parent_row:
                print(f"This ROM has no parent-clone relationships")
                
            conn.close()
            return parent_row[0] if parent_row else None
        except Exception as e:
            print(f"Error checking ROM relationships: {e}")
            return None
    
    def show_preview_standalone(self, rom_name, auto_close=False, force_logo=False, hide_joystick=False):
        """Show the preview for a specific ROM without running the main app - with performance optimizations"""
        import os
        import time  # Add this import
        import json
        import sqlite3
        import sys
        import threading
        
        print(f"Starting standalone preview for ROM: {rom_name}")
        
        # Find the MAME directory (already in __init__)
        if not hasattr(self, 'mame_dir') or not self.mame_dir:
            self.mame_dir = self.find_mame_directory()
            if not self.mame_dir:
                print("Error: MAME directory not found!")
                return
        
        print(f"Using MAME directory: {self.mame_dir}")
        
        # Save the requested screen number before loading settings
        requested_screen = None
        for i, arg in enumerate(sys.argv):
            if arg == '--screen' and i+1 < len(sys.argv):
                try:
                    requested_screen = int(sys.argv[i+1])
                    print(f"Found screen argument: {requested_screen}")
                except ValueError:
                    pass
        
        # Load settings
        self.load_settings()
        self.load_bezel_settings()
        self.load_layer_settings()
        
        # Override with the requested screen if specified on command-line
        if requested_screen is not None:
            self.preferred_preview_screen = requested_screen
            print(f"Using screen {requested_screen} from command line")
        
        # Check for bezel-on-top flag
        if '--bezel-on-top' in sys.argv:
            self.layer_order = {
                'background': 1,  # Background on bottom
                'bezel': 2,       # Bezel above background
                'logo': 3,
                'text': 4
            }
            print("Forcing bezel above background")
        
        # Handle hide-joystick flag
        if hide_joystick or '--hide-joystick' in sys.argv:
            if 'JOYSTICK' in self.visible_control_types:
                self.visible_control_types.remove('JOYSTICK')
                print("Hiding joystick controls")
        
        # Handle hide-buttons flag
        if '--hide-buttons' in sys.argv:
            self.hide_preview_buttons = True
            print("Hiding control buttons in preview")
        
        # Force logo visibility if requested
        if force_logo:
            self.logo_visible = True  
            self.save_logo_settings()
            print("Forced logo visibility enabled")
        
        # Ensure preview folder exists
        if hasattr(self, 'ensure_preview_folder_improved'):
            preview_dir = self.ensure_preview_folder_improved()
        else:
            preview_dir = os.path.join(self.mame_dir, "preview")
            if not os.path.exists(preview_dir):
                os.makedirs(preview_dir)
        
        # Force database initialization and wait for it to complete before proceeding
        print("Forcing database initialization for maximum performance")
        db_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.db")
        if not os.path.exists(db_path) or self.is_database_update_needed():
            print("Building database...")
            success = self.build_gamedata_db()
            if success:
                print("Database built successfully")
            else:
                print("Database build failed, will use slower methods")
        else:
            self.db_path = db_path
            print(f"Using existing database: {db_path}")
        
        # Don't create a persistent connection as it can't be shared across threads
        # Instead, modify the optimized method to create connections as needed

        # Patch get_game_data to prioritize database access in preview-only mode
        if not hasattr(self, 'original_get_game_data'):
            self.original_get_game_data = self.get_game_data
            
            def optimized_get_game_data(romname):
                # Check cache first
                if hasattr(self, 'rom_data_cache') and romname in self.rom_data_cache:
                    return self.rom_data_cache[romname]
                    
                # Try database first - direct access, bypass standard function
                if hasattr(self, 'db_path') and self.db_path and os.path.exists(self.db_path):
                    try:
                        # Create a new connection each time (required for thread safety)
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        
                        # First try direct lookup
                        cursor.execute('SELECT data FROM games WHERE romname = ?', (romname,))
                        row = cursor.fetchone()
                        
                        if row:
                            # Game found directly
                            game_data = json.loads(row[0])
                            result = self.convert_db_game_data(romname, game_data)
                            
                            # Cache the result
                            if not hasattr(self, 'rom_data_cache'):
                                self.rom_data_cache = {}
                            self.rom_data_cache[romname] = result
                            
                            # Clean up connection
                            conn.close()
                            
                            print(f"Got data for {romname} from database (fast path)")
                            return result
                        
                        # If not found directly, check if it's a clone
                        cursor.execute('SELECT parent FROM clones WHERE clone = ?', (romname,))
                        clone_row = cursor.fetchone()
                        
                        if clone_row:
                            # It's a clone, get the parent data
                            parent = clone_row[0]
                            cursor.execute('SELECT data FROM games WHERE romname = ?', (parent,))
                            parent_row = cursor.fetchone()
                            
                            if parent_row:
                                # Use parent data but update clone-specific fields
                                parent_data = json.loads(parent_row[0])
                                result = self.convert_db_game_data(romname, parent_data)
                                result['gamename'] = f"{romname} (Clone of {parent})"
                                
                                # Cache the result
                                if not hasattr(self, 'rom_data_cache'):
                                    self.rom_data_cache = {}
                                self.rom_data_cache[romname] = result
                                
                                # Clean up connection
                                conn.close()
                                
                                print(f"Got data for {romname} from parent {parent} in database (fast path)")
                                return result
                        
                        # Clean up connection if we get here without finding data
                        conn.close()
                        
                    except Exception as e:
                        print(f"Optimized database access failed: {e}, falling back to original method")
                        try:
                            if 'conn' in locals() and conn:
                                conn.close()
                        except:
                            pass
                
                # Fall back to original method
                return self.original_get_game_data(romname)
            
            # Replace the method
            self.get_game_data = optimized_get_game_data
            print("Installed optimized game data retrieval method")
        
        # Function to preload common controls to warm up the cache
        def preload_common_controls():
            """Preload the most commonly used controls to warm up the cache"""
            # Skip if the database isn't available
            if not hasattr(self, 'db_path') or not os.path.exists(self.db_path):
                return
                
            # List of common arcade games to preload
            common_roms = ["pacman", "mspacman", "galaga", "dkong", "sf2", "mk", "1942"]
            
            print("Preloading common game controls...")
            for rom in common_roms:
                if rom != rom_name:  # Don't duplicate the current ROM
                    try:
                        self.get_game_data(rom)
                    except Exception as e:
                        print(f"Error preloading {rom}: {e}")
            print("Preloading complete")
        
        # Start preloading in a background thread to avoid delaying the UI
        preload_thread = threading.Thread(target=preload_common_controls)
        preload_thread.daemon = True
        preload_thread.start()
        
        # Set the current game
        self.current_game = rom_name
        
        # Get game data with optimized method
        print(f"Getting game data for ROM: {rom_name}")
        start_time = time.time()
        game_data = self.get_game_data(rom_name)
        elapsed = time.time() - start_time
        print(f"Game data retrieved in {elapsed:.4f} seconds")
        
        # Rest of the method follows...
        
        if game_data:
            print(f"Found game data for: {rom_name}")
        else:
            # Try parent-clone relationship
            try:
                # Connect to database
                conn = self.db_conn if hasattr(self, 'db_conn') else sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 1. Check if it's a clone, and if so, try the parent
                cursor.execute('SELECT parent FROM clones WHERE clone = ?', (rom_name,))
                parent_row = cursor.fetchone()
                
                if parent_row:
                    parent = parent_row[0]
                    print(f"ROM {rom_name} is a clone of {parent}, trying parent")
                    game_data = self.get_game_data(parent)
                    if game_data:
                        print(f"Using data from parent ROM: {parent}")
                        self.current_game = parent
                
                # 2. If not found, check if it's a parent with clones
                if not game_data:
                    cursor.execute('SELECT clone FROM clones WHERE parent = ?', (rom_name,))
                    clones = cursor.fetchall()
                    
                    if clones:
                        print(f"ROM {rom_name} is a parent with clones, trying each clone")
                        for clone_row in clones:
                            clone = clone_row[0]
                            clone_data = self.get_game_data(clone)
                            if clone_data:
                                print(f"Using data from clone ROM: {clone}")
                                game_data = clone_data
                                self.current_game = clone
                                break
            except Exception as e:
                print(f"Error checking ROM relationships: {e}")
        
        # If still no data, try special case handling
        if not game_data:
            # Special handling for known problematic ROMs
            if rom_name.lower() == "xmen":
                alt_rom = "xmenu"
                print(f"Special case: Trying alternative name: {alt_rom}")
                game_data = self.get_game_data(alt_rom)
                if game_data:
                    self.current_game = alt_rom
            elif rom_name.lower() == "xmenu":
                alt_rom = "xmen"
                print(f"Special case: Trying alternative name: {alt_rom}")
                game_data = self.get_game_data(alt_rom)
                if game_data:
                    self.current_game = alt_rom
        
        # If still no data, create a default
        if not game_data:
            print(f"No game data found for {rom_name}, creating default data")
            game_data = {
                'romname': rom_name,
                'gamename': rom_name.upper(),
                'numPlayers': 1,
                'alternating': False,
                'players': [
                    {
                        'number': 1,
                        'numButtons': 6,
                        'labels': [
                            {'name': 'P1_BUTTON1', 'value': 'A Button'},
                            {'name': 'P1_BUTTON2', 'value': 'B Button'},
                            {'name': 'P1_BUTTON3', 'value': 'X Button'},
                            {'name': 'P1_BUTTON4', 'value': 'Y Button'},
                            {'name': 'P1_BUTTON5', 'value': 'LB Button'},
                            {'name': 'P1_BUTTON6', 'value': 'RB Button'},
                            {'name': 'P1_JOYSTICK_UP', 'value': 'Up'},
                            {'name': 'P1_JOYSTICK_DOWN', 'value': 'Down'},
                            {'name': 'P1_JOYSTICK_LEFT', 'value': 'Left'},
                            {'name': 'P1_JOYSTICK_RIGHT', 'value': 'Right'}
                        ]
                    }
                ]
            }
            
            # Cache this for future use
            if not hasattr(self, 'rom_data_cache'):
                self.rom_data_cache = {}
            self.rom_data_cache[rom_name] = game_data
        
        print(f"Successfully loaded game data for {rom_name}")
        print(f"Using screen {self.preferred_preview_screen} for preview")
        
        # Create a flag file to indicate the preview is active
        try:
            import time
            with open(os.path.join(self.mame_dir, "preview_active.txt"), "w") as f:
                f.write(f"Preview active for: {rom_name}\n")
                f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            print(f"Error creating activity file: {e}")
        
        # Start MAME process monitoring only if auto_close is enabled
        if auto_close:
            print("Auto-close enabled - preview will close when MAME exits")
            self.monitor_mame_process(check_interval=0.5)  # Faster interval for quicker response
        else:
            print("Auto-close disabled - preview will stay open until manually closed")
        
        # Warmup the canvas before showing to improve rendering speed
        def warmup_ui_components():
            """Create UI components in memory before showing to reduce lag"""
            try:
                import tkinter as tk
                # Create temporary canvas to load resources
                temp_root = tk.Tk()
                temp_root.withdraw()
                temp_canvas = tk.Canvas(temp_root, width=100, height=100)
                # Create some sample items to warm up the canvas
                temp_canvas.create_rectangle(10, 10, 90, 90, fill="black")
                temp_canvas.create_text(50, 50, text="Warmup", fill="white")
                temp_root.update()
                temp_root.destroy()
                print("UI components warmed up")
            except Exception as e:
                print(f"Warmup error (non-critical): {e}")
        
        # Run UI warmup in a background thread
        import threading
        warmup_thread = threading.Thread(target=warmup_ui_components)
        warmup_thread.daemon = True
        warmup_thread.start()
        
        # Show the preview window
        try:
            # Use a timer to measure preview window creation time
            start_time = time.time()
            self.show_preview()
            elapsed = time.time() - start_time
            print(f"Preview window displayed in {elapsed:.4f} seconds")
            
            # Force the window to take focus
            if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
                self.preview_window.attributes('-topmost', True)
                self.preview_window.after(100, lambda: self.force_window_focus())
                
                # Ensure window stays open at least a minimum time
                min_display_time = 10000  # 10 seconds minimum display time
                self.preview_window.after(min_display_time, lambda: print("Minimum display time reached"))
                
            # Start controller input polling
            self.start_xinput_polling()
            
        except Exception as e:
            print(f"Error showing preview: {str(e)}")
            import traceback
            traceback.print_exc()
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to show preview: {str(e)}")
            return
        
        # Clean up database connection when the application closes
        def cleanup_db_connection():
            if hasattr(self, 'db_conn'):
                try:
                    self.db_conn.close()
                    print("Database connection closed")
                except Exception as e:
                    print(f"Error closing database connection: {e}")
        
        # Register cleanup handler for window close
        if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
            self.preview_window.after(100, lambda: self.preview_window.protocol("WM_DELETE_WINDOW", 
                                                                        lambda: [cleanup_db_connection(), self.close_preview()]))
        
        # Start mainloop for just this window
        try:
            self.mainloop()
        except Exception as e:
            print(f"Error in mainloop: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Make sure to clean up database connection
            cleanup_db_connection()

    def start_xinput_polling(self):
        """Start polling for controller input with improved detection"""
        try:
            # Try to import inputs module
            from inputs import devices, get_gamepad
            
            # Check if gamepads are available
            gamepads = [device for device in devices.gamepads]
            if not gamepads:
                print("No gamepads detected, controller support disabled")
                return False
                
            print(f"Found gamepad: {gamepads[0].name}, enabling controller support")
            
            # Flag to prevent multiple polling loops
            self.xinput_polling_active = True
            
            # Track last detected button press time to prevent multiple triggers
            self.last_button_press_time = 0
            
            # Create a dedicated thread for controller polling
            import threading
            import time
            import queue
            
            # Create a queue for button events
            self.controller_event_queue = queue.Queue()
            
            # Thread function for continuous controller polling
            def controller_polling_thread():
                try:
                    while self.xinput_polling_active:
                        try:
                            # Get events from controller
                            events = get_gamepad()
                            
                            # Look for button presses
                            for event in events:
                                if event.ev_type == "Key" and event.state == 1:
                                    # Put button press event in queue
                                    self.controller_event_queue.put(event.code)
                                    
                        except Exception as e:
                            # Ignore expected errors
                            if "No more events to read" not in str(e):
                                print(f"Controller polling error: {e}")
                            
                        # Short sleep to avoid consuming too much CPU
                        time.sleep(0.01)
                except Exception as e:
                    print(f"Controller thread error: {e}")
                
                print("Controller polling thread ended")
            
            # Start the polling thread
            self.controller_thread = threading.Thread(target=controller_polling_thread)
            self.controller_thread.daemon = True
            self.controller_thread.start()
            
            # Function to check the event queue from the main thread
            def check_controller_queue():
                # Skip if window is closed or polling inactive
                if not hasattr(self, 'preview_window') or not self.preview_window.winfo_exists() or not self.xinput_polling_active:
                    return
                
                # Process up to 5 events at a time
                for _ in range(5):
                    if self.controller_event_queue.empty():
                        break
                    
                    try:
                        # Get button code from queue
                        button_code = self.controller_event_queue.get_nowait()
                        
                        # Check debounce time (300ms)
                        current_time = time.time()
                        if current_time - self.last_button_press_time > 0.3:
                            print(f"Controller button pressed: {button_code}")
                            self.last_button_press_time = current_time
                            
                            # Close the preview
                            self.close_preview()
                            return
                    except queue.Empty:
                        break
                    except Exception as e:
                        print(f"Error processing controller event: {e}")
                
                # Schedule next check if window still exists
                if hasattr(self, 'preview_window') and self.preview_window.winfo_exists() and self.xinput_polling_active:
                    self.preview_window.after(33, check_controller_queue)  # ~30Hz checking
            
            # Start the event queue checker
            self.preview_window.after(100, check_controller_queue)
            print("Started improved controller support")
            return True
            
        except ImportError:
            print("Inputs package not available, controller support disabled")
            return False
        except Exception as e:
            print(f"Error setting up controller input: {e}")
            return False
    
    def close_preview(self):
        """Close the preview window properly and clean up resources"""
        print("Close preview called")
        
        # Stop controller polling
        self.xinput_polling_active = False
        
        # Close the main preview window if it exists
        if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
            try:
                # Clean up any canvas references first
                if hasattr(self, 'preview_canvas'):
                    # Clear stored item references to avoid memory leaks
                    self.preview_canvas.delete("all")
                    
                # Clear text item references
                if hasattr(self, 'text_items'):
                    self.text_items = {}
                    
                # Destroy the window
                self.preview_window.destroy()
                print("Main preview window closed")
            except Exception as e:
                print(f"Error closing main preview window: {e}")
        
        # Also close any exact preview windows
        if hasattr(self, 'exact_preview_window') and self.exact_preview_window.winfo_exists():
            try:
                self.exact_preview_window.destroy()
                print("Exact preview window closed")
            except Exception as e:
                print(f"Error closing exact preview window: {e}")
        
        # If we're in standalone mode, exit the application
        if not hasattr(self, 'game_list') or not self.game_list.winfo_exists():
            print("In standalone mode, exiting application")
            self.after(100, self.quit_application)
    
    def force_window_focus(self):
        """Force the preview window to take focus"""
        try:
            if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
                # Platform-specific focus approaches
                import platform
                system = platform.system()
                
                if system == "Windows":
                    # Windows-specific approach
                    self.preview_window.focus_force()  # Standard Tkinter approach
                    
                    # Additional Windows-specific focus method
                    try:
                        import win32gui
                        import win32con
                        hwnd = int(self.preview_window.winfo_id())
                        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                        win32gui.SetForegroundWindow(hwnd)
                    except ImportError:
                        # Fall back to standard methods if win32gui not available
                        self.preview_window.lift()
                        self.preview_window.focus_set()
                        self.preview_window.grab_set()
                else:
                    # Standard Tkinter approaches for other systems
                    self.preview_window.lift()
                    self.preview_window.focus_force()
                    self.preview_window.focus_set()
                    self.preview_window.grab_set()
                    
                print("Forced focus on preview window")
        except Exception as e:
            print(f"Error forcing window focus: {e}")

    def monitor_mame_process(self, check_interval=2.0):
        """Monitor MAME process and close preview when MAME closes"""
        import threading
        import time
        import subprocess
        import sys
        import os
        
        print("Starting MAME process monitor")
        
        def check_mame():
            mame_running = True
            check_count = 0
            last_state = True
            
            while mame_running:
                time.sleep(check_interval)
                check_count += 1
                
                # Skip checking if the preview window is gone
                if not hasattr(self, 'preview_window') or not self.preview_window.winfo_exists():
                    print("Preview window closed, stopping monitor")
                    return
                
                # Check if any MAME process is running
                try:
                    if sys.platform == 'win32':
                        output = subprocess.check_output('tasklist /FI "IMAGENAME eq mame*"', shell=True)
                        mame_detected = b'mame' in output.lower()
                    else:
                        output = subprocess.check_output(['ps', 'aux'])
                        mame_detected = b'mame' in output
                    
                    # Only log when state changes
                    if mame_detected != last_state:
                        print(f"MAME running: {mame_detected}")
                        last_state = mame_detected
                    
                    mame_running = mame_detected
                except Exception as e:
                    print(f"Error checking MAME: {e}")
                    continue
            
            # MAME is no longer running - close preview
            print("MAME closed, closing preview")
            if hasattr(self, 'preview_window') and self.preview_window.winfo_exists():
                # Use after() to ensure this runs in the main thread
                self.preview_window.after(100, self.close_preview)
        
        # Start monitoring in a daemon thread
        monitor_thread = threading.Thread(target=check_mame, daemon=True)
        monitor_thread.start()
        print(f"Monitor thread started with check interval {check_interval}s")

    def quit_application(self):
        """Exit the application completely"""
        print("Quitting application")
        try:
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"Error during quit: {e}")
        finally:
            # Force exit
            import os
            print("Forcing exit")
            os._exit(0)
    
    # Update save_current_preview method to respect show_rom_info flag
    # Let's completely rewrite the save_current_preview method to ensure proper layering:
    def save_current_preview(self):
        """Save the current preview state as an image using settings"""
        import os
        from tkinter import messagebox
        from PIL import Image, ImageDraw, ImageFont, ImageChops
        import traceback
        
        if not hasattr(self, 'current_game') or not self.current_game:
            messagebox.showerror("Error", "No game is currently selected")
            return
                
        # Ensure preview directory exists
        preview_dir = self.ensure_preview_folder_improved()
        output_path = os.path.join(preview_dir, f"{self.current_game}.png")
        
        # Ask for confirmation if file exists
        if os.path.exists(output_path):
            if not messagebox.askyesno("Confirmation", 
                                    f"Image already exists for {self.current_game}.\nDo you want to replace it?"):
                return
        
        try:
            # Get all settings from central settings function
            settings = self.get_text_settings()
            print(f"Using text settings for saved image: {settings}")
            
            # Get fonts with consistent handling
            font, title_font = self.get_fonts_from_settings(settings)
            
            # Create separate layer images for proper compositing
            target_width, target_height = 1920, 1080  # Standard HD size
            
            # 1. Create RGBA base images for each layer (transparent)
            background_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            bezel_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            text_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            logo_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            
            # Create a draw object for the text layer
            text_draw = ImageDraw.Draw(text_layer)
            
            # Get y-offset from settings to ensure consistency
            settings = self.get_text_settings()
            y_offset = settings.get("y_offset", -40)

            # 2. Add background image
            background_path = None
            for ext in ['.png', '.jpg', '.jpeg']:
                # First check for ROM-specific background
                test_path = os.path.join(preview_dir, f"{self.current_game}{ext}")
                if os.path.exists(test_path):
                    background_path = test_path
                    break
                    
                # Then check for default background
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    background_path = test_path
                    break
                    
            if background_path:
                try:
                    bg_img = Image.open(background_path)
                    bg_img = bg_img.resize((target_width, target_height), Image.LANCZOS)
                    if bg_img.mode != 'RGBA':
                        bg_img = bg_img.convert('RGBA')
                    background_layer.paste(bg_img, (0, 0))
                except Exception as e:
                    print(f"Error with background: {e}")
            else:
                # Create a black background
                background_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
            
            # 3. Add bezel to bezel_layer
            if hasattr(self, 'bezel_visible') and self.bezel_visible:
                bezel_path = self.get_bezel_path(self.current_game)
                if bezel_path and os.path.exists(bezel_path):
                    try:
                        bezel_img = Image.open(bezel_path)
                        bezel_img = bezel_img.resize((target_width, target_height), Image.LANCZOS)
                        if bezel_img.mode != 'RGBA':
                            bezel_img = bezel_img.convert('RGBA')
                        # Paste onto bezel layer
                        bezel_layer.paste(bezel_img, (0, 0), bezel_img)
                    except Exception as e:
                        print(f"Error with bezel: {e}")
            
            # 4. Draw text and controls on text_layer
            text_draw = ImageDraw.Draw(text_layer)
            
            # Add game info if enabled
            game_data = self.get_game_data(self.current_game)
            if game_data and getattr(self, 'show_rom_info', False):
                # Draw title
                game_title = game_data['gamename']
                text_draw.text((target_width//2, 60), game_title, fill=(255, 255, 255, 255), anchor="mt", font=title_font)
                
                # Draw ROM name
                text_draw.text((target_width//2, 110), f"ROM: {self.current_game}", fill=(150, 150, 150, 255), anchor="mt", font=font)
                
                # Draw details if available
                if 'miscDetails' in game_data:
                    text_draw.text((target_width//2, 150), game_data['miscDetails'], 
                            fill=(150, 150, 150, 255), anchor="mt", font=font)
            
            # Get custom controls if they exist
            cfg_controls = {}
            if self.current_game in self.custom_configs:
                cfg_controls = self.parse_cfg_controls(self.custom_configs[self.current_game])
                # Convert mappings if XInput is enabled
                if self.use_xinput:
                    cfg_controls = {
                        control: self.convert_mapping(mapping, True)
                        for control, mapping in cfg_controls.items()
                    }
            
            # Draw all currently visible control texts using position manager for consistency
            if hasattr(self, 'text_items'):
                print(f"Found {len(self.text_items)} text items to render")
                bold_strength = settings.get('bold_strength', 2)
                
                # Debug what's in text_items
                print("Text items content sample:")
                sample_count = 0
                for control_name, data in self.text_items.items():
                    if sample_count < 3:  # Print first 3 items as sample
                        print(f"  {control_name}: {data.keys()}")
                        if 'action' in data:
                            print(f"    Action: {data['action']}")
                        if 'display_text' in data:
                            print(f"    Display text: {data['display_text']}")
                        sample_count += 1
                
                # Make sure we have a position manager
                if not hasattr(self, 'position_manager'):
                    self.position_manager = PositionManager(self)
                    self.position_manager.load_from_file(self.current_game)
                
                # Render each text item
                for control_name, data in self.text_items.items():
                    # Skip hidden items
                    try:
                        if (hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists() and
                            'text' in data and
                            self.preview_canvas.itemcget(data['text'], 'state') == 'hidden'):
                            print(f"Skipping hidden item: {control_name}")
                            continue
                    except Exception:
                        pass
                    
                    # Get normalized position and apply offset consistently
                    if 'base_y' in data and 'x' in data:
                        normalized_x, normalized_y = data['x'], data['base_y']
                        # Use position manager to apply offset consistently
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                    elif 'x' in data and 'y' in data:
                        # We don't have base_y, so normalize first
                        normalized_x, normalized_y = self.position_manager.normalize(data['x'], data['y'])
                        # Then apply offset
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                    else:
                        print(f"No position data for {control_name}, skipping")
                        continue
                    
                    # Get the text to display
                    display_text = None
                    
                    # Try to get display_text directly
                    if 'display_text' in data:
                        display_text = data['display_text']
                    # Try to get action and format it
                    elif 'action' in data:
                        action = data['action']
                        # Apply uppercase if needed
                        display_text = self.get_display_text(action, settings, 
                                                            data.get('control_name'), 
                                                            data.get('custom_mapping'))
                    
                    if not display_text:
                        print(f"No display text for {control_name}, skipping")
                        continue
                        
                    print(f"Drawing text: '{display_text}' at ({text_x}, {text_y})")
                    
                    # Apply bold effect based on settings
                    # Inside the save_current_preview method, replace the text drawing section with this:

                    # Apply bold effect based on settings
                    bold_strength = settings.get('bold_strength', 2)

                    if bold_strength == 0:
                        # No bold effect - explicitly use a top-left anchor point (default in PIL)
                        text_draw.text((text_x, text_y), display_text, fill=(255, 255, 255, 255), font=font)
                    else:
                        # Draw shadows for bold effect
                        offsets = []
                        if bold_strength >= 1:
                            offsets.extend([(1, 0), (0, 1), (-1, 0), (0, -1)])
                        if bold_strength >= 2:
                            offsets.extend([(1, 1), (-1, 1), (1, -1), (-1, -1)])
                        if bold_strength >= 3:
                            offsets.extend([(2, 0), (0, 2), (-2, 0), (0, -2)])
                        
                        # Draw shadows
                        for dx, dy in offsets:
                            text_draw.text((text_x+dx, text_y+dy), display_text, fill=(0, 0, 0, 255), font=font)
                        
                        # Draw main text
                        text_draw.text((text_x, text_y), display_text, fill=(255, 255, 255, 255), font=font)
            
            # 5. Add logo to logo_layer
            if hasattr(self, 'logo_visible') and self.logo_visible:
                logo_path = self.get_logo_path(self.current_game)
                if logo_path and os.path.exists(logo_path):
                    try:
                        logo_img = Image.open(logo_path)
                        if logo_img.mode != 'RGBA':
                            logo_img = logo_img.convert('RGBA')
                        
                        # Calculate size based on logo settings
                        logo_width, logo_height = logo_img.size
                        max_width = int(target_width * (self.logo_width_percentage / 100))
                        max_height = int(target_height * (self.logo_height_percentage / 100))
                        
                        # Resize logo
                        scale_factor = min(max_width / max(logo_width, 1), max_height / max(logo_height, 1))
                        new_width = max(int(logo_width * scale_factor), 1)
                        new_height = max(int(logo_height * scale_factor), 1)
                        logo_img = logo_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        # Calculate position with consistent y-offset handling
                        padding = 20
                        y_offset = getattr(self, 'logo_y_offset', 0)
                        
                        # Apply the Y offset to positioning
                        if self.logo_position == 'top-left':
                            position = (padding, padding + y_offset)
                        elif self.logo_position == 'top-right':
                            position = (target_width - new_width - padding, padding + y_offset)
                        elif self.logo_position == 'bottom-left':
                            position = (padding, target_height - new_height - padding + y_offset)
                        elif self.logo_position == 'bottom-center':
                            position = ((target_width - new_width) // 2, target_height - new_height - padding + y_offset)
                        elif self.logo_position == 'bottom-right':
                            position = (target_width - new_width - padding, target_height - new_height - padding + y_offset)
                        else:  # Default to top-center
                            position = ((target_width - new_width) // 2, padding + y_offset)
                            
                        print(f"Logo placement in image: {position} (using Y offset: {y_offset})")
                        
                        # Paste logo onto logo layer
                        logo_layer.paste(logo_img, position, logo_img)
                    except Exception as e:
                        print(f"Error with logo: {e}")
            
            # 6. Composite layers in the correct order
            # Get layer ordering from settings
            layer_order = getattr(self, 'layer_order', {
                'bezel': 1,       # Default: bezel on bottom
                'background': 2,  # Background above bezel
                'logo': 3,        # Logo above background
                'text': 4         # Text on top
            })
            
            # Create a dictionary of layers with their order
            layers = {
                'bezel': {'image': bezel_layer, 'order': layer_order.get('bezel', 1)},
                'background': {'image': background_layer, 'order': layer_order.get('background', 2)},
                'logo': {'image': logo_layer, 'order': layer_order.get('logo', 3)},
                'text': {'image': text_layer, 'order': layer_order.get('text', 4)}
            }
            
            # Sort layers by order
            sorted_layers = sorted(layers.items(), key=lambda x: x[1]['order'])
            
            # Create a new image and composite layers from bottom to top
            composite_img = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            for layer_name, layer_data in sorted_layers:
                print(f"Compositing layer: {layer_name} (order {layer_data['order']})")
                composite_img = Image.alpha_composite(composite_img, layer_data['image'])
            
            # 7. Convert to RGB for saving
            final_img = composite_img.convert('RGB')
            
            # 8. Save the image
            final_img.save(output_path, format="PNG")
            
            # 9. Show success message
            messagebox.showinfo("Success", f"Image saved to:\n{output_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preview: {str(e)}")
            print(f"Error saving preview: {e}")
            traceback.print_exc()

    def add_save_preview_button(self):
        """Add a button to save the current preview as an image"""
        if hasattr(self, 'button_row1') and self.button_row1.winfo_exists():
            # Add to the first row of buttons in the preview window
            save_button = ctk.CTkButton(
                self.button_row1,
                text="Save Image",
                command=self.save_current_preview,
                width=90  # Match other buttons
            )
            save_button.pack(side="left", padx=3)
            print("Added Save Image button to preview")
    
    def add_generate_images_button(self):
        """Add button to generate preview images for ROMs (using the centralized button system)"""
        # Create the button using the centralized method
        generate_images_button = self.create_button(
            self.stats_frame,
            text="Generate Images",
            command=self.show_generate_images_dialog,
            button_id="generate_images_button",
            show=getattr(self, 'show_generate_buttons', True)
        )
        
        # If the button was created (show=True), grid it
        if generate_images_button:
            generate_images_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")

    def show_generate_images_dialog(self):
        """Show dialog to configure image generation"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Generate Preview Images")
        dialog.geometry("400x320")
        dialog.transient(self)
        dialog.grab_set()
        
        # Add explanatory text
        explanation = ctk.CTkLabel(
            dialog,
            text="This will generate preview images for ROMs using your saved control positions.",
            font=("Arial", 12),
            wraplength=350,
            justify="left"
        )
        explanation.pack(padx=20, pady=20, anchor="w")
        
        # Add warning about existing images
        warning = ctk.CTkLabel(
            dialog,
            text="Note: Existing images will be skipped. Images will be saved in the preview folder.",
            font=("Arial", 12),
            wraplength=350,
            justify="left",
            text_color="yellow"
        )
        warning.pack(padx=20, pady=10, anchor="w")
        
        # Add note about the background image
        bg_note = ctk.CTkLabel(
            dialog,
            text="The generator will use default.png from your preview folder as the background image.",
            font=("Arial", 12),
            wraplength=350,
            justify="left"
        )
        bg_note.pack(padx=20, pady=5, anchor="w")
        
        # Option to limit number of images
        limit_frame = ctk.CTkFrame(dialog)
        limit_frame.pack(padx=20, pady=10, fill="x")
        
        limit_var = ctk.IntVar(value=1)  # Default to ON
        limit_checkbox = ctk.CTkCheckBox(
            limit_frame, 
            text="Limit number of images",
            variable=limit_var,
            onvalue=1,
            offvalue=0
        )
        limit_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        limit_count_var = ctk.StringVar(value="10")
        limit_entry = ctk.CTkEntry(
            limit_frame,
            textvariable=limit_count_var,
            width=60
        )
        limit_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # Buttons frame
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(padx=20, pady=20, fill="x")
        
        def on_generate():
            try:
                limit = None
                if limit_var.get() == 1:
                    try:
                        limit = int(limit_count_var.get())
                        if limit <= 0:
                            messagebox.showerror("Error", "Limit must be a positive number")
                            return
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid number for the limit")
                        return
                        
                dialog.destroy()
                self.generate_preview_images(limit)
            except Exception as e:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Error", f"An error occurred: {str(e)}")
        
        generate_button = ctk.CTkButton(
            button_frame,
            text="Generate",
            command=on_generate
        )
        generate_button.grid(row=0, column=0, padx=5, pady=5)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        )
        cancel_button.grid(row=0, column=1, padx=5, pady=5)

    def save_text_appearance_settings(self, settings):
        """Save text appearance settings to file using the centralized path"""
        try:
            settings_path = self.get_settings_path("text")
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
            print(f"Saved text appearance settings to: {settings_path}")
        except Exception as e:
            print(f"Error saving text appearance settings: {e}")

    def apply_text_settings(self, draw, text, text_x, text_y, font, settings=None):
        """Apply text appearance settings to draw text with appropriate styling"""
        if settings is None:
            settings = self.get_text_settings()
        
        # Apply uppercase if enabled
        use_uppercase = settings.get("use_uppercase", False)
        if use_uppercase:
            text = text.upper()
        
        # Apply Y offset adjustment - REMOVED direct offset application here
        # text_y = text_y + settings.get("y_offset", -40)
        
        # Apply bold effect based on strength
        bold_strength = settings.get("bold_strength", 2)
        
        if bold_strength == 0:
            # No bold effect, just draw the text
            draw.text((text_x, text_y), text, fill="white", font=font, anchor="nw")  # Explicitly use nw anchor
        else:
            # Calculate offsets based on bold strength
            offsets = []
            if bold_strength >= 1:
                offsets.extend([(1, 0), (0, 1), (-1, 0), (0, -1)])
            if bold_strength >= 2:
                offsets.extend([(1, 1), (-1, 1), (1, -1), (-1, -1)])
            if bold_strength >= 3:
                offsets.extend([(2, 0), (0, 2), (-2, 0), (0, -2)])
            if bold_strength >= 4:
                offsets.extend([(2, 1), (1, 2), (-2, 1), (-1, 2), (2, -1), (1, -2), (-2, -1), (-1, -2)])
            if bold_strength >= 5:
                offsets.extend([(2, 2), (-2, 2), (2, -2), (-2, -2)])
            
            # Draw shadows
            for dx, dy in offsets:
                draw.text((text_x+dx, text_y+dy), text, fill="black", font=font, anchor="nw")  # Explicitly use nw anchor
            
            # Draw main text
            draw.text((text_x, text_y), text, fill="white", font=font, anchor="nw")  # Explicitly use nw anchor

    def get_tkfont(self, settings=None):
        """Get a tkinter font object based on settings"""
        import tkinter.font as tkfont
        
        if settings is None:
            settings = self.get_text_settings(refresh=True)
        
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        
        # Apply scaling factor for certain fonts
        adjusted_size = self.apply_font_scaling(font_family, font_size)
        
        # Create and return the font object
        try:
            return tkfont.Font(family=font_family, size=adjusted_size, weight="bold")
        except Exception as e:
            print(f"Error creating font: {e}")
            return tkfont.Font(family="Arial", size=28, weight="bold")  # Fallback font

    def update_preview_text_appearance(self):
        """Update existing preview window text items to use current text appearance settings"""
        import tkinter.font as tkfont
        
        if not hasattr(self, 'preview_canvas') or not self.preview_canvas.winfo_exists():
            print("No preview window is currently open")
            return
                
        if not hasattr(self, 'text_items') or not self.text_items:
            print("No text items found in preview window")
            return
        
        # Load current text appearance settings
        settings = self.get_text_settings(refresh=True)  # Force refresh
        
        # Check if uppercase is enabled
        use_uppercase = settings.get("use_uppercase", False)
        print(f"Uppercase setting: {use_uppercase}")
        
        # Get font settings
        font_family = settings.get("font_family", "Arial")
        font_size = settings.get("font_size", 28)
        
        # Apply scaling factor
        adjusted_font_size = self.apply_font_scaling(font_family, font_size)
        
        print(f"Updating preview text: Font={font_family}, Size={adjusted_font_size}, Uppercase={use_uppercase}")
        
        # Try to create the font for preview with a couple of fallback methods
        preview_font = None
        error_message = None
        
        # Method 1: Try with font filename from settings (most reliable)
        try:
            if "font_filename" in settings:
                import os
                font_path = os.path.join(self.mame_dir, "preview", "settings", "fonts", settings["font_filename"])
                if os.path.exists(font_path):
                    # We can't use the font file directly with tkinter, but we'll note it's available
                    print(f"Found font file at: {font_path}")
                    try:
                        # Try to register the font with tkinter if possible
                        preview_font = tkfont.Font(family=font_family, size=adjusted_font_size, weight="bold")
                        print(f"Created font using font family name: {font_family}")
                    except Exception as e:
                        error_message = f"Error with family name, will use fallback: {e}"
                else:
                    error_message = f"Font file not found: {font_path}"
            else:
                error_message = "No font_filename in settings"
        except Exception as e:
            error_message = f"Error trying to use font file: {e}"
            
        # Method 2: Try with font family name directly
        if preview_font is None:
            try:
                preview_font = tkfont.Font(family=font_family, size=adjusted_font_size, weight="bold")
                print(f"Created font using font family directly: {font_family}")
            except Exception as e:
                print(f"Error creating font with family name: {e}")
                # Method 3: Fall back to Arial
                try:
                    preview_font = tkfont.Font(family="Arial", size=adjusted_font_size, weight="bold")
                    print("Falling back to Arial font")
                except Exception as e2:
                    print(f"Error creating Arial fallback font: {e2}")
                    # Method 4: Last resort - use system default
                    preview_font = tkfont.nametofont("TkDefaultFont")
                    preview_font.configure(size=adjusted_font_size, weight="bold")
                    print("Using system default font as final fallback")
        
        if error_message:
            print(f"Note on font loading: {error_message}")
            
        if preview_font is None:
            print("ERROR: Could not create any font!")
            return
        
        # Store original positions if not already stored
        if not hasattr(self, 'original_positions'):
            self.original_positions = {}
            for control_name, data in self.text_items.items():
                if 'x' in data and 'y' in data:
                    self.original_positions[control_name] = (data['x'], data['y'])
        
        # Update positions using the position manager
        # First, update the manager with the current positions
        self.position_manager.update_from_text_items(self.text_items)
        
        # Get the font's actual family name
        actual_font_family = preview_font.actual("family")
        print(f"Actual font being used: {actual_font_family}")
        
        # Update each text item in the preview
        for control_name, data in self.text_items.items():
            try:
                # Get the original action text
                if 'action' in data:
                    action = data['action']
                    
                    # Get display text (apply uppercase if needed)
                    display_text = self.get_display_text(action, settings)
                    
                    # Store the updated display text
                    data['display_text'] = display_text
                    
                    # Update text for items
                    if 'text' in data:
                        self.preview_canvas.itemconfigure(data['text'], text=display_text, font=preview_font)
                    
                    # Update shadow text
                    if 'shadow' in data and data['shadow'] is not None:
                        self.preview_canvas.itemconfigure(data['shadow'], text=display_text, font=preview_font)
                
                # Get the normalized position
                if 'base_y' in data:
                    normalized_x, normalized_y = data['x'], data['base_y']
                    
                    # Apply the current offset - don't modify the normalized y value
                    display_x, display_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                    
                    # Update position on canvas - for Tkinter, use top-left (northwest) anchor
                    if 'text' in data:
                        self.preview_canvas.coords(data['text'], display_x, display_y)
                    if 'shadow' in data and data['shadow'] is not None:
                        # Shadow should have a small offset
                        shadow_offset = settings.get('bold_strength', 2)
                        shadow_offset = max(1, min(shadow_offset, 3))  # Clamp between 1-3 pixels
                        self.preview_canvas.coords(data['shadow'], display_x+shadow_offset, display_y+shadow_offset)
                        
                    # Update stored position without changing the base_y
                    data['x'] = display_x
                    data['y'] = display_y
                    
            except Exception as e:
                print(f"Error updating text for {control_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Force canvas update
        try:
            self.preview_canvas.update()
            print("Preview text appearance updated")
        except Exception as e:
            print(f"Error updating canvas: {e}")
            import traceback
            traceback.print_exc()

    # 3. Ensure the generate_preview_images method uses the text settings
    def generate_preview_images(self, limit=None):
        """Generate preview images for ROMs using control layout and positions"""
        import os
        from tkinter import messagebox
        from PIL import Image, ImageDraw, ImageFont
        import traceback
        import sys

        # Ensure preview directory exists
        preview_dir = self.ensure_preview_folder_improved()
        
        # Load text appearance settings explicitly
        settings = self.get_text_settings()
        use_uppercase = settings.get("use_uppercase", False)
        print(f"Batch generation - Uppercase setting: {use_uppercase}")
        
        # Add more debug output for font/text settings
        print(f"Font settings: family={settings.get('font_family', 'Arial')}, size={settings.get('font_size', 28)}")
        print(f"Y-offset: {settings.get('y_offset', -40)}")
        print(f"Bold strength: {settings.get('bold_strength', 2)}")
        
        # Get visibility settings
        visible_control_types = self.visible_control_types
        print(f"Visible control types: {visible_control_types}")
        
        # Find default background image
        default_bg_path = None
        for ext in ['.png', '.jpg', '.jpeg']:
            test_path = os.path.join(preview_dir, f"default{ext}")
            if os.path.exists(test_path):
                default_bg_path = test_path
                print(f"Found default background image: {default_bg_path}")
                break
                
        if not default_bg_path:
            # Create a default background if none exists
            default_bg_path = self.create_default_image(preview_dir)
            if not default_bg_path:
                messagebox.showerror("Error", "No default background image found and couldn't create one.")
                return
        
        # Load global positions for control layouts
        global_positions = self.load_text_positions("global")
        if not global_positions and os.path.exists(os.path.join(self.mame_dir, "preview", "all_controls_positions.json")):
            global_positions = self.load_text_positions("all_controls")
            
        if not global_positions:
            messagebox.showerror("Error", "No global position layout found. Please create and save a global layout first.")
            return

        print(f"Loaded global positions: {len(global_positions)} items")
        
        # Print a sample of positions for debugging
        sample_count = 0
        for button, pos in global_positions.items():
            if sample_count < 3:
                print(f"Position sample - {button}: {pos}")
                sample_count += 1

        # Create an instance of position manager for consistent offset application
        if not hasattr(self, 'position_manager'):
            self.position_manager = PositionManager(self)

        # Get fonts based on settings
        font, title_font = self.get_fonts_from_settings(settings)
        
        # Sort ROMs for processing
        sorted_roms = sorted(self.available_roms)
        
        # Apply limit if specified
        if limit and limit > 0:
            print(f"Limiting to {limit} ROMs")
            sorted_roms = sorted_roms[:limit]
            
        # Keep track of stats
        created = 0
        skipped = 0
        errors = 0
        
        # Create status window to show progress
        status_window = ctk.CTkToplevel(self)
        status_window.title("Generating ROM Preview Images")
        status_window.geometry("500x300")
        status_window.transient(self)
        
        # Status label
        status_label = ctk.CTkLabel(
            status_window,
            text="Preparing to generate preview images...",
            font=("Arial", 14)
        )
        status_label.pack(pady=20)
        
        # Progress display
        progress_text = ctk.CTkLabel(
            status_window,
            text=f"0/{len(sorted_roms)} processed",
            font=("Arial", 12)
        )
        progress_text.pack(pady=10)
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(status_window)
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.set(0)
        
        # Stats display
        stats_label = ctk.CTkLabel(
            status_window,
            text="Created: 0 | Skipped: 0 | Errors: 0",
            font=("Arial", 12)
        )
        stats_label.pack(pady=10)
        
        # Cancel button
        cancel_flag = [False]  # Use list to allow modification in inner function
        
        def cancel_generation():
            cancel_flag[0] = True
            status_label.configure(text="Cancelling...")
        
        cancel_button = ctk.CTkButton(
            status_window,
            text="Cancel",
            command=cancel_generation
        )
        cancel_button.pack(pady=10)
        
        # Update the window
        status_window.update()
        
        try:
            # Load the default background image
            try:
                bg_img = Image.open(default_bg_path)
                # Use 1920x1080 for the output size to match your preview window
                target_width, target_height = 1920, 1080
                
                # Resize background if needed
                if bg_img.size != (target_width, target_height):
                    bg_img = bg_img.resize((target_width, target_height), Image.LANCZOS)
                    
                print(f"Loaded and prepared background image, size: {target_width}x{target_height}")
            except Exception as e:
                print(f"Error loading background image: {e}")
                # Create a blank black image at 1920x1080
                target_width, target_height = 1920, 1080
                bg_img = Image.new('RGB', (target_width, target_height), color='black')
            
            # Process each ROM
            for i, rom_name in enumerate(sorted_roms):
                if cancel_flag[0]:
                    break
                    
                # Update progress
                progress = (i + 1) / len(sorted_roms)
                progress_bar.set(progress)
                progress_text.configure(text=f"{i+1}/{len(sorted_roms)} processed")
                stats_label.configure(text=f"Created: {created} | Skipped: {skipped} | Errors: {errors}")
                status_label.configure(text=f"Processing: {rom_name}")
                status_window.update()
                
                # Check if image already exists (skip if it does)
                image_path = os.path.join(preview_dir, f"{rom_name}.png")
                if os.path.exists(image_path):
                    print(f"Image already exists for {rom_name}, skipping")
                    skipped += 1
                    continue
                
                # Get game data
                game_data = self.get_game_data(rom_name)
                if not game_data:
                    print(f"No game data for {rom_name}, skipping")
                    skipped += 1
                    continue
                    
                # Try to load ROM-specific positions first
                rom_positions = self.load_text_positions(rom_name)
                # Fall back to global positions if ROM-specific not available
                positions = rom_positions if rom_positions else global_positions
                
                # Print the first few positions for debugging
                print(f"Using positions for {rom_name} ({len(positions)} items)")
                
                try:
                    # Create separate layer images for proper compositing
                    background_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                    bezel_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                    text_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                    logo_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                    
                    # Create a draw object for the text layer
                    text_draw = ImageDraw.Draw(text_layer)
                    
                    # Copy the background image to the background layer
                    background_layer.paste(bg_img.convert('RGBA'), (0, 0))
                    
                    # Add game title text if show_rom_info is enabled
                    if getattr(self, 'show_rom_info', False):
                        # Draw title (always show this)
                        game_title = game_data['gamename']
                        text_draw.text((target_width//2, 60), game_title, fill=(255, 255, 255, 255), anchor="mt", font=title_font)
                        
                        # Draw ROM info
                        text_draw.text((target_width//2, 110), f"ROM: {rom_name}", fill=(150, 150, 150, 255), anchor="mt", font=font)
                            
                        # Add any details if available
                        if 'miscDetails' in game_data:
                            text_draw.text((target_width//2, 150), game_data['miscDetails'], 
                                    fill=(150, 150, 150, 255), anchor="mt", font=font)
                    
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
                    
                    # THIS IS THE CRITICAL PART: Draw all controls based on positions with consistent y-offset
                    drawn_controls = 0
                    
                    for player in game_data.get('players', []):
                        if player['number'] != 1:  # Only show P1 controls for now
                            continue
                            
                        for label in player.get('labels', []):
                            control_name = label['name']
                            action = label['value']
                            
                            # Check if this control type should be visible
                            is_visible = False
                            for control_type in visible_control_types:
                                if control_type in control_name:
                                    is_visible = True
                                    break
                                    
                            # Skip if not visible
                            if not is_visible:
                                print(f"  Skipping hidden control: {control_name}")
                                continue
                            
                            # Get XInput button name for positioning
                            custom_mapping = None
                            if control_name in cfg_controls:
                                custom_mapping = cfg_controls[control_name]
                                
                            xinput_button = self.get_xinput_button_from_control(control_name, custom_mapping)
                            
                            # Skip controls that don't map to XInput buttons
                            if not xinput_button:
                                continue
                            
                            # Format the display text with proper settings
                            display_text = self.get_display_text(action, settings, control_name, custom_mapping)
                            
                            # Skip if no display text
                            if not display_text:
                                continue
                                
                            # Get position from the saved layout
                            if xinput_button in positions:
                                # Get normalized position (positions are already normalized)
                                normalized_x, normalized_y = positions[xinput_button]
                                
                                # Use position manager to apply offset consistently
                                display_x, display_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                                
                                # Debug output - print position calculations for a few controls
                                if drawn_controls < 2:
                                    print(f"Position for {xinput_button} (control: {control_name}): " + 
                                        f"normalized=({normalized_x}, {normalized_y}), " + 
                                        f"display=({display_x}, {display_y})")
                                
                                # Apply bold effect based on settings
                                bold_strength = settings.get('bold_strength', 2)
                                
                                if bold_strength == 0:
                                    # No bold effect
                                    text_draw.text((display_x, display_y), display_text, fill=(255, 255, 255, 255), font=font)
                                else:
                                    # Draw shadows for bold effect
                                    offsets = []
                                    if bold_strength >= 1:
                                        offsets.extend([(1, 0), (0, 1), (-1, 0), (0, -1)])
                                    if bold_strength >= 2:
                                        offsets.extend([(1, 1), (-1, 1), (1, -1), (-1, -1)])
                                    if bold_strength >= 3:
                                        offsets.extend([(2, 0), (0, 2), (-2, 0), (0, -2)])
                                        
                                    # Draw shadows
                                    for dx, dy in offsets:
                                        text_draw.text((display_x+dx, display_y+dy), display_text, fill=(0, 0, 0, 255), font=font)
                                    
                                    # Draw main text
                                    text_draw.text((display_x, display_y), display_text, fill=(255, 255, 255, 255), font=font)
                                    
                                drawn_controls += 1
                            else:
                                print(f"  Warning: No position for {xinput_button}")
                    
                    print(f"Drew {drawn_controls} controls for {rom_name}")

                    # Add bezel if enabled
                    if getattr(self, 'bezel_visible', True):
                        bezel_img = self.add_bezel_to_image(background_layer.copy().convert('RGB'), rom_name)
                        if bezel_img != background_layer:
                            bezel_layer = bezel_img.convert('RGBA')
                            
                    # Add logo if enabled
                    if getattr(self, 'logo_visible', True):
                        logo_img = self.add_logo_to_image(Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0)), rom_name)
                        if logo_img.getbbox():  # Check if logo is not empty
                            logo_layer = logo_img.convert('RGBA')
                    
                    # Get layer ordering from settings (or use default)
                    layer_order = getattr(self, 'layer_order', {
                        'bezel': 1,       # Default: bezel on bottom
                        'background': 2,  # Background above bezel
                        'logo': 3,        # Logo above background
                        'text': 4         # Text on top
                    })
                    
                    # Create a dictionary of layers with their order
                    layers = {
                        'bezel': {'image': bezel_layer, 'order': layer_order.get('bezel', 1)},
                        'background': {'image': background_layer, 'order': layer_order.get('background', 2)},
                        'logo': {'image': logo_layer, 'order': layer_order.get('logo', 3)},
                        'text': {'image': text_layer, 'order': layer_order.get('text', 4)}
                    }
                    
                    # Sort layers by order
                    sorted_layers = sorted(layers.items(), key=lambda x: x[1]['order'])
                    
                    # Composite all layers in correct order
                    composite_img = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                    for layer_name, layer_data in sorted_layers:
                        print(f"Compositing layer: {layer_name} (order {layer_data['order']})")
                        composite_img = Image.alpha_composite(composite_img, layer_data['image'])
                    
                    # Save the final image (convert to RGB for compatibility)
                    final_img = composite_img.convert('RGB')
                    final_img.save(image_path, format="PNG")
                    
                    print(f"Created preview image for {rom_name}: {image_path}")
                    created += 1
                        
                except Exception as e:
                    print(f"Error creating image for {rom_name}: {e}")
                    traceback.print_exc()
                    errors += 1
                        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate images: {str(e)}")
            traceback.print_exc()
        finally:
            # Update final stats
            stats_label.configure(text=f"Created: {created} | Skipped: {skipped} | Errors: {errors}")
            status_label.configure(text="Completed" if not cancel_flag[0] else "Cancelled")
            progress_text.configure(text=f"Processed {created + skipped + errors} ROMs")
            
            # Replace cancel button with close button
            cancel_button.destroy()
            close_button = ctk.CTkButton(
                status_window,
                text="Close",
                command=status_window.destroy
            )
            close_button.pack(pady=10)
            
            # Return stats
            return {
                "created": created,
                "skipped": skipped,
                "errors": errors,
                "total": len(sorted_roms)
            }
    
    def get_font_path(self):
        """Get the absolute path to the font file based on settings"""
        import os
        
        # Get font name from settings
        settings = self.get_text_settings()
        font_family = settings.get("font_family", "Arial")
        
        # Define all possible font paths
        font_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        if not os.path.exists(font_dir):
            os.makedirs(font_dir, exist_ok=True)
        
        # Check for exact match first
        for ext in ['.otf', '.ttf']:
            font_path = os.path.join(font_dir, f"{font_family}{ext}")
            if os.path.exists(font_path):
                print(f"Using font file: {font_path}")
                return font_path
        
        # If no exact match, check for partial matches
        font_name_lower = font_family.lower().replace(' ', '')
        for filename in os.listdir(font_dir):
            if filename.lower().startswith(font_name_lower) and filename.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(font_dir, filename)
                print(f"Using font file (partial match): {font_path}")
                return font_path
        
        # No suitable font found, use a default fallback path
        default_path = os.path.join(font_dir, "Arial.ttf")
        print(f"No suitable font found for '{font_family}', using default path: {default_path}")
        
        # Try to ensure the default font exists
        if not os.path.exists(default_path):
            print("Default font file not found. Please install fonts in the fonts directory.")
        
        return default_path
    
    # 2. Update get_fonts_from_settings to only use font files, not system fonts
    def get_fonts_from_settings(self, settings=None):
        """Get font objects based on settings using only font files (no system fonts)"""
        import os
        from PIL import ImageFont
        
        # Default to our fixed settings if none provided
        if settings is None:
            settings = self.get_text_settings()
        
        font_family = settings.get("font_family")
        font_size = settings.get("font_size", 28)
        title_font_size = settings.get("title_size", 36)
        
        # Look for the font file in the fonts directory
        font_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        font_path = None
        
        # Check exact name match
        for ext in ['.ttf', '.otf']:
            test_path = os.path.join(font_dir, f"{font_family}{ext}")
            if os.path.exists(test_path):
                font_path = test_path
                break
        
        # If not found, look for partial name matches
        if not font_path and os.path.exists(font_dir):
            font_name_lower = font_family.lower().replace(' ', '')
            for filename in os.listdir(font_dir):
                if filename.lower().startswith(font_name_lower) and filename.lower().endswith(('.ttf', '.otf')):
                    font_path = os.path.join(font_dir, filename)
                    break
        
        # If font path found, load using direct file path
        if font_path:
            try:
                # Load using direct file path
                font = ImageFont.truetype(font_path, font_size)
                title_font = ImageFont.truetype(font_path, title_font_size)
                print(f"Loaded font from path: {font_path}")
                return font, title_font
            except Exception as e:
                print(f"Error loading font from {font_path}: {e}")
        
        # Last resort - use default PIL font
        print(f"Font '{font_family}' not found in fonts directory, using default")
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        
        return font, title_font

    def show_preview_original(self):
        """Store the original show_preview method to be called from the modified version"""
        pass  # This will be replaced with the original show_preview method

    def show_preview_with_settings(self):
        """Modified show_preview that applies text appearance settings and adds logo controls"""
        # Call the original method first to create the preview window
        result = self.show_preview_original()
        
        # Store original positions of text items before applying offset
        # This allows us to reapply the offset if settings change later
        if hasattr(self, 'text_items') and not hasattr(self, 'original_positions'):
            self.original_positions = {}
            for control_name, data in self.text_items.items():
                if 'x' in data and 'y' in data:
                    self.original_positions[control_name] = (data['x'], data['y'])
        
        # Now apply current text appearance settings
        self.update_preview_text_appearance()
        
        # Add text settings button to button row if it exists
        if hasattr(self, 'button_row1') and self.button_row1.winfo_exists():
            settings_button = ctk.CTkButton(
                self.button_row1,
                text="Text Settings",
                command=lambda: self.show_text_appearance_settings(update_preview=True),
                width=90  # Match other buttons
            )
            settings_button.pack(side="left", padx=3)
        
        # Add logo controls to the preview window
        self.add_logo_controls_to_preview()
        
        return result

    def get_formatted_text(self, text):
        """Apply consistent text formatting to all text (uppercase, etc.)"""
        settings = self.get_text_settings()
        
        if settings["uppercase"]:
            return text.upper()
        else:
            return text  # Keep original case
    
    def show_image_preview(self):
        """Show a window with an exact preview of how the image will be generated"""
        if not hasattr(self, 'current_game') or not self.current_game:
            messagebox.showerror("Error", "No game is currently selected")
            return

        import os
        from tkinter import messagebox
        from PIL import Image, ImageDraw, ImageTk, ImageFont
        import traceback

        # Check for and close any existing exact preview windows
        if hasattr(self, 'exact_preview_window') and self.exact_preview_window.winfo_exists():
            print("Closing existing exact preview window")
            self.exact_preview_window.destroy()
                
        try:
            print("\n--- STARTING EXACT PREVIEW ---")
            
            # Get all settings from central settings function
            settings = self.get_text_settings()
            font_size = settings.get("font_size", 28)
            title_size = settings.get("title_size", 36)
            bold_strength = settings.get("bold_strength", 2)
            y_offset = settings.get("y_offset", -40)
            
            print(f"Using text settings: size={font_size}, title={title_size}, "
                f"bold={bold_strength}, y_offset={y_offset}, uppercase={settings.get('uppercase', False)}")
            
            # Get direct path to font file
            font_path = self.get_font_path()
            if not font_path:
                messagebox.showerror("Error", f"Font file not found! Please add {settings.get('font_family', 'Arial')} to the fonts folder.")
                return
                    
            # Load font directly from file
            try:
                font = ImageFont.truetype(font_path, font_size)
                title_font = ImageFont.truetype(font_path, title_size)
                print(f"Loaded font for exact preview: {font_path}")
            except Exception as e:
                print(f"Error loading font: {e}")
                messagebox.showerror("Font Error", f"Could not load font: {str(e)}")
                return
            
            # Create a base black image
            target_width, target_height = 1920, 1080  # Standard full HD size
            base_img = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
            
            # Make sure we have a position manager
            if not hasattr(self, 'position_manager'):
                self.position_manager = PositionManager(self)
                self.position_manager.load_from_file(self.current_game)
            
            # Get layer ordering (or use default)
            if not hasattr(self, 'layer_order'):
                self.layer_order = {
                    'bezel': 1,       # Lowest layer (furthest back)
                    'background': 2,
                    'logo': 3,
                    'text': 4         # Highest layer (closest to front)
                }
                
            # Create a dictionary to hold all layered components
            layers = {}
            
            # 1. Load bezel if enabled
            if hasattr(self, 'bezel_visible') and self.bezel_visible:
                bezel_path = self.get_bezel_path(self.current_game)
                if bezel_path and os.path.exists(bezel_path):
                    try:
                        bezel_img = Image.open(bezel_path)
                        bezel_img = bezel_img.resize((target_width, target_height), Image.LANCZOS)
                        if bezel_img.mode != 'RGBA':
                            bezel_img = bezel_img.convert('RGBA')
                        layers['bezel'] = {'image': bezel_img, 'order': self.layer_order['bezel']}
                        print(f"Added bezel to layers, order: {self.layer_order['bezel']}")
                    except Exception as e:
                        print(f"Error loading bezel: {e}")
            
            # 2. Load the background image
            background_path = None
            preview_dir = self.ensure_preview_folder_improved()
            
            for ext in ['.png', '.jpg', '.jpeg']:
                # First check for ROM-specific background
                test_path = os.path.join(preview_dir, f"{self.current_game}{ext}")
                if os.path.exists(test_path):
                    background_path = test_path
                    print(f"Using ROM-specific background: {background_path}")
                    break
                    
                # Then check for default background
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    background_path = test_path
                    print(f"Using default background: {background_path}")
                    break
            
            if background_path:
                try:
                    bg_img = Image.open(background_path)
                    bg_img = bg_img.resize((target_width, target_height), Image.LANCZOS)
                    if bg_img.mode != 'RGBA':
                        bg_img = bg_img.convert('RGBA')
                    layers['background'] = {'image': bg_img, 'order': self.layer_order['background']}
                    print(f"Added background to layers, order: {self.layer_order['background']}")
                except Exception as e:
                    print(f"Error loading background: {e}")
            
            # 3. Create a blank transparent layer for text
            text_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            
            # 4. Draw game title and info on text layer
            game_data = self.get_game_data(self.current_game)
            if game_data:
                if getattr(self, 'show_rom_info', False):
                    # Draw title (always show this)
                    game_title = game_data['gamename']
                    text_draw.text((target_width//2, 60), game_title, fill=(255, 255, 255, 255), anchor="mt", font=title_font)
                    
                    # Only draw ROM info if show_rom_info is True
                    text_draw.text((target_width//2, 110), f"ROM: {self.current_game}", fill=(150, 150, 150, 255), anchor="mt", font=font)
                        
                    # Add any details if available
                    if 'miscDetails' in game_data:
                        text_draw.text((target_width//2, 150), game_data['miscDetails'], 
                                fill=(150, 150, 150, 255), anchor="mt", font=font)
            
            # 5. Draw all currently visible text items on text layer
            if hasattr(self, 'text_items'):
                print(f"Found {len(self.text_items)} text items to render")
                
                for control_name, data in self.text_items.items():
                    # Skip hidden items
                    try:
                        if (hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists() and
                            'text' in data and
                            self.preview_canvas.itemcget(data['text'], 'state') == 'hidden'):
                            print(f"Skipping hidden item: {control_name}")
                            continue
                    except Exception as e:
                        print(f"Error checking visibility for {control_name}: {e}")
                    
                    # Get normalized position from the data
                    if 'base_y' in data and 'x' in data:
                        # We have the normalized position already
                        normalized_x, normalized_y = data['x'], data['base_y']
                        # Use position manager to apply offset consistently
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                    else:
                        # We don't have base_y, need to normalize then apply offset
                        normalized_x, normalized_y = self.position_manager.normalize(data['x'], data['y'])
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y)
                    
                    # Get the display text
                    display_text = None
                    if 'display_text' in data:
                        display_text = data['display_text']
                    elif 'action' in data:
                        # Generate display text from action
                        action = data['action']
                        control_name_for_display = data.get('control_name')
                        custom_mapping = data.get('custom_mapping')
                        display_text = self.get_display_text(action, settings, control_name_for_display, custom_mapping)
                    
                    if not display_text:
                        print(f"No display text for {control_name}, skipping")
                        continue
                    
                    print(f"Drawing {control_name} at ({text_x}, {text_y}): {display_text}")
                    
                    # Apply bold effect based on settings
                    if bold_strength == 0:
                        # No bold effect
                        text_draw.text((text_x, text_y), display_text, fill=(255, 255, 255, 255), font=font)
                    else:
                        # Draw shadows for bold effect
                        offsets = []
                        if bold_strength >= 1:
                            offsets.extend([(1, 0), (0, 1), (-1, 0), (0, -1)])
                        if bold_strength >= 2:
                            offsets.extend([(1, 1), (-1, 1), (1, -1), (-1, -1)])
                        if bold_strength >= 3:
                            offsets.extend([(2, 0), (0, 2), (-2, 0), (0, -2)])
                            
                        # Draw shadows
                        for dx, dy in offsets:
                            text_draw.text((text_x+dx, text_y+dy), display_text, fill=(0, 0, 0, 255), font=font)
                        
                        # Draw main text
                        text_draw.text((text_x, text_y), display_text, fill=(255, 255, 255, 255), font=font)
            
            # Add text layer to layers dict
            layers['text'] = {'image': text_layer, 'order': self.layer_order['text']}
            print(f"Added text to layers, order: {self.layer_order['text']}")
            
            # 6. Load logo if enabled
            if hasattr(self, 'logo_visible') and self.logo_visible:
                logo_path = self.get_logo_path(self.current_game)
                if logo_path and os.path.exists(logo_path):
                    try:
                        logo_img = Image.open(logo_path)
                        if logo_img.mode != 'RGBA':
                            logo_img = logo_img.convert('RGBA')
                        
                        # Calculate size
                        max_width = int(target_width * (self.logo_width_percentage / 100))
                        max_height = int(target_height * (self.logo_height_percentage / 100))
                        logo_width, logo_height = logo_img.size
                        scale_factor = min(max_width / max(logo_width, 1), max_height / max(logo_height, 1))
                        new_width = max(int(logo_width * scale_factor), 1)
                        new_height = max(int(logo_height * scale_factor), 1)
                        logo_img = logo_img.resize((new_width, new_height), Image.LANCZOS)
                        
                        # Create a full-size transparent image for the logo
                        logo_layer = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
                        
                        # Get Y offset from settings (default to 0 if not set)
                        y_offset = getattr(self, 'logo_y_offset', 0)
                        
                        # Calculate position
                        padding = 20
                        
                        # Apply the Y offset to positioning
                        if self.logo_position == 'top-left':
                            position = (padding, padding + y_offset)
                        elif self.logo_position == 'top-right':
                            position = (target_width - new_width - padding, padding + y_offset)
                        elif self.logo_position == 'bottom-left':
                            position = (padding, target_height - new_height - padding + y_offset)
                        elif self.logo_position == 'bottom-center':
                            position = ((target_width - new_width) // 2, target_height - new_height - padding + y_offset)
                        elif self.logo_position == 'bottom-right':
                            position = (target_width - new_width - padding, target_height - new_height - padding + y_offset)
                        else:  # Default to top-center
                            position = ((target_width - new_width) // 2, padding + y_offset)
                            
                        print(f"Logo placement in exact preview: {position} (using Y offset: {y_offset})")
                        
                        # Paste logo onto the transparent layer
                        logo_layer.paste(logo_img, position, logo_img)
                        
                        # Add to layers
                        layers['logo'] = {'image': logo_layer, 'order': self.layer_order['logo']}
                        print(f"Added logo to layers, order: {self.layer_order['logo']}")
                    except Exception as e:
                        print(f"Error adding logo: {e}")
            
            # 7. Composite all layers in order
            # Sort layers by order
            sorted_layers = sorted(layers.items(), key=lambda x: x[1]['order'])

            # Composite from bottom to top
            composite_img = base_img.copy()
            for layer_name, layer_data in sorted_layers:
                print(f"Compositing layer: {layer_name} (order {layer_data['order']})")
                composite_img = Image.alpha_composite(composite_img, layer_data['image'])
            
            # Convert final image back to RGB for display
            final_img = composite_img.convert('RGB')
            print("Image composition complete")

            # Now display this image in a window
            self.exact_preview_window = ctk.CTkToplevel(self)
            self.exact_preview_window.title(f"Exact Image Preview: {self.current_game}")
            self.exact_preview_window.attributes('-topmost', True)
            
            # Resize the image to fit on screen (maintaining aspect ratio)
            screen_width = self.exact_preview_window.winfo_screenwidth()
            screen_height = self.exact_preview_window.winfo_screenheight()
            print(f"Screen dimensions: {screen_width}x{screen_height}")
            
            # Maximum size for preview (80% of screen)
            max_width = int(screen_width * 0.8)
            max_height = int(screen_height * 0.8)
            
            # Calculate scale factor
            scale_factor = min(max_width / target_width, max_height / target_height)
            
            # Calculate new dimensions
            display_width = int(target_width * scale_factor)
            display_height = int(target_height * scale_factor)
            print(f"Displaying at size: {display_width}x{display_height}")
            
            # Resize for display
            display_img = final_img.resize((display_width, display_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            print("Converting to PhotoImage")
            photo = ImageTk.PhotoImage(display_img)
            
            # Create canvas for the image
            canvas = ctk.CTkCanvas(self.exact_preview_window, width=display_width, height=display_height)
            canvas.pack(padx=10, pady=10)
            
            # Display the image
            print("Creating image on canvas")
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas.image = photo  # Keep a reference
            
            # Button frame
            button_frame = ctk.CTkFrame(self.exact_preview_window)
            button_frame.pack(padx=10, pady=10, fill="x")
            
            # Save button
            save_button = ctk.CTkButton(
                button_frame, 
                text="Save Image", 
                command=lambda: self.save_current_preview()
            )
            save_button.pack(side="left", padx=10)
            
            # Close button
            close_button = ctk.CTkButton(
                button_frame,
                text="Close",
                command=self.exact_preview_window.destroy
            )
            close_button.pack(side="right", padx=10)
            
            # Set window size based on image dimensions plus padding
            self.exact_preview_window.geometry(f"{display_width + 40}x{display_height + 100}")
            
            # Center window on screen
            x = (screen_width - (display_width + 40)) // 2
            y = (screen_height - (display_height + 100)) // 2
            self.exact_preview_window.geometry(f"+{x}+{y}")
            
            print("--- EXACT PREVIEW COMPLETED ---\n")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create preview: {str(e)}")
            print(f"Error creating preview: {e}")
            traceback.print_exc()

    def toggle_logo_and_refresh(self, preview_window, canvas, photo, original_img, display_width, display_height):
        """Toggle logo visibility and refresh the exact preview image"""
        from PIL import ImageTk
        
        # Toggle the visibility state
        self.logo_visible = not self.logo_visible
        
        # Update logo visibility state in settings
        self.save_logo_settings()
        
        try:
            # Create a new image with/without logo based on current visibility
            new_img = original_img.copy()
            
            # Add logo if visible
            if self.logo_visible:
                new_img = self.add_logo_to_image(new_img, self.current_game)
            
            # Resize for display
            display_img = new_img.resize((display_width, display_height), Image.LANCZOS)
            
            # Update the photo
            new_photo = ImageTk.PhotoImage(display_img)
            
            # Update canvas
            canvas.delete("all")  # Remove existing image
            canvas.create_image(0, 0, anchor="nw", image=new_photo)
            canvas.image = new_photo  # Keep a reference
            
            # Update button text
            for widget in preview_window.winfo_children():
                if isinstance(widget, ctk.CTkFrame):
                    for child in widget.winfo_children():
                        if isinstance(child, ctk.CTkButton) and child.cget("text") in ["Show Logo", "Hide Logo"]:
                            child.configure(text="Hide Logo" if self.logo_visible else "Show Logo")
            
            print(f"Updated logo visibility in exact preview: {'visible' if self.logo_visible else 'hidden'}")
        except Exception as e:
            print(f"Error updating logo in exact preview: {e}")
    
    def apply_preview_update_hook(self):
        """Apply hooks to update preview window for logos only (text settings removed)"""
        print("\n=== Applying preview hooks ===")
        
        # Store the original show_preview method properly
        if not hasattr(self, 'show_preview_original'):
            self.show_preview_original = self.show_preview
            print("Original show_preview method stored")
        
        # Define the new method that only applies logo settings
        def show_preview_with_logo_only(self):
            """Custom version of show_preview that applies logo settings only"""
            # Call the original method first
            result = self.show_preview_original()
            
            # Load settings
            if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
                self.load_logo_settings()
            
            # Add logo if needed
            if hasattr(self, 'preview_canvas') and self.current_game:
                # Add the logo to the canvas
                if self.logo_visible:
                    self.add_logo_to_preview_canvas()
                
            # Add logo controls to buttons if they exist
            if hasattr(self, 'button_row2') and self.button_row2.winfo_exists():
                # Logo controls
                toggle_text = "Hide Logo" if self.logo_visible else "Show Logo"
                self.logo_toggle_button = ctk.CTkButton(
                    self.button_row2,
                    text=toggle_text,
                    command=self.toggle_logo_visibility,
                    width=90
                )
                self.logo_toggle_button.pack(side="left", padx=3)
                
                self.logo_position_button = ctk.CTkButton(
                    self.button_row2,
                    text="Logo Pos",
                    command=self.show_logo_position_dialog,
                    width=90
                )
                self.logo_position_button.pack(side="left", padx=3)
                
            return result
        
        # Replace the original method with our new method
        self.show_preview = show_preview_with_logo_only.__get__(self, type(self))
        
        print("Replaced show_preview with custom version that applies logo settings only")
        print("=== Preview hooks applied ===\n")

    def scan_fonts_directory(self):
        """
        Scan the fonts directory and return a list of available fonts with their display names
        """
        import os
        from PIL import ImageFont, Image
        import re
        
        # Define the fonts directory
        fonts_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        if not os.path.exists(fonts_dir):
            os.makedirs(fonts_dir, exist_ok=True)
            print(f"Created fonts directory: {fonts_dir}")
            return []
        
        # List to store font information: (filename, display_name)
        available_fonts = []
        
        # Only scan for fonts in the custom font directory
        fonts_found = False
        
        # Scan all font files in the directory
        for filename in os.listdir(fonts_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                # Full path to the font file
                font_path = os.path.join(fonts_dir, filename)
                
                # Get proper display name
                display_name = self.get_font_display_name(font_path, filename)
                
                # Add to available fonts
                available_fonts.append((filename, display_name))
                fonts_found = True
                print(f"Found font: {display_name} ({filename})")
        
        # Add fallback font only if no fonts were found
        if not fonts_found:
            fallback_font = ("Arial.ttf", "Arial (Default)")
            available_fonts.append(fallback_font)
            print(f"No fonts found in directory, added fallback option: {fallback_font[1]}")
        
        # Simply sort all fonts alphabetically by display name
        # If we have the fallback Arial option, keep it at the top
        fallback_fonts = []
        other_fonts = []
        
        for font in available_fonts:
            if "Arial (Default)" in font[1]:
                fallback_fonts.append(font)
            else:
                other_fonts.append(font)
        
        # Sort the other fonts alphabetically
        other_fonts.sort(key=lambda x: x[1].lower())
        
        # Combine lists with fallback at the beginning
        result = []
        result.extend(fallback_fonts)
        result.extend(other_fonts)
        
        return result
    
    def get_font_display_name(self, font_path, filename):
        """
        Attempt to extract the proper display name from a font file
        Falls back to a cleaned-up version of the filename if extraction fails
        """
        import os
        from PIL import ImageFont
        import re
        
        # First try to get the actual font name from the file if possible
        try:
            # Try to load the font to see if we can extract its name
            font = ImageFont.truetype(font_path, 12)
            
            # Some fonts have metadata that can be accessed
            if hasattr(font, 'getname'):
                return font.getname()[0]
        except Exception as e:
            print(f"Could not extract font name from {filename}: {e}")
        
        # Fall back to cleaning up the filename
        display_name = filename
        
        # Remove file extension
        display_name = os.path.splitext(display_name)[0]
        
        # Replace hyphens and underscores with spaces
        display_name = display_name.replace('-', ' ').replace('_', ' ')
        
        # Clean up common naming patterns
        # Convert camelCase to spaces (e.g., PressStart2P -> Press Start 2P)
        display_name = re.sub(r'([a-z])([A-Z0-9])', r'\1 \2', display_name)
        
        # Insert space before numbers
        display_name = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', display_name)
        
        # Clean up multiple spaces
        display_name = ' '.join(display_name.split())
        
        return display_name

    # Modification to show_text_appearance_settings to improve font selection
    def get_system_fonts(self):
        """Get only the fonts available in our fonts directory"""
        # Default fallback fonts
        fallback_fonts = ["Arial", "Press Start 2P"]
        
        # Get fonts from the fonts directory
        fonts_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        if os.path.exists(fonts_dir):
            font_list = []
            for filename in os.listdir(fonts_dir):
                if filename.lower().endswith(('.ttf', '.otf')):
                    # Get display name
                    display_name = self.get_font_display_name(os.path.join(fonts_dir, filename), filename)
                    font_list.append(display_name)
            
            if font_list:
                return font_list
        
        return fallback_fonts

    def is_system_font(self, font_name):
        """Check if a font exists in our fonts directory"""
        fonts_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        if not os.path.exists(fonts_dir):
            return False
        
        # Look for exact match
        for ext in ['.ttf', '.otf']:
            if os.path.exists(os.path.join(fonts_dir, f"{font_name}{ext}")):
                return True
        
        # Look for partial match
        font_name_lower = font_name.lower().replace(' ', '')
        for filename in os.listdir(fonts_dir):
            if filename.lower().startswith(font_name_lower) and filename.lower().endswith(('.ttf', '.otf')):
                return True
        
        return False

    def debug_font_system(self):
        """Debug the font system and print information about available fonts in the fonts directory"""
        import os
        
        print("\n=== FONT DEBUG ===")
        
        # Check settings
        settings = self.get_text_settings(refresh=True)
        print(f"Font Family: {settings.get('font_family', 'Not set')}")
        print(f"Font Name: {settings.get('font_name', 'Not set')}")
        
        # Check fonts directory
        font_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        print(f"\nFonts Directory: {font_dir}")
        if os.path.exists(font_dir):
            print("Directory exists")
            font_files = [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf'))]
            print(f"Font files found: {len(font_files)}")
            for file in font_files:
                print(f"  - {file}")
        else:
            print("Directory does not exist")
            try:
                os.makedirs(font_dir, exist_ok=True)
                print(f"Created fonts directory: {font_dir}")
            except Exception as e:
                print(f"Error creating fonts directory: {e}")
        
        # Check for the selected font
        target = settings.get('font_family', 'Arial')
        print(f"\nSearching for font: {target}")
        found = False
        
        # Look for exact match
        for ext in ['.ttf', '.otf']:
            path = os.path.join(font_dir, f"{target}{ext}")
            if os.path.exists(path):
                print(f"Found exact match: {path}")
                found = True
                break
        
        # Look for partial match if not found
        if not found and os.path.exists(font_dir):
            target_lower = target.lower().replace(' ', '')
            for filename in os.listdir(font_dir):
                if filename.lower().startswith(target_lower) and filename.lower().endswith(('.ttf', '.otf')):
                    print(f"Found partial match: {filename}")
                    found = True
                    break
        
        if not found:
            print(f"Font '{target}' not found in fonts directory")
            print(f"Please add the font file to: {font_dir}")
        
        print("=== END FONT DEBUG ===\n")
        return True

    # Modified part of the show_text_appearance_settings method
    # Replace the font selection code with this:
    def create_font_selection(self, parent_frame, current_font, on_font_change_callback):
        """Create a compact font selection interface using only fonts from fonts directory"""
        font_frame = ctk.CTkFrame(parent_frame)
        font_frame.pack(fill="x", pady=5)  # Reduced vertical padding
        
        # Font selection row with label and dropdown side by side
        selection_row = ctk.CTkFrame(font_frame)
        selection_row.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(selection_row, text="Font:", width=60).pack(side="left", padx=5)
        
        # Get fonts from directory only
        available_fonts = self.scan_fonts_directory()
        directory_font_names = [display_name for _, display_name in available_fonts]
        
        # Add "Press Start 2P" if not in the list (our default)
        if "Press Start 2P" not in directory_font_names:
            directory_font_names.insert(0, "Press Start 2P")
        
        # Create font variable
        font_var = ctk.StringVar(value=current_font)
        
        # Create dropdown with fonts from directory
        font_dropdown = ctk.CTkOptionMenu(
            selection_row, 
            values=directory_font_names,
            variable=font_var,
            command=on_font_change_callback,
            width=300
        )
        font_dropdown.pack(side="left", padx=5, fill="x", expand=True)
        
        return font_var

    # Function to load and register a custom font
    def register_custom_font(self, font_path):
        """
        Copy a font file to the fonts directory and return its display name
        """
        import os
        import shutil
        
        try:
            # Create fonts directory if it doesn't exist
            fonts_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
            os.makedirs(fonts_dir, exist_ok=True)

            # Get filename from path
            filename = os.path.basename(font_path)
            
            # Destination path
            dest_path = os.path.join(fonts_dir, filename)
            
            # Copy the file
            if os.path.exists(dest_path):
                # File already exists
                print(f"Font file already exists: {dest_path}")
            else:
                shutil.copy2(font_path, dest_path)
                print(f"Copied font file to: {dest_path}")
            
            # Get display name
            display_name = self.get_font_display_name(dest_path, filename)
            
            return True, display_name
        except Exception as e:
            print(f"Error registering font: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def show_text_appearance_settings(self, update_preview=False):
        """Show dialog for text appearance settings with font selection from fonts directory only"""
        import os
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        # Get current settings
        settings = self.get_text_settings(refresh=True)
        
        # Create dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Text Appearance Settings")
        #dialog.geometry("500x600")  # Shorter without system fonts option
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog on the screen
        dialog_width = 500
        dialog_height = 600

        # Get screen width and height
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        # Calculate position x, y
        x = int((screen_width / 2) - (dialog_width / 2))
        y = int((screen_height / 2) - (dialog_height / 2))

        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Main frame with scrolling
        main_frame = ctk.CTkScrollableFrame(dialog)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Warning about restart
        restart_frame = ctk.CTkFrame(main_frame)
        restart_frame.pack(fill="x", pady=5)
        
        restart_label = ctk.CTkLabel(
            restart_frame,
            text="⚠️ Note: Font changes may require app restart to fully apply.",
            text_color="#FF8C00",  # Orange warning color
            font=("Arial", 12, "bold")
        )
        restart_label.pack(pady=10)
        
        # Font selection section
        font_section = ctk.CTkFrame(main_frame)
        font_section.pack(fill="x", pady=10)
        
        ctk.CTkLabel(font_section, text="Font Selection", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Scan directory fonts only
        available_fonts = self.scan_fonts_directory()
        
        # Create a mapping of display_name -> filename for easier lookup
        font_name_to_file = {display_name: filename for filename, display_name in available_fonts}
        
        # Current font
        current_font = settings.get("font_family", "Arial")
        
        # Create a warning label if no fonts found
        if not available_fonts or (len(available_fonts) == 1 and "Arial (Default)" in available_fonts[0][1]):
            warning_frame = ctk.CTkFrame(font_section, fg_color="#881111")  # Reddish background
            warning_frame.pack(fill="x", padx=10, pady=5)
            
            warning_text = ctk.CTkLabel(
                warning_frame,
                text="⚠️ No font files found in the fonts directory!\nYou should add at least one font file.",
                text_color="#FFFFFF",
                font=("Arial", 14, "bold")
            )
            warning_text.pack(pady=10)
            
            # Add an "Add Font Now" button directly in the warning
            add_font_now = ctk.CTkButton(
                warning_frame,
                text="Add Font Now...",
                command=lambda: add_custom_font(),
                fg_color="#FFD700",  # Gold color for emphasis
                text_color="#000000",
                hover_color="#FFA500"  # Orange hover
            )
            add_font_now.pack(pady=(0, 10))
        
        # Create frame for font controls
        font_controls = ctk.CTkFrame(font_section)
        font_controls.pack(fill="x", padx=10, pady=5)
        
        # Create a variable to store selected font
        font_var = ctk.StringVar(value=current_font)
        
        # Get list of font display names for dropdown
        directory_font_names = [display_name for _, display_name in available_fonts]
        
        # Font dropdown section with a "browse" button next to it
        font_dropdown_frame = ctk.CTkFrame(font_controls)
        font_dropdown_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(font_dropdown_frame, text="Font:", width=60).pack(side="left", padx=5)
        
        font_dropdown = ctk.CTkOptionMenu(
            font_dropdown_frame,
            values=directory_font_names,
            variable=font_var,
            width=250  # Slightly narrower to make room for button
        )
        font_dropdown.pack(side="left", padx=5, fill="x", expand=True)
        
        # Add font function
        def add_custom_font():
            filetypes = [("Font Files", "*.ttf *.otf")]
            font_path = filedialog.askopenfilename(
                title="Select Font File",
                filetypes=filetypes
            )
            
            if font_path:
                # Register the font
                success, result = self.register_custom_font(font_path)
                if success:
                    # Refresh the font list
                    new_fonts = self.scan_fonts_directory()
                    # Update dropdown values
                    new_display_names = [name for _, name in new_fonts]
                    
                    font_dropdown.configure(values=new_display_names)
                    
                    # Select the newly added font
                    if result in new_display_names:
                        font_var.set(result)
                        
                    messagebox.showinfo("Success", f"Added font: {result}")
                    
                    # If there was a warning, remove it
                    for widget in font_section.winfo_children():
                        if isinstance(widget, ctk.CTkFrame) and widget._fg_color == "#881111":
                            widget.destroy()
                            break
                else:
                    messagebox.showerror("Error", f"Could not add font: {result}")
        
        # Add the browse button directly next to the dropdown
        browse_button = ctk.CTkButton(
            font_dropdown_frame,
            text="Browse...",
            command=add_custom_font,
            width=80
        )
        browse_button.pack(side="left", padx=5)
        
        # Font preview
        preview_frame = ctk.CTkFrame(font_section)
        preview_frame.pack(fill="x", padx=10, pady=10)
        
        preview_label = ctk.CTkLabel(
            preview_frame,
            text="AaBbCcXxYyZz 123",
            font=("Arial", 18)
        )
        preview_label.pack(pady=10)
        
        # Function to update preview
        def update_font_preview(*args):
            selected_font = font_var.get()
            try:
                # Try to create the font for preview
                preview_label.configure(font=(selected_font, 18))
            except Exception as e:
                print(f"Error previewing font {selected_font}: {e}")
                # Fall back to default if selected font can't be loaded
                preview_label.configure(font=("Arial", 18))
                
                preview_label.configure(
                    text=f"⚠️ Font preview failed. Font may need installation.",
                    text_color="#FF8C00"  # Orange for warning
                )
                return
            
            # Reset preview text if successful
            preview_label.configure(
                text="AaBbCcXxYyZz 123",
                text_color=("black", "white")  # Default color
            )
        
        # Update preview when selection changes
        font_var.trace_add("write", update_font_preview)
        
        # Initialize preview
        update_font_preview()
        
        # Size and formatting section
        size_section = ctk.CTkFrame(main_frame)
        size_section.pack(fill="x", pady=10)
        
        ctk.CTkLabel(size_section, text="Size and Formatting", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Font size
        size_frame = ctk.CTkFrame(size_section)
        size_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(size_frame, text="Font Size:", width=100).pack(side="left", padx=5)
        
        # Get current size
        current_size = settings.get("font_size", 28)
        
        size_var = ctk.IntVar(value=current_size)
        size_slider = ctk.CTkSlider(
            size_frame,
            from_=10, 
            to=50,
            number_of_steps=40,
            variable=size_var
        )
        size_slider.pack(side="left", fill="x", expand=True, padx=5)
        
        size_label = ctk.CTkLabel(size_frame, text=str(current_size), width=30)
        size_label.pack(side="left", padx=5)
        
        def update_size_label(value):
            size_label.configure(text=str(int(value)))
        
        size_slider.configure(command=update_size_label)
        
        # Uppercase toggle
        uppercase_var = ctk.BooleanVar(value=settings.get("uppercase", True))
        uppercase_check = ctk.CTkCheckBox(
            size_section, 
            text="Use UPPERCASE text",
            variable=uppercase_var
        )
        uppercase_check.pack(anchor="w", padx=15, pady=5)
        
        # Bold strength
        bold_frame = ctk.CTkFrame(size_section)
        bold_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(bold_frame, text="Bold Strength:", width=100).pack(side="left", padx=5)
        
        current_bold = settings.get("bold_strength", 2)
        bold_var = ctk.IntVar(value=current_bold)
        bold_slider = ctk.CTkSlider(
            bold_frame,
            from_=0,
            to=5,
            number_of_steps=5,
            variable=bold_var
        )
        bold_slider.pack(side="left", fill="x", expand=True, padx=5)
        
        bold_label = ctk.CTkLabel(bold_frame, text=str(current_bold), width=30)
        bold_label.pack(side="left", padx=5)
        
        def update_bold_label(value):
            bold_label.configure(text=str(int(value)))
        
        bold_slider.configure(command=update_bold_label)
        
        # Y-offset
        offset_frame = ctk.CTkFrame(size_section)
        offset_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(offset_frame, text="Y Offset:", width=100).pack(side="left", padx=5)
        
        current_offset = settings.get("y_offset", -40)
        offset_var = ctk.IntVar(value=current_offset)
        offset_slider = ctk.CTkSlider(
            offset_frame,
            from_=-100,
            to=20,
            number_of_steps=120,
            variable=offset_var
        )
        offset_slider.pack(side="left", fill="x", expand=True, padx=5)
        
        offset_label = ctk.CTkLabel(offset_frame, text=str(current_offset), width=30)
        offset_label.pack(side="left", padx=5)
        
        def update_offset_label(value):
            offset_label.configure(text=str(int(value)))
        
        offset_slider.configure(command=update_offset_label)
        
        # Buttons frame
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        def save_settings():
            # Extract values from UI
            new_settings = {
                "font_family": font_var.get(),  # Store display name
                "font_size": int(size_var.get()),
                "uppercase": uppercase_var.get(),
                "use_uppercase": uppercase_var.get(),  # Duplicate for compatibility
                "bold_strength": int(bold_var.get()),
                "y_offset": int(offset_var.get()),
                "title_size": int(size_var.get()) + 8,  # Title size is font_size + 8
                "title_font_size": int(size_var.get()) + 8,  # Duplicate for compatibility
                # REMOVED: "font_source" setting - no longer needed
            }
            
            # Save the selected font filename
            selected_display_name = font_var.get()
            if selected_display_name in font_name_to_file:
                # Get filename that corresponds to this display name
                font_filename = font_name_to_file[selected_display_name]
                # Store this in settings for later use
                new_settings["font_filename"] = font_filename
            
            # Save settings
            self.save_text_appearance_settings(new_settings)
            
            # Update preview if requested
            if update_preview and hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
                try:
                    self.update_preview_text_appearance()
                    messagebox.showinfo(
                        "Settings Saved", 
                        "Settings saved successfully. Some font changes may require restarting the app to fully apply."
                    )
                except Exception as e:
                    messagebox.showwarning(
                        "Preview Update",
                        f"Settings saved, but preview update failed. Please restart the app to apply font changes.\n\nError: {str(e)}"
                    )
            else:
                messagebox.showinfo(
                    "Settings Saved", 
                    "Settings saved successfully. Please restart the app to apply font changes."
                )
            
            dialog.destroy()
        
        # Save button
        save_button = ctk.CTkButton(
            button_frame,
            text="Save Settings",
            command=save_settings
        )
        save_button.pack(side="left", padx=10)
        
        # Apply Button (applies without closing dialog)
        def apply_settings():
            # Extract values from UI
            new_settings = {
                "font_family": font_var.get(),
                "font_size": int(size_var.get()),
                "uppercase": uppercase_var.get(),
                "use_uppercase": uppercase_var.get(),
                "bold_strength": int(bold_var.get()),
                "y_offset": int(offset_var.get()),
                "title_size": int(size_var.get()) + 8,
                "title_font_size": int(size_var.get()) + 8
                # Removed: "font_source": font_source_var.get() 
            }
            
            # Save the selected font filename
            selected_display_name = font_var.get()
            if selected_display_name in font_name_to_file:
                font_filename = font_name_to_file[selected_display_name]
                new_settings["font_filename"] = font_filename
            
            # Save settings
            self.save_text_appearance_settings(new_settings)
            
            # Try to update preview
            if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
                try:
                    self.update_preview_text_appearance()
                    messagebox.showinfo(
                        "Settings Applied", 
                        "Settings applied to preview. Some font changes may not appear until app restart."
                    )
                except Exception as e:
                    messagebox.showwarning(
                        "Preview Update Failed",
                        f"Failed to update preview: {str(e)}\nTry restarting the app to apply font changes."
                    )
        
        # Reset button
        def reset_to_defaults():
            # Set controls to default values
            # Removed: font_source_var.set("directory")
            font_var.set("Arial")
            size_var.set(28)
            uppercase_var.set(True)
            bold_var.set(2)
            offset_var.set(-40)
            
            # Update labels
            update_size_label(28)
            update_bold_label(2)
            update_offset_label(-40)
            update_font_preview()
        
        reset_button = ctk.CTkButton(
            button_frame,
            text="Reset to Defaults",
            command=reset_to_defaults
        )
        reset_button.pack(side="left", padx=10)

    def debug_font_system(self):
        """Debug the font system and print information about available fonts in the fonts directory"""
        import os
        
        print("\n=== FONT DEBUG ===")
        
        # Check settings
        settings = self.get_text_settings(refresh=True)
        print(f"Font Family: {settings.get('font_family', 'Not set')}")
        print(f"Font Name: {settings.get('font_name', 'Not set')}")
        
        # Check fonts directory
        font_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        print(f"\nFonts Directory: {font_dir}")
        if os.path.exists(font_dir):
            print("Directory exists")
            font_files = [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf'))]
            print(f"Font files found: {len(font_files)}")
            for file in font_files:
                print(f"  - {file}")
        else:
            print("Directory does not exist")
            try:
                os.makedirs(font_dir, exist_ok=True)
                print(f"Created fonts directory: {font_dir}")
            except Exception as e:
                print(f"Error creating fonts directory: {e}")
        
        # Check for the selected font
        target = settings.get('font_family', 'Press Start 2P')
        print(f"\nSearching for font: {target}")
        found = False
        
        # Look for exact match
        for ext in ['.ttf', '.otf']:
            path = os.path.join(font_dir, f"{target}{ext}")
            if os.path.exists(path):
                print(f"Found exact match: {path}")
                found = True
                break
        
        # Look for partial match if not found
        if not found and os.path.exists(font_dir):
            target_lower = target.lower().replace(' ', '')
            for filename in os.listdir(font_dir):
                if filename.lower().startswith(target_lower) and filename.lower().endswith(('.ttf', '.otf')):
                    print(f"Found partial match: {filename}")
                    found = True
                    break
        
        if not found:
            print(f"Font '{target}' not found in fonts directory")
            print(f"Please add the font file to: {font_dir}")
        
        print("=== END FONT DEBUG ===\n")
        return True
    
    def apply_layering(self):
        """Apply proper z-order layering to all canvas elements based on settings"""
        if not hasattr(self, 'preview_canvas') or not self.preview_canvas.winfo_exists():
            return False
            
        # Get layering settings - could be stored in a settings file
        if not hasattr(self, 'layer_order'):
            # Default layering: bezel on bottom, then background, then logo, then text
            self.layer_order = {
                'bezel': 1,    # Lowest layer (furthest back)
                'background': 2,
                'logo': 3,
                'text': 4      # Highest layer (closest to front)
            }

        print(f"Applying layering with order: {self.layer_order}")

        try:
            # Get all items that we need to layer
            canvas = self.preview_canvas
            
            # Get all canvas items for reference
            all_items = canvas.find_all()
            print(f"Canvas has {len(all_items)} total items")
            
            # Background image is always at the bottom by default
            background_item = canvas.find_withtag("background_image")
            if background_item and len(background_item) > 0:
                print(f"Found background item: {background_item[0]}")
                if self.layer_order['background'] == 1:
                    canvas.lower(background_item[0])  # Send to very back
                
            # Handle bezel
            if hasattr(self, 'preview_bezel_item') and self.preview_bezel_item:
                print(f"Found bezel item: {self.preview_bezel_item}")
                # FORCE BEZEL ABOVE BACKGROUND WHEN IN STANDALONE MODE
                if not hasattr(self, 'game_list'):  # Check if we're in standalone mode
                    if background_item and len(background_item) > 0:
                        print("STANDALONE MODE: Forcing bezel above background")
                        canvas.lift(self.preview_bezel_item, background_item[0])
                else:
                    # Use regular layering in normal mode
                    if self.layer_order['bezel'] == 1:
                        canvas.lower(self.preview_bezel_item)  # Send to very back
                    elif self.layer_order['bezel'] > self.layer_order['background'] and background_item:
                        canvas.lift(self.preview_bezel_item, background_item[0])
            
            # Handle logo
            if hasattr(self, 'preview_logo_item') and self.preview_logo_item:
                # Determine what to place the logo above
                if self.layer_order['logo'] > self.layer_order['bezel'] and hasattr(self, 'preview_bezel_item'):
                    canvas.lift(self.preview_logo_item, self.preview_bezel_item)
                elif self.layer_order['logo'] > self.layer_order['background'] and background_item:
                    canvas.lift(self.preview_logo_item, background_item[0])
                elif self.layer_order['logo'] == 1:
                    canvas.lower(self.preview_logo_item)
                    
            # Text items should typically be on top
            if self.layer_order['text'] == 4 and hasattr(self, 'text_items'):
                for control_name, data in self.text_items.items():
                    if 'text' in data:
                        canvas.lift(data['text'])  # Bring text to front
                    if 'shadow' in data and data['shadow']:
                        canvas.lift(data['shadow'])  # Bring shadow to front (but behind text)
                        canvas.lower(data['shadow'], data['text'])  # Ensure shadow is behind text
            
            return True
        except Exception as e:
            print(f"Error applying layering: {e}")
            return False
    
    def show_layer_settings_dialog(self):
        """Show dialog to configure layer ordering"""
        if not hasattr(self, 'layer_order'):
            # Default layering: bezel on bottom, then background, then logo, then text
            self.layer_order = {
                'bezel': 1,    # Lowest layer (furthest back)
                'background': 2,
                'logo': 3,
                'text': 4      # Highest layer (closest to front)
            }
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Layer Order Settings")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Create sliders for each element
        ctk.CTkLabel(dialog, text="Layer Order Settings", font=("Arial", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(dialog, text="Drag sliders to adjust layer order (higher = in front)").pack(pady=(0, 20))
        
        # Create variables to store slider values
        bezel_var = ctk.IntVar(value=self.layer_order['bezel'])
        bg_var = ctk.IntVar(value=self.layer_order['background'])
        logo_var = ctk.IntVar(value=self.layer_order['logo'])
        text_var = ctk.IntVar(value=self.layer_order['text'])
        
        # Create slider frames
        slider_frame = ctk.CTkFrame(dialog)
        slider_frame.pack(fill="x", padx=20, pady=10)
        
        # Add sliders with labels
        def create_slider(parent, label, variable):
            row = ctk.CTkFrame(parent)
            row.pack(fill="x", pady=5)
            
            ctk.CTkLabel(row, text=f"{label}:", width=100).pack(side="left", padx=(0, 10))
            
            slider = ctk.CTkSlider(
                row,
                from_=1,
                to=4,
                number_of_steps=3,
                variable=variable
            )
            slider.pack(side="left", fill="x", expand=True, padx=5)
            
            value_label = ctk.CTkLabel(row, text=str(variable.get()), width=30)
            value_label.pack(side="left", padx=(10, 0))
            
            # Update value label when slider changes
            def update_value(_):
                value_label.configure(text=str(int(variable.get())))
            
            slider.configure(command=update_value)
            
            return slider
        
        bezel_slider = create_slider(slider_frame, "Bezel", bezel_var)
        bg_slider = create_slider(slider_frame, "Background", bg_var)
        logo_slider = create_slider(slider_frame, "Logo", logo_var)
        text_slider = create_slider(slider_frame, "Text", text_var)
        
        # Buttons frame
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(pady=20, fill="x")
        
        def apply_layer_changes():
            # Update layer order
            self.layer_order = {
                'bezel': int(bezel_var.get()),
                'background': int(bg_var.get()),
                'logo': int(logo_var.get()),
                'text': int(text_var.get())
            }
            
            # Save settings
            success = self.save_layer_settings()
            if success:
                print("Layer settings saved successfully")
            else:
                print("Failed to save layer settings")
            
            # Apply the new layering
            self.apply_layering()
            
            dialog.destroy()
        
        apply_button = ctk.CTkButton(
            button_frame,
            text="Apply",
            command=apply_layer_changes
        )
        apply_button.pack(side="left", padx=20)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        )
        cancel_button.pack(side="right", padx=20)
    
    def save_layer_settings(self):
        """Save layer order settings to file using the centralized path"""
        if not hasattr(self, 'mame_dir') or not self.mame_dir:
            print("Error: Cannot save layer settings - mame_dir not set")
            return
                
        settings_path = self.get_settings_path("layer")
        
        try:
            # Make sure we have a layer_order to save
            if not hasattr(self, 'layer_order'):
                self.layer_order = {
                    'bezel': 1,    # Lowest layer (furthest back)
                    'background': 2,
                    'logo': 3,
                    'text': 4      # Highest layer (closest to front)
                }
                    
            with open(settings_path, 'w') as f:
                json.dump(self.layer_order, f)
            print(f"Saved layer settings: {self.layer_order}")
            return True
        except Exception as e:
            print(f"Error saving layer settings: {e}")
            return False

    def load_layer_settings(self):
        """Load layer order settings from file using the centralized path"""
        if not hasattr(self, 'mame_dir') or not self.mame_dir:
            print("Cannot load layer settings - mame_dir not set")
            # Set default layer order
            self.layer_order = {
                'bezel': 2,    # Lowest layer (furthest back)
                'background': 1,
                'logo': 3,
                'text': 4      # Highest layer (closest to front)
            }
            return
        
        settings_path = self.get_settings_path("layer")
        
        # Default settings
        default_order = {
            'bezel': 2,    # Lowest layer (furthest back)
            'background': 1,
            'logo': 3,
            'text': 4      # Highest layer (closest to front)
        }
        
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    # Validate the settings format
                    required_keys = ['bezel', 'background', 'logo', 'text']
                    if all(key in saved_settings for key in required_keys):
                        self.layer_order = saved_settings
                        print(f"Loaded layer settings: {self.layer_order}")
                    else:
                        print("Invalid layer settings format, using defaults")
                        self.layer_order = default_order
            else:
                print("Layer settings file not found, using defaults")
                self.layer_order = default_order
                # Create the file with defaults
                self.save_layer_settings()
        except Exception as e:
            print(f"Error loading layer settings: {e}")
            self.layer_order = default_order
    
    def get_bezel_path(self, rom_name):
        """Find bezel path for a given ROM with custom path priority"""
        import os
        
        # Define potential bezel locations with new priority order
        bezel_paths = [
            # Primary path in autochanger/BezelNight directory
            os.path.join(self.mame_dir, "..", "..", "autochanger", "BezelNight", rom_name, "Bezel.png"),
            
            # Fallbacks in artwork directory
            os.path.join(self.mame_dir, "artwork", rom_name, "Bezel.png"),
            os.path.join(self.mame_dir, "artwork", rom_name, "bezel.png"),
            
            # Secondary paths
            os.path.join(self.mame_dir, "bezels", f"{rom_name}.png"),
            os.path.join(self.mame_dir, "preview", "bezels", f"{rom_name}.png"),
            
            # Default fallback bezel
            os.path.join(self.mame_dir, "artwork", "default", "Bezel.png"),
            os.path.join(self.mame_dir, "bezels", "default.png")
        ]
        
        print(f"Looking for bezel for {rom_name}")
        
        # Check each location
        for bezel_path in bezel_paths:
            norm_path = os.path.normpath(bezel_path)
            if os.path.exists(norm_path):
                print(f"Found bezel: {norm_path}")
                return norm_path
        
        print(f"No bezel found for {rom_name}")
        return None

    def load_bezel_settings(self):
        """Load bezel visibility settings using the centralized path"""
        settings_path = self.get_settings_path("bezel")
        
        # Default settings
        self.bezel_visible = True  # Visible by default
        
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    
                    # Only update if explicitly set
                    if 'bezel_visible' in saved_settings:
                        self.bezel_visible = bool(saved_settings['bezel_visible'])
            else:
                # Create default settings file if it doesn't exist
                settings = {'bezel_visible': True}
                with open(settings_path, 'w') as f:
                    json.dump(settings, f)
        except Exception as e:
            print(f"Error loading bezel settings: {e}")
            self.bezel_visible = True
                
        print(f"Loaded bezel settings: visible={self.bezel_visible}")
        return {'bezel_visible': self.bezel_visible}

    def save_bezel_settings(self):
        """Save bezel visibility settings using the centralized path"""
        settings_path = self.get_settings_path("bezel")
        
        try:
            # Load existing settings or create new
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            
            # Update with current bezel visibility
            settings['bezel_visible'] = self.bezel_visible
            
            # Save settings
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
                
            print(f"Saved bezel settings: visible={self.bezel_visible}")
        except Exception as e:
            print(f"Error saving bezel settings: {e}")

    def toggle_bezel_visibility(self):
        """Toggle bezel visibility in preview"""
        print("\n=== Toggling bezel visibility ===")
        
        # Toggle state
        old_value = getattr(self, 'bezel_visible', True)
        self.bezel_visible = not old_value
        print(f"Bezel visibility changed from {old_value} to {self.bezel_visible}")
        
        # Update button text if it exists
        if hasattr(self, 'bezel_toggle_button') and self.bezel_toggle_button.winfo_exists():
            toggle_text = "Hide Bezel" if self.bezel_visible else "Show Bezel"
            self.bezel_toggle_button.configure(text=toggle_text)
            print(f"Updated button text to: {toggle_text}")
        
        # Update canvas bezel
        if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
            if self.bezel_visible:
                # Add bezel to canvas
                success = self.add_bezel_to_preview_canvas()
                print(f"Bezel add attempt result: {success}")
            else:
                # Remove bezel if it exists
                if hasattr(self, 'preview_bezel_item') and self.preview_bezel_item:
                    try:
                        self.preview_canvas.delete(self.preview_bezel_item)
                        print("Removed bezel from canvas")
                        self.preview_bezel_item = None
                        self.preview_bezel_photo = None
                    except Exception as e:
                        print(f"Error removing bezel: {e}")
        
        # Save the setting
        self.save_bezel_settings()
        print("=== Toggle bezel complete ===\n")

    def add_bezel_to_preview_canvas(self):
        """Add bezel to the preview canvas with proper z-order control"""
        print("\n=== Starting add_bezel_to_preview_canvas ===")
        
        try:
            # Make sure we have a canvas
            if not hasattr(self, 'preview_canvas') or not self.preview_canvas.winfo_exists():
                print("No preview canvas available")
                return False
                
            # Check if bezel visibility is enabled
            if not hasattr(self, 'bezel_visible') or not self.bezel_visible:
                print("Bezel visibility is disabled")
                return False
                
            # First remove any existing bezel
            if hasattr(self, 'preview_bezel_item') and self.preview_bezel_item:
                print("Removing existing bezel item")
                try:
                    self.preview_canvas.delete(self.preview_bezel_item)
                except Exception as e:
                    print(f"Error removing existing bezel: {e}")
                self.preview_bezel_item = None
                self.preview_bezel_photo = None
            
            # Make sure we have a game selected
            if not hasattr(self, 'current_game') or not self.current_game:
                print("No current game selected")
                return False
            
            # Get the bezel path
            bezel_path = self.get_bezel_path(self.current_game)
            if not bezel_path:
                print(f"No bezel found for {self.current_game}")
                return False
                
            print(f"Found bezel path: {bezel_path}")
            
            # Load the bezel
            from PIL import Image, ImageTk
            try:
                bezel_img = Image.open(bezel_path)
                print(f"Loaded bezel image: {bezel_img.size} {bezel_img.mode}")
            except Exception as e:
                print(f"Error loading bezel image: {e}")
                return False
            
            # Get canvas dimensions
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            print(f"Canvas size: {canvas_width}x{canvas_height}")
            
            # If canvas size is too small, use reasonable defaults
            if canvas_width <= 1 or canvas_height <= 1:
                if hasattr(self, 'preview_window'):
                    # Try window size
                    canvas_width = self.preview_window.winfo_width()
                    canvas_height = self.preview_window.winfo_height()
                    print(f"Using window size: {canvas_width}x{canvas_height}")
                    
                    # If still invalid, use defaults
                    if canvas_width <= 1 or canvas_height <= 1:
                        canvas_width = 1920
                        canvas_height = 1080
                        print(f"Using default size: {canvas_width}x{canvas_height}")
                else:
                    canvas_width = 1920
                    canvas_height = 1080
                    print(f"Using default size: {canvas_width}x{canvas_height}")
            
            # Resize bezel to fit canvas exactly
            bezel_img = bezel_img.resize((canvas_width, canvas_height), Image.LANCZOS)
            print(f"Resized bezel to: {canvas_width}x{canvas_height}")
            
            # Convert to PhotoImage for Tkinter
            photo = ImageTk.PhotoImage(bezel_img)
            
            # Create the bezel image on the canvas
            img_item = self.preview_canvas.create_image(0, 0, image=photo, anchor="nw")
            
            # Store references
            self.preview_bezel_photo = photo  # Keep reference to prevent garbage collection
            self.preview_bezel_item = img_item
            
            # Apply the layering based on the setting
            self.apply_layering()
            
            print(f"Successfully added bezel to preview canvas")
            return True
                
        except Exception as e:
            print(f"Error in add_bezel_to_preview_canvas: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_bezel_to_image(self, image, rom_name):
        """Add bezel to the image for saving"""
        import os
        from PIL import Image
        
        # Load bezel settings if not already loaded
        if not hasattr(self, 'bezel_visible'):
            self.load_bezel_settings()
        
        # If bezel is set to hidden, return the original image
        if not self.bezel_visible:
            print(f"Bezel visibility is off, skipping bezel for {rom_name}")
            return image
        
        # Get bezel path
        bezel_path = self.get_bezel_path(rom_name)
        if not bezel_path:
            print(f"No bezel found for {rom_name}, returning original image")
            return image  # Return original if no bezel found
        
        try:
            # Open bezel image
            print(f"Opening bezel file: {bezel_path}")
            bezel_img = Image.open(bezel_path)
            print(f"Bezel image opened successfully: {bezel_img.size} {bezel_img.mode}")
            
            # Resize bezel to match the image size
            img_width, img_height = image.size
            bezel_img = bezel_img.resize((img_width, img_height), Image.LANCZOS)
            
            # Make sure bezel has alpha channel for transparency
            if bezel_img.mode != 'RGBA':
                print(f"Converting bezel from {bezel_img.mode} to RGBA")
                bezel_img = bezel_img.convert('RGBA')
            
            # Convert the game image to RGBA if it's not already
            if image.mode != 'RGBA':
                print(f"Converting game image from {image.mode} to RGBA")
                image = image.convert('RGBA')
            
            # IMPORTANT CHANGE: Properly layer the bezel
            # First create a new transparent base image
            result = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            
            # Get layer ordering - use defaults if not defined
            layer_order = getattr(self, 'layer_order', {
                'bezel': 1,       # Lowest layer (furthest back)
                'background': 2,
                'logo': 3,
                'text': 4         # Highest layer (closest to front)
            })
            
            # Check if bezel should be the bottom layer
            if layer_order['bezel'] < layer_order['background']:
                # Paste bezel first (bottom layer)
                result.paste(bezel_img, (0, 0), bezel_img)
                # Then paste game image on top
                result.paste(image, (0, 0), image)
            else:
                # Paste game image first
                result.paste(image, (0, 0), image)
                # Then paste bezel on top
                result.paste(bezel_img, (0, 0), bezel_img)
            
            # Convert back to RGB for compatibility
            result = result.convert('RGB')
            
            print(f"Bezel successfully composited with image for {rom_name}")
            return result
        
        except Exception as e:
            print(f"Error adding bezel for {rom_name}: {e}")
            import traceback
            traceback.print_exc()
            return image  # Return original on error
    
    def get_logo_path(self, rom_name):
        """Find logo path for a given ROM with support for relative and external paths"""
        import os
        
        # First try the local directories
        local_paths = [
            os.path.join(self.mame_dir, "logos"),
            os.path.join(self.mame_dir, "preview", "logos"),
            os.path.join(self.mame_dir, "artwork", "logos"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos")
        ]
        
        # Then try your specific path structure
        # Handle relative paths from MAME directory
        relative_path = os.path.join(self.mame_dir, "..", "..", "collections", "Arcades", "medium_artwork", "logo")
        absolute_path = os.path.abspath(relative_path)
        
        # Add your specific paths to the search list
        specific_paths = [
            absolute_path,  # Try the normalized absolute path first
            "..\\..\\collections\\Arcades\\medium_artwork\\logo",  # Raw relative path with backslashes
            os.path.join(self.mame_dir, "..\\..\\collections\\Arcades\\medium_artwork\\logo")  # Combined with MAME dir
        ]
        
        # Combine all paths, with preference to local paths first
        all_paths = local_paths + specific_paths
        
        print(f"Looking for logo for {rom_name} in multiple directories")
        
        # Check each directory for the logo
        for logo_dir in all_paths:
            try:
                # Normalize path slashes for Windows
                norm_dir = os.path.normpath(logo_dir)
                
                if os.path.exists(norm_dir):
                    print(f"Checking logo directory: {norm_dir}")
                    
                    # Try exact match with various extensions
                    for ext in ['.png', '.jpg', '.jpeg']:
                        logo_path = os.path.join(norm_dir, f"{rom_name}{ext}")
                        norm_path = os.path.normpath(logo_path)
                        
                        if os.path.exists(norm_path):
                            print(f"Found logo: {norm_path}")
                            return norm_path
            except Exception as e:
                print(f"Error checking path {logo_dir}: {e}")
        
        print(f"No logo found for {rom_name} in any directory")
        return None

    def add_logo_controls_to_preview(self):
        """Add controls for logo visibility and positioning in the preview window with detailed debugging"""
        print("\n--- ADDING LOGO CONTROLS TO PREVIEW ---")
        
        if not hasattr(self, 'button_row2'):
            print("ERROR: button_row2 attribute does not exist")
            return
            
        if not self.button_row2.winfo_exists():
            print("ERROR: button_row2 widget does not exist")
            return
        
        print("Found button_row2, adding logo controls")
        
        # Add Logo visibility toggle button
        self.logo_visible = True  # Default to visible
        try:
            self.logo_toggle_button = ctk.CTkButton(
                self.button_row2,
                text="Hide Logo",
                command=self.toggle_logo_visibility,
                width=90  # Match other buttons
            )
            self.logo_toggle_button.pack(side="left", padx=3)
            print("Successfully added logo toggle button")
        except Exception as e:
            print(f"ERROR creating logo toggle button: {e}")
            import traceback
            traceback.print_exc()
        
        # Add Logo position button (opens position dialog)
        try:
            self.logo_position_button = ctk.CTkButton(
                self.button_row2,
                text="Logo Pos",
                command=self.show_logo_position_dialog,
                width=90  # Match other buttons
            )
            self.logo_position_button.pack(side="left", padx=3)
            print("Successfully added logo position button")
        except Exception as e:
            print(f"ERROR creating logo position button: {e}")
            import traceback
            traceback.print_exc()
        
        print("--- LOGO CONTROLS ADDED ---\n")

    # Direct method to manually add the logo controls - can be called from anywhere
    def manually_add_logo_controls(self):
        """Method that can be manually called to add logo controls"""
        print("Manually adding logo controls")
        
        # Make sure button_row2 exists
        if hasattr(self, 'button_row2') and self.button_row2.winfo_exists():
            print("Found button_row2, adding logo controls")
            
            # Clear existing logo controls if they exist
            if hasattr(self, 'logo_toggle_button') and self.logo_toggle_button.winfo_exists():
                self.logo_toggle_button.destroy()
            if hasattr(self, 'logo_position_button') and self.logo_position_button.winfo_exists():
                self.logo_position_button.destroy()
            
            # Load logo settings
            self.load_logo_settings()
            
            # Create the toggle button
            self.logo_toggle_button = ctk.CTkButton(
                self.button_row2,
                text="Hide Logo" if self.logo_visible else "Show Logo",
                command=self.toggle_logo_visibility,
                width=90
            )
            self.logo_toggle_button.pack(side="left", padx=3)
            
            # Create the position button
            self.logo_position_button = ctk.CTkButton(
                self.button_row2,
                text="Logo Pos",
                command=self.show_logo_position_dialog,
                width=90
            )
            self.logo_position_button.pack(side="left", padx=3)
            
            print("Logo controls added successfully")
        else:
            print("button_row2 not found!")

    def toggle_logo_visibility(self):
        """Toggle the visibility of the logo in preview with improved reliability"""
        print("\n=== Toggling logo visibility ===")
        
        # Toggle the state
        old_value = getattr(self, 'logo_visible', True)
        self.logo_visible = not old_value
        print(f"Logo visibility changed from {old_value} to {self.logo_visible}")
        
        # Update the button text if it exists
        if hasattr(self, 'logo_toggle_button') and self.logo_toggle_button.winfo_exists():
            toggle_text = "Hide Logo" if self.logo_visible else "Show Logo"
            self.logo_toggle_button.configure(text=toggle_text)
            print(f"Updated button text to: {toggle_text}")
        
        # Update canvas logo
        if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
            if self.logo_visible:
                # Force add logo
                success = self.add_logo_to_preview_canvas()
                print(f"Logo add attempt result: {success}")
            else:
                # Remove logo if it exists
                if hasattr(self, 'preview_logo_item') and self.preview_logo_item:
                    try:
                        self.preview_canvas.delete(self.preview_logo_item)
                        print("Removed logo from canvas")
                        self.preview_logo_item = None
                        self.preview_logo_photo = None
                    except Exception as e:
                        print(f"Error removing logo: {e}")
        
        # Save the setting
        self.save_logo_settings()
        print(f"Saved logo settings, visibility={self.logo_visible}")
        print("=== Toggle logo complete ===\n")

    def show_logo_position_dialog(self):
        """Show dialog to configure logo position and Y offset"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Logo Position Settings")
        dialog.geometry("400x360")  # Make it taller for the new control
        dialog.transient(self)
        dialog.grab_set()
        
        # Load current settings
        if not hasattr(self, 'logo_position'):
            self.load_logo_settings()
        
        # Create position options
        position_var = ctk.StringVar(value=self.logo_position)
        
        # Create radio buttons for position options
        ctk.CTkLabel(dialog, text="Logo Position:", font=("Arial", 14, "bold")).pack(pady=(20, 10))
        
        positions = [
            ("Top Left", "top-left"),
            ("Top Center", "top-center"),
            ("Top Right", "top-right"),
            ("Bottom Left", "bottom-left"),
            ("Bottom Center", "bottom-center"),
            ("Bottom Right", "bottom-right")
        ]
        
        # Frame for radio buttons
        radio_frame = ctk.CTkFrame(dialog)
        radio_frame.pack(fill="x", padx=20, pady=5)
        
        # Create two columns of radio buttons for better layout
        for i, (text, value) in enumerate(positions):
            row = i % 3
            col = i // 3
            radio = ctk.CTkRadioButton(
                radio_frame,
                text=text,
                variable=position_var,
                value=value
            )
            radio.grid(row=row, column=col, sticky="w", padx=10, pady=5)
        
        # Add Y offset slider
        offset_frame = ctk.CTkFrame(dialog)
        offset_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(offset_frame, text="Y Position Offset:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 5))
        
        offset_var = ctk.IntVar(value=getattr(self, 'logo_y_offset', 0))
        
        # Display current value
        value_label = ctk.CTkLabel(offset_frame, text=f"Current: {offset_var.get()} pixels")
        value_label.pack(anchor="w", pady=(0, 5))
        
        # Add slider
        def update_offset_label(value):
            offset_var.set(int(value))
            value_label.configure(text=f"Current: {offset_var.get()} pixels")
        
        slider = ctk.CTkSlider(
            offset_frame,
            from_=-100,  # Allow negative values to move up
            to=100,
            number_of_steps=200,
            command=update_offset_label
        )
        slider.set(offset_var.get())  # Set initial value
        slider.pack(fill="x", pady=5)
        
        # Buttons frame
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(pady=20, fill="x")
        
        def apply_settings():
            # Store old values for comparison
            old_position = self.logo_position
            old_offset = getattr(self, 'logo_y_offset', 0)
            
            # Update with new values
            self.logo_position = position_var.get()
            self.logo_y_offset = offset_var.get()
            print(f"Changed logo position from {old_position} to {self.logo_position}")
            print(f"Changed logo Y offset from {old_offset} to {self.logo_y_offset}")
            
            # Update logo on canvas immediately
            if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
                self.add_logo_to_preview_canvas()
            
            self.save_logo_settings()
            dialog.destroy()
        
        apply_button = ctk.CTkButton(
            button_frame,
            text="Apply",
            command=apply_settings
        )
        apply_button.pack(side="left", padx=20)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        )
        cancel_button.pack(side="right", padx=20)

    def save_logo_settings(self):
        """Save logo settings to config file using the centralized path"""
        settings_path = self.get_settings_path("logo")
        
        try:
            # Load existing settings if available
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            
            # Update with current settings
            settings['logo_visible'] = self.logo_visible
            if hasattr(self, 'logo_position'):
                settings['logo_position'] = self.logo_position
            if hasattr(self, 'logo_y_offset'):
                settings['logo_y_offset'] = self.logo_y_offset
            
            # Save back to file
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
            
            print(f"Saved logo settings: {settings}")
        except Exception as e:
            print(f"Error saving logo settings: {e}")

    def load_logo_settings(self):
        """Load logo settings from config file using the centralized path"""
        settings_path = self.get_settings_path("logo")
        
        # Default settings - explicitly set logo_visible to True by default
        self.logo_visible = True  # Set it directly first
        self.logo_position = 'top-left'  # Default position
        self.logo_y_offset = 0  # Default Y offset (no adjustment)
        
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    # Only update if the setting exists and is explicitly False
                    if 'logo_visible' in saved_settings:
                        self.logo_visible = bool(saved_settings['logo_visible'])
                    if 'logo_position' in saved_settings:
                        self.logo_position = saved_settings['logo_position']
                    if 'logo_y_offset' in saved_settings:
                        self.logo_y_offset = int(saved_settings['logo_y_offset'])
            else:
                # If no settings file exists, create one with defaults
                settings = {
                    'logo_visible': True,
                    'logo_position': 'top-left',
                    'logo_y_offset': 0
                }
                with open(settings_path, 'w') as f:
                    json.dump(settings, f)
        except Exception as e:
            print(f"Error loading logo settings: {e}")
            # Ensure defaults are set even on error
            self.logo_visible = True
            self.logo_position = 'top-left'
            self.logo_y_offset = 0
        
        print(f"Loaded logo settings: visible={self.logo_visible}, position={self.logo_position}, y_offset={self.logo_y_offset}")
        return {'logo_visible': self.logo_visible, 'logo_position': self.logo_position, 'logo_y_offset': self.logo_y_offset}

    def add_logo_to_image(self, image, rom_name, max_width=None, max_height=None):
        """Add logo to the image if available and visible according to settings"""
        import os
        from PIL import Image
        
        # Load logo settings if not already loaded
        if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
            self.load_logo_settings()
        
        # If logo is set to hidden, return the original image
        if not self.logo_visible:
            print(f"Logo visibility is off, skipping logo for {rom_name}")
            return image
        
        # Get logo path
        logo_path = self.get_logo_path(rom_name)
        if not logo_path:
            print(f"No logo found for {rom_name}, returning original image")
            return image  # Return original image if no logo found
        
        try:
            # Open logo image and ensure it has transparency support
            print(f"Opening logo file: {logo_path}")
            logo_img = Image.open(logo_path)
            print(f"Logo image opened successfully: {logo_img.size} {logo_img.mode}")
            
            # Convert to RGBA if it's not already for transparency support
            if logo_img.mode != 'RGBA':
                logo_img = logo_img.convert('RGBA')
                print(f"Converted logo to RGBA for transparency")
            
            # Default max dimensions if not specified - use consistent class variables
            if max_width is None:
                max_width = int(image.width * (self.logo_width_percentage / 100))
            if max_height is None:
                max_height = int(image.height * (self.logo_height_percentage / 100))
            
            # Calculate scale to fit within max dimensions while maintaining aspect ratio
            logo_width, logo_height = logo_img.size
            scale_factor = min(max_width / max(logo_width, 1), max_height / max(logo_height, 1))
            
            # Resize logo
            new_width = max(int(logo_width * scale_factor), 1)
            new_height = max(int(logo_height * scale_factor), 1)
            print(f"Resizing logo from {logo_width}x{logo_height} to {new_width}x{new_height}")
            logo_img = logo_img.resize((new_width, new_height), Image.LANCZOS)
            
            # Calculate position based on logo_position setting
            padding = 20  # Padding from edges
            
            # Get the image dimensions
            img_width, img_height = image.size
            
            # Get Y offset (default to 0 if not set)
            y_offset = getattr(self, 'logo_y_offset', 0)
            
            # Calculate position based on setting - ensuring consistent Y offset handling
            if self.logo_position == 'top-left':
                position = (padding, padding + y_offset)
            elif self.logo_position == 'top-center':
                position = ((img_width - new_width) // 2, padding + y_offset)
            elif self.logo_position == 'top-right':
                position = (img_width - new_width - padding, padding + y_offset)
            elif self.logo_position == 'bottom-left':
                position = (padding, img_height - new_height - padding + y_offset)
            elif self.logo_position == 'bottom-center':
                position = ((img_width - new_width) // 2, img_height - new_height - padding + y_offset)
            elif self.logo_position == 'bottom-right':
                position = (img_width - new_width - padding, img_height - new_height - padding + y_offset)
            else:  # Default to top-center
                position = ((img_width - new_width) // 2, padding + y_offset)
            
            print(f"Placing logo at position: {position} ({self.logo_position} with Y offset: {y_offset})")
            
            # Create a copy of the image to avoid modifying the original
            # Ensure it's in RGBA mode for proper compositing
            if image.mode != 'RGBA':
                result = image.convert('RGBA')
            else:
                result = image.copy()
            
            # Paste logo onto image, respecting transparency
            result.paste(logo_img, position, logo_img)
            
            print(f"Logo successfully added to image for {rom_name}")
            return result
        
        except Exception as e:
            print(f"Error adding logo for {rom_name}: {e}")
            import traceback
            traceback.print_exc()
            return image  # Return original image on error

    def test_logo_functionality(self):
        """Test function to verify logo loading and display"""
        import os
        from PIL import Image
        
        print("\n--- LOGO TEST STARTING ---")
        if not hasattr(self, 'current_game') or not self.current_game:
            print("No game selected, using test game")
            test_game = "sf2"  # Example game with likely logo
        else:
            test_game = self.current_game
            
        print(f"Testing logo functionality for: {test_game}")
        
        # Create a test image
        test_img = Image.new('RGB', (1920, 1080), color='black')
        
        # Try to add logo
        print("Attempting to add logo...")
        result = self.add_logo_to_image(test_img, test_game)
        
        if result is test_img:
            print("Logo was NOT added (same image returned)")
        else:
            print("Logo was potentially added (different image returned)")
            
        print("--- LOGO TEST COMPLETE ---\n")

    '''def get_text_settings(self):
        """Central place for all text appearance settings"""
        return {
            "font_name": "ScoutCond-Bold",  # Base filename without extension
            "font_size": 42,                # Regular text size
            "title_size": 36,               # Title text size
            "uppercase": True,              # Whether to use uppercase
            "bold_strength": 2,             # Shadow effect (0-3)
            "y_offset": -30                 # Y-position adjustment
        }
        
        # 2. Replace the load_text_appearance_settings method
        def load_text_appearance_settings(self):
            """Load fixed text appearance settings"""
            return {
                "font_family": "Press Start 2P",
                "font_size": 28,
                "title_font_size": 36,
                "bold_strength": 2,
                "y_offset": -40,
                "use_uppercase": True
            }'''
    
    def get_default_font_settings(self):
        """
        Returns default font settings - single source of truth for font defaults
        """
        return {
            "font_family": "Arial",  # The font family name for display
            "font_size": 28,              # Regular font size
            "title_size": 36,             # Title text size
            "title_font_size": 36,  # Duplicate for compatibility
            "uppercase": True,            # Whether to use uppercase text
            "use_uppercase": True,        # Duplicate for compatibility
            "bold_strength": 2,           # Shadow effect (0-3)
            "y_offset": -40               # Y-position adjustment
        }

    def get_text_settings(self, refresh=False):
        """Central source of truth for all text appearance settings with file loading"""
        # You can keep cached settings if refresh=False for performance
        if not hasattr(self, '_text_settings_cache') or refresh:
            # Start with defaults
            self._text_settings_cache = self.get_default_font_settings()
            
            # Try to load from file
            settings_path = self.get_settings_path("text")
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, 'r') as f:
                        loaded_settings = json.load(f) 
                        # Update with loaded values but keep defaults for missing keys
                        self._text_settings_cache.update(loaded_settings)
                    print(f"Loaded text appearance settings from: {settings_path}")
                except Exception as e:
                    print(f"Error loading text settings: {e}")
                        
        return self._text_settings_cache

    def ensure_font_available(self):
        """Ensure font is available in the application directory"""
        import os
        
        # Get font settings
        settings = self.get_text_settings()
        font_family = settings.get("font_family")
        
        # Check for the font file
        font_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        os.makedirs(font_dir, exist_ok=True)
        
        # Look for the font file with the exact name
        for ext in ['.ttf', '.otf']:
            font_path = os.path.join(font_dir, f"{font_family}{ext}")
            if os.path.exists(font_path):
                print(f"Font file found: {font_path}")
                return True
        
        # Look for font files that start with the font name (ignoring case)
        font_name_lower = font_family.lower().replace(' ', '')
        for filename in os.listdir(font_dir):
            if filename.lower().startswith(font_name_lower) and filename.lower().endswith(('.ttf', '.otf')):
                print(f"Found font file with partial match: {filename}")
                return True
        
        print(f"Font '{font_family}' not found")
        print(f"The application will attempt to use a system font.")
        
        # Check if we have any fonts at all in the folder - just log, don't warn
        fonts_found = False
        for filename in os.listdir(font_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                fonts_found = True
                break
                
        if not fonts_found:
            # No fonts found, just log it without showing any warning dialog
            print(f"No font files found in fonts directory: {font_dir}")
        
        return False
        
    def is_system_font(self, font_name):
        """Check if a font exists in our fonts directory"""
        fonts_dir = os.path.join(self.mame_dir, "preview", "settings", "fonts")
        if not os.path.exists(fonts_dir):
            return False
        
        # Look for exact match
        for ext in ['.ttf', '.otf']:
            if os.path.exists(os.path.join(fonts_dir, f"{font_name}{ext}")):
                return True
        
        # Look for partial match
        font_name_lower = font_name.lower().replace(' ', '')
        for filename in os.listdir(fonts_dir):
            if filename.lower().startswith(font_name_lower) and filename.lower().endswith(('.ttf', '.otf')):
                return True
        
        return False
    
    def should_show_rom_info(self):
        """Helper method to determine if ROM info should be displayed"""
        return getattr(self, 'show_rom_info', False)
    
    def is_control_visible(self, control_name):
        """Check if a control should be visible based on visible_control_types setting"""
        # Always show joystick controls that are custom mapped
        if "JOYSTICK" in control_name and hasattr(self, 'current_game'):
            # Check if this game has a custom mapping for this control
            if self.current_game in self.custom_configs:
                cfg_controls = self.parse_cfg_controls(self.custom_configs[self.current_game])
                if control_name in cfg_controls:
                    return True  # Always show custom-mapped joystick controls
        
        # Normal visibility check based on control types
        for control_type in self.visible_control_types:
            if control_type in control_name:
                return True
        
        return False
    
    def create_text_with_shadow(self, canvas, x, y, text, font=None, shadow_offset=2, anchor="nw"):
        """Create text with shadow effect for better visibility"""
        # Get shadow offset from bold strength if available
        if hasattr(self, 'get_text_settings'):
            settings = self.get_text_settings()
            bold_strength = settings.get('bold_strength', 2)
            shadow_offset = max(1, min(bold_strength, 3))
        
        # If bold_strength is 0, don't create a shadow
        if shadow_offset == 0:
            text_item = canvas.create_text(
                x, y, 
                text=text, 
                font=font, 
                fill="white",
                anchor=anchor  # Use the provided anchor parameter
            )
            return text_item, None
        
        # Create shadow text
        shadow = canvas.create_text(
            x + shadow_offset, 
            y + shadow_offset, 
            text=text, 
            font=font, 
            fill="black",
            anchor=anchor  # Use the provided anchor parameter
        )
        
        # Create main text
        text_item = canvas.create_text(
            x, y, 
            text=text, 
            font=font, 
            fill="white",
            anchor=anchor  # Use the provided anchor parameter
        )
        
        return text_item, shadow
    
    def get_settings_path(self, file_type, rom_name=None, create_dirs=True):
        """
        Centralized function to handle settings file paths without legacy checks
        """
        import os
        
        # Base directory for all settings
        settings_base = os.path.join(self.mame_dir, "preview", "settings")
        
        # Create base settings directory if it doesn't exist
        if create_dirs and not os.path.exists(settings_base):
            os.makedirs(settings_base)
        
        # Define paths for each type of settings file
        if file_type == "general":
            # General application settings
            return os.path.join(settings_base, "control_config_settings.json")
        
        elif file_type == "text":
            # Text appearance settings
            return os.path.join(settings_base, "text_appearance_settings.json")
        
        elif file_type.startswith("positions"):
            # Extract suffix if present (e.g., "positions_no_names")
            suffix = file_type.replace("positions", "")
            
            # Positions files directory
            positions_dir = os.path.join(settings_base, "positions")
            if create_dirs and not os.path.exists(positions_dir):
                os.makedirs(positions_dir)
                
            if rom_name:
                # Game-specific positions
                return os.path.join(positions_dir, f"{rom_name}_positions{suffix}.json")
            else:
                # Global positions
                return os.path.join(positions_dir, f"global_positions{suffix}.json")
        
        elif file_type == "logo":
            # Logo settings
            return os.path.join(settings_base, "logo_settings.json")
        
        elif file_type == "bezel":
            # Bezel settings
            return os.path.join(settings_base, "bezel_settings.json")
        
        elif file_type == "layer":
            # Layer order settings
            return os.path.join(settings_base, "layer_settings.json")
        
        elif file_type == "custom_controls":
            # Custom controls directory
            custom_dir = os.path.join(settings_base, "custom_controls")
            if create_dirs and not os.path.exists(custom_dir):
                os.makedirs(custom_dir)
                
            if rom_name:
                return os.path.join(custom_dir, f"{rom_name}.json")
            else:
                return custom_dir
        
        # You can add more types as needed
        return None
        
        # Legacy path fallback (for compatibility with existing installations)
        # This allows a smooth transition by checking old locations if file doesn't exist in new location
        def get_legacy_path():
            if file_type == "general":
                return os.path.join(self.mame_dir, "control_config_settings.json")
            elif file_type == "text":
                return os.path.join(self.mame_dir, "text_appearance_settings.json")
            elif file_type.startswith("positions"):
                suffix = file_type.replace("positions", "")
                if rom_name:
                    return os.path.join(self.mame_dir, "preview", f"{rom_name}_positions{suffix}.json")
                else:
                    return os.path.join(self.mame_dir, "preview", f"global_positions{suffix}.json")
            elif file_type == "logo":
                return os.path.join(self.mame_dir, "logo_settings.json")
            elif file_type == "bezel":
                return os.path.join(self.mame_dir, "bezel_settings.json")
            elif file_type == "layer":
                return os.path.join(self.mame_dir, "layer_settings.json")
            elif file_type == "custom_controls" and rom_name:
                return os.path.join(self.mame_dir, "custom_controls", f"{rom_name}.json")
            return None
        
        return get_legacy_path() if not os.path.exists(settings_base) else None
    
    def migrate_settings_files(self):
        """
        Migrate existing settings files to the new centralized location
        
        This function should be called early in the application startup process
        to ensure all settings are properly migrated to the new structure.
        """
        import os
        import json
        import shutil
        
        print("\n=== Starting settings migration check ===")
        
        # Define migration mapping: (file_type, old_path, rom_name)
        migration_list = [
            ("general", os.path.join(self.mame_dir, "control_config_settings.json"), None),
            ("text", os.path.join(self.mame_dir, "text_appearance_settings.json"), None),
            ("logo", os.path.join(self.mame_dir, "logo_settings.json"), None),
            ("bezel", os.path.join(self.mame_dir, "bezel_settings.json"), None),
            ("layer", os.path.join(self.mame_dir, "layer_settings.json"), None)
        ]
        
        # Check for global positions file
        old_global_positions = os.path.join(self.mame_dir, "preview", "global_positions.json")
        if os.path.exists(old_global_positions):
            migration_list.append(("positions", old_global_positions, None))
        
        # Check for ROM-specific position files
        preview_dir = os.path.join(self.mame_dir, "preview")
        if os.path.exists(preview_dir):
            for filename in os.listdir(preview_dir):
                if filename.endswith("_positions.json") and filename != "global_positions.json":
                    rom_name = filename.replace("_positions.json", "")
                    migration_list.append(("positions", os.path.join(preview_dir, filename), rom_name))
        
        # Check for custom controls files
        custom_dir = os.path.join(self.mame_dir, "custom_controls")
        if os.path.exists(custom_dir):
            for filename in os.listdir(custom_dir):
                if filename.endswith(".json"):
                    rom_name = filename.replace(".json", "")
                    migration_list.append(("custom_controls", os.path.join(custom_dir, filename), rom_name))
        
        # Add this to the migration_list in migrate_settings_files method
        gamedata_legacy = os.path.join(self.mame_dir, "gamedata.json")
        if os.path.exists(gamedata_legacy):
            new_path = os.path.join(self.mame_dir, "preview", "settings", "gamedata.json")
            if not os.path.exists(new_path):
                try:
                    # Create directory if needed
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    # Copy file
                    shutil.copy2(gamedata_legacy, new_path)
                    print(f"Migrated: {gamedata_legacy} -> {new_path}")
                    migrated_count += 1
                except Exception as e:
                    print(f"Error migrating gamedata.json: {e}")
        
        # Perform the migration
        migrated_count = 0
        for file_type, old_path, rom_name in migration_list:
            if os.path.exists(old_path):
                # Get new path using settings manager
                new_path = self.get_settings_path(file_type, rom_name)
                
                # Create directory if needed
                new_dir = os.path.dirname(new_path)
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir)
                
                # Only migrate if the file doesn't already exist in the new location
                if not os.path.exists(new_path):
                    try:
                        # Copy file
                        shutil.copy2(old_path, new_path)
                        print(f"Migrated: {old_path} -> {new_path}")
                        migrated_count += 1
                        
                        # Optional: Remove old file after successful migration
                        # os.remove(old_path)
                        # print(f"Removed old file: {old_path}")
                    except Exception as e:
                        print(f"Error migrating {old_path}: {e}")
                else:
                    print(f"Skipped (already exists): {old_path}")
        
        if migrated_count > 0:
            print(f"Migration complete: {migrated_count} files migrated")
        else:
            print("No files needed migration")
        
        print("=== Settings migration check complete ===\n")
        return migrated_count
    
    def toggle_button_names(self):
        """Toggle between showing and hiding button names in the preview"""
        print("\n=== Toggling button names visibility ===")
        
        # Toggle the state
        old_value = getattr(self, 'show_button_names', True)
        self.show_button_names = not old_value
        print(f"Button names visibility changed from {old_value} to {self.show_button_names}")
        
        # Update the button text if it exists
        if hasattr(self, 'button_names_toggle_button') and self.button_names_toggle_button.winfo_exists():
            toggle_text = "Hide Names" if self.show_button_names else "Show Names"
            self.button_names_toggle_button.configure(text=toggle_text)
            print(f"Updated button text to: {toggle_text}")
        
        # Reload positions based on new button names visibility setting
        current_game = getattr(self, 'current_game', None)
        if hasattr(self, 'position_manager') and current_game:
            self.position_manager.positions = {}  # Clear current positions
            self.position_manager.load_from_file(current_game)  # Reload with proper variant
            print(f"Reloaded positions with button names: {self.show_button_names}")
        
        # Update all text items with new format and positions
        if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists() and hasattr(self, 'text_items'):
            settings = self.get_text_settings()
            
            for control_name, data in self.text_items.items():
                if 'action' in data:
                    # Generate the new display text based on current setting
                    action = data['action']
                    control_name_for_display = data.get('control_name')  # Get original control name if stored
                    custom_mapping = data.get('custom_mapping')
                    
                    display_text = self.get_display_text(action, settings, control_name_for_display, custom_mapping)
                    
                    # Get position from the position manager
                    if hasattr(self, 'position_manager'):
                        x, normalized_y = self.position_manager.get_normalized(control_name, data['x'], data.get('base_y', data['y']))
                        text_x, text_y = self.position_manager.apply_offset(x, normalized_y)
                        
                        # Update stored position in text_items
                        data['x'] = text_x
                        data['y'] = text_y
                        data['base_y'] = normalized_y
                    else:
                        text_x, text_y = data['x'], data['y']
                    
                    # Update the text item on canvas
                    if 'text' in data and self.preview_canvas.winfo_exists():
                        try:
                            self.preview_canvas.itemconfigure(data['text'], text=display_text)
                            self.preview_canvas.coords(data['text'], text_x, text_y)
                        except Exception as e:
                            print(f"Error updating text for {control_name}: {e}")
                    
                    # Update shadow text
                    if 'shadow' in data and data['shadow'] and self.preview_canvas.winfo_exists():
                        try:
                            self.preview_canvas.itemconfigure(data['shadow'], text=display_text)
                            # Apply shadow offset
                            shadow_offset = settings.get('bold_strength', 2)
                            shadow_offset = max(1, min(shadow_offset, 3))  # Clamp between 1-3 pixels
                            self.preview_canvas.coords(data['shadow'], text_x + shadow_offset, text_y + shadow_offset)
                        except Exception as e:
                            print(f"Error updating shadow for {control_name}: {e}")
                    
                    # Store the updated display text
                    data['display_text'] = display_text
        
        # Save the setting
        self.save_settings()
        print("=== Toggle button names complete ===\n")
    
    def show_preview(self):
        """Show a preview of the control layout for the current game on the second screen"""
        # First close any existing preview windows to prevent accumulation
        self.close_all_previews()
        
        if not self.current_game:
            messagebox.showinfo("No Game Selected", "Please select a game first")
            return
            
        # Create preview directory and handle bundled images if needed
        preview_dir = self.ensure_preview_folder_improved()

        # Check for a ROM-specific image (PNG or JPG)
        image_extensions = [".png", ".jpg", ".jpeg"]
        image_path = None

        for ext in image_extensions:
            test_path = os.path.join(preview_dir, f"{self.current_game}{ext}")
            if os.path.exists(test_path):
                image_path = test_path
                break

        # Fall back to default image (PNG or JPG)
        if not image_path:
            for ext in image_extensions:
                test_path = os.path.join(preview_dir, f"default{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    break

        # If no image found, show a message
        if not image_path:
            messagebox.showinfo(
                "Image Not Found",
                f"No preview image found for {self.current_game}\n"
                f"Place PNG or JPG images in {preview_dir} folder"
            )
            return

        # Get game control data
        game_data = self.get_game_data(self.current_game)
        if not game_data:
            messagebox.showinfo("No Control Data", f"No control data found for {self.current_game}")
            return
        
        # Check for screen preference in settings
        preferred_screen = getattr(self, 'preferred_preview_screen', 2)  # Default to second screen
        
        # We'll use tkinter directly for the window but CustomTkinter for buttons
        import tkinter as tk
        from PIL import Image, ImageTk
        
        # Create our preview window directly
        self.preview_window = tk.Toplevel()
        self.preview_window.title(f"Control Preview: {self.current_game}")
        
        # Hide window initially and prevent flashing
        self.preview_window.withdraw()
        
        # Configure the window to properly exit when closed
        self.preview_window.protocol("WM_DELETE_WINDOW", self.close_preview)
        
        # Bind ESC to the force_quit function
        self.preview_window.bind("<Escape>", lambda event: self.close_preview())
        
        # Get information about monitors through direct Windows API if possible
        monitors = []
        try:
            # Try to use Windows API
            import ctypes
            from ctypes import windll
            
            # Define structs needed to get monitor info
            class RECT(ctypes.Structure):
                _fields_ = [
                    ('left', ctypes.c_long),
                    ('top', ctypes.c_long),
                    ('right', ctypes.c_long),
                    ('bottom', ctypes.c_long)
                ]
                
            # Get monitor info
            def callback(monitor, dc, rect, data):
                rect = ctypes.cast(rect, ctypes.POINTER(RECT)).contents
                monitors.append({
                    'left': rect.left,
                    'top': rect.top,
                    'right': rect.right,
                    'bottom': rect.bottom,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top,
                    'index': len(monitors)  # Add index for selection
                })
                return 1
                
            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(RECT),
                ctypes.c_double
            )
            
            # Enumerate monitors
            windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
            
            print(f"Found {len(monitors)} monitors")
            for i, mon in enumerate(monitors):
                print(f"Monitor {i+1}: {mon['width']}x{mon['height']} at position {mon['left']},{mon['top']}")
                
        except Exception as e:
            print(f"Error using Windows API for monitor detection: {e}")
            # Create a minimal monitor list with defaults
            monitors = [{'left': 0, 'top': 0, 'width': 1920, 'height': 1080, 'index': 0}]
            
            # Try to detect second monitor using simple method
            full_width = self.winfo_screenwidth()
            if full_width > 2000:  # Assume wide screen means multiple monitors
                monitors.append({
                    'left': 1920, 'top': 0, 
                    'width': full_width - 1920, 'height': self.winfo_screenheight(),
                    'index': 1
                })
                print(f"Detected probable second monitor at x=1920 (simple method)")
        
        # Force at least two monitors for button functionality
        if len(monitors) < 2:
            monitors.append({
                'left': monitors[0]['width'], 
                'top': 0, 
                'width': monitors[0]['width'], 
                'height': monitors[0]['height'],
                'index': 1
            })
            print(f"Added virtual second monitor for button functionality")
        
        # Use selected monitor or fall back to primary
        target_monitor = None
        if 0 <= preferred_screen - 1 < len(monitors):
            target_monitor = monitors[preferred_screen - 1]
            print(f"Using preferred screen {preferred_screen}: {target_monitor}")
        else:
            # Default to first monitor if preferred screen doesn't exist
            target_monitor = monitors[0]
            print(f"Preferred screen {preferred_screen} not available, using monitor 1")
            
        # Position window on selected monitor
        window_x = target_monitor['left']
        window_y = target_monitor['top']
        window_width = target_monitor['width']
        window_height = target_monitor['height']
        
        print(f"Setting window dimensions: {window_width}x{window_height}+{window_x}+{window_y}")
        
        # Configure the preview window
        self.preview_window.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
        
        # Make it fullscreen without window decorations
        self.preview_window.overrideredirect(True)
        
        # Update tasks to allow window to process
        self.preview_window.update_idletasks()
        
        # Make the window visible
        self.preview_window.deiconify()
        
        # Ensure it stays on top
        self.preview_window.attributes('-topmost', True)

        # Load and display the image
        try:
            # Load the image
            img = Image.open(image_path)
            print(f"Loaded image: {image_path}, size={img.size}")
            
            # Get window dimensions (use the values we set earlier)
            win_width = window_width
            win_height = window_height
            
            # Resize image to fit window while maintaining aspect ratio
            img_width, img_height = img.size
            
            # Ensure dimensions are positive
            if win_width <= 0:
                win_width = 1024
            if win_height <= 0:
                win_height = 768
            
            # Handle zero-size image
            if img_width <= 0 or img_height <= 0:
                print("Image has invalid dimensions, creating blank image")
                img = Image.new('RGB', (win_width, win_height), color='black')
                img_width, img_height = img.size
            
            # Calculate resize ratio
            ratio = min(win_width/max(img_width, 1), win_height/max(img_height, 1))
            new_width = max(int(img_width * ratio), 1)  # Ensure at least 1 pixel
            new_height = max(int(img_height * ratio), 1)  # Ensure at least 1 pixel
            
            print(f"Resizing image to: {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Create canvas with black background
            canvas = tk.Canvas(self.preview_window, 
                            width=win_width, 
                            height=win_height,
                            bg="black",
                            highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            
            # Center the image
            x = max((win_width - new_width) // 2, 0)
            y = max((win_height - new_height) // 2, 0)
            # After creating the background image
            canvas.create_image(x, y, image=photo, anchor="nw", tags="background_image")
            canvas.image = photo  # Keep a reference to prevent garbage collection

            # Apply proper layering
            self.apply_layering()
            
            # Initialize logo display
            self.preview_logo_item = None
            self.preview_logo_photo = None

            # Load logo settings
            if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
                self.load_logo_settings()
                print(f"Loaded logo settings: visible={self.logo_visible}, position={self.logo_position}")

            # Add logo immediately if it should be visible
            if self.logo_visible:
                try:
                    self.add_logo_to_preview_canvas()
                    print("Added logo during preview initialization")
                except Exception as e:
                    print(f"Error adding logo during initialization: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Store canvas and image info for text placement
            self.preview_canvas = canvas
            self.image_x = x
            self.image_y = y
            
            # Reset text items dictionary
            self.text_items = {}
            
            # Load the position manager with saved positions
            self.position_manager.load_from_file(self.current_game)
            print(f"Loaded {len(self.position_manager.positions)} positions from position manager")
            
            # Load text appearance settings
            settings = self.get_text_settings()
            use_uppercase = settings.get("use_uppercase", False)
            font_family = settings.get("font_family", "Arial")
            font_size = settings.get("font_size", 28)
            bold_strength = settings.get("bold_strength", 2)
            y_offset = settings.get('y_offset', -40)
            
            print(f"Loaded text settings: uppercase={use_uppercase}, font={font_family}, size={font_size}, y_offset={y_offset}")
            
            # Apply scaling factor for fonts
            adjusted_font_size = self.apply_font_scaling(font_family, font_size)
            
            # Create font with correct size and family
            try:
                import tkinter.font as tkfont
                text_font = tkfont.Font(family=font_family, size=adjusted_font_size, weight="bold")
            except Exception as e:
                print(f"Error creating font: {e}")
                text_font = (font_family, adjusted_font_size, "bold")
            
            # Get custom controls if they exist
            cfg_controls = {}
            if self.current_game in self.custom_configs:
                cfg_controls = self.parse_cfg_controls(self.custom_configs[self.current_game])
                # Convert mappings if XInput is enabled
                if self.use_xinput:
                    cfg_controls = {
                        control: self.convert_mapping(mapping, True)
                        for control, mapping in cfg_controls.items()
                    }
            
            # Add player controls as text overlays
            control_count = 0
            
            # Process only Player 1 controls
            for player in game_data.get('players', []):
                if player['number'] != 1:
                    continue
                    
                for label in player.get('labels', []):
                    control_name = label['name']
                    action = label['value']
                    
                    # Only include P1 controls
                    if not control_name.startswith('P1_'):
                        continue
                    
                    # Check if there's a custom mapping for this control
                    custom_mapping = None
                    if control_name in cfg_controls:
                        custom_mapping = cfg_controls[control_name]
                    
                    # Get XInput button name for positioning
                    xinput_button = self.get_xinput_button_from_control(control_name, custom_mapping)
                    
                    # Skip controls that don't map to XInput buttons
                    if not xinput_button:
                        continue
                    
                    # Apply uppercase if enabled and add mapping info if custom mapping exists
                    display_text = self.get_display_text(action, settings, control_name, custom_mapping)
                    
                    # Skip if no display text
                    if not display_text:
                        continue
                        
                    print(f"Adding control: {control_name} = {display_text} (XInput: {xinput_button})")
                    
                    # Get position from position manager using the XInput button name as the key
                    if xinput_button in self.position_manager.positions:
                        # Get normalized position from position manager
                        normalized_x, normalized_y = self.position_manager.get_normalized(xinput_button)
                        
                        # Apply current offset for display
                        text_x, text_y = self.position_manager.apply_offset(normalized_x, normalized_y, y_offset)
                        
                        print(f"Using saved position for {xinput_button}: normalized=({normalized_x}, {normalized_y}), display=({text_x}, {text_y})")
                    else:
                        # Default position calculation
                        grid_x = x + 100 + (control_count % 5) * 150
                        grid_y = y + 50 + (control_count // 5) * 40
                        
                        # Apply offset to default position
                        text_x, text_y = grid_x, grid_y + y_offset
                        
                        # Store normalized position (without y-offset)
                        normalized_x, normalized_y = grid_x, grid_y
                        
                        # Store this position in the position manager using the XInput button name
                        self.position_manager.store(xinput_button, normalized_x, normalized_y, is_normalized=True)
                        
                        print(f"Using default position for {xinput_button}: ({text_x}, {text_y})")
                    
                    # Check visibility based on control type
                    is_visible = self.is_control_visible(control_name)
                    
                    # Create text with appropriate shadow effect
                    text_item, shadow_item = self.create_text_with_shadow(
                        canvas, 
                        text_x, 
                        text_y, 
                        display_text, 
                        text_font,
                        anchor="nw"  # Explicitly set anchor to northwest (top-left)
                    )
                    
                    # Set visibility state
                    if not is_visible:
                        canvas.itemconfigure(text_item, state="hidden")
                        if shadow_item is not None:
                            canvas.itemconfigure(shadow_item, state="hidden")
                    
                    # Store the text items - now using XInput button name as the key
                    self.text_items[xinput_button] = {
                        'text': text_item,
                        'shadow': shadow_item,
                        'action': action,
                        'display_text': display_text,
                        'control_name': control_name,  # Store original control name for reference
                        'x': text_x, 
                        'y': text_y,
                        'base_y': normalized_y,
                        'custom_mapping': custom_mapping
                    }
                    
                    # Make the text draggable - pass xinput_button as the identifier
                    self.make_draggable(canvas, text_item, shadow_item, xinput_button)
                    control_count += 1
            
            # Add right-click menu for text removal
            self.create_context_menu(canvas)

            self.frame_bg = tk.Frame(self.preview_window, bg="black")  # Changed to self.frame_bg

            # Only show if setting allows
            if not hasattr(self, 'hide_preview_buttons') or not self.hide_preview_buttons:
                self.frame_bg.place(relx=0.5, rely=0.95, anchor="center", width=min(1000, window_width-20), height=80)

            # Create ctk frame with default color
            button_frame = ctk.CTkFrame(self.frame_bg)  # Changed from frame_bg to self.frame_bg
            button_frame.pack(expand=True, fill="both")
            self.button_frame = button_frame  # Store reference to button frame

            # Create two rows of buttons using frames
            top_row = ctk.CTkFrame(button_frame)
            top_row.pack(side="top", fill="x", expand=True, pady=2)

            bottom_row = ctk.CTkFrame(button_frame)
            bottom_row.pack(side="bottom", fill="x", expand=True, pady=2)

            # Store row references for the feature buttons
            self.button_row1 = top_row
            self.button_row2 = bottom_row

            # Calculate button width to fit all buttons
            button_width = 90  # Slightly smaller width
            button_padx = 3    # Smaller padding
            
            # Top row buttons (4 buttons)
            # Close button - use the force_quit function to ensure proper termination
            close_button = ctk.CTkButton(
                top_row,
                text="Close",
                command=self.close_preview,  # Use quit_application for proper termination
                width=button_width
            )
            close_button.pack(side="left", padx=button_padx)

            # Reset positions button
            reset_button = ctk.CTkButton(
                top_row,
                text="Reset",
                command=self.reset_text_positions,
                width=button_width
            )
            reset_button.pack(side="left", padx=button_padx)

            # Add save buttons
            global_button = ctk.CTkButton(
                top_row,
                text="Global",
                command=self.save_global_positions,
                width=button_width
            )
            global_button.pack(side="left", padx=button_padx)

            # ROM button
            rom_button = ctk.CTkButton(
                top_row,
                text="ROM",
                command=self.save_rom_positions,
                width=button_width
            )
            rom_button.pack(side="left", padx=button_padx)

            # Bottom row buttons
            # Set initial state for toggle buttons
            self.show_texts = True

            # Add toggle joystick button
            joystick_button = ctk.CTkButton(
                bottom_row,
                text="Joystick",
                command=self.toggle_joystick_controls,
                width=button_width
            )
            joystick_button.pack(side="left", padx=button_padx)

            # Add toggle texts button to bottom row
            def toggle_texts():
                self.toggle_texts_visibility()
                texts_button.configure(text="Hide Texts" if self.show_texts else "Show Texts")
                
            texts_button = ctk.CTkButton(
                bottom_row,
                text="Hide Texts",
                command=toggle_texts,
                width=button_width
            )
            texts_button.pack(side="left", padx=button_padx)

            # Initialize logo settings
            if not hasattr(self, 'logo_visible') or not hasattr(self, 'logo_position'):
                self.load_logo_settings()
                print(f"Loaded logo settings: visible={self.logo_visible}, position={self.logo_position}")
            
            # Schedule the logo to be added after the window has fully rendered (300ms delay)
            if self.logo_visible:
                self.preview_window.after(300, self.add_logo_to_preview_canvas)
                print("Scheduled logo to be added after window initialization")
            
            # Add logo visibility toggle button to bottom row
            logo_toggle_text = "Hide Logo" if self.logo_visible else "Show Logo"
            logo_toggle_button = ctk.CTkButton(
                bottom_row,
                text=logo_toggle_text,
                command=self.toggle_logo_visibility,
                width=button_width
            )
            logo_toggle_button.pack(side="left", padx=button_padx)
            self.logo_toggle_button = logo_toggle_button  # Save reference
            
            # Add logo position button to bottom row
            logo_position_button = ctk.CTkButton(
                bottom_row,
                text="Logo Pos",
                command=self.show_logo_position_dialog,
                width=button_width
            )
            logo_position_button.pack(side="left", padx=button_padx)
            self.logo_position_button = logo_position_button  # Save reference
            
            # Now add the logo to the preview canvas if visibility is on
            if self.logo_visible:
                self.add_logo_to_preview_canvas()
            
            # Add this line after the "Now add the logo to the preview canvas" section
            # in the show_preview method:
            if hasattr(self, 'bezel_visible') and self.bezel_visible:
                self.add_bezel_to_preview_canvas()
                     
            # Add bezel visibility toggle button to bottom row
            bezel_toggle_text = "Hide Bezel" if self.bezel_visible else "Show Bezel"
            bezel_toggle_button = ctk.CTkButton(
                bottom_row,
                text=bezel_toggle_text,
                command=self.toggle_bezel_visibility,
                width=button_width
            )
            bezel_toggle_button.pack(side="left", padx=button_padx)
            self.bezel_toggle_button = bezel_toggle_button  # Save reference
            
            # Add button names toggle button to bottom row
            button_names_toggle_text = "Hide Names" if self.show_button_names else "Show Names"
            button_names_toggle_button = ctk.CTkButton(
                bottom_row,
                text=button_names_toggle_text,
                command=self.toggle_button_names,
                width=button_width
            )
            button_names_toggle_button.pack(side="left", padx=button_padx)
            self.button_names_toggle_button = button_names_toggle_button  # Save reference
                  
            # Add text settings button to the top row
            text_settings_button = ctk.CTkButton(
                top_row,
                text="Text Settings",
                command=lambda: self.show_text_appearance_settings(update_preview=True),
                width=button_width
            )
            text_settings_button.pack(side="left", padx=button_padx)

           # Add exact preview button
            save_button = self.create_button(
                top_row,
                text="Save Image",
                command=self.save_current_preview,
                button_id="save_button",
                width=button_width,
                show=getattr(self, 'show_save_button', True)
            )
            if save_button:  # Only pack if the button was created (not hidden)
                save_button.pack(side="left", padx=button_padx)
           
           # Add exact preview button
            exact_preview_button = self.create_button(
                top_row,
                text="Exact Preview",
                command=self.show_image_preview,
                button_id="exact_preview_button",
                width=button_width,
                show=getattr(self, 'show_exact_preview_button', True)
            )
            if exact_preview_button:  # Only pack if the button was created (not hidden)
                exact_preview_button.pack(side="left", padx=button_padx)

            # Add layer settings button to bottom row
            layer_settings_button = ctk.CTkButton(
                bottom_row,
                text="Layers",
                command=self.show_layer_settings_dialog,
                width=button_width  # Use the same width as other buttons
            )
            layer_settings_button.pack(side="left", padx=button_padx)

            # Add a repeated check to ensure logo appears
            def ping_logo_visibility(attempt=1, max_attempts=5):
                """Try multiple times to ensure logo is visible"""
                if not hasattr(self, 'preview_window') or not self.preview_window.winfo_exists():
                    return  # Window closed, stop trying
                    
                if self.logo_visible and (not hasattr(self, 'preview_logo_item') or not self.preview_logo_item):
                    print(f"Logo visibility check attempt {attempt} - adding logo now")
                    success = self.add_logo_to_preview_canvas()
                    
                    # If unsuccessful and we haven't reached max attempts, try again
                    if not success and attempt < max_attempts:
                        self.preview_window.after(250, lambda: ping_logo_visibility(attempt + 1, max_attempts))
                    elif success:
                        print(f"Logo successfully added on attempt {attempt}")
                    else:
                        print(f"Failed to add logo after {attempt} attempts")
                elif hasattr(self, 'preview_logo_item') and self.preview_logo_item:
                    print(f"Logo already visible on attempt {attempt}")
            
            # Schedule the first check after 200ms
            self.preview_window.after(200, ping_logo_visibility)
            
            # Add toggle screen button to bottom row
            def toggle_screen():
                # Cycle to the next available monitor
                current_screen = getattr(self, 'preferred_preview_screen', 2)
                next_screen = (current_screen % len(monitors)) + 1
                
                # Set the preference and print
                self.preferred_preview_screen = next_screen
                print(f"Switching to screen {next_screen}")
                
                # Close and reopen the preview window
                self.preview_window.destroy()
                self.show_preview()
                
            screen_button = ctk.CTkButton(
                bottom_row,
                text=f"Screen {preferred_screen}",
                command=toggle_screen,
                width=button_width
            )
            screen_button.pack(side="left", padx=button_padx)

            # Add the feature functions
            self.add_alignment_guides()
            self.add_show_all_buttons_feature()
        
        except ImportError:
            messagebox.showinfo("Missing Package", "Please install Pillow: pip install pillow")
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying image: {str(e)}")
            import traceback
            traceback.print_exc()

    def add_logo_controls_directly(self):
        """Add logo controls directly to the preview window button rows"""
        # Check if button rows exist
        if not hasattr(self, 'button_row2') or not self.button_row2.winfo_exists():
            print("ERROR: button_row2 widget does not exist")
            return
        
        # Add logo visibility toggle button
        toggle_text = "Hide Logo" if self.logo_visible else "Show Logo"
        self.logo_toggle_button = ctk.CTkButton(
            self.button_row2,
            text=toggle_text,
            command=self.toggle_logo_visibility,
            width=90
        )
        self.logo_toggle_button.pack(side="left", padx=3)
        
        # Add logo position button
        self.logo_position_button = ctk.CTkButton(
            self.button_row2,
            text="Logo Pos",
            command=self.show_logo_position_dialog,
            width=90
        )
        self.logo_position_button.pack(side="left", padx=3)
        
        print("Added logo controls directly to preview window")

    def add_logo_position_control_to_preview(self):
        """Add only the logo position control to preview window"""
        print("\n--- ADDING LOGO POSITION CONTROL TO PREVIEW ---")
        
        if not hasattr(self, 'button_row2'):
            print("ERROR: button_row2 attribute does not exist")
            return
            
        if not self.button_row2.winfo_exists():
            print("ERROR: button_row2 widget does not exist")
            return
        
        print("Found button_row2, adding logo position control")
        
        # Add Logo position button only
        try:
            self.logo_position_button = ctk.CTkButton(
                self.button_row2,
                text="Logo Pos",
                command=self.show_logo_position_dialog,
                width=90  # Match other buttons
            )
            self.logo_position_button.pack(side="left", padx=3)
            print("Successfully added logo position button")
        except Exception as e:
            print(f"ERROR creating logo position button: {e}")
            import traceback
            traceback.print_exc()
        
        print("--- LOGO POSITION CONTROL ADDED ---\n")

    def add_logo_to_preview_canvas(self):
        """Add logo to the preview canvas with Y offset support"""
        print("\n=== Starting add_logo_to_preview_canvas ===")
        
        try:
            # Make sure we have a canvas
            if not hasattr(self, 'preview_canvas') or not self.preview_canvas.winfo_exists():
                print("No preview canvas available")
                return False
                
            # Check if logo visibility is enabled
            if not hasattr(self, 'logo_visible') or not self.logo_visible:
                print("Logo visibility is disabled")
                return False
                
            # First remove any existing logo
            if hasattr(self, 'preview_logo_item') and self.preview_logo_item:
                print("Removing existing logo item")
                try:
                    self.preview_canvas.delete(self.preview_logo_item)
                except Exception as e:
                    print(f"Error removing existing logo: {e}")
                self.preview_logo_item = None
                self.preview_logo_photo = None
            
            # Make sure we have a game selected
            if not hasattr(self, 'current_game') or not self.current_game:
                print("No current game selected")
                return False
            
            # Get the logo path
            logo_path = self.get_logo_path(self.current_game)
            if not logo_path:
                print(f"No logo found for {self.current_game}")
                return False
                
            print(f"Found logo path: {logo_path}")
            
            # Load the logo with explicit transparency handling
            from PIL import Image, ImageTk
            try:
                # Load the logo image and specifically convert to RGBA to preserve transparency
                logo_img = Image.open(logo_path)
                
                # Debug the image mode and information
                print(f"Original logo image: {logo_img.size} {logo_img.mode}")
                
                # Always convert to RGBA to ensure transparency is properly handled
                if logo_img.mode != 'RGBA':
                    logo_img = logo_img.convert('RGBA')
                    print(f"Converted logo to RGBA format")
                
                # Calculate appropriate size
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()
                print(f"Canvas size: {canvas_width}x{canvas_height}")
                
                # If canvas size is invalid, use reasonable defaults
                if canvas_width <= 1 or canvas_height <= 1:
                    if hasattr(self, 'preview_window'):
                        canvas_width = self.preview_window.winfo_width()
                        canvas_height = self.preview_window.winfo_height()
                        print(f"Using window size: {canvas_width}x{canvas_height}")
                        
                        if canvas_width <= 1 or canvas_height <= 1:
                            canvas_width = 1920
                            canvas_height = 1080
                            print(f"Using default size: {canvas_width}x{canvas_height}")
                    else:
                        canvas_width = 1920
                        canvas_height = 1080
                        print(f"Using default size: {canvas_width}x{canvas_height}")
                
                # Use percentage-based sizing (with safety checks)
                max_width = int(canvas_width * (self.logo_width_percentage / 100))
                max_height = int(canvas_height * (self.logo_height_percentage / 100))
                
                # Enforce minimum size for visibility
                max_width = max(max_width, 100)
                max_height = max(max_height, 32)
                
                # Calculate scale factor
                logo_width, logo_height = logo_img.size
                scale = min(max_width / max(logo_width, 1), max_height / max(logo_height, 1))
                
                # Resize the logo with high quality resampling
                new_width = max(int(logo_width * scale), 1)
                new_height = max(int(logo_height * scale), 1)
                print(f"Resizing logo from {logo_width}x{logo_height} to {new_width}x{new_height}")
                logo_img = logo_img.resize((new_width, new_height), Image.LANCZOS)
                
                # Convert to PhotoImage for Tkinter - explicitly specify RGBA
                photo = ImageTk.PhotoImage(logo_img)
                
                # Position the logo based on logo_position setting
                padding = 20
                
                if not hasattr(self, 'logo_position'):
                    self.logo_position = 'top-left'  # Default position
                    
                # Get Y offset (default to 0 if not set)
                y_offset = getattr(self, 'logo_y_offset', 0)
                
                if self.logo_position == 'top-left':
                    x, y = padding, padding + y_offset
                elif self.logo_position == 'top-center':
                    x, y = (canvas_width - new_width) // 2, padding + y_offset
                elif self.logo_position == 'top-right':
                    x, y = canvas_width - new_width - padding, padding + y_offset
                elif self.logo_position == 'bottom-left':
                    x, y = padding, canvas_height - new_height - padding + y_offset
                elif self.logo_position == 'bottom-center':
                    x, y = (canvas_width - new_width) // 2, canvas_height - new_height - padding + y_offset
                elif self.logo_position == 'bottom-right':
                    x, y = canvas_width - new_width - padding, canvas_height - new_height - padding + y_offset
                else:  # Default to top-center
                    x, y = (canvas_width - new_width) // 2, padding + y_offset
                
                print(f"Placing logo at position: {x},{y} ({self.logo_position} with Y offset: {y_offset})")
                
                # Create the image on the canvas
                img_item = self.preview_canvas.create_image(x, y, image=photo, anchor="nw")
                
                # Store references
                self.preview_logo_photo = photo  # Keep a reference to prevent garbage collection
                self.preview_logo_item = img_item
                
                # Make sure logo is on top of other elements (or at proper layer if using layering system)
                if hasattr(self, 'apply_layering'):
                    self.apply_layering()
                else:
                    # Default behavior - raise logo above background
                    self.preview_canvas.lift(img_item)
                
                print(f"Successfully added logo to preview canvas")
                return True
                
            except Exception as e:
                print(f"Error loading logo image: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"Error in add_logo_to_preview_canvas: {e}")
            import traceback
            traceback.print_exc()
            return False
    
if __name__ == "__main__":
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description='MAME Control Configuration')
    parser.add_argument('--preview-only', action='store_true', help='Show only the preview window')
    parser.add_argument('--game', type=str, help='Specify the ROM name to preview')
    parser.add_argument('--screen', type=int, default=1, help='Screen number to display preview on (default: 2)')
    parser.add_argument('--auto-close', action='store_true', help='Automatically close preview when MAME exits')
    parser.add_argument('--force-logo', action='store_true', help='Force logo visibility in preview mode')
    parser.add_argument('--bezel-on-top', action='store_true', help='Force bezel to display on top of background')
    parser.add_argument('--hide-joystick', action='store_true', help='Hide joystick direction controls in preview')
    parser.add_argument('--hide-buttons', action='store_true', help='Hide control buttons in preview mode')
    args = parser.parse_args()
    
    if args.preview_only and args.game:
        # Preview-only mode: just show the preview for the specified game
        app = MAMEControlConfig(preview_only=True)
        
        # Load settings first (which might overwrite preferred_preview_screen)
        app.load_settings()
        
        # Override with command-line screen setting 
        app.preferred_preview_screen = args.screen
        print(f"Using screen {args.screen} from command line (main block)")
        
        # Set button visibility based on command line argument
        app.hide_preview_buttons = args.hide_buttons
        
        # Show the standalone preview with command line options
        app.show_preview_standalone(
            args.game, 
            auto_close=args.auto_close, 
            force_logo=args.force_logo,
            hide_joystick=args.hide_joystick
        )
    else:
        # Normal mode: start the full application
        app = MAMEControlConfig()
        app.mainloop()