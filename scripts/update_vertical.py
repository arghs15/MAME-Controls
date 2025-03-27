import json
import os
from datetime import datetime
import sys

# File paths - you should update these to the full paths where your files are located
# For example: r"D:\Deluxe LEGENDS Max\emulators\mame\preview\Test Fix JSON\Test Vert\vertical"
VERTICAL_FILE = r"D:\Deluxe LEGENDS Max\emulators\mame\preview\Test Fix JSON\Test Vert\vertical.txt"
GAMEDATA_FILE = r"D:\Deluxe LEGENDS Max\emulators\mame\preview\Test Fix JSON\Test Vert\gamedata.json"

# Check if the files exist
if not os.path.exists(VERTICAL_FILE):
    print(f"Error: The vertical file '{VERTICAL_FILE}' does not exist.")
    print("Please update the VERTICAL_FILE path in the script.")
    sys.exit(1)

if not os.path.exists(GAMEDATA_FILE):
    print(f"Error: The gamedata file '{GAMEDATA_FILE}' does not exist.")
    print("Please update the GAMEDATA_FILE path in the script.")
    sys.exit(1)

# Read the vertical games file
with open(VERTICAL_FILE, 'r') as f:
    vertical_games = [line.strip() for line in f.readlines() if line.strip()]

print(f"Found {len(vertical_games)} vertical games in the list")

# Read the gamedata.json file
try:
    with open(GAMEDATA_FILE, 'r') as f:
        game_data = json.load(f)
    print(f"Successfully loaded gamedata.json with {len(game_data)} games")
except Exception as e:
    print(f"Error reading gamedata.json: {e}")
    exit(1)

# Create a backup of the original file
backup_dir = os.path.dirname(GAMEDATA_FILE)
backup_filename = os.path.join(backup_dir, f"gamedata_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
with open(backup_filename, 'w') as f:
    json.dump(game_data, f, indent=2)
print(f"Created backup at {backup_filename}")

# Track which games were updated
updated_games = []
not_found_games = []

# Process each vertical game
for game in vertical_games:
    # Check if the game exists directly in the game_data
    if game in game_data:
        # Add vertical property if it doesn't exist
        if 'vertical' not in game_data[game]:
            game_data[game]['vertical'] = "yes"
            updated_games.append(game)
    else:
        # Check if it's a clone in any of the games
        found = False
        
        for parent_game, parent_data in game_data.items():
            if 'clones' in parent_data and game in parent_data['clones']:
                # It's a clone, so we mark the parent as vertical
                if 'vertical' not in game_data[parent_game]:
                    game_data[parent_game]['vertical'] = "yes"
                    updated_games.append(f"{parent_game} (parent of clone {game})")
                    found = True
                    break
        
        if not found:
            not_found_games.append(game)

# Write the updated data back to the file
with open(GAMEDATA_FILE, 'w') as f:
    json.dump(game_data, f, indent=2)

print("\nResults:")
print(f"- Updated {len(updated_games)} games with vertical: \"yes\"")
if updated_games:
    print('Updated games:')
    for game in updated_games:
        print(f"  - {game}")

if not_found_games:
    print('\nWarning: The following games from the vertical list were not found in gamedata.json:')
    for game in not_found_games:
        print(f"  - {game}")