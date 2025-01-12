import os
import csv
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FPLDataPipeline:
    def __init__(self, season="2024-2025"):
        # Load environment variables
        load_dotenv()
        
        # Initialize Supabase client
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.supabase = create_client(self.url, self.key)
        
        # Set up paths
        self.season = season
        self.base_path = Path("data") / season
        
    def fetch_all_records(self, table_name: str) -> list:
        """Fetches all records from a table using pagination."""
        all_data = []
        page_size = 1000
        start = 0
        
        while True:
            response = (self.supabase.table(table_name)
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
            
        return all_data

    def export_table(self, table_name: str):
        """Exports a Supabase table to CSV format."""
        try:
            # Fetch all data using pagination
            data = self.fetch_all_records(table_name)
            
            if not data:
                logging.warning(f"No data found in table {table_name}")
                return None
            
            # Create directory structure
            output_dir = self.base_path / table_name
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Export CSV
            csv_file_path = output_dir / f"{table_name}.csv"
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
                
            logging.info(f"Successfully exported {table_name} (Total records: {len(data)})")
            return csv_file_path
            
        except Exception as e:
            logging.error(f"Error exporting {table_name}: {e}")
            return None

    def get_current_gameweek(self, matches_df):
        """Determine the current gameweek based on matches data."""
        if 'gameweek' not in matches_df.columns:
            return None
        return matches_df['gameweek'].max()

    def split_matches(self, matches_path):
        """Split matches.csv by gameweek."""
        if not matches_path.exists():
            logging.error(f"Matches file not found at {matches_path}")
            return None
        
        # Read matches data
        matches_df = pd.read_csv(matches_path)
        current_gw = self.get_current_gameweek(matches_df)
        logging.info(f"Current gameweek: {current_gw}")
        
        # Create gameweek directory
        gw_base_path = matches_path.parent / 'gameweeks'
        
        # Split and save by gameweek
        for gw in matches_df['gameweek'].unique():
            # Skip past gameweeks
            if gw < current_gw:
                logging.info(f"Skipping past gameweek {gw}")
                continue
                
            gw_path = gw_base_path / f'GW{gw}'
            gw_path.mkdir(parents=True, exist_ok=True)
            
            gw_matches = matches_df[matches_df['gameweek'] == gw]
            gw_matches.to_csv(gw_path / 'matches.csv', index=False)
            logging.info(f"Created GW{gw} with {len(gw_matches)} matches")
            
        return matches_df

    def split_player_match_stats(self, stats_path, matches_df):
        """Split playermatchstats.csv by gameweek and match_id."""
        if not stats_path.exists():
            logging.error(f"Player match stats file not found at {stats_path}")
            return
        
        # Read player match stats
        stats_df = pd.read_csv(stats_path)
        current_gw = self.get_current_gameweek(matches_df)
        
        # Create match_id to gameweek mapping
        match_to_gw = dict(zip(matches_df['match_id'], matches_df['gameweek']))
        
        # Add gameweek column to stats
        stats_df['gameweek'] = stats_df['match_id'].map(match_to_gw)
        
        # Create base directory
        gw_base_path = stats_path.parent / 'gameweeks'
        
        # Split and save by gameweek
        for gw in stats_df['gameweek'].unique():
            if pd.isna(gw) or gw < current_gw:
                continue
                
            gw_path = gw_base_path / f'GW{int(gw)}'
            gw_path.mkdir(parents=True, exist_ok=True)
            
            gw_stats = stats_df[stats_df['gameweek'] == gw]
            gw_stats.to_csv(gw_path / 'playermatchstats.csv', index=False)
            
            # Further split by match_id within gameweek
            for match_id in gw_stats['match_id'].unique():
                match_path = gw_path / 'matches' / str(match_id)
                match_path.mkdir(parents=True, exist_ok=True)
                
                match_stats = gw_stats[gw_stats['match_id'] == match_id]
                match_stats.to_csv(match_path / 'playermatchstats.csv', index=False)

    def split_player_stats(self, stats_path):
        """Split playerstats.csv by gameweek."""
        if not stats_path.exists():
            logging.error(f"Player stats file not found at {stats_path}")
            return
        
        # Read player stats
        stats_df = pd.read_csv(stats_path)
        current_gw = stats_df['gw'].max()
        
        # Create gameweek directory
        gw_base_path = stats_path.parent / 'gameweeks'
        
        # Split and save by gameweek
        for gw in stats_df['gw'].unique():
            if gw < current_gw:
                continue
                
            gw_path = gw_base_path / f'GW{gw}'
            gw_path.mkdir(parents=True, exist_ok=True)
            
            gw_stats = stats_df[stats_df['gw'] == gw]
            gw_stats.to_csv(gw_path / 'playerstats.csv', index=False)
            logging.info(f"Created GW{gw} with {len(gw_stats)} player stats")

    def process_data(self):
        """Main function to process all data."""
        logging.info("Starting data pipeline...")
        
        # Export all tables first
        tables = ["matches", "playermatchstats", "players", "playerstats", "teams"]
        exported_files = {}
        
        for table in tables:
            file_path = self.export_table(table)
            if file_path:
                exported_files[table] = file_path
        
        # Split data by gameweek
        if 'matches' in exported_files:
            matches_df = self.split_matches(exported_files['matches'])
            
            if matches_df is not None and 'playermatchstats' in exported_files:
                self.split_player_match_stats(exported_files['playermatchstats'], matches_df)
        
        if 'playerstats' in exported_files:
            self.split_player_stats(exported_files['playerstats'])
        
        logging.info("Data pipeline completed!")

if __name__ == "__main__":
    pipeline = FPLDataPipeline()
    pipeline.process_data()
