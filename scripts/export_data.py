import os
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# --- Setup: Load Environment Variables and Connect to Supabase ---
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Check for credentials before creating a client
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
        # We only need the 'gameweek' column for this, which is efficient
        response = supabase.table('matches').select('gameweek').eq('finished', True).execute()
        
        if not response.data:
            print("  > No finished gameweeks found in the database. Starting fresh from Gameweek 1.")
            return 1
        
        # Extract all gameweek numbers and find the maximum
        finished_gameweeks = [item['gameweek'] for item in response.data if item.get('gameweek') is not None]
        if not finished_gameweeks:
            print("  > No valid gameweeks found in finished matches. Starting from Gameweek 1.")
            return 1

        latest_gw = max(finished_gameweeks)
        print(f"  > Latest finished gameweek found in database: {latest_gw}")
        return latest_gw
    except Exception as e:
        print(f"  ERROR: Could not fetch latest gameweek due to an error: {e}. Defaulting to Gameweek 1.")
        return 1

def fetch_data_since_gameweek(table_name: str, start_gameweek: int, gameweek_col: str = 'gameweek') -> pd.DataFrame:
    """Fetches all records from a table for a specific gameweek and all future gameweeks."""
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
    """Fetches records where a column value is in a provided list of IDs."""
    if not ids:
        return pd.DataFrame()
        
    print(f"Fetching {len(ids)} related records from '{table_name}' using '{column}'...")
    all_data = []
    # Supabase has a limit on the number of values in an .in() filter, so we process in chunks
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
    """
    Updates a CSV file with new data. It reads the existing file, appends the new data,
    and removes duplicates, keeping only the last (newest) entry for each unique record.
    """
    # Ensure the directory for the file exists
    create_directory(os.path.dirname(file_path))

    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path)
        combined_df = pd.concat([existing_df, df])
    else:
        combined_df = df
    
    # Drop duplicates based on the key identifier columns, keeping the latest entry
    updated_df = combined_df.drop_duplicates(subset=unique_cols, keep='last')
    updated_df.to_csv(file_path, index=False)


def main():
    """Main function to run the entire data export and processing pipeline."""
    season = "2024-2025"
    season_path = os.path.join('data', season)
    print(f"--- Starting Automated Data Update for Season {season} ---")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # 1. INTELLIGENTLY DETERMINE WHICH GAMEWEEKS TO PROCESS
    # We find the last gameweek that was marked as 'finished' in the database.
    # We will re-process this gameweek and all subsequent ones to catch updates.
    start_gameweek = get_latest_finished_gameweek()

    # 2. FETCH ONLY THE NECESSARY DATA FROM THE DATABASE
    matches_df = fetch_data_since_gameweek('matches', start_gameweek)
    if matches_df.empty:
        print("\nNo new or updated match data found since last finished gameweek. Process complete.")
        return

    # From the new matches, get IDs to fetch all related data
    relevant_match_ids = matches_df['match_id'].unique().tolist()
    player_match_stats_df = fetch_data_by_ids('playermatchstats', 'match_id', relevant_match_ids)
    
    # Fetch playerstats for the relevant gameweeks
    player_stats_df = fetch_data_since_gameweek('playerstats', start_gameweek, gameweek_col='gw')

    # Collect unique IDs to update master files for players and teams
    all_player_ids = player_match_stats_df['player_id'].unique().tolist()
    home_team_ids = matches_df['home_team_id'].unique()
    away_team_ids = matches_df['away_team_id'].unique()
    all_team_ids = list(set(home_team_ids) | set(away_team_ids))

    players_df = fetch_data_by_ids('players', 'player_id', all_player_ids)
    teams_df = fetch_data_by_ids('teams', 'team_id', all_team_ids)

    # 3. PROCESS AND SAVE THE FETCHED DATA INTO CSV FILES
    
    # --- Process Matches and PlayerMatchStats (Split by GW and Tournament) ---
    print("\n--- Processing and saving data split by Gameweek and Tournament ---")
    
    # Create a mapping of match_id to its tournament for easy lookup
    match_to_tournament_map = {}
    for _, row in matches_df.iterrows():
        try:
            tournament = row['match_id'].split('-')[2]
            match_to_tournament_map[row['match_id']] = tournament
        except IndexError:
            print(f"  WARNING: Could not parse tournament from match_id: {row.get('match_id', 'N/A')}")
    
    # Process Matches
    for gw, group in matches_df.groupby('gameweek'):
        for _, match in group.iterrows():
            tournament = match_to_tournament_map.get(match['match_id'])
            if tournament:
                output_dir = os.path.join(season_path, f"GW{gw}", tournament)
                file_path = os.path.join(output_dir, "matches.csv")
                update_csv(pd.DataFrame([match]), file_path, unique_cols=['match_id'])
    print("  > Finished processing 'matches'.")

    # Process PlayerMatchStats
    if not player_match_stats_df.empty:
        # Add 'gameweek' and 'tournament' columns to the stats dataframe for easy processing
        match_to_gameweek_map = matches_df.set_index('match_id')['gameweek'].to_dict()
        player_match_stats_df['gameweek'] = player_match_stats_df['match_id'].map(match_to_gameweek_map)
        player_match_stats_df['tournament'] = player_match_stats_df['match_id'].map(match_to_tournament_map)

        # Group by the new columns and save
        for (gw, tourn), group in player_match_stats_df.groupby(['gameweek', 'tournament']):
            if pd.isna(gw) or pd.isna(tourn):
                continue
            output_dir = os.path.join(season_path, f"GW{int(gw)}", tourn)
            file_path = os.path.join(output_dir, "playermatchstats.csv")
            update_csv(group.drop(columns=['gameweek', 'tournament']), file_path, unique_cols=['player_id', 'match_id'])
    print("  > Finished processing 'playermatchstats'.")

    # --- Process PlayerStats (Split by GW only) ---
    print("\n--- Processing and saving Player Stats by Gameweek ---")
    if not player_stats_df.empty:
        for gw, group in player_stats_df.groupby('gw'):
            output_dir = os.path.join(season_path, f"GW{int(gw)}")
            file_path = os.path.join(output_dir, "playerstats.csv")
            update_csv(group, file_path, unique_cols=['id', 'gw']) # Assuming 'id' is player_id and 'gw' is gameweek
    print("  > Finished processing 'playerstats'.")

    # --- Update Master Files (Players and Teams) ---
    print("\n--- Updating master data files ---")
    if not players_df.empty:
        update_csv(players_df, os.path.join(season_path, 'players.csv'), unique_cols=['player_id'])
        print("  > Master 'players.csv' updated.")
    
    if not teams_df.empty:
        update_csv(teams_df, os.path.join(season_path, 'teams.csv'), unique_cols=['team_id'])
        print("  > Master 'teams.csv' updated.")

    print("\n--- Automated data update process completed successfully! ---")


if __name__ == "__main__":
    main()
