# Ansible Deployment — Stage 2

Deploys the Note-Taking App using **Ansible** with Roles, Jinja2 templates, and Ansible Vault for secrets.

## Prerequisites

On your local machine (or control node):

```bash
pip install ansible
ansible-galaxy collection install community.mysql ansible.posix
```

## Setup

**1. Configure your host:**

Edit `inventory.ini` and replace the placeholder with your EC2 IP:

```ini
[notes_app]
1.2.3.4 ansible_user=ec2-user ansible_ssh_private_key_file=~/.ssh/your-key.pem
```

**2. Create the encrypted vault:**

```bash
ansible-vault create vars/vault.yml
```

Add the following keys (see `vars/vault.yml.example` for the full list):

```yaml
vault_db_password: "a-strong-password"
vault_secret_key: "a-long-random-string"
```

**3. Update `vars/main.yml`** with your repo URL and preferences (already set to sensible defaults).

## Deploy

```bash
ansible-playbook deploy.yml --ask-vault-pass
```

## Re-run a Single Role

```bash
ansible-playbook deploy.yml --tags database --ask-vault-pass
```

## Structure

```
02_ansible/
├── ansible.cfg              # Settings (inventory, SSH key, sudo)
├── inventory.ini            # EC2 host(s)
├── deploy.yml               # Master playbook
├── vars/
│   ├── main.yml             # Non-sensitive variables
│   ├── vault.yml            # Encrypted secrets (never committed)
│   └── vault.yml.example    # Template showing required keys
└── roles/
    ├── common/              # OS update & system packages
    ├── database/            # MariaDB, DB user, schema import
    ├── application/         # Clone repo, venv, pip, .env, systemd
    ├── webserver/           # Nginx reverse proxy
    └── backup/              # EBS volume mount & cron backup
```

## Key Improvements Over Bash Scripts

| Feature | Bash | Ansible |
| ------- | ---- | ------- |
| Idempotent | No | Yes |
| Secrets management | Plain `.env` | Ansible Vault (encrypted) |
| Multi-server | Manual SSH each | List IPs in inventory |
| Error handling | Exit codes | Built-in, per-task |
| Config templating | `sed` / `cp` | Jinja2 templates |
