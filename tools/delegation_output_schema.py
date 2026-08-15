"""JSON Schema contracts for delegated child final responses.

A contract is appended to child context, validated locally, and retried at
most once with the exact validation errors. Schema-less delegations are
unchanged.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
MAX_SCHEMA_RETRIES = 1


def coerce_output_schema(raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None, "output_schema must be a JSON Schema object, got a non-JSON string."
    if not isinstance(raw, dict):
        return None, f"output_schema must be a JSON Schema object, got {type(raw).__name__}."
    try:
        from jsonschema.validators import validator_for
        validator_for(raw).check_schema(raw)
    except ImportError:
        logger.debug("jsonschema unavailable; skipping schema meta-validation")
    except Exception as exc:
        return None, f"output_schema is not a valid JSON Schema: {exc}"
    return raw, None


def append_output_contract(context: Optional[str], schema: Dict[str, Any]) -> str:
    block = (
        "OUTPUT CONTRACT (machine-validated):\n"
        "Your FINAL response must be a single JSON value validating against "
        "this JSON Schema. Do not add prose outside the JSON.\n"
        + json.dumps(schema, indent=2, ensure_ascii=False)
    )
    base = (context or "").rstrip()
    return f"{base}\n\n{block}" if base else block


def extract_json_candidate(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()
        if raw.lower().startswith("json\n"):
            raw = raw.split("\n", 1)[1]
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = raw.find(opener), raw.rfind(closer)
        if start >= 0 and end > start:
            return raw[start : end + 1]
    return raw


def validate_output(text: str, schema: Dict[str, Any]) -> Tuple[bool, List[str], Any]:
    candidate = extract_json_candidate(text)
    try:
        parsed = json.loads(candidate)
    except (TypeError, ValueError) as exc:
        return False, [f"Response is not valid JSON: {exc}"], None
    try:
        from jsonschema.validators import validator_for
    except ImportError:
        return True, [], parsed
    validator = validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(parsed), key=lambda e: list(e.absolute_path))
    rendered: List[str] = []
    for error in errors[:10]:
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        rendered.append(f"{path}: {error.message}")
    return not rendered, rendered, parsed


def build_retry_message(errors: List[str]) -> str:
    return (
        "Your previous final response failed the OUTPUT CONTRACT. Validation errors:\n"
        + "\n".join(f"- {error}" for error in errors)
        + "\nReply with ONLY corrected JSON. Do not repeat the schema or add prose."
    )
