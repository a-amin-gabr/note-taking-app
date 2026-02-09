# 📝 Note-Taking Web App

A feature-rich Flask note-taking app with AWS Cognito authentication and guest mode.

## ✨ Features

| Core | Auth & Cloud |
|------|--------------|
| 📁 Categories | 🔐 AWS Cognito login |
| ✏️ Edit notes | 👻 Guest mode |
| 📌 Pin to top | 📎 S3 attachments |
| 🔍 Full-text search | 🔗 Share notes |
| 📝 Markdown support | |
| 🌓 Dark/Light themes | |
| 📦 Archive & restore | |
| 📤 Export JSON/TXT | |
| ⌨️ Keyboard shortcuts | |

## 🚀 Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Edit with your DB credentials

# Database
sudo mysql < schema.sql

# Run
python app.py
```

Visit `http://localhost:5000`

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+K` | Focus search |
| `Ctrl+T` | Toggle theme |
| `Ctrl+Enter` | Save note |
| `Esc` | Close modal |
| `?` | Show shortcuts |

## 🔐 AWS Cognito Setup (Optional)

1. Create a Cognito User Pool with Hosted UI
2. Add app client with callback URL: `http://localhost:5000/auth/cognito/callback`
3. Update `.env` with your Cognito settings

Without Cognito configured, users can still use **Guest Mode** with full functionality.

## 📁 Project Structure

```
├── app.py              # Main Flask app
├── auth.py             # Cognito & guest auth
├── schema.sql          # Database schema
├── requirements.txt    # Dependencies
├── .env.example        # Config template
├── templates/
│   ├── index.html      # Main dashboard
│   ├── login.html      # Login page
│   ├── categories.html # Manage categories
│   └── shared.html     # Public shared note
└── static/
    ├── style.css       # Themed styles
    └── app.js          # Client-side JS
```

## 🖥️ EC2 Deployment

See the full deployment guide for:

- RHEL 10 setup
- Systemd service configuration
- EBS backup volume setup
- Production Gunicorn config
