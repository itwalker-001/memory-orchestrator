from pathlib import Path


APP_VUE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.vue"


def test_admin_opens_as_modal_over_memories_view():
    source = APP_VUE.read_text(encoding="utf-8")

    assert "@click=\"openAdminModal\"" in source
    assert "v-if=\"adminOpen\"" in source
    assert "class=\"modal-overlay admin-overlay\"" in source
    assert "const adminOpen = ref(window.location.pathname.replace(/\\/$/, '').endsWith('/admin'))" in source
    assert "window.history.replaceState(null, '', '/ui/')" in source
    assert "currentPage === 'admin'" not in source
