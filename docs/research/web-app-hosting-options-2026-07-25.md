# Web-app hosting options: managed platforms, shared hosting, and VPSs

**Research date:** 2026-07-25  
**Decision supported:** deployment for portfolio, hobby, and educational web
applications from GitHub, including FastAPI/Flask backends, React frontends,
and small internal-service architectures.

## Recommendation

Start with **Render paid for backend services** and **Cloudflare Pages for a
static React frontend**:

```text
GitHub push to main
  ├── Cloudflare Pages: React frontend
  └── Render: public FastAPI API, database, and internal services
```

This is the smoothest path from a GitHub push to a public, always-on app. It
avoids maintaining an operating system, reverse proxy, TLS, and deployment
scripts. Render supports GitHub-triggered deploys, native Python or
Dockerfile builds, private services, workers, and private networking.

Use a **VPS with Docker Compose** later if there are enough always-on services
that per-service managed-platform cost is no longer worthwhile, or if learning
server operations is itself the goal. A 2 GB RAM and 50 GB disk VPS is a good
initial size for several low-traffic portfolio containers.

Do not choose ordinary shared web hosting as the default for FastAPI. It can
support Python and can be viable for a small Flask-style app, but it is a
constrained provider runtime rather than control of a normal ASGI deployment.

## Decision guide

| Situation | Recommended approach | Reason |
|---|---|---|
| One FastAPI/Flask API and React frontend | Render + Cloudflare Pages | GitHub deploys, public HTTPS, minimal operations |
| Public API plus internal API/worker/database | Separate Render services in one region | Private hostnames and ports; only required services are public |
| Several low-traffic, always-on apps | DigitalOcean VPS + Docker Compose + Cloudflare Pages | One predictable VM cost and multiple containers |
| Learn Linux, Docker, networking, and CI/CD | VPS + Docker Compose | Full control and direct operational experience |
| React-only static site | Cloudflare Pages | CDN delivery and GitHub deployments without a server |
| Existing small cPanel/Flask app | Shared hosting only after runtime validation | Python support alone does not guarantee ASGI support |

## Hosting models

| Model | Provider supplies | Owner controls | Fit for FastAPI |
|---|---|---|---|
| Shared web hosting | cPanel account, web-server integration, fixed quotas | Files and limited account settings | Possible through host-specific setup; not preferred |
| Managed app platform | Build/run environment, HTTPS, logs, deploys, private network | Source, build/start commands, secrets, optional Dockerfile | Excellent |
| VPS | Virtual Linux machine with assigned resources and IP | OS, packages, proxy, containers, backups, deployment | Excellent |

### Shared hosting and GoDaddy

Shared hosting means many customers use the same underlying server. Each
account has resource limits. GoDaddy currently lists the following cPanel
limits:

| Plan | CPU | RAM | Disk | Concurrent connections |
|---|---:|---:|---:|---:|
| Economy | 1 accessible core | 512 MB | 25 GB | 20 |
| Deluxe | 1 accessible core | 1 GB | 50 GB | 30 |

GoDaddy lists Python as supported on cPanel. That does **not** mean complete
control over FastAPI. The provider controls the web server, long-running
process model, listening ports, and system packages. A standard FastAPI setup
expects an ASGI server (Uvicorn or Gunicorn with Uvicorn workers), often
behind Nginx or Caddy. Verify the exact ASGI/Passenger model before purchasing
shared hosting. Flask's traditional WSGI deployment is generally a better fit.

## Managed-platform deployment

On a managed platform, a connected GitHub branch is built and deployed on each
push. The owner provides build/start commands and secrets. A typical Python
build uses:

```text
pip install -r requirements.txt
```

The provider installs dependencies in an isolated build/deployment environment
and provides logs, HTTPS, health checks, and redeployment. Render supports
native Python and can also build a Dockerfile from the repository.

Recommended service layout:

```text
React frontend (public CDN)
        ↓ HTTPS
Public FastAPI API (public)
        ├── Postgres / Redis (private)
        ├── processing service (private)
        └── background worker (private; consumes jobs)
```

On Render, use a **Web Service** for the public API, a **Private Service** for
an internal service that receives requests, and a **Background Worker** for a
job consumer. Services in the same workspace and region can communicate over
private hostnames and ports; private services have no public URL.

Keep a modular monolith until a service needs independent deployment, scaling,
resource use, or isolation. Do not introduce microservices merely because
containers are available.

## VPS deployment

With a VPS, a normal container architecture is:

```text
Internet
  → Caddy or Nginx (HTTPS and routing)
  → Docker Compose network
       ├── API container (public through proxy)
       ├── internal-service container (private network)
       ├── worker container
       └── database/Redis container
```

Only the reverse proxy exposes ports `80` and `443`; internal containers use
the Docker network. A GitHub Actions workflow can build/publish images, SSH
to the VPS, and run `docker compose up -d`.

This is cost-effective, but the owner maintains security updates, firewall
rules, proxy/TLS configuration, backups, monitoring, rollbacks, and disk
cleanup. Multiple containers do not require multiple servers initially.

For local development, use `docker-compose.yml` to run the whole system. In
managed production, deploy meaningful services separately so each has its own
logs, health checks, secrets, restarts, and deployment history.

Suggested layout:

```text
project/
  frontend/
  services/
    api/
    processing/
    worker/
  docker-compose.yml        # local development
  render.yaml               # managed production definitions
```

## Docker and dependencies

Dependencies are normally isolated per app, not globally shared among
customers. This avoids version conflicts and makes builds reproducible.

| Deployment type | Dependency approach |
|---|---|
| Shared hosting | Provider Python plus an account-level virtual environment, if supported |
| Managed native runtime | Platform runs `pip install -r requirements.txt` in an isolated build environment |
| VPS without Docker | Install OS packages, then a virtual environment per app |
| Docker | Each image includes needed OS packages, Python, and Python dependencies |

Do not assume FastAPI, Uvicorn, SQLAlchemy, or project packages are installed.
Commit `requirements.txt` or `pyproject.toml` with a lockfile. Dockerfiles are
worth adding when OS packages or reproducible environments justify them; they
are not required for a basic FastAPI deployment on Render.

## Cost and capacity snapshot

Prices are July 2026 snapshots. Region, tax, promotions, payment terms, and
usage can change the actual total.

| Option | Approximate annual base cost | Capacity / implication |
|---|---:|---|
| Railway Hobby + Cloudflare Pages | $60 minimum, plus usage | Convenient hobby platform; $5 monthly usage included |
| Render API + small database + static frontend | about $156 before growth usage | Render's current example is about $13/month |
| DigitalOcean 1 GB VPS | $72 | 1 vCPU, 25 GB SSD; one small app |
| DigitalOcean 2 GB VPS | $144 | 1 vCPU, 50 GB SSD; good multi-container start |
| DigitalOcean Spaces | $60 | 250 GiB object storage and 1 TiB outbound transfer |
| GoDaddy entry VPS | about $108 promotional first-year effective | 1 vCPU, 2 GB RAM, 40 GB NVMe; commitment/renewal vary |
| GoDaddy Economy shared | $71.88/year effective | $215.64 shown as three-year prepayment; 512 MB/25 GB quota |
| GoDaddy Deluxe shared | $95.88/year effective | $287.64 shown as three-year prepayment; 1 GB/50 GB quota |

Shared-hosting prices are not directly comparable with a VPS or managed
FastAPI platform: they are promotional multi-year cPanel plans. The current
GoDaddy page shows much higher three-year renewal totals, and SSL terms should
be checked at checkout.

## Storage guidance

A roughly 1.5 GB project does not imply a 200 GB server. A 40–50 GB disk is
normally enough for source, dependencies, a small database, and a limited
number of Docker images. Docker build cache, logs, images, backups, database
growth, and uploads can grow much faster than source code.

Store uploads, images, documents, video, model assets, and other large files
in object storage—not container/application disk. Keep durable application
data in a managed database or backed-up database volume.

## Practical default

1. Deploy React frontends on Cloudflare Pages.
2. Deploy the public FastAPI service on Render paid from GitHub.
3. Add Render private services and workers only when their boundary is useful.
4. Use managed Postgres initially; never rely on ephemeral app files for data.
5. Add Dockerfiles per backend service when reproducibility or OS packages
   require them; retain Compose for local development.
6. Move a collection of services to a 2 GB/50 GB VPS with Docker Compose if
   managed-service cost becomes the deciding factor.

## Sources

All sources below were checked on 2026-07-25.

- [Render web services](https://render.com/docs/web-services) — Git deployment, Python runtime, public services, and Docker.
- [Render deploys](https://render.com/docs/deploys) and [GitHub connection](https://render.com/docs/github) — automatic deployment behavior.
- [Render Docker](https://render.com/docs/docker) — Dockerfile builds and tradeoffs.
- [Render private network](https://render.com/docs/private-network), [private services](https://render.com/docs/private-services), and [service types](https://render.com/docs/service-types) — private services, internal ports, and workers.
- [Railway pricing](https://railway.com/pricing) — Hobby plan pricing and limits.
- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets) and [Spaces pricing](https://www.digitalocean.com/pricing/spaces-object-storage) — VM and object-storage estimates.
- [GoDaddy resource limits](https://www.godaddy.com/en-uk/help/resource-limits-12001) and [supported components](https://www.godaddy.com/help/which-components-does-my-hosting-support-5614) — shared-hosting quotas and Python support.
- [GoDaddy web hosting](https://www.godaddy.com/hosting/web-hosting) and [VPS plans](https://www.godaddy.com/es-es/hosting/servidor-vps) — pricing/capacity snapshots; locale varies.
