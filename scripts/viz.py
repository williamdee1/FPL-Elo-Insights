import matplotlib.pyplot as plt
import polars as pl
import pandas as pd
import numpy as np

from scripts.data_curate_25 import FplData
from scripts.utils import return_team_name, return_team_data


def plot_player_cumulative_points(ml_dataset_featured, player_id, figsize=(12, 6)):
    """
    Plot cumulative FPL points for a specific player throughout the season
    
    Parameters:
    -----------
    ml_dataset_featured : pl.DataFrame
        The featured ML dataset containing player data (Polars DataFrame)
    player_id : int
        The player's element/player_id
    figsize : tuple
        Figure size for the plot (width, height)
    
    Returns:
    --------
    fig, ax : matplotlib figure and axis objects
    """
    # Filter data for the specific player
    player_data = ml_dataset_featured.filter(pl.col('element') == player_id)
    
    if player_data.is_empty():
        print(f"No data found for player_id: {player_id}")
        return None, None
    
    # Sort by gameweek to ensure correct order
    player_data = player_data.sort('gameweek')
    
    # Get player name (handle different possible column names)
    if 'name' in player_data.columns:
        player_name = player_data['name'][0]
    elif 'web_name' in player_data.columns:
        player_name = player_data['web_name'][0]
    else:
        player_name = f"Player {player_id}"
    
    # Calculate cumulative points
    player_data = player_data.with_columns(
        pl.col('total_points').cum_sum().alias('cumulative_points')
    )
    
    # Convert to pandas for matplotlib (or extract as numpy arrays)
    gameweeks = player_data['gameweek'].to_numpy()
    total_points = player_data['total_points'].to_numpy()
    cumulative_points = player_data['cumulative_points'].to_numpy()
    
    # Create the plot
    fig, ax = plt.subplots(figsize=figsize)
    
    # Main cumulative line
    ax.plot(gameweeks, 
            cumulative_points, 
            marker='o', 
            linewidth=2, 
            markersize=8,
            color='darkblue')
    
    # Add individual gameweek points as bar chart on secondary axis
    ax2 = ax.twinx()
    bars = ax2.bar(gameweeks, 
                   total_points, 
                   alpha=0.3, 
                   color='lightblue',
                   label='Gameweek Points')
    
    # Highlight high-scoring gameweeks (>10 points)
    high_scores_mask = player_data['total_points'] > 10
    high_scores = player_data.filter(high_scores_mask)
    
    for i in range(len(high_scores)):
        row = high_scores[i]
        ax.annotate(f"{int(row['total_points'][0])}pts", 
                   xy=(row['gameweek'][0], row['cumulative_points'][0]),
                   xytext=(0, 10), 
                   textcoords='offset points',
                   ha='center',
                   fontsize=9,
                   color='darkgreen',
                   weight='bold')
    
    # Styling
    ax.set_xlabel('Gameweek', fontsize=12)
    ax.set_ylabel('Cumulative Points', fontsize=12)
    ax2.set_ylabel('Gameweek Points', fontsize=12)
    
    # Title with player info
    team_name = player_data['team'][0] if 'team' in player_data.columns else 'Unknown Team'
    position = player_data['position'][0] if 'position' in player_data.columns else 'Unknown'
    
    # Handle position if it's numeric
    if isinstance(position, (int, float)):
        position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        position = position_map.get(int(position), 'Unknown')
    
    ax.set_title(f'{player_name} - {team_name} ({position})\nFPL Points Progress 2024-25', 
                fontsize=14, weight='bold')
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Set x-axis to show all gameweeks
    ax.set_xticks(range(1, int(gameweeks.max()) + 1))
    
    # Summary statistics box
    total_points_sum = float(cumulative_points[-1])
    games_played = len(player_data)
    best_gw = float(total_points.max())
    
    stats_text = f'Total: {total_points_sum:.0f} pts\nGames: {games_played}\nBest GW: {best_gw:.0f} pts'
    ax.text(0.02, 0.98, stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10)
    
    # Legends - only if there are labels
    # ax.legend(loc='upper left')  # No label for main line
    ax2.legend(loc='upper right')
    
    plt.tight_layout()
    
    return fig, ax


#-------------------------#
# Fixture Radar Plots
#-------------------------#
def min_max_normalize(df, all_team_df, columns):
    return df.select([(pl.col(c) - all_team_df[c].min()) / (all_team_df[c].max() - all_team_df[c].min()) for c in columns])

def plot_radar(ax, df, all_team_df, columns, team_name, color, size):
    # Normalize:
    df = min_max_normalize(df, all_team_df, columns)

    # Average across the rows of the dataframe to get mean metrics:
    df = df.select([pl.col(c).mean().alias(c) for c in columns])

    values = df.select(columns).to_numpy()[0]
    N = len(columns)
    
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values = np.concatenate((values, [values[0]]))       # close the loop
    angles += angles[:1]

    ax.plot(angles, values, 'o-', linewidth=2, label=team_name, color=color, markersize=size-4)
    ax.fill(angles, values, alpha=0.25, color=color)
    ax.set_thetagrids(np.degrees(angles[:-1]), columns, fontsize=size)
    ax.set_ylim(0, 1)


def compare_radars(fpl_data, team_name1, team_name2, ax=None, size=8, gw_range=None):
    attack_cols = ['team_total_shots','team_shots_on_target','team_big_chances', 'team_opposition_half',
                    'team_xg_open_play','team_xg_set_play', 'team_accurate_passes',
                    'team_touches_in_opposition_box','team_successful_dribbles']

    team1_df = return_team_data(fpl_data, team_name=team_name1, gw_range=gw_range)
    team2_df = return_team_data(fpl_data, team_name=team_name2, gw_range=gw_range)

    if not ax:
        fig, ax = plt.subplots(figsize=(6,6), subplot_kw=dict(polar=True))
    plot_radar(ax, team1_df, fpl_data.merged_data, attack_cols, team_name1, color='#45B7D1', size=size)
    plot_radar(ax, team2_df, fpl_data.merged_data, attack_cols, team_name2, color='#FF6B6B', size=size)
    ax.set_title(f"{team_name1} vs {team_name2}", size=size+3, color='#1D293D', weight='bold')
    ax.margins(0)

    if not ax:
        plt.show()

def plot_fixture_radars(fpl_data: FplData,
                        year: str,
                        gameweek: int,
                        cols: int = 4,
                        gw_range: tuple = None):
    gw_fixtures = pd.read_csv(f'data/{year}/By Gameweek/GW{gameweek}/fixtures.csv')
    fig, axes = plt.subplots(nrows=-(-len(gw_fixtures)//cols), 
                             ncols=cols, 
                             figsize=(cols*5, cols*4), 
                             subplot_kw=dict(polar=True))
    axes = axes.flatten()

    for idx, row in gw_fixtures.iterrows():
        home_team_code = row['home_team']
        away_team_code = row['away_team']
        home_team_name = return_team_name(fpl_data, team_id=home_team_code)
        away_team_name = return_team_name(fpl_data, team_id=away_team_code)

        # Plot radar charts for each fixture
        ax = axes[idx]
        compare_radars(fpl_data, home_team_name, away_team_name, ax=ax, size=8, gw_range=gw_range)

    for j in range(len(gw_fixtures), len(axes)):
        fig.delaxes(axes[j])
    plt.show()