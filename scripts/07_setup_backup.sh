#!/bin/bash
# =====================================================
# Step 7: Setup Automated Backup (Cron)
# =====================================================

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
BACKUP_SCRIPT="${APP_DIR}/backup.sh"
BACKUP_DIR="/backup"
CRON_SCHEDULE="0 2 * * *"

echo "========================================="
echo "Step 7: Setting Up Automated Backup"
echo "========================================="

# Make backup script executable
chmod +x "$BACKUP_SCRIPT"
echo "Made $BACKUP_SCRIPT executable."

# Create backup directory if not exists
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
fi

# Set permissions
TARGET_USER="ec2-user"
if id "$TARGET_USER" &>/dev/null; then
    chown -R "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"
    chown "$TARGET_USER:$TARGET_USER" "$BACKUP_SCRIPT"
fi

# Setup cron job
CRON_CMD="$BACKUP_SCRIPT >> ${APP_DIR}/backup.log 2>&1"
(crontab -l 2>/dev/null | grep -F "$BACKUP_SCRIPT") && echo "Cron job already exists." || {
    (crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -
    echo "Cron job added: daily at 2:00 AM"
}

echo "[OK] Automated backup configured."
echo "   Logs: ${APP_DIR}/backup.log"
