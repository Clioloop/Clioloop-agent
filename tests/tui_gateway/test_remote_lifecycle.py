"""Focused contracts for authenticated backend-local Desktop lifecycle RPCs."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tui_gateway.remote_lifecycle import (
    BrowseGrantRegistry,
    RouteScope,
    RouteScopeError,
    UpdateCoordinator,
    canonical_route_key,
    discover_projects,
    read_project_tree,
    validate_route_scope,
)


class _RouteTransport:
    def __init__(self) -> None:
        self.route: str | None = None

    def bind_backend_route(self, route_key: str) -> bool:
        if self.route is None:
            self.route = route_key
        return self.route == route_key

    def write(self, obj: dict) -> bool:
        return True

    def close(self) -> None:
        pass


def test_route_scope_is_launch_profile_and_socket_bound(monkeypatch, tmp_path: Path) -> None:
    from clio_cli import profiles

    monkeypatch.setattr(profiles, "get_active_profile_name", lambda: "author")
    transport = _RouteTransport()
    route_key = canonical_route_key("url:https://box.test/clio", "author")
    params = {
        "connection_id": "url:https://box.test/clio",
        "profile": "author",
        "route_key": route_key,
    }

    scope = validate_route_scope(params, launch_home=tmp_path, transport=transport)
    assert scope.profile_home == tmp_path.resolve()
    assert transport.route == route_key

    other = {
        "connection_id": "other",
        "profile": "author",
        "route_key": canonical_route_key("other", "author"),
    }
    with pytest.raises(RouteScopeError, match="route changed"):
        validate_route_scope(other, launch_home=tmp_path, transport=transport)

    wrong_profile = {
        "connection_id": "x",
        "profile": "reviewer",
        "route_key": canonical_route_key("x", "reviewer"),
    }
    with pytest.raises(RouteScopeError, match="not served"):
        validate_route_scope(wrong_profile, launch_home=tmp_path)


def test_discovery_tree_grant_is_route_bound_and_blocks_escape(tmp_path: Path, monkeypatch) -> None:
    import tui_gateway.remote_lifecycle as lifecycle

    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(lifecycle, "BROWSE_GRANTS", BrowseGrantRegistry())
    scope = RouteScope("remote", "default", canonical_route_key("remote", "default"), tmp_path)
    project = discover_projects(scope, [str(root)])["projects"][0]
    listing = read_project_tree(scope, browse_token=project["browse_token"], path=str(root))

    assert listing["route_key"] == scope.route_key
    assert [entry["name"] for entry in listing["entries"]] == ["src", "escape"]
    with pytest.raises(RouteScopeError, match="escapes"):
        read_project_tree(scope, browse_token=project["browse_token"], path=str(root / "escape"))

    other = RouteScope("other", "default", canonical_route_key("other", "default"), tmp_path)
    with pytest.raises(RouteScopeError, match="unknown or expired"):
        read_project_tree(other, browse_token=project["browse_token"], path=str(root))


def test_update_coordinator_deduplicates_and_stays_bounded() -> None:
    coordinator = UpdateCoordinator(limit=1)
    started = threading.Event()
    release = threading.Event()
    results: list[dict] = []

    def work() -> dict:
        started.set()
        release.wait(2)
        return {"ok": True}

    owner = threading.Thread(target=lambda: results.append(coordinator.run("operation-1", work)))
    duplicate = threading.Thread(target=lambda: results.append(coordinator.run("operation-1", work)))
    owner.start()
    assert started.wait(1)
    duplicate.start()
    with pytest.raises(RouteScopeError, match="too many"):
        coordinator.run("operation-2", lambda: {"ok": True})
    release.set()
    owner.join(2)
    duplicate.join(2)

    assert results == [{"ok": True}, {"ok": True}]
    assert coordinator.run("operation-2", lambda: {"ok": True}) == {"ok": True}


def test_gateway_project_and_update_handlers_keep_route_contract(monkeypatch, tmp_path: Path) -> None:
    from tui_gateway import server
    import tui_gateway.remote_lifecycle as lifecycle

    root = tmp_path / "repo"
    root.mkdir()
    route_key = canonical_route_key("remote", "default")
    params = {"connection_id": "remote", "profile": "default", "route_key": route_key}
    transport = _RouteTransport()

    monkeypatch.setattr(server, "_clio_home", str(tmp_path))
    monkeypatch.setattr(lifecycle, "_resolve_profile_home", lambda profile, launch_home: tmp_path)
    monkeypatch.setattr(server, "perform_backend_update", lambda *args, **kwargs: {"ok": True, "message": "done"})
    server.UPDATE_COORDINATOR.clear()

    discovered = server.dispatch(
        {"id": "discover", "method": "project.discover", "params": {**params, "roots": [str(root)]}},
        transport,
    )
    assert discovered is not None
    project = discovered["result"]["projects"][0]
    tree = server.dispatch(
        {
            "id": "tree",
            "method": "project.tree",
            "params": {**params, "browse_token": project["browse_token"], "path": str(root)},
        },
        transport,
    )
    assert tree is not None and tree["result"]["route_key"] == route_key

    class _Writer(_RouteTransport):
        def __init__(self) -> None:
            super().__init__()
            self.response = None
            self.written = threading.Event()

        def write(self, obj: dict) -> bool:
            self.response = obj
            self.written.set()
            return True

    writer = _Writer()
    assert server.dispatch(
        {
            "id": "update",
            "method": "system.update",
            "params": {**params, "operation_id": "desktop-update-1"},
        },
        writer,
    ) is None
    assert writer.written.wait(2)
    assert writer.response["result"] == {
        "connection_id": "remote",
        "profile": "default",
        "route_key": route_key,
        "operation_id": "desktop-update-1",
        "ok": True,
        "message": "done",
    }
