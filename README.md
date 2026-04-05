# Resume Parser API

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/Code%20Style-Black-000000?style=for-the-badge)](https://github.com/psf/black)

**A production-grade REST API for extracting structured candidate data from PDF and DOCX resumes using NLP and machine learning.**

[Quick Start](#-quick-start) · [API Docs](#-api-documentation) · [Architecture](#-architecture) · [Deployment](#-deployment) · [Contributing](#-contributing)

</div>

---

## Overview

Resume Parser API ingests resume files in multiple formats and returns clean, structured JSON — names, emails, phone numbers, skills, experience levels, and confidence scores. It's built for scale: async processing, Redis caching, horizontal scaling, and full observability out of the box.

---

## Features

### Core Parsing
- **Multi-format support** — PDF, DOCX, TXT, and RTF
- **NLP-powered extraction** — names, emails, phones, and skills via spaCy
- **Confidence scoring** — per-entity extraction confidence in every response
- **OCR fallback** — optional Tesseract OCR for scanned documents
- **Table extraction** — experimental support for tabular resume sections

### API & Infrastructure
- **RESTful design** — clean, versioned endpoints (`/api/v1/`)
- **Dual authentication** — API key (simple) or JWT tokens (stateless)
- **Rate limiting** — configurable per-endpoint via Redis
- **Cursor-based pagination** — efficient list traversal at scale
- **Webhooks** — async event notifications (`resume.parsed`, `resume.failed`)

### Production-Ready
- **Async processing** — background jobs via Redis + RQ
- **Prometheus metrics** — request rates, latency histograms, error counts
- **Structured logging** — JSON logs with Sentry integration
- **Soft deletes** — 30-day data recovery window
- **Health probes** — liveness and readiness endpoints for Kubernetes

---

## Table of Contents

- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Database Schema](#-database-schema)
- [Development](#-development)
- [Deployment](#-deployment)
- [Monitoring](#-monitoring)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

---

## ⚡ Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser

cp .env.example .env.production
# Edit .env.production with your secrets (see Configuration)

docker-compose up -d

curl http://localhost:5000/health
```

### Local Development

```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm

createdb resume_parser_dev
flask db upgrade

python run.py
```

### First API Call

```bash
# Parse a resume
curl -X POST http://localhost:5000/api/v1/parse \
  -H "X-API-Key: your_api_key" \
  -F "file=@/path/to/resume.pdf"

# Retrieve by ID
curl http://localhost:5000/api/v1/resume/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your_api_key"

# List with filters
curl "http://localhost:5000/api/v1/resumes?page=1&per_page=20&status=completed&search=python" \
  -H "X-API-Key: your_api_key"
```

---

## 🏗 Architecture

### System Overview

```
┌──────────┐     ┌─────────┐     ┌───────────┐     ┌─────────────┐
│  Client  │────▶│  Nginx  │────▶│ Gunicorn  │────▶│    Flask    │
│          │◀────│ (Proxy) │◀────│  (WSGI)   │◀────│ Application │
└──────────┘     └─────────┘     └───────────┘     └──────┬──────┘
                                                          │
                    ┌─────────────────────────────────────┤
                    │                                     │
             ┌──────▼──────┐                    ┌────────▼───────┐
             │  PostgreSQL │                    │     Redis      │
             │  (Primary   │                    │  (Cache/Queue/ │
             │   Store)    │                    │   Rate Limit)  │
             └─────────────┘                    └────────────────┘
                                                         │
                                                ┌────────▼───────┐
                                                │   AWS S3 /     │
                                                │  Local Storage │
                                                └────────────────┘
```

### Component Stack

| Layer | Technology | Purpose |
|---|---|---|
| Reverse Proxy | Nginx | SSL termination, load balancing |
| WSGI Server | Gunicorn + Gevent | Async Python workers |
| Framework | Flask 2.3+ | Application logic |
| Database | PostgreSQL 15+ | Primary store with JSONB |
| Cache / Queue | Redis 7+ | Rate limiting, sessions, jobs |
| NLP | spaCy | Entity extraction |
| Storage | AWS S3 / Local | File storage backend |
| Metrics | Prometheus + Grafana | Observability |
| Logging | ELK Stack / Sentry | Error tracking |

### Data Flow

```
Upload → Validation → Text Extraction → NLP Processing → Storage → Response
            │               │                 │
         (type, size,   (PDF/DOCX         (names,
          MIME, AV)      parsers)         emails,
                                          skills)
                                             │
                                    Optional: Webhook → External Service
```

---

## 📦 Installation

### System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 20.04 / macOS 11 / WSL2 | Ubuntu 22.04 LTS |
| Python | 3.11 | 3.12 |
| PostgreSQL | 15 | 15+ |
| Redis | 7 | 7+ |
| RAM | 2 GB | 4 GB+ |
| CPU | 2 cores | 4 cores |

### Step-by-Step

#### 1. Install System Dependencies

**Ubuntu / Debian**
```bash
sudo apt-get update && sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  postgresql-15 postgresql-contrib \
  redis-server \
  libpq-dev libmagic1 poppler-utils tesseract-ocr \
  nginx
```

**macOS**
```bash
brew install python@3.11 postgresql@15 redis poppler tesseract nginx
```

#### 2. Clone and Install

```bash
git clone https://github.com/stephenombuya/Automated-Resume-Parser
cd resume-parser

python -m venv venv && source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Configure PostgreSQL

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE resume_parser_prod;
CREATE USER resume_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE resume_parser_prod TO resume_user;
EOF

flask db upgrade
```

#### 4. Set Environment Variables

```bash
cp .env.example .env.production
# Edit .env.production — the four fields below are required
```

```bash
SECRET_KEY=<32+ character secret>
JWT_SECRET_KEY=<32+ character secret>
DATABASE_URL=postgresql://resume_user:password@localhost:5432/resume_parser_prod
ADMIN_PASSWORD=<strong password>
```

#### 5. Download NLP Models

```bash
python -m spacy download en_core_web_sm        # Fast, smaller model
python -m spacy download en_core_web_md        # Optional: higher accuracy
```

#### 6. Initialize

```bash
mkdir -p uploads logs temp
chmod 750 uploads logs temp

python run.py --check    # Health check
python run.py --seed     # Optional: seed with test data
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | 32+ char session secret |
| `JWT_SECRET_KEY` | ✅ | — | 32+ char JWT secret |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection URL |
| `ADMIN_PASSWORD` | ✅ | — | Admin interface password |
| `FLASK_ENV` | No | `development` | `development` / `production` / `testing` |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_FILE_SIZE_MB` | No | `10` | Upload size limit |
| `RATE_LIMIT_ENABLED` | No | `true` | Toggle rate limiting |
| `CORS_ALLOWED_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `SENTRY_DSN` | No | — | Sentry project DSN |

### Feature Flags

| Flag | Default | Description |
|---|---|---|
| `ENABLE_OCR` | `false` | OCR for scanned PDFs (Tesseract) |
| `ENABLE_ML_SKILLS_EXTRACTION` | `false` | ML-based skills extraction |
| `ENABLE_EMAIL_NOTIFICATIONS` | `false` | Email event notifications |
| `ENABLE_CACHING` | `true` | Redis response caching |
| `ENABLE_ASYNC_PROCESSING` | `false` | Background job processing |
| `ENABLE_BETA_API` | `false` | Beta endpoints |

### Config Files

| File | Purpose |
|---|---|
| `.env` | Local development |
| `.env.production` | Production secrets |
| `.env.testing` | Test environment |
| `gunicorn.conf.py` | WSGI worker settings |
| `nginx.conf` | Reverse proxy config |

---

## 📚 API Documentation

### Authentication

The API supports two authentication methods.

**API Key** — pass in the `X-API-Key` header:
```http
GET /api/v1/resumes
X-API-Key: your_api_key_here
```

**JWT Token** — exchange your API key for a short-lived Bearer token:
```http
POST /api/v1/auth/token
Content-Type: application/json

{"api_key": "your_api_key"}
```
```json
{"access_token": "eyJ...", "token_type": "Bearer"}
```
```http
GET /api/v1/resumes
Authorization: Bearer eyJ...
```

---

### `POST /api/v1/parse` — Parse a Resume

Upload a resume file and receive structured extraction results.

**Request**
```
Content-Type: multipart/form-data

file              (required) Resume file — PDF, DOCX, TXT, RTF
extract_tables    (bool, default: true)
extract_skills    (bool, default: true)
return_raw_text   (bool, default: false)
```

**Response `200 OK`**
```json
{
  "success": true,
  "resume_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "phone": "+1 (555) 987-6543",
  "skills": ["Python", "Docker", "PostgreSQL", "AWS"],
  "experience_level": "senior",
  "confidence_scores": {
    "persons": 0.94,
    "skills": 0.87
  },
  "metadata": {
    "filename": "resume_20240601_093012.pdf",
    "file_size_mb": 0.38,
    "pages": 2,
    "processing_time_ms": 1102
  }
}
```

---

### `GET /api/v1/resume/{id}` — Get a Resume

```http
GET /api/v1/resume/550e8400-e29b-41d4-a716-446655440000
```

**Query Parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `include_sensitive` | bool | `false` | Include PII fields in response |

**Response `200 OK`**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "candidate_name": "Jane Smith",
  "email": "jane.smith@example.com",
  "skills": ["Python", "Docker"],
  "status": "completed",
  "created_at": "2024-06-01T09:30:12Z"
}
```

---

### `GET /api/v1/resumes` — List Resumes

```http
GET /api/v1/resumes?page=1&per_page=20&status=completed&search=python+developer
```

**Query Parameters**

| Param | Type | Description |
|---|---|---|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Results per page (default: 20, max: 100) |
| `status` | string | Filter by `pending` / `completed` / `failed` |
| `search` | string | Full-text search across name, skills |

**Response `200 OK`**
```json
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
```

---

### `DELETE /api/v1/resume/{id}` — Delete a Resume

Soft-deletes the record (recoverable for 30 days).

```json
{"success": true, "message": "Resume deleted successfully"}
```

---

### `GET /api/v1/stats` — Statistics

```json
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
```

---

### Webhooks

Register a URL to receive async event notifications:

```http
POST /webhook/register
Content-Type: application/json

{
  "url": "https://your-app.com/webhook",
  "events": ["resume.parsed", "resume.failed"],
  "secret": "your_webhook_secret"
}
```

---

## 🗄 Database Schema

### `resumes` Table

| Column | Type | Description |
|---|---|---|
| `id` | Integer | Auto-increment primary key |
| `uuid` | UUID | Public-facing identifier |
| `filename` | String(512) | Original upload filename |
| `candidate_name` | String(512) | Extracted name |
| `email` | String(255) | Extracted email |
| `phone` | String(50) | Extracted phone number |
| `skills` | JSONB | Array of extracted skills |
| `experience` | JSONB | Work experience entries |
| `education` | JSONB | Education entries |
| `status` | Enum | `pending` / `completed` / `failed` |
| `match_score` | Float | Overall score (0–100) |
| `created_at` | DateTime | Creation timestamp |
| `deleted_at` | DateTime | Soft delete timestamp |

### Indexes

```sql
-- Query performance
CREATE INDEX idx_resume_status_created  ON resumes(status, created_at);
CREATE INDEX idx_resume_candidate_email ON resumes(candidate_name, email);

-- JSONB skills queries
CREATE INDEX idx_resume_skills_gin      ON resumes USING gin(skills);

-- Full-text search
CREATE INDEX idx_resume_search_vector   ON resumes USING gin(search_vector);
```

---

## 💻 Development

### Project Structure

```
resume-parser/
├── app/
│   ├── api/            # Public API endpoints
│   ├── admin/          # Admin interface
│   ├── webhook/        # Webhook handlers
│   ├── parser/
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   └── nlp_processor.py
│   ├── models.py       # SQLAlchemy models
│   ├── config.py       # Configuration classes
│   └── utils.py        # Shared utilities
├── migrations/         # Alembic migrations
├── tests/              # Unit and integration tests
├── scripts/            # Utility scripts
├── uploads/            # Temporary file storage
├── logs/               # Application logs
├── requirements.txt
├── run.py              # Development server
├── wsgi.py             # Production WSGI entry
└── docker-compose.yml
```

### Running Tests

```bash
pytest tests/ -v                                   # All tests
pytest tests/ --cov=app --cov-report=html          # With coverage report
pytest tests/test_api.py -v                        # Single file
pytest -v --log-cli-level=INFO                     # Verbose with logging
```

### Code Quality

```bash
black app/ tests/       # Format
flake8 app/ tests/      # Lint
mypy app/               # Type checking
bandit -r app/          # Security scan
```

### Database Migrations

```bash
flask db migrate -m "Description of changes"   # Create
flask db upgrade                               # Apply
flask db downgrade                             # Rollback last
flask db history                               # View history
```

### Writing Tests

```python
def test_parse_resume(client):
    """POST /api/v1/parse returns structured extraction."""
    with open("tests/fixtures/resume.pdf", "rb") as f:
        response = client.post(
            "/api/v1/parse",
            data={"file": (f, "resume.pdf")},
            headers={"X-API-Key": "test_key"},
        )

    assert response.status_code == 200
    assert "name" in response.json
    assert "skills" in response.json
```

---

## 🚢 Deployment

### Docker (Recommended)

```bash
docker build -t resume-parser:latest .

docker-compose up -d
```

Or run standalone:

```bash
docker run -d \
  --name resume-parser \
  -p 5000:5000 \
  -e FLASK_ENV=production \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  resume-parser:latest
```

### Manual (Ubuntu 20.04+)

```bash
# 1. Create application user
sudo useradd -r -s /bin/bash resume-parser
sudo mkdir -p /var/www/resume-parser
sudo chown resume-parser:resume-parser /var/www/resume-parser

# 2. Deploy code
git clone https://github.com/stephenombuya/Automated-Resume-Parser /var/www/resume-parser
cd /var/www/resume-parser
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**`/etc/systemd/system/resume-parser.service`**
```ini
[Unit]
Description=Resume Parser
After=network.target postgresql.service redis.service

[Service]
User=resume-parser
WorkingDirectory=/var/www/resume-parser
EnvironmentFile=/var/www/resume-parser/.env.production
ExecStart=/var/www/resume-parser/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now resume-parser
```

**Nginx `/etc/nginx/sites-available/resume-parser`**
```nginx
server {
    listen 80;
    server_name api.resumeparser.com;

    client_max_body_size 15M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/resume-parser /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

### Kubernetes

```yaml
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
            requests: { memory: "512Mi", cpu: "250m" }
            limits:   { memory: "1Gi",   cpu: "500m" }
          livenessProbe:
            httpGet: { path: /health/live,  port: 5000 }
          readinessProbe:
            httpGet: { path: /health/ready, port: 5000 }
```

### Deployment Checklist

- [ ] All secrets in environment variables (not in code)
- [ ] `flask db upgrade` applied to production database
- [ ] SSL certificate installed and HTTPS enforced
- [ ] Firewall rules configured (80/443 only)
- [ ] `CORS_ALLOWED_ORIGINS` restricted to known domains
- [ ] Rate limiting enabled
- [ ] Prometheus + Grafana dashboards configured
- [ ] Log aggregation set up (ELK / CloudWatch / Loki)
- [ ] Backup strategy implemented and tested
- [ ] Health check endpoints verified
- [ ] Sentry DSN configured for error tracking

---

## 📊 Monitoring

### Health Endpoints

```bash
curl http://localhost:5000/health          # Basic
curl http://localhost:5000/health/ready    # Kubernetes readiness
curl http://localhost:5000/health/live     # Kubernetes liveness
curl http://localhost:5000/metrics         # Prometheus scrape
```

### Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Total HTTP requests by status |
| `http_request_duration_seconds` | Histogram | Request latency |
| `resume_parsed_total` | Counter | Total resumes successfully parsed |
| `resume_parsing_errors_total` | Counter | Parse failures |
| `active_uploads` | Gauge | Uploads currently in progress |
| `database_connections` | Gauge | Active PostgreSQL connections |
| `redis_connections` | Gauge | Active Redis connections |

### Recommended Alerts

```yaml
groups:
  - name: resume-parser
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        annotations:
          summary: "5xx error rate above 5%"

      - alert: SlowResponses
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        annotations:
          summary: "p95 latency exceeds 1 second"

      - alert: DatabaseDown
        expr: pg_up == 0
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL unreachable"
```

### Log Files

Logs are written to `/var/log/resume-parser/` with daily rotation:

| File | Contents |
|---|---|
| `app.log` | All application events (JSON in production) |
| `error.log` | Errors and exceptions only |
| `access.log` | Per-request access log |

```bash
# Useful one-liners
tail -f logs/error.log
grep "resume_id" logs/app.log | tail -50
awk '$NF > 1000' logs/access.log       # Requests slower than 1s
```

---

## 🔒 Security

### Security Headers

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

### Authentication & Access

- **API Keys** — revocable, with granular permission scopes
- **JWT Tokens** — short-lived (15 min) with refresh capability
- **IP Whitelisting** — restrict admin endpoints to trusted ranges
- **Rate Limiting** — per-IP and per-key, configurable per route

### Data Protection

- **TLS 1.2+** — enforced for all inbound and database connections
- **bcrypt / scrypt** — password hashing
- **PII redaction** — sensitive fields stripped from logs
- **Soft deletes** — records recoverable for 30 days before hard purge

### Security Checklist

- [ ] No secrets committed to version control
- [ ] HTTPS enforced (redirect HTTP → HTTPS)
- [ ] Database connections use TLS
- [ ] Uploaded files scanned for malware (ClamAV or similar)
- [ ] Rate limiting enabled on all public endpoints
- [ ] CORS `Access-Control-Allow-Origin` restricted to known origins
- [ ] SQL injection prevented by SQLAlchemy ORM (no raw queries)
- [ ] XSS inputs sanitized with Bleach
- [ ] CSRF protection enabled for any form-based routes
- [ ] Regular dependency updates (`pip-audit`, Dependabot)

---

## 🔧 Troubleshooting

### Database Connection Errors

```bash
sudo systemctl status postgresql
psql $DATABASE_URL -c "SELECT 1"
SELECT count(*) FROM pg_stat_activity;   # Check connection limit
```

### Redis Connection Errors

```bash
redis-cli ping
redis-cli INFO memory
```

### File Upload Failures

```bash
df -h                                   # Check disk space
ls -la uploads/                         # Check directory permissions
grep MAX_FILE_SIZE_MB .env.production   # Verify size limit
```

### High Memory Usage

```bash
htop
python -m memory_profiler run.py
export GUNICORN_WORKERS=2               # Reduce worker count
```

### Slow Responses

```bash
# Check indexes
psql -d resume_parser -c "\di"

# Query plan analysis
psql -d resume_parser -c "EXPLAIN ANALYZE SELECT * FROM resumes WHERE status = 'completed';"

# Enable query logging temporarily
export SQLALCHEMY_ECHO=1
```

### Debug Mode

```bash
export LOG_LEVEL=DEBUG
python run.py --debug
```

---

## 🤝 Contributing

Contributions are welcome! Please follow this workflow:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Write tests** for your changes
4. **Pass** the full test suite: `pytest tests/`
5. **Format** code: `black app/ tests/`
6. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/): `git commit -m 'feat: add bulk parsing endpoint'`
7. **Push** and open a Pull Request

### Code Standards

| Tool | Purpose | Command |
|---|---|---|
| Black | Formatting | `black app/ tests/` |
| Flake8 | Linting | `flake8 app/ tests/` |
| MyPy | Type checking | `mypy app/` |
| Bandit | Security scanning | `bandit -r app/` |
| Pytest | Testing (80%+ coverage required) | `pytest tests/ --cov=app` |

---

## 🗺 Roadmap

- [ ] Bulk upload endpoint (ZIP of resumes)
- [ ] Web UI for file uploads and result browsing
- [ ] Additional format support (RTF, HTML resumes)
- [ ] Industry-specific skills vocabularies
- [ ] Export to CSV / XLSX
- [ ] Enhanced ML-based experience classification
- [ ] Multi-language NLP support

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
