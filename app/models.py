"""
Production-grade database models for resume management system.
Features: validation, indexing, soft deletes, audit trails, JSON schema validation,
composite indexes, and query optimization.
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Index, 
    UniqueConstraint, 
    CheckConstraint, 
    event,
    func,
    text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import validates, reconstructor
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize database
db = SQLAlchemy()


class ResumeStatus(str, Enum):
    """Resume processing status states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ExperienceLevel(str, Enum):
    """Candidate experience level classification."""
    ENTRY = "entry"          # 0-2 years
    JUNIOR = "junior"        # 2-4 years
    MID = "mid"              # 4-7 years
    SENIOR = "senior"        # 7-10 years
    LEAD = "lead"            # 10+ years
    EXECUTIVE = "executive"  # 15+ years


class EducationLevel(str, Enum):
    """Education level classification."""
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"
    CERTIFICATION = "certification"
    OTHER = "other"


class Resume(db.Model):
    """
    Resume model with comprehensive validation, indexing, and audit trails.
    
    Features:
    - Automatic timestamps (created, updated, deleted)
    - Soft delete support
    - Full-text search indexing
    - JSON schema validation
    - Composite indexes for common queries
    - Event hooks for data integrity
    """
    
    __tablename__ = "resumes"
    
    # Primary identifiers
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(
        UUID(as_uuid=True),
        default=uuid4,
        unique=True,
        nullable=False,
        index=True,
        doc="Public-facing unique identifier"
    )
    
    # File information
    filename = db.Column(db.String(512), nullable=False, index=True)
    file_size = db.Column(db.Integer, nullable=True)  # Size in bytes
    file_hash = db.Column(db.String(64), nullable=True, index=True)  # SHA-256 for deduplication
    storage_path = db.Column(db.String(1024), nullable=True)  # Cloud storage path
    original_filename = db.Column(db.String(512), nullable=True)  # Preserve original name
    
    # Candidate information (indexed for search)
    candidate_name = db.Column(db.String(512), index=True)
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50), index=True)
    
    # Structured data (using JSONB for PostgreSQL - better performance than JSON)
    skills = db.Column(MutableList.as_mutable(JSONB), nullable=True)
    experience = db.Column(MutableDict.as_mutable(JSONB), nullable=True)
    education = db.Column(MutableDict.as_mutable(JSONB), nullable=True)
    
    # Enhanced fields
    languages = db.Column(ARRAY(db.String), nullable=True)  # Languages spoken
    certifications = db.Column(JSONB, nullable=True)  # Certifications list
    social_links = db.Column(JSONB, nullable=True)  # LinkedIn, GitHub, etc.
    portfolio_url = db.Column(db.String(512), nullable=True)
    
    # Classification and metadata
    status = db.Column(
        db.Enum(ResumeStatus),
        default=ResumeStatus.PENDING,
        nullable=False,
        index=True
    )
    experience_level = db.Column(
        db.Enum(ExperienceLevel),
        nullable=True,
        index=True
    )
    education_level = db.Column(
        db.Enum(EducationLevel),
        nullable=True,
        index=True
    )
    years_of_experience = db.Column(db.Float, nullable=True, index=True)  # Calculated field
    current_role = db.Column(db.String(255), nullable=True)
    current_company = db.Column(db.String(255), nullable=True)
    
    # Scores and analytics (for ranking and matching)
    match_score = db.Column(db.Float, nullable=True)  # 0-100 match score
    skills_score = db.Column(db.Float, nullable=True)
    experience_score = db.Column(db.Float, nullable=True)
    education_score = db.Column(db.Float, nullable=True)
    
    # Text search (PostgreSQL full-text search)
    search_vector = db.Column(
        db.TSVector,
        nullable=True,
        doc="Full-text search vector for efficient searching"
    )
    
    # Audit timestamps
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    deleted_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
        doc="Soft delete timestamp"
    )
    
    # Processing metadata
    processing_started_at = db.Column(db.DateTime, nullable=True)
    processing_completed_at = db.Column(db.DateTime, nullable=True)
    processing_error = db.Column(db.Text, nullable=True)
    processing_retries = db.Column(db.Integer, default=0)
    
    # Versioning and deduplication
    version = db.Column(db.Integer, default=1)
    parent_resume_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id"),
        nullable=True,
        doc="Reference to previous version"
    )
    is_duplicate = db.Column(db.Boolean, default=False, index=True)
    duplicate_of_id = db.Column(
        db.Integer,
        db.ForeignKey("resumes.id"),
        nullable=True
    )
    
    # Relationships
    parent_resume = db.relationship(
        "Resume",
        remote_side=[id],
        backref=db.backref("versions", lazy="dynamic"),
        foreign_keys=[parent_resume_id]
    )
    duplicate_of = db.relationship(
        "Resume",
        remote_side=[id],
        backref=db.backref("duplicates", lazy="dynamic"),
        foreign_keys=[duplicate_of_id]
    )
    
    # Indexes for performance
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('idx_resume_status_created', 'status', 'created_at'),
        Index('idx_resume_candidate_email', 'candidate_name', 'email'),
        Index('idx_resume_experience_level_status', 'experience_level', 'status'),
        Index('idx_resume_match_score', 'match_score', 'status'),
        
        # GIN index for JSONB fields (PostgreSQL)
        Index('idx_resume_skills_gin', 'skills', postgresql_using='gin'),
        Index('idx_resume_experience_gin', 'experience', postgresql_using='gin'),
        Index('idx_resume_education_gin', 'education', postgresql_using='gin'),
        
        # GIN index for full-text search
        Index('idx_resume_search_vector', 'search_vector', postgresql_using='gin'),
        
        # Constraints
        CheckConstraint(
            'match_score >= 0 AND match_score <= 100',
            name='check_match_score_range'
        ),
        CheckConstraint(
            'years_of_experience >= 0',
            name='check_years_experience_positive'
        ),
        CheckConstraint(
            'processing_retries >= 0 AND processing_retries <= 5',
            name='check_retries_range'
        ),
        UniqueConstraint('uuid', name='uq_resume_uuid'),
        UniqueConstraint('file_hash', name='uq_resume_file_hash', deferrable=True),
    )
    
    def __init__(self, **kwargs):
        """Initialize resume with validation."""
        super(Resume, self).__init__(**kwargs)
        self.validate_structured_data()
    
    @validates('email')
    def validate_email(self, key: str, email: Optional[str]) -> Optional[str]:
        """Validate email format."""
        if email is None:
            return email
        
        email = email.lower().strip()
        
        # RFC 5322 compliant regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError(f"Invalid email format: {email}")
        
        return email
    
    @validates('phone')
    def validate_phone(self, key: str, phone: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number."""
        if phone is None:
            return phone
        
        # Remove all non-digit characters except '+'
        cleaned = re.sub(r'[^\d+]', '', phone.strip())
        
        # Basic phone number validation
        digit_count = sum(c.isdigit() for c in cleaned)
        if digit_count < 7 or digit_count > 15:
            raise ValueError(f"Invalid phone number length: {phone}")
        
        return cleaned
    
    @validates('filename')
    def validate_filename(self, key: str, filename: str) -> str:
        """Validate filename for security."""
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")
        
        # Prevent path traversal attacks
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValueError("Invalid filename contains path traversal characters")
        
        # Check extension
        allowed_extensions = {'.pdf', '.docx', '.txt', '.rtf'}
        ext = filename[filename.rfind('.'):].lower() if '.' in filename else ''
        if ext not in allowed_extensions:
            raise ValueError(f"Unsupported file extension: {ext}")
        
        # Limit length
        if len(filename) > 512:
            raise ValueError("Filename exceeds maximum length")
        
        return filename.strip()
    
    @validates('skills')
    def validate_skills(self, key: str, skills: Optional[List[str]]) -> Optional[List[str]]:
        """Validate skills list."""
        if skills is None:
            return skills
        
        if not isinstance(skills, list):
            raise ValueError("Skills must be a list")
        
        # Clean and deduplicate skills
        cleaned = []
        seen = set()
        
        for skill in skills:
            if not skill or not isinstance(skill, str):
                continue
            
            skill = skill.strip().lower()
            if skill and skill not in seen and len(skill) <= 100:
                cleaned.append(skill)
                seen.add(skill)
        
        # Limit number of skills
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        
        return cleaned
    
    @validates('match_score')
    def validate_match_score(self, key: str, score: Optional[float]) -> Optional[float]:
        """Validate match score range."""
        if score is None:
            return score
        
        if not isinstance(score, (int, float)):
            raise ValueError("Match score must be a number")
        
        if score < 0 or score > 100:
            raise ValueError("Match score must be between 0 and 100")
        
        return round(score, 2)
    
    def validate_structured_data(self) -> None:
        """Validate JSON structured data schemas."""
        # Validate experience structure
        if self.experience:
            required_fields = ['company', 'title', 'start_date']
            if isinstance(self.experience, list):
                for exp in self.experience:
                    if isinstance(exp, dict):
                        # Validate required fields for each experience
                        for field in required_fields:
                            if field in exp and not exp.get(field):
                                raise ValueError(f"Experience missing {field}")
        
        # Validate education structure
        if self.education:
            required_fields = ['institution', 'degree']
            if isinstance(self.education, list):
                for edu in self.education:
                    if isinstance(edu, dict):
                        for field in required_fields:
                            if field in edu and not edu.get(field):
                                raise ValueError(f"Education missing {field}")
    
    @reconstructor
    def init_on_load(self):
        """Initialize instance when loaded from database."""
        # Ensure mutable types are properly initialized
        if self.skills is None:
            self.skills = []
        if self.experience is None:
            self.experience = []
        if self.education is None:
            self.education = []
    
    def soft_delete(self) -> None:
        """Soft delete the resume."""
        self.status = ResumeStatus.DELETED
        self.deleted_at = datetime.now(timezone.utc)
        db.session.add(self)
    
    def restore(self) -> None:
        """Restore a soft-deleted resume."""
        if self.status == ResumeStatus.DELETED:
            self.status = ResumeStatus.PENDING
            self.deleted_at = None
            db.session.add(self)
    
    def mark_processing_started(self) -> None:
        """Mark resume processing as started."""
        self.status = ResumeStatus.PROCESSING
        self.processing_started_at = datetime.now(timezone.utc)
        db.session.add(self)
    
    def mark_processing_completed(self) -> None:
        """Mark resume processing as completed."""
        self.status = ResumeStatus.COMPLETED
        self.processing_completed_at = datetime.now(timezone.utc)
        db.session.add(self)
    
    def mark_processing_failed(self, error: str) -> None:
        """Mark resume processing as failed."""
        self.status = ResumeStatus.FAILED
        self.processing_error = error
        self.processing_retries += 1
        db.session.add(self)
    
    def update_match_score(self, skills_score: float = None, 
                          experience_score: float = None,
                          education_score: float = None) -> None:
        """Update match scores and calculate overall score."""
        if skills_score is not None:
            self.skills_score = self.validate_match_score('skills_score', skills_score)
        if experience_score is not None:
            self.experience_score = self.validate_match_score('experience_score', experience_score)
        if education_score is not None:
            self.education_score = self.validate_match_score('education_score', education_score)
        
        # Calculate overall match score (weighted average)
        scores = []
        weights = []
        
        if self.skills_score is not None:
            scores.append(self.skills_score)
            weights.append(0.5)  # Skills weight
        if self.experience_score is not None:
            scores.append(self.experience_score)
            weights.append(0.3)  # Experience weight
        if self.education_score is not None:
            scores.append(self.education_score)
            weights.append(0.2)  # Education weight
        
        if scores:
            self.match_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
            db.session.add(self)
    
    def calculate_years_of_experience(self) -> Optional[float]:
        """Calculate total years of experience from experience entries."""
        if not self.experience:
            return None
        
        total_years = 0.0
        
        for exp in self.experience:
            if isinstance(exp, dict):
                start_date = exp.get('start_date')
                end_date = exp.get('end_date', datetime.now(timezone.utc))
                
                if start_date and end_date:
                    try:
                        # Parse dates (assuming ISO format or string)
                        if isinstance(start_date, str):
                            start_date = datetime.fromisoformat(start_date)
                        if isinstance(end_date, str):
                            end_date = datetime.fromisoformat(end_date)
                        
                        years = (end_date - start_date).days / 365.25
                        total_years += years
                    except (ValueError, TypeError):
                        continue
        
        self.years_of_experience = round(total_years, 1)
        db.session.add(self)
        return self.years_of_experience
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert resume to dictionary.
        
        Args:
            include_sensitive: Include sensitive fields (phone, email, etc.)
        """
        data = {
            "id": str(self.uuid),  # Use UUID for public API
            "filename": self.filename,
            "candidate_name": self.candidate_name,
            "skills": self.skills,
            "experience": self.experience,
            "education": self.education,
            "languages": self.languages,
            "certifications": self.certifications,
            "status": self.status.value if self.status else None,
            "experience_level": self.experience_level.value if self.experience_level else None,
            "education_level": self.education_level.value if self.education_level else None,
            "years_of_experience": self.years_of_experience,
            "match_score": self.match_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # Include sensitive fields if requested
        if include_sensitive:
            data.update({
                "email": self.email,
                "phone": self.phone,
                "social_links": self.social_links,
                "portfolio_url": self.portfolio_url,
            })
        
        return data
    
    def to_json(self, include_sensitive: bool = False) -> str:
        """Convert resume to JSON string."""
        return json.dumps(self.to_dict(include_sensitive), default=str)
    
    @classmethod
    def search(cls, query: str, status: Optional[ResumeStatus] = None,
               limit: int = 100, offset: int = 0):
        """
        Full-text search across resumes.
        
        Args:
            query: Search query string
            status: Filter by resume status
            limit: Maximum results
            offset: Pagination offset
        """
        from sqlalchemy import or_
        
        base_query = cls.query.filter(cls.deleted_at.is_(None))
        
        if status:
            base_query = base_query.filter(cls.status == status)
        
        # Use PostgreSQL full-text search if available
        if hasattr(cls, 'search_vector') and cls.search_vector is not None:
            search_query = func.plainto_tsquery('english', query)
            base_query = base_query.filter(cls.search_vector.op('@@')(search_query))
            base_query = base_query.order_by(
                func.ts_rank(cls.search_vector, search_query).desc()
            )
        else:
            # Fallback to basic text search
            search_pattern = f"%{query}%"
            base_query = base_query.filter(
                or_(
                    cls.candidate_name.ilike(search_pattern),
                    cls.skills.cast(db.String).ilike(search_pattern),
                    cls.email.ilike(search_pattern)
                )
            )
        
        return base_query.limit(limit).offset(offset).all()
    
    @classmethod
    def find_duplicates(cls, file_hash: str) -> List['Resume']:
        """Find duplicate resumes by file hash."""
        return cls.query.filter(
            cls.file_hash == file_hash,
            cls.deleted_at.is_(None)
        ).all()
    
    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """Get resume statistics for dashboard."""
        stats = {
            "total": cls.query.filter(cls.deleted_at.is_(None)).count(),
            "by_status": {},
            "by_experience_level": {},
            "by_education_level": {},
            "avg_match_score": 0.0,
            "total_skills": 0,
        }
        
        # Count by status
        for status in ResumeStatus:
            count = cls.query.filter(
                cls.status == status,
                cls.deleted_at.is_(None)
            ).count()
            stats["by_status"][status.value] = count
        
        # Count by experience level
        for level in ExperienceLevel:
            count = cls.query.filter(
                cls.experience_level == level,
                cls.deleted_at.is_(None)
            ).count()
            stats["by_experience_level"][level.value] = count
        
        # Count by education level
        for level in EducationLevel:
            count = cls.query.filter(
                cls.education_level == level,
                cls.deleted_at.is_(None)
            ).count()
            stats["by_education_level"][level.value] = count
        
        # Average match score
        from sqlalchemy import func
        avg_score = cls.query.with_entities(
            func.avg(cls.match_score)
        ).filter(
            cls.match_score.isnot(None),
            cls.deleted_at.is_(None)
        ).scalar()
        
        stats["avg_match_score"] = round(avg_score or 0, 2)
        
        return stats


# SQLAlchemy event listeners for automatic field updates

@event.listens_for(Resume, 'before_insert')
@event.listens_for(Resume, 'before_update')
def update_search_vector(mapper, connection, target: Resume):
    """Automatically update search vector before insert/update."""
    if target.candidate_name or target.skills or target.email:
        # Create search document from relevant fields
        search_doc = " ".join(filter(None, [
            target.candidate_name or "",
            " ".join(target.skills or []),
            target.email or "",
            target.current_role or "",
            target.current_company or "",
        ]))
        
        # Update search vector using PostgreSQL function
        connection.execute(
            text("""
                UPDATE resumes 
                SET search_vector = to_tsvector('english', :content)
                WHERE id = :id
            """),
            {"content": search_doc, "id": target.id}
        )


@event.listens_for(Resume, 'before_insert')
def set_initial_version(mapper, connection, target: Resume):
    """Set initial version number."""
    if target.version is None:
        target.version = 1


@event.listens_for(Resume, 'before_update')
def update_timestamp(mapper, connection, target: Resume):
    """Ensure updated_at is always set on update."""
    target.updated_at = datetime.now(timezone.utc)


# Example usage
if __name__ == "__main__":
    # This would typically be in a separate script or Flask CLI command
    
    # Create a new resume
    resume = Resume(
        filename="john_doe_resume.pdf",
        file_size=1024000,
        file_hash="sha256_hash_here",
        candidate_name="John Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        skills=["Python", "JavaScript", "SQL", "React", "AWS"],
        experience=[
            {
                "company": "Tech Corp",
                "title": "Senior Developer",
                "start_date": "2020-01-01",
                "end_date": "2023-12-31",
                "description": "Led development team"
            }
        ],
        education=[
            {
                "institution": "University of Technology",
                "degree": "Bachelor of Science in Computer Science",
                "year": 2019
            }
        ],
        languages=["English", "Spanish"],
        certifications=[
            {"name": "AWS Certified Solutions Architect", "year": 2022}
        ],
        experience_level=ExperienceLevel.SENIOR,
        education_level=EducationLevel.BACHELOR,
        current_role="Senior Software Engineer",
        current_company="Tech Corp"
    )
    
    # Validate and save
    try:
        db.session.add(resume)
        db.session.commit()
        
        # Update derived fields
        resume.calculate_years_of_experience()
        resume.update_match_score(skills_score=85, experience_score=90)
        db.session.commit()
        
        print(f"Resume created: {resume.uuid}")
        
        # Search for resumes
        results = Resume.search("Python Developer", status=ResumeStatus.COMPLETED)
        print(f"Found {len(results)} matching resumes")
        
        # Get statistics
        stats = Resume.get_statistics()
        print(f"Total resumes: {stats['total']}")
        
    except ValueError as e:
        print(f"Validation error: {e}")
        db.session.rollback()
    except Exception as e:
        print(f"Database error: {e}")
        db.session.rollback()
