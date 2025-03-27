import json
import copy
import os

def clean_gamedata(input_file, output_file):
    """
    Clean up gamedata.json by:
    1. Copying control names from clones to parent games where missing
    2. Removing redundant control data from clones
    """
    # Load the JSON data
    with open(input_file, 'r', encoding='utf-8') as f:
        gamedata = json.load(f)
    
    # Create a deep copy to avoid modifying while iterating
    cleaned_data = copy.deepcopy(gamedata)
    
    # Stats for reporting
    total_games = 0
    games_with_clones = 0
    names_transferred = 0
    
    # Process each parent game
    for game_id, game_info in gamedata.items():
        total_games += 1
        
        # Skip if the game doesn't have clones or controls
        if 'clones' not in game_info or 'controls' not in game_info:
            continue
            
        games_with_clones += 1
        parent_controls = game_info.get('controls', {})
        clone_list = game_info.get('clones', {})
        
        # Track if we've updated parent controls
        parent_updated = False
        
        # First pass: collect control names from clones that aren't in parent
        for clone_id, clone_info in clone_list.items():
            if 'controls' not in clone_info:
                continue
                
            # Check each control in the clone
            for control_id, control_info in clone_info['controls'].items():
                # If the control exists in parent but doesn't have a name
                if (control_id in parent_controls and 
                    'name' in control_info and 
                    ('name' not in parent_controls[control_id] or not parent_controls[control_id]['name'])):
                    
                    # Copy the name to the parent
                    cleaned_data[game_id]['controls'][control_id]['name'] = control_info['name']
                    names_transferred += 1
                    parent_updated = True
                    print(f"Transferred name '{control_info['name']}' for control {control_id} from {clone_id} to {game_id}")
        
        # Second pass: remove controls from all clones
        for clone_id in clone_list:
            if 'controls' in cleaned_data[game_id]['clones'][clone_id]:
                del cleaned_data[game_id]['clones'][clone_id]['controls']
    
    # Save the cleaned data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2)
    
    # Print statistics
    print(f"\nProcessing complete!")
    print(f"Total games processed: {total_games}")
    print(f"Games with clones: {games_with_clones}")
    print(f"Control names transferred: {names_transferred}")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python clean_gamedata.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    clean_gamedata(input_file, output_file)