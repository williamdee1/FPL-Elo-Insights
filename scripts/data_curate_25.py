from pathlib import Path
import polars as pl


class FplData:
    def __init__(self, year='2025-2026'):
        self.year = year
        self.base_path = Path(f"data/{year}") / "By Gameweek"

    def __init_data__(self):
        self.gw_data = {}
        self.gw_folders = self.get_gw_folders()

        files = ['matches',                     # Stats about each team, i.e. home/away score/ shots
                 'playermatchstats',            # Stats about each player's performance in each match
                 'players',                     # Information about players
                 'teams',                       # Information about teams
                 'playerstats'                  # Stats from Fantasy Premier League relating to each player
                 ]

        #---- Load Data for Each Gameweek
        for gw in self.gw_folders:
            gw_num = int(gw.name.split("GW")[1])
            gw_dict = {}
            for file_name in files:
                df = self.load_gw_data(gw_num, f"{file_name}.csv")
                if df is None:
                    gw_dict = None
                    break
                gw_dict[(gw.name, file_name)] = df

            if gw_dict is not None:  # only add if all files were present
                self.gw_data.update(gw_dict)

        #---- Combine data for each file across Gameweeks
        self.gw_data_combined = {}
        for file_name in files:
            dfs = [df for (_, fname), df in self.gw_data.items() if fname == file_name]
            if dfs:
                df = pl.concat(dfs, how="vertical_relaxed")
                # Drop cols where all values are null
                df = df.drop([c for c in df.columns if df.select(pl.col(c).is_null().all()).item()])
                self.gw_data_combined[file_name] = df

        #----- Clean and Merge the Data:
        self.clean_data()
        self.merged_data = self.merge_data()

        #----- Curate home and away team data:
        self.merged_data = self.curate_home_and_away()

    def get_gw_folders(self):
        # Return list of all gameweek folders:
        return sorted([f for f in self.base_path.iterdir() if f.is_dir() and f.name.startswith("GW") and not f.name.startswith("GW0")])

    def load_gw_data(self, gw_num, file_name):
        # Load specific data file for a given gameweek
        gw_file_path = self.base_path / f"GW{gw_num}" / file_name
        if gw_file_path.exists():
            df = pl.read_csv(gw_file_path)
            if df.shape[0] == 0:
                return None
            df = df.with_columns(pl.lit(gw_num).alias("gw"))  # Add gameweek number
            if file_name == 'matches.csv':
                df = df.filter(pl.col("tournament") == "prem") # Ensure only PL matches are included
            
            return df
        else:
            return None

    def clean_data(self):
        # Clean the combined dataframes
        for key, df in self.gw_data_combined.items():
            if key == 'matches':
                match_drop_cols = ["kickoff_time", "finished", "home_throws", "away_throws", 
                   "home_red_cards", "away_red_cards", "home_yellow_cards", "away_yellow_cards",
                   "stats_processed", "player_stats_processed", 
                   "home_walking_distance", "away_walking_distance", "home_sprinting_distance",
                   "away_sprinting_distance", "home_top_speed", "away_top_speed", "match_url",
                   "fotmob_id", 'tournament', "home_distance_covered", "away_distance_covered",
                   "home_number_of_sprints", "away_number_of_sprints", "home_running_distance",
                   "away_running_distance", "gameweek"]
                pct_cols = [c for c in df.columns if c.endswith("_pct")]
                df = df.drop(match_drop_cols + pct_cols)
            if key == 'teams':
                df = df.rename({'id': 'team_id'})
                df = df.rename({'code': 'team_code'})
                df = df.rename({'name': 'team_name'})
            if key == 'playerstats':
                df = df.rename({'id': 'player_id'})
                df = df.drop(['dreamteam_count'])
            self.gw_data_combined[key] = df

    def merge_data(self):
        # First merge the player match data with the match data:
        player_match_stats = self.gw_data_combined['playermatchstats']
        matches = self.gw_data_combined['matches']
        merged = player_match_stats.join(matches, 
                                         on=["match_id", "gw"], 
                                         how="inner")
        
        # Then merge in the player data:
        players = self.gw_data_combined['players']
        merged = merged.join(players[['player_id', 'team_code', 'gw', 'position']], 
                             on=["player_id", "gw"], 
                             how="inner")
        
        # Then merge in team data:
        teams = self.gw_data_combined['teams']
        merged = merged.join(teams[['team_code', 'strength', 'elo', 'gw', 'team_name']], 
                             on=["team_code", "gw"], 
                             how="inner")       
        

        # Then merge with the fpl player stats data:
        fpl_player_stats = self.gw_data_combined['playerstats']
        merged = merged.join(fpl_player_stats, 
                             on=["player_id", "gw"], 
                             how="left") # !! Note, this drops all players who haven't played yet this season
        
        # Drop chances of playing columns:
        merged = merged.drop(['chance_of_playing_next_round', 'chance_of_playing_this_round'])

        # Determine if player was home or away
        merged = merged.with_columns(
                    (pl.col("team_code") == pl.col("home_team")).alias("was_home")
                )

        # Cast boolean cols:
        bool_cols = [c for c, dt in zip(merged.columns, merged.dtypes) if dt == pl.Boolean]
        if bool_cols:
            merged = merged.with_columns([pl.col(c).cast(pl.Float64) for c in bool_cols])

        return merged
    
    def curate_home_and_away(self):

        # Split the merged dataframe into home and away dataframes
        self.merged_data = rename_home_away_columns(self.merged_data)

        self.merged_data = self.merged_data.with_columns([
                (pl.col('team_score') - pl.col('opp_score')).alias('goal_difference'),
                (pl.col('opp_score') == 0).cast(pl.Float64).alias('clean_sheet'),
                (pl.col('team_score') > pl.col('opp_score')).cast(pl.Float64).alias('team_won'),
            (pl.col('team_score') == pl.col('opp_score')).cast(pl.Float64).alias('team_drew'),
            (pl.col('team_score') < pl.col('opp_score')).cast(pl.Float64).alias('team_lost'),
        ])

        return self.merged_data


def rename_home_away_columns(df):
    """
    Transform home/away column pairs into own/opponent perspective based on team location.
    
    This function standardizes match data from a neutral perspective to a team-specific 
    perspective by renaming columns based on whether the team was playing at home or away.
    
    Args:
        df (polars.DataFrame): Input DataFrame containing match data with:
            - 'was_home' column: Boolean indicating if team was playing at home (1.0) or away (0.0)
            - Paired columns with 'home' and 'away' prefixes (e.g., 'home_team'/'away_team')
    
    Returns:
        polars.DataFrame: Transformed DataFrame where:
            - Home/away column pairs are replaced with own/opp pairs
            - 'own_*' columns represent the team's own stats/info
            - 'opp_*' columns represent the opponent's stats/info
            - All other columns (including 'was_home') are preserved unchanged
    
    Example:
        Input columns: ['player_id', 'was_home', 'home_team', 'away_team', 'home_score', 'away_score']
        
        For a player with was_home=1.0:
            - home_team -> own_team (team's own team)
            - away_team -> opp_team (opponent team)
            - home_score -> own_score (team's score)
            - away_score -> opp_score (opponent's score)
            
        For a player with was_home=0.0:
            - home_team -> opp_team (opponent team) 
            - away_team -> own_team (team's own team)
            - home_score -> opp_score (opponent's score)
            - away_score -> own_score (team's score)
    
    Note:
        - Only processes columns that have matching home/away pairs
        - Preserves the 'was_home' column for reference
        - Uses conditional logic to swap values based on team location
    """
    transformations = []
    other_cols = []
    
    for col in df.columns:
        if "home" in col.lower() and col != "was_home":  # Exclude was_home
            away_col = col.replace("home", "away")
            if away_col in df.columns:
                # Create team_ column
                team_col = col.replace("home", "team")
                transformations.append(
                    pl.when(pl.col("was_home") == 1.0)
                    .then(pl.col(col))
                    .otherwise(pl.col(away_col))
                    .alias(team_col)
                )
                
                # Create opp_ column  
                opp_col = away_col.replace("away", "opp")
                transformations.append(
                    pl.when(pl.col("was_home") == 1.0)
                    .then(pl.col(away_col))
                    .otherwise(pl.col(col))
                    .alias(opp_col)
                )
        elif "away" not in col.lower() or col == "was_home":  # Keep was_home
            # Keep non-home/away columns (and was_home)
            other_cols.append(pl.col(col))
    
    return df.select(other_cols + transformations)