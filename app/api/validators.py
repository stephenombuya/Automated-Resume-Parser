"""
Request validators for API endpoints.
"""

import re
from typing import Dict, Any, Optional, Tuple
from werkzeug.datastructures import FileStorage


def validate_parse_request(file: Optional[FileStorage]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate parse request.
    
    Returns:
        Tuple of (is_valid, error_response)
    """
    errors = []
    
    # Check if file exists
    if not file:
        errors.append({
            "field": "file",
            "message": "No file provided"
        })
        return False, {"errors": errors}
    
    # Check if filename is empty
    if file.filename == '':
        errors.append({
            "field": "file",
            "message": "No file selected"
        })
        return False, {"errors": errors}
    
    # Check file size (will be validated by FileValidator as well)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    return True, {}


def validate_pagination(page: int, per_page: int) -> Tuple[bool, Dict[str, Any]]:
    """Validate pagination parameters."""
    errors = []
    
    if page < 1:
        errors.append({
            "field": "page",
            "message": "Page must be at least 1"
        })
    
    if per_page < 1 or per_page > 100:
        errors.append({
            "field": "per_page",
            "message": "Per page must be between 1 and 100"
        })
    
    if errors:
        return False, {"errors": errors}
    
    return True, {}


def validate_resume_id(resume_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Validate resume ID format."""
    # UUID format validation
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if not re.match(uuid_pattern, resume_id, re.IGNORECASE):
        return False, {
            "error": "Invalid resume ID format",
            "message": "Resume ID must be a valid UUID"
        }
    
    return True, {}
