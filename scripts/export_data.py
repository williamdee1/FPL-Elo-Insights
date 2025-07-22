import os
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration ---
SEASON = "2025-2026"

# A map to rename tournament folders from their database name to a more readable name.
# If a tournament is not in this map, its original name will be used.
TOURNAMENT_NAME_MAP = {
    'friendly': 'friendlies',
    'premier-league': 'Premier League',
    'champions-league': 'Champions League'
}


# --- Setup: Load Environment Variables and Connect to Supabase ---
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("FATAL ERROR: SUPABASE_URL and SUPABASE_KEY must be set in your environment or a .env file.")
    exit()

supabase: Client = create_client(url, key)


# --- Helper Functions ---

def create_directory(path: str):
    """Creates a directory and its parents if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def get_latest_finished_gameweek() -> int:
    """Queries the database to find the latest gameweek with at least one finished match."""
    print("Querying database for the latest finished gameweek...")
    try:
        response = supabase.table('matches').select('gameweek').eq('finished', True).execute()
        
        if not response.data:
            print("  > No finished gameweeks found. Starting fresh from Gameweek 1.")
            return 1
        
        finished_gameweeks = [item['gameweek'] for item in response.data if item.get('gameweek') is not None]
        if not finished_gameweeks:
            print("  > No valid gameweeks in finished matches. Starting from Gameweek 1.")
            return 1

        latest_gw = max(finished_gameweeks)
        print(f"  > Latest finished gameweek found: {latest_gw}. Processing from this week onwards.")
        return latest_gw
    except Exception as e:
        print(f"  ERROR: Could not fetch latest gameweek: {e}. Defaulting to Gameweek 1.")
        return 1

def fetch_data_since_gameweek(table_name: str, start_gameweek: int, gameweek_col: str = 'gameweek') -> pd.DataFrame:
    """Fetches records from a table for a specific gameweek and all future ones."""
    print(f"Fetching data from '{table_name}' for GW{start_gameweek} onwards...")
    try:
        response = supabase.table(table_name).select('*').gte(gameweek_col, start_gameweek).execute()
        df = pd.DataFrame(response.data)
        print(f"  > Fetched {len(df)} rows from '{table_name}'.")
        return df
    except Exception as e:
        print(f"  ERROR fetching from '{table_name}': {e}")
        return pd.DataFrame()

def fetch_data_by_ids(table_name: str, column: str, ids: list) -> pd.DataFrame:
    """Fetches records where a column value is in a list of IDs, handling chunks."""
    if not ids:
        return pd.DataFrame()
        
    print(f"Fetching {len(ids)} related records from '{table_name}' using '{column}'...")
    all_data = []
    chunk_size = 500
    for i in range(0, len(ids), chunk_size):
        chunk_ids = ids[i:i + chunk_size]
        try:
            response = supabase.table(table_name).select('*').in_(column, chunk_ids).execute()
            all_data.extend(response.data)
        except Exception as e:
            print(f"  ERROR fetching chunk from '{table_name}': {e}")
    
    df = pd.DataFrame(all_data)
    print(f"  > Fetched {len(df)} total rows from '{table_name}'.")
    return df

def update_csv(df: pd.DataFrame, file_path: str, unique_cols: list):
    """Updates a CSV file with new data, keeping the latest records based on unique columns."""
    create_directory(os.path.dirname(file_path))
    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path)
        combined_df = pd.concat([existing_df, df])
    else:
        combined_df = df
    
    updated_df = combined_df.drop_duplicates(subset=unique_cols, keep='last')
    updated_df.to_csv(file_path, index=False)


def main():
    """Main function to run the entire data export and processing pipeline."""
    season_path = os.path.join('data', SEASON)
    print(f"--- Starting Automated Data Update for Season {SEASON} ---")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    start_gameweek = get_latest_finished_gameweek()

    matches_df = fetch_data_since_gameweek('matches', start_gameweek)
    if matches_df.empty:
        print("\nNo new or updated match data found. Process complete.")
        return

    relevant_match_ids = matches_df['match_id'].unique().tolist()
    player_match_stats_df = fetch_data_by_ids('playermatchstats', 'match_id', relevant_match_ids)
    player_stats_df = fetch_data_since_gameweek('playerstats', start_gameweek, gameweek_col='gw')

    active_player_ids = player_match_stats_df['player_id'].unique().tolist()
    home_team_ids = matches_df['home_team'].dropna().unique()
    away_team_ids = matches_df['away_team'].dropna().unique()
    active_team_ids_float = list(set(home_team_ids) | set(away_team_ids))
    active_team_ids = [int(i) for i in active_team_ids_float]

    players_df = fetch_data_by_ids('players', 'player_id', active_player_ids)
    teams_df = fetch_data_by_ids('teams', 'id', active_team_ids) 

    # --- Processing and Saving Data ---
    print("\n--- Processing and saving data into new directory structure ---")
    
    # Create necessary helper maps for processing
    match_to_tournament_map = {}
    for _, row in matches_df.iterrows():
        try:
            tournament_slug = row['match_id'].split('-')[2]
            # Use the rename map, or default to the original slug if not found
            tournament_folder_name = TOURNAMENT_NAME_MAP.get(tournament_slug, tournament_slug)
            match_to_tournament_map[row['match_id']] = tournament_folder_name
        except IndexError:
            print(f"  WARNING: Could not parse tournament from match_id: {row.get('match_id', 'N/A')}")
    
    # --- 1. Save data into the 'By Tournament' structure ---
    if not matches_df.empty:
        for gw, group in matches_df.groupby('gameweek'):
            for _, match in group.iterrows():
                tournament_folder = match_to_tournament_map.get(match['match_id'])
                if tournament_folder:
                    output_dir = os.path.join(season_path, "By Tournament", tournament_folder, f"GW{int(gw)}")
                    update_csv(pd.DataFrame([match]), os.path.join(output_dir, "matches.csv"), unique_cols=['match_id'])
    print("  > Processed 'matches' into 'By Tournament' structure.")

    if not player_match_stats_df.empty:
        match_to_gameweek_map = matches_df.set_index('match_id')['gameweek'].to_dict()
        player_match_stats_df['gameweek'] = player_match_stats_df['match_id'].map(match_to_gameweek_map)
        player_match_stats_df['tournament'] = player_match_stats_df['match_id'].map(match_to_tournament_map)
        player_match_stats_df.dropna(subset=['gameweek', 'tournament'], inplace=True)
        player_match_stats_df['gameweek'] = player_match_stats_df['gameweek'].astype(int)

        for (gw, tourn), group in player_match_stats_df.groupby(['gameweek', 'tournament']):
            output_dir = os.path.join(season_path, "By Tournament", tourn, f"GW{gw}")
            update_csv(group.drop(columns=['gameweek', 'tournament']), os.path.join(output_dir, "playermatchstats.csv"), unique_cols=['player_id', 'match_id'])
    print("  > Processed 'playermatchstats' into 'By Tournament' structure.")

    # --- 2. Save Gameweek Snapshots into the 'By Gameweek' structure ---
    if not player_stats_df.empty:
        for gw, group in player_stats_df.groupby('gw'):
            output_dir = os.path.join(season_path, "By Gameweek", f"GW{int(gw)}")
            update_csv(group, os.path.join(output_dir, "playerstats.csv"), unique_cols=['id', 'gw'])
    print("  > Processed 'playerstats' snapshots into 'By Gameweek' structure.")

    # NEW: Create weekly snapshots for players and teams
    if not players_df.empty:
        # We need to determine which gameweek this player data belongs to.
        # This is a simplification; we associate the player data with all active gameweeks.
        active_gameweeks = matches_df['gameweek'].unique()
        for gw in active_gameweeks:
            output_dir = os.path.join(season_path, "By Gameweek", f"GW{int(gw)}")
            update_csv(players_df, os.path.join(output_dir, "players.csv"), unique_cols=['player_id'])
    print("  > Processed 'players' snapshots into 'By Gameweek' structure.")

    if not teams_df.empty:
        active_gameweeks = matches_df['gameweek'].unique()
        for gw in active_gameweeks:
            output_dir = os.path.join(season_path, "By Gameweek", f"GW{int(gw)}")
            update_csv(teams_df, os.path.join(output_dir, "teams.csv"), unique_cols=['id'])
    print("  > Processed 'teams' snapshots into 'By Gameweek' structure.")

    # --- 3. Update Master Files in the root season folder ---
    print("\n--- Updating master data files ---")
    if not players_df.empty:
        update_csv(players_df, os.path.join(season_path, 'players.csv'), unique_cols=['player_id'])
        print("  > Master 'players.csv' updated.")
    
    if not teams_df.empty:
        update_csv(teams_df, os.path.join(season_path, 'teams.csv'), unique_cols=['id'])
        print("  > Master 'teams.csv' updated.")

    print("\n--- Automated data update process completed successfully! ---")


if __name__ == "__main__":
    main()
