import asyncio
import uuid
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from memory_orchestrator_server.config import get_settings
from memory_orchestrator_server.models import Project, Session

IDS = [
    "2a42b8bb-17e6-4fe5-a0ee-0053d511956f",
    "f589f8bb-e0bd-49d6-8bbd-81c17f23b531",
    "b105c36c-0a84-46e5-b2c1-d36b476d64f6",
    "f485018b-6234-47d3-9136-ecfb6ad3bef4",
]


async def main():
    engine = create_async_engine(get_settings().db_dsn)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for sid in IDS:
            pid = uuid.UUID(sid)
            proj = await s.get(Project, pid)
            if proj is None:
                print(f"SKIP   {sid} (not found)")
                continue
            n = (await s.execute(
                select(func.count()).select_from(Session).where(Session.project_id == pid)
            )).scalar_one()
            await s.execute(delete(Session).where(Session.project_id == pid))
            await s.delete(proj)
            await s.commit()
            print(f"DELETED {sid}  name={proj.display_name}  sessions_removed={n}")
    await engine.dispose()


asyncio.run(main())
