# Scripts

## install_pgvector.ps1

Installs pgvector extension files into a local Windows PostgreSQL 16 install.

**Requires Administrator privileges** (writes to `C:\Program Files\PostgreSQL\16`).

### Usage

```powershell
# Open an elevated PowerShell, then:
cd D:\AIPROJECT\memory-orchestrator
powershell -ExecutionPolicy Bypass -File scripts\install_pgvector.ps1
```

After success, enable the extension in the target database:

```sql
CREATE EXTENSION vector;
```

### Where the binaries come from

`scripts/pgvector/` holds the extracted contents of
[pgvector v0.8.2 for PostgreSQL 16 Windows build](https://github.com/andreiramani/pgvector_pgsql_windows/releases/tag/0.8.2_16.1)
by @andreiramani. Re-download from there if you need a different pgvector or PG major version.
