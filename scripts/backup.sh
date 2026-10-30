#!/bin/bash
# Morning Intelligence Assistant - Backup Script
# Run this via cron for regular backups

set -e

# Configuration
APP_DIR="$HOME/morning-intelligence"
BACKUP_DIR="$APP_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $(date)"

# Backup PostgreSQL database
echo "Backing up PostgreSQL database..."
docker compose -f "$APP_DIR/docker-compose.yml" exec -T db pg_dump -U morning_user morning_intel | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Backup application data
echo "Backing up application data..."
tar -czf "$BACKUP_DIR/app_data_$DATE.tar.gz" -C "$APP_DIR" data logs config/.env

# Backup logs (last 7 days)
echo "Backing up recent logs..."
find "$APP_DIR/logs" -name "*.log" -mtime -7 -exec tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" {} + 2>/dev/null || true

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Show backup sizes
echo "Backup completed. Current backups:"
ls -lh "$BACKUP_DIR"

echo "Backup finished at $(date)"