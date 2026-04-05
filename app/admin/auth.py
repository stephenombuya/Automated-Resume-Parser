"""
Admin authentication utilities.
"""

from functools import wraps
from flask import request, jsonify, g, current_app, session


# Admin users (in production, store in database)
ADMIN_USERS = {
    "admin@example.com": {
        "password_hash": "pbkdf2:sha256:260000$...",  # Use werkzeug generate_password_hash
        "role": "superadmin",
        "permissions": ["all"]
    }
}

# IP whitelist for admin access (optional)
ADMIN_IP_WHITELIST = [
    "127.0.0.1",
    "10.0.0.0/8",  # Internal network
]


def require_admin_auth(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if admin is already logged in via session
        if session.get('admin_logged_in'):
            return f(*args, **kwargs)
        
        # Check for API key in header (alternative)
        api_key = request.headers.get('X-Admin-Key')
        if api_key and api_key == current_app.config.get('ADMIN_API_KEY'):
            return f(*args, **kwargs)
        
        # For API responses, return JSON error
        if request.path.startswith('/admin/api/'):
            return jsonify({
                "error": "Authentication required",
                "message": "Admin access required",
                "code": 401
            }), 401
        
        # For web interface, redirect to login
        return redirect(url_for('admin.login'))
    
    return decorated_function


def require_ip_whitelist(f):
    """Decorator to restrict access by IP address."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        
        # Check if IP is whitelisted
        allowed = False
        for allowed_ip in ADMIN_IP_WHITELIST:
            if '/' in allowed_ip:
                # CIDR notation
                import ipaddress
                if ipaddress.ip_address(client_ip) in ipaddress.ip_network(allowed_ip):
                    allowed = True
                    break
            elif client_ip == allowed_ip:
                allowed = True
                break
        
        if not allowed and current_app.config['is_production']:
            current_app.logger.warning(f"Blocked admin access from {client_ip}")
            return jsonify({
                "error": "Access denied",
                "message": "Your IP address is not authorized",
                "code": 403
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function
