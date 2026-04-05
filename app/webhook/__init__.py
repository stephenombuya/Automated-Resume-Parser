"""
Webhook Blueprint for external integrations and event notifications.
"""

from flask import Blueprint

# Create blueprint
webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

# Import routes
from app.webhook import routes
