import os
import pandas as pd
import numpy as np
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)

def update_matches_by_gameweek(season_path):
    """Updates matches.csv by gameweek for all gameweeks."""
    matches_path = os.path.join(season_path, 'matches', 'matches.csv')
    if not os.path.exists(matches_path):
        print(f"Matches file not found at {matches_path}")
        return None

    matches_df = pd.read_csv(matches_path)
    print(f"Found {len(matches_df)} matches")

    gw_base_path = os.path.join(season_path, 'matches', 'gameweeks')

    # Split and save by gameweek for all gameweeks
    for gw in matches_df['gameweek'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)

        gw_matches = matches_df[matches_df['gameweek'] == gw]
        gw_matches.to_csv(os.path.join(gw_path, 'matches.csv'), index=False)
        print(f"Updated GW{gw} with {len(gw_matches)} matches")

    return matches_df

def update_player_match_stats(season_path, matches_df):
    """Updates playermatchstats.csv for all gameweeks."""
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

    # Update or add data by gameweek and match_id for all gameweeks
    for gw in stats_df['gameweek'].unique():
        if pd.isna(gw):
            print(f"Skipping records with missing gameweek")
            continue

        gw_int = int(gw)
        gw_path = os.path.join(gw_base_path, f'GW{gw_int}')
        create_directory(gw_path)

        gw_stats = stats_df[stats_df['gameweek'] == gw]

        # Check if gameweek exists
        existing_gw_stats_path = os.path.join(gw_path, 'playermatchstats.csv')
        if os.path.exists(existing_gw_stats_path):
            existing_gw_stats_df = pd.read_csv(existing_gw_stats_path)
            # Ensure consistent columns before merging
            for col in gw_stats.columns:
                if col not in existing_gw_stats_df.columns:
                    existing_gw_stats_df[col] = None
            for col in existing_gw_stats_df.columns:
                if col not in gw_stats.columns:
                    gw_stats[col] = None
        else:
            existing_gw_stats_df = pd.DataFrame(columns=gw_stats.columns)

        # Merge and update
        updated_gw_stats = pd.concat([existing_gw_stats_df, gw_stats]).drop_duplicates(subset=['player_id', 'match_id'], keep='last')
        updated_gw_stats.to_csv(existing_gw_stats_path, index=False)
        print(f"Updated GW{gw_int} with {len(updated_gw_stats)} player stats")

        for match_id in gw_stats['match_id'].unique():
            match_id_str = str(match_id)
            match_path = os.path.join(gw_path, 'matches', match_id_str)
            create_directory(match_path)

            match_stats = gw_stats[gw_stats['match_id'] == match_id]
            match_stats_path = os.path.join(match_path, 'playermatchstats.csv')

            # Check if match exists
            if os.path.exists(match_stats_path):
                existing_match_stats_df = pd.read_csv(match_stats_path)
                # Ensure consistent columns before merging
                for col in match_stats.columns:
                    if col not in existing_match_stats_df.columns:
                        existing_match_stats_df[col] = None
                for col in existing_match_stats_df.columns:
                    if col not in match_stats.columns:
                        match_stats[col] = None
            else:
                existing_match_stats_df = pd.DataFrame(columns=match_stats.columns)

            # Merge and update
            updated_match_stats = pd.concat([existing_match_stats_df, match_stats]).drop_duplicates(subset=['player_id', 'match_id'], keep='last')
            updated_match_stats.to_csv(match_stats_path, index=False)
            print(f"  - Updated Match {match_id_str} in GW{gw_int} with {len(updated_match_stats)} player stats")

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

    print("\nCSV update process completed!")

if __name__ == "__main__":
    main()
