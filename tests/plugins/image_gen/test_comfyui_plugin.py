"""Tests for the ComfyUI image generation plugin."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ── Import helpers ──────────────────────────────────────────────────────────

def _import_provider():
    """Import the ComfyUI provider, handling path setup."""
    import sys
    sys.path.insert(0, "/home/gjw/Clioloop-agent-main")
    from plugins.image_gen.comfyui import (
        ComfyUIImageGenProvider,
        _build_txt2img_workflow,
        _get_server_url,
        _get_checkpoint,
        _load_negative_prompt,
        _DIMENSIONS,
        DEFAULT_SERVER_URL,
        DEFAULT_MODEL_ID,
    )
    return (
        ComfyUIImageGenProvider,
        _build_txt2img_workflow,
        _get_server_url,
        _get_checkpoint,
        _load_negative_prompt,
        _DIMENSIONS,
        DEFAULT_SERVER_URL,
        DEFAULT_MODEL_ID,
    )


# ── Tests ───────────────────────────────────────────────────────────────────


class TestProviderMetadata:
    """Test provider identity and metadata."""

    def test_name(self):
        items = _import_provider()
        Provider = items[0]
        p = Provider()
        assert p.name == "comfyui"

    def test_display_name(self):
        items = _import_provider()
        Provider = items[0]
        p = Provider()
        assert p.display_name == "ComfyUI"

    def test_list_models(self):
        items = _import_provider()
        Provider = items[0]
        model_id = items[7]
        p = Provider()
        models = p.list_models()
        assert len(models) == 1
        assert models[0]["id"] == model_id

    def test_default_model(self):
        items = _import_provider()
        Provider = items[0]
        model_id = items[7]
        p = Provider()
        assert p.default_model() == model_id

    def test_setup_schema(self):
        items = _import_provider()
        Provider = items[0]
        p = Provider()
        schema = p.get_setup_schema()
        assert schema["name"] == "ComfyUI"
        assert schema["badge"] == "local"
        assert any(v["key"] == "COMFYUI_URL" for v in schema["env_vars"])


class TestServerUrl:
    """Test server URL resolution."""

    def test_default_url(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_URL", raising=False)
        items = _import_provider()
        get_url = items[2]
        default_url = items[6]
        assert get_url() == default_url

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_URL", "http://192.168.1.100:8188")
        items = _import_provider()
        get_url = items[2]
        assert get_url() == "http://192.168.1.100:8188"

    def test_env_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_URL", "http://localhost:8188/")
        items = _import_provider()
        get_url = items[2]
        assert get_url() == "http://localhost:8188"


class TestCheckpoint:
    """Test checkpoint resolution."""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_CHECKPOINT", "sd_xl_base.safetensors")
        items = _import_provider()
        get_ckpt = items[3]
        assert get_ckpt() == "sd_xl_base.safetensors"

    def test_default_empty(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_CHECKPOINT", raising=False)
        items = _import_provider()
        get_ckpt = items[3]
        assert get_ckpt() == ""


class TestWorkflowBuilder:
    """Test the built-in txt2img workflow template."""

    def test_workflow_has_required_nodes(self):
        items = _import_provider()
        build_wf = items[1]
        wf = build_wf(
            prompt="a cat",
            negative_prompt="blurry",
            width=1024,
            height=1024,
            checkpoint="model.safetensors",
            seed=42,
        )
        # Must have KSampler, CheckpointLoaderSimple, EmptyLatentImage,
        # CLIPTextEncode (x2), VAEDecode, SaveImage
        class_types = {n["class_type"] for n in wf.values()}
        assert "KSampler" in class_types
        assert "CheckpointLoaderSimple" in class_types
        assert "EmptyLatentImage" in class_types
        assert "CLIPTextEncode" in class_types
        assert "VAEDecode" in class_types
        assert "SaveImage" in class_types

    def test_prompt_injected(self):
        items = _import_provider()
        build_wf = items[1]
        wf = build_wf(
            prompt="a beautiful landscape",
            negative_prompt="blurry, low quality",
            width=1024,
            height=768,
            checkpoint="model.safetensors",
            seed=123,
        )
        # Find the CLIPTextEncode nodes
        clip_nodes = [
            (nid, n) for nid, n in wf.items()
            if n["class_type"] == "CLIPTextEncode"
        ]
        texts = [n["inputs"]["text"] for _, n in clip_nodes]
        assert "a beautiful landscape" in texts
        assert "blurry, low quality" in texts

    def test_dimensions_injected(self):
        items = _import_provider()
        build_wf = items[1]
        wf = build_wf(
            prompt="test",
            negative_prompt="",
            width=768,
            height=1024,
            checkpoint="model.safetensors",
            seed=1,
        )
        latent = [n for n in wf.values() if n["class_type"] == "EmptyLatentImage"][0]
        assert latent["inputs"]["width"] == 768
        assert latent["inputs"]["height"] == 1024

    def test_seed_injected(self):
        items = _import_provider()
        build_wf = items[1]
        wf = build_wf(
            prompt="test",
            negative_prompt="",
            width=512,
            height=512,
            checkpoint="model.safetensors",
            seed=999,
        )
        sampler = [n for n in wf.values() if n["class_type"] == "KSampler"][0]
        assert sampler["inputs"]["seed"] == 999

    def test_checkpoint_injected(self):
        items = _import_provider()
        build_wf = items[1]
        wf = build_wf(
            prompt="test",
            negative_prompt="",
            width=512,
            height=512,
            checkpoint="sdxl.safetensors",
            seed=1,
        )
        loader = [n for n in wf.values() if n["class_type"] == "CheckpointLoaderSimple"][0]
        assert loader["inputs"]["ckpt_name"] == "sdxl.safetensors"


class TestDimensions:
    """Test aspect ratio → dimension mapping."""

    def test_landscape(self):
        items = _import_provider()
        dims = items[5]
        w, h = dims["landscape"]
        assert w > h

    def test_square(self):
        items = _import_provider()
        dims = items[5]
        w, h = dims["square"]
        assert w == h

    def test_portrait(self):
        items = _import_provider()
        dims = items[5]
        w, h = dims["portrait"]
        assert w < h


class TestIsAvailable:
    """Test the is_available() method."""

    def test_unavailable_when_server_down(self, monkeypatch):
        items = _import_provider()
        Provider = items[0]
        monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
        p = Provider()
        assert p.is_available() is False

    def test_available_when_server_responds(self, monkeypatch):
        items = _import_provider()
        Provider = items[0]
        p = Provider()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.get", return_value=mock_response):
            assert p.is_available() is True


class TestGenerateErrors:
    """Test error handling in generate()."""

    def test_empty_prompt(self, monkeypatch):
        items = _import_provider()
        Provider = items[0]
        p = Provider()
        result = p.generate("", aspect_ratio="square")
        assert result["success"] is False
        assert "Prompt is required" in result["error"]

    def test_connection_error(self, monkeypatch):
        items = _import_provider()
        Provider = items[0]
        monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
        p = Provider()
        result = p.generate("a cat", aspect_ratio="square")
        assert result["success"] is False
        assert "Could not connect" in result["error"] or "ComfyUI" in result["error"]


class TestRegister:
    """Test plugin registration."""

    def test_register_calls_ctx(self):
        items = _import_provider()
        Provider = items[0]
        ctx = MagicMock()
        register = Provider.__module__ + ".register"
        import importlib
        mod = importlib.import_module("plugins.image_gen.comfyui")
        mod.register(ctx)
        ctx.register_image_gen_provider.assert_called_once()
        provider = ctx.register_image_gen_provider.call_args[0][0]
        assert isinstance(provider, Provider)
        assert provider.name == "comfyui"