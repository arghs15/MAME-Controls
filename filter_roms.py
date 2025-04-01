#!/usr/bin/env python3
"""
Simple script to filter gamedata.json based on a text file list of ROM names.
Preserves parent ROMs when needed.
"""
import json
import sys

def main():
    if len(sys.argv) != 4:
        print("Usage: python filter_roms.py <gamedata.json> <rom_list.txt> <output.json>")
        sys.exit(1)
    
    gamedata_path = sys.argv[1]
    rom_list_path = sys.argv[2]
    output_path = sys.argv[3]
    
    # Read gamedata.json
    print(f"Reading gamedata from {gamedata_path}")
    with open(gamedata_path, 'r', encoding='utf-8') as f:
        gamedata = json.load(f)
    print(f"Found {len(gamedata)} ROMs in gamedata.json")
    
    # Read ROM list
    print(f"Reading ROM list from {rom_list_path}")
    with open(rom_list_path, 'r', encoding='utf-8') as f:
        rom_list = set(line.strip() for line in f if line.strip())
    print(f"Found {len(rom_list)} ROMs in the list")
    
    # Build parent-clone relationships
    parent_map = {}
    for rom_name, rom_data in gamedata.items():
        if "clones" in rom_data:
            for clone_name in rom_data["clones"]:
                parent_map[clone_name] = rom_name
    
    # Find all ROMs to keep
    to_keep = set(rom_list)
    
    # Add parent ROMs if needed
    for rom in rom_list:
        if rom in parent_map:
            to_keep.add(parent_map[rom])
    
    # Add parents of clones that need to be preserved
    for rom_name, rom_data in gamedata.items():
        if "clones" in rom_data:
            clone_set = set(rom_data["clones"].keys())
            if clone_set.intersection(to_keep):
                to_keep.add(rom_name)
    
    # Create filtered gamedata
    filtered_data = {rom: gamedata[rom] for rom in to_keep if rom in gamedata}
    
    # Write output
    print(f"Writing filtered data with {len(filtered_data)} ROMs to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2)
    
    print("Done!")

if __name__ == "__main__":
    main()