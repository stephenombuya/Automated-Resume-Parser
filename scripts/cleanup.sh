# Cleanup old files script

set -e

echo "Cleaning up old uploads..."
find uploads -type f -mtime +1 -delete

echo "Cleaning up old logs..."
find logs -type f -name "*.log.*" -mtime +30 -delete

echo "Cleanup complete!"
