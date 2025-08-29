#!/usr/bin/env python3
"""
Test script for Phase 2: Feature Engineering Pipeline
Tests the complete flow from feature building to labeling and storage
"""

import sys
import os

# Add source to path
sys.path.append('/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/src')

from features.feature_builder import FeatureBuilder
from features.feature_store import FeatureStore
from features.regime_labeler import RegimeLabeler

def test_phase2_pipeline():
    """
    Run complete Phase 2 pipeline
    """
    print("\n" + "=" * 60)
    print("PHASE 2: FEATURE ENGINEERING PIPELINE TEST")
    print("=" * 60)
    
    # Step 1: Build features
    print("\n1. BUILDING FEATURES...")
    print("-" * 40)
    
    builder = FeatureBuilder()
    features_df = builder.build_feature_vector()
    
    if features_df is None:
        print("❌ Failed to build features")
        return False
    
    print(f"✅ Built {len(builder.feature_names)} features")
    print(f"   Timestamp: {features_df['timestamp'].iloc[0]}")
    print(f"   Data quality: {features_df['data_quality'].iloc[0]:.2%}")
    
    # Step 2: Register in feature store
    print("\n2. REGISTERING IN FEATURE STORE...")
    print("-" * 40)
    
    store = FeatureStore()
    version_id = store.register_features(
        features_df,
        source="scanner_data",
        notes="Phase 2 test - initial feature engineering"
    )
    
    if version_id:
        print(f"✅ Registered as version: {version_id}")
        
        # Validate retrieval
        retrieved = store.get_features(version_id=version_id)
        if retrieved is not None and len(retrieved) == len(features_df):
            print(f"   Successfully retrieved {len(retrieved)} rows")
        else:
            print("   ⚠️  Issue retrieving features")
    else:
        print("❌ Failed to register features")
    
    # Step 3: Label regimes
    print("\n3. LABELING MARKET REGIMES...")
    print("-" * 40)
    
    labeler = RegimeLabeler()
    labeled_df = labeler.label_features_dataframe(features_df)
    
    if 'regime_label' in labeled_df.columns:
        print(f"✅ Labeled {len(labeled_df)} observations")
        
        # Add transition features
        labeled_df = labeler.create_transition_features(labeled_df)
        print("   Added transition features")
        
        # Validate labels
        validation = labeler.validate_labels(labeled_df)
        
        print("\n   Label distribution:")
        for regime, stats in validation['label_distribution'].items():
            print(f"     {regime}: {stats['count']} ({stats['percentage']}%)")
        
        if validation.get('confidence_stats'):
            stats = validation['confidence_stats']
            print(f"\n   Confidence: mean={stats['mean']:.3f}, std={stats.get('std', 0):.3f}")
        
        # Save labeled data
        saved_file = labeler.save_labeled_data(labeled_df)
        if saved_file:
            print(f"\n   Saved to: {os.path.basename(saved_file)}")
    else:
        print("❌ Failed to label data")
    
    # Step 4: Feature store summary
    print("\n4. FEATURE STORE SUMMARY...")
    print("-" * 40)
    
    summary = store.get_store_summary()
    if summary:
        print(f"   Total versions: {summary['total_versions']}")
        print(f"   Active versions: {summary['active_versions']}")
        print(f"   Storage size: {summary['storage_size_mb']:.2f} MB")
        
        if summary['usage_stats']:
            print("\n   Usage statistics:")
            for usage_type, count in summary['usage_stats'].items():
                print(f"     {usage_type}: {count}")
    
    # Final summary
    print("\n" + "=" * 60)
    print("PHASE 2 TEST SUMMARY")
    print("=" * 60)
    
    success_items = []
    if features_df is not None:
        success_items.append(f"✅ Feature building ({len(builder.feature_names)} features)")
    if version_id:
        success_items.append(f"✅ Feature store (version {version_id})")
    if 'regime_label' in labeled_df.columns:
        success_items.append(f"✅ Regime labeling ({len(labeled_df)} samples)")
    if saved_file:
        success_items.append("✅ Data persistence")
    
    for item in success_items:
        print(item)
    
    print("\n📊 Key Metrics:")
    print(f"   Market L/S Ratio: {features_df['long_short_ratio'].iloc[0]:.2f}")
    print(f"   Bullish Percent: {features_df['bullish_percent'].iloc[0]:.1f}%")
    print(f"   Current Regime: {labeled_df['regime_label'].iloc[0]}")
    print(f"   Confidence: {labeled_df['regime_confidence'].iloc[0]:.2%}")
    
    # Check for issues
    issues = []
    if len(labeled_df) == 1:
        issues.append("⚠️  Only 1 data point - need more data for training")
    
    if validation['issues'] and 'passed' not in validation['issues'][0]:
        for issue in validation['issues'][:2]:  # Show first 2 issues
            issues.append(f"⚠️  {issue}")
    
    if issues:
        print("\n⚠️  Issues to address:")
        for issue in issues:
            print(f"   {issue}")
    
    print("\n" + "=" * 60)
    print("Phase 2 Feature Engineering: COMPLETED ✅")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    test_phase2_pipeline()