import os
import pandas as pd
import numpy as np
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)

def update_matches_by_gameweek(season_path):
    """Updates matches.csv by gameweek, adding new gameweeks if found."""
    matches_path = os.path.join(season_path, 'matches', 'matches.csv')
    if not os.path.exists(matches_path):
        print(f"Matches file not found at {matches_path}")
        return None

    matches_df = pd.read_csv(matches_path)
    print(f"Found {len(matches_df)} matches")

    gw_base_path = os.path.join(season_path, 'matches', 'gameweeks')

    # Get existing gameweeks from directory structure
    existing_gameweeks = set()
    if os.path.exists(gw_base_path):
        for dirname in os.listdir(gw_base_path):
            if dirname.startswith('GW'):
                try:
                    gw = int(dirname[2:])
                    existing_gameweeks.add(gw)
                except ValueError:
                    pass  # Ignore directories that are not in the format GW{number}

    # Split and save by gameweek, only for new gameweeks
    for gw in matches_df['gameweek'].unique():
        if gw not in existing_gameweeks:
            gw_path = os.path.join(gw_base_path, f'GW{gw}')
            create_directory(gw_path)

            gw_matches = matches_df[matches_df['gameweek'] == gw]
            gw_matches.to_csv(os.path.join(gw_path, 'matches.csv'), index=False)
            print(f"Created GW{gw} with {len(gw_matches)} matches")
        else:
            print(f"GW{gw} already exists, skipping.")

    return matches_df
    
def update_player_match_stats(season_path, matches_df):
    """Updates playermatchstats.csv by gameweek and match_id, adding new data."""
    stats_path = os.path.join(season_path, 'playermatchstats', 'playermatchstats.csv')
    if not os.path.exists(stats_path):
        print(f"Player match stats file not found at {stats_path}")
        return

    stats_df = pd.read_csv(stats_path)
    print(f"Found {len(stats_df)} player match stats")

    gw_base_path = os.path.join(season_path, 'playermatchstats', 'gameweeks')

    # Create match_id to gameweek mapping
    match_to_gw = dict(zip(matches_df['match_id'], matches_df['gameweek']))
    stats_df['gameweek'] = stats_df['match_id'].map(match_to_gw)

    # Get existing gameweeks and match_ids
    existing_gameweeks = set()
    existing_matches = {}  # {gw: {match_id}}
    if os.path.exists(gw_base_path):
        for gw_dir in os.listdir(gw_base_path):
            if gw_dir.startswith('GW'):
                try:
                    gw = int(gw_dir[2:])
                    existing_gameweeks.add(gw)
                    existing_matches[gw] = set()
                    matches_dir = os.path.join(gw_base_path, gw_dir, 'matches')
                    if os.path.exists(matches_dir):
                      for match_file in os.listdir(matches_dir):
                        try:
                          match_id = int(match_file)
                          existing_matches.setdefault(gw, set()).add(match_id)
                        except ValueError:
                          pass
                except ValueError:
                    pass

    # Update or add data by gameweek and match_id
    for gw in stats_df['gameweek'].unique():
        if pd.isna(gw):
            print(f"Skipping records with missing gameweek")
            continue
        
        gw_int = int(gw)
        gw_path = os.path.join(gw_base_path, f'GW{gw_int}')
        create_directory(gw_path)

        gw_stats = stats_df[stats_df['gameweek'] == gw]

        if gw_int not in existing_gameweeks:
            gw_stats.to_csv(os.path.join(gw_path, 'playermatchstats.csv'), index=False)
            print(f"Created GW{gw_int} with {len(gw_stats)} player stats")
        else:
            print(f"GW{gw_int} already exists, checking matches.")
            existing_gw_stats_path = os.path.join(gw_path, 'playermatchstats.csv')
            if os.path.exists(existing_gw_stats_path):
                existing_gw_stats_df = pd.read_csv(existing_gw_stats_path)
            else:
                existing_gw_stats_df = pd.DataFrame(columns=gw_stats.columns)
            
            # Merge data, keeping the latest
            updated_gw_stats = pd.concat([existing_gw_stats_df, gw_stats]).drop_duplicates(subset=['player_id', 'match_id'], keep='last')
            updated_gw_stats.to_csv(existing_gw_stats_path, index=False)
            print(f"Updated GW{gw_int} with {len(updated_gw_stats)} player stats")

        for match_id in gw_stats['match_id'].unique():
            if gw_int not in existing_matches or match_id not in existing_matches[gw_int]:
                match_path = os.path.join(gw_path, 'matches', str(match_id))
                create_directory(match_path)

                match_stats = gw_stats[gw_stats['match_id'] == match_id]
                match_stats.to_csv(os.path.join(match_path, 'playermatchstats.csv'), index=False)
                print(f"  - Match {match_id}: {len(match_stats)} player stats")
            else:
                print(f"  - Match {match_id} in GW{gw_int} already exists, checking for updates.")
                match_path = os.path.join(gw_path, 'matches', str(match_id), 'playermatchstats.csv')
                if os.path.exists(match_path):
                  existing_match_stats_df = pd.read_csv(match_path)
                else:
                  existing_match_stats_df = pd.DataFrame(columns=gw_stats.columns)

                match_stats = gw_stats[gw_stats['match_id'] == match_id]
                
                # Merge data, keeping the latest
                updated_match_stats = pd.concat([existing_match_stats_df, match_stats]).drop_duplicates(subset=['player_id'], keep='last')
                updated_match_stats.to_csv(match_path, index=False)
                print(f"  - Updated Match {match_id} in GW{gw_int} with {len(updated_match_stats)} player stats")

def update_player_stats(season_path):
    """Updates playerstats.csv by gameweek, adding new data."""
    stats_path = os.path.join(season_path, 'playerstats', 'playerstats.csv')
    if not os.path.exists(stats_path):
        print(f"Player stats file not found at {stats_path}")
        return

    stats_df = pd.read_csv(stats_path)
    print(f"Found {len(stats_df)} player stats")

    gw_base_path = os.path.join(season_path, 'playerstats', 'gameweeks')

    # Get existing gameweeks
    existing_gameweeks = set()
    if os.path.exists(gw_base_path):
        for dirname in os.listdir(gw_base_path):
            if dirname.startswith('GW'):
                try:
                    gw = int(dirname[2:])
                    existing_gameweeks.add(gw)
                except ValueError:
                    pass

    # Update or add data by gameweek
    for gw in stats_df['gw'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)

        gw_stats = stats_df[stats_df['gw'] == gw]

        if gw not in existing_gameweeks:
            gw_stats.to_csv(os.path.join(gw_path, 'playerstats.csv'), index=False)
            print(f"Created GW{gw} with {len(gw_stats)} player stats")
        else:
            print(f"GW{gw} already exists, checking for updates.")
            existing_gw_stats_path = os.path.join(gw_path, 'playerstats.csv')
            if os.path.exists(existing_gw_stats_path):
                existing_gw_stats_df = pd.read_csv(existing_gw_stats_path)
                # Merge data, keeping the latest
                updated_gw_stats = pd.concat([existing_gw_stats_df, gw_stats]).drop_duplicates(subset=['player_id'], keep='last')
                updated_gw_stats.to_csv(existing_gw_stats_path, index=False)
                print(f"Updated GW{gw} with {len(updated_gw_stats)} player stats")
            else:
                gw_stats.to_csv(os.path.join(gw_path, 'playerstats.csv'), index=False)
                print(f"Created GW{gw} with {len(gw_stats)} player stats")

def main():
    season = "2024-2025"
    season_path = os.path.join('data', season)

    print(f"Starting CSV update process...")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Looking for data in: {season_path}")

    # Update matches and get DataFrame for reference
    print("\nUpdating matches by gameweek...")
    matches_df = update_matches_by_gameweek(season_path)

    if matches_df is not None:
        # Update player match stats using matches reference
        print("\nUpdating player match stats by gameweek and match_id...")
        update_player_match_stats(season_path, matches_df)

    # Update player stats
    print("\nUpdating player stats by gameweek...")
    update_player_stats(season_path)

    print("\nCSV update process completed!")

if __name__ == "__main__":
    main()