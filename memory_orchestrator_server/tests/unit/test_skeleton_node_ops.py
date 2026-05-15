"""Unit tests for skeleton node repository operations (no DB required)."""
from memory_orchestrator_server.repository import BUILTIN_SKELETON_NODES


def test_builtin_skeleton_nodes_have_tags():
    for node in BUILTIN_SKELETON_NODES:
        assert "tags" in node, f"Node '{node['name']}' missing tags"
        assert isinstance(node["tags"], list)
        assert len(node["tags"]) > 0, f"Node '{node['name']}' has empty tags"


def test_builtin_skeleton_nodes_count():
    assert len(BUILTIN_SKELETON_NODES) == 11


def test_builtin_skeleton_nodes_sort_order():
    orders = [n["sort_order"] for n in BUILTIN_SKELETON_NODES]
    assert orders == list(range(11))
