#!/usr/bin/env python3
"""
Base Service Class for Dashboard Microservices
Provides common functionality for all dashboard services
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import json
import os
from datetime import datetime
from functools import wraps
import time
from typing import Dict, Any, Optional

class BaseService:
    """Base class for dashboard microservices"""
    
    def __init__(self, name: str, port: int, cache_ttl: int = 300):
        self.name = name
        self.port = port
        self.cache_ttl = cache_ttl
        self.app = Flask(name)
        CORS(self.app)  # Enable CORS for all routes
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Cache for storing results
        self.cache = {}
        self.cache_timestamps = {}
        
        # Service metadata
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
        
        # Setup common routes
        self._setup_common_routes()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup service-specific logging"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'{self.name}.log')
        
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _setup_common_routes(self):
        """Setup common routes for all services"""
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            uptime = (datetime.now() - self.start_time).total_seconds()
            return jsonify({
                'status': 'healthy',
                'service': self.name,
                'uptime_seconds': uptime,
                'request_count': self.request_count,
                'error_count': self.error_count,
                'cache_size': len(self.cache)
            })
        
        @self.app.route('/metrics')
        def metrics():
            """Service metrics endpoint"""
            return jsonify({
                'service': self.name,
                'port': self.port,
                'start_time': self.start_time.isoformat(),
                'requests': {
                    'total': self.request_count,
                    'errors': self.error_count,
                    'success_rate': (self.request_count - self.error_count) / max(1, self.request_count)
                },
                'cache': {
                    'size': len(self.cache),
                    'ttl': self.cache_ttl,
                    'keys': list(self.cache.keys())
                }
            })
        
        @self.app.before_request
        def before_request():
            """Track request metrics"""
            self.request_count += 1
            request.start_time = time.time()
        
        @self.app.after_request
        def after_request(response):
            """Log request completion"""
            if hasattr(request, 'start_time'):
                duration = time.time() - request.start_time
                self.logger.info(f"{request.method} {request.path} - {response.status_code} - {duration:.3f}s")
            return response
        
        @self.app.errorhandler(Exception)
        def handle_error(error):
            """Global error handler"""
            self.error_count += 1
            self.logger.error(f"Error handling request: {str(error)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'message': str(error),
                'service': self.name
            }), 500
    
    def cache_result(self, ttl: Optional[int] = None):
        """Decorator to cache function results"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Check if cached result exists and is fresh
                if cache_key in self.cache:
                    timestamp = self.cache_timestamps.get(cache_key, 0)
                    age = time.time() - timestamp
                    cache_ttl = ttl or self.cache_ttl
                    
                    if age < cache_ttl:
                        self.logger.debug(f"Cache hit for {cache_key}")
                        return self.cache[cache_key]
                
                # Call function and cache result
                try:
                    result = func(*args, **kwargs)
                    self.cache[cache_key] = result
                    self.cache_timestamps[cache_key] = time.time()
                    self.logger.debug(f"Cache miss for {cache_key}, result cached")
                    return result
                except Exception as e:
                    self.logger.error(f"Error in {func.__name__}: {str(e)}")
                    raise
            
            return wrapper
        return decorator
    
    def add_route(self, rule: str, endpoint: str = None, **options):
        """Add a route to the service"""
        def decorator(func):
            self.app.add_url_rule(rule, endpoint, func, **options)
            return func
        return decorator
    
    def run(self, debug: bool = False):
        """Start the service"""
        self.logger.info(f"Starting {self.name} service on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, debug=debug)
    
    def get_data_path(self, filename: str) -> str:
        """Get path to data file"""
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        return os.path.join(data_dir, filename)
    
    def load_json_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Load JSON file with error handling"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"File not found: {filepath}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading {filepath}: {e}")
            return None
    
    def standardize_response(self, data: Any, error: Optional[str] = None) -> Dict[str, Any]:
        """Standardize API response format"""
        response = {
            'service': self.name,
            'timestamp': datetime.now().isoformat(),
            'success': error is None,
        }
        
        if error:
            response['error'] = error
        else:
            response['data'] = data
            
        return response