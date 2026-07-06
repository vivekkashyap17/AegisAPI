# 🛡️ AegisAPI

**An adaptive, backend-driven API-security platform.** AegisAPI ingests API traffic events, scores each for risk, learns a per-subject **trust score**, detects anomalies with unsupervised ML, and returns a real-time **policy decision** — `ALLOW` · `THROTTLE` · `RATE_LIMIT` · `BLOCK` · `QUARANTINE`. Every decision is persisted as a tamper-evident audit log, streamed to Kafka, exposed as Prometheus metrics, and surfaced in a live Security Operations Console.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white">
  <img alt="Kafka" src="https://img.shields.io/badge/Apache%20Kafka-3.8%20KRaft-231F20?logo=apachekafka&logoColor=white">
  <img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-66%20passing-3fb950">
</p>

> **Note** — This is a portfolio project built to demonstrate real security-engineering patterns end to end (zero-trust scoring, adaptive policy, ML anomaly detection, streaming, observability, and edge defense). It is not a hardened production product.

---

## Table of contents

- [Why AegisAPI](#why-aegisapi)
- [Key features](#key-features)
- [Architecture](#architecture)
- [How a request is decided](#how-a-request-is-decided)
- [The decision engine](#the-decision-engine)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [API reference](#api-reference)
- [Observability](#observability)
- [Security Operations Console](#security-operations-console)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Build history](#build-history)
- [License](#license)

---

## Why AegisAPI

Traditional API security is static: a fixed rate limit, an allow/deny list, a WAF rule. AegisAPI is **adaptive** — it treats every request as evidence and continuously re-evaluates *how much it trusts the subject making it*. A caller that behaves normally earns trust and moves freely; one that spikes error rates, hits sensitive endpoints, or trips the anomaly detector loses trust and is progressively throttled, blocked, and finally quarantined until it re-authenticates.

It combines three complementary signals into a single decision:

| Signal | Source | Answers |
| --- | --- | --- |
| **Risk** | Rule-based heuristics (`scoring.py`) | *Is this individual request suspicious?* |
| **Trust** | Stateful per-subject score in Redis (`trust.py`) | *How has this subject behaved over time?* |
| **Anomaly** | Unsupervised Isolation Forest (`anomaly.py`) | *Does this request look statistically unlike normal traffic?* |

---

## Key features

- **🔐 Zero-trust auth** — RS256 (asymmetric) JWT with access/refresh tokens and a `type` claim, bcrypt password hashing (byte-safe 72-byte handling), and role-based access control (`admin` / `analyst`).
- **📈 Adaptive trust scoring** — a per-subject score in Redis (default `0.7`, 24 h TTL) that rises with clean traffic and falls with risk and anomalies.
- **🧮 Rule-based risk engine** — transparent, explainable per-request scoring across response time, error status, payload size, and sensitive endpoints.
- **🤖 ML anomaly detection** — an unsupervised `StandardScaler → IsolationForest` pipeline that self-trains on live traffic (no labelled attack data), persists to disk, and periodically retrains.
- **⚖️ Hot-reloadable policy engine** — the full threshold/delta rule set lives in Redis and can be retuned at runtime via the admin API — **no redeploy**.
- **🚧 Quarantine + step-up re-auth** — a quarantined subject is rejected up front until it proves identity again with credentials, which lifts quarantine and restores trust.
- **🌊 Kafka event streaming** — every decision is published to a `security-events` topic; an independent alert consumer reacts off the request path (publish-once / consume-many).
- **📊 Observability** — first-class Prometheus metrics at `/metrics` and provisioned Grafana dashboards + alert rules.
- **🧱 Edge gateway** — Nginx reverse proxy with TLS termination, network-level rate limiting, IP-reputation denylist, and hardened security headers.
- **🖥️ Security Operations Console** — a Streamlit dashboard for live monitoring, audit-log forensics, analytics, and admin policy/quarantine control.
- **🧪 Tested** — 66 self-contained pytest cases covering scoring, features, trust, policy, quarantine, metrics, and the anomaly model.
- **🐳 Fully containerized** — one `docker compose up` brings up the entire stack with health checks and restart policies.

---

## Architecture

AegisAPI runs as a set of cooperating services. The Nginx edge is the only public entrypoint; the app, database, cache, and broker are internal-only.

```mermaid
flowchart TD
    client([API client / traffic source])

    subgraph edge["Edge (public)"]
        nginx["Nginx gateway<br/>TLS · rate limit · IP denylist · security headers"]
    end

    subgraph core["Application core (internal network)"]
        app["FastAPI app<br/>auth · ingest · decision pipeline"]
        redis[("Redis 7<br/>trust scores · policy rules · quarantine · anomaly buffer")]
        pg[("PostgreSQL 16<br/>users · audit_logs")]
        kafka[["Kafka 3.8 (KRaft)<br/>security-events topic"]]
        consumer["Alert consumer<br/>reacts to BLOCK / QUARANTINE / RATE_LIMIT"]
    end

    subgraph ops["Observability & operations"]
        prom["Prometheus<br/>scrapes /metrics · alert rules"]
        graf["Grafana<br/>provisioned dashboards"]
        dash["Streamlit<br/>Security Operations Console"]
    end

    client -->|HTTPS| nginx --> app
    app <--> redis
    app --> pg
    app -->|publish| kafka --> consumer
    prom -->|scrape| app
    graf --> prom
    dash -->|server-side API calls| app
```

### Published ports (Docker Compose)

| Service | URL | Notes |
| --- | --- | --- |
| Nginx edge | `https://localhost:8443` (and `http://localhost:8080` → 301 redirect) | Only public entrypoint to the API |
| Streamlit console | `http://localhost:8501` | Operator UI |
| Grafana | `http://localhost:3000` | Login `admin` / `admin` |
| Prometheus | `http://localhost:9090` | Metrics & alert rules |
| FastAPI app | *internal only* | Reached through the gateway; `:8000` when run locally |

---

## How a request is decided

The heart of AegisAPI is `POST /api/v1/ingest`. Each event flows through a fixed pipeline before a verdict is returned and audited.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI /ingest
    participant R as Redis
    participant M as Isolation Forest
    participant DB as PostgreSQL
    participant K as Kafka

    C->>A: TrafficEvent (Bearer JWT)
    A->>R: quarantined?
    alt subject quarantined
        A->>DB: audit rejection
        A-->>C: 403 QUARANTINE (retry_after)
    else normal path
        A->>A: risk = calculate_risk_score(event)
        A->>M: analyze_event() → anomaly?
        A->>R: update trust score (risk + anomaly deltas)
        A->>A: policy = get_trust_action(trust, risk, anomaly, rules)
        opt verdict == QUARANTINE
            A->>R: register quarantine (TTL)
        end
        A->>DB: write audit_logs row
        A->>K: publish security-events
        A-->>C: 200 { analysis, policy }
    end
```

1. **Validate** — the `TrafficEvent` Pydantic model checks the payload (`endpoint`, `method`, `response_time`, `status_code`, `ip_address`, `payload_size`; client `timestamp` is ignored — the server stamps receive time).
2. **Enforce quarantine** — if the subject is already quarantined, the request is rejected `403` up front (still audited) without scoring or touching trust.
3. **Score risk** — transparent heuristics produce a `risk_score` (0–100) and `risk_level` (`LOW`/`MEDIUM`/`HIGH`).
4. **Detect anomalies** — 7 numeric features are buffered in Redis; once 100 events exist the model trains (and retrains every 50), then flags statistical outliers.
5. **Update trust** — the risk band and anomaly flag adjust the subject's Redis trust score.
6. **Decide policy** — `get_trust_action()` combines trust + risk + anomaly against the hot-reloadable rule set into the final action.
7. **Persist & stream** — the decision is written to `audit_logs` and published to Kafka; metrics are recorded for Prometheus.

---

## The decision engine

### Risk scoring (`services/scoring.py`)

| Condition | Points |
| --- | --- |
| `response_time` > 100 ms | +30 |
| `status_code` ≥ 500 | +25 |
| `payload_size` > 1000 bytes | +20 |
| Sensitive endpoint (`/login`, `/admin`, `/payment`) | +15 |

**Bands:** `0–29 → LOW` · `30–59 → MEDIUM` · `60+ → HIGH`.

### Trust scoring (`services/trust.py`)

- Redis key `trust:{user_id}`, default **0.7**, clamped to `[0.0, 1.0]`, 24 h TTL.
- Per-request delta by risk band: low `+0.02` · moderate `−0.05` · high `−0.15`.
- **Anomaly penalty `−0.20`** stacks on top (an anomalous high-risk request = `−0.15 − 0.20 = −0.35`).
- **Step-up recovery:** a successful re-auth restores trust to at least the `step_up_trust` baseline (`0.5`) — it never lowers an already-higher score.

### Anomaly detection (`services/features.py` + `services/anomaly.py`)

- **7 features:** `response_time`, `status_code`, `payload_size`, `is_sensitive_endpoint`, `is_error` (status ≥ 400), `method_code`, `endpoint_length`.
- **Model:** `StandardScaler → IsolationForest` (`contamination=0.05`). Scaling is essential — feature magnitudes differ by orders of magnitude, and without it the largest features dominate and flag normal traffic.
- **Lifecycle:** features buffer in a capped Redis list (`anomaly:buffer`, size 100); the model first trains at 100 events, retrains every 50, and persists to `isolation_forest.pkl`.

### Policy matrix (`get_trust_action`, evaluated top-down)

Thresholds below are the **defaults** (`policy:rules` in Redis) and are hot-reloadable via `PUT /api/v1/policy`.

| # | Condition | Action |
| --- | --- | --- |
| 1 | `trust < 0.3` | **QUARANTINE** |
| 2 | anomaly **and** `risk ≥ 60` | **QUARANTINE** |
| 3 | anomaly **and** `risk ≥ 30` | **BLOCK** |
| 4 | anomaly | **RATE_LIMIT** |
| 5 | `trust < 0.5` **and** `risk ≥ 60` | **BLOCK** |
| 6 | `trust < 0.6` **and** `30 ≤ risk < 60` | **RATE_LIMIT** |
| 7 | `risk ≥ 60` | **BLOCK** |
| 8 | `risk ≥ 30` | **THROTTLE** |
| 9 | otherwise | **ALLOW** |

### Tunable rules (`policy:rules`)

| Key | Default | Meaning |
| --- | --- | --- |
| `risk_high` / `risk_moderate` | `60` / `30` | Risk-band cutoffs |
| `trust_critical` / `trust_low` / `trust_reduced` | `0.3` / `0.5` / `0.6` | Trust cutoffs |
| `step_up_trust` | `0.5` | Trust floor restored after re-auth |
| `delta_high_risk` / `delta_moderate_risk` / `delta_low_risk` | `-0.15` / `-0.05` / `0.02` | Per-request trust deltas |
| `anomaly_penalty` | `-0.20` | Extra trust penalty for anomalous requests |
| `quarantine_ttl` | `3600` | Quarantine lifetime (seconds) |

---

## Tech stack

| Layer | Technology |
| --- | --- |
| **Language** | Python 3.11 (container) / 3.12 (local) |
| **API** | FastAPI 0.111 (async), Uvicorn / Gunicorn |
| **Auth** | RS256 JWT (`python-jose`), `bcrypt`, RBAC |
| **Persistence** | PostgreSQL 16 · SQLAlchemy 2.0 (async) · `asyncpg` |
| **State / cache** | Redis 7 (`redis-py` asyncio) |
| **Machine learning** | scikit-learn 1.4 (Isolation Forest + StandardScaler), NumPy |
| **Streaming** | Apache Kafka 3.8 in KRaft mode (no Zookeeper) via `aiokafka` |
| **Observability** | `prometheus-client` · Prometheus · Grafana |
| **Edge gateway** | Nginx (TLS, rate limiting, IP denylist, security headers) |
| **Operations UI** | Streamlit 1.39 |
| **Testing** | pytest · pytest-asyncio · fakeredis |
| **Packaging** | Docker · Docker Compose |

---

## Project structure

```
AegisAPI/
├── backend/
│   ├── app/
│   │   ├── api/            # routes.py (ingest/trust/logs/policy/quarantine), auth.py
│   │   ├── core/           # config, db, dependencies, redis, init_db, keys/
│   │   ├── models/         # user.py, audit.py (SQLAlchemy), traffic.py (Pydantic)
│   │   ├── services/       # scoring, trust, policy_rules, features, anomaly,
│   │   │                   #   quarantine, metrics, events (Kafka), auth
│   │   ├── workers/        # alert_consumer.py (Kafka consumer)
│   │   └── main.py         # app factory, lifespan, middleware, /health, /metrics
│   ├── tests/              # 66 pytest cases + fixtures (conftest.py)
│   └── pytest.ini
├── dashboard/              # Streamlit Security Operations Console (views/, api.py, ui.py)
├── nginx/                  # default.conf (TLS/rate-limit/headers), denylist.conf
├── monitoring/             # prometheus.yml, alerts.yml, grafana/ (provisioning + dashboards)
├── Dockerfile              # app image
├── docker-compose.yml      # full stack: app, postgres, redis, kafka, consumer,
│                           #   nginx, prometheus, grafana, dashboard
├── requirements.txt        # runtime deps (curated, ASCII source of truth)
├── requirements-dev.txt    # test/dev deps
└── .env                    # config (gitignored — see below)
```

---

## Getting started

### Prerequisites

- **Docker Desktop** (for the full-stack path), or
- **Python 3.11+**, **PostgreSQL 16**, and **Redis 7** (for local development).
- **OpenSSL** to generate RS256 keys and a dev TLS certificate.

### 1. Generate RS256 JWT keys (required)

The app signs and verifies tokens with an asymmetric key pair that is **gitignored** and never committed:

```bash
mkdir -p backend/app/core/keys
openssl genrsa -out backend/app/core/keys/private.pem 2048
openssl rsa -in backend/app/core/keys/private.pem -pubout -out backend/app/core/keys/public.pem
```

### Option A — Full stack with Docker Compose (recommended)

This brings up the app, PostgreSQL, Redis, Kafka, the alert consumer, Nginx, Prometheus, Grafana, and the Streamlit console.

```bash
# 1. Generate a self-signed dev certificate for the Nginx edge
mkdir -p nginx/certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout nginx/certs/aegis.key -out nginx/certs/aegis.crt \
  -subj "/CN=localhost"

# 2. Build and start everything
docker compose up --build
```

Then:
- API (through the gateway): `https://localhost:8443/docs` *(self-signed cert — accept the browser warning)*
- Console: `http://localhost:8501` · Grafana: `http://localhost:3000` · Prometheus: `http://localhost:9090`

> Database/Redis credentials and service URLs are injected by `docker-compose.yml` — no `.env` is needed for the containerized app.

### Option B — Local development (backend from source)

Config is loaded from a `.env` file at the **repo root** (`AegisAPI/.env`):

```dotenv
DATABASE_URL=postgresql+asyncpg://aegis:aegis@localhost:5432/aegisapi
SYNC_DATABASE_URL=postgresql://aegis:aegis@localhost:5432/aegisapi
APP_NAME=AegisAPI
REDIS_URL=redis://localhost:6379
```

```bash
# from the repo root
python -m venv venv
venv\Scripts\Activate.ps1            # Windows PowerShell
# source venv/bin/activate           # macOS/Linux
pip install -r requirements.txt

# run all backend commands from backend/ so imports resolve as app.*
cd backend
python -m app.core.init_db           # create tables (also auto-created on startup)
uvicorn app.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs` and `http://localhost:8000/redoc`.

> Kafka is optional in local dev — if `KAFKA_BOOTSTRAP_SERVERS` is unset, event publishing is a silent no-op and the request path is unaffected.

### 2. Create your first user

Registration is open; register an admin to unlock the policy/quarantine endpoints and the console's Admin page:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"changeme123","role":"admin"}'
```

---

## API reference

All application routes are prefixed with `/api/v1`. Protected routes require a `Authorization: Bearer <access_token>` header.

### Authentication

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | — | Register a user (`role`: `admin` \| `analyst`) |
| `POST` | `/api/v1/auth/login` | — | OAuth2 password login → access + refresh tokens |
| `POST` | `/api/v1/auth/step-up` | — | Re-auth challenge: clear quarantine + restore trust |
| `GET`  | `/api/v1/auth/me` | Bearer | Current user profile |

### Traffic & decisions

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/ingest` | Bearer | Score an event and return the policy decision |
| `GET`  | `/api/v1/trust/{user_id}` | Bearer | Current trust score + level for a subject |
| `GET`  | `/api/v1/logs` | Bearer | Query audit logs (filters: `user_id`, `action`, `risk_level`; paginated) |
| `GET`  | `/api/v1/logs/{log_id}` | Bearer | Fetch a single audit log by UUID |

### Administration (`admin` role)

| Method | Path | Description |
| --- | --- | --- |
| `GET`    | `/api/v1/policy` | Read the effective policy rule set |
| `PUT`    | `/api/v1/policy` | Hot-reload one or more policy rules (partial update) |
| `GET`    | `/api/v1/quarantine/{user_id}` | Inspect a subject's quarantine status |
| `DELETE` | `/api/v1/quarantine/{user_id}` | Manually release a subject from quarantine |

### Operational (unprefixed)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service banner |
| `GET` | `/health` | Liveness probe |
| `GET` | `/metrics` | Prometheus exposition |

<details>
<summary><strong>Example: score an event</strong></summary>

```bash
# 1) log in
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=changeme123" | jq -r .access_token)

# 2) ingest a traffic event
curl -s -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "svc-payments",
        "endpoint": "/payment",
        "method": "POST",
        "response_time": 420.0,
        "status_code": 500,
        "ip_address": "203.0.113.10",
        "payload_size": 2048
      }' | jq
```

Response (abridged):

```json
{
  "status": "processed",
  "analysis": { "risk_score": 90, "risk_level": "HIGH", "trust_score": 0.55, "anomaly_detected": false },
  "policy":   { "action": "BLOCK", "reason": "High risk detected" }
}
```
</details>

---

## Observability

**Prometheus metrics** (`GET /metrics`), scraped by the bundled Prometheus and visualized in provisioned Grafana dashboards:

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `aegis_ingest_requests_total` | counter | `action`, `risk_level` | Processed events by verdict and risk band |
| `aegis_risk_score` | histogram | — | Distribution of per-event risk scores |
| `aegis_trust_score` | histogram | — | Distribution of subject trust after each update |
| `aegis_anomalies_total` | counter | — | Events flagged anomalous by the ML detector |
| `aegis_quarantine_rejections_total` | counter | — | Requests rejected because the subject was quarantined |
| `aegis_policy_reloads_total` | counter | — | Successful hot reloads via `PUT /policy` |

Grafana dashboards and Prometheus alert rules are provisioned automatically from `monitoring/` when the stack starts.

---

## Security Operations Console

A Streamlit console (`dashboard/`) that talks to the API **server-side** (no browser-held JWT, no CORS):

- **🛰️ Overview** — headline posture at a glance.
- **📡 Live Monitor** — real-time stream of decisions.
- **🗒️ Audit Logs** — searchable, filterable forensic browser over `audit_logs`.
- **📊 Analytics** — action mix, risk/trust distributions, anomaly rate.
- **⚙️ Admin** *(admin only)* — edit policy rules live and manage quarantine.

Runs at `http://localhost:8501` in the Docker stack.

---

## Testing

66 self-contained tests (no live Postgres, Redis, or keys required — Redis is faked with `fakeredis`, and the covered modules are pure logic).

```bash
cd backend
pip install -r ../requirements-dev.txt
pytest -q
```

Coverage spans risk scoring, feature extraction, the trust/policy engine (including anomaly rows), hot-reloadable rules, quarantine, Prometheus recording helpers, and the Isolation Forest train/predict lifecycle.

---

## Design decisions

| Decision | Rationale |
| --- | --- |
| **RS256 over HS256** | Asymmetric keys — services verify with the public key only and can never forge tokens. |
| **Redis for trust** | Sub-millisecond reads, atomic updates, and TTL-based decay fit a hot, ephemeral score. |
| **PostgreSQL for audit** | ACID guarantees — a security audit trail must never be lost or partially written. |
| **UUID primary keys** | Globally unique and non-sequential — no enumeration of records. |
| **Isolation Forest** | Unsupervised — no labelled attack data required — wrapped in a scaler because features are on wildly different scales. |
| **Hot-reloadable rules in Redis** | Operators retune policy at runtime; no redeploy to respond to a live incident. |
| **Kafka (KRaft, no Zookeeper)** | Decouples producers from consumers with a replayable log; alerting reacts off the request path. |
| **Nginx edge** | Coarse, cheap defenses (rate limit, IP denylist, TLS) turn away floods before they cost the app a scoring/ML/DB cycle. |

---

## Build history

The project was built in phases, each a coherent slice of functionality:

| Phase | Delivered |
| --- | --- |
| 2 | PostgreSQL audit logs, traffic ingestion, log retrieval |
| 3 | RS256 JWT auth, registration/login, RBAC, protected routes |
| 4 | Redis trust scores + adaptive policy engine |
| 5 | ML anomaly detection (Isolation Forest) wired into ingest |
| — | pytest test suite (inserted before Phase 7) |
| 7 | Adaptive policy upgrade: hot-reloadable rules, quarantine, step-up re-auth |
| 8 | Observability: Prometheus metrics, Grafana dashboards, alert rules |
| 9 | Edge gateway: Nginx reverse proxy, rate limiting, IP denylist, TLS |
| 10 | Dockerization + Kafka event streaming + alert consumer |
| 11 | Security Operations Console (Streamlit) |
| 12 | Documentation & polish |

---

## License

Released for portfolio, educational, and demonstration purposes. Review and harden before any production use.
