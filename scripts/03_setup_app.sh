#!/bin/bash
# =====================================================
# Step 3: Setup Application (venv, pip, .env)
# =====================================================

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"

echo "========================================="
echo "Step 3: Setting Up Application"
echo "========================================="

cd "$APP_DIR"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[WARN] Created .env from .env.example -- please edit it with your credentials."
    else
        echo "[WARN] No .env.example found. Please create .env manually."
    fi
else
    echo ".env already exists."
fi

echo "[OK] Application setup complete."
