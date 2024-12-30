# FPL-Elo-Insights
Combines FPL data, manually curated match statistics, and historical Elo ratings for enhanced player performance analysis and insights.

## Overview

This project merges football data from multiple sources to create a rich dataset for analyzing player performance and informing Fantasy Premier League (FPL) decisions. It combines:

*   **Detailed Integrated Match Events:** Manually curated data providing in-depth statistics for each match.
*   **Historical and Current Elo Ratings:** Team strength ratings from [ClubElo.com](http://clubelo.com/), either from the time of the match or the current day's rating for future matches.
*   **Fantasy Premier League (FPL) Player Data:** Weekly points, player statistics, and other relevant metrics from the official FPL API.

By linking these datasets, you can gain deeper insights into how individual player performances correlate with team strength (Elo) and FPL outcomes. For instance, you can connect a player such as Erling Haaland with his weekly FPL points and all his stats for that game, such as ground duel success rate.

## Data Sources

*   **Integrated Match Events:** Detailed match events, player statistics, and other football-related data that has been manually curated.
*   **Club Elo:** A website that provides historical and current Elo ratings for football clubs. Data is retrieved from [http://clubelo.com/](http://clubelo.com/).
*   **FPL API:** The official Fantasy Premier League API, which provides player statistics, points, and other FPL-related information.

## Data Tables

This project includes the following key data tables:

| Table Name         | Description                                                                                                                                                                                                                             |
| :----------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `matches`          | Contains detailed statistics for each match, including team Elo ratings, match outcomes, and a wide range of performance metrics. **Links:** `home_team` and `away_team` link to the `teams` table. `match_id` links to `playermatchstats` |
| `playermatchstats` | Provides individual player statistics for each match, such as minutes played, goals, assists, shots, duels won, and much more. **Links:** `player_id` links to the `players` table, and `match_id` links to the `matches` table.               |
| `players`          | Stores basic player information from the FPL API, including player ID, name, team, and position. **Links:** `player_id` links to `playermatchstats`, `team_id` links to the `teams` table.                                                 |
| `playerstats`      | Contains a comprehensive set of FPL player statistics, including points, form, cost, expected stats (xG, xA), and various performance ranks. **Links:** `id` refers to `player_id` in the `players` table.                         |
| `teams`            | Holds team information from the FPL API, including team ID, name, strength, and Elo rating. **Links:** `id` links to `home_team` and `away_team` in the `matches` table and `team_id` in the `players` table.                               |

## Features

*   **Data Integration:** Combines integrated match events, Club Elo ratings, and FPL player data into a unified dataset.
*   **Historical Elo:** Uses historical Elo ratings from the time of each match for accurate team strength assessment.
*   **Current Elo (for future matches):** If a match hasn't been played yet, the current day's Elo rating is used as a proxy for team strength.
*   **Player-Centric Analysis:** Allows for in-depth analysis of individual player performance, linked to their FPL points and match statistics.


## Usage

<!-- Provide examples of how to use your code or access the data -->



## Known Issues

*   **Incomplete Match Data:** Some fields in the `matches` table are not yet fully populated, including:
    *   `home_team_difficulty`
    *   `away_team_difficulty`
    *   `home_penalties_missed`
    *   `away_penalties_missed`
    *   `home_penalties_saved`
    *   `away_penalties_saved`
    *   `home_own_goals`
    *   `away_own_goals`
    *   `home_bonus_points`
    *   `away_bonus_points`


---
**Key Changes:**

*   **Table Descriptions:** I've added details about the linked columns and how they establish relationships between the tables. For example, in the `matches` table description, I've mentioned that `home_team` and `away_team` link to the `teams` table. I've used similar explanations for other tables.


