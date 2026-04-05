"""
Production-grade configuration module with environment-based settings,
validation, security defaults, and feature flags.

Features:
- Multiple environment configs (development, testing, staging, production)
- Automatic validation of critical settings
- Secure defaults for production
- Database connection pooling and SSL
- File upload security settings
- Rate limiting and CORS configuration
- Feature flags for gradual rollouts
- Secret management with fallbacks
"""

import os
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import timedelta
from enum import Enum
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Environment(str, Enum):
    """Application environment enum."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log level enum."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration with connection pooling and SSL."""
    
    # Connection settings
    url: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    
    # SSL settings (for production)
    ssl_mode: str = "prefer"  # disable, allow, prefer, require, verify-ca, verify-full
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    ssl_ca: Optional[str] = None
    
    # Query settings
    echo: bool = False
    echo_pool: bool = False
    
    def get_engine_params(self) -> Dict[str, Any]:
        """Get SQLAlchemy engine parameters."""
        params = {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "echo": self.echo,
            "echo_pool": self.echo_pool,
        }
        
        # Add SSL parameters if in production mode
        if self.ssl_mode in ["require", "verify-ca", "verify-full"]:
            params["connect_args"] = {
                "sslmode": self.ssl_mode,
            }
            if self.ssl_cert:
                params["connect_args"]["sslcert"] = self.ssl_cert
            if self.ssl_key:
                params["connect_args"]["sslkey"] = self.ssl_key
            if self.ssl_ca:
                params["connect_args"]["sslrootcert"] = self.ssl_ca
        
        return params


@dataclass
class RedisConfig:
    """Redis configuration for caching and rate limiting."""
    
    url: str = "redis://localhost:6379/0"
    ssl: bool = False
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    max_connections: int = 50
    
    # Cache settings
    default_ttl: int = 300  # 5 minutes
    resume_cache_ttl: int = 3600  # 1 hour
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/hour"
    rate_limit_upload: str = "10/minute"
    rate_limit_search: str = "30/minute"


@dataclass
class FileUploadConfig:
    """File upload configuration with security settings."""
    
    # Basic settings
    upload_folder: str = "uploads"
    max_file_size_mb: int = 10
    allowed_extensions: set = field(default_factory=lambda: {'pdf', 'docx', 'txt'})
    allowed_mime_types: set = field(default_factory=lambda: {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    })
    
    # Security settings
    secure_filename: bool = True
    scan_for_viruses: bool = False  # Enable if virus scanner available
    virus_scan_endpoint: Optional[str] = None
    
    # Storage backend
    storage_backend: str = "local"  # local, s3, gcs, azure
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    cloudfront_url: Optional[str] = None
    
    # Processing settings
    max_upload_queue_size: int = 100
    async_processing: bool = True
    processing_timeout_seconds: int = 300
    
    def get_upload_path(self) -> Path:
        """Get absolute upload folder path."""
        path = Path(self.upload_folder)
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass
class SecurityConfig:
    """Security configuration."""
    
    # Secret keys
    secret_key: str = ""
    jwt_secret_key: str = ""
    api_key_salt: str = ""
    
    # JWT settings
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires: timedelta = timedelta(hours=1)
    jwt_refresh_token_expires: timedelta = timedelta(days=30)
    
    # CORS settings
    cors_allowed_origins: List[str] = field(default_factory=list)
    cors_allowed_methods: List[str] = field(default_factory=lambda: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    cors_allowed_headers: List[str] = field(default_factory=lambda: ['Content-Type', 'Authorization'])
    cors_allow_credentials: bool = True
    cors_max_age: int = 86400  # 24 hours
    
    # Session settings
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"
    session_cookie_max_age: int = 86400  # 24 hours
    
    # CSRF protection
    csrf_enabled: bool = True
    csrf_cookie_secure: bool = True
    csrf_cookie_httponly: bool = False
    
    # Rate limiting
    rate_limiting_enabled: bool = True
    rate_limit_storage: str = "redis"  # memory, redis
    
    # Security headers
    security_headers_enabled: bool = True
    content_security_policy: Optional[str] = None
    referrer_policy: str = "strict-origin-when-cross-origin"
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year


@dataclass
class LoggingConfig:
    """Logging configuration."""
    
    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # File logging
    file_enabled: bool = True
    file_path: str = "logs/app.log"
    file_max_bytes: int = 10485760  # 10MB
    file_backup_count: int = 10
    
    # JSON logging (for production/ELK stack)
    json_format: bool = False
    
    # Sentry integration
    sentry_dsn: Optional[str] = None
    sentry_environment: Optional[str] = None
    sentry_traces_sample_rate: float = 0.1
    
    # Request logging
    log_request_body: bool = False
    log_response_body: bool = False
    log_headers: List[str] = field(default_factory=lambda: ['user-agent', 'content-type'])
    
    # Sensitive data masking
    mask_passwords: bool = True
    mask_tokens: bool = True
    sensitive_fields: List[str] = field(default_factory=lambda: [
        'password', 'token', 'secret', 'key', 'authorization'
    ])


@dataclass
class FeatureFlags:
    """Feature flags for gradual rollouts and A/B testing."""
    
    # Core features
    enable_ocr: bool = False
    enable_ml_skills_extraction: bool = False
    enable_email_notifications: bool = False
    enable_slack_integration: bool = False
    enable_webhooks: bool = False
    
    # Beta features
    enable_beta_api: bool = False
    enable_ai_match_scoring: bool = False
    enable_parsed_resume_export: bool = False
    enable_bulk_upload: bool = False
    
    # Performance features
    enable_caching: bool = True
    enable_async_processing: bool = True
    enable_read_replica: bool = False
    
    # UI features (if applicable)
    enable_dark_mode: bool = True
    enable_advanced_search: bool = True
    
    def is_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return getattr(self, feature, False)
    
    def enable(self, feature: str) -> None:
        """Enable a feature flag."""
        if hasattr(self, feature):
            setattr(self, feature, True)
    
    def disable(self, feature: str) -> None:
        """Disable a feature flag."""
        if hasattr(self, feature):
            setattr(self, feature, False)


class Config:
    """
    Production-ready configuration class with environment-based settings.
    
    Usage:
        config = Config()
        app.config.from_object(config)
        
        # Or access specific configs
        db_url = config.DATABASE_URL
        upload_path = config.UPLOAD_CONFIG.get_upload_path()
    """
    
    def __init__(self, env: Optional[Environment] = None):
        """
        Initialize configuration.
        
        Args:
            env: Environment to load (auto-detected if not provided)
        """
        # Detect environment
        self.ENV = env or self._detect_environment()
        
        # Load configurations
        self._load_secrets()
        self._load_database_config()
        self._load_redis_config()
        self._load_upload_config()
        self._load_security_config()
        self._load_logging_config()
        self._load_feature_flags()
        
        # Validate critical settings
        self._validate_configuration()
    
    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables."""
        env_str = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower()
        
        if env_str in ['prod', 'production']:
            return Environment.PRODUCTION
        elif env_str in ['staging', 'stage']:
            return Environment.STAGING
        elif env_str in ['test', 'testing']:
            return Environment.TESTING
        else:
            return Environment.DEVELOPMENT
    
    def _load_secrets(self) -> None:
        """Load and validate secret keys."""
        # Generate secure keys if not provided (development only)
        if self.ENV == Environment.DEVELOPMENT:
            self.SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
            self.JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
            self.API_KEY_SALT = os.getenv('API_KEY_SALT', secrets.token_hex(16))
        else:
            # Production must have secrets in environment
            self.SECRET_KEY = os.getenv('SECRET_KEY')
            self.JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
            self.API_KEY_SALT = os.getenv('API_KEY_SALT')
            
            if not all([self.SECRET_KEY, self.JWT_SECRET_KEY, self.API_KEY_SALT]):
                raise ValueError(
                    "Production environment requires SECRET_KEY, JWT_SECRET_KEY, and API_KEY_SALT"
                )
        
        # Minimum key length validation
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
    
    def _load_database_config(self) -> None:
        """Load database configuration."""
        self.DATABASE_CONFIG = DatabaseConfig()
        
        # Get database URL from environment
        db_url = os.getenv('DATABASE_URL')
        
        if not db_url:
            # Default based on environment
            if self.ENV == Environment.PRODUCTION:
                raise ValueError("DATABASE_URL is required in production")
            elif self.ENV == Environment.TESTING:
                db_url = "postgresql://localhost/resume_parser_test"
            else:
                db_url = "postgresql://localhost/resume_parser"
        
        self.DATABASE_CONFIG.url = db_url
        
        # Configure pool settings based on environment
        if self.ENV == Environment.PRODUCTION:
            self.DATABASE_CONFIG.pool_size = int(os.getenv('DB_POOL_SIZE', '20'))
            self.DATABASE_CONFIG.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '40'))
            self.DATABASE_CONFIG.pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '60'))
            self.DATABASE_CONFIG.ssl_mode = os.getenv('DB_SSL_MODE', 'require')
            self.DATABASE_CONFIG.echo = False
            
            # SSL certificate paths
            self.DATABASE_CONFIG.ssl_cert = os.getenv('DB_SSL_CERT')
            self.DATABASE_CONFIG.ssl_key = os.getenv('DB_SSL_KEY')
            self.DATABASE_CONFIG.ssl_ca = os.getenv('DB_SSL_CA')
        elif self.ENV == Environment.STAGING:
            self.DATABASE_CONFIG.pool_size = 10
            self.DATABASE_CONFIG.max_overflow = 20
            self.DATABASE_CONFIG.echo = True
        else:
            # Development
            self.DATABASE_CONFIG.pool_size = 5
            self.DATABASE_CONFIG.max_overflow = 10
            self.DATABASE_CONFIG.echo = True
        
        # SQLAlchemy configuration
        self.SQLALCHEMY_DATABASE_URI = self.DATABASE_CONFIG.url
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.SQLALCHEMY_ENGINE_OPTIONS = self.DATABASE_CONFIG.get_engine_params()
    
    def _load_redis_config(self) -> None:
        """Load Redis configuration."""
        self.REDIS_CONFIG = RedisConfig()
        
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            self.REDIS_CONFIG.url = redis_url
        
        # Override with environment variables
        self.REDIS_CONFIG.ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
        self.REDIS_CONFIG.rate_limit_enabled = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    
    def _load_upload_config(self) -> None:
        """Load file upload configuration."""
        self.UPLOAD_CONFIG = FileUploadConfig()
        
        # Override from environment
        upload_folder = os.getenv('UPLOAD_FOLDER')
        if upload_folder:
            self.UPLOAD_CONFIG.upload_folder = upload_folder
        
        max_size = os.getenv('MAX_FILE_SIZE_MB')
        if max_size:
            self.UPLOAD_CONFIG.max_file_size_mb = int(max_size)
        
        # Storage backend configuration
        storage_backend = os.getenv('STORAGE_BACKEND', 'local')
        self.UPLOAD_CONFIG.storage_backend = storage_backend
        
        if storage_backend == 's3':
            self.UPLOAD_CONFIG.s3_bucket = os.getenv('S3_BUCKET')
            self.UPLOAD_CONFIG.s3_region = os.getenv('S3_REGION', 'us-east-1')
            self.UPLOAD_CONFIG.cloudfront_url = os.getenv('CLOUDFRONT_URL')
            
            if not self.UPLOAD_CONFIG.s3_bucket and self.ENV == Environment.PRODUCTION:
                raise ValueError("S3_BUCKET is required when using S3 storage in production")
        
        # Async processing
        self.UPLOAD_CONFIG.async_processing = os.getenv('ASYNC_PROCESSING', 'true').lower() == 'true'
        
        # Flask-Uploads compatibility
        self.UPLOAD_FOLDER = self.UPLOAD_CONFIG.upload_folder
        self.ALLOWED_EXTENSIONS = self.UPLOAD_CONFIG.allowed_extensions
        self.MAX_CONTENT_LENGTH = self.UPLOAD_CONFIG.max_file_size_mb * 1024 * 1024
    
    def _load_security_config(self) -> None:
        """Load security configuration."""
        self.SECURITY_CONFIG = SecurityConfig()
        
        # Set secret keys
        self.SECURITY_CONFIG.secret_key = self.SECRET_KEY
        self.SECURITY_CONFIG.jwt_secret_key = self.JWT_SECRET_KEY
        self.SECURITY_CONFIG.api_key_salt = self.API_KEY_SALT
        
        # CORS configuration
        cors_origins = os.getenv('CORS_ALLOWED_ORIGINS')
        if cors_origins:
            self.SECURITY_CONFIG.cors_allowed_origins = cors_origins.split(',')
        elif self.ENV == Environment.PRODUCTION:
            # Production must specify allowed origins
            raise ValueError("CORS_ALLOWED_ORIGINS must be specified in production")
        else:
            # Development defaults
            self.SECURITY_CONFIG.cors_allowed_origins = ['http://localhost:3000', 'http://localhost:5000']
        
        # Security headers
        if self.ENV == Environment.PRODUCTION:
            self.SECURITY_CONFIG.session_cookie_secure = True
            self.SECURITY_CONFIG.csrf_cookie_secure = True
            self.SECURITY_CONFIG.hsts_enabled = True
        else:
            self.SECURITY_CONFIG.session_cookie_secure = False
            self.SECURITY_CONFIG.csrf_cookie_secure = False
            self.SECURITY_CONFIG.hsts_enabled = False
        
        # Rate limiting
        self.SECURITY_CONFIG.rate_limiting_enabled = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        
        # Flask configuration
        self.SESSION_COOKIE_SECURE = self.SECURITY_CONFIG.session_cookie_secure
        self.SESSION_COOKIE_HTTPONLY = self.SECURITY_CONFIG.session_cookie_httponly
        self.SESSION_COOKIE_SAMESITE = self.SECURITY_CONFIG.session_cookie_samesite
        self.SESSION_COOKIE_MAX_AGE = self.SECURITY_CONFIG.session_cookie_max_age
    
    def _load_logging_config(self) -> None:
        """Load logging configuration."""
        self.LOGGING_CONFIG = LoggingConfig()
        
        # Set log level based on environment
        if self.ENV == Environment.DEVELOPMENT:
            self.LOGGING_CONFIG.level = LogLevel.DEBUG
            self.LOGGING_CONFIG.json_format = False
            self.LOGGING_CONFIG.log_request_body = True
        elif self.ENV == Environment.PRODUCTION:
            self.LOGGING_CONFIG.level = LogLevel.INFO
            self.LOGGING_CONFIG.json_format = True
            self.LOGGING_CONFIG.log_request_body = False
            self.LOGGING_CONFIG.log_response_body = False
        
        # Override with environment variables
        log_level = os.getenv('LOG_LEVEL', self.LOGGING_CONFIG.level.value).upper()
        if log_level in LogLevel.__members__:
            self.LOGGING_CONFIG.level = LogLevel[log_level]
        
        sentry_dsn = os.getenv('SENTRY_DSN')
        if sentry_dsn:
            self.LOGGING_CONFIG.sentry_dsn = sentry_dsn
            self.LOGGING_CONFIG.sentry_environment = self.ENV.value
    
    def _load_feature_flags(self) -> None:
        """Load feature flags from environment."""
        self.FEATURE_FLAGS = FeatureFlags()
        
        # Override with environment variables
        for feature in dir(self.FEATURE_FLAGS):
            if not feature.startswith('_') and not callable(getattr(self.FEATURE_FLAGS, feature)):
                env_var = f"ENABLE_{feature.upper()}"
                if env_var in os.environ:
                    setattr(self.FEATURE_FLAGS, feature, os.getenv(env_var, 'false').lower() == 'true')
        
        # Environment-specific defaults
        if self.ENV == Environment.PRODUCTION:
            self.FEATURE_FLAGS.enable_caching = True
            self.FEATURE_FLAGS.enable_async_processing = True
        elif self.ENV == Environment.DEVELOPMENT:
            self.FEATURE_FLAGS.enable_beta_api = True
            self.FEATURE_FLAGS.enable_ai_match_scoring = True
    
    def _validate_configuration(self) -> None:
        """Validate critical configuration settings."""
        # Check database connection
        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("Database URL is not configured")
        
        # Check upload folder permissions
        upload_path = self.UPLOAD_CONFIG.get_upload_path()
        if not os.access(upload_path, os.W_OK):
            raise ValueError(f"Upload folder {upload_path} is not writable")
        
        # Check logs folder permissions (if file logging enabled)
        if self.LOGGING_CONFIG.file_enabled:
            log_path = Path(self.LOGGING_CONFIG.file_path).parent
            log_path.mkdir(parents=True, exist_ok=True)
            if not os.access(log_path, os.W_OK):
                raise ValueError(f"Log folder {log_path} is not writable")
    
    # Helper methods for common configuration access
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENV == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENV == Environment.DEVELOPMENT
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.ENV == Environment.TESTING
    
    def get_database_url(self, include_db_name: bool = True) -> str:
        """Get database URL, optionally without database name."""
        if include_db_name:
            return self.SQLALCHEMY_DATABASE_URI
        
        # Remove database name from URL (for creating databases)
        url = self.SQLALCHEMY_DATABASE_URI
        if '/' in url.rsplit('/', 1)[0]:
            return url.rsplit('/', 1)[0]
        return url
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature flag is enabled."""
        return self.FEATURE_FLAGS.is_enabled(feature)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (for debugging, excludes secrets)."""
        return {
            "environment": self.ENV.value,
            "database": {
                "url": self._mask_url(self.SQLALCHEMY_DATABASE_URI),
                "pool_size": self.DATABASE_CONFIG.pool_size,
                "ssl_mode": self.DATABASE_CONFIG.ssl_mode,
            },
            "upload": {
                "folder": self.UPLOAD_CONFIG.upload_folder,
                "max_size_mb": self.UPLOAD_CONFIG.max_file_size_mb,
                "allowed_extensions": list(self.UPLOAD_CONFIG.allowed_extensions),
                "storage_backend": self.UPLOAD_CONFIG.storage_backend,
            },
            "security": {
                "cors_origins": self.SECURITY_CONFIG.cors_allowed_origins,
                "rate_limiting_enabled": self.SECURITY_CONFIG.rate_limiting_enabled,
                "hsts_enabled": self.SECURITY_CONFIG.hsts_enabled,
            },
            "logging": {
                "level": self.LOGGING_CONFIG.level.value,
                "json_format": self.LOGGING_CONFIG.json_format,
                "sentry_enabled": bool(self.LOGGING_CONFIG.sentry_dsn),
            },
            "features": {
                k: v for k, v in self.FEATURE_FLAGS.__dict__.items() 
                if not k.startswith('_')
            },
        }
    
    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in URL."""
        if '@' in url:
            parts = url.split('@')
            credentials = parts[0].split('://')
            if len(credentials) > 1:
                return f"{credentials[0]}://***@{parts[1]}"
        return url


# Environment-specific configurations
class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    def __init__(self):
        super().__init__(env=Environment.DEVELOPMENT)


class TestingConfig(Config):
    """Testing environment configuration."""
    
    def __init__(self):
        super().__init__(env=Environment.TESTING)
        self.TESTING = True
        self.WTF_CSRF_ENABLED = False


class StagingConfig(Config):
    """Staging environment configuration."""
    
    def __init__(self):
        super().__init__(env=Environment.STAGING)


class ProductionConfig(Config):
    """Production environment configuration."""
    
    def __init__(self):
        super().__init__(env=Environment.PRODUCTION)


# Configuration factory
def get_config(env: Optional[str] = None) -> Config:
    """
    Factory function to get configuration based on environment.
    
    Args:
        env: Environment name ('development', 'testing', 'staging', 'production')
    
    Returns:
        Config instance for the specified environment
    """
    env_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'staging': StagingConfig,
        'production': ProductionConfig,
    }
    
    env_key = env or os.getenv('FLASK_ENV', 'development')
    config_class = env_map.get(env_key.lower(), DevelopmentConfig)
    
    return config_class()


# Example usage
if __name__ == "__main__":
    # Load configuration
    config = get_config()
    
    print(f"Environment: {config.ENV.value}")
    print(f"Database: {config.get_database_url()}")
    print(f"Upload folder: {config.UPLOAD_CONFIG.upload_folder}")
    print(f"Max file size: {config.UPLOAD_CONFIG.max_file_size_mb}MB")
    print(f"Rate limiting enabled: {config.SECURITY_CONFIG.rate_limiting_enabled}")
    print(f"Features: {config.FEATURE_FLAGS.__dict__}")
    
    # Check if feature is enabled
    if config.is_feature_enabled('enable_ocr'):
        print("OCR is enabled")
    
    # Export for Flask
    print("\nFlask config ready:")
    print(f"SECRET_KEY set: {bool(config.SECRET_KEY)}")
    print(f"SQLALCHEMY_DATABASE_URI: {config.SQLALCHEMY_DATABASE_URI}")
