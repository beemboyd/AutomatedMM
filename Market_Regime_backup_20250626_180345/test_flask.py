#!/usr/bin/env python3
"""Test Flask setup"""

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '''
    <html>
        <body>
            <h1>Flask is working!</h1>
            <p>If you see this, Flask is installed and running correctly.</p>
            <p><a href="/test">Test API endpoint</a></p>
        </body>
    </html>
    '''

@app.route('/test')
def test():
    import json
    return json.dumps({
        'status': 'success',
        'message': 'API is working!',
        'flask_version': Flask.__version__
    })

if __name__ == '__main__':
    print("Starting test Flask server...")
    print("Open http://127.0.0.1:5001 in your browser")
    app.run(debug=True, port=5001)