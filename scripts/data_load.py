import pandas as pd
import os
from pathlib import Path

def load_all_gameweek_data(base_path="data/2024-2025"):
    """
    Load all gameweek match and player match data
    """
    # Initialize lists to store all gameweek data
    all_matches = []
    all_player_matches = []
    
    # Find all GW folders
    matches_path = Path(base_path) / "matches"
    player_matches_path = Path(base_path) / "playermatchstats"
    
    # Get all GW folders (assuming they follow GW1, GW2, ... pattern)
    gw_folders = sorted([f for f in matches_path.iterdir() if f.is_dir() and f.name.startswith("GW")])
    
    print(f"Found {len(gw_folders)} gameweek folders")
    
    for gw_folder in gw_folders:
        gw_num = int(gw_folder.name.replace("GW", ""))
        
        # Load matches for this gameweek
        matches_file = gw_folder / "matches.csv"
        if matches_file.exists():
            matches_df = pd.read_csv(matches_file)
            matches_df['gw'] = gw_num  # Add gameweek number
            all_matches.append(matches_df)
        
        # Load player match stats for this gameweek
        player_matches_file = player_matches_path / f"GW{gw_num}" / "playermatchstats.csv"
        if player_matches_file.exists():
            player_matches_df = pd.read_csv(player_matches_file)
            player_matches_df['gw'] = gw_num  # Add gameweek number
            all_player_matches.append(player_matches_df)
    
    # Combine all gameweeks
    matches_combined = pd.concat(all_matches, ignore_index=True) if all_matches else pd.DataFrame()
    player_matches_combined = pd.concat(all_player_matches, ignore_index=True) if all_player_matches else pd.DataFrame()
    
    return matches_combined, player_matches_combined