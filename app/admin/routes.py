"""
Admin routes for system management, user management, and analytics.
"""

from datetime import datetime, timedelta
from flask import request, jsonify, render_template, redirect, url_for, session, current_app
from sqlalchemy import func, and_

from app.admin import admin_bp
from app.admin.auth import require_admin_auth, require_ip_whitelist
from app.models import db, Resume, ResumeStatus, ExperienceLevel
from app.parser.nlp_processor import NLPProcessor


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Validate credentials (in production, use proper password hashing)
        if username == 'admin' and password == current_app.config.get('ADMIN_PASSWORD', 'changeme'):
            session['admin_logged_in'] = True
            session['admin_user'] = username
            session['login_time'] = datetime.utcnow().isoformat()
            
            current_app.logger.info(f"Admin login successful: {username}")
            return redirect(url_for('admin.dashboard'))
        else:
            current_app.logger.warning(f"Failed admin login attempt: {username}")
            return render_template('admin/login.html', error="Invalid credentials")
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    """Admin logout."""
    session.clear()
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@require_admin_auth
@require_ip_whitelist
def dashboard():
    """Admin dashboard."""
    return render_template('admin/dashboard.html')


@admin_bp.route('/api/stats', methods=['GET'])
@require_admin_auth
@require_ip_whitelist
def admin_stats():
    """
    Get detailed system statistics for administrators.
    """
    try:
        # Get time range (default: last 30 days)
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Database statistics
        total_resumes = Resume.query.filter_by(deleted_at=None).count()
        active_resumes = Resume.query.filter(
            Resume.deleted_at.is_(None),
            Resume.status != ResumeStatus.DELETED
        ).count()
        
        # Status distribution
        status_counts = db.session.query(
            Resume.status,
            func.count(Resume.id)
        ).filter(
            Resume.deleted_at.is_(None)
        ).group_by(Resume.status).all()
        
        status_distribution = {
            status.value if status else 'unknown': count
            for status, count in status_counts
        }
        
        # Experience level distribution
        level_counts = db.session.query(
            Resume.experience_level,
            func.count(Resume.id)
        ).filter(
            Resume.deleted_at.is_(None),
            Resume.experience_level.isnot(None)
        ).group_by(Resume.experience_level).all()
        
        experience_distribution = {
            level.value if level else 'unknown': count
            for level, count in level_counts
        }
        
        # Daily uploads (last 30 days)
        daily_uploads = db.session.query(
            func.date(Resume.created_at).label('date'),
            func.count(Resume.id).label('count')
        ).filter(
            Resume.created_at >= start_date,
            Resume.deleted_at.is_(None)
        ).group_by(func.date(Resume.created_at)).all()
        
        # Average match score
        avg_match_score = db.session.query(
            func.avg(Resume.match_score)
        ).filter(
            Resume.match_score.isnot(None),
            Resume.deleted_at.is_(None)
        ).scalar() or 0
        
        # Top skills (most frequent)
        # Note: This query depends on your database. For PostgreSQL with JSONB:
        top_skills = []
        if current_app.config['DATABASE_CONFIG'].url.startswith('postgresql'):
            # Unnest skills array and count frequencies
            from sqlalchemy import text
            result = db.session.execute(text("""
                SELECT skill, COUNT(*) as count
                FROM resumes, jsonb_array_elements_text(skills) AS skill
                WHERE deleted_at IS NULL AND skills IS NOT NULL
                GROUP BY skill
                ORDER BY count DESC
                LIMIT 20
            """))
            top_skills = [{"skill": row[0], "count": row[1]} for row in result]
        
        # NLP model info
        nlp_processor = NLPProcessor(lazy_load=True)
        nlp_info = nlp_processor.get_model_info()
        
        # System health checks
        health_checks = {
            "database": True,  # We're able to query
            "redis": _check_redis_connection(),
            "storage": _check_storage_health(),
            "nlp_model": nlp_info['loaded']
        }
        
        return jsonify({
            "success": True,
            "statistics": {
                "total_resumes": total_resumes,
                "active_resumes": active_resumes,
                "status_distribution": status_distribution,
                "experience_distribution": experience_distribution,
                "daily_uploads": [{"date": str(d[0]), "count": d[1]} for d in daily_uploads],
                "avg_match_score": round(avg_match_score, 2),
                "top_skills": top_skills
            },
            "nlp_info": nlp_info,
            "health_checks": health_checks,
            "environment": current_app.config['ENV'].value,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.exception(f"Failed to get admin stats: {e}")
        return jsonify({
            "error": "Failed to retrieve admin statistics",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@admin_bp.route('/api/resumes', methods=['GET'])
@require_admin_auth
@require_ip_whitelist
def admin_list_resumes():
    """
    List all resumes with admin view (includes sensitive data).
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 200)
        status = request.args.get('status')
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
        
        query = Resume.query
        if not include_deleted:
            query = query.filter_by(deleted_at=None)
        
        if status:
            try:
                query = query.filter_by(status=ResumeStatus(status))
            except ValueError:
                pass
        
        paginated = query.order_by(Resume.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            "resumes": [r.to_dict(include_sensitive=True) for r in paginated.items],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": paginated.total,
                "pages": paginated.pages
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to list resumes for admin: {e}")
        return jsonify({
            "error": "Failed to retrieve resumes",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@admin_bp.route('/api/resume/<resume_id>/permanent', methods=['DELETE'])
@require_admin_auth
@require_ip_whitelist
def permanent_delete_resume(resume_id: str):
    """
    Permanently delete a resume from database.
    
    Args:
        resume_id: Resume UUID
    """
    try:
        resume = Resume.query.filter_by(uuid=resume_id).first()
        
        if not resume:
            return jsonify({
                "error": "Resume not found",
                "code": 404
            }), 404
        
        # Permanent delete
        db.session.delete(resume)
        db.session.commit()
        
        current_app.logger.warning(f"Permanently deleted resume {resume_id}")
        
        return jsonify({
            "success": True,
            "message": "Resume permanently deleted",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to permanently delete resume {resume_id}: {e}")
        return jsonify({
            "error": "Failed to delete resume",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@admin_bp.route('/api/cache/clear', methods=['POST'])
@require_admin_auth
@require_ip_whitelist
def clear_cache():
    """Clear application caches."""
    try:
        # Clear NLP cache
        nlp_processor = NLPProcessor(lazy_load=True)
        nlp_processor.clear_cache()
        
        # Clear any other caches
        if hasattr(current_app, 'cache'):
            current_app.cache.clear()
        
        current_app.logger.info("Cache cleared by admin")
        
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


@admin_bp.route('/api/system/config', methods=['GET'])
@require_admin_auth
@require_ip_whitelist
def get_system_config():
    """Get current system configuration (secrets masked)."""
    config_dict = current_app.config['APP_CONFIG'].to_dict()
    
    # Mask sensitive values
    sensitive_keys = ['secret_key', 'jwt_secret_key', 'api_key_salt', 'password']
    for key in sensitive_keys:
        if key in config_dict:
            config_dict[key] = '***MASKED***'
    
    return jsonify({
        "config": config_dict,
        "timestamp": datetime.utcnow().isoformat()
    }), 200


def _check_redis_connection() -> bool:
    """Check Redis connection health."""
    try:
        if current_app.config.get('REDIS_CONFIG'):
            import redis
            r = redis.from_url(current_app.config['REDIS_CONFIG'].url)
            return r.ping()
    except Exception:
        pass
    return False


def _check_storage_health() -> bool:
    """Check storage backend health."""
    try:
        upload_folder = current_app.config['UPLOAD_CONFIG'].upload_folder
        test_file = os.path.join(upload_folder, '.health_check')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception:
        return False
