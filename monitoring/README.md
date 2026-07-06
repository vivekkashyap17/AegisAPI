# Monitoring (Phase 8 — Observability)

Prometheus scrapes the AegisAPI app's `/metrics` endpoint (added in slice 1) and
stores the time series. Grafana dashboards + alerts sit on top (slice 3).

Prometheus runs as a standalone container for now, matching how `aegis-postgres`
and `aegis-redis` are run. It folds into `docker-compose` at Phase 10.

## Prerequisites

The app must be running on the host and exposing metrics on port `8000`:

```bash
cd backend
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> The scrape target is `host.docker.internal:8000`. If you run uvicorn on a
> different port, update `targets` in `prometheus.yml` to match.

## Start Prometheus

```bash
docker run -d --name aegis-prometheus \
  --add-host=host.docker.internal:host-gateway \
  -p 9090:9090 \
  -v "$(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  -v "$(pwd)/monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro" \
  -v aegis-prometheus-data:/prometheus \
  prom/prometheus:latest
```

Run this from the repo root (`AegisAPI/`) so `$(pwd)/monitoring/...` resolves.
`--add-host=...:host-gateway` lets the container reach the host-run app;
`aegis-prometheus-data` is a named volume so the TSDB survives restarts. The
second mount loads the alerting rules (see below).

## Verify the scrape

- Prometheus UI: http://localhost:9090
- Target health: http://localhost:9090/targets — `aegisapi` should be **UP**
- Quick query (returns a value once the app has served some traffic):

  ```
  http://localhost:9090/api/v1/query?query=aegis_ingest_requests_total
  ```

## Alerting rules

`alerts.yml` defines four alerts (evaluated by Prometheus): `AegisApiDown`,
`HighAnomalyRate`, `HighBlockRate`, `QuarantineRejectionsActive`.

- View them: http://localhost:9090/alerts (or `/rules` for evaluation health)

Routing alerts to Slack/email needs **Alertmanager**, intentionally deferred to
the docker-compose work in Phase 10 — for now alerts surface in the Prometheus UI.

## Start Grafana (dashboards)

```bash
docker run -d --name aegis-grafana \
  --add-host=host.docker.internal:host-gateway \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_USER=admin \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  -v "$(pwd)/monitoring/grafana/provisioning:/etc/grafana/provisioning:ro" \
  -v "$(pwd)/monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro" \
  grafana/grafana:latest
```

Also run from the repo root. Grafana auto-provisions on boot:

- The **Prometheus datasource** (`grafana/provisioning/datasources/`) — points at
  `host.docker.internal:9090`.
- The **"AegisAPI — Security Overview"** dashboard (`grafana/dashboards/`) — ingest
  rate by action, request mix, anomaly rate, quarantine rejections, risk/trust
  percentiles, and cumulative counters.

Open http://localhost:3000 (login `admin` / `admin`) → **Dashboards → AegisAPI —
Security Overview**. Edit the JSON in `grafana/dashboards/` and restart to update.

## Lifecycle

```bash
docker stop  aegis-prometheus aegis-grafana   # stop
docker start aegis-prometheus aegis-grafana   # restart (config + data persist)
docker rm -f aegis-prometheus aegis-grafana   # remove (named volumes are kept)
```

After editing `prometheus.yml` / `alerts.yml`, restart the container to reload
(`docker restart aegis-prometheus`).
