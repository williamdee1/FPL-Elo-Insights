import os
import csv
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Supabase Connection ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def fetch_all_records(table_name: str) -> list:
    """Fetches all records from a table using pagination."""
    all_data = []
    page_size = 1000
    start = 0
    print(f"Fetching all records from '{table_name}'...")
    while True:
        try:
            response = (supabase.table(table_name)
                       .select("*")
                       .range(start, start + page_size - 1)
                       .execute())
            
            page_data = response.data
            if not page_data:
                break
                
            all_data.extend(page_data)
            
            if len(page_data) < page_size:
                break
                
            start += page_size
        except Exception as e:
            print(f"  ERROR: Could not fetch from {table_name}. Reason: {e}")
            return [] # Return empty list on error
            
    print(f"  > Found {len(all_data)} total records for '{table_name}'.")
    return all_data

def fetch_filtered_records(table_name: str, column: str, values: list) -> list:
    """Fetches records from a table filtered by a list of values in a column."""
    all_data = []
    page_size = 1000 # Supabase has a limit on how many values can be in an .in() filter
    
    # Process values in chunks to avoid hitting database limits
    for i in range(0, len(values), page_size):
        chunk_values = values[i:i + page_size]
        try:
            response = (supabase.table(table_name)
                       .select("*")
                       .in_(column, chunk_values)
                       .execute())
            
            page_data = response.data
            if page_data:
                all_data.extend(page_data)

        except Exception as e:
            print(f"  ERROR: Could not fetch filtered data from {table_name}. Reason: {e}")
            continue # Continue to next chunk
            
    print(f"  > Found {len(all_data)} filtered records in '{table_name}'.")
    return all_data

def export_data(data: list, table_name: str, output_dir: str):
    """Exports a list of data to both CSV and SQL formats in the specified directory."""
    if not data:
        print(f"Skipping export for '{table_name}' as no data was provided.")
        return

    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # --- Export to CSV ---
        csv_file_path = os.path.join(output_dir, f"{table_name}.csv")
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            
        # --- Export to SQL ---
        sql_file_path = os.path.join(output_dir, f"{table_name}.sql")
        with open(sql_file_path, 'w', encoding='utf-8') as sqlfile:
            # Add timestamp and metadata comment
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sqlfile.write(f"-- Data export from {table_name}\n")
            sqlfile.write(f"-- Generated on {timestamp}\n")
            sqlfile.write(f"-- Total records: {len(data)}\n\n")
            
            # Write DROP and CREATE TABLE statements
            sqlfile.write(f"DROP TABLE IF EXISTS {table_name};\n")
            columns = data[0].keys()
            create_table = f"CREATE TABLE {table_name} (\n"
            create_table += ",\n".join(f"    {col} TEXT" for col in columns)
            create_table += "\n);\n\n"
            sqlfile.write(create_table)
            
            # Write INSERT statements in batches for efficiency
            batch_size = 500
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                for row in batch:
                    # Properly format values for SQL, handling None and single quotes
                    values = [str(val).replace("'", "''") if val is not None else 'NULL' for val in row.values()]
                    values_str = ", ".join(f"'{val}'" if val != 'NULL' else val for val in values)
                    insert_stmt = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values_str});\n"
                    sqlfile.write(insert_stmt)
                
        print(f"  > Successfully exported '{table_name}' to {output_dir}")

    except Exception as e:
        print(f"  ERROR exporting {table_name}: {e}")
        return

def main():
    """Main function to export all tables with the new directory structure."""
    season = "2025-2026"
    season_dir = os.path.join("data", season)

    # --- PART 1: EXPORT GLOBAL TABLES ---
    print("--- Starting export for global season tables ---")
    global_tables = ["players", "playerstats", "teams"]
    for table in global_tables:
        table_data = fetch_all_records(table)
        if table_data:
            export_data(table_data, table, season_dir)
    print("--- Global tables export complete ---\n")

    # --- PART 2: EXPORT TOURNAMENT-SPECIFIC TABLES ---
    print("--- Starting export for tournament-specific tables ---")
    
    # Step A: Discover all tournaments from the 'matches' table
    all_matches = fetch_all_records("matches")
    if not all_matches:
        print("No matches found. Cannot proceed with tournament-specific exports.")
        return

    unique_tournaments = set()
    for match in all_matches:
        try:
            # Assumes match_id format is 'season-tournament-home-vs-away'
            tournament_name = match['match_id'].split('-')[1]
            unique_tournaments.add(tournament_name)
        except (KeyError, IndexError):
            print(f"  WARNING: Could not parse tournament from match_id: {match.get('match_id', 'N/A')}")
            continue
    
    if not unique_tournaments:
        print("Could not identify any unique tournaments from match data.")
        return
        
    print(f"Discovered {len(unique_tournaments)} tournaments: {', '.join(unique_tournaments)}")

    # Step B: Loop through each tournament and export its data
    for tournament in unique_tournaments:
        print(f"\n--- Processing tournament: {tournament} ---")
        tournament_dir = os.path.join(season_dir, tournament)

        # Filter and export 'matches' for the current tournament
        tournament_matches = [m for m in all_matches if m['match_id'].split('-')[1] == tournament]
        export_data(tournament_matches, "matches", tournament_dir)

        # Filter and export 'playermatchstats' for the current tournament
        match_ids_for_tournament = [m['match_id'] for m in tournament_matches]
        if match_ids_for_tournament:
            player_stats_data = fetch_filtered_records("playermatchstats", "match_id", match_ids_for_tournament)
            export_data(player_stats_data, "playermatchstats", tournament_dir)
        else:
            print(f"No matches found for tournament '{tournament}', skipping playermatchstats.")

    print("\n--- All exports complete! ---")


if __name__ == "__main__":
    main()
