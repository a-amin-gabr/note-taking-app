#!/bin/bash
# =====================================================
# Step 4: Setup Systemd Service (Gunicorn)
# =====================================================

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
SERVICE_FILE="${APP_DIR}/notes-app.service"

echo "========================================="
echo "Step 4: Setting Up Systemd Service"
echo "========================================="

if [ ! -f "$SERVICE_FILE" ]; then
    echo "[ERROR] Service file not found: $SERVICE_FILE"
    exit 1
fi

# Copy service file to systemd
echo "Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/notes-app.service

# Reload and start
sudo systemctl daemon-reload
sudo systemctl start notes-app
sudo systemctl enable notes-app

# Verify
if sudo systemctl is-active --quiet notes-app; then
    echo "[OK] notes-app service is running."
else
    echo "[ERROR] notes-app service failed to start."
    sudo journalctl -u notes-app --no-pager -n 20
    exit 1
fi
