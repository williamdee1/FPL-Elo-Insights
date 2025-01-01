import os
import pandas as pd
import numpy as np
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)

def split_matches_by_gameweek(season_path):
    """Split matches.csv by gameweek"""
    matches_path = os.path.join(season_path, 'matches', 'matches.csv')
    if not os.path.exists(matches_path):
        print(f"Matches file not found at {matches_path}")
        return None
    
    # Read matches data
    matches_df = pd.read_csv(matches_path)
    
    # Create gameweek directory
    gw_base_path = os.path.join(season_path, 'matches', 'gameweeks')
    
    # Split and save by gameweek
    for gw in matches_df['gameweek'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        
        gw_matches = matches_df[matches_df['gameweek'] == gw]
        gw_matches.to_csv(os.path.join(gw_path, 'matches.csv'), index=False)
        
    return matches_df

def split_player_match_stats(season_path, matches_df):
    """Split playermatchstats.csv by gameweek using match_id reference"""
    stats_path = os.path.join(season_path, 'playermatchstats', 'playermatchstats.csv')
    if not os.path.exists(stats_path):
        print(f"Player match stats file not found at {stats_path}")
        return
    
    # Read player match stats
    stats_df = pd.read_csv(stats_path)
    
    # Create base directory
    gw_base_path = os.path.join(season_path, 'playermatchstats', 'gameweeks')
    
    # Create match_id to gameweek mapping
    match_to_gw = dict(zip(matches_df['match_id'], matches_df['gameweek']))
    
    # Add gameweek column to stats
    stats_df['gameweek'] = stats_df['match_id'].map(match_to_gw)
    
    # Split and save by gameweek
    for gw in stats_df['gameweek'].unique():
        if pd.isna(gw):
            continue
            
        gw_path = os.path.join(gw_base_path, f'GW{int(gw)}')
        create_directory(gw_path)
        
        gw_stats = stats_df[stats_df['gameweek'] == gw]
        gw_stats.to_csv(os.path.join(gw_path, 'playermatchstats.csv'), index=False)
        
        # Further split by match_id within gameweek
        for match_id in gw_stats['match_id'].unique():
            match_path = os.path.join(gw_path, 'matches', str(match_id))
            create_directory(match_path)
            
            match_stats = gw_stats[gw_stats['match_id'] == match_id]
            match_stats.to_csv(os.path.join(match_path, 'playermatchstats.csv'), index=False)

def split_player_stats(season_path):
    """Split playerstats.csv by gameweek"""
    stats_path = os.path.join(season_path, 'playerstats', 'playerstats.csv')
    if not os.path.exists(stats_path):
        print(f"Player stats file not found at {stats_path}")
        return
    
    # Read player stats
    stats_df = pd.read_csv(stats_path)
    
    # Create gameweek directory
    gw_base_path = os.path.join(season_path, 'playerstats', 'gameweeks')
    
    # Split and save by gameweek
    for gw in stats_df['gw'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        
        gw_stats = stats_df[stats_df['gw'] == gw]
        gw_stats.to_csv(os.path.join(gw_path, 'playerstats.csv'), index=False)

def main():
    # Process for current season
    season = "2024-2025"  # Update this as needed
    season_path = os.path.join('data', season)
    
    print("Starting CSV splitting process...")
    
    # Split matches and get DataFrame for reference
    print("Splitting matches by gameweek...")
    matches_df = split_matches_by_gameweek(season_path)
    
    if matches_df is not None:
        # Split player match stats using matches reference
        print("Splitting player match stats by gameweek and match_id...")
        split_player_match_stats(season_path, matches_df)
    
    # Split player stats
    print("Splitting player stats by gameweek...")
    split_player_stats(season_path)
    
    print("CSV splitting process completed!")

if __name__ == "__main__":
    main()