# FPL-Elo-Insights: A Comprehensive Dataset for Premier League Analysis

This repository houses a meticulously curated dataset that combines Fantasy Premier League (FPL) data, manually collected match statistics, and historical Elo ratings to provide a powerful resource for in-depth football analysis, particularly for the English Premier League.

## Dive Deeper into Player and Team Performance

**FPL-Elo-Insights** empowers you to go beyond basic statistics and understand the factors driving player and team success. By integrating these diverse data sources, you can:

*   **Uncover Correlations:** Analyze how individual player performance metrics (ground duels won, accurate passes, etc.) correlate with FPL points and team Elo ratings.
*   **Evaluate Team Strength:** Assess team strength using historical Elo ratings from [ClubElo.com](http://clubelo.com/) for past matches and current Elo ratings for upcoming fixtures.
*   **Enhance FPL Strategy:** Make more informed decisions in Fantasy Premier League by considering detailed player statistics and team strength indicators.
*   **Track Player Development:** Connect a player like Erling Haaland to his weekly FPL points and all his associated match statistics, allowing you to track his performance trajectory throughout the season.
*   **Predict Match Outcomes:** Develop models that predict match outcomes by incorporating detailed match events, player stats, and team Elo ratings.

## Data Sources

This project leverages data from the following sources:

*   **Manually Curated Match Statistics:** This dataset includes a wide array of detailed match events, player statistics (e.g., touches, duels, shots, etc.), and other relevant football data. It has been meticulously collected and verified to ensure accuracy.
*   **Club Elo Ratings:** Historical and current Elo ratings for all Premier League teams are sourced from [ClubElo.com](http://clubelo.com/), providing a robust measure of team strength.
*   **Official Fantasy Premier League API:**  The official FPL API provides a wealth of data, including player statistics, weekly points, form, cost, and ownership percentages.

## Data Tables Explained

The repository contains the following interconnected data tables:

### `matches.csv`

This table contains comprehensive match-level data, including:

*   **`gameweek`:** The gameweek of the match.
*   **`kickoff_time`:** The date and time of the match kickoff.
*   **`home_team`, `away_team`:**  IDs of the home and away teams (referencing the `teams` table).
*   **`home_team_elo`, `away_team_elo`:** Elo ratings of the home and away teams at the time of the match (or current Elo if the match is in the future).
*   **`home_score`, `away_score`:** The final score of the match.
*   **`finished`:** Boolean indicating whether the match has finished.
*   **`match_id`:** A unique identifier for each match.
*   **`match_url`:** The URL of the match on the source website.
*   **`home_possession`, `away_possession`:** Percentage of possession for each team.
*   **`home_expected_goals_xg`, `away_expected_goals_xg`:** Expected goals for each team.
*   **`home_total_shots`, `away_total_shots`:** Total shots taken by each team.
*   **`home_shots_on_target`, `away_shots_on_target`:** Shots on target for each team.
*   **`home_big_chances`, `away_big_chances`:** Big chances created by each team.
*   **`home_big_chances_missed`, `away_big_chances_missed`:** Big chances missed by each team.
*   **`home_accurate_passes`, `away_accurate_passes`:** Number of accurate passes for each team.
*   **`home_accurate_passes_pct`, `away_accurate_passes_pct`:** Percentage of accurate passes for each team.
*   **`home_fouls_committed`, `away_fouls_committed`:** Fouls committed by each team.
*   **`home_corners`, `away_corners`:** Corners won by each team.
*   **`home_xg_open_play`, `away_xg_open_play`:** Expected goals from open play for each team.
*   **`home_xg_set_play`, `away_xg_set_play`:** Expected goals from set plays for each team.
*   **`home_non_penalty_xg`, `away_non_penalty_xg`:** Non-penalty expected goals for each team.
*   **`home_xg_on_target_xgot`, `away_xg_on_target_xgot`:** Expected goals on target for each team.
*   **`home_shots_off_target`, `away_shots_off_target`:** Shots off target for each team.
*   **`home_blocked_shots`, `away_blocked_shots`:** Blocked shots for each team.
*   **`home_hit_woodwork`, `away_hit_woodwork`:** Times each team hit the woodwork.
*   **`home_shots_inside_box`, `away_shots_inside_box`:** Shots taken inside the box by each team.
*   **`home_shots_outside_box`, `away_shots_outside_box`:** Shots taken outside the box by each team.
*   **`home_passes`, `away_passes`:** Total passes made by each team.
*   **`home_own_half`, `away_own_half`:** Passes made in each team's own half.
*   **`home_opposition_half`, `away_opposition_half`:** Passes made in the opposition's half for each team.
*   **`home_accurate_long_balls`, `away_accurate_long_balls`:** Accurate long balls made by each team.
*   **`home_accurate_long_balls_pct`, `away_accurate_long_balls_pct`:** Percentage of accurate long balls for each team.
*   **`home_accurate_crosses`, `away_accurate_crosses`:** Accurate crosses made by each team.
*   **`home_accurate_crosses_pct`, `away_accurate_crosses_pct`:** Percentage of accurate crosses for each team.
*   **`home_throws`, `away_throws`:** Throw-ins taken by each team.
*   **`home_touches_in_opposition_box`, `away_touches_in_opposition_box`:** Touches in the opposition box for each team.
*   **`home_offsides`, `away_offsides`:** Offsides for each team.
*   **`home_yellow_cards`, `away_yellow_cards`:** Yellow cards for each team.
*   **`home_red_cards`, `away_red_cards`:** Red cards for each team.
*   **`home_tackles_won`, `away_tackles_won`:** Tackles won by each team.
*   **`home_tackles_won_pct`, `away_tackles_won_pct`:** Percentage of tackles won by each team.
*   **`home_interceptions`, `away_interceptions`:** Interceptions made by each team.
*   **`home_blocks`, `away_blocks`:** Blocks made by each team.
*   **`home_clearances`, `away_clearances`:** Clearances made by each team.
*   **`home_keeper_saves`, `away_keeper_saves`:** Saves made by each team's goalkeeper.
*   **`home_duels_won`, `away_duels_won`:** Duels won by each team.
*   **`home_ground_duels_won`, `away_ground_duels_won`:** Ground duels won by each team.
*   **`home_ground_duels_won_pct`, `away_ground_duels_won_pct`:** Percentage of ground duels won by each team.
*   **`home_aerial_duels_won`, `away_aerial_duels_won`:** Aerial duels won by each team.
*   **`home_aerial_duels_won_pct`, `away_aerial_duels_won_pct`:** Percentage of aerial duels won by each team.
*   **`home_successful_dribbles`, `away_successful_dribbles`:** Successful dribbles made by each team.
*   **`home_successful_dribbles_pct`, `away_successful_dribbles_pct`:** Percentage of successful dribbles for each team.
*   **`fotmob_id`:** The ID of the match on FotMob (if available).
*   **`stats_processed`:** Boolean indicating whether the match statistics have been processed.
*   **`player_stats_processed`:** Boolean indicating whether the player statistics for the match have been processed.
*   **`home_penalties_missed`, `away_penalties_missed`:** Number of penalties missed by each team.
*   **`home_penalties_saved`, `away_penalties_saved`:** Number of penalties saved by each team's goalkeeper.
*   **`home_own_goals`, `away_own_goals`:** Number of own goals scored by each team.
*   **`home_bonus_points`, `away_bonus_points`:** Number of bonus points awarded to each team.
*   **`home_team_difficulty`, `away_team_difficulty`:** Difficulty ratings for the home and away teams (currently not populated).

**Links:**

*   `home_team` and `away_team` link to the `id` column in the `teams` table.
*   `match_id` links to the `match_id` column in the `playermatchstats` table.

### `playermatchstats.csv`

This table provides detailed player-level statistics for each match:

*   **`player_id`:** The ID of the player (referencing the `players` table).
*   **`match_id`:** The ID of the match (referencing the `matches` table).
*   **`minutes_played`:** Minutes played by the player in the match.
*   **`goals`:** Goals scored by the player.
*   **`assists`:** Assists by the player.
*   **`total_shots`:** Total shots taken by the player.
*   **`xg`:** Expected goals for the player.
*   **`xa`:** Expected assists for the player.
*   **`shots_on_target`:** Shots on target by the player.
*   **`successful_dribbles`:** Successful dribbles by the player.
*   **`big_chances_missed`:** Big chances missed by the player.
*   **`touches_opposition_box`:** Touches in the opposition box by the player.
*   **`touches`:** Total touches by the player.
*   **`accurate_passes`:** Accurate passes made by the player.
*   **`accurate_passes_percent`:** Percentage of accurate passes by the player.
*   **`chances_created`:** Chances created by the player.
*   **`final_third_passes`:** Passes into the final third by the player.
*   **`accurate_crosses`:** Accurate crosses by the player.
*   **`accurate_crosses_percent`:** Percentage of accurate crosses by the player.
*   **`accurate_long_balls`:** Accurate long balls by the player.
*   **`accurate_long_balls_percent`:** Percentage of accurate long balls by the player.
*   **`tackles_won`:** Tackles won by the player.
*   **`interceptions`:** Interceptions by the player.
*   **`recoveries`:** Ball recoveries by the player.
*   **`blocks`:** Blocks by the player.
*   **`clearances`:** Clearances by the player.
*   **`headed_clearances`:** Headed clearances by the player.
*   **`dribbled_past`:** Times the player was dribbled past.
*   **`duels_won`:** Duels won by the player.
*   **`duels_lost`:** Duels lost by the player.
*   **`ground_duels_won`:** Ground du
