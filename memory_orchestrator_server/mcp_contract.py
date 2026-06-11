from __future__ import annotations
from dataclasses import dataclass, field

# Minimal dataclasses replacing mcp.types — server only needs the schemas,
# not the full MCP protocol library.

@dataclass
class Tool:
    name: str
    description: str
    inputSchema: dict = field(default_factory=dict)


@dataclass
class Resource:
    name: str
    uri: str
    description: str = ""
    mimeType: str = "text/plain"


@dataclass
class ResourceTemplate:
    name: str
    uriTemplate: str
    description: str = ""
    mimeType: str = "text/plain"


TOOLS: list[Tool] = [
    Tool(name="search_memory", description="Retrieve memories by semantic similarity.",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string"}, "type": {"type": "array", "items": {"type": "string"}}, "top_k": {"type": "integer", "default": 3}}, "required": ["query"]}),
    Tool(name="save_memory", description="Write a memory to Memory Orchestrator; returns conflicts if near-duplicate exists.",
         inputSchema={"type": "object", "properties": {"type": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "content": {"type": "string"}, "why": {"type": "string"}, "how_to_apply": {"type": "string"}, "importance": {"type": "integer"}, "replace_id": {"type": "string"}}, "required": ["type", "name", "description", "content"]}),
    Tool(name="list_memories", description="List memory summaries.",
         inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string"}, "limit": {"type": "integer", "default": 50}}}),
    Tool(name="delete_memory", description="Soft or hard delete a memory.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "hard": {"type": "boolean"}}, "required": ["id"]}),
    Tool(name="promote_memory", description="Change memory importance.",
         inputSchema={"type": "object", "properties": {"id": {"type": "string"}, "importance": {"type": "integer"}}, "required": ["id"]}),
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
                 description="Read-only guide for memory-orchestrator."),
        Resource(name="Recent memories", uri=RESOURCE_RECENT, mimeType=RESOURCE_MIME,
                 description="Read-only summary of recent memories."),
    ]


def list_memory_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(name="Project memories", uriTemplate="memory://project/{slug}", mimeType=RESOURCE_MIME,
                         description="Read-only summary of memories for a project slug."),
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
        "Call the `save_memory` tool from this `memory-orchestrator` MCP server.",
        "Resources are read-only discovery/context surfaces.",
    ])
