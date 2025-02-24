import os
import pandas as pd
from pathlib import Path

# Utility function to create directories
def create_directory(path):
    Path(path).mkdir(parents=True, exist_ok=True)

# Function to determine the latest finished gameweek (for logging only)
def get_latest_finished_gameweek(season_path):
    """
    Determines the latest gameweek with at least one finished match.
    This is kept for informational purposes but not used for filtering.
    """
    matches_path = os.path.join(season_path, 'matches', 'matches.csv')
    matches_df = pd.read_csv(matches_path)
    # Assuming there's a 'finished' column indicating match status
    finished_matches = matches_df[matches_df['finished'] == True]
    if not finished_matches.empty:
        latest = finished_matches['gameweek'].max()
    else:
        latest = 0  # Default if no matches are finished
    return latest

# Update matches for all gameweeks
def update_matches_by_gameweek(season_path):
    """
    Processes all gameweeks in matches_df and saves matches per gameweek.
    No skipping based on latest_finished_gameweek.
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
    No skipping based on latest_finished_gameweek.
    """
    stats_path = os.path.join(season_path, 'playermatchstats', 'playermatchstats.csv')
    stats_df = pd.read_csv(stats_path)
    gw_base_path = os.path.join(season_path, 'playermatchstats', 'gameweeks')
    create_directory(gw_base_path)

    # Create a mapping from match_id to gameweek using matches_df
    match_to_gw = matches_df.set_index('match_id')['gameweek'].to_dict()
    stats_df['gameweek'] = stats_df['match_id'].map(match_to_gw)

    # Handle any unmapped gameweeks (e.g., missing matches)
    if stats_df['gameweek'].isna().any():
        print(f"Warning: {stats_df['gameweek'].isna().sum()} player stats have no matching gameweek.")

    total_stats = len(stats_df)
    print(f"Found {total_stats} player match stats across all gameweeks")

    for gw in stats_df['gameweek'].unique():
        if pd.isna(gw):
            continue  # Skip if gameweek is NaN
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        gw_stats = stats_df[stats_df['gameweek'] == gw]
        gw_stats.to_csv(os.path.join(gw_path, 'playermatchstats.csv'), index=False)
        print(f"Updated GW{gw} with {len(gw_stats)} player match stats")

# Update player stats for all gameweeks
def update_player_stats(season_path):
    """
    Processes all gameweeks in player stats.
    No skipping based on latest_finished_gameweek.
    """
    stats_path = os.path.join(season_path, 'playerstats', 'playerstats.csv')
    stats_df = pd.read_csv(stats_path)
    gw_base_path = os.path.join(season_path, 'playerstats', 'gameweeks')
    create_directory(gw_base_path)

    # Assuming stats_df has a 'gameweek' column
    total_stats = len(stats_df)
    print(f"Found {total_stats} player stats across all gameweeks")

    for gw in stats_df['gameweek'].unique():
        gw_path = os.path.join(gw_base_path, f'GW{gw}')
        create_directory(gw_path)
        gw_stats = stats_df[stats_df['gameweek'] == gw]
        gw_stats.to_csv(os.path.join(gw_path, 'playerstats.csv'), index=False)
        print(f"Updated GW{gw} with {len(gw_stats)} player stats")

# Main execution function
def main():
    season = "2024-2025"
    season_path = os.path.join('data', season)

    # Calculate latest finished gameweek for logging (optional)
    latest_finished_gameweek = get_latest_finished_gameweek(season_path)
    print(f"Latest gameweek with at least one finished match: {latest_finished_gameweek}")

    # Process all gameweeks for matches, player match stats, and player stats
    print("\nUpdating matches by gameweek...")
    matches_df = update_matches_by_gameweek(season_path)

    print("\nUpdating player match stats by gameweek...")
    update_player_match_stats(season_path, matches_df)

    print("\nUpdating player stats by gameweek...")
    update_player_stats(season_path)

    print("\nProcessing complete.")

if __name__ == "__main__":
    main()
