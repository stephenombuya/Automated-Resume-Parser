# Logs Directory

This directory contains application logs for monitoring and debugging.

## Log Files

- `app.log` - Main application log
- `error.log` - Error-only log (rotated separately)
- `access.log` - API access logs (if configured)
- `parser.log` - Resume parser specific logs

## Log Rotation

Logs are automatically rotated when they reach 10MB, with up to 10 backup files kept.

## Monitoring

For production, consider forwarding logs to:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Datadog
- Splunk
- AWS CloudWatch

## Permissions

```bash
# Ensure application can write to logs
chmod 750 logs/
chown www-data:www-data logs/
```

### Log Levels
- DEBUG: Detailed debugging information
- INFO: General application flow
- WARNING: Non-critical issues
- ERROR: Errors that need attention
- CRITICAL: System-critical failures
