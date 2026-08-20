import json

import pytest

from gateway.session_context import clear_session_vars, set_session_vars
from tools import desktop_ui
from tools.desktop_ui_tools import (
    _normalize_preview_target,
    annotate_preview,
    apply_layout,
    close_preview,
    desktop_ui_available,
    drive_preview,
    open_preview,
    read_preview,
)


@pytest.fixture(autouse=True)
def _reset_bridge(monkeypatch):
    monkeypatch.delenv("CLIO_DESKTOP", raising=False)
    desktop_ui.configure_bridge(emit_callback=None, request_callback=None)
    clear_session_vars([])
    yield
    desktop_ui.configure_bridge(emit_callback=None, request_callback=None)
    clear_session_vars([])


def test_preview_target_normalization():
    assert _normalize_preview_target("localhost:5174/app") == "http://localhost:5174/app"
    assert _normalize_preview_target("example.com/docs") == "https://example.com/docs"
    assert _normalize_preview_target("/work/demo.html") == "/work/demo.html"


def test_desktop_tools_fail_closed_off_surface():
    result = json.loads(open_preview("https://example.com"))
    assert "error" in result
    assert "Clio Desktop" in result["error"]


def test_emit_routes_to_current_ui_session(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "1")
    events = []
    desktop_ui.configure_bridge(
        emit_callback=lambda action, sid, payload: events.append((action, sid, payload)) or True,
    )
    tokens = set_session_vars(session_key="stored", ui_session_id="runtime-7")
    try:
        assert desktop_ui_available() is True
        opened = json.loads(open_preview("example.com", "Docs"))
        closed = json.loads(close_preview("example.com"))
        layout = json.loads(apply_layout("review", ["files", "review"]))
    finally:
        clear_session_vars(tokens)

    assert opened["success"] is True
    assert closed["success"] is True
    assert layout["success"] is True
    assert events == [
        ("preview.open", "runtime-7", {"url": "https://example.com", "label": "Docs"}),
        ("preview.close", "runtime-7", {"url": "https://example.com"}),
        ("layout.apply", "runtime-7", {"preset": "review", "panes": ["files", "review"]}),
    ]


def test_bounded_request_round_trip(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "true")
    calls = []

    def request(action, sid, payload, timeout):
        calls.append((action, sid, payload, timeout))
        return {"url": "https://example.com", "text": "page"}

    desktop_ui.configure_bridge(emit_callback=lambda *_: True, request_callback=request)
    tokens = set_session_vars(session_key="stored", ui_session_id="runtime-9")
    try:
        result = json.loads(read_preview(start=-5, count=99999))
    finally:
        clear_session_vars(tokens)

    assert result["success"] is True
    assert result["result"]["text"] == "page"
    assert calls == [("preview.read", "runtime-9", {"start": 0, "count": 20000}, 8.0)]


def test_request_without_renderer_returns_tool_error(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "1")
    tokens = set_session_vars(session_key="stored", ui_session_id="runtime-10")
    try:
        result = json.loads(read_preview())
    finally:
        clear_session_vars(tokens)
    assert "error" in result
    assert "only available in Clio Desktop" in result["error"]


def test_preview_drive_and_annotation_route_to_trusted_renderer(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "1")
    calls = []

    def request(action, sid, payload, timeout):
        calls.append((action, sid, payload, timeout))
        return {"success": True, "acted": payload["action"]}

    desktop_ui.configure_bridge(emit_callback=None, request_callback=request)
    tokens = set_session_vars(session_key="stored", ui_session_id="runtime-preview")
    try:
        driven = json.loads(drive_preview("type", ref="inp-name", text="Ada", submit=True))
        annotated = json.loads(annotate_preview("add", ref="inp-name", label="Author"))
    finally:
        clear_session_vars(tokens)

    assert driven == {"success": True, "acted": "type"}
    assert annotated == {"success": True, "acted": "add"}
    assert calls == [
        (
            "preview.drive",
            "runtime-preview",
            {"action": "type", "ref": "inp-name", "submit": True, "text": "Ada"},
            8.0,
        ),
        (
            "preview.annotate",
            "runtime-preview",
            {"action": "add", "ref": "inp-name", "label": "Author"},
            8.0,
        ),
    ]


def test_trusted_preview_actions_fail_closed_without_a_renderer(monkeypatch):
    monkeypatch.setenv("CLIO_DESKTOP", "1")
    tokens = set_session_vars(session_key="stored", ui_session_id="runtime-missing")
    try:
        driven = json.loads(drive_preview("click", ref="btn-save"))
        annotated = json.loads(annotate_preview("hold"))
    finally:
        clear_session_vars(tokens)

    assert "error" in driven
    assert "Clio Desktop" in driven["error"]
    assert "error" in annotated
