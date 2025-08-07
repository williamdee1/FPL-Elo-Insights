# Modelling Fantasy Premier League Player Points
## FPL-Elo-Insights: A Comprehensive FPL Dataset for the 2025/26 Season

Please refer to the original repository for the complete data and metadata:
https://github.com/olbauday/FPL-Elo-Insights


## Initial Work:

* Data curation scripts have been set up to work with the data structure in the original repository (linked above). See: https://github.com/williamdee1/FPL-Elo-Insights/blob/main/scripts/data_load.py
* An exploration of the underlying data can be found at: https://github.com/williamdee1/FPL-Elo-Insights/blob/main/exploration.ipynb
* Initial data curation has been performed to convert all features into rolling equivalents, and removed current gameweek features to prevent ML model leakage. See: https://github.com/williamdee1/FPL-Elo-Insights/blob/main/scripts/data_curate.py
* A first basic model has been created, and predictions made for GW 38 from the 2024/25 season, see below for top 10 predicted MFs:

  <img width="1110" height="473" alt="image" src="https://github.com/user-attachments/assets/24fd6389-d003-4582-8529-09e2a4e16810" />


