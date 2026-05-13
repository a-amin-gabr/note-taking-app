# Note-Taking Web App

A full-stack note-taking application built with **Flask**, **MariaDB**, and **AWS services**. Features user authentication via AWS Cognito (with guest mode fallback), S3 file attachments, Markdown rendering, and a complete modular deployment system for RHEL 10 on EC2.

**Live Demo:** [notes.abdallahgabr.me](https://notes.abdallahgabr.me/)

---

## Features

### Notes

- Create, edit, and delete notes with titles and rich content
- **Markdown support** with live preview (headings, lists, code blocks, tables, etc.)
- **Pin** important notes to the top of the dashboard
- **Archive** and restore notes
- **Full-text search** across titles and content
- **Categories** with custom colors for organization

### Sharing & Export

- Generate **public share links** with unique tokens
- **Export** all notes as JSON or plain text
- **Import** notes from JSON or TXT files

### File Attachments

- Upload files to notes via **AWS S3** or local storage fallback
- Image preview with click-to-view
- Attachment management per note

### User Profiles

- Display name, bio, and avatar uploads
- Timezone preferences
- Profile completion tracking

### Authentication

- **AWS Cognito** login with hosted UI
- **Guest mode** — full functionality without an account
- Session-based authentication

### UI/UX

- **Dark/Light theme** toggle with persistence
- **Keyboard shortcuts** for power users
- Responsive design for desktop and mobile
- Custom branding with app logo and favicon

---

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| Backend | Python 3 / Flask |
| Database | MariaDB (MySQL-compatible) |
| Auth | AWS Cognito + Guest mode |
| Storage | AWS S3 (optional, local fallback) |
| Server | Gunicorn + Nginx |
| OS | RHEL 10 on AWS EC2 |
| Backup | Cron + mysqldump to EBS volume |

---

## Quick Start

### Prerequisites

- Python 3.9+
- MariaDB or MySQL
- (Optional) AWS account for Cognito and S3

### Setup

```bash
git clone https://github.com/a-amin-gabr/note-taking-app.git
cd note-taking-app

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Edit with your credentials
sudo mysql < schema.sql

python app.py
```

Visit `http://localhost:5000`

---

## Configuration

All settings are managed via the `.env` file:

```env
# Required
SECRET_KEY=your-secret-key
DB_HOST=localhost
DB_USER=notes_user
DB_PASSWORD=notes_password
DB_NAME=notes_db

# Optional - AWS Cognito
COGNITO_USER_POOL_ID=
COGNITO_CLIENT_ID=
COGNITO_CLIENT_SECRET=
COGNITO_DOMAIN=

# Optional - S3 for file attachments
S3_BUCKET_NAME=
AWS_REGION=us-east-1
```

Without Cognito configured, users can still use **Guest Mode** with full functionality.

---

## Keyboard Shortcuts

| Key | Action |
| --- | ------ |
| `Ctrl+K` | Focus search |
| `Ctrl+T` | Toggle theme |
| `Ctrl+Enter` | Save note |
| `Esc` | Close modal |
| `?` | Show shortcuts help |

---

## Database Schema

Four tables with full referential integrity:

```
users ──────< categories
  │
  └────────< notes ──────< attachments
               │
               └── category_id (FK, SET NULL on delete)
```

| Table | Purpose |
| ----- | ------- |
| `users` | Cognito and guest accounts, profile data |
| `categories` | Per-user note categories with color |
| `notes` | Note content, pin/archive/share state, full-text index |
| `attachments` | S3 file references linked to notes |

A database trigger auto-creates default categories (Personal, Work, Ideas) for new users.

---

## API Endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET | `/` | Dashboard with notes list |
| POST | `/add` | Create a new note |
| POST | `/edit/<id>` | Update a note |
| POST | `/delete/<id>` | Delete a note |
| POST | `/pin/<id>` | Toggle pin status |
| POST | `/archive/<id>` | Toggle archive status |
| GET | `/api/note/<id>` | Get note details (JSON) |
| POST | `/api/note/<id>/share` | Generate share link |
| POST | `/api/note/<id>/unshare` | Disable sharing |
| GET | `/shared/<token>` | View shared note (public) |
| POST | `/note/<id>/attach` | Upload attachment |
| POST | `/note/<id>/attachment/<aid>/delete` | Delete attachment |
| GET | `/categories` | Manage categories |
| POST | `/category/delete/<id>` | Delete a category |
| GET | `/export` | Export notes (JSON/TXT) |
| POST | `/import` | Import notes |
| GET | `/api/stats` | User statistics (JSON) |
| POST | `/api/preview-markdown` | Render markdown to HTML |
| GET/POST | `/profile` | View/update profile |
| POST | `/profile/avatar` | Upload avatar |

---

## Project Structure

```
note-taking-app/
├── app.py                   # Main Flask application (routes, API, logic)
├── auth.py                  # AWS Cognito & guest authentication
├── schema.sql               # Database schema (4 tables + trigger)
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── notes-app.service        # Systemd unit file for Gunicorn
│
├── templates/
│   ├── index.html           # Main dashboard (notes list, modals)
│   ├── login.html           # Login page (Cognito + guest)
│   ├── profile.html         # User profile management
│   ├── categories.html      # Category management
│   └── shared.html          # Public shared note view
│
├── static/
│   ├── style.css            # Main stylesheet (themes, layout)
│   ├── app.js               # Client-side logic (modals, search, shortcuts)
│   ├── icons.css             # Icon definitions
│   ├── attachment-styles.css # Attachment UI styles
│   └── images/
│       └── logo.png         # App logo and favicon
│
├── deployments/             # DevOps Journey (Server-Based)
│   └── 01_bash_scripts/     # Stage 1: Bash deployment
│       ├── deploy.sh        # Master deployment script
│       ├── backup.sh        # Daily MariaDB backup (cron)
│       ├── restore.sh       # Restore from backup (interactive)
│       ├── notes-app.service# Systemd unit file for Gunicorn
│       ├── DEPLOYMENT.md    # Full deployment guide
│       └── scripts/         # Individual setup steps
│   ├── 02_ansible/          # Stage 2: Ansible automation
│   │   ├── deploy.yml       # Master playbook
│   │   ├── roles/           # Ansible roles
│   │   └── vars/            # Variables and Vault
│   └── 03_docker/           # Stage 3: Containerization
│       ├── Dockerfile       # Multi-stage build
│       ├── docker-compose.yml # 3-service orchestration
│       └── nginx/           # Nginx reverse proxy configs
│
├── serverless/              # Stage 4: Fully Serverless (Terraform)
│   ├── app/                 # Lambda application (DynamoDB)
│   ├── terraform/           # Modular IaC (5 modules)
│   └── scripts/             # Deploy helpers
│
├── README.md                # This file
```

---

## Deployment (EC2 / RHEL 10)

### One-Command Deploy

```bash
sudo ./deployments/01_bash_scripts/deploy.sh /dev/nvme1n1
```

This runs 7 setup steps automatically: system deps, MariaDB, app setup, Gunicorn, Nginx, EBS volume, and cron backup.

### Step-by-Step

Run individual scripts for granular control:

```bash
sudo bash deployments/01_bash_scripts/scripts/01_install_deps.sh
sudo bash deployments/01_bash_scripts/scripts/02_setup_db.sh
sudo bash deployments/01_bash_scripts/scripts/03_setup_app.sh
sudo bash deployments/01_bash_scripts/scripts/04_setup_service.sh
sudo bash deployments/01_bash_scripts/scripts/05_setup_nginx.sh
sudo bash deployments/01_bash_scripts/scripts/06_prepare_volume.sh /dev/nvme1n1
sudo bash deployments/01_bash_scripts/scripts/07_setup_backup.sh
```

See [deployments/01_bash_scripts/README.md](deployments/01_bash_scripts/README.md) for the full guide.

---

## Deployment (Ansible)

**Stage 2:** Full infrastructure-as-code automation.

```bash
cd deployments/02_ansible
ansible-playbook deploy.yml --ask-vault-pass
```

See [deployments/02_ansible/README.md](deployments/02_ansible/README.md) for details.

---

## Deployment (Docker)

**Stage 3:** Containerized application environment using Docker Compose.

```bash
cd deployments/03_docker
cp .env.example .env
docker compose up -d --build
```

See [deployments/03_docker/README.md](deployments/03_docker/README.md) for architecture and scaling details.

---

## Deployment (Serverless + Terraform)

**Stage 4:** Fully serverless — Lambda, DynamoDB, CloudFront, API Gateway. Zero servers, ~$0.50/month.

```bash
cd serverless/scripts
./deploy.sh
```

The serverless deploy script accepts `TF_STATE_BUCKET`, `TF_STATE_KEY`, and `TF_STATE_REGION` for Terraform backend setup. See [serverless/README.md](serverless/README.md) for the full architecture, bootstrap steps, and module breakdown.

---

## Backup & Restore

### Automated Backup

- Runs daily at **2:00 AM** via cron
- MariaDB dump compressed with gzip
- Stored on a dedicated EBS volume at `/backup`
- Auto-deletes backups older than 7 days
- Logs to `backup.log`

### Manual Backup

```bash
sudo ./deployments/01_bash_scripts/backup.sh
```

### Restore

```bash
# Interactive - lists available backups, pick by number
sudo ./deployments/01_bash_scripts/restore.sh

# Direct - specify a backup file
sudo ./deployments/01_bash_scripts/restore.sh notes_backup_20260215_020000.sql.gz
```

The restore script creates a **safety backup** before overwriting the database.

---

## License

This project is part of a DevOps portfolio demonstrating full-stack development, AWS integration, and production deployment automation.
