# Docker Deployment — Stage 3

Deploys the Note-Taking App as a **3-container architecture** using Docker Compose: Flask + Gunicorn, MariaDB, and Nginx.

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)

## Quick Start

**1. Create your `.env` file:**

```bash
cd deployments/03_docker
cp .env.example .env
# Edit .env with your actual secrets
```

**2. Build and launch:**

```bash
docker compose up -d --build
```

**3. Verify:**

```bash
docker compose ps         # All 3 containers should be "Up (healthy)"
docker compose logs app   # Check Flask startup
```

Visit **http://localhost** — the app is live!

## Architecture

```
┌─────────────┐     ┌─────────────┐      ┌─────────────┐
│    Nginx    │────▶│  Flask App  │────▶│   MariaDB   │
│  (Port 80)  │     │ (Port 5000) │      │ (Port 3306) │
└─────────────┘     └─────────────┘      └─────────────┘
     web                 app                   db
```

- **Nginx** handles external traffic on port 80/443 and proxies to the Flask container.
- **Flask + Gunicorn** runs the application logic.
- **MariaDB** stores all data, auto-initialized from `schema.sql` on first run.

## Common Commands

| Command | Description |
| ------- | ----------- |
| `docker compose up -d --build` | Build images and start all services |
| `docker compose down` | Stop and remove containers |
| `docker compose down -v` | Stop and **delete all data** (volumes) |
| `docker compose logs -f app` | Follow Flask application logs |
| `docker compose exec db mariadb -u root -p` | Open MariaDB shell |
| `docker compose restart app` | Restart only the Flask container |

## SSL / HTTPS

To enable HTTPS:

1. Place your certificate files in `nginx/certs/`:
   - `fullchain.pem`
   - `privkey.pem`

2. Uncomment the HTTPS server block in `nginx/default.conf`.

3. Restart Nginx:
   ```bash
   docker compose restart web
   ```

## Structure

```
03_docker/
├── Dockerfile            # Multi-stage build (builder + production)
├── docker-compose.yml    # 3-service orchestration
├── .env.example          # Template for secrets
├── .dockerignore         # Keeps build context small
├── .gitignore            # Excludes .env and certs from Git
├── nginx/
│   ├── default.conf      # Nginx reverse proxy configuration
│   └── certs/            # SSL certificates (not committed)
└── README.md             # This file
```

## Key Improvements Over Ansible

| Feature | Ansible | Docker |
| ------- | ------- | ------ |
| Environment parity | Server-specific | Identical everywhere |
| Startup time | Minutes (full provision) | Seconds (`docker compose up`) |
| Isolation | Shared host OS | Each service in own container |
| Rollback | Re-run playbook | `docker compose pull && up` |
| Local development | Requires VM/EC2 | Works on any laptop |
| Dependency conflicts | Possible | Impossible (isolated) |
