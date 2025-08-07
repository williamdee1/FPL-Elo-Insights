import numpy as np
import polars as pl


def create_ml_feature_set(df):
    """
    Create features to use in downstream ML models.
    """
    # Convert to Polars
    df = pl.from_pandas(df)
    
    # Map positions
    df = df.with_columns(
            pl.col('position').replace({'GK': 1, 'DEF': 2, 'MID': 3, 'FWD': 4, 'AM': 5}).cast(pl.Int64)
        )
    
    # Convert booleans to float
    bool_cols = [col for col in df.columns if df[col].dtype == pl.Boolean]
    if bool_cols:
        df = df.with_columns([pl.col(col).cast(pl.Float64) for col in bool_cols])
    
    # Create team features - handle was_home as either boolean or float
    # Check if was_home exists and its type
    if 'was_home' in df.columns:
        # If was_home is float, treat 1.0 as True, 0.0 as False
        df = df.with_columns([
            pl.when(pl.col('was_home') == 1.0)
              .then(pl.col('home_score'))
              .otherwise(pl.col('away_score'))
              .alias('team_goals'),
            pl.when(pl.col('was_home') == 1.0)
              .then(pl.col('away_score'))
              .otherwise(pl.col('home_score'))
              .alias('team_conceded'),
        ])
    
    df = df.with_columns([
        (pl.col('team_goals') - pl.col('team_conceded')).alias('goal_difference'),
        (pl.col('team_conceded') == 0).cast(pl.Float64).alias('clean_sheet'),
        (pl.col('team_goals') > pl.col('team_conceded')).cast(pl.Float64).alias('team_won'),
        (pl.col('team_goals') == pl.col('team_conceded')).cast(pl.Float64).alias('team_drew'),
        (pl.col('team_goals') < pl.col('team_conceded')).cast(pl.Float64).alias('team_lost'),
    ])

    # ALL performance metrics should be shifted to use only past data
    # This includes rolling averages for the last 5, 3, and 1 gameweeks
    # They relate to the current gameweek, so we only want prior weeks rolling data to avoid data leakage
    roll_feats = [
        'assists', 'bps', 'clean_sheets', 'creativity', 'threat', 
        'expected_assists',  'expected_goal_involvements', 'expected_goals', 'expected_goals_conceded',
        'goals_conceded', 'goals_scored', 'ict_index', 'influence', 'minutes', 'saves', 'starts', 
        'minutes_played', 'goals', 'total_shots', 'xg', 'xa', 'xgot', 'shots_on_target',
        'successful_dribbles', 'touches_opposition_box', 'touches', 
        'accurate_passes_percent', 'final_third_passes', 'accurate_crosses_percent', 'accurate_long_balls_percent',
        'tackles_won', 'tackles', 'interceptions', 'recoveries', 'blocks', 'clearances', 'headed_clearances',
        'dribbled_past', 'duels_won', 'duels_lost', 'ground_duels_won', 'aerial_duels_won', 'fouls_committed',
        'successful_dribbles_percent', 'goals_conceded_match', 'xgot_faced', 'goals_prevented', 'sweeper_actions',
        'high_claim', 'gk_accurate_long_balls', 'gk_accurate_passes', 'offsides', 'penalties_saved', 'chances_created',
        # curated team features
        'team_goals', 'team_conceded', 'goal_difference', 'clean_sheet', 'team_won', 'team_drew', 'team_lost',
    ]
    
    # Also include total_points for rolling features
    features_to_roll = roll_feats + ['total_points']
    
    # Create all rolling features at once using Polars expressions
    rolling_exprs = []
    
    for feat in features_to_roll:
        # Last 5 games
        rolling_exprs.append(
            pl.col(feat).shift(1).rolling_mean(5, min_periods=1)
            .over('element').alias(f'{feat}_last5')
        )
        # Last 3 games
        rolling_exprs.append(
            pl.col(feat).shift(1).rolling_mean(3, min_periods=1)
            .over('element').alias(f'{feat}_last3')
        )
        # Last game
        rolling_exprs.append(
            pl.col(feat).shift(1).over('element').alias(f'{feat}_last1')
        )
    
    # Apply all rolling calculations at once
    df = df.sort(['element', 'gameweek']).with_columns(rolling_exprs)
    
    # Drop cols which aren't needed for modeling:
    drop_feats = [
        # Redundant features that are already present in the dataset in other forms
        'xP', 'bonus',  'round', 'player_id', 'assists_match', 'accurate_crosses', 'accurate_long_balls', 'accurate_passes',
        'ground_duels_won_percent', 'aerial_duels_won_percent', 'tackles_won_percent', 'saves_match', 'gw', 'player_id_master',
        'player_code', 
        # Idenfiers where I don't know enough about the data to use them
        'fixture', 'opponent_team', 'selected', 'modified', 
        # Identifiers which occur rarely, and likely not useful for modeling
        'own_goals', 'penalties_missed', 'red_cards', 'yellow_cards', 'big_chances_missed', 'was_fouled',
        # Home/ away stats, to convert to different features before rolling:
        'team_h_score', 'team_a_score', 'home_team', 'away_team', 'away_score', 'home_score', 'team_id', 'was_home', 
    ]

    # Also now drop the current week performance features which were used to create the rolling features
    all_drop_feats = drop_feats + roll_feats
    df = df.drop([col for col in all_drop_feats if col in df.columns])

    # Replace all null values in the entire dataframe with 0
    df = df.fill_null(0)
    
    return df