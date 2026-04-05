"""
Webhook event handlers for processing events and external integrations.
"""

import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from flask import request, jsonify, current_app, g
from app.webhook import webhook_bp


# Webhook event types
WEBHOOK_EVENTS = {
    'resume.parsed': 'resume.parsed',
    'resume.failed': 'resume.failed',
    'resume.deleted': 'resume.deleted'
}


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature using HMAC-SHA256."""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@webhook_bp.route('/resume-processed', methods=['POST'])
def resume_processed_webhook():
    """
    Webhook endpoint for resume processing completion.
    
    Expected webhook payload:
    {
        "event": "resume.parsed",
        "resume_id": "uuid",
        "data": {
            "name": "...",
            "email": "..."
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    try:
        # Get webhook secret from config
        webhook_secret = current_app.config.get('WEBHOOK_SECRET')
        
        # Verify signature if secret is configured
        if webhook_secret:
            signature = request.headers.get('X-Webhook-Signature')
            if not signature:
                return jsonify({
                    "error": "Webhook signature required",
                    "code": 401
                }), 401
            
            payload = request.get_data()
            if not verify_webhook_signature(payload, signature, webhook_secret):
                current_app.logger.warning("Invalid webhook signature")
                return jsonify({
                    "error": "Invalid webhook signature",
                    "code": 401
                }), 401
        
        # Parse webhook payload
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "Invalid webhook payload",
                "code": 400
            }), 400
        
        event_type = data.get('event')
        resume_id = data.get('resume_id')
        event_data = data.get('data', {})
        timestamp = data.get('timestamp', datetime.utcnow().isoformat())
        
        # Validate event type
        if event_type not in WEBHOOK_EVENTS.values():
            current_app.logger.warning(f"Unknown webhook event: {event_type}")
            return jsonify({
                "error": f"Unknown event type: {event_type}",
                "code": 400
            }), 400
        
        # Process based on event type
        if event_type == 'resume.parsed':
            _handle_resume_parsed(resume_id, event_data)
        elif event_type == 'resume.failed':
            _handle_resume_failed(resume_id, event_data)
        elif event_type == 'resume.deleted':
            _handle_resume_deleted(resume_id, event_data)
        
        current_app.logger.info(f"Webhook processed: {event_type} for {resume_id}")
        
        return jsonify({
            "success": True,
            "message": "Webhook processed successfully",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")
        return jsonify({
            "error": "Internal server error",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


def _handle_resume_parsed(resume_id: str, data: Dict[str, Any]) -> None:
    """
    Handle resume parsed event.
    
    This could trigger:
    - Send email notification
    - Update external CRM
    - Trigger workflow
    - Index in search engine
    """
    current_app.logger.info(f"Resume parsed: {resume_id}")
    
    # Example: Send to external system
    # _send_to_external_api(data)
    
    # Example: Send email notification
    # _send_email_notification(data.get('email'), data.get('name'))
    
    # Example: Update analytics
    # _update_analytics('resume_parsed', resume_id)


def _handle_resume_failed(resume_id: str, data: Dict[str, Any]) -> None:
    """Handle resume parsing failure event."""
    error = data.get('error', 'Unknown error')
    current_app.logger.warning(f"Resume parsing failed: {resume_id} - {error}")
    
    # Example: Send alert to admin
    # _send_admin_alert(f"Resume parsing failed: {resume_id}", error)


def _handle_resume_deleted(resume_id: str, data: Dict[str, Any]) -> None:
    """Handle resume deletion event."""
    current_app.logger.info(f"Resume deleted: {resume_id}")
    
    # Example: Clean up external references
    # _cleanup_external_references(resume_id)


@webhook_bp.route('/register', methods=['POST'])
def register_webhook():
    """
    Register a new webhook endpoint.
    
    Expected payload:
    {
        "url": "https://example.com/webhook",
        "events": ["resume.parsed", "resume.failed"],
        "secret": "your_webhook_secret"
    }
    """
    # TODO: Store webhook registrations in database
    return jsonify({
        "success": True,
        "message": "Webhook registered successfully",
        "webhook_id": "wh_123456"
    }), 201


@webhook_bp.route('/test', methods=['POST'])
def test_webhook():
    """
    Test webhook endpoint for debugging.
    """
    data = request.get_json()
    
    current_app.logger.info(f"Test webhook received: {data}")
    
    return jsonify({
        "success": True,
        "echo": data,
        "timestamp": datetime.utcnow().isoformat()
    }), 200
