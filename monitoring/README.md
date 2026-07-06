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
  -v aegis-prometheus-data:/prometheus \
  prom/prometheus:latest
```

Run this from the repo root (`AegisAPI/`) so `$(pwd)/monitoring/...` resolves.
`--add-host=...:host-gateway` lets the container reach the host-run app;
`aegis-prometheus-data` is a named volume so the TSDB survives restarts.

## Verify the scrape

- Prometheus UI: http://localhost:9090
- Target health: http://localhost:9090/targets — `aegisapi` should be **UP**
- Quick query (returns a value once the app has served some traffic):

  ```
  http://localhost:9090/api/v1/query?query=aegis_ingest_requests_total
  ```

## Lifecycle

```bash
docker stop aegis-prometheus      # stop
docker start aegis-prometheus     # restart (config + data persist)
docker rm -f aegis-prometheus     # remove (named volume is kept)
```

After editing `prometheus.yml`, restart the container to reload it
(`docker restart aegis-prometheus`).
