# OMWOM Console

A lightweight operations dashboard for self-hosted infrastructure managed with Ansible and Semaphore. Built with Streamlit.

## What It Does

A single web interface for managing a server running WordPress sites, Odoo instances, Modoboa email, and supporting services. Instead of jumping between Semaphore, Uptime Kuma, Modoboa, and SSH, everything is visible and actionable from one dashboard.

**Dashboard** — server metrics, alerts (SSL expiry, backup failures, services down), site overview, backup status, SSL certificates, core services, activity log. Everything links to the relevant page or external tool.

**Sites** — add, remove, start/stop WordPress sites, Odoo instances, and mail domains. Per-site PHP version management. Quick backup per site. Email account creation via Modoboa API. Direct links to wp-admin, Odoo admin, and Modoboa.

**Restore** — upload a Softaculous WordPress Manager backup (or point to a server path for large files), parse the metadata, configure the restore target, and trigger the restore playbook via Semaphore. Full validation and confirmation flow.

**Health** — trigger the server health check playbook, view parsed results (system metrics, service status, Docker containers, SSL certs, backup status), installed runtimes (PHP, Python, databases, tools), and recent Semaphore task history.

**Backups** — 7/14/30-day history with Altair charts (color-coded by status, dual size+duration view), database and file backup details, remote provider status, verification history, restore test results. Manual backup trigger with scope selection.

**DNS** — live DNS record checker for any domain. Verifies A, MX, SPF, DKIM, and DMARC records. Bulk check all managed domains. Reference card for required records when onboarding a new site.

**Logs** — view and filter server logs (backup, mail, nginx, WordPress updates, fail2ban, auth). Severity highlighting, quick filter buttons, line counts.

## Quick Start

```bash
git clone https://github.com/jwincek/omwom-console.git
cd omwom-console
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m streamlit run Dashboard.py
```

Visit `http://localhost:8501`. The app runs in mock mode with simulated data until you configure the Semaphore and Modoboa API connections.

## Configuration

Copy `.env.example` to `.env` and set your API tokens:

```bash
cp .env.example .env
```

| Variable | Purpose | Required |
|----------|---------|----------|
| `SEMAPHORE_URL` | Semaphore base URL (e.g., `https://ops.omwom.com`) | For live mode |
| `SEMAPHORE_TOKEN` | Semaphore API bearer token | For live mode |
| `SEMAPHORE_PROJECT_ID` | Semaphore project ID (default: 1) | For live mode |
| `MODOBOA_URL` | Modoboa base URL (e.g., `https://mail.omwom.com`) | For email management |
| `MODOBOA_TOKEN` | Modoboa API token | For email management |

When these are not set, the app runs in **mock mode** with realistic simulated data — useful for development and evaluation.

## Project Structure

```
omwom-console/
├── Dashboard.py                    # Main dashboard with alerts
├── pages/
│   ├── 1_Sites.py                  # Site management (CRUD + controls)
│   ├── 2_Restore.py                # WordPress restore from backup
│   ├── 3_Health.py                 # Server health + installed runtimes
│   ├── 4_Backups.py                # Backup status + manual trigger
│   ├── 5_DNS.py                    # DNS record checker (live lookups)
│   └── 6_Logs.py                   # Log viewer with filtering
├── lib/
│   ├── database.py                 # SQLAlchemy + SQLite activity log
│   ├── semaphore.py                # Semaphore API client (real + mock)
│   ├── modoboa.py                  # Modoboa API client (real + mock)
│   ├── dns_checker.py              # DNS record verification
│   ├── softaculous.py              # Softaculous backup parser
│   ├── mock_data.py                # Mock server/site data
│   ├── mock_backups.py             # Mock backup data
│   └── mock_logs.py                # Mock log content
├── deploy/
│   ├── DEPLOY.md                   # Step-by-step deployment guide
│   ├── omwom-console.service       # systemd unit file
│   ├── console.omwom.com.conf      # Nginx vhost (WebSocket + auth + security headers)
│   └── console-deploy.yml          # Ansible playbook for git-based deploys
├── .streamlit/config.toml          # Theme + server config
├── .env.example                    # Environment variable template
├── requirements.txt                # Pinned dependencies
└── run.sh                          # Local dev runner
```

## Deployment

See [deploy/DEPLOY.md](deploy/DEPLOY.md) for the full guide. Summary:

1. Create system user and directory structure
2. `git clone` the repo (or SCP)
3. Create virtualenv and install dependencies
4. Configure `.env` with API tokens
5. Install systemd service
6. Configure Nginx with basic auth and SSL
7. Obtain SSL certificate via Certbot

Updates via git pull:

```bash
sudo -u consoleapp git -C /opt/omwom-console/app pull
sudo systemctl restart omwom-console
```

Or trigger deploys from Semaphore using the included `console-deploy.yml` playbook.

## Architecture

The console is a **viewer and trigger**, not a data owner. It reads from existing sources (Semaphore API, Modoboa API, server health scripts, DNS) and triggers actions through Semaphore task templates. The only local state is a SQLite activity log.

```
Browser → Nginx (basic auth + SSL) → Streamlit (port 8073)
                                          ├── Semaphore API (ops.omwom.com)
                                          │     └── Ansible playbooks
                                          ├── Modoboa API (mail.omwom.com)
                                          │     └── Email account management
                                          ├── DNS resolvers (live lookups)
                                          └── SQLite (activity log only)
```

All destructive actions (site removal, service stops) require confirmation. The Ansible playbooks create backups before removing anything.

## Adapting for Your Infrastructure

The mock data and Semaphore template IDs reflect a specific server setup (WordPress + Odoo + Modoboa on Ubuntu). To adapt for your own infrastructure:

1. Update `lib/mock_data.py` with your sites, services, and server specs
2. Update template IDs in `lib/semaphore.py` to match your Semaphore task templates
3. Adjust the Ansible playbooks in the project root to match your provisioning patterns
4. Modify the DNS checker's default mail server in `pages/5_DNS.py`

The patterns (API client with mock/production split, session state management, activity logging) transfer to any Ansible+Semaphore managed infrastructure.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI framework | Streamlit 1.56 |
| Charts | Altair 6.0 |
| Database | SQLite via SQLAlchemy 2.0 |
| DNS | dnspython 2.8 |
| HTTP client | Requests 2.33 |
| Data | Pandas 3.0 |
| Deployment | systemd + Nginx + Certbot |
| Auth | Nginx HTTP Basic Auth over TLS |

## License

MIT — see [LICENSE](LICENSE) for details.
