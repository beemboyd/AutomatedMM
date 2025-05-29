import os
import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Central configuration management for the trading system"""
    
    def __init__(self, config_file=None):
        """Initialize configuration from file or environment variables"""
        self.config = configparser.ConfigParser()
        
        # Default config file path
        if config_file is None:
            self.config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
        else:
            self.config_file = config_file
        
        # Load config from file if it exists
        if os.path.exists(self.config_file):
            logger.info(f"Loading configuration from {self.config_file}")
            self.config.read(self.config_file)
        else:
            logger.warning(f"Config file {self.config_file} not found, using default values and environment variables")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration"""
        self.config['API'] = {
            'broker': 'zerodha',
            'api_key': os.environ.get('ZERODHA_API_KEY', ''),
            'api_secret': os.environ.get('ZERODHA_API_SECRET', ''),
            'access_token': os.environ.get('ZERODHA_ACCESS_TOKEN', '')
        }
        
        self.config['Trading'] = {
            'max_positions': '3',
            'product_type': 'MIS',
            'exchange': 'NSE',
            'profit_target': '10.0',
            'position_size_percent': '2.0',
            'trend_ratio_threshold': '4.0',
            'volume_spike_threshold': '4.0'
        }
        
        self.config['System'] = {
            'data_dir': os.path.join(os.path.dirname(__file__), 'data'),
            'log_dir': os.path.join(os.path.dirname(__file__), 'logs'),
            'log_level': 'INFO'
        }
        
    def get(self, section, key, fallback=None):
        """Get configuration value with fallback"""
        # For API credentials, prioritize environment variables over config file
        if section == 'API':
            if key == 'api_key' and 'ZERODHA_API_KEY' in os.environ:
                return os.environ['ZERODHA_API_KEY']
            elif key == 'api_secret' and 'ZERODHA_API_SECRET' in os.environ:
                return os.environ['ZERODHA_API_SECRET']
            elif key == 'access_token' and 'ZERODHA_ACCESS_TOKEN' in os.environ:
                return os.environ['ZERODHA_ACCESS_TOKEN']

        return self.config.get(section, key, fallback=fallback)
    
    def get_int(self, section, key, fallback=None):
        """Get configuration value as integer with fallback"""
        return self.config.getint(section, key, fallback=fallback)
    
    def get_float(self, section, key, fallback=None):
        """Get configuration value as float with fallback"""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def get_bool(self, section, key, fallback=None):
        """Get configuration value as boolean with fallback"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def save(self):
        """Save configuration to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        logger.info(f"Configuration saved to {self.config_file}")
    
    def ensure_directories(self):
        """Ensure all required directories exist"""
        data_dir = self.get('System', 'data_dir')
        log_dir = self.get('System', 'log_dir')
        
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        return data_dir, log_dir

# Singleton instance
_config = None

def get_config(config_file=None):
    """Get or create the singleton configuration instance"""
    global _config
    if _config is None:
        _config = Config(config_file)
        _config.ensure_directories()
    return _config
