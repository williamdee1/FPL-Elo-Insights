import pandas as pd
import numpy as np
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

    # Replace NaN values with zero
    matches_combined.fillna(0, inplace=True)
    player_matches_combined.fillna(0, inplace=True)
    
    return matches_combined, player_matches_combined


def load_and_link_all_data(base_path="data/2024-2025"):
    """
    Load and link all datasets including match-level statistics
    """
    # 1. Load base datasets
    print("Loading base datasets...")
    fpl_player = pd.read_csv(f"{base_path}/gws/merged_gw.csv")
    players_master = pd.read_csv(f"{base_path}/players/players.csv")
    
    # team_stats = pd.read_csv(f"{base_path}/teams/teams.csv")  
    # # Removed as the values for each team are static (i.e. not weekly)
    
    # 2. Load all gameweek match data
    print("\nLoading match data across all gameweeks...")
    all_matches = []
    all_player_matches = []
    
    from pathlib import Path
    matches_path = Path(base_path) / "matches"
    player_matches_path = Path(base_path) / "playermatchstats"
    
    gw_folders = sorted([f for f in matches_path.iterdir() if f.is_dir() and f.name.startswith("GW")])
    
    for gw_folder in gw_folders:
        gw_num = int(gw_folder.name.replace("GW", ""))
        
        # Load matches
        matches_file = gw_folder / "matches.csv"
        if matches_file.exists():
            matches_df = pd.read_csv(matches_file)
            matches_df['gw'] = gw_num
            all_matches.append(matches_df)
        
        # Load player match stats
        player_matches_file = player_matches_path / f"GW{gw_num}" / "playermatchstats.csv"
        if player_matches_file.exists():
            player_matches_df = pd.read_csv(player_matches_file)
            player_matches_df['gw'] = gw_num
            all_player_matches.append(player_matches_df)
    
    matches_df = pd.concat(all_matches, ignore_index=True)
    player_matches_df = pd.concat(all_player_matches, ignore_index=True)
    
    print(f"Loaded {len(matches_df)} matches and {len(player_matches_df)} player-match records")
    
    # 3. Link everything together
    print("\nLinking datasets...")
    
    # First, link player matches with match data to get team info
    player_matches_enhanced = player_matches_df.merge(
        matches_df[['match_id', 'home_team', 'away_team', 'home_score', 'away_score']], 
        on='match_id',
        how='left'
    )
    
    # Now we need to figure out which team each player was on
    # We'll need to use the players_master to get team_id
    player_matches_enhanced = player_matches_enhanced.merge(
        players_master[['player_id', 'team_id']],
        on='player_id',
        how='left'
    )
    
    # Determine if player was home or away
    player_matches_enhanced['was_home'] = (
        player_matches_enhanced['team_id'] == player_matches_enhanced['home_team']
    )
    
    # 4. Create the main ML dataset
    # Start with FPL data as base
    ml_dataset = fpl_player.copy()
    ml_dataset.rename(columns={'GW': 'gameweek'}, inplace=True)
    
    # Merge with player matches to get detailed stats
    # Note: 'element' in fpl_player should match 'player_id' in player_matches
    ml_dataset = ml_dataset.merge(
        player_matches_enhanced,
        left_on=['element', 'gameweek'],
        right_on=['player_id', 'gw'],
        how='left',
        suffixes=('', '_match')
    )
    
    # Add player master info
    ml_dataset = ml_dataset.merge(
        players_master[['player_id', 'player_code', 'first_name', 'second_name']], 
        left_on='element',
        right_on='player_id',
        how='left',
        suffixes=('', '_master')
    )

    # Drop duplicated rows in data (caused by multiple matches in a gameweek)
    ml_dataset = ml_dataset[~ml_dataset.duplicated(subset=['element', 'gameweek', 'total_points'], keep='first')]

    # Sum up player total points if there are multiple entries for the same gameweek, average the other stats
    # Group by player and gameweek
    numeric_cols = ml_dataset.select_dtypes(include=[np.number]).columns.tolist()
    bool_cols = ml_dataset.select_dtypes(include=['bool']).columns.tolist()
    numeric_cols = [col for col in numeric_cols if col not in ['element', 'gameweek']]  # Remove groupby columns
    
    agg_dict = {col: 'mean' for col in numeric_cols}
    agg_dict['total_points'] = 'sum'  # Sum points if multiple matches
    # For boolean columns, take the mode (most common value)
    for col in bool_cols:
        agg_dict[col] = lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]
    # Keep first occurrence of string columns
    agg_dict['name'] = 'first'
    agg_dict['team'] = 'first'
    agg_dict['position'] = 'first'
    
    ml_dataset = ml_dataset.groupby(['element', 'gameweek']).agg(agg_dict).reset_index()

    # Drop columns which leak performance information (i.e. created after the gameweek)
    # leak_cols = ['xP', 'ict_index', 'selected']
    # ml_dataset = ml_dataset.drop(columns=[col for col in leak_cols if col in ml_dataset.columns], errors='ignore')

    #TODO: May need to fill in weeks where teams had blank gameweeks

    return ml_dataset, matches_df, player_matches_enhanced


