#!/bin/bash
# =====================================================
# Step 1: Install System Dependencies
# =====================================================

echo "========================================="
echo "Step 1: Installing System Dependencies"
echo "========================================="

# Update system
echo "Updating system packages..."
sudo dnf update -y

# Install required packages
echo "Installing dependencies..."
sudo dnf install -y \
    git \
    python3-pip \
    python3-devel \
    mysql-devel \
    gcc \
    nginx \
    mariadb-server

echo "[OK] System dependencies installed."
