from memory_orchestrator_server.repository import _minmax_norm


def test_minmax_norm_basic():
    out = _minmax_norm({"a": 2.0, "b": 4.0, "c": 6.0})
    assert out["a"] == 0.0
    assert out["c"] == 1.0
    assert abs(out["b"] - 0.5) < 1e-9


def test_minmax_norm_single_value_maps_to_one():
    # 只有一个候选时，max==min，应映射为 1.0（满分），不能除零。
    assert _minmax_norm({"x": 3.7}) == {"x": 1.0}


def test_minmax_norm_empty():
    assert _minmax_norm({}) == {}


def test_minmax_norm_all_equal():
    out = _minmax_norm({"a": 5.0, "b": 5.0})
    assert out == {"a": 1.0, "b": 1.0}
