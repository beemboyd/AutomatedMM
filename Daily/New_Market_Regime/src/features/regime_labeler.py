#!/usr/bin/env python3
"""
Regime Labeler Module
Defines and labels market regimes based on market conditions
Creates ground truth labels for supervised learning
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

# Setup logging
log_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/regime_labeler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RegimeLabeler:
    """
    Labels market regimes based on objective criteria
    
    Regime definitions:
    1. Strongly Bullish: High L/S ratio, positive momentum, low volatility
    2. Bullish: Positive trend, more longs than shorts
    3. Choppy Bullish: Mixed signals but leaning positive
    4. Neutral: No clear direction, balanced metrics
    5. Choppy Bearish: Mixed signals but leaning negative
    6. Bearish: Negative trend, more shorts than longs
    7. Strongly Bearish: Very low L/S ratio, negative momentum, high volatility
    """
    
    def __init__(self):
        self.data_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data'
        
        # Regime thresholds
        self.regime_thresholds = {
            'strongly_bullish': {
                'long_short_ratio': 2.0,      # L/S > 2
                'bullish_percent': 66.67,     # >66.67% bullish
                'market_score_mean': 1.5,     # High positive score
                'volatility_threshold': 0.02  # Low volatility
            },
            'bullish': {
                'long_short_ratio': 1.2,      # L/S > 1.2
                'bullish_percent': 55,        # >55% bullish
                'market_score_mean': 0.5,     # Positive score
                'volatility_threshold': 0.03
            },
            'choppy_bullish': {
                'long_short_ratio': 1.0,      # L/S > 1.0
                'bullish_percent': 50,        # >50% bullish
                'market_score_mean': 0,       # Slightly positive
                'volatility_threshold': 0.04  # Higher volatility
            },
            'neutral': {
                'long_short_ratio': (0.8, 1.2),  # Range
                'bullish_percent': (45, 55),     # Range
                'market_score_mean': (-0.5, 0.5),
                'volatility_threshold': 0.03
            },
            'choppy_bearish': {
                'long_short_ratio': 0.8,      # L/S < 0.8
                'bullish_percent': 45,        # <45% bullish
                'market_score_mean': -0.5,    # Slightly negative
                'volatility_threshold': 0.04
            },
            'bearish': {
                'long_short_ratio': 0.5,      # L/S < 0.5
                'bullish_percent': 35,        # <35% bullish
                'market_score_mean': -1.0,    # Negative score
                'volatility_threshold': 0.03
            },
            'strongly_bearish': {
                'long_short_ratio': 0.3,      # L/S < 0.3
                'bullish_percent': 25,        # <25% bullish
                'market_score_mean': -1.5,    # Very negative
                'volatility_threshold': 0.05  # High volatility
            }
        }
        
        # Regime encoding for ML
        self.regime_encoding = {
            'strongly_bullish': 3,
            'bullish': 2,
            'choppy_bullish': 1,
            'neutral': 0,
            'choppy_bearish': -1,
            'bearish': -2,
            'strongly_bearish': -3
        }
    
    def label_regime(self, features: Dict) -> Tuple[str, float]:
        """
        Label a single observation with regime and confidence
        """
        try:
            # Extract key metrics
            ls_ratio = features.get('long_short_ratio', 1.0)
            bullish_pct = features.get('bullish_percent', 50.0)
            market_score = features.get('market_score_mean', 0.0)
            
            # Calculate confidence scores for each regime
            regime_scores = {}
            
            # Strongly Bullish
            sb_score = 0
            if ls_ratio > self.regime_thresholds['strongly_bullish']['long_short_ratio']:
                sb_score += 0.4
            if bullish_pct > self.regime_thresholds['strongly_bullish']['bullish_percent']:
                sb_score += 0.3
            if market_score > self.regime_thresholds['strongly_bullish']['market_score_mean']:
                sb_score += 0.3
            regime_scores['strongly_bullish'] = sb_score
            
            # Bullish
            b_score = 0
            if ls_ratio > self.regime_thresholds['bullish']['long_short_ratio']:
                b_score += 0.4
            if bullish_pct > self.regime_thresholds['bullish']['bullish_percent']:
                b_score += 0.3
            if market_score > self.regime_thresholds['bullish']['market_score_mean']:
                b_score += 0.3
            regime_scores['bullish'] = b_score
            
            # Choppy Bullish
            cb_score = 0
            if ls_ratio > self.regime_thresholds['choppy_bullish']['long_short_ratio']:
                cb_score += 0.4
            if bullish_pct > self.regime_thresholds['choppy_bullish']['bullish_percent']:
                cb_score += 0.3
            if market_score > self.regime_thresholds['choppy_bullish']['market_score_mean']:
                cb_score += 0.3
            regime_scores['choppy_bullish'] = cb_score
            
            # Neutral
            n_score = 0
            n_thresholds = self.regime_thresholds['neutral']
            if (isinstance(n_thresholds['long_short_ratio'], tuple) and 
                n_thresholds['long_short_ratio'][0] <= ls_ratio <= n_thresholds['long_short_ratio'][1]):
                n_score += 0.4
            if (isinstance(n_thresholds['bullish_percent'], tuple) and
                n_thresholds['bullish_percent'][0] <= bullish_pct <= n_thresholds['bullish_percent'][1]):
                n_score += 0.3
            if (isinstance(n_thresholds['market_score_mean'], tuple) and
                n_thresholds['market_score_mean'][0] <= market_score <= n_thresholds['market_score_mean'][1]):
                n_score += 0.3
            regime_scores['neutral'] = n_score
            
            # Choppy Bearish
            cbe_score = 0
            if ls_ratio < self.regime_thresholds['choppy_bearish']['long_short_ratio']:
                cbe_score += 0.4
            if bullish_pct < self.regime_thresholds['choppy_bearish']['bullish_percent']:
                cbe_score += 0.3
            if market_score < self.regime_thresholds['choppy_bearish']['market_score_mean']:
                cbe_score += 0.3
            regime_scores['choppy_bearish'] = cbe_score
            
            # Bearish
            be_score = 0
            if ls_ratio < self.regime_thresholds['bearish']['long_short_ratio']:
                be_score += 0.4
            if bullish_pct < self.regime_thresholds['bearish']['bullish_percent']:
                be_score += 0.3
            if market_score < self.regime_thresholds['bearish']['market_score_mean']:
                be_score += 0.3
            regime_scores['bearish'] = be_score
            
            # Strongly Bearish
            sbe_score = 0
            if ls_ratio < self.regime_thresholds['strongly_bearish']['long_short_ratio']:
                sbe_score += 0.4
            if bullish_pct < self.regime_thresholds['strongly_bearish']['bullish_percent']:
                sbe_score += 0.3
            if market_score < self.regime_thresholds['strongly_bearish']['market_score_mean']:
                sbe_score += 0.3
            regime_scores['strongly_bearish'] = sbe_score
            
            # Select regime with highest score
            best_regime = max(regime_scores, key=regime_scores.get)
            confidence = regime_scores[best_regime]
            
            # Apply rule-based adjustments for edge cases
            if ls_ratio > 3.0 and bullish_pct > 75:
                best_regime = 'strongly_bullish'
                confidence = 0.95
            elif ls_ratio < 0.2 and bullish_pct < 20:
                best_regime = 'strongly_bearish'
                confidence = 0.95
            elif 0.9 <= ls_ratio <= 1.1 and 48 <= bullish_pct <= 52:
                best_regime = 'neutral'
                confidence = 0.90
            
            # Minimum confidence threshold
            if confidence < 0.3:
                best_regime = 'neutral'
                confidence = 0.5
            
            return best_regime, confidence
            
        except Exception as e:
            logger.error(f"Error labeling regime: {e}")
            return 'neutral', 0.5
    
    def label_features_dataframe(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Label all rows in a features dataframe
        """
        logger.info(f"Labeling {len(features_df)} observations")
        
        try:
            # Apply labeling to each row
            labels = []
            confidences = []
            
            for idx, row in features_df.iterrows():
                label, confidence = self.label_regime(row.to_dict())
                labels.append(label)
                confidences.append(confidence)
            
            # Add to dataframe
            features_df['regime_label'] = labels
            features_df['regime_confidence'] = confidences
            features_df['regime_encoded'] = features_df['regime_label'].map(self.regime_encoding)
            
            # Calculate label distribution
            label_counts = features_df['regime_label'].value_counts()
            logger.info("Regime distribution:")
            for regime, count in label_counts.items():
                pct = count / len(features_df) * 100
                logger.info(f"  {regime}: {count} ({pct:.1f}%)")
            
            # Check for label imbalance
            max_pct = label_counts.iloc[0] / len(features_df) * 100
            if max_pct > 50:
                logger.warning(f"Label imbalance detected: {label_counts.index[0]} = {max_pct:.1f}%")
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error labeling dataframe: {e}")
            return features_df
    
    def create_transition_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create features that capture regime transitions
        """
        try:
            if 'regime_encoded' not in features_df.columns:
                logger.error("Must label regimes before creating transition features")
                return features_df
            
            # Sort by timestamp
            if 'timestamp' in features_df.columns:
                features_df = features_df.sort_values('timestamp')
            
            # Previous regime
            features_df['prev_regime'] = features_df['regime_encoded'].shift(1)
            features_df['prev_regime_2'] = features_df['regime_encoded'].shift(2)
            
            # Regime change indicators
            features_df['regime_changed'] = (
                features_df['regime_encoded'] != features_df['prev_regime']
            ).astype(int)
            
            features_df['regime_change_magnitude'] = (
                features_df['regime_encoded'] - features_df['prev_regime']
            ).fillna(0)
            
            # Regime persistence (how long in current regime)
            regime_groups = (features_df['regime_encoded'] != features_df['prev_regime']).cumsum()
            features_df['regime_duration'] = regime_groups.groupby(regime_groups).cumcount() + 1
            
            # Transition probabilities (would need more data)
            features_df['transition_score'] = 0  # Placeholder
            
            logger.info("Added regime transition features")
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error creating transition features: {e}")
            return features_df
    
    def validate_labels(self, features_df: pd.DataFrame) -> Dict:
        """
        Validate label quality and consistency
        """
        validation_results = {
            'total_samples': len(features_df),
            'labeled_samples': 0,
            'label_distribution': {},
            'confidence_stats': {},
            'issues': []
        }
        
        try:
            if 'regime_label' not in features_df.columns:
                validation_results['issues'].append("No labels found")
                return validation_results
            
            # Count labeled samples
            validation_results['labeled_samples'] = features_df['regime_label'].notna().sum()
            
            # Label distribution
            label_counts = features_df['regime_label'].value_counts()
            total = len(features_df)
            
            for regime, count in label_counts.items():
                validation_results['label_distribution'][regime] = {
                    'count': int(count),
                    'percentage': round(count / total * 100, 2)
                }
            
            # Confidence statistics
            if 'regime_confidence' in features_df.columns:
                conf = features_df['regime_confidence']
                validation_results['confidence_stats'] = {
                    'mean': round(conf.mean(), 3),
                    'std': round(conf.std(), 3),
                    'min': round(conf.min(), 3),
                    'max': round(conf.max(), 3),
                    'low_confidence_count': int((conf < 0.5).sum())
                }
                
                if validation_results['confidence_stats']['mean'] < 0.6:
                    validation_results['issues'].append("Low average confidence")
            
            # Check for imbalance
            max_regime = label_counts.index[0]
            max_pct = label_counts.iloc[0] / total * 100
            
            if max_pct > 60:
                validation_results['issues'].append(
                    f"Severe imbalance: {max_regime} = {max_pct:.1f}%"
                )
            elif max_pct > 40:
                validation_results['issues'].append(
                    f"Moderate imbalance: {max_regime} = {max_pct:.1f}%"
                )
            
            # Check for missing regimes
            all_regimes = set(self.regime_encoding.keys())
            present_regimes = set(label_counts.index)
            missing = all_regimes - present_regimes
            
            if missing:
                validation_results['issues'].append(
                    f"Missing regimes: {', '.join(missing)}"
                )
            
            # Success message if no issues
            if not validation_results['issues']:
                validation_results['issues'].append("All validation checks passed")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating labels: {e}")
            validation_results['issues'].append(f"Validation error: {e}")
            return validation_results
    
    def save_labeled_data(self, features_df: pd.DataFrame, version: str = None):
        """
        Save labeled dataset
        """
        try:
            # Create labels directory
            labels_path = f"{self.data_path}/labels"
            os.makedirs(labels_path, exist_ok=True)
            
            # Generate version if not provided
            if version is None:
                version = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save to parquet
            output_file = f"{labels_path}/labeled_features_v{version}.parquet"
            features_df.to_parquet(output_file)
            
            # Save label metadata
            validation = self.validate_labels(features_df)
            
            # Convert numpy/pandas types to Python native types for JSON
            def make_json_serializable(obj):
                if isinstance(obj, (np.integer, np.int64)):
                    return int(obj)
                elif isinstance(obj, (np.floating, np.float64)):
                    return float(obj) if not np.isnan(obj) else None
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_serializable(v) for v in obj]
                return obj
            
            metadata = {
                'version': version,
                'created_at': datetime.now().isoformat(),
                'total_samples': len(features_df),
                'validation': make_json_serializable(validation),
                'regime_thresholds': self.regime_thresholds,
                'regime_encoding': self.regime_encoding
            }
            
            metadata_file = f"{labels_path}/labeled_features_v{version}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved labeled data to {output_file}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Error saving labeled data: {e}")
            return None


def main():
    """
    Test regime labeling
    """
    from feature_builder import FeatureBuilder
    
    # Build features first
    builder = FeatureBuilder()
    features_df = builder.build_feature_vector()
    
    if features_df is None:
        print("❌ No features available to label")
        return
    
    # Label the features
    labeler = RegimeLabeler()
    labeled_df = labeler.label_features_dataframe(features_df)
    
    # Add transition features
    labeled_df = labeler.create_transition_features(labeled_df)
    
    # Validate labels
    validation = labeler.validate_labels(labeled_df)
    
    print("\n" + "=" * 50)
    print("Regime Labeling Summary:")
    print("=" * 50)
    
    print(f"Total samples: {validation['total_samples']}")
    print(f"Labeled samples: {validation['labeled_samples']}")
    
    print("\nLabel distribution:")
    for regime, stats in validation['label_distribution'].items():
        print(f"  {regime}: {stats['count']} ({stats['percentage']}%)")
    
    if validation.get('confidence_stats'):
        print("\nConfidence statistics:")
        stats = validation['confidence_stats']
        print(f"  Mean: {stats['mean']:.3f}")
        print(f"  Std: {stats['std']:.3f}")
        print(f"  Range: [{stats['min']:.3f}, {stats['max']:.3f}]")
    
    print("\nValidation issues:")
    for issue in validation['issues']:
        print(f"  - {issue}")
    
    # Save labeled data
    saved_file = labeler.save_labeled_data(labeled_df)
    if saved_file:
        print(f"\n✅ Labeled data saved to: {saved_file}")
    
    # Display sample
    if 'regime_label' in labeled_df.columns:
        print("\nSample labels:")
        sample = labeled_df[['timestamp', 'regime_label', 'regime_confidence']].head()
        print(sample.to_string())


if __name__ == "__main__":
    main()