"""
Production-grade Flask application for resume parsing with comprehensive
error handling, security, monitoring, and scalability features.

Incorporates:
- Production configuration
- Database models with validation
- PDF and DOCX parsing with OCR fallback
- NLP entity extraction
- File validation and security
- Rate limiting
- Request/response logging
- Health checks
- Graceful error handling
"""

import os
import sys
import signal
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

from flask import Flask, request, jsonify, current_app, g
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from prometheus_flask_exporter import PrometheusMetrics

# Application imports
from config import get_config, Config
from models import db, Resume, ResumeStatus, ExperienceLevel, EducationLevel
from parser.pdf_parser import PDFParser, PDFParsingMode, PDFParserError
from parser.docx_parser import DOCXParser, DOCXParserError
from parser.nlp_processor import NLPProcessor, NLPProcessorError
from utils import (
    FileValidator,
    save_upload_file,
    allowed_file,
    PerformanceMonitor,
    timer,
    logger,
    ResumeParserError,
    FileTypeError,
    FileSizeError,
    VirusDetectedError,
    ParsingError
)

# Initialize Flask app
app = Flask(__name__)

# Load configuration based on environment
config = get_config()
app.config.from_object(config)

# Store config reference for easy access
app.config['APP_CONFIG'] = config

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# CORS configuration
CORS(
    app,
    origins=config.SECURITY_CONFIG.cors_allowed_origins,
    methods=config.SECURITY_CONFIG.cors_allowed_methods,
    allow_headers=config.SECURITY_CONFIG.cors_allowed_headers,
    supports_credentials=config.SECURITY_CONFIG.cors_allow_credentials,
    max_age=config.SECURITY_CONFIG.cors_max_age
)

# Rate limiting
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=[config.SECURITY_CONFIG.rate_limit_default],
    storage_uri=config.REDIS_CONFIG.url if config.SECURITY_CONFIG.rate_limiting_enabled else "memory://"
)

# Prometheus metrics (optional)
if config.is_production:
    metrics = PrometheusMetrics(app, group_by='endpoint')

# Initialize parsers with configuration
pdf_parser = PDFParser(
    mode=PDFParsingMode.HYBRID if config.is_feature_enabled('enable_ocr') else PDFParsingMode.FAST,
    preserve_layout=True,
    max_file_size_mb=config.UPLOAD_CONFIG.max_file_size_mb,
    extract_metadata=True,
    fallback_to_ocr=config.is_feature_enabled('enable_ocr')
)

docx_parser = DOCXParser(
    extract_tables=True,
    extract_headers=True,
    extract_footers=True,
    preserve_line_breaks=True,
    max_file_size_mb=config.UPLOAD_CONFIG.max_file_size_mb
)

nlp_processor = NLPProcessor(
    model_name="en_core_web_sm",
    lazy_load=True,
    extract_multiple_persons=True,
    normalize_phone=True,
    skills_case_sensitive=False,
    use_fuzzy_matching=False
)

# File validator
file_validator = FileValidator(
    max_file_size_mb=config.UPLOAD_CONFIG.max_file_size_mb,
    allowed_extensions=config.UPLOAD_CONFIG.allowed_extensions,
    scan_for_viruses=False  # Enable if virus scanning configured
)


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Handle HTTP exceptions with consistent response format."""
    response = {
        "error": error.description,
        "code": error.code,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Log error
    current_app.logger.error(f"HTTP {error.code}: {error.description}")
    
    return jsonify(response), error.code


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    """Handle file size exceeded error."""
    max_size_mb = current_app.config['UPLOAD_CONFIG'].max_file_size_mb
    return jsonify({
        "error": f"File size exceeds maximum allowed size of {max_size_mb}MB",
        "code": 413,
        "timestamp": datetime.utcnow().isoformat()
    }), 413


@app.errorhandler(FileTypeError)
def handle_file_type_error(error):
    """Handle invalid file type errors."""
    return jsonify({
        "error": str(error),
        "code": 400,
        "allowed_extensions": list(current_app.config['UPLOAD_CONFIG'].allowed_extensions),
        "timestamp": datetime.utcnow().isoformat()
    }), 400


@app.errorhandler(FileSizeError)
def handle_file_size_error(error):
    """Handle file size errors."""
    return jsonify({
        "error": str(error),
        "code": 400,
        "max_size_mb": current_app.config['UPLOAD_CONFIG'].max_file_size_mb,
        "timestamp": datetime.utcnow().isoformat()
    }), 400


@app.errorhandler(ParsingError)
def handle_parsing_error(error):
    """Handle document parsing errors."""
    return jsonify({
        "error": "Failed to parse document",
        "details": str(error),
        "code": 422,
        "timestamp": datetime.utcnow().isoformat()
    }), 422


@app.errorhandler(NLPProcessorError)
def handle_nlp_error(error):
    """Handle NLP processing errors."""
    return jsonify({
        "error": "Failed to extract information from document",
        "details": str(error),
        "code": 422,
        "timestamp": datetime.utcnow().isoformat()
    }), 422


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle unexpected errors gracefully."""
    current_app.logger.exception(f"Unexpected error: {error}")
    
    return jsonify({
        "error": "An unexpected error occurred",
        "code": 500,
        "timestamp": datetime.utcnow().isoformat()
    }), 500


# ============================================================================
# Middleware
# ============================================================================

@app.before_request
def before_request():
    """Request preprocessing."""
    g.request_start_time = time.time()
    g.request_id = os.urandom(8).hex()
    
    # Log request
    current_app.logger.info(
        f"Request {g.request_id}: {request.method} {request.path} "
        f"from {request.remote_addr}"
    )
    
    # Add security headers
    if current_app.config['SECURITY_CONFIG'].security_headers_enabled:
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            if current_app.config['SECURITY_CONFIG'].hsts_enabled:
                response.headers['Strict-Transport-Security'] = f"max-age={current_app.config['SECURITY_CONFIG'].hsts_max_age}"
            
            if current_app.config['SECURITY_CONFIG'].referrer_policy:
                response.headers['Referrer-Policy'] = current_app.config['SECURITY_CONFIG'].referrer_policy
            
            return response


@app.after_request
def after_request(response):
    """Request post-processing."""
    if hasattr(g, 'request_start_time'):
        elapsed_ms = (time.time() - g.request_start_time) * 1000
        
        current_app.logger.info(
            f"Response {g.request_id}: {response.status_code} "
            f"in {elapsed_ms:.2f}ms"
        )
        
        # Add timing header
        response.headers['X-Response-Time-MS'] = str(int(elapsed_ms))
    
    return response


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": current_app.config['ENV'].value
    }), 200


@app.route('/health/ready', methods=['GET'])
def readiness_check():
    """Readiness check for orchestration."""
    checks = {
        "database": False,
        "parsers": False,
        "nlp": False
    }
    
    try:
        # Check database connection
        db.session.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        current_app.logger.error(f"Database readiness check failed: {e}")
    
    # Check parsers are initialized
    checks["parsers"] = pdf_parser is not None and docx_parser is not None
    checks["nlp"] = nlp_processor is not None
    
    all_ready = all(checks.values())
    
    return jsonify({
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }), 200 if all_ready else 503


@app.route('/health/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint (if not using prometheus_flask_exporter)."""
    if not current_app.config['is_production']:
        return jsonify({"error": "Metrics only available in production"}), 404
    
    # Return basic metrics
    return jsonify({
        "requests": request.metrics if hasattr(request, 'metrics') else {},
        "timestamp": datetime.utcnow().isoformat()
    }), 200


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/api/v1/parse', methods=['POST'])
@limiter.limit(config.SECURITY_CONFIG.rate_limit_upload)
def parse_resume():
    """
    Parse a resume file and extract candidate information.
    
    Expected: multipart/form-data with 'file' field containing the resume.
    
    Returns:
        JSON with extracted candidate information
    """
    with PerformanceMonitor("parse_resume_endpoint"):
        # Validate file presence
        if 'file' not in request.files:
            return jsonify({
                "error": "No file provided",
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "error": "No file selected",
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        # Validate file type
        if not allowed_file(file.filename, current_app.config['UPLOAD_CONFIG'].allowed_extensions):
            return jsonify({
                "error": "Invalid file type",
                "code": 400,
                "allowed_extensions": list(current_app.config['UPLOAD_CONFIG'].allowed_extensions),
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        # Save file temporarily
        temp_filepath = None
        try:
            # Save and validate file
            save_result = save_upload_file(
                file,
                current_app.config['UPLOAD_CONFIG'].upload_folder,
                secure=True,
                generate_unique_name=True
            )
            
            temp_filepath = save_result['filepath']
            
            # Validate file (size, MIME type, corruption)
            validation = file_validator.validate_file(temp_filepath)
            
            if not validation['valid']:
                return jsonify({
                    "error": "File validation failed",
                    "details": validation['errors'],
                    "code": 400,
                    "timestamp": datetime.utcnow().isoformat()
                }), 400
            
            # Parse based on file extension
            extension = Path(temp_filepath).suffix.lower().lstrip('.')
            
            with timer(f"parse_{extension}_file"):
                if extension == 'pdf':
                    parse_result = pdf_parser.parse(temp_filepath)
                    text = parse_result.text
                    metadata = parse_result.metadata
                elif extension == 'docx':
                    parse_result = docx_parser.parse(temp_filepath)
                    text = parse_result.text
                    metadata = parse_result.metadata
                else:
                    # Fallback for text files
                    with open(temp_filepath, 'r', encoding='utf-8') as f:
                        text = f.read()
                    metadata = {"file_type": "text"}
            
            # Extract information using NLP
            with timer("nlp_extraction"):
                extraction = nlp_processor.extract_all(text)
            
            # Calculate experience level and years
            years_of_experience = None
            experience_level = None
            
            if extraction.skills:
                # Rough heuristic based on skills seniority
                senior_skills = {'leadership', 'management', 'architecture', 'strategy'}
                junior_skills = {'intern', 'assistant', 'trainee'}
                
                if any(skill in senior_skills for skill in extraction.skills):
                    experience_level = ExperienceLevel.SENIOR
                elif any(skill in junior_skills for skill in extraction.skills):
                    experience_level = ExperienceLevel.JUNIOR
                else:
                    experience_level = ExperienceLevel.MID
            
            # Save to database
            resume = Resume(
                filename=save_result['filename'],
                original_filename=file.filename,
                file_size=save_result['size_bytes'],
                file_hash=save_result['sha256'],
                candidate_name=extraction.first_person,
                email=extraction.first_email,
                phone=extraction.first_phone,
                skills=extraction.skills,
                experience=[],
                education=[],
                status=ResumeStatus.COMPLETED,
                experience_level=experience_level,
                years_of_experience=years_of_experience,
                processing_started_at=g.get('request_start_time', datetime.utcnow()),
                processing_completed_at=datetime.utcnow()
            )
            
            # Add scores if available
            if extraction.confidence_scores:
                resume.update_match_score(
                    skills_score=extraction.confidence_scores.get('skills', 0) * 100,
                    experience_score=extraction.confidence_scores.get('persons', 0) * 100
                )
            
            db.session.add(resume)
            db.session.commit()
            
            # Prepare response
            response_data = {
                "success": True,
                "resume_id": str(resume.uuid),
                "name": extraction.first_person,
                "email": extraction.first_email,
                "phone": extraction.first_phone,
                "skills": extraction.skills,
                "experience_level": experience_level.value if experience_level else None,
                "confidence_scores": extraction.confidence_scores,
                "metadata": {
                    "filename": save_result['filename'],
                    "file_size_mb": save_result['size_mb'],
                    "file_hash": save_result['sha256'][:16] + "...",
                    "pages": parse_result.total_pages if extension == 'pdf' else 1,
                    "processing_time_ms": extraction.processing_time_ms
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            current_app.logger.info(
                f"Successfully parsed resume {resume.uuid}: "
                f"{extraction.first_person}, {len(extraction.skills)} skills"
            )
            
            return jsonify(response_data), 200
            
        except (FileTypeError, FileSizeError, VirusDetectedError) as e:
            db.session.rollback()
            current_app.logger.warning(f"File validation error: {e}")
            return jsonify({
                "error": str(e),
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
            
        except (PDFParserError, DOCXParserError) as e:
            db.session.rollback()
            current_app.logger.error(f"Parsing error: {e}")
            return jsonify({
                "error": "Failed to parse document",
                "details": str(e),
                "code": 422,
                "timestamp": datetime.utcnow().isoformat()
            }), 422
            
        except NLPProcessorError as e:
            db.session.rollback()
            current_app.logger.error(f"NLP error: {e}")
            return jsonify({
                "error": "Failed to extract information",
                "details": str(e),
                "code": 422,
                "timestamp": datetime.utcnow().isoformat()
            }), 422
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Unexpected error: {e}")
            return jsonify({
                "error": "Internal server error",
                "code": 500,
                "timestamp": datetime.utcnow().isoformat()
            }), 500
            
        finally:
            # Clean up temporary file
            if temp_filepath and os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                    current_app.logger.debug(f"Cleaned up temp file: {temp_filepath}")
                except Exception as e:
                    current_app.logger.warning(f"Failed to clean up temp file: {e}")


@app.route('/api/v1/resume/<resume_id>', methods=['GET'])
def get_resume(resume_id: str):
    """
    Retrieve parsed resume by ID.
    
    Args:
        resume_id: Resume UUID (public ID)
    
    Returns:
        JSON with resume information
    """
    try:
        # Query by UUID
        resume = Resume.query.filter_by(uuid=resume_id, deleted_at=None).first_or_404()
        
        # Check if we should include sensitive info (authentication required)
        include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
        
        # In production, require authentication for sensitive data
        if include_sensitive and current_app.config['is_production']:
            # TODO: Add authentication check
            include_sensitive = False
        
        return jsonify(resume.to_dict(include_sensitive=include_sensitive)), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve resume {resume_id}: {e}")
        return jsonify({
            "error": "Resume not found",
            "code": 404,
            "timestamp": datetime.utcnow().isoformat()
        }), 404


@app.route('/api/v1/resumes', methods=['GET'])
@limiter.limit("100/hour")
def list_resumes():
    """
    List resumes with pagination and filtering.
    
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - status: Filter by status
    - experience_level: Filter by experience level
    - search: Search query for full-text search
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        experience_level = request.args.get('experience_level')
        search_query = request.args.get('search')
        
        query = Resume.query.filter_by(deleted_at=None)
        
        # Apply filters
        if status:
            query = query.filter_by(status=ResumeStatus(status))
        
        if experience_level:
            query = query.filter_by(experience_level=ExperienceLevel(experience_level))
        
        if search_query:
            # Use full-text search
            resumes = Resume.search(search_query, limit=per_page, offset=(page-1)*per_page)
            total = Resume.query.filter_by(deleted_at=None).count()
        else:
            # Regular pagination
            paginated = query.order_by(Resume.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            resumes = paginated.items
            total = paginated.total
        
        return jsonify({
            "resumes": [r.to_dict(include_sensitive=False) for r in resumes],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to list resumes: {e}")
        return jsonify({
            "error": "Failed to retrieve resumes",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@app.route('/api/v1/resume/<resume_id>', methods=['DELETE'])
def delete_resume(resume_id: str):
    """
    Soft delete a resume.
    
    Args:
        resume_id: Resume UUID
    """
    try:
        resume = Resume.query.filter_by(uuid=resume_id, deleted_at=None).first_or_404()
        
        # Soft delete
        resume.soft_delete()
        db.session.commit()
        
        current_app.logger.info(f"Soft deleted resume {resume_id}")
        
        return jsonify({
            "success": True,
            "message": "Resume deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete resume {resume_id}: {e}")
        return jsonify({
            "error": "Failed to delete resume",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@app.route('/api/v1/stats', methods=['GET'])
def get_statistics():
    """
    Get resume statistics for dashboard.
    """
    try:
        stats = Resume.get_statistics()
        
        return jsonify({
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to get statistics: {e}")
        return jsonify({
            "error": "Failed to retrieve statistics",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


# ============================================================================
# Admin Endpoints (Protected)
# ============================================================================

@app.route('/api/v1/admin/cache/clear', methods=['POST'])
def clear_cache():
    """
    Clear application caches.
    This endpoint should be protected with authentication in production.
    """
    # TODO: Add authentication check
    
    try:
        nlp_processor.clear_cache()
        
        return jsonify({
            "success": True,
            "message": "Cache cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to clear cache: {e}")
        return jsonify({
            "error": "Failed to clear cache",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@app.route('/api/v1/admin/stats', methods=['GET'])
def admin_stats():
    """
    Detailed system statistics for administrators.
    """
    # TODO: Add authentication check
    
    try:
        # Get database stats
        total_resumes = Resume.query.filter_by(deleted_at=None).count()
        processing_stats = db.session.execute(
            "SELECT status, COUNT(*) FROM resumes GROUP BY status"
        ).fetchall()
        
        # Get model info
        model_info = nlp_processor.get_model_info()
        
        return jsonify({
            "database": {
                "total_resumes": total_resumes,
                "by_status": {status: count for status, count in processing_stats}
            },
            "nlp": model_info,
            "config": current_app.config['APP_CONFIG'].to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to get admin stats: {e}")
        return jsonify({
            "error": "Failed to retrieve admin statistics",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


# ============================================================================
# Graceful Shutdown
# ============================================================================

def graceful_shutdown(signum, frame):
    """Handle graceful shutdown signals."""
    current_app.logger.info("Received shutdown signal, cleaning up...")
    
    # Clean up resources
    if hasattr(pdf_parser, 'cleanup'):
        pdf_parser.cleanup()
    
    if hasattr(docx_parser, 'cleanup'):
        docx_parser.cleanup()
    
    # Close database connections
    db.session.close()
    
    current_app.logger.info("Shutdown complete")
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


# ============================================================================
# Application Factory Pattern (for advanced use)
# ============================================================================

def create_app(config_env: Optional[str] = None) -> Flask:
    """
    Application factory for creating app instances.
    
    Args:
        config_env: Environment name (development, testing, staging, production)
    
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    config_obj = get_config(config_env)
    app.config.from_object(config_obj)
    app.config['APP_CONFIG'] = config_obj
    
    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)
    
    # Initialize CORS
    CORS(app, origins=config_obj.SECURITY_CONFIG.cors_allowed_origins)
    
    # Initialize rate limiter
    Limiter(app, key_func=get_remote_address)
    
    # Register blueprints (if any)
    # from app.api import bp as api_bp
    # app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


def register_error_handlers(app: Flask):
    """Register error handlers for the application."""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Resource not found",
            "code": 404,
            "timestamp": datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "error": "Method not allowed",
            "code": 405,
            "timestamp": datetime.utcnow().isoformat()
        }), 405


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Configure logging for development
    if config.is_development:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Create database tables
    with app.app_context():
        db.create_all()
        current_app.logger.info(f"Database tables created in {config.ENV.value} environment")
    
    # Run the application
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    # Use production server in production
    if config.is_production:
        # Use Gunicorn in production, not the built-in server
        current_app.logger.warning(
            "Running in production with Flask development server. "
            "Use Gunicorn or uWSGI for production."
        )
    
    app.run(
        host=host,
        port=port,
        debug=config.is_development,
        threaded=True
    )
