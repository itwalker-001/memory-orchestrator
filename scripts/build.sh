#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
server_root="$repo_root/memory_orchestrator_server"

image="memory-orchestrator-server-base"
db_image="memory-orchestrator-db"
force=0
admin_token_name="${MO_ADMIN_TOKEN_NAME:-bootstrap-admin}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)
      force=1
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
      echo "usage: $0 [--force] [--image IMAGE] [--admin-token-name NAME]" >&2
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
echo "Updated .env: MO_BASE_IMAGE=$tag  MO_DB_IMAGE=$db_tag"

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
echo "Deploying services with MO_BASE_IMAGE=$tag MO_DB_IMAGE=$db_tag"
"$compose_cmd" --env-file "$env_file" up -d --build

echo "Waiting for server to become healthy (up to 450 s)..."
i=0
while [ "$i" -lt 90 ]; do
  status="$(docker inspect --format='{{.State.Health.Status}}' memory-orchestrator-server 2>/dev/null || echo 'unknown')"
  if [ "$status" = "healthy" ]; then
    echo "Service healthy after $((i * 5)) s"
    break
  fi
  i=$((i + 1))
  sleep 5
done

if [ "$i" -ge 90 ]; then
  echo "WARNING: health check timed out after 450 s — service may still be starting" >&2
  "$compose_cmd" ps
fi

token_output="$(
  "$compose_cmd" exec -T server \
    mo-server token create --kind ui_admin --name "$admin_token_name"
)"

echo
echo "ADMIN TOKEN"
echo "==========="
echo "$token_output"
