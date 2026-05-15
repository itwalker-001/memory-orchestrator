from memory_orchestrator_server.ingestor import (
    MemoryCandidateWithNode, build_extraction_prompt_with_skeleton,
)


def test_memory_candidate_with_node_optional():
    m = MemoryCandidateWithNode(
        type="project", name="n", description="d", content="c",
        why="w", how_to_apply="h",
    )
    assert m.skeleton_node is None


def test_memory_candidate_with_node_set():
    m = MemoryCandidateWithNode(
        type="project", name="n", description="d", content="c",
        why="w", how_to_apply="h",
        skeleton_node={"name": "前端", "parent_name": None, "create_if_missing": False},
    )
    assert m.skeleton_node["name"] == "前端"


def test_build_extraction_prompt_with_skeleton_includes_nodes():
    skeleton = [
        {"name": "前端", "prompt_hint": "UI components", "children": []},
        {"name": "后端", "prompt_hint": "API logic", "children": []},
    ]
    prompt = build_extraction_prompt_with_skeleton("transcript text", "proj-123", skeleton)
    assert "前端" in prompt
    assert "UI components" in prompt
    assert "skeleton_node" in prompt


def test_build_extraction_prompt_no_skeleton_unchanged():
    from memory_orchestrator_server.ingestor import build_extraction_prompt
    prompt = build_extraction_prompt("transcript text", "proj-123")
    assert "transcript text" in prompt
    assert "proj-123" in prompt
