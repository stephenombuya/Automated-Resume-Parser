import os
import re
from werkzeug.utils import secure_filename
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
        allowed_extensions (set): Set of allowed file extensions
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_upload_file(uploaded_file, upload_folder: str) -> Optional[str]:
    """
    Safely save an uploaded file to the specified folder.
    
    Args:
        uploaded_file: FileStorage object from Flask
        upload_folder (str): Path to upload folder
    
    Returns:
        str: Path to saved file or None if save failed
    """
    try:
        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join(upload_folder, filename)
        uploaded_file.save(filepath)
        logger.info(f"Successfully saved file: {filename}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return None

def clean_text(text: str) -> str:
    """
    Clean and normalize extracted text from documents.
    
    Args:
        text (str): Raw text to clean
    
    Returns:
        str: Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s@.+-]', ' ', text)
    return text.strip()

def extract_dates(text: str) -> List[str]:
    """
    Extract dates from text using regex.
    
    Args:
        text (str): Text to extract dates from
    
    Returns:
        List[str]: List of extracted dates
    """
    # Match common date formats (MM/DD/YYYY, MM-DD-YYYY, Month YYYY)
    date_patterns = [
        r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
        r'Dec(?:ember)?)\s+\d{4}'
    ]
    
    dates = []
    for pattern in date_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        dates.extend([match.group() for match in matches])
    
    return dates

def format_phone_number(phone: str) -> str:
    """
    Format phone numbers consistently.
    
    Args:
        phone (str): Raw phone number string
    
    Returns:
        str: Formatted phone number
    """
    # Remove all non-numeric characters
    digits = re.sub(r'\D', '', phone)
    
    # Format based on length
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone

def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email (str): Email address to validate
    
    Returns:
        bool: True if email is valid, False otherwise
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

# Error handling utilities
class ResumeParserError(Exception):
    """Base exception class for resume parser errors"""
    pass

class FileTypeError(ResumeParserError):
    """Raised when file type is not supported"""
    pass

class ParsingError(ResumeParserError):
    """Raised when there's an error parsing the document"""
    pass

class ExtractionError(ResumeParserError):
    """Raised when there's an error extracting information"""
    pass
