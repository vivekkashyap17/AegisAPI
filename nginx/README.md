# Edge Gateway (Phase 9 — Nginx reverse proxy)

Nginx sits in front of the FastAPI app as the single public entrypoint. Every
request hits Nginx first and is proxied to the app (uvicorn on the host). This
is the foundation for network-level defenses added in later slices:

- **Slice 1 (this):** reverse proxy + real-client-IP forwarding.
- **Slice 2:** network-level rate limiting + IP reputation (deny/allow lists).
- **Slice 3:** TLS termination (HTTPS) + hardened security headers.

Nginx runs as a standalone container for now, matching how `aegis-postgres`,
`aegis-redis`, and `aegis-prometheus` are run. It folds into `docker-compose`
at Phase 10.

## Prerequisites

The app must be running on the host on port `8000`. Run it with `--proxy-headers`
so it trusts the `X-Forwarded-*` headers Nginx sends (so `request.client` and
access logs reflect the true client, not the proxy):

```bash
cd backend
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

> The upstream target is `host.docker.internal:8000`. If you run uvicorn on a
> different port, update the `upstream` block in `nginx/default.conf` to match.

## Start the gateway

```bash
docker run -d --name aegis-nginx \
  --add-host=host.docker.internal:host-gateway \
  -p 8080:80 \
  -v "$(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:latest
```

Run this from the repo root (`AegisAPI/`) so `$(pwd)/nginx/...` resolves.
`--add-host=...:host-gateway` lets the container reach the host-run app. The
gateway listens on host port `8080`.

## Verify

- **Gateway is up (Nginx itself):**

  ```
  curl http://localhost:8080/gateway-health
  # {"status":"gateway healthy"}
  ```

- **Proxy reaches the app:**

  ```
  curl http://localhost:8080/health
  # {"status":"healthy","app":"AegisAPI"}
  ```

- **Full app through the gateway:** open http://localhost:8080/docs — the same
  Swagger UI, now served via Nginx. Every endpoint works identically through
  `:8080` as it did on `:8000`.

## Lifecycle

```bash
docker stop  aegis-nginx     # stop
docker start aegis-nginx     # restart
docker rm -f aegis-nginx     # remove
```

After editing `default.conf`, reload without downtime:

```bash
docker exec aegis-nginx nginx -s reload
```

(or `docker restart aegis-nginx`).

## Note on the direct app port

For now the app is still directly reachable on `:8000` alongside the gateway on
`:8080` — convenient in development. In production you would stop exposing
`:8000` publicly so **all** traffic is forced through the gateway. That lockdown
lands with the `docker-compose` networking work in Phase 10.
