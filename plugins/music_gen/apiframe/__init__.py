"""
Apiframe (Suno V5) Music Generation Provider
=============================================

Backend plugin for music generation using Suno V5 via the Apiframe API.
Apiframe is an unofficial Suno API wrapper providing REST access to Suno's
V5 model with pay-as-you-go pricing.

Dual-path architecture:
  1. **Managed gateway** (Omni Loop Portal Subscription): Max-plan users
     route through the portal's gateway proxy (vendor ``clioloop-music``).
     The portal swaps the user's token for the house API key and meters
     usage against their plan. No API key needed from the user.
  2. **Direct API key** (BYO): User sets ``APIFRAME_API_KEY`` env var.
     Calls go directly to ``https://api.apiframe.ai/v2``. No metering.

The plugin checks the managed gateway first; falls back to direct API key.

Supports:
- Text-to-music generation (prompt describes the song)
- Custom lyrics (prompt is the lyrics, custom_mode=true)
- Instrumental-only mode
- Vocal gender selection (male/female)
- Style and negative tags
- Style weight and weirdness controls
- Suno V5 and V5.5 model versions
- Returns 2 tracks per generation (Suno default)
- Follow-up actions: extend, cover, add_vocals, stems
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from agent.music_gen_provider import (
    MusicGenProvider,
    DEFAULT_OUTPUT_FORMAT,
    error_response,
    save_url_audio,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENDOR = "clioloop-music"
APIFRAME_BASE_URL = "https://api.apiframe.ai/v2"
POLL_INTERVAL = 3  # seconds between polling
POLL_TIMEOUT = 300  # max seconds to wait for job completion

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

APIFRAME_MODELS: List[Dict[str, Any]] = [
    {
        "id": "suno-v5",
        "display": "Suno V5",
        "speed": "~30s",
        "strengths": "Full songs with vocals, lyrics, instrumentals — best-in-class vocal quality",
        "price": "$0.11/song",
        "max_duration": 240,
    },
    {
        "id": "suno-v5_5",
        "display": "Suno V5.5",
        "speed": "~30s",
        "strengths": "Latest Suno model — improved quality over V5",
        "price": "$0.11/song",
        "max_duration": 240,
    },
]

DEFAULT_MODEL_ID = "suno-v5"

# Map our model IDs to Apiframe's model_version strings
_MODEL_VERSION_MAP = {
    "suno-v5": "V5",
    "suno-v5_5": "V5_5",
}

# Action endpoint path
_ACTION_ENDPOINT = "/music/suno/action"


def _get_api_key() -> Optional[str]:
    """Return the Apiframe API key from env vars, or None."""
    return os.environ.get("APIFRAME_API_KEY")


def _is_managed_ready() -> bool:
    """Check if the managed tool gateway (portal subscription) is ready."""
    try:
        from tools.managed_tool_gateway import is_managed_tool_gateway_ready
        return bool(is_managed_tool_gateway_ready(VENDOR))
    except Exception:
        return False


def _read_managed_token() -> Optional[str]:
    """Read the managed access token for portal gateway."""
    try:
        from tools.managed_tool_gateway import read_managed_access_token
        return read_managed_access_token()
    except Exception:
        return None


def _build_gateway_url() -> Optional[str]:
    """Build the vendor gateway URL for the clioloop-music vendor."""
    try:
        from tools.managed_tool_gateway import build_vendor_gateway_url
        return build_vendor_gateway_url(VENDOR)
    except Exception:
        return None


class ApiframeMusicGenProvider(MusicGenProvider):
    """Suno V5 music generation via Apiframe API."""

    @property
    def name(self) -> str:
        return "apiframe"

    @property
    def display_name(self) -> str:
        return "Apiframe (Suno V5)"

    def is_available(self) -> bool:
        """Available if either managed gateway is ready OR direct API key is set."""
        if _is_managed_ready():
            return True
        return _get_api_key() is not None

    def list_models(self) -> List[Dict[str, Any]]:
        return list(APIFRAME_MODELS)

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL_ID

    def capabilities(self) -> Dict[str, Any]:
        return {
            "max_duration": 240,
            "min_duration": 5,
            "supports_lyrics": True,
            "supports_instrumental": True,
            "supports_extend": True,
            "supports_cover": True,
            "supports_add_vocals": True,
            "supports_stems": True,
            "supports_style": True,
            "supports_vocal_gender": True,
            "supports_title": True,
            "supports_style_weight": True,
            "supports_weirdness": True,
            "supports_auto_lyrics": True,
            "supports_audio_weight": True,
            "supports_continue_at": True,
            "output_formats": ["mp3"],
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "paid",
            "tag": "Suno V5 via Apiframe — $0.11/song",
            "env_vars": [
                {
                    "key": "APIFRAME_API_KEY",
                    "prompt": "Apiframe API key (optional with Omni Loop Portal Subscription)",
                    "url": "https://console.apiframe.ai/signup",
                },
            ],
        }

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        action: str = "generate",
        # Generation params
        lyrics: Optional[str] = None,
        instrumental: Optional[bool] = None,
        style: Optional[str] = None,
        negative_tags: Optional[str] = None,
        vocal_gender: Optional[str] = None,
        title: Optional[str] = None,
        style_weight: Optional[float] = None,
        weirdness: Optional[float] = None,
        auto_lyrics: Optional[bool] = None,
        # Follow-up action params
        parent_job_id: Optional[str] = None,
        track_index: Optional[int] = None,
        track_id: Optional[str] = None,
        # Extend-specific
        continue_at: Optional[int] = None,
        # Cover-specific
        audio_weight: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate music or perform a follow-up action using Suno V5 via Apiframe.

        Tries managed gateway first (portal subscription), then falls back
        to direct API key.
        """
        resolved_model = model or DEFAULT_MODEL_ID

        # Validate model
        known_models = {m["id"] for m in APIFRAME_MODELS}
        if resolved_model not in known_models:
            return error_response(
                error=f"Unknown model '{resolved_model}'. Available: {', '.join(sorted(known_models))}",
                error_type="invalid_model",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )

        # Validate action-specific requirements
        if action != "generate":
            if not parent_job_id:
                return error_response(
                    error=f"parent_job_id is required for action '{action}'",
                    error_type="missing_required_param",
                    provider=self.name,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                )
            if track_index is None and not track_id:
                return error_response(
                    error=f"Either track_index (1 or 2) or track_id is required for action '{action}'",
                    error_type="missing_required_param",
                    provider=self.name,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                )

            return self._execute_action(
                prompt=prompt,
                resolved_model=resolved_model,
                action=action,
                lyrics=lyrics,
                style=style,
                negative_tags=negative_tags,
                title=title,
                parent_job_id=parent_job_id,
                track_index=track_index,
                track_id=track_id,
                continue_at=continue_at,
                audio_weight=audio_weight,
            )

        # Action = "generate"
        # Try managed gateway first
        if _is_managed_ready():
            logger.debug("music_gen: using managed gateway (portal subscription)")
            return self._generate_via_gateway(
                prompt=prompt,
                resolved_model=resolved_model,
                lyrics=lyrics,
                instrumental=instrumental,
                style=style,
                negative_tags=negative_tags,
                vocal_gender=vocal_gender,
                title=title,
                style_weight=style_weight,
                weirdness=weirdness,
                auto_lyrics=auto_lyrics,
            )

        # Fall back to direct API key
        api_key = _get_api_key()
        if api_key is None:
            return error_response(
                error=(
                    "No music generation backend available. Either:\n"
                    "1. Subscribe to Omni Loop Portal Max plan for managed music generation, or\n"
                    "2. Set APIFRAME_API_KEY env var (get one at https://console.apiframe.ai/signup)"
                ),
                error_type="missing_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )

        logger.debug("music_gen: using direct APIFRAME_API_KEY")
        return self._generate_direct(
            prompt=prompt,
            api_key=api_key,
            resolved_model=resolved_model,
            lyrics=lyrics,
            instrumental=instrumental,
            style=style,
            negative_tags=negative_tags,
            vocal_gender=vocal_gender,
            title=title,
            style_weight=style_weight,
            weirdness=weirdness,
            auto_lyrics=auto_lyrics,
        )

    # -----------------------------------------------------------------------
    # Generation — direct API key path
    # -----------------------------------------------------------------------

    def _generate_direct(
        self,
        *,
        prompt: str,
        api_key: str,
        resolved_model: str,
        lyrics: Optional[str],
        instrumental: Optional[bool],
        style: Optional[str],
        negative_tags: Optional[str],
        vocal_gender: Optional[str],
        title: Optional[str],
        style_weight: Optional[float],
        weirdness: Optional[float],
        auto_lyrics: Optional[bool],
    ) -> Dict[str, Any]:
        """Generate music via direct Apiframe API call."""
        import requests

        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

        # Build request body
        body = self._build_generate_body(
            prompt=prompt,
            resolved_model=resolved_model,
            lyrics=lyrics,
            instrumental=instrumental,
            style=style,
            negative_tags=negative_tags,
            vocal_gender=vocal_gender,
            title=title,
            style_weight=style_weight,
            weirdness=weirdness,
            auto_lyrics=auto_lyrics,
        )

        # Submit generation
        try:
            resp = requests.post(
                f"{APIFRAME_BASE_URL}/music/generate",
                headers=headers,
                json=body,
                timeout=30,
            )
        except Exception as exc:
            return error_response(
                error=f"Failed to connect to Apiframe: {exc}",
                error_type="connection_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        if resp.status_code == 402:
            return error_response(
                error="Insufficient Apiframe credits. Top up at https://console.apiframe.ai",
                error_type="insufficient_credits",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )
        if resp.status_code == 401:
            return error_response(
                error="Invalid APIFRAME_API_KEY. Check your key at https://console.apiframe.ai",
                error_type="invalid_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )
        if resp.status_code != 202:
            return error_response(
                error=f"Apiframe API error: {resp.status_code} {resp.text[:200]}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        job_id = resp.json().get("jobId")
        if not job_id:
            return error_response(
                error=f"Apiframe returned no jobId: {resp.text[:200]}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        # Poll for completion
        return self._poll_and_return(
            job_id=job_id,
            headers=headers,
            base_url=APIFRAME_BASE_URL,
            prompt=prompt,
            resolved_model=resolved_model,
            action="generate",
            instrumental=instrumental,
        )

    # -----------------------------------------------------------------------
    # Generation — managed gateway path
    # -----------------------------------------------------------------------

    def _generate_via_gateway(
        self,
        *,
        prompt: str,
        resolved_model: str,
        lyrics: Optional[str],
        instrumental: Optional[bool],
        style: Optional[str],
        negative_tags: Optional[str],
        vocal_gender: Optional[str],
        title: Optional[str],
        style_weight: Optional[float],
        weirdness: Optional[float],
        auto_lyrics: Optional[bool],
    ) -> Dict[str, Any]:
        """Generate music via the portal managed gateway (clioloop-music vendor)."""
        import requests

        token = _read_managed_token()
        gateway_url = _build_gateway_url()
        if not token or not gateway_url:
            return error_response(
                error="Managed gateway not available. Set APIFRAME_API_KEY as fallback.",
                error_type="gateway_unavailable",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        gateway_base = gateway_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Build request body — same as direct
        body = self._build_generate_body(
            prompt=prompt,
            resolved_model=resolved_model,
            lyrics=lyrics,
            instrumental=instrumental,
            style=style,
            negative_tags=negative_tags,
            vocal_gender=vocal_gender,
            title=title,
            style_weight=style_weight,
            weirdness=weirdness,
            auto_lyrics=auto_lyrics,
        )

        # Submit via gateway — the portal proxies to Apiframe
        try:
            resp = requests.post(
                f"{gateway_base}/music/generate",
                headers=headers,
                json=body,
                timeout=30,
            )
        except Exception as exc:
            return error_response(
                error=f"Failed to connect to managed gateway: {exc}",
                error_type="connection_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        if resp.status_code != 202:
            return error_response(
                error=f"Managed gateway error: {resp.status_code} {resp.text[:200]}",
                error_type="gateway_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        job_id = resp.json().get("jobId")
        if not job_id:
            return error_response(
                error=f"Gateway returned no jobId: {resp.text[:200]}",
                error_type="gateway_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action="generate",
            )

        # Poll for completion via gateway
        return self._poll_and_return(
            job_id=job_id,
            headers=headers,
            base_url=gateway_base,
            prompt=prompt,
            resolved_model=resolved_model,
            action="generate",
            instrumental=instrumental,
        )

    # -----------------------------------------------------------------------
    # Follow-up actions (extend, cover, add_vocals, stems)
    # -----------------------------------------------------------------------

    def _execute_action(
        self,
        *,
        prompt: str,
        resolved_model: str,
        action: str,
        lyrics: Optional[str],
        style: Optional[str],
        negative_tags: Optional[str],
        title: Optional[str],
        parent_job_id: str,
        track_index: Optional[int],
        track_id: Optional[str],
        continue_at: Optional[int],
        audio_weight: Optional[float],
    ) -> Dict[str, Any]:
        """Execute a follow-up action (extend/cover/add_vocals/stems)."""
        import requests

        # Build the action request body
        body = self._build_action_body(
            action=action,
            parent_job_id=parent_job_id,
            track_index=track_index,
            track_id=track_id,
            prompt=prompt if action in ("extend", "cover", "add_vocals") else "",
            lyrics=lyrics,
            style=style,
            negative_tags=negative_tags,
            title=title,
            continue_at=continue_at,
            audio_weight=audio_weight,
        )

        # Try managed gateway first
        if _is_managed_ready():
            token = _read_managed_token()
            gateway_url = _build_gateway_url()
            if token and gateway_url:
                gateway_base = gateway_url.rstrip("/")
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                base_url = gateway_base
            else:
                return error_response(
                    error="Managed gateway not available. Set APIFRAME_API_KEY as fallback.",
                    error_type="gateway_unavailable",
                    provider=self.name,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                )
        else:
            api_key = _get_api_key()
            if api_key is None:
                return error_response(
                    error=(
                        "No music generation backend available. Either:\n"
                        "1. Subscribe to Omni Loop Portal Max plan, or\n"
                        "2. Set APIFRAME_API_KEY env var"
                    ),
                    error_type="missing_api_key",
                    provider=self.name,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                )
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            }
            base_url = APIFRAME_BASE_URL

        # Submit action
        try:
            resp = requests.post(
                f"{base_url}{_ACTION_ENDPOINT}",
                headers=headers,
                json=body,
                timeout=30,
            )
        except Exception as exc:
            return error_response(
                error=f"Failed to connect to Apiframe: {exc}",
                error_type="connection_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )

        if resp.status_code == 402:
            return error_response(
                error="Insufficient Apiframe credits. Top up at https://console.apiframe.ai",
                error_type="insufficient_credits",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )
        if resp.status_code == 401:
            return error_response(
                error="Invalid API key. Check your credentials.",
                error_type="invalid_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )
        if resp.status_code == 409:
            try:
                err_detail = resp.json().get("error", resp.text[:200])
            except Exception:
                err_detail = resp.text[:200]
            return error_response(
                error=f"Apiframe action '{action}' rejected (409): {err_detail}. "
                      f"This may happen if the parent job is not a Suno generation "
                      f"(e.g. stems results cannot be parents) or if continue_at "
                      f"exceeds the track duration.",
                error_type="action_conflict",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )
        if resp.status_code != 202:
            return error_response(
                error=f"Apiframe API error: {resp.status_code} {resp.text[:200]}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )

        job_id = resp.json().get("jobId")
        if not job_id:
            return error_response(
                error=f"Apiframe returned no jobId: {resp.text[:200]}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                action=action,
            )

        # Poll for completion
        return self._poll_and_return(
            job_id=job_id,
            headers=headers,
            base_url=base_url,
            prompt=prompt,
            resolved_model=resolved_model,
            action=action,
            instrumental=None,
            parent_job_id=parent_job_id,
        )

    # -----------------------------------------------------------------------
    # Request body builders
    # -----------------------------------------------------------------------

    def _build_generate_body(
        self,
        *,
        prompt: str,
        resolved_model: str,
        lyrics: Optional[str],
        instrumental: Optional[bool],
        style: Optional[str],
        negative_tags: Optional[str],
        vocal_gender: Optional[str],
        title: Optional[str],
        style_weight: Optional[float],
        weirdness: Optional[float],
        auto_lyrics: Optional[bool],
    ) -> Dict[str, Any]:
        """Build the Apiframe /music/generate request body."""
        model_version = _MODEL_VERSION_MAP.get(resolved_model, "V5")

        # If lyrics are provided, use custom mode (prompt = lyrics)
        if lyrics:
            suno_params: Dict[str, Any] = {
                "custom_mode": True,
                "model_version": model_version,
                "prompt": lyrics[:5000],
            }
            if instrumental is not None:
                suno_params["instrumental"] = bool(instrumental)
            if style:
                suno_params["style"] = style[:1000]
            if negative_tags:
                suno_params["negative_tags"] = negative_tags[:500]
            if vocal_gender and vocal_gender in ("m", "f"):
                suno_params["vocal_gender"] = vocal_gender
            if title:
                suno_params["title"] = title[:80]
            if style_weight is not None:
                suno_params["style_weight"] = max(0.0, min(1.0, float(style_weight)))
            if weirdness is not None:
                suno_params["weirdness_constraint"] = max(0.0, min(1.0, float(weirdness)))
            if auto_lyrics is not None:
                suno_params["auto_lyrics"] = bool(auto_lyrics)

            return {
                "prompt": lyrics[:5000],
                "model": "suno",
                "sunoParams": suno_params,
            }

        # Standard mode — prompt is a song description
        suno_params = {
            "custom_mode": False,
            "model_version": model_version,
        }
        if instrumental is not None:
            suno_params["instrumental"] = bool(instrumental)
        if style:
            suno_params["style"] = style[:1000]
        if negative_tags:
            suno_params["negative_tags"] = negative_tags[:500]
        if vocal_gender and vocal_gender in ("m", "f"):
            suno_params["vocal_gender"] = vocal_gender
        if title:
            suno_params["title"] = title[:80]
        if style_weight is not None:
            suno_params["style_weight"] = max(0.0, min(1.0, float(style_weight)))
        if weirdness is not None:
            suno_params["weirdness_constraint"] = max(0.0, min(1.0, float(weirdness)))

        return {
            "prompt": prompt[:500],  # Suno limits to 500 chars in non-custom mode
            "model": "suno",
            "sunoParams": suno_params,
        }

    def _build_action_body(
        self,
        *,
        action: str,
        parent_job_id: str,
        track_index: Optional[int],
        track_id: Optional[str],
        prompt: str = "",
        lyrics: Optional[str] = None,
        style: Optional[str] = None,
        negative_tags: Optional[str] = None,
        title: Optional[str] = None,
        continue_at: Optional[int] = None,
        audio_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build the Apiframe /music/suno/action request body."""
        body: Dict[str, Any] = {
            "parentJobId": parent_job_id,
            "action": action,
        }

        # Track identification: prefer track_id if provided, else index
        if track_id:
            body["trackId"] = track_id
        elif track_index is not None:
            body["index"] = int(track_index)

        if action == "extend":
            if continue_at is not None:
                body["continueAt"] = float(continue_at)
            # prompt for extend = lyrics (if parent was custom) or description
            if lyrics:
                body["prompt"] = lyrics[:5000]
            elif prompt:
                body["prompt"] = prompt[:5000]
            if style:
                body["style"] = style[:1000]
            if negative_tags:
                body["negative_tags"] = negative_tags[:500]
            if title:
                body["title"] = title[:80]

        elif action == "cover":
            if lyrics:
                body["prompt"] = lyrics[:5000]
            elif prompt:
                body["prompt"] = prompt[:5000]
            if style:
                body["style"] = style[:1000]
            if negative_tags:
                body["negative_tags"] = negative_tags[:500]
            if title:
                body["title"] = title[:80]
            if audio_weight is not None:
                body["audio_weight"] = max(0.0, min(1.0, float(audio_weight)))

        elif action == "add_vocals":
            # prompt is required for add_vocals — it's the lyrics to sing
            if lyrics:
                body["prompt"] = lyrics[:5000]
            elif prompt:
                body["prompt"] = prompt[:5000]
            if style:
                body["style"] = style[:1000]
            if negative_tags:
                body["negative_tags"] = negative_tags[:500]
            if title:
                body["title"] = title[:80]

        elif action == "stems":
            # No additional params for stems — just parentJobId + index/trackId
            pass

        return body

    # -----------------------------------------------------------------------
    # Polling and response building
    # -----------------------------------------------------------------------

    def _poll_and_return(
        self,
        *,
        job_id: str,
        headers: Dict[str, str],
        base_url: str,
        prompt: str,
        resolved_model: str,
        action: str = "generate",
        instrumental: Optional[bool] = None,
        parent_job_id: str = "",
    ) -> Dict[str, Any]:
        """Poll the job status until complete, then download and cache all audio tracks."""
        import requests

        poll_url = f"{base_url}/jobs/{job_id}"

        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            try:
                resp = requests.get(poll_url, headers=headers, timeout=15)
            except Exception as exc:
                logger.warning("music_gen: poll error for job %s: %s", job_id, exc)
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                continue

            if resp.status_code != 200:
                logger.warning("music_gen: poll returned %s for job %s", resp.status_code, job_id)
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                continue

            data = resp.json()
            status = data.get("status", "")

            if status == "COMPLETED":
                tracks = data.get("result", {}).get("tracks", [])
                if not tracks:
                    return error_response(
                        error="Apiframe returned no tracks in completed job",
                        error_type="empty_response",
                        provider=self.name,
                        model=resolved_model,
                        prompt=prompt,
                        action=action,
                    )

                # Download and cache ALL tracks
                all_tracks_data: List[Dict[str, Any]] = []
                for idx, track in enumerate(tracks):
                    track_audio_url = track.get("audioUrl")
                    track_title = track.get("title")
                    track_duration = track.get("duration", 0)
                    track_id = track.get("id", "")

                    if not track_audio_url:
                        logger.warning(
                            "music_gen: track %d has no audioUrl, skipping", idx
                        )
                        continue

                    # Download audio to local cache (CDN URLs expire after 90 days)
                    try:
                        cached_path = save_url_audio(
                            track_audio_url,
                            prefix="suno" if action == "generate" else f"suno_{action}",
                        )
                        audio_path = str(cached_path)
                    except Exception as exc:
                        logger.warning("music_gen: failed to cache track %d: %s — using URL", idx, exc)
                        audio_path = track_audio_url

                    track_entry: Dict[str, Any] = {
                        "id": track_id,
                        "audio": audio_path,
                        "title": track_title or "",
                        "duration": int(track_duration) if track_duration else 0,
                        "track_index": idx + 1,
                    }
                    if track.get("imageUrl"):
                        track_entry["cover_art_url"] = track["imageUrl"]
                    if track.get("tags"):
                        track_entry["tags"] = track["tags"]

                    all_tracks_data.append(track_entry)

                if not all_tracks_data:
                    return error_response(
                        error="All tracks had no audioUrl",
                        error_type="empty_response",
                        provider=self.name,
                        model=resolved_model,
                        prompt=prompt,
                        action=action,
                    )

                # Use the first track as primary
                primary = all_tracks_data[0]
                primary_audio = primary["audio"]
                primary_duration = primary["duration"]
                primary_track_id = primary["id"]
                primary_track_index = primary["track_index"]

                # Build follow-up hint
                follow_up_hint = self._build_follow_up_hint(action, job_id, primary_track_index)

                # Build extra metadata
                extra: Dict[str, Any] = {}
                if primary.get("title"):
                    extra["title"] = primary["title"]
                if primary.get("tags"):
                    extra["tags"] = primary["tags"]
                if primary.get("cover_art_url"):
                    extra["cover_art_url"] = primary["cover_art_url"]

                return success_response(
                    audio=primary_audio,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                    duration=primary_duration,
                    instrumental=bool(instrumental) if instrumental else False,
                    provider=self.name,
                    job_id=job_id,
                    track_id=primary_track_id,
                    track_index=primary_track_index,
                    all_tracks=all_tracks_data,
                    parent_job_id=parent_job_id,
                    follow_up_hint=follow_up_hint,
                    extra=extra,
                )

            if status == "FAILED":
                error_msg = data.get("error", "Generation failed")
                return error_response(
                    error=f"Apiframe {action} failed: {error_msg}",
                    error_type="generation_failed",
                    provider=self.name,
                    model=resolved_model,
                    prompt=prompt,
                    action=action,
                )

            # Still in progress — wait and retry
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        return error_response(
            error=f"Timed out after {POLL_TIMEOUT}s waiting for music {action}",
            error_type="timeout",
            provider=self.name,
            model=resolved_model,
            prompt=prompt,
            action=action,
        )

    def _build_follow_up_hint(self, action: str, job_id: str, track_index: int) -> str:
        """Build a hint string telling the agent what follow-up actions are available."""
        if action == "stems":
            return (
                "Stems are terminal — they cannot be used as parent for further "
                "actions. Both vocals and instrumental files have been delivered."
            )

        actions = []
        if action == "generate":
            actions = ["extend", "cover", "add vocals (if instrumental)", "stems"]
        elif action in ("extend", "cover", "add_vocals"):
            actions = ["extend", "cover", "stems"]

        hint = (
            f"Track {track_index} from job {job_id} can be used for follow-up actions: "
            f"{', '.join(actions)}. Use action='extend' with parent_job_id='{job_id}' "
            f"and track_index={track_index} to extend, action='cover' to re-style, "
            f"action='stems' to split into vocals + instrumental."
        )
        return hint


def register(ctx) -> None:
    ctx.register_music_gen_provider(ApiframeMusicGenProvider())