from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_optional_manifests_are_disabled_by_default():
    import yaml
    manifests = [
        "plugins/platforms/buzz/plugin.yaml", "plugins/platforms/photon/plugin.yaml",
        "plugins/platforms/raft/plugin.yaml", "plugins/cron_providers/chronos/plugin.yaml",
        "plugins/image_gen/deepinfra/plugin.yaml", "plugins/image_gen/openrouter/plugin.yaml",
        "plugins/video_gen/deepinfra/plugin.yaml",
    ]
    for path in manifests:
        assert yaml.safe_load((ROOT / path).read_text())["kind"] == "standalone"


def test_requirements_checks_fail_closed_without_credentials(monkeypatch):
    for key in ("BUZZ_RELAY_URL", "BUZZ_PRIVATE_KEY", "PHOTON_PROJECT_ID",
                "PHOTON_PROJECT_SECRET", "RAFT_PROFILE", "DEEPINFRA_API_KEY",
                "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    modules = [
        _load("plugins/platforms/buzz/adapter.py", "req_buzz"),
        _load("plugins/platforms/photon/adapter.py", "req_photon"),
        _load("plugins/platforms/raft/adapter.py", "req_raft"),
        _load("plugins/image_gen/deepinfra/__init__.py", "req_di_image"),
        _load("plugins/image_gen/openrouter/__init__.py", "req_or_image"),
        _load("plugins/video_gen/deepinfra/__init__.py", "req_di_video"),
    ]
    assert all(module.check_requirements() is False for module in modules)


def test_platform_foundations_register_and_requirements(monkeypatch):
    cases = [
        ("buzz", {"BUZZ_RELAY_URL": "wss://relay", "BUZZ_PRIVATE_KEY": "x"}),
        ("photon", {"PHOTON_PROJECT_ID": "p", "PHOTON_PROJECT_SECRET": "s"}),
        ("raft", {"RAFT_PROFILE": "agent"}),
    ]
    for name, env in cases:
        mod = _load(f"plugins/platforms/{name}/adapter.py", f"optional_{name}")
        for key, value in env.items(): monkeypatch.setenv(key, value)
        assert mod.validate_config(SimpleNamespace(extra={}))
        ctx = MagicMock(); mod.register(ctx); ctx.register_platform.assert_called_once()
        adapter = getattr(mod, f"{name.title()}Adapter")(SimpleNamespace(extra={}))
        result = asyncio.run(adapter.send("room", "hello"))
        assert result.success and adapter.outbox[0]["content"] == "hello"


def test_deepinfra_image_mocked_sdk(monkeypatch, tmp_path):
    mod = _load("plugins/image_gen/deepinfra/__init__.py", "optional_di_image")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "key")
    monkeypatch.setenv("DEEPINFRA_IMAGE_MODEL", "vendor/model")
    fake_client = MagicMock()
    fake_client.images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json="aW1hZ2U=", url=None)]
    )
    fake_openai = MagicMock(); fake_openai.OpenAI.return_value = fake_client
    with patch.dict("sys.modules", {"openai": fake_openai}), patch.object(mod, "save_b64_image", return_value=tmp_path / "x.png"):
        result = mod.DeepInfraImageGenProvider().generate("cat")
    assert result["success"] and fake_openai.OpenAI.call_args.kwargs["base_url"].endswith("/v1/openai")


def test_openrouter_image_mocked_http(monkeypatch, tmp_path):
    mod = _load("plugins/image_gen/openrouter/__init__.py", "optional_or_image")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    response = MagicMock(); response.json.return_value = {"choices": [{"message": {"images": [{"image_url": {"url": "data:image/png;base64,aW1hZ2U="}}]}}]}
    response.raise_for_status.return_value = None
    with patch("requests.post", return_value=response) as post, patch.object(mod, "save_b64_image", return_value=tmp_path / "x.png"):
        result = mod.OpenRouterImageGenProvider().generate("cat", image_url="https://example.test/ref.png")
    assert result["success"]
    assert post.call_args.kwargs["json"]["modalities"] == ["image", "text"]


def test_deepinfra_video_mocked_sdk(monkeypatch, tmp_path):
    mod = _load("plugins/video_gen/deepinfra/__init__.py", "optional_di_video")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "key")
    monkeypatch.setenv("DEEPINFRA_VIDEO_MODEL", "vendor/video")
    job = SimpleNamespace(status="succeeded", id="v1", data=[], error=None)
    fake_client = MagicMock(); fake_client.videos.create.return_value = job
    fake_client.videos.download_content.return_value.read.return_value = b"mp4"
    fake_openai = MagicMock(); fake_openai.OpenAI.return_value = fake_client
    with patch.dict("sys.modules", {"openai": fake_openai}), patch.object(mod, "save_bytes_video", return_value=tmp_path / "x.mp4"):
        result = mod.DeepInfraVideoGenProvider().generate("move")
    assert result["success"] and result["video"].endswith("x.mp4")
