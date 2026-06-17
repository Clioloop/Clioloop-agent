#!/usr/bin/env python3
"""Supertonic premium TTS server for the Omni Loop Portal.

Exposes an OpenAI-compatible ``POST /v1/audio/speech`` endpoint backed by
Supertone's Supertonic-3 local ONNX model, so the portal's tool gateway
(vendor ``openai-audio``) can serve studio-quality voices to entitled
subscribers without any per-character vendor bill.

Request body (OpenAI dialect — unknown fields ignored):
    {"model": "...", "input": "text", "voice": "F1", "speed": 1.05,
     "response_format": "mp3"|"wav"|"opus"}

Auth is the portal's job — this server binds to localhost only and trusts
the gateway in front of it.

Run: python3 supertonic_server.py [port]   (default 8077)
Deps: pip install supertonic soundfile  (+ ffmpeg for mp3/opus output)
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from supertonic import TTS

MODEL = "supertonic-3"
DEFAULT_VOICE = "F1"
MAX_INPUT_CHARS = 5000

_engine = None
_styles: dict = {}
_lock = threading.Lock()


def engine() -> TTS:
    global _engine
    with _lock:
        if _engine is None:
            print(f"[supertonic] loading {MODEL}…", flush=True)
            _engine = TTS(model=MODEL)
            print("[supertonic] ready", flush=True)
        return _engine


def style_for(voice: str):
    with _lock:
        if voice not in _styles:
            _styles[voice] = _engine.get_voice_style(voice)
        return _styles[voice]


def synthesize(text: str, voice: str, speed: float, fmt: str) -> tuple[bytes, str]:
    eng = engine()
    try:
        style = style_for(voice)
    except Exception:
        style = style_for(DEFAULT_VOICE)
    wav, _sr = eng.synthesize(text, style, speed=speed)

    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "out.wav"
        eng.save_audio(wav, str(wav_path))
        if fmt == "wav" or not shutil.which("ffmpeg"):
            return wav_path.read_bytes(), "audio/wav"
        out_path = Path(td) / f"out.{fmt}"
        subprocess.run(
            ["ffmpeg", "-i", str(wav_path), "-y", "-loglevel", "error", str(out_path)],
            check=True, timeout=60,
        )
        mime = {"mp3": "audio/mpeg", "opus": "audio/ogg", "flac": "audio/flac"}.get(fmt, "application/octet-stream")
        return out_path.read_bytes(), mime


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health", "/v1/health"):
            body = json.dumps({"ok": True, "model": MODEL}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.path.startswith("/v1/audio/speech"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = str(payload.get("input") or "").strip()[:MAX_INPUT_CHARS]
            if not text:
                raise ValueError("input is required")
            voice = str(payload.get("voice") or DEFAULT_VOICE)
            # OpenAI voice names aren't Supertonic styles — map the common
            # ones onto our two house voices so default configs just work.
            voice_map = {
                "alloy": "F1", "nova": "F1", "shimmer": "F1", "coral": "F1",
                "echo": "M1", "onyx": "M1", "fable": "M1", "ash": "M1",
            }
            voice = voice_map.get(voice.lower(), voice)
            speed = float(payload.get("speed") or 1.05)
            fmt = str(payload.get("response_format") or "mp3").lower()
            audio, mime = synthesize(text, voice, speed, fmt)
        except Exception as exc:
            body = json.dumps({"error": {"message": str(exc), "type": "invalid_request_error"}}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, fmt, *args):
        print("[supertonic]", fmt % args, flush=True)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8077
    engine()  # warm the model before accepting traffic
    print(f"[supertonic] listening on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
