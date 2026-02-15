#!/bin/bash
# =====================================================
# MariaDB Restore Script for Note-Taking App
# Restores from a backup in /backup
# Usage: sudo ./restore.sh [backup_file]
# If no file specified, lists available and prompts
# =====================================================

# Configuration
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

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Root check
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo ./restore.sh)"
    exit 1
fi

# Check backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    echo "[ERROR] Backup directory $BACKUP_DIR does not exist."
    exit 1
fi

# List available backups
list_backups() {
    echo ""
    echo "Available backups:"
    echo "-------------------------------------------"
    local i=1
    for f in $(ls -t "$BACKUP_DIR"/notes_backup_*.sql.gz 2>/dev/null); do
        local size=$(du -h "$f" | awk '{print $1}')
        local date=$(stat -c '%y' "$f" 2>/dev/null | cut -d'.' -f1)
        printf "  [%d] %s (%s) - %s\n" "$i" "$(basename "$f")" "$size" "$date"
        i=$((i + 1))
    done
    if [ $i -eq 1 ]; then
        echo "  No backups found in $BACKUP_DIR"
        exit 1
    fi
    echo "-------------------------------------------"
}

# If backup file provided as argument, use it
if [ -n "$1" ]; then
    BACKUP_FILE="$1"
    # If just a filename, prepend backup dir
    if [[ "$BACKUP_FILE" != /* ]]; then
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
    fi
else
    # Interactive mode: list and prompt
    list_backups

    BACKUPS=($(ls -t "$BACKUP_DIR"/notes_backup_*.sql.gz 2>/dev/null))
    TOTAL=${#BACKUPS[@]}

    echo ""
    read -p "Select backup number [1-${TOTAL}] (or 'q' to quit): " CHOICE

    if [ "$CHOICE" == "q" ] || [ "$CHOICE" == "Q" ]; then
        echo "Restore cancelled."
        exit 0
    fi

    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt "$TOTAL" ]; then
        echo "[ERROR] Invalid selection."
        exit 1
    fi

    BACKUP_FILE="${BACKUPS[$((CHOICE - 1))]}"
fi

# Validate file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo ""
echo "====================================================="
echo "  Database Restore"
echo "====================================================="
echo "  Backup:   $(basename "$BACKUP_FILE")"
echo "  Database: $DB_NAME"
echo "====================================================="
echo ""

# Confirmation
read -p "WARNING: This will overwrite the current database. Continue? (y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a safety backup before restoring
log_message "Creating safety backup before restore..."
SAFETY_FILE="${BACKUP_DIR}/pre_restore_${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$SAFETY_FILE" 2>> "$LOG_FILE"
if [ $? -eq 0 ]; then
    gzip "$SAFETY_FILE"
    log_message "Safety backup created: ${SAFETY_FILE}.gz"
else
    log_message "[WARN] Safety backup failed. Proceeding anyway..."
    rm -f "$SAFETY_FILE"
fi

# Decompress if gzipped
RESTORE_FILE="$BACKUP_FILE"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    log_message "Decompressing backup..."
    TEMP_FILE="/tmp/restore_$(date +%s).sql"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to decompress backup."
        rm -f "$TEMP_FILE"
        exit 1
    fi
    RESTORE_FILE="$TEMP_FILE"
fi

# Restore
log_message "Restoring database '$DB_NAME' from $(basename "$BACKUP_FILE")..."
mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$RESTORE_FILE" 2>> "$LOG_FILE"

if [ $? -eq 0 ]; then
    log_message "[OK] Database restored successfully."
    echo ""
    echo "====================================================="
    echo "  Restore Complete"
    echo "====================================================="
    echo "  Restored from: $(basename "$BACKUP_FILE")"
    echo "  Safety backup: $(basename "${SAFETY_FILE}.gz" 2>/dev/null)"
    echo "====================================================="
else
    log_message "[ERROR] Restore failed! Check credentials and backup file."
    echo ""
    echo "Restore failed. Your safety backup is at: ${SAFETY_FILE}.gz"
    echo "To roll back: sudo ./restore.sh ${SAFETY_FILE}.gz"
fi

# Cleanup temp file
if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
    rm -f "$TEMP_FILE"
fi
