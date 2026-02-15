#!/bin/bash
# =====================================================
# Step 2: Setup MariaDB Database
# =====================================================

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"

# Load .env if exists
if [ -f "${APP_DIR}/.env" ]; then
    export $(grep -v '^#' "${APP_DIR}/.env" | xargs)
fi

DB_NAME="${DB_NAME:-notes_db}"
DB_USER="${DB_USER:-notes_user}"
DB_PASSWORD="${DB_PASSWORD:-secure_password}"

echo "========================================="
echo "Step 2: Setting Up MariaDB"
echo "========================================="

# Start and enable MariaDB
echo "Starting MariaDB..."
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Create database and user
echo "Creating database '$DB_NAME' and user '$DB_USER'..."
sudo mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOF

if [ $? -eq 0 ]; then
    echo "[OK] Database setup complete."
else
    echo "[ERROR] Database setup failed."
    exit 1
fi

# Import schema if it exists
if [ -f "${APP_DIR}/schema.sql" ]; then
    echo "Importing database schema..."
    sudo mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "${APP_DIR}/schema.sql"
    echo "[OK] Schema imported."
fi
