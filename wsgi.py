"""
WSGI entry point for production servers (Gunicorn, uWSGI, etc.)

Usage with Gunicorn:
    gunicorn --worker-class gevent --workers 4 --bind 0.0.0.0:5000 wsgi:app

Usage with uWSGI:
    uwsgi --http :5000 --wsgi-file wsgi.py --callable app --processes 4 --threads 2
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv

# Load appropriate .env file
env_file = os.getenv('ENV_FILE', '.env.production' if os.getenv('FLASK_ENV') == 'production' else '.env')
if Path(env_file).exists():
    load_dotenv(env_file)

# Create application instance
from app import create_app
app = create_app()

# Application is ready for WSGI server
if __name__ == '__main__':
    # This is only executed when running directly, not via WSGI
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host=host, port=port)
