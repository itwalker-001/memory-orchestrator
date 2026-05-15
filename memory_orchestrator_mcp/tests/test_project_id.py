from memory_orchestrator_mcp.project_id import normalize_git_remote, project_id_from_path


def test_https_github_normalized():
    assert normalize_git_remote("https://github.com/Foo/Bar.git") == "github.com/foo/bar"


def test_ssh_github_normalized():
    assert normalize_git_remote("git@github.com:Foo/Bar.git") == "github.com/foo/bar"


def test_http_without_git_suffix():
    assert normalize_git_remote("http://gitlab.com/a/b") == "gitlab.com/a/b"


def test_invalid_remote_returns_none():
    assert normalize_git_remote("") is None
    assert normalize_git_remote("not-a-url") is None


def test_path_fallback_deterministic():
    a = project_id_from_path("/home/user/work/proj")
    b = project_id_from_path("/home/user/work/proj")
    assert a == b
    assert a.startswith("local:")
    assert len(a) == len("local:") + 12


def test_path_fallback_different_paths_differ():
    a = project_id_from_path("/a")
    b = project_id_from_path("/b")
    assert a != b
