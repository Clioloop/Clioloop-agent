import json
import sqlite3
import zipfile

from clio_db_maintenance import database_check, optimize_database, repair_database
from clio_profile_bundle import export_profile_bundle, import_profile_bundle
from clio_projects import ProjectsDB
from clio_state import SessionDB


def test_metadata_routing_and_text_roundtrip(tmp_path):
    source = SessionDB(tmp_path / "source.db")
    source.create_session("parent", "cli")
    source.end_session("parent", "compression")
    source.create_session("child", "cli", parent_session_id="parent")
    source.append_message("child", "user", "日本語の検索テスト")
    assert source.set_session_pinned("child", True)
    assert source.set_session_hidden("child", True)
    assert source.set_session_read("child", False)
    assert source.get_session("parent")["pinned"] == 1
    assert source.get_session("child")["hidden"] == 1
    assert source.session_unread(source.get_session("child"))

    source.save_gateway_routing_entry("good", json.dumps({"platform": "telegram"}))
    source.save_gateway_routing_entry("bad", "not-json")
    assert source.repair_gateway_routing() == {"checked": 2, "removed": 1, "kept": 1}
    assert set(source.load_gateway_routing_entries()) == {"good"}

    for fmt in ("jsonl", "markdown", "html"):
        text = source.export_session_text("child", fmt)
        dest = SessionDB(tmp_path / f"dest-{fmt}.db")
        result = dest.import_session_text(text, fmt)
        assert result["imported"] == 1
        assert dest.get_messages("child")[0]["content"] == "日本語の検索テスト"
        dest.close()
    if source._fts_enabled:
        assert source.search_messages("日本語")
    source.close()


def test_non_destructive_maintenance(tmp_path):
    path = tmp_path / "state.db"
    db = SessionDB(path)
    db.create_session("s", "cli")
    db.append_message("s", "user", "hello")
    db.close()
    before = path.read_bytes()
    repaired = repair_database(path)
    optimized = optimize_database(path)
    assert database_check(repaired)["ok"]
    assert database_check(optimized)["ok"]
    assert path.read_bytes() == before


def test_profile_bundle_excludes_secrets_and_rejects_traversal(tmp_path):
    profile = tmp_path / "profile"
    (profile / "skills" / "demo").mkdir(parents=True)
    (profile / "skills" / "demo" / "SKILL.md").write_text("safe")
    (profile / "credentials.json").write_text("secret")
    (profile / "config.json").write_text(json.dumps({"theme": "dark", "api_key": "abc"}))
    bundle = export_profile_bundle(profile, tmp_path / "profile.zip")
    with zipfile.ZipFile(bundle) as zf:
        assert "credentials.json" not in zf.namelist()
        assert json.loads(zf.read("config.json"))["api_key"] == "<redacted>"
    restored = tmp_path / "restored"
    assert import_profile_bundle(bundle, restored) == 2
    assert (restored / "skills" / "demo" / "SKILL.md").read_text() == "safe"


def test_projects_workspaces_and_session_moves(tmp_path):
    projects = ProjectsDB(tmp_path / "projects.db")
    one = projects.create_project("One")
    two = projects.create_project("Two")
    repo = tmp_path / "repo"
    worktree = repo / ".worktrees" / "feature"
    projects.add_workspace(one, str(repo), repo_root=str(repo), primary=True)
    projects.add_workspace(two, str(worktree), repo_root=str(repo), worktree_path=str(worktree), branch="feature")
    assert projects.project_for_session("implicit", cwd=str(worktree / "src")) == two
    projects.move_session("s1", one)
    projects.move_session("s1", two)
    assert projects.project_for_session("s1") == two
    assert projects.list_projects()[1]["session_ids"] == ["s1"]
    projects.close()
