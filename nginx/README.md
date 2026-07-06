# Edge Gateway (Phase 9 — Nginx reverse proxy)

Nginx sits in front of the FastAPI app as the single public entrypoint. Every
request hits Nginx first and is proxied to the app (uvicorn on the host). This
is the foundation for network-level defenses added in later slices:

- **Slice 1:** reverse proxy + real-client-IP forwarding.
- **Slice 2:** network-level rate limiting + IP reputation denylist.
- **Slice 3 (this):** TLS termination (HTTPS) + hardened security headers.

> **Phase 10 update:** Nginx is now part of the root `docker-compose.yml` — run
> the whole stack with `docker compose up` from the repo root. The upstream now
> targets the `app` compose service by name (`app:8000`) instead of
> `host.docker.internal`, so the standalone `docker run` command below only works
> outside compose (with the upstream pointed back at the host) and is kept for
> reference.

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

## Generate the dev TLS certificate (slice 3)

TLS is terminated at the gateway. The dev cert is self-signed and **not
committed** (`nginx/certs/` is gitignored — private keys never go in git).
Generate it once, from the repo root:

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout nginx/certs/aegis.key \
  -out nginx/certs/aegis.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

For production you'd replace this with a real CA-issued cert (e.g. Let's
Encrypt) — same file paths, no config change.

## Start the gateway

```bash
docker run -d --name aegis-nginx \
  --add-host=host.docker.internal:host-gateway \
  -p 8080:80 \
  -p 8443:443 \
  -v "$(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$(pwd)/nginx/denylist.conf:/etc/nginx/denylist.conf:ro" \
  -v "$(pwd)/nginx/certs:/etc/nginx/certs:ro" \
  nginx:latest
```

Run this from the repo root (`AegisAPI/`) so `$(pwd)/nginx/...` resolves.
`--add-host=...:host-gateway` lets the container reach the host-run app. The
gateway listens on host port `8080` (HTTP, redirects to HTTPS) and `8443`
(HTTPS). The mounts are the config, the IP-reputation denylist (slice 2), and
the TLS certs (slice 3).

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

- **Full app through the gateway:** open https://localhost:8443/docs — the same
  Swagger UI, now served via Nginx over HTTPS. (The browser will warn about the
  self-signed cert — expected in dev; click through.)

## TLS termination (slice 3)

Clients speak **HTTPS** to the edge on `:8443`; Nginx decrypts and forwards
plain HTTP to the app on the private hop. Plain HTTP on `:8080` is **redirected**
to HTTPS. Verify:

```bash
# HTTPS serves the app (-k trusts the self-signed dev cert):
curl -sk https://localhost:8443/health
# {"status":"healthy","app":"AegisAPI"}

# HTTP is redirected to HTTPS (301):
curl -sI http://localhost:8080/api/v1/logs | grep -iE "^HTTP|^location"
# HTTP/1.1 301 Moved Permanently
# Location: https://localhost/api/v1/logs

# Hardened security headers are present:
curl -skI https://localhost:8443/health | grep -iE "strict-transport|x-content-type|x-frame|referrer"

# TLS 1.3 is negotiated:
echo | openssl s_client -connect localhost:8443 2>/dev/null | grep -iE "Protocol|Cipher" | head -2
```

Security headers set on every proxied response: `Strict-Transport-Security`
(HSTS), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy`. TLS is restricted to 1.2/1.3.

> **Dev caveats.** (1) The redirect `Location` uses the standard HTTPS port
> (`https://localhost/...`, no `:8443`) — correct for production where HTTPS is
> on `443`. On the dev `:8443` mapping, follow the redirect to `https://localhost:8443`
> manually. (2) HSTS tells browsers to force HTTPS for a year — if that becomes
> inconvenient on `localhost` during dev, clear the site's HSTS state in the
> browser or drop the header.

## Rate limiting (slice 2)

Configured in `default.conf`: **10 req/s per IP** with a **burst of 20**, and a
cap of **20 concurrent connections per IP**. Excess traffic gets `429 Too Many
Requests`. Prove it by firing a burst:

```bash
for i in $(seq 1 60); do
  curl -sk -o /dev/null -w "%{http_code}\n" https://localhost:8443/health &
done | sort | uniq -c
# ~21x 200 (burst + one refill), the rest 429
```

Tune the numbers in the `limit_req_zone` / `limit_req` directives and reload.

## IP reputation denylist (slice 2)

`denylist.conf` lists sources to reject at the edge with `403`, before any
proxying or app work. It ships empty. To block an IP:

```bash
echo 'deny 203.0.113.10;' >> nginx/denylist.conf   # single IP or CIDR
docker exec aegis-nginx nginx -s reload             # apply without downtime
```

Denied sources get `403` on all proxied routes. (The `/gateway-health` endpoint
stays reachable even from a denied IP — its `return` runs before the access
phase — so health probes are never locked out.)

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
