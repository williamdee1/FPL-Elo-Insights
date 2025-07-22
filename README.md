# FPL-Elo-Insights: A Comprehensive FPL Dataset for the 2025/26 Season

Welcome to FPL-Elo-Insights, a meticulously curated dataset designed to empower your Fantasy Premier League analysis beyond the surface. This project uniquely links official FPL player data with detailed match statistics and historical team Elo ratings, allowing for unparalleled insights.

It combines three powerful data sources:
1.  **Official FPL API Data**: All the essential player points, costs, form, ownership, xG/xA, and more.
2.  **Manually Curated Match Stats (Opta-like)**: Deep-dive performance metrics for every player and match.
3.  **ClubElo.com Elo Ratings**: Historical and current team strength ratings for robust fixture analysis.

## What's New for the 2025/26 Season?

This season, FPL-Elo-Insights is taking a massive leap forward, pushing beyond what inspired this project to deliver an even richer analytical experience.

### 🏆 Expanded Tournament Coverage Synced to FPL Players
This is the big one! The dataset now includes data from all major competitions, including **pre-season friendlies, domestic cups (FA Cup, League Cup), and all European competitions (Champions League, Europa League, Conference League).**

Crucially, this vast new data is directly linked to your FPL player IDs, allowing you to seamlessly track how players perform across all competitions and see how it might impact their FPL potential. No more guessing how pre-season form or European fatigue could influence your picks!

### 🛡️ Enhanced Defensive & Midfield Metrics (CBIT)
Following the new FPL rules that reward defensive contributions, I've integrated **Clearances, Blocks, Interceptions, and Tackles (CBIT)** for every player in every match. This means you can now:
*   Identify defensive gems who might rack up points under the new FPL rules.
*   Analyze how effectively players contribute defensively beyond just clean sheets.
*   Spot differentials in midfield and defense who excel in these often-overlooked areas.

### 📂 New & Improved Data Structure
The data is now organized into a more intuitive structure to make analysis easier than ever. You can access data sliced in different ways depending on your needs.

## Data Updates

The dataset is automatically refreshed twice daily at:
- **5:00 AM UTC**
- **5:00 PM UTC**

All data is provided in **CSV format** for easy import into any data analysis tool.

## Data Structure Overview

The data for the season is organized into three main categories within the `data/2025-2026/` directory:

1.  **Master Files**
    *   Location: `/`
    *   Description: These are the main, always-up-to-date files for the entire season.
    *   Files: `players.csv`, `teams.csv`, `playerstats.csv`

2.  **By Gameweek**
    *   Location: `By Gameweek/GW{x}/`
    *   Description: Contains a complete snapshot of all data relevant to a specific gameweek.
    *   Files: `matches.csv`, `playermatchstats.csv`, `playerstats.csv`, `players.csv`, `teams.csv`

3.  **By Tournament**
    *   Location: `By Tournament/{tournament_name}/GW{x}/`
    *   Description: Contains a self-contained snapshot of all data for a specific tournament within a specific gameweek.
    *   Files: `matches.csv`, `playermatchstats.csv`, `playerstats.csv`, `players.csv`, `teams.csv`

## Table Overview

| Table Name | Description | Key Features | Primary Use Cases |
|------------|-------------|--------------|-------------------|
| `matches` | Comprehensive match-level data | Contains detailed statistics for each match including scores, possession, shots, and team performance metrics | Match analysis, team performance tracking, and fixture difficulty assessment |
| `playermatchstats` | Detailed player statistics for each match | Individual performance metrics including goals, assists, touches, passes, and now **CBIT** data. | Player performance analysis, scouting, and historical tracking |
| `players` | Basic player information from FPL API | Core player details including name, position, and team affiliation | Player identification and basic information lookup |
| `playerstats` | FPL-specific player statistics | Extensive FPL metrics including costs, ownership, form, and expected performance indicators | FPL strategy, player valuation, and transfer planning |
| `teams` | Team information and strength indicators | Team details, strength ratings, and Elo scores | Team analysis, fixture difficulty assessment, and performance tracking |

## Using The Data
Feel free to use the data from this repository in whatever way works best for you—whether for your website, blog posts, or other projects. If possible, I’d greatly appreciate it if you could include a link back to this repository as the data source.

Inspired by the amazing work of [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League), this project aims to continue the spirit of open data in the FPL community. If you build something cool, let me know – I'd be happy to feature a link to your project!

## Data Tables Explained

### `matches`
This table contains comprehensive match-level data for all finished games.
*(Full column list omitted for brevity - see the original README for the complete list if needed, or explore the CSV file.)*
- **Key Columns:** `gameweek`, `kickoff_time`, `home_team`, `away_team`, `home_score`, `away_score`, `home_team_elo`, `away_team_elo`, `finished`, `match_id`, etc.
- **Links:** `home_team` and `away_team` link to `id` in the `teams` table. `match_id` links to `playermatchstats`.

### `playermatchstats`
This table provides detailed player-level statistics for each match.
- **Key Columns:** `player_id`, `match_id`, `minutes_played`, `goals`, `assists`, `xg`, `xa`, `touches`, and now **`clearances`**, **`blocks`**, **`interceptions`**, **`tackles_won`**.
- **Links:** `player_id` links to `player_id` in the `players` table. `match_id` links to `match_id` in the `matches` table.

### `players`
This table contains basic information about each player from the FPL API.
- **Key Columns:** `player_id`, `first_name`, `second_name`, `web_name`, `team_id`, `position`.
- **Links:** `team_id` links to `id` in the `teams` table.

### `playerstats`
This table stores a wide range of FPL player statistics, updated per gameweek.
- **Key Columns:** `id` (player's ID), `now_cost`, `selected_by_percent`, `total_points`, `form`, `ep_next`, `expected_goals`, `expected_assists`, `gw`.
- **Links:** `id` links to `player_id` in the `players` table.

### `teams`
This table contains information about each team, including their Elo rating.
- **Key Columns:** `id`, `name`, `short_name`, `strength`, `elo`.
- **Links:** `id` links to `home_team`, `away_team` in `matches` and `team_id` in `players`.

## Contributing
Contributions to this project are welcome! If you have suggestions for improvements, additional data sources, or want to help fill in the missing data, please feel free to open an issue.
