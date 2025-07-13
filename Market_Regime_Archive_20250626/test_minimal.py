#!/usr/bin/env python3
import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    import flask
    print(f"Flask version: {flask.__version__}")
    print("Flask imported successfully!")
    
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def hello():
        return '<h1>Flask is working!</h1>'
    
    print("\nStarting Flask server...")
    print("Visit: http://localhost:9999")
    app.run(host='localhost', port=9999, debug=False)
    
except ImportError as e:
    print(f"Flask import error: {e}")
    print("\nTry installing Flask with:")
    print("python3 -m pip install flask")
except Exception as e:
    print(f"Error: {e}")