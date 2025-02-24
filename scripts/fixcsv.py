import os
import pandas as pd
from pathlib import Path

# Utility function to create directories
def create_directory(path):
    Path(path).mkdir(parents=True, exist_ok=True)

# Update matches for all gameweeks
def update_matches_by_gameweek(season_path):
    """
    Processes all gameweeks in matches_df and saves matches per gameweek.
    """
    matches_path = os.path.join(season_path, 'matches', 'matches.csv')
    matches_df = pd.read_csv(matches_path)
    gw_base_path = os.path.join(season_path, 'matches', 'gameweeks')
    create_directory(gw_base_path)

    for gw in matches_df['gameweek'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        gw_matches = matches_df[matches_df['gameweek'] == gw]
        gw_matches.to_csv(os.path.join(gw_path, 'matches.csv'), index=False)
        print(f"Updated GW{gw} with {len(gw_matches)} matches")

    return matches_df

# Update player match stats for all gameweeks
def update_player_match_stats(season_path, matches_df):
    """
    Processes all gameweeks in player match stats, mapping match_id to gameweek.
    """
    stats_path = os.path.join(season_path, 'playermatchstats', 'playermatchstats.csv')
    stats_df = pd.read_csv(stats_path)
    gw_base_path = os.path.join(season_path, 'playermatchstats', 'gameweeks')
    create_directory(gw_base_path)

    # Map match_id to gameweek using matches_df
    match_to_gw = matches_df.set_index('match_id')['gameweek'].to_dict()
    stats_df['gameweek'] = stats_df['match_id'].map(match_to_gw)

    # Warn about any stats that don’t map to a gameweek
    if stats_df['gameweek'].isna().any():
        print(f"Warning: {stats_df['gameweek'].isna().sum()} player stats have no matching gameweek.")

    total_stats = len(stats_df)
    print(f"Found {total_stats} player match stats across all gameweeks")

    for gw in stats_df['gameweek'].unique():
        if pd.isna(gw):
            continue  # Skip if gameweek is missing
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        gw_stats = stats_df[stats_df['gameweek'] == gw]
        gw_stats.to_csv(os.path.join(gw_path, 'playermatchstats.csv'), index=False)
        print(f"Updated GW{gw} with {len(gw_stats)} player match stats")

# Main execution function
def main():
    season = "2024-2025"
    season_path = os.path.join('data', season)

    # Process all gameweeks for matches and player match stats
    print("Updating matches by gameweek...")
    matches_df = update_matches_by_gameweek(season_path)

    print("\nUpdating player match stats by gameweek...")
    update_player_match_stats(season_path, matches_df)

    print("\nProcessing complete.")

if __name__ == "__main__":
    main()
