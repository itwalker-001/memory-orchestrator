#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
env_file="$repo_root/.env"

# 读取 .env
pg_user="$(grep '^POSTGRES_USER=' "$env_file" | cut -d= -f2-)"
pg_db="$(grep '^POSTGRES_DB=' "$env_file" | cut -d= -f2-)"
db_container="memory-orchestrator-db"

# 备份目录（默认 repo_root/backups，可用 BACKUP_DIR 覆盖）
backup_dir="${BACKUP_DIR:-$repo_root/backups}"
mkdir -p "$backup_dir"

timestamp="$(date +%Y%m%d_%H%M%S)"
backup_file="$backup_dir/${pg_db}_${timestamp}.dump"

echo "Backing up $pg_db → $backup_file"

docker exec "$db_container" \
  pg_dump -U "$pg_user" -d "$pg_db" -F c \
  | cat > "$backup_file"

size="$(du -sh "$backup_file" | cut -f1)"
echo "Done: $backup_file ($size)"

# 保留最近 7 份，自动删除旧备份
keep=7
ls -1t "$backup_dir/${pg_db}_"*.dump 2>/dev/null \
  | tail -n +$((keep + 1)) \
  | xargs -r rm -f
echo "Retention: kept latest $keep backups"
