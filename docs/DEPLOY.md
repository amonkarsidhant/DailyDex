# Deploying DailyDex to a VM

Every command below runs **on the server**, over SSH. Replace `SERVER_IP` and
`deploy-user` with your own.

---

## 0. Before anything: the TLS constraint

`docker-compose.yml` sets `DAILYDEX_PRODUCTION=1`, which makes `init_auth`
**refuse to boot** without `DAILYDEX_AUTH_ENABLED=1`. This is deliberate and
fail-closed — a production deploy cannot accidentally run unauthenticated.

With auth enabled and `SESSION_COOKIE_SECURE=1` (the default), the session cookie
is named `__Host-dailydex_session`, and browsers **reject `__Host-` cookies over
plain HTTP**.

Consequence: served over `http://SERVER_IP:8888`, the app starts, the login form
submits, and you are silently never logged in — with no error explaining why.
Compose also binds `127.0.0.1:8888`, so the port is not reachable externally
until something fronts it.

Choose an access model before deploying:

| Option | When to use | Trade-off |
|---|---|---|
| **A. SSH tunnel** | Single-user cockpit — the common case | Zero public exposure. Needs `SESSION_COOKIE_SECURE=0`, which is safe because traffic never leaves the tunnel |
| **B. Domain + Caddy** | Others need browser access | Needs a DNS record for the host; real TLS issued automatically |
| **C. Self-signed cert** | Quick public test | Browser warning on every visit |

A is the smallest correct setup. B is right as soon as more than one person needs
access.

---

## 1. Install prerequisites and clone

```bash
sudo apt-get update -y && sudo apt-get install -y git curl
git clone https://github.com/amonkarsidhant/DailyDex.git
cd DailyDex
```

## 2. Create `.env`, generating secrets on the server

Generate them here rather than pasting them in, so they never pass through
another machine's shell history or a chat log.

```bash
cp .env.example .env
python3 - <<'PY'
import pathlib, re, secrets
p = pathlib.Path(".env"); t = p.read_text()
t = re.sub(r"^FLASK_SECRET_KEY=.*$", f"FLASK_SECRET_KEY={secrets.token_hex(32)}", t, flags=re.M)
t = re.sub(r"^AUTH_INVITE_CODE=.*$", f"AUTH_INVITE_CODE={secrets.token_urlsafe(24)}", t, flags=re.M)
p.write_text(t)
print("secrets written to .env")
PY
chmod 600 .env
```

The app enforces minimum lengths at boot: `FLASK_SECRET_KEY` ≥ 32 chars,
`AUTH_INVITE_CODE` ≥ 16 chars while signup is open.

Then set the access mode. **Option A (tunnel):**

```bash
sed -i 's/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=0/' .env
sed -i 's/^DAILYDEX_ALLOWED_HOSTS=.*/DAILYDEX_ALLOWED_HOSTS=localhost,127.0.0.1/' .env
sed -i 's|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=http://localhost:8888|' .env
```

**Option B (domain):** keep `SESSION_COOKIE_SECURE=1` and put your real hostname in
`DAILYDEX_ALLOWED_HOSTS` and `PUBLIC_BASE_URL`.

Finally set an LLM key. Without one, generation falls back to the rule-based clip
writer — quietly, so it is easy to ship rule-based scripts without noticing:

```bash
nano .env    # NVIDIA_API_KEY (free tier), or switch LLM_PROVIDER and its key
```

## 3. Deploy

```bash
bash deploy.sh
```

Installs Docker if absent, builds the three services (`web`, `orchestrator`,
`video-worker`), starts them, and polls `/health` for 60 seconds.

If Docker was installed fresh, log out and back in once so your user picks up the
`docker` group, then re-run.

## 4. Verify

```bash
curl -sf http://127.0.0.1:8888/health && echo OK
docker compose ps
docker compose logs --tail 40 web
```

Expect `web` healthy, `orchestrator` up, `video-worker` up. A restarting `web` is
almost always the auth contract:

```bash
docker compose logs web | grep -iE "DAILYDEX_AUTH_ENABLED|FLASK_SECRET_KEY|AUTH_INVITE_CODE"
```

| Log line | Cause |
|---|---|
| `DAILYDEX_AUTH_ENABLED=1 is required in production` | not set in `.env` |
| `FLASK_SECRET_KEY must be set to at least 32 characters` | secret generation step skipped |
| `AUTH_INVITE_CODE must be set to at least 16 characters` | same |

## 5. Reach it

**Option A** — from your workstation:

```bash
ssh -L 8888:127.0.0.1:8888 deploy-user@SERVER_IP
```

Leave the session open and browse `http://localhost:8888`.

**Option B** — on the server:

```bash
sudo apt-get install -y caddy
echo 'your-domain.example {
    reverse_proxy 127.0.0.1:8888
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

Caddy obtains a Let's Encrypt certificate automatically. Keep
`AUTH_TRUST_PROXY_HEADERS=1` so the app sees the real scheme and client IP.

## 6. First login

Register the **first** account using the invite code from `.env`. Signup closes
automatically once that account exists, so no second account can be created.

```bash
grep AUTH_INVITE_CODE .env
```

## 7. First content run

```bash
docker compose exec web python src/orchestrator.py --step fetch
docker compose logs -f orchestrator
```

The orchestrator then self-schedules: fetch every 2h, studio every 6h, analytics
sync every 6h.

---

## Ongoing operation

```bash
cd DailyDex && git pull && docker compose build && docker compose up -d   # update
docker compose logs -f orchestrator                                        # watch
docker compose down                                                        # stop
```

## Operational notes

- **Sizing.** Give the VM at least 2GB RAM, ideally 4GB. `video-worker` runs
  Chromium for Remotion renders and is the memory-hungry service.
- **Nothing auto-publishes.** Renders land in the factory queue as
  `pending_review`; publishing is always an explicit action.
- **YouTube upload** needs a Google Cloud OAuth client — connect at
  `/api/integrations/youtube/connect`. An upload costs roughly 1600 quota units
  against a 10,000/day default, so about 6 uploads per day without an increase.
- **LinkedIn carousels** render to PDF on the server. Posting them additionally
  requires a LinkedIn app with the `w_member_social` scope.
- **`CODE_GRAPH_ENABLED=0`** by default in production; it can expose source files.
- **Back up** the Docker volume `dailydex-data` — it holds the SQLite database,
  settings, and rendered media.
