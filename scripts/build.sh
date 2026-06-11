#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
server_root="$repo_root/memory_orchestrator_server"

image="memory-orchestrator-server-base"
db_image="memory-orchestrator-db"
force=0
skip_token=0
admin_token_name="${MO_ADMIN_TOKEN_NAME:-bootstrap-admin}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)
      force=1
      ;;
    --skip-token)
      skip_token=1
      ;;
    --image)
      shift
      if [ "$#" -eq 0 ]; then
        echo "missing value for --image" >&2
        exit 2
      fi
      image="$1"
      ;;
    --admin-token-name)
      shift
      if [ "$#" -eq 0 ]; then
        echo "missing value for --admin-token-name" >&2
        exit 2
      fi
      admin_token_name="$1"
      ;;
    *)
      echo "usage: $0 [--force] [--skip-token] [--image IMAGE] [--admin-token-name NAME]" >&2
      echo "  (no flags)   rebuild app image using cached base; always recompiles server code" >&2
      echo "  --force      also rebuild base image (heavy: Python deps + ML models)" >&2
      echo "  --skip-token skip ui_admin token creation/rotation" >&2
      exit 2
      ;;
  esac
  shift
done

cd "$server_root"

hash_files="Dockerfile.base pyproject.toml uv.lock download_models.py"

for file in $hash_files; do
  if [ ! -f "$file" ]; then
    echo "missing hash input: $file" >&2
    exit 1
  fi
done

hash="$(
  sha256sum $hash_files \
    | sha256sum \
    | awk '{print substr($1, 1, 12)}'
)"
tag="${image}:${hash}"

if [ "$force" -eq 0 ] && docker image inspect "$tag" >/dev/null 2>&1; then
  echo "Base image already exists: $tag"
else
  docker build -f Dockerfile.base -t "$tag" -t "${image}:latest" .
fi

echo "MO_BASE_IMAGE=$tag"

cd "$repo_root"

db_hash="$(
  sha256sum Dockerfile.db \
    | sha256sum \
    | awk '{print substr($1, 1, 12)}'
)"
db_tag="${db_image}:${db_hash}"

if [ "$force" -eq 0 ] && docker image inspect "$db_tag" >/dev/null 2>&1; then
  echo "Database image already exists: $db_tag"
else
  docker build -f Dockerfile.db -t "$db_tag" -t "${db_image}:latest" .
fi

echo "MO_DB_IMAGE=$db_tag"

# Write computed image tags back to .env (upsert: replace if exists, append if missing)
env_file="$repo_root/.env"
set_env() {
  key="$1" val="$2"
  tmp="$(mktemp)"
  grep -v "^${key}=" "$env_file" > "$tmp" 2>/dev/null || true
  echo "${key}=${val}" >> "$tmp"
  mv "$tmp" "$env_file"
}
set_env MO_BASE_IMAGE "$tag"
set_env MO_DB_IMAGE "$db_tag"

# MO_DB_DSN is not written to .env; docker-compose.yml assembles it inline from
# POSTGRES_USER / MO_DB_PASSWORD / MO_DB_HOST / MO_DB_PORT / POSTGRES_DB.
echo "Updated .env: MO_BASE_IMAGE=$tag  MO_DB_IMAGE=$db_tag"

# Download models if not already present on host
models_dir="$(grep '^MO_MODELS_DIR=' "$env_file" | cut -d= -f2-)"
case "$models_dir" in
  /*) : ;;
  *)  models_dir="$repo_root/$models_dir" ;;
esac
if [ ! -d "$models_dir/BAAI/bge-m3" ]; then
  echo "Models not found, downloading via base image..."
  docker run --rm \
    -v "$models_dir:/app/memory_orchestrator_server/models" \
    -v "$server_root/download_models.py:/app/memory_orchestrator_server/download_models.py:ro" \
    "${tag}" \
    python /app/memory_orchestrator_server/download_models.py
  echo "Models downloaded to $models_dir"
else
  echo "Models already present: $models_dir"
fi

# Ensure postgres data directory exists (Docker does not auto-create bind mount dirs)
pgdata="$(grep '^MO_PGDATA=' "$env_file" | cut -d= -f2-)"
# Resolve relative path against repo root
case "$pgdata" in
  /*) : ;;
  *)  pgdata="$repo_root/$pgdata" ;;
esac
mkdir -p "$pgdata"
echo "Postgres data dir: $pgdata"

compose_cmd="${COMPOSE_CMD:-docker-compose}"
# --force also passes --no-cache to compose so the app layer is rebuilt without Docker cache
compose_build_opts=""
[ "$force" -eq 1 ] && compose_build_opts="--no-cache"
echo "Deploying services with MO_BASE_IMAGE=$tag MO_DB_IMAGE=$db_tag"

# wait_healthy <container> <max_seconds> <interval_seconds> <label>
# Polls docker health status; exits 1 immediately on unhealthy or timeout.
wait_healthy() {
  container="$1" max_sec="$2" interval="$3" label="$4"
  elapsed=0
  echo "Waiting for ${label} to become healthy (up to ${max_sec} s)..."
  while [ "$elapsed" -le "$max_sec" ]; do
    h="$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo 'missing')"
    case "$h" in
      healthy)
        echo "${label} healthy after ${elapsed} s"
        return 0
        ;;
      unhealthy)
        echo "ERROR: ${label} is unhealthy" >&2
        docker logs --tail 30 "$container" >&2 2>/dev/null || true
        return 1
        ;;
    esac
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  echo "ERROR: ${label} did not become healthy within ${max_sec} s" >&2
  docker logs --tail 30 "$container" >&2 2>/dev/null || true
  return 1
}

# 1. Start (and build) the database
#    NOTE: --no-cache is a `build` flag, not an `up` flag; only apply it to the
#    explicit `build` step below (server). The db image is selected by hash tag.
"$compose_cmd" --env-file "$env_file" up -d --build db

# 2. Wait for database to become healthy
wait_healthy memory-orchestrator-db 90 1 "Database" || { "$compose_cmd" ps; exit 1; }

# 3. Build server image first — migrations run with the NEW code, not the previous image.
#    CACHE_BUST forces the app layer to always recompile.
cache_bust="$(date +%s)"
# shellcheck disable=SC2086
"$compose_cmd" --env-file "$env_file" build $compose_build_opts \
  --build-arg "CACHE_BUST=${cache_bust}" \
  server

# 4. Run database migrations using the freshly built image
echo "Running database migrations..."
"$compose_cmd" --env-file "$env_file" run --rm \
  server \
  sh -c "cd /app/memory_orchestrator_server && alembic upgrade head"

# 5. Start server
"$compose_cmd" --env-file "$env_file" up -d server

# 6. Wait for server healthy
wait_healthy memory-orchestrator-server 450 2 "Service" || "$compose_cmd" ps

if [ "$skip_token" -eq 1 ]; then
  echo "Skipping token creation (--skip-token)."
else
  token_output="$(
    "$compose_cmd" exec -T server \
      mo-server token create --kind ui_admin --name "$admin_token_name"
  )"
  echo
  echo "ADMIN TOKEN"
  echo "==========="
  echo "$token_output"
fi
