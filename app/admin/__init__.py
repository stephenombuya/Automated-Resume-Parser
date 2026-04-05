"""
Admin Blueprint for internal administration endpoints.
Protected by admin authentication and IP whitelisting.
"""

from flask import Blueprint

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import routes
from app.admin import routes
