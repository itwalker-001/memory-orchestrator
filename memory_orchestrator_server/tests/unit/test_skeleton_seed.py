from memory_orchestrator_server.repository import BUILTIN_SKELETON_NODES


def test_builtin_nodes_count():
    assert len(BUILTIN_SKELETON_NODES) == 11


def test_builtin_nodes_names():
    names = [n["name"] for n in BUILTIN_SKELETON_NODES]
    assert names == [
        "项目概况", "需求", "设计", "技术栈", "前端",
        "后端", "数据库", "测试", "部署", "决策记录", "经验库",
    ]


def test_builtin_nodes_have_required_keys():
    for node in BUILTIN_SKELETON_NODES:
        assert "name" in node
        assert "description" in node
        assert "prompt_hint" in node
        assert "sort_order" in node
