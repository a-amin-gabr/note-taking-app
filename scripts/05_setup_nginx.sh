#!/bin/bash
# =====================================================
# Step 5: Setup Nginx Reverse Proxy
# =====================================================

echo "========================================="
echo "Step 5: Setting Up Nginx"
echo "========================================="

NGINX_CONF="/etc/nginx/conf.d/notes-app.conf"

# Create Nginx config
echo "Writing Nginx configuration..."
sudo tee "$NGINX_CONF" > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /opt/note-taking-app/static;
    }
}
EOF

# Test and restart
echo "Testing Nginx configuration..."
sudo nginx -t
if [ $? -ne 0 ]; then
    echo "[ERROR] Nginx configuration test failed."
    exit 1
fi

sudo systemctl restart nginx
sudo systemctl enable nginx

echo "[OK] Nginx configured and running."
