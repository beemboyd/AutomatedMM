# Market Regime Module - Setup & Configuration Guide

## Installation Requirements

### System Requirements

- **Operating System**: macOS 10.15+, Ubuntu 18.04+, or Windows 10+
- **Python Version**: 3.8 or higher
- **Memory**: Minimum 4GB RAM, Recommended 8GB+
- **Storage**: 2GB free space for data and logs
- **Network**: Stable internet connection for API access

### Dependencies

#### Python Packages
```bash
# Core dependencies
pip install pandas>=1.3.0
pip install numpy>=1.21.0
pip install scikit-learn>=1.0.0
pip install flask>=2.0.0
pip install requests>=2.26.0
pip install pytz>=2021.3

# Optional but recommended
pip install openpyxl>=3.0.7  # For Excel file handling
pip install xlrd>=2.0.1      # For legacy Excel support
pip install matplotlib>=3.4.3  # For chart generation
pip install seaborn>=0.11.2    # For advanced visualizations
```

#### System Packages
```bash
# macOS
brew install nginx  # For production deployment

# Ubuntu
sudo apt-get update
sudo apt-get install nginx python3-dev

# Install from requirements.txt
pip install -r requirements.txt
```

### Directory Structure Setup

```bash
# Navigate to India-TS project root
cd /path/to/India-TS

# Create Market Regime directory structure
mkdir -p Daily/Market_Regime/{regime_analysis,dashboards,data,scan_results,trend_analysis}

# Set permissions
chmod 755 Daily/Market_Regime
chmod 644 Daily/Market_Regime/*.py
chmod 755 Daily/Market_Regime/{regime_analysis,dashboards,data}
```

## Configuration Files

### 1. Core Configuration (`config.py`)

```python
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.absolute()
DAILY_DIR = BASE_DIR.parent
PROJECT_ROOT = DAILY_DIR.parent

# Data directories
REGIME_DIR = BASE_DIR / "regime_analysis"
DASHBOARDS_DIR = BASE_DIR / "dashboards"
DATA_DIR = BASE_DIR / "data"
SCAN_RESULTS_DIR = BASE_DIR / "scan_results"
TREND_DIR = BASE_DIR / "trend_analysis"

# Scanner result directories
RESULTS_DIR = DAILY_DIR / "results"
RESULTS_SHORT_DIR = DAILY_DIR / "results-s"

# Cache settings
CACHE_TTL_SECONDS = 300  # 5 minutes for index data
API_CACHE_TTL_SECONDS = 30  # 30 seconds for API responses

# Dashboard settings
DASHBOARD_PORTS = {
    'static': 5001,
    'enhanced': 8080,
    'health': 7080
}

# Auto-refresh intervals (seconds)
DASHBOARD_REFRESH_INTERVAL = 30
ANALYSIS_INTERVAL = 1800  # 30 minutes

# File patterns
LONG_PATTERN = "Long_Reversal_Daily_{date}*.xlsx"
SHORT_PATTERN = "Short_Reversal_Daily_{date}*.xlsx"

# API configuration
KITE_CONNECT_TIMEOUT = 10  # seconds
MAX_API_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = DATA_DIR / "market_regime.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
```

### 2. Regime Smoother Configuration

```python
# regime_smoother_config.py
REGIME_SMOOTHER_CONFIG = {
    # Minimum time regime must be active before allowing change
    'min_regime_duration_hours': 2.0,
    
    # Minimum confidence required for regime change
    'confidence_threshold': 0.7,
    
    # Moving average periods for smoothing
    'ma_periods': 3,
    
    # Extreme ratio thresholds (beyond which changes are blocked)
    'extreme_ratio_threshold': 3.0,
    'extreme_ratio_low': 0.33,
    
    # Volatility window for calculating market volatility
    'volatility_window': 5,
    
    # Maximum volatility allowed for regime changes
    'max_volatility': 0.5,
    
    # Persistence requirements
    'require_consecutive_signals': 2,
    
    # Override conditions
    'allow_extreme_confidence': 0.9,  # Override smoothing if confidence > 90%
    'force_change_after_hours': 6.0   # Force change after 6 hours regardless
}
```

### 3. Index Analyzer Configuration

```python
# index_analyzer_config.py
INDEX_CONFIG = {
    # KiteConnect instrument tokens
    'index_tokens': {
        'NIFTY 50': 256265,
        'NIFTY MIDCAP 100': 288009,
        'NIFTY SMLCAP 100': 288265
    },
    
    # SMA calculation parameters
    'sma_period': 20,
    'min_data_points': 15,  # Minimum points required for SMA
    
    # Weight factors for different indices
    'index_weights': {
        'NIFTY 50': 0.5,
        'NIFTY MIDCAP 100': 0.3,
        'NIFTY SMLCAP 100': 0.2
    },
    
    # Trend determination thresholds
    'trend_thresholds': {
        'strong_bullish': 0.8,  # 80%+ indices above SMA20
        'bullish': 0.6,         # 60%+ indices above SMA20
        'neutral': 0.4,         # 40-60% indices above SMA20
        'bearish': 0.2,         # 20-40% indices above SMA20
        'strong_bearish': 0.0   # <20% indices above SMA20
    },
    
    # Cache and retry settings
    'cache_ttl_minutes': 5,
    'api_timeout_seconds': 10,
    'max_retries': 3,
    'retry_delay_seconds': 1,
    
    # Data validation
    'max_price_deviation_pct': 10.0,  # Max % deviation from previous price
    'min_sma_ratio': 0.5,  # Minimum SMA/Price ratio
    'max_sma_ratio': 2.0   # Maximum SMA/Price ratio
}
```

### 4. ML Model Configuration

```python
# ml_model_config.py
ML_CONFIG = {
    # Model parameters
    'model_type': 'RandomForestClassifier',
    'n_estimators': 100,
    'max_depth': 10,
    'min_samples_split': 5,
    'min_samples_leaf': 2,
    'random_state': 42,
    
    # Feature engineering
    'feature_columns': [
        'current_ratio',
        'ma3_long',
        'ma3_short', 
        'avg_ratio',
        'momentum',
        'volatility',
        'index_trend_score'
    ],
    
    # Training parameters
    'test_size': 0.2,
    'validation_split': 0.2,
    'cross_validation_folds': 5,
    
    # Model validation
    'min_accuracy_threshold': 0.7,
    'retrain_frequency_days': 7,
    'min_training_samples': 100,
    
    # Prediction confidence
    'confidence_calibration': True,
    'probability_threshold': 0.6,
    
    # Performance tracking
    'track_feature_importance': True,
    'save_model_metrics': True,
    'model_versioning': True
}
```

### 5. Dashboard Configuration

```python
# dashboard_config.py
DASHBOARD_CONFIG = {
    # Flask app settings
    'flask_config': {
        'DEBUG': False,
        'TESTING': False,
        'SECRET_KEY': 'your-secret-key-here',
        'JSONIFY_PRETTYPRINT_REGULAR': True
    },
    
    # Dashboard refresh rates
    'refresh_intervals': {
        'enhanced_dashboard': 30,  # seconds
        'health_dashboard': 60,    # seconds
        'static_dashboard': 300    # seconds (regeneration)
    },
    
    # Chart configurations
    'chart_config': {
        'history_window': 50,      # Number of data points to keep
        'sparkline_points': 20,    # Points for sparkline charts
        'update_animation': True,
        'theme': 'modern'
    },
    
    # Display settings
    'display_config': {
        'datetime_format': '%Y-%m-%d %H:%M:%S',
        'percentage_decimals': 1,
        'currency_symbol': '₹',
        'number_format': ',.2f'
    },
    
    # Alert thresholds
    'alert_thresholds': {
        'stale_data_minutes': 40,
        'low_confidence': 0.4,
        'high_volatility': 0.7,
        'extreme_ratio': 5.0
    },
    
    # Security settings
    'security': {
        'enable_cors': True,
        'cors_origins': ['http://localhost:*'],
        'rate_limit': '100 per minute',
        'enable_auth': False  # Set to True for production
    }
}
```

## Environment Setup

### 1. Environment Variables

Create a `.env` file in the Market_Regime directory:

```bash
# .env file
# KiteConnect API Configuration
KITE_API_KEY=your_api_key_here
KITE_ACCESS_TOKEN=your_access_token_here

# Dashboard Configuration
FLASK_ENV=production
FLASK_DEBUG=False

# Logging Configuration
LOG_LEVEL=INFO
LOG_TO_FILE=True

# Cache Configuration
REDIS_URL=redis://localhost:6379/0  # Optional: Use Redis for caching
CACHE_TYPE=simple  # simple, redis, or memcached

# Database Configuration
DATABASE_URL=sqlite:///market_regime.db

# Alert Configuration
ENABLE_ALERTS=True
ALERT_EMAIL=your-email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password

# Security
SECRET_KEY=your-very-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Performance
MAX_WORKERS=4
WORKER_TIMEOUT=120
```

### 2. Loading Environment Variables

```python
# env_loader.py
import os
from dotenv import load_dotenv
from pathlib import Path

def load_environment():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent / '.env'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        print("No .env file found, using system environment variables")
    
    # Validate required variables
    required_vars = ['KITE_API_KEY', 'KITE_ACCESS_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    return {
        'kite_api_key': os.getenv('KITE_API_KEY'),
        'kite_access_token': os.getenv('KITE_ACCESS_TOKEN'),
        'flask_env': os.getenv('FLASK_ENV', 'development'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'cache_type': os.getenv('CACHE_TYPE', 'simple'),
        'enable_alerts': os.getenv('ENABLE_ALERTS', 'False').lower() == 'true'
    }
```

## Service Configuration

### 1. Systemd Service Files (Linux)

Create service files for production deployment:

**market-regime-enhanced.service**:
```ini
[Unit]
Description=Market Regime Enhanced Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/India-TS/Daily/Market_Regime
Environment=PATH=/path/to/python/venv/bin
ExecStart=/path/to/python/venv/bin/python dashboard_enhanced.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**market-regime-health.service**:
```ini
[Unit]
Description=Market Regime Health Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/India-TS/Daily/Market_Regime
Environment=PATH=/path/to/python/venv/bin
ExecStart=/path/to/python/venv/bin/python dashboard_health_check.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Cron Jobs for Analysis

Add to crontab for scheduled analysis:

```bash
# Edit crontab
crontab -e

# Add the following lines:
# Market regime analysis every 30 minutes during market hours (9:15 AM - 3:30 PM IST)
*/30 9-15 * * 1-5 cd /path/to/India-TS/Daily/Market_Regime && /path/to/python/venv/bin/python market_regime_analyzer.py

# Generate static dashboard every hour
0 * * * * cd /path/to/India-TS/Daily/Market_Regime && /path/to/python/venv/bin/python trend_dashboard.py

# Cleanup old files daily at 6 AM
0 6 * * * find /path/to/India-TS/Daily/Market_Regime/regime_analysis -name "regime_report_*.json" -mtime +7 -delete
```

### 3. macOS LaunchAgents

For macOS, create LaunchAgent files:

**com.india-ts.market-regime-analysis.plist**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.market-regime-analysis</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/India-TS/Daily/Market_Regime/market_regime_analyzer.py</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>WorkingDirectory</key>
    <string>/path/to/India-TS/Daily/Market_Regime</string>
    <key>StandardOutPath</key>
    <string>/tmp/market-regime-analysis.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/market-regime-analysis-error.log</string>
</dict>
</plist>
```

Load the LaunchAgent:
```bash
cp com.india-ts.market-regime-analysis.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.india-ts.market-regime-analysis.plist
```

## Network Configuration

### 1. Nginx Configuration

**nginx.conf** for production deployment:

```nginx
upstream market_regime_enhanced {
    server 127.0.0.1:8080;
}

upstream market_regime_health {
    server 127.0.0.1:7080;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;
    
    # Static dashboard
    location /market-regime/ {
        alias /path/to/India-TS/Daily/Market_Regime/dashboards/;
        try_files $uri $uri/ =404;
        
        # Cache static files
        location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1h;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # Enhanced dashboard
    location /enhanced/ {
        proxy_pass http://market_regime_enhanced/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Health dashboard
    location /health/ {
        proxy_pass http://market_regime_health/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://market_regime_enhanced/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # CORS headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
}
```

### 2. Firewall Configuration

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

# Block direct access to Flask ports
sudo ufw deny 8080
sudo ufw deny 7080

# macOS (using built-in firewall)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setallowsigned on
```

## Database Setup

### 1. SQLite Database Initialization

```python
# database_setup.py
import sqlite3
from pathlib import Path

def initialize_database():
    """Initialize SQLite database for market regime data"""
    db_path = Path(__file__).parent / "data" / "regime_learning.db"
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regime_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            regime TEXT NOT NULL,
            confidence REAL NOT NULL,
            long_count INTEGER NOT NULL,
            short_count INTEGER NOT NULL,
            ratio REAL NOT NULL,
            market_score REAL,
            trend_score REAL,
            volatility_score REAL,
            index_trend TEXT,
            index_strength REAL,
            smoothing_active BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT NOT NULL,
            accuracy REAL NOT NULL,
            total_predictions INTEGER NOT NULL,
            regime_accuracy TEXT,  -- JSON string
            training_date TEXT NOT NULL,
            feature_importance TEXT,  -- JSON string
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL,
            resolved BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_timestamp ON regime_history(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_type ON system_alerts(alert_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_severity ON system_alerts(severity)")
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized at {db_path}")

if __name__ == "__main__":
    initialize_database()
```

### 2. Data Backup Configuration

```bash
#!/bin/bash
# backup_regime_data.sh

BACKUP_DIR="/path/to/backups/market-regime"
DATA_DIR="/path/to/India-TS/Daily/Market_Regime"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
cp "$DATA_DIR/data/regime_learning.db" "$BACKUP_DIR/regime_learning_$DATE.db"

# Backup JSON reports (last 7 days)
find "$DATA_DIR/regime_analysis" -name "*.json" -mtime -7 -exec cp {} "$BACKUP_DIR/" \;

# Compress old backups
find "$BACKUP_DIR" -name "*.db" -mtime +7 -exec gzip {} \;

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR"
```

## Monitoring & Logging

### 1. Logging Configuration

```python
# logging_config.py
import logging
import logging.handlers
from pathlib import Path

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "market_regime.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Specific loggers
    analysis_logger = logging.getLogger('market_regime.analysis')
    analysis_logger.setLevel(logging.DEBUG)
    
    api_logger = logging.getLogger('market_regime.api')
    api_logger.setLevel(logging.INFO)
    
    dashboard_logger = logging.getLogger('market_regime.dashboard')
    dashboard_logger.setLevel(logging.INFO)
    
    return {
        'analysis': analysis_logger,
        'api': api_logger,
        'dashboard': dashboard_logger
    }
```

### 2. Health Check Scripts

```python
# health_check.py
import requests
import json
import sys
from datetime import datetime, timedelta

def check_system_health():
    """Comprehensive system health check"""
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': 'healthy',
        'checks': {}
    }
    
    # Check enhanced dashboard
    try:
        response = requests.get('http://localhost:8080/api/current_analysis', timeout=10)
        if response.status_code == 200:
            health_status['checks']['enhanced_dashboard'] = 'healthy'
        else:
            health_status['checks']['enhanced_dashboard'] = f'error_{response.status_code}'
            health_status['overall_status'] = 'degraded'
    except Exception as e:
        health_status['checks']['enhanced_dashboard'] = f'error_{str(e)}'
        health_status['overall_status'] = 'critical'
    
    # Check health dashboard
    try:
        response = requests.get('http://localhost:7080/api/health', timeout=10)
        if response.status_code == 200:
            health_status['checks']['health_dashboard'] = 'healthy'
        else:
            health_status['checks']['health_dashboard'] = f'error_{response.status_code}'
            health_status['overall_status'] = 'degraded'
    except Exception as e:
        health_status['checks']['health_dashboard'] = f'error_{str(e)}'
        health_status['overall_status'] = 'critical'
    
    # Check data freshness
    try:
        from pathlib import Path
        summary_file = Path(__file__).parent / "regime_analysis" / "latest_regime_summary.json"
        if summary_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(summary_file.stat().st_mtime)
            if file_age < timedelta(minutes=40):
                health_status['checks']['data_freshness'] = 'healthy'
            else:
                health_status['checks']['data_freshness'] = f'stale_{file_age.total_seconds()/60:.0f}min'
                health_status['overall_status'] = 'degraded'
        else:
            health_status['checks']['data_freshness'] = 'missing'
            health_status['overall_status'] = 'critical'
    except Exception as e:
        health_status['checks']['data_freshness'] = f'error_{str(e)}'
        health_status['overall_status'] = 'critical'
    
    return health_status

if __name__ == "__main__":
    health = check_system_health()
    print(json.dumps(health, indent=2))
    
    if health['overall_status'] == 'critical':
        sys.exit(1)
    elif health['overall_status'] == 'degraded':
        sys.exit(2)
    else:
        sys.exit(0)
```

## Security Configuration

### 1. API Security

```python
# security.py
from functools import wraps
from flask import request, jsonify
import os
import hashlib
import hmac

def require_api_key(f):
    """Decorator to require API key for sensitive endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('API_SECRET_KEY')
        
        if not api_key or not expected_key:
            return jsonify({'error': 'API key required'}), 401
        
        if not hmac.compare_digest(api_key, expected_key):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def validate_request_data(required_fields):
    """Decorator to validate request data"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == 'POST':
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'JSON data required'}), 400
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({'error': f'Missing fields: {missing_fields}'}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### 2. File System Security

```bash
#!/bin/bash
# secure_installation.sh

# Set proper file permissions
chmod 750 /path/to/India-TS/Daily/Market_Regime
chmod 640 /path/to/India-TS/Daily/Market_Regime/.env
chmod 644 /path/to/India-TS/Daily/Market_Regime/*.py
chmod 755 /path/to/India-TS/Daily/Market_Regime/data
chmod 755 /path/to/India-TS/Daily/Market_Regime/regime_analysis

# Create restricted user for the service
sudo useradd -r -s /bin/false market-regime
sudo chown -R market-regime:market-regime /path/to/India-TS/Daily/Market_Regime

# Set up log rotation
sudo tee /etc/logrotate.d/market-regime << EOF
/path/to/India-TS/Daily/Market_Regime/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su market-regime market-regime
}
EOF
```

## Performance Tuning

### 1. Flask Application Tuning

```python
# performance_config.py
import multiprocessing

# Gunicorn configuration
bind = "127.0.0.1:8080"
workers = min(4, multiprocessing.cpu_count())
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Flask performance settings
FLASK_CONFIG = {
    'JSONIFY_PRETTYPRINT_REGULAR': False,  # Disable pretty printing in production
    'JSON_SORT_KEYS': False,               # Disable key sorting
    'SEND_FILE_MAX_AGE_DEFAULT': 3600,     # Cache static files for 1 hour
}

# Cache configuration
CACHE_CONFIG = {
    'CACHE_TYPE': 'simple',  # Use 'redis' for production
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_THRESHOLD': 1000,
}
```

### 2. Database Optimization

```python
# database_optimization.py
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """Optimized database connection with proper settings"""
    conn = sqlite3.connect(
        'data/regime_learning.db',
        timeout=20.0,
        check_same_thread=False
    )
    
    # Performance optimizations
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    conn.execute('PRAGMA temp_store=MEMORY')
    
    try:
        yield conn
    finally:
        conn.close()

def optimize_database():
    """Run database optimization"""
    with get_db_connection() as conn:
        conn.execute('ANALYZE')
        conn.execute('VACUUM')
        conn.commit()
```

---

*Setup & Configuration Guide for India-TS Market Regime Analysis Module v3.0*  
*Last updated: July 14, 2025*