"""
Production-grade Flask application factory with comprehensive extension
initialization, blueprint registration, error handling, and CLI commands.

Features:
- Application factory pattern
- Extension initialization with proper configuration
- Blueprint registration with URL prefixes
- Health check endpoints
- CLI commands for database operations
- Request/response middleware
- CORS and security headers
- Rate limiting integration
- Logging configuration
- Graceful shutdown handling
"""

import os
import sys
import logging
import signal
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union, List

from flask import Flask, jsonify, request, g, current_app, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

# Configuration imports
from config import get_config, Config, Environment

# Database imports
from models import db, Resume

# Parser imports
from parser.pdf_parser import PDFParser, PDFParsingMode
from parser.docx_parser import DOCXParser
from parser.nlp_processor import NLPProcessor

# Utilities
from utils import (
    FileValidator,
    PerformanceMonitor,
    logger,
    ResumeParserError,
    FileTypeError,
    FileSizeError,
    ParsingError,
    NLPProcessorError
)

# Blueprints (will be created)
from api import api_bp
from admin import admin_bp
from webhook import webhook_bp


class AppFactory:
    """
    Production-ready Flask application factory with comprehensive setup.
    
    Usage:
        app = AppFactory.create_app()
        app = AppFactory.create_app(config_env='production')
    """
    
    @staticmethod
    def create_app(config_env: Optional[str] = None) -> Flask:
        """
        Create and configure Flask application instance.
        
        Args:
            config_env: Environment name (development, testing, staging, production)
        
        Returns:
            Configured Flask application
        """
        # Load configuration
        config_obj = get_config(config_env)
        
        # Create Flask app
        app = Flask(
            __name__,
            instance_relative_config=True,
            static_folder='static',
            static_url_path='/static'
        )
        
        # Load configuration
        app.config.from_object(config_obj)
        app.config['APP_CONFIG'] = config_obj
        
        # Setup logging
        AppFactory._setup_logging(app)
        
        # Initialize extensions
        AppFactory._init_extensions(app)
        
        # Register blueprints
        AppFactory._register_blueprints(app)
        
        # Register error handlers
        AppFactory._register_error_handlers(app)
        
        # Register middleware
        AppFactory._register_middleware(app)
        
        # Register CLI commands
        AppFactory._register_cli_commands(app)
        
        # Setup shutdown handlers
        AppFactory._setup_shutdown_handlers(app)
        
        # Log startup information
        AppFactory._log_startup_info(app)
        
        return app
    
    @staticmethod
    def _setup_logging(app: Flask) -> None:
        """Configure logging for the application."""
        log_config = app.config['LOGGING_CONFIG']
        
        # Set log level
        log_level = getattr(logging, log_config.level.value)
        app.logger.setLevel(log_level)
        
        # Configure handlers
        if log_config.file_enabled:
            # File handler with rotation
            log_path = Path(log_config.file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_config.file_path,
                maxBytes=log_config.file_max_bytes,
                backupCount=log_config.file_backup_count
            )
            file_handler.setLevel(log_level)
            
            if log_config.json_format:
                # Use JSON formatter for structured logging
                try:
                    from pythonjsonlogger import jsonlogger
                    formatter = jsonlogger.JsonFormatter(
                        fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
                    )
                except ImportError:
                    formatter = logging.Formatter(log_config.format)
            else:
                formatter = logging.Formatter(log_config.format, log_config.date_format)
            
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
        
        # Console handler for development
        if app.config['is_development']:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter(log_config.format, log_config.date_format)
            console_handler.setFormatter(console_formatter)
            app.logger.addHandler(console_handler)
        
        # Sentry integration
        if log_config.sentry_dsn:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.flask import FlaskIntegration
                from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
                
                sentry_sdk.init(
                    dsn=log_config.sentry_dsn,
                    environment=log_config.sentry_environment or app.config['ENV'].value,
                    integrations=[
                        FlaskIntegration(),
                        SqlalchemyIntegration()
                    ],
                    traces_sample_rate=log_config.sentry_traces_sample_rate
                )
                app.logger.info("Sentry integration enabled")
            except ImportError:
                app.logger.warning("Sentry SDK not installed, skipping integration")
    
    @staticmethod
    def _init_extensions(app: Flask) -> None:
        """Initialize Flask extensions."""
        
        # Database
        db.init_app(app)
        
        # Database migrations
        migrate = Migrate(app, db, directory='migrations')
        
        # CORS
        cors_config = app.config['SECURITY_CONFIG']
        CORS(
            app,
            origins=cors_config.cors_allowed_origins,
            methods=cors_config.cors_allowed_methods,
            allow_headers=cors_config.cors_allowed_headers,
            supports_credentials=cors_config.cors_allow_credentials,
            max_age=cors_config.cors_max_age
        )
        
        # Rate limiting
        limiter_config = app.config['SECURITY_CONFIG']
        if limiter_config.rate_limiting_enabled:
            storage_uri = app.config['REDIS_CONFIG'].url if limiter_config.rate_limit_storage == 'redis' else "memory://"
            Limiter(
                app,
                key_func=get_remote_address,
                default_limits=[limiter_config.rate_limit_default],
                storage_uri=storage_uri,
                strategy="fixed-window"
            )
        
        # Prometheus metrics (optional)
        if app.config['is_production']:
            try:
                from prometheus_flask_exporter import PrometheusMetrics
                metrics = PrometheusMetrics(app, group_by='endpoint')
                app.config['PROMETHEUS_METRICS'] = metrics
                app.logger.info("Prometheus metrics enabled")
            except ImportError:
                app.logger.warning("Prometheus exporter not installed")
        
        # Store extension references on app
        app.extensions = {
            'db': db,
            'migrate': migrate
        }
    
    @staticmethod
    def _register_blueprints(app: Flask) -> None:
        """Register all blueprints with proper URL prefixes."""
        
        # API blueprint
        if hasattr(api_bp, 'register_blueprint'):
            app.register_blueprint(api_bp, url_prefix='/api/v1')
        elif isinstance(api_bp, Blueprint):
            app.register_blueprint(api_bp, url_prefix='/api/v1')
        
        # Admin blueprint (protected)
        if hasattr(admin_bp, 'register_blueprint'):
            app.register_blueprint(admin_bp, url_prefix='/admin')
        elif isinstance(admin_bp, Blueprint):
            app.register_blueprint(admin_bp, url_prefix='/admin')
        
        # Webhook blueprint
        if hasattr(webhook_bp, 'register_blueprint'):
            app.register_blueprint(webhook_bp, url_prefix='/webhook')
        elif isinstance(webhook_bp, Blueprint):
            app.register_blueprint(webhook_bp, url_prefix='/webhook')
        
        # Root health endpoint
        @app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                "status": "healthy",
                "environment": app.config['ENV'].value,
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        
        @app.route('/health/ready', methods=['GET'])
        def readiness_check():
            """Kubernetes readiness probe."""
            checks = {
                "database": False,
                "application": True
            }
            
            try:
                # Check database connection
                db.session.execute("SELECT 1")
                checks["database"] = True
            except Exception as e:
                app.logger.error(f"Readiness check failed: {e}")
            
            all_ready = all(checks.values())
            status_code = 200 if all_ready else 503
            
            return jsonify({
                "ready": all_ready,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }), status_code
        
        @app.route('/health/live', methods=['GET'])
        def liveness_check():
            """Kubernetes liveness probe."""
            return jsonify({
                "alive": True,
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        
        @app.route('/metrics', methods=['GET'])
        def metrics_endpoint():
            """Prometheus metrics endpoint."""
            if 'PROMETHEUS_METRICS' in app.config:
                return app.config['PROMETHEUS_METRICS'].export_metrics()
            else:
                return jsonify({"error": "Metrics not enabled"}), 404
        
        @app.route('/info', methods=['GET'])
        def app_info():
            """Application information endpoint."""
            return jsonify({
                "name": "Resume Parser API",
                "version": app.config.get('APP_VERSION', '1.0.0'),
                "environment": app.config['ENV'].value,
                "features": {
                    "ocr": app.config.is_feature_enabled('enable_ocr'),
                    "async_processing": app.config.is_feature_enabled('enable_async_processing'),
                    "caching": app.config.is_feature_enabled('enable_caching'),
                },
                "timestamp": datetime.utcnow().isoformat()
            }), 200
    
    @staticmethod
    def _register_error_handlers(app: Flask) -> None:
        """Register custom error handlers."""
        
        @app.errorhandler(400)
        def bad_request(error):
            return jsonify({
                "error": "Bad request",
                "message": str(error.description) if hasattr(error, 'description') else "Invalid request",
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        @app.errorhandler(401)
        def unauthorized(error):
            return jsonify({
                "error": "Unauthorized",
                "message": "Authentication required",
                "code": 401,
                "timestamp": datetime.utcnow().isoformat()
            }), 401
        
        @app.errorhandler(403)
        def forbidden(error):
            return jsonify({
                "error": "Forbidden",
                "message": "You don't have permission to access this resource",
                "code": 403,
                "timestamp": datetime.utcnow().isoformat()
            }), 403
        
        @app.errorhandler(404)
        def not_found(error):
            return jsonify({
                "error": "Not found",
                "message": "The requested resource was not found",
                "code": 404,
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        @app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({
                "error": "Method not allowed",
                "message": f"Method {request.method} is not allowed for this endpoint",
                "code": 405,
                "timestamp": datetime.utcnow().isoformat()
            }), 405
        
        @app.errorhandler(413)
        def request_entity_too_large(error):
            max_size_mb = app.config['UPLOAD_CONFIG'].max_file_size_mb
            return jsonify({
                "error": "Request entity too large",
                "message": f"File size exceeds maximum of {max_size_mb}MB",
                "code": 413,
                "timestamp": datetime.utcnow().isoformat()
            }), 413
        
        @app.errorhandler(429)
        def too_many_requests(error):
            return jsonify({
                "error": "Too many requests",
                "message": "Rate limit exceeded. Please try again later.",
                "code": 429,
                "timestamp": datetime.utcnow().isoformat()
            }), 429
        
        @app.errorhandler(500)
        def internal_server_error(error):
            app.logger.exception(f"Internal server error: {error}")
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "code": 500,
                "timestamp": datetime.utcnow().isoformat()
            }), 500
        
        @app.errorhandler(FileTypeError)
        def handle_file_type_error(error):
            return jsonify({
                "error": "Invalid file type",
                "message": str(error),
                "allowed_extensions": list(app.config['UPLOAD_CONFIG'].allowed_extensions),
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        @app.errorhandler(FileSizeError)
        def handle_file_size_error(error):
            return jsonify({
                "error": "File size exceeded",
                "message": str(error),
                "max_size_mb": app.config['UPLOAD_CONFIG'].max_file_size_mb,
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
        @app.errorhandler(ParsingError)
        def handle_parsing_error(error):
            return jsonify({
                "error": "Document parsing failed",
                "message": str(error),
                "code": 422,
                "timestamp": datetime.utcnow().isoformat()
            }), 422
        
        @app.errorhandler(NLPProcessorError)
        def handle_nlp_error(error):
            return jsonify({
                "error": "Information extraction failed",
                "message": str(error),
                "code": 422,
                "timestamp": datetime.utcnow().isoformat()
            }), 422
        
        @app.errorhandler(ResumeParserError)
        def handle_parser_error(error):
            return jsonify({
                "error": "Resume parsing failed",
                "message": str(error),
                "code": 422,
                "timestamp": datetime.utcnow().isoformat()
            }), 422
        
        @app.errorhandler(Exception)
        def handle_unhandled_exception(error):
            app.logger.exception(f"Unhandled exception: {error}")
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred. Our team has been notified.",
                "code": 500,
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    
    @staticmethod
    def _register_middleware(app: Flask) -> None:
        """Register request/response middleware."""
        
        @app.before_request
        def before_request():
            """Request preprocessing middleware."""
            # Generate request ID
            g.request_id = os.urandom(8).hex()
            g.request_start_time = time.time()
            
            # Log request
            app.logger.info(
                f"[{g.request_id}] {request.method} {request.path} "
                f"from {request.remote_addr}"
            )
            
            # Add security headers to response
            @app.after_request
            def add_security_headers(response):
                # Security headers
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['X-XSS-Protection'] = '1; mode=block'
                response.headers['X-Request-ID'] = g.get('request_id', '')
                
                # Add timing header
                if hasattr(g, 'request_start_time'):
                    elapsed_ms = (time.time() - g.request_start_time) * 1000
                    response.headers['X-Response-Time-MS'] = str(int(elapsed_ms))
                
                # HSTS header for production
                if app.config['is_production'] and app.config['SECURITY_CONFIG'].hsts_enabled:
                    response.headers['Strict-Transport-Security'] = \
                        f"max-age={app.config['SECURITY_CONFIG'].hsts_max_age}"
                
                # Referrer policy
                if app.config['SECURITY_CONFIG'].referrer_policy:
                    response.headers['Referrer-Policy'] = \
                        app.config['SECURITY_CONFIG'].referrer_policy
                
                return response
        
        @app.after_request
        def after_request(response):
            """Response post-processing middleware."""
            # Log response
            if hasattr(g, 'request_id'):
                app.logger.info(
                    f"[{g.request_id}] Response: {response.status_code} "
                    f"in {response.headers.get('X-Response-Time-MS', '0')}ms"
                )
            
            # CORS headers for development
            if app.config['is_development']:
                response.headers['Access-Control-Allow-Origin'] = '*'
            
            return response
    
    @staticmethod
    def _register_cli_commands(app: Flask) -> None:
        """Register Flask CLI commands."""
        
        @app.cli.command('init-db')
        def init_db():
            """Initialize the database."""
            with app.app_context():
                db.create_all()
                app.logger.info("Database tables created")
                print("✓ Database initialized")
        
        @app.cli.command('reset-db')
        def reset_db():
            """Reset the database (drop and recreate)."""
            confirm = input("WARNING: This will delete all data. Are you sure? (y/N): ")
            if confirm.lower() == 'y':
                with app.app_context():
                    db.drop_all()
                    db.create_all()
                    app.logger.info("Database reset completed")
                    print("✓ Database reset")
            else:
                print("Operation cancelled")
        
        @app.cli.command('seed-db')
        def seed_db():
            """Seed the database with sample data."""
            from faker import Faker
            import random
            
            fake = Faker()
            
            with app.app_context():
                for _ in range(10):
                    resume = Resume(
                        filename=f"{fake.name().replace(' ', '_')}.pdf",
                        candidate_name=fake.name(),
                        email=fake.email(),
                        phone=fake.phone_number(),
                        skills=[fake.word() for _ in range(random.randint(3, 8))],
                        experience=[],
                        education=[]
                    )
                    db.session.add(resume)
                
                db.session.commit()
                app.logger.info("Database seeded with sample data")
                print("✓ Database seeded with 10 sample resumes")
        
        @app.cli.command('show-config')
        def show_config():
            """Display current configuration."""
            config_dict = app.config['APP_CONFIG'].to_dict()
            print("\n=== Application Configuration ===\n")
            for key, value in config_dict.items():
                print(f"{key}: {value}")
        
        @app.cli.command('check-health')
        def check_health():
            """Check application health."""
            import requests
            
            url = f"http://localhost:{os.getenv('FLASK_PORT', 5000)}/health"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print("✓ Application is healthy")
                    data = response.json()
                    print(f"  Environment: {data['environment']}")
                    print(f"  Status: {data['status']}")
                else:
                    print(f"✗ Health check failed with status {response.status_code}")
            except Exception as e:
                print(f"✗ Health check failed: {e}")
    
    @staticmethod
    def _setup_shutdown_handlers(app: Flask) -> None:
        """Setup graceful shutdown handlers."""
        
        def graceful_shutdown(signum, frame):
            """Handle shutdown signals."""
            app.logger.info("Received shutdown signal, cleaning up...")
            
            # Close database connections
            try:
                db.session.close()
                app.logger.info("Database connections closed")
            except Exception as e:
                app.logger.error(f"Error closing database: {e}")
            
            # Clean up parser resources
            try:
                if 'pdf_parser' in app.config:
                    pdf_parser = app.config['pdf_parser']
                    if hasattr(pdf_parser, 'cleanup'):
                        pdf_parser.cleanup()
            except Exception as e:
                app.logger.error(f"Error cleaning up PDF parser: {e}")
            
            try:
                if 'docx_parser' in app.config:
                    docx_parser = app.config['docx_parser']
                    if hasattr(docx_parser, 'cleanup'):
                        docx_parser.cleanup()
            except Exception as e:
                app.logger.error(f"Error cleaning up DOCX parser: {e}")
            
            app.logger.info("Shutdown complete")
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, graceful_shutdown)
        signal.signal(signal.SIGINT, graceful_shutdown)
    
    @staticmethod
    def _log_startup_info(app: Flask) -> None:
        """Log application startup information."""
        app.logger.info("=" * 60)
        app.logger.info("Application Starting")
        app.logger.info(f"Environment: {app.config['ENV'].value}")
        app.logger.info(f"Debug Mode: {app.debug}")
        app.logger.info(f"Database: {app.config['DATABASE_CONFIG'].url[:50]}...")
        app.logger.info(f"Upload Folder: {app.config['UPLOAD_CONFIG'].upload_folder}")
        app.logger.info(f"Max File Size: {app.config['UPLOAD_CONFIG'].max_file_size_mb}MB")
        app.logger.info(f"Rate Limiting: {app.config['SECURITY_CONFIG'].rate_limiting_enabled}")
        app.logger.info(f"CORS Origins: {app.config['SECURITY_CONFIG'].cors_allowed_origins}")
        app.logger.info(f"Features Enabled: {[k for k, v in app.config['FEATURE_FLAGS'].__dict__.items() if v and not k.startswith('_')]}")
        app.logger.info("=" * 60)


# ============================================================================
# Application Instance Creation (Simplified)
# ============================================================================

def create_app(config_env: Optional[str] = None) -> Flask:
    """
    Factory function for creating Flask application instance.
    
    Args:
        config_env: Environment name (development, testing, staging, production)
    
    Returns:
        Configured Flask application
    """
    return AppFactory.create_app(config_env)



# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Create application
    app = create_app()
    
    # Create upload directory if it doesn't exist
    upload_folder = app.config['UPLOAD_CONFIG'].upload_folder
    os.makedirs(upload_folder, exist_ok=True)
    
    # Get host and port from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    # Run application
    if app.config['is_production']:
        app.logger.warning(
            "Running in production with Flask development server. "
            "Use Gunicorn or uWSGI for production deployments."
        )
    
    app.run(
        host=host,
        port=port,
        debug=app.config['is_development'],
        threaded=True,
        use_reloader=app.config['is_development']
    )
