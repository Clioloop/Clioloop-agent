from __future__ import annotations

import re
from pathlib import Path


GATEWAY_TS = Path(__file__).resolve().parents[2] / "portal" / "src" / "lib" / "gateway.ts"


def _vendor_block(source: str, vendor: str) -> str:
    match = re.search(rf'"{re.escape(vendor)}":\s*\{{(?P<body>.*?)\n\s*\}},', source, re.S)
    assert match, f"{vendor} vendor block not found"
    return match.group("body")


def test_clioloop_image_is_image_gen_at_two_cents():
    source = GATEWAY_TS.read_text()
    block = _vendor_block(source, "clioloop-image")

    assert 'service: "image_gen"' in block
    assert "costMicros: 20_000" in block


def test_openai_audio_tts_is_one_cent():
    source = GATEWAY_TS.read_text()
    block = _vendor_block(source, "openai-audio")

    assert 'service: "tts"' in block
    assert "costMicros: 10_000" in block


def test_vidu_is_video_only_for_portal_entitlement():
    source = GATEWAY_TS.read_text()
    block = _vendor_block(source, "vidu")

    assert 'service: "video_gen"' in block
    assert 'keyEnv: "VIDU_API_KEY"' in block
    assert "Authorization: `Token ${key}`" in block


def test_clioloop_image_asset_fetches_are_unmetered():
    source = GATEWAY_TS.read_text()

    assert "export function gatewayRequestCostMicros" in source
    assert 'vendor.id === "clioloop-image"' in source
    assert 'method.toUpperCase() === "POST" && path[0] === "generate"' in source


def test_vidu_generation_metering_is_dynamic_and_marked_up():
    source = GATEWAY_TS.read_text()

    assert "VIDU_MARKED_UP_MICROS_PER_SECOND" in source
    assert '"540p": 42_000' in source
    assert '"720p": 66_000' in source
    assert '"1080p": 78_000' in source
    assert 'path[0] !== "text2video" && path[0] !== "img2video"' in source
    assert "gatewayShouldRecordUsage" in source
