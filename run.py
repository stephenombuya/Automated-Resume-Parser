#!/usr/bin/env python
"""
Application entry point for development and production.

Usage:
    python run.py                    # Development server
    python run.py --prod             # Production checks
    python run.py --migrate          # Run database migrations
    python run.py --seed             # Seed database with test data
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Load environment variables
env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(env_file)


def create_app_instance():
    """Create Flask app instance."""
    from app import create_app
    return create_app()


def run_migrations():
    """Run database migrations."""
    import subprocess
    print("Running database migrations...")
    result = subprocess.run(['flask', 'db', 'upgrade'], capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ Migrations completed successfully")
    else:
        print(f"✗ Migration failed: {result.stderr}")
        sys.exit(1)


def seed_database():
    """Seed database with test data."""
    from app import create_app
    from app.models import db, Resume, ResumeStatus
    from faker import Faker
    import random
    
    app = create_app()
    fake = Faker()
    
    with app.app_context():
        # Check if data already exists
        if Resume.query.count() > 0:
            confirm = input("Database already has data. Overwrite? (y/N): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        # Clear existing data
        db.session.query(Resume).delete()
        
        # Create test resumes
        skills_pool = [
            'Python', 'JavaScript', 'Java', 'SQL', 'React', 'AWS',
            'Docker', 'Kubernetes', 'Machine Learning', 'Data Analysis',
            'Project Management', 'Leadership', 'Communication'
        ]
        
        for i in range(50):
            resume = Resume(
                filename=f"resume_{i+1}.pdf",
                candidate_name=fake.name(),
                email=fake.email(),
                phone=fake.phone_number(),
                skills=random.sample(skills_pool, k=random.randint(3, 8)),
                status=random.choice(list(ResumeStatus)),
                created_at=fake.date_time_this_year()
            )
            db.session.add(resume)
        
        db.session.commit()
        print(f"✓ Database seeded with {Resume.query.count()} test resumes")


def check_environment():
    """Check production environment configuration."""
    errors = []
    warnings = []
    
    # Check required environment variables
    required_vars = ['SECRET_KEY', 'JWT_SECRET_KEY', 'API_KEY_SALT', 'DATABASE_URL']
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
        elif var.endswith('KEY') and len(os.getenv(var, '')) < 32:
            warnings.append(f"{var} is less than 32 characters")
    
    # Check upload directory
    upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        warnings.append(f"Upload directory does not exist: {upload_folder}")
    elif not os.access(upload_folder, os.W_OK):
        errors.append(f"Upload directory is not writable: {upload_folder}")
    
    # Check database connection
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from app.models import db
            db.session.execute("SELECT 1")
        print("✓ Database connection successful")
    except Exception as e:
        errors.append(f"Database connection failed: {e}")
    
    # Check Redis connection (if enabled)
    if os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true':
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            print("✓ Redis connection successful")
        except Exception as e:
            warnings.append(f"Redis connection failed: {e}")
    
    # Print results
    print("\n" + "=" * 50)
    print("Environment Check Results")
    print("=" * 50)
    
    if errors:
        print("\n❌ ERRORS:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("\n✓ All checks passed!")
    
    return len(errors) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Resume Parser Application')
    parser.add_argument('--prod', action='store_true', help='Run production checks')
    parser.add_argument('--migrate', action='store_true', help='Run database migrations')
    parser.add_argument('--seed', action='store_true', help='Seed database with test data')
    parser.add_argument('--check', action='store_true', help='Check environment configuration')
    parser.add_argument('--host', default=None, help='Host to bind to')
    parser.add_argument('--port', type=int, default=None, help='Port to bind to')
    
    args = parser.parse_args()
    
    # Run environment check
    if args.check or args.prod:
        if not check_environment():
            if args.prod:
                sys.exit(1)
    
    # Run migrations
    if args.migrate:
        run_migrations()
        return
    
    # Seed database
    if args.seed:
        seed_database()
        return
    
    # Create and run application
    app = create_app_instance()
    
    # Get host and port
    host = args.host or os.getenv('FLASK_HOST', '0.0.0.0')
    port = args.port or int(os.getenv('FLASK_PORT', 5000))
    
    # Production warning
    if os.getenv('FLASK_ENV') == 'production':
        print("\n" + "=" * 60)
        print("⚠️  WARNING: Running in production mode")
        print("=" * 60)
        print("For production deployment, use:")
        print("  gunicorn --worker-class gevent --workers 4 run:app")
        print("=" * 60 + "\n")
    
    # Run application
    app.run(
        host=host,
        port=port,
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
        threaded=True
    )


if __name__ == '__main__':
    main()
