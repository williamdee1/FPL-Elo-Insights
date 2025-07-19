#Updated Data to include clearances, blocks, interceptions and tackles (CBIT) for every player in 24/25 season 


# Season Updates
# 2025/26 Season - Coming Soon!
Hey everyone! Just a heads up that the automated updates are currently taking a well-deserved summer break. Once the official FPL API wakes up for the 2025/26 season 
(usually around July when we all start getting excited about our new fantasy teams!), everything will spring back to life automatically

# FPL-Elo-Insights: A Comprehensive Dataset for Premier League Analysis

This repository houses a meticulously curated dataset that combines Fantasy Premier League (FPL) data, manually collected match statistics, and historical Elo ratings to provide a powerful resource for in-depth football analysis, particularly for the FPL

## Data Updates and Availability

The dataset is automatically refreshed twice daily at:
- 5:00 AM UTC
- 5:00 PM UTC

## Data Format

All data is available in two formats:
- CSV files for easy import into data analysis tools
- SQL DB files 

## Table Overview

| Table Name | Description | Key Features | Primary Use Cases |
|------------|-------------|--------------|-------------------|
| matches | Comprehensive match-level data | Contains detailed statistics for each match including scores, possession, shots, and team performance metrics | Match analysis, team performance tracking, and fixture difficulty assessment |
| playermatchstats | Detailed player statistics for each match | Individual player performance metrics including goals, assists, touches, passes, and defensive actions | Player performance analysis, scouting, and historical tracking |
| players | Basic player information from FPL API | Core player details including name, position, and team affiliation | Player identification and basic information lookup |
| playerstats | FPL-specific player statistics | Extensive FPL metrics including costs, ownership, form, and expected performance indicators | FPL strategy, player valuation, and transfer planning |
| teams | Team information and strength indicators | Team details, strength ratings, and Elo scores | Team analysis, fixture difficulty assessment, and performance tracking |

## Using
Feel free to use the data from this repository in whatever way works best for you—whether for your website, blog posts, or other projects. If possible, I’d greatly appreciate it if you could include a link back to this repository as the data source. Without completly copying the amazing [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League). I’d be happy to feature a link to your post or site as a notable usage of the repository!

## Data Sources

This project leverages data from the following sources:

*   **Manually Curated Match Statistics:** This dataset includes a wide array of detailed match events, player statistics (e.g., touches, duels, shots, etc.), and other relevant football data. 
*   **Club Elo Ratings:** Historical and current Elo ratings for all Premier League teams are sourced from [ClubElo.com](http://clubelo.com/).
*   **Official Fantasy Premier League API:**  The official FPL API provides a wealth of data, including player statistics, weekly points, form, cost, and ownership percentages.

## Data Tables Explained

The repository contains the following interconnected data tables:

### `matches`

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

### `playermatchstats`

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
*   **`ground_duels_won`:** Ground duels won by the player.
*   **`ground_duels_won_percent`:** Percentage of ground duels won by the player.
*   **`aerial_duels_won`:** Aerial duels won by the player.
*   **`aerial_duels_won_percent`:** Percentage of aerial duels won by the player.
*   **`was_fouled`:** Times the player was fouled.
*   **`fouls_committed`:** Fouls committed by the player.
*   **`saves`:** Saves made by the player (typically for goalkeepers).
*   **`goals_conceded`:** Goals conceded by the player (typically for goalkeepers and defenders).
*   **`xgot_faced`:** Expected goals on target faced by the player (typically for goalkeepers).
*   **`goals_prevented`:** Goals prevented by the player (typically for goalkeepers).
*   **`sweeper_actions`:** Sweeper actions performed by the player (typically for goalkeepers).
*   **`gk_accurate_passes`:** Accurate passes made by the goalkeeper.
*   **`gk_accurate_long_balls`:** Accurate long balls made by the goalkeeper.

**Links:**

*   `player_id` links to the `id` column in the `players` table.
*   `match_id` links to the `match_id` column in the `matches` table.

### `players`

This table contains basic information about each player from the FPL API:

*   **`player_code`:** The unique code for the player in the FPL API.
*   **`player_id`:** A unique identifier for each player within this dataset.
*   **`first_name`:** The player's first name.
*   **`second_name`:** The player's second name.
*   **`web_name`:** The player's name as it appears on the FPL website.
*   **`team_id`:** The ID of the team the player belongs to (referencing the `teams` table).
*   **`position`:** The player's position (e.g., Goalkeeper, Defender, Midfielder, Forward).

**Links:**

*   `player_id` links to the `player_id` column in the `playermatchstats` table.
*   `team_id` links to the `id` column in the `teams` table.

### `playerstats`

This table stores a wide range of FPL player statistics:

*   **`id`:** The ID of the player (referencing the `player_id` in the `players` table).
*   **`status`:** The player's availability status (e.g., available, injured, suspended).
*   **`chance_of_playing_next_round`:** The player's chance of playing in the next round (percentage).
*   **`chance_of_playing_this_round`:** The player's chance of playing in the current round (percentage).
*   **`now_cost`:** The player's current cost in the FPL game.
*   **`now_cost_rank`:** The player's cost rank among all players.
*   **`now_cost_rank_type`:** The player's cost rank within their position.
*   **`cost_change_event`:** The change in the player's cost since the last gameweek.
*   **`cost_change_event_fall`:** The fall in the player's cost since the last gameweek.
*   **`cost_change_start`:** The change in the player's cost since the start of the season.
*   **`cost_change_start_fall`:** The fall in the player's cost since the start of the season.
*   **`selected_by_percent`:** The percentage of FPL managers who have selected the player.
*   **`selected_rank`:** The player's rank based on selection percentage.
*   **`selected_rank_type`:** The player's rank based on selection percentage within their position.
*   **`total_points`:** The player's total FPL points for the season.
*   **`event_points`:** The player's FPL points for the current gameweek.
*   **`points_per_game`:** The player's average FPL points per game.
*   **`points_per_game_rank`:** The player's rank based on average points per game.
*   **`points_per_game_rank_type`:** The player's rank based on average points per game within their position.
*   **`bonus`:** Bonus points awarded to the player.
*   **`bps`:** Bonus Points System score.
*   **`form`:** The player's recent form, based on average points over the last few gameweeks.
*   **`form_rank`:** The player's form rank.
*   **`form_rank_type`:** The player's form rank within their position.
*   **`value_form`:** A measure of the player's value based on recent form and cost.
*   **`value_season`:** A measure of the player's value based on season performance and cost.
*   **`dreamteam_count`:** The number of times the player has been in the FPL Dream Team.
*   **`transfers_in`:** Total transfers in for the player.
*   **`transfers_in_event`:** Transfers in for the player in the current gameweek.
*   **`transfers_out`:** Total transfers out for the player.
*   **`transfers_out_event`:** Transfers out for the player in the current gameweek.
*   **`ep_next`:** Expected points for the player in the next gameweek.
*   **`ep_this`:** Expected points for the player in the current gameweek.
*   **`expected_goals`, `expected_assists`, `expected_goal_involvements`, `expected_goals_conceded`:** Expected performance metrics.
*   **`expected_goals_per_90`, `expected_assists_per_90`, `expected_goal_involvements_per_90`, `expected_goals_conceded_per_90`:** Expected performance metrics per 90 minutes.
*   **`influence`, `influence_rank`, `influence_rank_type`:** Measures of a player's influence on the game.
*   **`creativity`, `creativity_rank`, `creativity_rank_type`:** Measures of a player's creativity.
*   **`threat`, `threat_rank`, `threat_rank_type`:** Measures of a player's attacking threat.
*   **`ict_index`, `ict_index_rank`, `ict_index_rank_type`:** ICT Index (Influence, Creativity, Threat) and its ranks.
*   **`corners_and_indirect_freekicks_order`:**  Indicates if the player is likely to take corners and indirect freekicks.
*   **`direct_freekicks_order`:** Indicates if the player is likely to take direct freekicks.
*   **`penalties_order`:** Indicates if the player is likely to take penalties.
*   **`gw`:** The gameweek these stats apply to.

**Links:**

*   `id` links to the `player_id` in the `players` table.

### `teams`

This table contains information about each team from the FPL API:

*   **`code`:** The team's unique code in the FPL API.
*   **`id`:** A unique identifier for each team within this dataset.
*   **`name`:** The full name of the team.
*   **`short_name`:** The short name (abbreviation) of the team.
*   **`strength`:** Overall team strength (FPL rating).
*   **`strength_overall_home`:** Overall team strength when playing at home (FPL rating).
*   **`strength_overall_away`:** Overall team strength when playing away (FPL rating).
*   **`strength_attack_home`:** Attacking strength when playing at home (FPL rating).
*   **`strength_attack_away`:** Attacking strength when playing away (FPL rating).
*   **`strength_defence_home`:** Defensive strength when playing at home (FPL rating).
*   **`strength_defence_away`:** Defensive strength when playing away (FPL rating).
*   **`pulse_id`:** The team's ID on Pulse Live (a sports data provider).
*   **`elo`:** The team's Elo rating.

**Links:**

*   `id` links to `home_team` and `away_team` in the `matches` table.
*   `id` also links to `team_id` in the `players` table.

## Contributing

Contributions to this project are welcome! If you have suggestions for improvements, additional data sources, or want to help fill in the missing data, please feel free to open an issue 


