"""End-to-end smoke: save a memory, search it back via MCP client."""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command="python", args=["-m", "memory_orchestrator.cli", "serve-mcp"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert "save_memory" in names and "search_memory" in names
            print("tools ok:", names)

            r = await session.call_tool("save_memory", {
                "type": "user", "name": "smoke-role",
                "description": "smoke test user memory",
                "content": "the user is running a smoke test for memory orchestrator",
            })
            print("save:", r.content[0].text)

            r = await session.call_tool("search_memory", {
                "query": "smoke test memory orchestrator", "top_k": 3,
            })
            print("search:", r.content[0].text)
            data = json.loads(r.content[0].text)
            assert any("smoke-role" == m["name"] for m in data)
            print("smoke OK")


if __name__ == "__main__":
    asyncio.run(main())
