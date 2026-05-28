#!/usr/bin/env bash
# =============================================================================
# DailyDex — One-shot deploy script
# Run from the project root on your Mac:
#   chmod +x deploy.sh && ./deploy.sh
#
# What this does:
#   1. Reads credentials from .env
#   2. Creates a Supabase project named "dailydex"
#   3. Runs the Postgres schema migration
#   4. Sets all required Vercel environment variables
#   5. Deploys to Vercel
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]  ${NC} $*"; }
error() { echo -e "${RED}[error] ${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
    error ".env file not found — run from the project root."
fi
set -a; source .env; set +a

[[ -z "${VERCEL_TOKEN:-}" ]]    && error "VERCEL_TOKEN is not set in .env"
[[ -z "${SUPABASE_TOKEN:-}" ]]  && error "SUPABASE_TOKEN is not set in .env"

# ── Check dependencies ────────────────────────────────────────────────────────
command -v vercel  >/dev/null 2>&1 || error "Vercel CLI not found. Install: npm install -g vercel"
command -v psql    >/dev/null 2>&1 || warn  "psql not found — schema migration step will be skipped"
command -v curl    >/dev/null 2>&1 || error "curl is required"
command -v jq      >/dev/null 2>&1 || error "jq is required (brew install jq)"

# ── Step 1: Get Supabase org ID ───────────────────────────────────────────────
info "Fetching Supabase organisations…"
ORGS_JSON=$(curl -sf -X GET "https://api.supabase.com/v1/organizations" \
    -H "Authorization: Bearer ${SUPABASE_TOKEN}" \
    -H "Content-Type: application/json")

ORG_ID=$(echo "$ORGS_JSON" | jq -r '.[0].id // empty')
[[ -z "$ORG_ID" ]] && error "Could not find a Supabase organisation. Check your token."
info "Using org: $ORG_ID"

# ── Step 2: Create (or reuse) Supabase project ────────────────────────────────
info "Checking for existing 'dailydex' project…"
PROJECTS_JSON=$(curl -sf -X GET "https://api.supabase.com/v1/projects" \
    -H "Authorization: Bearer ${SUPABASE_TOKEN}" \
    -H "Content-Type: application/json")

PROJECT_REF=$(echo "$PROJECTS_JSON" | jq -r '.[] | select((.name|ascii_downcase)=="dailydex") | .id // empty' | head -1)

if [[ -n "$PROJECT_REF" ]]; then
    info "Found existing project: $PROJECT_REF — skipping creation."
    # If no SUPABASE_DB_PASSWORD recorded, reset it via API so we can build DATABASE_URL
    if [[ -z "${SUPABASE_DB_PASSWORD:-}" ]]; then
        info "No SUPABASE_DB_PASSWORD in .env — resetting DB password via API…"
        DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 24 || true)
        RESET_RESP=$(curl -sf -X PATCH "https://api.supabase.com/v1/projects/${PROJECT_REF}/config/database" \
            -H "Authorization: Bearer ${SUPABASE_TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{\"password\":\"${DB_PASSWORD}\"}" || echo "RESET_FAIL")
        if [[ "$RESET_RESP" == "RESET_FAIL" ]]; then
            warn "DB password reset failed — set SUPABASE_DB_PASSWORD in .env manually."
        else
            echo "" >> .env
            echo "# Supabase DB password (reset by deploy.sh)" >> .env
            echo "SUPABASE_DB_PASSWORD=${DB_PASSWORD}" >> .env
            export SUPABASE_DB_PASSWORD="${DB_PASSWORD}"
            info "DB password reset and saved."
        fi
    fi
else
    info "Creating new Supabase project 'dailydex'…"
    # Generate a random DB password (avoid SIGPIPE from /dev/urandom | head under pipefail)
    DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 24 || true)

    CREATE_JSON=$(curl -sf -X POST "https://api.supabase.com/v1/projects" \
        -H "Authorization: Bearer ${SUPABASE_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
          \"name\":          \"dailydex\",
          \"organization_id\": \"${ORG_ID}\",
          \"region\":        \"us-east-1\",
          \"plan\":          \"free\",
          \"db_pass\":       \"${DB_PASSWORD}\"
        }")

    PROJECT_REF=$(echo "$CREATE_JSON" | jq -r '.id // empty')
    [[ -z "$PROJECT_REF" ]] && { echo "$CREATE_JSON"; error "Project creation failed."; }
    info "Project created: $PROJECT_REF"

    # Wait for the project to be ready (up to 3 min)
    info "Waiting for Supabase project to come online…"
    for i in $(seq 1 36); do
        STATUS=$(curl -sf "https://api.supabase.com/v1/projects/${PROJECT_REF}" \
            -H "Authorization: Bearer ${SUPABASE_TOKEN}" | jq -r '.status // "unknown"')
        info "  status: $STATUS (${i}/36)"
        [[ "$STATUS" == "ACTIVE_HEALTHY" ]] && break
        sleep 5
    done
    [[ "$STATUS" != "ACTIVE_HEALTHY" ]] && warn "Project may not be fully ready — proceeding anyway."

    # Persist DB password to .env so user has it
    echo "" >> .env
    echo "# Supabase DB password (generated by deploy.sh)" >> .env
    echo "SUPABASE_DB_PASSWORD=${DB_PASSWORD}" >> .env
fi

# ── Step 3: Fetch connection details ──────────────────────────────────────────
info "Fetching project connection strings…"
PROJ_JSON=$(curl -sf "https://api.supabase.com/v1/projects/${PROJECT_REF}" \
    -H "Authorization: Bearer ${SUPABASE_TOKEN}")

SUPABASE_URL="https://${PROJECT_REF}.supabase.co"
SUPABASE_DB_HOST=$(echo "$PROJ_JSON" | jq -r '.db_host // "db.'${PROJECT_REF}'.supabase.co"')

# Fetch API keys
KEYS_JSON=$(curl -sf "https://api.supabase.com/v1/projects/${PROJECT_REF}/api-keys" \
    -H "Authorization: Bearer ${SUPABASE_TOKEN}")
SUPABASE_ANON_KEY=$(echo "$KEYS_JSON"     | jq -r '.[] | select(.name=="anon") | .api_key // empty')
SUPABASE_SERVICE_KEY=$(echo "$KEYS_JSON"  | jq -r '.[] | select(.name=="service_role") | .api_key // empty')

# Build DATABASE_URL using the Transaction pooler (port 6543) for serverless
DB_PASS="${SUPABASE_DB_PASSWORD:-}"
if [[ -z "$DB_PASS" ]]; then
    warn "SUPABASE_DB_PASSWORD not set in .env — DATABASE_URL will need to be set manually."
    DATABASE_URL="postgresql://postgres:YOUR_DB_PASS@db.${PROJECT_REF}.supabase.co:5432/postgres"
else
    # Use the pooler endpoint for serverless (Supabase Transaction pooler)
    DATABASE_URL="postgresql://postgres.${PROJECT_REF}:${DB_PASS}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
fi

# Update .env with all connection info
{
    echo ""
    echo "# Supabase connection details (populated by deploy.sh)"
    echo "SUPABASE_URL=${SUPABASE_URL}"
    echo "SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}"
    echo "SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_KEY}"
    echo "DATABASE_URL=${DATABASE_URL}"
} >> .env

info "Connection details saved to .env"

# ── Step 4: Run schema migration ──────────────────────────────────────────────
if command -v psql >/dev/null 2>&1 && [[ "$DATABASE_URL" != *"YOUR_DB_PASS"* ]]; then
    info "Running Postgres schema migration…"
    psql "$DATABASE_URL" -f supabase_schema.sql && info "Schema migration complete."
else
    warn "Skipping auto-migration. Run manually:"
    warn "  psql \"\$DATABASE_URL\" -f supabase_schema.sql"
    warn "or paste supabase_schema.sql into the Supabase SQL editor at:"
    warn "  https://supabase.com/dashboard/project/${PROJECT_REF}/sql/new"
fi

# ── Step 5: Set Vercel env vars ───────────────────────────────────────────────
info "Configuring Vercel project environment variables…"

set_vercel_env() {
    local KEY="$1" VAL="$2" TARGET="${3:-production,preview}"
    echo "$VAL" | vercel env add "$KEY" "$TARGET" \
        --token "$VERCEL_TOKEN" --yes 2>/dev/null || \
    vercel env rm "$KEY" "$TARGET" --token "$VERCEL_TOKEN" --yes 2>/dev/null && \
    echo "$VAL" | vercel env add "$KEY" "$TARGET" \
        --token "$VERCEL_TOKEN" --yes 2>/dev/null
}

# Required secrets
set_vercel_env "DATABASE_URL"              "$DATABASE_URL"
set_vercel_env "SUPABASE_URL"              "$SUPABASE_URL"
set_vercel_env "SUPABASE_ANON_KEY"         "$SUPABASE_ANON_KEY"
set_vercel_env "SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_SERVICE_KEY"
set_vercel_env "CREATOR_ENRICHER_PRIMARY"  "0"

# Forward any ANTHROPIC_API_KEY present locally
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    set_vercel_env "ANTHROPIC_API_KEY" "$ANTHROPIC_API_KEY"
    info "ANTHROPIC_API_KEY forwarded to Vercel."
fi

info "Environment variables set."

# ── Step 6: Deploy to Vercel ──────────────────────────────────────────────────
info "Deploying DailyDex to Vercel…"
DEPLOY_OUTPUT=$(vercel --token "$VERCEL_TOKEN" \
    --prod \
    --yes \
    --name "dailydex" \
    2>&1)

echo "$DEPLOY_OUTPUT"

DEPLOY_URL=$(echo "$DEPLOY_OUTPUT" | grep -Eo 'https://[a-z0-9\-]+\.vercel\.app' | tail -1)

if [[ -n "$DEPLOY_URL" ]]; then
    info "✅ Deployed! Live at: $DEPLOY_URL"
    echo "" >> .env
    echo "VERCEL_DEPLOY_URL=${DEPLOY_URL}" >> .env
else
    warn "Could not extract deploy URL from output above — check Vercel dashboard."
fi

info "─────────────────────────────────────────────────────────"
info "Next steps:"
info "  1. Open ${DEPLOY_URL:-https://vercel.com/dashboard} to verify"
info "  2. If schema migration was skipped, paste supabase_schema.sql"
info "     into: https://supabase.com/dashboard/project/${PROJECT_REF}/sql/new"
info "  3. Set ANTHROPIC_API_KEY on Vercel if not done:"
info "     vercel env add ANTHROPIC_API_KEY production --token \$VERCEL_TOKEN"
info "─────────────────────────────────────────────────────────"
