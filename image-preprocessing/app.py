"""
Flask Application Main Entry Point

This is the main Flask application file that initializes the app
and registers all routes.
"""

from flask import Flask
from routes import register_routes

# Create Flask application
app = Flask(__name__)
# Increased limit for large folder uploads (10GB max)
# Note: For very large datasets (10,000+ images), use folder path input instead of upload
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10GB max
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

# Register all routes
register_routes(app)


if __name__ == '__main__':
    # Run the Flask development server
    app.run(debug=True, host='0.0.0.0', port=5000)

