#!/bin/bash
# =====================================================
# Master Deployment Script
# Runs all setup steps in order
# Usage: sudo ./deploy.sh [backup_device]
# Example: sudo ./deploy.sh /dev/nvme1n1
# =====================================================

set -e  # Exit on first error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
BACKUP_DEVICE="${1:-/dev/nvme1n1}"

# Root check
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root: sudo ./deploy.sh"
    exit 1
fi

echo "====================================================="
echo "  Note-Taking App - Full Deployment"
echo "  $(date)"
echo "====================================================="
echo ""

# Make all scripts executable
chmod +x "${SCRIPTS_DIR}"/*.sh
chmod +x "${SCRIPT_DIR}/backup.sh"

# Step 1: System Dependencies
bash "${SCRIPTS_DIR}/01_install_deps.sh"
echo ""

# Step 2: Database Setup
bash "${SCRIPTS_DIR}/02_setup_db.sh"
echo ""

# Step 3: Application Setup
bash "${SCRIPTS_DIR}/03_setup_app.sh"
echo ""

# Step 4: Systemd Service
bash "${SCRIPTS_DIR}/04_setup_service.sh"
echo ""

# Step 5: Nginx
bash "${SCRIPTS_DIR}/05_setup_nginx.sh"
echo ""

# Step 6: Backup Volume
bash "${SCRIPTS_DIR}/06_prepare_volume.sh" "$BACKUP_DEVICE"
echo ""

# Step 7: Automated Backup
bash "${SCRIPTS_DIR}/07_setup_backup.sh"
echo ""

echo "====================================================="
echo "  Deployment Complete!"
echo "====================================================="
echo ""
echo "  App:     http://$(hostname -I | awk '{print $1}')"
echo "  Service: sudo systemctl status notes-app"
echo "  Logs:    journalctl -u notes-app"
echo "  Backup:  ls -la /backup/"
echo ""
echo "  Next: Edit .env with your credentials if needed."
echo "====================================================="
