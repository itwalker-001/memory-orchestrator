"""Quick graph dump: vertices + edges from Apache AGE memory_graph."""
import asyncio
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DSN = os.getenv(
    "MO_DB_DSN",
    "postgresql+asyncpg://postgres:mo_secret@172.16.10.124:15432/memory_orchestrator",
)
GRAPH = "memory_graph"


async def main() -> None:
    engine = create_async_engine(DSN)
    async with engine.connect() as conn:
        # ── check AGE ──
        try:
            await conn.execute(text("LOAD 'age'"))
            await conn.execute(text('SET LOCAL search_path = ag_catalog, "$user", public'))
        except Exception as e:
            print(f"[ERROR] AGE not available: {e}")
            return

        # ── vertices ──
        print("=" * 60)
        print("VERTICES (Memory nodes)")
        print("=" * 60)
        try:
            rows = await conn.execute(
                text(
                    f"SELECT * FROM cypher('{GRAPH}', $$ "
                    f"MATCH (m:Memory) RETURN m.id, m.type ORDER BY m.type "
                    f"$$) AS (mid agtype, mtype agtype)"
                )
            )
            vertices = list(rows)
            if not vertices:
                print("  (no vertices)")
            for row in vertices:
                mid = str(row[0]).strip('"')
                mtype = str(row[1]).strip('"')
                print(f"  [{mtype:12s}]  {mid}")
        except Exception as e:
            print(f"  [ERROR] {e}")

        # ── edges ──
        print()
        print("=" * 60)
        print("EDGES (Relations)")
        print("=" * 60)
        try:
            rows = await conn.execute(
                text(
                    f"SELECT * FROM cypher('{GRAPH}', $$ "
                    f"MATCH (a:Memory)-[r]->(b:Memory) "
                    f"RETURN a.id, r.rel_type, b.id "
                    f"$$) AS (src agtype, rel agtype, tgt agtype)"
                )
            )
            edges = list(rows)
            if not edges:
                print("  (no edges)")
            for row in edges:
                src = str(row[0]).strip('"')
                rel = str(row[1]).strip('"')
                tgt = str(row[2]).strip('"')
                print(f"  {src[:8]}…  --[{rel}]-->  {tgt[:8]}…")
        except Exception as e:
            print(f"  [ERROR] {e}")

        # ── summary ──
        print()
        print(f"Total vertices: {len(vertices) if 'vertices' in dir() else '?'}")
        print(f"Total edges:    {len(edges) if 'edges' in dir() else '?'}")

    await engine.dispose()


asyncio.run(main())
