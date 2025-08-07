import matplotlib.pyplot as plt
import polars as pl


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