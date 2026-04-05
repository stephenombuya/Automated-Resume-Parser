# Resume Parser API
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Flask Version](https://img.shields.io/badge/flask-2.3+-green.svg)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Security](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

A production-grade resume parsing API that extracts candidate information from PDF and DOCX files using NLP and machine learning techniques.

## 🚀 Features
### Core Capabilities
- **Multi-format Support**: Parse PDF, DOCX, TXT, and RTF files
- **Entity Extraction**: Extract names, emails, phone numbers, and skills
- **Structured Output**: JSON response with normalized data
- **High Accuracy**: NLP-powered extraction with confidence scoring
- **OCR Support**: Optional OCR fallback for scanned documents
- **Table Extraction**: Parse tables from documents (experimental)


### Production Features
- **High Performance**: Async processing with connection pooling
- **Scalable**: Horizontal scaling with Redis and PostgreSQL
- **Secure**: API key authentication, rate limiting, CORS
- **Observable**: Prometheus metrics, structured logging, Sentry integration
- **Reliable**: Comprehensive error handling, retry logic, health checks
- **Maintainable**: Migration support, feature flags, environment configs


### API Features
- **RESTful API**: Clean, consistent REST endpoints
- **Authentication**: API key and JWT token support
- **Rate Limiting**: Configurable limits per endpoint
- **Pagination**: List endpoints with cursor-based pagination
- **Filtering**: Search and filter by status, experience, skills
- **Webhooks**: Event notifications for async processing


## 📋 Table of Contents
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Development](#development)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)


## ⚡ Quick Start
### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/resume-parser.git
cd resume-parser
# Copy environment configuration
cp .env.example .env.production
# Edit configuration (required)
vim .env.production
# Build and run with Docker Compose
docker-compose up -d
# Check health
curl http://localhost:5000/health
```

### Local Development

```bash
# Clone and enter directory
git clone https://github.com/yourusername/resume-parser.git
cd resume-parser
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
# Download spaCy model
python -m spacy download en_core_web_sm
# Set up database
createdb resume_parser_dev
flask db upgrade
# Run development server
python run.py
```

### Test the API

```bash
# Parse a resume
curl -X POST http://localhost:5000/api/v1/parse \
 -H "X-API-Key: your_api_key" \
 -F "file=@/path/to/resume.pdf"
# Get resume by ID
curl http://localhost:5000/api/v1/resume/123e4567-e89b-12d3-a456-426614174000 \
 -H "X-API-Key: your_api_key"
# List resumes with pagination
curl "http://localhost:5000/api/v1/resumes?page=1&per_page=20&status=completed" \
 -H "X-API-Key: your_api_key"
# Search resumes
curl "http://localhost:5000/api/v1/resumes?search=python+developer" \
 -H "X-API-Key: your_api_key"
```

## 🏗 Architecture

### System Architecture

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│   Nginx      │────▶│   Gunicorn  │
│  (Browser/  │     │  (Reverse    │     │   (WSGI)    │
│   API)      │◀────│   Proxy)     │◀────│             │
└─────────────┘     └──────────────┘     └──────┬──────┘
 │
 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Redis     │◀────│   Flask      │────▶│  PostgreSQL │
│  (Cache/    │     │  Application │     │  (Database) │
│   Rate)     │     │              │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
 │
 ▼
 ┌─────────────┐
 │   S3/Cloud  │
 │  (Storage)  │
 └─────────────┘
```

### Component Stack
  1. **Web Server**
    - Nginx
  2. **Reverse proxy, SSL termination, load balancing**
    - **WSGI Server**
  3. **Gunicorn + Gevent**
    - Python application server with async workers
  4. **Framework**
    - Flask 2.3+
    - Web application framework
  5. **Database**
    - PostgreSQL 15+
    - Primary data store with JSONB support
  6. **Cache**
    - Redis 7+
    - Rate limiting, session storage, caching
  7. **Task Queue**
    - Redis + RQ
    - Async job processing (optional)
  8. **Storage**
    - AWS S3 / Local
    - File storage backend
  9. **Monitoring**
    - Prometheus + Grafana
    - Metrics collection and visualization
  10. **Logging**
    - ELK Stack / Sentry
    - Centralized logging and error tracking

### Data Flow

1.  **Upload**: Client uploads resume → Nginx → Gunicorn → Flask
    
2.  **Validation**: File type, size, MIME type, virus scan
    
3.  **Parsing**: Extract text based on file format (PDF/DOCX)
    
4.  **NLP Processing**: Entity extraction (names, emails, skills)
    
5.  **Storage**: Save to PostgreSQL, upload file to S3
    
6.  **Response**: Return structured JSON to client
    
7.  **Async** (optional): Webhook notification to external services
    

## 📦 Installation

### System Requirements

-   **OS**: Linux (Ubuntu 20.04+), macOS 11+, or Windows 10+ (WSL2)
    
-   **Python**: 3.11 or higher
    
-   **PostgreSQL**: 15 or higher
    
-   **Redis**: 7 or higher
    
-   **RAM**: Minimum 2GB, Recommended 4GB+
    
-   **CPU**: 2+ cores recommended
    

### Step-by-Step Installation

#### 1. Install System Dependencies

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y \
 python3.11 python3.11-venv python3.11-dev \
 postgresql-15 postgresql-contrib \
 redis-server \
 libpq-dev libmagic1 poppler-utils tesseract-ocr \
 nginx
```

**macOS:**

```bash
brew install python@3.11 postgresql@15 redis poppler tesseract nginx
```

**Windows (WSL2):**

```bash
# Follow Ubuntu instructions within WSL2
```

#### 2. Clone and Setup Project

```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Configure Database

```bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE resume_parser_prod;
CREATE USER resume_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE resume_parser_prod TO resume_user;
\q
# Run migrations
flask db upgrade
```

#### 4. Configure Environment

```bash
# Copy example configuration
cp .env.example .env.production
# Edit configuration (required fields)
vim .env.production
```

**Required Configuration:**

```bash
SECRET_KEY=your_32_byte_secret_key
JWT_SECRET_KEY=your_32_byte_jwt_key
DATABASE_URL=postgresql://resume_user:password@localhost:5432/resume_parser_prod
ADMIN_PASSWORD=strong_admin_password
```

#### 5. Download NLP Models

```bash
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_md  # Optional, for better accuracy
```

#### 6. Initialize Application

```bash
# Create required directories
mkdir -p uploads logs temp
# Set permissions
chmod 750 uploads logs temp
# Run health check
python run.py --check
# Seed database with test data (optional)
python run.py --seed
```

## ⚙️ Configuration

### Environment Variables

Variable

Required

Default

Description

`FLASK_ENV`

No

`development`

Environment (development/production/testing)

`SECRET_KEY`

**Yes**

-

32+ char secret for sessions

`JWT_SECRET_KEY`

**Yes**

-

32+ char secret for JWT tokens

`DATABASE_URL`

**Yes**

-

PostgreSQL connection URL

`REDIS_URL`

No

`redis://localhost:6379/0`

Redis connection URL

`MAX_FILE_SIZE_MB`

No

`10`

Maximum upload size in MB

`RATE_LIMIT_ENABLED`

No

`true`

Enable rate limiting

`CORS_ALLOWED_ORIGINS`

No

`*`

Allowed CORS origins

`LOG_LEVEL`

No

`INFO`

Logging level

`SENTRY_DSN`

No

-

Sentry error tracking DSN

### Feature Flags

Flag

Default

Description

`ENABLE_OCR`

`false`

Enable OCR for scanned PDFs

`ENABLE_ML_SKILLS_EXTRACTION`

`false`

Use ML for skills extraction

`ENABLE_EMAIL_NOTIFICATIONS`

`false`

Send email notifications

`ENABLE_CACHING`

`true`

Enable Redis caching

`ENABLE_ASYNC_PROCESSING`

`false`

Async resume processing

`ENABLE_BETA_API`

`false`

Enable beta API endpoints

### Configuration Files

-   `.env` - Development environment
    
-   `.env.production` - Production environment
    
-   `.env.testing` - Testing environment
    
-   `gunicorn.conf.py` - Gunicorn WSGI settings
    
-   `nginx.conf` - Nginx reverse proxy settings
    

## 📚 API Documentation

### Authentication

The API supports two authentication methods:

#### 1. API Key (Simple)

http

GET /api/v1/resumes
X-API-Key: your_api_key_here

#### 2. JWT Token (Advanced)

http

POST /api/v1/auth/token
Content-Type: application/json
{"api_key": "your_api_key"}
# Response
{"access_token": "jwt_token_here", "token_type": "Bearer"}
# Use token
GET /api/v1/resumes
Authorization: Bearer jwt_token_here

### Endpoints

#### Parse Resume

http

POST /api/v1/parse
Content-Type: multipart/form-data
Parameters:
- file: Resume file (required)
- extract_tables: boolean (default: true)
- extract_skills: boolean (default: true)
- return_raw_text: boolean (default: false)
Response:
{
 "success": true,
 "resume_id": "550e8400-e29b-41d4-a716-446655440000",
 "name": "John Doe",
 "email": "john.doe@example.com",
 "phone": "+1 (555) 123-4567",
 "skills": ["Python", "JavaScript", "AWS"],
 "experience_level": "senior",
 "confidence_scores": {
 "skills": 0.85,
 "persons": 0.92
 },
 "metadata": {
 "filename": "resume_20240101_123456.pdf",
 "file_size_mb": 0.45,
 "pages": 2,
 "processing_time_ms": 1234
 }
}

#### Get Resume

http

GET /api/v1/resume/{resume_id}
Query Parameters:
- include_sensitive: boolean (default: false)
Response:
{
 "id": "550e8400-e29b-41d4-a716-446655440000",
 "candidate_name": "John Doe",
 "email": "john.doe@example.com",
 "skills": ["Python", "JavaScript"],
 "status": "completed",
 "created_at": "2024-01-01T12:00:00Z"
}

#### List Resumes

http

GET /api/v1/resumes?page=1&per_page=20&status=completed&search=python
Response:
{
 "resumes": [...],
 "pagination": {
 "page": 1,
 "per_page": 20,
 "total": 150,
 "pages": 8,
 "has_next": true,
 "has_prev": false
 }
}

#### Delete Resume

http

DELETE /api/v1/resume/{resume_id}
Response:
{
 "success": true,
 "message": "Resume deleted successfully"
}

#### Get Statistics

http

GET /api/v1/stats
Response:
{
 "statistics": {
 "total": 1250,
 "by_status": {
 "completed": 1100,
 "failed": 100,
 "pending": 50
 },
 "avg_match_score": 78.5
 }
}

### Webhooks

Configure webhooks to receive async notifications:

http

POST /webhook/register
Content-Type: application/json
{
 "url": "https://your-app.com/webhook",
 "events": ["resume.parsed", "resume.failed"],
 "secret": "your_webhook_secret"
}

## 🗄️ Database Schema

### Resumes Table

Column

Type

Description

`id`

Integer

Auto-increment primary key

`uuid`

UUID

Public-facing unique identifier

`filename`

String(512)

Original filename

`candidate_name`

String(512)

Extracted candidate name

`email`

String(255)

Extracted email address

`phone`

String(50)

Extracted phone number

`skills`

JSONB

Array of extracted skills

`experience`

JSONB

Work experience entries

`education`

JSONB

Education entries

`status`

Enum

Processing status

`match_score`

Float

Overall match score (0-100)

`created_at`

DateTime

Record creation timestamp

`deleted_at`

DateTime

Soft delete timestamp

### Indexes

```sql
-- Performance indexes
CREATE INDEX idx_resume_status_created ON resumes(status, created_at);
CREATE INDEX idx_resume_candidate_email ON resumes(candidate_name, email);
CREATE INDEX idx_resume_skills_gin ON resumes USING gin(skills);
-- Full-text search
CREATE INDEX idx_resume_search_vector ON resumes USING gin(search_vector);
```

## 💻 Development

### Project Structure

```text
resume-parser/
├── app/                    # Application package
│   ├── api/               # Public API endpoints
│   ├── admin/             # Admin interface
│   ├── webhook/           # Webhook handlers
│   ├── parser/            # Document parsers
│   ├── models.py          # Database models
│   ├── config.py          # Configuration
│   └── utils.py           # Utilities
├── migrations/            # Database migrations
├── tests/                 # Unit and integration tests
├── scripts/               # Utility scripts
├── uploads/               # Temporary upload storage
├── logs/                  # Application logs
├── requirements.txt       # Python dependencies
├── run.py                 # Development server
├── wsgi.py                # Production WSGI entry
└── docker-compose.yml     # Docker composition
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v
# Run with coverage
pytest tests/ --cov=app --cov-report=html
# Run specific test file
pytest tests/test_api.py -v
# Run with verbose output
pytest -v --log-cli-level=INFO
```

### Code Quality

```bash
# Format code
black app/ tests/
# Lint code
flake8 app/ tests/
# Type checking
mypy app/
# Security scan
bandit -r app/
```

### Database Migrations

```bash
# Create migration
flask db migrate -m "Description of changes"
# Apply migrations
flask db upgrade
# Rollback last migration
flask db downgrade
# View migration history
flask db history
```

### Local Development Tips

```bash
# Use development config
export FLASK_ENV=development
# Enable debug mode
export FLASK_DEBUG=1
# Run with hot reload
python run.py
# Watch logs
tail -f logs/app.log
# Monitor database queries
export SQLALCHEMY_ECHO=1
```

## 🚢 Deployment

### Docker Deployment (Recommended)

```bash
# Build image
docker build -t resume-parser:latest .
# Run container
docker run -d \
 --name resume-parser \
 -p 5000:5000 \
 -e FLASK_ENV=production \
 -v $(pwd)/uploads:/app/uploads \
 -v $(pwd)/logs:/app/logs \
 resume-parser:latest
# Use Docker Compose for full stack
docker-compose up -d
```

### Manual Deployment (Ubuntu 20.04+)

#### 1. Setup User and Directory

```bash
# Create application user
sudo useradd -r -s /bin/bash resume-parser
sudo mkdir -p /var/www/resume-parser
sudo chown resume-parser:resume-parser /var/www/resume-parser
```

#### 2. Deploy Code

```bash
# Clone repository
git clone https://github.com/yourusername/resume-parser.git /var/www/resume-parser
# Install dependencies
cd /var/www/resume-parser
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Configure Systemd Service

Create `/etc/systemd/system/resume-parser.service`:

ini

[Unit]
Description=Resume Parser Gunicorn Service
After=network.target postgresql.service redis.service
[Service]
User=resume-parser
Group=resume-parser
WorkingDirectory=/var/www/resume-parser
Environment="PATH=/var/www/resume-parser/venv/bin"
EnvironmentFile=/var/www/resume-parser/.env.production
ExecStart=/var/www/resume-parser/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true
[Install]
WantedBy=multi-user.target

#### 4. Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable resume-parser
sudo systemctl start resume-parser
sudo systemctl status resume-parser
```

#### 5. Configure Nginx

Create `/etc/nginx/sites-available/resume-parser`:

```nginx
server {
 listen 80;
 server_name api.resumeparser.com;
  
 location / {
 proxy_pass http://127.0.0.1:5000;
 proxy_set_header Host $host;
 proxy_set_header X-Real-IP $remote_addr;
 proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
 }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/resume-parser /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
 name: resume-parser
spec:
 replicas: 3
 selector:
 matchLabels:
 app: resume-parser
 template:
 metadata:
 labels:
 app: resume-parser
 spec:
 containers:
 - name: app
 image: resume-parser:latest
 ports:
 - containerPort: 5000
 envFrom:
 - secretRef:
 name: resume-parser-secrets
 resources:
 requests:
 memory: "512Mi"
 cpu: "250m"
 limits:
 memory: "1Gi"
 cpu: "500m"
 livenessProbe:
 httpGet:
 path: /health/live
 port: 5000
 readinessProbe:
 httpGet:
 path: /health/ready
 port: 5000
```

### Deployment Checklist

-   Environment variables configured
    
-   Database migrations applied
    
-   SSL certificates installed
    
-   Firewall rules configured
    
-   Monitoring setup (Prometheus, Grafana)
    
-   Backup strategy implemented
    
-   Rate limiting configured
    
-   CORS origins restricted
    
-   Log aggregation configured
    
-   Health checks verified
    

## 📊 Monitoring

### Health Check Endpoints

```bash
# Basic health
curl http://localhost:5000/health
# Readiness probe (Kubernetes)
curl http://localhost:5000/health/ready
# Liveness probe
curl http://localhost:5000/health/live
# Metrics (Prometheus)
curl http://localhost:5000/metrics
```

### Prometheus Metrics

Metric

Type

Description

`http_requests_total`

Counter

Total HTTP requests

`http_request_duration_seconds`

Histogram

Request latency

`resume_parsed_total`

Counter

Total resumes parsed

`resume_parsing_errors_total`

Counter

Parsing errors

`active_uploads`

Gauge

Current uploads processing

`database_connections`

Gauge

Active DB connections

`redis_connections`

Gauge

Active Redis connections

### Logging

Logs are written to `/var/log/resume-parser/` with rotation:

-   `app.log` - Application logs (JSON format in production)
    
-   `error.log` - Error-only logs
    
-   `access.log` - API access logs
    

### Sentry Integration

```python
# Enable Sentry for error tracking
SENTRY_DSN=https://your-dsn@sentry.io/project-id
```

### Alerts Configuration

Recommended Prometheus alerts:

```yaml
groups:
- name: resume-parser
 rules:
 - alert: HighErrorRate
 expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
 annotations:
 summary: "High error rate detected"
  
 - alert: SlowResponses
 expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
 annotations:
 summary: "API response time degraded"
  
 - alert: DatabaseDown
 expr: pg_up == 0
 severity: critical
```

## 🔒 Security

### Security Headers

The API includes security headers by default:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Referrer-Policy: strict-origin-when-cross-origin
```

### Authentication

-   **API Keys**: Revocable keys with granular permissions
    
-   **JWT Tokens**: Short-lived tokens with refresh capability
    
-   **IP Whitelisting**: Restrict access to trusted IPs
    
-   **Rate Limiting**: Prevent abuse with configurable limits
    

### Data Protection

-   **Encryption**: TLS 1.2+ for all communications
    
-   **Hashing**: Passwords hashed with bcrypt/scrypt
    
-   **PII Masking**: Sensitive data redacted in logs
    
-   **Soft Delete**: Data recoverable for 30 days
    

### Security Checklist

-   All secrets in environment variables (not code)
    
-   HTTPS enabled in production
    
-   Database connections use SSL
    
-   Regular security updates (apt, pip)
    
-   File uploads scanned for malware
    
-   Rate limiting enabled
    
-   CORS properly configured
    
-   SQL injection protection (SQLAlchemy)
    
-   XSS prevention (Bleach)
    
-   CSRF protection for forms
    

## 🔧 Troubleshooting

### Common Issues

#### Database Connection Failed

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql
# Test connection
psql $DATABASE_URL
# Check connection limit
SELECT count(*) FROM pg_stat_activity;
```

#### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping
# Check memory usage
redis-cli INFO memory
# Clear cache if corrupted
python -c "from app.parser.nlp_processor import NLPProcessor; NLPProcessor().clear_cache()"
```

#### File Upload Fails

```bash
# Check disk space
df -h
# Check permissions
ls -la uploads/
# Check file size limit
grep MAX_FILE_SIZE_MB .env.production
```

#### High Memory Usage

```bash
# Check memory usage
htop
# Profile application
python -m memory_profiler run.py
# Limit worker count
export GUNICORN_WORKERS=2
```

#### Slow Response Times

```bash
# Check database indexes
psql -d resume_parser -c "\di"
# Analyze query performance
psql -d resume_parser -c "EXPLAIN ANALYZE SELECT * FROM resumes WHERE ..."
# Enable query logging
export SQLALCHEMY_ECHO=1
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
# Run with debugger
python run.py --debug
# Enable profiling
flask profile --help
```

### Log Analysis

```bash
# View recent errors
tail -100 logs/error.log
# Search for specific resume
grep "resume_id" logs/app.log
# Count request rates
cat logs/access.log | awk '{print $1}' | sort | uniq -c
# Analyze slow requests
awk '$NF > 1000' logs/access.log  # Requests > 1 second
```

## 🤝 Contributing

Contributions are welcomed. To contribute:
1.  Fork the repository
    
2.  Create a feature branch (`git checkout -b feature/amazing-feature`)
    
3.  Make changes with tests
    
4.  Run test suite (`pytest tests/`)
    
5.  Commit changes (`git commit -m 'Add amazing feature'`)
    
6.  Push to branch (`git push origin feature/amazing-feature`)
    
7.  Open Pull Request
    

### Code Standards

-   **Style**: Black code formatter
    
-   **Linting**: Flake8
    
-   **Types**: MyPy type checking
    
-   **Tests**: Pytest with 80%+ coverage
    
-   **Commits**: Conventional commits format
    

### Testing Guidelines

python

def test_parse_resume(client):
 """Test resume parsing endpoint."""
 with open('tests/fixtures/resume.pdf', 'rb') as f:
 response = client.post('/api/v1/parse', data={
 'file': (f, 'resume.pdf')
 }, headers={'X-API-Key': 'test_key'})
  
 assert response.status_code == 200
 assert 'name' in response.json
 assert 'skills' in response.json

## 📄 License

This project is licensed under the MIT License - see the `LICENSE`file for details.


    

    # Automated Resume Parser

A Python-based application that automatically extracts and analyzes information from resume documents (PDF and DOCX formats) using natural language processing.

## Features

- **Multiple Format Support**: Parse resumes in PDF and DOCX formats
- **Intelligent Information Extraction**: Extract key details including:
  - Candidate name
  - Email address
  - Phone number
  - Skills
- **Database Storage**: Automatically store parsed information in PostgreSQL database
- **RESTful API**: Simple API endpoint for resume parsing
- **Scalable Architecture**: Modular design for easy extensions and modifications

## Technology Stack

- **Backend**: Python 3.9+, Flask
- **Database**: PostgreSQL
- **NLP**: SpaCy
- **Document Processing**: PyPDF2, python-docx
- **Development Tools**: pytest, black, flake8

## Installation

1. Clone the repository:
```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download SpaCy model:
```bash
python -m spacy download en_core_web_sm
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

6. Initialize the database:
```bash
flask db upgrade
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Send a POST request to parse a resume:
```bash
curl -X POST -F "file=@/path/to/resume.pdf" http://localhost:5000/parse
```

### Example Response

```json
{
    "name": "John Doe",
    "email": "john.doe@email.com",
    "phone": "+1 123-456-7890",
    "skills": ["python", "java", "sql"]
}
```

## Project Structure

```
resume-parser/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── parser/
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   └── nlp_processor.py
│   └── utils.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Development

- Run tests:
```bash
pytest
```

- Format code:
```bash
black .
```

- Check code style:
```bash
flake8
```

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments

- SpaCy for providing excellent NLP capabilities
- PyPDF2 and python-docx for document parsing functionality

## Future Improvements

- Add support for more document formats
- Implement machine learning for better information extraction
- Add bulk processing capabilities
- Create a web interface for file uploads
- Enhance skills detection with industry-specific vocabularies
- Add export functionality to various formats
