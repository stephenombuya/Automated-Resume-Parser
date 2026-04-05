"""
API authentication utilities.
Supports API keys, JWT tokens, and rate limiting.
"""

import os
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any

import jwt
from flask import request, jsonify, g, current_app

# API key storage (in production, use database or Redis)
API_KEYS = {
    "prod_api_key_123": {
        "name": "Production Client",
        "rate_limit": "1000/hour",
        "permissions": ["read", "write"]
    },
    "test_api_key_456": {
        "name": "Test Client",
        "rate_limit": "100/hour",
        "permissions": ["read"]
    }
}


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                "error": "API key required",
                "message": "Please provide X-API-Key header",
                "code": 401
            }), 401
        
        # Validate API key
        if api_key not in API_KEYS:
            return jsonify({
                "error": "Invalid API key",
                "message": "The provided API key is invalid",
                "code": 401
            }), 401
        
        # Store API key info in request context
        g.api_key_info = API_KEYS[api_key]
        g.api_key = api_key
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_jwt_token(f):
    """Decorator to require JWT token authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "JWT token required",
                "message": "Please provide Bearer token in Authorization header",
                "code": 401
            }), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=[current_app.config['SECURITY_CONFIG'].jwt_algorithm]
            )
            
            # Store user info in request context
            g.user = payload
            g.user_id = payload.get('user_id')
            
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Token expired",
                "message": "JWT token has expired",
                "code": 401
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Invalid token",
                "message": "JWT token is invalid",
                "code": 401
            }), 401
    
    return decorated_function


def generate_api_key(name: str, permissions: list) -> str:
    """Generate a new API key."""
    import secrets
    api_key = secrets.token_urlsafe(32)
    API_KEYS[api_key] = {
        "name": name,
        "rate_limit": "100/hour",
        "permissions": permissions,
        "created_at": datetime.utcnow().isoformat()
    }
    return api_key


def generate_jwt_token(user_id: int, email: str, expires_in_hours: int = 24) -> str:
    """Generate JWT token for user."""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm=current_app.config['SECURITY_CONFIG'].jwt_algorithm
    )
    
    return token
