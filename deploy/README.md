## Test24 Backend Deployment Guide

This folder keeps everything needed to deploy the Test24 backend on a fresh Ubuntu/Debian server using **only Git clones/pulls**. Nothing is copied manually; you always build from an auditable commit that already passed local testing.

### 1. Server topology

| Item              | Value/Example                           |
|-------------------|-----------------------------------------|
| Repo URL          | `https://github.com/Nurmuhammad0071/Test24.git` |
| Deploy user       | `test24` (system user, no shell login)  |
| App directory     | `/opt/test24/app`                      |
| Virtualenv        | `/opt/test24/venv`                     |
| Env file          | `/etc/test24/test24.env`               |
| Gunicorn socket   | `/run/test24/gunicorn.sock`            |
| Systemd service   | `test24.service`                       |
| Nginx site        | `/etc/nginx/sites-available/test24.conf` |

> **Important:** Never push untested or dirty worktree code. Always run tests locally, commit, and push before trying to deploy.

### 2. One-time bootstrap

Run the script as root. It installs system packages, creates the deployment user, clones the repo, installs Python deps, migrates the database, and prepares static assets.

```bash
scp deploy/scripts/bootstrap.sh root@<SERVER_IP>:/tmp/test24-bootstrap.sh
ssh root@<SERVER_IP> 'bash /tmp/test24-bootstrap.sh \
  --repo-token YOUR_GITHUB_TOKEN_HERE \
  --branch main \
  --domain api.test24.uz'
```

The script will:

1. Install `git`, `python3-venv`, `nginx`, `postgresql-client`, `curl`.
2. Create `/opt/test24`, system user/group `test24`.
3. Clone the repository with the provided token.
4. Create `/etc/test24/test24.env` (copy your local `example.env` contents there, then edit secrets).
5. Set up the virtualenv, run `pip install -r requirements.txt`.
6. Run `python manage.py migrate` and `collectstatic --noinput`.
7. Drop the ready-made systemd and Nginx configs into place and enable the service.

### 3. Updating / auto-deploy

For zero-downtime updates, the server only needs to pull the latest commit and restart Gunicorn safely. Use the `deploy/scripts/update.sh` helper via SSH:

```bash
ssh root@<SERVER_IP> '/opt/test24/app/deploy/scripts/update.sh --branch main'
```

`update.sh` performs:

1. `git fetch origin` + `git reset --hard origin/<branch>` (enforces clean tree).
2. Dependency upgrade if `requirements.txt` changed.
3. `python manage.py migrate` + `collectstatic`.
4. `systemctl restart test24`.

The script is idempotent and only touches `/opt/test24`. No other services are restarted.

### 4. Nginx & SSL

`deploy/nginx/test24.conf` is ready to drop into `/etc/nginx/sites-available`. It assumes Let’s Encrypt certificates under `/etc/letsencrypt/live/api.test24.uz/`. Adjust the domain/email and then run:

```bash
ln -s /etc/nginx/sites-available/test24.conf /etc/nginx/sites-enabled/test24.conf
nginx -t && systemctl reload nginx
```

Use `certbot --nginx -d api.test24.uz` after the site is reachable to obtain certificates.

### 5. Systemd service

`deploy/systemd/test24.service` starts Gunicorn on a free port/socket and restarts automatically if it crashes. Enable it once:

```bash
cp deploy/systemd/test24.service /etc/systemd/system/test24.service
systemctl daemon-reload
systemctl enable --now test24
```

Logs are available via `journalctl -u test24 -f`.

### 6. Rollbacks

The update script keeps the previous commit hash in `/opt/test24/.last_release`. To roll back:

```bash
ssh root@<SERVER_IP> '
  cd /opt/test24/app && \
  git checkout $(cat ../.last_release) && \
  /opt/test24/app/deploy/scripts/update.sh --skip-pull --no-migrate
'
```

### 7. Troubleshooting checklist

- `systemctl status test24` → Gunicorn health.
- `journalctl -u test24 -n 200` → runtime errors.
- `tail -n 200 /var/log/nginx/test24_access.log`.
- `python manage.py check --deploy` after every configuration change.

Keep all modifications in Git so the server never receives untracked files. Any hotfix must be applied locally, tested, committed, and pushed before the server pulls it.

