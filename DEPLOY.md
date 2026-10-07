# AWS EC2 + Docker Compose CD

Continuous Deploy: push to `main` → GitHub Actions CI (tests) → CD builds images → SSH to EC2 → `docker compose up -d`.

## One-time AWS setup

1. Launch an **Ubuntu 22.04/24.04** EC2 instance (`t3.small` is enough to start).
2. Attach an **Elastic IP**.
3. Security group inbound rules:
   - `22` from your IP only (SSH)
   - `80` from `0.0.0.0/0` (HTTP)
   - `443` from `0.0.0.0/0` (HTTPS, after you add TLS)
4. SSH in and install Docker:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu
```

Log out and back in so the `docker` group applies.

5. Create the app directory and copy compose files from this repo:

```bash
sudo mkdir -p /opt/ironman
sudo chown "$USER:$USER" /opt/ironman
cd /opt/ironman
# Copy docker-compose.prod.yml and .env onto the server (scp or git clone).
cp .env.example .env
nano .env   # fill real values
```

## GitHub Secrets

### Backend repo (`ironman`)

| Secret | Purpose |
| --- | --- |
| `EC2_HOST` | Elastic IP or public DNS |
| `EC2_USER` | Usually `ubuntu` |
| `EC2_SSH_KEY` | Private key PEM contents for the EC2 key pair |
| `GHCR_TOKEN` | GitHub PAT with `read:packages` + `write:packages` |

### Frontend repo (`studynotes-react`)

| Secret | Purpose |
| --- | --- |
| `EC2_HOST` | Same as backend |
| `EC2_USER` | Same as backend |
| `EC2_SSH_KEY` | Same as backend |
| `GHCR_TOKEN` | Same PAT (packages read/write) |
| `VITE_API_BASE_URL` | Leave empty for same-host Nginx, or set full API origin |

## Server `.env` keys

See [`.env.example`](.env.example). Important:

- `POSTGRES_HOST=db` (compose service name)
- `POSTGRES_PORT=5432`
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS=your.domain.com,YOUR_EIP`
- `CORS_ALLOWED_ORIGINS=http://YOUR_EIP,https://your.domain.com`
- `CSRF_TRUSTED_ORIGINS=http://YOUR_EIP,https://your.domain.com`
- `WEB_IMAGE=ghcr.io/<owner>/ironman-web:latest`
- `FRONTEND_IMAGE=ghcr.io/<owner>/studynotes-frontend:latest`

Never commit `.env`.

## First manual deploy on EC2

```bash
cd /opt/ironman
echo "$GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl -I http://127.0.0.1/
```

## Daily flow (separate, no conflict)

**Backend**
1. Push to `main` on `ironman`
2. Django CI runs
3. Backend CD builds/pushes only `ironman-web` and restarts only the `web` service

**Frontend**
1. Push to `main` on `studynotes-react`
2. Frontend CD builds/pushes only `studynotes-frontend` and restarts only the `frontend` service

They do not rebuild each other’s images, so one deploy cannot overwrite the other.

## Frontend image

Built only from the `studynotes-react` repo Dockerfile (Nginx serves Vite `dist`, proxies API to `web:8000`, serves `/static/` + `/media/` from shared volumes).

For same-host deploy, leave `VITE_API_BASE_URL` empty so the React app calls `/academics/` and `/authentication/` on the same origin.

## HTTPS (later)

Put TLS on the EC2 host with Caddy or Certbot in front of port 80, or extend `deploy/nginx` with certificates. Update `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to `https://...`.
