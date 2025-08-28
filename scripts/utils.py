
import polars as pl
from scripts.data_curate_25 import FplData


def check_in_colname(df, value):
    """
    Check if a value exists in the column names of a DataFrame.
    """
    return [x for x in df.columns if value in x]

def return_player_id(fpl_data: FplData, 
                     search_string: str) -> int:
    """
    Return the player ID for a given player name.

    Example: return_player_id(fpl_data, "Salah")
    """
    player_id = fpl_data.gw_data_combined['players'].filter(
                    (pl.col("first_name").str.to_lowercase().str.contains(search_string.lower())) |
                    (pl.col("second_name").str.to_lowercase().str.contains(search_string.lower()))
                )["player_id"].unique()

    if player_id.shape[0] == 0:
        raise ValueError(f"Player '{search_string}' not found.")
    elif player_id.shape[0] > 1:
        raise ValueError(f"Multiple players found for '{search_string}'. Please be more specific.")
    else:
        return player_id[0]

def return_player_data(fpl_data: FplData, 
                       player_id: int = None,
                       player_name: str = None) -> pl.DataFrame:
    """
    Return the merged data for a given player ID or name.
    """
    if player_id is not None:
        player_data = fpl_data.merged_data.filter(pl.col("player_id") == player_id)
    elif player_name is not None:
        player_id = return_player_id(fpl_data, player_name)
        player_data = fpl_data.merged_data.filter(pl.col("player_id") == player_id)
    else:
        raise ValueError("Either player_id or player_name must be provided.")

    return player_data

def return_team_id(fpl_data: FplData, search_string: str) -> int:
    """
    Return the team ID (actually code aligns with the rest of the data) for a given team name.

    Example: return_team_id(fpl_data, "Manchester City")
    """
    team_id = fpl_data.gw_data_combined['teams'].filter(
                    pl.col("team_name").str.to_lowercase().str.contains(search_string.lower())
                )["team_code"].unique()

    if team_id.shape[0] == 0:
        raise ValueError(f"Team '{search_string}' not found.")
    elif team_id.shape[0] > 1:
        raise ValueError(f"Multiple teams found for '{search_string}'. Please be more specific.")
    else:
        return team_id[0]

def return_team_name(fpl_data: FplData, team_id: int) -> str:
    """
    Return the team name for a given team ID.
    """
    team_name = fpl_data.gw_data_combined['teams'].filter(
                    pl.col("team_code") == team_id
                )["team_name"].unique()

    if team_name.shape[0] == 0:
        raise ValueError(f"Team with ID '{team_id}' not found.")
    elif team_name.shape[0] > 1:
        raise ValueError(f"Multiple teams found for ID '{team_id}'. Please be more specific.")
    else:
        return team_name[0]

def return_team_data(fpl_data: FplData, 
                     team_id: int = None,
                     team_name: str = None,
                     gw_range: tuple = None) -> pl.DataFrame:
    """
    Return the merged data for a given team ID or name.
    """
    if team_id is not None:
        team_data = fpl_data.merged_data.filter(pl.col("team_code") == team_id)
    elif team_name is not None:
        team_id = return_team_id(fpl_data, team_name)
        team_data = fpl_data.merged_data.filter(pl.col("team_code") == team_id)
    else:
        raise ValueError("Either team_id or team_name must be provided.")
    
    # Filter to remove player-specific data:
    # Team goals conceded relates to the teams goals conceded when each player was on the field
    # Overall team goals conceded is represented by "opp_score"
    team_data = team_data.drop(["team_goals_conceded"])
    team_cols = [c for c in team_data.columns if "team" in c] or [c for c in team_data.columns if "opp" in c]
    keep_cols = ["match_id", "goal_difference", "clean_sheet"] + team_cols

    # Filter to only include specific gameweeks
    if gw_range:
        team_data = team_data.filter(pl.col("gw").is_between(gw_range[0], gw_range[1]))

    return team_data[keep_cols].unique() # Effectively removes player-specific data