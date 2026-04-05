"""Initial migration - Create resumes table

Revision ID: 001_initial_migration
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

# revision identifiers, used by Alembic.
revision = '001_initial_migration'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types for PostgreSQL
    op.execute("CREATE TYPE resumestatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'archived', 'deleted')")
    op.execute("CREATE TYPE experiencelevel AS ENUM ('entry', 'junior', 'mid', 'senior', 'lead', 'executive')")
    op.execute("CREATE TYPE educationlevel AS ENUM ('high_school', 'associate', 'bachelor', 'master', 'doctorate', 'certification', 'other')")
    
    # Create resumes table
    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('storage_path', sa.String(1024), nullable=True),
        sa.Column('original_filename', sa.String(512), nullable=True),
        sa.Column('candidate_name', sa.String(512), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('skills', JSONB(), nullable=True),
        sa.Column('experience', JSONB(), nullable=True),
        sa.Column('education', JSONB(), nullable=True),
        sa.Column('languages', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('certifications', JSONB(), nullable=True),
        sa.Column('social_links', JSONB(), nullable=True),
        sa.Column('portfolio_url', sa.String(512), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'archived', 'deleted', name='resumestatus'), nullable=False),
        sa.Column('experience_level', sa.Enum('entry', 'junior', 'mid', 'senior', 'lead', 'executive', name='experiencelevel'), nullable=True),
        sa.Column('education_level', sa.Enum('high_school', 'associate', 'bachelor', 'master', 'doctorate', 'certification', 'other', name='educationlevel'), nullable=True),
        sa.Column('years_of_experience', sa.Float(), nullable=True),
        sa.Column('current_role', sa.String(255), nullable=True),
        sa.Column('current_company', sa.String(255), nullable=True),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('skills_score', sa.Float(), nullable=True),
        sa.Column('experience_score', sa.Float(), nullable=True),
        sa.Column('education_score', sa.Float(), nullable=True),
        sa.Column('search_vector', TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processing_retries', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('parent_resume_id', sa.Integer(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=True),
        sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Unique constraints
        sa.UniqueConstraint('uuid', name='uq_resume_uuid'),
        sa.UniqueConstraint('file_hash', name='uq_resume_file_hash'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['parent_resume_id'], ['resumes.id'], ),
        sa.ForeignKeyConstraint(['duplicate_of_id'], ['resumes.id'], ),
        
        # Check constraints
        sa.CheckConstraint('match_score >= 0 AND match_score <= 100', name='check_match_score_range'),
        sa.CheckConstraint('years_of_experience >= 0', name='check_years_experience_positive'),
        sa.CheckConstraint('processing_retries >= 0 AND processing_retries <= 5', name='check_retries_range'),
    )
    
    # Create indexes
    op.create_index('idx_resume_uuid', 'resumes', ['uuid'])
    op.create_index('idx_resume_filename', 'resumes', ['filename'])
    op.create_index('idx_resume_email', 'resumes', ['email'])
    op.create_index('idx_resume_phone', 'resumes', ['phone'])
    op.create_index('idx_resume_candidate_name', 'resumes', ['candidate_name'])
    op.create_index('idx_resume_file_hash', 'resumes', ['file_hash'])
    op.create_index('idx_resume_status', 'resumes', ['status'])
    op.create_index('idx_resume_experience_level', 'resumes', ['experience_level'])
    op.create_index('idx_resume_education_level', 'resumes', ['education_level'])
    op.create_index('idx_resume_created_at', 'resumes', ['created_at'])
    op.create_index('idx_resume_updated_at', 'resumes', ['updated_at'])
    op.create_index('idx_resume_deleted_at', 'resumes', ['deleted_at'])
    op.create_index('idx_resume_match_score', 'resumes', ['match_score'])
    op.create_index('idx_resume_years_experience', 'resumes', ['years_of_experience'])
    
    # Composite indexes for common queries
    op.create_index('idx_resume_status_created', 'resumes', ['status', 'created_at'])
    op.create_index('idx_resume_candidate_email', 'resumes', ['candidate_name', 'email'])
    op.create_index('idx_resume_experience_level_status', 'resumes', ['experience_level', 'status'])
    
    # GIN indexes for JSONB fields (PostgreSQL)
    op.create_index('idx_resume_skills_gin', 'resumes', ['skills'], postgresql_using='gin')
    op.create_index('idx_resume_experience_gin', 'resumes', ['experience'], postgresql_using='gin')
    op.create_index('idx_resume_education_gin', 'resumes', ['education'], postgresql_using='gin')
    op.create_index('idx_resume_certifications_gin', 'resumes', ['certifications'], postgresql_using='gin')
    
    # GIN index for full-text search
    op.create_index('idx_resume_search_vector', 'resumes', ['search_vector'], postgresql_using='gin')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_resume_search_vector', table_name='resumes')
    op.drop_index('idx_resume_certifications_gin', table_name='resumes')
    op.drop_index('idx_resume_education_gin', table_name='resumes')
    op.drop_index('idx_resume_experience_gin', table_name='resumes')
    op.drop_index('idx_resume_skills_gin', table_name='resumes')
    op.drop_index('idx_resume_experience_level_status', table_name='resumes')
    op.drop_index('idx_resume_candidate_email', table_name='resumes')
    op.drop_index('idx_resume_status_created', table_name='resumes')
    op.drop_index('idx_resume_years_experience', table_name='resumes')
    op.drop_index('idx_resume_match_score', table_name='resumes')
    op.drop_index('idx_resume_deleted_at', table_name='resumes')
    op.drop_index('idx_resume_updated_at', table_name='resumes')
    op.drop_index('idx_resume_created_at', table_name='resumes')
    op.drop_index('idx_resume_education_level', table_name='resumes')
    op.drop_index('idx_resume_experience_level', table_name='resumes')
    op.drop_index('idx_resume_status', table_name='resumes')
    op.drop_index('idx_resume_file_hash', table_name='resumes')
    op.drop_index('idx_resume_candidate_name', table_name='resumes')
    op.drop_index('idx_resume_phone', table_name='resumes')
    op.drop_index('idx_resume_email', table_name='resumes')
    op.drop_index('idx_resume_filename', table_name='resumes')
    op.drop_index('idx_resume_uuid', table_name='resumes')
    
    # Drop table
    op.drop_table('resumes')
    
    # Drop enum types
    op.execute("DROP TYPE resumestatus")
    op.execute("DROP TYPE experiencelevel")
    op.execute("DROP TYPE educationlevel")
