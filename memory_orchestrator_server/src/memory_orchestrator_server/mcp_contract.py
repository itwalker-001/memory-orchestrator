from __future__ import annotations

from mcp.types import Resource, ResourceTemplate, Tool

TOOLS: list[Tool] = [
    Tool(name="search_memory", description="Retrieve memories by semantic similarity.",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string"}, "type": {"type": "array", "items": {"type": "string"}}, "top_k": {"type": "integer", "default": 3}}, "required": ["query"]}),
    Tool(name="save_memory", description="Write a memory to Memory Orchestrator; returns conflicts if near-duplicate exists.",
         inputSchema={"type": "object", "properties": {"type": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "content": {"type": "string"}, "project_id": {"type": "string"}, "why": {"type": "string"}, "how_to_apply": {"type": "string"}, "importance": {"type": "integer"}, "replace_id": {"type": "string"}}, "required": ["type", "name", "description", "content"]}),
    Tool(name="list_memories", description="List memory summaries.",
         inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string"}, "limit": {"type": "integer", "default": 50}}}),
    Tool(name="delete_memory", description="Soft or hard delete a memory.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "hard": {"type": "boolean"}}, "required": ["id"]}),
    Tool(name="promote_memory", description="Change importance or scope.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "importance": {"type": "integer"}, "make_global": {"type": "boolean"}}, "required": ["id"]}),
    Tool(name="ingest_session", description="Ingest transcript for auto extraction.",
         inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "project_id": {"type": "string"}, "transcript_path": {"type": "string"}}, "required": ["session_id", "transcript_path"]}),
]

RESOURCE_GUIDE = "memory://orchestrator/guide"
RESOURCE_RECENT = "memory://recent"
RESOURCE_PROJECT_PREFIX = "memory://project/"
RESOURCE_MIME = "text/markdown"


def list_memory_resources() -> list[Resource]:
    return [
        Resource(name="Memory Orchestrator MCP guide", uri=RESOURCE_GUIDE, mimeType=RESOURCE_MIME,
                 description="Read-only guide for memory-orchestrator. Writes are available through the MCP tool save_memory on this server, not resources/templates."),
        Resource(name="Recent memories", uri=RESOURCE_RECENT, mimeType=RESOURCE_MIME,
                 description="Read-only summary of recent memories. To write memories, call the save_memory tool from this MCP server."),
    ]


def list_memory_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(name="Project memories", uriTemplate="memory://project/{slug}", mimeType=RESOURCE_MIME,
                         description="Read-only summary of memories for a project slug. To write memories, call the save_memory tool from this MCP server with project_id."),
    ]


def memory_resource_guide() -> str:
    return "\n".join([
        "# Memory Orchestrator MCP", "",
        "This server exposes memories mainly as MCP tools.", "",
        "Use these tools:",
        "- `search_memory` to retrieve relevant memories.",
        "- `list_memories` to inspect memory summaries.",
        "- `save_memory` to write memories.",
        "- `promote_memory` to change importance or scope.",
        "- `delete_memory` to remove memories.", "",
        "Call the `save_memory` tool from this `memory-orchestrator` MCP server. Some "
        "clients may display that as `memory-orchestrator.save_memory`, but the tool "
        "name exposed by this server is `save_memory`.", "",
        "Resources are read-only discovery/context surfaces. Do not infer that writing is "
        "unavailable because resources/templates are read-only; write by calling "
        "the `save_memory` tool.",
    ])
