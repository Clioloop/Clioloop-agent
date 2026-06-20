"""Tests for agent/music_gen_registry.py — provider registration & active lookup."""

from __future__ import annotations

import pytest

from agent import music_gen_registry
from agent.music_gen_provider import MusicGenProvider


class _FakeProvider(MusicGenProvider):
    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt, **kw):
        return {"success": True, "audio": f"{self._name}://{prompt}"}


@pytest.fixture(autouse=True)
def _reset_registry():
    music_gen_registry._reset_for_tests()
    yield
    music_gen_registry._reset_for_tests()


class TestRegisterProvider:
    def test_register_and_lookup(self):
        provider = _FakeProvider("fake")
        music_gen_registry.register_provider(provider)
        assert music_gen_registry.get_provider("fake") is provider

    def test_rejects_non_provider(self):
        with pytest.raises(TypeError):
            music_gen_registry.register_provider("not a provider")  # type: ignore[arg-type]

    def test_rejects_empty_name(self):
        class Empty(MusicGenProvider):
            @property
            def name(self) -> str:
                return ""

            def generate(self, prompt, **kw):
                return {}

        with pytest.raises(ValueError):
            music_gen_registry.register_provider(Empty())

    def test_reregister_overwrites(self):
        a = _FakeProvider("same")
        b = _FakeProvider("same")
        music_gen_registry.register_provider(a)
        music_gen_registry.register_provider(b)
        assert music_gen_registry.get_provider("same") is b

    def test_list_is_sorted(self):
        music_gen_registry.register_provider(_FakeProvider("zeta"))
        music_gen_registry.register_provider(_FakeProvider("alpha"))
        names = [p.name for p in music_gen_registry.list_providers()]
        assert names == ["alpha", "zeta"]


class TestGetActiveProvider:
    def test_single_provider_autoresolves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        music_gen_registry.register_provider(_FakeProvider("solo"))
        active = music_gen_registry.get_active_provider()
        assert active is not None and active.name == "solo"

    def test_no_provider_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        assert music_gen_registry.get_active_provider() is None

    def test_explicit_config_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        # Write a config with explicit provider
        config_file = tmp_path / "config.yaml"
        config_file.write_text("music_gen:\n  provider: beta\n")
        music_gen_registry.register_provider(_FakeProvider("alpha"))
        music_gen_registry.register_provider(_FakeProvider("beta"))
        active = music_gen_registry.get_active_provider()
        assert active is not None and active.name == "beta"

    def test_unavailable_single_provider_not_autoresolved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        music_gen_registry.register_provider(_FakeProvider("nope", available=False))
        active = music_gen_registry.get_active_provider()
        assert active is None

    def test_explicit_config_returns_even_if_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLIO_HOME", str(tmp_path))
        config_file = tmp_path / "config.yaml"
        config_file.write_text("music_gen:\n  provider: ghost\n")
        music_gen_registry.register_provider(_FakeProvider("ghost", available=False))
        active = music_gen_registry.get_active_provider()
        # Explicit config wins — provider returned even if unavailable
        # so the tool can surface a precise error
        assert active is not None and active.name == "ghost"