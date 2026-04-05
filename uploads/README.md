# Uploads Directory

This directory stores temporary uploaded resume files during processing.

## Security Notes

- Files are automatically deleted after processing
- Do not store sensitive files here permanently
- Ensure proper permissions: `chmod 750 uploads/`
- The directory should not be publicly accessible

## Directory Structure

```
uploads/
├── temp/ # Temporary files during processing
├── processed/ # Processed files (optional, if you want to keep)
└── failed/ # Failed uploads for debugging
```


## Cleanup

Files older than 24 hours are automatically cleaned up by the system.

## Permissions

```bash
# Set proper permissions
chmod 750 uploads/
chown www-data:www-data uploads/
```
