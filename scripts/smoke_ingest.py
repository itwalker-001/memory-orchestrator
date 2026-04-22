"""Feed a short fake transcript into /ingest and verify memories appear."""
import asyncio
import json
import tempfile
import time
from pathlib import Path
import httpx


TRANSCRIPT = [
    {"role": "user", "content": "don't mock the database in these tests — we got burned last quarter"},
    {"role": "assistant", "content": "understood — will use real DB for integration tests"},
    {"role": "user", "content": "good. Also, I'm a senior Go dev, new to Python."},
    {"role": "assistant", "content": "got it"},
]


async def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        tp = Path(d) / "transcript.jsonl"
        with tp.open("w") as f:
            for line in TRANSCRIPT:
                f.write(json.dumps(line) + "\n")

        async with httpx.AsyncClient() as c:
            r = await c.post(
                "http://localhost:8765/ingest",
                json={
                    "session_id": f"smoke-{int(time.time())}",
                    "project_id": "github.com/smoke/test",
                    "transcript_path": str(tp),
                },
            )
            assert r.status_code == 202, r.text
            print("ingest accepted")

            await asyncio.sleep(8)
            r = await c.get("http://localhost:8765/stats", params={"project_id": "*"})
            print("global stats:", r.json())
            r2 = await c.get("http://localhost:8765/stats", params={"project_id": "github.com/smoke/test"})
            print("project stats:", r2.json())


if __name__ == "__main__":
    asyncio.run(main())
