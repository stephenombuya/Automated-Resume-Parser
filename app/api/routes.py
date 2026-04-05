"""
API routes for resume management.
"""

import os
from pathlib import Path
from datetime import datetime

from flask import request, jsonify, g, current_app
from werkzeug.utils import secure_filename

from app.api import api_bp
from app.api.auth import require_api_key, require_jwt_token, generate_jwt_token
from app.api.validators import (
    validate_parse_request,
    validate_pagination,
    validate_resume_id
)
from app.models import db, Resume, ResumeStatus, ExperienceLevel
from app.parser.pdf_parser import PDFParser, PDFParsingMode, PDFParserError
from app.parser.docx_parser import DOCXParser, DOCXParserError
from app.parser.nlp_processor import NLPProcessor, NLPProcessorError
from app.utils import (
    FileValidator,
    save_upload_file,
    allowed_file,
    PerformanceMonitor,
    timer,
    logger,
    ResumeParserError,
    FileTypeError,
    FileSizeError,
    ParsingError
)


# Initialize parsers (lazy loading)
_pdf_parser = None
_docx_parser = None
_nlp_processor = None
_file_validator = None


def get_pdf_parser():
    """Get or initialize PDF parser."""
    global _pdf_parser
    if _pdf_parser is None:
        _pdf_parser = PDFParser(
            mode=PDFParsingMode.HYBRID if current_app.config.is_feature_enabled('enable_ocr') else PDFParsingMode.FAST,
            preserve_layout=True,
            max_file_size_mb=current_app.config['UPLOAD_CONFIG'].max_file_size_mb,
            extract_metadata=True,
            fallback_to_ocr=current_app.config.is_feature_enabled('enable_ocr')
        )
    return _pdf_parser


def get_docx_parser():
    """Get or initialize DOCX parser."""
    global _docx_parser
    if _docx_parser is None:
        _docx_parser = DOCXParser(
            extract_tables=True,
            extract_headers=True,
            extract_footers=True,
            preserve_line_breaks=True,
            max_file_size_mb=current_app.config['UPLOAD_CONFIG'].max_file_size_mb
        )
    return _docx_parser


def get_nlp_processor():
    """Get or initialize NLP processor."""
    global _nlp_processor
    if _nlp_processor is None:
        _nlp_processor = NLPProcessor(
            model_name="en_core_web_sm",
            lazy_load=True,
            extract_multiple_persons=True,
            normalize_phone=True,
            skills_case_sensitive=False,
            use_fuzzy_matching=False
        )
    return _nlp_processor


def get_file_validator():
    """Get or initialize file validator."""
    global _file_validator
    if _file_validator is None:
        _file_validator = FileValidator(
            max_file_size_mb=current_app.config['UPLOAD_CONFIG'].max_file_size_mb,
            allowed_extensions=current_app.config['UPLOAD_CONFIG'].allowed_extensions,
            scan_for_viruses=False
        )
    return _file_validator


@api_bp.route('/auth/token', methods=['POST'])
def get_token():
    """
    Generate JWT token for authenticated user.
    
    Request body:
    {
        "api_key": "your_api_key"
    }
    """
    data = request.get_json()
    
    if not data or 'api_key' not in data:
        return jsonify({
            "error": "API key required",
            "code": 400
        }), 400
    
    api_key = data['api_key']
    
    # Validate API key
    if api_key not in API_KEYS:
        return jsonify({
            "error": "Invalid API key",
            "code": 401
        }), 401
    
    # Generate JWT token
    token = generate_jwt_token(
        user_id=hash(api_key),
        email=f"api_{api_key[:8]}@example.com",
        expires_in_hours=24
    )
    
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 86400  # 24 hours in seconds
    }), 200


@api_bp.route('/parse', methods=['POST'])
@require_api_key
def parse_resume():
    """
    Parse a resume file and extract candidate information.
    
    Expected: multipart/form-data with 'file' field containing the resume.
    
    Optional parameters:
    - extract_tables: boolean (default: true)
    - extract_skills: boolean (default: true)
    - return_raw_text: boolean (default: false)
    
    Returns:
        JSON with extracted candidate information
    """
    with PerformanceMonitor("parse_resume_endpoint"):
        # Validate request
        file = request.files.get('file')
        is_valid, error_response = validate_parse_request(file)
        
        if not is_valid:
            return jsonify(error_response), 400
        
        # Get optional parameters
        extract_tables = request.form.get('extract_tables', 'true').lower() == 'true'
        extract_skills = request.form.get('extract_skills', 'true').lower() == 'true'
        return_raw_text = request.form.get('return_raw_text', 'false').lower() == 'true'
        
        temp_filepath = None
        
        try:
            # Validate file type
            if not allowed_file(file.filename, current_app.config['UPLOAD_CONFIG'].allowed_extensions):
                return jsonify({
                    "error": "Invalid file type",
                    "allowed_extensions": list(current_app.config['UPLOAD_CONFIG'].allowed_extensions),
                    "code": 400
                }), 400
            
            # Save and validate file
            save_result = save_upload_file(
                file,
                current_app.config['UPLOAD_CONFIG'].upload_folder,
                secure=True,
                generate_unique_name=True
            )
            
            temp_filepath = save_result['filepath']
            
            # Validate file (size, MIME type, corruption)
            validator = get_file_validator()
            validation = validator.validate_file(temp_filepath)
            
            if not validation['valid']:
                return jsonify({
                    "error": "File validation failed",
                    "details": validation['errors'],
                    "code": 400
                }), 400
            
            # Parse based on file extension
            extension = Path(temp_filepath).suffix.lower().lstrip('.')
            
            with timer(f"parse_{extension}_file"):
                if extension == 'pdf':
                    parser = get_pdf_parser()
                    parse_result = parser.parse(temp_filepath)
                    text = parse_result.text
                    metadata = parse_result.metadata
                    tables = parse_result.tables if extract_tables else []
                elif extension == 'docx':
                    parser = get_docx_parser()
                    parse_result = parser.parse(temp_filepath)
                    text = parse_result.text
                    metadata = parse_result.metadata
                    tables = parse_result.tables if extract_tables else []
                else:
                    # Fallback for text files
                    with open(temp_filepath, 'r', encoding='utf-8') as f:
                        text = f.read()
                    metadata = {"file_type": "text"}
                    tables = []
            
            # Extract information using NLP
            with timer("nlp_extraction"):
                nlp = get_nlp_processor()
                extraction = nlp.extract_all(text) if extract_skills else None
            
            # Calculate experience level
            experience_level = None
            if extraction and extraction.skills:
                senior_skills = {'leadership', 'management', 'architecture', 'strategy', 'senior'}
                junior_skills = {'intern', 'assistant', 'trainee', 'junior', 'entry'}
                
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
                candidate_name=extraction.first_person if extraction else None,
                email=extraction.first_email if extraction else None,
                phone=extraction.first_phone if extraction else None,
                skills=extraction.skills if extraction else [],
                experience=[],
                education=[],
                status=ResumeStatus.COMPLETED,
                experience_level=experience_level,
                processing_started_at=datetime.utcnow(),
                processing_completed_at=datetime.utcnow()
            )
            
            # Add scores if available
            if extraction and extraction.confidence_scores:
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
                "name": extraction.first_person if extraction else None,
                "email": extraction.first_email if extraction else None,
                "phone": extraction.first_phone if extraction else None,
                "skills": extraction.skills if extraction else [],
                "experience_level": experience_level.value if experience_level else None,
                "confidence_scores": extraction.confidence_scores if extraction else {},
                "metadata": {
                    "filename": save_result['filename'],
                    "file_size_mb": save_result['size_mb'],
                    "pages": parse_result.total_pages if extension == 'pdf' else 1,
                    "processing_time_ms": extraction.processing_time_ms if extraction else 0
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Include raw text if requested
            if return_raw_text:
                response_data["raw_text"] = text[:5000]  # Limit text length
            
            # Include tables if extracted
            if extract_tables and tables:
                response_data["tables"] = tables[:10]  # Limit number of tables
            
            current_app.logger.info(
                f"Successfully parsed resume {resume.uuid}: "
                f"{extraction.first_person if extraction else 'Unknown'}"
            )
            
            return jsonify(response_data), 200
            
        except (FileTypeError, FileSizeError) as e:
            db.session.rollback()
            current_app.logger.warning(f"File validation error: {e}")
            return jsonify({
                "error": str(e),
                "code": 400,
                "timestamp": datetime.utcnow().isoformat()
            }), 400
            
        except (PDFParserError, DOCXParserError, ParsingError) as e:
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


@api_bp.route('/resume/<resume_id>', methods=['GET'])
@require_api_key
def get_resume(resume_id: str):
    """
    Retrieve parsed resume by ID.
    
    Args:
        resume_id: Resume UUID (public ID)
    
    Query parameters:
    - include_sensitive: boolean (default: false)
    """
    # Validate resume ID
    is_valid, error_response = validate_resume_id(resume_id)
    if not is_valid:
        return jsonify(error_response), 400
    
    try:
        resume = Resume.query.filter_by(uuid=resume_id, deleted_at=None).first()
        
        if not resume:
            return jsonify({
                "error": "Resume not found",
                "code": 404,
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        # Check if we should include sensitive info
        include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
        
        # Require admin or owner for sensitive data
        if include_sensitive:
            # Check if user has admin permission
            has_admin = g.api_key_info.get('permissions', []).count('admin') > 0
            if not has_admin:
                return jsonify({
                    "error": "Insufficient permissions",
                    "message": "Admin access required for sensitive data",
                    "code": 403
                }), 403
        
        return jsonify(resume.to_dict(include_sensitive=include_sensitive)), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve resume {resume_id}: {e}")
        return jsonify({
            "error": "Failed to retrieve resume",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@api_bp.route('/resumes', methods=['GET'])
@require_api_key
def list_resumes():
    """
    List resumes with pagination and filtering.
    
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - status: Filter by status
    - experience_level: Filter by experience level
    - search: Search query for full-text search
    - sort_by: created_at, match_score (default: created_at)
    - sort_order: asc, desc (default: desc)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        experience_level = request.args.get('experience_level')
        search_query = request.args.get('search')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Validate pagination
        is_valid, error_response = validate_pagination(page, per_page)
        if not is_valid:
            return jsonify(error_response), 400
        
        query = Resume.query.filter_by(deleted_at=None)
        
        # Apply filters
        if status:
            try:
                query = query.filter_by(status=ResumeStatus(status))
            except ValueError:
                return jsonify({
                    "error": f"Invalid status: {status}",
                    "valid_statuses": [s.value for s in ResumeStatus],
                    "code": 400
                }), 400
        
        if experience_level:
            try:
                query = query.filter_by(experience_level=ExperienceLevel(experience_level))
            except ValueError:
                return jsonify({
                    "error": f"Invalid experience level: {experience_level}",
                    "valid_levels": [l.value for l in ExperienceLevel],
                    "code": 400
                }), 400
        
        # Apply search
        if search_query:
            resumes = Resume.search(search_query, limit=per_page, offset=(page-1)*per_page)
            total = Resume.query.filter_by(deleted_at=None).count()
        else:
            # Apply sorting
            if sort_by == 'created_at':
                if sort_order == 'asc':
                    query = query.order_by(Resume.created_at.asc())
                else:
                    query = query.order_by(Resume.created_at.desc())
            elif sort_by == 'match_score':
                if sort_order == 'asc':
                    query = query.order_by(Resume.match_score.asc())
                else:
                    query = query.order_by(Resume.match_score.desc())
            else:
                return jsonify({
                    "error": f"Invalid sort_by: {sort_by}",
                    "valid_sort_fields": ["created_at", "match_score"],
                    "code": 400
                }), 400
            
            # Paginate
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)
            resumes = paginated.items
            total = paginated.total
        
        return jsonify({
            "resumes": [r.to_dict(include_sensitive=False) for r in resumes],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
                "has_next": page * per_page < total,
                "has_prev": page > 1
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


@api_bp.route('/resume/<resume_id>', methods=['DELETE'])
@require_api_key
def delete_resume(resume_id: str):
    """
    Soft delete a resume.
    
    Args:
        resume_id: Resume UUID
    """
    # Validate resume ID
    is_valid, error_response = validate_resume_id(resume_id)
    if not is_valid:
        return jsonify(error_response), 400
    
    # Check permissions
    if 'write' not in g.api_key_info.get('permissions', []):
        return jsonify({
            "error": "Insufficient permissions",
            "message": "Write access required",
            "code": 403
        }), 403
    
    try:
        resume = Resume.query.filter_by(uuid=resume_id, deleted_at=None).first()
        
        if not resume:
            return jsonify({
                "error": "Resume not found",
                "code": 404,
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
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


@api_bp.route('/stats', methods=['GET'])
@require_api_key
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


@api_bp.route('/health', methods=['GET'])
def api_health():
    """API health check endpoint (no auth required)."""
    return jsonify({
        "status": "healthy",
        "service": "Resume Parser API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200
