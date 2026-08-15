"""Security and round-trip tests for the profile-scoped dashboard workspace."""

from pathlib import Path

import pytest


@pytest.fixture
def client(_isolate_clio_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    from clio_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN
    return TestClient(app, headers={_SESSION_HEADER_NAME: _SESSION_TOKEN})


def test_profile_file_round_trip_and_browse(client):
    written = client.put(
        "/api/profiles/default/file",
        params={"path": "blueprints/release.md"},
        json={"content": "# Release\n"},
    )
    assert written.status_code == 200, written.text
    read = client.get(
        "/api/profiles/default/file",
        params={"path": "blueprints/release.md"},
    )
    assert read.status_code == 200
    assert read.json()["content"] == "# Release\n"
    listing = client.get(
        "/api/profiles/default/files", params={"path": "blueprints"}
    )
    assert listing.status_code == 200
    assert [entry["name"] for entry in listing.json()["entries"]] == ["release.md"]


@pytest.mark.parametrize("path", ["../outside.md", ".env", "nested/.secret.md", "state.db"])
def test_profile_file_api_rejects_escape_and_secrets(client, path):
    response = client.get("/api/profiles/default/file", params={"path": path})
    assert response.status_code in {400, 403}


def test_profile_file_api_hides_and_rejects_symlink_escape(client, tmp_path):
    from clio_constants import get_clio_home

    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = get_clio_home() / "escape.md"
    link.symlink_to(outside)

    listing = client.get("/api/profiles/default/files")
    assert listing.status_code == 200
    assert "escape.md" not in {entry["name"] for entry in listing.json()["entries"]}
    response = client.get("/api/profiles/default/file", params={"path": "escape.md"})
    assert response.status_code == 403


def test_profile_builder_validates_reasoning(client):
    bad = client.put(
        "/api/profiles/default/builder", json={"reasoning_effort": "unlimited"}
    )
    assert bad.status_code == 400
    good = client.put(
        "/api/profiles/default/builder",
        json={"soul": "# Test persona\n", "reasoning_effort": "low"},
    )
    assert good.status_code == 200, good.text
    result = client.get("/api/profiles/default/builder")
    assert result.status_code == 200
    assert result.json()["soul"] == "# Test persona\n"
    assert result.json()["reasoning_effort"] == "low"
