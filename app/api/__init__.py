"""
API Blueprint for public resume parsing endpoints.
Handles resume upload, parsing, and retrieval with rate limiting and validation.
"""

from flask import Blueprint

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Import routes to register them
from app.api import routes
