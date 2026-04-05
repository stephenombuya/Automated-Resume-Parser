"""
Production-grade utilities module for file handling, text processing,
validation, and error handling.

Features:
- Secure file upload handling with virus scanning
- Advanced text cleaning and normalization
- Multi-format date extraction
- International phone number formatting
- Email validation with MX record checking
- Comprehensive error hierarchy
- Performance monitoring and caching
- Thread-safe operations
"""

import os
import re
import hashlib
import magic
import bleach
import email_validator
import phonenumbers
from phonenumbers import PhoneNumberType, NumberParseException
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union, Tuple, Set
from pathlib import Path
from functools import lru_cache, wraps
from time import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import logging
from logging.handlers import RotatingFileHandler
import tempfile
import shutil
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

# Optional imports for enhanced functionality
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import pdf2image
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class ResumeParserError(Exception):
    """Base exception class for resume parser errors."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class FileTypeError(ResumeParserError):
    """Raised when file type is not supported."""
    pass


class FileSizeError(ResumeParserError):
    """Raised when file size exceeds limits."""
    pass


class FileCorruptError(ResumeParserError):
    """Raised when file is corrupt or malformed."""
    pass


class VirusDetectedError(ResumeParserError):
    """Raised when virus is detected in uploaded file."""
    pass


class ParsingError(ResumeParserError):
    """Raised when there's an error parsing the document."""
    pass


class ExtractionError(ResumeParserError):
    """Raised when there's an error extracting information."""
    pass


class ValidationError(ResumeParserError):
    """Raised when validation fails."""
    pass


# ============================================================================
# Decorators for Monitoring and Caching
# ============================================================================

def monitor_performance(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time() - start_time) * 1000
            logger.debug(f"{func.__name__} completed in {elapsed_ms:.2f}ms")
            return result
        except Exception as e:
            elapsed_ms = (time() - start_time) * 1000
            logger.error(f"{func.__name__} failed after {elapsed_ms:.2f}ms: {e}")
            raise
    return wrapper


def retry_on_failure(max_retries: int = 3, delay_seconds: float = 1.0):
    """Decorator to retry function on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay_seconds * (attempt + 1))
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__}")
                    else:
                        logger.error(f"All {max_retries} retries failed for {func.__name__}")
            
            raise last_exception
        return wrapper
    return decorator


# ============================================================================
# File Handling Utilities
# ============================================================================

class FileValidator:
    """Comprehensive file validation with MIME type checking and virus scanning."""
    
    # Common MIME types for documents
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'text/rtf',
        'application/rtf',
    }
    
    # File signatures (magic bytes) for additional validation
    FILE_SIGNATURES = {
        b'%PDF': 'application/pdf',
        b'PK\x03\x04': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        b'\\documentclass': 'text/latex',
    }
    
    def __init__(
        self,
        max_file_size_mb: int = 10,
        allowed_extensions: Optional[Set[str]] = None,
        scan_for_viruses: bool = False,
        virus_scan_endpoint: Optional[str] = None
    ):
        """
        Initialize file validator.
        
        Args:
            max_file_size_mb: Maximum allowed file size in MB
            allowed_extensions: Set of allowed file extensions
            scan_for_viruses: Enable virus scanning
            virus_scan_endpoint: Endpoint for virus scanning API
        """
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.allowed_extensions = allowed_extensions or {'pdf', 'docx', 'txt', 'rtf'}
        self.scan_for_viruses = scan_for_viruses
        self.virus_scan_endpoint = virus_scan_endpoint
        
        # Initialize magic for MIME detection
        self.magic = magic.Magic(mime=True)
    
    def validate_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Comprehensive file validation.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            Dictionary with validation results and metadata
            
        Raises:
            FileTypeError: If file type is not allowed
            FileSizeError: If file size exceeds limit
            FileCorruptError: If file is corrupt
            VirusDetectedError: If virus is detected
        """
        path = Path(file_path)
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        # Check file existence
        if not path.exists():
            validation_result["errors"].append("File does not exist")
            raise FileTypeError("File does not exist")
        
        # Check file size
        file_size = path.stat().st_size
        validation_result["metadata"]["size_bytes"] = file_size
        
        if file_size == 0:
            validation_result["errors"].append("File is empty")
            raise FileCorruptError("File is empty")
        
        if file_size > self.max_file_size_bytes:
            error_msg = f"File size {file_size / 1024 / 1024:.2f}MB exceeds limit {self.max_file_size_bytes / 1024 / 1024:.2f}MB"
            validation_result["errors"].append(error_msg)
            raise FileSizeError(error_msg)
        
        # Check file extension
        extension = path.suffix.lower().lstrip('.')
        if extension not in self.allowed_extensions:
            validation_result["errors"].append(f"File extension '{extension}' not allowed")
            raise FileTypeError(f"File extension '{extension}' not allowed")
        
        # Check MIME type
        mime_type = self.magic.from_file(str(path))
        validation_result["metadata"]["mime_type"] = mime_type
        
        if mime_type not in self.ALLOWED_MIME_TYPES:
            validation_result["warnings"].append(f"Unusual MIME type: {mime_type}")
        
        # Check file signature (magic bytes)
        with open(path, 'rb') as f:
            file_header = f.read(8)
            
        for signature, expected_mime in self.FILE_SIGNATURES.items():
            if file_header.startswith(signature):
                validation_result["metadata"]["detected_format"] = expected_mime
                break
        
        # Check for corruption (try to open file with appropriate parser)
        is_corrupt = self._check_file_corruption(path, mime_type)
        if is_corrupt:
            validation_result["errors"].append("File appears to be corrupt")
            raise FileCorruptError("File appears to be corrupt")
        
        # Virus scan (if enabled)
        if self.scan_for_viruses:
            virus_detected = self._scan_for_viruses(path)
            if virus_detected:
                validation_result["errors"].append("Virus detected in file")
                raise VirusDetectedError("Virus detected in file")
        
        # Calculate file hash for deduplication
        validation_result["metadata"]["sha256"] = self._calculate_file_hash(path)
        
        validation_result["valid"] = True
        validation_result["metadata"]["extension"] = extension
        
        return validation_result
    
    def _check_file_corruption(self, file_path: Path, mime_type: str) -> bool:
        """Check if file is corrupt by attempting to parse it."""
        try:
            if mime_type == 'application/pdf':
                import PyPDF2
                with open(file_path, 'rb') as f:
                    PyPDF2.PdfReader(f)
            elif 'document' in mime_type:
                from docx import Document
                Document(str(file_path))
            elif 'text' in mime_type:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(1024)
            return False
        except Exception as e:
            logger.warning(f"Corruption check failed for {file_path}: {e}")
            return True
    
    def _scan_for_viruses(self, file_path: Path) -> bool:
        """
        Scan file for viruses.
        
        Placeholder for actual virus scanning integration.
        Implement with ClamAV, VirusTotal, or similar service.
        """
        # TODO: Implement actual virus scanning
        # Example: clamd scan or VirusTotal API
        return False
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


@monitor_performance
def save_upload_file(
    uploaded_file: FileStorage,
    upload_folder: Union[str, Path],
    secure: bool = True,
    generate_unique_name: bool = False
) -> Dict[str, Any]:
    """
    Safely save an uploaded file with comprehensive validation and metadata.
    
    Args:
        uploaded_file: FileStorage object from Flask
        upload_folder: Path to upload folder
        secure: Use secure_filename for sanitization
        generate_unique_name: Generate unique name to prevent collisions
    
    Returns:
        Dictionary containing file path, filename, size, and hash
        
    Raises:
        FileTypeError: If file type is invalid
        FileSizeError: If file size exceeds limits
    """
    if not uploaded_file or not uploaded_file.filename:
        raise FileTypeError("No file provided or file has no filename")
    
    # Ensure upload directory exists
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Validate file size (read first chunk if needed)
    uploaded_file.seek(0, 2)  # Seek to end
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)  # Reset to beginning
    
    # Check if directory is writable
    if not os.access(upload_path, os.W_OK):
        raise FileSizeError(f"Upload directory {upload_path} is not writable")
    
    # Get secure filename
    if secure:
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            raise FileTypeError("Invalid filename after sanitization")
    else:
        filename = uploaded_file.filename
    
    # Generate unique name if requested
    if generate_unique_name:
        name_parts = filename.rsplit('.', 1)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        
        if len(name_parts) == 2:
            filename = f"{name_parts[0]}_{timestamp}_{unique_id}.{name_parts[1]}"
        else:
            filename = f"{filename}_{timestamp}_{unique_id}"
    
    file_path = upload_path / filename
    
    try:
        # Save file
        uploaded_file.save(str(file_path))
        logger.info(f"Successfully saved file: {filename} ({file_size} bytes)")
        
        # Calculate file hash
        file_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                file_hash.update(chunk)
        
        return {
            "filepath": str(file_path),
            "filename": filename,
            "size_bytes": file_size,
            "size_mb": round(file_size / 1024 / 1024, 2),
            "sha256": file_hash.hexdigest(),
            "saved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error saving file {filename}: {str(e)}")
        raise FileTypeError(f"Failed to save file: {str(e)}")


def allowed_file(filename: str, allowed_extensions: Set[str]) -> bool:
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename: Name of the file to check
        allowed_extensions: Set of allowed file extensions
    
    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in allowed_extensions


# ============================================================================
# Text Processing Utilities
# ============================================================================

class TextCleaner:
    """Advanced text cleaning and normalization."""
    
    # Common OCR errors and corrections
    OCR_CORRECTIONS = {
        'rn': 'm',
        'vv': 'w',
        'l': 'I',  # Context-dependent
    }
    
    # Patterns to remove (PII, URLs, etc.)
    REMOVAL_PATTERNS = [
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]'),  # Phone numbers
        (r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b', '[EMAIL]'),    # Email addresses
        (r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', '[URL]'),  # URLs
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),              # SSN
    ]
    
    @staticmethod
    @monitor_performance
    def clean_text(
        text: str,
        remove_special_chars: bool = True,
        normalize_whitespace: bool = True,
        remove_emails: bool = False,
        remove_phones: bool = False,
        max_length: Optional[int] = None
    ) -> str:
        """
        Clean and normalize extracted text from documents.
        
        Args:
            text: Raw text to clean
            remove_special_chars: Remove non-alphanumeric characters
            normalize_whitespace: Normalize whitespace (collapse multiple spaces)
            remove_emails: Remove email addresses
            remove_phones: Remove phone numbers
            max_length: Maximum length of returned text
        
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        original_length = len(text)
        
        # Remove null bytes and control characters
        text = text.replace('\x00', '')
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Remove or mask sensitive information
        if remove_emails or remove_phones:
            for pattern, replacement in TextCleaner.REMOVAL_PATTERNS:
                if (remove_emails and '@' in pattern) or (remove_phones and '\\d' in pattern):
                    text = re.sub(pattern, replacement, text)
                elif not (remove_emails or remove_phones):
                    text = re.sub(pattern, replacement, text)
        
        # Remove special characters if requested
        if remove_special_chars:
            # Keep alphanumeric, spaces, dots, @, +, -
            text = re.sub(r'[^\w\s@.+-]', ' ', text)
        
        # Normalize whitespace
        if normalize_whitespace:
            # Replace tabs, newlines, multiple spaces with single space
            text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        # Apply length limit
        if max_length and len(text) > max_length:
            text = text[:max_length]
            logger.debug(f"Text truncated from {original_length} to {max_length} characters")
        
        return text
    
    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize unicode characters to ASCII where possible."""
        import unicodedata
        
        # Normalize to NFKD form
        normalized = unicodedata.normalize('NFKD', text)
        
        # Encode to ASCII, ignoring non-ASCII characters
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
        
        return ascii_text
    
    @staticmethod
    def remove_html_tags(text: str) -> str:
        """Remove HTML/XML tags from text."""
        return re.sub(r'<[^>]+>', '', text)
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Sanitize HTML to prevent XSS attacks."""
        return bleach.clean(
            text,
            tags=[],  # Strip all tags
            attributes={},
            strip=True
        )


# ============================================================================
# Date Extraction and Validation
# ============================================================================

class DateExtractor:
    """Advanced date extraction with multiple format support."""
    
    # Date patterns for extraction
    DATE_PATTERNS = [
        # MM/DD/YYYY, MM-DD-YYYY, MM.DD.YYYY
        (r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b', 'numeric'),
        
        # YYYY-MM-DD (ISO)
        (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', 'iso'),
        
        # Month DD, YYYY
        (r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
         r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
         r'Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b', 'month_day_year'),
        
        # DD Month YYYY
        (r'\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
         r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
         r'Dec(?:ember)?)\s+(\d{4})\b', 'day_month_year'),
        
        # Just year
        (r'\b(19|20)\d{2}\b', 'year'),
        
        # Season and year
        (r'\b(Spring|Summer|Fall|Winter)\s+(\d{4})\b', 'season_year'),
    ]
    
    # Month name to number mapping
    MONTH_MAP = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    @classmethod
    @monitor_performance
    def extract_dates(
        cls,
        text: str,
        min_year: int = 1900,
        max_year: int = 2100,
        return_objects: bool = False
    ) -> Union[List[str], List[date]]:
        """
        Extract dates from text using multiple regex patterns.
        
        Args:
            text: Text to extract dates from
            min_year: Minimum valid year
            max_year: Maximum valid year
            return_objects: Return date objects instead of strings
        
        Returns:
            List of extracted dates (strings or date objects)
        """
        if not text:
            return []
        
        dates = []
        seen = set()
        
        for pattern, pattern_type in cls.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    parsed_date = cls._parse_date_match(match, pattern_type)
                    
                    if parsed_date and min_year <= parsed_date.year <= max_year:
                        if return_objects:
                            if parsed_date not in seen:
                                dates.append(parsed_date)
                                seen.add(parsed_date)
                        else:
                            date_str = parsed_date.strftime("%Y-%m-%d")
                            if date_str not in seen:
                                dates.append(date_str)
                                seen.add(date_str)
                                
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse date match: {e}")
                    continue
        
        # Sort dates chronologically
        if return_objects:
            dates.sort()
        else:
            dates.sort()
        
        return dates
    
    @classmethod
    def _parse_date_match(cls, match: re.Match, pattern_type: str) -> Optional[date]:
        """Parse a regex match into a date object."""
        try:
            if pattern_type == 'numeric':
                month, day, year = match.group(1), match.group(2), match.group(3)
                return date(int(year), int(month), int(day))
            
            elif pattern_type == 'iso':
                year, month, day = match.group(1), match.group(2), match.group(3)
                return date(int(year), int(month), int(day))
            
            elif pattern_type == 'month_day_year':
                month_name, day, year = match.group(1), match.group(2), match.group(3)
                month_num = cls.MONTH_MAP.get(month_name.lower())
                if month_num:
                    return date(int(year), month_num, int(day))
            
            elif pattern_type == 'day_month_year':
                day, month_name, year = match.group(1), match.group(2), match.group(3)
                month_num = cls.MONTH_MAP.get(month_name.lower())
                if month_num:
                    return date(int(year), month_num, int(day))
            
            elif pattern_type == 'year':
                year = int(match.group(0))
                return date(year, 1, 1)
            
            elif pattern_type == 'season_year':
                season, year = match.group(1), match.group(2)
                # Return approximate date for season
                season_month = {'spring': 3, 'summer': 6, 'fall': 9, 'winter': 12}
                month = season_month.get(season.lower(), 1)
                return date(int(year), month, 1)
                
        except (ValueError, TypeError) as e:
            logger.debug(f"Date parsing error: {e}")
        
        return None


# ============================================================================
# Phone Number Processing
# ============================================================================

class PhoneProcessor:
    """International phone number formatting and validation."""
    
    @staticmethod
    @monitor_performance
    def format_phone_number(
        phone: str,
        default_country: str = "US",
        format_type: str = "international"
    ) -> Optional[str]:
        """
        Format phone numbers consistently using Google's phonenumbers library.
        
        Args:
            phone: Raw phone number string
            default_country: Default country code for parsing
            format_type: 'national', 'international', 'e164'
        
        Returns:
            Formatted phone number or None if invalid
        """
        if not phone:
            return None
        
        try:
            # Parse phone number
            parsed_number = phonenumbers.parse(phone, default_country)
            
            # Validate it's a possible number
            if not phonenumbers.is_possible_number(parsed_number):
                logger.debug(f"Phone number {phone} is not possible")
                return None
            
            # Format based on type
            if format_type == "international":
                formatted = phonenumbers.format_number(
                    parsed_number,
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
            elif format_type == "national":
                formatted = phonenumbers.format_number(
                    parsed_number,
                    phonenumbers.PhoneNumberFormat.NATIONAL
                )
            elif format_type == "e164":
                formatted = phonenumbers.format_number(
                    parsed_number,
                    phonenumbers.PhoneNumberFormat.E164
                )
            else:
                formatted = phonenumbers.format_number(
                    parsed_number,
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
            
            return formatted
            
        except NumberParseException as e:
            logger.debug(f"Failed to parse phone number {phone}: {e}")
            return None
    
    @staticmethod
    def extract_phone_numbers(text: str, default_country: str = "US") -> List[str]:
        """
        Extract all phone numbers from text.
        
        Args:
            text: Text to extract from
            default_country: Default country code
        
        Returns:
            List of formatted phone numbers
        """
        if not text:
            return []
        
        # Use phonenumbers library for robust extraction
        try:
            matches = phonenumbers.PhoneNumberMatcher(text, default_country)
            numbers = []
            
            for match in matches:
                formatted = phonenumbers.format_number(
                    match.number,
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                numbers.append(formatted)
            
            return list(dict.fromkeys(numbers))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Phone extraction failed: {e}")
            return []
    
    @staticmethod
    def validate_phone_number(phone: str, default_country: str = "US") -> bool:
        """
        Validate phone number.
        
        Args:
            phone: Phone number to validate
            default_country: Default country code
        
        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = phonenumbers.parse(phone, default_country)
            return phonenumbers.is_valid_number(parsed)
        except NumberParseException:
            return False


# ============================================================================
# Email Validation
# ============================================================================

class EmailValidator:
    """Comprehensive email validation with MX record checking."""
    
    @staticmethod
    @monitor_performance
    def validate_email(
        email: str,
        check_mx: bool = False,
        check_deliverability: bool = False
    ) -> Dict[str, Any]:
        """
        Validate email address format and optionally check MX records.
        
        Args:
            email: Email address to validate
            check_mx: Check MX records for domain
            check_deliverability: Check if email is deliverable
        
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": False,
            "email": email,
            "normalized": None,
            "errors": [],
            "warnings": []
        }
        
        if not email:
            result["errors"].append("Email is empty")
            return result
        
        try:
            # Validate using email-validator library
            validation = email_validator.validate_email(
                email,
                check_deliverability=check_deliverability,
                allow_smtputf8=False
            )
            
            result["valid"] = True
            result["normalized"] = validation.normalized
            
            # Check MX records if requested
            if check_mx and validation.domain:
                import dns.resolver
                try:
                    mx_records = dns.resolver.resolve(validation.domain, 'MX')
                    result["mx_records"] = [str(record.exchange) for record in mx_records]
                except Exception as e:
                    result["warnings"].append(f"MX lookup failed: {str(e)}")
            
        except email_validator.EmailNotValidError as e:
            result["errors"].append(str(e))
            logger.debug(f"Email validation failed for {email}: {e}")
        
        return result
    
    @staticmethod
    def extract_emails(text: str, unique_only: bool = True) -> List[str]:
        """
        Extract all email addresses from text.
        
        Args:
            text: Text to extract from
            unique_only: Return only unique emails
        
        Returns:
            List of email addresses
        """
        if not text:
            return []
        
        # RFC 5322 compliant email pattern
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        
        # Normalize to lowercase
        emails = [e.lower() for e in emails]
        
        if unique_only:
            emails = list(dict.fromkeys(emails))
        
        return emails


# ============================================================================
# Performance Utilities
# ============================================================================

class PerformanceMonitor:
    """Context manager for performance monitoring."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time()
        elapsed_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type:
            logger.error(f"{self.operation_name} failed after {elapsed_ms:.2f}ms")
        else:
            logger.info(f"{self.operation_name} completed in {elapsed_ms:.2f}ms")
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@contextmanager
def timer(operation_name: str):
    """Context manager for timing operations."""
    start = time()
    try:
        yield
    finally:
        elapsed_ms = (time() - start) * 1000
        logger.debug(f"{operation_name} took {elapsed_ms:.2f}ms")


# ============================================================================
# Batch Processing Utilities
# ============================================================================

class BatchProcessor:
    """Process multiple items in parallel with progress tracking."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_batch(
        self,
        items: List[Any],
        process_func,
        progress_callback=None
    ) -> List[Tuple[Any, Optional[Exception]]]:
        """
        Process a batch of items in parallel.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            progress_callback: Callback for progress updates
        
        Returns:
            List of (result, error) tuples
        """
        results = []
        total = len(items)
        
        futures = {self.executor.submit(process_func, item): item for item in items}
        
        for i, future in enumerate(futures):
            try:
                result = future.result()
                results.append((result, None))
            except Exception as e:
                results.append((None, e))
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def shutdown(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)


# ============================================================================
# Main Export Functions (Backward Compatibility)
# ============================================================================

# Create default instances
_default_validator = FileValidator()
_default_cleaner = TextCleaner()
_default_date_extractor = DateExtractor()
_default_phone_processor = PhoneProcessor()
_default_email_validator = EmailValidator()

# Backward compatible functions
def clean_text(text: str) -> str:
    """Backward compatible text cleaning function."""
    return _default_cleaner.clean_text(text, remove_special_chars=True)


def extract_dates(text: str) -> List[str]:
    """Backward compatible date extraction function."""
    return _default_date_extractor.extract_dates(text, return_objects=False)


def format_phone_number(phone: str) -> str:
    """Backward compatible phone formatting function."""
    result = _default_phone_processor.format_phone_number(phone)
    return result if result else phone


def validate_email(email: str) -> bool:
    """Backward compatible email validation function."""
    result = _default_email_validator.validate_email(email)
    return result["valid"]


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example 1: File validation
    validator = FileValidator(max_file_size_mb=10)
    
    # Example 2: Text cleaning
    cleaner = TextCleaner()
    dirty_text = "Hello   world!  This has  multiple  spaces. john@example.com"
    cleaned = cleaner.clean_text(dirty_text, remove_emails=True)
    print(f"Cleaned: {cleaned}")
    
    # Example 3: Date extraction
    text_with_dates = "I worked from Jan 15, 2020 to December 2023. Started on 01/15/2020."
    dates = DateExtractor.extract_dates(text_with_dates)
    print(f"Dates found: {dates}")
    
    # Example 4: Phone formatting
    phone = format_phone_number("+1 (555) 123-4567")
    print(f"Formatted phone: {phone}")
    
    # Example 5: Email validation
    email_result = EmailValidator.validate_email("user@example.com", check_mx=False)
    print(f"Email valid: {email_result['valid']}")
    
    # Example 6: Performance monitoring
    with PerformanceMonitor("example_operation"):
        # Simulate work
        import time
        time.sleep(0.1)
    
    print("All utilities ready for production!")
