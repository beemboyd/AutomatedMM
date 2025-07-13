#!/usr/bin/env python3
"""
Enhanced Market Regime Detection using Clustering Algorithms

This module implements various clustering algorithms to identify market regimes
based on multiple technical and statistical features.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

class ClusteringRegimeDetector:
    """
    Enhanced market regime detection using unsupervised clustering algorithms.
    Identifies different market environments and adjusts strategies accordingly.
    """
    
    def __init__(self, n_regimes=4, lookback_periods=[20, 50, 100, 200]):
        """
        Initialize the clustering-based regime detector.
        
        Args:
            n_regimes (int): Number of market regimes to identify
            lookback_periods (list): Periods for calculating features
        """
        self.n_regimes = n_regimes
        self.lookback_periods = lookback_periods
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=0.95)  # Keep 95% of variance
        self.regime_labels = {
            0: "STRONG_BULLISH",
            1: "WEAK_BULLISH", 
            2: "WEAK_BEARISH",
            3: "STRONG_BEARISH",
            4: "HIGH_VOLATILITY",
            5: "LOW_VOLATILITY"
        }
        
    def calculate_features(self, data):
        """
        Calculate comprehensive features for clustering.
        
        Args:
            data (pd.DataFrame): OHLCV data
            
        Returns:
            pd.DataFrame: Feature matrix
        """
        features = pd.DataFrame(index=data.index)
        
        # Price-based features
        features['returns'] = data['Close'].pct_change()
        features['log_returns'] = np.log(data['Close'] / data['Close'].shift(1))
        
        # Volatility features
        features['realized_vol'] = features['returns'].rolling(20).std() * np.sqrt(252)
        features['parkinson_vol'] = self._calculate_parkinson_volatility(data)
        features['garman_klass_vol'] = self._calculate_garman_klass_volatility(data)
        
        # Trend features
        for period in self.lookback_periods:
            # Simple Moving Average
            features[f'sma_{period}'] = data['Close'].rolling(period).mean()
            features[f'sma_ratio_{period}'] = data['Close'] / features[f'sma_{period}']
            
            # Exponential Moving Average
            features[f'ema_{period}'] = data['Close'].ewm(span=period, adjust=False).mean()
            features[f'ema_ratio_{period}'] = data['Close'] / features[f'ema_{period}']
            
            # Rate of Change
            features[f'roc_{period}'] = (data['Close'] - data['Close'].shift(period)) / data['Close'].shift(period)
            
            # Relative Strength Index
            features[f'rsi_{period}'] = self._calculate_rsi(data['Close'], period)
            
        # Market Microstructure features
        features['spread'] = (data['High'] - data['Low']) / data['Close']
        features['volume_ratio'] = data['Volume'] / data['Volume'].rolling(20).mean()
        
        # Statistical features
        features['skewness_20'] = features['returns'].rolling(20).skew()
        features['kurtosis_20'] = features['returns'].rolling(20).kurt()
        features['skewness_50'] = features['returns'].rolling(50).skew()
        features['kurtosis_50'] = features['returns'].rolling(50).kurt()
        
        # Autocorrelation features
        features['autocorr_1'] = features['returns'].rolling(20).apply(lambda x: x.autocorr(lag=1))
        features['autocorr_5'] = features['returns'].rolling(20).apply(lambda x: x.autocorr(lag=5))
        
        # Hurst exponent (trend persistence)
        features['hurst'] = self._calculate_rolling_hurst(data['Close'])
        
        # Volume features
        features['volume_sma_ratio'] = data['Volume'] / data['Volume'].rolling(20).mean()
        features['price_volume_corr'] = features['returns'].rolling(20).corr(data['Volume'].pct_change())
        
        # Regime change indicators
        features['vol_change'] = features['realized_vol'].pct_change(periods=20)
        features['trend_strength'] = self._calculate_trend_strength(data['Close'])
        
        # Drop NaN values
        features = features.dropna()
        
        return features
    
    def _calculate_parkinson_volatility(self, data, window=20):
        """Calculate Parkinson volatility estimator"""
        hl_ratio = np.log(data['High'] / data['Low'])
        return np.sqrt(hl_ratio.rolling(window).apply(lambda x: np.sum(x**2) / (4 * len(x) * np.log(2)))) * np.sqrt(252)
    
    def _calculate_garman_klass_volatility(self, data, window=20):
        """Calculate Garman-Klass volatility estimator"""
        log_hl = np.log(data['High'] / data['Low'])
        log_co = np.log(data['Close'] / data['Open'])
        
        rs = 0.5 * log_hl**2 - (2*np.log(2)-1) * log_co**2
        return np.sqrt(rs.rolling(window).mean() * 252)
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_rolling_hurst(self, prices, window=100):
        """Calculate rolling Hurst exponent"""
        def hurst(ts):
            if len(ts) < 20:
                return np.nan
            
            lags = range(2, min(20, len(ts)//2))
            tau = []
            
            for lag in lags:
                diff = np.subtract(ts[lag:], ts[:-lag])
                tau.append(np.sqrt(np.std(diff)))
            
            if len(tau) > 0:
                m = np.polyfit(np.log(lags), np.log(tau), 1)
                return m[0]
            return np.nan
        
        return prices.rolling(window).apply(hurst)
    
    def _calculate_trend_strength(self, prices, window=20):
        """Calculate trend strength using linear regression slope"""
        def trend_slope(ts):
            if len(ts) < 2:
                return np.nan
            x = np.arange(len(ts))
            slope, _ = np.polyfit(x, ts, 1)
            return slope / ts.iloc[-1] * 100
        
        return prices.rolling(window).apply(trend_slope)
    
    def fit_kmeans(self, features, n_clusters=None):
        """
        Fit K-Means clustering model.
        
        Args:
            features (pd.DataFrame): Feature matrix
            n_clusters (int): Number of clusters (uses self.n_regimes if None)
            
        Returns:
            tuple: (labels, model, metrics)
        """
        if n_clusters is None:
            n_clusters = self.n_regimes
            
        # Scale features
        features_scaled = self.scaler.fit_transform(features)
        
        # Apply PCA for dimensionality reduction
        features_pca = self.pca.fit_transform(features_scaled)
        
        # Fit K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features_pca)
        
        # Calculate metrics
        silhouette = silhouette_score(features_pca, labels)
        inertia = kmeans.inertia_
        
        metrics = {
            'silhouette_score': silhouette,
            'inertia': inertia,
            'n_clusters': n_clusters
        }
        
        return labels, kmeans, metrics
    
    def fit_gmm(self, features, n_components=None):
        """
        Fit Gaussian Mixture Model.
        
        Args:
            features (pd.DataFrame): Feature matrix
            n_components (int): Number of components (uses self.n_regimes if None)
            
        Returns:
            tuple: (labels, model, metrics)
        """
        if n_components is None:
            n_components = self.n_regimes
            
        # Scale features
        features_scaled = self.scaler.fit_transform(features)
        
        # Apply PCA
        features_pca = self.pca.fit_transform(features_scaled)
        
        # Fit GMM
        gmm = GaussianMixture(n_components=n_components, random_state=42)
        gmm.fit(features_pca)
        labels = gmm.predict(features_pca)
        
        # Calculate metrics
        bic = gmm.bic(features_pca)
        aic = gmm.aic(features_pca)
        log_likelihood = gmm.score(features_pca)
        
        metrics = {
            'bic': bic,
            'aic': aic,
            'log_likelihood': log_likelihood,
            'n_components': n_components
        }
        
        return labels, gmm, metrics
    
    def fit_dbscan(self, features, eps=0.5, min_samples=5):
        """
        Fit DBSCAN clustering model.
        
        Args:
            features (pd.DataFrame): Feature matrix
            eps (float): Maximum distance between samples
            min_samples (int): Minimum samples in a neighborhood
            
        Returns:
            tuple: (labels, model, metrics)
        """
        # Scale features
        features_scaled = self.scaler.fit_transform(features)
        
        # Apply PCA
        features_pca = self.pca.fit_transform(features_scaled)
        
        # Fit DBSCAN
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(features_pca)
        
        # Calculate metrics
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)
        
        metrics = {
            'n_clusters': n_clusters,
            'n_noise_points': n_noise,
            'eps': eps,
            'min_samples': min_samples
        }
        
        # Calculate silhouette score if we have more than one cluster
        if n_clusters > 1:
            # Filter out noise points for silhouette calculation
            mask = labels != -1
            if mask.sum() > 0:
                try:
                    silhouette = silhouette_score(features_pca[mask], labels[mask])
                    metrics['silhouette_score'] = silhouette
                except:
                    metrics['silhouette_score'] = np.nan
        
        return labels, dbscan, metrics
    
    def fit_hierarchical(self, features, n_clusters=None):
        """
        Fit Hierarchical clustering model.
        
        Args:
            features (pd.DataFrame): Feature matrix
            n_clusters (int): Number of clusters (uses self.n_regimes if None)
            
        Returns:
            tuple: (labels, model, metrics)
        """
        if n_clusters is None:
            n_clusters = self.n_regimes
            
        # Scale features
        features_scaled = self.scaler.fit_transform(features)
        
        # Apply PCA
        features_pca = self.pca.fit_transform(features_scaled)
        
        # Fit Hierarchical clustering
        hierarchical = AgglomerativeClustering(n_clusters=n_clusters)
        labels = hierarchical.fit_predict(features_pca)
        
        # Calculate metrics
        silhouette = silhouette_score(features_pca, labels)
        
        metrics = {
            'silhouette_score': silhouette,
            'n_clusters': n_clusters
        }
        
        return labels, hierarchical, metrics
    
    def identify_regime_characteristics(self, features, labels):
        """
        Identify characteristics of each regime cluster.
        
        Args:
            features (pd.DataFrame): Feature matrix
            labels (np.array): Cluster labels
            
        Returns:
            dict: Regime characteristics
        """
        regime_chars = {}
        
        for regime in np.unique(labels):
            if regime == -1:  # Skip noise points in DBSCAN
                continue
                
            regime_data = features[labels == regime]
            
            # Calculate average characteristics
            chars = {
                'avg_return': regime_data['returns'].mean() * 252,  # Annualized
                'avg_volatility': regime_data['realized_vol'].mean(),
                'avg_trend_strength': regime_data['trend_strength'].mean(),
                'avg_hurst': regime_data['hurst'].mean(),
                'avg_volume_ratio': regime_data['volume_ratio'].mean(),
                'count': len(regime_data),
                'percentage': len(regime_data) / len(features) * 100
            }
            
            # Classify regime based on characteristics
            if chars['avg_return'] > 0.1 and chars['avg_trend_strength'] > 5:
                regime_name = "STRONG_BULLISH"
            elif chars['avg_return'] > 0 and chars['avg_trend_strength'] > 0:
                regime_name = "WEAK_BULLISH"
            elif chars['avg_return'] < -0.1 and chars['avg_trend_strength'] < -5:
                regime_name = "STRONG_BEARISH"
            elif chars['avg_return'] < 0 and chars['avg_trend_strength'] < 0:
                regime_name = "WEAK_BEARISH"
            elif chars['avg_volatility'] > 0.3:
                regime_name = "HIGH_VOLATILITY"
            else:
                regime_name = "LOW_VOLATILITY"
            
            chars['regime_name'] = regime_name
            regime_chars[regime] = chars
        
        return regime_chars
    
    def ensemble_clustering(self, features, methods=['kmeans', 'gmm', 'hierarchical']):
        """
        Ensemble approach combining multiple clustering methods.
        
        Args:
            features (pd.DataFrame): Feature matrix
            methods (list): List of clustering methods to use
            
        Returns:
            tuple: (ensemble_labels, all_results)
        """
        all_labels = []
        all_results = {}
        
        if 'kmeans' in methods:
            labels, model, metrics = self.fit_kmeans(features)
            all_labels.append(labels)
            all_results['kmeans'] = {'labels': labels, 'model': model, 'metrics': metrics}
        
        if 'gmm' in methods:
            labels, model, metrics = self.fit_gmm(features)
            all_labels.append(labels)
            all_results['gmm'] = {'labels': labels, 'model': model, 'metrics': metrics}
        
        if 'hierarchical' in methods:
            labels, model, metrics = self.fit_hierarchical(features)
            all_labels.append(labels)
            all_results['hierarchical'] = {'labels': labels, 'model': model, 'metrics': metrics}
        
        if 'dbscan' in methods:
            # Auto-tune DBSCAN parameters
            eps, min_samples = self._tune_dbscan_params(features)
            labels, model, metrics = self.fit_dbscan(features, eps, min_samples)
            all_labels.append(labels)
            all_results['dbscan'] = {'labels': labels, 'model': model, 'metrics': metrics}
        
        # Ensemble voting
        ensemble_labels = self._ensemble_vote(all_labels)
        
        return ensemble_labels, all_results
    
    def _tune_dbscan_params(self, features):
        """Auto-tune DBSCAN parameters using k-distance graph"""
        from sklearn.neighbors import NearestNeighbors
        
        features_scaled = self.scaler.fit_transform(features)
        features_pca = self.pca.fit_transform(features_scaled)
        
        # Find optimal min_samples (usually 2 * dimensions)
        min_samples = min(5, features_pca.shape[1] * 2)
        
        # Find optimal eps using k-distance graph
        neighbors = NearestNeighbors(n_neighbors=min_samples)
        neighbors_fit = neighbors.fit(features_pca)
        distances, indices = neighbors_fit.kneighbors(features_pca)
        
        # Sort distances and find elbow
        distances = np.sort(distances[:, -1], axis=0)
        
        # Simple elbow detection: find maximum curvature
        eps = np.percentile(distances, 90)  # Use 90th percentile as eps
        
        return eps, min_samples
    
    def _ensemble_vote(self, all_labels):
        """Combine multiple clustering results using majority voting"""
        # Convert all labels to same scale (0 to n_regimes-1)
        normalized_labels = []
        
        for labels in all_labels:
            # Map unique labels to 0, 1, 2, ...
            unique_labels = np.unique(labels[labels != -1])  # Exclude noise
            label_map = {old: new for new, old in enumerate(unique_labels)}
            
            new_labels = np.array([label_map.get(l, -1) for l in labels])
            normalized_labels.append(new_labels)
        
        # Majority voting
        ensemble_labels = np.zeros(len(normalized_labels[0]))
        
        for i in range(len(ensemble_labels)):
            votes = [labels[i] for labels in normalized_labels if labels[i] != -1]
            if votes:
                # Most common vote
                ensemble_labels[i] = max(set(votes), key=votes.count)
            else:
                ensemble_labels[i] = -1  # Noise
        
        return ensemble_labels.astype(int)