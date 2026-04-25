# 🚀 Deployment Guide: Note-Taking App on RHEL 10

Deploy the Note-Taking Application on AWS EC2 (RHEL 10) with **one command** or step-by-step.

## Prerequisites

- **EC2 Instance**: t2.micro or t3.micro (RHEL 10 AMI)
- **Security Group**: Allow SSH (22), HTTP (80), HTTPS (443)
- **EBS Volume**: Additional volume for backups (e.g., `/dev/nvme1n1`)

---

## Quick Deploy (One Command)

```bash
git clone https://github.com/a-amin-gabr/note-taking-app.git /opt/note-taking-app
cd /opt/note-taking-app
sudo ./deploy.sh /dev/nvme1n1
```

This runs all 7 steps automatically. Edit `.env` with your credentials afterwards.

---

## Step-by-Step (Manual)

Each step is a standalone script in `scripts/`. Run individually if needed:

| Script | What It Does |
| ------ | ------------ |
| `scripts/01_install_deps.sh` | System packages (git, python3, nginx, mariadb, etc.) |
| `scripts/02_setup_db.sh` | Start MariaDB, create database & user, import schema |
| `scripts/03_setup_app.sh` | Python venv, pip install, `.env` setup |
| `scripts/04_setup_service.sh` | Copy `notes-app.service` to systemd, start & enable |
| `scripts/05_setup_nginx.sh` | Write Nginx reverse proxy config, restart |
| `scripts/06_prepare_volume.sh` | Format, mount, persist EBS volume as `/backup` |
| `scripts/07_setup_backup.sh` | Set permissions, add daily cron job (2:00 AM) |

Run any step individually:

```bash
sudo bash scripts/01_install_deps.sh
```

---

## Project Structure

```
├── deploy.sh               # Master deployment script
├── backup.sh               # Daily backup (runs via cron)
├── notes-app.service        # Systemd unit file
├── scripts/
│   ├── 01_install_deps.sh   # System dependencies
│   ├── 02_setup_db.sh       # MariaDB setup
│   ├── 03_setup_app.sh      # App setup (venv, pip)
│   ├── 04_setup_service.sh  # Gunicorn systemd service
│   ├── 05_setup_nginx.sh    # Nginx reverse proxy
│   ├── 06_prepare_volume.sh # EBS volume → /backup
│   └── 07_setup_backup.sh   # Cron job for daily backups
├── app.py                   # Flask application
├── auth.py                  # Authentication module
├── schema.sql               # Database schema
└── requirements.txt         # Python dependencies
```

## Troubleshooting

| Issue | Command |
| ----- | ------- |
| App logs | `journalctl -u notes-app` |
| Nginx errors | `cat /var/log/nginx/error.log` |
| Backup logs | `cat /opt/note-taking-app/backup.log` |
| Service status | `sudo systemctl status notes-app` |
| Test backup | `sudo ./backup.sh && ls -la /backup/` |
