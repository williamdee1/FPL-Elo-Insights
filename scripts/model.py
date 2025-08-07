import polars as pl
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

class FPLPointPredictor:
    """
    Complete ML pipeline for FPL point prediction using Polars
    """
    
    def __init__(self, use_xgboost=False, analysis_cols=None, target_col='total_points'):
        self.scaler = StandardScaler()
        self.analysis_cols = analysis_cols or ['element', 'gameweek']
        self.target_col = target_col
        self.feature_columns = None

        if use_xgboost:
            self.model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )
        else:
            self.model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            )
    
    def prepare_features(self, df):
        """
        Prepare features from Polars DataFrame
        """
        # Get feature columns (exclude analysis cols and target)
        exclude_cols = self.analysis_cols + [self.target_col]
        self.feature_columns = [col for col in df.columns if col not in exclude_cols]
        
        # Select features and convert to numpy
        X = df.select(self.feature_columns).fill_null(0).to_numpy()
        return X
    
    def train(self, df):
        """
        Train the model with proper time series validation
        """
        # Sort by gameweek to ensure proper time order
        df = df.sort(['element', 'gameweek'])
        
        # Prepare features and target
        X = self.prepare_features(df)
        y = df[self.target_col].to_numpy()
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Time series split for validation
        tscv = TimeSeriesSplit(n_splits=5)
        
        # Store validation results
        val_scores = []
        feature_importance = []
        
        # Get gameweeks for proper splitting
        gameweeks = df['gameweek'].to_numpy()
        
        # Cross-validation with time-aware splitting
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_scaled)):
            # Ensure we're not using future gameweeks to predict past
            train_gw_max = gameweeks[train_idx].max()
            val_gw_min = gameweeks[val_idx].min()
            
            print(f"Fold {fold+1}: Training up to GW {train_gw_max}, validating on GW {val_gw_min}+")
            
            X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            self.model.fit(X_train, y_train)
            val_pred = self.model.predict(X_val)
            
            mae = mean_absolute_error(y_val, val_pred)
            r2 = r2_score(y_val, val_pred)
            val_scores.append({'mae': mae, 'r2': r2})
            
            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                feature_importance.append(self.model.feature_importances_)
        
        # Train final model on all data
        self.model.fit(X_scaled, y)
        
        # Average feature importance
        if feature_importance:
            avg_importance = np.mean(feature_importance, axis=0)
            self.feature_importance_df = pl.DataFrame({
                'feature': self.feature_columns,
                'importance': avg_importance
            }).sort('importance', descending=True)
            
            print("\nTop 10 most important features:")
            print(self.feature_importance_df.head(10))
        
        # Print results
        avg_mae = np.mean([s['mae'] for s in val_scores])
        avg_r2 = np.mean([s['r2'] for s in val_scores])
        
        print(f"\nCross-validation results:")
        print(f"Average MAE: {avg_mae:.3f} points")
        print(f"Average R²: {avg_r2:.3f}")
        
        return val_scores
    
    def predict_next_gameweek(self, df_current_gw):
        """
        Predict points for the next gameweek
        """
        # Store actual points if available
        has_actual = self.target_col in df_current_gw.columns
        
        # Prepare features
        X_current = self.prepare_features(df_current_gw)
        X_scaled = self.scaler.transform(X_current)
        
        # Make predictions
        predictions = self.model.predict(X_scaled)
        
        # Add predictions to dataframe
        df_with_pred = df_current_gw.with_columns([
            pl.Series('predicted_points', predictions),
            (pl.Series('predicted_points', predictions) / (pl.col('value') / 10)).alias('predicted_value')
        ])
        
        # Add actual points if available
        if has_actual:
            df_with_pred = df_with_pred.with_columns(
                pl.col(self.target_col).alias('actual_points')
            )
        
        return df_with_pred
    
    def get_top_picks(self, predictions_df, n_per_position=5, sort_by='predicted_points'):
        """
        Get top player recommendations by position
        """
        # Check if position is numeric
        if predictions_df['position'].dtype in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
            # First cast to string, then replace
            position_map = {'1': 'GKP', '2': 'DEF', '3': 'MID', '4': 'FWD'}
            predictions_df = predictions_df.with_columns(
                pl.col('position').cast(pl.Utf8).replace(position_map).alias('position_name')
            )
            pos_col = 'position_name'
        else:
            pos_col = 'position'
        
        # Get top picks by position
        top_picks = {}
        
        for pos in ['GKP', 'DEF', 'MID', 'FWD']:
            pos_players = predictions_df.filter(pl.col(pos_col) == pos).sort(sort_by, descending=True)
            
            if not pos_players.is_empty():
                top_picks[pos] = pos_players.head(n_per_position).select([
                    'name', 'team', 'value', 'predicted_points', 'predicted_value', 'total_points',
                ])
        
        return top_picks