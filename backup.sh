#!/bin/bash
# =====================================================
# MariaDB Backup Script for Note-Taking App
# Run via cron: 0 2 * * * /path/to/backup.sh
# =====================================================

# Configuration
# Dynamic directory detection
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_DIR="${SCRIPT_DIR}"
BACKUP_DIR="/backup"
LOG_FILE="${APP_DIR}/backup.log"

# Load settings from .env if it exists
if [ -f "${APP_DIR}/.env" ]; then
    export $(grep -v '^#' "${APP_DIR}/.env" | xargs)
fi

DB_NAME="${DB_NAME:-notes_db}"
DB_USER="${DB_USER:-notes_user}"
DB_PASSWORD="${DB_PASSWORD:-your_password_here}"
RETENTION_DAYS=7

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    log_message "Error: Backup directory $BACKUP_DIR does not exist! attempting to create..."
    mkdir -p "$BACKUP_DIR"
    if [ $? -ne 0 ]; then
        log_message "Error: Failed to create backup directory. Check permissions."
        exit 1
    fi
fi

# Create timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/notes_backup_${TIMESTAMP}.sql"

# Perform backup
log_message "Starting backup for database: $DB_NAME"
mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$BACKUP_FILE" 2>> "$LOG_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    log_message "Backup successful: $BACKUP_FILE"
    
    # Compress the backup
    gzip "$BACKUP_FILE"
    if [ $? -eq 0 ]; then
        log_message "Compressed to: ${BACKUP_FILE}.gz"
    else
        log_message "Warning: Gzip compression failed."
    fi
    
    # Remove old backups (older than RETENTION_DAYS)
    log_message "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "notes_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    
    log_message "Backup process completed successfully."
else
    log_message "Error: Backup failed! Check MySQL credentials and permissions."
    # Clean up empty file if dump failed
    if [ -f "$BACKUP_FILE" ]; then
        rm "$BACKUP_FILE"
    fi
    exit 1
fi
