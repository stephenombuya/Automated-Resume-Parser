# Database backup script

set -e

BACKUP_DIR="/var/backups/resume-parser"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/resume_parser_$TIMESTAMP.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Load environment variables
source .env.production

# Backup database
echo "Backing up database to $BACKUP_FILE..."
pg_dump $DATABASE_URL > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Keep only last 30 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup complete: ${BACKUP_FILE}.gz"

# Optional: Upload to S3
# aws s3 cp ${BACKUP_FILE}.gz s3://your-backup-bucket/resume-parser/
